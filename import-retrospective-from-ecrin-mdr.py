from molgenis import client
import requests
from molgenis.client import MolgenisRequestError

ECRIN_TO_BBMRI = {
    'NCT02315716': ['bbmri-eric:ID:UK_GBR-1-200:collection:1'],
    'ISRCTN50083238': ['bbmri-eric:ID:UK_GBR-1-145:collection:389-1098',
                       'bbmri-eric:ID:UK_GBR-1-145:collection:389-1099',
                       'bbmri-eric:ID:UK_GBR-1-145:collection:389-1100',
                       'bbmri-eric:ID:UK_GBR-1-145:collection:389-1101',
                       'bbmri-eric:ID:UK_GBR-1-145:collection:389-1102',
                       'bbmri-eric:ID:UK_GBR-1-145:collection:389-1103'],
    'NCT02308722': ['bbmri-eric:ID:UK_GBR-1-145:collection:388-1090',
                    'bbmri-eric:ID:UK_GBR-1-145:collection:388-1091',
                    'bbmri-eric:ID:UK_GBR-1-145:collection:388-1092',
                    'bbmri-eric:ID:UK_GBR-1-145:collection:388-1093',
                    'bbmri-eric:ID:UK_GBR-1-145:collection:388-1094',
                    'bbmri-eric:ID:UK_GBR-1-145:collection:388-1095'],
    'NCT03641547': ['bbmri-eric:ID:UK_GBR-1-145:collection:390-1104',
                    'bbmri-eric:ID:UK_GBR-1-145:collection:390-1105',
                    'bbmri-eric:ID:UK_GBR-1-145:collection:390-1106',
                    'bbmri-eric:ID:UK_GBR-1-145:collection:390-1107'],
    'NCT03529669': ['bbmri-eric:ID:UK_GBR-1-145:collection:391-1108',
                    'bbmri-eric:ID:UK_GBR-1-145:collection:391-1109',
                    'bbmri-eric:ID:UK_GBR-1-145:collection:391-1110',
                    'bbmri-eric:ID:UK_GBR-1-145:collection:391-1111'],
    'NCT00357682': ['bbmri-eric:ID:UK_GBR-1-145:collection:396-1122',
                    'bbmri-eric:ID:UK_GBR-1-145:collection:396-1123',
                    'bbmri-eric:ID:UK_GBR-1-145:collection:396-1124',
                    'bbmri-eric:ID:UK_GBR-1-145:collection:396-1125'],
    'NCT04111978': [
        'bbmri-eric:ID:CH_UniversitatsspitalBasel:collection:CH_MATAO'],
    'NCT01303887': ['bbmri-eric:ID:UK_GBR-1-119:collection:310-880',
                    'bbmri-eric:ID:UK_GBR-1-119:collection:310-881'],
    'NCT03562169': ['bbmri-eric:ID:UK_GBR-1-179:collection:1'],
    'ISRCTN44687907': ['bbmri-eric:ID:UK_GBR-1-35:collection:193-582',
                       'bbmri-eric:ID:UK_GBR-1-35:collection:193-583'],
    'NCT00994318': ['bbmri-eric:ID:AT_MUW:collection:BB9315'],
    'NCT03961438': ['bbmri-eric:ID:NL_AMCBB:collection:AB20-012'],
    'NCT00749450': ['bbmri-eric:ID:UK_GBR-1-24:collection:1'],
    'ISRCTN84013636': ['bbmri-eric:ID:UK_GBR-1-104:collection:1'],
    'NCT01654146': ['bbmri-eric:ID:UK_GBR-1-151:collection:1'],
    'NCT00112931': ['bbmri-eric:ID:UK_GBR-1-191:collection:1'],
    '7277': ['bbmri-eric:ID:NL_CRC:collection:10012'],
    '2016-002493-13': [
        'bbmri-eric:ID:NL_AAAACXSW447PSACQK2MBZ5YAAM:collection:AAAACXSW47D4CACQK2MBZ5YAAE'],
    'NCT02826512': [
        'bbmri-eric:ID:NL_AAAACXSW447PSACQK2MBZ5YAAM:collection:AAAACYBR6IJTWACQK2MBZ5YAAE'],
    '8261': ['bbmri-eric:ID:NL_CRC:collection:10006'],
    'NCT02945566': ['bbmri-eric:ID:NL_CRC:collection:10034'],
    '2013-003489-15': ['bbmri-eric:ID:NL_CRC:collection:10026'],
    # 'NCT03737539(some remaining uncertainty)': [
    #     'bbmri-eric:ID:NL_CRC:collection:10019'],
    'DRKS00011917': ['bbmri-eric:ID:NL_CRC:collection:10031'],
    'NCT02231086': ['bbmri-eric:ID:NL_CRC:collection:10033'],
    'NCT02057913': ['bbmri-eric:ID:UK_GBR-1-134:collection:1'],
    'NCT04396899': [
        'bbmri-eric:ID:DE_UMGB:collection:BioVAT-HF'],
    'NCT03792490': [
        'bbmri-eric:ID:DE_UMGB:collection:ROCK-ALS'],
    '8177.': ['bbmri-eric:ID:NL_CRC:collection:10023'],
    'NCT02070146': ['bbmri-eric:ID:NL_CRC:collection:10032'],
    'DRKS00011023 ': ['bbmri-eric:ID:DE_IBBJ:collection:TARGET'],
    '2015-001969-49': [
        'bbmri-eric:ID:NL_AAAACXSW447PSACQK2MBZ5YAAM:collection:AAAACXSW45URYACQK2MBZ5YAAE'],
    'NCT02371304': ['bbmri-eric:ID:NL_CRC:collection:10030'],
    'ISRCTN48151589': ['bbmri-eric:ID:NL_AMCBB:collection:AB16-005'],
    'NCT00058032': ['bbmri-eric:ID:UK_GBR-1-123:collection:1'],
    'NCT02925234': [
        'bbmri-eric:ID:NL_AAAACXSW447PSACQK2MBZ5YAAM:collection:AAAACXSW46HH4ACQK2MBZ5YAAE'],
    '280': ['bbmri-eric:ID:NL_AMCBB:collection:AB17-001'],
    #### BBMRI_TO_ECRIN
    '2021-001459-15': [
        'bbmri-eric:ID:AT_MUG:collection:COVAC-DMStudy:diabetesmellitustype1diabetesmellitustype2COVID-19COVID-19vaccine'],
    '2021-001054-57': [
        'bbmri-eric:ID:NL_AAAACW5FCXM3MZSUAVNCZ2AAAE:collection:EMC_CB_IMPORT_2021_05'],
    '2021-002327-38': [
        'bbmri-eric:ID:NL_AMCBB:collection:AB21-009'],
    '2021-005051-37': [
        'bbmri-eric:ID:NL_AMCBB:collection:AB21-022'],
    '2021-001072-41': [
        'bbmri-eric:ID:NL_AAAACW5FCXM3MZSUAVNCZ2AAAE:collection:EMC_2023_6535'],
    'NCT04858607': [
        'bbmri-eric:ID:AT_MUG:collection:TheCoVVacStudy:COVID-19vaccinationimmunocompromisedhealthyt-cellagingt-cellimmunityhumoralandcellularimmuneresponse'],
    'NCT05142540': [
        'bbmri-eric:ID:AT_MUG:collection:TheCoVVacBoostStudy-COVID-19boostervaccination']
}

