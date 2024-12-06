# vim:ts=8:sw=8:tw=0:noet

import re
import logging as log
import collections as py_collections

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning,DataCheckEntityType

BBMRICohortsNetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts'
BBMRICohortsDNANetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts_DNA'


def compareFactsColl(self, dir, factsList, collList, collection, errorDescription, actionDescription, warningsList): # TO improve
	if factsList != [] and py_collections.Counter(factsList) != py_collections.Counter(collList):
		warningsList.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, errorDescription + f" - collection information: {sorted(collList)} - fact information: {sorted(factsList)}", actionDescription, collection['contact']['email']))

def compareAge(self, dir, factAges : set, factsAgeUnits : set, collection, warningsList):
	# NOTE assuming that collection age units uppercase and singular match with facts age units lowercase and plural (at least with years, YEAR, months, MONTH works)
	collUnits = set()
	collUnitsAdapt = set()
	# gather coll age units
	for collAUnit in collection['age_unit']:
		collUnits.add(collAUnit['id'])
		{i.lower() + 's' for i in collUnits}
		collUnitsAdapt = {i.lower() + 's' for i in collUnits}
	if sorted(collUnitsAdapt) != sorted(factsAgeUnits):
		warningsList.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, f"Age unit ID of the collection is {collection['age_unit']} while the age unit in the fact table is {factsAgeUnits}", "Check age unit information of the collection description with age units from the facts table and correct as necessary", collection['contact']['email']))
	else:
		# Comparison of numbers
		# TODO, NOTE: not sure what happens when there is more than 1 age unit i.e.: month and year
		minFactAge = int(min(sorted(factAges)))
		maxFactAge = int(max(sorted(factAges)))
		# check if any of age groups is outside of min-max range of the collection:
		try:
			if (minFactAge < collection['age_low']) or (maxFactAge > collection['age_high']):
				warningsList.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, f"Fact table age outside collection age_high age_low range", "Check age range of the collection description with ages from the facts table and correct as necessary", collection['contact']['email'])) #TODO: explain it better
			if (collection['age_low'] < minFactAge) or (collection['age_high'] > maxFactAge):
				warningsList.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, f"Collection ages outside facts age range", "Check age information of the collection description with age ranges from the facts table and correct as necessary", collection['contact']['email'])) #TODO: explain it better
		except KeyError as e:
			log.info(f"Incomplete age range information for {collection['id']}: " + str(e) + " missing")

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
	warningsList.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, f"Collection and biobank are not available for commercial collaboration modes: collection[commercial_use] is {formatAttribute('commercial_use', collection)}, biobank[collaboration_commercial] is {formatAttribute('collaboration_commercial', biobank)}", "Check if this is true (that both are false): if so, remove the networks BBMRI Cohorts/BBMRI Cohorts DNA , otherwise correct the value of commercial availibility", collection['contact']['email']))


