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
    """Detailed warning-suppression load result."""

    suppressions: dict[str, dict[str, str]]
    warning_suppressions: dict[str, dict[str, str]]
    fix_suppressions: dict[str, dict[str, str]]
    entries: list[WarningSuppressionEntryModel]
    issues: list[str]


def serialize_suppression_entries(entries: list[WarningSuppressionEntryModel]) -> dict[str, Any]:
    """Return a canonical JSON payload for suppression entries."""
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
    """Write entries to JSON file in canonical v2 list format."""
    payload = serialize_suppression_entries(entries)
    output_path = Path(path)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_warning_suppressions(
    path: str | Path | None,
    *,
    warn=None,
) -> dict[str, dict[str, str]]:
    """Return ``check_id -> entity_id -> reason`` suppressions from JSON."""
    return load_warning_suppressions_detailed(path, warn=warn).warning_suppressions


def load_warning_suppressions_detailed(
    path: str | Path | None,
    *,
    warn=None,
) -> WarningSuppressionLoadResult:
    """Return detailed suppression load result for diagnostics and tooling."""
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
    """Return non-fatal diagnostics (expired, stale entity IDs, unknown checks)."""
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
    try:
        return WarningSuppressionEntryModel.parse_obj(payload)
    except ValidationError as exc:
        warn_from_validation_error(context, exc, warn)
        return None
