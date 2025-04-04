# vim:ts=8:sw=8:tw=0:noet

import re
import logging as log
import collections as py_collections
from directory import Directory

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning,DataCheckEntityType

BBMRICohortsNetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts'
BBMRICohortsDNANetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts_DNA'


def compareFactsColl(self, dir, factsList, collList, collection, errorDescription, actionDescription, warningsList): # TO improve
	if factsList != [] and py_collections.Counter(factsList) != py_collections.Counter(collList):
		warningsList.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, errorDescription + f" - collection information: {sorted(collList)} - fact information: {sorted(factsList)}", actionDescription, dir.getCollectionContact(collection['id'])['email']))

def compareAge(self, dir, factAges : set, factsAgeUnits : set, collection, warningsList):
	# NOTE assuming that collection age units uppercase and singular match with facts age units lowercase and plural (at least with years, YEAR, months, MONTH works)
	collUnitsAdapt = collection['age_unit'].lower() + 's'
	if collUnitsAdapt != str((',').join(sorted(factsAgeUnits))):
		warningsList.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, f"Age unit ID of the collection is {collection['age_unit']} while the age unit in the fact table is {factsAgeUnits}", "Check age unit information of the collection description with age units from the facts table and correct as necessary", dir.getCollectionContact(collection['id'])['email']))
	else:
		# Comparison of numbers
		# TODO, NOTE: not sure what happens when there is more than 1 age unit i.e.: month and year
		minFactAge = int(min(sorted(factAges)))
		maxFactAge = int(max(sorted(factAges)))
		# check if any of age groups is outside of min-max range of the collection:
		try:
			if (minFactAge < collection['age_low']) or (maxFactAge > collection['age_high']):
				warningsList.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, f"Fact table age outside collection age_high age_low range", "Check age range of the collection description with ages from the facts table and correct as necessary", dir.getCollectionContact(collection['id'])['email'])) #TODO: explain it better
			if (collection['age_low'] < minFactAge) or (collection['age_high'] > maxFactAge):
				warningsList.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, f"Collection ages outside facts age range", "Check age information of the collection description with age ranges from the facts table and correct as necessary", dir.getCollectionContact(collection['id'])['email'])) #TODO: explain it better
		except KeyError as e:
			log.info(f"Incomplete age range information for {collection['id']}: " + str(e) + " missing")


