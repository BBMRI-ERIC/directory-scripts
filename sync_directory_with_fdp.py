"""
Script to synchronize the BBMRI Directory data of biobanks and collections with their FAIR Data Point/DCAT representation.
It gets the data of biobanks and collections from a Molgenis instance of the Directory, converts it and upload the
converted one into another Molgenis instance. The Molgenis instance can be the same or different. The destination
instance needs to be deployed with the FDP instance already deployed. Also, the FDP must have the fdp_Catalog already
created.
"""

from collections import OrderedDict

from molgenis import client
from molgenis.client import MolgenisRequestError

BBMRI_BIOBANK_ENTITY = 'eu_bbmri_eric_biobanks'
BBMRI_CONTACT_ENTITY = 'eu_bbmri_eric_persons'
BBMRI_DATA_SERVICE_ENTITY = 'eu_bbmri_eric_record_service'

FDP_CATALOG = 'fdp_Catalog'
FDP_BIOBANK = 'fdp_Biobank'
FDP_COLLECTION = 'fdp_Collection'
FDP_BIOBANK_ORGANIZATION = 'fdp_BiobankOrganization'
FDP_CONTACT = 'fdp_ContactPointIndividual'
FDP_DATA_SERVICE = 'fdp_DataService'
FDP_IRI = 'fdp_IRI'

ORPHA_ONTOLOGY_PREFIX = 'http://www.orpha.net/ORDO/Orphanet_'
ORPHA_DIRECTORY_PREFIX = 'ORPHA:'
ICD_10_ONTOLOGY_PREFIX = 'http://purl.bioontology.org/ontology/ICD10/'
ICD_10_DIRECTORY_PREFIX = 'urn:miriam:icd:'

BIOBANKS_ATTRIBUTES = f'id,name,acronym,description,country,juridical_person,contact,collections'
BIOBANKS_EXPAND_ATTRIBUTES = f'country,juridical_person,contact,collections'

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

"""
It gets the data from the source Molgenis and filters the one that are already it the destination Molgenis.
If reset flag is True it doesn't filter the biobanks to add 
"""
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


"""
Send converted data to the destination

:params session: Molgenis session to use
:params entity: the name of Molgenis entity type of the records to add 
:params records: lists of dictionary with data of the FDP entity to add
"""
def create_records(session, entity, records):
    created_records = []
    for i in range(0, len(records), 1000):
        try:
            created_records.extend(session.add_all(entity, records[i:i + 1000]))
        except MolgenisRequestError as ex:
            print("Error adding records")
            print(ex)
    print("Added {} record(s) of type {}".format(len(created_records), entity))


"""
Delete records in the destination Molgenis. Used when reset flag is True

:params session: Molgenis session to use
:params entity: the name of Molgenis entity type of the records to delete
:params records_ids: the ids of the records of type :entity: to delete 
"""
def delete_records(session, entity, records_ids):
    removed_records = []
    for i in range(0, len(records_ids), 1000):
        try:
            removed_records.extend(
                session.delete_list(entity, [record_id for record_id in records_ids[i:i + 1000]]))
        except MolgenisRequestError as ex:
            print("Error removing records")
            print(ex)
    print(f"Removed {len(removed_records)} of type {entity}")


"""
Returns the country code correspondent to the country in input 
"""
def get_country(country):
    return 'GB' if country == 'UK' else country


"""
Returns the IRI of the disease code to use in the FDP
"""
def get_disease_ontology_code(disease_code):
    if ORPHA_DIRECTORY_PREFIX in disease_code:
        return disease_code.replace(ORPHA_DIRECTORY_PREFIX, ORPHA_ONTOLOGY_PREFIX)
    if ICD_10_DIRECTORY_PREFIX in disease_code:
        return disease_code.replace(ICD_10_DIRECTORY_PREFIX, ICD_10_ONTOLOGY_PREFIX)


"""
Return the IRI of the collection type

:params collection_type: the collection type code in the directory 
"""
def get_collection_type_ontology_code(collection_type):
    return COLLECTION_TYPES_ONTOLOGIES.get(collection_type, None)


"""
Gets the contact data of the contact with id :contact_id: from the source Molgenis and 
returns the FDP corresponding FDP record

:params session: Molgenis session to use
:params contact_id: the id of the contact in the Directory
"""
def get_contact_record(session, contact_id):
    contact = session.get_by_id(BBMRI_CONTACT_ENTITY, contact_id)
    return (
        f'{contact["id"]}',
        f'mailto:{contact["email"]}',
        f'tel:{contact["phone"].replace(" ", "")}' if 'phone' in contact else None,
        contact['first_name'] if 'first_name' in contact else None,
        contact['last_name'] if 'last_name' in contact else None,
        contact['title_before_name'] if 'title_before_name' in contact else None,
        contact['title_after_name'] if 'title_after_name' in contact else None
    )


