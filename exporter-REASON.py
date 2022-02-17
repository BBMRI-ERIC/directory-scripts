#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:et

import pprint
import re
import argparse
import logging as log
from builtins import str, isinstance, len, set, int
from typing import List

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

# NOTE: Changed
orphacodes = OrphaCodes(''.join(args.orphacodesfile))

collectionsIBDLynchDiagnosed = []
biobanksIBDLynchDiagnosed = set()
IBDLynchSamplesExplicit = 0
IBDLynchSamplesIncOoM = 0
IBDLynchDonorsExplicit = 0
collectionsChronicPancreatitisDuctalCancerDiagnosed = []
biobanksChronicPancreatitisDuctalCancerDiagnosed = set()
chronicPancreatitisDuctalCancerSamplesExplicit = 0
chronicPancreatitisDuctalCancerSamplesIncOoM = 0
chronicPancreatitisDuctalCancerDonorsExplicit = 0
collectionsCholangiocarcinomaDiagnosed = []
biobanksCholangiocarcinomaDiagnosed = set()
cholangiocarcinomaSamplesExplicit = 0
cholangiocarcinomaSamplesIncOoM = 0
cholangiocarcinomaDonorsExplicit = 0
isIBDLynch = None
isChronicPancreatitisDuctalCancer = None
isCholangiocarcinoma = None


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
    obesity = False

    for d in collection['diagnosis_available']:
        if re.search('-', d['id']):
            diag_ranges.append(d['id'])
        else:
            diags.append(d['id'])

    if diag_ranges:
        log.warning("There are diagnosis ranges provided for collection " + collection['id'] + ": " + str(diag_ranges))

    log.debug(str(collection['diagnosis_available']))

    # Search by diagnoses codes
    for d in diags + diag_ranges:
        # ICD10 Codes
        # Search Lynch and IBD
        if re.search(r'^urn:miriam:icd:', d):
            d = re.sub(r'^urn:miriam:icd:', '', d)
            isIBDLynch = ICD10CodesHelper.isIBDLynchCode(d)
            if isIBDLynch is not None and isIBDLynch:
                    log.debug(
                        "Collection %s identified as IBD or Lynch syndrome collection due to ICD-10 code %s" % (collection['id'], d))
        
        # Search Chronic Pancreatitis and Ductal Cancer
            isChronicPancreatitisDuctalCancer = ICD10CodesHelper.isChronicPancreatitisDuctalCancerCode(d)
            if isChronicPancreatitisDuctalCancer is not None and isChronicPancreatitisDuctalCancer:
                    log.debug(
                        "Collection %s identified as pancreatic ductal malignancy or chronic pancreatitis collection due to ICD-10 code %s" % (collection['id'], d))

        # Search Cholangiocarcinoma
            isCholangiocarcinoma = ICD10CodesHelper.isCholangiocarcinomaCode(d)
            if isCholangiocarcinoma is not None and isCholangiocarcinoma:
                    log.debug(
                        "Collection %s identified as cholangiocarcinoma collection due to ICD-10 code %s" % (collection['id'], d))

        # ORPHA codes
        if re.search(r'^ORPHA:', d):
            d = re.sub(r'^ORPHA:', '', d)
            if orphacodes.isValidOrphaCode(d):
                # Search Lynch and IBD
                isIBDLynch = orphacodes.isIBDLynchOrphaCode(d)
                if isIBDLynch:
                    log.debug("Collection %s identified as IBD or Lynch syndrome collection due to ORPHA code %s" % (collection['id'], d))
                isChronicPancreatitisDuctalCancer = orphacodes.isChronicPancreatitisDuctalCancerOrphaCode(d)
                # Search Chronic Pancreatitis and Ductal Cancer
                if isChronicPancreatitisDuctalCancer:
                    log.debug("Collection %s identified as pancreatic ductal malignancy or chronic pancreatitis collection due to ORPHA code %s" % (collection['id'], d))
                isCholangiocarcinoma = orphacodes.isCholangiocarcinomaOrphaCode(d)
                # Search Cholangiocarcinoma
                if isCholangiocarcinoma:
                    log.debug("Collection %s identified as cholangiocarcinoma collection due to ORPHA code %s" % (collection['id'], d))

            else:
                log.warning("Collection %s has invalid ORPHA code %s" % (collection['id'], d))

    # Search by name
    if 'name' in collection:
        # Search Lynch and IBD
        if re.search(r'(inflammatory bowel|IBD|Crohn|Ulcerative colitis|Lynch|HNPCC)', collection['name'], re.IGNORECASE):
                    log.debug("Collection %s identified as IBD or Lynch syndrome collection due to its name %s" % (collection['id'], collection['name']))
                    isIBDLynch = True
        # Search Chronic Pancreatitis and Ductal Cancer
        if re.search(r'(pancreatitis|Pancreatic Duct Adenocarcinoma|IPMN)', collection['name'], re.IGNORECASE):
                    log.debug("Collection %s identified as pancreatic ductal malignancy or chronic pancreatitis collection due to its name %s" % (collection['id'], collection['name']))
                    isChronicPancreatitisDuctalCancer = True
        # Search Cholangiocarcinoma
        if re.search(r'(Cholangiocarcinoma)', collection['name'], re.IGNORECASE):
                    log.debug("Collection %s identified as cholangiocarcinoma collection due to its name %s" % (collection['id'], collection['name']))
                    isCholangiocarcinoma = True

    # Search by description
    if 'description' in collection:
        # Search Lynch and IBD
        if re.search(r'(inflammatory bowel|IBD|Crohn|Ulcerative colitis|Lynch|HNPCC)', collection['description'], re.IGNORECASE):
                    log.debug("Collection %s identified as IBD or Lynch syndrome collection due to its description" % (collection['id']))
                    isIBDLynch = True
        # Search Chronic Pancreatitis and Ductal Cancer
        if re.search(r'(pancreatitis|Pancreatic Duct Adenocarcinoma|IPMN)', collection['description'], re.IGNORECASE):
                    log.debug("Collection %s identified as pancreatic ductal malignancy or chronic pancreatitis collection due to its description" % (collection['id']))
                    isChronicPancreatitisDuctalCancer = True
        # Search Cholangiocarcinoma
        if re.search(r'(Cholangiocarcinoma)', collection['description'], re.IGNORECASE):
                    log.debug("Collection %s identified as cholangiocarcinoma collection due to its description" % (collection['id']))
                    isCholangiocarcinoma = True

    age_unit = None
    if 'age_unit' in collection:
        age_units = collection['age_unit']
        if len(age_units) > 1:
            log.warning("Ambiguous age units provided for %s: %s"%(collection['id'],age_units))
        if len(age_units) < 1:
            log.warning("Age units missing for %s"%(collection['id']))
        else:
            age_unit = age_units[0]['id']

    age_min = 50
    if age_unit == "MONTH":
        age_min = age_min*12
    elif age_unit == "WEEK":
        age_min = age_min*52.1775
    elif age_unit == "DAY":
        age_min = age_min*365.25

    age_max = 74
    if age_unit == "MONTH":
        age_max = age_max*12
    elif age_unit == "WEEK":
        age_max = age_max*52.1775
    elif age_unit == "DAY":
        age_max = age_max*365.25

    wantedAgeRange = None

    if 'age_low' in collection and 'age_high' in collection and collection['age_low'] > collection['age_high']:
        log.warning("Age range mismatch detected for collection: %s (%s), age range: %d-%d"%(collection['id'], collection['name'], collection.get('age_low'), collection.get('age_high')))
    else:
        if (('age_low' in collection and collection['age_low'] <= age_max ) and ('age_high' in collection and collection['age_high'] >= age_min)):
            wantedAgeRange = True

    if isIBDLynch and wantedAgeRange:
        log.info(f"IBD or Lynch syndrome collection detected: {collection['id']}, age range: {collection.get('age_low')}-{collection.get('age_high')}, diags: {diags + diag_ranges}")
        collectionsIBDLynchDiagnosed.append(collection)
        biobanksIBDLynchDiagnosed.add(biobankId)
        if 'size' in collection and isinstance(collection['size'], int):
            IBDLynchSamplesExplicit += collection['size']
            IBDLynchSamplesIncOoM += collection['size']
        else:
            log.info('Adding %d for OoM %d on behalf of %s'%(10**OoM, OoM, collection['id']))
            IBDLynchSamplesIncOoM += 10 ** OoM
        if 'number_of_donors' in collection and isinstance(collection['number_of_donors'], int):
            IBDLynchDonorsExplicit += collection['number_of_donors']
    
    if isChronicPancreatitisDuctalCancer and wantedAgeRange:
        log.info(f"Pancreatic ductal malignancy or chronic pancreatitis collection detected: {collection['id']}, age range: {collection.get('age_low')}-{collection.get('age_high')}, diags: {diags + diag_ranges}")
        collectionsChronicPancreatitisDuctalCancerDiagnosed.append(collection)
        biobanksChronicPancreatitisDuctalCancerDiagnosed.add(biobankId)
        if 'size' in collection and isinstance(collection['size'], int):
            chronicPancreatitisDuctalCancerSamplesExplicit += collection['size']
            chronicPancreatitisDuctalCancerSamplesIncOoM += collection['size']
        else:
            log.info('Adding %d for OoM %d on behalf of %s'%(10**OoM, OoM, collection['id']))
            chronicPancreatitisDuctalCancerSamplesIncOoM += 10 ** OoM
        if 'number_of_donors' in collection and isinstance(collection['number_of_donors'], int):
            chronicPancreatitisDuctalCancerDonorsExplicit += collection['number_of_donors']
    
    if isCholangiocarcinoma and wantedAgeRange:
        log.info(f"Cholangiocarcinoma collection detected: {collection['id']}, age range: {collection.get('age_low')}-{collection.get('age_high')}, diags: {diags + diag_ranges}")
        collectionsCholangiocarcinomaDiagnosed.append(collection)
        biobanksCholangiocarcinomaDiagnosed.add(biobankId)
        if 'size' in collection and isinstance(collection['size'], int):
            cholangiocarcinomaSamplesExplicit += collection['size']
            cholangiocarcinomaSamplesIncOoM += collection['size']
        else:
            log.info('Adding %d for OoM %d on behalf of %s'%(10**OoM, OoM, collection['id']))
            cholangiocarcinomaSamplesIncOoM += 10 ** OoM
        if 'number_of_donors' in collection and isinstance(collection['number_of_donors'], int):
            cholangiocarcinomaDonorsExplicit += collection['number_of_donors']

