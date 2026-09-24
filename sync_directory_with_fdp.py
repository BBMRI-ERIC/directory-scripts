"""
Script to synchronize the BBMRI Directory data of biobanks and collections with their FAIR Data Point/DCAT representation.
It gets the data of biobanks and collections from a Molgenis instance of the Directory, converts it and upload the
converted one into another Molgenis instance. The Molgenis instance can be the same or different. The destination
instance needs the FDP EMX model and the "bbmri-directory" FDP_Catalog (i.e., the FDP Catalog with data of the directory)
already deployed

--------------------------------------------------------------------------------------------------------------------------

Authors

 - Vittorio Meloni <vittorio.meloni@crs4.it>

Acknowledgments:

This work has been partially funded by the following sources:

 - The European Joint Programme on Rare Disease (EJPRD) project (grant agreement N. 825575);

and has evolved within the context of the BBMRI-ERIC Common Service IT.
"""
from collections import OrderedDict

import pprint
from datetime import datetime

from molgenis import client
from molgenis.client import MolgenisRequestError

BBMRI_BIOBANK_ENTITY = 'eu_bbmri_eric_biobanks'
BBMRI_CONTACT_ENTITY = 'eu_bbmri_eric_persons'
BBMRI_DATA_SERVICE_ENTITY = 'eu_bbmri_eric_record_service'

FDP_CATALOG = 'fdp_Catalog'
FDP_BIOBANK = 'fdp_Biobank'
FDP_COLLECTION = 'fdp_Collection'
FDP_BIOBANK_LEGAL_PERSON = 'fdp_BiobankLegalPerson'
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


def get_missing_biobanks(session, reset, **kwargs):
    """Read source biobanks and select records absent from the FDP target.

    Args:
        session: Molgenis session able to read both Directory and FDP entities.
        reset: Whether to return every source biobank without reading existing
            FDP biobank identifiers.
        **kwargs: Additional source ``session.get`` options, such as ``q``,
            ``attributes``, and ``expand``; keys are passed through unchanged.

    Returns:
        Source biobank mappings in server order. Reset mode returns all fetched
        records; incremental mode excludes IDs already stored as
        ``fdp_Biobank.identifier``. This function performs remote reads only.
    """
    print("Getting source entities from {}".format(BBMRI_BIOBANK_ENTITY))
    source_records = session.get(BBMRI_BIOBANK_ENTITY, **kwargs)
    print("Found {}".format(source_records))
    missing_biobanks = []
    for sr in source_records:
        add_biobank = True
        # for c in sr["collections"]:
        #     if "record_service" in c:
        #         add_biobank = True
        if add_biobank:
            missing_biobanks.append(sr)
    # if reset is True the missing biobanks are all
    if reset:
        return missing_biobanks

    print("Getting ids already present")
    dest_records_ids = [r['identifier'] for r in session.get(FDP_BIOBANK, attributes='identifier')]
    new_records = [sr for sr in missing_biobanks if sr['id'] not in dest_records_ids]
    print("Found {} new records to insert".format(len(new_records)))
    return new_records


def create_records(session, entity, records):
    """Add converted FDP records to one entity in batches of at most 1,000.

    Args:
        session: Authenticated Molgenis session receiving remote additions.
        entity: FDP entity name passed to ``add_all``.
        records: Record dictionaries to send in input order.

    Returns:
        None. Successful IDs/responses are accumulated only for the final count.
        A ``MolgenisRequestError`` is printed per failed batch and processing
        continues with later batches. There is no prompt, dry-run, retry, or
        rollback, so earlier batch additions remain applied.
    """
    created_records = []
    for i in range(0, len(records), 1000):
        try:
            created_records.extend(session.add_all(entity, records[i:i + 1000]))
        except MolgenisRequestError as ex:
            print("Error adding records")
            print(ex)
    print("Added {} record(s) of type {}".format(len(created_records), entity))


def delete_records(session, entity, records_ids):
    """Delete destination FDP identifiers in batches of at most 1,000.

    Args:
        session: Authenticated Molgenis session performing remote deletions.
        entity: FDP entity name passed to ``delete_list``.
        records_ids: Entity identifiers to delete in input order.

    Returns:
        None. Successful responses are counted for output. A
        ``MolgenisRequestError`` is printed per failed batch and deletion
        continues, without prompt, dry-run, retry, or rollback.
    """
    removed_records = []
    for i in range(0, len(records_ids), 1000):
        try:
            removed_records.extend(
                session.delete_list(entity, [record_id for record_id in records_ids[i:i + 1000]]))
        except MolgenisRequestError as ex:
            print("Error removing records")
            print(ex)
    print(f"Removed {len(removed_records)} of type {entity}")


def get_country(country):
    """Convert the Directory's UK country code for FDP output.

    Args:
        country: Directory country code.

    Returns:
        ``GB`` for exact input ``UK``; every other value is returned unchanged.
    """
    return 'GB' if country == 'UK' else country


