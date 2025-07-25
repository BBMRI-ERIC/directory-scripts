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

covidExistingDiagnosed = []
covidExistingControls = []
covidProspective = []
covidOther = []
covidOnlyExistingDiagnosed = []
covidBiobanksExistingDiagnosed = set()
covidOnlyBiobanksExistingDiagnosed = set()
covidBiobanksExistingControls = set()
covidBiobanksProspective = set()
covidBiobanksOther = set()
covidBiobanks = set()
covidCollectionSamplesExplicit = 0
covidCollectionDonorsExplicit = 0
covidCollectionSamplesIncOoM = 0
covidOnlyCollectionSamplesExplicit = 0
covidOnlyCollectionDonorsExplicit = 0
covidOnlyCollectionSamplesIncOoM = 0

for collection in dir.getCollections():
    log.debug("Analyzing collection " + collection['id'])
    biobankId = dir.getCollectionBiobankId(collection['id'])
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
    collection_networks = []
    if 'network' in collection:
        for n in collection['network']:
            collection_networks.append(n['id'])

    OoM = int(collection['order_of_magnitude'])

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
        
        log.debug(str(collection['diagnosis_available']))

    if diag_ranges:
        log.warning("There are diagnosis ranges provided for collection " + collection['id'] + ": " + str(diag_ranges))

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

    # now we try to get as pessimistic estimates as possible
    if not diag_ranges:
        for d in diags:
            if not (re.search('U07', d) or re.search('RA01', d) or re.search('(840533007|840534001|840535000|840536004|840539006|840544004|840546002)', d)):
                non_covid = True
    else:
        non_covid = True

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
        covidBiobanksExistingDiagnosed.add(biobankId)
        if not non_covid:
            covidOnlyExistingDiagnosed.append(collection)
            covidOnlyBiobanksExistingDiagnosed.add(biobankId)
        if 'size' in collection and isinstance(collection['size'], int):
            covidCollectionSamplesExplicit += collection['size']
            covidCollectionSamplesIncOoM += collection['size']
            if not non_covid:
                covidOnlyCollectionSamplesExplicit += collection['size']
                covidOnlyCollectionSamplesIncOoM += collection['size']
        else:
            covidCollectionSamplesIncOoM += 10**OoM
            if not non_covid:
                covidOnlyCollectionSamplesIncOoM += 10**OoM
        if 'number_of_donors' in collection and isinstance(collection['number_of_donors'], int):
            covidCollectionDonorsExplicit += collection['number_of_donors']
            if not non_covid:
                covidOnlyCollectionDonorsExplicit += collection['number_of_donors']

    if covid_diag and non_covid:
        log.info("Collection " + collection['id'] + " has a mixture of COVID and non-COVID diagnoses: %s"%(diags+diag_ranges))
    if covid_control and not covid_prospective:
        log.info("Collection " + collection['id'] + " has control cases for COVID")
        covidExistingControls.append(collection)
        covidBiobanksExistingControls.add(biobankId)
    if covid_prospective:
        log.info("Collection " + collection['id'] + " is a prospective COVID collection")
        covidProspective.append(collection)
        covidBiobanksProspective.add(biobankId)

    if 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:COVID19' in collection_networks and not covid_diag and not covid_control and not covid_prospective:
        covidOther.append(collection)
        covidBiobanksOther.add(biobankId)

    if covid_diag or covid_control or covid_prospective or 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:COVID19' in collection_networks:
        covidBiobanks.add(biobankId)

pd_covidExistingDiagnosed = pd.DataFrame(covidExistingDiagnosed)
pd_covidExistingControls = pd.DataFrame(covidExistingControls)
pd_covidProspective = pd.DataFrame(covidProspective)
pd_covidOther = pd.DataFrame(covidOther)

def printCollectionStdout(collectionList : List, headerStr : str):
    print(headerStr + " - " + str(len(collectionList)) + " collections")
    for collection in collectionList:
        biobankId = dir.getCollectionBiobankId(collection['id'])
        biobank = dir.getBiobankById(biobankId)
        print("   Collection: " + collection['id'] + " - " + collection['name'] + ". Parent biobank: " +  biobankId + " - " + biobank['name'])

if not args.nostdout:
    printCollectionStdout(covidExistingDiagnosed, "COVID Diagnosed")
    print("\n\n")
    printCollectionStdout(covidExistingControls, "COVID Controls")
    print("\n\n")
    printCollectionStdout(covidProspective, "COVID Prospective")
    print("\n\n")
    print("Totals:")
    print("- total number of COVID-relevant biobanks: %d"%(len(covidBiobanks)))
    print("- total number of COVID-relevant collections with existing samples: %d in %d biobanks"%(len(covidExistingDiagnosed),len(covidBiobanksExistingDiagnosed)))
    print("- total number of COVID-only collections with existing samples: %d in %d biobanks"%(len(covidOnlyExistingDiagnosed),len(covidOnlyBiobanksExistingDiagnosed)))
    print("- total number of COVID-relevant collections with control samples: %d in %d biobanks"%(len(covidExistingControls),len(covidBiobanksExistingControls)))
    print("- total number of COVID-relevant prospective collections: %d in %d biobanks"%(len(covidProspective),len(covidBiobanksProspective)))
    print("- total number of other COVID-relevant collections: %d in %d biobanks"%(len(covidOther),len(covidBiobanksOther)))
    print("Estimated totals:")
    print("- total number of samples advertised explicitly in COVID-only collections: %d"%(covidOnlyCollectionSamplesExplicit))
    print("- total number of samples advertised explicitly in COVID-relevant collections: %d"%(covidCollectionSamplesExplicit))
    print("- total number of donors advertised explicitly in COVID-only collections: %d"%(covidOnlyCollectionDonorsExplicit))
    print("- total number of donors advertised explicitly in COVID-relevant collections: %d"%(covidCollectionDonorsExplicit))
    print("- total number of samples advertised in COVID-only collections including OoM estimates: %d"%(covidOnlyCollectionSamplesIncOoM))
    print("- total number of samples advertised in COVID-relevant collections including OoM estimates: %d"%(covidCollectionSamplesIncOoM))

for df in (pd_covidExistingDiagnosed,pd_covidProspective,pd_covidOther):
    pddfutils.tidyCollectionDf(df)

covidOnlyCollectionIDs = [c['id'] for c in covidOnlyExistingDiagnosed]
pd_covidExistingDiagnosed['COVID_only'] = pd_covidExistingDiagnosed['id'].map(lambda x: True if x in covidOnlyCollectionIDs else False)

if args.outputXLSX is not None:
    log.info("Outputting warnings in Excel file " + args.outputXLSX[0])
    writer = pd.ExcelWriter(args.outputXLSX[0], engine='xlsxwriter')
    pd_covidExistingDiagnosed.to_excel(writer, sheet_name='COVID Diagnosed')
    pd_covidExistingControls.to_excel(writer, sheet_name='COVID Controls')
    pd_covidProspective.to_excel(writer, sheet_name='COVID Prospective')
    pd_covidOther.to_excel(writer, sheet_name='COVID Other')
    writer.close()
