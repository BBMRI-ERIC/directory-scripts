# vim:ts=8:sw=8:tw=0:noet

import logging as log

from yapsy.IPlugin import IPlugin

from ai_cache import load_ai_findings_for_directory
from customwarnings import (
	DataCheckEntityType,
	DataCheckWarning,
	DataCheckWarningLevel,
	make_check_id,
)

CHECK_ID_PREFIX = 'AI'


# AI-backed findings are stored as curated records in ai-check-cache/<schema>/*.json.
# The plugin keeps stable warning IDs for the manual, while the repository cache
# stores the concrete entity-level findings generated from current Directory data.
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
		'fix': 'Add the structured material if paraffin-embedded tissue is really stored, or clarify in the text when the mention only refers to slides, sections, images, or derived DNA/RNA from FFPE material.',
	},
	'AI:CovidText': {
		'entity': 'COLLECTION',
		'fields': ['COLLECTION.description', 'COLLECTION.diagnosis_available', 'COLLECTION.name'],
		'severity': 'WARNING',
		'summary': 'Collection text suggests COVID-19 disease or post-/long-COVID focus, but the structured diagnosis metadata does not reflect that context.',
		'fix': 'Add the relevant structured diagnoses if the collection really targets COVID-19 or post-/long-COVID content (for example U07.* or U09.9), or reword the narrative to avoid misleading search results.',
	},
}


class AIFindings(IPlugin):
	CHECK_ID_PREFIX = 'AI'

	def check(self, dir, args):
		log.info('Running shareable AI-curated checks (AIFindings)')
		load_result = load_ai_findings_for_directory(dir)
		for issue in load_result.issues:
			self._log_cache_issue(issue)
		warnings = []
		for finding in load_result.findings:
			if not self._entity_exists_in_scope(dir, finding):
				continue
			warnings.append(self._build_warning(dir, finding))
		return warnings

	def _build_warning(self, dir, finding):
		rule = finding['rule']
		if rule == 'StudyText':
			self._validate_rule_metadata(
				finding,
				expected_entity='COLLECTION',
				expected_severity='WARNING',
			)
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
		if rule == 'AgeText':
			self._validate_rule_metadata(
				finding,
				expected_entity='COLLECTION',
				expected_severity='WARNING',
			)
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
		if rule == 'FFPEText':
			self._validate_rule_metadata(
				finding,
				expected_entity='COLLECTION',
				expected_severity='WARNING',
			)
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
		if rule == 'CovidText':
			self._validate_rule_metadata(
				finding,
				expected_entity='COLLECTION',
				expected_severity='WARNING',
			)
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

	def _log_cache_issue(self, issue):
		if issue.reason == 'scope-mismatch':
			log.warning(
				'AI cache %s was generated for withdrawn scope %s, but the current run uses a different scope. Rerun run-ai-checks.py before trusting AI findings.',
				issue.path,
				issue.withdrawn_scope,
			)
			return
		if issue.reason == 'missing-checksums':
			log.warning(
				'AI cache %s does not contain checksum metadata. Rerun run-ai-checks.py before trusting AI findings.',
				issue.path,
			)
			return
		log.warning(
			'AI cache %s is stale for rule %s (%s). Rerun run-ai-checks.py. Changed entities: %s',
			issue.path,
			issue.rule,
			issue.reason,
			', '.join(issue.entity_ids),
		)

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
