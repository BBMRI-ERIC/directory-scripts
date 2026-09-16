"""Read and validate SO2 descriptive-survey workbooks without external services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from types import MappingProxyType
from typing import Any, Literal, Mapping, Sequence
from unicodedata import normalize
from zipfile import BadZipFile

import openpyxl
import pandas as pd


class InputError(Exception):
    """Raised when a workbook or its descriptive schema is invalid."""


QuestionType = Literal["single_choice", "multi_choice", "ordinal", "free_text"]
_QUESTION_TYPES = frozenset({"single_choice", "multi_choice", "ordinal", "free_text"})


@dataclass(frozen=True)
class QuestionDefinition:
    """Validated classification and presentation metadata for one survey question."""

    question_id: str
    column: str
    question_type: QuestionType
    label: str
    categories: tuple[str, ...]
    delimiter: str | None
    parent_columns: tuple[str, ...]
    applicability: Mapping[str, Any] | None


@dataclass(frozen=True)
class SurveyWorkbook:
    """Validated workbook provenance and the retained response rows."""

    source_path: str
    source_sha256: str
    worksheet: str
    alias: str
    export_date: str
    header_row: int
    responses: pd.DataFrame
    total_data_rows: int
    excluded_blank_rows: int


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a JSON object while rejecting ambiguous duplicate keys."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"Schema contains duplicate JSON key: {key!r}.")
        result[key] = value
    return result


def load_descriptive_schema(path: str | Path) -> dict[str, Any]:
    """Load a descriptive-workbook schema while rejecting duplicate JSON keys."""
    schema_path = Path(path)
    try:
        with schema_path.open(encoding="utf-8") as schema_file:
            schema = json.load(schema_file, object_pairs_hook=_reject_duplicate_json_keys)
    except OSError as exc:
        raise InputError(f"Could not read descriptive schema {schema_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"Invalid JSON in descriptive schema {schema_path}: {exc}") from exc
    if not isinstance(schema, dict):
        raise InputError("Descriptive schema root must be a JSON object.")
    return schema


def _required_mapping(value: Any, name: str) -> Mapping[str, Any]:
    """Return a required object-shaped schema value."""
    if not isinstance(value, Mapping):
        raise InputError(f"Schema field {name} must be an object.")
    return value


def _required_text(value: Any, name: str) -> str:
    """Return a required nonblank schema string."""
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"Schema field {name} must be a nonblank string.")
    return value


def _text_sequence(value: Any, name: str) -> tuple[str, ...]:
    """Return a sequence of unique nonblank schema strings."""
    if not isinstance(value, list):
        raise InputError(f"Schema field {name} must be an array of strings.")
    values = tuple(_required_text(item, name) for item in value)
    if len(set(values)) != len(values):
        raise InputError(f"Schema field {name} must not contain duplicate columns.")
    return values


def _is_blank(value: Any) -> bool:
    """Return whether a scalar spreadsheet value is blank for response filtering."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return bool(pd.isna(value))


def is_nonblank_response_row(row: pd.Series, classified_columns: Sequence[str]) -> bool:
    """Return whether context or question cells contain a nonblank response value."""
    return any(not _is_blank(row[column]) for column in classified_columns)


def _validate_question(question: Any, position: int) -> QuestionDefinition:
    """Validate one question object and return its immutable public definition."""
    item = _required_mapping(question, f"questions[{position}]")
    required_fields = ("question_id", "column", "question_type", "label", "categories")
    for field in required_fields:
        if field not in item:
            raise InputError(f"Schema question {position} is missing required field {field}.")

    question_type = _required_text(item["question_type"], f"questions[{position}].question_type")
    if question_type not in _QUESTION_TYPES:
        raise InputError(
            f"Schema question {position} has invalid question_type {question_type!r}."
        )
    categories = _text_sequence(item["categories"], f"questions[{position}].categories")
    if question_type != "free_text" and not categories:
        raise InputError(f"Schema question {position} requires at least one category.")
    if question_type == "free_text" and categories:
        raise InputError(f"Schema free_text question {position} must not define categories.")

    delimiter = item.get("delimiter")
    if question_type == "multi_choice":
        delimiter = _required_text(delimiter, f"questions[{position}].delimiter")
    elif delimiter is not None:
        raise InputError(
            f"Schema question {position} may define delimiter only for multi_choice."
        )

    parent_columns = _text_sequence(
        item.get("parent_columns", []), f"questions[{position}].parent_columns"
    )
    applicability = item.get("applicability")
    if applicability is not None:
        applicability = MappingProxyType(dict(_required_mapping(
            applicability, f"questions[{position}].applicability"
        )))
    return QuestionDefinition(
        question_id=_required_text(item["question_id"], f"questions[{position}].question_id"),
        column=_required_text(item["column"], f"questions[{position}].column"),
        question_type=question_type,
        label=_required_text(item["label"], f"questions[{position}].label"),
        categories=categories,
        delimiter=delimiter,
        parent_columns=parent_columns,
        applicability=applicability,
    )


