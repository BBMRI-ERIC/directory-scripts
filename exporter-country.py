#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:et

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

for NN in sorted(countryBiobanks):
    print(f"{NN}: biobanks total = {len(countryBiobanks[NN])}, biobanks with collections = {len(countryBiobanksWithCollections[NN])}, collections = {len(countryCollections[NN])}")

#for collection in countryCollections['UK']:
#   print(f"{collection}")
