#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

import pprint
import re
import logging as log
from builtins import str, isinstance, len, set, int
from typing import List

import pandas as pd

from cli_common import (
    add_logging_arguments,
    add_no_stdout_argument,
    add_purge_cache_arguments,
    add_xlsx_output_argument,
    build_parser,
    configure_logging,
)
from directory import Directory
from orphacodes import OrphaCodes
from icd10codeshelper import ICD10CodesHelper
import pddfutils
from xlsxutils import write_xlsx_tables

cachesList = ['directory']

pp = pprint.PrettyPrinter(indent=4)


parser = build_parser()
add_logging_arguments(parser)
add_xlsx_output_argument(parser)
parser.add_argument('-O', '--orphacodes-mapfile', dest='orphacodesfile', nargs=1,
                    help='file name of Orpha code mappings from http://www.orphadata.org/cgi-bin/ORPHAnomenclature.html')
add_no_stdout_argument(parser)
add_purge_cache_arguments(parser, cachesList)
parser.set_defaults(purgeCaches=[])
args = parser.parse_args()

configure_logging(args)

# Main code

dir = Directory(purgeCaches=args.purgeCaches, debug=args.debug, pp=pp)

log.info('Total biobanks: ' + str(dir.getBiobanksCount()))
log.info('Total collections: ' + str(dir.getCollectionsCount()))

orphacodes = OrphaCodes(args.orphacodesfile)

pediatricExistingDiagnosed = []
pediatricOnlyExistingDiagnosed = []
pediatricBiobanksExistingDiagnosed = set()
pediatricOnlyBiobanksExistingDiagnosed = set()
pediatricBiobanks = set()
pediatricOnlyBiobanks = set()
pediatricCollectionSamplesExplicit = 0
pediatricCollectionDonorsExplicit = 0
pediatricCollectionSamplesIncOoM = 0
pediatricOnlyCollectionSamplesExplicit = 0
pediatricOnlyCollectionDonorsExplicit = 0
pediatricOnlyCollectionSamplesIncOoM = 0

for collection in dir.getCollections():
    log.debug("Analyzing collection " + collection['id'])
    biobankId = dir.getCollectionBiobankId(collection['id'])
    biobank = dir.getBiobankById(biobankId)
    biobank_capabilities = []
    if 'capabilities' in biobank:
        for c in biobank['capabilities']:
            biobank_capabilities.append(c)
    biobank_covid = []
    if 'covid19biobank' in biobank:
        for c in biobank['covid19biobank']:
            biobank_covid.append(c)
    biobank_networks = []
    if 'network' in biobank:
        for n in biobank['network']:
            biobank_networks.append(n['id'])

    OoM = collection['order_of_magnitude']

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
                log.warning("Collection %s has invalid ORPHA code %s" % (collection['id'], d))

    pediatric = False
    pediatricOnly = False

    age_unit = None
    if 'age_unit' in collection:
        age_units = collection['age_unit']
        if len(age_units) > 1:
            log.warning("Ambiguous age units provided for %s: %s"%(collection['id'],age_units))
        if len(age_units) < 1:
            log.warning("Age units missing for %s"%(collection['id']))
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
            log.warning("Age range mismatch detected for collection: %s (%s), age range: %d-%d"%(collection['id'], collection['name'], collection.get('age_low'), collection.get('age_high')))
    elif 'age_high' in collection and collection['age_high'] < 0:
        log.warning("Age range mismatch detected for collection: %s (%s), age range: %d-%d"%(collection['id'], collection['name'], collection.get('age_low'), collection.get('age_high')))
    else:
        if 'age_low' in collection and 'age_high' in collection and collection['age_low'] > collection['age_high']:
            log.warning("Age range mismatch detected for collection: %s (%s), age range: %d-%d"%(collection['id'], collection['name'], collection.get('age_low'), collection.get('age_high')))
        else:
            if (('age_low' in collection and collection['age_low'] < age_max ) or ('age_high' in collection and collection['age_high'] < age_max)):
                pediatric = True
            if 'age_high' in collection and collection['age_high'] < age_max:
                pediatricOnly = True
                log.debug(f"Pediatric-only collection detected: {collection['id']}, age range: {collection.get('age_low')}-{collection.get('age_high')}, diags: {diags + diag_ranges}")

    if pediatric:
        log.info(f"Pediatric collection detected: {collection['id']}, age range: {collection.get('age_low')}-{collection.get('age_high')}, diags: {diags + diag_ranges}")
        pediatricExistingDiagnosed.append(collection)
        pediatricBiobanksExistingDiagnosed.add(biobankId)
        pediatricBiobanks.add(biobankId)
        if 'size' in collection and isinstance(collection['size'], int):
            pediatricCollectionSamplesExplicit += collection['size']
            pediatricCollectionSamplesIncOoM += collection['size']
    if pediatricOnly:
        log.info(f"Pediatric-only collection detected: {collection['id']}, age range: {collection.get('age_low')}-{collection.get('age_high')}, diags: {diags + diag_ranges}")
        pediatricOnlyExistingDiagnosed.append(collection)
        pediatricOnlyBiobanksExistingDiagnosed.add(biobankId)
        pediatricOnlyBiobanks.add(biobankId)
        if 'size' in collection and isinstance(collection['size'], int):
            pediatricOnlyCollectionSamplesExplicit += collection['size']
            pediatricOnlyCollectionSamplesIncOoM += collection['size']
    if 'number_of_donors' in collection and isinstance(collection['number_of_donors'], int):
        if pediatric:
            pediatricCollectionDonorsExplicit += collection['number_of_donors']
        if pediatricOnly:
            pediatricOnlyCollectionDonorsExplicit += collection['number_of_donors']

