from collections import OrderedDict

from molgenis import client
from molgenis.client import MolgenisRequestError

molgenis_url = 'http://localhost:82'
directory_url = 'http://localhost:82'

MOLGENIS_URL = f'{molgenis_url}'  # URL of the molgenis to query
DIRECTORY_URL = f'{directory_url}'  # URL of the directory

BBMRI_BIOBANK_ENTITY = 'eu_bbmri_eric_biobanks'
BBMRI_DATA_SERVICE_ENTITY = 'eu_bbmri_eric_record_service'

FDP_BIOBANK = 'fdp_Biobank'
FDP_COLLECTION = 'fdp_Collection'
FDP_PUBLISHER = 'fdp_Publisher'
FDP_CONTACT = 'fdp_ContactPointIndividual'
FDP_DATA_SERVICE = 'fdp_DataService'
FDP_IRI = 'fdp_IRI'

ORPHA_ONTOLOGY_PREFIX = 'http://www.orpha.net/ORDO/Orphanet_'
ORPHA_DIRECTORY_PREFIX = 'ORPHA:'
ICD_10_ONTOLOGY_PREFIX = 'http://purl.bioontology.org/ontology/ICD10/'
ICD_10_DIRECTORY_PREFIX = 'urn:miriam:icd:'

COLLECTIONS_ATTRIBUTES = '*,record_service(*)'
BIOBANKS_ATTRIBUTES = f'id,name,acronym,description,country,juridical_person,contact,collections'
BIOBANKS_EXPAND_ATTRIBUTES = f'country,juridical_person,contact,collections'
COLLECTIONS_EXPAND_ATTRIBUTES = 'biobank,diagnosis_available,country,record_service'

COLLECTION_TYPES_ONTOLOGIES = {
    'BIRTH_COHORT': 'http://purl.obolibrary.org/obo/OBI_0002614',
    'CASE_CONTROL': 'http://purl.obolibrary.org/obo/OBIB_0000693',
    'COHORT': 'http://purl.obolibrary.org/obo/OBIB_0000696',
    'CROSS_SECTIONAL': 'http://purl.obolibrary.org/obo/OBIB_0000694',
    'DISEASE_SPECIFIC': 'http://purl.obolibrary.org/obo/OBI_0002615',
    'HOSPITAL': None,
    'IMAGE': None,
    'LONGITUDINAL': 'http://purl.obolibrary.org/obo/OBIB_0000695',
    'NON_HUMAN': None,
    'OTHER': None,
    'POPULATION_BASED': 'http://purl.obolibrary.org/obo/OBIB_0000698',
    'PROSPECTIVE_COLLECTION': None,
    'QUALITY_CONTROL': 'http://purl.obolibrary.org/obo/OBIB_0000699',
    'RD': None,
    'SAMPLE': None,
    'TWIN_STUDY': 'http://purl.obolibrary.org/obo/OBIB_0000700'
}


def get_missing_biobanks(session, reset, **kwargs):
    print("Getting source entities from {}".format(BBMRI_BIOBANK_ENTITY))
    source_records = session.get(BBMRI_BIOBANK_ENTITY, **kwargs)
    # if reset is True the missing biobanks are all
    if reset:
        return source_records

    print("Getting ids already present")
    dest_records_ids = [r['identifier'] for r in session.get(FDP_BIOBANK, attributes='identifier')]
    new_records = [sr for sr in source_records if sr['id'] not in dest_records_ids]
    print("Found {} new records to insert".format(len(new_records)))
    return new_records


def create_records(session, entity, records):
    created_records = []
    for i in range(0, len(records), 1000):
        try:
            created_records.extend(session.add_all(entity, records[i:i + 1000]))
        except MolgenisRequestError as ex:
            print("Error adding records")
            print(ex)
    print("Added {} record(s) of type {}".format(len(created_records), entity))


def delete_records(session, entity, records):
    removed_records = []
    for i in range(0, len(records), 1000):
        try:
            removed_records.extend(
                session.delete_list(entity, [record['identifier'] for record in records[i:i + 1000]]))
        except MolgenisRequestError as ex:
            print("Error removing records")
            print(ex)
    print(f"Removed {len(removed_records)} of type {entity}")


def get_country(country):
    return 'GB' if country == 'UK' else country


def get_disease_ontology_code(disease_code):
    if ORPHA_DIRECTORY_PREFIX in disease_code:
        return disease_code.replace(ORPHA_DIRECTORY_PREFIX, ORPHA_ONTOLOGY_PREFIX)
    if ICD_10_DIRECTORY_PREFIX in disease_code:
        return disease_code.replace(ICD_10_DIRECTORY_PREFIX, ICD_10_ONTOLOGY_PREFIX)


