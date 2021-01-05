#!/usr/bin/python3
# vim:ts=8:sw=8:tw=0:noet

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
    cancer_diag = False
    cancer_control = False
    cancer_prospective = False
    non_cancer = False

    for d in collection['diagnosis_available']:
        if re.search('-', d['id']):
            diag_ranges.append(d['id'])
        else:
            diags.append(d['id'])

    if diag_ranges:
        log.warning("There are diagnosis ranges provided for collection " + collection['id'] + ": " + str(diag_ranges))

    log.debug(str(collection['diagnosis_available']))

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

    #            m = re.search(r'^(?P<block>[A-Z])(?P<code>\d{1,2})(\.(?P<subcode>\d+))?$', d)
    #			if m:
    #				log.debug("Block: %s, code: %s, subcode %s"%(m.group('block'), m.group('code'), m.group('subcode')))
    #				if m.group('block') == 'C' or (m.group('block') == 'D' and int(m.group('code')) <= 48):
    #					log.debug("Collection %s identified as cancer collection due to ICD-10 code %s"%(collection['id'],d))
    #					cancer_diag = True
    #				else:
    #					log.debug("Collection %s identified as non-cancer collection due to ICD-10 code %s"%(collection['id'],d))
    #					non_cancer = True
    #			elif d in ['C7A', 'C7B', 'D3A']:
    #				log.debug("Collection %s identified as cancer collection due to ICD-10 less common code %s"%(collection['id'],d))
    #				cancer_diag = True
    #			elif d in cancer_chapters_roman:
    #				if d == "II":
    #					log.debug("Collection %s identified as cancer collection due to ICD-10 chapter %s"%(collection['id'],d))
    #					cancer_diag = True
    #				else:
    #					log.debug("Collection %s identified as non-cancer collection due to ICD-10 chapter %s"%(collection['id'],d))
    #					non_cancer = True
    #			else:
    #				log.warn("Cannot match ICD-10 diagnosis %s"%(d))

    # Add ORPHAcode parser based on en_product1.xml mappings

    #		code = icd10.find(d)
    #		log.debug("Code %s found and converted to %s"%(d,code))
    #		if code is None:
    #			if d in cancer_chapters_roman:
    #				if d == "II":
    #					log.debug("Cancer diagnosis term found: %s"%(d))
    #					cancer_diag = True
    #			else:
    #				log.warn("Detected unknown code: %s"%(d))
    #			continue
    #		try:
    #			if code.chapter == "II":
    #				log.debug("Cancer diagnosis term found: %s"%(d))
    #				cancer_diag = True
    #			elif d in ['C7A', 'C7B', 'D3A']:
    #				log.debug("Less common cancer diagnosis term found: %s"%(d))
    #				cancer_diag = True
    #			else:
    #				log.debug("Non-cancer diagnosis term found: %s"%(d))
    #				non_cancer = True
    #		except:
    #			log.warn("Failed to process code: %s"%(d))

    # TODO: write a more generic parser of ranges
    #	for d in diag_ranges:
    #		if re.search('^urn:miriam:icd:', d):
    #			d = re.sub('^urn:miriam:icd:', '', d)
    #			if d in cancer_diag_ranges:
    #				log.debug("Collection %s identified as cancer collection due to ICD-10 code range %s"%(collection['id'],d))
    #				cancer_diag = True
    #			else:
    #				log.debug("Collection %s identified as non-cancer collection due to ICD-10 code range %s"%(collection['id'],d))
    #				non_cancer = True

    if cancer_diag:
        log.info("Collection " + collection['id'] + " has cancer cases")
        cancerExistingDiagnosed.append(collection)
        cancerBiobanksExistingDiagnosed.add(biobankId)
        if not non_cancer:
            log.info("Collection %s has cancer cases only" % (collection['id']))
            cancerOnlyExistingDiagnosed.append(collection)
            cancerOnlyBiobanksExistingDiagnosed.add(biobankId)
        else:
            log.info("Collection %s has mixture of cancer and non-cancer cases" % (collection['id']))
        if 'size' in collection and isinstance(collection['size'], int):
            cancerCollectionSamplesExplicit += collection['size']
            cancerCollectionSamplesIncOoM += collection['size']
            if not non_cancer:
                cancerOnlyCollectionSamplesExplicit += collection['size']
                cancerOnlyCollectionSamplesIncOoM += collection['size']
        else:
            cancerCollectionSamplesIncOoM += 10 ** OoM
            if not non_cancer:
                cancerOnlyCollectionSamplesIncOoM += 10 ** OoM
        if 'number_of_donors' in collection and isinstance(collection['number_of_donors'], int):
            cancerCollectionDonorsExplicit += collection['number_of_donors']
            if not non_cancer:
                cancerOnlyCollectionDonorsExplicit += collection['number_of_donors']

