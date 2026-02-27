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

countryInstitutions = {}

for biobank in dir.getBiobanks():
    biobankId = biobank['id']
    try:
        biobankJuridicalPerson = biobank['juridical_person']
        biobankCountry = biobank['country']
        if not biobankCountry in countryInstitutions:
            countryInstitutions[biobankCountry] = set()
        log.debug(f"Biobank {biobankId} from institution {biobankJuridicalPerson} added to country {biobankCountry}")
        countryInstitutions[biobankCountry].add(biobankJuridicalPerson)
    except KeyError:
        log.error("Biobank " + biobankId + " has no juridical person set!")

if args.verbose:
    for country in sorted(countryInstitutions):
        print(f"{country}: institutions total = {len(countryInstitutions[country])}")

if not args.nostdout:
    for country in sorted(countryInstitutions):
        for institution in sorted(countryInstitutions[country]):
            print(f"{country}\t{institution}")

if args.outputXLSX is not None:
    pd_countryInstitutions = pd.DataFrame([{'Country' : country, 'Institution' : institution} for country in sorted(countryInstitutions) for institution in sorted(countryInstitutions[country])])
    write_xlsx_tables(args.outputXLSX[0], [(pd_countryInstitutions, 'Institutions')])