def get_collection_type_ontology_code(collection_type):
    return COLLECTION_TYPES_ONTOLOGIES.get(collection_type, None)


def get_records_to_add(biobank_data, session):
    missing_iris = []
    data_services = []
    for c in biobank_data['collections']:
        for d in c['diagnosis_available']:
            try:
                session.get_by_id('fdp_IRI', d['id'], attributes='id')
            except MolgenisRequestError:
                missing_iris.append((d['id'], get_disease_ontology_code(d['id'])))

        for t in c['type']:
            try:
                session.get_by_id('fdp_IRI', t['id'], attributes='id')
            except MolgenisRequestError:
                ontology_code = get_collection_type_ontology_code(t['id'])
                if ontology_code is not None:
                    missing_iris.append((t['id'], ontology_code))

        if 'record_service' in c:
            rs_data = session.get_by_id(BBMRI_DATA_SERVICE_ENTITY, c['record_service']['id'])
            data_services.append({
                'identifier': rs_data['id'],
                'endpointUrl': rs_data['url'],
                'endpointDescription': rs_data['description'] if 'description' in rs_data else None,
                'conformsTo': rs_data['conformsTo']
            })

    res = {
        FDP_BIOBANK: {
            'identifier': biobank_data['id'],
            'IRI': f'{DIRECTORY_URL}/api/fdp/fdp_Biobank/{biobank_data["id"]}',
            'catalog': 'bbmri-directory',  # TODO: get it dynamically
            'title': biobank_data['name'],
            'acronym': biobank_data['acronym'] if 'acronym' in biobank_data else None,
            'description': biobank_data['description'] if 'description' in biobank_data else None,
            'publisher': f'{biobank_data["id"]}-pub',
            'landingPage': f'{DIRECTORY_URL}/#/biobank/{biobank_data["id"]}',
            'contactPoint': f'{biobank_data["id"]}-cp' if 'contact' in biobank_data else None,
            'country': get_country(biobank_data['country']['id'])
        },
        FDP_PUBLISHER: {
            'identifier': f'{biobank_data["id"]}-pub',
            'label': biobank_data['juridical_person']
        },
        FDP_CONTACT: {
            'identifier': f'{biobank_data["id"]}-cp',
            'email': f'mailto:{biobank_data["contact"]["email"]}' if 'contact' in biobank_data else '',
            'address': '',
            'telephone': '',
        },
        FDP_COLLECTION: [{
            'identifier': c['id'],
            'title': c['name'],
            'biobank': biobank_data["id"],
            'description': c['description'] if 'description' in c else None,
            'type': [t['id'] for t in c['type'] if get_collection_type_ontology_code(t['id']) is not None],
            'theme': [d['id'] for d in c['diagnosis_available']],
            'service': c['record_service']['id'] if 'record_service' in c else None
        } for c in biobank_data['collections']],
        FDP_IRI: missing_iris,
        FDP_DATA_SERVICE: data_services
    }
    return res


def sync(session, reset, **kwargs):
    missing_biobanks = get_missing_biobanks(session, reset=reset, attributes=BIOBANKS_ATTRIBUTES,
                                            expand=BIOBANKS_EXPAND_ATTRIBUTES,
                                            **kwargs)

    records = OrderedDict({
        FDP_PUBLISHER: [],
        FDP_CONTACT: [],
        FDP_IRI: set(),
        FDP_DATA_SERVICE: [],
        FDP_BIOBANK: [],
        FDP_COLLECTION: []
    })
    for b in missing_biobanks:
        new_records = get_records_to_add(b, session)
        for k, v in new_records.items():
            if type(records[k]) == list:
                if type(new_records[k]) == list:
                    records[k].extend(new_records[k])
                else:
                    records[k].append(new_records[k])
            else:
                records[k].update(new_records[k])

    if reset:
        for k, v in reversed(records.items()):
            if k != 'fdp_IRI' and len(v) > 0:
                delete_records(session, k, v)

    for k, v in records.items():
        if len(v) > 0:
            if k == FDP_IRI:
                create_records(session, k, [{'id': i[0], 'IRI': i[1]} for i in v])
            else:
                create_records(session, k, v)


s = client.Session(MOLGENIS_URL)
s.login('admin', 'admin')

reset = True
sync(s, reset)
