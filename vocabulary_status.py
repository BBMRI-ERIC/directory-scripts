"""Compute non-blocking QC compatibility and reference-backed migration advice."""

from __future__ import annotations

import re
import sys
from pathlib import Path
import subprocess

from vocabulary_guidance import content_hash, load_guidance


def term_fingerprint(term: dict) -> str:
    """Fingerprint term meanings while ignoring CSV/API empty-value differences.

    Args:
        term: Reference row with exact name, label, definition and optional identifiers.

    Returns:
        SHA-256 of semantic properties; display ordering and runtime metadata are excluded.
    """
    normalized = {}
    for key in ("name", "label", "definition", "parent", "codesystem", "code", "ontologyTermURI", "serviceCategory"):
        value = term.get(key)
        if isinstance(value, dict):
            value = value.get("name", value.get("id"))
        if isinstance(value, list):
            value = sorted(item.get("name", item.get("id")) if isinstance(item, dict) else item for item in value)
        if value not in (None, "", []):
            normalized[key] = value
    return content_hash(normalized)


def ontology_fingerprint(rows: list[dict]) -> str:
    """Fingerprint an entire reference vocabulary independently of row order.

    Args:
        rows: Term records using CSV or API reference representations.

    Returns:
        SHA-256 of sorted name-to-meaning fingerprints.
    """
    return content_hash({row["name"]: term_fingerprint(row) for row in rows})


def model_structure(metadata: dict) -> dict:
    """Normalize the model properties exposed by both upstream CSV and the API.

    Args:
        metadata: Tables/columns mapping from live metadata or parse_model_csv.

    Returns:
        Independent mapping of business column types, required/key and references.
        Runtime columns, layout headings and unavailable read-only flags are excluded.
    """
    result = {}
    for table in metadata.get("tables", []):
        columns = {}
        for column in table.get("columns", []):
            name = column["name"]
            kind = column.get("columnType", "").upper()
            if name.startswith("mg_") or kind in {"HEADING", "SECTION"}:
                continue
            normalized = {"columnType": kind, "required": str(column.get("required", "false")).lower() == "true"}
            for key in ("key", "refSchemaName", "refTableName", "refBackId"):
                value = column.get(key)
                if key == "refSchemaName" and value == metadata.get("name"):
                    value = None
                if value not in (None, "", 0, "0"):
                    normalized[key] = str(value)
            columns[name] = normalized
        result[table["name"]] = columns
    return result


def model_fingerprint(metadata: dict) -> str:
    """Fingerprint normalized business structure without unexposed model properties.

    Args:
        metadata: Tables/columns mapping from the API or pinned upstream model CSV.

    Returns:
        Stable SHA-256 of the model_structure projection, not a deployment identity.
    """
    return content_hash(model_structure(metadata))


def deprecation_state(definition: str | None) -> str:
    """Recognize explicit current deprecation rather than mentions of the word.

    Args:
        definition: Reference definition text; missing definitions are not declarations.

    Returns:
        deprecated for supported explicit declarations, unverified for other mentions,
        or current when no deprecation is mentioned.
    """
    text = definition or ""
    if re.search(r"\b(?:restored|restoration|reinstated|formerly|previously|historical)\b|\b(?:not|no longer)\s+deprecated\b", text, re.IGNORECASE):
        return "unverified" if re.search(r"\bdeprecated\b", text, re.IGNORECASE) else "current"
    if re.match(r"^\s*(?:(?:(?:this\s+)?(?:term|value)\s+is\s+deprecated)|(?:deprecated(?:\s+(?:value|term))?))\s*(?:[,.:;]|$)", text, re.IGNORECASE):
        return "deprecated"
    return "unverified" if re.search(r"\bdeprecated\b", text, re.IGNORECASE) else "current"


def reference_column_issue(metadata: dict, table: str, field: str, reference: str) -> str | None:
    """Check whether the observed field supports the intended reference lookup.

    Args:
        metadata: Directory schema metadata, not entity records.
        table: Entity table owning the field to inspect.
        field: Column expected to hold multiple reference terms.
        reference: Expected reference table in the DirectoryOntologies schema.

    Returns:
        None for a supported multi-value reference, otherwise a readable coverage
        limitation. Missing properties remain unknown rather than assumed correct.
    """
    column = next((column for entity in metadata.get("tables", []) if entity["name"] == table
                   for column in entity.get("columns", []) if column["name"] == field), None)
    if column is None:
        return f"{table}.{field} is unavailable in the observed model"
    if column.get("columnType") not in {"ONTOLOGY_ARRAY", "REF_ARRAY"}:
        return f"{table}.{field} has unsupported or unknown reference type {column.get('columnType', 'unknown')}"
    if column.get("refTableName") != reference or column.get("refSchemaName") != "DirectoryOntologies":
        return f"{table}.{field} does not expose the expected DirectoryOntologies.{reference} reference"
    return None