def validate_descriptive_schema(
    schema: Mapping[str, Any], columns: Sequence[str]
) -> list[QuestionDefinition]:
    """Validate the schema against source headers and return question definitions."""
    root = _required_mapping(schema, "schema")
    for field in ("schema_version", "input", "columns", "questions", "output"):
        if field not in root:
            raise InputError(f"Schema is missing required field {field}.")
    if root["schema_version"] != "1":
        raise InputError(f"Unknown descriptive schema version: {root['schema_version']!r}.")

    headers = tuple(columns)
    if any(not isinstance(header, str) or not header.strip() for header in headers):
        raise InputError("Workbook header row 4 contains a blank header.")
    if len(set(headers)) != len(headers):
        raise InputError("Workbook header row 4 contains nonunique headers.")

    input_schema = _required_mapping(root["input"], "input")
    for field in ("worksheet", "alias", "header_row"):
        if field not in input_schema:
            raise InputError(f"Schema input is missing required field {field}.")
    _required_text(input_schema["worksheet"], "input.worksheet")
    _required_text(input_schema["alias"], "input.alias")
    if input_schema["header_row"] != 4:
        raise InputError("Schema input.header_row must be 4.")

    column_schema = _required_mapping(root["columns"], "columns")
    for field in (
        "respondent_context", "institution_column", "country_column",
        "administrative_exclusions", "administrative_exclusion_reasons",
    ):
        if field not in column_schema:
            raise InputError(f"Schema columns is missing required field {field}.")
    context_columns = _text_sequence(
        column_schema["respondent_context"], "columns.respondent_context"
    )
    administrative_columns = _text_sequence(
        column_schema["administrative_exclusions"], "columns.administrative_exclusions"
    )
    institution_column = _required_text(
        column_schema["institution_column"], "columns.institution_column"
    )
    country_column = _required_text(
        column_schema["country_column"], "columns.country_column"
    )
    if institution_column not in context_columns:
        raise InputError("Schema columns.institution_column must be respondent context.")
    if country_column not in context_columns:
        raise InputError("Schema columns.country_column must be respondent context.")
    reasons = _required_mapping(
        column_schema["administrative_exclusion_reasons"],
        "columns.administrative_exclusion_reasons",
    )
    if set(reasons) != set(administrative_columns):
        missing = sorted(set(administrative_columns) - set(reasons))
        unexpected = sorted(set(reasons) - set(administrative_columns))
        column = missing[0] if missing else unexpected[0]
        raise InputError(
            f"Schema administrative exclusion reasons do not match administrative exclusion {column!r}."
        )
    for column in administrative_columns:
        _required_text(reasons[column], f"columns.administrative_exclusion_reasons.{column}")
    if not isinstance(root["questions"], list):
        raise InputError("Schema field questions must be an array.")
    questions = [_validate_question(question, index) for index, question in enumerate(root["questions"])]
    question_columns = {question.column for question in questions}
    for question in questions:
        if question.question_type == "free_text":
            invalid_parents = sorted(set(question.parent_columns) - question_columns)
            if invalid_parents:
                raise InputError(
                    f"Schema free_text parent column must name a declared question column: {invalid_parents[0]!r}."
                )

    classifications = (
        list(context_columns)
        + list(administrative_columns)
        + [question.column for question in questions]
    )
    duplicates = sorted({column for column in classifications if classifications.count(column) > 1})
    if duplicates:
        raise InputError(f"Source column classified more than once: {duplicates[0]!r}.")
    declared_columns = classifications + [
        parent_column for question in questions for parent_column in question.parent_columns
    ]
    missing = sorted(set(declared_columns) - set(headers))
    if missing:
        raise InputError(f"Schema-declared column is absent: {missing[0]!r}.")
    unclassified = sorted(set(headers) - set(classifications))
    if unclassified:
        raise InputError(f"Schema has unclassified source column: {unclassified[0]!r}.")

    output = _required_mapping(root["output"], "output")
    if "source_row_column" not in output:
        raise InputError("Schema output is missing required field source_row_column.")
    source_row_column = _required_text(output["source_row_column"], "output.source_row_column")
    if source_row_column in headers:
        raise InputError("Schema output.source_row_column must not collide with a source column.")
    return questions


