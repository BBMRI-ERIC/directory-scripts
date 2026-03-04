# vim:ts=4:sw=4:tw=0:sts=4:et

"""Helpers for loading shareable AI-curated findings from the repository."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from validation_helpers import warn_from_validation_error
from validation_models import AICachePayloadModel, ValidationError


AI_CACHE_ROOT = Path(__file__).resolve().parent / "ai-check-cache"
TIMESTAMP_KEYS = {"timestamp", "mg_insertedOn", "mg_updatedOn"}


@dataclass(frozen=True)
class AICacheIssue:
    """Describe a stale or incompatible AI cache payload."""

    path: Path
    rule: str
    withdrawn_scope: str
    reason: str
    entity_ids: tuple[str, ...]


@dataclass(frozen=True)
class AICacheLoadResult:
    """Return AI findings together with cache validation issues."""

    findings: list[dict[str, Any]]
    issues: list[AICacheIssue]


@dataclass(frozen=True)
class AICachePayload:
    """Validated payload loaded from one AI cache JSON file."""

    path: Path
    data: dict[str, Any]
    findings: list[dict[str, Any]]


def get_ai_cache_paths(schema: str) -> list[Path]:
    """Return JSON cache files for a schema, ordered by filename."""
    schema_dir = AI_CACHE_ROOT / schema
    if not schema_dir.exists():
        return []
    return sorted(path for path in schema_dir.glob("*.json") if path.is_file())


def get_withdrawn_scope_label(directory: Any) -> str:
    """Return the normalized withdrawn-scope label for a Directory-like object."""
    if bool(getattr(directory, "only_withdrawn_entities", False)):
        return "only-withdrawn"
    if bool(getattr(directory, "include_withdrawn_entities", False)):
        return "include-withdrawn"
    return "active-only"


def load_ai_findings(schema: str, *, warn=None) -> list[dict[str, Any]]:
    """Load and validate AI-curated findings for one schema."""
    findings: list[dict[str, Any]] = []
    for payload in load_ai_payloads(schema, warn=warn):
        findings.extend(payload.findings)
    return findings


def load_ai_findings_for_directory(directory: Any, *, warn=None) -> AICacheLoadResult:
    """Load AI findings and keep only records whose cached source data still matches."""
    if hasattr(directory, "prepare_ai_cache_checksum_state"):
        directory.prepare_ai_cache_checksum_state()
    findings: list[dict[str, Any]] = []
    issues: list[AICacheIssue] = []
    for payload in load_ai_payloads(directory.getSchema(), warn=warn):
        reusable_records, payload_issues = _validate_payload_against_directory(
            payload, directory
        )
        findings.extend(reusable_records)
        issues.extend(payload_issues)
    return AICacheLoadResult(findings=findings, issues=issues)


def load_ai_payloads(schema: str, *, warn=None) -> list[AICachePayload]:
    """Load validated AI cache payloads for one schema."""
    payloads: list[AICachePayload] = []
    for path in get_ai_cache_paths(schema):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            if warn is not None:
                warn(f"{path}: invalid JSON: {exc}")
            continue
        try:
            payloads.append(_validate_payload(path, payload))
        except ValidationError as exc:
            warn_from_validation_error(str(path), exc, warn)
    return payloads


def compute_entity_checksum(entity: dict[str, Any]) -> str:
    """Return a stable checksum for an entity, excluding runtime metadata."""
    return compute_checksum(entity)


def compute_source_checksum(
    entity_type: str,
    entity: dict[str, Any],
    fields: Iterable[str],
) -> str:
    """Return a stable checksum for the source fields used by one AI rule."""
    source_projection = {
        field: _extract_field_value(entity_type, entity, field) for field in fields
    }
    return compute_checksum(source_projection)


def compute_checksum(value: Any) -> str:
    """Return a stable checksum for nested data structures.

    Timestamps and `mg_*` runtime metadata are excluded so that pure update-metadata
    changes do not invalidate the AI cache.
    """
    canonical = _canonicalize(value)
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_payload(path: Path, payload: Any) -> AICachePayload:
    """Validate one cache payload and return its normalized representation."""
    model = AICachePayloadModel.parse_obj(payload)
    normalized_payload = model.dict()
    findings = normalized_payload["findings"]
    return AICachePayload(path=path, data=normalized_payload, findings=findings)


def _validate_payload_against_directory(
    payload: AICachePayload,
    directory: Any,
) -> tuple[list[dict[str, Any]], list[AICacheIssue]]:
    """Return reusable findings plus script-level cache issues for one payload."""
    issues: list[AICacheIssue] = []
    reusable_findings = list(payload.findings)
    expected_scope = payload.data.get("withdrawn_scope", "active-only")
    current_scope = get_withdrawn_scope_label(directory)
    rule = str(payload.data.get("rule") or _infer_rule_from_payload(payload.findings))
    checked_fields = payload.data.get("checked_fields", [])
    checked_entities = payload.data.get("checked_entities", [])

    if expected_scope != current_scope:
        issues.append(
            AICacheIssue(
                path=payload.path,
                rule=rule,
                withdrawn_scope=expected_scope,
                reason="scope-mismatch",
                entity_ids=(),
            )
        )

    if not checked_entities or not checked_fields:
        issues.append(
            AICacheIssue(
                path=payload.path,
                rule=rule,
                withdrawn_scope=expected_scope,
                reason="missing-checksums",
                entity_ids=(),
            )
        )
        return reusable_findings, issues

    entity_type = checked_entities[0]["entity_type"]
    current_entities = _get_entities_in_scope(directory, entity_type)
    current_by_id = {entity["id"]: entity for entity in current_entities}
    checked_by_id = {record["entity_id"]: record for record in checked_entities}

    stale_ids: set[str] = set()
    added_ids = sorted(set(current_by_id) - set(checked_by_id))
    removed_ids = sorted(set(checked_by_id) - set(current_by_id))
    if added_ids:
        stale_ids.update(added_ids)
        issues.append(
            AICacheIssue(
                path=payload.path,
                rule=rule,
                withdrawn_scope=expected_scope,
                reason="new-entities",
                entity_ids=tuple(added_ids),
            )
        )
    if removed_ids:
        stale_ids.update(removed_ids)
        issues.append(
            AICacheIssue(
                path=payload.path,
                rule=rule,
                withdrawn_scope=expected_scope,
                reason="removed-entities",
                entity_ids=tuple(removed_ids),
            )
        )

    changed_ids: list[str] = []
    for entity_id in sorted(set(current_by_id) & set(checked_by_id)):
        entity = _get_checksum_entity(directory, entity_type, entity_id, current_by_id[entity_id])
        expected = checked_by_id[entity_id]
        current_entity_checksum = compute_entity_checksum(entity)
        current_source_checksum = compute_source_checksum(entity_type, entity, checked_fields)
        if (
            current_entity_checksum != expected["entity_checksum"]
            or current_source_checksum != expected["source_checksum"]
        ):
            stale_ids.add(entity_id)
            changed_ids.append(entity_id)
    if changed_ids:
        issues.append(
            AICacheIssue(
                path=payload.path,
                rule=rule,
                withdrawn_scope=expected_scope,
                reason="changed-entities",
                entity_ids=tuple(changed_ids),
            )
        )

    if stale_ids:
        reusable_findings = [
            finding
            for finding in reusable_findings
            if finding["entity_id"] not in stale_ids
        ]
    return reusable_findings, issues


def _get_entities_in_scope(directory: Any, entity_type: str) -> list[dict[str, Any]]:
    """Return current Directory entities for the given entity type and scope."""
    if entity_type == "BIOBANK":
        return list(directory.getBiobanks())
    if entity_type == "COLLECTION":
        return list(directory.getCollections())
    raise ValueError(f"Unsupported AI cache entity_type {entity_type!r}.")


def _get_checksum_entity(
    directory: Any,
    entity_type: str,
    entity_id: str,
    fallback_entity: dict[str, Any],
) -> dict[str, Any]:
    """Return the immutable checksum basis for one entity when available."""
    getter = getattr(directory, "get_ai_checksum_entity", None)
    if getter is None:
        return fallback_entity
    checksum_entity = getter(entity_type, entity_id)
    if checksum_entity is None:
        return fallback_entity
    return checksum_entity


def _infer_rule_from_payload(findings: list[dict[str, Any]]) -> str:
    """Infer the rule name for legacy payloads lacking top-level metadata."""
    if not findings:
        return "Unknown"
    return str(findings[0].get("rule", "Unknown"))


def _extract_field_value(entity_type: str, entity: dict[str, Any], field: str) -> Any:
    """Extract a local entity field using `ENTITY.field` or plain `field` syntax."""
    if "." in field:
        prefix, field_name = field.split(".", 1)
        if prefix and prefix != entity_type:
            raise ValueError(
                f"Field {field!r} does not belong to entity type {entity_type!r}."
            )
    else:
        field_name = field
    return entity.get(field_name)


def _canonicalize(value: Any) -> Any:
    """Return a stable, timestamp-free representation for hashing."""
    if isinstance(value, dict):
        normalized = {}
        for key in sorted(value):
            if _should_ignore_checksum_key(key):
                continue
            normalized[key] = _canonicalize(value[key])
        return normalized
    if isinstance(value, list):
        canonical_items = [_canonicalize(item) for item in value]
        return sorted(
            canonical_items,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        )
    return value


def _should_ignore_checksum_key(key: str) -> bool:
    """Return whether a dict key should be ignored for checksum purposes."""
    return key in TIMESTAMP_KEYS or key.startswith("mg_")
