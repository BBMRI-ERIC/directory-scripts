"""Read and validate SO2 descriptive-survey workbooks without external services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
import json
from math import ceil, cos, radians
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
    exclusive_categories: tuple[str, ...] = ()
    category_aliases: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))


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
    """Load a descriptive-workbook schema while rejecting duplicate JSON keys.

    Args:
        path: JSON schema path.

    Returns:
        Parsed object-shaped schema.

    Raises:
        InputError: If the file cannot be read, is malformed JSON, contains
            duplicate keys, or does not have an object root.
    """
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
    """Return whether context or question cells contain a nonblank response value.

    Args:
        row: One workbook data row.
        classified_columns: Context and question columns that define a response.

    Returns:
        True when at least one classified cell is nonblank.
    """
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
    exclusive_categories = _text_sequence(
        item.get("exclusive_categories", []),
        f"questions[{position}].exclusive_categories",
    )
    if exclusive_categories and question_type != "multi_choice":
        raise InputError(
            f"Schema question {position} may define exclusive categories only for multi_choice."
        )
    unknown_exclusive = sorted(set(exclusive_categories) - set(categories))
    if unknown_exclusive:
        raise InputError(
            f"Schema question {position} has unknown exclusive category {unknown_exclusive[0]!r}.")
    aliases = _required_mapping(item.get("category_aliases", {}), f"questions[{position}].category_aliases")
    category_aliases = {
        _required_text(source, f"questions[{position}].category_aliases key"):
        _required_text(target, f"questions[{position}].category_aliases[{source!r}]")
        for source, target in aliases.items()
    }
    unknown_alias_targets = sorted(set(category_aliases.values()) - set(categories))
    if unknown_alias_targets:
        raise InputError(
            f"Schema question {position} aliases unknown category {unknown_alias_targets[0]!r}."
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
        exclusive_categories=exclusive_categories,
        category_aliases=MappingProxyType(category_aliases),
    )


def validate_descriptive_schema(
    schema: Mapping[str, Any], columns: Sequence[str]
) -> list[QuestionDefinition]:
    """Validate the schema against source headers.

    Args:
        schema: Parsed descriptive schema.
        columns: Exact workbook headers.

    Returns:
        Immutable question definitions in report order.

    Raises:
        InputError: If the schema, classifications, routing, or references are invalid.
    """
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
    question_by_column = {question.column: question for question in questions}
    for question in questions:
        if question.applicability is None:
            continue
        applicability_column = question.applicability.get("column")
        applicability_values = question.applicability.get("values")
        if not isinstance(applicability_column, str) or not applicability_column.strip():
            raise InputError(
                f"Schema applicability for {question.column!r} must declare a nonblank column."
            )
        if applicability_column not in question_by_column:
            raise InputError(
                "Schema applicability column must name a declared question: "
                f"{applicability_column!r}."
            )
        values = _text_sequence(
            applicability_values, f"applicability values for {question.column!r}"
        )
        if not values:
            raise InputError(
                f"Schema applicability for {question.column!r} requires at least one value."
            )
        invalid_values = sorted(
            set(values) - set(question_by_column[applicability_column].categories)
        )
        if invalid_values:
            raise InputError(
                f"Schema applicability value {invalid_values[0]!r} is not declared "
                f"for {applicability_column!r}."
            )
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
    """Read an SO2 workbook and retain only meaningful response rows.

    Args:
        path: Source XLSX path.
        schema: Parsed descriptive schema for the workbook.

    Returns:
        Validated workbook provenance and retained response rows.

    Raises:
        InputError: If the workbook, envelope, headers, or schema relationship is invalid.
    """
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
    question: QuestionDefinition,
    responses: pd.DataFrame,
    question_by_column: Mapping[str, QuestionDefinition],
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
    parent_question = question_by_column[column]
    applicable_values = frozenset(values)
    eligibility_unknown = responses[column].map(_is_blank)
    applicable = responses[column].map(
        lambda value: bool(
            applicable_values.intersection(_structured_answers(parent_question, value)[0])
        )
    ) & ~eligibility_unknown
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
        canonical_answer = question.category_aliases.get(answer, answer)
        if canonical_answer in answers:
            duplicates.append(canonical_answer)
        else:
            answers.append(canonical_answer)
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
    contradictory_selections: list[dict[str, Any]] = []
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
        exclusive_values = [
            answer for answer in answers if answer in question.exclusive_categories
        ]
        if exclusive_values and len(answers) > 1:
            contradictory_selections.append(
                {
                    "source_row": source_row,
                    "exclusive_values": exclusive_values,
                    "values": answers,
                }
            )
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
            "contradictory_selections": contradictory_selections,
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
    """Build literal narrative evidence and parent-answer context for one free-text question.

    Args:
        question: Validated free-text question definition and its configured parent columns.
        responses: Included, nonblank survey response rows.
        institution_column: Response column identifying the responding institution.
        country_column: Response column containing the submitted country value.
        source_row_column: Synthetic workbook-row provenance column.
        question_by_column: Complete validated registry, used to diagnose parent values.

    Returns:
        JSON-serializable free-text rows retaining literal narrative and parent
        context, together with population and parent-context diagnostics.
    """
    rows = []
    missing_parent_answers: list[dict[str, Any]] = []
    unexpected_parent_answers: list[dict[str, Any]] = []
    for _, response in responses.iterrows():
        if _is_blank(response[question.column]) or _is_empty_free_text(response[question.column]):
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
            "contradictory_selections": [],
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
                "applicability": _applicability_summary(
                    question, workbook.responses, question_by_column
                ),
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
    chart_documents: Mapping[str, str]
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


_URL_PATTERN = re.compile(r"https?://[^\s<>{}\[\]]+")
_EMPTY_FREE_TEXT = frozenset({"", "-", "n/a", "na", "nil", "none", "no", "no comment", "nothing", "not applicable"})


def _is_empty_free_text(value: Any) -> bool:
    """Return whether a nominal free-text response conveys no narrative information.

    Args:
        value: Literal cell value from a free-text survey question.

    Returns:
        ``True`` when the normalized value is a known empty-response placeholder.
    """
    return str(value).strip().casefold().rstrip(".") in _EMPTY_FREE_TEXT


def _tex_with_links(value: Any) -> str:
    """Escape narrative text while replacing literal HTTP(S) URLs with short hyperlinks.

    Args:
        value: Literal free-text response which may include HTTP(S) URLs.

    Returns:
        TeX-safe text, with each detected URL represented by a ``link`` hyperlink.
    """
    text = str(value)
    parts: list[str] = []
    cursor = 0
    for match in _URL_PATTERN.finditer(text):
        parts.append(_tex(text[cursor:match.start()]))
        url = match.group(0)
        parts.append(r"\href{\detokenize{" + url + r"}}{link}")
        cursor = match.end()
    parts.append(_tex(text[cursor:]))
    return "".join(parts)


def _question_identifier(value: Any) -> str:
    """Render a compact monospace identifier with legal line breaks at underscores.

    Args:
        value: Question identifier from the descriptive-report schema.

    Returns:
        TeX markup for a smaller monospace identifier which may wrap at underscores.
    """
    return r"\smaller[3]\texttt{" + _tex(value).replace(r"\_", r"\_\hspace{0pt}") + r"}\normalsize"


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
    max_stem_length = 120 - len(f"{number:02d}-{suffix}.tex")
    stem = stem[:max_stem_length].rstrip("-")
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


def _bar_end_label(category: Mapping[str, Any]) -> str:
    """Return a short denominator-aware label for one bar endpoint.

    Args:
        category: Renderable category with count, percentage, and value semantics.

    Returns:
        TeX-safe count/percentage text using the report abbreviation glossary.
    """
    count = int(category["count"])
    percentage = category.get("percent")
    if percentage is None:
        return f"{count} (no percentage base)"
    basis = "oIR" if category["value"] == "Missing" else "oAR"
    return f"{count} ({float(percentage):.1f}\\% {basis})"


_ORDINAL_EXCEPTIONS = frozenset({
    "missing", "not applicable", "n/a", "don't know", "i don't know", "i don’t know",
})


def _bar_row_height(category: Mapping[str, Any]) -> float:
    """Return vertical axis space needed by a category label.

    Args:
        category: Renderable descriptive category with a literal ``value``.

    Returns:
        Axis-coordinate height that prevents neighbouring wrapped labels touching.
    """
    return max(1, ceil(len(str(category["value"])) / 26)) + 0.35


def _bar_chunks(
    categories: Sequence[Mapping[str, Any]], max_height: float = 12.0
) -> list[list[Mapping[str, Any]]]:
    """Partition ordered categories into page-sized chart groups.

    Args:
        categories: Categories in the semantic display order to preserve.
        max_height: Maximum sum of adaptive row heights in one chart fragment.

    Returns:
        Non-empty ordered groups; each fits the requested height unless one
        category alone requires more space.
    """
    chunks: list[list[Mapping[str, Any]]] = []
    current: list[Mapping[str, Any]] = []
    current_height = 0.0
    for category in categories:
        row_height = _bar_row_height(category)
        if current and current_height + row_height > max_height:
            chunks.append(current)
            current = []
            current_height = 0.0
        current.append(category)
        current_height += row_height
    if current:
        chunks.append(current)
    return chunks


def _bar_axis(
    categories: Sequence[Mapping[str, Any]], *, shared_max_count: int | None = None
) -> str:
    """Render one horizontal count-bar axis with adaptive row spacing.

    Args:
        categories: Non-empty ordered categories to render in this axis.
        shared_max_count: Optional maximum count across sibling chunks, ensuring
            their horizontal axes use an identical scale.

    Returns:
        A complete TikZ/PGFPlots axis fragment, or explanatory TeX when empty.
    """
    if not categories:
        return r"\emph{No categories in this group.}"
    max_count = shared_max_count or max(int(category["count"]) for category in categories)
    rows = []
    labels = []
    ticks = []
    cursor = 0.0
    for category in categories:
        row_height = _bar_row_height(category)
        position = cursor + row_height / 2
        cursor += row_height
        count = int(category["count"])
        normalized = str(category["value"]).strip().casefold()
        color = (
            "bbmriRed" if normalized == "missing"
            else "bbmriGray" if normalized in _ORDINAL_EXCEPTIONS
            else "bbmriBlue"
        )
        rows.append(
            f"\\addplot+[fill={color},draw={color},bar shift=0pt] coordinates "
            f"{{({count},{position:.2f})}};"
        )
        labels.append(
            f"\\node[anchor=west,font=\\scriptsize,align=left] "
            f"at (axis cs:{count + 0.08},{position:.2f}) "
            f"{{{_bar_end_label(category)}}};"
        )
        ticks.append(f"{position:.2f}")
    tick_labels = ",".join(
        rf"{{\parbox{{0.40\linewidth}}{{\raggedleft {_tex(category['value'])}}}}}"
        for category in categories
    )
    return "\n".join([
        r"\begin{tikzpicture}",
        r"\begin{axis}[xbar, xmin=0, xmax=" + f"{max(1, max_count) * 1.18:.2f}, "
        r"ymin=0, ymax=" + f"{cursor + 0.70:.2f}, width=0.42\\linewidth, xshift=0.46\\linewidth, "
        r"scale only axis, height=" + f"{max(3.0, 0.52 * cursor + 1):.1f}cm,",
        f"ytick={{{','.join(ticks)}}}, yticklabels={{{tick_labels}}},",
        r"xlabel={Count}, y dir=reverse, axis x line*=bottom, axis y line*=left,",
        r"yticklabel style={text width=0.40\linewidth,align=right,font=\scriptsize},",
        r"enlarge x limits={upper,value=0.14}, clip=false]",
        *rows,
        *labels,
        r"\end{axis}",
        r"\end{tikzpicture}",
    ])


def _bar_charts(categories: Sequence[Mapping[str, Any]]) -> str:
    """Render page-sized bar charts with an identical count scale.

    Args:
        categories: Ordered categories for one conceptual chart.

    Returns:
        TeX fragments separated by page breaks when multiple chunks are needed.
    """
    if not categories:
        return _bar_axis(categories)
    shared_max_count = max(int(category["count"]) for category in categories)
    fragments = []
    for index, chunk in enumerate(_bar_chunks(categories)):
        if index:
            fragments.extend([r"\clearpage", r"\noindent\textit{Continued}\par"])
        fragments.append(_bar_axis(chunk, shared_max_count=shared_max_count))
    return "\n".join(fragments)


def _bar_fragment(question: Mapping[str, Any]) -> str:
    """Render a question's categorical bars, separating ordinal exceptions.

    Args:
        question: Validated question payload containing category counts.

    Returns:
        TeX for one or more compatible bar-chart pages.
    """
    categories = question["categories"]
    if question["question_type"] != "ordinal":
        return _bar_charts(categories)
    ordered = [
        category for category in categories
        if str(category["value"]).strip().casefold() not in _ORDINAL_EXCEPTIONS
    ]
    exceptional = [category for category in categories if category not in ordered]
    fragments = [r"\noindent\textit{Ordered scale}\par", _bar_charts(ordered)]
    if any(int(category["count"]) for category in exceptional):
        fragments.extend([r"\noindent\textit{Exceptional categories}\par", _bar_charts(exceptional)])
    return "\n".join(fragments)

def _pie_fragment(question: Mapping[str, Any], answered_only: bool) -> str:
    """Render a pie whose leader lines connect each segment to its label.

    Args:
        question: Validated categorical question payload with pie categories.
        answered_only: Whether the Missing category is excluded from this chart.

    Returns:
        Complete TikZ markup with labels placed on the nearest horizontal side.
    """
    categories = [
        category for category in question["pie_categories"]
        if int(category["count"]) > 0
        and not (answered_only and category.get("excluded_from_chart"))
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
    legend_y = {"left": 1.35, "right": 1.35}
    colors = ("bbmriBlue", "bbmriTeal", "bbmriGold", "bbmriGray", "bbmriRed")
    slices = [r"\begin{tikzpicture}", rf"\node[above] at (0,1.9) {{{title}}};"]
    for index, category in enumerate(categories):
        count = int(category["count"])
        end = start + 360 * count / total
        middle = (start + end) / 2
        color = (
            "bbmriRed" if str(category["value"]).strip().casefold() == "missing"
            else colors[index % len(colors)]
        )
        label = f"{_tex(category['value'])}: {count} ({100 * count / total:.1f}\\%)"
        label_lines = max(1, ceil(len(str(category["value"])) / 42))
        side = "right" if cos(radians(middle)) >= 0 else "left"
        y = legend_y[side]
        slices.append(
            rf"\path[fill={color},draw=white] (0,0) -- ({start:.3f}:1.5)"
            rf" arc ({start:.3f}:{end:.3f}:1.5) -- cycle;"
        )
        if side == "right":
            slices.extend([
                rf"\draw[{color},dashed,thin] ({middle:.3f}:1.5) -- (1.72,{y:.2f});",
                rf"\fill[{color}] (1.76,{y - 0.06:.2f}) rectangle (1.90,{y + 0.06:.2f});",
                rf"\node[anchor=west,align=left,text width=0.40\linewidth,font=\scriptsize] at (1.98,{y:.2f}) {{{label}}};",
            ])
        else:
            slices.extend([
                rf"\draw[{color},dashed,thin] ({middle:.3f}:1.5) -- (-1.72,{y:.2f});",
                rf"\fill[{color}] (-1.90,{y - 0.06:.2f}) rectangle (-1.76,{y + 0.06:.2f});",
                rf"\node[anchor=east,align=right,text width=0.40\linewidth,font=\scriptsize] at (-1.98,{y:.2f}) {{{label}}};",
            ])
        legend_y[side] -= 0.42 * label_lines + 0.16
        start = end
    slices.append(r"\end{tikzpicture}")
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


_COUNTRY_CODES = {
    "austria": "AT", "belgium": "BE", "bulgaria": "BG", "czech republic": "CZ",
    "cz": "CZ", "denmark": "DK", "estonia": "EE", "finland": "FI", "france": "FR",
    "germany": "DE", "hungary": "HU", "italia": "IT", "italy": "IT", "latvia": "LV",
    "lithuania": "LT", "malta": "MT", "netherlands": "NL", "the netherlands": "NL",
    "norway": "NO", "poland": "PL", "qatar": "QA", "slovakia": "SK", "spain": "ES",
    "sweden": "SE", "switzerland": "CH",
}


def _country_code(value: Any) -> str:
    """Return the ISO 3166-1 alpha-2 code for a reported country or ``??`` if unknown.

    Args:
        value: Literal country value from one submitted survey row.

    Returns:
        A two-letter code after whitespace, case, and accent normalisation.
    """
    normalized = normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    return _COUNTRY_CODES.get(normalized.strip().casefold(), "??")


def _question_tables(question: Mapping[str, Any]) -> str:
    """Render the optional evidence table for one validated question payload.

    Args:
        question: Validated question payload with either free-text rows or structured contributions.

    Returns:
        TeX for the table, or an empty string if no free-text evidence exists.
    """
    if question["question_type"] == "free_text":
        evidence = question["free_text_rows"]
        if not evidence:
            return ""
        show_parent = any(item["parent_answers"] for item in evidence)
        headers = [r"CC", r"Institution"]
        if show_parent:
            headers.append(r"Parent context")
        headers.append(r"Response")
        rows = [headers]
        for item in evidence:
            # The nearby child-question heading identifies the parent question;
            # values retain the useful response context without repeating it verbatim.
            parents = "; ".join(parent["value"] for parent in item["parent_answers"]) or "None"
            row = [_tex(_country_code(item["country"])), _tex(item["institution"])]
            if show_parent:
                row.append(_tex(parents))
            row.append(_tex_with_links(item["text"]))
            rows.append(row)
        columns = (
            r"p{0.04\linewidth}p{0.27\linewidth}p{0.61\linewidth}"
            if not show_parent else r"p{0.04\linewidth}p{0.21\linewidth}p{0.20\linewidth}p{0.47\linewidth}"
        )
        return "\n".join([r"\smaller[1]", _table(rows, columns), r"\normalsize"])
    grouped: dict[tuple[str, str], list[str]] = {}
    for item in question["contributions"]:
        entry = _tex(item["institution"])
        if item["repeated_response"]:
            entry += " [suspected repeated response]"
        grouped.setdefault((str(item["value"]), str(item["country"])), []).append(entry)
    rows = [[r"Value", r"Country", r"Institutions"]]
    for (value, country), institutions in grouped.items():
        rows.append([
            _tex(value), _tex(country), r"{\raggedright " + "; ".join(institutions) + r"\par}",
        ])
    return "\n".join([
        r"\smaller[3]",
        _table(rows, r"p{0.22\linewidth}p{0.18\linewidth}p{0.52\linewidth}"),
        r"\normalsize",
    ])


def _preamble() -> str:
    """Return the shared XeLaTeX preamble for reports and standalone charts."""
    return r"""\documentclass[11pt]{article}