"""
It generates the FDP records related to a biobank from the representation of the biobank in the Directory.
It returns a dictionary with data for entities:
fdp_Biobank: data of the Biobank as organization
fdp_BiobankOrganization: data of the Jurystic Person that manage the Biobank
fdp_Collection: list of collections of the biobank
fdp_Contacts: contact of the biobank and the collections to add
fdp_IRI: codes of diseases and collection types (if not already present in the destination)
fdp_DataService: data related to the Data service, if present
"""
def get_records_to_add(biobank_data, session, directory_prefix):
    missing_iris = []
    data_services = []
    contacts = []
    print('processing biobank', biobank_data['id'])

    print("getting biobank's contact data")
    if 'contact' in biobank_data:
        contacts.append(get_contact_record(session, biobank_data['contact']['id']))

    for collection in biobank_data['collections']:
        print("processing collection", collection['id'])
        for d in collection['diagnosis_available']:
            # it checks if the diagnosis is already present in the destination, if not it adds it to the ones to insert
            try:
                session.get_by_id('fdp_IRI', d['id'], attributes='id')
            except MolgenisRequestError:
                missing_iris.append((d['id'], get_disease_ontology_code(d['id'])))

        for t in collection['type']:
            # same as diagnosis for collection type
            try:
                session.get_by_id('fdp_IRI', t['id'], attributes='id')
            except MolgenisRequestError:
                ontology_code = get_collection_type_ontology_code(t['id'])
                if ontology_code is not None:
                    missing_iris.append((t['id'], ontology_code))

        if 'contact' in collection:
            # it adds data about the contacts
            contacts.append(get_contact_record(session, collection['contact']['id']))

        if 'record_service' in collection:
            # if the collection has a record service it generates the corresponding DataService
            rs = session.get_by_id(BBMRI_DATA_SERVICE_ENTITY, collection['record_service']['id'])
            data_services.append({
                'identifier': rs['id'],
                'endpointUrl': rs['url'],
                'endpointDescription': rs['description'] if 'description' in rs else None,
                'conformsTo': rs['conformsTo']
            })

    res = {
        FDP_BIOBANK: {
            'identifier': biobank_data['id'],
            'IRI': f'{directory_prefix}/api/fdp/fdp_Biobank/{biobank_data["id"]}',  # TODO: use the PID
            'title': biobank_data['name'],
            'acronym': biobank_data['acronym'] if 'acronym' in biobank_data else None,
            'description': biobank_data['description'] if 'description' in biobank_data else None,
            'publisher': f'{biobank_data["id"]}-pub',
            'landingPage': f'{directory_prefix}/#/biobank/{biobank_data["id"]}',
            'contactPoint': f'{biobank_data["contact"]["id"]}' if 'contact' in biobank_data else None,
            'country': get_country(biobank_data['country']['id'])
        },
        FDP_BIOBANK_ORGANIZATION: {
            'identifier': f'{biobank_data["id"]}-pub',
            'name': biobank_data['juridical_person']
        },
        FDP_CONTACT: contacts,
        FDP_COLLECTION: [{
            'identifier': c['id'],
            'IRI': f'{directory_prefix}/api/fdp/fdp_Collection/{c["id"]}',
            'contactPoint': f'{c["contact"]["id"]}' if 'contact' in c else None,
            # 'catalog': 'bbmri-directory',  # it
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

def update_catalog(session, new_collections):
    prev_collections = session.get_by_id(FDP_CATALOG, 'bbmri-directory', attributes='collection')

    collections = set([c['identifier'] for c in prev_collections['collection'] + new_collections])

    session.update_one(FDP_CATALOG, 'bbmri-directory', 'collection', list(collections))

"""
Main function that gets the data of the missing biobanks, convert it and upload the new records.
"""
def sync(session, directory_prefix, reset, **kwargs):
    # it gets the missing biobanks
    missing_biobanks = get_missing_biobanks(session, reset=reset, attributes=BIOBANKS_ATTRIBUTES,
                                            expand=BIOBANKS_EXPAND_ATTRIBUTES, **kwargs)
    # it gathers the data for all the biobanks
    records = OrderedDict({
        FDP_BIOBANK_ORGANIZATION: [],
        FDP_CONTACT: set(),
        FDP_IRI: set(),
        FDP_DATA_SERVICE: [],
        FDP_BIOBANK: [],
        FDP_COLLECTION: []
    })
    for b in missing_biobanks:
        # it gets the records to add for a biobank
        new_records = get_records_to_add(b, session, directory_prefix)
        # it updates the overall records with the ones from of the processed biobank
        for k, v in new_records.items():
            if type(records[k]) == list:
                if type(new_records[k]) == list:
                    records[k].extend(new_records[k])
                else:
                    records[k].append(new_records[k])
            else:
                records[k].update(new_records[k])

    # if the reset flag is True, it deletes the old records
    if reset:
        session.update_one('fdp_Catalog', 'bbmri-directory', 'collection', [])
        for k, v in reversed(records.items()):
            if k not in (FDP_IRI, FDP_CONTACT) and len(v) > 0:
                delete_records(session, k, [i['identifier'] for i in v])
            if k == FDP_CONTACT and len(v) > 0:
                delete_records(session, k, [i[0] for i in v])

    # it creates all the
    for k, v in records.items():
        if len(v) > 0:
            if k == FDP_IRI:
                create_records(session, k, [{'id': i[0], 'IRI': i[1]} for i in v])
            elif k == FDP_CONTACT:
                create_records(session, k, [{
                    'identifier': i[0],
                    'email': i[1],
                    'telephone': i[2],
                    'given_name': i[3],
                    'family_name': i[4],
                    'honorific_prefix': i[5],
                    'honorific_suffix': i[6]
                } for i in v])
            else:
                create_records(session, k, v)

    update_catalog(session, records[FDP_COLLECTION])


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--molgenis-url', '-U')
    parser.add_argument('--molgenis-user', '-u')
    parser.add_argument('--molgenis-password', '-p')
    parser.add_argument('--directory-prefix', '-d',
                        help='The main prefix of the url to be used to generate IRIs')
    parser.add_argument('--reset', '-r', dest='reset', action='store_true')
    args = parser.parse_args()

    directory_prefix = args.directory_prefix.replace('/', '',
                                                     -1)  # just in case the input put the last /, it removes it

    s = client.Session(args.molgenis_url)
    s.login(args.molgenis_user, args.molgenis_password)

    sync(s, directory_prefix, args.reset)
