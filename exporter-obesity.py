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
from oomutils import (
    describe_oom_estimate_policy,
    estimate_count_from_oom,
    get_oom_upper_bound_coefficient,
)
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
log.info(
    "OoM estimate policy: %s (coefficient=%s)",
    describe_oom_estimate_policy(),
    get_oom_upper_bound_coefficient(),
)

orphacodes = OrphaCodes(args.orphacodesfile[0])

collectionsPediatricOnlyObesityDiagnosed = []
biobanksPediatricOnlyObesityDiagnosed = set()
pediatricOnlyObesitySamplesExplicit = 0
pediatricOnlyObesitySamplesIncOoM = 0
pediatricOnlyObesityDonorsExplicit = 0
collectionsPediatricObesityDiagnosed = []
biobanksPediatricObesityDiagnosed = set()
pediatricObesitySamplesExplicit = 0
pediatricObesitySamplesIncOoM = 0
pediatricObesityDonorsExplicit = 0
collectionsObesityDiagnosed = []
biobanksObesityDiagnosed = set()
obesitySamplesExplicit = 0
obesitySamplesIncOoM = 0
obesityDonorsExplicit = 0


for collection in dir.getCollections():
    log.debug("Analyzing collection " + collection['id'])
    biobankId = dir.getCollectionBiobankId(collection['id'])
    biobank = dir.getBiobankById(biobankId)

    # Add contact info
    if 'contact' in collection:
        collection['contact'] = dir.getContact(collection['contact']['id'])

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
    obesity = False

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
            isObesity = ICD10CodesHelper.isObesityCode(d)
            if isObesity is not None and isObesity:
                    log.debug(
                        "Collection %s identified as obesity collection due to ICD-10 code %s" % (collection['id'], d))
                    obesity = True

    if 'name' in collection:
        if re.search(r'(obesity|obese)', collection['name'], re.IGNORECASE):
                    log.debug("Collection %s identified as obesity collection due to its name %s" % (collection['id'], collection['name']))
                    obesity = True

    if 'description' in collection:
        if re.search(r'(obesity|obese)', collection['description'], re.IGNORECASE):
                    log.debug("Collection %s identified as obesity collection due to its description" % (collection['id']))
                    obesity = True

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
                log.debug("Pediatric-only collection detected: %s, age high: %d, diags: %s"%(collection['id'], collection.get('age_high'), diags + diag_ranges))

    if pediatricOnly and obesity:
        log.info(f"Pediatric-only collection detected: {collection['id']}, age range: {collection.get('age_low')}-{collection.get('age_high')}, diags: {diags + diag_ranges}")
        collectionsPediatricOnlyObesityDiagnosed.append(collection)
        biobanksPediatricOnlyObesityDiagnosed.add(biobankId)
        if 'size' in collection and isinstance(collection['size'], int):
            pediatricOnlyObesitySamplesExplicit += collection['size']
            pediatricOnlyObesitySamplesIncOoM += collection['size']
        else:
            estimate = estimate_count_from_oom(collection['order_of_magnitude'])
            log.info('Adding %d for OoM %s on behalf of %s'%(estimate, collection['order_of_magnitude'], collection['id']))
            pediatricOnlyObesitySamplesIncOoM += estimate
        if 'number_of_donors' in collection and isinstance(collection['number_of_donors'], int):
            pediatricOnlyObesityDonorsExplicit += collection['number_of_donors']
    elif pediatric and obesity:
        log.info(f"Pediatric collection detected: {collection['id']}, age range: {collection.get('age_low')}-{collection.get('age_high')}, diags: {diags + diag_ranges}")
        collectionsPediatricObesityDiagnosed.append(collection)
        biobanksPediatricObesityDiagnosed.add(biobankId)
        if 'size' in collection and isinstance(collection['size'], int):
            pediatricObesitySamplesExplicit += collection['size']
            pediatricObesitySamplesIncOoM += collection['size']
        else:
            estimate = estimate_count_from_oom(collection['order_of_magnitude'])
            log.info('Adding %d for OoM %s on behalf of %s'%(estimate, collection['order_of_magnitude'], collection['id']))
            pediatricObesitySamplesIncOoM += estimate
        if 'number_of_donors' in collection and isinstance(collection['number_of_donors'], int):
            pediatricObesityDonorsExplicit += collection['number_of_donors']
    elif obesity:
        log.info(f"Pediatric-only collection detected: {collection['id']}, age range: {collection.get('age_low')}-{collection.get('age_high')}, diags: {diags + diag_ranges}")
        collectionsObesityDiagnosed.append(collection)
        biobanksObesityDiagnosed.add(biobankId)
        if 'size' in collection and isinstance(collection['size'], int):
            obesitySamplesExplicit += collection['size']
            obesitySamplesIncOoM += collection['size']
        else:
            estimate = estimate_count_from_oom(collection['order_of_magnitude'])
            log.info('Adding %d for OoM %s on behalf of %s'%(estimate, collection['order_of_magnitude'], collection['id']))
            obesitySamplesIncOoM += estimate
        if 'number_of_donors' in collection and isinstance(collection['number_of_donors'], int):
            obesityDonorsExplicit += collection['number_of_donors']