def get_disease_ontology_code(disease_code):
    """Expand a supported Directory disease code into an ontology IRI.

    Args:
        disease_code: Diagnosis identifier containing ``ORPHA:`` or
            ``urn:miriam:icd:``.

    Returns:
        Identifier with the recognized marker replaced by its ORDO or ICD-10
        IRI prefix, prioritizing ORPHA when both markers occur; otherwise
        ``None``.
    """
    if ORPHA_DIRECTORY_PREFIX in disease_code:
        return disease_code.replace(ORPHA_DIRECTORY_PREFIX, ORPHA_ONTOLOGY_PREFIX)
    if ICD_10_DIRECTORY_PREFIX in disease_code:
        return disease_code.replace(ICD_10_DIRECTORY_PREFIX, ICD_10_ONTOLOGY_PREFIX)


def get_collection_type_ontology_code(collection_type):
    """Look up the configured ontology IRI for a Directory collection type.

    Args:
        collection_type: Exact Directory collection-type code.

    Returns:
        Configured ontology IRI, or ``None`` for unmapped and intentionally
        unsupported type codes.
    """
    return COLLECTION_TYPES_ONTOLOGIES.get(collection_type, None)


def get_contact_record(session, contact_id):
    """Read one Directory contact and convert it to an FDP contact tuple.

    Args:
        session: Molgenis session used for the source contact read.
        contact_id: Exact Directory person identifier.

    Returns:
        Seven-item tuple of identifier, ``mailto:`` email, optional whitespace-
        stripped ``tel:`` phone, first name, last name, prefix, and suffix.
        Missing optional keys become ``None``; the required email is not
        normalized.

    Raises:
        KeyError: If the returned contact lacks required ``id`` or ``email``.
    """
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


def get_records_to_add(biobank_data, session, directory_prefix):
    """Convert one expanded Directory biobank into FDP entity payloads.

    Args:
        biobank_data: Expanded source record with required ID, name, country,
            juridical person, and collections; contacts, descriptions, ages,
            diagnoses, types, sizes, and record services supply optional fields.
        session: Molgenis session used for source contact/service reads and FDP
            IRI existence checks. Missing IRIs are not written here.
        directory_prefix: Public Directory URL prefix used to build landing-page
            and collection IRI values.

    Returns:
        Mapping with one biobank and legal-person record plus collection lists,
        contact tuples, missing supported ontology-IRI tuples, and data-service
        records. ``issued`` and ``modified`` timestamps are generated at
        conversion time. No remote mutation occurs.

    Raises:
        KeyError: If required expanded biobank, collection, contact, or service
            fields are absent.
    """

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
                ontology_code = get_disease_ontology_code(d['id'])
                if ontology_code is not None:
                    missing_iris.append((d['id'], ontology_code))

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
                'conformsTo': rs['conformsTo'],
                'type': rs['type'],
                'issued': datetime.now().isoformat(),
                'modified': datetime.now().isoformat(),
                'publisher': 'bbmri',
                'title': f'Data Service of {collection["name"]}',
                'language': ['eng-eu']
            })

    res = {
        FDP_BIOBANK: {
            'identifier': biobank_data['id'],
            # 'IRI': f'{directory_prefix}/api/fdp/fdp_Biobank/{biobank_data["id"]}',  # TODO: use the PID
            'title': biobank_data['name'],
            'acronym': biobank_data['acronym'] if 'acronym' in biobank_data else None,
            'description': biobank_data['description'] if 'description' in biobank_data else None,
            'publisher': f'{biobank_data["id"]}-pub',
            'landingPage': f'{directory_prefix}/#/biobank/{biobank_data["id"]}',
            'contactPoint': f'{biobank_data["contact"]["id"]}' if 'contact' in biobank_data else None,
            'country': get_country(biobank_data['country']['id'])
        },
        FDP_BIOBANK_LEGAL_PERSON: {
            'identifier': f'{biobank_data["id"]}-pub',
            'name': biobank_data['juridical_person']
        },
        FDP_CONTACT: contacts,
        FDP_COLLECTION: [{
            'IRI': f'{directory_prefix}/api/fdp/fdp_Collection/{c["id"]}',
            'additionalRDFType': "http://www.w3.org/ns/dcat#Dataset",
            'identifier': c['id'],
            'biobank': biobank_data["id"],
            'publisher': 'bbmri',
            'title': c['name'],
            'description': c['description'] if 'description' in c else None,
            'diseases': [d['id'].replace("urn:miriam:icd:", "ICD10:") for d in c['diagnosis_available']],
            'theme': ['EU:HEALTH'] + [d['id'] for d in c['diagnosis_available']],
            'type': '',
            'landingPage': f'{directory_prefix}/#/collection/{c["id"]}',
            'contactPoint': f'{c["contact"]["id"]}' if 'contact' in c else None,
            'service': c['record_service']['id'] if 'record_service' in c else None,
            'vpConnection': 'ejprd-vp-discoverable' if 'record_service' in c else None,
            'issued': datetime.now().isoformat(),
            'modified': datetime.now().isoformat(),
            'personalData': 'true',
            'version': '',
            'language': ['eng-eu'],
            'country': 'EU',
            'rights': 'restricted',
            'policy': '', # CRC Cohort 'https://www.bbmri-eric.eu/services/access-policies/',
            'minAge': c['age_low'] if 'age_low' in c else None,
            'maxAge': c['age_high'] if 'age_high' in c else None,
            'numberOfRecords': c['size'] if 'size' in c else None,
            'numberOfUniqueIndividuals': c['number_of_donors'] if 'number_of_donors' in c else None

        } for c in biobank_data['collections']],
        FDP_IRI: missing_iris,
        FDP_DATA_SERVICE: data_services
    }
    return res


