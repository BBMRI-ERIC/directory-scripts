"""Validate reviewed vocabulary migration advice and select applicable entries."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

DEFAULT_GUIDANCE_PATH = Path(__file__).with_name("vocabulary-guidance.json")
MIGRATION_RELATIONSHIPS = {
    "equivalent", "target_broader", "target_narrower", "split", "combination", "unresolved"
}
BINDING_RELATIONSHIPS = {
    "equivalent", "directory_broader", "directory_narrower", "missing_in_directory",
    "directory_extension", "unresolved",
}
ACTION_KINDS = {
    "replace_known_value", "inspect_existing_information", "ask_curator",
    "collect_missing_metadata", "no_safe_replacement",
}


def content_hash(value: Any) -> str:
    """Fingerprint a JSON-compatible value independently of mapping order.

    Args:
        value: JSON data to serialize; list order remains significant.

    Returns:
        SHA-256 hexadecimal digest of the canonical UTF-8 serialization.
    """
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _object(value: Any, required: tuple[str, ...], location: str) -> dict:
    """Require a mapping with explicit fields at a local-artifact location.

    Args:
        value: Candidate mapping; never coerced from another type.
        required: Keys which must exist in the mapping.
        location: Human-readable path used in validation errors.

    Returns:
        The original validated mapping, without copying.

    Raises:
        ValueError: If a mapping or one of its required fields is absent.
    """
    if not isinstance(value, dict) or any(key not in value for key in required):
        raise ValueError(f"Invalid guidance {location}: expected object containing {', '.join(required)}")
    return value


def _strings(value: Any, location: str, *, nonempty: bool = False) -> list[str]:
    """Require a list of unique nonblank strings.

    Args:
        value: Candidate list; empty lists are accepted unless prohibited.
        location: Field path to include in an error.
        nonempty: Whether at least one item is required.

    Returns:
        The validated original list.

    Raises:
        ValueError: If item types, blank strings or duplicates violate the contract.
    """
    if (not isinstance(value, list) or (nonempty and not value)
            or any(not isinstance(item, str) or not item.strip() for item in value)
            or len(set(value)) != len(value)):
        raise ValueError(f"Invalid guidance {location}: expected unique nonblank strings")
    return value


def _references(value: Any, available: dict, location: str) -> None:
    """Check local references without resolving remote sources.

    Args:
        value: List of referenced stable identifiers.
        available: Mapping defining the allowed identifiers.
        location: Field path for actionable validation errors.

    Returns:
        None.

    Raises:
        ValueError: If an identifier is duplicated or undefined.
    """
    for key in _strings(value, location):
        if key not in available:
            raise ValueError(f"Invalid guidance {location}: undefined reference {key!r}")


def validate_guidance(document: dict) -> dict:
    """Validate a curated local guidance document without optional dependencies.

    Args:
        document: Decoded version-one guidance including evidence and review state.

    Returns:
        The same mapping, validated without mutation or remote requests.

    Raises:
        ValueError: If structure, enums, evidence or cross-references are invalid.
    """
    _object(document, ("schema_version", "sources", "production_checks", "expectations",
                       "migrations", "miabis_bindings", "structural_changes", "manual_sections"), "root")
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        raise ValueError("Unsupported guidance schema_version; expected 1")
    for key in ("sources", "production_checks", "expectations", "manual_sections"):
        _object(document[key], (), key)
    sources = document["sources"]
    for key, source in sources.items():
        _object(source, ("repository", "revision", "path", "sha256", "locator"), f"sources.{key}")
        if (not re.fullmatch(r"[0-9a-f]{40}", str(source["revision"]))
                or not re.fullmatch(r"[0-9a-f]{64}", str(source["sha256"]))
                or any(not isinstance(source[field], str) or not source[field].strip()
                       for field in ("repository", "path", "locator"))):
            raise ValueError(f"Invalid guidance source {key}: immutable revision/path/hash required")
        if "semantic_hash" in source and not re.fullmatch(r"[0-9a-f]{64}", str(source["semantic_hash"])):
            raise ValueError(f"Invalid guidance source {key}: malformed semantic fingerprint")
        if "term_hashes" in source:
            hashes = _object(source["term_hashes"], (), f"sources.{key}.term_hashes")
            if any(not isinstance(name, str) or not name.strip()
                   or not re.fullmatch(r"[0-9a-f]{64}", str(digest)) for name, digest in hashes.items()):
                raise ValueError(f"Invalid guidance source {key}: malformed term fingerprint")
    for key, section in document["manual_sections"].items():
        _object(section, ("label", "title", "publication"), f"manual_sections.{key}")
        if section["publication"] not in {"published", "unpublished"}:
            raise ValueError(f"Invalid Manual publication status for {key}")
        if any(not isinstance(section[field], str) or not section[field].strip() for field in ("label", "title")):
            raise ValueError(f"Manual section {key} requires a label and readable title")
    for key, observation in document["production_checks"].items():
        _object(observation, ("target", "schema", "checked_at", "server_manifest", "content_hashes", "compatible_source_ids", "note"), f"production_checks.{key}")
        try:
            checked = datetime.fromisoformat(observation["checked_at"])
            if checked.tzinfo is None:
                raise ValueError("production check needs a timezone")
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid guidance production-check timestamp: {key}") from exc
        _references(observation["compatible_source_ids"], sources, key + ".compatible_source_ids")
        _object(observation["server_manifest"], (), key + ".server_manifest")
        _object(observation["content_hashes"], (), key + ".content_hashes")
    expectations = document["expectations"]
    if "software" in expectations:
        software = _object(expectations["software"], ("release",), "expectations.software")
        if not isinstance(software["release"], str) or not re.fullmatch(r"v?\d+\.\d+\.\d+", software["release"]):
            raise ValueError("Expected software baseline must be an explicit release")
    components = list(_object(expectations.get("ontologies", {}), (), "expectations.ontologies").values())
    if "model" in expectations:
        components.append(expectations["model"])
    for component in components:
        _object(component, ("expected_reference_id", "older_reference_ids", "newer_reference_ids"), "expectations component")
        _references([component["expected_reference_id"]] + _strings(component["older_reference_ids"], "older references")
                    + _strings(component["newer_reference_ids"], "newer references"), sources, "expectations component")
    seen_ids = set()
    migration_contexts = set()
    for group in ("migrations", "miabis_bindings", "structural_changes"):
        if not isinstance(document[group], list):
            raise ValueError(f"Invalid guidance {group}: expected array")
        for entry in document[group]:
            _object(entry, ("id", "explanation", "evidence_ids", "review", "manual_section_ids"), group)
            if not isinstance(entry["id"], str) or not entry["id"] or entry["id"] in seen_ids:
                raise ValueError("Invalid guidance: missing or duplicate entry ID")
            seen_ids.add(entry["id"])
            if not isinstance(entry["explanation"], str) or not entry["explanation"].strip():
                raise ValueError("Guidance requires a readable explanation")
            _references(entry["evidence_ids"], sources, entry["id"] + ".evidence_ids")
            _references(entry["manual_section_ids"], document["manual_sections"], entry["id"] + ".manual_section_ids")
            review = _object(entry["review"], ("state", "reviewed_on", "note"), entry["id"] + ".review")
            if review["state"] not in {"accepted", "needs_review"}:
                raise ValueError("Invalid guidance review state")
            if review["reviewed_on"] is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(review["reviewed_on"])):
                raise ValueError("Invalid guidance review date")
            if review["state"] == "accepted" and review["reviewed_on"] is None:
                raise ValueError("Accepted guidance requires a review date")
            if review["reviewed_on"] is not None:
                date.fromisoformat(review["reviewed_on"])
            if group == "miabis_bindings":
                _object(entry, ("miabis_concept", "directory_terms", "relationship"), entry["id"])
                if entry["relationship"] not in BINDING_RELATIONSHIPS:
                    raise ValueError("Invalid MIABIS relationship direction")
                concept = entry["miabis_concept"]
                if concept is not None:
                    _object(concept, ("source_id", "name", "locator", "definition_hash"), entry["id"] + ".miabis_concept")
                    _references([concept["source_id"]], sources, entry["id"] + ".miabis_concept")
                    if not re.fullmatch(r"[0-9a-f]{64}", str(concept["definition_hash"])):
                        raise ValueError("Invalid MIABIS definition fingerprint")
                if not isinstance(entry["directory_terms"], list):
                    raise ValueError("Directory term bindings must be an array")
                for target in entry["directory_terms"]:
                    _object(target, ("table", "name"), entry["id"] + ".directory_terms")
                    if target["table"] not in {"DataCategories", "ServiceTypes"} or not isinstance(target["name"], str) or not target["name"].strip():
                        raise ValueError("Invalid Directory term binding")
                if entry["relationship"] == "directory_extension" and (concept is not None or not entry["directory_terms"]):
                    raise ValueError("Directory extension requires targets and no normative counterpart")
                if entry["relationship"] == "missing_in_directory" and (concept is None or entry["directory_terms"]):
                    raise ValueError("Missing Directory concept requires a reference concept and no targets")
                continue
            _object(entry, ("actions", "information_needed"), entry["id"])
            _strings(entry["information_needed"], entry["id"] + ".information_needed")
            if not isinstance(entry["actions"], list) or not entry["actions"]:
                raise ValueError("Guidance must state a curator action")
            for action in entry["actions"]:
                _object(action, ("kind", "text"), entry["id"] + ".actions")
                if action["kind"] not in ACTION_KINDS or not isinstance(action["text"], str) or not action["text"].strip():
                    raise ValueError("Invalid guidance action")
            if group == "structural_changes":
                _object(entry, ("affected_fields", "change", "before_source_ids", "after_source_ids", "production_check_ids"), entry["id"])
                history = entry
            else:
                _object(entry, ("table", "entity_fields", "previous_terms", "status", "applicability", "history", "replacement_options"), entry["id"])
                if entry["table"] not in {"DataCategories", "ServiceTypes"} or entry["status"] not in {
                    "deprecated", "removed", "replaced", "restored", "changed_definition"
                }:
                    raise ValueError("Invalid guidance vocabulary or migration status")
                refs = _object(entry["applicability"], ("reviewed_reference_ids",), entry["id"])["reviewed_reference_ids"]
                _references(refs, sources, entry["id"] + ".applicability")
                _strings(entry["entity_fields"], entry["id"] + ".entity_fields", nonempty=True)
                for term in _strings(entry["previous_terms"], entry["id"] + ".previous_terms", nonempty=True):
                    for ref in refs:
                        context = (entry["table"], term, ref)
                        if context in migration_contexts:
                            raise ValueError(f"Conflicting guidance for {context}")
                        migration_contexts.add(context)
                if not isinstance(entry["replacement_options"], list):
                    raise ValueError("Invalid replacement options")
                for option in entry["replacement_options"]:
                    _object(option, ("terms", "relationship", "basis", "conditions", "explanation", "evidence_ids"), entry["id"])
                    _strings(option["terms"], entry["id"] + ".terms", nonempty=True)
                    _strings(option["conditions"], entry["id"] + ".conditions")
                    if option["relationship"] not in MIGRATION_RELATIONSHIPS or option["basis"] not in {"upstream_explicit", "reviewed_recommendation"}:
                        raise ValueError("Invalid guidance replacement relationship/basis")
                    _references(option["evidence_ids"], sources, entry["id"] + ".options.evidence")
                history = _object(entry["history"], ("before_source_ids", "after_source_ids", "production_check_ids"), entry["id"] + ".history")
            for field in ("before_source_ids", "after_source_ids"):
                _references(history[field], sources, entry["id"] + "." + field)
            _references(history["production_check_ids"], document["production_checks"], entry["id"] + ".production_checks")
    return document


def load_guidance(path: Path | None = None) -> dict:
    """Load and validate the bundled guidance or an explicit replacement file.

    Args:
        path: Optional input path; default is anchored to this module, not cwd.

    Returns:
        Decoded, validated document owned by the caller.

    Raises:
        ValueError: If the file cannot be read, decoded or validated safely.
    """
    target = DEFAULT_GUIDANCE_PATH if path is None else Path(path)
    try:
        return validate_guidance(json.loads(target.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(f"Cannot load vocabulary guidance {target}: {exc}") from exc


def find_guidance(document: dict, table: str, term: str) -> list[dict]:
    """Select accepted advice candidates without claiming reference compatibility.

    Args:
        document: Previously validated guidance document; never modified.
        table: Exact reference vocabulary table name.
        term: Exact stored old term name, not its display label.

    Returns:
        Matching accepted entries sorted by stable ID. Callers must additionally
        verify the reviewed definitions before displaying replacement advice.
    """
    return sorted((entry for entry in document["migrations"]
                   if entry["table"] == table and term in entry["previous_terms"]
                   and entry["review"]["state"] == "accepted"), key=lambda entry: entry["id"])