pd_pediatricExistingDiagnosed = pd.DataFrame(pediatricExistingDiagnosed)
pd_pediatricOnlyExistingDiagnosed = pd.DataFrame(pediatricOnlyExistingDiagnosed)


def printCollectionStdout(collectionList: List, headerStr: str):
    print(headerStr + " - " + str(len(collectionList)) + " collections")
    for collection in collectionList:
        biobankId = dir.getCollectionBiobankId(collection['id'])
        biobank = dir.getBiobankById(biobankId)
        log.info("   Collection: " + collection['id'] + " - " + collection['name'] + ". Parent biobank: " + biobankId + " - " + biobank['name'])


if not args.nostdout:
    print("Biobanks/collections totals:")
    print("- total of pediatric biobanks: %d" % (len(pediatricBiobanks)))
    print("- total of pediatric collections with existing samples: %d in %d biobanks" % (len(pediatricExistingDiagnosed), len(pediatricBiobanksExistingDiagnosed)))
    print("- total of pediatric-only biobanks: %d" % (len(pediatricOnlyBiobanks)))
    print("- total of pediatric-only collections with existing samples: %d in %d biobanks" % (len(pediatricOnlyExistingDiagnosed), len(pediatricOnlyBiobanksExistingDiagnosed)))
    print("\n")
    print("Estimated sample totals:")
    print("- total of samples/donors advertised explicitly in pediatric collections: %d / %d" % (pediatricCollectionSamplesExplicit, pediatricCollectionDonorsExplicit))
    print("- total of samples advertised in pediatric collections including OoM estimates: %d" % (pediatricCollectionSamplesIncOoM))
    print("- total of samples/donors advertised explicitly in pediatric-only collections: %d / %d" % (pediatricOnlyCollectionSamplesExplicit, pediatricOnlyCollectionDonorsExplicit))
    print("- total of samples advertised in pediatric-only collections including OoM estimates: %d" % (pediatricOnlyCollectionSamplesIncOoM))

for df in (pd_pediatricExistingDiagnosed, pd_pediatricOnlyExistingDiagnosed):
    pddfutils.tidyCollectionDf(df)

if args.outputXLSX is not None:
    write_xlsx_tables(
        args.outputXLSX[0],
        [
            (pd_pediatricExistingDiagnosed, 'Pediatric'),
            (pd_pediatricOnlyExistingDiagnosed, 'Pediatric-only'),
        ],
    )
