#!/usr/bin/python3
'''
BBMRI-ERIC Directory Cohorts
'''

#############
## Imports ##
#############

# External
import pprint
import argparse
import logging as log
import pandas as pd
import time
import os.path

# Internal
from directory import Directory
#from checks.BBMRICohorts import BBMRICohorts
from warningscontainer import WarningsContainer
from yapsy.PluginManager import PluginManager


# Functions

def getCollBBNetwork(network, networkname, biobankId, biobank, coll_list : list, bb_list : list, checkedBbsIds : list):
    if network['id'] == networkname:
        coll_list.append(collection)
        if biobankId not in checkedBbsIds:
            bb_list.append(biobank)
            checkedBbsIds.append(biobankId)
    return coll_list, bb_list, checkedBbsIds

def addColletion2Df(collList : list, network : str, entity : str, df : pd.DataFrame, df_coll : pd.DataFrame, df_collFactsSampleNumber : pd.DataFrame):
    for coll in collList:
        nrSampDonProv = 'N'
        collsFactsSamples = 0
        factsProvided = 'N'
        warningProvided = 'N'
        errorProvided = 'N'
        df_coll.loc[len(df)] = [network,entity,str(coll['country']['id']),str(coll['name']),str(coll['id'])]
        if 'size' in coll and 'number_of_donors' in coll:
            if isinstance(coll['size'], int) and isinstance(coll['number_of_donors'], int):
                nrSampDonProv = 'Y'

        #Facts table
        if coll['facts'] != []:
            for fact in dir.getFacts():
                if fact['collection']['id'] == coll['id']:
                    if 'number_of_samples' in fact:
                        collsFactsSamples += fact['number_of_samples']
            if collsFactsSamples > 0:
                factsProvided = 'Y'
                df_collFactsSampleNumber.loc[len(df)] = [network,entity,str(coll['country']['id']),str(coll['name']),str(coll['id']),int(collsFactsSamples)]
        if coll['id'] in collIDsWARNING:
            warningProvided = 'Y'
        if coll['id'] in collIDsERROR:
            errorProvided = 'Y'
        log.info(network + '\t' + entity + '\t' + str(coll['country']['id']))
        df.loc[len(df)] = [network,entity,str(coll['country']['id']),str(nrSampDonProv),str(factsProvided),int(collsFactsSamples),str(errorProvided),str(warningProvided)]
    return df, df_coll, df_collFactsSampleNumber

def addBB2Df(BBList : list, network : str, entity : str, df : pd.DataFrame, df_bb : pd.DataFrame):
    for biobank_cohort in BBList:
        df.loc[len(df)] = [network,entity,str(biobank_cohort['country']['id']),'NA','NA',int(0),'NA','NA']
        df_bb.loc[len(df)] = [network,entity,str(biobank_cohort['country']['id']),str(biobank_cohort['name']),str(biobank_cohort['id'])]
        log.info(network + '\t'+ entity +'\t' + str(biobank_cohort['country']['id']))
    return df, df_bb

def outputExcelBiobanksCollections(filename : str, dfBiobanks : pd.DataFrame, biobanksLabel : str, dfCollections : pd.DataFrame, collectionsLabel : str, dfStats : pd.DataFrame, statsLabel : str, dfStats2 : pd.DataFrame, statsLabel2 : str, numberSamplesFacts : pd.DataFrame, samplesFactsLabel : str):
    log.info("Outputting warnings in Excel file " + filename)
    writer = pd.ExcelWriter(filename, engine='xlsxwriter')
    dfBiobanks.to_excel(writer, sheet_name=biobanksLabel)
    dfCollections.to_excel(writer, sheet_name=collectionsLabel)
    dfStats.to_excel(writer, sheet_name=statsLabel)
    dfStats2.to_excel(writer, sheet_name=statsLabel2)
    numberSamplesFacts.to_excel(writer, sheet_name=samplesFactsLabel)
    writer.close()


#############
### Main ####
#############

cachesList = ['directory', 'geocoding']

simplePluginManager = PluginManager()
simplePluginManager.setPluginPlaces(["checks"])
simplePluginManager.collectPlugins()

pluginList = []
for pluginInfo in simplePluginManager.getAllPlugins():
    pluginList.append(os.path.basename(pluginInfo.path))

remoteCheckList = ['emails', 'geocoding', 'URLs']

#####################
## Parse arguments ##
#####################

parser = argparse.ArgumentParser()
parser.add_argument('--purge-all-caches', dest='purgeCaches', action='store_const', const=cachesList, help='disable all long remote checks (directory and geocoding)')
parser.add_argument('-a', '--aggregator', dest='aggregator', type=str, default=['Network','Entity','Country','CollWithSampleDonorProvided','CollWithFactsProvided','nrSamplesFactTables','ErrorProvided','WarningProvided'], help='Space-separated list of the aggregators used in stdout. Accepted values: Network Entity Country')
parser.add_argument('-X', '--output-XLSX', dest='outputXLSX', default='bbmri_cohorts_stats.xlsx',
                    help='output of results into an XLSX with filename provided as parameter')
