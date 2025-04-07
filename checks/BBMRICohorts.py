# vim:ts=8:sw=8:tw=0:noet

import re
import logging as log
import collections as py_collections

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning,DataCheckEntityType

BBMRICohortsNetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts'
BBMRICohortsDNANetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts_DNA'

def checkCollabBB(self, dir, collection : dict, biobank : dict, warningsList):

	def checkAttribute (feature : str, entity : dict, state : bool):
		if feature in entity:
			if entity[feature] == state:
				return True
		return False

	def formatAttribute (feature : str, entity : dict):
		if feature in entity:
			return f'{entity[feature]}'
		return f'not set'

	if checkAttribute('commercial_use', collection, True):
		return

	if checkAttribute('collaboration_commercial', biobank, True):
		# commercial collaboration must not be forbidden on the collection level
		if not checkAttribute('commercial_use', collection, False):
			return

	# If we got here, the previous checks failed
	warningsList.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, f"Collection and biobank are not available for commercial collaboration modes: collection[commercial_use] is {formatAttribute('commercial_use', collection)}, biobank[collaboration_commercial] is {formatAttribute('collaboration_commercial', biobank)}", "Check if this is true (that both are false): if so, remove the networks BBMRI Cohorts/BBMRI Cohorts DNA , otherwise correct the value of commercial availibility", dir.getCollectionContact(collection['id'])['email']))


class BBMRICohorts(IPlugin):

	def check(self, dir, args):
		warnings = []
		log.info("Running content checks on BBMRI Cohorts (BBMRICohorts)")

		for collection in dir.getCollections():

			collsFactsSamples = 0
			collsFactsDonors = 0

			biobankId = dir.getCollectionBiobankId(collection['id'])
			biobank = dir.getBiobankById(biobankId)
			
			biobank_networks = []
			if 'network' in biobank:
				for n in biobank['network']:
					biobank_networks.append(n['id'])
			
			collection_networks = []
			if 'network' in collection:
				for n in collection['network']:
					collection_networks.append(n['id'])
			
			if BBMRICohortsNetworkName in collection_networks or BBMRICohortsDNANetworkName in collection_networks:
				#OoM = collection['order_of_magnitude']['id']  # EMX2 OoM does not have ID, then:
				OoM = int(collection['order_of_magnitude'])
				
				data_categories = []
				if 'data_categories' in collection:
					for c in collection['data_categories']:
						#data_categories.append(c['id']) # EMX2 data_categories does not have ID, then:
						data_categories.append(c)

				types = []
				if 'type' in collection:
					for t in collection['type']:
						#types.append(t['id']) # EMX2 types does not have ID, then:
						types.append(t)

				# Check commercial use
				checkCollabBB(self, dir, collection, biobank, warnings)
				
				# Check presence of fact tables
				if 'facts' in collection.keys() and collection['facts'] != []: # TODO: if not, raise an error? # EMX2 change
					#if collection['facts'] != []:
					
					for fact in dir.getCollectionFacts(collection['id']):

						if 'number_of_samples' in fact:
							collsFactsSamples += fact['number_of_samples']
						if 'number_of_donors' in fact:
							collsFactsDonors += fact['number_of_donors']
					
					# TODO: should these check be generic and not just for BBMRI Cohorts?
					if collsFactsSamples > 0 or collsFactsDonors > 0:
						if BBMRICohortsNetworkName in collection_networks or BBMRICohortsDNANetworkName in collection_networks:
							log.info(f"Hooooray, we have found BBMRI Cohorts collection with the fact table populated: {collection['id']}")
						if BBMRICohortsNetworkName in biobank_networks or BBMRICohortsDNANetworkName in biobank_networks:
							log.info(f"Hooooray, we have found BBMRI Cohorts biobank with a collection with the fact table populated: {collection['id']}")

				else:
					if 'network' in collection and (BBMRICohortsNetworkName in collection_networks or BBMRICohortsDNANetworkName in collection_networks):
						BBMRICohortsList = set()
						if (BBMRICohortsNetworkName in collection_networks):
							BBMRICohortsList.add(BBMRICohortsNetworkName)
						if (BBMRICohortsDNANetworkName in collection_networks):
							BBMRICohortsList.add(BBMRICohortsDNANetworkName)
						warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, f"Collection in BBMRI cohorts {BBMRICohortsList} but the fact table is missing", "Prepare the facts table for the collection and upload", dir.getCollectionContact(collection['id'])['email']))
				
		for biobank in dir.getBiobanks():
			biobank_networks = []
			if 'network' in biobank:
				for n in biobank['network']:
					biobank_networks.append(n['id'])

			collections = dir.getGraphBiobankCollectionsFromBiobank(biobank['id'])
			collection_networks = set()  # set is sufficient since we only collect all the networks in which any of the collections of a biobank are participating
			for collection in collections:
				if 'network' in collection:
					for n in collection['network']:
						collection_networks.add(n['id'])

			for network in [BBMRICohortsNetworkName, BBMRICohortsDNANetworkName]:
				# if network in biobank_networks and not network in collection_networks:
					# warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, f"Biobank in BBMRI-Cohorts network {network} but has no collections in the same network network."))
				 if network in biobank_networks:
					 warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, f"Biobanks are not expected to be part of BBMRI-Cohorts networks, only specific collections must be included. Biobank participates in BBMRI-Cohorts network: {network}.", "Remove BBMRI Cohorts/BBMRI Cohorts DNA network from the Biobank entry, check which collections shall be flagged with the networks BBMRI Cohorts / BBMRI Cohorts DNA and flag them", dir.getCollectionContact(biobank['id'])['email']))
		return warnings