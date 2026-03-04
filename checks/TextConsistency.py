# vim:ts=8:sw=8:tw=0:noet

import logging as log

from yapsy.IPlugin import IPlugin

from check_fix_helpers import (
    make_collection_multi_value_fix,
    make_collection_scalar_set_fix,
)
from customwarnings import DataCheckEntityType, DataCheckWarning, DataCheckWarningLevel
from text_consistency import build_text_consistency_findings

CHECK_DOCS = {
	'TXT:AgeRange': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.age_high', 'COLLECTION.age_low', 'COLLECTION.description', 'COLLECTION.name'],
		'severity': 'WARNING',
		'summary': 'Collection text suggests an age group that does not match the structured age range.',
		'fix': 'Align the age_low/age_high metadata with the narrative description, or reword the narrative if the collection is broader than the text suggests.',
	},
	'TXT:StudyType': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.description', 'COLLECTION.name', 'COLLECTION.type'],
		'severity': 'WARNING',
		'summary': 'Collection text suggests a study-design concept that is missing from the structured collection type.',
		'fix': 'Review the collection name/description and add the relevant structured type such as PROSPECTIVE_COLLECTION, LONGITUDINAL, or CASE_CONTROL when appropriate.',
	},
	'TXT:FFPEMaterial': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.description', 'COLLECTION.materials', 'COLLECTION.name'],
		'severity': 'WARNING',
		'summary': 'Collection text mentions FFPE/paraffin material but the structured materials do not include TISSUE_PARAFFIN_EMBEDDED.',
		'fix': 'Add the structured material if paraffin-embedded tissue is really stored, or clarify in the text when the mention only refers to slides, sections, images, or derived DNA/RNA from FFPE material.',
	},
	'TXT:CovidDiag': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.description', 'COLLECTION.diagnosis_available', 'COLLECTION.name'],
		'severity': 'WARNING',
		'summary': 'Collection text suggests COVID-19 disease or post-/long-COVID focus, but the structured diagnosis metadata does not reflect that context.',
		'fix': 'Add the relevant structured diagnoses if the collection really targets COVID-19 or post-/long-COVID content (for example U07.* or U09.9), or reword the narrative to avoid misleading search results.',
	},
}


