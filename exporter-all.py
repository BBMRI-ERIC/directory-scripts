#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

import pprint
import logging as log
from builtins import str, isinstance, len, set, int
from typing import List

import pandas as pd

from cli_common import (
    add_directory_schema_argument,
    add_logging_arguments,
    add_no_stdout_argument,
    add_optional_xlsx_output_argument,
    add_purge_cache_arguments,
    add_withdrawn_scope_arguments,
    add_xlsx_output_argument,
    build_directory_kwargs,
    build_parser,
    configure_logging,
)
from directory import Directory
from oomutils import (
    describe_oom_estimate_policy,
    estimate_count_from_oom_or_none,
    get_oom_upper_bound_coefficient,
)
import pddfutils
from xlsxutils import write_xlsx_tables

cachesList = ['directory']

pp = pprint.PrettyPrinter(indent=4)


parser = build_parser()
add_logging_arguments(parser)
add_xlsx_output_argument(parser)
add_optional_xlsx_output_argument(
    parser,
    dest='outputXLSXwithdrawn',
    long_option='--output-xlsx-withdrawn',
    legacy_long_options=['--output-XLSX-withdrawn'],
    help_text='write withdrawn biobanks and collections to the provided XLSX file',
)
add_no_stdout_argument(parser)
add_directory_schema_argument(parser, default="ERIC")
add_withdrawn_scope_arguments(parser)
add_purge_cache_arguments(parser, cachesList)
parser.add_argument(
    '--include-withdrawn-sheets-in-output',
    dest='includeWithdrawnSheetsInOutput',
    action='store_true',
    help='append withdrawn-entity sheets to the main XLSX output (requires -X and -w/--include-withdrawn)',
)
parser.add_argument('-FCT', '--filter-collection-type', '--filter-coll-type', dest='filterCollType', nargs='+', action='extend',
                    help='filter by the collection types in the data model, each of them between quotes ("") and separated by a space. E.g.: -FCT "CASE_CONTROL" "LONGITUDINAL" "DISEASE_SPECIFIC"') # TODO: Till now it uses the terms from the data model, different from the ones displayed in Directory
parser.add_argument('-FMT', '--filter-material-type', dest='filterMatType', nargs='+', action='extend',
                    help='filter by the material types in the data model, each of them between quotes ("") and separated by a space. E.g.: -FCT "SERUM" "SAMPLE"') # TODO: Till now it uses the terms from the data model, different from the ones displayed in Directory


parser.set_defaults(purgeCaches=[], filterCollType=[], filterMatType=[])
args = parser.parse_args()
filterCollType = args.filterCollType
filterMatType = args.filterMatType

if args.outputXLSXwithdrawn is not None and not (
    args.include_withdrawn or args.only_withdrawn
):
    parser.error(
        "--output-xlsx-withdrawn requires --include-withdrawn or --only-withdrawn."
    )
if args.includeWithdrawnSheetsInOutput and args.outputXLSX is None:
    parser.error("--include-withdrawn-sheets-in-output requires -X/--output-XLSX.")
if args.includeWithdrawnSheetsInOutput and not args.include_withdrawn:
    parser.error("--include-withdrawn-sheets-in-output requires -w/--include-withdrawn.")

configure_logging(args)


### Initialize variables
allCollections = []
withdrawnCollections = []
allServices = []
withdrawnServices = []
allStudies = []
withdrawnStudies = []
allContacts = []
withdrawnContacts = []
allNetworks = []
withdrawnNetworks = []
allBiobanks = set()
withdrawnBiobanks = set()
allCollectionSamplesExplicit = 0
allCollectionDonorsExplicit = 0
allCollectionSamplesIncOoM = 0
# OoM Donors
allCollectionDonorsIncOoM = 0
allCountries = set()
targetColls = []

### Functions
def buildDirectoryEntityURL(entity_route: str, entity_id: str) -> str:
    base_url = dir.getDirectoryUrl().rstrip('/')
    return f"{base_url}/{dir.getSchema()}/directory/#/{entity_route}/{entity_id}"


