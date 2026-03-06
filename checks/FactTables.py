# vim:ts=8:sw=8:tw=0:noet

import re
import logging as log
import collections as py_collections
from fact_sheet_utils import (
	FACT_DIMENSION_KEYS,
	analyze_collection_fact_sheet,
	count_star_dimensions,
	get_dimension_values,
	get_matching_one_star_rows,
)
from fact_descriptor_sync import (
	collect_fact_descriptor_values,
	derive_age_range_update,
	fact_descriptor_values_for_comparison,
	normalize_descriptor_value,
	parse_collection_multi_value_field,
)
from check_fix_helpers import build_fact_alignment_fix_proposals
from check_fix_helpers import build_fact_k_anonymity_drop_fixes
from k_anonymity import donor_value_violates_k

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel, DataCheckWarning, DataCheckEntityType, make_check_id

BBMRICohortsNetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts'
BBMRICohortsDNANetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts_DNA'
CHECK_ID_PREFIX = "FT"


def compareFactsColl(self, dir, factsList, collList, collection, errorDescription, actionDescription, warningsList): # TO improve
	if factsList and py_collections.Counter(factsList) != py_collections.Counter(collList):
		warningsList.append(DataCheckWarning(make_check_id(self, "CollFactsMismatch"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), errorDescription + f" - collection information: {sorted(collList)} - fact information: {sorted(factsList)}", actionDescription, dir.getCollectionContact(collection['id'])['email'], fix_proposals=build_fact_alignment_fix_proposals(collection, dir.getCollectionFacts(collection['id']))))


def _format_age_range(low, high, unit):
	if not unit:
		unit = "UNKNOWN"
	if low is None and high is None:
		return f"unknown {unit}"
	if low is None:
		return f"up to {high} {unit}"
	if high is None:
		return f"{low}+ {unit} (open upper bound)"
	return f"{low}-{high} {unit}"


def _format_age_notes(notes):
	if not notes:
		return ""
	return " " + " ".join(notes)


