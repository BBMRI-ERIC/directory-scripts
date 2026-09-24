"""Structured QC-derived fix proposals and update-plan serialization."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from customwarnings import DataCheckEntityType, DataCheckWarning
from nncontacts import NNContacts


FIX_PLAN_FORMAT_VERSION = 1
APPLICABLE_CONFIDENCE_LEVELS = {"certain", "almost_certain", "uncertain"}
APPLICABLE_MODES = {"append", "replace", "set", "clear", "enable_flag", "disable_flag", "delete_rows"}


@dataclass
class EntityFixProposal:
    """One reviewable Directory update derived from one or more QC warnings.

    Attributes:
        update_id: Stable semantic identifier for the proposed operation.
        module: User-visible QC check-prefix family that produced the update.
        entity_type: Directory entity type name.
        entity_id: Directory identifier of the record to update.
        field: Directory field affected by the operation.
        mode: Apply mode such as ``append``, ``replace``, or ``delete_rows``.
        confidence: Review confidence: certain, almost_certain, or uncertain.
        current_value_at_export: Value observed when the plan was generated.
        proposed_value: Target value or row IDs supplied to the updater.
        human_explanation: Reviewer-facing explanation of the proposed change.
        rationale: Optional field-specific derivation rationale.
        expected_current_value: Value required at apply time; defaults to the
            exported value when omitted.
        term_explanations: Ontology term ID/label explanations for review.
        source_check_ids: Deduplicated check IDs that supplied this proposal.
        source_warning_messages: Deduplicated originating warning messages.
        source_warning_actions: Deduplicated originating warning actions.
        replace_required: Whether safe application requires explicit replacement.
        blocking_reason: Reason automated application must not proceed.
        exclusive_group: Mutually exclusive proposal group, if any.
        staging_area: Parsed node/staging-area prefix; inferred from entity ID
            when construction receives an empty value.
        update_checksum: SHA-256 integrity marker over every other field.
    """

    update_id: str
    module: str
    entity_type: str
    entity_id: str
    field: str
    mode: str
    confidence: str
    current_value_at_export: Any
    proposed_value: Any
    human_explanation: str
    rationale: str = ""
    expected_current_value: Any = None
    term_explanations: list[dict[str, str]] = field(default_factory=list)
    source_check_ids: list[str] = field(default_factory=list)
    source_warning_messages: list[str] = field(default_factory=list)
    source_warning_actions: list[str] = field(default_factory=list)
    replace_required: bool = False
    blocking_reason: str = ""
    exclusive_group: str = ""
    staging_area: str = ""
    update_checksum: str = ""

    def __post_init__(self) -> None:
        """Fill omitted apply-time expectation and staging-area metadata.

        Returns:
            None.

        Side Effects:
            Mutates this proposal. An absent ``expected_current_value`` is set
            to ``current_value_at_export`` and an empty ``staging_area`` is
            derived from ``entity_id``.
        """
        if self.expected_current_value is None:
            self.expected_current_value = self.current_value_at_export
        if not self.staging_area:
            self.staging_area = NNContacts.extract_staging_area(self.entity_id)

    def without_checksum(self) -> dict[str, Any]:
        """Return a deep dataclass serialization excluding the integrity field.

        Returns:
            A newly allocated dictionary suitable for checksum calculation. Its
            nested containers are produced by ``dataclasses.asdict`` and changes
            to it do not mutate this proposal.
        """
        payload = asdict(self)
        payload.pop("update_checksum", None)
        return payload

    def finalize_checksum(self) -> None:
        """Recompute this proposal's checksum from all non-checksum fields.

        Returns:
            None.

        Side Effects:
            Replaces ``update_checksum`` on this object. JSON-incompatible
            field values propagate the ``TypeError`` raised by serialization.
        """
        self.update_checksum = compute_checksum(self.without_checksum())

    def to_dict(self) -> dict[str, Any]:
        """Serialize this proposal, calculating a missing checksum first.

        Returns:
            A deep dataclass dictionary including ``update_checksum``.

        Side Effects:
            Mutates this proposal only when ``update_checksum`` is empty, by
            calculating and storing it before serialization.
        """
        if not self.update_checksum:
            self.finalize_checksum()
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EntityFixProposal":
        """Construct a proposal from a serialized proposal mapping.

        Args:
            payload: Mapping whose keys match the dataclass constructor. It is
                read without mutation.

        Returns:
            A new proposal, with normal post-initialization defaults applied.

        Raises:
            TypeError: If required fields are missing or unknown keys are present.
        """
        proposal = cls(**payload)
        return proposal


@dataclass
class FixPlanLoadResult:
    """Parsed update plan together with non-fatal checksum issues.

    Attributes:
        payload: Decoded update-plan JSON, including unvalidated user edits.
        issues: Advisory file- or update-checksum mismatch messages.
    """

    payload: dict[str, Any]
    issues: list[str]


def make_fix_proposal(**kwargs) -> EntityFixProposal:
    """Construct a proposal and immediately populate its checksum.

    Args:
        **kwargs: Keyword arguments accepted by ``EntityFixProposal``. Mutable
            values become fields of the newly created proposal.

    Returns:
        A new proposal whose ``update_checksum`` covers its current fields.

    Raises:
        TypeError: If the supplied keywords do not satisfy the dataclass
            constructor or cannot be JSON serialized for checksum creation.
    """
    proposal = EntityFixProposal(**kwargs)
    proposal.finalize_checksum()
    return proposal


def compute_checksum(payload: Any) -> str:
    """Hash a deterministic compact JSON representation with SHA-256.

    Args:
        payload: JSON-compatible value. Object keys are sorted; list ordering is
            preserved exactly.

    Returns:
        Lowercase hexadecimal SHA-256 digest of ASCII-escaped canonical JSON.

    Raises:
        TypeError: If ``payload`` contains a value unsupported by ``json.dumps``.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_json_value(value: Any) -> Any:
    """Recursively convert common containers to JSON-safe primitive values.

    Args:
        value: Value to normalize. Dictionaries have stringified keys; tuples
            and sets become lists, while unsupported scalars become ``str``.

    Returns:
        A new normalized container or an unchanged primitive. Set iteration order
        is intentionally not stabilized, so callers needing reproducible hashes
        must avoid sets or sort them first.
    """
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): normalize_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [normalize_json_value(item) for item in value]
    return str(value)


