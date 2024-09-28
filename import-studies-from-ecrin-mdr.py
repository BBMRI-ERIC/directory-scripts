"""
Script that imports the ECRIN MDR studies into the BBMRI Directory.
This script works with a version of the BBMRI Directory with the following modifications:
    - addition of the entity `eu_bbmri_eric_studies`
    - addition of the xref attribute `study` to eu_bbmri_collections to link the collection with the study that generated it

It get in input:
    - a CSV file with three columns mdr_id,mdr_title,collection_id containingn the id of the study in ECRIN, its title and
      the id of the corresponding collection in the directory
    - the url of the directory
    - the username and the password of the user with insert rights in the directory

For each study in the CSV, the script:
  - gets the study information from the ECRIN MDR
  - creates a eu_bbmri_eric_studies object in the Directory
  - creates an eu_bbmri_eric_also_known_in record with the link to the study in ECRIN MDR
  - updates the collection with the study and the also_known_in links
"""

import argparse
import csv
import logging
import os
from collections import defaultdict, Counter

import requests
from molgenis import client
from molgenis.client import MolgenisRequestError

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

BBMRI_ALSO_KNOWN_IN = 'eu_bbmri_eric_also_known_in'
BBMRI_STUDY = 'eu_bbmri_eric_studies'
BBMRI_COLLECTION = 'eu_bbmri_eric_collections'


def get_study_detail(mdr_id):
    """
    Gets from ECRIN MDR the details of the study with id :mdr_id:

    :param mdr_id: Id of the study
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
        'All': ['MALE','FEMALE']
    }[ecrin_gender_eligibility]



def create_directory_entities(session, mdr_data, mdr_title, collections_ids):
    """
    Creates in the BBMRI directory the entities corresponding to the study and updates the collections to associate the study.

    In particular, it creates two entities:
     - study, with data of the ECRIN MDR study
     - also_known_in, to link the newly created study to its record in ECRIN MDR.

    It also updates the collections linked to the study with the reference to the newly created study
    """

    also_known_id = f'ecrin-mdr:{mdr_data["id"]}'  # internal bbmri id of the "also_known_entity" corresponding to the study
    old_study_id = f'bbmri_eric:ID:EXT:{mdr_data["id"]}'  # internal bbmri id of the study
    study_id = f'bbmri_eric:ID:{mdr_data["id"]}'  # internal bbmri id of the study

    # It removes old studies' references from collections record
    for cid in collections_ids:
        logger.debug("Resetting collection")
        session.update_one(BBMRI_COLLECTION, cid, 'study', None)

    # it removes the study if already present
    try:
        res = session.delete(BBMRI_STUDY, old_study_id)
        logger.debug("Study %s already present: removing" % study_id)
        logger.debug("Removed response %s" % res.status_code)
        if res.status_code == 204:
            res = session.delete(BBMRI_STUDY, study_id)
            logger.debug("Failed removing old id. Trying new study")
    except MolgenisRequestError as e:
        logger.debug("Removal failed")

    # it removes the also_known_in record if already present
    try:
        session.delete(BBMRI_ALSO_KNOWN_IN, also_known_id)
        logger.debug("also_Known_in already present: removing")
    except MolgenisRequestError as e:
        logger.debug(e)

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
    logger.debug("Adding also_known_in")
    session.add(BBMRI_ALSO_KNOWN_IN, also_known)

    try:
        number_of_subject = int(mdr_data['study_enrolment'])
    except (ValueError, TypeError):
        number_of_subject = None
    # creates the study record
    study = {
        'id': study_id,
        'title': mdr_title,
        'description': mdr_data['brief_description'],
        'type': mdr_data['study_type']['name'],
        'number_of_subjects': number_of_subject,
        'sex': get_sex_value(mdr_data['study_gender_elig']['name']),
        'age_low': mdr_data['min_age'].get('value') if mdr_data['min_age'] is not None else None,
        'age_high': mdr_data['max_age'].get('value') if mdr_data['max_age'] is not None else None,
        'age_unit': get_age_unit(mdr_data['min_age'], mdr_data['max_age']),
        'also_known': also_known_id
    }
    logger.debug("Adding study")
    try:
        session.add(BBMRI_STUDY, study)
    except MolgenisRequestError as err:
        # If some error occurs, it fails
        logger.error("Failed to add the study %s" % study_id)
        logger.error(err)
        return False

    # Updates the collections with the id of the associated study
    logger.debug("Updating study collection")
    for cid in collections_ids:
        session.update_one(BBMRI_COLLECTION, cid, 'study', study_id)
    return True


def process_study(molgenis_session, mdr_id, mdr_title, collections_ids):
    """
    Function to process a study. It gets study details from MDR and create the corresponding entries in the BBMRI directory
    """
    logger.info("Processing study %s" % mdr_id)
    logger.debug("Collections are %s" % collections_ids)
    logger.debug("Getting study detail")
    study_detail = get_study_detail(mdr_id)
    if study_detail is None:
        logger.debug("Couldn't find details for study")
        return False
    else:
        logger.info("Updating directory for study")
        return create_directory_entities(molgenis_session, study_detail['full_study'], mdr_title, collections_ids)


def file_exist(file_argument):
    """
    Checks if the file in input actually exists
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

    with open(args.input_file) as f:
        reader = csv.DictReader(f)
        failures = []
        successes = []
        studies_collections = defaultdict(list)

        for match in reader:
            studies_collections[(match["mdr_id"], match["mdr_title"])].append(
                f"bbmri-eric:ID:{match['collection_id']}")
        molgenis_session = client.Session(url=args.url)
        molgenis_session.login(args.username, args.password)
        studies_per_id = count_studies_ids(studies_collections)
        print(studies_collections)
        for s, c in studies_collections.items():
            if process_study(molgenis_session, s[0], s[1], c) is True:
                successes.append(s[0])
            else:
                failures.append(s[0])

    logger.info("Studies with same id and different title: %s", studies_per_id)
    logger.info("Number of study added: %s" % len(successes))
    logger.info("Number of study failed: %s" % len(failures))
    logger.info("List of failed study: %s" % ", ".join(failures))
