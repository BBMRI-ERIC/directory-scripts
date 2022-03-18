#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:et

import sys
sys.stdout.reconfigure(encoding='utf-8')


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

collectionsEndometriosisDiagnosed = []
biobanksEndometriosisDiagnosed = set()
EndometriosisSamplesExplicit = 0
EndometriosisSamplesIncOoM = 0
EndometriosisDonorsExplicit = 0

collectionsMyomatosisDiagnosed = []
biobanksMyomatosisDiagnosed = set()
MyomatosisSamplesExplicit = 0
MyomatosisSamplesIncOoM = 0
MyomatosisDonorsExplicit = 0



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
    endometriosis = None
    myomatosis = None
    collection['control_samples'] = False

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
        # Search Endometriosis
        if re.search(r'^urn:miriam:icd:', d):
            d = re.sub(r'^urn:miriam:icd:', '', d)
            isEndometriosis = ICD10CodesHelper.isEndometriosisCode(d)
            if isEndometriosis:
                    log.debug(
                        "Collection %s identified as Endometriosis collection due to ICD-10 code %s" % (collection['id'], d))
                    endometriosis = True
                    
        
        # Search Myomatosis 
            isMyomatosis = ICD10CodesHelper.isMyomatosisCode(d)
            if isMyomatosis:
                    log.debug(
                        "Collection %s identified as Myomatosis collection due to ICD-10 code %s" % (collection['id'], d))
                    myomatosis = True
                    

        # ORPHA codes
        if re.search(r'^ORPHA:', d):
            d = re.sub(r'^ORPHA:', '', d)
            if orphacodes.isValidOrphaCode(d):

                # Search Endometriosis
                isEndometriosis = orphacodes.isEndometriosisOrphaCode(d)
                if isEndometriosis:
                    log.debug("Collection %s identified as Endometriosis collection due to ORPHA code %s" % (collection['id'], d))
                    endometriosis = True
                    

                # Search Myomatosis
                isMyomatosis = orphacodes.isMyomatosisOrphaCode(d)
                if isMyomatosis:
                    log.debug("Collection %s identified as Myomatosis collection due to ORPHA code %s" % (collection['id'], d))
                    myomatosis = True

            else:
                log.warning("Collection %s has invalid ORPHA code %s" % (collection['id'], d))

    # Search by name
    if 'name' in collection:
        # Search Endometriosis
        if re.search(r'(Endometriosis)', collection['name'], re.IGNORECASE): 
                    log.debug("Collection %s identified as Endometriosis collection due to its name %s" % (collection['id'], collection['name']))
                    # Search for control
                    if re.search(r'(Control)', collection['name'], re.IGNORECASE): 
                        collection['control_samples'] = True
                        log.debug("Collection %s identified as control collection due to its name %s" % (collection['id'], collection['name']))
                    endometriosis = True
        # Search Myomatosis
        if re.search(r'(Myomatosis|Leiomyoma of uterus|Myoma of uterus)', collection['name'], re.IGNORECASE):
                    log.debug("Collection %s identified as Myomatosis collection due to its name %s" % (collection['id'], collection['name']))
                    # Search for control
                    if re.search(r'(Control)', collection['name'], re.IGNORECASE): 
                        collection['control_samples'] = True
                        log.debug("Collection %s identified as control collection due to its name %s" % (collection['id'], collection['name']))
                    myomatosis = True


    # Search by description
    if 'description' in collection:
        # Search Endometriosis
        if re.search(r'(Endometriosis)', collection['description'], re.IGNORECASE):
                    log.debug("Collection %s identified as Endometriosis collection due to its description" % (collection['id']))
                    # Search for control:
                    if re.search(r'(Control)', collection['description'], re.IGNORECASE):
                        collection['control_samples'] = True
                        log.debug("Collection %s identified as control collection due to its description" % (collection['id']))
                    endometriosis = True
        # Search Chronic Pancreatitis and Ductal Cancer
        if re.search(r'(Myomatosis|Leiomyoma of uterus|Myoma of uterus)', collection['description'], re.IGNORECASE):
                    # Search for control 
                    log.debug("Collection %s identified as Myomatosis collection due to its description" % (collection['id']))
                    # Search for control:
                    if re.search(r'(Control)', collection['description'], re.IGNORECASE):
                        collection['control_samples'] = True
                        log.debug("Collection %s identified as control collection due to its description" % (collection['id']))
                    myomatosis = True

    if endometriosis:
        # Search for control
        if not collection['control_samples']:
            for coltype in collection['type']:
                        if 'POPULATION_BASED' in coltype['id'] or 'CASE_CONTROL' in coltype['id']:
                            collection['control_samples'] = True
                            log.debug("Collection %s identified as control collection due to its type" % (coltype['id']))

        log.info(f"Endometriosis collection detected: {collection['id']}, age range: {collection.get('age_low')}-{collection.get('age_high')}, diags: {diags + diag_ranges}")
        collectionsEndometriosisDiagnosed.append(collection)
        biobanksEndometriosisDiagnosed.add(biobankId)
        if 'size' in collection and isinstance(collection['size'], int):
            EndometriosisSamplesExplicit += collection['size']
            EndometriosisSamplesIncOoM += collection['size']
        else:
            log.info('Adding %d for OoM %d on behalf of %s'%(10**OoM, OoM, collection['id']))
            EndometriosisSamplesIncOoM += 10 ** OoM
        if 'number_of_donors' in collection and isinstance(collection['number_of_donors'], int):
            EndometriosisDonorsExplicit += collection['number_of_donors']
    
    if myomatosis:
        # Search for control
        if not collection['control_samples']:
            for coltype in collection['type']:
                        if 'POPULATION_BASED' in coltype['id'] or 'CASE_CONTROL' in coltype['id']:
                            collection['control_samples'] = True
                            log.debug("Collection %s identified as control collection due to its type" % (coltype['id']))

        log.info(f"Myomatosis collection detected: {collection['id']}, age range: {collection.get('age_low')}-{collection.get('age_high')}, diags: {diags + diag_ranges}")
        collectionsMyomatosisDiagnosed.append(collection)
        biobanksMyomatosisDiagnosed.add(biobankId)
        if 'size' in collection and isinstance(collection['size'], int):
            MyomatosisSamplesExplicit += collection['size']
            MyomatosisSamplesIncOoM += collection['size']
        else:
            log.info('Adding %d for OoM %d on behalf of %s'%(10**OoM, OoM, collection['id']))
            MyomatosisSamplesIncOoM += 10 ** OoM
        if 'number_of_donors' in collection and isinstance(collection['number_of_donors'], int):
            MyomatosisDonorsExplicit += collection['number_of_donors']

