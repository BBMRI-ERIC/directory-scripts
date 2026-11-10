"""Compare reviewed MIABIS concepts with Directory metadata, never entity data."""

from __future__ import annotations

import hashlib
import json

from vocabulary_guidance import content_hash
from vocabulary_status import term_fingerprint, reference_column_issue, model_structure, model_fingerprint, ontology_fingerprint
from vocabulary_sources import history_path_transitions, parse_model_csv, parse_vocabulary_csv

CLASSIFICATION_LABELS = {
    "equivalent": "Represented by a reviewed counterpart",
    "directory_broader": "Directory term has a broader meaning",
    "directory_narrower": "Directory term has a more specific meaning",
    "missing_in_directory": "No Directory counterpart established",
    "directory_extension": "Directory has an additional documented term",
    "unresolved": "Meaning needs review",
    "binding_needs_review": "Definitions changed since the comparison was reviewed",
    "unexplained_addition": "Additional Directory term needs review",
}


def _history_content(component: str, text: str) -> tuple[str, dict]:
    """Parse a supported historical source into a digest and readable difference keys.

    Args:
        component: model, DataCategories or ServiceTypes, selecting the source parser.
        text: Exact source contents for one historical version.

    Returns:
        Semantic/structural fingerprint and key-to-value projection used to explain
        differences, not infer scientific equivalence from changed text.

    Raises:
        ValueError: If the source version uses an unsupported file format.
    """
    if component == "model":
        metadata = parse_model_csv(text)
        structure = model_structure(metadata)
        flat = {f"table {table}": "present" for table in structure}
        flat.update({f"{table}.{field}": value for table, columns in structure.items() for field, value in columns.items()})
        return model_fingerprint(metadata), flat
    rows = parse_vocabulary_csv(text)
    return ontology_fingerprint(rows), {row["name"]: term_fingerprint(row) for row in rows}


