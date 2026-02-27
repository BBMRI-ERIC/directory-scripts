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

cohortCollections = []
cohortBiobankIds = set()
cohortCountries = set()

for collection in dir.getCollections():
    log.debug("Analyzing collection " + collection['id'])
    biobankId = dir.getCollectionBiobankId(collection['id'])
    biobank = dir.getBiobankById(biobankId)
    country = biobank['country']

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

    OoM = collection['order_of_magnitude']

    materials = []
    if 'materials' in collection:
        for m in collection['materials']:
            materials.append(m)
    
    data_categories = []
    if 'data_categories' in collection:
        for c in collection['data_categories']:
            data_categories.append(c)

    types = []
    if 'type' in collection:
        for t in collection['type']:
            types.append(t)
    log.debug("Types: " + str(types))
    
    diags = []
    diag_ranges = []
    covid_diag = False
    covid_control = False
    covid_prospective = False
    non_covid = False

    if 'diagnosis_available' in collection:
        for d in collection['diagnosis_available']:
            if re.search('-', d['name']):
                diag_ranges.append(d['name'])
            else:
                diags.append(d['name'])

    if diag_ranges:
        log.warning("There are diagnosis ranges provided for collection " + collection['id'] + ": " + str(diag_ranges))
    
    if 'COHORT' in types or 'POPULATION_BASED' in types:
        cohortCollections.append(collection)
        cohortBiobankIds.add(biobankId)
        cohortCountries.add(country)

pd_cohortCollections = pd.DataFrame(cohortCollections)
pddfutils.tidyBiobankDf(pd_cohortCollections)

def printCollectionStdout(collectionList : List, headerStr : str):
    print(headerStr + " - " + str(len(collectionList)) + " collections")
    for collection in collectionList:
        biobankId = dir.getCollectionBiobankId(collection['id'])
        biobank = dir.getBiobankById(biobankId)
        print("   Collection: " + collection['id'] + " - " + collection['name'] + ". Parent biobank: " +  biobankId + " - " + biobank['name'])

if not args.nostdout:
    printCollectionStdout(cohortCollections, "Cohort collections")
    print("List of countries: %s"%(", ".join(sorted(cohortCountries))))
    print("\n\n")
    print("Totals:")
    print("- total number of cohort biobanks: %d"%(len(cohortBiobankIds)))
    print("- total number of cohort collections: %d"%(len(cohortCollections)))
    print("- total number of cohort countries: %d"%(len(cohortCountries)))

if args.outputXLSX is not None:
    write_xlsx_tables(
        args.outputXLSX[0],
        [(pd_cohortCollections, 'Cohort collections', False)],
    )