def compatibility_message(snapshot: dict, guidance: dict) -> dict | None:
    """Combine independently evidenced component differences into one diagnostic.

    Args:
        snapshot: Available metadata envelope, possibly cached or missing server manifest.
        guidance: Reviewed expectations and source fingerprints; never fetched or modified.

    Returns:
        One level/text mapping, WARNING if any component is known older and INFO
        otherwise; None when every compared component matches. Unknowns are explicit.
    """
    differences = []
    older = False
    expectations = guidance.get("expectations", {})
    expected_release = expectations.get("software", {}).get("release")
    observed_release = snapshot.get("server_manifest", {}).get("SpecificationVersion", "unreported")
    if expected_release and observed_release != expected_release:
        expected = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", expected_release)
        observed = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(observed_release))
        direction = "unverified"
        if expected and observed:
            observed_parts, expected_parts = tuple(map(int, observed.groups())), tuple(map(int, expected.groups()))
            direction = "equal" if observed_parts == expected_parts else "older" if observed_parts < expected_parts else "newer"
        older |= direction == "older"
        if direction != "equal":
            differences.append(f"software expected {expected_release}, observed {observed_release} ({direction})")
    components = {"model": ("schema", expectations.get("model"))}
    components.update({table: (table, expected) for table, expected in expectations.get("ontologies", {}).items()})
    fingerprints = dict(snapshot.get("content_hashes", {}))
    if "schema_metadata" in snapshot:
        fingerprints["schema"] = model_fingerprint(snapshot["schema_metadata"])
    fingerprints.update({table: ontology_fingerprint(rows) for table, rows in snapshot.get("ontologies", {}).items()})
    sources = guidance.get("sources", {})
    for component, (hash_key, expected) in components.items():
        if not expected:
            continue
        reference = expected["expected_reference_id"]
        observed_hash = fingerprints.get(hash_key)
        target_hash = sources[reference].get("semantic_hash")
        if observed_hash and target_hash and observed_hash == target_hash:
            continue
        direction, observed_ref = "unverified", "unknown revision"
        for category, ids in (("older", expected.get("older_reference_ids", [])),
                              ("newer", expected.get("newer_reference_ids", []))):
            matches = [key for key in ids if observed_hash and sources[key].get("semantic_hash") == observed_hash]
            if matches:
                direction, observed_ref = category, "/".join(matches)
                break
        older |= direction == "older"
        differences.append(f"{component} expected {reference}, observed {observed_ref} ({direction})")
    if not differences:
        return None
    return {"level": "WARNING" if older else "INFO", "text": "; ".join(differences)}


def prepare_vocabulary_context(directory, args) -> dict:
    """Load optional guidance and cached/live references once for a QC run.

    Args:
        directory: Loaded Directory instance providing target and schema identity.
        args: Runner namespace; missing optional vocabulary/auth attributes are tolerated.

    Returns:
        Cached-on-instance context with guidance, metadata and nonfatal diagnostics.
        Failed optional inputs reduce only vocabulary-check coverage.
    """
    existing = getattr(directory, "_qc_vocabulary_context", None)
    if existing is not None:
        return existing
    from directory import get_directory_metadata_snapshot

    context = {"guidance": None, "snapshot": None, "diagnostics": []}
    try:
        context["guidance"] = load_guidance(getattr(args, "vocabulary_guidance", None))
    except ValueError as exc:
        context["diagnostics"].append(str(exc))
    try:
        context["snapshot"] = get_directory_metadata_snapshot(
            directory_url=directory.getDirectoryUrl(), schema=directory.getSchema(),
            ontology_tables=("DataCategories", "ServiceTypes"),
            refresh=bool(getattr(args, "refresh_vocabulary_reference", False)),
            offline=bool(getattr(args, "offline_reference", False)),
            username=getattr(args, "username", None), password=getattr(args, "password", None),
            token=getattr(args, "token", None),
        )
        if context["snapshot"].get("schema_error"):
            context["diagnostics"].append("Schema metadata unavailable; software compatibility remains reportable, but vocabulary paths require verified field references: " + context["snapshot"]["schema_error"])
    except (ValueError, RuntimeError) as exc:
        context["diagnostics"].append(f"Vocabulary checks unavailable; other checks continue: {exc}")
    directory._qc_vocabulary_context = context
    return context


