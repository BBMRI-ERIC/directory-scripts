import argparse
import csv
import logging
import os
from collections import defaultdict

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

BBMRI_URL = 'http://localhost'
BBMRI_ALSO_KNOWN_IN = 'eu_bbmri_eric_also_known_in'
BBMRI_STUDY = 'eu_bbmri_eric_studies'
BBMRI_COLLECTION = 'eu_bbmri_eric_collections'


def send_request(url, data):
    return requests.post(url, json=data)


def get_study_detail(mdr_id):
    payload = {
        "studyId": mdr_id
    }
    res = send_request(ECRIN_MDR_URL, payload)
    return res.json()


def get_mdr_internal_id(registry_id):
    payload = {
        "page": 0,
        "size": 10,
        "searchType": 11,
        "searchValue": registry_id
    }

    res = send_request(ECRIN_SPECIFIC_STUDY, payload)
    data = res.json()
    if data['total'] == 0:
        logger.debug("Not found", registry_id)
        return None
    elif data['total'] == 1:
        return data['data'][0]['id']
    else:
        logger.debug("Found more than one")


def get_age_unit(min_age, max_age):
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


def create_directory_entities(mdr_data, mdr_title, collections_ids):
    session = client.Session(BBMRI_URL)
    session.login('admin', 'admin')

    also_known_id = f'ecrin-mdr:{mdr_data["id"]}'
    study_id = f'bbmri_eric:ID:EXT:{mdr_data["id"]}'

    for cid in collections_ids:
        session.update_one(BBMRI_COLLECTION, cid, 'study', None)

    try:
        session.delete(BBMRI_STUDY, study_id)
        logger.debug("Study already present: removing")
    except MolgenisRequestError as err:
        pass

    try:
        session.delete(BBMRI_ALSO_KNOWN_IN, also_known_id)
        logger.debug("Also_Known_in already present: removing")
    except MolgenisRequestError as err:
        pass

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
        logger.error("Failed to add the study %s" % study_id)
        logger.error(err)
        return False

    logger.debug("Updating study collection")
    for cid in collections_ids:
        session.update_one(BBMRI_COLLECTION, cid, 'study', study_id)
    return True


def process_study(mdr_id, mdr_title, collections_ids):
    logger.debug("Processing study %s" % mdr_id)
    logger.debug("Collections are %s" % collections_ids)
    logger.debug("Getting study detail")
    study_detail = get_study_detail(mdr_id)
    if study_detail["total"] == 0:
        logger.debug("Couldn't find details for study")
        return False
    else:
        logger.debug("Updating directory for study")
        return create_directory_entities(study_detail['data'][0], mdr_title, collections_ids)


def file_exist(file_argument):
    if os.path.exists(file_argument):
        return file_argument
    raise argparse.ArgumentTypeError("File {} does not exist".format(file_argument))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input-file", dest="input_file", type=file_exist, required=True,
                        help="CSV file with mdr and csv matchings")
    args = parser.parse_args()

    with open(args.input_file) as f:
        reader = csv.DictReader(f)
        failures = []
        successes = []
        studies_collections = defaultdict(list)

        for match in reader:
            studies_collections[(match["mdr_id"], match["mdr_title"])].append(f"bbmri-eric:ID:{match['collection_id']}")

        for s, c in studies_collections.items():
            if process_study(s[0], s[1], c) is True:
                successes.append(s[0])
            else:
                failures.append(s[0])

    logger.info("Number of study added: %s" % len(successes))
    logger.info("Number of study failed: %s" % len(failures))
    logger.info("List of failed study: %s" % ", ".join(failures))
