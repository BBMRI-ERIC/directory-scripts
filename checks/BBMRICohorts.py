# vim:ts=8:sw=8:tw=0:noet

import re
import logging as log
import collections as python_collections

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning,DataCheckEntityType

BBMRICohortsNetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts'
BBMRICohortsDNANetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts_DNA'

class BBMRICohorts(IPlugin):

	def check(self, dir, args):
		warnings = []
		log.info("Running content checks on BBMRI Cohorts (BBMRICohorts)")

		for collection in dir.getCollections():
			biobankId = dir.getCollectionBiobankId(collection['id'])
			biobank = dir.getBiobankById(biobankId)
			biobank_capabilities = []
			if 'capabilities' in biobank:
				for c in biobank['capabilities']:
					biobank_capabilities.append(c['id'])
			biobank_networks = []
			if 'network' in biobank:
				for n in biobank['network']:
					biobank_networks.append(n['id'])
			collection_networks = []
			if 'network' in collection:
				for n in collection['network']:
					collection_networks.append(n['id'])

			OoM = collection['order_of_magnitude']['id']

			materials = []
			if 'materials' in collection:
				for m in collection['materials']:
					materials.append(m['id'])
			
			data_categories = []
			if 'data_categories' in collection:
				for c in collection['data_categories']:
					data_categories.append(c['id'])

			types = []
			if 'type' in collection:
				for t in collection['type']:
					types.append(t['id'])
                        
			diags = []
			diag_ranges = []

			for d in collection['diagnosis_available']:
				if re.search('-', d['id']):
					diag_ranges.append(d['id'])
				else:
					diags.append(d['id'])

			age_ranges = set()
			collAges = set()
			if 'age_range' in collection:
				for a in collection['age_range']:
					if re.search('-', a['id']):
						age_ranges.add(a['id'])
					else:
						collAges.add(a['id'])

			sex_ranges = set()
			collSex = set()
			for s in collection['sex']:
				if re.search('-', s['id']):
					sex_ranges.add(s['id'])
				else:
					collSex.add(s['id'])
					


			collectionFacts = []
			collFactsDiseases = set()
			collFactsAgeGroups = set()
			collFactsSexGroups = set()
			collFactsMaterialTypes =set() 
			collsFactsSamples = 0

			# Check presence of fact tables
			if collection['facts'] != []:
				if BBMRICohortsNetworkName in collection_networks or BBMRICohortsDNANetworkName in collection_networks:
					log.info(f"Hooooray, we have found BBMRI Cohorts collection with the fact table populated: {collection['id']}")
				if BBMRICohortsNetworkName in biobank_networks or BBMRICohortsDNANetworkName in biobank_networks:
					log.info(f"Hooooray, we have found BBMRI Cohorts biobank with a collection with the fact table populated: {collection['id']}")

				for fact in dir.getFacts():
					if fact['collection']['id'] == collection['id']:
						collectionFacts.append(fact) # We collect here all the facts for a given collection (maybe not needed)
						if 'disease' in fact:
							collFactsDiseases.add(fact['disease']['id']) # Collect all diagnoses from facts
							collFactsAgeGroups.add(fact['age_range']['id']) 
							collFactsSexGroups.add(fact['sex']['id'])
							collFactsMaterialTypes.add(fact['sample_type']['id'])
							collsFactsSamples += fact['number_of_samples']
						# TODO: add getting also age, sex and material groups - and use sets not arrays, it's not ordered


				# check that the fact table contains all the diagnoses described in the collection
				if collFactsDiseases != [] and python_collections.Counter(collFactsDiseases) != python_collections.Counter(diags):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Diagnoses of collection and facts table do not match"))
			
				# check that the fact table contains all the age ranges and biological sex that are described in the collection
				if collFactsAgeGroups != [] and python_collections.Counter(collFactsAgeGroups) != python_collections.Counter(collAges):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Age ranges of collection and facts table do not match"))
				if collFactsSexGroups != [] and python_collections.Counter(collFactsSexGroups) != python_collections.Counter(collSex):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Sex of collection and facts table do not match"))

				# TODO: check that the fact table contains all the material types that are described in the collection
				#	warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Material types of collection and facts table do not match"))

			if 'size' in collection:
				if not isinstance(collection['size'], int):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Collection size (number of samples) is not an integer"))
				# check that the total numbers of samples is matching total number of samples in the fact table (donor's are not aggregable)
				if collsFactsSamples != collection['size']:
						warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, f"Collection size (number of samples {collection['size']}) differs from total number of samples in facts table ({collsFactsSamples})"))
			else:
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Collection size (number of samples) not provided"))

			# TODO: check that if the DNA network, the fact table contains liquid materials from which DNA can be extracted
			if 'network' in collection:
				if BBMRICohortsDNANetworkName in collection_networks: 
					pass # TODO check materials and add those compatible with the network

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
				if network in biobank_networks and not network in collection_networks:
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, f"Biobank in BBMRI-Cohorts network {network} but has no collections in the same network network."))
			
		return warnings