class BBMRICohorts(IPlugin):

	def check(self, dir, args):
		warnings = []
		log.info("Running content checks on BBMRI Cohorts (BBMRICohorts)")

		for collection in dir.getCollections():
			collectionFacts = []
			collFactsDiseases = set()
			#collFactsAgeGroups = set()
			collFactsSexGroups = set()
			collFactsMaterialTypes =set() 
			collsFactsSamples = 0
			ages = set()
			ageUnits = set()

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

				collSex = set()
				for s in collection['sex']:
						collSex.add(s['id'])

				# Check commercial use
				checkCollabBB(self, dir, collection, biobank, warnings)

				# Check presence of fact tables
				if collection['facts'] != []:
					for fact in dir.getFacts():
						if fact['collection']['id'] == collection['id']:
							collectionFacts.append(fact) # We collect here all the facts for a given collection (maybe not needed)
							if 'disease' in fact:
								collFactsDiseases.add(fact['disease']['id']) # Collect all diagnoses from facts
							if 'age_range' in fact:
								ages.update(re.findall(r'\d+', fact['age_range']['label']))
								ageUnits.update(re.findall(r'\((?:\d+-\d+\s)?(.*?)\)', fact['age_range']['label']))
								# Deal with >80
								if '>80 years' in ageUnits:
									# Remove the old value
									ageUnits.remove('>80 years')
									# Add the new value
									ageUnits.add('years')
								#collFactsAgeGroups.add(fact['age_range']['id'])
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
						compareFactsColl(self, dir, collFactsDiseases, diags, collection, "Diagnoses of collection and facts table do not match", "Check diagnosis entries of the collection description with diagnoses from the facts table and correct as necessary", warnings)
					
						# check that the fact table contains all the age ranges and biological sex that are described in the collection
						# TODO: age range check needs to be reimplemented - it can't be done as a comparison of arrays as the collection-level information is provided as a min/max age
						# NOTE: half way implemented. Missing: deal with negative ages and Unknown (we do not have such cases for now, but will be needed)
						compareAge(self, dir, ages, ageUnits, collection, warnings)

						#compareFactsColl(self, dir, collFactsAgeGroups, collAges, collection, "Age ranges of collection and facts table do not match", warnings)
						compareFactsColl(self, dir, collFactsSexGroups, collSex, collection, "Sex of collection and facts table do not match", "Check sex information of the collection description with sex information from the facts table and correct as necessary", warnings)

						# check that the fact table contains all the material types that are described in the collection
						compareFactsColl(self, dir, collFactsMaterialTypes, materials, collection, "Material types of collection and facts table do not match", "Check material types of the collection description with material types from the facts table and correct as necessary", warnings)


						if 'size' in collection:
							if not isinstance(collection['size'], int):
								warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Collection size attribute (number of samples) is not an integer", collection['contact']['email']))
							# check that the total numbers of samples is matching total number of samples in the fact table (donor's are not aggregable)
							if collsFactsSamples < collection['size']:
									warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, f"Value of the collection size attribute (number of samples - {collection['size']}) is greater than the total number of samples in facts table ({collsFactsSamples}) - maybe false positive due to anonymization", "Check size information of the collection description with the cummulated number from the facts table and correct as necessary", collection['contact']['email']))
							elif collsFactsSamples > collection['size']:
									warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, f"Value of the collection size attribute (number of samples - {collection['size']}) is smaller than the total number of samples in facts table ({collsFactsSamples})", "Check size information of the collection description with the cummulated number from the facts table and correct as necessary", collection['contact']['email']))
						else:
							warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, "Collection size attribute (number of samples) not provided", "Add size attribute to the collection", collection['contact']['email']))

						# check that if the DNA network, the fact table contains liquid materials from which DNA can be extracted (DNA, Peripheral blood cells, Whole Blood)
						if 'network' in collection:
							if BBMRICohortsDNANetworkName in collection_networks:
								requiredMaterialTypes = ['DNA','WHOLE_BLOOD','PERIPHERAL_BLOOD_CELLS','BUFFY_COAT','CDNA','PLASMA','SERUM']
								if not any(mat in collFactsMaterialTypes for mat in requiredMaterialTypes):
									warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, f"Collection in {BBMRICohortsDNANetworkName} but the fact table does not contain any of the expected material types: {','.join(requiredMaterialTypes)})", collection['contact']['email']))

								if 'NAV' in collFactsMaterialTypes:
									warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, f"Collection in {BBMRICohortsDNANetworkName} but the fact table does specified the NAV (not-available) material type", collection['contact']['email']))

				else:
					if 'network' in collection and (BBMRICohortsNetworkName in collection_networks or BBMRICohortsDNANetworkName in collection_networks):
						warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, f"Collection in BBMRI cohorts but the fact table is missing", "Prepare the facts table for the collection and upload", collection['contact']['email']))

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
					 warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, f"Biobanks are not expected to be part of BBMRI-Cohorts networks, only specific collections must be included. Biobank participates in BBMRI-Cohorts network: {network}.", "Remove BBMRI Cohorts/BBMRI Cohorts DNA network from the Biobank entry, check which collections shall be flagged with the networks BBMRI Cohorts / BBMRI Cohorts DNA and flag them", biobank['contact']['email']))
			
		return warnings
