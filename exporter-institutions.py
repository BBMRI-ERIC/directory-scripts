#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

from typing import List

import pprint
import re
import argparse
import logging as log
import time
from typing import List
import os.path

import xlsxwriter
import pandas as pd

from directory import Directory


cachesList = ['directory', 'emails', 'geocoding', 'URLs']

pp = pprint.PrettyPrinter(indent=4)

class ExtendAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest) or []
        items.extend(values)
        setattr(namespace, self.dest, items)

parser = argparse.ArgumentParser()
parser.register('action', 'extend', ExtendAction)
parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='verbose information on progress of the data checks')
parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='debug information on progress of the data checks')
parser.add_argument('-X', '--output-XLSX', dest='outputXLSX', nargs=1, help='output of results into XLSX with filename provided as parameter')
parser.add_argument('-N', '--output-no-stdout', dest='nostdout', action='store_true', help='no output of results into stdout (default: enabled)')
parser.add_argument('--purge-all-caches', dest='purgeCaches', action='store_const', const=cachesList, help='disable all long remote checks (email address testing, geocoding, URLs')
parser.add_argument('--purge-cache', dest='purgeCaches', nargs='+', action='extend', choices=cachesList, help='disable particular long remote checks')
parser.set_defaults(disableChecksRemote = [], disablePlugins = [], purgeCaches=[])
args = parser.parse_args()

if args.debug:
    log.basicConfig(format="%(levelname)s: %(message)s", level=log.DEBUG)
elif args.verbose:
    log.basicConfig(format="%(levelname)s: %(message)s", level=log.INFO)
else:
    log.basicConfig(format="%(levelname)s: %(message)s")


# Main code

dir = Directory(purgeCaches=args.purgeCaches, debug=args.debug, pp=pp)

log.info('Total biobanks: ' + str(dir.getBiobanksCount()))
log.info('Total collections: ' + str(dir.getCollectionsCount()))

countryInstitutions = {}

for biobank in dir.getBiobanks():
    biobankId = biobank['id']
    biobankJuridicalPerson = biobank['juridical_person']
    biobankCountry = biobank['country']['id']
    if not biobankCountry in countryInstitutions:
        countryInstitutions[biobankCountry] = set()
    log.debug(f"Biobank {biobankId} from institution {biobankJuridicalPerson} added to country {biobankCountry}")
    countryInstitutions[biobankCountry].add(biobankJuridicalPerson)

if args.verbose:
    for country in sorted(countryInstitutions):
        print(f"{country}: institutions total = {len(countryInstitutions[country])}")

if not args.nostdout:
    for country in sorted(countryInstitutions):
        for institution in sorted(countryInstitutions[country]):
            print(f"{country}\t{institution}")

if args.outputXLSX is not None:
    pd_countryInstitutions = pd.DataFrame([{'Country' : country, 'Institution' : institution} for country in sorted(countryInstitutions) for institution in sorted(countryInstitutions[country])])
    log.info("Outputting warnings in Excel file " + args.outputXLSX[0])
    writer = pd.ExcelWriter(args.outputXLSX[0], engine='xlsxwriter')
    pd_countryInstitutions.to_excel(writer, sheet_name='Institutions')
    writer.save()