pd_collectionsIBDLynchDiagnosed = pd.DataFrame(collectionsIBDLynchDiagnosed)
pd_collectionsChronicPancreatitisDuctalCancerDiagnosed = pd.DataFrame(collectionsChronicPancreatitisDuctalCancerDiagnosed)
pd_collectionsCholangiocarcinomaDiagnosed = pd.DataFrame(collectionsCholangiocarcinomaDiagnosed)


def printCollectionStdout(collectionList: List, headerStr: str):
    print(headerStr + " - " + str(len(collectionList)) + " collections")
    for collection in collectionList:
        biobankId = dir.getCollectionBiobankId(collection['id'])
        biobank = dir.getBiobankById(biobankId)
        log.info("   Collection: " + collection['id'] + " - " + collection['name'] + ". Parent biobank: " + biobankId + " - " + biobank['name'])


if not args.nostdout:
    print("Biobanks/collections totals:")
    print("- total of Lynch syndrome or IBD collections with existing samples: %d in %d biobanks" % (
    len(collectionsIBDLynchDiagnosed), len(biobanksIBDLynchDiagnosed)))
    print("- total of Lynch syndrome or IBD samples: %d explicit, %d with OoM; donors: %d explicit" % (
    IBDLynchSamplesExplicit, IBDLynchSamplesIncOoM,  IBDLynchDonorsExplicit))
    print("- total of pancreatic ductal malignancy or chronic pancreatitis collections with existing samples: %d in %d biobanks" % (
    len(collectionsChronicPancreatitisDuctalCancerDiagnosed), len(biobanksChronicPancreatitisDuctalCancerDiagnosed)))
    print("- total of pancreatic ductal malignancy or chronic pancreatitis samples: %d explicit, %d with OoM; donors: %d explicit" % (
    chronicPancreatitisDuctalCancerSamplesExplicit, chronicPancreatitisDuctalCancerSamplesIncOoM,  chronicPancreatitisDuctalCancerDonorsExplicit))
    print("- total of cholangiocarcinoma collections with existing samples: %d in %d biobanks" % (
    len(collectionsCholangiocarcinomaDiagnosed), len(biobanksCholangiocarcinomaDiagnosed)))
    print("- total of cholangiocarcinoma samples: %d explicit, %d with OoM; donors: %d explicit" % (
    cholangiocarcinomaSamplesExplicit, cholangiocarcinomaSamplesIncOoM, cholangiocarcinomaDonorsExplicit))

for df in (pd_collectionsIBDLynchDiagnosed, pd_collectionsChronicPancreatitisDuctalCancerDiagnosed, pd_collectionsCholangiocarcinomaDiagnosed):
    pddfutils.tidyCollectionDf(df)

if args.outputXLSX is not None:
    log.info("Outputting warnings in Excel file " + args.outputXLSX[0])
    writer = pd.ExcelWriter(args.outputXLSX[0], engine='xlsxwriter')
    pd_collectionsIBDLynchDiagnosed.to_excel(writer, sheet_name='Lynch syndrome or IBD')
    pd_collectionsChronicPancreatitisDuctalCancerDiagnosed.to_excel(writer, sheet_name='Pan ductal malig or chronic pan')
    pd_collectionsCholangiocarcinomaDiagnosed.to_excel(writer, sheet_name='Cholangiocarcinoma')
    writer.save()
