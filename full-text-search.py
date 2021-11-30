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

from whoosh.index import create_in, open_dir
from whoosh.fields import *
from whoosh.analysis import *
from whoosh.query import *
from whoosh.support.charset import accent_map

cachesList = ['directory', 'index']

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


indexdir = "indexdir"


# purging directory cache means the index cache should be purged as well - data has to be refreshed in the index, too
if 'directory' in args.purgeCaches:
        args.purgeCaches.add('index')
if 'index' in args.purgeCaches or not os.path.exists(indexdir):
	dir = Directory(purgeCaches=args.purgeCaches, debug=args.debug, pp=pp)

	log.info('Total biobanks: ' + str(dir.getBiobanksCount()))
	log.info('Total collections: ' + str(dir.getCollectionsCount()))

	if not os.path.exists(indexdir):
	    os.makedirs(indexdir)

	my_ana = StemmingAnalyzer() | CharsetFilter(accent_map)
	# this tokenizer allows for searching on full IDs as well as on components between : chars
	# however, in search there is a problem with searching for : chars - escaping does not work, hence introduced the hack below to replace : with ?
	# uncommenting LoggingFilter() and running the script with -d allows for debugging the tokenization
	my_id_ana = RegexTokenizer(expression=re.compile('[^ ]+')) | LowercaseFilter() | TeeFilter(PassFilter(), IntraWordFilter(delims=u':',splitnums=False) | StopFilter(stoplist=frozenset(['bbmri-eric', 'id', 'contactid', 'networkid', 'collection']))) # | LoggingFilter()
	schema = Schema(id=TEXT(stored=True,analyzer=my_id_ana), type=STORED, name=TEXT(stored=True,analyzer=my_ana), acronym=ID, description=TEXT(analyzer=my_ana), address=TEXT(analyzer=my_ana), phone=TEXT, email=TEXT, juridical_person=TEXT(analyzer=my_ana), bioresource_reference=TEXT, head_name=TEXT(analyzer=my_ana),contact_id=TEXT(analyzer=my_id_ana))
	ix = create_in(indexdir, schema)
	writer = ix.writer()

	def getFullName(entity):
		return " ".join(filter(None,[entity.get('head_title_before_name'), entity.get('head_firstname'), entity.get('head_lastname'), entity.get('head_title_after_name')]))

	for collection in dir.getCollections():
		log.debug("Analyzing collection " + collection['id'])
		biobankId = dir.getCollectionBiobankId(collection['id'])
		biobank = dir.getBiobankById(biobankId)
		contactId = None
		if 'contact' in collection:
			contactId = collection['contact']['id']
		elif 'contact' in biobank:
			contactId = biobank['contact']['id']
		writer.add_document(id=collection['id'], type=u"COLLECTION", name=collection.get('name'), description=collection.get('description'), acronym=collection.get('acronym'), bioresource_reference=collection.get('bioresource_reference'), head_name=getFullName(collection), contact_id=contactId)

	for biobank in dir.getBiobanks():
		log.debug("Analyzing biobank " + biobank['id'])
		contactId = None
		if 'contact' in biobank:
			contactId = biobank['contact']['id']
		writer.add_document(id=biobank['id'], type=u"BIOBANK", name=biobank.get('name'), description=biobank.get('description'), acronym=biobank.get('acronym'), juridical_person=biobank.get('juridical_person'), bioresource_reference=biobank.get('bioresource_reference'), head_name=getFullName(biobank), contact_id=contactId)

	for contact in dir.getContacts():
		log.debug("Analyzing contact " + contact['id'])
		writer.add_document(id=contact['id'], type=u"CONTACT", name=" ".join(filter(None,[contact.get('title_before_name'), contact.get('first_name'), contact.get('last_name'), contact.get('title_after_name')])), phone=contact.get('phone'), email=contact.get('email'), address=", ".join(filter(None,[contact.get('address'),contact.get('city'),contact.get('zip')])))

	writer.commit()

else:
	ix = open_dir(indexdir)

matchingCollections = {}
matchingBiobanks = {}
matchingContacts = {}

from whoosh.qparser import QueryParser,MultifieldParser
with ix.searcher() as searcher:
	searchq = " ".join(args.searchQuery)
	# XXX: this is a hack workaround around escaping of : character that does not work properly
	searchq = re.sub(r':', '?', searchq)
	query = MultifieldParser(["id", "name", "description", "acronym", "phone", "email", "juridical_person", "bioresource_reference", "head_name", "address", "contact_id"], ix.schema).parse(searchq)
	results = searcher.search(query, limit=None)
	for r in results:
		print(r)