pd_collectionsEndometriosisDiagnosed = pd.DataFrame(collectionsEndometriosisDiagnosed)
pd_collectionsMyomatosisDiagnosed = pd.DataFrame(collectionsMyomatosisDiagnosed)


def printCollectionStdout(collectionList: List, headerStr: str):
    print(headerStr + " - " + str(len(collectionList)) + " collections")
    for collection in collectionList:
        biobankId = dir.getCollectionBiobankId(collection['id'])
        biobank = dir.getBiobankById(biobankId)
        log.info("   Collection: " + collection['id'] + " - " + collection['name'] + ". Parent biobank: " + biobankId + " - " + biobank['name'])


if not args.nostdout:
    print("Biobanks/collections totals:")
    print("- total of Endometriosis collections with existing samples: %d in %d biobanks" % (
    len(collectionsEndometriosisDiagnosed), len(biobanksEndometriosisDiagnosed)))
    print("- total of Endometriosis samples: %d explicit, %d with OoM; donors: %d explicit" % (
    EndometriosisSamplesExplicit, EndometriosisSamplesIncOoM,  EndometriosisDonorsExplicit))
    print("- total of Myomatosis collections with existing samples: %d in %d biobanks" % (
    len(collectionsMyomatosisDiagnosed), len(biobanksMyomatosisDiagnosed)))
    print("- total of Myomatosis samples: %d explicit, %d with OoM; donors: %d explicit" % (
    MyomatosisSamplesExplicit, MyomatosisSamplesIncOoM,  MyomatosisDonorsExplicit))


for df in (pd_collectionsEndometriosisDiagnosed, pd_collectionsMyomatosisDiagnosed):
    pddfutils.tidyCollectionDf(df)

if args.outputXLSX is not None:
    log.info("Outputting warnings in Excel file " + args.outputXLSX[0])
    writer = pd.ExcelWriter(args.outputXLSX[0], engine='xlsxwriter')
    pd_collectionsEndometriosisDiagnosed.to_excel(writer, sheet_name='Endometriosis')
    pd_collectionsMyomatosisDiagnosed.to_excel(writer, sheet_name='Myomatosis')
    writer.save()