parser.add_argument('-XWE', '--output-WE-XLSX', dest='outputWEXLSX', nargs=1, help='output of warnings and errors into XLSX with filename provided as parameter')
parser.add_argument('-N', '--output-no-stdout', dest='nostdout', action='store_true', help='no output of results into stdout (default: enabled)')
parser.add_argument('-w', '--warnings', dest='warnings', action='store_true', help='print warning information on stdout')
parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='debug information on progress of the data checks')
parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='verbose information on progress of the data checks')
parser.add_argument('-p', '--password', dest='password', help='Password of the account used to login to the Directory')
parser.add_argument('-u', '--username', dest='username', help='Username of the account used to login to the Directory')
parser.add_argument('-P', '--package', dest='package', default='eu_bbmri_eric', help='MOLGENIS Package that contains the data (default eu_bbmri_eric).')
parser.add_argument('--print-filtered-df', dest='printDf', default=False, action="store_true", help='Print filtered data frame to stdout')
parser.add_argument('--disable-checks-all-remote', dest='disableChecksRemote', action='store_const', const=remoteCheckList, help='disable all long remote checks (email address testing, geocoding, URLs')
parser.add_argument('--disable-checks-remote', dest='disableChecksRemote', nargs='+', action='extend', choices=remoteCheckList, help='disable particular long remote checks')
parser.add_argument('--disable-plugins', dest='disablePlugins', nargs='+', action='extend', choices=pluginList, help='disable particular check(s)')
#parser.add_argument('--purge-cache', dest='purgeCaches', nargs='+', action='extend', choices=cachesList, help='disable particular long remote checks')

parser.set_defaults(disableChecksRemote = [], disablePlugins = [], purgeCaches=[])
args = parser.parse_args()
aggregator = args.aggregator
outputXLSX = args.outputXLSX
outputWEXLSX = args.outputWEXLSX

# Get info from Directory
pp = pprint.PrettyPrinter(indent=4)
if args.username is not None and args.password is not None:
    dir = Directory(package=args.package, purgeCaches=args.purgeCaches, debug=args.debug, pp=pp, username=args.username, password=args.password)
else:
    dir = Directory(package=args.package, purgeCaches=args.purgeCaches, debug=args.debug, pp=pp)


'''
warningsObj = BBMRICohorts()
warnings = warningsObj.check(dir, args)
collIDsERROR= [war.directoryEntityID for war in warnings if str(war.level) == 'DataCheckWarningLevel.ERROR']
collIDsWARNING= [war.directoryEntityID for war in warnings if str(war.level) == 'DataCheckWarningLevel.WARNING']
if args.warnings and len(warnings) > 0:
    warningContainer = WarningsContainer()
    for w in warnings:
           warningContainer.newWarning(w)
    warningContainer.dumpWarnings()
'''


bbmri_cohort_bb=[]
bbmri_cohort_dna_bb=[]
bbmri_cohort_coll=[]
bbmri_cohort_dna_coll=[]
bbmri_cohort_bbcoll=[]
bbmri_cohort_dna_bbcoll=[]
BBMRICohortsNetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts'
BBMRICohortsDNANetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts_DNA'

for biobank in dir.getBiobanks():
    log.debug("Analyzing collection " + biobank['id'])
    if 'network' in biobank:
        for n in biobank['network']:
            if n['id'] == BBMRICohortsNetworkName:
                bbmri_cohort_bb.append(biobank)
            if n['id'] == BBMRICohortsDNANetworkName:
                bbmri_cohort_dna_bb.append(biobank)

checkedBbsIdsCohort=[]
checkedBbsIdsCohortDNA=[]
for collection in dir.getCollections():
    log.debug("Analyzing collection " + collection['id'])
    biobankId = dir.getCollectionBiobankId(collection['id'])
    biobank = dir.getBiobankById(biobankId)
    if 'network' in collection:
        for n in collection['network']:
            bbmri_cohort_coll, bbmri_cohort_bbcoll, checkedBbsIdsCohort = getCollBBNetwork(n, BBMRICohortsNetworkName, biobankId, biobank, bbmri_cohort_coll, bbmri_cohort_bbcoll, checkedBbsIdsCohort)
            bbmri_cohort_dna_coll, bbmri_cohort_dna_bbcoll, checkedBbsIdsCohortDNA = getCollBBNetwork(n, BBMRICohortsDNANetworkName, biobankId, biobank, bbmri_cohort_dna_coll, bbmri_cohort_dna_bbcoll, checkedBbsIdsCohortDNA)
        
