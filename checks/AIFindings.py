# vim:ts=8:sw=8:tw=0:noet

import logging as log

from yapsy.IPlugin import IPlugin

from ai_cache import load_ai_findings_for_directory
from customwarnings import DataCheckEntityType, DataCheckWarning, DataCheckWarningLevel, make_check_id
from validation_helpers import build_validation_warning_handler

CHECK_ID_PREFIX = 'AI'


# `ai-check-cache/` is reserved for findings that require full AI-model review on
# live data and cannot be expressed robustly as deterministic regex/heuristic
# checks. Deterministic text heuristics belong in regular plugins such as
# TextConsistency, not in the repository AI cache.
CHECK_DOCS = {
	'AI:Curated': {
		'entity': 'COLLECTION',
		'fields': [],
		'severity': 'WARNING',
		'dynamic_metadata': ['severity', 'entity'],
		'summary': 'AI-reviewed finding stored in the shareable ai-check-cache repository.',
		'fix': 'Review the cached finding details and evidence, then update the structured metadata or narrative accordingly. If the finding can be expressed deterministically, replace it with a regular plugin check instead of keeping it in the AI cache.',
	},
}


class AIFindings(IPlugin):
	CHECK_ID_PREFIX = 'AI'

	def check(self, dir, args):
		log.info('Running shareable AI-curated checks (AIFindings)')
		warn = build_validation_warning_handler(
			enabled=not bool(getattr(args, "suppress_validation_warnings", False)),
			logger=log.getLogger("validation"),
		)
		try:
			load_result = load_ai_findings_for_directory(dir, warn=warn)
		except TypeError as exc:
			if "unexpected keyword argument 'warn'" not in str(exc):
				raise
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
		entity_type = self._resolve_entity_type(finding)
		severity = self._resolve_severity(finding)
		return DataCheckWarning(
			make_check_id(CHECK_ID_PREFIX, 'Curated'),
			'',
			self._resolve_nn(dir, finding),
			severity,
			finding['entity_id'],
			entity_type,
			str(finding.get('withdrawn', '')),
			self._format_message(finding),
			finding['action'],
			finding.get('email', ''),
		)

	def _format_message(self, finding):
		rule = finding.get('rule')
		message = finding['message']
		if not rule:
			return message
		return f"[{rule}] {message}"

	def _log_cache_issue(self, issue):
		if issue.reason == 'scope-mismatch':
			log.warning(
				'AI cache %s was generated for withdrawn scope %s, but the current run uses a different scope. Rerun the live AI-review workflow before trusting AI findings.',
				issue.path,
				issue.withdrawn_scope,
			)
			return
		if issue.reason == 'missing-checksums':
			log.warning(
				'AI cache %s does not contain checksum metadata. Refresh the live AI-review workflow before trusting AI findings.',
				issue.path,
			)
			return
		log.warning(
			'AI cache %s is stale for rule %s (%s). Refresh the live AI-review workflow. Changed entities: %s',
			issue.path,
			issue.rule,
			issue.reason,
			', '.join(issue.entity_ids),
		)

	def _resolve_entity_type(self, finding):
		entity_type = finding['entity_type']
		mapping = {
			'BIOBANK': DataCheckEntityType.BIOBANK,
			'COLLECTION': DataCheckEntityType.COLLECTION,
		}
		if entity_type not in mapping:
			raise ValueError(
				f"AI finding {finding.get('rule')!r} for {finding['entity_id']!r} "
				f"uses unsupported entity_type={entity_type!r}."
			)
		return mapping[entity_type]

	def _resolve_severity(self, finding):
		severity = finding['severity']
		mapping = {
			'ERROR': DataCheckWarningLevel.ERROR,
			'WARNING': DataCheckWarningLevel.WARNING,
			'INFO': DataCheckWarningLevel.INFO,
		}
		if severity not in mapping:
			raise ValueError(
				f"AI finding {finding.get('rule')!r} for {finding['entity_id']!r} "
				f"uses unsupported severity={severity!r}."
			)
		return mapping[severity]

	def _entity_exists_in_scope(self, dir, finding):
		if finding['entity_type'] == 'COLLECTION':
			return dir.getCollectionById(finding['entity_id']) is not None
		if finding['entity_type'] == 'BIOBANK':
			return dir.getBiobankById(finding['entity_id']) is not None
		return False

	def _resolve_nn(self, dir, finding):
		if finding.get('nn'):
			return finding['nn']
		if finding['entity_type'] == 'BIOBANK':
			return dir.getBiobankNN(finding['entity_id'])
		return dir.getCollectionNN(finding['entity_id'])
