#!/usr/bin/env python3
"""Normalize BBMRI strategic-objectives TOML/JSON into a validated JSON spec."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _load_raw_spec(path: Path) -> dict:
    """Read a raw strategic-objectives mapping from JSON or TOML.

    Args:
        path: Input path whose suffix selects JSON or TOML decoding.

    Returns:
        Parsed top-level mapping from the source file.

    Raises:
        SystemExit: If the filename suffix is not a supported source format.
        OSError: If the file cannot be read.
    """
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix.lower() in {".toml", ".tml"}:
        import tomllib

        return tomllib.loads(path.read_text(encoding="utf-8"))
    raise SystemExit(f"Unsupported strategic-objectives input format: {path.suffix}")


def _is_country_code(value: str) -> bool:
    """Test whether text is exactly an uppercase two-letter country code.

    Args:
        value: Candidate text, accepting an empty string.

    Returns:
        ``True`` only for two uppercase ASCII letters.
    """
    return bool(re.fullmatch(r"[A-Z]{2}", value or ""))


def _normalize_lead_country(raw: str) -> str:
    """Normalize a country or HQ-prefixed co-lead code.

    Args:
        raw: Uppercase source country token or ``HQ-XX`` representation.

    Returns:
        Bare two-letter code for recognized forms, otherwise the original text or
        an empty string.
    """
    if _is_country_code(raw):
        return raw
    match = re.fullmatch(r"HQ-([A-Z]{2})", raw or "")
    if match:
        return match.group(1)
    return raw or ""


def _normalize_names(value) -> list[str]:
    """Normalize a co-lead name scalar or sequence to a string list.

    Args:
        value: Missing value, single name string, or iterable of name values.

    Returns:
        Newly allocated list, preserving a single string as one name.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _normalize_goal(goal: dict) -> dict:
    """Normalize one goal while retaining unrecognized source fields.

    Args:
        goal: Raw goal mapping in either supported strategic-objective shape.

    Returns:
        Newly allocated normalized goal mapping with stable known keys and copied
        extra source fields.
    """
    normalized_leads = []
    for entry in goal.get("co_leads", []) or []:
        country_raw = str(entry.get("country", "")).strip().upper()
        normalized_leads.append(
            {
                "country": _normalize_lead_country(country_raw),
                "country_raw": country_raw,
                "names": _normalize_names(entry.get("names")),
            }
        )
    normalized_goal = {
        "id": str(goal.get("id", "")).strip(),
        "title": str(goal.get("title", "")).strip(),
        "description": str(goal.get("description", "")).strip(),
        "co_leads": normalized_leads,
        "contributors_nn": [str(item).strip().upper() for item in goal.get("contributors_nn", []) or []],
        "contributions_hq": [str(item).strip() for item in goal.get("contributions_hq", []) or []],
    }
    for extra_key, value in goal.items():
        if extra_key not in normalized_goal:
            normalized_goal[extra_key] = value
    return normalized_goal


def _normalize_objectives(raw: dict) -> list[dict]:
    """Normalize either supported strategic-objectives source shape.

    Args:
        raw: Raw top-level mapping with an ``objectives`` list or legacy ``SO1``
        through ``SO8`` mappings.

    Returns:
        Newly allocated normalized objective list in source iteration order.
    """
    objectives = []
    if isinstance(raw.get("objectives"), list):
        source_objectives = raw["objectives"]
        for item in source_objectives:
            goals = [_normalize_goal(goal) for goal in item.get("goals", []) or []]
            objectives.append(
                {
                    "id": str(item.get("id", "")).strip(),
                    "title": str(item.get("title", "")).strip(),
                    "description": str(item.get("description", "")).strip(),
                    "goals": goals,
                }
            )
        return objectives

    for key, value in raw.items():
        if not re.fullmatch(r"SO[1-8]", key):
            continue
        goals = []
        if isinstance(value, dict):
            if isinstance(value.get("goals"), list):
                for goal_value in value.get("goals", []):
                    if not isinstance(goal_value, dict):
                        continue
                    goal = dict(goal_value)
                    goals.append(_normalize_goal(goal))
            else:
                for goal_id, goal_value in value.items():
                    if not isinstance(goal_value, dict):
                        continue
                    goal = dict(goal_value)
                    goal.setdefault("id", goal_id)
                    goals.append(_normalize_goal(goal))
        objectives.append(
            {
                "id": key,
                "title": str(value.get("title", "")).strip() if isinstance(value, dict) else "",
                "description": str(value.get("description", "")).strip() if isinstance(value, dict) else "",
                "goals": goals,
            }
        )
    return objectives


def normalize_spec(raw: dict) -> dict:
    """Construct the stable JSON specification consumed by map tooling.

    Args:
        raw: Raw strategic-objectives source mapping accepted by
            ``_normalize_objectives``.

    Returns:
        Newly allocated schema-versioned mapping with note and normalized
        objectives.
    """
    schema_version = int(raw.get("schema_version", 1))
    note = str(raw.get("note", "")).strip()
    objectives = _normalize_objectives(raw)
    normalized = {
        "schema_version": schema_version,
        "note": note,
        "objectives": objectives,
    }
    return normalized


def main() -> None:
    """Normalize a strategic-objectives source file and write or print JSON.

    Returns:
        None. Reads CLI-selected input, writes JSON to stdout for ``-`` output,
        or overwrites the requested local output path without creating parents.

    Raises:
        SystemExit: If source format is unsupported.
        OSError: If the input or requested output cannot be accessed.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="-")
    args = parser.parse_args()

    raw = _load_raw_spec(Path(args.input))
    normalized = normalize_spec(raw)
    payload = json.dumps(normalized, ensure_ascii=False, indent=2)
    if args.output == "-" or not args.output:
        sys.stdout.write(payload)
        sys.stdout.write("\n")
        return
    Path(args.output).write_text(payload + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
