# vim:ts=8:sw=8:tw=0:noet

import re
import logging as log
import collections as py_collections
from fact_sheet_utils import (
	analyze_collection_fact_sheet,
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
                       'fields': ['facts'],
                       'fix': 'Add all-but-one-star rows for the represented values of each fact-sheet dimension.',
                       'severity': 'WARNING',
                       'summary': 'The fact sheet has no all-but-one-star marginal rows.'},
 'FT:OneStarValue': {'entity': 'COLLECTION',
                     'fields': ['facts'],
                     'fix': 'Add one all-but-one-star row for the reported dimension value.',
                     'severity': 'INFO',
                     'summary': 'A represented fact-sheet dimension value has no all-but-one-star row.'},
 'FT:AllStarMissing': {'entity': 'COLLECTION',
                       'fields': ['facts'],
                       'fix': 'Add one all-star row or remove duplicate all-star rows so exactly one remains.',
                       'severity': 'WARNING',
                       'summary': 'The fact sheet does not contain exactly one all-star aggregate row.'},
 'FT:AllStarDonorGap': {'entity': 'COLLECTION',
                        'fields': ['facts', 'number_of_donors'],
                        'fix': 'Correct the all-star donor count or collection number_of_donors so they agree.',
                        'severity': 'WARNING',
                        'summary': 'The all-star donor count differs from the collection donor count.'},
 'FT:AllStarSizeGap': {'entity': 'COLLECTION',
                       'fields': ['facts', 'size'],
                       'fix': 'Correct the all-star sample count or collection size so they agree.',
                       'severity': 'WARNING',
                       'summary': 'The all-star sample count differs from the collection sample count.'},
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
                                                      '{kAnonymityViolatingList}'},
 'FT:OneStarDuplicate': {
     'entity': 'COLLECTION',
     'fields': ['facts'],
     'severity': 'WARNING',
     'summary': 'Multiple all-but-one-star rows describe the same dimension value.',
     'fix': 'Keep one authoritative all-but-one-star row for each dimension value.'},
 'FT:OneStarSamplesAboveAllStar': {
     'entity': 'COLLECTION',
     'fields': ['facts'],
     'severity': 'WARNING',
     'summary': 'An all-but-one-star sample count exceeds the all-star sample count.',
     'fix': 'Correct the individual marginal or all-star sample count without summing marginal values.'},
 'FT:OneStarDonorsAboveAllStar': {
     'entity': 'COLLECTION',
     'fields': ['facts'],
     'severity': 'WARNING',
     'summary': 'An all-but-one-star donor count exceeds the all-star donor count.',
     'fix': 'Correct the individual marginal or all-star donor count without summing marginal values.'},
 'FT:AllStarSamplesOoMGap': {
     'entity': 'COLLECTION',
     'fields': ['facts', 'order_of_magnitude'],
     'severity': 'WARNING',
     'summary': 'The all-star sample count is outside the collection sample OoM interval.',
     'fix': 'Correct the all-star sample count or collection order_of_magnitude.'},
 'FT:AllStarDonorsOoMGap': {
     'entity': 'COLLECTION',
     'fields': ['facts', 'order_of_magnitude_donors'],
     'severity': 'WARNING',
     'summary': 'The all-star donor count is outside the collection donor OoM interval.',
     'fix': 'Correct the all-star donor count or collection order_of_magnitude_donors.'}}


