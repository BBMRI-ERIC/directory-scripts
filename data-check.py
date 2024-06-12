#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

import pprint
import re
import argparse
import logging as log
import time
from typing import List
import os.path

import xlsxwriter

from yapsy.PluginManager import PluginManager

from customwarnings import DataCheckWarning
from nncontacts import NNContacts
from directory import Directory

from orphacodes import OrphaCodes

disabledChecks = {
#       "SemiemptyFields" : {"bbmri-eric:ID:NO_HUNT", "bbmri-eric:ID:NO_Janus"}
    }

pp = pprint.PrettyPrinter(indent=4)

class ExtendAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest) or []
        items.extend(values)
        setattr(namespace, self.dest, items)

simplePluginManager = PluginManager()
simplePluginManager.setPluginPlaces(["checks"])
simplePluginManager.collectPlugins()

pluginList = []
for pluginInfo in simplePluginManager.getAllPlugins():
    pluginList.append(os.path.basename(pluginInfo.path))

remoteCheckList = ['emails', 'geocoding', 'URLs']
cachesList = ['directory', 'emails', 'geocoding', 'URLs']

parser = argparse.ArgumentParser()
parser.register('action', 'extend', ExtendAction)
parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='verbose information on progress of the data checks')
parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='debug information on progress of the data checks')
parser.add_argument('-X', '--output-XLSX', dest='outputXLSX', nargs=1, help='output of results into XLSX with filename provided as parameter')
parser.add_argument('-N', '--output-no-stdout', dest='nostdout', action='store_true', help='no output of results into stdout (default: enabled)')
parser.add_argument('--disable-checks-all-remote', dest='disableChecksRemote', action='store_const', const=remoteCheckList, help='disable all long remote checks (email address testing, geocoding, URLs')
parser.add_argument('--disable-checks-remote', dest='disableChecksRemote', nargs='+', action='extend', choices=remoteCheckList, help='disable particular long remote checks')
parser.add_argument('--disable-plugins', dest='disablePlugins', nargs='+', action='extend', choices=pluginList, help='disable particular check(s)')
parser.add_argument('--purge-all-caches', dest='purgeCaches', action='store_const', const=cachesList, help='disable all long remote checks (email address testing, geocoding, URLs')
parser.add_argument('--purge-cache', dest='purgeCaches', nargs='+', action='extend', choices=cachesList, help='purge particular cache(s)')
parser.add_argument('-O', '--orphacodes-mapfile', dest='orphacodesfile', nargs=1,
                    help='file name of Orpha code mappings from http://www.orphadata.org/cgi-bin/ORPHAnomenclature.html')
parser.add_argument('-p', '--password', dest='password', help='Password of the account used to login to the Directory')
parser.add_argument('-u', '--username', dest='username', help='Username of the account used to login to the Directory')
parser.add_argument('-P', '--package', dest='package', default='eu_bbmri_eric', help='MOLGENIS Package that contains the data (default eu_bbmri_eric).')

parser.set_defaults(disableChecksRemote = [], disablePlugins = [], purgeCaches=[])
args = parser.parse_args()

if args.debug:
    log.basicConfig(format="%(levelname)s: %(message)s", level=log.DEBUG)
elif args.verbose:
    log.basicConfig(format="%(levelname)s: %(message)s", level=log.INFO)
else:
    log.basicConfig(format="%(levelname)s: %(message)s")

