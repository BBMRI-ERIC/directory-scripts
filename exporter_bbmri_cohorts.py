#!/usr/bin/python3
'''
BBMRI-ERIC Directory Cohorts
'''

#############
## Imports ##
#############

# External
import pprint
import re
import argparse
import json
import configparser
import geopy.geocoders
from dms2dec.dms_convert import dms2dec
import ssl
import logging as log
import smtplib
import pandas as pd
from flatten_json import flatten

# Internal
from directory import Directory

cachesList = ['directory', 'geocoding']

#####################
## Parse arguments ##
#####################

parser = argparse.ArgumentParser()
parser.add_argument('--purge-all-caches', dest='purgeCaches', action='store_const', const=cachesList, help='disable all long remote checks (directory and geocoding)')
parser.add_argument('-a', '--aggregator', dest='aggregator', type=str, default=['Network','Entity','Country'], help='Space-separated list of the aggregators used in stdout. Accepted values: Network Entity Country')
parser.add_argument('-X', '--output-XLSX', dest='outputXLSX', default='bbmri_cohorts_stats.xlsx',
                    help='output of results into an XLSX with filename provided as parameter')
parser.add_argument('-o', '--outName', dest='outName', default='bbmri-directory-5-0', help='Output file name')
parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='debug information on progress of the data checks')
parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='verbose information on progress of the data checks')
parser.add_argument('-p', '--password', dest='password', help='Password of the account used to login to the Directory')
parser.add_argument('-u', '--username', dest='username', help='Username of the account used to login to the Directory')
parser.add_argument('-P', '--package', dest='package', default='eu_bbmri_eric', help='MOLGENIS Package that contains the data (default eu_bbmri_eric).')
parser.add_argument('--print-filtered-df', dest='printDf', default=False, action="store_true", help='Print filtered data frame to stdout')
#parser.add_argument('--purge-cache', dest='purgeCaches', nargs='+', action='extend', choices=cachesList, help='disable particular long remote checks')

parser.set_defaults(purgeCaches=[])
args = parser.parse_args()
aggregator = args.aggregator
outputXLSX = args.outputXLSX

# Get info from Directory
pp = pprint.PrettyPrinter(indent=4)
if args.username is not None and args.password is not None:
    dir = Directory(package=args.package, purgeCaches=args.purgeCaches, debug=args.debug, pp=pp, username=args.username, password=args.password)
else:
    dir = Directory(package=args.package, purgeCaches=args.purgeCaches, debug=args.debug, pp=pp)

bbmri_cohort_bb=[]
bbmri_cohort_dna_bb=[]
bbmri_cohort_coll=[]
bbmri_cohort_dna_coll=[]
bbmri_cohort_bbcoll=[]
bbmri_cohort_dna_bbcoll=[]

for biobank in dir.getBiobanks():
    log.debug("Analyzing collection " + biobank['id'])
    if 'network' in biobank:
        for n in biobank['network']:
            if n['id'] == 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts':
                bbmri_cohort_bb.append(biobank)
                #print(biobank['id'] +' '+biobank['country']['id'])
            if n['id'] == 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts_DNA':
                bbmri_cohort_dna_bb.append(biobank)

checkedBbsIdsCohort=[]
checkedBbsIdsCohortDNA=[]
for collection in dir.getCollections():
    log.debug("Analyzing collection " + collection['id'])
    biobankId = dir.getCollectionBiobankId(collection['id'])
    biobank = dir.getBiobankById(biobankId)
    if 'network' in collection:
        for n in collection['network']:
            if n['id'] == 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts':
                bbmri_cohort_coll.append(collection)
                if biobankId not in checkedBbsIdsCohort:
                    bbmri_cohort_bbcoll.append(biobank)
                    checkedBbsIdsCohort.append(biobankId)
            if n['id'] == 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts_DNA':
                bbmri_cohort_dna_coll.append(collection)
                if biobankId not in checkedBbsIdsCohortDNA:
                    bbmri_cohort_dna_bbcoll.append(biobank)
                    checkedBbsIdsCohortDNA.append(biobankId)
        

