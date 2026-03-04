"""Load and normalize check-warning suppressions from JSON."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from validation_helpers import warn_from_validation_error
from validation_models import ValidationError, WarningSuppressionEntryModel

DEFAULT_WARNING_SUPPRESSIONS_PATH = Path(__file__).resolve().parent / "warning-suppressions.json"


def load_warning_suppressions(
    path: str | Path | None,
    *,
    warn=None,
) -> dict[str, dict[str, str]]:
    """Return ``check_id -> entity_id -> reason`` suppressions from JSON."""
    if path is None:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        logging.debug("Warning suppression file %s does not exist.", config_path)
        return {}

    try:
        with config_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        if warn is not None:
            warn(f"{config_path}: invalid JSON: {exc}")
        return {}
    try:
        suppressions = _parse_suppressions_payload(payload, warn=warn, source=str(config_path))
    except ValueError as exc:
        if warn is not None:
            warn(f"{config_path}: {exc}")
        return {}
    logging.info(
        "Loaded %s warning suppression(s) across %s check ID(s) from %s.",
        sum(len(entities) for entities in suppressions.values()),
        len(suppressions),
        config_path,
    )
    return suppressions


def _parse_suppressions_payload(
    payload: Any,
    *,
    warn=None,
    source: str = "warning suppressions",
) -> dict[str, dict[str, str]]:
    if not payload:
        return {}
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
) -> dict[str, dict[str, str]]:
    suppressions: dict[str, dict[str, str]] = {}
    for check_id, value in payload.items():
        if isinstance(value, list):
            for entity_id in value:
                record = _validate_entry(
                    {"check_id": check_id, "entity_id": entity_id, "reason": ""},
                    context=f"{source}: {check_id}",
                    warn=warn,
                )
                if record is not None:
                    suppressions.setdefault(record.check_id, {})[record.entity_id] = record.reason
            continue
        if isinstance(value, dict):
            entities = value.get("entities", value)
            if isinstance(entities, list):
                for entity_id in entities:
                    record = _validate_entry(
                        {"check_id": check_id, "entity_id": entity_id, "reason": ""},
                        context=f"{source}: {check_id}",
                        warn=warn,
                    )
                    if record is not None:
                        suppressions.setdefault(record.check_id, {})[record.entity_id] = record.reason
                continue
            if isinstance(entities, dict):
                for entity_id, reason in entities.items():
                    record = _validate_entry(
                        {"check_id": check_id, "entity_id": entity_id, "reason": reason},
                        context=f"{source}: {check_id}",
                        warn=warn,
                    )
                    if record is not None:
                        suppressions.setdefault(record.check_id, {})[record.entity_id] = record.reason
                continue
        if warn is not None:
            warn(
                f"{source}: unsupported suppression entry for {check_id!r}; "
                "expected a list or an object with 'entities'."
            )
        continue
    return suppressions


def _parse_suppression_list(entries: Any, *, warn=None, source: str) -> dict[str, dict[str, str]]:
    if not isinstance(entries, list):
        raise ValueError("'suppressions' must be a list.")
    suppressions: dict[str, dict[str, str]] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            if warn is not None:
                warn(f"{source}: suppressions[{index}] must be a JSON object.")
            continue
            # keep parsing remaining entries
        record = _validate_entry(entry, context=f"{source}: suppressions[{index}]", warn=warn)
        if record is not None:
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
