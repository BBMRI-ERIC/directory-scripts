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
                    help='output of results into XLSX with filename provided as parameter')
parser.add_argument('-O', '--orphacodes-mapfile', dest='orphacodesfile', nargs=1,
                    help='file name of Orpha code mappings from http://www.orphadata.org/cgi-bin/ORPHAnomenclature.html')
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

orphacodes = OrphaCodes(args.orphacodesfile)

cancerExistingDiagnosed = []
cancerOnlyExistingDiagnosed = []
cancerExistingControls = []
cancerProspective = []
cancerBiobanksExistingDiagnosed = set()
cancerOnlyBiobanksExistingDiagnosed = set()
cancerBiobanksExistingControls = set()
cancerBiobanksProspective = set()
cancerBiobanks = set()
cancerCollectionSamplesExplicit = 0
cancerCollectionDonorsExplicit = 0
cancerCollectionSamplesIncOoM = 0
cancerOnlyCollectionSamplesExplicit = 0
cancerOnlyCollectionDonorsExplicit = 0
cancerOnlyCollectionSamplesIncOoM = 0
cancerInstitutions = set()
cancerCountries = set()

pediatricCancerExistingDiagnosed = []
pediatricCancerOnlyExistingDiagnosed = []
pediatricCancerBiobanksExistingDiagnosed = set()
pediatricCancerOnlyBiobanksExistingDiagnosed = set()
pediatricCancerBiobanks = set()
pediatricCancerCollectionSamplesExplicit = 0
pediatricCancerCollectionDonorsExplicit = 0
pediatricCancerCollectionSamplesIncOoM = 0
pediatricCancerOnlyCollectionSamplesExplicit = 0
pediatricCancerOnlyCollectionDonorsExplicit = 0
pediatricCancerOnlyCollectionSamplesIncOoM = 0
pediatricOnlyCancerExistingDiagnosed = []
pediatricOnlyCancerOnlyExistingDiagnosed = []
pediatricOnlyCancerBiobanksExistingDiagnosed = set()
pediatricOnlyCancerOnlyBiobanksExistingDiagnosed = set()
pediatricOnlyCancerBiobanks = set()
pediatricOnlyCancerCollectionSamplesExplicit = 0
pediatricOnlyCancerCollectionDonorsExplicit = 0
pediatricOnlyCancerCollectionSamplesIncOoM = 0
pediatricOnlyCancerOnlyCollectionSamplesExplicit = 0
pediatricOnlyCancerOnlyCollectionDonorsExplicit = 0
pediatricOnlyCancerOnlyCollectionSamplesIncOoM = 0
pediatricCancerInstitutions = set()
pediatricCancerCountries = set()

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
    cancer_diag = False
    cancer_control = False
    cancer_prospective = False
    non_cancer = False

    if 'diagnosis_available' in collection:
        for d in collection['diagnosis_available']:
            if re.search('-', d['name']):
                diag_ranges.append(d['name'])
            else:
                diags.append(d['name'])

        log.debug(str(collection['diagnosis_available']))

    if diag_ranges:
        log.warning("There are diagnosis ranges provided for collection " + collection['id'] + ": " + str(diag_ranges))


    for d in diags + diag_ranges:
        if re.search(r'^urn:miriam:icd:', d):
            d = re.sub(r'^urn:miriam:icd:', '', d)
            isCancer = ICD10CodesHelper.isCancerCode(d)
            if isCancer is not None:
                if isCancer:
                    log.debug(
                        "Collection %s identified as cancer collection due to ICD-10 code %s" % (collection['id'], d))
                    cancer_diag = True
                else:
                    log.debug("Collection %s identified as non-cancer collection due to ICD-10 code %s" % (
                    collection['id'], d))
                    non_cancer = True
            else:
                isCancerChapter = ICD10CodesHelper.isCancerChapter(d)
                if isCancerChapter is not None:
                    if isCancerChapter:
                        log.debug("Collection %s identified as cancer collection due to ICD-10 chapter %s" % (
                        collection['id'], d))
                        cancer_diag = True
                    else:
                        log.debug("Collection %s identified as non-cancer collection due to ICD-10 chapter %s" % (
                        collection['id'], d))
                        non_cancer = True
                else:
                    log.warning("Cannot match ICD-10 diagnosis %s" % (d))

        if re.search(r'^ORPHA:', d):
            d = re.sub(r'^ORPHA:', '', d)
            if orphacodes.isValidOrphaCode(d):
                isCancer = orphacodes.isCancerOrphaCode(d)
                if isCancer:
                    log.debug("Collection %s identified as cancer collection due to ORPHA code %s" % (collection['id'], d))
                    cancer_diag = True
                else:
                    log.debug("Collection %s identified as non-cancer collection due to ORPHA code %s" % (collection['id'], d))
                    non_cancer = True
            else:
                log.warn("Collection %s has invalid ORPHA code %s" % (collection['id'], d))

    if 'NON_HUMAN' in types:
        log.info("Non-human collection %s skipped" % (collection['id']))
        continue

    pediatric = False
    pediatricOnly = False

    age_unit = None
    if 'age_unit' in collection:
        age_units = collection['age_unit']
        if len(age_units) > 1:
            log.warn("Ambiguous age units provided for %s: %s"%(collection['id'],age_units))
        if len(age_units) < 1:
            log.warn("Age units missing for %s"%(collection['id']))
        else:
            age_unit = age_units[0]

    age_max = 18
    if age_unit == "MONTH":
        age_max = age_max*12
    elif age_unit == "WEEK":
        age_max = age_max*52.1775
    elif age_unit == "DAY":
        age_max = age_max*365.25

    if 'age_high' in collection and collection['age_high'] == 0:
        if 'age_low' in collection and collection['age_low'] < 0:
            pediatric = True
            pediatricOnly = True
            log.debug("Prenatal collection detected: %s (%s), age range: %d-%d, diags: %s"%(collection['id'], collection['name'], collection.get('age_low'), collection.get('age_high'), diags + diag_ranges))
        else:
            log.warn("Age range mismatch detected for collection: %s (%s), age range: %d-%d"%(collection['id'], collection['name'], collection.get('age_low'), collection.get('age_high')))
    elif 'age_high' in collection and collection['age_high'] < 0:
        log.warn("Age range mismatch detected for collection: %s (%s), age range: %d-%d"%(collection['id'], collection['name'], collection.get('age_low'), collection.get('age_high')))
    else:
        if 'age_low' in collection and 'age_high' in collection and collection['age_low'] > collection['age_high']:
            log.warn("Age range mismatch detected for collection: %s (%s), age range: %d-%d"%(collection['id'], collection['name'], collection.get('age_low'), collection.get('age_high')))
        else:
            if (('age_low' in collection and collection['age_low'] < age_max ) or ('age_high' in collection and collection['age_high'] < age_max)):
                pediatric = True
            if 'age_high' in collection and collection['age_high'] < age_max:
                pediatricOnly = True
                log.debug("Pediatric-only collection detected: %s, age range: %d-%d, diags: %s"%(collection['id'], (collection.get('age_low') if 'age_low' in collection else 0), collection.get('age_high'), diags + diag_ranges))

    if cancer_diag:
        log.info(f"Cancer collection detected: {collection['id']}")
        cancerExistingDiagnosed.append(collection)
        cancerBiobanksExistingDiagnosed.add(biobankId)
        cancerBiobanks.add(biobankId)
        if pediatric:
            log.info(f"Pediatric cancer collection detected: {collection['id']}, age range: {collection.get('age_low')}-{collection.get('age_high')}, diags: {diags + diag_ranges}")
            pediatricCancerExistingDiagnosed.append(collection)
            pediatricCancerBiobanksExistingDiagnosed.add(biobankId)
            pediatricCancerBiobanks.add(biobankId)
        if pediatricOnly:
            log.info(f"Pediatric-only cancer collection detected: {collection['id']}, age range: {collection.get('age_low')}-{collection.get('age_high')}, diags: {diags + diag_ranges}")
            pediatricOnlyCancerExistingDiagnosed.append(collection)
            pediatricOnlyCancerBiobanksExistingDiagnosed.add(biobankId)
            pediatricOnlyCancerBiobanks.add(biobankId)
        if not non_cancer:
            log.info(f"Cancer-only collection detected:  {collection['id']}")
            cancerOnlyExistingDiagnosed.append(collection)
            cancerOnlyBiobanksExistingDiagnosed.add(biobankId)
            if pediatric:
                pediatricCancerOnlyExistingDiagnosed.append(collection)
                pediatricCancerOnlyBiobanksExistingDiagnosed.add(biobankId)
            if pediatricOnly:
                log.info(f"Pediatric-only cancer-only collection detected:  {collection['id']}")
                pediatricOnlyCancerOnlyExistingDiagnosed.append(collection)
                pediatricOnlyCancerOnlyBiobanksExistingDiagnosed.add(biobankId)
        else:
            log.info(f"Mixed cancer/non-cancer collection detected: {collection['id']}")
        if 'size' in collection and isinstance(collection['size'], int):
            cancerCollectionSamplesExplicit += collection['size']
            cancerCollectionSamplesIncOoM += collection['size']
            if pediatric:
                pediatricCancerCollectionSamplesExplicit += collection['size']
                pediatricCancerCollectionSamplesIncOoM += collection['size']
            if pediatricOnly:
                pediatricOnlyCancerCollectionSamplesExplicit += collection['size']
                pediatricOnlyCancerCollectionSamplesIncOoM += collection['size']
            if not non_cancer:
                cancerOnlyCollectionSamplesExplicit += collection['size']
                cancerOnlyCollectionSamplesIncOoM += collection['size']
                if pediatric:
                    pediatricCancerOnlyCollectionSamplesExplicit += collection['size']
                    pediatricCancerOnlyCollectionSamplesIncOoM += collection['size']
                if pediatricOnly:
                    pediatricOnlyCancerOnlyCollectionSamplesExplicit += collection['size']
                    pediatricOnlyCancerOnlyCollectionSamplesIncOoM += collection['size']
        else:
            cancerCollectionSamplesIncOoM += 10 ** OoM
            if pediatric:
                pediatricCancerCollectionSamplesIncOoM += 10 ** OoM
            if pediatricOnly:
                pediatricOnlyCancerCollectionSamplesIncOoM += 10 ** OoM
            if not non_cancer:
                cancerOnlyCollectionSamplesIncOoM += 10 ** OoM
                if pediatric:
                    pediatricCancerOnlyCollectionSamplesIncOoM += 10 ** OoM
                if pediatricOnly:
                    pediatricOnlyCancerOnlyCollectionSamplesIncOoM += 10 ** OoM
        if 'number_of_donors' in collection and isinstance(collection['number_of_donors'], int):
            cancerCollectionDonorsExplicit += collection['number_of_donors']
            if pediatric:
                pediatricCancerCollectionDonorsExplicit += collection['number_of_donors']
            if pediatricOnly:
                pediatricOnlyCancerCollectionDonorsExplicit += collection['number_of_donors']
            if not non_cancer:
                cancerOnlyCollectionDonorsExplicit += collection['number_of_donors']
                if pediatric:
                    pediatricCancerOnlyCollectionDonorsExplicit += collection['number_of_donors']
                if pediatricOnly:
                    pediatricOnlyCancerOnlyCollectionDonorsExplicit += collection['number_of_donors']