\usepackage{fontspec}
\usepackage{relsize}
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


def _applicability_text(question: Mapping[str, Any]) -> str:
    """Return a compact literal rendering of declared applicability results."""
    applicability = question["applicability"]
    if applicability.get("status") != "evaluated":
        return "Applicability: unknown (no verified routing rule)"
    values = ", ".join(str(value) for value in applicability["values"])
    return (
        f"Applicability: evaluated from {applicability['column']} = {values}; "
        f"applicable {applicability['applicable_rows']}; "
        f"inapplicable {applicability['inapplicable_rows']}; "
        f"eligible unanswered {applicability['eligible_unanswered_rows']}; "
        f"structurally skipped {applicability['structurally_skipped_rows']}; "
        f"eligibility unknown {applicability['eligibility_unknown_rows']}; "
        f"out-of-route answered {applicability['out_of_route_answered_rows']}"
    )


def _chart_unit(question: Mapping[str, Any]) -> str:
    """Return the observation unit represented by one chart bar or slice."""
    if question["question_type"] == "multi_choice":
        return "submitted response rows selecting each value"
    return "submitted response rows"


def _standalone_tex(
    question: Mapping[str, Any], fragment: str, answered_only: bool,
) -> str:
    """Return a self-contained chart document with interpretation metadata."""
    population = question["population"]
    variant = " (answered rows only)" if answered_only else ""
    note = (
        f"Missing: {population['M']} of {population['N']} included rows. "
        "Blank means blank; applicability is reported separately."
    )
    return "\n".join([
        _preamble(),
        r"\begin{document}",
        rf"\section*{{{_tex(question['label'])}{_tex(variant)}}}",
        rf"\noindent Question identifier: {_question_identifier(question['question_id'])}\\",
        rf"Denominator: {population['A']} answering rows; Missing uses "
        rf"{population['N']} included rows\\",
        rf"Unit: {_tex(_chart_unit(question))}\\",
        rf"\emph{{{_tex(note)}}}",
        fragment,
        r"\end{document}",
        "",
    ])


