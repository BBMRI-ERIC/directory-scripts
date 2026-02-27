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

countryBiobanks = {}
countryBiobanksWithCollections = {}
countryCollections = {}

for collection in dir.getCollections():
    collectionId = collection['id']
    log.debug("Analyzing collection " + collectionId)
    biobankId = dir.getCollectionBiobankId(collectionId)
    biobank = dir.getBiobankById(biobankId)
    NN = dir.getBiobankNN(biobankId)
    if not NN in countryBiobanks:
        countryBiobanks[NN] = set()
    if not NN in countryBiobanksWithCollections:
        countryBiobanksWithCollections[NN] = set()
    if not NN in countryCollections:
        countryCollections[NN] = set()
    countryBiobanks[NN].add(biobankId)
    countryBiobanksWithCollections[NN].add(biobankId)
    countryCollections[NN].add(collectionId)
    
for biobank in dir.getBiobanks():
    biobankId = biobank['id']
    NN = dir.getBiobankNN(biobankId)
    if not NN in countryBiobanks:
        countryBiobanks[NN] = set()
    if not biobankId in countryBiobanks[NN]:
        log.info(f"Biobank {biobankId} without having collections")
        countryBiobanks[NN].add(biobankId)

output_rows = []
for NN in sorted(countryBiobanks):
    output_rows.append(
        {
            'Country': NN,
            'Biobanks total': len(countryBiobanks[NN]),
            'Biobanks with collections': len(countryBiobanksWithCollections[NN]),
            'Collections': len(countryCollections[NN]),
        }
    )
    if not args.nostdout:
        print(
            f"{NN}: biobanks total = {len(countryBiobanks[NN])}, "
            f"biobanks with collections = {len(countryBiobanksWithCollections[NN])}, "
            f"collections = {len(countryCollections[NN])}"
        )

if args.outputXLSX is not None:
    pd.DataFrame(output_rows).to_excel(
        args.outputXLSX[0],
        sheet_name='Country summary',
        index=False,
    )

#for collection in countryCollections['UK']:
#   print(f"{collection}")
