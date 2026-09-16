"""Read and validate SO2 descriptive-survey workbooks without external services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping, Sequence
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