def analyseCollections(collections, allCollectionSamplesExplicit, allCollectionDonorsExplicit, allCollectionSamplesIncOoM, allCollectionDonorsIncOoM):
    for collection in collections:
        log.debug("Analyzing collection " + collection['id'])
        biobankId = dir.getCollectionBiobankId(collection['id'])
        biobank = dir.getBiobankById(biobankId)
        
        if 'contact' in collection:
            collection['contact'] = dir.getContact(collection['contact']['id'])

        collection_withdrawn = dir.isCollectionWithdrawn(collection['id'])
        biobank_withdrawn = dir.isBiobankWithdrawn(biobankId)
        if collection_withdrawn:
            withdrawnCollections.append(collection)
            log.debug("Detected a withdrawn collection: %s", collection['id'])
        if biobank_withdrawn:
            withdrawnBiobanks.add(biobankId)
        if collection_withdrawn and not (args.include_withdrawn or args.only_withdrawn):
            continue

        if biobank['country'] != 'EU':
            allCountries.add(biobank['country'])
        allCollections.append(collection)
        allBiobanks.add(biobankId)
        #if 'size' in collection and isinstance(collection['size'], int) and dir.isTopLevelCollection(collection['id']):
        if dir.isCountableCollection(collection['id'], 'size'):

            allCollectionSamplesExplicit += collection['size']
            allCollectionSamplesIncOoM += collection['size']
        else:
            # note that OoM is only counted for top-level collections to avoid double counting - because OoM is mandatory parameter, any child collection has a parent which has OoM filled in
            if dir.isTopLevelCollection(collection['id']):
                estimate = estimate_count_from_oom_or_none(
                    collection.get('order_of_magnitude'),
                    collection_id=collection['id'],
                    field_name='order_of_magnitude',
                )
                if estimate is not None:
                    allCollectionSamplesIncOoM += estimate
        #if 'number_of_donors' in collection and isinstance(collection['number_of_donors'], int) and dir.isTopLevelCollection(collection['id']):
        if dir.isCountableCollection(collection['id'], 'number_of_donors'):
            allCollectionDonorsExplicit += collection['number_of_donors']
            # OoM Donors
            allCollectionDonorsIncOoM += collection['number_of_donors']
        else:
            if dir.isTopLevelCollection(collection['id']):
                estimate = estimate_count_from_oom_or_none(
                    collection.get('order_of_magnitude_donors'),
                    collection_id=collection['id'],
                    field_name='order_of_magnitude_donors',
                )
                if estimate is not None:
                    allCollectionDonorsIncOoM += estimate

        # Print also the Directory URL:
        if not 'directoryURL' in collection:
            collection['directoryURL'] = buildDirectoryEntityURL('collection', collection['id'])

    return allCollections, withdrawnCollections, allCollectionSamplesExplicit, allCollectionDonorsExplicit, allCollectionSamplesIncOoM, allCollectionDonorsIncOoM, allBiobanks

def analyseBBs():
    for biobank in dir.getBiobanks():
        biobankId = biobank['id']
        if 'contact' in biobank:
            biobank['contact'] = dir.getContact(biobank['contact']['id'])
        if 'directoryURL' not in biobank:
            biobank['directoryURL'] = buildDirectoryEntityURL('biobank', biobankId)
        log.debug("Analyzing biobank " + biobankId)
        if biobankId in allBiobanks:
            continue
        log.info("   Biobank without any collection identified: " + biobankId)
        if dir.isBiobankWithdrawn(biobankId):
            withdrawnBiobanks.add(biobankId)
            log.debug("Detected a withdrawn biobank without any collection %s", biobankId)
            if not (args.include_withdrawn or args.only_withdrawn):
                continue
        allBiobanks.add(biobankId)
    return allBiobanks

def printCollectionStdout(collectionList: List):
    for collection in collectionList:
        biobankId = dir.getCollectionBiobankId(collection['id'])
        biobank = dir.getBiobankById(biobankId)
        log.info("   Collection: " + collection['id'] + " - " + collection['name'] + ". Parent biobank: " + biobankId + " - " + biobank['name'])
    log.info("\n\n")

def analyseServices():
    for service in dir.getServices():
        biobankId = dir.getServiceBiobankId(service['id'])
        biobank = dir.getBiobankById(biobankId)
        if biobank is None:
            continue
        allServices.append(service)
        allBiobanks.add(biobankId)
        if dir.isBiobankWithdrawn(biobankId):
            withdrawnServices.append(service)
            withdrawnBiobanks.add(biobankId)
        if 'directoryURL' not in service:
            service['directoryURL'] = buildDirectoryEntityURL('service', service['id'])


def _study_has_withdrawn_collection(study: dict) -> bool:
    for collection_id in dir.getStudyCollectionIds(study['id']):
        if dir.isCollectionWithdrawn(collection_id):
            return True
    return False


