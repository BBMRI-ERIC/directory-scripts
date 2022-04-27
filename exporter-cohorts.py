#!/usr/bin/python3
# vim:ts=8:sw=8:tw=0:noet

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
import pddfutils

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

cohortCollections = []
cohortBiobankIds = set()
cohortCountries = set()

for collection in dir.getCollections():
	log.debug("Analyzing collection " + collection['id'])
	biobankId = dir.getCollectionBiobankId(collection['id'])
	biobank = dir.getBiobankById(biobankId)
	country = biobank['country']['id']

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
	log.info("Outputting warnings in Excel file " + args.outputXLSX[0])
	writer = pd.ExcelWriter(args.outputXLSX[0], engine='xlsxwriter')
	pd_cohortCountries.to_excel(writer, sheet_name='Cohort collections',index=False)
	writer.save()