def read_descriptive_workbook(
    path: str | Path, schema: Mapping[str, Any]
) -> SurveyWorkbook:
    """Read a validated SO2 workbook and retain only meaningful response rows."""
    source_path = Path(path)
    try:
        source_bytes = source_path.read_bytes()
    except OSError as exc:
        raise InputError(f"Could not read descriptive workbook {source_path}: {exc}") from exc

    try:
        workbook = openpyxl.load_workbook(source_path, read_only=True, data_only=True)
    except (
        OSError,
        ValueError,
        BadZipFile,
        openpyxl.utils.exceptions.InvalidFileException,
    ) as exc:
        raise InputError(f"Could not open descriptive workbook {source_path}: {exc}") from exc
    try:
        root = _required_mapping(schema, "schema")
        if "input" not in root:
            raise InputError("Schema is missing required field input.")
        input_schema = _required_mapping(root["input"], "input")
        worksheet_name = _required_text(input_schema.get("worksheet"), "input.worksheet")
        expected_alias = _required_text(input_schema.get("alias"), "input.alias")
        header_row = input_schema.get("header_row")
        if header_row != 4:
            raise InputError("Schema input.header_row must be 4.")
        if worksheet_name not in workbook.sheetnames:
            raise InputError(f"Workbook has wrong worksheet: expected {worksheet_name!r}.")
        sheet = workbook[worksheet_name]
        if sheet.cell(1, 1).value != "Alias" or sheet.cell(1, 2).value != expected_alias:
            raise InputError("Workbook row 1 alias does not match the descriptive schema.")
        export_date = sheet.cell(2, 2).value
        if sheet.cell(2, 1).value != "Export Date" or not isinstance(export_date, datetime):
            raise InputError("Workbook row 2 export date must be a labeled datetime.")
        export_date = export_date.isoformat()
        if any(cell.value is not None and str(cell.value).strip() for cell in sheet[3]):
            raise InputError("Workbook row 3 must be fully blank.")

        headers = [sheet.cell(4, column).value for column in range(1, sheet.max_column + 1)]
        if any(not isinstance(header, str) or not header.strip() for header in headers):
            raise InputError("Workbook header row 4 contains a blank header.")
        try:
            questions = validate_descriptive_schema(schema, headers)
        except InputError as exc:
            if "Schema-declared column is absent" in str(exc) or "unclassified source column" in str(exc):
                raise InputError("Workbook header row 4 does not match the descriptive schema.") from exc
            raise
        output = _required_mapping(_required_mapping(schema, "schema")["output"], "output")
        source_row_column = _required_text(output.get("source_row_column"), "output.source_row_column")

        records = []
        for source_row, values in enumerate(
            sheet.iter_rows(min_row=5, max_col=len(headers), values_only=True), start=5
        ):
            record = dict(zip(headers, values, strict=True))
            record[source_row_column] = source_row
            records.append(record)
    finally:
        workbook.close()

    data = pd.DataFrame.from_records(records, columns=[*headers, source_row_column])
    context_columns = tuple(schema["columns"]["respondent_context"])
    classified_response_columns = (*context_columns, *(question.column for question in questions))
    response_mask = data.apply(
        lambda row: is_nonblank_response_row(row, classified_response_columns), axis=1
    )
    responses = data.loc[response_mask].reset_index(drop=True)
    return SurveyWorkbook(
        source_path=str(source_path),
        source_sha256=sha256(source_bytes).hexdigest(),
        worksheet=worksheet_name,
        alias=expected_alias,
        export_date=export_date,
        header_row=4,
        responses=responses,
        total_data_rows=len(data.index),
        excluded_blank_rows=int((~response_mask).sum()),
    )


def _display_value(value: Any) -> str:
    """Return a JSON-safe literal response value, using Missing only for blanks."""
    return "Missing" if _is_blank(value) else str(value)


def _normalised_respondent_value(value: Any) -> str:
    """Normalize a respondent identity component solely for repeat detection."""
    return " ".join(_display_value(value).split()).casefold()


def _percentage(count: int, base: int) -> float | None:
    """Return a four-decimal percentage or null when no denominator exists."""
    return None if base == 0 else round(count * 100 / base, 4)


def _applicability_summary(
    question: QuestionDefinition, responses: pd.DataFrame
) -> dict[str, Any]:
    """Evaluate an explicitly declared routing rule, never infer one from blanks."""
    if question.applicability is None:
        return {"status": "unknown"}
    column = question.applicability.get("column")
    values = question.applicability.get("values")
    if not isinstance(column, str) or not isinstance(values, list) or not all(
        isinstance(value, str) for value in values
    ):
        raise InputError(
            f"Schema applicability for {question.column!r} must declare column and string values."
        )
    if column not in responses.columns:
        raise InputError(f"Schema applicability column is absent: {column!r}.")
    eligibility_unknown = responses[column].map(_is_blank)
    applicable = responses[column].isin(values) & ~eligibility_unknown
    inapplicable = ~applicable & ~eligibility_unknown
    answered = ~responses[question.column].map(_is_blank)
    return {
        "status": "evaluated",
        "column": column,
        "values": values,
        "applicable_rows": int(applicable.sum()),
        "inapplicable_rows": int(inapplicable.sum()),
        "eligible_unanswered_rows": int((applicable & ~answered).sum()),
        "structurally_skipped_rows": int((inapplicable & ~answered).sum()),
        "eligibility_unknown_rows": int(eligibility_unknown.sum()),
        "out_of_route_answered_rows": int((inapplicable & answered).sum()),
    }