def compareAge(self, dir, collectionFacts, collection, warningsList):
	age_update = derive_age_range_update(collectionFacts)
	derived_low = age_update["age_low"]
	derived_high = age_update["age_high"]
	derived_unit = age_update["age_unit"]
	notes = age_update["notes"]

	if derived_low is None and derived_high is None and derived_unit is None:
		return

	collection_unit = normalize_descriptor_value(collection['age_unit']) or None
	if derived_unit and collection_unit and derived_unit != collection_unit:
		warningsList.append(DataCheckWarning(make_check_id(self, "AgeUnitMismatch"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Age unit of the collection is {collection_unit} while the fact-sheet age ranges imply {derived_unit}.{_format_age_notes(notes)}", "Check age unit information of the collection description with age units from the facts table and correct as necessary", dir.getCollectionContact(collection['id'])['email'], fix_proposals=build_fact_alignment_fix_proposals(collection, dir.getCollectionFacts(collection['id']))))
		return

	try:
		coll_age_low = int(collection['age_low'])
		coll_age_high = int(collection['age_high'])
	except (KeyError, TypeError, ValueError) as e:
		log.info(f"Incomplete age range information for {collection['id']}: " + str(e) + " missing")
		return

	display_unit = collection_unit or derived_unit
	collection_range = _format_age_range(coll_age_low, coll_age_high, display_unit)
	facts_range = _format_age_range(derived_low, derived_high, display_unit)

	if (derived_low is not None and derived_low < coll_age_low) or (derived_high is not None and derived_high > coll_age_high):
		warningsList.append(DataCheckWarning(make_check_id(self, "AgeRangeMismatch"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Fact-sheet age range ({facts_range}) is outside the collection age range ({collection_range}); suggested range based on the fact sheet is {facts_range}.{_format_age_notes(notes)}", "Check age range of the collection description with ages from the facts table and correct as necessary", dir.getCollectionContact(collection['id'])['email'], fix_proposals=build_fact_alignment_fix_proposals(collection, dir.getCollectionFacts(collection['id']))))
	if (derived_low is not None and coll_age_low < derived_low) or (derived_high is not None and coll_age_high > derived_high):
		warningsList.append(DataCheckWarning(make_check_id(self, "AgeRangeBroad"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Collection age range ({collection_range}) is broader than the fact-sheet age range ({facts_range}); suggested range based on the fact sheet is {facts_range}.{_format_age_notes(notes)}", "Check age information of the collection description with age ranges from the facts table and correct as necessary", dir.getCollectionContact(collection['id'])['email'], fix_proposals=build_fact_alignment_fix_proposals(collection, dir.getCollectionFacts(collection['id']))))


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
	                                                         'age_low'],
	                                              'fix': 'Check age information of the '
	                                                     'collection description with age '
	                                                     'ranges from the facts table and '
                                                     'correct as necessary',
                                              'severity': 'WARNING',
                                              'summary': 'Collection ages outside '
                                                         'facts age range'},
 'FT:AgeRangeMismatch': {'entity': 'COLLECTION',
	                                        'fields': ['age_high', 'age_low'],
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
                           'fields': ['donors_present', 'facts', 'id', 'materials', 'network'],
                           'severity': 'ERROR',
                           'summary': 'Collection in {BBMRICohortsDNANetworkName} but '
                                      'the fact table does not contain any of the '
                                      'expected material types: '
                                      "{','.join(requiredMaterialTypes)})"},
 'FT:DnaNavPresent': {'entity': 'COLLECTION',
                            'fields': ['donors_present', 'facts', 'id', 'materials', 'network'],
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
                                           'fix': 'For public Directory data, apply a donor k-anonymity baseline of k=10 and remove fact rows below that threshold. If the collection is already pre-anonymized under a documented policy, this rule may be reviewed as an explicit exception.',
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

			materials = parse_collection_multi_value_field(collection.get('materials'))
			diags = [
				value for value in parse_collection_multi_value_field(collection.get('diagnosis_available'))
				if not re.search('-', value)
			]
			collSex = parse_collection_multi_value_field(collection.get('sex'))

			if 'facts' in collection.keys() and collection['facts'] != []:
				collectionFacts = dir.getCollectionFacts(collection['id'])
				for fact in collectionFacts:
					if 'number_of_samples' in fact:
						collsFactsSamples += fact['number_of_samples']
					if 'number_of_donors' in fact:
						collsFactsDonors += fact['number_of_donors']

				fact_sheet = analyze_collection_fact_sheet(collection, collectionFacts)
				raw_fact_descriptor_values = collect_fact_descriptor_values(collectionFacts)
				fact_descriptor_values = fact_descriptor_values_for_comparison(collectionFacts, collection)
				all_star_samples = fact_sheet['all_star_number_of_samples']
				all_star_donors = fact_sheet['all_star_number_of_donors']

				if collsFactsSamples > 0 or fact_sheet['donors_present']:
					log.info(f"Hooooray, we have found BBMRI fact table populated: {collection['id']}")

					if all_star_donors == 0 or (all_star_donors is None and not fact_sheet['donors_present']):
						warnings.append(DataCheckWarning(make_check_id(self, "DonorsZero"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "fact table information has 0 donors/patients"))
					else:
						kAnonymityViolatingList = []
						kAnonymityLimit = 10
						for f in collectionFacts:
							if donor_value_violates_k(f.get('number_of_donors'), kAnonymityLimit):
								kAnonymityViolatingList.append([f['id'], f"{f['number_of_donors']} donor(s)"])
						if kAnonymityViolatingList:
							warnings.append(DataCheckWarning(make_check_id(self, "KAnonViolation"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"the {len(kAnonymityViolatingList)} records of fact table violates {kAnonymityLimit}-anonymity: {kAnonymityViolatingList}", f"For publicly exposed highly aggregated Directory data, the recommended donor k-anonymity baseline is k={kAnonymityLimit}. Drop violating fact rows unless this collection is already pre-anonymized under a documented exception policy.", fix_proposals=build_fact_k_anonymity_drop_fixes(collection, collectionFacts, k_limit=kAnonymityLimit)))

					compareFactsColl(self, dir, fact_descriptor_values['diagnosis_available'], diags, collection, "Diagnoses of collection and facts table do not match", "Check diagnosis entries of the collection description with diagnoses from the facts table and correct as necessary", warnings)

					if 'age_unit' in collection.keys():
						compareAge(self, dir, collectionFacts, collection, warnings)

					compareFactsColl(self, dir, fact_descriptor_values['sex'], collSex, collection, "Sex of collection and facts table do not match", "Check sex information of the collection description with sex information from the facts table and correct as necessary", warnings)
					compareFactsColl(self, dir, fact_descriptor_values['materials'], materials, collection, "Material types of collection and facts table do not match", "Check material types of the collection description with material types from the facts table and correct as necessary", warnings)

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
						if not any(mat in fact_descriptor_values['materials'] for mat in requiredMaterialTypes):
							warnings.append(DataCheckWarning(make_check_id(self, "DnaMaterials"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Collection in {BBMRICohortsDNANetworkName} but the fact table does not contain any of the expected material types: {','.join(requiredMaterialTypes)})", dir.getCollectionContact(collection['id'])['email']))

						if 'NAV' in raw_fact_descriptor_values['materials']:
							warnings.append(DataCheckWarning(make_check_id(self, "DnaNavPresent"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Collection in {BBMRICohortsDNANetworkName} but the fact table does specified the NAV (not-available) material type", dir.getCollectionContact(collection['id'])['email']))
		return warnings
