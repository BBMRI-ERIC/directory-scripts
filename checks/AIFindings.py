# vim:ts=8:sw=8:tw=0:noet

import logging as log

from yapsy.IPlugin import IPlugin

from ai_cache import load_ai_findings
from customwarnings import (
	DataCheckEntityType,
	DataCheckWarning,
	DataCheckWarningLevel,
	make_check_id,
)

CHECK_ID_PREFIX = 'AI'


# AI-backed findings are stored as curated records in ai-check-cache/<schema>/*.json.
# The goal is to keep a shareable, reviewable repository of issues identified by
# model-assisted review without relying on private runtime caches or live model
# access inside the standard QC pipeline.
CHECK_DOCS = {
	'AI:StudyText': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.description', 'COLLECTION.name', 'COLLECTION.type'],
		'severity': 'WARNING',
		'summary': 'Collection text suggests a study-design concept that is missing from the structured collection type.',
		'fix': 'Review the collection name/description and add the relevant structured type such as PROSPECTIVE_COLLECTION, LONGITUDINAL, or CASE_CONTROL when appropriate.',
	},
	'AI:AgeText': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.age_high', 'COLLECTION.age_low', 'COLLECTION.description', 'COLLECTION.name'],
		'severity': 'WARNING',
		'summary': 'Collection text suggests a target age group that does not match the structured age range.',
		'fix': 'Align the age_low/age_high metadata with the narrative description, or reword the narrative if the collection is broader than the text suggests.',
	},
	'AI:FFPEText': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.description', 'COLLECTION.materials', 'COLLECTION.name'],
		'severity': 'WARNING',
		'summary': 'Collection text mentions FFPE/paraffin material but the structured materials do not include TISSUE_PARAFFIN_EMBEDDED.',
		'fix': 'Add the structured material if it is really present, or clarify in the text that the mention refers to a different preparation or derivative.',
	},
	'AI:CovidText': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.description', 'COLLECTION.diagnosis_available', 'COLLECTION.name'],
		'severity': 'WARNING',
		'summary': 'Collection text suggests COVID-19, post-COVID, or vaccination focus but the structured diagnosis metadata does not reflect that context.',
		'fix': 'Add the relevant structured diagnoses if the collection really targets COVID-19/post-COVID content, or reword the narrative to avoid misleading search results.',
	},
}


LEVELS = {
	'ERROR': DataCheckWarningLevel.ERROR,
	'WARNING': DataCheckWarningLevel.WARNING,
	'INFO': DataCheckWarningLevel.INFO,
}

ENTITY_TYPES = {
	'BIOBANK': DataCheckEntityType.BIOBANK,
	'COLLECTION': DataCheckEntityType.COLLECTION,
}

class AIFindings(IPlugin):
	CHECK_ID_PREFIX = 'AI'

	def check(self, dir, args):
		log.info('Running shareable AI-curated checks (AIFindings)')
		findings = load_ai_findings(dir.getSchema())
		warnings = []
		for finding in findings:
			if not self._entity_exists_in_scope(dir, finding):
				continue
			warnings.append(self._build_warning(dir, finding))
		return warnings

	def _build_warning(self, dir, finding):
		rule = finding['rule']
		if rule == 'StudyText':
			self._validate_rule_metadata(finding, expected_entity='COLLECTION', expected_severity='WARNING')
			return DataCheckWarning(
				make_check_id(CHECK_ID_PREFIX, 'StudyText'),
				'',
				self._resolve_nn(dir, finding),
				DataCheckWarningLevel.WARNING,
				finding['entity_id'],
				DataCheckEntityType.COLLECTION,
				str(finding.get('withdrawn', '')),
				finding['message'],
				finding['action'],
				finding.get('email', ''),
			)
		elif rule == 'AgeText':
			self._validate_rule_metadata(finding, expected_entity='COLLECTION', expected_severity='WARNING')
			return DataCheckWarning(
				make_check_id(CHECK_ID_PREFIX, 'AgeText'),
				'',
				self._resolve_nn(dir, finding),
				DataCheckWarningLevel.WARNING,
				finding['entity_id'],
				DataCheckEntityType.COLLECTION,
				str(finding.get('withdrawn', '')),
				finding['message'],
				finding['action'],
				finding.get('email', ''),
			)
		elif rule == 'FFPEText':
			self._validate_rule_metadata(finding, expected_entity='COLLECTION', expected_severity='WARNING')
			return DataCheckWarning(
				make_check_id(CHECK_ID_PREFIX, 'FFPEText'),
				'',
				self._resolve_nn(dir, finding),
				DataCheckWarningLevel.WARNING,
				finding['entity_id'],
				DataCheckEntityType.COLLECTION,
				str(finding.get('withdrawn', '')),
				finding['message'],
				finding['action'],
				finding.get('email', ''),
			)
		elif rule == 'CovidText':
			self._validate_rule_metadata(finding, expected_entity='COLLECTION', expected_severity='WARNING')
			return DataCheckWarning(
				make_check_id(CHECK_ID_PREFIX, 'CovidText'),
				'',
				self._resolve_nn(dir, finding),
				DataCheckWarningLevel.WARNING,
				finding['entity_id'],
				DataCheckEntityType.COLLECTION,
				str(finding.get('withdrawn', '')),
				finding['message'],
				finding['action'],
				finding.get('email', ''),
			)
		raise ValueError(f"Unsupported AI finding rule {rule!r}.")

	def _validate_rule_metadata(self, finding, expected_entity, expected_severity):
		if finding['entity_type'] != expected_entity:
			raise ValueError(
				f"AI finding {finding['rule']!r} for {finding['entity_id']!r} "
				f"must use entity_type={expected_entity!r}."
			)
		if finding['severity'] != expected_severity:
			raise ValueError(
				f"AI finding {finding['rule']!r} for {finding['entity_id']!r} "
				f"must use severity={expected_severity!r}."
			)

	def _entity_exists_in_scope(self, dir, finding):
		if finding['entity_type'] == 'BIOBANK':
			return dir.getBiobankById(finding['entity_id']) is not None
		if finding['entity_type'] == 'COLLECTION':
			return dir.getCollectionById(finding['entity_id']) is not None
		return False

	def _resolve_nn(self, dir, finding):
		if finding.get('nn'):
			return finding['nn']
		if finding['entity_type'] == 'BIOBANK':
			return dir.getBiobankNN(finding['entity_id'])
		return dir.getCollectionNN(finding['entity_id'])