class TextConsistency(IPlugin):
	def check(self, dir, args):
		log.info('Running deterministic text consistency checks (TextConsistency)')
		warnings = []
		for collection in dir.getCollections():
			for finding in build_text_consistency_findings(collection):
				warnings.append(self._build_warning(dir, collection, finding))
		return warnings

	def _build_warning(self, dir, collection, finding):
		check_id = finding['check_id']
		if check_id == 'TXT:AgeRange':
			return DataCheckWarning(
				'TXT:AgeRange',
				'',
				dir.getCollectionNN(collection['id']),
				DataCheckWarningLevel.WARNING,
				collection['id'],
				DataCheckEntityType.COLLECTION,
				str(dir.isCollectionWithdrawn(collection['id'])),
				finding['message'],
				finding['action'],
				fix_proposals=self._age_fix_proposals(collection, finding),
			)
		if check_id == 'TXT:StudyType':
			return DataCheckWarning(
				'TXT:StudyType',
				'',
				dir.getCollectionNN(collection['id']),
				DataCheckWarningLevel.WARNING,
				collection['id'],
				DataCheckEntityType.COLLECTION,
				str(dir.isCollectionWithdrawn(collection['id'])),
				finding['message'],
				finding['action'],
				fix_proposals=self._study_type_fix_proposals(collection, finding),
			)
		if check_id == 'TXT:FFPEMaterial':
			return DataCheckWarning(
				'TXT:FFPEMaterial',
				'',
				dir.getCollectionNN(collection['id']),
				DataCheckWarningLevel.WARNING,
				collection['id'],
				DataCheckEntityType.COLLECTION,
				str(dir.isCollectionWithdrawn(collection['id'])),
				finding['message'],
				finding['action'],
				fix_proposals=self._ffpe_fix_proposals(collection, finding),
			)
		if check_id == 'TXT:CovidDiag':
			return DataCheckWarning(
				'TXT:CovidDiag',
				'',
				dir.getCollectionNN(collection['id']),
				DataCheckWarningLevel.WARNING,
				collection['id'],
				DataCheckEntityType.COLLECTION,
				str(dir.isCollectionWithdrawn(collection['id'])),
				finding['message'],
				finding['action'],
				fix_proposals=self._covid_fix_proposals(collection, finding),
			)
		raise ValueError(f'Unsupported TextConsistency check_id {check_id!r}.')

	def _age_fix_proposals(self, collection, finding):
		suggested_age = finding.get('suggested_age') or {}
		fixes = []
		for field in ('age_low', 'age_high', 'age_unit'):
			value = suggested_age.get(field)
			if value is None:
				continue
			fixes.append(
				make_collection_scalar_set_fix(
					update_id=f'age.{field}.from_text',
					module='TXT',
					collection=collection,
					field=field,
					proposed_value=value,
					confidence='uncertain',
					human_explanation=(
						'Collection narrative suggests a more specific age range than the current structured age metadata.'
					),
					rationale='Narrative-derived age updates are heuristic and require review before application.',
					blocking_reason='Narrative-derived age interpretation is uncertain and may need manual choice.',
				)
			)
		return fixes

	def _study_type_fix_proposals(self, collection, finding):
		suggested_types = finding.get('suggested_types') or []
		if not suggested_types:
			return []
		return [
			make_collection_multi_value_fix(
				update_id=f'collection_type.add.{suggested_type.lower()}',
				module='TXT',
				collection=collection,
				field='type',
				proposed_values=[suggested_type],
				confidence='uncertain',
				human_explanation=(
					f"Collection narrative suggests adding the structured collection type {suggested_type}."
				),
				rationale='Narrative-derived study-design fixes are heuristic and require review before application.',
				blocking_reason='Narrative-derived type interpretation is uncertain and may conflict with local curation intent.',
			)
			for suggested_type in suggested_types
		]

	def _ffpe_fix_proposals(self, collection, finding):
		suggested_materials = finding.get('suggested_materials') or []
		if not suggested_materials:
			return []
		return [
			make_collection_multi_value_fix(
				update_id='materials.add.tissue_paraffin_embedded',
				module='TXT',
				collection=collection,
				field='materials',
				proposed_values=suggested_materials,
				confidence='almost_certain',
				human_explanation='Collection narrative strongly suggests paraffin-embedded tissue as a structured material type.',
				rationale='The deterministic FFPE text heuristic suppresses known slide/image/derived-material false positives before proposing this update.',
			)
		]

	def _covid_fix_proposals(self, collection, finding):
		fixes = []
		for diagnosis in finding.get('suggested_diagnoses') or []:
			fixes.append(
				make_collection_multi_value_fix(
					update_id=f"diagnoses.add.{diagnosis.split(':')[-1].lower()}",
					module='TXT',
					collection=collection,
					field='diagnosis_available',
					proposed_values=[diagnosis],
					confidence='almost_certain',
					human_explanation='Collection narrative suggests a missing structured post-/long-COVID diagnosis.',
					rationale='The deterministic text heuristic matched long/post-COVID wording and did not find an existing post-COVID diagnosis.',
				)
			)
		alternatives = finding.get('suggested_diagnosis_alternatives') or []
		for index, candidate_values in enumerate(alternatives, start=1):
			fixes.append(
				make_collection_multi_value_fix(
					update_id=f'diagnoses.add.covid_acute_option_{index}',
					module='TXT',
					collection=collection,
					field='diagnosis_available',
					proposed_values=candidate_values,
					confidence='uncertain',
					human_explanation='Collection narrative suggests a COVID-19 diagnosis, but the exact structured acute-COVID code still needs curator choice.',
					rationale='The deterministic text heuristic indicates COVID-19 disease context but cannot safely distinguish the exact acute diagnosis code.',
					blocking_reason='Several plausible acute COVID-19 diagnosis codes exist; choose the correct one explicitly.',
					exclusive_group='text_covid_acute_diagnosis',
				)
			)
		return fixes