def _append_fact_sheet_analysis_warnings(self, dir, collection, fact_sheet, warnings):
	"""Translate shared fact-sheet analysis warnings into QC warnings."""
	contact = dir.getCollectionContact(collection['id'])
	contact_email = '' if contact is None else contact.get('email', '')
	for fact_warning in fact_sheet['warnings']:
		warning_code = fact_warning['code']
		if warning_code == 'missing_all_but_one_value' and fact_sheet['all_but_one_rows'] == 0:
			continue
		if collection.get('facts'):
			common_args = (
				"", dir.getCollectionNN(collection['id']), collection['id'],
				str(collection['withdrawn']),
				fact_warning['message'],
				"Review the fact-sheet aggregate rows and collection-level counts; do not add values across aggregation levels.",
				contact_email,
			)
			match warning_code:
				case 'missing_all_star' | 'multiple_all_star':
					warnings.append(DataCheckWarning(make_check_id(self, "AllStarMissing"), common_args[0], common_args[1], DataCheckWarningLevel.WARNING, common_args[2], DataCheckEntityType.COLLECTION, common_args[3], common_args[4], common_args[5], common_args[6]))
				case 'missing_all_but_one':
					warnings.append(DataCheckWarning(make_check_id(self, "OneStarMissing"), common_args[0], common_args[1], DataCheckWarningLevel.WARNING, common_args[2], DataCheckEntityType.COLLECTION, common_args[3], common_args[4], common_args[5], common_args[6]))
				case 'missing_all_but_one_value':
					warnings.append(DataCheckWarning(make_check_id(self, "OneStarValue"), common_args[0], common_args[1], DataCheckWarningLevel.INFO, common_args[2], DataCheckEntityType.COLLECTION, common_args[3], common_args[4], common_args[5], common_args[6]))
				case 'multiple_all_but_one_value':
					warnings.append(DataCheckWarning(make_check_id(self, "OneStarDuplicate"), common_args[0], common_args[1], DataCheckWarningLevel.WARNING, common_args[2], DataCheckEntityType.COLLECTION, common_args[3], common_args[4], common_args[5], common_args[6]))
				case 'all_star_samples_mismatch':
					if collection.get('size') is not None:
						warnings.append(DataCheckWarning(make_check_id(self, "AllStarSizeGap"), common_args[0], common_args[1], DataCheckWarningLevel.WARNING, common_args[2], DataCheckEntityType.COLLECTION, common_args[3], common_args[4], common_args[5], common_args[6]))
				case 'all_star_donors_mismatch':
					if collection.get('number_of_donors') is not None:
						warnings.append(DataCheckWarning(make_check_id(self, "AllStarDonorGap"), common_args[0], common_args[1], DataCheckWarningLevel.WARNING, common_args[2], DataCheckEntityType.COLLECTION, common_args[3], common_args[4], common_args[5], common_args[6]))
				case 'all_star_samples_oom_mismatch':
					if collection.get('order_of_magnitude') is not None:
						warnings.append(DataCheckWarning(make_check_id(self, "AllStarSamplesOoMGap"), common_args[0], common_args[1], DataCheckWarningLevel.WARNING, common_args[2], DataCheckEntityType.COLLECTION, common_args[3], common_args[4], common_args[5], common_args[6]))
				case 'all_star_donors_oom_mismatch':
					if collection.get('order_of_magnitude_donors') is not None:
						warnings.append(DataCheckWarning(make_check_id(self, "AllStarDonorsOoMGap"), common_args[0], common_args[1], DataCheckWarningLevel.WARNING, common_args[2], DataCheckEntityType.COLLECTION, common_args[3], common_args[4], common_args[5], common_args[6]))
				case 'all_but_one_samples_above_all_star':
					warnings.append(DataCheckWarning(make_check_id(self, "OneStarSamplesAboveAllStar"), common_args[0], common_args[1], DataCheckWarningLevel.WARNING, common_args[2], DataCheckEntityType.COLLECTION, common_args[3], common_args[4], common_args[5], common_args[6]))
				case 'all_but_one_donors_above_all_star':
					warnings.append(DataCheckWarning(make_check_id(self, "OneStarDonorsAboveAllStar"), common_args[0], common_args[1], DataCheckWarningLevel.WARNING, common_args[2], DataCheckEntityType.COLLECTION, common_args[3], common_args[4], common_args[5], common_args[6]))


def _has_positive_fact_count(facts, field):
	"""Return whether any fact row has a positive integer count in a field."""
	return any(
		isinstance(fact.get(field), int)
		and not isinstance(fact.get(field), bool)
		and fact[field] > 0
		for fact in facts
	)

class FactTables(IPlugin):
	CHECK_ID_PREFIX = "FT"

	def check(self, dir, args):
		warnings = []
		log.info("Running content checks on facts tables")

		for collection in dir.getCollections():
			collectionFacts = []

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
				fact_sheet = analyze_collection_fact_sheet(collection, collectionFacts)
				raw_fact_descriptor_values = collect_fact_descriptor_values(collectionFacts)
				fact_descriptor_values = fact_descriptor_values_for_comparison(collectionFacts, collection)
				all_star_samples = fact_sheet['all_star_number_of_samples']
				all_star_donors = fact_sheet['all_star_number_of_donors']

				_append_fact_sheet_analysis_warnings(
					self,
					dir,
					collection,
					fact_sheet,
					warnings,
				)

				samples_present = _has_positive_fact_count(
					collectionFacts,
					'number_of_samples',
				)
				if samples_present or fact_sheet['donors_present']:
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
