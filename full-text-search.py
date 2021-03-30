#!/usr/bin/python3
# vim:ts=8:sw=8:tw=0:noet

from typing import List

import pprint
import re
import argparse
import logging as log
import time
from typing import List
import os.path

from directory import Directory

from whoosh.index import create_in
from whoosh.fields import *

cachesList = ['directory', 'emails', 'geocoding', 'URLs']

pp = pprint.PrettyPrinter(indent=4)

class ExtendAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest) or []
        items.extend(values)
        setattr(namespace, self.dest, items)

parser = argparse.ArgumentParser()
parser.register('action', 'extend', ExtendAction)
parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='verbose information on progress of the data checks')
parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='debug information on progress of the data checks')
parser.add_argument('--purge-all-caches', dest='purgeCaches', action='store_const', const=cachesList, help='disable all long remote checks (email address testing, geocoding, URLs')
parser.add_argument('--purge-cache', dest='purgeCaches', nargs='+', action='extend', choices=cachesList, help='disable particular long remote checks')
parser.add_argument('searchQuery', nargs='+', help='search query')
parser.set_defaults(disableChecksRemote = [], disablePlugins = [], purgeCaches=[])
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

indexdir = "indexdir"

if not os.path.exists(indexdir):
    os.makedirs(indexdir)

schema = Schema(id=ID(stored=True), type=STORED, name=TEXT, acronym=ID, description=TEXT, address=TEXT, phone=TEXT, email=TEXT, juridical_person=TEXT, bioresource_reference=ID, head_name=TEXT)
ix = create_in(indexdir, schema)
writer = ix.writer()

def getFullName(entity):
	return " ".join(filter(None,[entity.get('head_title_before_name'), entity.get('head_firstname'), entity.get('head_lastname'), entity.get('head_title_after_name')]))

for collection in dir.getCollections():
	log.debug("Analyzing collection " + collection['id'])
	biobankId = dir.getCollectionBiobank(collection['id'])
	biobank = dir.getBiobankById(biobankId)
	writer.add_document(id=collection['id'], type=u"COLLECTION", name=collection.get('name'), description=collection.get('description'), acronym=collection.get('acronym'), bioresource_reference=collection.get('bioresource_reference'), head_name=getFullName(collection))

for biobank in dir.getBiobanks():
	log.debug("Analyzing biobank " + biobank['id'])
	writer.add_document(id=biobank['id'], type=u"BIOBANK", name=biobank.get('name'), description=biobank.get('description'), acronym=biobank.get('acronym'), juridical_person=biobank.get('juridical_person'), bioresource_reference=biobank.get('bioresource_reference'), head_name=getFullName(biobank))

for contact in dir.getContacts():
	log.debug("Analyzing contact " + contact['id'])
	writer.add_document(id=contact['id'], type=u"CONTACT", name=" ".join(filter(None,[contact.get('title_before_name'), contact.get('first_name'), contact.get('last_name'), contact.get('title_after_name')])), phone=contact.get('phone'), email=contact.get('email'), address=", ".join(filter(None,[contact.get('address'),contact.get('city'),contact.get('zip')])))

writer.commit()

def printCollectionStdout(collectionList : List, headerStr : str):
	print(headerStr + " - " + str(len(collectionList)) + " collections")
	for collection in collectionList:
		biobankId = dir.getCollectionBiobank(collection['id'])
		biobank = dir.getBiobankById(biobankId)
		print("   Collection: " + collection['id'] + " - " + collection['name'] + ". Parent biobank: " +  biobankId + " - " + biobank['name'])


matchingCollections = {}
matchingBiobanks = {}
matchingContacts = {}

from whoosh.qparser import QueryParser,MultifieldParser
with ix.searcher() as searcher:
	#query = QueryParser("name", ix.schema).parse("Masaryk")
	query = MultifieldParser(["id", "name", "description", "acronym", "phone", "email", "juridical_person", "bioresource_reference", "head_name", "address"], ix.schema).parse(" ".join(args.searchQuery))
	results = searcher.search(query)
	for r in results:
		print(r)
