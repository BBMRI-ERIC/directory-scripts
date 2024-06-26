#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

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
typeList = ['COLLECTION', 'BIOBANK', 'CONTACT', 'NETWORK']

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
parser.add_argument('-i', '--print-ids-only', dest='printIdsOnly', action='store_true', help='print only matching IDs instead of search hits')
parser.add_argument('--purge-all-caches', dest='purgeCaches', action='store_const', const=cachesList, help='disable all long remote checks (email address testing, geocoding, URLs')
parser.add_argument('--purge-cache', dest='purgeCaches', nargs='+', action='extend', choices=cachesList, help='disable particular long remote checks')
parser.add_argument('--limit-types', dest='limitTypes', nargs='+', action='extend', choices=typeList, help='return only specific types')
parser.add_argument('searchQuery', nargs='+', help='search query')
parser.set_defaults(disableChecksRemote = [], disablePlugins = [], purgeCaches=[], limitTypes=[])
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
if 'directory' in args.purgeCaches and 'index' not in args.purgeCaches:
        args.purgeCaches.append('index')
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
    schema = Schema(id=TEXT(stored=True,analyzer=my_id_ana), type=STORED, name=TEXT(stored=True,analyzer=my_ana), acronym=ID, description=TEXT(analyzer=my_ana), address=TEXT(analyzer=my_ana), phone=TEXT, email=TEXT, juridical_person=TEXT(analyzer=my_ana), bioresource_reference=TEXT, head_id=TEXT(analyzer=my_id_ana), head_name=TEXT(analyzer=my_ana), contact_id=TEXT(analyzer=my_id_ana), contact_name=TEXT(analyzer=my_ana), also_known=TEXT(analyzer=my_ana))
    ix = create_in(indexdir, schema)
    writer = ix.writer()

    def getContact(contactId):
        contact = None
        try:
            contact = dir.getContact(contactId)
        except:
            pass
        return contact


    def getContactFullName(entity):
        if entity is None:
            return ""
        else:
            return " ".join(filter(None,[entity.get('title_before_name'), entity.get('first_name'), entity.get('last_name'), entity.get('title_after_name')]))

    def getAlsoKnown(entity):
        # TODO: this is a temporary hack - also_known needs to be properly handled by the Directory class and made accessible here
        also_known = []
        for ak in entity.get('also_known'):
            also_known.append(ak["id"])
        if also_known:
            return("\n".join(also_known))
        else:
            return("")

    for collection in dir.getCollections():
        log.debug("Analyzing collection " + collection['id'])
        biobankId = dir.getCollectionBiobankId(collection['id'])
        biobank = dir.getBiobankById(biobankId)
        contactId = None
        if 'contact' in collection:
            contactId = collection['contact']['id']
        elif 'contact' in biobank:
            contactId = biobank['contact']['id']
        writer.add_document(id=collection['id'], type=u"COLLECTION", name=collection.get('name'), description=collection.get('description'), acronym=collection.get('acronym'), bioresource_reference=collection.get('bioresource_reference'), contact_id=contactId, contact_name=getContactFullName(getContact(contactId)))

    for biobank in dir.getBiobanks():
        log.debug("Analyzing biobank " + biobank['id'])
        contactId = None
        if 'contact' in biobank:
            contactId = biobank['contact']['id']
        headId = None
        if 'head' in biobank:
            headId = biobank['head']['id']
        writer.add_document(id=biobank['id'], type=u"BIOBANK", name=biobank.get('name'), description=biobank.get('description'), acronym=biobank.get('acronym'), juridical_person=biobank.get('juridical_person'), bioresource_reference=biobank.get('bioresource_reference'), head_id=headId, head_name=getContactFullName(getContact(headId)), contact_id=contactId, contact_name=getContactFullName(getContact(contactId)))

    for contact in dir.getContacts():
        log.debug("Analyzing contact " + contact['id'])
        writer.add_document(id=contact['id'], type=u"CONTACT", name=getContactFullName(contact), phone=contact.get('phone'), email=contact.get('email'), address=", ".join(filter(None,[contact.get('address'),contact.get('city'),contact.get('zip')])))
    
    for network in dir.getNetworks():
        log.debug("Analyzing network " + network['id'])
        contactId = None
        if 'contact' in network:
            contactId = network['contact']['id']
        try:
            writer.add_document(id=network['id'], type=u"NETWORK", name=network.get('name'), description=network.get('description'), acronym=network.get('acronym'), contact_id=contactId, contact_name=getContactFullName(getContact(contactId)), also_known=getAlsoKnown(network))
        except Exception as e:
            pp.pprint(network)
            raise e

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
    query = MultifieldParser(["id", "name", "description", "acronym", "phone", "email", "juridical_person", "bioresource_reference", "address", "contact_id", "contact_name", "head_id", "head_name", "also_known"], ix.schema).parse(searchq)
    results = searcher.search(query, limit=None)
    for r in results:
        if args.limitTypes:
            if r["type"] not in args.limitTypes:
                continue
        if args.printIdsOnly:
            print(r["id"])
        else:
            print(r)
