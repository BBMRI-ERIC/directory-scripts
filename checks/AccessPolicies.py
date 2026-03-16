# vim:ts=8:sw=8:tw=0:noet

import re
import urllib.request
import logging as log

from yapsy.IPlugin import IPlugin
from check_fix_helpers import make_collection_term_append_fix
from customwarnings import DataCheckWarningLevel, DataCheckWarning, DataCheckEntityType, make_check_id
from duo_terms import normalize_duo_term_ids

from directory import Directory

# Machine-readable check documentation for the manual generator and other tooling.
# Keep severity/entity/fields aligned with the emitted DataCheckWarning(...) calls.
CHECK_DOCS = {'AP:BBAvailNone': {'entity': 'BIOBANK',
                                            'fields': ['collaboration_commercial',
                                                       'collaboration_non_for_profit'],
                                            'severity': 'ERROR',
                                            'summary': 'Biobank is available neither '
                                                       'for commercial nor for '
                                                       'non-for-profit collaboration'},
 'AP:BioDuoMissing': {'entity': 'COLLECTION',
                                                 'fields': ['data_use'],
                                                 'severity': 'INFO',
                                                 'summary': 'Collection contains '
                                                            'biological material types '
                                                            "'{materials}' but ethics "
                                                            'approval needed '
                                                            "'{DUO_term_ethics_needed}' "
                                                            'is not specified in '
                                                            'data_use attribute (may '
                                                            'be false-positive). DUO '
                                                            'documentation available '
                                                            'at '
                                                            '{DUOs_to_url(DUO_term_ethics_needed)}'},
 'AP:DiseaseDuoMissing': {'entity': 'COLLECTION',
                                                     'fields': ['data_use', 'type'],
                                                     'severity': 'INFO',
                                                     'summary': 'Collection is disease '
                                                                'specific but '
                                                                "'{DUO_term_disease_specific}' "
                                                                'is not specified in '
                                                                'data_use attribute '
                                                                '(may be '
                                                                'false-positive). DUO '
                                                                'documentation '
                                                                'available at '
                                                                '{DUOs_to_url(DUO_term_disease_specific)}'},
 'AP:AccessMissing': {'entity': 'COLLECTION',
                                             'fields': ['access_description',
                                                        'access_fee',
                                                        'access_joint_project',
                                                        'access_uri'],
                                             'severity': 'ERROR',
                                             'summary': 'No generic access mode '
                                                        'enabled and no access '
                                                        'policy (description nor URI) '
                                                        'provided for collection'},
 'AP:DataRetDuo': {'entity': 'COLLECTION',
                                                  'fields': ['data_use'],
                                                  'severity': 'INFO',
                                                  'summary': 'Data return is not '
                                                             'required (missing '
                                                             '{DUO_term_data_return}) '
                                                             'in data_use attribute - '
                                                             'it is recommended for '
                                                             'biobanks to support it '
                                                             'based on BBMRI-ERIC '
                                                             'Access policy (but not '
                                                             'required). DUO '
                                                             'documentation available '
                                                             'at '
                                                             '{DUOs_to_url(DUO_term_data_return)}'},
 'AP:DuoMissing': {'entity': 'COLLECTION',
                                                   'fields': ['data_use'],
                                                   'severity': 'WARNING',
                                                   'summary': 'No Data Use Ontology '
                                                              '(DUO) term provided in '
                                                              'data_use attribute'},
 'AP:JointDuo': {'entity': 'COLLECTION',
                                                 'fields': ['data_use'],
                                                 'severity': 'WARNING',
                                                 'summary': 'Joint projects for '
                                                            'sample/data/image access '
                                                            'specified and '
                                                            '{DUO_term_joint_project} '
                                                            'is not specified in '
                                                            'data_use attribute. DUO '
                                                            'documentation available '
                                                            'at '
                                                            '{DUOs_to_url(DUO_term_joint_project)}'},
 'AP:CollDuoMissing': {'entity': 'COLLECTION',
                                                'fields': ['collaboration_commercial',
                                                           'collaboration_non_for_profit',
                                                           'data_use'],
                                                'severity': 'INFO',
                                                'summary': 'At least one of '
                                                           '{attributes} specified on '
                                                           'collection level but '
                                                           "'{DUO_term}' is not "
                                                           'specified in data_use '
                                                           'attribute (may be however '
                                                           'intentional). DUO '
                                                           'documentation available at '
                                                           '{DUOs_to_url(DUO_term)}'},
 'AP:BBDuoMissing': {'entity': 'COLLECTION',
                                                 'fields': ['collaboration_commercial',
                                                            'collaboration_non_for_profit',
                                                            'data_use'],
                                                 'severity': 'INFO',
                                                 'summary': 'At least one of '
                                                            '{attributes} specified on '
                                                            'biobank level and not '
                                                            'overridden on collection '
                                                            "but '{DUO_term}' is not "
                                                            'specified in data_use '
                                                            'attribute (may be however '
                                                            'intentional). DUO '
                                                            'documentation available '
                                                            'at '
                                                            '{DUOs_to_url(DUO_term)}'},
 'AP:CollDuoConflict': {'entity': 'COLLECTION',
                                                 'fields': ['collaboration_commercial',
                                                            'collaboration_non_for_profit',
                                                            'data_use'],
                                                 'severity': 'ERROR',
                                                 'summary': 'At least one of '
                                                            '{attributes} specified on '
                                                            'collection level but '
                                                            "conflicting '{DUO_term}' "
                                                            'is specified in data_use '
                                                            'attribute. DUO '
                                                            'documentation available '
                                                            'at '
                                                            '{DUOs_to_url(DUO_term)}'},
 'AP:BBAttrDuoConflict': {'entity': 'COLLECTION',
                                                 'fields': ['collaboration_commercial',
                                                            'collaboration_non_for_profit',
                                                            'data_use'],
                                                 'severity': 'ERROR',
                                                 'summary': 'At least one of '
                                                            '{attributes} specified on '
                                                            'biobank level and not '
                                                            'overridden on collection '
                                                            'but conflicting '
                                                            "'{DUO_term}' is specified "
                                                            'in data_use attribute. '
                                                            'DUO documentation '
                                                            'available at '
                                                            '{DUOs_to_url(DUO_term)}'},
 'AP:GenericDuoMissing': {'entity': 'COLLECTION',
                                                   'fields': ['data_use'],
                                                   'severity': 'WARNING',
                                                   'summary': 'None of generic '
                                                              'research use purposes '
                                                              'provided '
                                                              '({DUO_terms_research}) '
                                                              'in data_use attribute - '
                                                              'suspect situation for a '
                                                              'biobank registered in '
                                                              'BBMRI-ERIC Directory, '
                                                              'which is for research '
                                                              'purposes. DUO '
                                                              'documentation available '
                                                              'at '
                                                              '{DUOs_to_url(DUO_terms_research)}'},
}


