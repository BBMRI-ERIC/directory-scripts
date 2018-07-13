#!/usr/bin/python3

import pprint
import re
from enum import Enum

import molgenis
import networkx as nx

from yapsy.PluginManager import PluginManager

from customwarnings import WarningLevel,Warning

pp = pprint.PrettyPrinter(indent=4)

class WarningsContainer:

	def __init__(self):
		# TODO
		self._NNtoEmails = {
				'AT' : 'Philipp.Ueberbacher@aau.at, heimo.mueller@medunigraz.at',
				'BE' : 'TODO',
				'BG' : 'TODO',
				'CH' : 'TODO',
				'CY' : 'TODO',
				'CZ' : 'dudova@ics.muni.cz, hopet@ics.muni.cz',
				'DE' : 'michael.hummel@charite.de',
				'EE' : 'TODO',
				'FI' : 'TODO',
				'FR' : 'TODO',
				'GR' : 'TODO',
				'IT' : 'TODO',
				'LV' : 'TODO',
				'MT' : 'TODO',
				'NL' : 'TODO',
				'NO' : 'TODO',
				'PL' : 'TODO',
				'SE' : 'TODO',
				'TR' : 'TODO',
				'UK' : 'TODO',
				'IARC' : 'TODO',
				}
		self.__warnings = {}

	def newWarning(self, warning : Warning):
		warning_key = ""
		if warning.recipients != "":
			warning_key = recipients + ", "
		warning_key += self._NNtoEmails[warning.NN]
		if warning_key in self.__warnings:
			self.__warnings[warning_key].append(warning)
		else:
			self.__warnings[warning_key] = [warning]

	def dumpWarnings(self):
		for wk in self.__warnings:
			print(wk + ":")
			for w in self.__warnings[wk]:
				w.dump()
			print("")


# Definition of Directory structure

class Directory:

	def __init__(self):
		session = molgenis.Session("https://directory.bbmri-eric.eu/api/")
		self.biobanks = session.get("eu_bbmri_eric_biobanks", num=0, expand=['contact','collections','country'])
		self.collections = session.get("eu_bbmri_eric_collections", num=0, expand=['biobank','contact','network','parent_collection','sub_collections'])
		self.contacts = session.get("eu_bbmri_eric_persons", num=0)
		self.networks = session.get("eu_bbmri_eric_networks", num=0, expand=['contact'])

		self.directoryGraph = nx.DiGraph()
		self.directoryCollectionsDAG = nx.DiGraph()
		for b in self.biobanks:
			if self.directoryGraph.has_node(b['id']):
				raise Exception('DirectoryStructure', 'Conflicting ID found: ' + b['id'])
			self.directoryGraph.add_node(b['id'], data=b)
			self.directoryCollectionsDAG.add_node(b['id'], data=b)
		for c in self.collections:
			if self.directoryGraph.has_node(c['id']):
				raise Exception('DirectoryStructure', 'Conflicting ID found: ' + c['id'])
			self.directoryGraph.add_node(c['id'], data=c)
			self.directoryCollectionsDAG.add_node(c['id'], data=c)
		# check forward pointers from biobanks
		for b in self.biobanks:
			for c in b['collections']['items']:
				if not self.directoryGraph.has_node(c['id']):
					raise Exception('DirectoryStructure', 'Biobank refers non-existent collection ID: ' + c['id'])
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
		# now make graphs immutable
		nx.freeze(self.directoryGraph)
		nx.freeze(self.directoryCollectionsDAG)

		# now we check if all the edges in the graph are in both directions
		for e in self.directoryGraph.edges():
			if not self.directoryGraph.has_edge(e[1],e[0]):
				raise Exception('DirectoryStructure', 'Missing edge: ' + e[1] + ' to ' + e[0])
		# we check that DAG is indeed DAG :-)
		if not nx.algorithms.dag.is_directed_acyclic_graph(self.directoryCollectionsDAG):
			raise Exception('DirectoryStructure', 'Collection DAG is not DAG')



	def getBiobanks(self):
		return self.biobanks

	def getBiobanksCount(self):
		return len(self.biobanks)

	def getBiobankNN(self, biobankID : str):
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
		return self.getBiobankNN(self.getCollectionBiobank(collectionID))

	# return the whole subgraph including the biobank itself
	def getGraphBiobankCollectionsFromBiobank(self, biobankID : str):
		return self.directoryCollectionsDAG.subgraph(nx.algorithms.dag.descendants(self.directoryCollectionsDAG, biobankID).union({biobankID}))

	# return the whole subgraph including some collection 
	def getGraphBiobankCollectionsFromCollection(self, collectionID : str):
		return self.directoryCollectionsDAG.subgraph(nx.algorithms.dag.ancestors(self.directoryCollectionsDAG, collectionID).union(nx.algorithms.dag.descendants(self.directoryCollectionsDAG, collectionID)).union({collectionID}))

# Main code

simplePluginManager = PluginManager()
simplePluginManager.setPluginPlaces(["checks"])
simplePluginManager.collectPlugins()

dir = Directory()
warningContainer = WarningsContainer()

print('Total biobanks: ' + str(dir.getBiobanksCount()))
print('Total collections: ' + str(dir.getCollectionsCount()))

#print('MMCI collections: ')
#for biobank in dir.getBiobanks():
#	if(re.search('MMCI', biobank['id'])):
#		pp.pprint(biobank)
#		collections = dir.getGraphBiobankCollections(biobank['id'])
#		for e in collections.edges:
#			print("   "+str(e[0])+" -> "+str(e[1]))

for pluginInfo in simplePluginManager.getAllPlugins():
   simplePluginManager.activatePluginByName(pluginInfo.name)
   warnings = pluginInfo.plugin_object.check(dir)
   if len(warnings) > 0:
	   for w in warnings:
		   warningContainer.newWarning(w)

warningContainer.dumpWarnings()