def attach_warning_context(proposal: EntityFixProposal, warning: DataCheckWarning) -> EntityFixProposal:
    """Merge one warning's provenance and missing entity context into a proposal.

    Args:
        proposal: Proposal to enrich in place.
        warning: Source warning supplying check ID, message, action, and missing
            entity metadata. It is read without mutation.

    Returns:
        The same ``proposal`` object after deduplicating provenance and refreshing
        its checksum.

    Side Effects:
        Appends missing source fields, fills an empty entity type/ID/staging area,
        and replaces ``proposal.update_checksum``.
    """
    if warning.dataCheckID not in proposal.source_check_ids:
        proposal.source_check_ids.append(warning.dataCheckID)
    if warning.message and warning.message not in proposal.source_warning_messages:
        proposal.source_warning_messages.append(warning.message)
    if warning.action and warning.action not in proposal.source_warning_actions:
        proposal.source_warning_actions.append(warning.action)
    if not proposal.entity_type:
        if isinstance(warning.directoryEntityType, DataCheckEntityType):
            proposal.entity_type = warning.directoryEntityType.name
        else:
            proposal.entity_type = str(warning.directoryEntityType)
    if not proposal.entity_id:
        proposal.entity_id = warning.directoryEntityID
    if not proposal.staging_area:
        proposal.staging_area = NNContacts.extract_staging_area(proposal.entity_id)
    proposal.finalize_checksum()
    return proposal


def _proposal_merge_key(proposal: EntityFixProposal) -> tuple[Any, ...]:
    """Return the identity tuple used to coalesce equivalent proposals.

    Args:
        proposal: Proposal whose non-provenance update semantics form the key.

    Returns:
        Tuple containing target fields, normalized JSON strings for values, and
        replacement/blocking/exclusivity constraints; provenance is excluded.
    """
    payload = proposal.without_checksum()
    return (
        payload["update_id"],
        payload["module"],
        payload["entity_type"],
        payload["entity_id"],
        payload["field"],
        payload["mode"],
        payload["confidence"],
        json.dumps(payload["current_value_at_export"], sort_keys=True, ensure_ascii=True),
        json.dumps(payload["expected_current_value"], sort_keys=True, ensure_ascii=True),
        json.dumps(payload["proposed_value"], sort_keys=True, ensure_ascii=True),
        payload["replace_required"],
        payload["blocking_reason"],
        payload["exclusive_group"],
    )