def analyseStudies():
    for study in dir.getStudies():
        studyBiobankIds = dir.getStudyBiobankIds(study['id'])
        for biobankId in studyBiobankIds:
            allBiobanks.add(biobankId)
            if dir.isBiobankWithdrawn(biobankId):
                withdrawnBiobanks.add(biobankId)
        allStudies.append(study)
        if _study_has_withdrawn_collection(study):
            withdrawnStudies.append(study)
        if 'directoryURL' not in study:
            study['directoryURL'] = buildDirectoryEntityURL('study', study['id'])


def _collect_reference_ids(value):
    if isinstance(value, dict):
        reference_id = value.get('id')
        return [reference_id] if reference_id else []
    if isinstance(value, list):
        return [
            element.get('id')
            for element in value
            if isinstance(element, dict) and element.get('id')
        ]
    return []


def _collect_scope_contact_ids(biobank_ids, collections, networks):
    contact_ids = set()
    for biobank_id in biobank_ids:
        biobank = dir.getBiobankById(biobank_id)
        if biobank is None:
            continue
        contact_ids.update(_collect_reference_ids(biobank.get('contact')))
        contact_ids.update(_collect_reference_ids(biobank.get('contacts')))
    for collection in collections:
        contact_ids.update(_collect_reference_ids(collection.get('contact')))
        contact_ids.update(_collect_reference_ids(collection.get('contacts')))
    for network in networks:
        contact_ids.update(_collect_reference_ids(network.get('contact')))
        contact_ids.update(_collect_reference_ids(network.get('contacts')))
    return contact_ids


def _collect_scope_network_ids(biobank_ids, collections):
    network_ids = set()
    for biobank_id in biobank_ids:
        biobank = dir.getBiobankById(biobank_id)
        if biobank is None:
            continue
        network_ids.update(_collect_reference_ids(biobank.get('network')))
        network_ids.update(_collect_reference_ids(biobank.get('networks')))
    for collection in collections:
        network_ids.update(_collect_reference_ids(collection.get('network')))
        network_ids.update(_collect_reference_ids(collection.get('networks')))
    return network_ids


def analyseNetworks():
    selected_network_ids = _collect_scope_network_ids(allBiobanks, allCollections)
    selected_withdrawn_network_ids = _collect_scope_network_ids(withdrawnBiobanks, withdrawnCollections)
    network_by_id = {network['id']: network for network in dir.getNetworks()}
    for network_id in sorted(selected_network_ids):
        network = network_by_id.get(network_id)
        if network is None:
            continue
        if 'directoryURL' not in network:
            network['directoryURL'] = buildDirectoryEntityURL('network', network['id'])
        allNetworks.append(network)
    for network_id in sorted(selected_withdrawn_network_ids):
        network = network_by_id.get(network_id)
        if network is None:
            continue
        if 'directoryURL' not in network:
            network['directoryURL'] = buildDirectoryEntityURL('network', network['id'])
        withdrawnNetworks.append(network)


def analyseContacts():
    selected_contact_ids = _collect_scope_contact_ids(allBiobanks, allCollections, allNetworks)
    selected_withdrawn_contact_ids = _collect_scope_contact_ids(withdrawnBiobanks, withdrawnCollections, withdrawnNetworks)
    for contact_id in sorted(selected_contact_ids):
        contact = dir.getContact(contact_id)
        if 'directoryURL' not in contact:
            contact['directoryURL'] = buildDirectoryEntityURL('person', contact['id'])
        allContacts.append(contact)
    for contact_id in sorted(selected_withdrawn_contact_ids):
        contact = dir.getContact(contact_id)
        if 'directoryURL' not in contact:
            contact['directoryURL'] = buildDirectoryEntityURL('person', contact['id'])
        withdrawnContacts.append(contact)


def printServiceStdout(serviceList: List):
    for service in serviceList:
        biobankId = dir.getServiceBiobankId(service['id'])
        biobank = dir.getBiobankById(biobankId)
        serviceName = service.get('name', '')
        biobankName = biobank.get('name', '') if biobank is not None else ''
        log.info("   Service: " + service['id'] + " - " + serviceName + ". Parent biobank: " + biobankId + " - " + biobankName)
    log.info("\n\n")


def printStudyStdout(studyList: List):
    for study in studyList:
        studyTitle = study.get('title', '')
        studyBiobankIds = dir.getStudyBiobankIds(study['id'])
        if len(studyBiobankIds) == 1:
            biobankId = studyBiobankIds[0]
            biobank = dir.getBiobankById(biobankId)
            biobankName = biobank.get('name', '') if biobank is not None else ''
            log.info("   Study: " + study['id'] + " - " + studyTitle + ". Parent biobank: " + biobankId + " - " + biobankName)
        else:
            log.info("   Study: " + study['id'] + " - " + studyTitle + ". Parent biobanks: " + ",".join(studyBiobankIds))
    log.info("\n\n")