def print_vocabulary_context(context: dict, *, stream=None) -> None:
    """Print version context and at most one compatibility message per run.

    Args:
        context: Shared run context returned by prepare_vocabulary_context.
        stream: Optional text stream; defaults to stderr, including in XLSX-only runs.

    Returns:
        None. Marks the context printed to avoid duplicate messages from consumers.
    """
    if context.get("printed"):
        return
    context["printed"] = True
    target = stream if stream is not None else sys.stderr
    print("QC tool: " + tool_revision(), file=target)
    snapshot, guidance = context.get("snapshot"), context.get("guidance")
    if snapshot:
        manifest = snapshot.get("server_manifest", {})
        print(f"Directory observation: {snapshot['target']}/{snapshot['schema']}; "
              f"software {manifest.get('SpecificationVersion', 'unknown')} "
              f"({manifest.get('ImplementationVersion', 'unknown')}); "
              f"software observed {snapshot.get('manifest_retrieved_at', snapshot['retrieved_at'])}; "
              f"{snapshot['channel']} retrieved {snapshot['retrieved_at']}; "
              "model/ontologies are migrated separately from software.", file=target)
    if guidance:
        checks = guidance.get("production_checks", {})
        dates = ", ".join(sorted({value["checked_at"] for value in checks.values()})) or "not recorded"
        print(f"QC guidance: contract {guidance['schema_version']}, sha256 {content_hash(guidance)[:12]}; "
              f"recorded production observations: {dates}; MIABIS comparison is a separate tool.", file=target)
        components = {"model": guidance.get("expectations", {}).get("model")}
        components.update(guidance.get("expectations", {}).get("ontologies", {}))
        references = []
        software = guidance.get("expectations", {}).get("software")
        if software:
            revision = software.get("revision")
            references.append(f"software {software['release']} ({revision[:12] if revision else 'commit not recorded'})")
        for name, expected in components.items():
            if expected:
                source_id = expected["expected_reference_id"]
                revision = guidance["sources"][source_id]["revision"]
                references.append(f"{name} {revision[:12]}")
        if references:
            print("QC development baseline: " + "; ".join(references)
                  + ". See the Manual's Development baselines and production checks section "
                  "(https://zenodo.org/doi/10.5281/zenodo.2583446; updated section may not yet be published).", file=target)
    if snapshot and guidance:
        message = compatibility_message(snapshot, guidance)
        if message:
            print(f"{message['level']}: Directory compatibility: {message['text']}", file=target)


def tool_revision() -> str:
    """Describe the checked-out QC code without requiring Git or network access.

    Returns:
        Full Git revision with tracked-modification marker, or an explicit unknown
        when this directory is not a readable Git checkout. Local report files
        do not mark an otherwise clean tracked implementation as modified.
    """
    root = Path(__file__).resolve().parent
    try:
        revision = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                                  capture_output=True, text=True, check=True, timeout=3).stdout.strip()
        state = subprocess.run(["git", "-C", str(root), "diff-index", "--quiet", "HEAD", "--"],
                               capture_output=True, timeout=3)
        return revision + (" + tracked modifications" if state.returncode == 1 else "" if state.returncode == 0 else " (modification state unknown)")
    except (OSError, subprocess.SubprocessError):
        return "unknown (Git revision unavailable)"


def advice_matches(entry: dict, rows: list[dict], guidance: dict) -> bool:
    """Require reviewed meanings for every relevant old and proposed term.

    Args:
        entry: Accepted migration candidate selected by exact old stored name.
        rows: Available current reference rows for the entry's vocabulary table.
        guidance: Validated sources defining reviewed per-term fingerprints.

    Returns:
        True if a reviewed source has identical definitions for all relevant terms;
        unrelated additional terms do not invalidate advice.
    """
    actual = {row["name"]: term_fingerprint(row) for row in rows}
    relevant = set(entry["previous_terms"])
    relevant.update(term for option in entry["replacement_options"] for term in option["terms"])
    for source_id in entry["applicability"]["reviewed_reference_ids"]:
        hashes = guidance["sources"][source_id].get("term_hashes", {})
        if all(name in hashes and actual.get(name) == hashes[name] for name in relevant):
            return True
    return False
