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
    """Describe a stale or incompatible AI cache payload.

    Attributes:
        path: Repository JSON file whose cache record was rejected or is stale.
        rule: AI rule named by the payload, or inferred from its first finding.
        withdrawn_scope: Scope recorded in the payload when it was generated.
        reason: Stable machine-readable reason for invalidating the payload subset.
        entity_ids: Sorted immutable IDs affected by the issue, when applicable.
    """

    path: Path
    rule: str
    withdrawn_scope: str
    reason: str
    entity_ids: tuple[str, ...]


@dataclass(frozen=True)
class AICacheLoadResult:
    """Return AI findings together with cache validation issues.

    Attributes:
        findings: Reusable finding mappings owned by the returned list.
        issues: Scope or checksum validation issues owned by the returned list.
    """

    findings: list[dict[str, Any]]
    issues: list[AICacheIssue]


@dataclass(frozen=True)
class AICachePayload:
    """Validated payload loaded from one AI cache JSON file.

    Attributes:
        path: JSON source file from which this payload was read.
        data: Normalized payload mapping returned by the validation model.
        findings: Normalized findings contained in `data`; the list is shared with it.
    """

    path: Path
    data: dict[str, Any]
    findings: list[dict[str, Any]]


def get_ai_cache_paths(schema: str) -> list[Path]:
    """Return JSON cache files for a schema, ordered by filename.

    Args:
        schema: Exact schema directory name below the repository AI-cache root.

    Returns:
        Existing regular `*.json` paths in lexicographic filename order; an empty
        list when the schema directory does not exist.
    """
    schema_dir = AI_CACHE_ROOT / schema
    if not schema_dir.exists():
        return []
    return sorted(path for path in schema_dir.glob("*.json") if path.is_file())


def get_withdrawn_scope_label(directory: Any) -> str:
    """Return the normalized withdrawn-scope label for a Directory-like object.

    Args:
        directory: Directory-like object whose ``only_withdrawn_entities`` and
            ``include_withdrawn_entities`` flags are inspected defensively.

    Returns:
        One of `only-withdrawn`, `include-withdrawn`, or `active-only`, with the
        only-withdrawn flag taking precedence.
    """
    if bool(getattr(directory, "only_withdrawn_entities", False)):
        return "only-withdrawn"
    if bool(getattr(directory, "include_withdrawn_entities", False)):
        return "include-withdrawn"
    return "active-only"


def load_ai_findings(schema: str, *, warn=None) -> list[dict[str, Any]]:
    """Load and validate AI-curated findings for one schema.

    Args:
        schema: Cache schema directory to load.
        warn: Optional callback receiving one message for malformed JSON or a
            payload validation error; no warning is emitted when it is `None`.

    Returns:
        A newly assembled list of normalized findings from every valid payload.
    """
    findings: list[dict[str, Any]] = []
    for payload in load_ai_payloads(schema, warn=warn):
        findings.extend(payload.findings)
    return findings


def load_ai_findings_for_directory(directory: Any, *, warn=None) -> AICacheLoadResult:
    """Load AI findings and keep only records whose cached source data still matches.

    Args:
        directory: Directory-like object supplying schema, current scoped entities,
            and optionally an immutable checksum snapshot.
        warn: Optional callback passed to payload loading for non-fatal file errors.

    Returns:
        Reusable normalized findings and all detected scope/checksum issues. Stale
        entities are excluded from findings but remain represented by issues.
    """
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
    """Load validated AI cache payloads for one schema.

    Args:
        schema: Cache schema directory to scan.
        warn: Optional callback for invalid JSON or `ValidationError` details.

    Returns:
        Validated payload objects in path order. Invalid files are skipped rather
        than aborting the load.
    """
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
    """Return a stable checksum for an entity, excluding runtime metadata.

    Args:
        entity: Entity mapping to hash without mutating it.

    Returns:
        SHA-256 hex digest of the canonicalized entity, excluding timestamp and
        `mg_` metadata keys.
    """
    return compute_checksum(entity)