df  = pd.DataFrame(columns = ['Network','Entity','Country'])
df_bb  = pd.DataFrame(columns = ['Network','Entity','Country','Name','ID'])
df_coll  = pd.DataFrame(columns = ['Network','Entity','Country','Name','ID'])


for biobank_cohort in bbmri_cohort_bb:
    df.loc[len(df)] = ['BBMRI_Cohort','Biobank',str(biobank_cohort['country']['id'])]
    df_bb.loc[len(df)] = ['BBMRI_Cohort','Biobank',str(biobank_cohort['country']['id']),str(biobank_cohort['name']),str(biobank_cohort['id'])]
    #print('BBMRI_Cohort' + '\tBiobank\t' + str(biobank_cohort['country']['id']))

for biobank_cohort_dna in bbmri_cohort_dna_bb:
    df.loc[len(df)] = ['BBMRI_Cohort_DNA','Biobank',str(biobank_cohort_dna['country']['id'])]
    df_bb.loc[len(df)] = ['BBMRI_Cohort_DNA','Biobank',str(biobank_cohort_dna['country']['id']),str(biobank_cohort_dna['name']),str(biobank_cohort_dna['id'])]
    #print('BBMRI_Cohort_DNA' + '\tBiobank\t' + str(biobank_cohort_dna['country']['id']))

for bbcoll_cohort in bbmri_cohort_bbcoll:
    df.loc[len(df)] = ['BBMRI_Cohort','BiobankCollection',str(bbcoll_cohort['country']['id'])]
    df_bb.loc[len(df)] = ['BBMRI_Cohort','BiobankCollection',str(bbcoll_cohort['country']['id']),str(bbcoll_cohort['name']),str(bbcoll_cohort['id'])]
    #print('BBMRI_Cohort' + '\tCollection\t' + str(coll_cohort['country']['id']))

for bbcoll_cohort_dna in bbmri_cohort_dna_bbcoll:
    df.loc[len(df)] = ['BBMRI_Cohort_DNA','BiobankCollection',str(bbcoll_cohort_dna['country']['id'])]
    df_bb.loc[len(df)] = ['BBMRI_Cohort_DNA','BiobankCollection',str(bbcoll_cohort_dna['country']['id']),str(bbcoll_cohort_dna['name']),str(bbcoll_cohort_dna['id'])]
    #print('BBMRI_Cohort_DNA' + '\tCollection\t' + str(coll_cohort_dna['country']['id']))

for coll_cohort in bbmri_cohort_coll:
    df.loc[len(df)] = ['BBMRI_Cohort','Collection',str(coll_cohort['country']['id'])]
    df_coll.loc[len(df)] = ['BBMRI_Cohort','Collection',str(coll_cohort['country']['id']),str(coll_cohort['name']),str(coll_cohort['id'])]
    #print('BBMRI_Cohort' + '\tCollection\t' + str(coll_cohort['country']['id']))

for coll_cohort_dna in bbmri_cohort_dna_coll:
    df.loc[len(df)] = ['BBMRI_Cohort_DNA','Collection',str(coll_cohort_dna['country']['id'])]
    df_coll.loc[len(df)] = ['BBMRI_Cohort_DNA','Collection',str(coll_cohort_dna['country']['id']),str(coll_cohort_dna['name']),str(coll_cohort_dna['id'])]
    #print('BBMRI_Cohort_DNA' + '\tCollection\t' + str(coll_cohort_dna['country']['id']))


def outputExcelBiobanksCollections(filename : str, dfBiobanks : pd.DataFrame, biobanksLabel : str, dfCollections : pd.DataFrame, collectionsLabel : str, dfStats : pd.DataFrame, statsLabel : str):
    log.info("Outputting warnings in Excel file " + filename)
    writer = pd.ExcelWriter(filename, engine='xlsxwriter')
    dfBiobanks.to_excel(writer, sheet_name=biobanksLabel)
    dfCollections.to_excel(writer, sheet_name=collectionsLabel)
    dfStats.to_excel(writer, sheet_name=statsLabel)
    writer.close()

statsdf = df.groupby(aggregator).size().reset_index(name='Count')
outputExcelBiobanksCollections(args.outputXLSX, df_bb, "Biobanks", df_coll, "Collections", statsdf, "Stats")