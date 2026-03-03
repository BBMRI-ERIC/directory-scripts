#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

import pprint
import re
import logging as log
import time
from typing import List
import os.path


from cli_common import (
    add_validation_warning_argument,
    build_directory_kwargs,
    add_directory_auth_arguments,
    add_directory_schema_argument,
    add_logging_arguments,
    add_no_stdout_argument,
    add_plugin_disable_argument,
    add_purge_cache_arguments,
    add_remote_check_disable_arguments,
    add_withdrawn_scope_arguments,
    add_xlsx_output_argument,
    build_parser,
    configure_logging,
)
from validation_helpers import build_validation_warning_handler
from yapsy.PluginManager import PluginManager
from yapsy.IPlugin import IPlugin
import inspect

from customwarnings import DataCheckWarning
from warningscontainer import WarningsContainer
from nncontacts import NNContacts
from directory import Directory
from warning_suppressions import (
    DEFAULT_WARNING_SUPPRESSIONS_PATH,
    load_warning_suppressions,
)

from orphacodes import OrphaCodes

disabledChecks = {
#       "SemiemptyFields" : {"bbmri-eric:ID:NO_HUNT", "bbmri-eric:ID:NO_Janus"}
    }

pp = pprint.PrettyPrinter(indent=4)

class SafePluginManager(PluginManager):
    def isCorrectPlugin(self, candidate, category_name):
        try:
            module = candidate.load()
            for element in vars(module).values():
                if inspect.isclass(element) and issubclass(element, self.categories_interfaces[category_name]):
                    return True
            return False
        except Exception:
            return False

log.getLogger('yapsy').setLevel(log.INFO)

#simplePluginManager = PluginManager()
simplePluginManager = SafePluginManager(categories_filter={"Default": IPlugin})
simplePluginManager.setPluginPlaces(["checks"])
simplePluginManager.collectPlugins()

pluginList = []
for pluginInfo in simplePluginManager.getAllPlugins():
    pluginList.append(os.path.basename(pluginInfo.path))

remoteCheckList = ['emails', 'geocoding', 'URLs']
cachesList = ['directory', 'emails', 'geocoding', 'URLs']

parser = build_parser()
add_logging_arguments(parser)
add_xlsx_output_argument(parser)
add_no_stdout_argument(parser)
add_validation_warning_argument(parser)
add_withdrawn_scope_arguments(
    parser,
    include_help_text="include explicitly and logically withdrawn biobanks/collections in checks",
    only_help_text="run checks only on explicitly or logically withdrawn biobanks/collections",
)
add_remote_check_disable_arguments(parser, remoteCheckList)
add_plugin_disable_argument(parser, pluginList)
add_purge_cache_arguments(parser, cachesList)
parser.add_argument('-O', '--orphacodes-mapfile', dest='orphacodesfile', nargs=1,
                    help='file name of Orpha code mappings from http://www.orphadata.org/cgi-bin/ORPHAnomenclature.html')
parser.add_argument(
    '--warning-suppressions',
    dest='warning_suppressions',
    default=str(DEFAULT_WARNING_SUPPRESSIONS_PATH),
    help='JSON file mapping check IDs to entity IDs whose warnings should be suppressed as known false positives',
)
add_directory_auth_arguments(parser)
add_directory_schema_argument(parser, default='ERIC')

parser.set_defaults(disableChecksRemote = [], disablePlugins = [], purgeCaches=[])
args = parser.parse_args()

configure_logging(args)


# Main code

dir = Directory(**build_directory_kwargs(args, pp=pp))
dir.prepare_ai_cache_checksum_state()
validation_warn = build_validation_warning_handler(
    enabled=not getattr(args, "suppress_validation_warnings", False),
    logger=log.getLogger("validation"),
)
warningContainer = WarningsContainer(
    load_warning_suppressions(args.warning_suppressions, warn=validation_warn)
)

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
    allBiobanks = {}
    allCollections = {}
    for biobank in dir.getBiobanks():
        allBiobanks[biobank['id']] = str(dir.isBiobankWithdrawn(biobank['id']))
    for collection in dir.getCollections():
        allCollections[collection['id']] = str(dir.isCollectionWithdrawn(collection['id']))
    warningContainer.dumpWarningsXLSX(args.outputXLSX, allBiobanks, allCollections, True)
