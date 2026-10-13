"""Compose and transactionally publish combined SO2 and MuCP reports."""

from __future__ import annotations

import colorsys
from copy import deepcopy
from collections import defaultdict
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Mapping, Sequence

import so2_descriptive_report as descriptive


def _report_country_copy(value: Any) -> Any:
    """Normalize countries in a detached report model without touching source payloads.

    Args:
        value: JSON-shaped report payload, nested row or scalar to copy for rendering.

    Returns:
        Detached data with report country labels TR/MNE and explicit country-code
        cells; source answer strings, identities and the caller's payload are intact.
    """
    from survey_combined_quantity_views import report_country_code
    if isinstance(value, Mapping):
        source_fields = {"metadata", "raw_answer", "raw_response", "original_response",
                         "mucp_source_records", "so2_source_records", "source_records", "record"}
        result = {key: deepcopy(item) if key in source_fields else _report_country_copy(item)
                  for key, item in value.items()}
        if "country" in result and not isinstance(result["country"], (Mapping, list)):
            result["country"] = report_country_code(result["country"])
            result["country_code"] = result["country"]
        return result
    if isinstance(value, (list, tuple)):
        return [_report_country_copy(item) for item in value]
    return deepcopy(value)


class CombinedPublicationError(ValueError):
    """User-facing validation, preparation or publication failure."""


def load_report_presentation(path: Path) -> dict[str, Any]:
    """Load the versioned, curated labels used by combined report renderers.

    Args:
        path: JSON presentation configuration path, not a source-evidence path.

    Returns:
        Validated mapping with version 1 group titles and seven curated heatmaps.

    Raises:
        ValueError: If the JSON, version, keys, or curated labels are invalid.
    """
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot load report presentation metadata: {exc}") from exc
    if not isinstance(value, dict) or set(value) - {"version", "group_titles", "heatmaps", "modality_quantities"}:
        raise ValueError("Report presentation contains unknown top-level fields")
    if type(value.get("version")) is not int or value["version"] != 1:
        raise ValueError("Unsupported report presentation version; expected integer version 1")
    titles = value.get("group_titles")
    if not isinstance(titles, dict) or any(
        not isinstance(key, str) or not key.startswith("MuCP.")
        or not isinstance(title, str) or not title.strip()
        for key, title in titles.items()
    ):
        raise ValueError("Report presentation group_titles must map MuCP group IDs to nonempty titles")
    if "modality_quantities" in value:
        from survey_mucp_quantities import _definitions
        if not isinstance(value["modality_quantities"], list):
            raise ValueError("Report presentation modality_quantities must be a list")
        _definitions(value["modality_quantities"])
    heatmaps = value.get("heatmaps", {})
    if not isinstance(heatmaps, dict):
        raise ValueError("Report presentation heatmaps must be an object")
    expected_ids = {"so2-technical_readiness_qms", "so2-personnel_infrastructure",
                    "so2-collection_automation_audit", "so2-returned_data_policy",
                    "so2-legal_barriers_exploratory", "mucp-consent-sharing", "qms-sops"}
    if set(heatmaps) != expected_ids:
        raise ValueError("Report presentation must define exactly the seven approved heatmaps")
    fields = {"heading", "row_axis_lines", "column_axis_lines", "row_tick_labels", "column_tick_labels"}
    for definition_id, entry in heatmaps.items():
        if not isinstance(definition_id, str) or not isinstance(entry, dict) or set(entry) != fields:
            raise ValueError("Report presentation heatmap definition has invalid fields")
        if not isinstance(entry["heading"], str) or not entry["heading"].strip():
            raise ValueError(f"Report presentation heatmap {definition_id} needs a heading")
        for axis in ("row", "column"):
            lines = entry[f"{axis}_axis_lines"]
            ticks = entry[f"{axis}_tick_labels"]
            if (not isinstance(lines, list) or not 1 <= len(lines) <= 3
                    or any(not isinstance(line, str) or not line.strip() for line in lines)):
                raise ValueError(f"Report presentation heatmap {definition_id} needs 1-3 {axis} axis lines")
            if (not isinstance(ticks, dict) or not ticks
                    or any(not isinstance(key, str) or not key or not isinstance(label, str) or not label.strip()
                           for key, label in ticks.items())):
                raise ValueError(f"Report presentation heatmap {definition_id} needs curated {axis} tick labels")
    return value


def validate_heatmap_presentation(
    definitions: Sequence[Mapping[str, Any]], presentation: Mapping[str, Any],
) -> None:
    """Reject uncurated combined heatmap categories before any output publication.

    Args:
        definitions: Built or registry heatmap definitions with stable ID and axes.
        presentation: Validated version 1 report presentation metadata.

    Returns:
        None. Every supplied category has an explicit approved short label.

    Raises:
        ValueError: If a definition or category has no curated presentation entry.
    """
    curated = presentation["heatmaps"]
    for definition in definitions:
        definition_id = str(definition["definition_id"])
        if definition_id not in curated:
            raise ValueError(f"Heatmap {definition_id} has no curated presentation")
        for axis in ("row", "column"):
            unknown = set(definition[f"{axis}_categories"]) - set(curated[definition_id][f"{axis}_tick_labels"])
            if unknown:
                raise ValueError(f"Heatmap {definition_id} requires curated {axis} category label: {sorted(unknown)!r}")


def _compact_source_context(value: Any) -> str:
    """Remove only known machine provenance prefixes from reader-facing text.

    Args:
        value: Literal source text or label to compact without changing substantive wording.

    Returns:
        Text with leading response/submission serialization labels removed.
    """
    return descriptive._compact_report_context(value)


def _tex(value: Any, include_contact_details: bool = False) -> str:
    """Escape literal data for ordinary TeX text and mask email addresses.

    Args:
        value: Literal report value, potentially containing an email address.
        include_contact_details: Whether to retain email-shaped text in this view.

    Returns:
        TeX-safe text with email-shaped contact details redacted.
    """
    safe = str(value)
    if not include_contact_details:
        safe = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[contact redacted]", safe)
    return descriptive._tex(safe)


def _slug(value: str) -> str:
    """Create a bounded ASCII filename component.

    Args:
        value: Human-readable label or identifier.

    Returns:
        Lowercase hyphenated ASCII component, possibly empty.
    """
    return descriptive._slug(value)[:72].rstrip("-")


def _biobank_identifier(biobank: Mapping[str, Any]) -> str:
    """Return the canonical biobank identifier from supported payload fields.

    Args:
        biobank: Combined biobank mapping.

    Returns:
        Biobank ID or a stable explicit unknown marker.
    """
    return str(biobank.get("biobank_id", biobank.get("id", "unknown-biobank")))


def _contact_field(item: Mapping[str, Any]) -> bool:
    """Recognize dedicated identity/contact fields for publication filtering.

    Args:
        item: Evidence mapping whose field identifiers and labels are inspected.

    Returns:
        Whether the evidence item is a submitter/name/email contact field.
    """
    values = [str(item.get(key, "")) for key in (
        "question_id", "question_label", "field", "column", "field_name",
    )]
    fields = {
        re.sub(r"[^a-z0-9]+", "", part.casefold())
        for value in values for part in re.split(r"[._:/\\-]+", value)
        if part
    }
    contact_names = {
        "name", "first", "firstname", "last", "lastname", "givenname", "surname",
        "email", "emailaddress", "submitter", "contactname", "contactperson", "contactemail",
    }
    return bool(fields & contact_names)


def _compact_identifier(value: Any) -> str:
    """Shorten hash-like references for publication while preserving their JSON originals.

    Args:
        value: Source locator or evidence identifier.

    Returns:
        Human-sized reference with long hexadecimal runs abbreviated.
    """
    text = str(value)
    return re.sub(r"[0-9a-fA-F]{24,}", lambda match: match.group(0)[:12] + "...", text)


def _breakable_identifier(value: Any, include_contact_details: bool = False) -> str:
    """Render a compact monospace reference with line-break opportunities.

    Args:
        value: Source ID or locator to render.
        include_contact_details: Whether email-shaped text is permitted.

    Returns:
        Small monospace TeX with legal breaks through long identifier runs.
    """
    text = _compact_identifier(value)
    if not include_contact_details:
        text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[contact redacted]", text)
    chunks = [text[index:index + 10] for index in range(0, len(text), 10)]
    escaped = r"\allowbreak{}".join(descriptive._tex(chunk) for chunk in chunks)
    return r"\texttt{\scriptsize " + escaped + "}"


def _breakable_text(value: Any, include_contact_details: bool = False) -> str:
    """Escape literal text with invisible break points for long inventory names.

    Args:
        value: Literal filename or other untrusted display text.
        include_contact_details: Whether email-shaped text is permitted.

    Returns:
        TeX-safe text preserving every character while allowing line wrapping.
    """
    text = str(value)
    if not include_contact_details:
        text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[contact redacted]", text)
    return r"\allowbreak{}".join(
        _tex(text[index:index + 14]) for index in range(0, len(text), 14)
    )


def _display_value(value: Any, include_contact_details: bool) -> str:
    """Convert scalar/list evidence to privacy-aware literal display text.

    Args:
        value: Raw or normalized answer value, including meaningful false/null.
        include_contact_details: Whether email-shaped text is permitted in output.

    Returns:
        Stable literal string, preserving false and null rather than dropping them.
    """
    if value is None:
        text = "null"
    elif value is False:
        text = "false"
    elif value is True:
        text = "true"
    elif isinstance(value, (list, tuple)):
        text = "; ".join(map(str, value))
    elif isinstance(value, Mapping):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    if not include_contact_details:
        text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[contact redacted]", text)
    return text