def countCountriesInstitutions(biobanks, institutions : set, countries : set):
    for biobankId in biobanks:
        biobank = dir.getBiobankById(biobankId)
        biobankJuridicalPerson = biobank['juridical_person'].strip()
        if len(biobankJuridicalPerson) > 0:
            institutions.add(biobankJuridicalPerson)
        else:
            log.warning(f'Identified empty juridical person for biobank {biobankId}')
        countries.add(biobank['country'])

countCountriesInstitutions(cancerBiobanks, cancerInstitutions, cancerCountries)
countCountriesInstitutions(pediatricCancerBiobanks, pediatricCancerInstitutions, pediatricCancerCountries)

pd_cancerExistingDiagnosed = pd.DataFrame(cancerExistingDiagnosed)
pd_cancerOnlyExistingDiagnosed = pd.DataFrame(cancerOnlyExistingDiagnosed)
pd_pediatricCancerExistingDiagnosed = pd.DataFrame(pediatricCancerExistingDiagnosed)
pd_pediatricOnlyCancerExistingDiagnosed = pd.DataFrame(pediatricOnlyCancerExistingDiagnosed)
pd_pediatricOnlyCancerOnlyExistingDiagnosed = pd.DataFrame(pediatricOnlyCancerOnlyExistingDiagnosed)