def get_collections_in_catalog(session):
    """Read collection identifiers from the fixed BBMRI FDP catalog.

    Args:
        session: Molgenis session used to fetch catalog ``bbmri-directory``.

    Returns:
        Collection ``identifier`` values in catalog order.

    Raises:
        KeyError: If the catalog response lacks ``collection`` or an item lacks
            ``identifier``.
    """
    catalog = session.get_by_id(FDP_CATALOG, 'bbmri-directory', attributes='collection')
    return [c['identifier'] for c in catalog['collection']]


def reset_catalog(session, collections_to_update):
    """Remove incoming collection IDs from the catalog before reset writes.

    Args:
        session: Authenticated Molgenis session reading and updating the FDP
            catalog.
        collections_to_update: Converted collection mappings whose ``IRI``
            final path components identify catalog entries to remove.

    Returns:
        None. The catalog's ``collection`` field is updated remotely once,
        retaining prior identifiers not present in this synchronization batch.
        There is no prompt, dry-run, or rollback.

    Raises:
        KeyError: If a converted collection lacks ``IRI``.
    """
    collections_in_catalog = get_collections_in_catalog(session)
    collections_to_update_ids = list([c['IRI'].split('/')[-1] for c in collections_to_update])
    for c in collections_in_catalog[:]:
        if c in collections_to_update_ids:
            collections_in_catalog.remove(c)
    session.update_one('fdp_Catalog', 'bbmri-directory', 'collection', collections_in_catalog)


def update_catalog(session, new_collections):
    """Union newly created collection IDs into the fixed FDP catalog.

    Args:
        session: Authenticated Molgenis session reading and updating the catalog.
        new_collections: Converted collection mappings containing ``identifier``.

    Returns:
        None. A set union is written remotely to the catalog, so collection
        ordering is not preserved. There is no prompt, dry-run, or rollback.

    Raises:
        KeyError: If a new collection lacks ``identifier``.
    """
    prev_collections = get_collections_in_catalog(session)

    collections = set(prev_collections + [c['identifier'] for c in new_collections])

    session.update_one(FDP_CATALOG, 'bbmri-directory', 'collection', list(collections))


def sync(session, directory_prefix, reset, **kwargs):
    """Convert selected Directory biobanks and mutate their FDP representation.

    Incremental mode ignores source biobanks whose IDs already exist in
    ``fdp_Biobank``. Reset mode processes every selected source biobank, first
    removes its incoming collection IDs from the catalog, and then deletes only
    converted biobank, legal-person, collection, data-service, and contact IDs;
    existing IRI records are deliberately not deleted. Converted entities are
    then added in dependency order and the new collection identifiers are
    unioned back into catalog ``bbmri-directory``.

    Args:
        session: Authenticated Molgenis session spanning source Directory and
            destination FDP entities.
        directory_prefix: Public Directory URL prefix for emitted FDP links.
        reset: Whether to delete matching destination records before addition.
        **kwargs: Additional source-biobank query options forwarded to
            ``session.get``; the CLI supplies ``q`` while this function adds
            fixed ``attributes`` and ``expand`` selections.

    Returns:
        None. The function performs remote reads and writes only; it creates no
        local files. It has no confirmation or dry-run mode. Batch add/delete
        request errors are printed and processing continues, so partial reset
        or creation is possible. Catalog updates and successful earlier batches
        have no transaction or rollback if a later step fails.

    Raises:
        KeyError: If required expanded Directory or catalog fields are absent.
    """
    # it gets the missing biobanks
    missing_biobanks = get_missing_biobanks(session, reset=reset, attributes=BIOBANKS_ATTRIBUTES,
                                            expand=BIOBANKS_EXPAND_ATTRIBUTES, **kwargs)

    # it gathers the data for all the biobanks
    records = OrderedDict({
        FDP_BIOBANK_LEGAL_PERSON: [],
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
        reset_catalog(session, records[FDP_COLLECTION])

        for k, v in reversed(records.items()):
            if k not in (FDP_IRI, FDP_CONTACT) and len(v) > 0:
                delete_records(session, k, [i['identifier'] for i in v])
            if k == FDP_CONTACT and len(v) > 0:
                delete_records(session, k, [i[0] for i in v])

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

    directory_prefix = args.directory_prefix  # .replace('/', '', -1)  # just in case the input put the last /, it removes it
    s = client.Session(args.molgenis_url)
    s.login(args.molgenis_user, args.molgenis_password)

    sync(s, directory_prefix, args.reset, q="id==bbmri-eric:ID:EU_BBMRI-ERIC")
