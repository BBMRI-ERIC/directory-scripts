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

covidExistingDiagnosed = []
covidExistingControls = []
covidProspective = []

for collection in dir.getCollections():
	log.debug("Analyzing collection " + collection['id'])
	biobankId = dir.getCollectionBiobank(collection['id'])
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

	for d in collection['diagnosis_available']:
		if re.search('-', d['id']):
			diag_ranges.append(d['id'])
		else:
			diags.append(d['id'])

	if diag_ranges:
		log.warning("There are diagnosis ranges provided for collection " + collection['id'] + ": " + str(diag_ranges))

	log.debug(str(collection['diagnosis_available']))

	for d in diags+diag_ranges:
		# ICD-10
		if re.search('U07', d):
			covid_diag = True
		# ICD-10
		if re.search('Z03.818', d):
			covid_control = True
		# ICD-11
		if re.search('RA01', d):
			covid_diag = True
		# SNOMED CT
		if re.search('(840533007|840534001|840535000|840536004|840539006|840544004|840546002)', d):
			covid_diag = True

	if types:
		if 'PROSPECTIVE_STUDY' in types and (covid_diag or covid_control):
			covid_prospective = True
	
	if re.search('COVID19PROSPECTIVE', collection['id']):
		if types and not 'PROSPECTIVE_STUDY' in types:
			log.warning("Prospective study by ID but not by collection type for collectionID " + collection['id'])
		covid_prospective = True
	
	if re.search('^Ability to collect', collection['name']):
		if types and not 'PROSPECTIVE_STUDY' in types:
			log.warning("Prospective study by name but not by collection type for collectionID " + collection['id'])
		if not re.search('COVID19PROSPECTIVE', collection['id']):
			log.warning("Prospective study by name but missing correct collection ID for collectionID " + collection['id'])
		covid_prospective = True
	
	if re.search('COVID19', collection['id']) and not (covid_diag or covid_control or covid_prospective):
		log.warning("Incorrectly types COVID collectionID - missing diagnosis " + collection['id'])
		covid_diag = True
	
	if covid_diag and not covid_prospective:
		log.info("Collection " + collection['id'] + " has COVID-positive cases")
		covidExistingDiagnosed.append(collection)
	if covid_control and not covid_prospective:
		log.info("Collection " + collection['id'] + " has control cases for COVID")
		covidExistingControls.append(collection)
	if covid_prospective:
		log.info("Collection " + collection['id'] + " is a prospective COVID collection")
		covidProspective.append(collection)

pd_covidExistingDiagnosed = pd.DataFrame(covidExistingDiagnosed)
pd_covidExistingControls = pd.DataFrame(covidExistingControls)
pd_covidProspective = pd.DataFrame(covidProspective)

def printCollectionStdout(collectionList : List, headerStr : str):
	print(headerStr + " - " + str(len(collectionList)) + " collections")
	for collection in collectionList:
		biobankId = dir.getCollectionBiobank(collection['id'])
		biobank = dir.getBiobankById(biobankId)
		print("   Collection: " + collection['id'] + " - " + collection['name'] + ". Parent biobank: " +  biobankId + " - " + biobank['name'] + "\n")

if not args.nostdout:
	log.info("Outputting warnings on stdout")
	printCollectionStdout(covidExistingDiagnosed, "COVID Diagnosed")
	print("\n\n")
	printCollectionStdout(covidExistingControls, "COVID Controls")
	print("\n\n")
	printCollectionStdout(covidProspective, "COVID Prospective")

if args.outputXLSX is not None:
	log.info("Outputting warnings in Excel file " + args.outputXLSX[0])
	writer = pd.ExcelWriter(args.outputXLSX[0], engine='xlsxwriter')
	pd_covidExistingDiagnosed.to_excel(writer, sheet_name='COVID Diagnosed')
	pd_covidExistingControls.to_excel(writer, sheet_name='COVID Controls')
	pd_covidProspective.to_excel(writer, sheet_name='COVID Prospective')
	writer.save()