pediatricOnlyCancerOnlyBiobanks = []
for biobankId in pediatricOnlyCancerOnlyBiobanksExistingDiagnosed:
    pediatricOnlyCancerOnlyBiobanks.append(dir.getBiobankById(biobankId))
pd_pediatricOnlyCancerOnlyBiobanks = pd.DataFrame(pediatricOnlyCancerOnlyBiobanks)


def printCollectionStdout(collectionList: List, headerStr: str):
    print(headerStr + " - " + str(len(collectionList)) + " collections")
    for collection in collectionList:
        biobankId = dir.getCollectionBiobankId(collection['id'])
        biobank = dir.getBiobankById(biobankId)
        log.info("   Collection: " + collection['id'] + " - " + collection['name'] + ". Parent biobank: " + biobankId + " - " + biobank['name'])


if not args.nostdout:
    printCollectionStdout(cancerExistingDiagnosed, "Cancer Diagnosed")
    print("\n\n")
    printCollectionStdout(cancerExistingControls, "Cancer Controls")
    print("\n\n")
    printCollectionStdout(cancerProspective, "Cancer Prospective")
    print("\n\n")
    print("Totals:")
    print("- total of cancer-relevant biobanks: %d biobanks in %d institutions from %d countries" % (len(cancerBiobanks), len(cancerInstitutions), len(cancerCountries)))
    print("- total of cancer-relevant collections with existing samples: %d collections in %d biobanks" % (
    len(cancerExistingDiagnosed), len(cancerBiobanksExistingDiagnosed)))
    print("- total of cancer-only collections with existing samples: %d collections in %d biobanks" % (
    len(cancerOnlyExistingDiagnosed), len(cancerOnlyBiobanksExistingDiagnosed)))
    print("- total of cancer-relevant collections with control samples: %d collections in %d biobanks" % (
    len(cancerExistingControls), len(cancerBiobanksExistingControls)))
    print("- total of cancer-relevant prospective collections: %d collections in %d biobanks" % (
    len(cancerProspective), len(cancerBiobanksProspective)))
    print("Estimated totals:")
    print("- total of samples/donors advertised explicitly in cancer-only collections: %d samples / %d donors" % (
        cancerOnlyCollectionSamplesExplicit, cancerOnlyCollectionDonorsExplicit))
    print("- total of samples advertised in cancer-only collections including OoM estimates: %d samples" % (
        cancerOnlyCollectionSamplesIncOoM))
    print("- total of samples/donors advertised explicitly in cancer-relevant collections: %d samples / %d donors" % (
        cancerCollectionSamplesExplicit, cancerCollectionDonorsExplicit))
    print("- total of samples advertised in cancer-relevant collections including OoM estimates: %d samples" % (
        cancerCollectionSamplesIncOoM))
    print("\n\n")
    #printCollectionStdout(pediatricCancerExistingDiagnosed, "Pediatric Cancer Diagnosed")
    #printCollectionStdout(pediatricOnlyCancerExistingDiagnosed, "Pediatric Only Cancer Diagnosed")
    #print("\n\n")
    print("Pediatric biobanks/collections totals:")
    print("- total of pediatric pediatricCancer-relevant biobanks: %d biobanks in %d institutions from %d countries" % (len(pediatricCancerBiobanks), len(pediatricCancerInstitutions), len(pediatricCancerCountries)))
    print("- total of pediatric cancer-relevant collections with existing samples: %d collections in %d biobanks" % (
    len(pediatricCancerExistingDiagnosed), len(pediatricCancerBiobanksExistingDiagnosed)))
    print("- total of pediatric cancer-only collections with existing samples: %d collections in %d biobanks" % (
    len(pediatricCancerOnlyExistingDiagnosed), len(pediatricCancerOnlyBiobanksExistingDiagnosed)))
    print("- total of pediatric-only cancer-relevant biobanks: %d biobanks" % (len(pediatricOnlyCancerBiobanks)))
    print("- total of pediatric-only cancer-relevant collections with existing samples: %d collections in %d biobanks" % (
    len(pediatricOnlyCancerExistingDiagnosed), len(pediatricOnlyCancerBiobanksExistingDiagnosed)))
    print("- total of pediatric-only cancer-only collections with existing samples: %d collections in %d biobanks" % (
    len(pediatricOnlyCancerOnlyExistingDiagnosed), len(pediatricOnlyCancerOnlyBiobanksExistingDiagnosed)))
    print("\n\n")
    print("Estimated sample totals:")
    print("- total of samples/donors advertised explicitly in pediatric-only cancer-only collections: %d samples / %d donors" % (
        pediatricOnlyCancerOnlyCollectionSamplesExplicit, pediatricOnlyCancerOnlyCollectionDonorsExplicit))
    print("- total of samples advertised in pediatric-only cancer-only collections including OoM estimates: %d samples" % (
        pediatricOnlyCancerOnlyCollectionSamplesIncOoM))
    print("- total of samples/donors advertised explicitly in pediatric-only cancer-relevant collections: %d samples / %d donors" % (
        pediatricOnlyCancerCollectionSamplesExplicit, pediatricOnlyCancerCollectionDonorsExplicit))
    print("- total of samples advertised in pediatric-only cancer-relevant collections including OoM estimates: %d samples" % (
        pediatricOnlyCancerCollectionSamplesIncOoM))
    print("\n")
    print("- total of samples/donors advertised explicitly in pediatric cancer-only collections: %d samples / %d donors" % (
        pediatricCancerOnlyCollectionSamplesExplicit, pediatricCancerOnlyCollectionDonorsExplicit))
    print("- total of samples advertised in pediatric cancer-only collections including OoM estimates: %d samples" % (
        pediatricCancerOnlyCollectionSamplesIncOoM))
    print("- total of samples/donors advertised explicitly in pediatric cancer-relevant collections: %d samples / %d donors" % (
        pediatricCancerCollectionSamplesExplicit, pediatricCancerCollectionDonorsExplicit))
    print("- total of samples advertised in pediatric cancer-relevant collections including OoM estimates: %d samples" % (
        pediatricCancerCollectionSamplesIncOoM))

