from molgenis import client
from molgenis.client import MolgenisRequestError

molgenisURL = 'http://localhost:82'
directoryURL = 'http://localhost:82'

MOLGENIS_URL = f'{molgenisURL}'  # URL of the molgenis to query
DIRECTORY_URL = f'{directoryURL}'  # URL of the directory

BBMRI_BIOBANK_ENTITY = 'eu_bbmri_eric_biobanks'
BBMRI_COLLECTION_ENTITY = 'eu_bbmri_eric_collections'

FDP_BIOBANK_ENTITY = 'fdp_Biobank'
FDP_COLLECTION_ENTITY = 'fdp_Collection'

ORPHA_ONTOLOGY_PREFIX = 'http://www.orpha.net/ORDO/Orphanet_'
ORPHA_DIRECTORY_PREFIX = 'ORPHA:'
ICD_10_ONTOLOGY_PREFIX = 'http://purl.bioontology.org/ontology/ICD10/'
ICD_10_DIRECTORY_PREFIX = 'urn:miriam:icd:'

BIOBANKS_ATTRIBUTES = 'id,name,acronym,description,country,juridical_person,collections,contact'
BIOBANKS_EXPAND_ATTRIBUTES = 'country,juridical_person,collections,contact'
COLLECTIONS_ATTRIBUTES = 'id,name,description,biobank,diagnosis_available,country,parent_collection'
COLLECTIONS_EXPAND_ATTRIBUTES = 'biobank,diagnosis_available,country'

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


def _get_missing_biobanks(session, **kwargs):
    print("Getting source entities from {}".format(BBMRI_BIOBANK_ENTITY))
    source_records = session.get(BBMRI_BIOBANK_ENTITY, **kwargs)
    print("Getting ids already present")
    dest_records_ids = [r['identifier'] for r in session.get(FDP_BIOBANK_ENTITY, attributes='identifier')]
    new_records = [sr for sr in source_records if sr['id'] not in dest_records_ids]
    print("Found {} new records to insert".format(len(new_records)))
    return source_records


def _add_new_records(session, entity, records):
    created_records = []
    for i in range(0, len(records), 1000):
        try:
            created_records.extend(session.add_all(entity, records[i:i + 1000]))
        except MolgenisRequestError as ex:
            print("Error adding records")
            print(ex)
    print("Added {} record(s) of type {}".format(len(created_records), entity))


def _convert_country(country):
    return 'GB' if country == 'UK' else country


def _get_disease_ontology_code(disease_code):
    if ORPHA_DIRECTORY_PREFIX in disease_code:
        return disease_code.replace(ORPHA_ONTOLOGY_PREFIX, ORPHA_ONTOLOGY_PREFIX)
    if ICD_10_DIRECTORY_PREFIX in disease_code:
        return disease_code.replace(ICD_10_DIRECTORY_PREFIX, ICD_10_ONTOLOGY_PREFIX)


def _get_collection_type_ontology_code(collection_type):
    return COLLECTION_TYPES_ONTOLOGIES.get(collection_type, None)


def get_records_to_add(biobank_data, session):
    missing_iris = []
    for c in biobank_data['collections']:
        for d in c['diagnosis_available']:
            try:
                session.get_by_id('fdp_IRI', d['id'], attributes='id')
            except MolgenisRequestError:
                missing_iris.append((d['id'], _get_disease_ontology_code(d['id'])))

        for t in c['type']:
            try:
                session.get_by_id('fdp_IRI', t['id'], attributes='id')
            except MolgenisRequestError:
                ontology_code = _get_collection_type_ontology_code(t['id'])
                if ontology_code is not None:
                    missing_iris.append((t['id'], ontology_code))

    return {
        'fdp_Biobank': {
            'IRI': f'{DIRECTORY_URL}/api/fdp/fdp_Biobank/{biobank_data["id"]}',
            'catalog': 'bbmri-directory',  # TODO: get it dynamically
            'identifier': biobank_data['id'],
            'title': biobank_data['name'],
            'acronym': biobank_data['acronym'] if 'acronym' in biobank_data else None,
            'description': biobank_data['description'] if 'description' in biobank_data else None,
            'publisher': f'{biobank_data["id"]}-pub',
            'landingPage': f'{DIRECTORY_URL}/#/biobank/{biobank_data["id"]}',
            'contactPoint': f'{biobank_data["id"]}-cp' if 'contact' in biobank_data else None,
            'country': _convert_country(biobank_data['country']['id'])
        },
        'fdp_Publisher': {
            'identifier': f'{biobank_data["id"]}-pub',
            'label': biobank_data['juridical_person']
        },
        'fdp_ContactPointIndividual': {
            'identifier': f'{biobank_data["id"]}-cp',
            'email': f'mailto:{biobank_data["contact"]["email"]}' if 'contact' in biobank_data else '',
            'address': '',
            'telephone': '',
        },
        'fdp_Collection': [{
            'identifier': c['id'],
            'title': c['name'],
            'biobank': biobank_data["id"],
            'description': c['description'] if 'description' in c else None,
            'type': [t['id'] for t in c['type'] if _get_collection_type_ontology_code(t['id']) is not None],
            'theme': [d['id'] for d in c['diagnosis_available']]
        } for c in biobank_data['collections']],
        'fdp_IRI': missing_iris
    }


def sync_biobanks(session, **kwargs):
    missing_biobanks = _get_missing_biobanks(session, attributes=BIOBANKS_ATTRIBUTES,
                                             expand=BIOBANKS_EXPAND_ATTRIBUTES, **kwargs)
    biobanks = []
    publishers = []
    contacts = []
    collections = []
    iris = set()
    for b in missing_biobanks:
        records = get_records_to_add(b, session)
        biobanks.append(records['fdp_Biobank'])
        publishers.append(records['fdp_Publisher'])
        contacts.append(records['fdp_ContactPointIndividual'])
        collections.extend(records['fdp_Collection'])
        iris.update(records['fdp_IRI'])

    _add_new_records(session, 'fdp_Publisher', publishers)
    _add_new_records(session, 'fdp_ContactPointIndividual', contacts)
    _add_new_records(session, 'fdp_IRI', [{'id': i[0], 'IRI': i[1]} for i in iris])
    _add_new_records(session, 'fdp_Biobank', biobanks)
    _add_new_records(session, 'fdp_Collection', collections)

s = client.Session(MOLGENIS_URL)
s.login('admin', 'admin')

sync_biobanks(s, num=1)
