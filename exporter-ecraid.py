#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

from typing import List

import pprint
import re
import logging as log
import time
from typing import List
import os.path

import pandas as pd

from cli_common import (
    add_logging_arguments,
    add_no_stdout_argument,
    add_purge_cache_arguments,
    add_xlsx_output_argument,
    build_parser,
    configure_logging,
)
from directory import Directory
import pddfutils
from xlsxutils import write_xlsx_tables

cachesList = ['directory']

pp = pprint.PrettyPrinter(indent=4)

parser = build_parser()
add_logging_arguments(parser)
add_xlsx_output_argument(parser)
add_no_stdout_argument(parser)
add_purge_cache_arguments(parser, cachesList)
parser.set_defaults(purgeCaches=[])
args = parser.parse_args()

configure_logging(args)


# Main code

dir = Directory(purgeCaches=args.purgeCaches, debug=args.debug, pp=pp)

log.info('Total biobanks: ' + str(dir.getBiobanksCount()))
log.info('Total collections: ' + str(dir.getCollectionsCount()))

ecraidBSLCollections = []
ecraidPathogenCollections = []
ecraidRelevantBiobankIds = set()

for collection in dir.getCollections():
    log.debug("Analyzing collection " + collection['id'])
    biobankId = dir.getCollectionBiobankId(collection['id'])
    biobank = dir.getBiobankById(biobankId)

    biobank_capabilities = []
    if 'capabilities' in biobank:
        for c in biobank['capabilities']:
            biobank_capabilities.append(c['id'])
    biobank_covid = []
    if 'covid19biobank' in biobank:
        for c in biobank['covid19biobank']:
            biobank_covid.append(c['id'])
    biobank_networks = []
    if 'network' in biobank:
        for n in biobank['network']:
            biobank_networks.append(n['id'])
    collection_networks = []
    if 'network' in collection:
        for n in collection['network']:
            collection_networks.append(n['id'])

    OoM = collection['order_of_magnitude']['id']

    materials = []
    if 'materials' in collection:
        for m in collection['materials']:
            materials.append(m['id'])
    
    data_categories = []
    if 'data_categories' in collection:
        for c in collection['data_categories']:
            data_categories.append(c['id'])

    types = []
    if 'type' in collection:
        for t in collection['type']:
            types.append(t['id'])
    log.debug("Types: " + str(types))
    
    diags = []
    diag_ranges = []
    covid_diag = False
    covid_control = False
    covid_prospective = False
    non_covid = False

    for d in collection['diagnosis_available']:
        if re.search('-', d['id']):
            diag_ranges.append(d['id'])
        else:
            diags.append(d['id'])

    if diag_ranges:
        log.warning("There are diagnosis ranges provided for collection " + collection['id'] + ": " + str(diag_ranges))
    
    if 'BSL2' in biobank_covid or 'BSL3' in biobank_covid:
        ecraidBSLCollections.append(collection)
        ecraidRelevantBiobankIds.add(biobankId)
    
    if 'PATHOGEN' in materials:
        ecraidPathogenCollections.append(collection)
        ecraidRelevantBiobankIds.add(biobankId)

pd_ecraidBSLCollections = pd.DataFrame(ecraidBSLCollections)
pd_ecraidPathogenCollections = pd.DataFrame(ecraidPathogenCollections)

ecraidRelevantBiobanks = []
for b in ecraidRelevantBiobankIds:
    ecraidRelevantBiobanks.append(dir.getBiobankById(b))
pd_ecraidRelevantBiobanks = pd.DataFrame(ecraidRelevantBiobanks)

def printCollectionStdout(collectionList : List, headerStr : str):
    print(headerStr + " - " + str(len(collectionList)) + " collections")
    for collection in collectionList:
        biobankId = dir.getCollectionBiobankId(collection['id'])
        biobank = dir.getBiobankById(biobankId)
        print("   Collection: " + collection['id'] + " - " + collection['name'] + ". Parent biobank: " +  biobankId + " - " + biobank['name'])

if not args.nostdout:
    printCollectionStdout(ecraidBSLCollections, "ECRAID-relevant collections with BSL-2/BSL-3 labs")
    print("\n\n")
    printCollectionStdout(ecraidPathogenCollections, "ECRAID-relevant pathogen collections")
    print("\n\n")
    print("Totals:")
    print("- total number of ECRAID-relevant biobanks: %d"%(len(ecraidRelevantBiobanks)))
    print("- total number of ECRAID-relevant collections with BSL-2/BSL-3 labs: %d"%(len(ecraidBSLCollections)))
    print("- total number of ECRAID-relevant pathogen collections: %d"%(len(ecraidPathogenCollections)))

for df in (pd_ecraidBSLCollections,pd_ecraidPathogenCollections):
    pddfutils.tidyCollectionDf(df)

pddfutils.tidyBiobankDf(pd_ecraidRelevantBiobanks)

if args.outputXLSX is not None:
    write_xlsx_tables(
        args.outputXLSX[0],
        [
            (pd_ecraidBSLCollections, 'Collections with BSL labs', False),
            (pd_ecraidPathogenCollections, 'Pathogen collections', False),
            (pd_ecraidRelevantBiobanks, 'Institutions', False),
        ],
    )