class FactTables(IPlugin):

	def check(self, dir, args):
		warnings = []
		log.info("Running content checks on facts tables")

		for collection in dir.getCollections():
			collectionFacts = []
			collFactsDiseases = set()
			#collFactsAgeGroups = set()
			collFactsSexGroups = set()
			collFactsMaterialTypes =set() 
			collsFactsSamples = 0
			collsFactsDonors = 0

			ages = set()
			ageUnits = set()

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

			materials = []
			if 'materials' in collection:
				for m in collection['materials']:
					#materials.append(m['id']) # EMX2 materials does not have ID, then:
					materials.append(m)
	
			diags = []
			diag_ranges = []
			if 'diagnosis_available'in collection.keys(): #TODO: if not, raise an error ?
				for d in collection['diagnosis_available']:
					if re.search('-', d['name']): # EMX2 collection['diagnosis_available'] has name but not id (this applies to all times we call d in this loop)
						diag_ranges.append(d['name'])
					else:
						diags.append(d['name'])

			# TODO: Raise an error if sex not present?
			collSex = set(Directory.getListOfEntityAttributes(collection, 'sex'))

			#132 - 252
			# Check presence of fact tables
			if 'facts' in collection.keys() and collection['facts'] != []: # TODO: if not, raise an error? # EMX2 change
				#if collection['facts'] != []:
				for fact in dir.getCollectionFacts(collection['id']):
					collectionFacts.append(fact) # We collect here all the facts for a given collection (maybe not needed)
					if 'disease' in fact:
						collFactsDiseases.add(fact['disease']['name']) # Collect all diagnoses from facts
					if 'age_range' in fact:
						ages.update(re.findall(r'\d+', fact['age_range']))
						ageUnits.update(re.findall(r'\((?:\d+-\d+\s)?(.*?)\)', fact['age_range']))
						# Deal with >80
						if '>80 years' in ageUnits:
							# Remove the old value
							ageUnits.remove('>80 years')
							# Add the new value
							ageUnits.add('years')
						#collFactsAgeGroups.add(fact['age_range']['id'])
					if 'sex' in fact:
						collFactsSexGroups.add(fact['sex'])
					if 'sample_type' in fact:
						collFactsMaterialTypes.add(fact['sample_type'])
					if 'number_of_samples' in fact:
						collsFactsSamples += fact['number_of_samples']
					if 'number_of_donors' in fact:
						collsFactsDonors += fact['number_of_donors']

				# TODO: should these check be generic and not just for BBMRI Cohorts?
				if collsFactsSamples > 0 or collsFactsDonors > 0:
					log.info(f"Hooooray, we have found BBMRI fact table populated: {collection['id']}")

					# TODO: check this only for human collections?
					if collsFactsDonors == 0:
						warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, f"fact table information has 0 donors/patients"))
					else:
						kAnonymityViolatingList = []
						kAnonymityLimit = 5
						for f in dir.getCollectionFacts(collection['id']):
							if 'number_of_donors' in f and f['number_of_donors'] > 0 and f['number_of_donors'] < kAnonymityLimit:
								kAnonymityViolatingList.append([f['id'], f"{f['number_of_donors']} donor(s)"])
						if kAnonymityViolatingList:
							warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, f"the {len(kAnonymityViolatingList)} records of fact table violates {kAnonymityLimit}-anonymity: {kAnonymityViolatingList}"))

					# check that the fact table contains all the diagnoses described in the collection
					compareFactsColl(self, dir, collFactsDiseases, diags, collection, "Diagnoses of collection and facts table do not match", "Check diagnosis entries of the collection description with diagnoses from the facts table and correct as necessary", warnings)
				
					# check that the fact table contains all the age ranges and biological sex that are described in the collection
					# TODO: age range check needs to be reimplemented - it can't be done as a comparison of arrays as the collection-level information is provided as a min/max age
					# NOTE: half way implemented. Missing: deal with negative ages and Unknown (we do not have such cases for now, but will be needed)
					if 'age_unit' in collection.keys() and ageUnits: # TODO: if not, raise a warning?
						compareAge(self, dir, ages, ageUnits, collection, warnings)

					#compareFactsColl(self, dir, collFactsAgeGroups, collAges, collection, "Age ranges of collection and facts table do not match", warnings)
					compareFactsColl(self, dir, collFactsSexGroups, collSex, collection, "Sex of collection and facts table do not match", "Check sex information of the collection description with sex information from the facts table and correct as necessary", warnings)

					# check that the fact table contains all the material types that are described in the collection
					compareFactsColl(self, dir, collFactsMaterialTypes, materials, collection, "Material types of collection and facts table do not match", "Check material types of the collection description with material types from the facts table and correct as necessary", warnings)

					# TODO: check presence of 0-order and 1-order aggregates (i.e., all stars and all-but-one stars records)
					collectionFacts = dir.getCollectionFacts(collection['id'])
					if collectionFacts:
						fact_keys = ['sex', 'age_range', 'sample_type', 'disease']
						# note that the fact table contains dicts as values with ontological description of the value, hence only selecting id attribute from the dict
						#fact_values = { key: list(set(f.get(key).get('id') for f in collectionFacts if f.get(key) is not None)) for key in fact_keys } # no ids in EMX2, either nothing or 'name', depend on the key then:
						fact_values = { key: list(set(f.get(key).get('name') if key == 'disease' else f.get(key) for f in collectionFacts if f.get(key) is not None)) for key in fact_keys }
						# this is a structure for debugging in case we need to see the structure of the dict
						#fact_values = { key: set(frozenset(f.get(key).items()) if isinstance(f.get(key), dict) else f.get(key)
						#				            for f in collectionFacts if f.get(key) is not None
						#					        ) for key in fact_keys }
						#log.info(f'fact_values: {fact_values}')
						aggregates = dict(py_collections.Counter(
								[ sum(1 for key in fact_keys if f.get(key) == '*') for f in collectionFacts ]
								))
						aggregates = { k: 0 if k not in aggregates else aggregates[k] for k in range(0,len(fact_keys)+1)  }
						#log.info(f'aggregates: {aggregates}')
						# This is a basic check for all-aggregated value in the fact table - there is only one.
						if not 4 in aggregates or aggregates[4] != 1:
							warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, f"missing all-star aggregate: {aggregates[4]}"))
						# This is a basic check that there is at least one row for aggregates[3]. It could be ommitted and have only the more detailed checks below, which start to be applied once the user introduces their first aggregate[3] row. 
						# TODO: What is better from UX perspective - keep or remove this simple one?
						if not 3 in aggregates or aggregates[3] < 1:
							warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, f"missing all-but-one-star aggregate: {aggregates[3]}"))
						else:
							# This is more advanced check: for all the values that are present in the table (and are not suppressed by the k-anonymity), there should be also corresponding line in the aggregates[3]. However, it does not hold vice versa, due to k-anonymity suppression, there can be other lines in aggregates[3], which are not visible in the fully decomposed lines due to the k-anonymity caused suppression.
							# TODO: this needs to be tested once the fact table checks are applied to all the fact tables and not only the ones which are in the cohorts!! (CRC-Cohort contains this star data)
							for fk in fact_values:
								for v in fact_values[fk]:
									#rows = [ f for f in collectionFacts if f.get(fk) is not None and f.get(fk).get('id') == v and (sum(1 for key in fact_keys if f.get(key) == '*')) == 3] # In EMX2 there are no ids, then:
									rows = [ f for f in collectionFacts if f.get(fk) is not None and f.get(fk) == v and (sum(1 for key in fact_keys if f.get(key) == '*')) == 3]

									if rows:
										log.info(f'3-star rows found for {fk} value {v}: {rows}')
									else:
										warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, f"missing all-but-one-star aggregate for {fk} value {v}: {aggregates[3]}"))


					if 'size' in collection:
						if not isinstance(collection['size'], int):
							warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Collection size attribute (number of samples) is not an integer", dir.getCollectionContact(collection['id'])['email']))
						# check that the total numbers of samples is matching total number of samples in the fact table (donor's are not aggregable)
						if collsFactsSamples < collection['size']:
								warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, f"Value of the collection size attribute (number of samples - {collection['size']}) is greater than the total number of samples in facts table ({collsFactsSamples}) - maybe false positive due to anonymization", "Check size information of the collection description with the cummulated number from the facts table and correct as necessary", dir.getCollectionContact(collection['id'])['email']))
						elif collsFactsSamples > collection['size']:
								warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, f"Value of the collection size attribute (number of samples - {collection['size']}) is smaller than the total number of samples in facts table ({collsFactsSamples})", "Check size information of the collection description with the cummulated number from the facts table and correct as necessary", dir.getCollectionContact(collection['id'])['email']))
					else:
						warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, "Collection size attribute (number of samples) not provided", "Add size attribute to the collection", dir.getCollectionContact(collection['id'])['email']))

					# check that if the DNA network, the fact table contains liquid materials from which DNA can be extracted (DNA, Peripheral blood cells, Whole Blood)
					if 'network' in collection:
						if BBMRICohortsDNANetworkName in collection_networks:
							requiredMaterialTypes = ['DNA','WHOLE_BLOOD','PERIPHERAL_BLOOD_CELLS','BUFFY_COAT','CDNA','PLASMA','SERUM']
							if not any(mat in collFactsMaterialTypes for mat in requiredMaterialTypes):
								warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, f"Collection in {BBMRICohortsDNANetworkName} but the fact table does not contain any of the expected material types: {','.join(requiredMaterialTypes)})", dir.getCollectionContact(collection['id'])['email']))

							if 'NAV' in collFactsMaterialTypes:
								warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, f"Collection in {BBMRICohortsDNANetworkName} but the fact table does specified the NAV (not-available) material type", dir.getCollectionContact(collection['id'])['email']))
			'''
			else:
				if 'network' in collection and (BBMRICohortsNetworkName in collection_networks or BBMRICohortsDNANetworkName in collection_networks):
					BBMRICohortsList = set()
					if (BBMRICohortsNetworkName in collection_networks):
						BBMRICohortsList.add(BBMRICohortsNetworkName)
					if (BBMRICohortsDNANetworkName in collection_networks):
						BBMRICohortsList.add(BBMRICohortsDNANetworkName)
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, f"Collection in BBMRI cohorts {BBMRICohortsList} but the fact table is missing", "Prepare the facts table for the collection and upload", collection['contact']['email']))
			'''
		return warnings