def printContactStdout(contactList: List):
    for contact in contactList:
        contactName = " ".join([value for value in [contact.get('first_name'), contact.get('last_name')] if value])
        label = contactName if contactName else contact.get('email', '')
        log.info("   Contact: " + contact['id'] + " - " + label)
    log.info("\n\n")


def printNetworkStdout(networkList: List):
    for network in networkList:
        log.info("   Network: " + network['id'] + " - " + network.get('name', ''))
    log.info("\n\n")


def outputExcelDirectoryEntities(
    filename : str,
    dfBiobanks : pd.DataFrame,
    biobanksLabel : str,
    dfCollections : pd.DataFrame,
    collectionsLabel : str,
    dfServices : pd.DataFrame,
    servicesLabel : str,
    dfStudies : pd.DataFrame,
    studiesLabel : str,
    dfContacts : pd.DataFrame,
    contactsLabel : str,
    dfNetworks : pd.DataFrame,
    networksLabel : str,
    extraSheets = None,
):
    sheet_specs = [
        (dfBiobanks, biobanksLabel, True, {"hyperlink_columns": [("id", "directoryURL")]}),
        (dfCollections, collectionsLabel, True, {"hyperlink_columns": [("id", "directoryURL")]}),
        (dfServices, servicesLabel, True, {"hyperlink_columns": [("id", "directoryURL")]}),
        (dfStudies, studiesLabel, True, {"hyperlink_columns": [("id", "directoryURL")]}),
        (dfContacts, contactsLabel, True, {"hyperlink_columns": [("id", "directoryURL")]}),
        (dfNetworks, networksLabel, True, {"hyperlink_columns": [("id", "directoryURL")]}),
    ]
    if extraSheets:
        sheet_specs.extend(extraSheets)
    write_xlsx_tables(
        filename,
        sheet_specs,
    )

### Main

dir = Directory(**build_directory_kwargs(args, pp=pp))

log.info('Total biobanks: ' + str(dir.getBiobanksCount()))
log.info('Total collections: ' + str(dir.getCollectionsCount()))
log.info(
    "OoM estimate policy: %s (coefficient=%s)",
    describe_oom_estimate_policy(),
    get_oom_upper_bound_coefficient(),
)

if filterCollType and filterMatType:
    for collection in dir.getCollections():
        if 'parent_collection' in collection:
            continue
        if 'materials' in collection and any(t in collection['type'] for t in filterCollType) and any(m in collection['materials'] for m in filterMatType):
            targetColls.append(collection)
    allCollections, withdrawnCollections, allCollectionSamplesExplicit, allCollectionDonorsExplicit, allCollectionSamplesIncOoM, allCollectionDonorsIncOoM, allBiobanks = analyseCollections(targetColls, allCollectionSamplesExplicit, allCollectionDonorsExplicit, allCollectionSamplesIncOoM, allCollectionDonorsIncOoM)
elif filterCollType or filterMatType:
    for collection in dir.getCollections():
        if 'parent_collection' in collection:
            continue
        if 'materials' in collection:
            if any(t in collection['type'] for t in filterCollType) or any(m in collection['materials'] for m in filterMatType):
                targetColls.append(collection)
        else:
            if any(t in collection['type'] for t in filterCollType):
                targetColls.append(collection)
    allCollections, withdrawnCollections, allCollectionSamplesExplicit, allCollectionDonorsExplicit, allCollectionSamplesIncOoM, allCollectionDonorsIncOoM, allBiobanks = analyseCollections(targetColls, allCollectionSamplesExplicit, allCollectionDonorsExplicit, allCollectionSamplesIncOoM, allCollectionDonorsIncOoM)
else:
    for collection in dir.getCollections():
        targetColls.append(collection)
    allCollections, withdrawnCollections, allCollectionSamplesExplicit, allCollectionDonorsExplicit, allCollectionSamplesIncOoM, allCollectionDonorsIncOoM, allBiobanks = analyseCollections(targetColls, allCollectionSamplesExplicit, allCollectionDonorsExplicit, allCollectionSamplesIncOoM, allCollectionDonorsIncOoM)
    allBiobanks = analyseBBs()

analyseServices()
analyseStudies()
analyseNetworks()
analyseContacts()

