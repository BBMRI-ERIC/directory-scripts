"""Merge reviewed SO2 biobank submissions offline while retaining literal evidence."""

from dataclasses import replace
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

import pandas as pd
from nncontacts import NNContacts

from so2_descriptive_report import (
    InputError, QuestionDefinition, SurveyWorkbook, _country_code, _is_blank, _is_empty_free_text,
    normalize_structured_answer,
)


def default_response_identity_path(mapping_dir: Path) -> Path:
    """Select private reviewed identities or the data-free portable template.

    Args:
        mapping_dir: Repository directory containing SO2 mapping configuration.

    Returns:
        Local source-bound identity JSON when present, otherwise the committed
        empty example. Explicit caller paths must not use this fallback.
    """
    local = mapping_dir / "so2_2025_response_identities.json"
    return local if local.exists() else mapping_dir / "so2_2025_response_identities.example.json"


def merge_descriptive_responses(
    workbook: SurveyWorkbook,
    schema: Mapping[str, Any],
    questions: Sequence[QuestionDefinition],
    mapping: Mapping[str, Any],
) -> tuple[SurveyWorkbook, dict[str, Any]]:
    """Build one observation per trusted biobank, preserving unassigned submissions.

    Args:
        workbook: Original validated workbook; its dataframe is never modified.
        schema: Descriptive schema naming institution, country, and source-row columns.
        questions: Validated definitions used to normalize and compare answers.
        mapping: Version-one reviewed source mappings keyed by workbook SHA-256
            and row, plus exact institution country corrections. Row overrides
            apply only to their original workbook bytes.

    Returns:
        New workbook with merged observations and an auditable summary containing
        all literal source records, identity decisions, country corrections,
        duplicate groups, and question-level conflicts. Unresolved submissions
        remain individual observations rather than being name-merged.

    Raises:
        InputError: If mapping structure, reviewed IDs/countries, or explicit
            versus reviewed identities are inconsistent.
    """
    if not isinstance(mapping, Mapping) or mapping.get("schema_version") != 1:
        raise InputError("Unsupported SO2 response-identity mapping version.")
    reviewed_sources = mapping.get("reviewed_sources", {})
    countries = mapping.get("country_overrides", {})
    if not isinstance(reviewed_sources, dict) or not isinstance(countries, dict):
        raise InputError("SO2 reviewed_sources and country_overrides must be objects.")
    reviewed = reviewed_sources.get(workbook.source_sha256, {})
    if not isinstance(reviewed, dict):
        raise InputError("SO2 reviewed source rows must be an object.")
    institution_column = schema["columns"]["institution_column"]
    country_column = schema["columns"]["country_column"]
    row_column = schema["output"]["source_row_column"]
    id_column = "BiobankID in the Directory (if available)"
    groups: dict[str, list[dict[str, Any]]] = {}
    originals = []
    corrections = []
    unresolved = []
    decisions = []
    for _, source in workbook.responses.iterrows():
        row = int(source[row_column])
        record = {column: ("" if _is_blank(value) else str(value)) for column, value in source.items()}
        record[row_column] = row
        originals.append({"source_row": row, "answers": dict(record)})
        override = reviewed.get(str(row), {})
        if not isinstance(override, dict):
            raise InputError(f"Invalid reviewed mapping for SO2 row {row}.")
        raw_id = str(record.get(id_column, "")).strip()
        bare_id = raw_id.removeprefix("bbmri-eric:ID:")
        prefix = bare_id.partition("_")[0]
        valid_prefix = prefix in NNContacts.MEMBER_NODE_CODES or NNContacts.is_permitted_non_country_prefix(prefix)
        explicit = f"bbmri-eric:ID:{bare_id}" if valid_prefix and re.fullmatch(r"[A-Z]{2,5}_[A-Za-z0-9_.-]+", bare_id) else None
        identity = override.get("biobank_id") or explicit
        if identity and not re.fullmatch(r"bbmri-eric:ID:[A-Z]{2,5}_[A-Za-z0-9_.:-]+", identity):
            raise InputError(f"Invalid reviewed biobank ID for SO2 row {row}.")
        if explicit and identity != explicit:
            raise InputError(f"Reviewed identity conflicts with explicit biobank ID at SO2 row {row}.")
        country = _country_code(record[country_column])
        corrected = override.get("country") or countries.get(record[institution_column])
        if corrected is None and country == "??" and re.search(r"\bIRCCS\b", record[institution_column], re.IGNORECASE):
            corrected = "IT"
        if corrected is not None:
            if _country_code(corrected) == "??":
                raise InputError(f"Invalid reviewed country for SO2 row {row}.")
            country = _country_code(corrected)
        if country != "??":
            record[country_column] = country
        if record[country_column] != source[country_column]:
            corrections.append({"source_row": row, "institution": record[institution_column], "raw_country": str(source[country_column]), "country": country, "method": "reviewed_correction" if corrected else "country_alias"})
        if not identity:
            unresolved.append(row)
        key = identity or f"unresolved:row:{row}"
        groups.setdefault(key, []).append(record)
        decisions.append({"source_row": row, "biobank_id": identity, "method": "reviewed_override" if override.get("biobank_id") else "explicit_id" if explicit else "unresolved", "reason": override.get("reason")})
    merged = []
    observation_sources = []
    duplicates = []
    conflicts = []
    for identity, records in groups.items():
        result = dict(records[0])
        rows = [record[row_column] for record in records]
        if len(records) > 1:
            duplicates.append({"biobank_id": identity, "source_rows": rows, "country": result[country_column], "institutions": list(dict.fromkeys(record[institution_column] for record in records))})
        for question in questions:
            values = [record[question.column] for record in records if not _is_blank(record[question.column])]
            if not values:
                result[question.column] = ""
                continue
            if question.question_type == "free_text":
                result[question.column] = "\n\n".join(dict.fromkeys(value for value in values if not _is_empty_free_text(value)))
                continue
            selections = [normalize_structured_answer(question, value)[0] for value in values]
            distinct = {tuple(sorted(value)) for value in selections}
            if len(distinct) > 1:
                conflicts.append({"biobank_id": identity, "source_rows": rows, "question_id": question.question_id, "question_label": question.label, "raw_answers": [{"source_row": record[row_column], "answer": record[question.column]} for record in records], "handling": "union_with_difference_flag" if question.question_type == "multi_choice" else "conflicting_answers_category"})
            if question.question_type == "multi_choice":
                union = set(item for selection in selections for item in selection)
                ordered = [item for item in question.categories if item in union] + sorted(union - set(question.categories))
                result[question.column] = question.delimiter.join(ordered)
            else:
                result[question.column] = "Conflicting answers" if len(distinct) > 1 else selections[0][0]
        merged.append(result)
        observation_sources.append({
            "representative_source_row": rows[0],
            "biobank_id": None if identity.startswith("unresolved:") else identity,
            "source_rows": rows,
            "answer_sources": {
                question.question_id: [record[row_column] for record in records if not _is_blank(record[question.column])]
                for question in questions
            },
        })
    summary = {
        "statistical_unit": "trusted biobank identity; unresolved submissions retained separately",
        "received_submissions": len(originals), "analytical_observations": len(merged),
        "merged_submissions": len(originals) - len(merged),
        "duplicate_groups": duplicates, "conflicts": conflicts,
        "source_records": originals, "identity_decisions": decisions,
        "observation_sources": observation_sources,
        "country_corrections": corrections, "unresolved_identity_rows": unresolved,
    }
    return replace(workbook, responses=pd.DataFrame(merged, columns=workbook.responses.columns)), summary
