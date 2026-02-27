#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

import pprint
import logging as log
from builtins import str, isinstance, len, set, int
from typing import List

import pandas as pd

from cli_common import (
    add_logging_arguments,
    add_no_stdout_argument,
    add_optional_xlsx_output_argument,
    add_purge_cache_arguments,
    add_xlsx_output_argument,
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
add_purge_cache_arguments(parser, cachesList)
parser.add_argument('-FCT', '--filter-collection-type', '--filter-coll-type', dest='filterCollType', nargs='+', action='extend',
                    help='filter by the collection types in the data model, each of them between quotes ("") and separated by a space. E.g.: -FCT "CASE_CONTROL" "LONGITUDINAL" "DISEASE_SPECIFIC"') # TODO: Till now it uses the terms from the data model, different from the ones displayed in Directory
parser.add_argument('-FMT', '--filter-material-type', dest='filterMatType', nargs='+', action='extend',
                    help='filter by the material types in the data model, each of them between quotes ("") and separated by a space. E.g.: -FCT "SERUM" "SAMPLE"') # TODO: Till now it uses the terms from the data model, different from the ones displayed in Directory


parser.set_defaults(purgeCaches=[], filterCollType=[], filterMatType=[])
args = parser.parse_args()
filterCollType = args.filterCollType
filterMatType = args.filterMatType

configure_logging(args)


### Initialize variables
allCollections = []
withdrawnCollections = []
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
def analyseCollections(collections, allCollectionSamplesExplicit, allCollectionDonorsExplicit, allCollectionSamplesIncOoM, allCollectionDonorsIncOoM):
    for collection in collections:
        log.debug("Analyzing collection " + collection['id'])
        biobankId = dir.getCollectionBiobankId(collection['id'])
        biobank = dir.getBiobankById(biobankId)
        
        if 'contact' in collection:
            collection['contact'] = dir.getContact(collection['contact']['id'])

        collection_withdrawn = False
        if 'withdrawn' in collection and collection['withdrawn']:
            withdrawnCollections.append(collection)
            log.debug("Detected a withdrawn collection: " + collection['id'])
            collection_withdrawn = True
        if 'withdrawn' in biobank and biobank['withdrawn']:
            withdrawnBiobanks.add(biobankId)
            if not collection_withdrawn:
                log.debug("Detected a withdrawn collection " + collection['id'] + " because a withdrawn biobank: " + biobankId)
                collection_withdrawn = True
        if collection_withdrawn:
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
            collection['directoryURL'] = 'https://directory.bbmri-eric.eu/ERIC/directory/#/collection/' + collection['id']

    return allCollections, withdrawnCollections, allCollectionSamplesExplicit, allCollectionDonorsExplicit, allCollectionSamplesIncOoM, allCollectionDonorsIncOoM, allBiobanks

def analyseBBs():
    for biobank in dir.getBiobanks():
        biobankId = biobank['id']
        if 'contact' in biobank:
            biobank['contact'] = dir.getContact(biobank['contact']['id'])
        log.debug("Analyzing biobank " + biobankId)
        if not biobankId in allBiobanks and not biobankId in withdrawnBiobanks:
            log.info("   Biobank without any collection identified: " + biobankId)
            if 'withdrawn' in biobank and biobank['withdrawn']:
                withdrawnBiobanks.add(biobankId)
                log.debug("Detected a withdrawn biobank without any collection " + biobankId)
            else:
                allBiobanks.add(biobankId)
    return allBiobanks

def printCollectionStdout(collectionList: List):
    for collection in collectionList:
        biobankId = dir.getCollectionBiobankId(collection['id'])
        biobank = dir.getBiobankById(biobankId)
        log.info("   Collection: " + collection['id'] + " - " + collection['name'] + ". Parent biobank: " + biobankId + " - " + biobank['name'])
    log.info("\n\n")

def outputExcelBiobanksCollections(filename : str, dfBiobanks : pd.DataFrame, biobanksLabel : str, dfCollections : pd.DataFrame, collectionsLabel : str):
    write_xlsx_tables(
        filename,
        [
            (dfBiobanks, biobanksLabel),
            (dfCollections, collectionsLabel),
        ],
    )

### Main

dir = Directory(purgeCaches=args.purgeCaches, debug=args.debug, pp=pp)

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

pd_allCollections = pd.DataFrame(allCollections)
pd_withdrawnCollections = pd.DataFrame(withdrawnCollections)
pd_allBiobanks = pd.DataFrame([dir.getBiobankById(biobankId) for biobankId in allBiobanks])
pd_withdrawnBiobanks = pd.DataFrame([dir.getBiobankById(biobankId) for biobankId in withdrawnBiobanks])

if not args.nostdout:
    printCollectionStdout(allCollections)
    print("Totals:")
    print("- total of biobanks: %d" % (len(allBiobanks)))
    print("- total of withdrawn biobanks: %d" % (len(withdrawnBiobanks)))
    print("- total of collections with existing samples: %d" % (len(allCollections)))
    print("- total of countries: %d" % ( len(allCountries)))
    print("Estimated totals:")
    print("- total of samples/donors advertised explicitly in all-relevant collections: %d / %d" % (
        allCollectionSamplesExplicit, allCollectionDonorsExplicit))
    print("- total of samples/donors advertised in all-relevant collections including OoM estimates: %d / %d" % (
        allCollectionSamplesIncOoM, allCollectionDonorsIncOoM))

for df in (pd_allCollections, pd_withdrawnCollections):
    pddfutils.tidyCollectionDf(df)
for df in (pd_allBiobanks, pd_withdrawnBiobanks):
    pddfutils.tidyBiobankDf(df)

if args.outputXLSX is not None:
    outputExcelBiobanksCollections(args.outputXLSX[0], pd_allBiobanks, "Biobanks", pd_allCollections, "Collections")

if args.outputXLSXwithdrawn is not None:
    outputExcelBiobanksCollections(args.outputXLSXwithdrawn[0], pd_withdrawnBiobanks, "Withdrawn biobanks", pd_withdrawnCollections, "Withdrawn collections")
