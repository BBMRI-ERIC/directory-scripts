#!/usr/bin/python3
# vim:ts=4:sw=4:sts=4:tw=0:et

from typing import List

import pprint
import re
import logging as log

from cli_common import (
    add_directory_schema_argument,
    add_logging_arguments,
    add_no_stdout_argument,
    add_purge_cache_arguments,
    add_withdrawn_scope_arguments,
    add_xlsx_output_argument,
    build_directory_kwargs,
    build_parser,
    configure_logging,
)
from directory import Directory


cachesList = ['directory']

pp = pprint.PrettyPrinter(indent=4)

parser = build_parser()
add_logging_arguments(parser)
add_xlsx_output_argument(parser)
add_no_stdout_argument(parser)
add_directory_schema_argument(parser, default="ERIC")
add_withdrawn_scope_arguments(parser)
add_purge_cache_arguments(parser, cachesList)
parser.set_defaults(purgeCaches=[])
args = parser.parse_args()
configure_logging(args)


# Main code

dir = Directory(**build_directory_kwargs(args, pp=pp))

log.info('Total biobanks: ' + str(dir.getBiobanksCount()))
log.info('Total collections: ' + str(dir.getCollectionsCount()))

for collection in dir.getCollections():
    log.info(f"Collection ID: {collection['id']}")
    if re.search('^bbmri-eric:ID:AT_MUG:collection:', collection['id']):
        subcollections = dir.getCollectionsDescendants(collection['id'])
        if len(subcollections) > 0:
            # just parent biobank ID
            biobankId = dir.getCollectionBiobankId(collection['id'])
            # get the whole subgraph of ancestors, current collection and its descendants
            subcollection_graph = dir.getGraphBiobankCollectionsFromCollection(collection['id'])

            print(f"Subcollections of parent collection {collection['id']} - {collection['name']}")
            for subcollection_Id in subcollection_graph.successors(collection['id']):
                subcollection = dir.getCollectionById(subcollection_Id)
                if subcollection is None:
                    log.warning("Subcollection %s not found, skipping" % subcollection_Id)
                    continue
                if collection['name'].lower() in subcollection['name'].lower():
                    data_element = re.sub(re.escape(collection['name'] + ' - '), '', subcollection['name'], flags=re.IGNORECASE)
                    print(f"{subcollection_Id} - Data element: {data_element}")
                else:
                    print(f"{subcollection_Id} - Name: {subcollection['name']}")
            print("")