def match_directory_history(implementation: dict, history: dict) -> dict:
    """Match observed model/terms to source intervals without inventing deployment IDs.

    Args:
        implementation: Metadata-only Directory snapshot with independent observations.
        history: Complete pinned source history, endpoint snapshots and ordered edits.

    Returns:
        Per-component matching intervals or explicit no-match differences/unsupported
        evidence. Structural model matches exclude descriptions/defaults/validation
        and unavailable read-only properties; they do not prove full schema equality.
    """
    model_path = "data/biobank-directory/" + ("" if implementation.get("schema") == "ERIC" else "stagingArea/") + "molgenis.csv"
    components = {"model": model_path,
                  "DataCategories": "data/biobank-directory/ontologies/DataCategories.csv",
                  "ServiceTypes": "data/biobank-directory/ontologies/ServiceTypes.csv"}
    results = {}
    for component, path in components.items():
        record = {"path": path, "matching_intervals": [], "status": "unavailable"}
        results[component] = record
        endpoints = history.get("snapshots", {}).get(path)
        if not endpoints or not history.get("start_revision") or not history.get("end_revision"):
            record["limitation"] = "Pinned endpoint contents are unavailable; no source revision can be established."
            continue
        if component == "model":
            if implementation.get("schema_error") or "schema_metadata" not in implementation:
                record["limitation"] = "Observed schema metadata is unavailable."
                continue
            structure = model_structure(implementation["schema_metadata"])
            actual_hash = model_fingerprint(implementation["schema_metadata"])
            actual = {f"table {table}": "present" for table in structure}
            actual.update({f"{table}.{field}": value for table, columns in structure.items() for field, value in columns.items()})
        else:
            rows = implementation.get("ontologies", {}).get(component)
            if rows is None:
                record["limitation"] = "Observed reference vocabulary is unavailable."
                continue
            actual_hash = ontology_fingerprint(rows)
            actual = {row["name"]: term_fingerprint(row) for row in rows}
        related = history_path_transitions(history, path)
        versions = [(history["start_revision"], endpoints["at_start"], path)]
        versions.extend((item["commit"], item["after"], item["path"]) for item in related)
        try:
            for idx, (revision, text, source_path) in enumerate(versions):
                if not text:
                    continue
                fingerprint, _ = _history_content(component, text)
                if actual_hash == fingerprint:
                    record["matching_intervals"].append({
                        "from_revision": revision,
                        "before_revision": versions[idx + 1][0] if idx + 1 < len(versions) else None,
                        "through_revision": None if idx + 1 < len(versions) else history["end_revision"],
                        "path": source_path, "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    })
            latest_text = endpoints["at_end"]
            latest_hash, latest = _history_content(component, latest_text) if latest_text else (None, {})
            record["status"] = "matched" if record["matching_intervals"] else "no_match"
            record["observed_fingerprint"] = actual_hash
            record["latest_source_fingerprint"] = latest_hash
            record["differences_from_latest"] = {
                "added": sorted(actual.keys() - latest.keys()),
                "removed": sorted(latest.keys() - actual.keys()),
                "changed": sorted(name for name in actual.keys() & latest.keys() if actual[name] != latest[name]),
            }
        except ValueError as exc:
            record["status"] = "unavailable"
            record["limitation"] = f"Unsupported historical source format: {exc}"
        record["meaning"] = ("Compatible business type/required/key/reference structure; excluded properties remain unverified."
                             if component == "model" else "Compatible term names, definitions and identifiers.")
        record["meaning"] += " Matching intervals are upstream content evidence, not deployment commits or dates."
    return results


def _binding_current(binding: dict, reference: dict, implemented: dict, guidance: dict) -> bool:
    """Require current evidence before reusing a reviewed conceptual comparison.

    Args:
        binding: Guidance record relating reference and implemented concepts.
        reference: Pinned MIABIS reference envelope.
        implemented: Table-to-name lookup of observed Directory term rows.
        guidance: Source records supplying pinned revisions and term fingerprints.

    Returns:
        True when accepted review, MIABIS revision/definition and Directory
        meanings all remain compatible with the recorded evidence.
    """
    if binding["review"]["state"] != "accepted":
        return False
    concept = binding.get("miabis_concept")
    if concept:
        source = guidance["sources"].get(concept["source_id"], {})
        if source.get("revision") != reference.get("revision"):
            return False
        if concept.get("definition_hash"):
            matches = [row for rows in reference["terms"].values() for row in rows if row["name"] == concept["name"]]
            if len(matches) != 1 or hashlib.sha256(matches[0].get("definition", "").encode()).hexdigest() != concept["definition_hash"]:
                return False
    for target in binding["directory_terms"]:
        row = implemented.get(target["table"], {}).get(target["name"])
        if row is None:
            return False
        if not any(guidance["sources"][key].get("term_hashes", {}).get(target["name"]) == term_fingerprint(row)
                   for key in binding["evidence_ids"]):
            return False
    return True


def compare_reference(reference: dict, implementation: dict, guidance: dict, history: dict) -> dict:
    """Account for every reference and implemented term without inferred equivalence.

    Args:
        reference: Parsed pinned MIABIS sources and both supported vocabulary lists.
        implementation: Directory metadata-only snapshot with reference ontology rows.
        guidance: Validated reviewed migration/comparison document.
        history: Reconstructed upstream history with an explicit completeness flag.

    Returns:
        Deterministically ordered report, evidence, coverage and exit_status:
        0 complete/reviewed, 1 complete requiring review, 2 incomplete inputs.
    """
    comparisons = []
    coverage = {}
    complete = bool(reference.get("complete") and history.get("complete"))
    implemented = {table: {row["name"]: row for row in rows}
                   for table, rows in implementation.get("ontologies", {}).items()}
    for table in ("DataCategories", "ServiceTypes"):
        reference_rows = reference.get("terms", {}).get(table)
        directory_rows = implemented.get(table)
        if reference_rows is None or directory_rows is None:
            complete = False
        reference_rows = reference_rows or []
        directory_rows = directory_rows or {}
        coverage[table] = {"reference": len(reference_rows), "implementation": len(directory_rows)}
        represented = set()
        for concept in sorted(reference_rows, key=lambda row: row["name"]):
            bindings = []
            # Null reference concepts identify extensions rather than MIABIS terms.
            for binding in guidance["miabis_bindings"]:
                linked = binding.get("miabis_concept")
                if linked and linked["name"] == concept["name"] and (
                    not binding["directory_terms"] or any(target["table"] == table for target in binding["directory_terms"])
                ):
                    bindings.append(binding)
            if len(bindings) == 1:
                binding = bindings[0]
                targets = [target["name"] for target in binding["directory_terms"] if target["table"] == table]
                present = [name for name in targets if name in directory_rows]
                represented.update(present)
                classification = binding["relationship"]
                if targets and not present:
                    classification = "missing_in_directory"
                elif not _binding_current(binding, reference, implemented, guidance):
                    classification = "binding_needs_review"
                explanation = binding["explanation"]
            else:
                present = [concept["name"]] if concept["name"] in directory_rows else []
                represented.update(present)
                classification = "unresolved"
                explanation = "No unique reviewed comparison establishes this concept's representation."
            comparisons.append({"table": table, "reference_terms": [concept["name"]], "directory_terms": present,
                                "classification": classification, "explanation": explanation,
                                "review_required": classification != "equivalent"})
        for name in sorted(directory_rows.keys() - represented):
            bindings = [binding for binding in guidance["miabis_bindings"]
                        if binding["relationship"] == "directory_extension"
                        and {"table": table, "name": name} in binding["directory_terms"]]
            accepted = len(bindings) == 1 and _binding_current(bindings[0], reference, implemented, guidance)
            comparisons.append({"table": table, "reference_terms": [], "directory_terms": [name],
                                "classification": "directory_extension" if accepted else "unexplained_addition",
                                "explanation": bindings[0]["explanation"] if len(bindings) == 1 else "No reviewed explanation for this additional term.",
                                "review_required": not accepted})
    for row in comparisons:
        reference_lookup = {term["name"]: term for term in reference.get("terms", {}).get(row["table"], [])}
        row["reference_evidence"] = [dict(reference_lookup[name]) for name in row["reference_terms"] if name in reference_lookup]
        row["directory_evidence"] = [
            {key: value for key, value in implemented[row["table"]][name].items()
             if key in {"name", "label", "definition", "codesystem", "code", "ontologyTermURI", "parent", "serviceCategory"}}
            for name in row["directory_terms"]
        ]
        row["finding_id"] = "MIABIS-" + content_hash({key: row[key] for key in ("table", "reference_terms", "directory_terms", "classification")})[:16]
    comparisons.sort(key=lambda row: (row["table"], row["reference_terms"], row["directory_terms"], row["classification"]))
    history_matches = match_directory_history(implementation, history)
    if any(value["status"] == "unavailable" for value in history_matches.values()):
        complete = False
    if implementation.get("schema_error"):
        complete = False
    reference_issues = reference.get("source_conflicts", [])
    schema_checks = []
    for table, field, reference_table in (("Collections", "data_categories", "DataCategories"),
                                          ("Services", "serviceTypes", "ServiceTypes")):
        issue = reference_column_issue(implementation.get("schema_metadata", {}), table, field, reference_table)
        cardinality = reference.get("attributes", {}).get(reference_table, {}).get("cardinality")
        if issue is None and cardinality in {"1", "1..1", "0..1"}:
            issue = f"The MIABIS component lists cardinality {cardinality}, while Directory exposes a multi-value field; confirm the intended interpretation."
        schema_checks.append({"field": f"{table}.{field}", "reference_table": reference_table,
                              "review_required": issue is not None,
                              "explanation": issue or "The field uses the expected multi-value reference."})
    review_count = (sum(row["review_required"] for row in comparisons + schema_checks)
                    + len(reference_issues) + sum(value["status"] == "no_match" for value in history_matches.values()))
    return {
        "format_version": 1, "complete": complete,
        "exit_status": 2 if not complete else 1 if review_count else 0,
        "review_count": review_count,
        "target": implementation.get("target"), "schema": implementation.get("schema"),
        "observed_at": implementation.get("retrieved_at"), "channel": implementation.get("channel"),
        "server_manifest": implementation.get("server_manifest", {}),
        "manifest_observed_at": implementation.get("manifest_retrieved_at", implementation.get("retrieved_at")),
        "content_hashes": implementation.get("content_hashes", {}),
        "miabis_revision": reference.get("revision"),
        "reference_sources": {path: {key: value for key, value in source.items() if key != "text"}
                              for path, source in reference.get("sources", {}).items()},
        "reference_issues": reference_issues, "reference_attributes": reference.get("attributes", {}),
        "publication_context": reference.get("publication_context", "Publication status not established."),
        "history_matches": history_matches,
        "coverage": coverage, "comparisons": comparisons, "schema_checks": schema_checks, "history": history,
        "limitations": ["Only Dataset Type and Service Type vocabularies and their relevant schema references are in scope.",
                        "Software installation and model/ontology migration happen separately; observed content is not a deployment date.",
                        "No complete conformance conclusion is available." if not complete else
                        "Unresolved comparisons require review; textual similarity does not establish equal meaning."],
    }


def _tex_escape(text: str) -> str:
    """Escape arbitrary vocabulary explanations for an ordinary LaTeX text cell.

    Args:
        text: Human-readable content, never intended as trusted TeX commands.

    Returns:
        Text with TeX control characters escaped without double-escaping insertions.
    """
    replacements = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
                    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(replacements.get(char, char) for char in text)


def render_comparison(report: dict, *, format: str) -> str:
    """Render a deterministic standalone report or a reviewed LaTeX fragment.

    Args:
        report: Comparison result carrying coverage, evidence and limitations.
        format: json, markdown or tex; fragments are not automatically inserted in Manual.

    Returns:
        Complete report text with plain-language classifications and limitations.

    Raises:
        ValueError: If the requested rendering format is unsupported.
    """
    if format == "json":
        return json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    if format not in {"markdown", "tex"}:
        raise ValueError(f"Unsupported comparison report format: {format}")
    lines = ["# Directory and MIABIS comparison" if format == "markdown" else r"\subsection{Directory and MIABIS comparison}"]
    summaries = [f"Directory: {report.get('target')}/{report.get('schema')}; observed {report.get('observed_at')} ({report.get('channel')}).",
                 f"Software: {report.get('server_manifest', {}).get('SpecificationVersion', 'unknown')}; implementation {report.get('server_manifest', {}).get('ImplementationVersion', 'unknown')}; observed {report.get('manifest_observed_at')}.",
                 f"MIABIS reference: {report.get('miabis_revision')}"] + report["limitations"]
    for text in summaries:
        lines.append(text if format == "markdown" else _tex_escape(text) + r"\par")
    context = report.get("publication_context")
    if context:
        lines.append(context if format == "markdown" else _tex_escape(context) + r"\par")
    for issue in report.get("reference_issues", []):
        text = "Reference documents: " + issue["explanation"]
        if issue.get("component_only"):
            text += " Only in the component: " + ", ".join(issue["component_only"]) + "."
        if issue.get("all_lists_only"):
            text += " Only in all lists: " + ", ".join(issue["all_lists_only"]) + "."
        lines.append(text if format == "markdown" else _tex_escape(text) + r"\par")
    lines.append("## Upstream content matching" if format == "markdown" else r"\subsubsection{Upstream content matching}")
    for component, match in report.get("history_matches", {}).items():
        text = component + ": " + match["status"].replace("_", " ") + ". " + match.get("meaning", match.get("limitation", ""))
        lines.append(text if format == "markdown" else _tex_escape(text) + r"\par")
        for interval in match["matching_intervals"]:
            text = "Compatible contents from " + interval["from_revision"]
            if interval["before_revision"]:
                text += " up to, but excluding, " + interval["before_revision"]
            else:
                text += " through " + interval["through_revision"]
            lines.append(text if format == "markdown" else _tex_escape(text) + r"\par")
        if match["status"] == "no_match":
            for key, label in (("added", "Additional in Directory"), ("removed", "Missing from Directory"), ("changed", "Changed definitions or properties")):
                names = match["differences_from_latest"][key]
                if names:
                    text = label + ": " + ", ".join(names) + "."
                    lines.append(text if format == "markdown" else _tex_escape(text) + r"\par")
    for check in report.get("schema_checks", []):
        text = check["field"] + ": " + check["explanation"]
        lines.append(text if format == "markdown" else _tex_escape(text) + r"\par")
    for row in report["comparisons"]:
        heading = f"{row['table']}: {', '.join(row['reference_terms']) or '(Directory addition)'} -> {', '.join(row['directory_terms']) or '(no counterpart)'}"
        description = CLASSIFICATION_LABELS[row["classification"]] + ": " + row["explanation"]
        if format == "markdown":
            lines.extend(["", "## " + heading.replace("\n", " "), description])
        else:
            lines.extend([r"\paragraph{" + _tex_escape(heading) + "}", _tex_escape(description) + r"\par"])
        for key, label in (("reference_evidence", "MIABIS"), ("directory_evidence", "Directory")):
            for evidence in row.get(key, []):
                text = label + " definition (" + evidence["name"] + "): " + (evidence.get("definition") or "No definition supplied.")
                lines.append(text if format == "markdown" else _tex_escape(text) + r"\par")
    lines.append("## Reference sources" if format == "markdown" else r"\subsubsection{Reference sources}")
    for path, source in sorted(report.get("reference_sources", {}).items()):
        if format == "markdown":
            lines.append(f"- [{path}]({source['url']}); SHA-256 `{source['sha256']}`")
        else:
            lines.append(r"\href{" + _tex_escape(source["url"]) + "}{" + _tex_escape(path) + r"}\par")
    if format == "markdown":
        lines.extend(["", "## Source changes"])
        for transition in report.get("history", {}).get("transitions", []):
            lines.append(f"- {transition['committed_at']}: `{transition['commit']}` / `{transition['path']}`: {transition.get('changes', 'model fields changed')}")
    return "\n".join(lines) + "\n"
