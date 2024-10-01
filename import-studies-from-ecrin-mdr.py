"""
Script that imports the ECRIN MDR studies into the BBMRI Directory.
The studies are associated to one or more collections. When a Study and a Collection are associated it means that
the Colection was created in the context of the Study

It gets in input:
    - a CSV file with three columns mdr_id,mdr_title,collection_id containing the id of the study in ECRIN, its title and
      the id of the corresponding collection in the directory
    - the url of the Directory where to store the data
    - the username and the password of the user with insert rights in the Directory

For each study in the CSV, the script:
  - gets the study information from the ECRIN MDR
  - creates a Study record in the Directory
  - creates an AlsoKnownIn record with the link to the study in ECRIN MDR
  - updates the Collection with the reference to the associated Study
"""

import argparse
import asyncio
import csv
import logging
import os
from collections import defaultdict, Counter, OrderedDict

import requests
from molgenis_emx2_pyclient import client

#
logger = logging.getLogger('ecrin_mdr_importer')
logger.setLevel(logging.DEBUG)

fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

hdlr = logging.StreamHandler()
hdlr.setLevel(logging.DEBUG)
hdlr.setFormatter(fmt)
logger.addHandler(hdlr)

ECRIN_URL = 'https://newmdr.ecrin.org'
ECRIN_STUDY_API_ENDPOINT = f'{ECRIN_URL}/api/Study/AllDetails'
ECRIN_STUDY_URL = f'{ECRIN_URL}/Study'

BBMRI_ALSO_KNOWN_IN = 'AlsoKnownIn'
BBMRI_STUDY = 'Studies'
BBMRI_COLLECTION = 'Collections'


def get_study_details(mdr_id):
    """
    Gets from ECRIN MDR the details of the study with id :mdr_id:

    :param mdr_id: the id of the study
    """
    res = requests.get(f'{ECRIN_STUDY_API_ENDPOINT}/{mdr_id}')
    if res.status_code == 200:
        return res.json()
    else:
        return None


def get_age_unit(min_age, max_age):
    """
    Maps age unit values of MDR to the ones in BBMRI
    """
    mapping = {
        "Years": "YEAR",
        "Months": "MONTH",
        "Weeks": "WEEK"
    }
    if min_age is not None and max_age is not None:
        assert min_age['unit_name'] == max_age['unit_name']
        unit = min_age['unit_name']
    elif min_age is not None:
        unit = min_age['unit_name']
    elif max_age is not None:
        unit = max_age['unit_name']
    else:
        return None
    return mapping[unit]


def get_sex_value(ecrin_gender_eligibility):
    return {
        'Male': 'MALE',
        'Female': 'FEMALE',
        'Not provided': 'NAV',
        'All': ['MALE', 'FEMALE']
    }[ecrin_gender_eligibility]


def create_directory_records(eric_session, mdr_data, mdr_title, collections_ids):
    """
    Creates the records to be stored in Molgenis

    In particular, it creates two records:
     - study, with data of the ECRIN MDR study
     - also_known_in, to link the newly created study to its record in ECRIN MDR.
    It also updates the collections linked to the study with the reference to the newly created study
    """

    also_known_id = f'ecrin-mdr:{mdr_data["id"]}'  # internal bbmri id of the "also_known_entity" corresponding to the study
    study_id = f'bbmri_eric:studyID:{mdr_data["id"]}'  # internal bbmri id of the study

    # creates the also known record
    also_known = {
        'id': also_known_id,
        'name_system': 'ECRIN MDR',
        'pid': mdr_data["id"],
        'url': f'{ECRIN_STUDY_URL}/{mdr_data["id"]}',
        'national_node': 'EXT',
        'withdrawn': False,
        'label': mdr_data["display_title"]
    }

    try:
        number_of_subject = int(mdr_data['study_enrolment'])
    except (ValueError, TypeError):
        number_of_subject = None
    # creates the study record
    sex = get_sex_value(mdr_data['study_gender_elig']['name'])

    study = {
        'id': study_id,
        'title': mdr_title,
        'description': mdr_data['brief_description'],
        'type': mdr_data['study_type']['name'],
        'number_of_subjects': number_of_subject,
        'sex': sex if isinstance(sex, str) else ",".join(sex),
        'age_low': mdr_data['min_age'].get('value') if mdr_data['min_age'] is not None else None,
        'age_high': mdr_data['max_age'].get('value') if mdr_data['max_age'] is not None else None,
        'age_unit': get_age_unit(mdr_data['min_age'], mdr_data['max_age']),
        'also_known': also_known_id,
        'national_node': 'EXT'
    }

    # # Updates the collections with the id of the associated study
    updated_collections = []
    for cid in collections_ids:
        collections = eric_session.get(table='Collections', query_filter=f'id=={cid}', schema='ERIC')
        studies_ids = set(collections[0]['study'].split(','))
        studies_ids.add(study_id)
        collections[0]['study'] = ",".join(studies_ids)
        updated_collections.append(collections[0])

    return {
        'AlsoKnownIn': also_known,
        'Studies': study,
        'Collections': updated_collections
    }