def _merge_term_explanations(left: list[dict[str, str]], right: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    """Append term explanations not already matched by ID and label.

    Args:
        left: Existing explanations; it is read but not mutated.
        right: Additional explanations consumed in iteration order.

    Returns:
        New list retaining ``left`` order and copying each accepted mapping from
        ``right``. Duplicate keys are compared only by ``term_id`` and ``label``.
    """
    seen = {(item.get("term_id"), item.get("label")) for item in left}
    merged = list(left)
    for item in right:
        key = (item.get("term_id"), item.get("label"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(item))
    return merged


def _is_entity_suppressed(
    suppressions: dict[str, dict[str, str]] | None,
    check_id: str,
    entity_id: str,
) -> bool:
    """Test whether one check/update key suppresses one entity.

    Args:
        suppressions: Optional check-key mapping with entity-ID dictionaries or
            legacy sets.
        check_id: Source check or update identifier to look up.
        entity_id: Directory entity identifier to test.

    Returns:
        ``True`` only when the identifier occurs under the requested key.
    """
    if not suppressions:
        return False
    check_suppressions = suppressions.get(check_id, {})
    if isinstance(check_suppressions, set):
        return entity_id in check_suppressions
    return entity_id in check_suppressions


def _is_proposal_suppressed(
    proposal: EntityFixProposal,
    suppressions: dict[str, dict[str, str]] | None,
) -> bool:
    """Test proposal suppression by update ID, module/update ID, or source check.

    Args:
        proposal: Candidate proposal; read without mutation.
        suppressions: Optional entity suppression lookup.

    Returns:
        ``True`` if any supported key suppresses the proposal's entity.
    """
    if not suppressions:
        return False
    candidate_update_ids = [proposal.update_id]
    module_update_id = f"{proposal.module}/{proposal.update_id}" if proposal.module else proposal.update_id
    if module_update_id not in candidate_update_ids:
        candidate_update_ids.append(module_update_id)
    for candidate_update_id in candidate_update_ids:
        if _is_entity_suppressed(suppressions, candidate_update_id, proposal.entity_id):
            return True
    for source_check_id in proposal.source_check_ids:
        if _is_entity_suppressed(suppressions, source_check_id, proposal.entity_id):
            return True
    return False


def collect_fix_proposals(
    warnings: Iterable[DataCheckWarning],
    suppressions: dict[str, dict[str, str]] | None = None,
) -> list[EntityFixProposal]:
    """Collect unsuppressed warning proposals and merge equivalent updates.

    Args:
        warnings: Warnings whose ``fix_proposals`` may contain proposal objects
            or serialized mappings. The iterable is consumed once.
        suppressions: Optional lookup for source-check and update-ID exclusions.

    Returns:
        First-seen-order proposals after semantic deduplication. Matching updates
        combine provenance and distinct term explanations.

    Side Effects:
        Existing ``EntityFixProposal`` instances stored on warnings are enriched
        in place with warning context and refreshed checksums; dictionary inputs
        instead create new proposal instances.
    """
    merged: dict[tuple[Any, ...], EntityFixProposal] = {}
    for warning in warnings:
        for raw_proposal in getattr(warning, "fix_proposals", []) or []:
            proposal = raw_proposal if isinstance(raw_proposal, EntityFixProposal) else EntityFixProposal.from_dict(raw_proposal)
            proposal = attach_warning_context(proposal, warning)
            if _is_proposal_suppressed(proposal, suppressions):
                continue
            key = _proposal_merge_key(proposal)
            existing = merged.get(key)
            if existing is None:
                merged[key] = proposal
                continue
            for check_id in proposal.source_check_ids:
                if check_id not in existing.source_check_ids:
                    existing.source_check_ids.append(check_id)
            for message in proposal.source_warning_messages:
                if message not in existing.source_warning_messages:
                    existing.source_warning_messages.append(message)
            for action in proposal.source_warning_actions:
                if action not in existing.source_warning_actions:
                    existing.source_warning_actions.append(action)
            existing.term_explanations = _merge_term_explanations(
                existing.term_explanations,
                proposal.term_explanations,
            )
            existing.finalize_checksum()
    return list(merged.values())


def build_fix_plan_payload(
    warnings: Iterable[DataCheckWarning],
    *,
    schema: str,
    include_withdrawn: bool,
    only_withdrawn: bool,
    suppressions: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a timestamped, checksummed JSON-ready QC update plan.

    Args:
        warnings: Source warning iterable, consumed once by proposal collection.
        schema: Directory schema recorded in ``generated_by``.
        include_withdrawn: Records that the source run included withdrawn data.
        only_withdrawn: Takes precedence when selecting the recorded withdrawn
            scope label.
        suppressions: Optional proposal suppression lookup.

    Returns:
        New format-version-1 payload with UTC generation time, sorted serialized
        updates, and a file checksum excluding the checksum field itself.

    Side Effects:
        May enrich/checksum proposal objects carried by ``warnings`` as described
        by ``collect_fix_proposals``.
    """
    updates = [
        proposal.to_dict()
        for proposal in sorted(
            collect_fix_proposals(warnings, suppressions=suppressions),
            key=lambda item: (item.entity_id, item.module, item.field, item.update_id),
        )
    ]
    payload = {
        "format_version": FIX_PLAN_FORMAT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": {
            "tool": "data-check.py",
            "schema": schema,
            "withdrawn_scope": (
                "only-withdrawn"
                if only_withdrawn
                else ("include-withdrawn" if include_withdrawn else "active-only")
            ),
        },
        "updates": updates,
    }
    payload["file_checksum"] = compute_checksum({key: value for key, value in payload.items() if key != "file_checksum"})
    return payload


def write_fix_plan(
    path: str | Path,
    warnings: Iterable[DataCheckWarning],
    *,
    schema: str,
    include_withdrawn: bool,
    only_withdrawn: bool,
    suppressions: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Build and directly write an indented QC update-plan JSON document.

    Args:
        path: Destination JSON path. Its parent must exist; any existing file is
            overwritten directly.
        warnings: Source warnings consumed to build the plan.
        schema: Schema recorded in the generated payload.
        include_withdrawn: Source-run withdrawn inclusion flag.
        only_withdrawn: Source-run withdrawn-only flag.
        suppressions: Optional proposal suppression lookup.

    Returns:
        The newly built payload after the write call succeeds.

    Raises:
        OSError: If the direct, non-atomic write cannot open or finish writing
            the destination; a failure can leave a partial or truncated file.
    """
    payload = build_fix_plan_payload(
        warnings,
        schema=schema,
        include_withdrawn=include_withdrawn,
        only_withdrawn=only_withdrawn,
        suppressions=suppressions,
    )
    output_path = Path(path)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def load_fix_plan(path: str | Path) -> FixPlanLoadResult:
    """Read an update plan and report checksum mismatches without rejecting it.

    Args:
        path: JSON file to read. The payload is not schema-validated or mutated.

    Returns:
        Decoded payload plus advisory file and per-update checksum mismatches.

    Raises:
        OSError: If the path cannot be read.
        json.JSONDecodeError: If the file is not valid JSON.
        AttributeError: If decoded JSON is not an object supporting ``get``.
    """
    plan_path = Path(path)
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    issues = []
    expected_file_checksum = payload.get("file_checksum", "")
    actual_file_checksum = compute_checksum({key: value for key, value in payload.items() if key != "file_checksum"})
    if expected_file_checksum and expected_file_checksum != actual_file_checksum:
        issues.append(f"Update-plan file checksum mismatch for {plan_path}.")

    for update in payload.get("updates", []):
        expected_update_checksum = update.get("update_checksum", "")
        actual_update_checksum = compute_checksum({key: value for key, value in update.items() if key != "update_checksum"})
        if expected_update_checksum and expected_update_checksum != actual_update_checksum:
            issues.append(
                f"Update checksum mismatch for {update.get('update_id')} on {update.get('entity_id')}."
            )
    return FixPlanLoadResult(payload=payload, issues=issues)