def dossier_source_rows(
    biobank: Mapping[str, Any], source_manifest: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    """Join dossier response IDs to deduplicated source-manifest filenames.

    Args:
        biobank: Combined biobank record with MuCP source records in metadata form.
        source_manifest: Already-validated source rows keyed by ``source_id``; no
            file reads or source reconstruction are performed here.

    Returns:
        Stable response-ID/filename rows containing basenames only, deduplicated
        by original response and source ID across assigned scopes. Distinct source
        IDs retain separate rows even with equal filenames. Missing filenames use
        the explicit ``Filename not supplied`` marker.
    """
    manifest_by_id = {
        str(item["source_id"]): item for item in source_manifest
        if isinstance(item, Mapping) and item.get("source_id") is not None
    }
    rows: list[dict[str, str]] = []
    records = biobank.get("mucp_source_records", [])
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        return rows
    response_sources: dict[str, set[str]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            continue
        metadata = record.get("metadata", {})
        if not isinstance(metadata, Mapping):
            metadata = {}
        response_id = str(metadata.get("response_id", record.get("record_id", "Response ID unavailable")))
        source_ids = response_sources.setdefault(response_id, set())
        for field in ("source_ids", "full_evidence_source_ids"):
            values = metadata.get(field, [])
            if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
                source_ids.update(str(value) for value in values if value is not None)
        metadata_refs = metadata.get("source_refs", [])
        if isinstance(metadata_refs, Sequence) and not isinstance(metadata_refs, (str, bytes)):
            source_ids.update(str(ref["source_id"]) for ref in metadata_refs
                              if isinstance(ref, Mapping) and ref.get("source_id") is not None)
        for evidence in biobank.get("evidence", []):
            if (not isinstance(evidence, Mapping)
                    or str(evidence.get("source_record_id")) not in {response_id, str(record.get("record_id"))}):
                continue
            refs = evidence.get("source_refs", [])
            if isinstance(refs, Sequence) and not isinstance(refs, (str, bytes)):
                source_ids.update(str(ref["source_id"]) for ref in refs
                                  if isinstance(ref, Mapping) and ref.get("source_id") is not None)
    for response_id, source_ids in response_sources.items():
        if not source_ids:
            rows.append({"response_id": response_id, "filename": "Filename not supplied"})
        for source_id in sorted(source_ids):
            manifest_item = manifest_by_id.get(source_id, {})
            filename = manifest_item.get("filename")
            if not isinstance(filename, str) or not filename.strip():
                basename = "Filename not supplied"
            else:
                basename = filename.replace("\\", "/").rsplit("/", 1)[-1] or "Filename not supplied"
            rows.append({"response_id": response_id, "filename": basename})
    return sorted(rows, key=lambda item: (item["response_id"].casefold(), item["filename"].casefold()))


def human_answer_rows(item: Mapping[str, Any], extended: bool) -> list[tuple[str, str]]:
    """Create reader-facing answer rows or the technical extended-evidence view.

    Args:
        item: One immutable source-evidence contribution.
        extended: Whether to retain machine state, normalized/raw fields and locators.

    Returns:
        Label/value pairs; compact output contains one human answer per contribution.
    """
    survey_value = str(item.get("survey", "Unknown"))
    survey = "SO2" if survey_value.casefold() == "so2" else "MuCP" if survey_value.casefold() == "mucp" else survey_value
    question = str(item.get("question_label") or item.get("question_id") or item.get("kind") or "Question")
    question_id = item.get("question_id", "")
    scope = str(item.get("scope_label", ""))
    state = str(item.get("answer_state", "unknown"))
    normalized = item.get("normalized_value")
    if extended:
        refs = item.get("source_refs", [])
        first_ref = refs[0] if isinstance(refs, Sequence) and refs and isinstance(refs[0], Mapping) else {}
        rows = [
            ("Source / question / scope",
             f"[{survey}] {question} (ID: {question_id}); "
             f"response: {_compact_identifier(item.get('source_record_id', 'unavailable'))}; "
             f"scope: {scope or 'Scope unavailable'}; locator: {first_ref.get('locator', 'unavailable')}"),
            ("Answer state", state),
            ("Normalized value", _display_value(normalized, True)),
            ("Raw answer", _display_value(item.get("raw_answer"), True)),
        ]
        raw_text = item.get("raw_text", item.get("message", item.get("warning")))
        if raw_text is not None:
            rows.append(("Raw text", _display_value(raw_text, True)))
        qualifier = item.get("qualifier_text")
        if qualifier is not None and str(qualifier).strip():
            rows.append(("Qualifier", str(qualifier)))
        rows.append(("Evidence ID", _compact_identifier(item.get("evidence_id", "unavailable"))))
        return rows

    mucp_checkbox = survey == "MuCP" and item.get("kind") == "structured_answer"
    if mucp_checkbox:
        state_labels = {
            "affirmed": "Yes",
            "explicit_negative": "No",
            "unknown": "Unknown",
            "conditional": "Conditional",
            "ambiguous_or_source_conflict": "Unknown (ambiguous or conflicting source evidence)",
        }
        answer = state_labels.get(normalized, "Unknown") if isinstance(normalized, str) else "Unknown"
        raw_text = item.get("raw_text")
        if raw_text is not None and str(raw_text).strip() and not _is_checkbox_restatement(item, raw_text):
            clean_text = _compact_source_context(raw_text)
            if normalized == "conditional":
                answer += ": " + clean_text
            elif clean_text:
                answer += "; " + clean_text
    else:
        raw_text = item.get("raw_text", item.get("message", item.get("warning")))
        raw_answer = item.get("raw_answer")
        answer_value = raw_text if raw_text is not None else raw_answer
        answer = _compact_source_context(_display_value(answer_value, True)) if answer_value is not None else "Unknown"
        if isinstance(raw_answer, (str, int, float)) and str(raw_answer).strip():
            raw_display = _compact_source_context(_display_value(raw_answer, True))
            if raw_display and raw_display not in answer:
                answer = raw_display + ("; " + answer if answer != "Unknown" else "")
    qualifier = item.get("qualifier_text")
    if qualifier is not None and str(qualifier).strip():
        clean_qualifier = _compact_source_context(qualifier)
        if clean_qualifier and clean_qualifier not in answer:
            answer += "; " + clean_qualifier
    scope_suffix = ""
    response_label = item.get("response_label")
    contexts = [str(response_label)] if response_label else []
    if scope and scope.casefold() not in {"submission", "biobank-wide", "biobank wide"}:
        contexts.append(_compact_source_context(scope))
    context_suffix = " (" + "; ".join(contexts) + ")" if contexts else ""
    label = f"[{survey}] {_compact_source_context(question)}{context_suffix}"
    return [(label, answer)]


def _is_checkbox_restatement(item: Mapping[str, Any], value: Any) -> bool:
    """Recognize only a bare option/tick restatement of its displayed question.

    Args:
        item: Structured MuCP answer with a question label/ID and raw option.
        value: Raw text considered for omission from the compact answer row.

    Returns:
        Whether the text is exactly the question/option label, optionally ticked.
    """
    text = str(value).strip()
    bare = re.sub(r"^\s*(?:[xX✓✔☒☑]\s*)", "", text).strip()
    candidates = {
        str(item.get("question_label", "")).strip().casefold(),
        str(item.get("question_id", "")).rsplit(".", 1)[-1].rsplit("_", 1)[-1].strip().casefold(),
    }
    normalized = item.get("normalized_value")
    if normalized == "affirmed":
        candidates.add("yes")
    elif normalized == "explicit_negative":
        candidates.add("no")
    raw_answer = str(item.get("raw_answer", "")).strip()
    raw_answer_bare = re.sub(r"^\s*(?:[xX✓✔☒☑]\s*)", "", raw_answer).strip().casefold()
    if raw_answer_bare in candidates:
        candidates.add(raw_answer_bare)
    return bool(bare) and bare.casefold() in candidates


def format_reported_quantity(quantity: Mapping[str, Any]) -> str:
    """Format a source-classified reported total with exact relation semantics.

    Args:
        quantity: One authoritative ``reported_total`` mapping. Narrative numeric
            mentions must not be passed here because their indexed units may be
            unsupported; render those with an explicit unverified-unit notice.

    Returns:
        TeX-safe quantity, temporal qualifier, source qualifier, and original
        wording. Math symbols are emitted once as TeX math and not re-escaped.

    Raises:
        ValueError: If the value/unit or the relation/time category is unsupported.
    """
    value = quantity.get("value")
    unit = quantity.get("unit")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("A reported quantity requires a finite numeric value")
    if not isinstance(unit, str) or not unit.strip():
        raise ValueError("A reported quantity requires a source-classified unit")
    numeric = f"{value:g}" if isinstance(value, float) else str(value)
    relation = quantity.get("relation", "reported_value")
    symbols = {
        "less_than": "$<$", "strictly_less_than": "$<$", "less_than_exclusive": "$<$",
        "at_most": r"$\leq$", "less_than_or_equal": r"$\leq$",
        "greater_than": "$>$", "strictly_greater_than": "$>$",
        "at_least": r"$\geq$", "greater_than_or_equal": r"$\geq$",
        "approximately": r"$\approx$", "approximate": r"$\approx$",
    }
    if relation == "approximate_upper_bound":
        result = f"approximately at most {numeric} {_tex(unit)}"
    elif relation == "approximate_lower_bound":
        result = f"approximately at least {numeric} {_tex(unit)}"
    elif relation == "reported_value":
        result = f"{numeric} {_tex(unit)}"
    elif relation in symbols:
        result = f"{symbols[relation]}{numeric} {_tex(unit)}"
    else:
        raise ValueError(f"Unsupported reported quantity relation: {relation!r}")

    temporal = quantity.get("temporal_status")
    if temporal is not None:
        if not isinstance(temporal, str):
            raise ValueError("Reported quantity temporal status must be text")
        temporal_labels = {"unspecified": "", "current": "current", "future": "future",
                           "historical": "historical", "cumulative": "cumulative",
                           "previous": "previous"}
        temporal_label = temporal_labels.get(temporal)
        if temporal_label is None:
            temporal_label = "as recorded: " + temporal.replace("_", " ")
        if temporal_label:
            result += f" ({_tex(temporal_label)})"
    qualifier = quantity.get("qualifier_text")
    if qualifier is not None and str(qualifier).strip():
        result += "; " + _tex(qualifier)
    raw_text = quantity.get("raw_text")
    if raw_text is not None and str(raw_text).strip():
        result += "; Original wording [MuCP]: " + _tex(raw_text)
    return result


def _compact_material(value: Any) -> Any:
    """Remove technical provenance fields from a presentation-only value copy.

    Args:
        value: Original structured answer or supplemental value, never mutated.

    Returns:
        Recursively copied semantic material without source locators/identifiers.
        Full provenance remains in the original combined JSON evidence.
    """
    technical = {"evidence", "source_refs", "source_id", "source_record_id", "evidence_id",
                 "locator", "input_json_pointer", "input_sha256", "source_sha256"}
    if isinstance(value, Mapping):
        return {key: _compact_material(child) for key, child in value.items() if key not in technical}
    if isinstance(value, (list, tuple)):
        return [_compact_material(child) for child in value]
    return value


def _theme_question_ids(theme: Mapping[str, Any]) -> set[str]:
    """Extract survey-qualified question selectors from one crosswalk theme.

    Args:
        theme: Thematic crosswalk entry containing question selector strings.

    Returns:
        Set of bare question IDs and survey-qualified selectors recognized by the theme.
    """
    selectors = theme.get("questions", theme.get("question_ids", []))
    if isinstance(selectors, Mapping):
        selectors = [value for values in selectors.values()
                     for value in (values if isinstance(values, list) else [values])]
    if not isinstance(selectors, Sequence) or isinstance(selectors, (str, bytes)):
        return set()
    result = set()
    for selector in selectors:
        value = str(selector)
        result.add(value)
        if ":" in value:
            result.add(value.split(":", 1)[1])
    return result


def _text_rows(label: str, text: str) -> list[list[str]]:
    """Split literal text into page-sized table cells without discarding wording.

    Args:
        label: Reader-facing field label, repeated on continuation rows.
        text: Privacy-filtered literal source text, before TeX escaping.

    Returns:
        Label and escaped value pairs, split between whitespace-separated tokens.
        URL tokens remain intact and are displayed as hyperlinks.
    """
    from survey_descriptive import text_chunks
    chunks = text_chunks(text)
    return [["{}" + _tex(label + (" (continued)" if index else "")),
             descriptive._tex_with_links(chunk)] for index, chunk in enumerate(chunks)]


def _combined_biobank_table(
    rows: Sequence[Mapping[str, Any]], columns: str, headers: Sequence[str],
    options: Mapping[str, Any], biobank_column_index: int = 0,
) -> str:
    """Route a combined-report biobank-column table through its block renderer.

    Args:
        rows: Validated renderer rows with canonical bank identity and TeX-ready cells.
        columns: Longtable column specification including the biobank column.
        headers: TeX-ready headers in rendered column order.
        options: Combined rendering options including the repeat-cell choice.
        biobank_column_index: Position of the rendered biobank column.

    Returns:
        TeX for bank-grouped blocks with fixed continuation labels.
    """
    from survey_combined_tables import render_biobank_table

    return render_biobank_table(
        rows, columns, headers,
        repeated_entries=options.get("table_biobank_repeated_entries", "empty"),
        biobank_column_index=biobank_column_index,
        country_headings=options.get("country_headings", False),
    )


def _quantity_exclusion_label(reason: Any) -> str:
    """Translate quantity exclusion codes into approachable report wording.

    Args:
        reason: Stored machine-readable code explaining why a count is not additive.

    Returns:
        Human-readable wording; unknown codes retain their space-separated spelling.
        Different counts are not described as respondent errors or contradictions.
    """
    labels = {
        "same_scope_conflicting_quantities": "Different reported counts; cannot safely add them",
        "qualified_relation": "Approximate count or bound, not an exact total",
        "non_current_time": "Historical or future count, not a current total",
        "same_scope_mixed_temporal_status": "Counts refer to different times",
        "ambiguous_submission_scopes": "Population overlap between submissions unclear",
        "unsupported_unit": "Count unit unclear",
    }
    return labels.get(str(reason), str(reason).replace("_", " "))


def _quantity_wording_adds_information(quantity: Mapping[str, Any], raw_text: Any) -> bool:
    """Detect source-answer wording that adds content beyond the parsed amount.

    Args:
        quantity: Parsed scoped quantity retaining its value, unit and relation.
        raw_text: Full source-owned answer text, not a clipped quantity-index window.

    Returns:
        Whether meaningful source wording remains after removing the parsed numeric
        amount, unit synonyms, relation wording, and current-time qualifier.
    """
    text = str(raw_text).casefold()
    value = quantity.get("value")
    from survey_mucp_quantities import _count_measurement
    literal = _count_measurement(str(raw_text)) or _count_measurement(str(raw_text), numeric_only=True)
    if literal is not None and literal["value"] == value:
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        text = re.sub(re.escape(f"{value:g}" if isinstance(value, float) else str(value)), " ", text)
    text = re.sub(
        r"\b(?:donors?|individuals?|persons?|people|participants?|samples?|aliquots?)\b",
        " ", text,
    )
    text = re.sub(
        r"\b(?:at\s+most|up\s+to|no\s+more\s+than|at\s+least|over|more\s+than|"
        r"approximately|about|around|current|currently|reported|count|counts)\b",
        " ", text,
    )
    return bool(re.sub(r"[^a-z]+", "", text))


def _material_rows(value: Any, prefix: str, include_contact_details: bool,
                   extended_evidence: bool = False) -> list[list[str]]:
    """Flatten supplemental source material into bounded, readable table rows.

    Args:
        value: Original nested material; full values remain unchanged in JSON.
        prefix: Source-qualified path identifying the material in the dossier.
        include_contact_details: Whether email-shaped text is retained.
        extended_evidence: Whether nested technical source locators are displayed.

    Returns:
        Escaped field/value pairs. Bulk locator lists are summarized with their
        count and a JSON reference; substantive text is split, not truncated.
    """
    rows: list[list[str]] = []
    if isinstance(value, Mapping):
        for key, child in sorted(value.items()):
            if not extended_evidence and key in {"source_id", "source_record_id", "evidence_id",
                                                 "locator", "input_json_pointer", "input_sha256", "source_sha256"}:
                continue
            dedicated_contact = re.sub(r"[^a-z]", "", key.casefold()) in {
                "contact", "contacts", "contactdetails", "contactname", "contactperson", "contactemail",
                "email", "emailaddress", "submitter", "submittername", "respondentname", "firstname", "lastname", "responsibleperson",
            }
            if dedicated_contact and not include_contact_details:
                continue
            path = f"{prefix} / {key}"
            if key in {"evidence", "source_refs"} and isinstance(child, (list, tuple)):
                preview = ("; " + _display_value(list(child[:1]), include_contact_details)) if extended_evidence else ""
                rows.extend(_text_rows(path, f"{len(child)} evidence locators retained in JSON" + preview))
            else:
                rows.extend(_material_rows(child, path, include_contact_details, extended_evidence))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value, start=1):
            rows.extend(_material_rows(child, f"{prefix} / {index}", include_contact_details, extended_evidence))
    else:
        display = _display_value(value, include_contact_details)
        rows.extend(_text_rows(prefix, display if extended_evidence else _compact_source_context(display)))
    return rows


def _evidence_table(items: Sequence[Mapping[str, Any]], include_contact_details: bool,
                    extended_evidence: bool = False) -> str:
    """Render independent provenance-bearing evidence rows without data reduction.

    Args:
        items: Ordered source evidence items in one dossier topic.
        include_contact_details: Whether dedicated contact fields and email text appear.
        extended_evidence: Whether technical source IDs, locators and hashes appear.

    Returns:
        Escaped TeX table. Compact mode puts full source-tagged prompts and human
        answers in the wide value column with short pageable field labels;
        extended mode retains state, normalized/raw answer, scope and locators.
    """
    rows = [["Evidence field", "Source value"]]
    for item in items:
        survey = str(item.get("survey", "Unknown"))
        source = "SO2" if survey.casefold() == "so2" else "MuCP" if survey.casefold() == "mucp" else survey
        if not extended_evidence:
            for label, value in human_answer_rows(item, False):
                rows.extend(_text_rows(f"[{source}] Question", _display_value(label, include_contact_details)))
                rows.extend(_text_rows(f"[{source}] Answer", _display_value(value, include_contact_details)))
            continue
        refs = item.get("source_refs", [])
        locator = ""
        if refs and isinstance(refs[0], Mapping):
            locator = str(refs[0].get("locator", ""))
        evidence_id = str(item.get("evidence_id", ""))
        question_id = item.get("question_id", "")
        question = item.get("question_label", item.get("question_id", item.get("kind", "Question")))
        scope = item.get("scope_label", item.get("scope_id", "Scope unavailable"))
        if not extended_evidence and source == "SO2" and str(scope).startswith("Submission;"):
            scope = "Submission"
        source_question = (
            f"[{source}] {_tex(question, include_contact_details)} "
            f"(ID: {descriptive._question_identifier(question_id)}); "
            f"source record: {_breakable_identifier(item.get('source_record_id', 'unavailable'), include_contact_details)}; "
            f"scope: {_tex(scope, include_contact_details)}; locator: "
            f"{_breakable_identifier(locator or 'unavailable', include_contact_details)}; "
            f"evidence: {_breakable_identifier(evidence_id or 'unavailable', include_contact_details)}"
        )
        if not extended_evidence:
            source_question = f"[{source}] {_tex(question, include_contact_details)}"
        rows.extend([
            ["Source / question / scope" if extended_evidence else "Question", source_question],
            ["Scope", _tex(scope, include_contact_details)],
            ["Answer state", _tex(item.get("answer_state", "unspecified"), include_contact_details)],
        ])
        grouped: dict[str, list[str]] = {}
        for label, value in (
            ("Normalized value", item.get("normalized_value")), ("Raw answer", item.get("raw_answer")),
            ("Raw text", item.get("raw_text", item.get("message", item.get("warning")))),
            ("Qualifier", item.get("qualifier_text")),
        ):
            if label == "Qualifier" and (value is None or not str(value).strip()):
                continue
            # Fold literal values before privacy masking: redaction is not equality.
            literal = _display_value(value if extended_evidence else _compact_material(value), True)
            grouped.setdefault(literal, []).append(label)
        for literal, labels in grouped.items():
            rows.extend(_text_rows(f"[{source}] {' / '.join(labels)}",
                                   _display_value(literal, include_contact_details)))
    return descriptive._table(
        rows,
        r"p{0.25\linewidth}p{0.71\linewidth}" if extended_evidence
        else r"p{0.30\linewidth}p{0.66\linewidth}",
    )


def render_biobank_dossier(biobank: Mapping[str, Any], options: Mapping[str, Any]) -> str:
    """Render one reusable, contact-safe biobank evidence dossier fragment.

    Args:
        biobank: Combined biobank mapping with evidence, observations and identity.
        options: Presentation options; ``include_contact_details`` explicitly
            enables dedicated submitter/name/email fields and unmasked email text.
            ``directory_target`` and ``directory_schema`` select the web-view
            link base; omitted values use the public ERIC Directory.
            ``extended_evidence`` enables technical answer-source references.
            ``dossier_heading_level`` selects section (standalone default) or
            subsection (within the combined evidence appendix).

    Returns:
        TeX fragment containing identity, scoped source evidence and summaries.
    """
    include_contacts = bool(options.get("include_contact_details", False))
    extended = bool(options.get("extended_evidence", False))
    heading = options.get("dossier_heading_level", "section")
    if heading not in {"section", "subsection"}:
        raise ValueError("Dossier heading must be section or subsection")
    bid = _biobank_identifier(biobank)
    name = biobank.get("name", "Name unavailable")
    country = biobank.get("country", "Country unavailable")
    url = (str(options.get("directory_target", "https://directory.bbmri-eric.eu")).rstrip("/")
           + "/" + str(options.get("directory_schema", "ERIC")) + "/directory/#/biobank/" + bid)
    lines = [
        rf"\{heading}{{Biobank dossier: {_tex(name, include_contacts)}}}",
        rf"\label{{dossier-{sha256(bid.encode()).hexdigest()[:16]}}}",
        rf"\noindent Directory biobank: \href{{{_tex(url, True)}}}{{{_tex(bid, include_contacts)}}}; country: {_tex(country, include_contacts)}\par",
    ]
    evidence = [item for item in biobank.get("evidence", []) if isinstance(item, Mapping)]
    visible = [item for item in evidence if include_contacts or not _contact_field(item)]
    visible.sort(key=lambda item: (
        str(item.get("source_record_id", "")).casefold(),
        str(item.get("scope_label", item.get("scope_id", ""))).casefold(),
        str(item.get("question_id", "")).casefold(),
    ))
    source_records = biobank.get("mucp_source_records", [])
    response_ids = sorted({
        str(record.get("metadata", {}).get("response_id", record.get("record_id", "Response ID unavailable")))
        for record in source_records if isinstance(record, Mapping)
        and isinstance(record.get("metadata", {}), Mapping)
    }, key=str.casefold)
    response_labels = {response_id: f"Response {index}"
                       for index, response_id in enumerate(response_ids, start=1)}
    if len(response_ids) > 1:
        visible = [{**item, "response_label": response_labels.get(str(item.get("source_record_id", "")))}
                   if str(item.get("survey", "")).casefold() == "mucp" else dict(item)
                   for item in visible]
    inventory = dossier_source_rows(biobank, options.get("source_manifest", []))
    inventory_rows = [["MuCP response ID", "Source filename"]]
    missing_names = 0
    for source in inventory:
        missing_names += source["filename"] == "Filename not supplied"
        response_id = source["response_id"]
        response_display = (
            f"{response_labels[response_id]} ({response_id})"
            if len(response_ids) > 1 and response_id in response_labels else response_id
        )
        inventory_rows.append([
            _breakable_identifier(response_display, include_contacts),
            _breakable_text(source["filename"], include_contacts),
        ])
    lines.extend([
        r"\subsection*{MuCP response source files}",
        descriptive._table(inventory_rows, r"p{0.34\linewidth}p{0.60\linewidth}"),
    ])
    if missing_names:
        lines.append(rf"\emph{{Diagnostic: filename not supplied for {missing_names} MuCP source reference(s); no filename was inferred.}}")
    themes = [item for item in biobank.get("thematic_groups", []) if isinstance(item, Mapping)]
    assigned: set[int] = set()
    for theme in themes:
        selectors = _theme_question_ids(theme)
        selected = []
        for item in visible:
            survey = str(item.get("survey", "Unknown"))
            qid = str(item.get("question_id", ""))
            if qid in selectors or f"{survey}:{qid}" in selectors:
                selected.append(item)
                assigned.add(id(item))
        selected.sort(key=lambda item: (
            str(item.get("source_record_id", "")).casefold(),
            str(item.get("scope_label", item.get("scope_id", ""))).casefold(),
            str(item.get("question_id", "")).casefold(),
        ))
        lines.extend([
            rf"\subsection*{{{_tex(theme.get('title', 'Thematic contribution'))}}}",
            rf"\noindent Relationship: {_tex(theme.get('relationship', 'not specified'))}. "
            rf"{_tex(theme.get('explanation', ''))}\par",
        ])
        if selected:
            lines.extend([r"\smaller[1]", _evidence_table(selected, include_contacts, extended), r"\normalsize"])
        else:
            lines.append(r"\emph{No linked source contributions were supplied for this theme.}")
    remaining = [item for item in visible if id(item) not in assigned]
    if remaining:
        heading = "Additional source evidence" if themes else "Source evidence"
        lines.extend([
            rf"\subsection*{{{heading}}}", r"\smaller[1]",
            _evidence_table(remaining, include_contacts, extended), r"\normalsize",
        ])
    elif not visible:
        lines.append(r"\emph{No publishable source evidence is available for this biobank.}")
    for field, heading, text_field in (
        ("narratives", "Root narratives", "raw_text"),
        ("warnings", "Source warnings", "message"),
    ):
        records = []
        for index, value in enumerate(biobank.get(field, []), start=1):
            record = dict(value) if isinstance(value, Mapping) else {text_field: value}
            record.setdefault("survey", "Unknown")
            record.setdefault("kind", field[:-1])
            record.setdefault("question_id", f"{field}.{index}")
            record.setdefault("evidence_id", record.get("source_record_id", f"{field}-{index}"))
            records.append(record)
        if records:
            lines.extend([rf"\subsection*{{{heading}}}", r"\smaller[1]",
                          _evidence_table(records, include_contacts, extended), r"\normalsize"])
    scopes = biobank.get("scopes", {})
    for scope in scopes.values() if isinstance(scopes, Mapping) else scopes:
        if scope.get("kind") != "collection" or scope.get("survey", "MuCP") != "MuCP":
            continue
        metadata = scope.get("metadata", {})
        if metadata:
            reference = (rf"; source record: {_breakable_identifier(scope.get('source_record_id'), include_contacts)}"
                         if extended else "")
            lines.extend([r"\subsection*{[MuCP] Collection scope details}",
                rf"\noindent Scope: {_tex(scope.get('label', scope.get('scope_id')), include_contacts)}" + reference + r"\par",
                r"\smaller[1]", descriptive._table([["Field", "Original scoped value"]] +
                    _material_rows(metadata, "[MuCP] Collection", include_contacts, extended),
                    r"p{0.20\linewidth}p{0.74\linewidth}"), r"\normalsize"])
    for index, record in enumerate(biobank.get("mucp_source_records", []), start=1):
        metadata = record.get("metadata", {})
        supplemental = {key: metadata[key] for key in ("structured_tables", "quantity_index", "extraction_notes") if metadata.get(key)}
        if supplemental:
            source = (_breakable_identifier(record.get("source_response_id", record["record_id"]), include_contacts)
                      if extended else str(index))
            lines.extend([r"\subsection*{[MuCP] Supplemental source material}",
                rf"\noindent MuCP submission: {source}\par",
                r"\smaller[1]", descriptive._table([["Field", "Original source value"]] +
                    _material_rows(supplemental, "[MuCP] Material", include_contacts, extended),
                    r"p{0.20\linewidth}p{0.74\linewidth}"), r"\normalsize"])
    observations = biobank.get("observations", [])
    if observations:
        lines.extend([r"\subsection*{Derived summary observations}"])
        question_labels = {(item.get("survey"), item.get("question_id")): item.get("question_label")
                           for item in visible if item.get("question_label")}
        for observation in observations:
            if not isinstance(observation, Mapping):
                continue
            survey = str(observation.get("survey", "Unknown"))
            source = "SO2" if survey.casefold() == "so2" else "MuCP" if survey.casefold() == "mucp" else survey
            question = observation.get("question_label") or question_labels.get(
                (survey, observation.get("question_id")), observation.get("question_id", "Question"))
            state = observation.get("state", "unspecified")
            refs = observation.get("contribution_ids", observation.get("evidence_ids", []))
            references = (rf"; evidence references: {', '.join(_breakable_identifier(ref, include_contacts) for ref in refs[:3]) or 'none recorded'}"
                          rf"{f'; {len(refs) - 3} additional contributions retained in JSON' if len(refs) > 3 else ''}") if extended else ""
            lines.append(rf"\noindent [{_tex(source, include_contacts)}] Derived summary: "
                         rf"{_tex(question, include_contacts)} = {_tex(state.replace('_', ' '), include_contacts)}"
                         + references + r"\par")
    return "\n".join(lines)


def _dossier_filename(biobank: Mapping[str, Any]) -> str:
    """Build a stable safe filename using a readable slug and ID digest.

    Args:
        biobank: Combined biobank mapping with its canonical ID and display name.

    Returns:
        A safe relative TeX filename that does not expose punctuation from the ID.
    """
    bid = _biobank_identifier(biobank)
    stem = _slug(str(biobank.get("name", "biobank"))) or "biobank"
    digest = sha256(bid.encode("utf-8")).hexdigest()[:10]
    return f"{stem}-{digest}.tex"


def render_individual_biobank_documents(
    payload: Mapping[str, Any], options: Mapping[str, Any],
) -> Mapping[str, str]:
    """Render standalone TeX documents from the same dossier fragments.

    Args:
        payload: Combined payload containing the overlapping ``biobanks`` list.
        options: Shared report presentation options.

    Returns:
        Mapping of safe relative TeX filenames to complete standalone documents.
    """
    documents: dict[str, str] = {}
    for biobank in payload.get("biobanks", []):
        filename = _dossier_filename(biobank)
        if filename in documents:
            raise descriptive.InputError(f"Biobank dossier filename collision: {filename}")
        body = render_biobank_dossier(biobank, {
            **options, "source_manifest": payload.get("source_manifest", options.get("source_manifest", [])),
        })
        documents[filename] = "\n".join([
            descriptive._preamble(), r"\begin{document}",
            r"\tableofcontents", body, r"\end{document}", "",
        ])
    return documents


def _render_heatmaps(
    cross_survey: Mapping[str, Any], question_labels: Mapping[str, str],
) -> tuple[list[str], dict[str, str], list[str]]:
    """Render configured combined heatmaps and retain missing-definition diagnostics.

    Args:
        cross_survey: Cross-survey statistics mapping with optional ``heatmaps``.
        question_labels: Question labels keyed by question identifier.

    Returns:
        TeX fragments, chart-fragment mapping and omission diagnostics.
    """
    body: list[str] = []
    fragments: dict[str, str] = {}
    diagnostics: list[str] = []
    heatmaps = cross_survey.get("heatmaps", [])
    if isinstance(heatmaps, Mapping):
        heatmaps = list(heatmaps.values())
    for item in heatmaps:
        if not isinstance(item, Mapping):
            diagnostics.append("A cross-survey heatmap entry was omitted because it is not a mapping.")
            continue
        definition = item.get("definition")
        pair = item.get("pair", item.get("statistics"))
        definition_id = item.get("definition_id", definition.get("definition_id", "unknown")
                               if isinstance(definition, Mapping) else "unknown")
        omission = item.get("omission_reason")
        if omission:
            diagnostics.append(f"Heatmap {definition_id} omitted: {omission}")
            body.append(rf"\emph{{Heatmap {_tex(definition_id)} omitted: {_tex(omission)}}}")
            continue
        if not isinstance(definition, Mapping) or not isinstance(pair, Mapping):
            diagnostics.append(f"Heatmap {definition_id} omitted: definition or pair is unavailable.")
            continue
        unit = str(item.get("unit", "survey-participating biobanks"))
        key = "heatmap-" + (_slug(str(definition_id)) or "pair")
        supplied_labels = item.get("question_labels", [])
        if isinstance(supplied_labels, Mapping):
            labels = dict(supplied_labels)
        else:
            labels = dict(question_labels)
            if isinstance(supplied_labels, Sequence) and not isinstance(supplied_labels, (str, bytes)):
                if len(supplied_labels) > 0:
                    labels[str(definition.get("row_question_id", ""))] = str(supplied_labels[0])
                if len(supplied_labels) > 1:
                    labels[str(definition.get("column_question_id", ""))] = str(supplied_labels[1])
        presentation = definition.get("presentation")
        fragment = descriptive._association_heatmap_fragment(
            definition, pair, labels, unit=unit,
        )
        if isinstance(presentation, Mapping):
            row_id = str(definition["row_question_id"])
            column_id = str(definition["column_question_id"])
            if body:
                body.append(r"\clearpage")
            fragment = "\n".join([rf"\subsection{{{_tex(presentation['heading'])}}}",
                         rf"\noindent\textbf{{Y-axis question:}} {_tex(labels[row_id])}\par",
                         rf"\noindent\textbf{{X-axis question:}} {_tex(labels[column_id])}\par", fragment])
        elif supplied_labels:
            label_values = list(supplied_labels.values()) if isinstance(supplied_labels, Mapping) else list(supplied_labels)
            body.append(rf"\subsection{{{_tex(' x '.join(map(str, label_values)))}}}")
        fragments[key] = fragment
        body.append(fragment)
    return body, fragments, diagnostics


def _profile_questions(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Adapt eligible single-scope size bands to the existing ordinal chart renderer.

    Args:
        profile: MuCP cohort profile with unique-bank state and size-band counts.

    Returns:
        Nonempty ordinal size-band mappings. Missing-evidence states are summarized
        as counts in the combined report rather than rendered as charts.
    """
    questions = []
    for unit, summary in profile["sizes"].items():
        counts = summary["size_bands"]
        base = sum(counts.values())
        if not base:
            continue
        ordered = ("0", "1-99", "100-999", "1,000-9,999", "10,000-99,999", "100,000+")
        questions.append({"question_id": f"MuCP.size.{unit}.bands",
            "analytical_unit": profile.get("analytical_unit", "unique_overlapping_biobank"),
            "label": f"[MuCP] {unit.capitalize()}: eligible single-scope reported size bands",
            "question_type": "ordinal", "type": "derived scoped size bands",
            "population": {"N": base, "A": base, "M": 0},
            "population_labels": ["biobanks with eligible scoped counts",
                "eligible single-scope counts", "not applicable"],
            "categories": [{"value": key, "count": counts[key],
                "percent": counts[key] * 100 / base, "percent_base": base,
                "percent_basis": "eligible scoped counts"} for key in ordered],
            "contributions": [], "free_text_rows": []})
    return questions


def _clinical_enrichment(
    biobanks: Sequence[Mapping[str, Any]], include_contacts: bool,
    compact_source_context: bool = False,
    repeated_entries: str = "empty",
    include_dossier_links: bool = False,
) -> str:
    """Pair MuCP clinical evidence with SO2 interoperability without fusing claims.

    Args:
        biobanks: Unique cohort dossiers containing scoped evidence and observations.
        include_contacts: Whether contact-shaped text is retained rather than masked.
        compact_source_context: Whether established leading serialization prefixes
            are removed from displayed scope and source context.
        repeated_entries: Combined-only repeated biobank-cell presentation mode.
        include_dossier_links: Whether dossier destinations are present in this
            document and biobank names may link to them.

    Returns:
        Reader-facing table with source labels, qualifications and optional dossier links.
    """
    clinical = {"B.available_data.clinical_phenotype": "Clinical phenotype data",
                "C.available_data.clinical_laboratory": "Clinical/laboratory data",
                "C.available_data.medication_treatment": "Medication/treatment data",
                "C.available_data.longitudinal_outcomes": "Longitudinal outcomes",
                "C.available_data.real_world_data": "Real-world data", "C.available_data.proms": "PROMs"}
    standards = {"q_018_does_the_staff_dedicated_or_not_managing_the_repository_have_experience_",
                 "q_019_standards"}
    rows = []
    for bb in biobanks:
        from survey_descriptive import classify_reported_checkbox_observation
        classified = [(obs, classify_reported_checkbox_observation(obs))
                      for obs in bb.get("observations", []) if obs.get("survey") == "MuCP"
                      and obs.get("question_id") in clinical]
        classified = [(obs, state) for obs, state in classified
                      if state["eligible"] or state["affirmative"] is True]
        if not classified:
            continue
        labels = {item.get("question_id"): item.get("question_label", item.get("question_id"))
                  for item in bb.get("evidence", []) if item.get("survey") == "MuCP"}
        mucp_parts = []
        for obs, classification in classified:
            label = labels.get(obs["question_id"], clinical[obs["question_id"]])
            if compact_source_context:
                label = _compact_source_context(label)
            if classification["affirmative"]:
                status = ("reported for at least one collection; varies by collection, not universal coverage"
                          if classification["varies_by_collection"] else "reported in at least one scope")
            else:
                status = "No in all reported applicable scopes"
            mucp_parts.append(f"[MuCP] {label}: {status}")
        mucp = "; ".join(mucp_parts)
        items = [item for item in bb.get("evidence", []) if item.get("survey") == "SO2"
                 and item.get("question_id") in standards]
        answers = []
        for item in items:
            label = "Additional standards" if item["question_id"] == "q_019_standards" else "Terminology/modelling experience"
            value = item.get("raw_answer", item.get("normalized_value"))
            display = "Not reported" if value is None or value == "" else _display_value(value, include_contacts)
            scope = str(item.get("scope_label", "Submission"))
            if scope.startswith("Submission;"):
                scope = "Submission"
            if compact_source_context:
                label, display, scope = map(_compact_source_context, (label, display, scope))
            if compact_source_context and scope.casefold() in {"submission", "biobank-wide", "biobank wide"}:
                scope = ""
            answers.append(f"[SO2] {label}: {display}" + (f" ({scope})" if scope else ""))
        so2 = "; ".join(answers)
        if not so2:
            so2 = "Not reported; unknown, not evidence of no interoperability experience"
        link = "dossier-" + sha256(_biobank_identifier(bb).encode()).hexdigest()[:16]
        bank_label = _tex(_display_value(bb.get("name", ""), include_contacts))
        if include_dossier_links:
            bank_label = rf"\hyperref[{link}]{{{bank_label}}}"
        # Chunk each column together so unusually long source wording can paginate.
        left, right = _text_rows("", mucp), _text_rows("", so2)
        for index in range(max(len(left), len(right))):
            rows.append({
                "biobank_id": _biobank_identifier(bb),
                "country": str(bb.get("country") or "Unknown"),
                "biobank_sort_label": str(bb.get("name") or ""),
                "biobank_label": bank_label,
                "cells": [left[index][1] if index < len(left) else "",
                          right[index][1] if index < len(right) else ""],
            })
    return "\n".join([r"\subsection{Clinical data and SO2 interoperability}",
        r"Reported data and SO2 staff experience are complementary, not proof of implemented interoperability or coverage of the same collection. Conflicting and qualified source reports remain in the dossiers.",
        _combined_biobank_table(rows, r"p{0.18\linewidth}p{0.31\linewidth}p{0.45\linewidth}",
            ["Biobank", "[MuCP] Clinical/phenotypic evidence", "[SO2] Interoperability experience/standards"],
            {"table_biobank_repeated_entries": repeated_entries})
        if rows else r"\emph{No affirmative clinical/phenotypic reports in this cohort.}"])


def render_matching_breakdown(
    breakdown: Mapping[str, Any], options: Mapping[str, Any],
) -> str:
    """Render stored matching outcomes as survey, status, country and institution lists.

    Args:
        breakdown: Versioned inventory returned by ``build_matching_breakdown``.
        options: Combined report options; ``include_contact_details`` controls contact
            masking, and ``matching_summary_only`` omits the institution roster for
            the early overview while the complete roster remains in the appendix.

    Returns:
        TeX fragment with separate SO2/MuCP inventories and an accepted-ID cohort note.
    """
    labels = {"accepted": "Accepted", "unmatched": "Unmatched",
              "review": "Manual review", "excluded": "Excluded"}
    include_contacts = bool(options.get("include_contact_details", False))
    lines = [r"\subsection*{Survey matching inventory}",
             "Source-record counts describe response rows, not independent questionnaires "
             "or total respondent biobanks. Matching status is independent of report inclusion: "
             "all-MuCP retains unresolved and identity-excluded MuCP sources."]
    overlap = breakdown.get("accepted_overlap", {})
    lines.append(
        rf"\par Accepted Directory-ID intersection: "
        rf"{int(overlap.get('count', 0))} biobanks. This is the verified shared subset, "
        "not the complete MuCP reporting cohort; unresolved identities may hide additional overlap."
    )
    lines.append(r"\begin{itemize}")
    for survey in ("SO2", "MuCP"):
        info = breakdown.get("surveys", {}).get(survey, {})
        counts = info.get("status_counts", {})
        lines.append(rf"\item[{survey}] {int(info.get('total_records', 0))} source records; "
                     rf"{int(counts.get('accepted', 0))} accepted, "
                     rf"{int(info.get('distinct_accepted_directory_ids', 0))} distinct accepted Directory IDs, "
                     rf"{int(info.get('accepted_exclusive_directory_id_count', 0))} accepted only in this survey, "
                     rf"{int(counts.get('unmatched', 0))} unmatched, "
                     rf"{int(counts.get('review', 0))} manual review, "
                     rf"{int(counts.get('excluded', 0))} excluded.")
        if options.get("matching_summary_only", False):
            continue
        lines.append(r"\begin{itemize}")
        for status in ("accepted", "unmatched", "review", "excluded"):
            groups = info.get("country_groups", {}).get(status, ())
            count = int(counts.get(status, 0))
            noun = "source record" if count == 1 else "source records"
            lines.append(rf"\item {labels[status]} ({count} {noun})")
            if groups:
                lines.append(r"\begin{itemize}")
                for group in groups:
                    institutions = []
                    for institution in group.get("institutions", ()):
                        name = _tex(institution.get("name", "(institution not reported)"), include_contacts)
                        count = int(institution.get('record_count', 0))
                        details = [f"{count} source records"] if count > 1 else []
                        distinct = institution.get("distinct_directory_ids")
                        if distinct is not None and int(distinct) > 1:
                            details.append(f"{int(distinct)} distinct Directory IDs")
                        reasons = institution.get("exclusion_reasons", ())
                        if reasons:
                            details.append("reason: " + ", ".join(
                                _tex(reason, include_contacts) for reason in reasons
                            ))
                        if status == "excluded":
                            ids = institution.get("source_record_ids", ())
                            if ids:
                                details.append("records: " + ", ".join(
                                    _tex(record_id, include_contacts) for record_id in ids
                                ))
                        institutions.append(name + (" (" + "; ".join(details) + ")" if details else ""))
                    lines.append(rf"\item {_tex(group.get('country', 'Unknown'))}: "
                                 + "; ".join(institutions))
                lines.append(r"\end{itemize}")
            else:
                lines.append(r"\emph{None.}")
        country_summaries = info.get("country_summary_records", ())
        lines.append(r"\item Country-summary records (non-biobank evidence): "
                     + ("; ".join(
                         f"{_tex(item.get('country', 'Unknown'))} ({_tex(item.get('status', 'excluded'))}; "
                         f"{_tex(item.get('reason', ''))}; record {_tex(item.get('record_id', ''))})"
                         for item in country_summaries
                     ) if country_summaries else "None."))
        lines.append(r"\end{itemize}")
    lines.append(r"\end{itemize}")
    return "\n".join(lines)


def render_combined_tex(
    payload: Mapping[str, Any], options: Mapping[str, Any], upset_assets: Any = None,
) -> descriptive.RenderedDescriptiveReport:
    """Render the coherent combined report and reusable chart documents.

    Args:
        payload: Combined JSON mapping with biobanks and descriptive statistics.
        options: Rendering options passed to the generic section composer.
        upset_assets: Optional ``ValidatedUpSetAssets`` from the existing asset
            validator, with ``state`` and figure objects; absent/incomplete assets
            are explicitly reported rather than guessed.

    Returns:
        Complete report TeX, chart fragments/documents/paths and diagnostics.
    """
    payload = _report_country_copy(payload)
    stats = payload.get("descriptive_statistics", {})
    stats = stats if isinstance(stats, Mapping) else {}
    biobanks = sorted(payload.get("biobanks", []), key=lambda item: (
        str(item.get("country", "")).casefold(), _biobank_identifier(item),
    ))
    options = dict(options)
    presentation_path = Path(options.get(
        "report_presentation_path",
        Path(__file__).parent / "survey-mappings/so2_mucp_report_presentation.json",
    ))
    presentation = load_report_presentation(presentation_path)
    options["source_manifest"] = payload.get("source_manifest", options.get("source_manifest", []))
    options["compact_source_context"] = True
    options["include_section_heading"] = False
    options["include_scope_state_tables"] = False
    options["defer_evidence_tables"] = True
    evidence_sections: list[str] = []
    body_lines: list[str] = [
        r"\clearpage", r"\section{Cohort overview}",
        rf"\noindent Reporting units selected for this report: {len(biobanks)}\par",
    ]
    countries: dict[str, int] = {}
    for biobank in biobanks:
        country = str(biobank.get("country", "Unknown"))
        countries[country] = countries.get(country, 0) + 1
    if countries:
        body_lines.append(r"\subsection*{Cohort by country}")
        body_lines.extend(rf"\noindent {_tex(country)}: {count}\par" for country, count in sorted(countries.items()))
    else:
        body_lines.append(r"\emph{No biobanks in the selected cohort.}")
    for survey in ("MuCP", "SO2"):
        participation = stats.get(survey, {}).get("participation", {})
        if participation:
            body_lines.append(_tex(f"{survey}: {participation['participating_N']} selected reporting units supplied responses; "
                                   f"{participation['no_response_N']} supplied no {survey} response.") + r"\par")
    breakdown = payload.get("matching_breakdown")
    if not isinstance(breakdown, Mapping):
        from survey_combined import build_matching_breakdown
        breakdown = build_matching_breakdown(payload)
    body_lines.append(render_matching_breakdown(breakdown, {**options, "matching_summary_only": True}))
    body_lines.append(r"\par\hyperref[matching-source-review]{Matching inventory and source review}.\par")
    matching = payload.get("matching_summary", {})
    coverage = payload.get("metadata", {}).get("mucp_source_coverage", {})
    if coverage:
        body_lines.append(_tex(f"MuCP source coverage: {coverage['included_records']} of {coverage['input_records']} responses included.") + r"\par")
        body_lines.append(_tex(coverage["interpretation"]) + r"\par")
        unresolved = sum(b.get("reporting_unit_kind") == "unresolved_source_reporting_unit" for b in biobanks)
        national = sum(b.get("reporting_unit_kind") == "national_summary" for b in biobanks)
        body_lines.append(_tex(f"Reporting units include {unresolved} unresolved source groups and {national} national summaries. These are not verified distinct biobanks; charts count reporting units, while SO2 comparisons require genuine shared identities.") + r"\par")
    if isinstance(matching, Mapping):
        for key, value in sorted(matching.items()):
            body_lines.append(rf"\noindent {_tex(key.replace('_', ' '))}: {_tex(value)}\par")

    diagnostics: list[str] = []
    for biobank in biobanks:
        if any(row["filename"] == "Filename not supplied" for row in dossier_source_rows(
            biobank, options["source_manifest"],
        )):
            diagnostics.append(
                f"{_biobank_identifier(biobank)}: one or more MuCP source filenames were not supplied."
            )
    dossier_fragments = [r"\clearpage" + "\n" + render_biobank_dossier(
        item, {**options, "dossier_heading_level": "subsection"}) for item in biobanks] if options.get("include_dossiers", False) else []

    chart_fragments: dict[str, str] = {}
    chart_documents: dict[str, str] = {}
    chart_paths: dict[str, str] = {}
    def append_statistics(title: str, survey: str, questions: Sequence[Mapping[str, Any]],
                          evidence_only: bool = False) -> None:
        """Append one body rendered by the generic statistics section composer.

        Args:
            title: Reader-facing major or part heading.
            survey: Source survey label used on every answer table/chart.
            questions: Renderer-compatible statistics question mappings.
            evidence_only: Whether contextual submission fields belong entirely in
                Detailed evidence rather than creating another main survey section.

        Returns:
            None after appending the body, charts and any omissions.
        """
        if not evidence_only:
            body_lines.extend([r"\clearpage", rf"\section{{{_tex(title)}}}"])
        if not options.get("include_contact_details", False):
            hidden = [question for question in questions if _contact_field(question)]
            questions = [question for question in questions if not _contact_field(question)]
            if hidden:
                (evidence_sections if evidence_only else body_lines).append(
                    r"\noindent Dedicated contact fields are retained in JSON but omitted from this report.\par")
        rendered_body = descriptive.render_statistics_sections(
            [{"survey": survey, "label": title, "questions": questions}], {
                **options,
                "pie_variants": "all_only" if title.startswith("MuCP Part") else "default",
                "table_biobank_repeated_entries": options.get("table_biobank_repeated_entries", "empty"),
            },
        )
        if evidence_only:
            evidence_sections.extend([rf"\subsection{{{_tex(title)}}}", rendered_body.tex])
        else:
            body_lines.append(rendered_body.tex)
        chart_fragments.update(rendered_body.chart_fragments)
        chart_documents.update(rendered_body.chart_documents)
        chart_paths.update(rendered_body.chart_paths)
        diagnostics.extend(rendered_body.diagnostics)
        evidence_sections.extend(rendered_body.evidence_fragments.values())

    so2_questions = stats.get("SO2", {}).get("questions", [])
    from survey_descriptive import build_mucp_cohort_profile
    profile = stats.get("MuCP", {}).get("cohort_profile") or build_mucp_cohort_profile(biobanks)
    append_statistics("MuCP cohort profile", "MuCP", _profile_questions(profile))
    profile_interpretation = str(profile["interpretation"])
    profile_interpretation = profile_interpretation.replace(
        "Numeric mentions and scopes are never summed.",
        "Numeric-mention inventories and size-band categories are not additive. "
        "Separately, exact totals add only counts checked against their sources and for repeated reports: "
        "reported collections or whole-biobank counts by country or linked material/data type; "
        "these totals may overlap across collections and types and are not unique-person estimates.",
    )
    body_lines.append(r"\par\vspace{0.5em}" + _tex(profile_interpretation) + r"\par")
    size_rows = [["Counts of", "Reporting units with counts for identifiable collections or the whole biobank", "Reporting units mentioning counts", "Reporting units with no reported counts"]]
    for unit, summary in profile["sizes"].items():
        unit_label = {"donors": "donor counts", "samples": "sample counts",
                      "aliquots": "aliquot counts", "unit_unclear": "unit-unclear quantities"}.get(unit, unit)
        size_rows.append([_tex(unit_label), str(summary["biobanks_with_scoped_reported_sizes"]),
            str(summary["biobanks_with_quantity_evidence"]), str(summary["states"]["missing"])])
    body_lines.append(descriptive._table(size_rows, r"p{0.13\linewidth}p{0.26\linewidth}p{0.29\linewidth}p{0.23\linewidth}"))
    body_lines.append(r"\par\hyperref[evidence-scoped-sizes]{Reported quantities and collection context}.\par")
    scoped_rows = []
    from survey_descriptive import text_chunks
    rendered_answers: set[tuple[str, str, str, str]] = set()
    rendered_quantities: set[tuple[str, ...]] = set()

    for unit, summary in profile["sizes"].items():
        for row in summary["rows"]:
            scope = _compact_source_context(row.get("scope_label") or "")
            scope = re.sub(r"^Collection Name and BBMRI-ERIC Id:\s*", "", scope, flags=re.I)
            if row.get("kind") == "numeric_mention_not_additive":
                scope = "Collection not identified"
            elif (not scope or scope.casefold().startswith(
                    ("submission", "biobank-wide", "biobank wide", "collection_or_submission_as_reported"))):
                scope = "Collection not identified"
            if row.get("kind") == "numeric_mention_not_additive":
                amount = f"{row['value']:g} unit unclear"
                amount += r"; number mentioned in the answer, not a verified collection total"
            else:
                base_quantity = {key: value for key, value in row.items()
                                 if key not in {"raw_text", "qualifier_text"}}
                if row.get("unit") == "unit_unclear":
                    amount = f"{row['value']:g} unit unclear"
                else:
                    amount = format_reported_quantity(base_quantity)
            source = str(row.get("survey") or "MuCP")
            answer_type = row.get("answer_type")
            answer_label = ("Reported answer (free text)" if answer_type == "free_text"
                            else "Reported answer (structured)" if answer_type == "structured"
                            else "Reported answer")
            quantity_parts = [f"[{source}] [{_tex(scope)}] {amount}"]
            qualifier = row.get("qualifier_text")
            if qualifier is not None and str(qualifier).strip():
                safe_qualifier = _display_value(qualifier, bool(options.get("include_contact_details")))
                quantity_parts.extend(
                    _tex(f"[{source}] Qualification" + (" (continued)" if index else "") + ": ")
                    + descriptive._tex_with_links(chunk)
                    for index, chunk in enumerate(text_chunks(safe_qualifier))
                )
            raw_text = row.get("raw_text")
            answer_key = (str(row.get("biobank_id", "")), str(row.get("source_record_id", "")),
                          str(row.get("scope_id", "")), str(raw_text or ""))
            # Source narratives already contain their counts. Do not display each
            # extracted mention again as an extra, apparently independent amount.
            source_has_amount = any(
                int(re.sub(r"[\s,.]", "", token)) == row.get("value")
                for token in re.findall(r"\d+(?:(?:[\s,.])\d{3})*", str(raw_text or ""))
            )
            use_source_answer = bool(raw_text is not None and str(raw_text).strip()
                                     and source_has_amount
                                     and (row.get("kind") == "numeric_mention_not_additive"
                                          or _quantity_wording_adds_information(row, raw_text)))
            if use_source_answer:
                if answer_key in rendered_answers:
                    continue
                rendered_answers.add(answer_key)
                safe_raw_text = _display_value(raw_text, bool(options.get("include_contact_details")))
                unit_context = ("; unit unclear" if unit == "unit_unclear"
                                else f"; counts of {unit}")
                quantity_parts = [
                    _tex(f"[{source}] [{scope}] {answer_label}" + (" (continued)" if index else "") + ": ")
                    + descriptive._tex_with_links(chunk)
                    for index, chunk in enumerate(text_chunks(safe_raw_text + unit_context))
                ]
                if qualifier is not None and str(qualifier).strip() and str(qualifier).strip() not in str(raw_text):
                    quantity_parts.append(_tex(f"[{source}] Qualification: ")
                                          + descriptive._tex_with_links(str(qualifier)))
            if (raw_text is not None and str(raw_text).strip()
                    and _quantity_wording_adds_information(row, raw_text)
                    and answer_key not in rendered_answers):
                rendered_answers.add(answer_key)
                safe_raw_text = _display_value(raw_text, bool(options.get("include_contact_details")))
                quantity_parts.extend(
                    _tex(f"[{source}] {answer_label}" + (" (continued)" if index else "") + ": ")
                    + descriptive._tex_with_links(chunk)
                    for index, chunk in enumerate(text_chunks(safe_raw_text))
                )
            display_key = (str(row.get("biobank_id", "")), str(row.get("source_record_id", "")),
                           str(row.get("scope_id", "")), str(scope),
                           re.sub(r"\W+", " ", " ".join(quantity_parts)).strip().casefold())
            if display_key in rendered_quantities:
                continue
            rendered_quantities.add(display_key)
            for index, quantity in enumerate(quantity_parts):
                bank_id = str(row.get("biobank_id") or "")
                if not bank_id:
                    raise ValueError("Scoped quantity row is missing canonical biobank_id")
                scoped_rows.append({
                    "biobank_id": bank_id,
                    "country": str(row.get("country") or "Unknown"),
                    "biobank_sort_label": str(row.get("institution") or ""),
                    "biobank_label": _tex(_display_value(
                        row.get("institution", ""), bool(options.get("include_contact_details")))),
                    "cells": [quantity],
                })
    evidence_sections.append(r"\subsection{Reported quantities and collection context}\label{evidence-scoped-sizes}")
    evidence_sections.append(_combined_biobank_table(scoped_rows,
        r"p{0.20\linewidth}p{0.74\linewidth}", ["Biobank", "Reported quantity and context"],
        {**options, "country_headings": True}) if scoped_rows
        else r"\emph{No source-classified sample or individual quantities available.}")
    quantity_summary = stats.get("MuCP", {}).get("modality_quantities")
    quantity_aggregates = stats.get("MuCP", {}).get("quantity_aggregates")
    if isinstance(quantity_aggregates, Mapping):
        body_lines.extend([r"\clearpage", r"\subsection{Counts by material type and data type}",
            r"\noindent Collection counts describe donors or samples in collections reporting each type, "
            r"not necessarily the amount of that material or data. Counts reported without an identified "
            r"collection and counts specifically for a type are labelled separately. "
            r"The same people can occur in several collections or types; do not add different type totals.\par"])
        body_lines.append(render_modality_quantity_totals(quantity_aggregates, {
            "modality_definitions": presentation["modality_quantities"],
        }))
        contribution_table = render_quantity_contributions(quantity_aggregates, biobanks, options)
        if contribution_table:
            body_lines.append(r"\par\hyperref[evidence-quantity-selection]{Quantity inclusion and exclusion evidence}.\par")
            evidence_sections.extend([r"\subsection{Quantity inclusion and exclusion evidence}\label{evidence-quantity-selection}", contribution_table])
    if isinstance(quantity_summary, Mapping):
        body_lines.extend([r"\clearpage", r"\subsection{Reported counts by country and type}",
                           r"\noindent Countries use Directory metadata where resolved, otherwise the survey's country; "
                           r"they do not describe participants' residence. "
                           r"Confirmed counts are colored; unconfirmed/uncertain reported counts are gray. "
                           r"The total label is the sum of displayed values, not a verified population total.\par"])
        if isinstance(quantity_aggregates, Mapping):
            from survey_combined_quantity_views import build_reported_quantity_chart_views
            views = stats.get("MuCP", {}).get("quantity_chart_views") or build_reported_quantity_chart_views(
                quantity_aggregates, biobanks, presentation["modality_quantities"], profile)
            body_lines.append(r"\par\hyperref[evidence-count-coverage]{Source-count coverage and missing counts}.\par")
            evidence_sections.extend([r"\subsection{Source-count coverage}\label{evidence-count-coverage}",
                                      render_quantity_source_coverage(views, options)])
            aggregate_charts = render_quantity_chart_views(views, {**options, "biobanks": biobanks})
            for key, fragment in aggregate_charts.items():
                body_lines.extend([r"\clearpage", fragment])
                chart_fragments[key] = fragment
                chart_documents[key] = "\n".join([
                    descriptive._preamble(), r"\begin{document}", fragment, r"\end{document}",
                ])
    body_lines.append(r"\par\hyperref[evidence-clinical-interoperability]{Clinical data and SO2 interoperability evidence}.\par")
    evidence_sections.extend([r"\phantomsection\label{evidence-clinical-interoperability}", _clinical_enrichment(
        biobanks, bool(options.get("include_contact_details")), compact_source_context=True,
        repeated_entries=options.get("table_biobank_repeated_entries", "empty"),
        include_dossier_links=bool(options.get("include_dossiers", False)))])
    mucp = stats.get("MuCP", {})
    mucp_questions = mucp.get("questions", []) if isinstance(mucp, Mapping) else []
    question_labels: dict[str, str] = {}
    for question in mucp_questions:
        question_labels[str(question.get("question_id", ""))] = str(question.get("label", ""))
    question_labels.update({
        str(question.get("question_id", "")): str(question.get("label", ""))
        for question in so2_questions
    })
    part_groups: dict[str, list[Mapping[str, Any]]] = {}
    for question in mucp_questions:
        part = str(question.get("part", "MuCP"))
        part_groups.setdefault(part, []).append(question)
    if not part_groups:
        part_groups["MuCP"] = []
    for part, questions in sorted(part_groups.items(), key=lambda item: (
            {"B": 0, "C": 1, "MuCP": 2}.get(item[0].removeprefix("Part "), 3), item[0])):
        title = {
            "B": "MuCP Part B: mandatory criteria",
            "C": "MuCP Part C: additional criteria",
            "MuCP": "MuCP",
        }.get(part.removeprefix("Part "), f"MuCP {part}")
        append_statistics(title, "MuCP", questions, evidence_only=part.removeprefix("Part ") not in {"B", "C", "MuCP"})
    group_questions = mucp.get("groups", []) if isinstance(mucp, Mapping) else []
    if group_questions:
        titled_groups = []
        for question in group_questions:
            copied = dict(question)
            copied["hide_question_identifier"] = True
            question_id = str(question.get("question_id", ""))
            curated_title = presentation["group_titles"].get(question_id)
            if curated_title:
                copied["label"] = curated_title
            else:
                copied["label"] = "[MuCP] Group title requires curation"
                diagnostics.append(f"No curated title for MuCP group {question_id!r}; generic heading used.")
            titled_groups.append(copied)
        append_statistics("MuCP group frequencies", "MuCP", titled_groups)

    cross_body, cross_fragments, cross_diagnostics = _render_heatmaps(
        stats.get("cross_survey", {}), question_labels,
    )
    body_lines.extend([r"\clearpage", r"\section{Cross-survey enrichment}"])
    if cross_body:
        body_lines.extend(cross_body)
    else:
        body_lines.append(r"\emph{No cross-survey enrichment panels were supplied.}")
    diagnostics.extend(cross_diagnostics)
    for key, fragment in cross_fragments.items():
        chart_documents[key] = "\n".join([descriptive._preamble(), r"\begin{document}",
                                         fragment, r"\end{document}"])

    upset_fragments: dict[str, str] = {}
    figures = getattr(upset_assets, "figures", None)
    asset_state = getattr(upset_assets, "state", None)
    if isinstance(upset_assets, Mapping):
        figures = upset_assets
        asset_state = "complete"
    if upset_assets is None:
        asset_state = "empty"
    if asset_state != "complete" or not isinstance(figures, Mapping) or not figures:
        diagnostics.append("UpSet figures omitted: no complete validated assets were supplied.")
        body_lines.append(r"\emph{UpSet figures omitted: no complete validated assets were supplied.}")
    else:
        body_lines.append(r"\subsection*{Shared UpSet figures}")
        for definition_id, figure in figures.items():
            if isinstance(figure, Sequence) and not isinstance(figure, (str, bytes)) and len(figure) == 2:
                upset_pdf, deviation_pdf = figure
            else:
                upset_pdf = getattr(figure, "upset_pdf", None)
                deviation_pdf = getattr(figure, "deviation_pdf", None)
            if not upset_pdf or not deviation_pdf:
                diagnostics.append(f"UpSet {definition_id} omitted: both figure paths are required.")
                body_lines.append(rf"\emph{{UpSet {_tex(definition_id)} omitted: incomplete asset pair.}}")
                continue
            key = f"upset-{_slug(str(definition_id)) or 'figure'}"
            matrix = next((item for item in payload.get("upset_matrices", [])
                           if item.get("id") == definition_id), {})
            figure_lines = [
                rf"\includegraphics[width=\linewidth,height=0.82\textheight,keepaspectratio]{{\detokenize{{{upset_pdf}}}}}",
            ]
            if options.get("include_upset_deviations", False):
                figure_lines.extend([
                    r"\clearpage",
                    r"\noindent\emph{Exploratory deviation from an independence model; not a significance test.}\par",
                    rf"\includegraphics[width=\linewidth,height=0.82\textheight,keepaspectratio]{{\detokenize{{{deviation_pdf}}}}}",
                ])
            upset_fragments[key] = "\n".join(figure_lines)
            body_lines.extend([r"\clearpage", rf"\subsubsection*{{{_tex(matrix.get('title', definition_id))}}}",
                _tex(matrix.get("interpretation", "Reported patterns describe represented scopes, not universal same-collection availability.")),
                rf"\par Cohort: {matrix.get('cohort_N', len(biobanks))}; included in matrix: {matrix.get('matrix_N', 'unavailable')}.\par",
                upset_fragments[key]])
            from survey_combined_intersections import build_intersection_catalogue
            anchor = "evidence-members-" + _slug(str(definition_id))
            body_lines.append(rf"\par\hyperref[{anchor}]{{Biobanks contributing to each intersection bar}}.\par")
            evidence_sections.extend([rf"\subsection{{{_tex(matrix.get('title', definition_id))}: intersection members}}\label{{{anchor}}}",
                render_intersection_membership_table(
                    matrix.get("intersections") or build_intersection_catalogue(matrix), options)])

    append_statistics("SO2", "SO2", so2_questions)
    body_lines.extend([r"\clearpage", r"\section{Detailed evidence}", *evidence_sections])
    body_lines.extend([r"\clearpage", r"\appendix"])
    body_lines.append(r"\section{Matching and source review}\label{matching-source-review}")
    body_lines.append(render_matching_breakdown(breakdown, options))
    for key in ("unmatched_so2", "unmatched_mucp", "manual_review_matches", "excluded_source_records"):
        values = payload.get(key, [])
        body_lines.append(rf"\subsection*{{{_tex(key.replace('_', ' ').title())}}}")
        if not values:
            body_lines.append(r"\emph{None.}")
        for value in values:
            if isinstance(value, Mapping):
                decision = value.get("resolution", value)
                fields = ("source_record_id", "status", "method", "explanation", "reason", "biobank_id", "candidate_ids")
                detail = "; ".join(f"{field}={decision[field]}" for field in fields if field in decision)
                body_lines.append(rf"\noindent {_tex(detail)}\par")
            else:
                body_lines.append(rf"\noindent {_tex(value)}\par")
    if options.get("include_dossiers", False):
        body_lines.extend([r"\clearpage", r"\section{Biobank evidence dossiers}", *dossier_fragments])

    tex = "\n".join([
        descriptive._preamble(), r"\begin{document}",
        r"\title{Combined SO2 and MuCP analysis}", r"\maketitle",
        r"\tableofcontents", r"\clearpage", r"\section*{Abbreviations}",
        r"N/A/M: selected reporting units responding to the question's survey / reporting units with an answer / missing answers. Resolved units represent biobanks; unresolved source records and national summaries are separately identified in the overview. Units with no response to that survey are reported separately.",
        r"Applicable unticked MuCP checkbox options are No. Genuinely unknown, not-asked, conditional and indeterminate responses remain missing; raw unmarked evidence is preserved. SO2 conflicts and scope variation are separate categories, so N need not equal A plus M.",
        r"oAB: percentage among reporting units with an answer; oIB: percentage among selected reporting units participating in the question's survey.",
        r"oSB: percentage among reporting units with a single unqualified reported size scope, not whole-bank totals.",
        r"CC: reporting country code; TR denotes Turkey and MNE denotes Montenegro.",
        r"Recognizable email addresses are masked unless contact details are explicitly included. Person names embedded in arbitrary narratives may not be identifiable automatically; review narrative text before publication.",
        *body_lines, r"\end{document}", "",
    ])
    fragments = {**chart_fragments, **cross_fragments, **upset_fragments}
    return descriptive.RenderedDescriptiveReport(
        tex=tex, chart_fragments=fragments, chart_documents=chart_documents,
        chart_paths=chart_paths, diagnostics=tuple(diagnostics),
    )


def render_modality_quantity_coverage(
    summary: Mapping[str, Any], options: Mapping[str, Any],
) -> dict[str, str]:
    """Render the legacy unique-bank coverage matrices for compatibility callers.

    Args:
        summary: Pure quantity summary with cohort_N and per-modality unit/class coverage.
        options: Public modality_definitions supplying reader-facing row labels.

    Returns:
        Three independent class-to-TeX matrices of banks with/without eligible
        measurements. Amounts and overlapping scope counts are never aggregated.
    """
    coverage = summary.get("coverage", {})
    cohort = coverage.get("cohort_N")
    if type(cohort) is not int or cohort < 0:
        raise ValueError("Quantity coverage requires a nonnegative integer cohort_N")
    labels = {item["id"]: item["label"] for item in options.get("modality_definitions", [])}
    units = ("samples", "donors", "individuals", "participants")
    titles = {"modality_specific": "Direct modality quantity coverage",
              "collection_size_context": "Collection size context coverage",
              "submission_size_context": "Submission size context coverage"}
    tables = {}
    for linkage, title in titles.items():
        rows = [["Modality", "Samples", "Donors", "Individuals", "Participants"]]
        for modality in coverage.get("by_modality", []):
            indexed = {(item["unit"], item["linkage"]): item for item in modality["by_unit"]}
            if len(indexed) != len(modality["by_unit"]):
                raise ValueError("Duplicate quantity coverage unit/class entry")
            row = [_tex(labels.get(modality["modality_id"], modality["modality_id"]))]
            for unit in units:
                item = indexed.get((unit, linkage))
                if item is None:
                    raise ValueError("Quantity coverage lacks a modality unit/class entry")
                present, missing = item["biobanks_with_source_points"], item["biobanks_without_eligible_points"]
                if type(present) is not int or type(missing) is not int or min(present, missing) < 0 or present + missing != cohort:
                    raise ValueError("Quantity coverage bank counts disagree with cohort_N")
                row.append(f"{present} / {missing}")
            rows.append(row)
        parts = [rf"\subsubsection*{{{_tex(title)}}}",
                 rf"\noindent Each cell is biobanks with / without eligible measurements; cohort N = {cohort}. "
                 r"Repeated points from one bank count once. Units and classes are separate; do not sum cells. "
                 r"Missing measurements are not zero amounts or negative modality answers.\par"]
        if cohort and len(rows) > 1:
            parts.extend([r"\small", descriptive._table(rows,
                r"p{0.24\linewidth}p{0.15\linewidth}p{0.15\linewidth}p{0.15\linewidth}p{0.15\linewidth}"), r"\normalsize"])
        else:
            parts.append(r"\emph{No overlapping biobanks with quantity coverage to report.}")
        tables[linkage] = "\n".join(parts)
    return tables


def render_modality_quantity_totals(
    aggregates: Mapping[str, Any], options: Mapping[str, Any],
) -> str:
    """Render basis-separated, unit-labelled modality quantity totals.

    Args:
        aggregates: Stored MuCP ``quantity_aggregates`` mapping with modality totals,
            excluded contributions and diagnostics.
        options: ``modality_definitions`` supplying every configured modality ID and
            reader-facing label.

    Returns:
        TeX table with one or more rows for every configured modality. Collection
        totals, submission-only fallbacks and direct measurements remain separate;
        absent eligible totals are displayed as ``Not reported``.

    Raises:
        TypeError: If the aggregates, options, definitions or totals have invalid shapes.
        ValueError: If identifiers, units, bases, counts or totals are malformed.
    """
    if not isinstance(aggregates, Mapping) or not isinstance(options, Mapping):
        raise TypeError("Quantity aggregates and rendering options must be mappings")
    definitions = options.get("modality_definitions")
    totals = aggregates.get("modality_totals", [])
    exclusions = aggregates.get("excluded_contributions", [])
    if not isinstance(definitions, Sequence) or isinstance(definitions, (str, bytes)):
        raise TypeError("Quantity totals require modality definitions")
    if not isinstance(totals, Sequence) or isinstance(totals, (str, bytes)):
        raise TypeError("Quantity modality_totals must be a sequence")
    if not isinstance(exclusions, Sequence) or isinstance(exclusions, (str, bytes)):
        raise TypeError("Quantity excluded_contributions must be a sequence")

    labels: dict[str, str] = {}
    for definition in definitions:
        if not isinstance(definition, Mapping):
            raise TypeError("Modality definitions must be mappings")
        modality_id, label = definition.get("id"), definition.get("label")
        if not isinstance(modality_id, str) or not modality_id or not isinstance(label, str) or not label.strip():
            raise ValueError("Every modality definition needs a nonempty ID and label")
        if modality_id in labels:
            raise ValueError(f"Duplicate modality definition: {modality_id}")
        labels[modality_id] = label

    indexed: dict[str, list[Mapping[str, Any]]] = {key: [] for key in labels}
    for total in totals:
        if not isinstance(total, Mapping):
            raise TypeError("Modality totals must be mappings")
        modality_id = total.get("modality_id")
        if modality_id not in indexed:
            raise ValueError(f"Aggregate references undefined modality: {modality_id!r}")
        unit, basis = total.get("unit"), total.get("basis")
        if unit not in {"donors", "samples", "aliquots", "unit_unclear"}:
            raise ValueError(f"Unsupported aggregate quantity unit: {unit!r}")
        if basis not in {"collection", "submission_fallback", "direct_modality"}:
            raise ValueError(f"Unsupported aggregate quantity basis: {basis!r}")
        value = total.get("reported_total")
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                  or not math.isfinite(value) or value < 0):
            raise ValueError("Reported modality totals must be null or finite nonnegative numbers")
        for key in ("contributing_biobanks", "contributing_scopes", "excluded_count"):
            if type(total.get(key)) is not int or total[key] < 0:
                raise ValueError(f"Modality total {key} must be a nonnegative integer")
        indexed[modality_id].append(total)

    excluded_by_modality: dict[str, list[Mapping[str, Any]]] = {key: [] for key in labels}
    for excluded in exclusions:
        if not isinstance(excluded, Mapping):
            raise TypeError("Excluded quantity contributions must be mappings")
        modality_ids = excluded.get("modality_ids", [])
        if not isinstance(modality_ids, Sequence) or isinstance(modality_ids, (str, bytes)):
            raise TypeError("Excluded contribution modality_ids must be a sequence")
        for modality_id in modality_ids:
            if modality_id not in excluded_by_modality:
                raise ValueError(f"Exclusion references undefined modality: {modality_id!r}")
            if excluded.get("view", "modality") == "modality":
                excluded_by_modality[modality_id].append(excluded)

    basis_labels = {
        "collection": "{unit} in collections reporting this type",
        "submission_fallback": "Count reported; collection not identified ({unit})",
        "direct_modality": "Count reported specifically for this type ({unit})",
    }
    rows = [["Material or data type", "What the count describes", "Reported total",
             "Biobanks / reported groups", "Counts not included"]]
    from survey_combined_quantity_views import quantity_display_labels
    previous_kind = None
    for modality_id, label in labels.items():
        definition = next(item for item in definitions if item["id"] == modality_id)
        kind = quantity_display_labels(definition)["kind"]
        if kind != previous_kind:
            rows.append([r"\textbf{" + _tex(kind + "s") + "}", "", "", "", ""])
            previous_kind = kind
        modality_totals = indexed[modality_id]
        if not modality_totals:
            excluded = excluded_by_modality[modality_id]
            reason_counts: dict[str, int] = {}
            for item in excluded:
                reason = _quantity_exclusion_label(item.get("reason", "uncertainty"))
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            exclusion_text = ("; ".join(f"{reason}: {count}" for reason, count in sorted(reason_counts.items()))
                              if reason_counts else "0")
            rows.append([_tex(label), "No eligible source total", "Not reported", "0 / 0",
                         _tex(exclusion_text)])
            continue
        for total in sorted(modality_totals, key=lambda item: (item["basis"], item["unit"],
                                                                str(item.get("temporal_status", "")))):
            unit_label = "unit unclear" if total["unit"] == "unit_unclear" else total["unit"]
            basis_label = basis_labels[total["basis"]].format(unit=unit_label)
            basis_label += "; time: " + str(total.get("temporal_status") or "unspecified").replace("_", " ")
            value = total["reported_total"]
            total_label = "Not reported" if value is None else (
                f"{value:g} {_tex(unit_label)}" if isinstance(value, float)
                else f"{value} {_tex(unit_label)}")
            excluded_items = [item for item in excluded_by_modality[modality_id]
                              if item.get("basis") == total["basis"]
                              and item.get("unit") == total["unit"]
                              and item.get("temporal_status", "unspecified") == total.get("temporal_status", "unspecified")]
            reason_counts: dict[str, int] = {}
            for item in excluded_items:
                reason = _quantity_exclusion_label(item.get("reason", "uncertainty"))
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            reasons = "; ".join(f"{reason}: {count}" for reason, count in sorted(reason_counts.items()))
            excluded_text = str(total["excluded_count"])
            if reasons:
                excluded_text += "; " + reasons
            rows.append([_tex(label), _tex(basis_label), total_label,
                f"{total['contributing_biobanks']} / {total['contributing_scopes']}",
                _tex(excluded_text)])
    if len(rows) == 1:
        return r"\emph{No modality quantity definitions are configured.}"
    return descriptive._table(rows,
        r"p{0.16\linewidth}p{0.35\linewidth}p{0.15\linewidth}p{0.13\linewidth}p{0.16\linewidth}")


def render_quantity_contributions(
    aggregates: Mapping[str, Any], biobanks: Sequence[Mapping[str, Any]],
    options: Mapping[str, Any],
) -> str:
    """Render source candidates with explicit per-view eligibility and exclusions.

    Args:
        aggregates: Stored MuCP quantities, selected totals and view-specific exclusions.
        biobanks: Combined cohort records supplying canonical bank labels.
        options: Combined rendering options, including repeat-cell presentation.

    Returns:
        Compact biobank-grouped table of contribution amount, unit, basis, scope and
        linked modality and selection status. Qualified/excluded evidence is retained;
        the table is empty only when no source candidate or exclusion is available.

    Raises:
        ValueError: If an aggregate contribution references an unknown biobank.
    """
    bank_index = {_biobank_identifier(bank): bank for bank in biobanks}
    rows = []
    candidates = list(aggregates.get("contributions", []))
    seen = {tuple(item.get("quantity_ids", [])) for item in candidates}
    for excluded in aggregates.get("excluded_contributions", []):
        key = tuple(excluded.get("quantity_ids", []))
        if key not in seen:
            seen.add(key)
            candidates.append(excluded)
    for contribution in candidates:
        bank_id = str(contribution.get("biobank_id", ""))
        bank = bank_index.get(bank_id)
        if bank is None:
            raise ValueError(f"Quantity contribution references unknown biobank {bank_id!r}")
        scope_members = list(contribution.get("scope_members", []))
        if not scope_members:
            scopes = bank.get("scopes", {})
            if isinstance(scopes, Mapping):
                scope = scopes.get(contribution.get("scope_id"))
            else:
                scope = next((item for item in scopes if item.get("scope_id") == contribution.get("scope_id")), None)
            if scope is not None:
                scope_members.append(scope)
        scope_names = [
            str(scope.get("label") or "").strip()
            for scope in scope_members
            if str(scope.get("label") or "").strip()
            and str(scope.get("label")).strip().casefold()
            not in {"submission", "biobank-wide", "biobank wide"}
        ]
        fallback_scope = ("Reported collection (name not supplied)"
                          if any(scope.get("kind") == "collection" for scope in scope_members)
                          else "Collection not identified" if scope_members and all(
                              scope.get("kind") == "submission" for scope in scope_members)
                          else "Collection not identified")
        scope_label = "; ".join(dict.fromkeys(scope_names)) or fallback_scope
        unit = "unit unclear" if contribution.get("unit") == "unit_unclear" else str(contribution.get("unit"))
        value = contribution.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Quantity contribution values must be numeric")
        amount = f"{value:g}" if isinstance(value, float) else str(value)
        basis = {"collection": "count for an identified collection", "submission_fallback": "collection not identified",
                 "direct_modality": "count specifically for this type"}.get(contribution.get("basis"), "what this count covers is unclear")
        modalities = ", ".join(str(item) for item in contribution.get("modality_ids", []))
        quantity_ids = set(contribution.get("quantity_ids", []))
        selection = []
        for view, key, dimension in (("Country total", "country_totals", "country"),
                                     ("Material/data type", "modality_totals", "modality_id")):
            selected_labels = []
            for total in aggregates.get(key, []):
                if (total.get("unit"), total.get("basis"), total.get("temporal_status", "unspecified")) != (
                        contribution.get("unit"), contribution.get("basis"), contribution.get("temporal_status", "unspecified")):
                    continue
                if any(quantity_ids.intersection(segment.get("quantity_ids", []))
                       for segment in total.get("segments", [])):
                    selected_labels.append(str(total.get(dimension)))
            if selected_labels:
                selection.append(f"Included in {view}: " + ", ".join(dict.fromkeys(selected_labels)))
        for excluded in aggregates.get("excluded_contributions", []):
            if quantity_ids.intersection(excluded.get("quantity_ids", [])):
                view = ("Country total" if excluded.get("view") == "country" else
                        "Material/data type " + ", ".join(excluded.get("modality_ids", [])))
                selection.append(view + ": excluded - " + _quantity_exclusion_label(excluded.get("reason", "uncertainty")))
        temporal = str(contribution.get("temporal_status") or "unspecified").replace("_", " ")
        relation = str(contribution.get("relation") or "reported_value").replace("_", " ")
        rows.append({
            "biobank_id": bank_id, "country": str(bank.get("country") or "Unknown"),
            "biobank_sort_label": str(bank.get("name") or bank_id),
            "biobank_label": _tex(_display_value(bank.get("name", bank_id),
                                                bool(options.get("include_contact_details")))),
            "cells": [
                _tex(str(bank.get("country") or "Unknown")),
                f"[MuCP] {amount} {_tex(unit)} ({_tex(relation)}; time: {_tex(temporal)}; {_tex(basis)}; {_tex(scope_label)})"
                + r"\par " + _tex("; ".join(dict.fromkeys(selection)) or "Not selected for an aggregate view"),
                _tex(modalities or "No material/data type identified"),
            ],
        })
    if not rows:
        return ""
    return "\n".join([
        r"\subsubsection*{Source quantities and aggregation status}",
        _combined_biobank_table(rows,
            r"p{0.18\linewidth}p{0.14\linewidth}p{0.46\linewidth}p{0.16\linewidth}",
            ["Biobank", "Country", "Reported contribution and aggregation status", "Material/data type"], options),
    ])


def _quantity_point_context(
    observations: Sequence[Mapping[str, Any]], biobanks: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    """Map quantity IDs to human bank, submission ordinal and scope descriptions.

    Args:
        observations: Distinct source quantity rows whose Q points must remain identifiable.
        biobanks: Validated cohort records supplying names, original response IDs and scopes.

    Returns:
        Quantity-ID to readable source context, using stable ordinals for missing labels
        without exposing technical provenance identifiers in ordinary measurement tables.
    """
    banks = {bank["biobank_id"]: bank for bank in biobanks}
    bank_ids = sorted({row["biobank_id"] for row in observations})
    result = {}
    for bank_ordinal, bid in enumerate(bank_ids, 1):
        bank = banks.get(bid, {})
        name = bank.get("name")
        if not isinstance(name, str) or not name.strip() or name == bid:
            name = f"Biobank {bank_ordinal}"
        records = {record["record_id"]: record for record in bank.get("mucp_source_records", [])}
        bank_rows = [row for row in observations if row["biobank_id"] == bid]
        record_ids = sorted(set(records) | {row["source_record_id"] for row in bank_rows})
        responses = {rid: str(records.get(rid, {}).get("metadata", {}).get("response_id") or rid)
                     for rid in record_ids}
        ordinals = {response: index for index, response in enumerate(sorted(set(responses.values())), 1)}
        scopes = bank.get("scopes", {})
        scope_ids = sorted(set(scopes) | {row["scope_id"] for row in bank_rows})
        for row in bank_rows:
            scope = scopes.get(row["scope_id"], {})
            label = _compact_source_context(scope.get("label") or row.get("scope_label") or "")
            label = re.sub(r"^Collection Name and BBMRI-ERIC Id:\s*", "", label, flags=re.I)
            for identifier in (row["scope_id"], row["source_record_id"], responses[row["source_record_id"]], scope.get("collection_id")):
                if identifier:
                    label = re.sub(r"(?<!\w)" + re.escape(str(identifier)) + r"(?!\w)", "", label)
            label = re.sub(r"bbmri-eric:ID:[\w:.%-]+", "", label)
            label = label.strip(" ;:\n\t")
            if not label or label in {"collection", "collection_or_submission_as_reported"}:
                label = ("Reported collection" if row["linkage"] == "collection_size_context" else "Reported scope")
                label += f" {scope_ids.index(row['scope_id']) + 1}"
            if label.casefold() in {"submission", "biobank-wide", "biobank wide"}:
                label = ""
            context = [name, f"Submission {ordinals[responses[row['source_record_id']]]}"]
            if label:
                context.append(label)
            result[row["quantity_id"]] = "; ".join(context)
    return result


def render_modality_quantity_charts(
    summary: Mapping[str, Any], options: Mapping[str, Any],
) -> dict[str, str]:
    """Render non-additive source quantity points in country-specific PGF panels.

    Args:
        summary: Pure modality quantity summary with provenance-backed observations.
        options: Public modality_definitions, cohort biobanks for readable point context,
            and extended_evidence controlling technical identifiers in the point table.

    Returns:
        Chart-key to self-contained TikZ fragment; no unsupported unit gets a chart.
    """
    definitions = options.get("modality_definitions", [])
    labels = {item["id"]: item["label"] for item in definitions}
    banks = {_biobank_identifier(item): item for item in options.get("biobanks", [])}
    repeated_entries = options.get("table_biobank_repeated_entries", "empty")
    observations = summary.get("observations", [])
    if not isinstance(observations, list):
        raise ValueError("Modality quantity observations must be a list")
    point_context = _quantity_point_context(observations, options.get("biobanks", []))
    units = ("samples", "donors", "individuals", "participants")
    classes = ("modality_specific", "collection_size_context", "submission_size_context")
    marks = {"reported_value": "*", "greater_than": "triangle*", "at_least": "triangle",
             "less_than": "square*", "at_most": "square", "approximate": "diamond*"}
    relation_labels = {"reported_value": "reported value", "greater_than": "greater than",
                       "at_least": "at least", "less_than": "less than",
                       "at_most": "at most", "approximate": "approximately"}
    charts: dict[str, str] = {}
    for linkage in classes:
        for unit in units:
            matching = [row for row in observations if row["linkage"] == linkage and row["unit"] == unit]
            if not matching:
                continue
            positives = [row["value"] for row in matching if row["value"] > 0]
            log_scale = len(positives) > 1 and max(positives) / min(positives) > 100
            minimum = min(positives) if positives else 1
            maximum = max((row["value"] for row in matching), default=1)
            countries = sorted({str(row["country"] or "unknown") for row in matching})
            for country in countries:
                rows = [row for row in matching if str(row["country"] or "unknown") == country]
                for page, start in enumerate(range(0, len(rows), 16), 1):
                    part = rows[start:start + 16]
                    key = f"mucp-quantity-{linkage}-{unit}-{_slug(country) or 'unknown'}-{page}"
                    ylabels = []
                    lines = []
                    zero_rows = []
                    evidence_rows = []
                    for ordinal, row in enumerate(part, 1):
                        linked = " / ".join(labels.get(link["modality_id"], link["modality_id"])
                                            for link in row["modality_links"])
                        point_label = f"Q{start + ordinal}"
                        ylabels.append("{" + point_label + "}")
                        safe_source = point_context[row["quantity_id"]]
                        bank = banks.get(row["biobank_id"])
                        bank_name = (
                            _tex(_display_value(bank.get("name", row["biobank_id"]),
                                                bool(options.get("include_contact_details"))))
                            if bank is not None else _tex(safe_source.split("; ", 1)[0])
                        )
                        source_context = safe_source.split("; ", 1)[1] if "; " in safe_source else safe_source
                        source_context = _tex(source_context, bool(options.get("include_contact_details")))
                        if options.get("extended_evidence", False):
                            source = "; ".join((row["biobank_id"], row["source_record_id"], row["scope_id"]))
                            source_context += r"\par " + _tex(source).replace(r"\_", r"\_\allowbreak{}").replace(":", r":\allowbreak{}")
                        temporal = str(row.get("temporal_status") or "unspecified").replace("_", " ")
                        evidence_rows.append({
                            "biobank_id": row["biobank_id"], "country": str(row.get("country") or "Unknown"),
                            "biobank_sort_label": str(bank.get("name") or row["biobank_id"]) if bank else safe_source.split("; ", 1)[0],
                            "biobank_label": bank_name,
                            "cells": [point_label, source_context,
                            _tex("[MuCP] " + linked) + r"\par " + _tex(relation_labels.get(row["relation"], row["relation"]))
                            + " " + str(row["value"]) + " " + _tex(unit)
                            + "; " + _tex("time not specified" if temporal == "unspecified" else "time: " + temporal)],
                        })
                        value = row["value"]
                        if log_scale and value == 0:
                            zero_rows.append(point_label)
                            continue
                        mark = marks.get(row["relation"])
                        if mark is None or type(value) is not int or value < 0:
                            raise ValueError("Unsupported modality quantity plot value or relation")
                        lines.append(rf"\addplot+[only marks,mark={mark},mark size=2.8pt] coordinates {{({value},{ordinal})}};")
                    axis = [r"\begin{tikzpicture}", r"\begin{axis}[",
                            r"width=0.94\linewidth,height=" + f"{max(5, min(14, 1.0 * len(part) + 3))}cm,",
                            "ytick={" + ",".join(str(i) for i in range(1, len(part) + 1)) + "},",
                            "yticklabels={" + ",".join(ylabels) + "},",
                            "ymin=0.5,ymax=" + str(len(part) + 0.5) + ",",
                            r"ylabel={Source quantity point},xlabel={Reported " + _tex(unit)
                            + (" (log scale)" if log_scale else "") + "},",
                            r"enlarge x limits=0.05,grid=major,scaled x ticks=false,",
                            (f"xmode=log,log ticks with fixed point,xmin={max(0.9, minimum * 0.9):g},xmax={maximum * 1.1:g},"
                             if log_scale else f"xmin=0,xmax={max(1, maximum * 1.1):g},"),
                            *(["xtick={0},"] if maximum == 0 else []),
                            r"tick label style={font=\sffamily\small,/pgf/number format/assume math mode=true},label style={font=\sffamily\small}", r"]",
                            *lines, r"\end{axis}", r"\end{tikzpicture}"]
                    heading = {"modality_specific": "Direct modality quantities",
                               "collection_size_context": "Collection size context",
                               "submission_size_context": "Submission size context"}[linkage]
                    heading += f" ({unit}), Directory country {country}, panel {page}"
                    axis.insert(0, rf"\subsubsection*{{{_tex(heading)}}}")
                    axis.insert(1, r"\noindent\small One point per source quantity; point IDs map to the evidence table. "
                                   r"Context counts are not modality coverage. Source time is not established unless stated. "
                                   r"Markers: circle = reported value, triangle = lower bound, square = upper bound, "
                                   r"diamond = approximate. For bound markers only, filled = strict and open = inclusive.\par\normalsize")
                    if zero_rows:
                        axis.append(r"\par\noindent Zero-valued quantities or bounds in " + _tex(unit) + " (not plotted on log axis): "
                                    + _tex("; ".join(zero_rows)) + r".\par")
                    axis.append(_combined_biobank_table(evidence_rows,
                        r"p{0.15\linewidth}p{0.07\linewidth}p{0.30\linewidth}p{0.39\linewidth}",
                        ["Biobank", "Point", "Source and scope", "Linked modality; measurement"],
                        {"table_biobank_repeated_entries": repeated_entries}))
                    charts[key] = "\n".join(axis)
    return charts


def _quantity_chart_color(index: int) -> str:
    """Return a deterministic distinguishable HTML color for one sorted bank ordinal.

    Args:
        index: Zero-based position in the global lexicographic biobank ID order.

    Returns:
        Six-digit RGB hex color, stable across chart scale, page and modality.
    """
    hue = (index * 0.618033988749895 + 0.58) % 1.0
    red, green, blue = colorsys.hls_to_rgb(hue, 0.48, 0.62)
    return f"{round(red * 255):02X}{round(green * 255):02X}{round(blue * 255):02X}"


def _quantity_plot_number(value: int | float) -> str:
    """Format finite chart coordinates as fixed-point numbers accepted by PGFPlots.

    Args:
        value: A nonnegative quantity or axis coordinate.

    Returns:
        Decimal text with no exponent notation or redundant fractional zeroes.
    """
    if isinstance(value, int):
        return str(value)
    return f"{value:.12f}".rstrip("0").rstrip(".")


def _quantity_chart_name(bank_id: str, banks: Mapping[str, Mapping[str, Any]],
                         options: Mapping[str, Any]) -> str:
    """Resolve the safe human legend label for one canonical Directory biobank.

    Args:
        bank_id: Canonical biobank identifier referenced by aggregate segments.
        banks: Validated bank-ID lookup derived from the supplied cohort.
        options: Rendering privacy options, including contact-detail inclusion.

    Returns:
        TeX-escaped display name (or ID) and, for gray segments, the pre-escaped
        source quantity/context explanation supplied by the reporting adapter.
    """
    bank = banks.get(bank_id, {})
    name = bank.get("name")
    if not isinstance(name, str) or not name.strip():
        name = bank_id
    label = _tex(_display_value(name, bool(options.get("include_contact_details"))))
    return label + (r"\par " + str(bank["quantity_legend"]) if bank.get("quantity_legend") else "")


def render_quantity_source_coverage(views: Mapping[str, Any], options: Mapping[str, Any]) -> str:
    """Keep every count-source response visible, including answers without usable counts.

    Args:
        views: Inclusive reporting views with a source record coverage inventory.
        options: Contact-visibility options applied consistently to institution names.

    Returns:
        A compact country/status roster. Unparsed numeric narratives refer readers
        to Detailed evidence rather than turning ages, dates or code fragments into counts.
        No missing response is represented by an invented zero-valued segment.
    """
    groups = defaultdict(lambda: defaultdict(int))
    labels = {"counts_displayed": "Counts displayed (colored/gray)",
              "numeric_answer_needs_interpretation": "Numeric answer needs interpretation (detailed evidence)",
              "count_not_reported": "Count not reported"}
    for row in views.get("source_coverage", []):
        name = _display_value(row["institution"], bool(options.get("include_contact_details")))
        groups[(row["country"], row["status"])][name] += 1
    rows = [["CC", "Count reporting", "Institutions"]]
    from survey_descriptive import text_chunks
    for (country, status), names in sorted(groups.items()):
        institutions = [name + (f" [{count} responses]" if count > 1 else "")
                        for name, count in sorted(names.items())]
        for index, chunk in enumerate(text_chunks("; ".join(institutions), limit=700)):
            rows.append([_tex(country) if index == 0 else "", _tex(labels[status]) if index == 0 else "",
                         _tex(chunk)])
    return (r"\noindent All source responses are retained. Unknown units have their own panels; "
            r"uninterpreted numeric text stays in Detailed evidence and is never assumed to be a count.\par"
            + descriptive._table(rows, r"p{0.06\linewidth}p{0.26\linewidth}p{0.59\linewidth}"))


def render_nonadditive_quantity_charts(
    summary: Mapping[str, Any], aggregates: Mapping[str, Any], options: Mapping[str, Any],
) -> dict[str, str]:
    """Show known-unit counts excluded from exact stacks as separate observations.

    Args:
        summary: Source-owned quantity observations, including original bound relations.
        aggregates: Audited exclusions identifying quantities that cannot be summed.
        options: Owning biobank records and the report's contact-visibility policy.

    Returns:
        Linear point-chart fragments with country/observation ticks and a source-labelled
        key. Identical B/C counts in one record/scope share a display mark; populations
        with different counts stay separate. No country totals are manufactured.
    """
    excluded = {qid for row in aggregates.get("excluded_contributions", [])
                for qid in row.get("quantity_ids", [])}
    banks = {bank["biobank_id"]: bank for bank in options.get("biobanks", [])}
    grouped: dict[str, dict[tuple[Any, ...], dict[str, Any]]] = {}
    for row in summary.get("observations", []):
        if row["quantity_id"] not in excluded or row["unit"] not in {"donors", "samples", "aliquots"}:
            continue
        key = tuple(row.get(field) for field in (
            "biobank_id", "source_record_id", "scope_id", "value", "relation", "temporal_status"))
        entry = grouped.setdefault(row["unit"], {}).setdefault(key, {**row, "parts": set()})
        question_id = str(row.get("question_id") or "")
        entry["parts"].add("Part " + question_id.split(".")[0]
                           if question_id.startswith(("B.", "C.")) else "Reported collection")
    charts = {}
    for unit, entries in sorted(grouped.items()):
        rows = sorted(entries.values(), key=lambda row: (
            row.get("country") or "Unknown", banks[row["biobank_id"]].get("name") or "",
            row["source_record_id"], row["scope_id"], row["value"]))
        largest_count = max(row["value"] for row in rows)
        maximum = largest_count * 1.18 or 1
        ticks_x = sorted({round(largest_count * fraction) for fraction in (0, 1 / 3, 2 / 3, 1)})
        if largest_count == 0:
            ticks_x = [0, 1]
        for start in range(0, len(rows), 12):
            page = rows[start:start + 12]
            ticks, marks = [], []
            table = [["Mark", "Biobank", "Source and reported count"]]
            for index, row in enumerate(page, 1):
                label = f"{row.get('country') or 'Unknown'} \\#{start + index}"
                ticks.append("{" + label + "}")
                amount = format_reported_quantity(row)
                marks.extend([
                    r"\addplot+[only marks,mark=*,color=blue] coordinates {(" + f"{row['value']:g},{index}" + ")};",
                    r"\node[anchor=west,font=\sffamily\scriptsize] at (rel axis cs:1.02,"
                    + f"{1 - (index - 0.5) / len(page):g}" + ") {" + amount + "};",
                ])
                bank = banks[row["biobank_id"]]
                table.append([label, _tex(_display_value(bank.get("name") or row["biobank_id"],
                                                       bool(options.get("include_contact_details")))),
                              "[MuCP] " + _tex(" / ".join(sorted(row["parts"]))) + ": " + amount
                              + "; " + _tex(str(row.get("temporal_status") or "unspecified") + " time")])
            charts[f"mucp-nonadditive-{unit}-{start // 12 + 1}"] = "\n".join([
                rf"\subsubsection*{{Non-additive reported counts ({_tex(unit)})}}",
                r"\noindent These observations cannot be added to country totals: they are approximate, "
                r"bounds, potentially overlapping populations or otherwise unsuitable for exact sums. "
                r"Dots mark the reported number, not an exact count when a bound or approximation is shown. "
                r"Different Part B/C counts remain separate; agreeing repeated counts share one mark.\par",
                r"\begin{tikzpicture}\begin{axis}[width=0.70\linewidth,clip=false,",
                f"height={2.5 + 0.38 * len(page):g}cm,xmin=0,xmax={maximum:g},",
                f"ymin=0.5,ymax={len(page) + 0.5:g},y dir=reverse,",
                "ytick={" + ",".join(str(i) for i in range(1, len(page) + 1)) + "},",
                "yticklabels={" + ",".join(ticks) + "},",
                r"xlabel={Reported number (see qualifications)},scaled x ticks=false,",
                "xtick={" + ",".join(str(tick) for tick in ticks_x) + "},",
                r"tick label style={font=\sffamily\scriptsize},label style={font=\sffamily\small},",
                r"xticklabel style={/pgf/number format/fixed,/pgf/number format/precision=0},grid=major]",
                *marks, r"\end{axis}\end{tikzpicture}\par",
                descriptive._table(table, r"p{0.10\linewidth}p{0.46\linewidth}p{0.35\linewidth}"),
            ])
    return charts


def render_country_quantity_charts(
    aggregates: Mapping[str, Any], options: Mapping[str, Any],
) -> dict[str, str]:
    """Render exact country-stacked quantity aggregates on linear count axes.

    Args:
        aggregates: Stored MuCP quantity aggregate mapping containing ``country_totals``,
            ``modality_totals`` and excluded-contribution evidence.
        options: Combined renderer options. ``biobanks`` maps canonical IDs to country
            and labels; ``modality_definitions`` maps modality IDs to public labels.
            ``include_uncertain_counts`` permits gray reporting-only contributions;
            ``show_confirmed_total_labels`` prints both subtotals, and
            ``quantity_rows_per_panel`` controls the number of rows per chart.
            ``allow_empty_confirmed_rows`` retains zero confirmed contributions
            without treating them as unattributed reported population counts.

    Returns:
        Chart key to TeX-safe PGF/TikZ fragment, with identical raw segment boundaries,
        stable bank colors, readable legends, and shared limits across compatible panels.

    Raises:
        TypeError: If aggregate rows, bank records or modality definitions are malformed.
        ValueError: If totals, segment values, units, bases or references are invalid.
    """
    if not isinstance(aggregates, Mapping) or not isinstance(options, Mapping):
        raise TypeError("Country quantity charts require aggregate and option mappings")
    banks_input = options.get("biobanks", [])
    if not isinstance(banks_input, Sequence) or isinstance(banks_input, (str, bytes)):
        raise TypeError("Country quantity chart biobanks must be a sequence")
    banks: dict[str, Mapping[str, Any]] = {}
    for bank in banks_input:
        if not isinstance(bank, Mapping):
            raise TypeError("Country quantity chart biobank entries must be mappings")
        bank_id = _biobank_identifier(bank)
        if not bank_id or bank_id in banks:
            raise ValueError("Country quantity chart biobank IDs must be nonempty and unique")
        banks[bank_id] = bank

    definitions = options.get("modality_definitions", [])
    if not isinstance(definitions, Sequence) or isinstance(definitions, (str, bytes)):
        raise TypeError("Country quantity chart modality definitions must be a sequence")
    modality_labels: dict[str, str] = {}
    for definition in definitions:
        if not isinstance(definition, Mapping):
            raise TypeError("Country quantity chart modality definitions must be mappings")
        modality_id, label = definition.get("id"), definition.get("label")
        if not isinstance(modality_id, str) or not modality_id or not isinstance(label, str) or not label.strip():
            raise ValueError("Country quantity chart modalities need nonempty IDs and labels")
        if modality_id in modality_labels:
            raise ValueError(f"Duplicate quantity chart modality ID: {modality_id}")
        modality_labels[modality_id] = label

    def validate_total(total: Any, dimension: str) -> Mapping[str, Any]:
        """Validate one stored aggregate row before using its plotted coordinates.

        Args:
            total: Untrusted country or modality aggregate row.
            dimension: Aggregate dimension key, either ``country`` or ``modality_id``.

        Returns:
            The validated mapping without mutating it.
        """
        if not isinstance(total, Mapping):
            raise TypeError("Country quantity totals must be mappings")
        value = total.get(dimension)
        if not isinstance(value, str) or not value:
            raise ValueError(f"Country quantity total needs a nonempty {dimension}")
        allowed_units = {"donors", "samples", "aliquots"}
        if options.get("include_uncertain_counts"):
            allowed_units.add("unit_unclear")
        if total.get("unit") not in allowed_units:
            raise ValueError(f"Unsupported exact quantity chart unit: {total.get('unit')!r}")
        if total.get("basis") not in {"collection", "submission_fallback", "direct_modality"}:
            raise ValueError(f"Unsupported quantity chart basis: {total.get('basis')!r}")
        reported = total.get("reported_total")
        if reported is not None and (isinstance(reported, bool) or not isinstance(reported, (int, float))
                                     or not math.isfinite(reported) or reported < 0):
            raise ValueError("Country quantity chart total must be null or a finite nonnegative number")
        segments = total.get("segments")
        if not isinstance(segments, Sequence) or isinstance(segments, (str, bytes)):
            raise TypeError("Country quantity chart segments must be a sequence")
        seen_banks: set[str] = set()
        for segment in segments:
            if not isinstance(segment, Mapping):
                raise TypeError("Country quantity chart segments must be mappings")
            bank_id, amount = segment.get("biobank_id"), segment.get("value")
            if not isinstance(bank_id, str) or bank_id not in banks:
                raise ValueError(f"Quantity chart segment references unknown biobank {bank_id!r}")
            if bank_id in seen_banks:
                raise ValueError(f"Quantity chart total has duplicate biobank segment {bank_id!r}")
            seen_banks.add(bank_id)
            if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount < 0:
                raise ValueError("Quantity chart segments require finite nonnegative values")
        segment_sum = sum(segment["value"] for segment in segments)
        if segments and reported is not None and not math.isclose(segment_sum, reported):
            raise ValueError("Country quantity chart segments do not sum to the reported total")
        if reported is None and segments:
            raise ValueError("Country quantity chart cannot plot segments for an unreported total")
        return total

    raw_country_totals = aggregates.get("country_totals", [])
    raw_modality_totals = aggregates.get("modality_totals", [])
    excluded = aggregates.get("excluded_contributions", [])
    if not isinstance(raw_country_totals, Sequence) or isinstance(raw_country_totals, (str, bytes)):
        raise TypeError("Country quantity aggregates country_totals must be a sequence")
    if not isinstance(raw_modality_totals, Sequence) or isinstance(raw_modality_totals, (str, bytes)):
        raise TypeError("Country quantity aggregates modality_totals must be a sequence")
    if not isinstance(excluded, Sequence) or isinstance(excluded, (str, bytes)):
        raise TypeError("Country quantity aggregate exclusions must be a sequence")
    country_totals = [validate_total(row, "country") for row in raw_country_totals]
    modality_totals = [validate_total(row, "modality_id") for row in raw_modality_totals]
    unplottable_totals: list[Mapping[str, Any]] = []
    for total in modality_totals:
        if total["modality_id"] not in modality_labels:
            raise ValueError(f"Quantity chart references undefined modality {total['modality_id']!r}")
        if total["reported_total"] is not None and not total["segments"]:
            unplottable_totals.append(total)
    unplottable_totals.extend(total for total in country_totals
                              if total["reported_total"] is not None and not total["segments"]
                              and not (options.get("allow_empty_confirmed_rows") and total["reported_total"] == 0))

    # Convert modality bank segments to country rows without combining modalities or bases.
    panels: list[dict[str, Any]] = []
    country_groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for total in country_totals:
        if total["reported_total"] is None:
            continue
        country_key = (total["unit"], total["basis"], str(total.get("temporal_status", "unspecified")))
        country_groups.setdefault(country_key, []).append(total)
    for (unit, basis, temporal), totals in sorted(country_groups.items()):
        panels.append({"view": "country-total", "label": "Country total",
                       "modality_id": "all", "unit": unit, "basis": basis,
                       "temporal_status": temporal,
                       "rows": [{"country": total["country"], "reported_total": total["reported_total"],
                                 "segments": total["segments"],
                                 "confirmed_total": total.get("confirmed_total", total["reported_total"]),
                                 "has_uncertainty": total.get("has_uncertainty", False)} for total in totals]})

    modality_groups: dict[tuple[str, str, str, str], dict[str, dict[str, Any]]] = {}
    for total in modality_totals:
        if total["reported_total"] is None:
            continue
        group_key = (total["modality_id"], total["unit"], total["basis"],
                     str(total.get("temporal_status", "unspecified")))
        country_rows = modality_groups.setdefault(group_key, {})
        for segment in total["segments"]:
            bank_id = segment["biobank_id"]
            country = str(banks[bank_id].get("country") or "Unknown")
            row = country_rows.setdefault(country, {"country": country, "reported_total": 0, "segments": []})
            row["reported_total"] += segment["value"]
            row["segments"].append(segment)
    for (modality_id, unit, basis, temporal), rows in sorted(modality_groups.items()):
        panels.append({"view": "modality", "label": modality_labels[modality_id],
                       "modality_id": modality_id, "unit": unit, "basis": basis,
                       "temporal_status": temporal, "rows": list(rows.values())})

    def panel_key(panel: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
        """Return a deterministic order key for chart families.

        Args:
            panel: Validated chart-family record.

        Returns:
            Basis/unit/view/modality/time ordering tuple.
        """
        return (panel["basis"], panel["unit"], panel["view"], panel["modality_id"],
                str(panel["temporal_status"]))

    bank_order = sorted({segment["biobank_id"] for panel in panels for row in panel["rows"]
                         for segment in row["segments"]})
    color_names = {bank_id: ("mucpUncertainGray" if banks[bank_id].get("quantity_uncertain") else "mucpBankColor")
                   + str(index) for index, bank_id in enumerate(bank_order)}
    gray_groups = defaultdict(list)
    for bank_id in bank_order:
        if banks[bank_id].get("quantity_uncertain"):
            gray_groups[str(banks[bank_id].get("country") or "Unknown")].append(bank_id)
    gray_levels = {bank_id: round(80 + 130 * index / max(1, len(group) - 1))
                   for group in gray_groups.values() for index, bank_id in enumerate(group)}
    color_definitions = [rf"\definecolor{{{color_names[bank_id]}}}{{HTML}}{{{('%02X' % gray_levels[bank_id]) * 3 if bank_id in gray_levels else _quantity_chart_color(index)}}}"
                         for index, bank_id in enumerate(bank_order)]
    scale_maxima: dict[tuple[str, str, str], float] = {}
    for panel in panels:
        scale_key = (panel["basis"], panel["unit"], panel["temporal_status"])
        scale_maxima[scale_key] = max([scale_maxima.get(scale_key, 0),
                                       *(row["reported_total"] for row in panel["rows"])])

    exclusion_reasons: dict[tuple[str, str, str], set[str]] = {}
    for item in excluded:
        if not isinstance(item, Mapping):
            raise TypeError("Quantity chart exclusions must be mappings")
        reason = _quantity_exclusion_label(item.get("reason", "excluded evidence"))
        unit = str(item.get("unit", ""))
        basis = str(item.get("basis", ""))
        for modality_id in item.get("modality_ids", []):
            exclusion_reasons.setdefault((modality_id, unit, basis), set()).add(reason)
        if item.get("view") == "country" or not item.get("modality_ids"):
            exclusion_reasons.setdefault(("all", unit, basis), set()).add(reason)

    charts: dict[str, str] = {}
    for index, total in enumerate(unplottable_totals, 1):
        dimension = str(total.get("modality_id", total.get("country", "quantity total")))
        title = modality_labels.get(dimension, dimension)
        note = (rf"\subsubsection*{{{_tex(title)}: aggregate total not charted}}" + "\n"
                + r"\noindent The reported total has no biobank segment attribution, so it cannot "
                  r"be shown as a country stack. The value remains in the supporting totals table.\par")
        key = (f"mucp-quantity-unplotted-{_slug(dimension) or 'total'}-"
               f"{total['basis']}-{total['unit']}-{index}")
        charts[key] = note
    page_size = int(options.get("quantity_rows_per_panel", 16))
    if page_size < 1:
        raise ValueError("quantity_rows_per_panel must be positive")
    basis_labels = {"collection": "collection totals", "submission_fallback": "submission fallback",
                    "direct_modality": "direct modality measurements"}
    for panel in sorted(panels, key=panel_key):
        rows = sorted(panel["rows"], key=lambda row: (str(row["country"]).casefold(), str(row["country"])))
        countries = [str(row["country"]) for row in rows]
        all_bank_ids = sorted({segment["biobank_id"] for row in rows for segment in row["segments"]})
        basis, unit, temporal = panel["basis"], panel["unit"], panel["temporal_status"]
        xmax = max(1, scale_maxima[(basis, unit, temporal)])
        for page, start in enumerate(range(0, len(rows), page_size), 1):
            page_rows = rows[start:start + page_size]
            page_bank_ids = sorted({segment["biobank_id"] for row in page_rows for segment in row["segments"]})
            legend = [rf"\parbox[t]{{0.45\textwidth}}{{\raggedright\textcolor{{{color_names[bank_id]}}}{{\rule{{0.9em}}{{0.9em}}}} "
                      + _quantity_chart_name(bank_id, banks, options) + "}" for bank_id in page_bank_ids]
            legend_lines = [r"\begin{longtable}{p{0.45\linewidth}p{0.45\linewidth}}",
                            r"\endfirsthead",
                            r"\multicolumn{2}{p{0.92\linewidth}}{\textbf{Reporting-unit segments (continued)}} \\",
                            r"\endhead"]
            for index in range(0, len(legend), 2):
                pair = legend[index:index + 2]
                legend_lines.append(" & ".join(pair + ([""] if len(pair) == 1 else [])) + r" \\")
            legend_lines.append(r"\end{longtable}")
            if any(row.get("has_uncertainty") for row in page_rows):
                legend_lines.extend([
                    r"\noindent\textbf{Reported counts---not a verified total.} "
                    r"Colored segments are confirmed; gray segments are unconfirmed/uncertain. "
                    r"Approximate counts and bounds use their reported number for width. "
                    r"Potentially overlapping populations may be stacked for visibility, not as a valid sum.\par",
                    descriptive._table([["Country/type", "Confirmed", "Uncertain reported numbers", "Total displayed"]]
                        + [[_tex(row["country"]), _quantity_plot_number(row.get("confirmed_total", row["reported_total"])),
                            _quantity_plot_number(row["reported_total"] - row.get("confirmed_total", row["reported_total"])),
                            _quantity_plot_number(row["reported_total"])] for row in page_rows],
                        r"p{0.22\linewidth}p{0.18\linewidth}p{0.30\linewidth}p{0.20\linewidth}"),
                ])
            count = len(page_rows)
            height = max(5.0, min(17.0, 0.72 * count + 2.8))
            axis_options = [
                r"width=0.96\linewidth, height=" + f"{height:g}cm,",
                "ytick={" + ",".join(str(index) for index in range(1, count + 1)) + "},",
                "yticklabels={" + ",".join(
                    r"\mbox{\sffamily\small " + _tex(country) + "}"
                    for country in countries[start:start + count]
                ) + "},",
                "ymin=0.5,ymax=" + str(count + 0.5) + ",y dir=reverse,",
                r"xlabel={Reported " + _tex(unit) + "},",
            ]
            data_lines = []
            # Additive segment widths use raw counts on the linear axis.
            for index, row in enumerate(page_rows, 1):
                boundaries = [0]
                cumulative = 0
                for segment in row["segments"]:
                    amount = segment["value"]
                    boundaries.append(cumulative + amount)
                    cumulative += amount
                data_lines.append("% raw cumulative boundaries: " + ",".join(
                    _quantity_plot_number(value) for value in boundaries))
                for segment_index, segment in enumerate(row["segments"]):
                    amount = segment["value"]
                    left = sum(item["value"] for item in row["segments"][:segment_index])
                    right = left + amount
                    color = color_names[segment["biobank_id"]]
                    data_lines.append(rf"\path[fill={color},draw=white,line width=0.3pt] "
                                 + f"(axis cs:{_quantity_plot_number(left)},{index - 0.36:g}) rectangle "
                                 + f"(axis cs:{_quantity_plot_number(right)},{index + 0.36:g});")
                if any(segment["value"] == 1 for segment in row["segments"]):
                    data_lines.append(r"% one-sized segment retained in the legend and contribution table")
            linear_options = [r"xmode=normal,xmin=0,xmax=" + _quantity_plot_number(xmax) + ",",
                             "xtick distance=" + _quantity_plot_number(max(1, xmax / 5)) + ",",
                             r"grid=major,scaled x ticks=false,"]
            slug = _slug(str(panel["modality_id"])) or "all"
            heading = (f"{panel['label']} ({basis_labels[basis]}, {unit}, "
                       f"time {str(temporal).replace('_', ' ')}), countries {start + 1}-{start + count}")
            legend_lines[2] = (r"\multicolumn{2}{p{0.92\linewidth}}{\raggedright\textbf{Reporting-unit segments (continued)} "
                               + _tex(heading) + r"} \\")
            exclusions = exclusion_reasons.get((str(panel["modality_id"]), unit, basis), set())
            exclusions |= exclusion_reasons.get(("all", unit, basis), set())
            related_exclusions = sorted({reason for (modality_id, excluded_unit, excluded_basis), reasons
                                         in exclusion_reasons.items()
                                         if modality_id not in {"all", str(panel["modality_id"])}
                                         and excluded_unit == unit and excluded_basis == basis
                                         for reason in reasons})
            note = (r"\noindent Gray segments retain uncertain source numbers, with their original qualifications "
                    r"in the legend. The bar's length is a display sum, not a confirmed country/biobank total.\par"
                    if options.get("include_uncertain_counts") else
                    r"\noindent Exact stacks include only eligible reported values. Bounds, qualified, "
                    r"unclear-unit and otherwise excluded quantities are not plotted; their source "
                    r"evidence and reasons remain in the supporting tables.\par")
            if exclusions:
                note += r"\noindent Excluded evidence for this view: " + _tex("; ".join(sorted(exclusions))) + r".\par"
            if related_exclusions:
                note += (r"\noindent Other modality views in this unit/basis exclude: "
                         + _tex("; ".join(related_exclusions)) + r".\par")
            base_key = (f"mucp-quantity-country-{slug}-{basis}-{unit}-"
                        f"{_slug(str(temporal)) or 'unspecified'}")
            for scale, x_options, chart_data in (("linear", linear_options, data_lines),):
                total_labels = []
                for index, row in enumerate(page_rows, 1):
                    total = row["reported_total"]
                    fraction = total / xmax
                    # Reserve label width inside the plot even for invisible small bars.
                    label_x = max(0.25, min(0.99, fraction))
                    label_y = 1 - (index - 0.5) / count
                    text = _quantity_plot_number(total) + " " + _tex(unit)
                    if options.get("show_confirmed_total_labels"):
                        text = "confirmed: " + _quantity_plot_number(row.get("confirmed_total", total)) + ", total: " + _quantity_plot_number(total)
                        label_x = max(0.60, label_x)
                    elif row.get("has_uncertainty"):
                        text += "*"
                    if total == 0:
                        text += " (zero total)"
                    total_labels.append(
                        rf"\node[anchor=east,font=\sffamily\small,fill=white,fill opacity=0.85,text opacity=1,inner sep=1pt] at "
                        + f"(rel axis cs:{label_x:g},{label_y:g}) " + "{" + text + "};")
                content = [rf"\subsubsection*{{{_tex(heading)} ({scale} scale)}}", note,
                           *color_definitions, r"\begin{tikzpicture}", r"\begin{axis}["]
                content.extend(axis_options + x_options + [
                    r"xticklabel style={font=\sffamily\small,"
                    r"/pgf/number format/fixed,/pgf/number format/precision=0,"
                    r"/pgf/number format/1000 sep={\,},"
                    r"/pgf/number format/assume math mode=true},",
                    r"label style={font=\sffamily\small},", r"]", *chart_data, *total_labels,
                    r"\end{axis}", r"\end{tikzpicture}\par",
                ])
                content.extend([
                           r"\smallskip\noindent\textbf{Reporting-unit segments}\par",
                           *legend_lines])
                charts[f"{base_key}-{scale}-{page}"] = "\n".join(line for line in content if line)
    return charts


def render_intersection_membership_table(catalogue: Sequence[Mapping[str, Any]], options: Mapping[str, Any]) -> str:
    """Link each labelled exclusive intersection to its contributing biobanks.

    Args:
        catalogue: Ordered bars with exact patterns, counts and country-grouped members.
        options: Combined-report contact visibility policy.

    Returns:
        Breakable TeX table immediately usable beneath the corresponding UpSet figure.
    """
    rows = [["Bar", "Count", "Selected material/data types or technologies", "Biobanks by country"]]
    for bar in catalogue:
        members = []
        for group in bar["countries"]:
            names = [_tex(bank["name"], bool(options.get("include_contact_details"))) + " (" + _breakable_identifier(bank["biobank_id"]) + ")"
                     for bank in group["biobanks"]]
            members.append(_tex(group["country"]) + ": " + "; ".join(names))
        rows.append([_tex(bar["bar_id"]), str(bar["count"]),
                     _tex("; ".join(bar["selected_labels"]) or "None selected"), r"\par ".join(members)])
    return descriptive._table(rows, r"p{0.06\linewidth}p{0.08\linewidth}p{0.29\linewidth}p{0.50\linewidth}")


def render_quantity_chart_views(views: Mapping[str, Any], options: Mapping[str, Any]) -> dict[str, str]:
    """Render consolidated quantity views using the audited raw-boundary stack primitive.

    Args:
        views: Prepared country and material/data rows with attributed raw segments.
        options: Combined report options and owning biobank records.

    Returns:
        Named TeX fragments with paired confirmed/inclusive country panels when
        source coverage is present. Units and measurement meanings stay separate;
        reporting dates remain in source descriptions rather than separate panels.
    """
    from copy import deepcopy
    from survey_combined_quantity_views import prepare_quantity_report_views, report_country_code
    inclusive = "source_coverage" in views
    if inclusive:
        views = prepare_quantity_report_views(views)
    charts = {}
    for dimension in ("country_views", "type_views"):
        variants = []
        for original in views.get(dimension, []):
            if inclusive and dimension == "country_views":
                confirmed = deepcopy(original)
                for row in confirmed["rows"]:
                    row["segments"] = [s for s in row["segments"] if not s.get("uncertain")]
                    row["display_total"] = row["confirmed_total"]
                    row["uncertain_total"] = 0
                variants.append((confirmed, "confirmed-only"))
            variants.append((original, "inclusive" if inclusive else "legacy"))
        for index, (view, variant) in enumerate(variants):
            is_type = dimension == "type_views"
            pseudo_banks = []
            source_banks = {b["biobank_id"]: b for b in options.get("biobanks", [])}
            totals = []
            for row in view["rows"]:
                segments = []
                for segment in row["segments"]:
                    sid = segment["id"]
                    if segment.get("uncertain"):
                        owner = source_banks[segment["biobank_ids"][0]]
                        relations = sorted({item.get("relation") or "reported_value" for item in
                                            segment.get("qualification_contributions") or [segment]})
                        amounts = [format_reported_quantity({"value": segment["value"], "unit": view["unit"],
                                                             "relation": relation}) for relation in relations]
                        amount = ("Different reported bounds: " if len(amounts) > 1 else "") + "; ".join(amounts)
                        details = []
                        for contribution in segment.get("qualification_contributions") or [segment]:
                            for field in ("source_unit", "raw_text", "qualifier_text"):
                                value = str(contribution.get(field) or "")
                                if value and value not in details:
                                    details.append(value)
                        detail = "; ".join(details)
                        dates = [date for date in segment.get("reporting_dates", []) if date != "unspecified"]
                        if dates:
                            detail += "; reporting period: " + ", ".join(dates)
                        parts = str(segment.get("question_id") or "").split(".")[0]
                        context = ("Part " + parts if parts in {"B", "C"} else segment.get("scope_label")) or "Scope unconfirmed"
                        reasons = "; ".join(_quantity_exclusion_label(r) for r in segment["reasons"])
                        name = ((report_country_code(owner.get("country")) + ": ") if is_type else "") + str(owner.get("name") or owner["biobank_id"])
                        bank = {"biobank_id": sid, "country": owner.get("country"), "name": name,
                                "quantity_uncertain": True, "quantity_legend": amount + "; " + _tex(context)
                                + ("; " + _tex(detail) if detail else "")
                                + "; unconfirmed/uncertain: " + _tex(reasons)}
                    else:
                        bank = {"biobank_id": sid, "name": sid, "country": sid} if is_type else source_banks[sid]
                        dates = [date for date in segment.get("reporting_dates", []) if date != "unspecified"]
                        if dates:
                            date_context = (row["label"] + ": " if is_type else "") + "reporting period: " + ", ".join(dates)
                            bank = {**bank, "quantity_legend": _tex(date_context)}
                    existing_bank = next((b for b in pseudo_banks if b["biobank_id"] == sid), None)
                    if existing_bank is None:
                        pseudo_banks.append(dict(bank))
                    elif bank.get("quantity_legend") and bank["quantity_legend"] not in existing_bank.get("quantity_legend", ""):
                        existing_bank["quantity_legend"] = (existing_bank.get("quantity_legend", "")
                            + r"\par " + bank["quantity_legend"]).lstrip()
                    segments.append({"biobank_id": sid, "value": segment["value"], "quantity_ids": segment["quantity_ids"]})
                totals.append({"country": row["label"], "unit": view["unit"], "basis": "collection",
                    "temporal_status": view["temporal_status"], "reported_total": row.get("display_total", row["reported_total"]),
                    "confirmed_total": row.get("confirmed_total", row["reported_total"]),
                    "has_uncertainty": any(segment.get("uncertain") for segment in row["segments"]),
                    "contributing_biobanks": len(segments), "contributing_scopes": len(segments),
                    "excluded_count": 0, "segments": segments})
            rendered = render_country_quantity_charts({"country_totals": totals, "modality_totals": [], "excluded_contributions": []},
                {**options, "biobanks": pseudo_banks, "modality_definitions": [],
                 "include_uncertain_counts": inclusive,
                 "show_confirmed_total_labels": inclusive and variant == "inclusive",
                 "allow_empty_confirmed_rows": variant == "confirmed-only",
                 "quantity_rows_per_panel": max(1, len(totals)) if inclusive else 16})
            meaning = "counts reported specifically for each type" if view["meaning"] == "direct" else "counts in collections reporting each type"
            for key, fragment in rendered.items():
                heading = f"{view['kind']}s: {meaning}" if is_type else "Reported counts by country"
                fragment = fragment.replace("Country total (collection totals, ", heading + " (")
                fragment = fragment.replace("time unspecified", "reporting date not specified")
                if inclusive:
                    fragment = fragment.replace(", time mixed reported dates", "")
                    variant_title = "confirmed only" if variant == "confirmed-only" else "confirmed + uncertain"
                    fragment = fragment.replace(" (linear scale)", " (" + variant_title + "; linear scale)")
                    if variant == "confirmed-only":
                        fragment = fragment.replace(
                            "Gray segments retain uncertain source numbers, with their original qualifications "
                            "in the legend. The bar's length is a display sum, not a confirmed country/biobank total.",
                            "Only confirmed contributions are shown. Zero means no confirmed contribution, "
                            "not that the country has no donors or samples.")
                if view["unit"] == "unit_unclear":
                    fragment = fragment.replace("Reported counts by country", "Reported size numbers with unclear units")
                    fragment = fragment.replace(r"unit\_unclear", "unit unclear")
                if is_type:
                    fragment = fragment.replace("Reporting-unit segments", "Country contributions").replace("countries 1-", "types 1-")
                charts[f"{dimension}-{index}-{variant}-{key}"] = fragment
    return charts


def _markdown_review(payload: Mapping[str, Any]) -> str:
    """Build a concise deterministic review packet without respondent contact fields.

    Args:
        payload: Combined payload containing matching/review diagnostics.

    Returns:
        UTF-8-ready Markdown summary of cohort and unresolved matching counts.
    """
    from survey_combined import render_match_review
    return render_match_review(payload) + "\n"


def _target_path(value: Any, key: str) -> Path:
    """Normalize and validate one output target without following a target symlink.

    Args:
        value: Path-like output target from the caller's mapping.
        key: Stable mapping key included in validation errors.

    Returns:
        Normalized absolute path without resolving symlink target contents.
    """
    path = Path(value).expanduser().absolute()
    if path.is_symlink():
        raise CombinedPublicationError(f"Output target {key} must not be a symbolic link: {path}")
    if not path.parent.is_dir():
        raise CombinedPublicationError(f"Output parent directory does not exist for {key}: {path.parent}")
    return path


def _compile_document(tex: str, label: str, passes: int = 2) -> Path:
    """Compile TeX in a temporary directory and return its complete PDF path.

    Args:
        tex: Complete self-contained XeLaTeX source.
        label: Safe filename stem for temporary compilation files.
        passes: Minimum XeLaTeX passes (at least two). Reference files must
            stabilize; up to four additional passes handle TOC pagination changes.

    Returns:
        Path to the compiled PDF inside a live temporary directory.

    Raises:
        InputError: If source writing/compilation fails, pass count is invalid,
            or reference files do not stabilize within the bounded pass limit.
    """
    directory = Path(tempfile.mkdtemp(prefix="combined-compile-"))
    source = directory / f"{_slug(label) or 'document'}.tex"
    try:
        if not isinstance(passes, int) or isinstance(passes, bool) or passes < 1:
            raise descriptive.InputError("Combined compilation passes must be a positive integer")
        descriptive._write_compilation_source(source, tex, "combined report source")
        minimum = max(2, passes)
        previous = None
        for index in range(minimum + 4):
            pdf = descriptive._run_xelatex(source, directory, passes=1)
            references = tuple(source.with_suffix(suffix).read_bytes()
                               if source.with_suffix(suffix).is_file() else b""
                               for suffix in (".aux", ".toc", ".out"))
            if index + 1 >= minimum and references == previous:
                return pdf
            previous = references
        raise descriptive.InputError("Combined report references did not stabilize; no PDF was published")
    except BaseException:
        shutil.rmtree(directory, ignore_errors=True)
        raise


def publish_combined_outputs(
    payload: Mapping[str, Any], rendered: descriptive.RenderedDescriptiveReport | None,
    targets: Mapping[str, Any], dossier_documents: Mapping[str, str],
    upset_matrices: Sequence[Any], overwrite: bool,
) -> None:
    """Stage and transactionally publish requested combined analysis artifacts.

    Args:
        payload: Canonical combined JSON payload to serialize without mutation.
        rendered: Optional complete report returned by ``render_combined_tex``.
        targets: Output-key mapping supporting JSON, TeX/PDF, chart/dossier
            directories, review Markdown and a pre-generated R bundle stage.
        dossier_documents: Safe filename-to-complete-TeX mapping for dossiers.
        upset_matrices: Optional matrix metadata; bundle bytes are supplied via
            ``targets['upset_bundle_stage']`` and are never generated or executed here.
        overwrite: Whether existing output files or directories may be replaced.

    Returns:
        None after every requested output is staged and all final targets are promoted.

    Raises:
        ValueError: If output targets conflict, rendering/staging fails, overwrite
            is disallowed, or publication cannot complete without rollback.
    """
    del upset_matrices  # The controller owns bundle generation and validation.
    allowed = {
        "output_json", "output_tex", "output_pdf", "output_chart_dir",
        "output_biobank_pdf_dir", "output_match_review", "output_upset_r_dir",
        "upset_bundle_stage",
    }
    unknown = set(targets) - allowed
    if unknown:
        raise CombinedPublicationError(f"Unknown combined publication targets: {sorted(unknown)}")
    raw = {
        key: value for key, value in targets.items()
        if key != "upset_bundle_stage" and value is not None
    }
    bundle_stage = targets.get("upset_bundle_stage")
    if "output_json" not in raw:
        raise CombinedPublicationError("Combined publication requires output_json.")
    normalized = {key: _target_path(value, key) for key, value in raw.items()}
    resolved = {key: path.resolve(strict=False) for key, path in normalized.items()}
    for left_key, left in resolved.items():
        for right_key, right in resolved.items():
            if left_key >= right_key:
                continue
            if left == right or left in right.parents or right in left.parents:
                raise CombinedPublicationError(f"Combined output targets overlap: {left_key} and {right_key}.")
    directory_keys = {"output_chart_dir", "output_biobank_pdf_dir", "output_upset_r_dir"}
    for key, path in normalized.items():
        if key in directory_keys:
            if path.exists() and not path.is_dir():
                raise CombinedPublicationError(f"Directory output target is not a directory: {path}")
            if path.exists() and any(path.iterdir()) and not overwrite:
                raise CombinedPublicationError(f"Output directory already exists and is not empty: {path}")
        elif path.exists() and not overwrite:
            raise CombinedPublicationError(f"Output already exists: {path}")
        if path.exists() and not path.is_dir() and key in directory_keys:
            raise CombinedPublicationError(f"Directory output target is not a directory: {path}")
    if any(key in raw for key in ("output_tex", "output_pdf", "output_chart_dir")) and rendered is None:
        raise CombinedPublicationError("Rendered report content is required for TeX, PDF, and chart outputs.")
    if "output_pdf" in raw and rendered is None:
        raise CombinedPublicationError("Rendered report content is required for PDF output.")
    if "output_biobank_pdf_dir" in raw and not dossier_documents:
        if payload.get("biobanks"):
            raise CombinedPublicationError("Dossier documents are required for nonempty per-biobank PDF output.")
    if "output_upset_r_dir" in raw:
        source = bundle_stage
        if source is None or not Path(source).is_dir():
            raise CombinedPublicationError("A prepared upset_bundle_stage directory is required for R bundle publication.")

    file_content: dict[Path, str] = {}
    if "output_json" in raw:
        file_content[normalized["output_json"]] = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False,
        ) + "\n"
    if "output_tex" in raw and rendered is not None:
        file_content[normalized["output_tex"]] = rendered.tex
    if "output_match_review" in raw:
        file_content[normalized["output_match_review"]] = _markdown_review(payload)

    prepared_directories: dict[str, Path] = {}
    temporary_roots: list[Path] = []
    file_stages: dict[Path, Path] = {}
    dir_stages: dict[Path, Path] = {}
    try:
        for target, content in file_content.items():
            file_stages[target] = descriptive._stage_publication_file(target, text=content)
        pdfs: dict[str, Path] = {}
        if "output_pdf" in raw and rendered is not None:
            pdfs["output_pdf"] = _compile_document(rendered.tex, "combined-report", passes=2)
            temporary_roots.append(pdfs["output_pdf"].parent)
        if "output_chart_dir" in raw and rendered is not None:
            stage = Path(tempfile.mkdtemp(prefix=".combined-charts-", dir=normalized["output_chart_dir"].parent))
            prepared_directories["output_chart_dir"] = stage
            for key, document in rendered.chart_documents.items():
                pdf = _compile_document(document, key, passes=1)
                temporary_roots.append(pdf.parent)
                shutil.copy2(pdf, stage / f"{key}.pdf")
        if "output_biobank_pdf_dir" in raw:
            stage = Path(tempfile.mkdtemp(prefix=".combined-dossiers-", dir=normalized["output_biobank_pdf_dir"].parent))
            prepared_directories["output_biobank_pdf_dir"] = stage
            for filename, document in dossier_documents.items():
                candidate = Path(filename)
                if candidate.is_absolute() or candidate.name != filename or candidate.suffix != ".tex":
                    raise CombinedPublicationError(f"Unsafe biobank dossier filename: {filename!r}")
                pdf = _compile_document(document, candidate.stem, passes=2)
                temporary_roots.append(pdf.parent)
                shutil.copy2(pdf, stage / f"{candidate.stem}.pdf")
        if "output_upset_r_dir" in raw:
            stage = Path(tempfile.mkdtemp(prefix=".combined-upset-", dir=normalized["output_upset_r_dir"].parent))
            shutil.rmtree(stage)
            shutil.copytree(Path(bundle_stage), stage)
            prepared_directories["output_upset_r_dir"] = stage

        for key, pdf in pdfs.items():
            target = normalized[key]
            file_stages[target] = descriptive._stage_publication_file(target, source=pdf)
        for key, stage in prepared_directories.items():
            dir_stages[normalized[key]] = stage
    except BaseException as exc:
        descriptive._discard_publication_stages(list(file_stages.values()))
        for stage in dir_stages.values():
            shutil.rmtree(stage, ignore_errors=True)
        for stage in prepared_directories.values():
            if stage.exists():
                shutil.rmtree(stage, ignore_errors=True)
        for root in temporary_roots:
            shutil.rmtree(root, ignore_errors=True)
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        if isinstance(exc, CombinedPublicationError):
            raise
        if isinstance(exc, descriptive.InputError):
            raise CombinedPublicationError(str(exc)) from exc
        raise CombinedPublicationError(f"Could not prepare combined outputs: {exc}") from exc

    all_stages: dict[Path, Path] = {**file_stages, **dir_stages}
    backups: dict[Path, Path] = {}
    published: list[Path] = []
    try:
        for target, stage in all_stages.items():
            if target.is_symlink():
                raise CombinedPublicationError(f"Output target became a symbolic link during preparation: {target}")
            if target.exists() and not overwrite:
                if not (target in dir_stages and target.is_dir() and not any(target.iterdir())):
                    raise CombinedPublicationError(f"Output already exists after preparation: {target}")
            if target.exists():
                if target.is_dir():
                    backup = Path(tempfile.mkdtemp(prefix=f".{target.name}.backup-", dir=target.parent))
                    backup.rmdir()
                else:
                    descriptor, backup_name = tempfile.mkstemp(prefix=f".{target.name}.backup-", dir=target.parent)
                    os.close(descriptor)
                    backup = Path(backup_name)
                os.replace(target, backup)
                backups[target] = backup
            os.replace(stage, target)
            published.append(target)
    except BaseException as exc:
        rollback_errors: list[str] = []
        for target in reversed(published):
            try:
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink(missing_ok=True)
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        for target, backup in backups.items():
            try:
                os.replace(backup, target)
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        for stage in file_stages.values():
            stage.unlink(missing_ok=True)
        for stage in dir_stages.values():
            if stage.exists():
                shutil.rmtree(stage, ignore_errors=True)
        for root in temporary_roots:
            shutil.rmtree(root, ignore_errors=True)
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        suffix = f"; rollback errors: {'; '.join(rollback_errors)}" if rollback_errors else ""
        raise CombinedPublicationError(f"Could not publish combined outputs: {exc}{suffix}") from exc
    else:
        for backup in backups.values():
            if backup.is_dir():
                shutil.rmtree(backup)
            else:
                backup.unlink(missing_ok=True)
        for root in temporary_roots:
            shutil.rmtree(root, ignore_errors=True)