ECRIN_URL = 'https://mdr.ecrin-rms.org/mdr/v1'
ECRIN_SPECIFIC_STUDY = f'{ECRIN_URL}/specific-study'
ECRIN_MDR_URL = f'{ECRIN_URL}/study'

BBMRI_URL = 'http://localhost'
BBMRI_ALSO_KNOWN_IN = 'eu_bbmri_eric_also_known_in'
BBMRI_STUDY = 'eu_bbmri_eric_studies'
BBMRI_COLLECTION = 'eu_bbmri_eric_collections'

def send_request(url, data):
    return requests.post(url, json=data)


def get_study_detail(ecrin_id):
    payload = {
        "studyId": ecrin_id
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
        print("Not found", registry_id)
        return None
    elif data['total'] == 1:
        return data['data'][0]['id']
    else:
        print("Found more than one")


def get_age_unit(min_age, max_age):
    mapping = {
        'Years': "YEAR"
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


def create_directory_entities(ecrin_data, collections_ids):
    session = client.Session(BBMRI_URL)
    session.login('admin', 'admin')

    also_known_id = f'ecrin-mdr:{ecrin_data["id"]}'
    study_id = f'bbmri_eric:ID:EXT:{ecrin_data["id"]}'

    for cid in collections_ids:
        session.update_one(BBMRI_COLLECTION, cid, 'study', None)

    try:
        session.delete(BBMRI_STUDY, study_id)
        print("Study already present: removing")
    except MolgenisRequestError as err:
        pass

    try:
        session.delete(BBMRI_ALSO_KNOWN_IN, also_known_id)
        print("Also_Known_in already present: removing")
    except MolgenisRequestError as err:
        pass

    also_known = {
        'id': also_known_id,
        'name_system': 'ECRIN MDR',
        'pid': ecrin_data["id"],
        'url': f'https://crmdr.org/study/{ecrin_data["id"]}',
        'national_node': 'EXT', # to
        'withdrawn': False,
        'label': ecrin_data["displayTitle"]
    }
    print("Adding also_known_in")
    res = session.add(BBMRI_ALSO_KNOWN_IN, also_known)

    study = {
        'id': study_id,
        'title': ecrin_data['displayTitle'],
        'description': ecrin_data['briefDescription'],
        'type': ecrin_data['studyType'],
        'status': ecrin_data['studyStatus'],
        'min_age': ecrin_data['minAge'].get('value') if ecrin_data['minAge'] is not None else None,
        'max_age': ecrin_data['maxAge'].get('value') if ecrin_data['maxAge'] is not None else None,
        'age_unit': get_age_unit(ecrin_data['minAge'], ecrin_data['maxAge']),
        'also_known': also_known_id
    }
    print("Adding study")
    session.add(BBMRI_STUDY, study)

    print("Updating study collection")
    for cid in collections_ids:
        session.update_one(BBMRI_COLLECTION, cid, 'study', study_id)


if __name__ == '__main__':
    founded = []
    for ecrin_id, collections_ids in ECRIN_TO_BBMRI.items():
        print("Processing study %s" % ecrin_id)
        print("Getting internal id")
        internal_id = get_mdr_internal_id(ecrin_id)
        if internal_id is not None:
            print("Found ID %s" % internal_id)
            print("Getting study detail")
            study_detail = get_study_detail(internal_id)
            print("Updating directory for study")
            create_directory_entities(study_detail['data'][0], collections_ids)
            print()
        else:
            print("Not found. Skipping")
