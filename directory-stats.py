#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:et

import pprint
import re
from enum import Enum
import sys
import argparse
import logging as log
import time
from typing import List
import os.path

import molgenis
import networkx as nx
import xlsxwriter

from yapsy.PluginManager import PluginManager
from diskcache import Cache

from customwarnings import DataCheckWarningLevel,DataCheckWarning

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
cachesList = ['directory', 'emails', 'geocoding']

parser = argparse.ArgumentParser()
parser.register('action', 'extend', ExtendAction)
parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='verbose information on progress of the data checks')
parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='debug information on progress of the data checks')
parser.add_argument('-X', '--output-XLSX', dest='outputXLSX', nargs=1, help='output of results into XLSX with filename provided as parameter')
parser.add_argument('-N', '--output-no-stdout', dest='nostdout', action='store_true', help='no output of results into stdout (default: enabled)')
parser.add_argument('--disable-checks-all-remote', dest='disableChecksRemote', action='store_const', const=remoteCheckList, help='disable all long remote checks (email address testing, geocoding, URLs')
parser.add_argument('--disable-checks-remote', dest='disableChecksRemote', nargs='+', action='extend', choices=remoteCheckList, help='disable particular long remote checks')
parser.add_argument('--disable-plugins', dest='disablePlugins', nargs='+', action='extend', choices=pluginList, help='disable particular long remote checks')
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


# Definition of Directory structure
from directory import Directory

# Main code

dir = Directory()

biobanks = {}
for biobank in dir.getBiobanks():
    biobankID = biobank['id']
    collections = dir.getGraphBiobankCollectionsFromBiobank(biobank['id'])
    biobanks[biobankID] = {}
    biobanks[biobankID]['topLevelCollections'] = collections.successors(biobank['id'])
    biobanks[biobankID]['biobankOrderOfMagnitude'] = 0
    biobanks[biobankID]['biobankSizeExact'] = 0
    biobanks[biobankID]['biobankSizeEstimate'] = 0
    for collectionID in biobanks[biobank['id']]['topLevelCollections']:
        OoM = dir.directoryGraph.nodes[collectionID]['data']['order_of_magnitude']['id']
        if 'size' in collection.keys:
            size = collection['size']
        else:
            size = 0
        if OoM > biobanks[biobank['id']]['biobankOrderOfMagnitude']:
            biobanks[biobank['id']]['biobankOrderOfMagnitude'] = OoM
        if size == 0:
            biobanks[biobank['id']]['biobankSizeEstimate'] += 3 * 10^OoM
        else:
            biobanks[biobank['id']]['biobankSizeExact'] += size
    biobanks[biobank['id']]['biobankSizeTotal'] = biobanks[biobank['id']]['biobankSizeExact'] + biobanks[biobank['id']]['biobankSizeEstimate'] 

log.info('Total biobanks: ' + str(dir.getBiobanksCount()))
log.info('Total collections: ' + str(dir.getCollectionsCount()))

if not args.nostdout:
    log.info("Outputting warnings on stdout")

    for biobankID in sorted(biobanks.iteritems(), key=lambda kv: kv[1]['biobankSizeTotal']):
        print(biobankID + "\t" + len(biobanks[biobankID]['topLevelCollections']) + "\t" + biobanks[biobankID]['biobankSizeTotal'])

if args.outputXLSX is not None:
    log.info("Outputting warnings in Excel file " + args.outputXLSX[0])