def compute_source_checksum(
    entity_type: str,
    entity: dict[str, Any],
    fields: Iterable[str],
) -> str:
    """Return a stable checksum for the source fields used by one AI rule.

    Args:
        entity_type: Entity family expected by qualified field names.
        entity: Entity mapping from which configured source values are projected.
        fields: Plain or `ENTITY.field` field specifications to include.

    Returns:
        SHA-256 hex digest of the projected source values.

    Raises:
        ValueError: If a qualified field belongs to another entity type.
    """
    source_projection = {
        field: _extract_field_value(entity_type, entity, field) for field in fields
    }
    return compute_checksum(source_projection)


def compute_checksum(value: Any) -> str:
    """Return a stable checksum for nested data structures.

    Args:
        value: JSON-like value to canonicalize and hash; it is never mutated.

    Returns:
        Deterministic SHA-256 hex digest. Mapping keys and list items are ordered
        canonically before JSON serialization.
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
    """Validate one cache payload and return its normalized representation.

    Args:
        path: Source JSON path retained in the returned object.
        payload: Decoded JSON value to validate and normalize.

    Returns:
        Payload object containing the model's normalized mapping and its findings.

    Raises:
        ValidationError: If the payload does not satisfy the cache schema.
    """
    model = AICachePayloadModel.parse_obj(payload)
    normalized_payload = model.dict()
    findings = normalized_payload["findings"]
    return AICachePayload(path=path, data=normalized_payload, findings=findings)


def _validate_payload_against_directory(
    payload: AICachePayload,
    directory: Any,
) -> tuple[list[dict[str, Any]], list[AICacheIssue]]:
    """Return reusable findings plus script-level cache issues for one payload.

    Args:
        payload: Previously validated cache payload to compare with live scope.
        directory: Directory-like object used to retrieve current entities and,
            where supported, checksum snapshot entities.

    Returns:
        Newly allocated `(findings, issues)` lists. Findings for added, removed,
        or changed entities are excluded; a scope mismatch is reported but does
        not itself remove findings.
    """
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
    """Return current Directory entities for the given entity type and scope.

    Args:
        directory: Directory-like object providing scoped biobank/collection reads.
        entity_type: Supported cache entity family, `BIOBANK` or `COLLECTION`.

    Returns:
        A new list copied from the matching Directory iterator.

    Raises:
        ValueError: If `entity_type` is unsupported by the AI cache.
    """
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
    """Return the immutable checksum basis for one entity when available.

    Args:
        directory: Directory-like object that may expose `get_ai_checksum_entity`.
        entity_type: Entity family supplied to that optional getter.
        entity_id: Entity ID supplied to that optional getter.
        fallback_entity: Current scoped entity returned when no snapshot is available.

    Returns:
        Snapshot mapping when the optional getter returns one; otherwise the exact
        `fallback_entity` object without copying it.
    """
    getter = getattr(directory, "get_ai_checksum_entity", None)
    if getter is None:
        return fallback_entity
    checksum_entity = getter(entity_type, entity_id)
    if checksum_entity is None:
        return fallback_entity
    return checksum_entity


def _infer_rule_from_payload(findings: list[dict[str, Any]]) -> str:
    """Infer the rule name for legacy payloads lacking top-level metadata.

    Args:
        findings: Normalized finding mappings from a legacy cache payload.

    Returns:
        First finding's `rule` coerced to text, or `Unknown` for an empty list.
    """
    if not findings:
        return "Unknown"
    return str(findings[0].get("rule", "Unknown"))


def _extract_field_value(entity_type: str, entity: dict[str, Any], field: str) -> Any:
    """Extract a local entity field using `ENTITY.field` or plain `field` syntax.

    Args:
        entity_type: Entity family against which a qualified field prefix is checked.
        entity: Mapping read without mutation.
        field: Plain key or `ENTITY.key` qualified source-field specification.

    Returns:
        Field value from `entity`, or `None` when the unqualified key is absent.

    Raises:
        ValueError: If a nonempty qualifier differs from `entity_type`.
    """
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
    """Return a stable, timestamp-free representation for hashing.

    Args:
        value: JSON-like value to transform without mutating its containers.

    Returns:
        Canonical nested value with ignored metadata removed from mappings and
        list items sorted by their canonical JSON representation.
    """
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
    """Return whether a dict key should be ignored for checksum purposes.

    Args:
        key: Mapping key considered during checksum canonicalization.

    Returns:
        `True` for configured timestamps and all `mg_` runtime metadata keys.
    """
    return key in TIMESTAMP_KEYS or key.startswith("mg_")
