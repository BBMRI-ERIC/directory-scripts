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

countryBiobanks = {}
countryBiobanksWithCollections = {}
countryCollections = {}

for collection in dir.getCollections():
    collectionId = collection['id']
    log.debug("Analyzing collection " + collectionId)
    biobankId = dir.getCollectionBiobankId(collectionId)
    biobank = dir.getBiobankById(biobankId)
    country_code = dir.getBiobankCountry(biobankId)
    if country_code not in countryBiobanks:
        countryBiobanks[country_code] = set()
    if country_code not in countryBiobanksWithCollections:
        countryBiobanksWithCollections[country_code] = set()
    if country_code not in countryCollections:
        countryCollections[country_code] = set()
    countryBiobanks[country_code].add(biobankId)
    countryBiobanksWithCollections[country_code].add(biobankId)
    countryCollections[country_code].add(collectionId)
    
for biobank in dir.getBiobanks():
    biobankId = biobank['id']
    country_code = dir.getBiobankCountry(biobankId)
    if country_code not in countryBiobanks:
        countryBiobanks[country_code] = set()
    if biobankId not in countryBiobanks[country_code]:
        log.info(f"Biobank {biobankId} without having collections")
        countryBiobanks[country_code].add(biobankId)

output_rows = []
for country_code in sorted(countryBiobanks):
    output_rows.append(
        {
            'Country': country_code,
            'Biobanks total': len(countryBiobanks[country_code]),
            'Biobanks with collections': len(countryBiobanksWithCollections.get(country_code, set())),
            'Collections': len(countryCollections.get(country_code, set())),
        }
    )
    if not args.nostdout:
        print(
            f"{country_code}: biobanks total = {len(countryBiobanks[country_code])}, "
            f"biobanks with collections = {len(countryBiobanksWithCollections.get(country_code, set()))}, "
            f"collections = {len(countryCollections.get(country_code, set()))}"
        )

if args.outputXLSX is not None:
    pd.DataFrame(output_rows).to_excel(
        args.outputXLSX[0],
        sheet_name='Country summary',
        index=False,
    )

#for collection in countryCollections['UK']:
#   print(f"{collection}")