class WarningsContainer:

    def __init__(self):
        # TODO
        self.__warnings = {}
        self.__warningsNNs = {}

    def newWarning(self, warning : DataCheckWarning):
        warning_key = ""
        self.__warningsNNs.setdefault(warning.NN,[]).append(warning)
        if warning.recipients != "":
            warning_key = recipients + ", "
        try: 
            warning_key += NNContacts.NNtoEmails[warning.NN]
        except KeyError:
            warning_key += 'petr.holub@bbmri-eric.eu, e.van.enckevort@rug.nl, a.w.hodselmans@rug.nl'
        self.__warnings.setdefault(warning_key,[]).append(warning)

    def dumpWarnings(self):
        for wk in sorted(self.__warnings):
            print(wk + ":")
            for w in sorted(self.__warnings[wk], key=lambda x: x.directoryEntityID + ":" + str(x.level.value)):
                if not (w.dataCheckID in disabledChecks and w.directoryEntityID in disabledChecks[w.dataCheckID]):
                    w.dump()
            print("")

    def dumpWarningsXLSX(self, filename : List[str]):
        workbook = xlsxwriter.Workbook(filename[0])
        bold = workbook.add_format({'bold': True})
        for nn in sorted(self.__warningsNNs):
            worksheet = workbook.add_worksheet(nn)
            worksheet_row = 0
            worksheet.write_string(worksheet_row, 0, "Entity ID", bold)
            worksheet.set_column(0,0, 50)
            worksheet.write_string(worksheet_row, 1, "Entity type", bold)
            worksheet.set_column(1,1, 10)
            worksheet.write_string(worksheet_row, 2, "Check", bold)
            worksheet.set_column(2,2, 20)
            worksheet.write_string(worksheet_row, 3, "Severity", bold)
            worksheet.set_column(3,3, 10)
            worksheet.write_string(worksheet_row, 4, "Message", bold)
            worksheet.set_column(4,4, 120)
            for w in sorted(self.__warningsNNs[nn], key=lambda x: x.directoryEntityID + ":" + str(x.level.value)):
                if not (w.dataCheckID in disabledChecks and w.directoryEntityID in disabledChecks[w.dataCheckID]):
                    worksheet_row += 1
                    worksheet.write_string(worksheet_row, 0, w.directoryEntityID)
                    worksheet.write_string(worksheet_row, 1, w.directoryEntityType.value)
                    worksheet.write_string(worksheet_row, 2, w.dataCheckID)
                    worksheet.write_string(worksheet_row, 3, w.level.name)
                    worksheet.write_string(worksheet_row, 4, w.message)
        workbook.close()

# Main code

if args.username is not None and args.password is not None:
    dir = Directory(package=args.package, purgeCaches=args.purgeCaches, debug=args.debug, pp=pp, username=args.username, password=args.password)
else:
    dir = Directory(package=args.package, purgeCaches=args.purgeCaches, debug=args.debug, pp=pp)
warningContainer = WarningsContainer()

orphacodes = None
if args.orphacodesfile is not None:
    orphacodes = OrphaCodes(args.orphacodesfile[0])
    dir.setOrphaCodesMapper(orphacodes)

log.info('Total biobanks: ' + str(dir.getBiobanksCount()))
log.info('Total collections: ' + str(dir.getCollectionsCount()))

log.debug('MMCI collections: ')
if args.debug:
    for biobank in dir.getBiobanks():
        if(re.search('MMCI', biobank['id'])):
            pp.pprint(biobank)
            collections = dir.getGraphBiobankCollectionsFromBiobank(biobank['id'])
            for e in collections.edges:
                print("   "+str(e[0])+" -> "+str(e[1]))

    for collection in dir.getCollections():
        if(re.search('MMCI', collection['id'])):
            pp.pprint(collection)

for pluginInfo in simplePluginManager.getAllPlugins():
    if os.path.basename(pluginInfo.path) in args.disablePlugins:
        continue
    simplePluginManager.activatePluginByName(pluginInfo.name)
    start_time = time.perf_counter()
    warnings = pluginInfo.plugin_object.check(dir, args)
    end_time = time.perf_counter()
    log.info('   ... check finished in ' + "%0.3f" % (end_time-start_time) + 's')
    if len(warnings) > 0:
       for w in warnings:
           warningContainer.newWarning(w)

if not args.nostdout:
    log.info("Outputting warnings on stdout")
    warningContainer.dumpWarnings()
if args.outputXLSX is not None:
    log.info("Outputting warnings in Excel file " + args.outputXLSX[0])
    warningContainer.dumpWarningsXLSX(args.outputXLSX)