def _respondent_groups(
    responses: pd.DataFrame, institution_column: str, country_column: str, source_row_column: str
) -> tuple[set[int], list[dict[str, Any]]]:
    """Flag repeated normalized country/institution pairs without removing source rows."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for _, row in responses.iterrows():
        key = (
            _normalised_respondent_value(row[country_column]),
            _normalised_respondent_value(row[institution_column]),
        )
        groups.setdefault(key, []).append(
            {
                "country": _display_value(row[country_column]),
                "institution": _display_value(row[institution_column]),
                "source_row": int(row[source_row_column]),
            }
        )
    duplicates = [group for group in groups.values() if len(group) > 1]
    duplicate_rows = {item["source_row"] for group in duplicates for item in group}
    return duplicate_rows, [
        {"responses": sorted(group, key=lambda item: item["source_row"])}
        for group in sorted(duplicates, key=lambda group: min(item["source_row"] for item in group))
    ]


def _structured_answers(
    question: QuestionDefinition, value: Any
) -> tuple[list[str], list[str]]:
    """Return deduplicated declared selections and duplicate selections from one response."""
    if _is_blank(value):
        return [], []
    raw_answers = (
        [part.strip() for part in str(value).split(question.delimiter)]
        if question.question_type == "multi_choice"
        else [str(value)]
    )
    answers: list[str] = []
    duplicates: list[str] = []
    for answer in raw_answers:
        if answer in answers:
            duplicates.append(answer)
        else:
            answers.append(answer)
    return answers, duplicates


def _structured_question_payload(
    question: QuestionDefinition,
    responses: pd.DataFrame,
    institution_column: str,
    country_column: str,
    source_row_column: str,
    duplicate_rows: set[int],
) -> dict[str, Any]:
    """Build counts and literal evidence for one non-narrative survey question."""
    counts = {category: 0 for category in question.categories}
    declared_categories = frozenset(question.categories)
    contributions: list[dict[str, Any]] = []
    duplicate_selections: list[dict[str, Any]] = []
    unexpected_selections: list[dict[str, Any]] = []
    answered_rows = 0
    for _, row in responses.iterrows():
        source_row = int(row[source_row_column])
        answers, duplicates = _structured_answers(question, row[question.column])
        if answers:
            answered_rows += 1
        if duplicates:
            duplicate_selections.append({"source_row": source_row, "values": duplicates})
        unexpected = [answer for answer in answers if answer not in declared_categories]
        if unexpected:
            unexpected_selections.append({"source_row": source_row, "values": unexpected})
            for answer in unexpected:
                counts.setdefault(answer, 0)
        selected = answers
        if not selected:
            selected = ["Missing"]
        for answer in selected:
            if answer != "Missing":
                counts[answer] += 1
            contributions.append(
                {
                    "value": answer,
                    "country": _display_value(row[country_column]),
                    "institution": _display_value(row[institution_column]),
                    "source_row": source_row,
                    "repeated_response": source_row in duplicate_rows,
                }
            )
    duplicate_selections.sort(key=lambda item: item["source_row"])
    unexpected_selections.sort(key=lambda item: item["source_row"])
    population = {"N": len(responses), "A": answered_rows, "M": len(responses) - answered_rows}
    population["blank_rows"] = population["M"]
    category_rows = [
        {
            "value": category,
            "count": counts[category],
            "percent_base": population["A"],
            "percent": _percentage(counts[category], population["A"]),
        }
        for category in counts
    ]
    category_rows.append(
        {
            "value": "Missing",
            "count": population["M"],
            "percent_base": population["N"],
            "percent": _percentage(population["M"], population["N"]),
        }
    )
    category_order = {value: index for index, value in enumerate((*counts, "Missing"))}
    contributions.sort(
        key=lambda item: (
            category_order[item["value"]], item["country"], item["institution"], item["source_row"]
        )
    )
    return {
        "population": population,
        "categories": category_rows,
        "pie_categories": [
            {**category, "excluded_from_chart": category["value"] == "Missing"}
            for category in category_rows
        ],
        "contributions": contributions,
        "free_text_rows": [],
        "diagnostics": {
            "duplicate_selections": duplicate_selections,
            "unexpected_selections": unexpected_selections,
        },
    }


def _free_text_question_payload(
    question: QuestionDefinition,
    responses: pd.DataFrame,
    institution_column: str,
    country_column: str,
    source_row_column: str,
    question_by_column: Mapping[str, QuestionDefinition],
) -> dict[str, Any]:
    """Build literal narrative evidence and parent-answer context for one free-text question."""
    rows = []
    missing_parent_answers: list[dict[str, Any]] = []
    unexpected_parent_answers: list[dict[str, Any]] = []
    for _, response in responses.iterrows():
        if _is_blank(response[question.column]):
            continue
        source_row = int(response[source_row_column])
        parent_answers = [
            {"column": column, "value": _display_value(response[column])}
            for column in question.parent_columns
        ]
        missing_columns = [answer["column"] for answer in parent_answers if answer["value"] == "Missing"]
        if missing_columns:
            missing_parent_answers.append({"source_row": source_row, "columns": missing_columns})
        unexpected_values = [
            answer
            for answer in parent_answers
            if answer["value"] != "Missing"
            and any(
                value not in question_by_column[answer["column"]].categories
                for value in _structured_answers(question_by_column[answer["column"]], response[answer["column"]])[0]
            )
        ]
        if unexpected_values:
            unexpected_parent_answers.append({"source_row": source_row, "values": unexpected_values})
        rows.append(
            {
                "country": _display_value(response[country_column]),
                "institution": _display_value(response[institution_column]),
                "source_row": source_row,
                "text": str(response[question.column]),
                "parent_answers": parent_answers,
            }
        )
    rows.sort(key=lambda item: (item["country"], item["institution"], item["source_row"]))
    population = {"N": len(responses), "A": len(rows), "M": len(responses) - len(rows)}
    population["blank_rows"] = population["M"]
    return {
        "population": population,
        "categories": [],
        "pie_categories": [],
        "contributions": [],
        "free_text_rows": rows,
        "diagnostics": {
            "duplicate_selections": [],
            "unexpected_selections": [],
            "missing_parent_answers": missing_parent_answers,
            "unexpected_parent_answers": unexpected_parent_answers,
        },
    }


def build_descriptive_payload(
    workbook: SurveyWorkbook, schema: Mapping[str, Any]
) -> dict[str, Any]:
    """Build a self-contained descriptive payload without Directory data.

    Args:
        workbook: Validated source workbook and nonblank survey rows.
        schema: Validated complete descriptive registry.

    Returns:
        JSON-serializable provenance, diagnostics, question counts, literal
        contribution rows, and free-text evidence.

    Raises:
        InputError: If the schema or its explicit applicability rule is invalid.
    """
    root = _required_mapping(schema, "schema")
    output = _required_mapping(root["output"], "output")
    source_row_column = _required_text(output["source_row_column"], "output.source_row_column")
    headers = [column for column in workbook.responses.columns if column != source_row_column]
    questions = validate_descriptive_schema(schema, headers)
    if source_row_column not in workbook.responses.columns:
        raise InputError(f"Workbook responses lack source-row column {source_row_column!r}.")
    columns = _required_mapping(root["columns"], "columns")
    institution_column = _required_text(columns["institution_column"], "columns.institution_column")
    country_column = _required_text(columns["country_column"], "columns.country_column")
    duplicate_rows, duplicate_groups = _respondent_groups(
        workbook.responses, institution_column, country_column, source_row_column
    )
    question_by_column = {question.column: question for question in questions}
    question_payloads = []
    for question in questions:
        detail = (
            _free_text_question_payload(
                question,
                workbook.responses,
                institution_column,
                country_column,
                source_row_column,
                question_by_column,
            )
            if question.question_type == "free_text"
            else _structured_question_payload(
                question, workbook.responses, institution_column, country_column,
                source_row_column, duplicate_rows
            )
        )
        question_payloads.append(
            {
                "question_id": question.question_id,
                "column": question.column,
                "label": question.label,
                "question_type": question.question_type,
                "applicability": _applicability_summary(question, workbook.responses),
                **detail,
            }
        )
    return {
        "payload_type": "so2_descriptive_statistics",
        "payload_version": "1",
        "provenance": {
            "source_path": workbook.source_path,
            "source_sha256": workbook.source_sha256,
            "worksheet": workbook.worksheet,
            "alias": workbook.alias,
            "export_date": workbook.export_date,
            "header_row": workbook.header_row,
            "total_data_rows": workbook.total_data_rows,
            "excluded_blank_rows": workbook.excluded_blank_rows,
            "included_response_rows": len(workbook.responses),
            "schema_version": root["schema_version"],
        },
        "diagnostics": {"duplicate_respondent_groups": duplicate_groups},
        "questions": question_payloads,
    }


@dataclass(frozen=True)
class RenderedDescriptiveReport:
    """Rendered report TeX and shared standalone-chart fragments."""

    tex: str
    chart_fragments: Mapping[str, str]
    chart_paths: Mapping[str, str]


_TEX_ESCAPE = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _tex(value: Any) -> str:
    """Escape a literal value for ordinary TeX text."""
    return "".join(_TEX_ESCAPE.get(character, character) for character in str(value))


def _slug(value: str) -> str:
    """Return an ASCII filename stem derived from presentation metadata."""
    ascii_value = normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", ascii_value.lower())).strip("-")


def _chart_key(question: Mapping[str, Any], answered_only: bool = False) -> str:
    """Return a stable chart filename key from the question identifier and label."""
    match = re.search(r"(?:^|_)q?0*(\d{1,3})(?:_|$)", str(question["question_id"]))
    if match is None:
        raise InputError(f"Question id lacks a numeric chart prefix: {question['question_id']!r}.")
    number = int(match.group(1))
    compact_names = {8: "experience", 9: "institution-type"}
    stem = compact_names.get(number, _slug(str(question["label"])))
    if not stem:
        raise InputError(f"Question label cannot form a chart filename: {question['label']!r}.")
    suffix = "-answered-only" if answered_only else ""
    return f"{number:02d}-{stem}{suffix}"


def _category_label(category: Mapping[str, Any]) -> str:
    """Return an explicit count and denominator-aware percentage label."""
    value = _tex(category["value"])
    count = int(category["count"])
    percentage = category.get("percent")
    if percentage is None:
        return f"{value}: {count} (no percentage base)"
    basis = "all included rows" if category["value"] == "Missing" else "answering rows"
    return f"{value}: {count} ({float(percentage):.1f}\\% of {basis})"


def _bar_fragment(question: Mapping[str, Any]) -> str:
    """Render a horizontal count bar chart, including its distinct Missing bar."""
    categories = question["categories"]
    rows = []
    labels = []
    for index, category in enumerate(categories, start=1):
        count = int(category["count"])
        rows.append(f"\\addplot+[fill=bbmriBlue] coordinates {{({count},{index})}};")
        labels.append(
            f"\\node[anchor=west,font=\\scriptsize] at (axis cs:{count + 0.08},{index}) "
            f"{{{_category_label(category)}}};"
        )
    ticks = ",".join(str(index) for index in range(1, len(categories) + 1))
    tick_labels = ",".join(f"{{{_tex(category['value'])}}}" for category in categories)
    return "\n".join([
        r"\begin{tikzpicture}",
        r"\begin{axis}[xbar, xmin=0, width=\linewidth, height="
        + f"{max(3.0, 0.65 * len(categories) + 1):.1f}cm,",
        f"ytick={{{ticks}}}, yticklabels={{{tick_labels}}},",
        r"xlabel={Count}, y dir=reverse, axis x line*=bottom, axis y line=none,",
        r"enlarge y limits=0.15, clip=false]",
        *rows,
        *labels,
        r"\end{axis}",
        r"\end{tikzpicture}",
    ])


def _pie_fragment(question: Mapping[str, Any], answered_only: bool) -> str:
    """Render a small categorical pie from the same payload category data."""
    categories = [
        category for category in question["pie_categories"]
        if not (answered_only and category.get("excluded_from_chart"))
    ]
    total = sum(int(category["count"]) for category in categories)
    title = "answered rows only" if answered_only else "including Missing"
    if total == 0:
        return "\n".join([
            r"\begin{tikzpicture}",
            rf"\node {{No responses ({title})}};",
            r"\end{tikzpicture}",
        ])
    start = 0.0
    colors = ("bbmriBlue", "bbmriTeal", "bbmriGold", "bbmriGray", "bbmriRed")
    slices = [r"\begin{tikzpicture}", rf"\node[above] at (0,1.9) {{{title}}};"]
    for index, category in enumerate(categories):
        end = start + 360 * int(category["count"]) / total
        slices.append(
            rf"\path[fill={colors[index % len(colors)]},draw=white] (0,0) -- ({start:.3f}:1.5)"
            rf" arc ({start:.3f}:{end:.3f}:1.5) -- cycle;"
        )
        start = end
    legend = r" \\ ".join(_category_label(category) for category in categories)
    slices.extend([rf"\node[align=left,text width=0.9\linewidth] at (0,-2.2) {{{legend}}};",
                   r"\end{tikzpicture}"])
    return "\n".join(slices)


def _table(rows: Sequence[Sequence[str]], columns: str) -> str:
    """Render a longtable with a repeated header and literal rows."""
    if not rows:
        return ""
    header, *body = rows
    return "\n".join([
        rf"\begin{{longtable}}{{{columns}}}",
        r"\toprule",
        " & ".join(header) + r" \\",
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        " & ".join(header) + r" \\",
        r"\midrule",
        r"\endhead",
        *[" & ".join(row) + r" \\" for row in body],
        r"\bottomrule",
        r"\end{longtable}",
    ])


def _question_tables(question: Mapping[str, Any]) -> str:
    """Render contribution or free-text evidence tables for a question."""
    if question["question_type"] == "free_text":
        rows = [[r"Country", r"Institution", r"Source row", r"Parent context", r"Response"]]
        for item in question["free_text_rows"]:
            parents = "; ".join(
                f"{parent['column']} = {parent['value']}" for parent in item["parent_answers"]
            ) or "None"
            rows.append([
                _tex(item["country"]), _tex(item["institution"]), str(item["source_row"]),
                _tex(parents), _tex(item["text"]),
            ])
        return _table(rows, r"p{0.12\linewidth}p{0.16\linewidth}r"
                      r"p{0.27\linewidth}p{0.27\linewidth}")
    rows = [[r"Value", r"Country", r"Institution", r"Source row", r"Note"]]
    for item in question["contributions"]:
        rows.append([
            _tex(item["value"]), _tex(item["country"]), _tex(item["institution"]),
            str(item["source_row"]),
            r"\textbf{Suspected repeated response}" if item["repeated_response"] else "",
        ])
    return _table(rows, r"p{0.18\linewidth}p{0.16\linewidth}p{0.22\linewidth}rp{0.22\linewidth}")


def _preamble() -> str:
    """Return the shared XeLaTeX preamble for reports and standalone charts."""
    return r"""\documentclass[11pt]{article}
