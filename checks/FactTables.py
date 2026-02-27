# vim:ts=8:sw=8:tw=0:noet

import re
import logging as log
import collections as py_collections

from directory import Directory
from fact_sheet_utils import (
	FACT_DIMENSION_KEYS,
	analyze_collection_fact_sheet,
	count_star_dimensions,
	get_dimension_values,
	get_matching_one_star_rows,
)

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel, DataCheckWarning, DataCheckEntityType, make_check_id

BBMRICohortsNetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts'
BBMRICohortsDNANetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts_DNA'
CHECK_ID_PREFIX = "FT"


def compareFactsColl(self, dir, factsList, collList, collection, errorDescription, actionDescription, warningsList): # TO improve
	if factsList != [] and py_collections.Counter(factsList) != py_collections.Counter(collList):
		warningsList.append(DataCheckWarning(make_check_id(self, "CollFactsMismatch"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), errorDescription + f" - collection information: {sorted(collList)} - fact information: {sorted(factsList)}", actionDescription, dir.getCollectionContact(collection['id'])['email']))


def compareAge(self, dir, factAges: set, factsAgeUnits: set, collection, warningsList):
	# NOTE assuming that collection age units uppercase and singular match with facts age units lowercase and plural (at least with years, YEAR, months, MONTH works)
	collUnitsAdapt = collection['age_unit'].lower() + 's'
	if collUnitsAdapt != str((',').join(sorted(factsAgeUnits))):
		warningsList.append(DataCheckWarning(make_check_id(self, "AgeUnitMismatch"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Age unit ID of the collection is {collection['age_unit']} while the age unit in the fact table is {factsAgeUnits}", "Check age unit information of the collection description with age units from the facts table and correct as necessary", dir.getCollectionContact(collection['id'])['email']))
	else:
		minFactAge = int(min(sorted(factAges)))
		maxFactAge = int(max(sorted(factAges)))
		try:
			if (minFactAge < collection['age_low']) or (maxFactAge > collection['age_high']):
				warningsList.append(DataCheckWarning(make_check_id(self, "AgeRangeMismatch"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Fact table age outside collection age_high age_low range", "Check age range of the collection description with ages from the facts table and correct as necessary", dir.getCollectionContact(collection['id'])['email']))
			if (collection['age_low'] < minFactAge) or (collection['age_high'] > maxFactAge):
				warningsList.append(DataCheckWarning(make_check_id(self, "AgeRangeBroad"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Collection ages outside facts age range", "Check age information of the collection description with age ranges from the facts table and correct as necessary", dir.getCollectionContact(collection['id'])['email']))
		except KeyError as e:
			log.info(f"Incomplete age range information for {collection['id']}: " + str(e) + " missing")


# Machine-readable check documentation for the manual generator and other tooling.
# Keep severity/entity/fields aligned with the emitted DataCheckWarning(...) calls.
CHECK_DOCS = {'FT:SizeMissing': {'entity': 'COLLECTION',
                                           'fields': ['donors_present',
                                                      'facts',
                                                      'id',
                                                      'size'],
                                           'fix': 'Add size attribute to the '
                                                  'collection',
                                           'severity': 'WARNING',
                                           'summary': 'Collection size attribute '
                                                      '(number of samples) not '
                                                      'provided'},
 'FT:OneStarMissing': {'entity': 'COLLECTION',
                                               'fields': ['donors_present',
                                                          'facts',
                                                          'id'],
                                               'severity': 'WARNING',
                                               'summary': 'missing all-but-one-star '
                                                          'aggregate: {aggregates[3]}'},
 'FT:OneStarValue': {'entity': 'COLLECTION',
                                            'fields': ['donors_present', 'facts', 'id'],
                                            'severity': 'INFO',
                                            'summary': 'missing all-but-one-star '
                                                       'aggregate for {fk} value '
                                                       '{value}: {aggregates[3]}'},
 'FT:AllStarMissing': {'entity': 'COLLECTION',
                                            'fields': ['all_star_rows',
                                                       'donors_present',
                                                       'facts',
                                                       'id'],
                                            'severity': 'WARNING',
                                            'summary': 'Expected exactly one all-star '
                                                       'aggregate row, found '
                                                       "{fact_sheet['all_star_rows']}."},
 'FT:AllStarDonorGap': {'entity': 'COLLECTION',
                                                      'fields': ['code',
                                                                 'donors_present',
                                                                 'facts',
                                                                 'id'],
                                                      'fix': 'Check the all-star '
                                                             'aggregate row and '
                                                             'collection '
                                                             'number_of_donors.',
                                                      'severity': 'WARNING',
                                                      'summary': 'Check '
                                                                 'FT:AllStarDonorGap'},
 'FT:AllStarSizeGap': {'entity': 'COLLECTION',
                                                     'fields': ['code',
                                                                'donors_present',
                                                                'facts',
                                                                'id'],
                                                     'fix': 'Check the all-star '
                                                            'aggregate row and '
                                                            'collection size.',
                                                     'severity': 'WARNING',
                                                     'summary': 'Check '
                                                                'FT:AllStarSizeGap'},
 'FT:AgeRangeBroad': {'entity': 'COLLECTION',
                                              'fields': ['age_high',
                                                         'age_low',
                                                         'age_unit'],
                                              'fix': 'Check age information of the '
                                                     'collection description with age '
                                                     'ranges from the facts table and '
                                                     'correct as necessary',
                                              'severity': 'WARNING',
                                              'summary': 'Collection ages outside '
                                                         'facts age range'},
 'FT:AgeRangeMismatch': {'entity': 'COLLECTION',
                                        'fields': ['age_high', 'age_low', 'age_unit'],
                                        'fix': 'Check age range of the collection '
                                               'description with ages from the facts '
                                               'table and correct as necessary',
                                        'severity': 'WARNING',
                                        'summary': 'Fact table age outside collection '
                                                   'age_high age_low range'},
 'FT:AgeUnitMismatch': {'entity': 'COLLECTION',
                                        'fields': ['age_unit'],
                                        'fix': 'Check age unit information of the '
                                               'collection description with age units '
                                               'from the facts table and correct as '
                                               'necessary',
                                        'severity': 'WARNING',
                                        'summary': 'Age unit ID of the collection is '
                                                   "{collection['age_unit']} while the "
                                                   'age unit in the fact table is '
                                                   '{factsAgeUnits}'},
 'FT:SizeAboveAllStar': {'entity': 'COLLECTION',
                                               'fields': ['all_star_number_of_samples',
                                                          'donors_present',
                                                          'facts',
                                                          'id',
                                                          'size'],
                                               'fix': 'Check size information of the '
                                                      'collection description with the '
                                                      'all-star row from the facts '
                                                      'table and correct as necessary',
                                               'severity': 'WARNING',
                                               'summary': 'Value of the collection '
                                                          'size attribute (number of '
                                                          'samples - '
                                                          "{collection['size']}) is "
                                                          'greater than the all-star '
                                                          'aggregate number_of_samples '
                                                          '({all_star_samples})'},
 'FT:SizeBelowAllStar': {'entity': 'COLLECTION',
                                                'fields': ['all_star_number_of_samples',
                                                           'donors_present',
                                                           'facts',
                                                           'id',
                                                           'size'],
                                                'fix': 'Check size information of the '
                                                       'collection description with '
                                                       'the all-star row from the '
                                                       'facts table and correct as '
                                                       'necessary',
                                                'severity': 'WARNING',
                                                'summary': 'Value of the collection '
                                                           'size attribute (number of '
                                                           'samples - '
                                                           "{collection['size']}) is "
                                                           'smaller than the all-star '
                                                           'aggregate '
                                                           'number_of_samples '
                                                           '({all_star_samples})'},
 'FT:DnaMaterials': {'entity': 'COLLECTION',
                           'fields': ['donors_present', 'facts', 'id', 'network'],
                           'severity': 'ERROR',
                           'summary': 'Collection in {BBMRICohortsDNANetworkName} but '
                                      'the fact table does not contain any of the '
                                      'expected material types: '
                                      "{','.join(requiredMaterialTypes)})"},
 'FT:DnaNavPresent': {'entity': 'COLLECTION',
                            'fields': ['donors_present', 'facts', 'id', 'network'],
                            'severity': 'ERROR',
                            'summary': 'Collection in {BBMRICohortsDNANetworkName} but '
                                       'the fact table does specified the NAV '
                                       '(not-available) material type'},
 'FT:CollFactsMismatch': {'entity': 'COLLECTION',
                                            'fields': ['diagnosis_available',
                                                       'facts',
                                                       'id',
                                                       'materials',
                                                       'sex'],
                                            'fix': 'Align the collection-level '
                                                   'descriptors with the fact '
                                                   'sheet. Check diagnoses, sex, '
                                                   'and material type values on the '
                                                   'collection record against the '
                                                   'values present in the fact '
                                                   'table and correct whichever '
                                                   'side is wrong.',
                                            'severity': 'WARNING',
                                            'summary': 'The fact sheet and the main '
                                                       'collection record describe '
                                                       'different diagnoses, sex '
                                                       'groups, or material '
                                                       'types.'},
 'FT:SizeInvalid': {'entity': 'COLLECTION',
                                              'fields': ['donors_present',
                                                         'facts',
                                                         'id',
                                                         'size'],
                                              'severity': 'ERROR',
                                              'summary': 'Collection size attribute '
                                                         '(number of samples) is not '
                                                         'an integer'},
 'FT:DonorsZero': {'entity': 'COLLECTION',
                                               'fields': ['all_star_number_of_donors',
                                                          'donors_present',
                                                          'facts',
                                                          'id'],
                                               'severity': 'WARNING',
                                               'summary': 'fact table information has '
                                                          '0 donors/patients'},
 'FT:KAnonViolation': {'entity': 'COLLECTION',
                                           'fields': ['all_star_number_of_donors',
                                                      'donors_present',
                                                      'facts',
                                                      'id'],
                                           'severity': 'WARNING',
                                           'summary': 'the '
                                                      '{len(kAnonymityViolatingList)} '
                                                      'records of fact table violates '
                                                      '{kAnonymityLimit}-anonymity: '
                                                      '{kAnonymityViolatingList}'}}

class FactTables(IPlugin):
	CHECK_ID_PREFIX = "FT"

	def check(self, dir, args):
		warnings = []
		log.info("Running content checks on facts tables")

		for collection in dir.getCollections():
			collectionFacts = []
			collFactsDiseases = set()
			collFactsSexGroups = set()
			collFactsMaterialTypes = set()
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
					materials.append(m)

			diags = []
			if 'diagnosis_available' in collection.keys():
				for d in collection['diagnosis_available']:
					if not re.search('-', d['name']):
						diags.append(d['name'])

			collSex = set(Directory.getListOfEntityAttributes(collection, 'sex'))

			if 'facts' in collection.keys() and collection['facts'] != []:
				collectionFacts = dir.getCollectionFacts(collection['id'])
				for fact in collectionFacts:
					if 'disease' in fact and isinstance(fact['disease'], dict):
						collFactsDiseases.add(fact['disease']['name'])
					if 'age_range' in fact:
						ages.update(re.findall(r'\d+', fact['age_range']))
						ageUnits.update(re.findall(r'\((?:\d+-\d+\s)?(.*?)\)', fact['age_range']))
						if '>80 years' in ageUnits:
							ageUnits.remove('>80 years')
							ageUnits.add('years')
					if 'sex' in fact:
						collFactsSexGroups.add(fact['sex'])
					if 'sample_type' in fact:
						collFactsMaterialTypes.add(fact['sample_type'])
					if 'number_of_samples' in fact:
						collsFactsSamples += fact['number_of_samples']
					if 'number_of_donors' in fact:
						collsFactsDonors += fact['number_of_donors']

				fact_sheet = analyze_collection_fact_sheet(collection, collectionFacts)
				all_star_samples = fact_sheet['all_star_number_of_samples']
				all_star_donors = fact_sheet['all_star_number_of_donors']

				if collsFactsSamples > 0 or fact_sheet['donors_present']:
					log.info(f"Hooooray, we have found BBMRI fact table populated: {collection['id']}")

					if all_star_donors == 0 or (all_star_donors is None and not fact_sheet['donors_present']):
						warnings.append(DataCheckWarning(make_check_id(self, "DonorsZero"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "fact table information has 0 donors/patients"))
					else:
						kAnonymityViolatingList = []
						kAnonymityLimit = 5
						for f in collectionFacts:
							if 'number_of_donors' in f and f['number_of_donors'] > 0 and f['number_of_donors'] < kAnonymityLimit:
								kAnonymityViolatingList.append([f['id'], f"{f['number_of_donors']} donor(s)"])
						if kAnonymityViolatingList:
							warnings.append(DataCheckWarning(make_check_id(self, "KAnonViolation"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"the {len(kAnonymityViolatingList)} records of fact table violates {kAnonymityLimit}-anonymity: {kAnonymityViolatingList}"))

					compareFactsColl(self, dir, collFactsDiseases, diags, collection, "Diagnoses of collection and facts table do not match", "Check diagnosis entries of the collection description with diagnoses from the facts table and correct as necessary", warnings)

					if 'age_unit' in collection.keys() and ageUnits:
						compareAge(self, dir, ages, ageUnits, collection, warnings)

					compareFactsColl(self, dir, collFactsSexGroups, collSex, collection, "Sex of collection and facts table do not match", "Check sex information of the collection description with sex information from the facts table and correct as necessary", warnings)
					compareFactsColl(self, dir, collFactsMaterialTypes, materials, collection, "Material types of collection and facts table do not match", "Check material types of the collection description with material types from the facts table and correct as necessary", warnings)

					fact_values = get_dimension_values(collectionFacts)
					aggregates = dict(py_collections.Counter(
						[count_star_dimensions(f, FACT_DIMENSION_KEYS) for f in collectionFacts]
					))
					aggregates = {k: 0 if k not in aggregates else aggregates[k] for k in range(0, len(FACT_DIMENSION_KEYS) + 1)}
					if fact_sheet['all_star_rows'] != 1:
						warnings.append(DataCheckWarning(make_check_id(self, "AllStarMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Expected exactly one all-star aggregate row, found {fact_sheet['all_star_rows']}."))
					if aggregates[3] < 1:
						warnings.append(DataCheckWarning(make_check_id(self, "OneStarMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"missing all-but-one-star aggregate: {aggregates[3]}"))
					else:
						for fk in fact_values:
							for value in fact_values[fk]:
								rows = get_matching_one_star_rows(collectionFacts, fk, value)
								if rows:
									log.info(f'3-star rows found for {fk} value {value}: {rows}')
								else:
									warnings.append(DataCheckWarning(make_check_id(self, "OneStarValue"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"missing all-but-one-star aggregate for {fk} value {value}: {aggregates[3]}"))

					for fact_warning in fact_sheet['warnings']:
						if fact_warning['code'] == 'all_star_samples_mismatch':
							warnings.append(DataCheckWarning(make_check_id(self, "AllStarSizeGap"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), fact_warning['message'], "Check the all-star aggregate row and collection size."))
						elif fact_warning['code'] == 'all_star_donors_mismatch':
							warnings.append(DataCheckWarning(make_check_id(self, "AllStarDonorGap"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), fact_warning['message'], "Check the all-star aggregate row and collection number_of_donors."))

					if 'size' in collection:
						if not isinstance(collection['size'], int):
							warnings.append(DataCheckWarning(make_check_id(self, "SizeInvalid"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Collection size attribute (number of samples) is not an integer", dir.getCollectionContact(collection['id'])['email']))
						if isinstance(all_star_samples, int) and all_star_samples < collection['size']:
							warnings.append(DataCheckWarning(make_check_id(self, "SizeAboveAllStar"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Value of the collection size attribute (number of samples - {collection['size']}) is greater than the all-star aggregate number_of_samples ({all_star_samples})", "Check size information of the collection description with the all-star row from the facts table and correct as necessary", dir.getCollectionContact(collection['id'])['email']))
						elif isinstance(all_star_samples, int) and all_star_samples > collection['size']:
							warnings.append(DataCheckWarning(make_check_id(self, "SizeBelowAllStar"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Value of the collection size attribute (number of samples - {collection['size']}) is smaller than the all-star aggregate number_of_samples ({all_star_samples})", "Check size information of the collection description with the all-star row from the facts table and correct as necessary", dir.getCollectionContact(collection['id'])['email']))
					else:
						warnings.append(DataCheckWarning(make_check_id(self, "SizeMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Collection size attribute (number of samples) not provided", "Add size attribute to the collection", dir.getCollectionContact(collection['id'])['email']))

					if 'network' in collection and BBMRICohortsDNANetworkName in collection_networks:
						requiredMaterialTypes = ['DNA', 'WHOLE_BLOOD', 'PERIPHERAL_BLOOD_CELLS', 'BUFFY_COAT', 'CDNA', 'PLASMA', 'SERUM']
						if not any(mat in collFactsMaterialTypes for mat in requiredMaterialTypes):
							warnings.append(DataCheckWarning(make_check_id(self, "DnaMaterials"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Collection in {BBMRICohortsDNANetworkName} but the fact table does not contain any of the expected material types: {','.join(requiredMaterialTypes)})", dir.getCollectionContact(collection['id'])['email']))

						if 'NAV' in collFactsMaterialTypes:
							warnings.append(DataCheckWarning(make_check_id(self, "DnaNavPresent"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Collection in {BBMRICohortsDNANetworkName} but the fact table does specified the NAV (not-available) material type", dir.getCollectionContact(collection['id'])['email']))
		return warnings
