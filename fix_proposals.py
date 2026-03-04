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
APPLICABLE_MODES = {"append", "replace", "set", "clear", "enable_flag", "disable_flag"}


@dataclass
class EntityFixProposal:
    """Structured fix proposal attached to a QC warning."""

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
        if self.expected_current_value is None:
            self.expected_current_value = self.current_value_at_export
        if not self.staging_area:
            self.staging_area = NNContacts.extract_staging_area(self.entity_id)

    def without_checksum(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("update_checksum", None)
        return payload

    def finalize_checksum(self) -> None:
        self.update_checksum = compute_checksum(self.without_checksum())

    def to_dict(self) -> dict[str, Any]:
        if not self.update_checksum:
            self.finalize_checksum()
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EntityFixProposal":
        proposal = cls(**payload)
        return proposal


@dataclass
class FixPlanLoadResult:
    """Parsed update plan together with non-fatal checksum issues."""

    payload: dict[str, Any]
    issues: list[str]


def make_fix_proposal(**kwargs) -> EntityFixProposal:
    """Return a normalized fix proposal."""
    proposal = EntityFixProposal(**kwargs)
    proposal.finalize_checksum()
    return proposal


def compute_checksum(payload: Any) -> str:
    """Return a deterministic SHA-256 checksum for JSON-compatible data."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_json_value(value: Any) -> Any:
    """Return a JSON-safe value for fix-plan serialization."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): normalize_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [normalize_json_value(item) for item in value]
    return str(value)


def attach_warning_context(proposal: EntityFixProposal, warning: DataCheckWarning) -> EntityFixProposal:
    """Return a proposal enriched with its originating warning context."""
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
    seen = {(item.get("term_id"), item.get("label")) for item in left}
    merged = list(left)
    for item in right:
        key = (item.get("term_id"), item.get("label"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(item))
    return merged


def collect_fix_proposals(warnings: Iterable[DataCheckWarning]) -> list[EntityFixProposal]:
    """Return deduplicated fix proposals collected from warnings."""
    merged: dict[tuple[Any, ...], EntityFixProposal] = {}
    for warning in warnings:
        for raw_proposal in getattr(warning, "fix_proposals", []) or []:
            proposal = raw_proposal if isinstance(raw_proposal, EntityFixProposal) else EntityFixProposal.from_dict(raw_proposal)
            proposal = attach_warning_context(proposal, warning)
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


def build_fix_plan_payload(warnings: Iterable[DataCheckWarning], *, schema: str, include_withdrawn: bool, only_withdrawn: bool) -> dict[str, Any]:
    """Return an exported fix-plan payload for the provided warnings."""
    updates = [
        proposal.to_dict()
        for proposal in sorted(
            collect_fix_proposals(warnings),
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


def write_fix_plan(path: str | Path, warnings: Iterable[DataCheckWarning], *, schema: str, include_withdrawn: bool, only_withdrawn: bool) -> dict[str, Any]:
    """Serialize a fix plan to disk and return the written payload."""
    payload = build_fix_plan_payload(
        warnings,
        schema=schema,
        include_withdrawn=include_withdrawn,
        only_withdrawn=only_withdrawn,
    )
    output_path = Path(path)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def load_fix_plan(path: str | Path) -> FixPlanLoadResult:
    """Load a fix plan and return checksum issues as non-fatal warnings."""
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