pd_collectionsPediatricOnlyObesityDiagnosed = pd.DataFrame(collectionsPediatricOnlyObesityDiagnosed)
pd_collectionsPediatricObesityDiagnosed = pd.DataFrame(collectionsPediatricObesityDiagnosed)
pd_collectionsObesityDiagnosed = pd.DataFrame(collectionsObesityDiagnosed)


def printCollectionStdout(collectionList: List, headerStr: str):
    print(headerStr + " - " + str(len(collectionList)) + " collections")
    for collection in collectionList:
        biobankId = dir.getCollectionBiobankId(collection['id'])
        biobank = dir.getBiobankById(biobankId)
        log.info("   Collection: " + collection['id'] + " - " + collection['name'] + ". Parent biobank: " + biobankId + " - " + biobank['name'])


if not args.nostdout:
    print("Biobanks/collections totals:")
    print("- total of pediatric-only obesity collections with existing samples: %d in %d biobanks" % (
    len(collectionsPediatricOnlyObesityDiagnosed), len(biobanksPediatricOnlyObesityDiagnosed)))
    print("- total of pediatric-only obesity samples: %d explicit, %d with OoM; donors: %d explicit" % (
    pediatricOnlyObesitySamplesExplicit, pediatricOnlyObesitySamplesIncOoM,  pediatricOnlyObesityDonorsExplicit))
    print("- total of pediatric obesity collections with existing samples: %d in %d biobanks" % (
    len(collectionsPediatricObesityDiagnosed), len(biobanksPediatricObesityDiagnosed)))
    print("- total of pediatric obesity samples: %d explicit, %d with OoM; donors: %d explicit" % (
    pediatricObesitySamplesExplicit, pediatricObesitySamplesIncOoM,  pediatricObesityDonorsExplicit))
    print("- total of obesity collections with existing samples: %d in %d biobanks" % (
    len(collectionsObesityDiagnosed), len(biobanksObesityDiagnosed)))
    print("- total of obesity samples: %d explicit, %d with OoM; donors: %d explicit" % (
    obesitySamplesExplicit, obesitySamplesIncOoM,  obesityDonorsExplicit))

for df in (pd_collectionsPediatricOnlyObesityDiagnosed, pd_collectionsPediatricObesityDiagnosed, pd_collectionsObesityDiagnosed):
    pddfutils.tidyCollectionDf(df)

if args.outputXLSX is not None:
    write_xlsx_tables(
        args.outputXLSX[0],
        [
            (pd_collectionsPediatricOnlyObesityDiagnosed, 'Pediatric-only obesity'),
            (pd_collectionsPediatricObesityDiagnosed, 'Pediatric obesity'),
            (pd_collectionsObesityDiagnosed, 'Obesity'),
        ],
    )
