# vim:ts=4:sw=4:tw=0:sts=4:et

"""Helpers for loading shareable AI-curated findings from the repository."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


AI_CACHE_ROOT = Path(__file__).resolve().parent / "ai-check-cache"


def get_ai_cache_paths(schema: str) -> list[Path]:
    """Return JSON cache files for a schema, ordered by filename."""
    schema_dir = AI_CACHE_ROOT / schema
    if not schema_dir.exists():
        return []
    return sorted(path for path in schema_dir.glob("*.json") if path.is_file())


def load_ai_findings(schema: str) -> list[dict[str, Any]]:
    """Load and validate AI-curated findings for one schema."""
    findings: list[dict[str, Any]] = []
    for path in get_ai_cache_paths(schema):
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get("findings")
        if not isinstance(records, list):
            raise ValueError(f"{path}: expected 'findings' to be a list.")
        for index, record in enumerate(records):
            findings.append(_validate_record(path, index, record))
    return findings


def _validate_record(path: Path, index: int, record: Any) -> dict[str, Any]:
    """Validate one AI finding record and return the normalized mapping."""
    if not isinstance(record, dict):
        raise ValueError(f"{path}: finding #{index} must be a JSON object.")

    required_fields = {
        "rule",
        "entity_id",
        "entity_type",
        "severity",
        "message",
        "action",
    }
    missing = sorted(required_fields - set(record))
    if missing:
        raise ValueError(
            f"{path}: finding #{index} is missing required fields: {missing}."
        )

    normalized = dict(record)
    normalized.setdefault("fields", [])
    normalized.setdefault("email", "")
    normalized.setdefault("nn", "")
    normalized.setdefault("withdrawn", "")

    if normalized["entity_type"] not in {"BIOBANK", "COLLECTION"}:
        raise ValueError(
            f"{path}: finding #{index} has unsupported entity_type "
            f"{normalized['entity_type']!r}."
        )
    if normalized["severity"] not in {"ERROR", "WARNING", "INFO"}:
        raise ValueError(
            f"{path}: finding #{index} has unsupported severity "
            f"{normalized['severity']!r}."
        )
    if not isinstance(normalized["fields"], list):
        raise ValueError(f"{path}: finding #{index} field 'fields' must be a list.")

    return normalized