pd_allCollections = pd.DataFrame(allCollections)
pd_withdrawnCollections = pd.DataFrame(withdrawnCollections)
pd_allServices = pd.DataFrame(allServices)
pd_withdrawnServices = pd.DataFrame(withdrawnServices)
pd_allStudies = pd.DataFrame(allStudies)
pd_withdrawnStudies = pd.DataFrame(withdrawnStudies)
pd_allContacts = pd.DataFrame(allContacts)
pd_withdrawnContacts = pd.DataFrame(withdrawnContacts)
pd_allNetworks = pd.DataFrame(allNetworks)
pd_withdrawnNetworks = pd.DataFrame(withdrawnNetworks)
pd_allBiobanks = pd.DataFrame([dir.getBiobankById(biobankId) for biobankId in allBiobanks])
pd_withdrawnBiobanks = pd.DataFrame([dir.getBiobankById(biobankId) for biobankId in withdrawnBiobanks])

if not args.nostdout:
    printCollectionStdout(allCollections)
    printServiceStdout(allServices)
    printStudyStdout(allStudies)
    printContactStdout(allContacts)
    printNetworkStdout(allNetworks)
    print("Totals:")
    print("- total of biobanks in selected scope: %d" % (len(allBiobanks)))
    print("- total of withdrawn biobanks in selected scope: %d" % (len(withdrawnBiobanks)))
    print("- total of collections with existing samples in selected scope: %d" % (len(allCollections)))
    print("- total of services in selected scope: %d" % (len(allServices)))
    print("- total of studies in selected scope: %d" % (len(allStudies)))
    print("- total of contacts in selected scope: %d" % (len(allContacts)))
    print("- total of networks in selected scope: %d" % (len(allNetworks)))
    print("- total of countries: %d" % ( len(allCountries)))
    print("Estimated totals:")
    print("- total of samples/donors advertised explicitly in all-relevant collections: %d / %d" % (
        allCollectionSamplesExplicit, allCollectionDonorsExplicit))
    print("- total of samples/donors advertised in all-relevant collections including OoM estimates: %d / %d" % (
        allCollectionSamplesIncOoM, allCollectionDonorsIncOoM))

for df in (pd_allCollections, pd_withdrawnCollections):
    if not df.empty:
        pddfutils.tidyCollectionDf(df)
for df in (pd_allBiobanks, pd_withdrawnBiobanks):
    if not df.empty:
        pddfutils.tidyBiobankDf(df)
for df in (pd_allServices, pd_withdrawnServices):
    if not df.empty:
        pddfutils.tidyServiceDf(df)
for df in (pd_allStudies, pd_withdrawnStudies):
    if not df.empty:
        pddfutils.tidyStudyDf(df)
for df in (pd_allContacts, pd_withdrawnContacts):
    if not df.empty:
        pddfutils.tidyContactDf(df)
for df in (pd_allNetworks, pd_withdrawnNetworks):
    if not df.empty:
        pddfutils.tidyNetworkDf(df)

if args.outputXLSX is not None:
    extra_sheets = []
    if args.includeWithdrawnSheetsInOutput:
        extra_sheets.extend(
            [
                (pd_withdrawnBiobanks, "Withdrawn biobanks", True, {"hyperlink_columns": [("id", "directoryURL")]}),
                (pd_withdrawnCollections, "Withdrawn collections", True, {"hyperlink_columns": [("id", "directoryURL")]}),
                (pd_withdrawnServices, "Withdrawn services", True, {"hyperlink_columns": [("id", "directoryURL")]}),
                (pd_withdrawnStudies, "Withdrawn studies", True, {"hyperlink_columns": [("id", "directoryURL")]}),
                (pd_withdrawnContacts, "Withdrawn contacts", True, {"hyperlink_columns": [("id", "directoryURL")]}),
                (pd_withdrawnNetworks, "Withdrawn networks", True, {"hyperlink_columns": [("id", "directoryURL")]}),
            ]
        )
    outputExcelDirectoryEntities(
        args.outputXLSX[0],
        pd_allBiobanks,
        "Biobanks",
        pd_allCollections,
        "Collections",
        pd_allServices,
        "Services",
        pd_allStudies,
        "Studies",
        pd_allContacts,
        "Contacts",
        pd_allNetworks,
        "Networks",
        extra_sheets,
    )

if args.outputXLSXwithdrawn is not None:
    outputExcelDirectoryEntities(
        args.outputXLSXwithdrawn[0],
        pd_withdrawnBiobanks,
        "Withdrawn biobanks",
        pd_withdrawnCollections,
        "Withdrawn collections",
        pd_withdrawnServices,
        "Withdrawn services",
        pd_withdrawnStudies,
        "Withdrawn studies",
        pd_withdrawnContacts,
        "Withdrawn contacts",
        pd_withdrawnNetworks,
        "Withdrawn networks",
    )