def _payload_mapping(value: Any, path: str) -> Mapping[str, Any]:
    """Return one object-shaped payload value or raise a contextual input error."""
    if not isinstance(value, Mapping):
        raise InputError(f"Descriptive statistics payload {path} must be an object.")
    return value


def _payload_array(value: Any, path: str) -> list[Any]:
    """Return one array-shaped payload value or raise a contextual input error."""
    if not isinstance(value, list):
        raise InputError(f"Descriptive statistics payload {path} must be an array.")
    return value


def _payload_text(value: Any, path: str) -> str:
    """Return one nonblank payload string or raise a contextual input error."""
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"Descriptive statistics payload {path} must be a nonblank string.")
    return value


def _payload_count(value: Any, path: str) -> int:
    """Return one nonnegative integer payload count."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InputError(
            f"Descriptive statistics payload {path} must be a nonnegative integer."
        )
    return value


def _validate_render_payload(payload: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    """Validate the nested immutable payload contract consumed by the renderer."""
    if not isinstance(payload, Mapping):
        raise InputError("Descriptive statistics payload root must be a JSON object.")
    if payload.get("payload_type") != "so2_descriptive_statistics":
        raise InputError("Expected a so2_descriptive_statistics payload.")
    if payload.get("payload_version") != "1":
        raise InputError("Unsupported descriptive statistics payload version.")
    provenance = _payload_mapping(payload.get("provenance"), "provenance")
    for field in ("source_path", "source_sha256", "worksheet", "alias", "export_date"):
        _payload_text(provenance.get(field), f"provenance.{field}")
    for field in (
        "header_row", "total_data_rows", "excluded_blank_rows", "included_response_rows",
    ):
        _payload_count(provenance.get(field), f"provenance.{field}")
    if not isinstance(provenance.get("schema_version"), (str, int)):
        raise InputError(
            "Descriptive statistics payload provenance.schema_version must be text or an integer."
        )
    _payload_mapping(payload.get("diagnostics"), "diagnostics")
    questions = _payload_array(payload.get("questions"), "questions")
    validated_questions: list[Mapping[str, Any]] = []
    for index, value in enumerate(questions):
        path = f"questions[{index}]"
        question = _payload_mapping(value, path)
        for field in ("question_id", "column", "label"):
            _payload_text(question.get(field), f"{path}.{field}")
        question_type = question.get("question_type")
        if question_type not in _QUESTION_TYPES:
            raise InputError(
                f"Descriptive statistics payload {path}.question_type is invalid: "
                f"{question_type!r}."
            )
        population = _payload_mapping(question.get("population"), f"{path}.population")
        population_counts = {
            field: _payload_count(population.get(field), f"{path}.population.{field}")
            for field in ("N", "A", "M")
        }
        if population_counts["N"] != population_counts["A"] + population_counts["M"]:
            raise InputError(
                f"Descriptive statistics payload {path}.population must satisfy N = A + M."
            )
        if "blank_rows" in population:
            blank_rows = _payload_count(
                population["blank_rows"], f"{path}.population.blank_rows"
            )
            if blank_rows != population_counts["M"]:
                raise InputError(
                    f"Descriptive statistics payload {path}.population.blank_rows must equal M."
                )
        categories = _payload_array(question.get("categories"), f"{path}.categories")
        for category_index, category_value in enumerate(categories):
            category_path = f"{path}.categories[{category_index}]"
            category = _payload_mapping(category_value, category_path)
            _payload_text(category.get("value"), f"{category_path}.value")
            _payload_count(category.get("count"), f"{category_path}.count")
            _payload_count(category.get("percent_base"), f"{category_path}.percent_base")
            percentage = category.get("percent")
            if percentage is not None and (
                isinstance(percentage, bool) or not isinstance(percentage, (int, float))
            ):
                raise InputError(
                    f"Descriptive statistics payload {category_path}.percent "
                    "must be numeric or null."
                )
        for field in ("contributions", "free_text_rows"):
            rows = _payload_array(question.get(field), f"{path}.{field}")
            if not all(isinstance(row, Mapping) for row in rows):
                raise InputError(
                    f"Descriptive statistics payload {path}.{field} must contain objects."
                )
            for row_index, row in enumerate(rows):
                row_path = f"{path}.{field}[{row_index}]"
                for text_field in ("country", "institution"):
                    _payload_text(row.get(text_field), f"{row_path}.{text_field}")
                _payload_count(row.get("source_row"), f"{row_path}.source_row")
                if field == "contributions":
                    _payload_text(row.get("value"), f"{row_path}.value")
                    if not isinstance(row.get("repeated_response"), bool):
                        raise InputError(
                            f"Descriptive statistics payload "
                            f"{row_path}.repeated_response must be boolean."
                        )
                else:
                    _payload_text(row.get("text"), f"{row_path}.text")
                    parent_answers = _payload_array(
                        row.get("parent_answers"), f"{row_path}.parent_answers"
                    )
                    for parent_index, parent_value in enumerate(parent_answers):
                        parent_path = f"{row_path}.parent_answers[{parent_index}]"
                        parent = _payload_mapping(parent_value, parent_path)
                        _payload_text(parent.get("column"), f"{parent_path}.column")
                        _payload_text(parent.get("value"), f"{parent_path}.value")
        _payload_mapping(question.get("diagnostics"), f"{path}.diagnostics")
        applicability = _payload_mapping(
            question.get("applicability"), f"{path}.applicability"
        )
        status = applicability.get("status")
        if status not in {"unknown", "evaluated"}:
            raise InputError(
                f"Descriptive statistics payload {path}.applicability.status is invalid."
            )
        if status == "evaluated":
            _payload_text(applicability.get("column"), f"{path}.applicability.column")
            applicability_values = _payload_array(
                applicability.get("values"), f"{path}.applicability.values"
            )
            if not applicability_values or not all(
                isinstance(item, str) and item.strip() for item in applicability_values
            ):
                raise InputError(
                    f"Descriptive statistics payload {path}.applicability.values "
                    "must contain nonblank strings."
                )
            for field in (
                "applicable_rows", "inapplicable_rows", "eligible_unanswered_rows",
                "structurally_skipped_rows", "eligibility_unknown_rows",
                "out_of_route_answered_rows",
            ):
                _payload_count(
                    applicability.get(field), f"{path}.applicability.{field}"
                )
        if question_type == "free_text" and categories:
            raise InputError(
                f"Descriptive statistics payload {path}.categories must be empty for free_text."
            )
        if question_type != "free_text":
            pie_categories = _payload_array(
                question.get("pie_categories"), f"{path}.pie_categories"
            )
            for category_index, category_value in enumerate(pie_categories):
                category_path = f"{path}.pie_categories[{category_index}]"
                category = _payload_mapping(category_value, category_path)
                _payload_text(category.get("value"), f"{category_path}.value")
                _payload_count(category.get("count"), f"{category_path}.count")
                _payload_count(
                    category.get("percent_base"), f"{category_path}.percent_base"
                )
                percentage = category.get("percent")
                if percentage is not None and (
                    isinstance(percentage, bool)
                    or not isinstance(percentage, (int, float))
                ):
                    raise InputError(
                        f"Descriptive statistics payload {category_path}.percent "
                        "must be numeric or null."
                    )
                if not isinstance(category.get("excluded_from_chart"), bool):
                    raise InputError(
                        f"Descriptive statistics payload "
                        f"{category_path}.excluded_from_chart must be boolean."
                    )
        validated_questions.append(question)
    return validated_questions


def render_descriptive_tex(
    payload: Mapping[str, Any],
    chart_dir: str | Path | None,
    report_path: str | Path | None = None,
    include_contribution_tables: bool = False,
) -> RenderedDescriptiveReport:
    """Render a self-contained report and reusable standalone chart documents.

    Args:
        payload: Validated descriptive-statistics payload.
        chart_dir: Optional target directory used to derive printable chart paths.
        report_path: Optional report path used as the base for relative chart paths.
        include_contribution_tables: Whether optional grouped structured-response
            evidence tables are included in the report body.

    Returns:
        Report TeX, shared chart fragments, standalone documents, and chart paths.

    Raises:
        InputError: If the payload is malformed or chart metadata cannot be
            converted into stable filenames.
    """
    questions = _validate_render_payload(payload)
    fragments: dict[str, str] = {}
    chart_documents: dict[str, str] = {}
    chart_paths: dict[str, str] = {}
    report = [_preamble(), r"\begin{document}", r"\section*{SO2 descriptive statistics}"]
    provenance = payload.get("provenance", {})
    report.append(rf"Source path: {_tex(provenance['source_path'])}\\")
    report.append(rf"Alias: {_tex(provenance.get('alias', 'Unknown'))}\\")
    report.append(rf"Export date: {_tex(provenance.get('export_date', 'Unknown'))}\\")
    report.append(rf"Source SHA-256: {_tex(provenance.get('source_sha256', 'Unknown'))}\\")
    report.append(rf"Worksheet: {_tex(provenance.get('worksheet', 'Unknown'))}\\")
    report.append(rf"Header row: {_tex(provenance['header_row'])}\\")
    report.append(rf"Total data rows: {_tex(provenance['total_data_rows'])}\\")
    report.append(
        rf"Included response rows: {_tex(provenance.get('included_response_rows', 'Unknown'))}\\"
    )
    report.append(
        rf"Excluded blank rows: {_tex(provenance.get('excluded_blank_rows', 'Unknown'))}\\"
    )
    report.append(
        rf"Descriptive schema version: {_tex(provenance.get('schema_version', 'Unknown'))}\\"
    )
    report.extend([
        r"\tableofcontents",
        r"\clearpage",
        r"\section*{Abbreviations}",
        r"\noindent CC: ISO 3166-1 alpha-2 country code; N: included response rows; A: rows with a nonblank answer; M: missing responses (N - A).\\",
        r"\noindent oAR: percentage of answering rows; oIR: percentage of included response rows.\\",
        r"\clearpage",
    ])
    for question in questions:
        for field in ("question_id", "label", "question_type", "categories", "population",
                      "contributions", "free_text_rows", "applicability"):
            if field not in question:
                raise InputError(f"Descriptive statistics question lacks {field}: {question!r}.")
        report.extend([r"\clearpage", rf"\section{{{_tex(question['label'])}}}"])
        population = question["population"]
        report.append(rf"\noindent Question identifier: {_question_identifier(question['question_id'])}\\")
        report.append(rf"N/A/M (included/answered/missing): {population['N']} / {population['A']} / {population['M']}\\")
        report.append(rf"{_tex(_applicability_text(question))}\\")
        if question["question_type"] == "free_text":
            report.append(_question_tables(question) or r"\emph{No text responses.}")
            continue
        use_pie = question["question_type"] == "single_choice"
        variants = (False, True) if use_pie and population["M"] else ((True,) if use_pie else (False,))
        question_paths: list[str] = []
        for answered_only in variants:
            key = _chart_key(question, answered_only)
            fragment = _pie_fragment(question, answered_only) if use_pie else _bar_fragment(question)
            fragments[key] = fragment
            chart_documents[key] = _standalone_tex(question, fragment, answered_only)
            report.append(fragment)
            if chart_dir is not None:
                chart_pdf = Path(chart_dir) / f"{key}.pdf"
                base = Path(report_path).parent if report_path is not None else Path.cwd()
                chart_paths[key] = Path(os.path.relpath(chart_pdf, start=base)).as_posix()
                question_paths.append(chart_paths[key])
                report.extend([
                    r"\noindent",
                    r"\begingroup\raggedright\smaller[3]",
                    rf"\url{{{_tex(chart_paths[key])}}}\par",
                    r"\endgroup",
                ])
        if chart_dir is not None and isinstance(question, dict):
            question["chart_paths"] = question_paths
        tables = _question_tables(question) if (
            question["question_type"] == "free_text" or include_contribution_tables
        ) else ""
        if tables:
            report.append(tables)
    report.extend([r"\end{document}", ""])
    if chart_dir is not None and isinstance(payload, dict):
        payload["chart_paths"] = dict(chart_paths)
    return RenderedDescriptiveReport(
        tex="\n".join(report),
        chart_fragments=MappingProxyType(fragments),
        chart_documents=MappingProxyType(chart_documents),
        chart_paths=MappingProxyType(chart_paths),
    )


def _run_xelatex(source: Path, output_dir: Path, passes: int = 1) -> Path:
    """Compile one staged XeLaTeX source repeatedly and return its completed PDF."""
    if passes < 1:
        raise AssertionError("XeLaTeX compilation requires at least one pass.")
    compiler = shutil.which("xelatex")
    if compiler is None:
        raise InputError("XeLaTeX is required to render descriptive report PDFs.")
    pdf = output_dir / f"{source.stem}.pdf"
    for _ in range(passes):
        result = subprocess.run(
            [compiler, "-interaction=nonstopmode", "-halt-on-error", "-output-directory", str(output_dir), str(source)],
            cwd=source.parent, capture_output=True, text=True, check=False,
        )
        if result.returncode != 0 or not pdf.is_file():
            details = (result.stderr or result.stdout).strip()
            raise InputError(f"XeLaTeX failed for {source.name}: {details or 'no PDF was produced'}")
    return pdf


def _require_new_or_empty_chart_dir(chart_dir: Path, overwrite: bool = False) -> None:
    """Reject unsafe chart output paths and directories with existing artifacts."""
    if chart_dir.is_symlink():
        raise InputError(f"Chart directory must not be a symbolic link: {chart_dir}")
    if chart_dir.exists() and (not chart_dir.is_dir() or (not overwrite and any(chart_dir.iterdir()))):
        raise InputError(f"Chart directory must be new or empty: {chart_dir}")


def _write_compilation_source(path: Path, content: str, description: str) -> None:
    """Write a temporary TeX source through the user-facing input error boundary."""
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise InputError(f"Could not write {description} {path.name}: {exc}") from exc


def _stage_publication_file(
    target: Path, *, text: str | None = None, source: Path | None = None,
) -> Path:
    """Create a complete hidden staging file on the target filesystem."""
    if (text is None) == (source is None):
        raise AssertionError("Exactly one publication source must be provided.")
    descriptor, stage_name = tempfile.mkstemp(
        prefix=f".{target.name}.so2-stage-", dir=target.parent,
    )
    os.close(descriptor)
    stage = Path(stage_name)
    try:
        if text is not None:
            stage.write_text(text, encoding="utf-8")
        else:
            shutil.copy2(source, stage)
    except OSError:
        stage.unlink(missing_ok=True)
        raise
    return stage


def _discard_publication_stages(stages: Sequence[Path]) -> None:
    """Remove target-filesystem staging files that were not promoted."""
    for stage in stages:
        stage.unlink(missing_ok=True)


def render_descriptive_pdf(
    rendered: RenderedDescriptiveReport,
    tex_path: str | Path,
    pdf_path: str | Path | None,
    chart_dir: str | Path | None,
    overwrite: bool = False,
) -> None:
    """Compile and transactionally publish a descriptive report and charts.

    Args:
        rendered: Self-contained TeX and standalone chart documents.
        tex_path: Target for the published report source.
        pdf_path: Optional target for the compiled report PDF.
        chart_dir: Optional output directory for standalone chart PDFs.
        overwrite: Whether existing outputs may be replaced after successful staging.

    Returns:
        None.

    Raises:
        InputError: If targets are unsafe, staging or compilation fails, or
            publication cannot complete without partial output.
    """
    target_tex = Path(tex_path)
    target_pdf = Path(pdf_path) if pdf_path is not None else None
    target_charts = Path(chart_dir) if chart_dir is not None else None
    if target_charts is not None:
        _require_new_or_empty_chart_dir(target_charts, overwrite)
    targets = [target_tex, *(path for path in (target_pdf, target_charts) if path is not None)]
    if any(not target.parent.exists() for target in targets):
        raise InputError("Output parent directory does not exist.")
    with tempfile.TemporaryDirectory(prefix="so2-report-") as report_temporary, \
            tempfile.TemporaryDirectory(prefix="so2-charts-") as chart_temporary:
        report_stage = Path(report_temporary)
        chart_stage = Path(chart_temporary)

        chart_pdfs: dict[str, Path] = {}
        if target_charts is not None:
            for key, document in rendered.chart_documents.items():
                source = chart_stage / f"{key}.tex"
                _write_compilation_source(source, document, "chart source")
                chart_pdfs[key] = _run_xelatex(source, chart_stage)

        report_pdf = None
        if target_pdf is not None:
            report_source = report_stage / "report.tex"
            _write_compilation_source(report_source, rendered.tex, "report source")
            report_pdf = _run_xelatex(report_source, report_stage, passes=2)
        publication_stages: list[Path] = []
        try:
            staged_tex = _stage_publication_file(target_tex, text=rendered.tex)
            publication_stages.append(staged_tex)
            staged_pdf = None
            if target_pdf is not None and report_pdf is not None:
                staged_pdf = _stage_publication_file(target_pdf, source=report_pdf)
                publication_stages.append(staged_pdf)
        except OSError as exc:
            _discard_publication_stages(publication_stages)
            raise InputError(f"Could not stage descriptive report outputs: {exc}") from exc

        publish_charts = None
        if target_charts is not None:
            _require_new_or_empty_chart_dir(target_charts, overwrite)
            publish_charts = Path(tempfile.mkdtemp(prefix=".so2-charts-", dir=target_charts.parent))
            try:
                for key, source_pdf in chart_pdfs.items():
                    shutil.copy2(source_pdf, publish_charts / f"{key}.pdf")
            except OSError as exc:
                shutil.rmtree(publish_charts, ignore_errors=True)
                _discard_publication_stages(publication_stages)
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

        def replace_directory(source: Path, target: Path) -> None:
            """Publish a staged directory while retaining its prior directory for rollback."""
            if target.exists():
                backup = Path(tempfile.mkdtemp(prefix=".so2-charts-backup-", dir=target.parent))
                backup.rmdir()
                os.replace(target, backup)
                backups[target] = backup
            os.replace(source, target)
            published.append(target)

        try:
            replace_file(staged_tex, target_tex)
            if target_pdf is not None and staged_pdf is not None:
                replace_file(staged_pdf, target_pdf)
            if target_charts is not None and publish_charts is not None:
                replace_directory(publish_charts, target_charts)
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
            _discard_publication_stages(publication_stages)
            if rollback_failures:
                details = "; ".join(str(rollback_exc) for rollback_exc in rollback_failures)
                raise InputError(
                    "Could not publish descriptive report outputs: "
                    f"{exc}; rollback could not establish a clean state: {details}"
                ) from exc
            raise InputError(f"Could not publish descriptive report outputs: {exc}") from exc
        _discard_publication_stages(publication_stages)
        for backup in backups.values():
            if backup.is_dir():
                shutil.rmtree(backup)
            else:
                backup.unlink(missing_ok=True)