def process_study(eric_session, mdr_id, mdr_title, collections_ids):
    """
    Function to process a study. It gets study details from MDR and create the corresponding records to be upsert in the
    Directory.
    :return: A dict object with keys being the tables of the Directory to be udpated with the records.
    None if the study couldn't be found

    """
    logger.info("Processing study %s" % mdr_id)
    logger.debug("Collections are %s" % collections_ids)
    logger.debug("Getting study detail")
    study_detail = get_study_details(mdr_id)
    if study_detail is None:
        logger.debug("Couldn't find details for study")
        return None
    else:
        logger.info("Updating directory for study")
        return create_directory_records(eric_session, study_detail['full_study'], mdr_title, collections_ids)


def file_exist(file_argument):
    """
    Checks if the file actually exists
    """
    if os.path.exists(file_argument):
        return file_argument
    raise argparse.ArgumentTypeError("File {} does not exist".format(file_argument))


def count_studies_ids(studies):
    """
    Check if there are studies with the same id but different title, in input data
    """
    counter = Counter([s[0] for s in studies])
    return [study_id for study_id in counter if counter[study_id] > 1]


async def main(input_file, url, username, password):
    entities = OrderedDict({
        'AlsoKnownIn': [],
        'Studies': [],
        'Collections': []
    })

    with open(input_file) as f:
        reader = csv.DictReader(f)
        studies_collections = defaultdict(list)

        for match in reader:
            studies_collections[(match["mdr_id"], match["mdr_title"])].append(f"bbmri-eric:ID:{match['collection_id']}")
        studies_with_different_title = count_studies_ids(studies_collections)

        with client.Client(url=url) as emx2_client:
            emx2_client.signin(username, password)
            counter = 0
            for s, c in studies_collections.items():
                if counter > 10:
                    break
                records = process_study(emx2_client, s[0], s[1], c)
                if records is None:
                    logger.error(f"Skipping study {s[0]}")
                else:
                    for k, v in records.items():
                        if isinstance(v, list):
                            entities[k].extend(v)
                        else:
                            entities[k].append(v)
                        counter += 1

            for k, v in entities.items():
                with open(f"{k}.csv", "w") as outfile:
                    fieldnames = list(v[0].keys())
                    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(v)

            await emx2_client.upload_file(file_path='./AlsoKnownIn.csv', schema='ERIC')
            await emx2_client.upload_file(file_path='./Studies.csv', schema='ERIC')
            await emx2_client.upload_file(file_path='./Collections.csv', schema='ERIC')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input-file", dest="input_file", type=file_exist, required=True,
                        help="CSV file with mdr and csv matchings")
    parser.add_argument('--url', '-u', type=str, required=True, help='the url of the BBMRI directory')
    parser.add_argument('--username', '-U', type=str, required=True,
                        help='the user name of the user of the BBMRI directory')
    parser.add_argument('--password', '-P', type=str, required=True,
                        help='the password of the user of the BBMRI directory')

    args = parser.parse_args()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        asyncio.run(main(args.input_file, args.url, args.username, args.password))
    except KeyboardInterrupt:
        pass
