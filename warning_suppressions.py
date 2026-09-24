"""Load and normalize check-warning suppressions from JSON."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import logging
from pathlib import Path
from typing import Any

from validation_helpers import warn_from_validation_error
from validation_models import ValidationError, WarningSuppressionEntryModel

DEFAULT_WARNING_SUPPRESSIONS_PATH = Path(__file__).resolve().parent / "warning-suppressions.json"


@dataclass
class WarningSuppressionLoadResult:
    """Normalized suppression configuration and recoverable load diagnostics.

    Attributes:
        suppressions: Legacy alias for ``warning_suppressions``; maps check IDs
            to entity IDs and their stored reasons.
        warning_suppressions: Entries enabled for warning suppression, keyed by
            check ID then entity ID.
        fix_suppressions: Entries enabled for fix-proposal suppression, keyed
            by check ID then entity ID.
        entries: Validated v2 records, including records that suppress only
            fixes or only warnings.
        issues: Non-fatal file-level JSON or payload-shape errors. Per-record
            validation errors are reported through the optional warning callback.
    """

    suppressions: dict[str, dict[str, str]]
    warning_suppressions: dict[str, dict[str, str]]
    fix_suppressions: dict[str, dict[str, str]]
    entries: list[WarningSuppressionEntryModel]
    issues: list[str]


def serialize_suppression_entries(entries: list[WarningSuppressionEntryModel]) -> dict[str, Any]:
    """Build the canonical version-2 JSON payload for suppression entries.

    Args:
        entries: Validated records to serialize. The list and its records are
            read-only to this function; records are emitted sorted by check ID
            and entity ID.

    Returns:
        A newly allocated ``{"version": 2, "suppressions": [...]}`` mapping.
        Optional false/empty fields are omitted except explicit false suppression
        flags; each record's ``extras`` is copied last and can add keys.
    """
    serialized = []
    for entry in sorted(entries, key=lambda item: (item.check_id, item.entity_id)):
        payload: dict[str, Any] = {
            "check_id": entry.check_id,
            "entity_id": entry.entity_id,
        }
        if entry.entity_type:
            payload["entity_type"] = entry.entity_type
        if not entry.suppress_warning:
            payload["suppress_warning"] = False
        if not entry.suppress_fix:
            payload["suppress_fix"] = False
        if entry.reason:
            payload["reason"] = entry.reason
        if entry.added_by:
            payload["added_by"] = entry.added_by
        if entry.added_on:
            payload["added_on"] = entry.added_on
        if entry.expires_on:
            payload["expires_on"] = entry.expires_on
        if entry.ticket:
            payload["ticket"] = entry.ticket
        payload.update(entry.extras)
        serialized.append(payload)
    return {"version": 2, "suppressions": serialized}


def write_suppression_entries(path: str | Path, entries: list[WarningSuppressionEntryModel]) -> None:
    """Serialize suppression entries as indented canonical JSON at ``path``.

    Args:
        path: Destination file. Its parent directory must already exist.
            An existing file is truncated and replaced in place.
        entries: Validated records passed to ``serialize_suppression_entries``;
            they are not mutated.

    Returns:
        None.

    Raises:
        OSError: If the destination cannot be opened or written. The write is
            direct rather than atomic, so a failure can leave a partial file.
    """
    payload = serialize_suppression_entries(entries)
    output_path = Path(path)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_warning_suppressions(
    path: str | Path | None,
    *,
    warn=None,
) -> dict[str, dict[str, str]]:
    """Load only warning-enabled suppression mappings from a JSON file.

    Args:
        path: JSON path, or ``None`` to disable suppression loading.
        warn: Optional callable receiving recoverable parse or record-validation
            messages.

    Returns:
        A ``check_id -> entity_id -> reason`` mapping. Missing paths, ``None``,
        invalid JSON, and invalid top-level payloads yield an empty mapping.

    Raises:
        OSError: If an existing file cannot be read.
    """
    return load_warning_suppressions_detailed(path, warn=warn).warning_suppressions


def load_warning_suppressions_detailed(
    path: str | Path | None,
    *,
    warn=None,
) -> WarningSuppressionLoadResult:
    """Load, validate, and partition legacy or v2 warning suppressions.

    Args:
        path: JSON path, or ``None`` to return an empty result without file I/O.
        warn: Optional callable invoked for invalid JSON, invalid payload shape,
            and invalid individual records.

    Returns:
        Normalized v2 entries plus warning and fix lookup maps. Missing paths
        and file-level parse/shape errors return empty maps; the latter are also
        recorded in ``issues``.

    Raises:
        OSError: If an existing path cannot be opened for reading.
    """
    if path is None:
        return WarningSuppressionLoadResult(
            suppressions={},
            warning_suppressions={},
            fix_suppressions={},
            entries=[],
            issues=[],
        )
    config_path = Path(path)
    if not config_path.exists():
        logging.debug("Warning suppression file %s does not exist.", config_path)
        return WarningSuppressionLoadResult(
            suppressions={},
            warning_suppressions={},
            fix_suppressions={},
            entries=[],
            issues=[],
        )

    try:
        with config_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        message = f"{config_path}: invalid JSON: {exc}"
        if warn is not None:
            warn(message)
        return WarningSuppressionLoadResult(
            suppressions={},
            warning_suppressions={},
            fix_suppressions={},
            entries=[],
            issues=[message],
        )
    try:
        entries = _parse_suppressions_payload(payload, warn=warn, source=str(config_path))
    except ValueError as exc:
        message = f"{config_path}: {exc}"
        if warn is not None:
            warn(message)
        return WarningSuppressionLoadResult(
            suppressions={},
            warning_suppressions={},
            fix_suppressions={},
            entries=[],
            issues=[message],
        )
    warning_suppressions = _entries_to_suppression_map(entries, target="warning")
    fix_suppressions = _entries_to_suppression_map(entries, target="fix")
    logging.info(
        "Loaded %s warning suppression(s) across %s check ID(s) from %s.",
        sum(len(entities) for entities in warning_suppressions.values()),
        len(warning_suppressions),
        config_path,
    )
    return WarningSuppressionLoadResult(
        suppressions=warning_suppressions,
        warning_suppressions=warning_suppressions,
        fix_suppressions=fix_suppressions,
        entries=entries,
        issues=[],
    )


def summarize_suppression_diagnostics(
    entries: list[WarningSuppressionEntryModel],
    *,
    known_check_ids: set[str] | None = None,
    known_check_prefixes: set[str] | None = None,
    known_entities: dict[str, set[str]] | None = None,
    today_value: date | None = None,
) -> list[str]:
    """Diagnose stale suppression metadata without changing the entries.

    Args:
        entries: Validated suppression records to inspect; not mutated.
        known_check_ids: Complete check/update IDs currently known to the caller.
        known_check_prefixes: Accepted check families used when an exact ID is
            absent, including slash-separated update-plan IDs.
        known_entities: Optional entity IDs grouped by declared entity type.
        today_value: Date used for expiry comparisons; defaults to today.

    Returns:
        Human-readable diagnostics for unknown check families, invalid or expired
        dates, and stale typed or untyped entity IDs. Empty/omitted reference
        sets deliberately suppress the corresponding diagnostic.
    """
    diagnostics: list[str] = []
    check_ids = known_check_ids or set()
    check_prefixes = known_check_prefixes or set()
    entities_by_type = known_entities or {}
    today_value = today_value or date.today()

    known_all_entities = set()
    for entity_ids in entities_by_type.values():
        known_all_entities.update(entity_ids)

    for entry in entries:
        if entry.check_id not in check_ids:
            if ":" in entry.check_id:
                check_prefix = entry.check_id.split(":", 1)[0]
            elif "/" in entry.check_id:
                # Update-plan suppression keys may use module/update_id format.
                check_prefix = entry.check_id.split("/", 1)[0]
            else:
                check_prefix = entry.check_id
            if check_prefix not in check_prefixes:
                diagnostics.append(
                    f"Suppression {entry.check_id}::{entry.entity_id}: unknown check_id (no matching check prefix)."
                )
        if entry.expires_on:
            try:
                expiry = date.fromisoformat(entry.expires_on)
            except ValueError:
                diagnostics.append(
                    f"Suppression {entry.check_id}::{entry.entity_id}: invalid expires_on date {entry.expires_on!r}."
                )
            else:
                if expiry < today_value:
                    diagnostics.append(
                        f"Suppression {entry.check_id}::{entry.entity_id}: expired on {entry.expires_on}."
                    )
        if entry.entity_type:
            typed_ids = entities_by_type.get(entry.entity_type, set())
            if entry.entity_id not in typed_ids:
                diagnostics.append(
                    f"Suppression {entry.check_id}::{entry.entity_id}: entity_id not found for declared entity_type {entry.entity_type}."
                )
        elif known_all_entities and entry.entity_id not in known_all_entities:
            diagnostics.append(
                f"Suppression {entry.check_id}::{entry.entity_id}: entity_id not found in current schema."
            )
    return diagnostics


def _parse_suppressions_payload(
    payload: Any,
    *,
    warn=None,
    source: str = "warning suppressions",
) -> list[WarningSuppressionEntryModel]:
    """Parse a version-2 list payload or a supported legacy mapping.

    Args:
        payload: Decoded JSON value. False-y values mean no suppressions.
        warn: Optional callback for malformed individual records.
        source: Text prefix included in callbacks and exceptions.

    Returns:
        Newly constructed validated records, preserving supported input order.

    Raises:
        ValueError: If a truthy payload is neither an object nor an object with
            a list-compatible ``suppressions`` member.
    """
    if not payload:
        return []
    if isinstance(payload, dict) and "suppressions" in payload:
        return _parse_suppression_list(payload["suppressions"], warn=warn, source=source)
    if isinstance(payload, dict):
        return _parse_suppression_map(payload, warn=warn, source=source)
    raise ValueError("Warning suppressions must be a JSON object or contain a 'suppressions' list.")


def _parse_suppression_map(
    payload: dict[str, Any],
    *,
    warn=None,
    source: str,
) -> list[WarningSuppressionEntryModel]:
    """Convert legacy check-ID mappings into validated v2 records.

    Args:
        payload: Legacy ``check_id -> list|mapping`` JSON object.
        warn: Optional callback for unsupported values and invalid records.
        source: Text prefix for warning context.

    Returns:
        Validated records in mapping iteration order. List values become records
        with blank reasons; objects may share metadata and specify entities as a
        list or an entity-to-reason map.
    """
    entries: list[WarningSuppressionEntryModel] = []
    for check_id, value in payload.items():
        if isinstance(value, list):
            for entity_id in value:
                record = _validate_entry(
                    {"check_id": check_id, "entity_id": entity_id, "reason": ""},
                    context=f"{source}: {check_id}",
                    warn=warn,
                )
                if record is not None:
                    entries.append(record)
            continue
        if isinstance(value, dict):
            entities = value.get("entities", value)
            shared = {
                "entity_type": value.get("entity_type"),
                "reason": value.get("reason"),
                "added_by": value.get("added_by"),
                "added_on": value.get("added_on"),
                "expires_on": value.get("expires_on"),
                "ticket": value.get("ticket"),
            }
            if isinstance(entities, list):
                for entity_id in entities:
                    record = _validate_entry(
                        {"check_id": check_id, "entity_id": entity_id, **shared},
                        context=f"{source}: {check_id}",
                        warn=warn,
                    )
                    if record is not None:
                        entries.append(record)
                continue
            if isinstance(entities, dict):
                for entity_id, reason in entities.items():
                    effective_reason = reason if reason not in (None, "") else shared.get("reason")
                    record = _validate_entry(
                        {"check_id": check_id, "entity_id": entity_id, **shared, "reason": effective_reason},
                        context=f"{source}: {check_id}",
                        warn=warn,
                    )
                    if record is not None:
                        entries.append(record)
                continue
        if warn is not None:
            warn(
                f"{source}: unsupported suppression entry for {check_id!r}; "
                "expected a list or an object with 'entities'."
            )
        continue
    return entries


def _parse_suppression_list(items: Any, *, warn=None, source: str) -> list[WarningSuppressionEntryModel]:
    """Validate the v2 ``suppressions`` list while retaining valid records.

    Args:
        items: Candidate list of JSON-object records.
        warn: Optional callback for non-object or model-invalid items.
        source: Text prefix and list index context for callbacks.

    Returns:
        Newly validated records in list order; invalid entries are skipped.

    Raises:
        ValueError: If ``items`` is not a list.
    """
    if not isinstance(items, list):
        raise ValueError("'suppressions' must be a list.")
    entries: list[WarningSuppressionEntryModel] = []
    for index, entry in enumerate(items):
        if not isinstance(entry, dict):
            if warn is not None:
                warn(f"{source}: suppressions[{index}] must be a JSON object.")
            continue
            # keep parsing remaining entries
        record = _validate_entry(entry, context=f"{source}: suppressions[{index}]", warn=warn)
        if record is not None:
            entries.append(record)
    return entries


def _entries_to_suppression_map(
    entries: list[WarningSuppressionEntryModel],
    *,
    target: str,
) -> dict[str, dict[str, str]]:
    """Build a reason lookup for warning-only or fix-only suppression.

    Args:
        entries: Validated records to filter; not mutated.
        target: ``"warning"`` or ``"fix"``. Other values include every
            record because neither exclusion condition applies.

    Returns:
        Newly allocated ``check_id -> entity_id -> reason`` lookup. Later
        duplicate records replace the reason for the same key.
    """
    suppressions: dict[str, dict[str, str]] = {}
    for record in entries:
        if target == "warning" and not record.suppress_warning:
            continue
        if target == "fix" and not record.suppress_fix:
            continue
        suppressions.setdefault(record.check_id, {})[record.entity_id] = record.reason
    return suppressions


def _validate_entry(
    payload: dict[str, Any],
    *,
    context: str,
    warn=None,
) -> WarningSuppressionEntryModel | None:
    """Parse one suppression record and report model errors non-fatally.

    Args:
        payload: Candidate record mapping passed to the validation model.
        context: Prefix identifying the source record in validation output.
        warn: Optional callback used by ``warn_from_validation_error``.

    Returns:
        A validated model, or ``None`` after reporting a ``ValidationError``.
    """
    try:
        return WarningSuppressionEntryModel.parse_obj(payload)
    except ValidationError as exc:
        warn_from_validation_error(context, exc, warn)
        return None
