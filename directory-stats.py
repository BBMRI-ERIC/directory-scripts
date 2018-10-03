#!/usr/bin/python3

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
#		"SemiemptyFields" : {"bbmri-eric:ID:NO_HUNT", "bbmri-eric:ID:NO_Janus"}
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

class Directory:

	def __init__(self):
		cache_dir = 'data-check-cache/directory'
		if not os.path.exists(cache_dir):
			os.makedirs(cache_dir)
		cache = Cache(cache_dir)
		if 'directory' in args.purgeCaches:
			cache.clear()

		self.__directoryURL = "https://directory.bbmri-eric.eu/api/"
		log.info('Retrieving directory content from ' + self.__directoryURL)
		session = molgenis.Session(self.__directoryURL)
		log.info('   ... retrieving biobanks')
		if 'biobanks' in cache:
			self.biobanks = cache['biobanks']
		else:
			start_time = time.perf_counter()
			self.biobanks = session.get("eu_bbmri_eric_biobanks", num=0, expand=['contact','collections','country'])
			cache['biobanks'] = self.biobanks  
			end_time = time.perf_counter()
			log.info('   ... retrieved biobanks in ' + "%0.3f" % (end_time-start_time) + 's')
		log.info('   ... retrieving collections')
		if 'collections' in cache:
			self.collections = cache['collections']
		else:
			start_time = time.perf_counter()
			#self.collections = session.get("eu_bbmri_eric_collections", num=0, expand=['biobank','contact','network','parent_collection','sub_collections','type','materials','order_of_magnitude','data_categories', 'diagnosis_available', 'imaging_modality', 'image_dataset_type'])
			self.collections = session.get("eu_bbmri_eric_collections", num=0, expand=[])
			cache['collections'] = self.collections  
			end_time = time.perf_counter()
			log.info('   ... retrieved %d collections in %0.3fs' % (len(self.collections), (end_time-start_time)))
		log.info('   ... retrieving contacts')
		if 'contacts' in cache:
			self.contacts = cache['contacts']
		else:
			start_time = time.perf_counter()
			self.contacts = session.get("eu_bbmri_eric_persons", num=0, expand=['biobanks','collections','networks','country'])
			cache['contacts'] = self.contacts  
			end_time = time.perf_counter()
			log.info('   ... retrieved contacts in ' + "%0.3f" % (end_time-start_time) + 's')
		log.info('   ... retrieving networks')
		if 'networks' in cache:
			self.networks = cache['networks']
		else:
			start_time = time.perf_counter()
			self.networks = session.get("eu_bbmri_eric_networks", num=0, expand=['contact','country'])
			cache['networks'] = self.networks  
			end_time = time.perf_counter()
			log.info('   ... retrieved networks in ' + "%0.3f" % (end_time-start_time) + 's')
		log.info('   ... all entities retrieved')
		self.contactHashmap = {}

		log.info('Processing directory data')
		# Graph containing only biobanks and collections
		self.directoryGraph = nx.DiGraph()
		# DAG containing only biobanks and collections
		self.directoryCollectionsDAG = nx.DiGraph()
		# Weighted graph linking contacts to biobanks/collections/networks
		self.contactGraph = nx.DiGraph()
		# Graph linking networks to biobanks/collections
		self.networkGraph = nx.DiGraph()
		for c in self.contacts:
			if re.search('BBNM', c['id']):
				log.info("Removing contact " + c['id'])
				self.contacts.remove(c)
				continue
			if self.contactGraph.has_node(c['id']):
				raise Exception('DirectoryStructure', 'Conflicting ID found in contactGraph: ' + c['id'])
			# XXX temporary hack -- adding contactID prefix
			#self.contactGraph.add_node(c['id'], data=c)
			self.contactGraph.add_node('contactID:'+c['id'], data=c)
			self.contactHashmap[c['id']] = c
		for b in self.biobanks:
			if re.search('BBNM', b['id']):
				log.info("Removing biobank " + b['id'])
				self.biobanks.remove(b)
				continue
			if self.directoryGraph.has_node(b['id']):
				raise Exception('DirectoryStructure', 'Conflicting ID found in directoryGraph: ' + b['id'])
			self.directoryGraph.add_node(b['id'], data=b)
			self.directoryCollectionsDAG.add_node(b['id'], data=b)
			if self.contactGraph.has_node(b['id']):
				raise Exception('DirectoryStructure', 'Conflicting ID found in contactGraph: ' + b['id'])
			self.contactGraph.add_node(b['id'], data=b)
			if self.networkGraph.has_node(b['id']):
				raise Exception('DirectoryStructure', 'Conflicting ID found in networkGraph: ' + b['id'])
			self.networkGraph.add_node(b['id'], data=b)
		for c in self.collections:
			if re.search('mtb', c['id']):
				log.debug("Processing " + c['id'])
			if re.search('BBNM', c['id']) or ('id' in c['biobank'] and re.search('BBNM', c['biobank']['id'])):
				log.info("Removing collection " + c['id'])
				self.collections.remove(c)
				continue
			if self.directoryGraph.has_node(c['id']):
				raise Exception('DirectoryStructure', 'Conflicting ID found: ' + c['id'])
			self.directoryGraph.add_node(c['id'], data=c)
			self.directoryCollectionsDAG.add_node(c['id'], data=c)
			if self.contactGraph.has_node(c['id']):
				raise Exception('DirectoryStructure', 'Conflicting ID found in contactGraph: ' + c['id'])
			self.contactGraph.add_node(c['id'], data=c)
			if self.networkGraph.has_node(c['id']):
				raise Exception('DirectoryStructure', 'Conflicting ID found in networkGraph: ' + c['id'])
			self.networkGraph.add_node(c['id'], data=c)
			if re.search('mtb', c['id']):
				log.debug("Finished processing " + c['id'])
		for n in self.networks:
			if self.contactGraph.has_node(n['id']):
				raise Exception('DirectoryStructure', 'Conflicting ID found in contactGraph: ' + n['id'])
			self.contactGraph.add_node(n['id'], data=n)
			if self.networkGraph.has_node(n['id']):
				raise Exception('DirectoryStructure', 'Conflicting ID found in networkGraph: ' + n['id'])
			self.networkGraph.add_node(n['id'], data=n)

		# check forward pointers from biobanks
		for b in self.biobanks:
			for c in b['collections']['items']:
				if not self.directoryGraph.has_node(c['id']):
					raise Exception('DirectoryStructure', 'Biobank ' + b['id'] + ' refers non-existent collection ID: ' + c['id'])
		# add biobank contact and network edges
		for b in self.biobanks:
			if 'contact' in b:
				self.contactGraph.add_edge(b['id'],'contactID:'+b['contact']['id'])
			if 'networks' in c:
				for n in c['networks']['items']:
					self.networkGraph.add_edge(b['id'], n['id'])

		# now we have all the collections created and checked duplicates, so we create edges
		for c in self.collections:
			if 'parent_collection' in c:
				# some child collection
				self.directoryGraph.add_edge(c['id'], c['parent_collection']['id'])
			else:
				# some of root collections of a biobank
				# we add both edges as we can't extract this information from the biobank level (it contains pointers to all the child collections)
				self.directoryGraph.add_edge(c['id'], c['biobank']['id'])
				self.directoryGraph.add_edge(c['biobank']['id'], c['id'])
				self.directoryCollectionsDAG.add_edge(c['biobank']['id'], c['id'])
			if 'sub_collections' in c:
				# some of root collections of a biobank
				for sb in c['sub_collections']['items']:
					self.directoryGraph.add_edge(c['id'], sb['id'])
					self.directoryCollectionsDAG.add_edge(c['id'], sb['id'])
			if 'contact' in c:
				self.contactGraph.add_edge(c['id'],'contactID:'+c['contact']['id'])
			if 'networks' in c:
				for n in c['networks']['items']:
					self.networkGraph.add_edge(c['id'], n['id'])

		# processing network edges
		for n in self.networks:
			if 'biobanks' in n:
				for b in n['biobanks']['items']:
					self.networkGraph.add_edge(n['id'], b['id'])
			if 'contacts' in n:
				for c in n['contacts']['items']:
					self.contactGraph.add_edge(n['id'], 'contactID:'+c['id'])
			if 'collections' in n:
				for c in n['collections']['items']:
					self.networkGraph.add_edge(n['id'], c['id'])

		# processing edges from contacts
		for c in self.contacts:
			if 'biobanks' in c:
				for b in c['biobanks']['items']:
					self.contactGraph.add_edge('contactID:'+c['id'], b['id'])
			if 'collections' in c:
				for coll in c['collections']['items']:
					self.contactGraph.add_edge('contactID:'+c['id'], coll['id'])
			if 'networks' in c:
				for n in c['networks']['items']:
					self.contactGraph.add_edge('contactID:'+c['id'], n['id'])

		# now make graphs immutable
		nx.freeze(self.directoryGraph)
		nx.freeze(self.directoryCollectionsDAG)
		nx.freeze(self.contactGraph)
		nx.freeze(self.networkGraph)

		log.info('Checks of directory data as graphs')
		# now we check if all the edges in the graph are in both directions
		for e in self.directoryGraph.edges():
			if not self.directoryGraph.has_edge(e[1],e[0]):
				raise Exception('DirectoryStructure', 'directoryGraph: Missing edge: ' + e[1] + ' to ' + e[0])
		for e in self.contactGraph.edges():
			if not self.contactGraph.has_edge(e[1],e[0]):
				raise Exception('DirectoryStructure', 'contactGraph: Missing edge: ' + e[1] + ' to ' + e[0])
		for e in self.networkGraph.edges():
			if not self.networkGraph.has_edge(e[1],e[0]):
				raise Exception('DirectoryStructure', 'networkGraph: Missing edge: ' + e[1] + ' to ' + e[0])
		# we check that DAG is indeed DAG :-)
		if not nx.algorithms.dag.is_directed_acyclic_graph(self.directoryCollectionsDAG):
			raise Exception('DirectoryStructure', 'Collection DAG is not DAG')

		log.info('Directory structure initialized')


	def getBiobanks(self):
		return self.biobanks

	def getBiobanksCount(self):
		return len(self.biobanks)

	def getBiobankNN(self, biobankID : str):
		# TODO: handle IARC!
		#data = nx.get_node_attributes(self.directoryGraph, 'data')
		#pp.pprint(data)
		#biobank = data[biobankID]
		biobank = self.directoryGraph.nodes[biobankID]['data']
		return biobank['country']['id']

	def getCollections(self):
		return self.collections

	def getCollectionsCount(self):
		return len(self.collections)

	def getCollectionBiobank(self, collectionID : str):
		collection = self.directoryGraph.nodes[collectionID]['data']
		return collection['biobank']['id']

	def getCollectionNN(self, collectionID):
		# TODO: handle IARC!
		return self.getBiobankNN(self.getCollectionBiobank(collectionID))

	# return the whole subgraph including the biobank itself
	def getGraphBiobankCollectionsFromBiobank(self, biobankID : str):
		return self.directoryCollectionsDAG.subgraph(nx.algorithms.dag.descendants(self.directoryCollectionsDAG, biobankID).union({biobankID}))

	# return the whole subgraph including some collection 
	def getGraphBiobankCollectionsFromCollection(self, collectionID : str):
		return self.directoryCollectionsDAG.subgraph(nx.algorithms.dag.ancestors(self.directoryCollectionsDAG, collectionID).union(nx.algorithms.dag.descendants(self.directoryCollectionsDAG, collectionID)).union({collectionID}))

	def getCollectionsDescendants(self, collectionID : str):
		return self.directoryCollectionsDAG.subgraph(nx.algorithms.dag.descendants(self.directoryCollectionsDAG, collectionID))

	def getContacts(self):
		return self.contacts

	def getContactNN(self, contactID : str):
		# TODO: handle IARC!
		return self.contactHashmap[contactID]['country']['id']

	def getNetworks(self):
		return self.networks

	def getNetworkNN(self, networkID : str):
		# TODO: handle IARC!
		network = self.networkGraph.nodes[networkID]['data']
		NN = ""
		if 'country' in network:
			NN = network['country']['id']
		elif 'contact' in network:
			NN = self.getContactNN(network['contact']['id'])
		else:
			raise Exception('DirectoryStructure', 'Unable to determine National Node affiliation of network ' + networkID)
		return NN

# Main code

dir = Directory()

biobanks = {}
for biobank in dir.getBiobanks():
	collections = dir.getGraphBiobankCollectionsFromBiobank(biobank['id'])
	biobanks[biobank['id']]['topLevelCollections'] = collections.successors(biobank['id'])
	biobanks[biobank['id']]['biobankOrderOfMagnitude'] = 0
	biobanks[biobank['id']]['biobankSizeExact'] = 0
	biobanks[biobank['id']]['biobankSizeEstimate'] = 0
	for collection in biobanks[biobank['id']]['topLevelCollections']:
		OoM = collection['order_of_magnitude']['id']
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