def _has_meaningful_access_value(value):
	"""Return whether an access-policy field contains a meaningful non-empty value."""
	if value is None:
		return False
	if isinstance(value, bool):
		return value
	if isinstance(value, float):
		# pandas/pyclient may expose missing values as NaN
		return not (value != value)
	if isinstance(value, str):
		return not re.search(r'^\s*$', value)
	if isinstance(value, (list, tuple, set, dict)):
		return len(value) > 0
	return bool(value)


def _collection_has_generic_access_policy(collection):
	"""Return whether the collection exposes any generic access-policy field."""
	for field_name in ('access_fee', 'access_joint_project', 'access_description', 'access_uri'):
		if _has_meaningful_access_value(collection.get(field_name)):
			return True
	return False


def _collection_requires_joint_project_duo(collection):
	"""Return whether generic access metadata says joint-project access is required."""
	return _has_meaningful_access_value(collection.get('access_joint_project'))

class AccessPolicies(IPlugin):
	CHECK_ID_PREFIX = "AP"
	def check(self, dir, args):
		warnings = []
		log.info("Running access policy checks (AccessPolicies)")
		for biobank in dir.getBiobanks():
			if((not 'collaboration_commercial' in biobank or biobank['collaboration_commercial'] == False) and
					(not 'collaboration_non_for_profit' in biobank or biobank['collaboration_non_for_profit'] == False)):
				warnings.append(DataCheckWarning(make_check_id(self, "BBAvailNone"), "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "Biobank is available neither for commercial nor for non-for-profit collaboration"))

		for collection in dir.getCollections():

			#materials = Directory.getListOfEntityAttributeIds(collection, 'materials') EMX2 materials do not have id, then:
			raw_materials = Directory.getListOfEntityAttributes(collection, 'materials')
			materials = []
			for material in raw_materials:
				material_value = str(material).strip() if material is not None else ""
				if not material_value or material_value.upper() == "NAV":
					continue
				materials.append(material_value)
			#collection_types = Directory.getListOfEntityAttributeIds(collection, 'type') # EMX2 types does not have ID, then:
			collection_types = Directory.getListOfEntityAttributes(collection, 'type')
			#DUOs = Directory.getListOfEntityAttributeIds(collection, 'data_use') # EMX2 types does not have ID, then:
			DUOs = normalize_duo_term_ids(Directory.getListOfEntityAttributes(collection, 'data_use'))
			data_categories = []
			for c in collection.get('data_categories', []):
				data_categories.append(c)

			biobankId = dir.getCollectionBiobankId(collection['id'])
			biobank = dir.getBiobankById(biobankId)
			
			if not _collection_has_generic_access_policy(collection):
				warnings.append(DataCheckWarning(make_check_id(self, "AccessMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "No generic access mode enabled and no access policy (description nor URI) provided for collection"))

			# DUO specific checks
							
			if not DUOs:
				warnings.append(DataCheckWarning(make_check_id(self, "DuoMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "No Data Use Ontology (DUO) term provided in data_use attribute"))

			# aux routine to translate DUO codes to URLs
			def DUOs_to_url(DUO_list):
				if not isinstance(DUO_list, list):
					DUO_list = [ DUO_list ]
				replacements = [
						(r':', '_'),
						(r'^', 'http://purl.obolibrary.org/obo/'),
						]
				DUO_urls = DUO_list
				for s, t in replacements:
					DUO_urls = [re.sub(s, t, i) for i in DUO_urls]
				return " ".join(DUO_urls)

			# Generic checks on allowing research
			DUO_terms_research = ['DUO:0000007', 'DUO:0000006', 'DUO:0000042']
			if  not any(x in DUOs for x in DUO_terms_research):
				warnings.append(DataCheckWarning(make_check_id(self, "GenericDuoMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"None of generic research use purposes provided ({DUO_terms_research}) in data_use attribute - suspect situation for a biobank registered in BBMRI-ERIC Directory, which is for research purposes. DUO documentation available at {DUOs_to_url(DUO_terms_research)}", fix_proposals=[
					make_collection_term_append_fix(
						update_id="access.duo.general_research_use",
						module="AP",
						collection=collection,
						field="data_use",
						term_id="DUO:0000042",
						confidence="uncertain",
						human_explanation="Add DUO:0000042 (general research use) if the collection allows general research use.",
						rationale="Generic research-use coverage is missing, but the exact DUO scope requires curator confirmation.",
						exclusive_group="access_generic_research_use",
						blocking_reason="Several generic DUO choices may be plausible; choose the one matching the real consent/access policy.",
					),
					make_collection_term_append_fix(
						update_id="access.duo.health_medical_biomedical",
						module="AP",
						collection=collection,
						field="data_use",
						term_id="DUO:0000006",
						confidence="uncertain",
						human_explanation="Add DUO:0000006 (health or medical or biomedical research) if the collection is restricted to health/medical research use.",
						rationale="Generic research-use coverage is missing, but the exact DUO scope requires curator confirmation.",
						exclusive_group="access_generic_research_use",
						blocking_reason="Several generic DUO choices may be plausible; choose the one matching the real consent/access policy.",
					),
				]))

			# description of data reuse policy based on BBMRI-ERIC Access Policy
			DUO_term_data_return = 'DUO:0000029'
			if  not DUO_term_data_return in DUOs:
				warnings.append(DataCheckWarning(make_check_id(self, "DataRetDuo"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Data return is not required (missing {DUO_term_data_return}) in data_use attribute - it is recommended for biobanks to support it based on BBMRI-ERIC Access policy (but not required). DUO documentation available at {DUOs_to_url(DUO_term_data_return)}", fix_proposals=[
					make_collection_term_append_fix(
						update_id="access.duo.return_to_resource",
						module="AP",
						collection=collection,
						field="data_use",
						term_id=DUO_term_data_return,
						confidence="uncertain",
						human_explanation="Add DUO:0000029 (return to database or resource) if derived/enriched data must be returned to the resource.",
						rationale="The QC check treats data-return support as recommended, not mandatory, so curator confirmation is still needed.",
						blocking_reason="This is a policy recommendation, not a deterministic requirement.",
					)
				]))

			# checks on different modes of collaboration - this is still a bit messy as DUO does not fit perfectly to our needs
			DUO_term_joint_project = 'DUO:0000020'
			if _collection_requires_joint_project_duo(collection) and DUO_term_joint_project not in DUOs:
				warnings.append(DataCheckWarning(make_check_id(self, "JointDuo"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Joint projects for sample/data/image access specified and {DUO_term_joint_project} is not specified in data_use attribute. DUO documentation available at {DUOs_to_url(DUO_term_joint_project)}", fix_proposals=[
					make_collection_term_append_fix(
						update_id="access.duo.collaboration_required",
						module="AP",
						collection=collection,
						field="data_use",
						term_id=DUO_term_joint_project,
						confidence="certain",
						human_explanation="Add DUO:0000020 (collaboration required) because the collection already advertises a joint-project access requirement.",
						rationale="The structured joint-project access flags directly imply this DUO modifier.",
					)
				]))

			# DUO term DUO:0000018 seems not only to allow non-for-profit collaboration, but also forbids commercial collaboration
			for attributes,negative_attributes,DUO_term in [(['collaboration_non_for_profit'], ['collaboration_commercial'], 'DUO:0000018')]:
				if any((x in collection and collection[x] == True) for x in attributes) and not (any((x in collection and collection[x] == True) for x in negative_attributes) or any((x not in collection and x in biobank and biobank[x] == True) for x in negative_attributes)) and DUO_term not in DUOs:
					warnings.append(DataCheckWarning(make_check_id(self, "CollDuoMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"At least one of {attributes} specified on collection level but '{DUO_term}' is not specified in data_use attribute (may be however intentional). DUO documentation available at {DUOs_to_url(DUO_term)}", fix_proposals=[
						make_collection_term_append_fix(
							update_id="access.duo.non_profit_non_commercial",
							module="AP",
							collection=collection,
							field="data_use",
							term_id=DUO_term,
							confidence="almost_certain",
							human_explanation="Add DUO:0000018 (not for profit, non commercial use only) because the collection is explicitly limited to non-profit/non-commercial collaboration.",
							rationale="The structured collaboration flags directly suggest a non-commercial DUO restriction, but local policy confirmation is still advisable.",
						)
					]))
				elif any((x not in collection and x in biobank and biobank[x] == True) for x in attributes) and not (any((x in collection and collection[x] == True) for x in negative_attributes) or any((x not in collection and x in biobank and biobank[x] == True) for x in negative_attributes)) and DUO_term not in DUOs:
					warnings.append(DataCheckWarning(make_check_id(self, "BBDuoMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"At least one of {attributes} specified on biobank level and not overridden on collection but '{DUO_term}' is not specified in data_use attribute (may be however intentional). DUO documentation available at {DUOs_to_url(DUO_term)}", fix_proposals=[
						make_collection_term_append_fix(
							update_id="access.duo.non_profit_non_commercial",
							module="AP",
							collection=collection,
							field="data_use",
							term_id=DUO_term,
							confidence="almost_certain",
							human_explanation="Add DUO:0000018 (not for profit, non commercial use only) because the inherited biobank collaboration flags limit the collection to non-profit/non-commercial use.",
							rationale="The inherited collaboration flags strongly suggest a non-commercial DUO restriction, but local policy confirmation is still advisable.",
						)
					]))

			for attributes,negative_DUO_term in [(['collaboration_commercial'], 'DUO:0000018')]:
				if any((x in collection and collection[x] == True) for x in attributes) and negative_DUO_term in DUOs:
					warnings.append(DataCheckWarning(make_check_id(self, "CollDuoConflict"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"At least one of {attributes} specified on collection level but conflicting '{negative_DUO_term}' is specified in data_use attribute. DUO documentation available at {DUOs_to_url(negative_DUO_term)}"))
				elif any((x not in collection and x in biobank and biobank[x] == True) for x in attributes) and negative_DUO_term in DUOs:
					warnings.append(DataCheckWarning(make_check_id(self, "BBAttrDuoConflict"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"At least one of {attributes} specified on biobank level and not overridden on collection but conflicting '{negative_DUO_term}' is specified in data_use attribute. DUO documentation available at {DUOs_to_url(negative_DUO_term)}"))

			# DUO term DUO:0000007 is potentially relevant for DISEASE_SPECIFIC collections
			DUO_term_disease_specific = 'DUO:0000007'
			if 'DISEASE_SPECIFIC' in collection_types and DUO_term_disease_specific not in DUOs:
				warnings.append(DataCheckWarning(make_check_id(self, "DiseaseDuoMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Collection is disease specific but '{DUO_term_disease_specific}' is not specified in data_use attribute (may be false-positive). DUO documentation available at {DUOs_to_url(DUO_term_disease_specific)}", fix_proposals=[
					make_collection_term_append_fix(
						update_id="access.duo.disease_specific_research",
						module="AP",
						collection=collection,
						field="data_use",
						term_id=DUO_term_disease_specific,
						confidence="almost_certain",
						human_explanation="Add DUO:0000007 (disease-specific research) because the collection is already typed as DISEASE_SPECIFIC.",
						rationale="The structured collection type strongly suggests disease-specific DUO restriction, but local consent wording should still be checked.",
					)
				]))

			# DUO term DUO:0000021 (ethics approval needed) is usually needed for reuse of human biological material
			DUO_term_ethics_needed = 'DUO:0000021'
			if materials and DUO_term_ethics_needed not in DUOs:
				warnings.append(DataCheckWarning(make_check_id(self, "BioDuoMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Collection contains biological material types from materials attribute '{collection.get('materials', [])}' but ethics approval needed '{DUO_term_ethics_needed}' is not specified in data_use attribute (may be false-positive). DUO documentation available at {DUOs_to_url(DUO_term_ethics_needed)}", fix_proposals=[
					make_collection_term_append_fix(
						update_id="access.duo.ethics_approval_required",
						module="AP",
						collection=collection,
						field="data_use",
						term_id=DUO_term_ethics_needed,
						confidence="uncertain",
						human_explanation="Add DUO:0000021 (ethics approval required) if access to this biomaterial collection indeed requires documented local ethics approval.",
						rationale="Presence of biological material alone does not prove that this DUO modifier is required for the collection.",
						blocking_reason="Ethics-approval requirements depend on local policy and consent conditions; curator confirmation is required.",
					)
				]))


		return warnings