df  = pd.DataFrame(columns = ['Network','Entity','Country','CollWithSampleDonorProvided','CollWithFactsProvided','nrSamplesFactTables','ErrorProvided','WarningProvided'])
df_coll  = pd.DataFrame(columns = ['Network','Entity','Country','Name','ID'])
df_collFactsSampleNumber  = pd.DataFrame(columns = ['Network','Entity','Country','Name','ID','NumberOfSamples'])

# Retrieve the warnings
warningContainer = WarningsContainer()
for pluginInfo in simplePluginManager.getAllPlugins():
    if os.path.basename(pluginInfo.path) in args.disablePlugins:
        continue
    simplePluginManager.activatePluginByName(pluginInfo.name)
    start_time = time.perf_counter()
    warnings = pluginInfo.plugin_object.check(dir, args)
    end_time = time.perf_counter()
    log.info('   ... check finished in ' + "%0.3f" % (end_time-start_time) + 's')
    collIDsERROR= [war.directoryEntityID for war in warnings if str(war.level) == 'DataCheckWarningLevel.ERROR']
    collIDsWARNING= [war.directoryEntityID for war in warnings if str(war.level) == 'DataCheckWarningLevel.WARNING']
    if args.warnings and len(warnings) > 0:
        for w in warnings:
            #if w.directoryEntityID in [coll['id'] for coll in bbmri_cohort_coll] or w.directoryEntityID in [coll['id'] for coll in bbmri_cohort_dna_coll]:
                #warningContainer.newWarning(w)
            if w.directoryEntityID in [bb['id'] for bb in bbmri_cohort_bb]:
                warningContainer.newWarning(w)
            elif w.directoryEntityID in [bb['id'] for bb in bbmri_cohort_dna_bb]:
                warningContainer.newWarning(w)
            elif w.directoryEntityID in [coll['id'] for coll in bbmri_cohort_coll]:
                warningContainer.newWarning(w)
            elif w.directoryEntityID in [coll['id'] for coll in bbmri_cohort_dna_coll]:
                warningContainer.newWarning(w)
            elif w.directoryEntityID in [coll['id'] for coll in bbmri_cohort_bbcoll]:
                warningContainer.newWarning(w)
            elif w.directoryEntityID in [coll['id'] for coll in bbmri_cohort_dna_bbcoll]:
                warningContainer.newWarning(w)

if not args.nostdout:
    log.info("Outputting warnings on stdout")
    warningContainer.dumpWarnings()
if args.outputWEXLSX is not None:
    log.info("Outputting warnings in Excel file " + args.outputWEXLSX[0])
    warningContainer.dumpWarningsXLSX(args.outputWEXLSX, allNNs_sheet = True)

df, df_coll, df_collFactsSampleNumber = addColletion2Df(bbmri_cohort_coll, 'BBMRI_Cohort', 'Collection',df, df_coll, df_collFactsSampleNumber)
df, df_coll, df_collFactsSampleNumber = addColletion2Df(bbmri_cohort_dna_coll, 'BBMRI_Cohort_DNA', 'Collection',df, df_coll, df_collFactsSampleNumber)

df_bb  = pd.DataFrame(columns = ['Network','Entity','Country','Name','ID'])

df, df_bb = addBB2Df(bbmri_cohort_bb, 'BBMRI_Cohort', 'Biobank', df, df_bb)
df, df_bb = addBB2Df(bbmri_cohort_dna_bb, 'BBMRI_Cohort_DNA', 'Biobank', df, df_bb)
df, df_bb = addBB2Df(bbmri_cohort_bbcoll, 'BBMRI_Cohort', 'BiobankWithCollectionInNetwork', df, df_bb)
df, df_bb = addBB2Df(bbmri_cohort_dna_bbcoll, 'BBMRI_Cohort_DNA', 'BiobankWithCollectionInNetwork', df, df_bb)

# Prepare output
# Stats1
countCountries = df.groupby(aggregator).size().reset_index(name='Count')

columns_to_sum = ['nrSamplesFactTables','Count']
columns_to_group_by = ['Network','Entity','Country','CollWithSampleDonorProvided','CollWithFactsProvided','ErrorProvided','WarningProvided']

statsdf = countCountries.groupby(columns_to_group_by, as_index=False).agg({col: 'sum' for col in columns_to_sum})

#Stats2 = Only Collections and less columns
df_onlyColl = df[df['Entity'] == 'Collection']
df_lessCol = df_onlyColl[['Network','Entity','Country']]
statsdf2 = df_lessCol.groupby(['Network','Entity','Country']).size().reset_index(name='Count')

outputExcelBiobanksCollections(args.outputXLSX, df_bb, "Biobanks", df_coll, "Collections", statsdf2, "Stats", statsdf, "StatsDetailed", df_collFactsSampleNumber, "NumberOfSamplesFactTable")
