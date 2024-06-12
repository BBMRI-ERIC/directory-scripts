# vim:ts=8:sw=8:tw=0:noet

import re
import logging as log
import collections as py_collections

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning,DataCheckEntityType

BBMRICohortsNetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts'
BBMRICohortsDNANetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts_DNA'


def compareFactsColl(self, dir, factsList, collList, collection, errorDescription, warningsList): # TO improve
	if factsList != [] and py_collections.Counter(factsList) != py_collections.Counter(collList):
		warningsList.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, errorDescription + f" - collection information: {collList} - fact information: {factsList}"))

class BBMRICohorts(IPlugin):

	def check(self, dir, args):
		warnings = []
		log.info("Running content checks on BBMRI Cohorts (BBMRICohorts)")

		for collection in dir.getCollections():
			collectionFacts = []
			collFactsDiseases = set()
			collFactsAgeGroups = set()
			collFactsSexGroups = set()
			collFactsMaterialTypes =set() 
			collsFactsSamples = 0

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

			if BBMRICohortsNetworkName in collection_networks or BBMRICohortsDNANetworkName in collection_networks:
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

				collSex = set()
				for s in collection['sex']:
						collSex.add(s['id'])

				# Check presence of fact tables
				if collection['facts'] != []:
					for fact in dir.getFacts():
						if fact['collection']['id'] == collection['id']:
							collectionFacts.append(fact) # We collect here all the facts for a given collection (maybe not needed)
							if 'disease' in fact:
								collFactsDiseases.add(fact['disease']['id']) # Collect all diagnoses from facts
							if 'age_range' in fact:
								collFactsAgeGroups.add(fact['age_range']['id'])
							if 'sex' in fact:
								collFactsSexGroups.add(fact['sex']['id'])
							if 'sample_type' in fact:
								collFactsMaterialTypes.add(fact['sample_type']['id'])
							if 'number_of_samples' in fact:
								collsFactsSamples += fact['number_of_samples']
					if collsFactsSamples > 0:
						if BBMRICohortsNetworkName in collection_networks or BBMRICohortsDNANetworkName in collection_networks:
							log.info(f"Hooooray, we have found BBMRI Cohorts collection with the fact table populated: {collection['id']}")
						if BBMRICohortsNetworkName in biobank_networks or BBMRICohortsDNANetworkName in biobank_networks:
							log.info(f"Hooooray, we have found BBMRI Cohorts biobank with a collection with the fact table populated: {collection['id']}")

						# check that the fact table contains all the diagnoses described in the collection
						compareFactsColl(self, dir, collFactsDiseases, diags, collection, "Diagnoses of collection and facts table do not match", warnings)
					
						# check that the fact table contains all the age ranges and biological sex that are described in the collection
						compareFactsColl(self, dir, collFactsAgeGroups, collAges, collection, "Age ranges of collection and facts table do not match", warnings)
						compareFactsColl(self, dir, collFactsSexGroups, collSex, collection, "Sex of collection and facts table do not match", warnings)

						# check that the fact table contains all the material types that are described in the collection
						compareFactsColl(self, dir, collFactsMaterialTypes, materials, collection, "Material types of collection and facts table do not match", warnings)


						if 'size' in collection:
							if not isinstance(collection['size'], int):
								warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Collection size attribute (number of samples) is not an integer"))
							# check that the total numbers of samples is matching total number of samples in the fact table (donor's are not aggregable)
							if collsFactsSamples != collection['size']:
									warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, f"Value of the collection size attribute (number of samples - {collection['size']}) differs from total number of samples in facts table ({collsFactsSamples})"))
						else:
							warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Collection size attribute (number of samples) not provided"))

						# check that if the DNA network, the fact table contains liquid materials from which DNA can be extracted (DNA, Peripheral blood cells, Whole Blood)
						if 'network' in collection:
							if BBMRICohortsDNANetworkName in collection_networks:
								requiredMaterialTypes = ['DNA','WHOLE_BLOOD','PERIPHERAL_BLOOD_CELLS']
								if not any(mat in collFactsMaterialTypes for mat in requiredMaterialTypes):
									warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, f"Collection in {BBMRICohortsDNANetworkName} but the fact table does not contain any of the expected material types: {','.join(requiredMaterialTypes)})"))

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