\usepackage{fontspec}
\usepackage{longtable}
\usepackage{booktabs}
\usepackage{xcolor}
\usepackage{hyperref}
\usepackage{xurl}
\usepackage{tikz}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\definecolor{bbmriBlue}{HTML}{005A9C}
\definecolor{bbmriTeal}{HTML}{008C95}
\definecolor{bbmriGold}{HTML}{D8A000}
\definecolor{bbmriGray}{HTML}{7A7A7A}
\definecolor{bbmriRed}{HTML}{B63A3A}
"""


def _standalone_tex(fragment_key: str) -> str:
    """Return a standalone vector-chart document that inputs one shared fragment."""
    return _preamble() + "\n\\begin{document}\n\\input{fragments/" + fragment_key + ".tex}\n\\end{document}\n"


def _validate_render_payload(payload: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    """Validate the minimal immutable payload contract consumed by the renderer."""
    if payload.get("payload_type") != "so2_descriptive_statistics":
        raise InputError("Expected a so2_descriptive_statistics payload.")
    if payload.get("payload_version") != "1":
        raise InputError("Unsupported descriptive statistics payload version.")
    questions = payload.get("questions")
    if not isinstance(questions, list) or not all(isinstance(item, Mapping) for item in questions):
        raise InputError("Descriptive statistics payload questions must be an array of objects.")
    return questions


def render_descriptive_tex(
    payload: Mapping[str, Any], chart_dir: str | Path | None
) -> RenderedDescriptiveReport:
    """Render report TeX and reusable chart fragments from a descriptive payload."""
    questions = _validate_render_payload(payload)
    fragments: dict[str, str] = {}
    chart_paths: dict[str, str] = {}
    report = [_preamble(), r"\begin{document}", r"\section*{SO2 descriptive statistics}"]
    provenance = payload.get("provenance", {})
    report.append(rf"Alias: {_tex(provenance.get('alias', 'Unknown'))}\\")
    report.append(rf"Export date: {_tex(provenance.get('export_date', 'Unknown'))}\\")
    for question in questions:
        for field in ("question_id", "label", "question_type", "categories", "population",
                      "contributions", "free_text_rows"):
            if field not in question:
                raise InputError(f"Descriptive statistics question lacks {field}: {question!r}.")
        report.append(rf"\section*{{{_tex(question['label'])}}}")
        if question["question_type"] == "free_text":
            report.append(_question_tables(question) or r"\emph{No free-text responses.}")
            continue
        use_pie = question["question_type"] == "single_choice" and question.get("chart") == "pie"
        variants = (False, True) if use_pie and question["population"]["M"] else (False,)
        for answered_only in variants:
            key = _chart_key(question, answered_only)
            fragments[key] = _pie_fragment(question, answered_only) if use_pie else _bar_fragment(question)
            chart_paths[key] = (
                f"{Path(chart_dir).as_posix()}/{key}.pdf" if chart_dir is not None else ""
            )
            report.append(rf"\input{{fragments/{key}.tex}}")
            if chart_dir is not None:
                report.append(rf"\noindent\texttt{{{_tex(chart_paths[key])}}}\\")
        tables = _question_tables(question)
        if tables:
            report.append(tables)
    report.extend([r"\end{document}", ""])
    return RenderedDescriptiveReport(
        tex="\n".join([
            report[0],
            r"\iffalse",
            *fragments.values(),
            r"\fi",
            *report[1:],
        ]),
        chart_fragments=MappingProxyType(fragments),
        chart_paths=MappingProxyType(chart_paths),
    )


def _run_xelatex(source: Path, output_dir: Path) -> Path:
    """Compile one staged XeLaTeX source and return its completed PDF."""
    compiler = shutil.which("xelatex")
    if compiler is None:
        raise InputError("XeLaTeX is required to render descriptive report PDFs.")
    result = subprocess.run(
        [compiler, "-interaction=nonstopmode", "-halt-on-error", "-output-directory", str(output_dir), str(source)],
        cwd=source.parent, capture_output=True, text=True, check=False,
    )
    pdf = output_dir / f"{source.stem}.pdf"
    if result.returncode != 0 or not pdf.is_file():
        details = (result.stderr or result.stdout).strip()
        raise InputError(f"XeLaTeX failed for {source.name}: {details or 'no PDF was produced'}")
    return pdf


def _require_new_or_empty_chart_dir(chart_dir: Path) -> None:
    """Reject unsafe chart output paths and directories with existing artifacts."""
    if chart_dir.is_symlink():
        raise InputError(f"Chart directory must not be a symbolic link: {chart_dir}")
    if chart_dir.exists() and (not chart_dir.is_dir() or any(chart_dir.iterdir())):
        raise InputError(f"Chart directory must be new or empty: {chart_dir}")


def render_descriptive_pdf(
    rendered: RenderedDescriptiveReport,
    tex_path: str | Path,
    pdf_path: str | Path | None,
    chart_dir: str | Path | None,
) -> None:
    """Compile staged report and charts, publishing outputs only after all succeed."""
    target_tex = Path(tex_path)
    target_pdf = Path(pdf_path) if pdf_path is not None else None
    target_charts = Path(chart_dir) if chart_dir is not None else None
    if target_charts is not None:
        _require_new_or_empty_chart_dir(target_charts)
    targets = [target_tex, *(path for path in (target_pdf, target_charts) if path is not None)]
    if any(not target.parent.exists() for target in targets):
        raise InputError("Output parent directory does not exist.")
    with tempfile.TemporaryDirectory(prefix="so2-report-") as report_temporary, \
            tempfile.TemporaryDirectory(prefix="so2-charts-") as chart_temporary:
        report_stage = Path(report_temporary)
        chart_stage = Path(chart_temporary)
        for stage in (report_stage, chart_stage):
            fragments_dir = stage / "fragments"
            fragments_dir.mkdir()
            for key, fragment in rendered.chart_fragments.items():
                (fragments_dir / f"{key}.tex").write_text(fragment, encoding="utf-8")

        chart_pdfs: dict[str, Path] = {}
        for key in rendered.chart_fragments:
            source = chart_stage / f"{key}.tex"
            source.write_text(_standalone_tex(key), encoding="utf-8")
            chart_pdfs[key] = _run_xelatex(source, chart_stage)

        report_source = report_stage / "report.tex"
        report_source.write_text(rendered.tex, encoding="utf-8")
        report_pdf = _run_xelatex(report_source, report_stage) if target_pdf is not None else None
        staged_tex = report_stage / "published-report.tex"
        staged_tex.write_text(rendered.tex, encoding="utf-8")

        publish_charts = None
        if target_charts is not None:
            _require_new_or_empty_chart_dir(target_charts)
            publish_charts = Path(tempfile.mkdtemp(prefix=".so2-charts-", dir=target_charts.parent))
            try:
                for key, source_pdf in chart_pdfs.items():
                    shutil.copy2(source_pdf, publish_charts / f"{key}.pdf")
            except OSError as exc:
                shutil.rmtree(publish_charts, ignore_errors=True)
                raise InputError(f"Could not stage chart PDFs for publication: {exc}") from exc

        published: list[Path] = []
        backups: dict[Path, Path] = {}
        chart_dir_was_empty = target_charts is not None and target_charts.exists()

        def replace_file(source: Path, target: Path) -> None:
            """Publish one file while retaining its prior value for rollback."""
            if target.exists():
                descriptor, backup_name = tempfile.mkstemp(
                    prefix=".so2-report-backup-", dir=target.parent,
                )
                os.close(descriptor)
                backup = Path(backup_name)
                os.replace(target, backup)
                backups[target] = backup
            os.replace(source, target)
            published.append(target)

        try:
            replace_file(staged_tex, target_tex)
            if target_pdf is not None and report_pdf is not None:
                replace_file(report_pdf, target_pdf)
            if target_charts is not None and publish_charts is not None:
                if target_charts.exists():
                    target_charts.rmdir()
                os.replace(publish_charts, target_charts)
                published.append(target_charts)
        except OSError as exc:
            rollback_failures: list[OSError] = []
            for target in reversed(published):
                try:
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink(missing_ok=True)
                except OSError as rollback_exc:
                    rollback_failures.append(rollback_exc)
            for target, backup in backups.items():
                try:
                    os.replace(backup, target)
                except OSError as rollback_exc:
                    rollback_failures.append(rollback_exc)
            if chart_dir_was_empty and target_charts is not None:
                try:
                    if not target_charts.exists():
                        target_charts.mkdir()
                    elif not target_charts.is_dir() or any(target_charts.iterdir()):
                        raise OSError(f"chart directory has unexpected contents: {target_charts}")
                except OSError as rollback_exc:
                    rollback_failures.append(rollback_exc)
            if publish_charts is not None:
                try:
                    if publish_charts.exists():
                        shutil.rmtree(publish_charts)
                except OSError as rollback_exc:
                    rollback_failures.append(rollback_exc)
            if rollback_failures:
                details = "; ".join(str(rollback_exc) for rollback_exc in rollback_failures)
                raise InputError(
                    "Could not publish descriptive report outputs: "
                    f"{exc}; rollback could not establish a clean state: {details}"
                ) from exc
            raise InputError(f"Could not publish descriptive report outputs: {exc}") from exc
        for backup in backups.values():
            backup.unlink(missing_ok=True)
