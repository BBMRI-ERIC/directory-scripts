#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

import pprint
import re
import argparse
import logging as log
from builtins import str, isinstance, len, set, int
from typing import List
import json

import pandas as pd

from directory import Directory
from orphacodes import OrphaCodes
from icd10codeshelper import ICD10CodesHelper
import pddfutils

cachesList = ['directory', 'emails', 'geocoding', 'URLs']

pp = pprint.PrettyPrinter(indent=4)


class ExtendAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        from builtins import getattr, setattr
        items = getattr(namespace, self.dest) or []
        items.extend(values)
        setattr(namespace, self.dest, items)


parser = argparse.ArgumentParser()
parser.register('action', 'extend', ExtendAction)
parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                    help='verbose information on progress of the data checks')
parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                    help='debug information on progress of the data checks')
parser.add_argument('-X', '--output-XLSX', dest='outputXLSX', nargs=1,
                    help='output of results into an XLSX with filename provided as parameter')
parser.add_argument('--output-XLSX-withdrawn', dest='outputXLSXwithdrawn', nargs=1,
                    help='output withdrawn biobanks and collections into an XLSX with filename provided as parameter')
parser.add_argument('-N', '--output-no-stdout', dest='nostdout', action='store_true',
                    help='no output of results into stdout (default: enabled)')
parser.add_argument('--purge-all-caches', dest='purgeCaches', action='store_const', const=cachesList,
                    help='disable all long remote checks (email address testing, geocoding, URLs')
parser.add_argument('--purge-cache', dest='purgeCaches', nargs='+', action='extend', choices=cachesList,
                    help='disable particular long remote checks')
parser.set_defaults(disableChecksRemote=[], disablePlugins=[], purgeCaches=[])
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

allCollections = []
withdrawnCollections = []
allBiobanks = set()
withdrawnBiobanks = set()
allCollectionSamplesExplicit = 0
allCollectionDonorsExplicit = 0
allCollectionSamplesIncOoM = 0
allCountries = set()

for collection in dir.getCollections():
    log.debug("Analyzing collection " + collection['id'])
    biobankId = dir.getCollectionBiobankId(collection['id'])
    biobank = dir.getBiobankById(biobankId)

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


    allCountries.add(biobank['country']['id'])
    allCollections.append(collection)
    allBiobanks.add(biobankId)
    if 'size' in collection and isinstance(collection['size'], int):
        allCollectionSamplesExplicit += collection['size']
        allCollectionSamplesIncOoM += collection['size']
    else:
        allCollectionSamplesIncOoM += int(10 ** OoM)
    if 'number_of_donors' in collection and isinstance(collection['number_of_donors'], int):
        allCollectionDonorsExplicit += collection['number_of_donors']

for biobank in dir.getBiobanks():
    biobankId = biobank['id']
    log.debug("Analyzing biobank " + biobankId)
    if not biobankId in allBiobanks and not biobankId in withdrawnBiobanks:
        log.info("   Biobank without any collection identified: " + biobankId)
        if 'withdrawn' in biobank and biobank['withdrawn']:
            withdrawnBiobanks.add(biobankId)
            log.debug("Detected a withdrawn biobank without any collection " + biobankId)
        else:
            allBiobanks.add(biobankId)

pd_allCollections = pd.DataFrame(allCollections)
pd_withdrawnCollections = pd.DataFrame(withdrawnCollections)
pd_allBiobanks = pd.DataFrame([dir.getBiobankById(biobankId) for biobankId in allBiobanks])
pd_withdrawnBiobanks = pd.DataFrame([dir.getBiobankById(biobankId) for biobankId in withdrawnBiobanks])

def printCollectionStdout(collectionList: List):
    for collection in collectionList:
        biobankId = dir.getCollectionBiobankId(collection['id'])
        biobank = dir.getBiobankById(biobankId)
        log.info("   Collection: " + collection['id'] + " - " + collection['name'] + ". Parent biobank: " + biobankId + " - " + biobank['name'])
    log.info("\n\n")

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
    print("- total of samples advertised in all-relevant collections including OoM estimates: %d" % (
        allCollectionSamplesIncOoM))

for df in (pd_allCollections, pd_withdrawnCollections):
    pddfutils.tidyCollectionDf(df)
for df in (pd_allBiobanks, pd_withdrawnBiobanks):
    pddfutils.tidyBiobankDf(df)

def outputExcelBiobanksCollections(filename : str, dfBiobanks : pd.DataFrame, biobanksLabel : str, dfCollections : pd.DataFrame, collectionsLabel : str):
    log.info("Outputting warnings in Excel file " + filename)
    writer = pd.ExcelWriter(filename, engine='xlsxwriter')
    dfBiobanks.to_excel(writer, sheet_name=biobanksLabel)
    dfCollections.to_excel(writer, sheet_name=collectionsLabel)
    writer.save()

if args.outputXLSX is not None:
    outputExcelBiobanksCollections(args.outputXLSX[0], pd_allBiobanks, "Biobanks", pd_allCollections, "Collections")

if args.outputXLSXwithdrawn is not None:
    outputExcelBiobanksCollections(args.outputXLSXwithdrawn[0], pd_withdrawnBiobanks, "Withdrawn biobanks", pd_withdrawnCollections, "Withdrawn collections")
