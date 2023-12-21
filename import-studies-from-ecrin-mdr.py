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
hdlr.setLevel(logging.INFO)
hdlr.setFormatter(fmt)

logger.addHandler(hdlr)

ECRIN_URL = 'https://mdr.ecrin-rms.org/mdr/v1'
ECRIN_SPECIFIC_STUDY = f'{ECRIN_URL}/specific-study'
ECRIN_MDR_URL = f'{ECRIN_URL}/study'

BBMRI_ALSO_KNOWN_IN = 'eu_bbmri_eric_also_known_in'
BBMRI_STUDY = 'eu_bbmri_eric_studies'
BBMRI_COLLECTION = 'eu_bbmri_eric_collections'


def get_study_detail(mdr_id):
    """
    Gets from ECRIN MDR the details of the study with id :mdr_id:

    :param mdr_id: Id of the study
    """
    payload = {
        "studyId": mdr_id
    }
    res = requests.post(ECRIN_MDR_URL, json=payload)
    return res.json()


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
        assert min_age['unitName'] == max_age['unitName']
        unit = min_age['unitName']
    elif min_age is not None:
        unit = min_age['unitName']
    elif max_age is not None:
        unit = max_age['unitName']
    else:
        return None
    return mapping[unit]


def create_directory_entities(session, mdr_data, mdr_title, collections_ids):
    """
    Creates in the BBMRI directory the entities corresponding to the study and updates the collections to associate the study.

    In particular, it creates two entities:
     - study, with data of the ECRIN MDR study
     - also_known_in, to link the newly created study to its record in ECRIN MDR.

    It also updates the collections linked to the study with the reference to the newly created study
    """
    also_known_id = f'ecrin-mdr:{mdr_data["id"]}'  # internal bbmri id of the "also_known_entity" corresponding to the study
    study_id = f'bbmri_eric:ID:EXT:{mdr_data["id"]}'  # internal bbmri id of the study

    # It removes old studies' references from collections record
    for cid in collections_ids:
        logger.debug("Resetting collection")
        session.update_one(BBMRI_COLLECTION, cid, 'study', None)

    # it removes the study if already present
    try:
        session.delete(BBMRI_STUDY, study_id)
        logger.debug("Study already present: removing")
    except MolgenisRequestError:
        pass

    # it removes the also_known_in record if already present
    try:
        session.delete(BBMRI_ALSO_KNOWN_IN, also_known_id)
        logger.debug("also_Known_in already present: removing")
    except MolgenisRequestError:
        pass

    # creates the also known record
    also_known = {
        'id': also_known_id,
        'name_system': 'ECRIN MDR',
        'pid': mdr_data["id"],
        'url': f'https://crmdr.org/study/{mdr_data["id"]}',
        'national_node': 'EXT',  # to
        'withdrawn': False,
        'label': mdr_data["displayTitle"]
    }
    logger.debug("Adding also_known_in")
    session.add(BBMRI_ALSO_KNOWN_IN, also_known)

    # creates the study record
    study = {
        'id': study_id,
        'title': mdr_title,
        'description': mdr_data['briefDescription'],
        'type': mdr_data['studyType'],
        'status': mdr_data['studyStatus'],
        'min_age': mdr_data['minAge'].get('value') if mdr_data['minAge'] is not None else None,
        'max_age': mdr_data['maxAge'].get('value') if mdr_data['maxAge'] is not None else None,
        'age_unit': get_age_unit(mdr_data['minAge'], mdr_data['maxAge']),
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
    if study_detail["total"] == 0:
        logger.debug("Couldn't find details for study")
        return False
    else:
        logger.debug("Updating directory for study")
        return create_directory_entities(molgenis_session, study_detail['data'][0], mdr_title, collections_ids)


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
            studies_collections[(match["MDR ID"], match["MDR Title"])].append(
                f"bbmri-eric:ID:{match['BBMRI collection id']}")
        molgenis_session = client.Session(url=args.url)
        molgenis_session.login(args.username, args.password)
        studies_per_id = count_studies_ids(studies_collections)

        for s, c in studies_collections.items():
            if process_study(molgenis_session, s[0], s[1], c) is True:
                successes.append(s[0])
            else:
                failures.append(s[0])

    logger.info("Studies with same id and different title: %s", studies_per_id)
    logger.info("Number of study added: %s" % len(successes))
    logger.info("Number of study failed: %s" % len(failures))
    logger.info("List of failed study: %s" % ", ".join(failures))
