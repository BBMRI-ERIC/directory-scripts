# vim:ts=8:sw=8:tw=0:noet

"""Expose curated AI-reviewed Directory findings as data-quality warnings."""

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
	"""Expose checksum-valid AI-reviewed cache findings as Directory warnings.

	The plugin reads shareable findings for entities in the active Directory scope, logs stale-cache diagnostics, and returns AI:Curated warnings. It never invokes a model or writes Directory data.
	"""
	CHECK_ID_PREFIX = 'AI'

	def check(self, dir, args):
		"""Load curated findings, discard entities outside the active scope, and return their warnings.

		Args:
		    dir: Loaded Directory view used to validate finding scope and derive National Node identifiers.
		    args: Runner options controlling whether validation diagnostics from the cache loader are suppressed.

		Returns:
		    AI:Curated warnings built from valid cached findings for visible entities; the Directory is not modified.
		"""
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
		"""Convert one validated cache finding into a Directory warning.

		Args:
		    dir: Loaded Directory view used to resolve a fallback National Node identifier.
		    finding: Validated cached finding containing entity, severity, message, action, and optional contact metadata.

		Returns:
		    An AI:Curated ``DataCheckWarning`` preserving the finding's entity, severity, withdrawal state, and evidence text.
		"""
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
		"""Prefix a cached finding message with its rule when one is present.

		Args:
		    finding: Cached finding containing a required message and optional rule identifier.

		Returns:
		    The original message, or a bracketed rule followed by that message.
		"""
		rule = finding.get('rule')
		message = finding['message']
		if not rule:
			return message
		return f"[{rule}] {message}"

	def _log_cache_issue(self, issue):
		"""Log an actionable diagnostic for one stale or incompatible AI cache record.

		Args:
		    issue: Cache issue describing its reason, source path, scope, rule, and affected entities.

		Returns:
		    None. A warning is emitted through the module logger; the cache is not changed.
		"""
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
		"""Map a supported cached entity-type token to the warning enum.

		Args:
		    finding: Cached finding whose ``entity_type`` must be BIOBANK or COLLECTION.

		Returns:
		    The corresponding ``DataCheckEntityType`` value.
		"""
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
		"""Map a supported cached severity token to the warning-level enum.

		Args:
		    finding: Cached finding whose ``severity`` must be ERROR, WARNING, or INFO.

		Returns:
		    The corresponding ``DataCheckWarningLevel`` value.
		"""
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
		"""Return whether a cached finding targets a visible supported entity.

		Args:
		    dir: Loaded Directory view whose configured scope determines entity visibility.
		    finding: Cached finding containing entity type and identifier.

		Returns:
		    ``True`` for a visible biobank or collection target; ``False`` for absent or unsupported targets.
		"""
		if finding['entity_type'] == 'COLLECTION':
			return dir.getCollectionById(finding['entity_id']) is not None
		if finding['entity_type'] == 'BIOBANK':
			return dir.getBiobankById(finding['entity_id']) is not None
		return False

	def _resolve_nn(self, dir, finding):
		"""Resolve the National Node stored on or implied by a cached finding.

		Args:
		    dir: Loaded Directory view used for entity-derived Node lookup.
		    finding: Cached finding with an optional explicit ``nn`` and required entity identity.

		Returns:
		    The explicit Node identifier when present, otherwise the Node derived from the target biobank or collection.
		"""
		if finding.get('nn'):
			return finding['nn']
		if finding['entity_type'] == 'BIOBANK':
			return dir.getBiobankNN(finding['entity_id'])
		return dir.getCollectionNN(finding['entity_id'])