for df in (pd_cancerExistingDiagnosed, pd_cancerOnlyExistingDiagnosed, pd_pediatricCancerExistingDiagnosed, pd_pediatricOnlyCancerExistingDiagnosed, pd_pediatricOnlyCancerOnlyExistingDiagnosed): 
    pddfutils.tidyCollectionDf(df)

for df in (pd_pediatricOnlyCancerOnlyBiobanks,):
    pddfutils.tidyBiobankDf(df)

if args.outputXLSX is not None:
    log.info("Outputting warnings in Excel file " + args.outputXLSX[0])
    writer = pd.ExcelWriter(args.outputXLSX[0], engine='xlsxwriter')
    pd_cancerExistingDiagnosed.to_excel(writer, sheet_name='Cancer')
    pd_cancerOnlyExistingDiagnosed.to_excel(writer, sheet_name='Cancer-only')
    pd_pediatricCancerExistingDiagnosed.to_excel(writer, sheet_name='Pediatric cancer')
    pd_pediatricOnlyCancerExistingDiagnosed.to_excel(writer, sheet_name='Pediatric cancer-only')
    pd_pediatricOnlyCancerOnlyExistingDiagnosed.to_excel(writer, sheet_name='Ped-only cancer-only')
    pd_pediatricOnlyCancerOnlyBiobanks.to_excel(writer, sheet_name='Ped-only cancer-only BBs')
    writer.close()
