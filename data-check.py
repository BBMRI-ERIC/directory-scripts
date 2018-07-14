#!/usr/bin/python3

import pprint
import re
from enum import Enum

import molgenis
import networkx as nx

from yapsy.PluginManager import PluginManager

from customwarnings import DataCheckWarningLevel,DataCheckWarning

disabledChecks = {
#		"SemiemptyFields" : {"bbmri-eric:ID:NO_HUNT", "bbmri-eric:ID:NO_Janus"}
		}

pp = pprint.PrettyPrinter(indent=4)

class WarningsContainer:

	def __init__(self):
		# TODO
		self._NNtoEmails = {
				'AT' : 'Philipp.Ueberbacher@aau.at, heimo.mueller@medunigraz.at',
				'BE' : 'annelies.debucquoy@kankerregister.org',
				'BG' : 'TODO',
				'CH' : 'christine.currat@chuv.ch',
				'CY' : 'Deltas@ucy.ac.cy',
				'CZ' : 'dudova@ics.muni.cz, hopet@ics.muni.cz',
				'DE' : 'michael.hummel@charite.de, caecilia.engels@charite.de',
				'EE' : 'kristjan.metsalu@ut.ee',
				'FI' : 'niina.eklund@thl.fi',
				'FR' : 'soraya.aakki@inserm.fr, michael.hisbergues@inserm.fr',
				'GR' : 's.kolyva@pasteur.gr, thanos@bioacademy.gr',
				'IT' : 'marialuisa.lavitrano@unimib.it, luciano.milanesi@itb.cnr.it, barbara.parodi@hsanmartino.it, elena.bravo@iss.it',
				'LV' : 'linda.zaharenko@biomed.lu.lv',
				'MT' : 'joanna.vella@um.edu.mt, alex.felice@um.edu.mt',
				'NL' : 'd.van.enckevort@rug.nl, david.van.enckevort@umcg.nl',
				'NO' : 'vegard.marschhauser@ntnu.no, kristian.hveem@ntnu.no',
				'PL' : 'Lukasz.Kozera@eitplus.pl, dominik.strapagiel@biol.uni.lodz.pl, blazej.marciniak@biol.uni.lodz.pl',
				'SE' : 'tobias.sjoblom@igp.uu.se',
				'TR' : 'TODO',
				'UK' : 'philip.quinlan@nottingham.ac.uk, jurgen.mitsch@nottingham.ac.uk',
				'IARC' : 'TODO',
				}
		self.__warnings = {}

	def newWarning(self, warning : DataCheckWarning):
		warning_key = ""
		if warning.recipients != "":
			warning_key = recipients + ", "
		warning_key += self._NNtoEmails[warning.NN]
		if warning_key in self.__warnings:
			self.__warnings[warning_key].append(warning)
		else:
			self.__warnings[warning_key] = [warning]

	def dumpWarnings(self):
		for wk in sorted(self.__warnings):
			print(wk + ":")
			for w in sorted(self.__warnings[wk], key=lambda x: x.directoryEntityID + ":" + str(x.level.value)):
				if not (w.dataCheckID in disabledChecks and w.directoryEntityID in disabledChecks[w.dataCheckID]):
					w.dump()
			print("")


# Definition of Directory structure

class Directory:

	def __init__(self):
		session = molgenis.Session("https://directory.bbmri-eric.eu/api/")
		self.biobanks = session.get("eu_bbmri_eric_biobanks", num=0, expand=['contact','collections','country'])
		self.collections = session.get("eu_bbmri_eric_collections", num=0, expand=['biobank','contact','network','parent_collection','sub_collections','type','materials','order_of_magnitude','data_categories', 'diagnosis_available', 'imaging_modality', 'image_dataset_type'])
		self.contacts = session.get("eu_bbmri_eric_persons", num=0, expand=['biobanks','collections','networks','country'])
		self.networks = session.get("eu_bbmri_eric_networks", num=0, expand=['contact','country'])
		self.contactHashmap = {}

		# Graph containing only biobanks and collections
		self.directoryGraph = nx.DiGraph()
		# DAG containing only biobanks and collections
		self.directoryCollectionsDAG = nx.DiGraph()
		# Weighted graph linking contacts to biobanks/collections/networks
		self.contactGraph = nx.DiGraph()
		# Graph linking networks to biobanks/collections
		self.networkGraph = nx.DiGraph()
		for c in self.contacts:
			if self.contactGraph.has_node(c['id']):
				raise Exception('DirectoryStructure', 'Conflicting ID found in contactGraph: ' + c['id'])
			# XXX temporary hack -- adding contactID prefix
			#self.contactGraph.add_node(c['id'], data=c)
			self.contactGraph.add_node('contactID:'+c['id'], data=c)
			self.contactHashmap[c['id']] = c
		for b in self.biobanks:
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
					raise Exception('DirectoryStructure', 'Biobank refers non-existent collection ID: ' + c['id'])
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

simplePluginManager = PluginManager()
simplePluginManager.setPluginPlaces(["checks"])
simplePluginManager.collectPlugins()

dir = Directory()
warningContainer = WarningsContainer()

print('Total biobanks: ' + str(dir.getBiobanksCount()))
print('Total collections: ' + str(dir.getCollectionsCount()))

print('MMCI collections: ')
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
   simplePluginManager.activatePluginByName(pluginInfo.name)
   warnings = pluginInfo.plugin_object.check(dir)
   if len(warnings) > 0:
	   for w in warnings:
		   warningContainer.newWarning(w)

warningContainer.dumpWarnings()
