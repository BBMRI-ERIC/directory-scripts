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
    add_directory_schema_argument,
    add_logging_arguments,
    add_no_stdout_argument,
    add_purge_cache_arguments,
    add_withdrawn_scope_arguments,
    add_xlsx_output_argument,
    build_directory_kwargs,
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
add_directory_schema_argument(parser, default="ERIC")
add_withdrawn_scope_arguments(parser)
add_purge_cache_arguments(parser, cachesList)
parser.set_defaults(purgeCaches=[])
args = parser.parse_args()

configure_logging(args)


# Main code

dir = Directory(**build_directory_kwargs(args, pp=pp))

log.info('Total biobanks: ' + str(dir.getBiobanksCount()))
log.info('Total collections: ' + str(dir.getCollectionsCount()))

ecraidBSLCollections = []
ecraidPathogenCollections = []
ecraidRelevantBiobankIds = set()

for collection in dir.getCollections():
    log.debug("Analyzing collection " + collection['id'])
    biobankId = dir.getCollectionBiobankId(collection['id'])
    biobank = dir.getBiobankById(biobankId)

    biobank_capabilities = Directory.getListOfEntityAttributeIds(biobank, 'capabilities')
    biobank_covid = Directory.getListOfEntityAttributeIds(biobank, 'covid19biobank')
    biobank_networks = Directory.getListOfEntityAttributeIds(biobank, 'network')
    collection_networks = Directory.getListOfEntityAttributeIds(collection, 'network')

    OoM = Directory.getEntityAttributeId(collection.get('order_of_magnitude'))

    materials = Directory.getListOfEntityAttributeIds(collection, 'materials')
    data_categories = Directory.getListOfEntityAttributeIds(collection, 'data_categories')
    types = Directory.getListOfEntityAttributeIds(collection, 'type')
    log.debug("Types: " + str(types))
    
    diags = []
    diag_ranges = []
    covid_diag = False
    covid_control = False
    covid_prospective = False
    non_covid = False

    if 'diagnosis_available' in collection:
        for d in Directory.getListOfEntityAttributeIds(collection, 'diagnosis_available'):
            if re.search('-', str(d)):
                diag_ranges.append(d)
            else:
                diags.append(d)

    if diag_ranges:
        log.warning("There are diagnosis ranges provided for collection " + collection['id'] + ": " + str(diag_ranges))
    
    if 'BSL2' in biobank_covid or 'BSL3' in biobank_covid:
        ecraidBSLCollections.append(collection)
        ecraidRelevantBiobankIds.add(biobankId)
    
    if 'PATHOGEN' in materials:
        ecraidPathogenCollections.append(collection)
        ecraidRelevantBiobankIds.add(biobankId)

collection_columns = list(dir.getCollections()[0].keys()) if dir.getCollections() else []
biobank_columns = list(dir.getBiobanks()[0].keys()) if dir.getBiobanks() else []

pd_ecraidBSLCollections = pd.DataFrame(ecraidBSLCollections, columns=collection_columns)
pd_ecraidPathogenCollections = pd.DataFrame(ecraidPathogenCollections, columns=collection_columns)

ecraidRelevantBiobanks = []
for b in ecraidRelevantBiobankIds:
    ecraidRelevantBiobanks.append(dir.getBiobankById(b))
pd_ecraidRelevantBiobanks = pd.DataFrame(ecraidRelevantBiobanks, columns=biobank_columns)

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