pd_cancerExistingDiagnosed = pd.DataFrame(cancerExistingDiagnosed)
pd_cancerExistingControls = pd.DataFrame(cancerExistingControls)
pd_cancerProspective = pd.DataFrame(cancerProspective)


def printCollectionStdout(collectionList: List, headerStr: str):
    print(headerStr + " - " + str(len(collectionList)) + " collections")
    for collection in collectionList:
        biobankId = dir.getCollectionBiobank(collection['id'])
        biobank = dir.getBiobankById(biobankId)
        print("   Collection: " + collection['id'] + " - " + collection[
            'name'] + ". Parent biobank: " + biobankId + " - " + biobank['name'])


if not args.nostdout:
    printCollectionStdout(cancerExistingDiagnosed, "Cancer Diagnosed")
    print("\n\n")
    printCollectionStdout(cancerExistingControls, "Cancer Controls")
    print("\n\n")
    printCollectionStdout(cancerProspective, "Cancer Prospective")
    print("\n\n")
    print("Totals:")
    print("- total number of cancer-relevant biobanks: %d" % (len(cancerBiobanks)))
    print("- total number of cancer-relevant collections with existing samples: %d in %d biobanks" % (
    len(cancerExistingDiagnosed), len(cancerBiobanksExistingDiagnosed)))
    print("- total number of exclusive cancer collections with existing samples: %d in %d biobanks" % (
    len(cancerOnlyExistingDiagnosed), len(cancerOnlyBiobanksExistingDiagnosed)))
    print("- total number of cancer-relevant collections with control samples: %d in %d biobanks" % (
    len(cancerExistingControls), len(cancerBiobanksExistingControls)))
    print("- total number of cancer-relevant prospective collections: %d in %d biobanks" % (
    len(cancerProspective), len(cancerBiobanksProspective)))
    print("Estimated totals:")
    print("- total number of samples advertised explicitly in cancer-only collections: %d" % (
        cancerOnlyCollectionSamplesExplicit))
    print("- total number of samples advertised explicitly in cancer-relevant collections: %d" % (
        cancerCollectionSamplesExplicit))
    print("- total number of donors advertised explicitly in cancer-only collections: %d" % (
        cancerOnlyCollectionDonorsExplicit))
    print("- total number of donors advertised explicitly in cancer-relevant collections: %d" % (
        cancerCollectionDonorsExplicit))
    print("- total number of samples advertised in cancer-only collections including OoM estimates: %d" % (
        cancerOnlyCollectionSamplesIncOoM))
    print("- total number of samples advertised in cancer-relevant collections including OoM estimates: %d" % (
        cancerCollectionSamplesIncOoM))

if args.outputXLSX is not None:
    log.info("Outputting warnings in Excel file " + args.outputXLSX[0])
    writer = pd.ExcelWriter(args.outputXLSX[0], engine='xlsxwriter')
    pd_cancerExistingDiagnosed.to_excel(writer, sheet_name='Cancer Diagnosed')
    pd_cancerExistingControls.to_excel(writer, sheet_name='Cancer Controls')
    pd_cancerProspective.to_excel(writer, sheet_name='Cancer Prospective')
    writer.save()
