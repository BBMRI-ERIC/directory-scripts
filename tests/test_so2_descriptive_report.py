"""Tests for the self-contained SO2 descriptive-workbook reader."""

from copy import deepcopy
import importlib
from datetime import datetime
import inspect
from pathlib import Path
import shutil

import openpyxl
import pandas as pd
import pytest


module = importlib.import_module("so2_descriptive_report")
WORKTREE = Path(__file__).resolve().parents[1]
PRODUCTION_SCHEMA = WORKTREE / "survey-mappings" / "so2_2025_descriptive_report.json"
PRODUCTION_WORKBOOK = Path("/storage/emulated/0/BBMRI-ERIC/directory-scripts/Content_Export_SO2_2025_20260313.xlsx")
LEGAL_GDPR = "What types of legal barriers have you faced?: Data protection regulations (e.g., GDPR)"
LEGAL_LICENSING = "What types of legal barriers have you faced?: Licensing restrictions"
LEGAL_OWNERSHIP = "What types of legal barriers have you faced?: Lack of clarity on data ownership"
LEGAL_CROSS_BORDER = "What types of legal barriers have you faced?: Cross-border data sharing restrictions"
OTHER_LEGAL = "If there are other legal barriers, please specify:"
OTHER_ORGANISATIONAL = "If there are other organisational barriers, please specify:"
RETURNED_DATA_STORAGE = "How much disk space do you currently require storing returned data overall (for all returned data altogether)?"
ORDINAL_BARRIER_CATEGORIES = ["never", "rarely", "occasionally", "frequently"]
TRACEABILITY_READINESS = (
    "How would you rate your repository’s technical readiness for integrating full digital "
    "traceability? Please choose what corresponds the most to your current situation. By “digital "
    "traceability,” we mean the structured, automated, and system-supported capture and linkage of "
    "associated data (e.g. preanalytical, clinical, research-derived), enabling traceability of a "
    "sample across its full lifecycle, from collection through processing, storage, use, and data "
    "generation. This includes the use of dedicated software (e.g. BIMS/LIMS), digital metadata "
    "standards, audit trails, and secure linkage to clinical data or research data."
)


HEADERS = [
    "Name of Institution",
    "Country",
    "Creation date",
    "Last update",
    "Digital maturity",
]


def minimal_schema():
    """Return a complete schema for the controlled workbook fixture."""
    return {
        "schema_version": "1",
        "input": {
            "worksheet": "Survey responses",
            "alias": "SO2_2025",
            "header_row": 4,
        },
        "columns": {
            "respondent_context": ["Name of Institution", "Country"],
            "institution_column": "Name of Institution",
            "country_column": "Country",
            "administrative_exclusions": ["Creation date", "Last update"],
            "administrative_exclusion_reasons": {
                "Creation date": "Administrative export metadata.",
                "Last update": "Administrative export metadata.",
            },
        },
        "questions": [
            {
                "question_id": "digital_maturity",
                "column": "Digital maturity",
                "question_type": "ordinal",
                "label": "Digital maturity",
                "categories": ["Low", "High"],
            }
        ],
        "output": {"source_row_column": "source_row"},
    }


def write_descriptive_workbook(tmp_path, rows=(), mutator=None):
    """Write a workbook matching the survey service envelope."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Survey responses"
    sheet.cell(1, 1, "Alias")
    sheet.cell(1, 2, "SO2_2025")
    sheet.cell(2, 1, "Export Date")
    sheet.cell(2, 2, datetime(2026, 3, 13, 7, 22, 45))
    for column_number, header in enumerate(HEADERS, start=1):
        sheet.cell(4, column_number, header)
    for row_number, row in enumerate(rows, start=5):
        for column_number, header in enumerate(HEADERS, start=1):
            sheet.cell(row_number, column_number, row.get(header))
    if mutator is not None:
        mutator(sheet)
    path = tmp_path / "descriptive.xlsx"
    workbook.save(path)
    return path


def descriptive_workbook(rows, source_rows=None):
    """Build a validated in-memory survey workbook for payload behavior tests."""
    source_rows = source_rows or range(5, 5 + len(rows))
    return module.SurveyWorkbook(
        source_path="controlled.xlsx",
        source_sha256="a" * 64,
        worksheet="Survey responses",
        alias="SO2_2025",
        export_date="2026-03-13T07:22:45",
        header_row=4,
        responses=pd.DataFrame(
            [{**row, "source_row": source_row} for row, source_row in zip(rows, source_rows, strict=True)]
        ),
        total_data_rows=len(rows),
        excluded_blank_rows=0,
    )


def descriptive_schema(question):
    """Build the schema required for a controlled descriptive question."""
    return {
        "schema_version": "1",
        "input": {"worksheet": "Survey responses", "alias": "SO2_2025", "header_row": 4},
        "columns": {
            "respondent_context": ["Name of Institution", "Country"],
            "institution_column": "Name of Institution",
            "country_column": "Country",
            "administrative_exclusions": [],
            "administrative_exclusion_reasons": {},
        },
        "questions": [
            *[
                {
                    "question_id": f"parent_{index}", "column": column,
                    "question_type": "ordinal", "label": column,
                    "categories": list(dict.fromkeys([
                        "frequently",
                        *(
                            question.get("applicability", {}).get("values", [])
                            if question.get("applicability", {}).get("column") == column
                            else []
                        ),
                    ])),
                }
                for index, column in enumerate(question.get("parent_columns", []))
            ],
            question,
        ],
        "output": {"source_row_column": "source_row"},
    }


def payload_question(workbook, schema):
    """Return the one question in a controlled descriptive payload."""
    return next(
        item for item in module.build_descriptive_payload(workbook, schema)["questions"]
        if item["question_id"] == schema["questions"][-1]["question_id"]
    )


def test_multi_choice_has_answered_selection_percentages_and_all_row_missing_percent():
    """Selections use answered rows while Missing always uses every response row."""
    question = {
        "question_id": "systems",
        "column": "Systems",
        "question_type": "multi_choice",
        "label": "Systems",
        "categories": ["LIMS", "PACS"],
        "delimiter": ";",
    }
    workbook = descriptive_workbook([
        {"Name of Institution": "Alpha", "Country": "Austria", "Systems": "LIMS;PACS"},
        {"Name of Institution": "Beta", "Country": "Belgium", "Systems": "PACS"},
        {"Name of Institution": "Gamma", "Country": "Czech Republic", "Systems": ""},
    ])

    result = payload_question(workbook, descriptive_schema(question))

    assert result["population"] == {"N": 3, "A": 2, "M": 1, "blank_rows": 1}
    assert result["categories"] == [
        {"value": "LIMS", "count": 1, "percent_base": 2, "percent": 50.0},
        {"value": "PACS", "count": 2, "percent_base": 2, "percent": 100.0},
        {"value": "Missing", "count": 1, "percent_base": 3, "percent": pytest.approx(33.3333)},
    ]


def test_literal_duplicate_contributions_are_preserved_and_marked():
    """Repeated normalized respondents retain both literal source contributions."""
    question = {
        "question_id": "answer",
        "column": "Answer",
        "question_type": "single_choice",
        "label": "Answer",
        "categories": ["Yes", "No"],
    }
    workbook = descriptive_workbook([
        {"Name of Institution": " Alpha ", "Country": "Austria", "Answer": "Yes"},
        {"Name of Institution": "alpha", "Country": "austria", "Answer": "Yes"},
    ], source_rows=[5, 6])

    contributions = payload_question(workbook, descriptive_schema(question))["contributions"]

    assert [(row["source_row"], row["repeated_response"]) for row in contributions] == [
        (5, True), (6, True)
    ]
    assert contributions[0]["institution"] == " Alpha "


def test_free_text_preserves_missing_parent_and_parent_group():
    """Narrative rows preserve literal text and normalized missing parent values."""
    question = {
        "question_id": "other_barrier",
        "column": "Other barrier",
        "question_type": "free_text",
        "label": "Other barrier",
        "categories": [],
        "parent_columns": ["Barrier A", "Barrier B"],
    }
    workbook = descriptive_workbook([
        {
            "Name of Institution": "Alpha",
            "Country": "Austria",
            "Barrier A": "frequently",
            "Barrier B": "",
            "Other barrier": "Need legal support",
        }
    ])

    row = payload_question(workbook, descriptive_schema(question))["free_text_rows"][0]

    assert row["parent_answers"] == [
        {"column": "Barrier A", "value": "frequently"},
        {"column": "Barrier B", "value": "Missing"},
    ]
    assert row["text"] == "Need legal support"


def test_blank_conditional_answer_stays_blank_when_applicability_is_unknown():
    """A blank answer is not inferred as inapplicable without explicit routing metadata."""
    question = {
        "question_id": "conditional",
        "column": "Conditional",
        "question_type": "single_choice",
        "label": "Conditional",
        "categories": ["Yes", "No"],
    }
    workbook = descriptive_workbook([
        {"Name of Institution": "Alpha", "Country": "Austria", "Conditional": ""}
    ])

    result = payload_question(workbook, descriptive_schema(question))

    assert result["applicability"] == {"status": "unknown"}
    assert result["population"]["blank_rows"] == 1


def test_multi_choice_preserves_unexpected_literals_and_sorts_all_contributions():
    """Multi-select evidence remains literal, deduplicated, diagnosed, and ordered."""
    question = {
        "question_id": "systems",
        "column": "Systems",
        "question_type": "multi_choice",
        "label": "Systems",
        "categories": ["LIMS", "PACS"],
        "delimiter": ";",
    }
    workbook = descriptive_workbook(
        [
            {"Name of Institution": "Zeta", "Country": "Sweden", "Systems": "PACS;LIMS;PACS;Odd"},
            {"Name of Institution": "Beta", "Country": "Austria", "Systems": "Odd"},
            {"Name of Institution": "Alpha", "Country": "Belgium", "Systems": ""},
            {"Name of Institution": "Alpha", "Country": "Austria", "Systems": "LIMS"},
        ],
        source_rows=[8, 5, 6, 7],
    )

    result = payload_question(workbook, descriptive_schema(question))

    assert result["population"] == {"N": 4, "A": 3, "M": 1, "blank_rows": 1}
    assert result["categories"] == [
        {"value": "LIMS", "count": 2, "percent_base": 3, "percent": pytest.approx(66.6667)},
        {"value": "PACS", "count": 1, "percent_base": 3, "percent": pytest.approx(33.3333)},
        {"value": "Odd", "count": 2, "percent_base": 3, "percent": pytest.approx(66.6667)},
        {"value": "Missing", "count": 1, "percent_base": 4, "percent": 25.0},
    ]
    assert [row["value"] for row in result["contributions"]] == [
        "LIMS", "LIMS", "PACS", "Odd", "Odd", "Missing"
    ]
    assert [row["source_row"] for row in result["contributions"]] == [7, 8, 8, 5, 8, 6]
    assert result["diagnostics"] == {
        "duplicate_selections": [{"source_row": 8, "values": ["PACS"]}],
        "unexpected_selections": [
            {"source_row": 5, "values": ["Odd"]},
            {"source_row": 8, "values": ["Odd"]},
        ],
        "contradictory_selections": [],
    }
    assert result["pie_categories"][-1]["excluded_from_chart"] is True


def test_declared_applicability_separates_skips_unanswered_and_out_of_route_answers():
    """Declared routing exposes row states without discarding any submitted answer."""
    question = {
        "question_id": "conditional",
        "column": "Conditional",
        "question_type": "single_choice",
        "label": "Conditional",
        "categories": ["Yes", "No"],
        "parent_columns": ["Gate"],
        "applicability": {"column": "Gate", "values": ["Yes"]},
    }
    workbook = descriptive_workbook(
        [
            {"Name of Institution": "Alpha", "Country": "Austria", "Gate": "Yes", "Conditional": ""},
            {"Name of Institution": "Beta", "Country": "Belgium", "Gate": "No", "Conditional": ""},
            {"Name of Institution": "Gamma", "Country": "Czech Republic", "Gate": "No", "Conditional": "No"},
            {"Name of Institution": "Delta", "Country": "Denmark", "Gate": "Yes", "Conditional": "Yes"},
        ]
    )

    result = payload_question(workbook, descriptive_schema(question))

    assert result["applicability"] == {
        "status": "evaluated",
        "column": "Gate",
        "values": ["Yes"],
        "applicable_rows": 2,
        "inapplicable_rows": 2,
        "eligible_unanswered_rows": 1,
        "structurally_skipped_rows": 1,
        "eligibility_unknown_rows": 0,
        "out_of_route_answered_rows": 1,
    }
    assert result["population"] == {"N": 4, "A": 2, "M": 2, "blank_rows": 2}
    assert [(row["value"], row["source_row"]) for row in result["contributions"]] == [
        ("Yes", 8), ("No", 7), ("Missing", 5), ("Missing", 6)
    ]


def test_blank_declared_applicability_value_is_unknown_not_inapplicable():
    """Blank routing metadata is reported as unknown rather than a structural skip."""
    question = {
        "question_id": "conditional",
        "column": "Conditional",
        "question_type": "single_choice",
        "label": "Conditional",
        "categories": ["Yes", "No"],
        "parent_columns": ["Gate"],
        "applicability": {"column": "Gate", "values": ["Yes"]},
    }
    workbook = descriptive_workbook([
        {"Name of Institution": "Alpha", "Country": "Austria", "Gate": "  ", "Conditional": ""}
    ])

    result = payload_question(workbook, descriptive_schema(question))

    assert result["applicability"] == {
        "status": "evaluated",
        "column": "Gate",
        "values": ["Yes"],
        "applicable_rows": 0,
        "inapplicable_rows": 0,
        "eligible_unanswered_rows": 0,
        "structurally_skipped_rows": 0,
        "eligibility_unknown_rows": 1,
        "out_of_route_answered_rows": 0,
    }


def test_applicability_matches_a_selection_inside_multi_choice_parent():
    """A routing value may be one selection in a delimiter-separated parent answer."""
    question = {
        "question_id": "q_020_exchange",
        "column": "Exchange",
        "question_type": "multi_choice",
        "label": "Exchange",
        "categories": ["No", "Yes"],
        "delimiter": ";",
        "parent_columns": ["Standards"],
        "applicability": {"column": "Standards", "values": ["HL7 FHIR"]},
    }
    workbook = descriptive_workbook([{
        "Name of Institution": "Alpha",
        "Country": "Austria",
        "Standards": "MIABIS;HL7 FHIR",
        "Exchange": "Yes",
    }])
    schema = descriptive_schema(question)
    schema["questions"][0].update({
        "question_type": "multi_choice",
        "categories": ["MIABIS", "HL7 FHIR"],
        "delimiter": ";",
    })

    result = payload_question(workbook, schema)

    assert result["applicability"]["applicable_rows"] == 1
    assert result["applicability"]["inapplicable_rows"] == 0
    assert result["applicability"]["out_of_route_answered_rows"] == 0


def test_schema_rejects_invalid_applicability_references_and_values():
    """Routing rules must reference declared questions and canonical parent values."""
    question = {
        "question_id": "conditional",
        "column": "Conditional",
        "question_type": "single_choice",
        "label": "Conditional",
        "categories": ["Yes", "No"],
        "parent_columns": ["Gate"],
        "applicability": {"column": "Missing gate", "values": ["Yes"]},
    }
    schema = descriptive_schema(question)
    columns = ["Name of Institution", "Country", "Gate", "Conditional"]

    with pytest.raises(module.InputError, match="applicability column.*declared question"):
        module.validate_descriptive_schema(schema, columns)

    question["applicability"] = {"column": "Gate", "values": ["Maybe"]}
    schema = descriptive_schema(question)
    schema["questions"][0]["categories"] = ["Yes", "No"]

    with pytest.raises(module.InputError, match="applicability value.*Maybe.*Gate"):
        module.validate_descriptive_schema(schema, columns)


def test_multi_choice_exclusive_category_combination_is_diagnosed():
    """Mutually exclusive selections remain counted and are traceable as contradictions."""
    question = {
        "question_id": "q_020_exchange",
        "column": "Exchange",
        "question_type": "multi_choice",
        "label": "Exchange",
        "categories": ["No", "Yes - national", "Yes - international"],
        "delimiter": ";",
        "exclusive_categories": ["No"],
    }
    workbook = descriptive_workbook([
        {
            "Name of Institution": "Alpha",
            "Country": "Austria",
            "Exchange": "No;Yes - national",
        }
    ])

    result = payload_question(workbook, descriptive_schema(question))

    assert result["diagnostics"]["contradictory_selections"] == [{
        "source_row": 5,
        "exclusive_values": ["No"],
        "values": ["No", "Yes - national"],
    }]
    assert [(item["value"], item["count"]) for item in result["categories"]] == [
        ("No", 1), ("Yes - national", 1), ("Yes - international", 0), ("Missing", 0)
    ]


def test_schema_rejects_invalid_exclusive_categories():
    """Only multi-choice questions may declare canonical mutually exclusive values."""
    question = {
        "question_id": "q_020_exchange",
        "column": "Exchange",
        "question_type": "multi_choice",
        "label": "Exchange",
        "categories": ["No", "Yes"],
        "delimiter": ";",
        "exclusive_categories": ["Unknown"],
    }
    schema = descriptive_schema(question)

    with pytest.raises(module.InputError, match="exclusive categor.*Unknown"):
        module.validate_descriptive_schema(
            schema, ["Name of Institution", "Country", "Exchange"]
        )


def test_payload_records_schema_provenance_and_free_text_parent_inconsistencies():
    """Payload provenance and narrative diagnostics make later rendering self-contained."""
    question = {
        "question_id": "other_barrier",
        "column": "Other barrier",
        "question_type": "free_text",
        "label": "Other barrier",
        "categories": [],
        "parent_columns": ["Barrier A"],
    }
    workbook = descriptive_workbook(
        [
            {"Name of Institution": "Alpha", "Country": "Austria", "Barrier A": "unexpected", "Other barrier": "Text A"},
            {"Name of Institution": "Beta", "Country": "Belgium", "Barrier A": "", "Other barrier": "Text B"},
        ]
    )
    schema = descriptive_schema(question)

    payload = module.build_descriptive_payload(workbook, schema)
    result = payload_question(workbook, schema)

    assert payload["payload_type"] == "so2_descriptive_statistics"
    assert payload["payload_version"] == "1"
    assert payload["provenance"] == {
        "source_path": "controlled.xlsx",
        "source_sha256": "a" * 64,
        "worksheet": "Survey responses",
        "alias": "SO2_2025",
        "export_date": "2026-03-13T07:22:45",
        "header_row": 4,
        "total_data_rows": 2,
        "excluded_blank_rows": 0,
        "included_response_rows": 2,
        "schema_version": "1",
    }
    assert result["diagnostics"] == {
        "duplicate_selections": [],
        "unexpected_selections": [],
        "contradictory_selections": [],
        "missing_parent_answers": [{"source_row": 6, "columns": ["Barrier A"]}],
        "unexpected_parent_answers": [{
            "source_row": 5,
            "values": [{"column": "Barrier A", "value": "unexpected"}],
        }],
    }


def test_free_text_parent_diagnostics_parse_multi_choice_parent_answers():
    """A declared multi-choice parent accepts its delimiter-separated selections."""
    question = {
        "question_id": "other_system",
        "column": "Other system",
        "question_type": "free_text",
        "label": "Other system",
        "categories": [],
        "parent_columns": ["Systems"],
    }
    workbook = descriptive_workbook([
        {
            "Name of Institution": "Alpha",
            "Country": "Austria",
            "Systems": "A;B",
            "Other system": "Custom system",
        }
    ])
    schema = descriptive_schema(question)
    schema["questions"][0].update({
        "question_type": "multi_choice",
        "categories": ["A", "B"],
        "delimiter": ";",
    })

    result = payload_question(workbook, schema)

    assert result["diagnostics"]["unexpected_parent_answers"] == []


def wrong_alias_row(sheet):
    """Break the row-1 alias envelope field."""
    sheet.cell(1, 1, "Wrong label")


def missing_export_date(sheet):
    """Break the row-2 export-date envelope field."""
    sheet.cell(2, 2).value = None


def invalid_export_date(sheet):
    """Break the datetime row-2 export-date envelope field."""
    sheet.cell(2, 2, "not-a-date")


def nonblank_separator(sheet):
    """Break the required blank separator row."""
    sheet.cell(3, 1, "not blank")


def wrong_header(sheet):
    """Break the first cell of the row-4 header row."""
    sheet.cell(4, 1, "Institution")


def test_reader_preserves_service_metadata_and_only_response_rows(tmp_path):
    """Reader preserves service provenance and excludes blank data records."""
    workbook = write_descriptive_workbook(
        tmp_path,
        rows=[
            {"Name of Institution": "Alpha", "Country": "Austria"},
            {"Creation date": "2026-01-01", "Last update": "2026-01-02"},
            {},
        ],
    )

    result = module.read_descriptive_workbook(workbook, minimal_schema())

    assert result.alias == "SO2_2025"
    assert result.export_date == "2026-03-13T07:22:45"
    assert result.header_row == 4
    assert result.worksheet == "Survey responses"
    assert result.responses["Name of Institution"].tolist() == ["Alpha"]
    assert result.responses["source_row"].tolist() == [5]
    assert result.total_data_rows == 3
    assert result.excluded_blank_rows == 2
    assert len(result.source_sha256) == 64



@pytest.mark.skipif(
    not PRODUCTION_WORKBOOK.exists(),
    reason=f"Production SO2 workbook is unavailable at {PRODUCTION_WORKBOOK}",
)
def test_reader_reads_actual_production_workbook_envelope():
    """Reader accepts the service's labeled production envelope without Directory access."""
    result = module.read_descriptive_workbook(
        PRODUCTION_WORKBOOK, module.load_descriptive_schema(PRODUCTION_SCHEMA)
    )

    assert result.alias == "SO2_2025"
    assert result.export_date == "2026-03-13T07:22:45"
    assert result.header_row == 4
    assert result.worksheet == "Content"
@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (wrong_alias_row, "row 1"),
        (missing_export_date, "row 2"),
        (invalid_export_date, "row 2"),
        (nonblank_separator, "row 3"),
        (wrong_header, "header row 4"),
    ],
)
def test_reader_rejects_invalid_service_envelope(tmp_path, mutator, message):
    """Reader rejects each service-envelope row when it is malformed."""
    with pytest.raises(module.InputError, match=message):
        module.read_descriptive_workbook(
            write_descriptive_workbook(tmp_path, mutator=mutator), minimal_schema()
        )


def test_reader_converts_corrupt_xlsx_to_input_error(tmp_path):
    """Reader reports a non-ZIP XLSX file as a user-facing input error."""
    workbook = tmp_path / "corrupt.xlsx"
    workbook.write_bytes(b"not a ZIP workbook")

    with pytest.raises(module.InputError, match="Could not open descriptive workbook"):
        module.read_descriptive_workbook(workbook, minimal_schema())


def test_reader_rejects_missing_schema_fields(tmp_path):
    """Reader reports incomplete schemas as actionable input errors."""
    schema = minimal_schema()
    del schema["input"]

    with pytest.raises(module.InputError, match="input"):
        module.read_descriptive_workbook(write_descriptive_workbook(tmp_path), schema)


def test_schema_rejects_missing_or_unclassified_columns():
    """Schema cannot omit a source column or declare one that is absent."""
    with pytest.raises(module.InputError, match="unclassified source column"):
        module.validate_descriptive_schema(
            minimal_schema(), HEADERS + ["Extra"]
        )
    with pytest.raises(module.InputError, match="declared column is absent"):
        module.validate_descriptive_schema(
            minimal_schema(), ["Name of Institution", "Country"]
        )


def test_schema_rejects_duplicate_classification_and_invalid_question_values():
    """Schema requires one classification per column and valid question fields."""
    schema = minimal_schema()
    schema["columns"]["respondent_context"].append("Digital maturity")
    with pytest.raises(module.InputError, match="classified more than once"):
        module.validate_descriptive_schema(schema, HEADERS)

    schema = minimal_schema()
    schema["questions"][0]["question_type"] = "numeric"
    with pytest.raises(module.InputError, match="question_type"):
        module.validate_descriptive_schema(schema, HEADERS)



@pytest.mark.parametrize(
    "field",
    ["institution_column", "country_column", "administrative_exclusion_reasons"],
)
def test_schema_requires_shared_context_and_named_administrative_reasons(field):
    """Schema names report-wide context columns and every administrative exclusion reason."""
    schema = minimal_schema()
    del schema["columns"][field]

    with pytest.raises(module.InputError, match=field):
        module.validate_descriptive_schema(schema, HEADERS)

    schema = minimal_schema()
    del schema["columns"]["administrative_exclusion_reasons"]["Last update"]
    with pytest.raises(module.InputError, match="Last update"):
        module.validate_descriptive_schema(schema, HEADERS)


def test_schema_rejects_free_text_parent_that_is_not_a_question_column():
    """Free-text parents must resolve to declared question columns."""
    schema = minimal_schema()
    schema["questions"][0].update({
        "question_type": "free_text",
        "categories": [],
        "parent_columns": ["Name of Institution"],
    })

    with pytest.raises(module.InputError, match="free_text parent.*question column"):
        module.validate_descriptive_schema(schema, HEADERS)

def test_schema_rejects_absent_parent_column():
    """Question parent references must name an existing source column."""
    schema = minimal_schema()
    schema["questions"][0]["parent_columns"] = ["Missing parent"]

    with pytest.raises(module.InputError, match="declared column is absent"):
        module.validate_descriptive_schema(schema, HEADERS)


def test_load_schema_rejects_duplicate_json_keys_and_invalid_output(tmp_path):
    """Schema loading rejects ambiguous JSON and unusable output provenance."""
    duplicate_keys = tmp_path / "duplicate-keys.json"
    duplicate_keys.write_text('{"schema_version": "1", "schema_version": "1"}')
    with pytest.raises(module.InputError, match="duplicate JSON key"):
        module.load_descriptive_schema(duplicate_keys)

    schema = minimal_schema()
    schema["output"] = {"source_row_column": "Name of Institution"}
    with pytest.raises(module.InputError, match="output.source_row_column"):
        module.validate_descriptive_schema(schema, HEADERS)


def test_schema_returns_frozen_question_definitions():
    """Validated questions expose the stable immutable public data class."""
    questions = module.validate_descriptive_schema(minimal_schema(), HEADERS)

    assert questions[0] == module.QuestionDefinition(
        question_id="digital_maturity",
        column="Digital maturity",
        question_type="ordinal",
        label="Digital maturity",
        categories=("Low", "High"),
        delimiter=None,
        parent_columns=(),
        applicability=None,
    )
    with pytest.raises(AttributeError):
        questions[0].label = "Changed"


def test_nonblank_response_row_ignores_administrative_values():
    """Creation and update timestamps alone never create a response record."""
    pandas = pytest.importorskip("pandas")
    row = pandas.Series(
        {
            "Name of Institution": " ",
            "Country": None,
            "Creation date": "2026-01-01",
            "Last update": "2026-01-02",
            "Digital maturity": "\t",
        }
    )

    assert not module.is_nonblank_response_row(
        row, ["Name of Institution", "Country", "Digital maturity"]
    )


def read_row_four_headers(workbook_path):
    """Return the exact production workbook row-4 headers."""
    workbook = openpyxl.load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        return [cell.value for cell in workbook.active[4]]
    finally:
        workbook.close()


def questions_by_column(schema):
    """Index raw schema questions by their explicit source header."""
    return {question["column"]: question for question in schema["questions"]}


def test_production_schema_accounts_for_every_header():
    """The production registry classifies each current source header exactly once."""
    schema = module.load_descriptive_schema(PRODUCTION_SCHEMA)
    headers = read_row_four_headers(PRODUCTION_WORKBOOK)
    module.validate_descriptive_schema(schema, headers)
    classified = set(schema["columns"]["respondent_context"])
    classified |= set(schema["columns"]["administrative_exclusions"])
    classified |= {item["column"] for item in schema["questions"]}

    assert classified == set(headers)
    assert len(classified) == len(headers)


def test_production_schema_declares_verified_routing_and_exclusive_answers():
    """Production diagnostics are driven by explicit survey semantics."""
    schema = module.load_descriptive_schema(PRODUCTION_SCHEMA)
    questions = {question["question_id"]: question for question in schema["questions"]}

    assert questions[
        "q_020_if_you_support_hl7_fhir_does_your_repository_support_the_national_or_int"
    ]["applicability"] == {
        "column": questions[
            "q_018_does_the_staff_dedicated_or_not_managing_the_repository_have_experience_"
        ]["column"],
        "values": ["HL7 FHIR"],
    }
    expected_exclusive = {
        "q_100_do_you_store_returned_data_select_all_that_apply":
            {"We don’t store returned data."},
    }
    assert {
        question_id: set(questions[question_id]["exclusive_categories"])
        for question_id in expected_exclusive
    } == expected_exclusive


def test_production_schema_narrative_barrier_columns_are_free_text_with_parents():
    """Other-barrier narrative answers remain text while retaining their matrix context."""
    questions = questions_by_column(module.load_descriptive_schema(PRODUCTION_SCHEMA))

    assert questions[LEGAL_GDPR]["question_type"] == "ordinal"
    assert questions[OTHER_LEGAL]["question_type"] == "free_text"
    assert questions[OTHER_LEGAL]["categories"] == []
    assert questions[OTHER_LEGAL]["parent_columns"] == [
        LEGAL_GDPR,
        LEGAL_LICENSING,
        LEGAL_OWNERSHIP,
        LEGAL_CROSS_BORDER,
    ]
    assert questions[OTHER_ORGANISATIONAL]["question_type"] == "free_text"
    assert questions[OTHER_ORGANISATIONAL]["categories"] == []
    assert questions[OTHER_ORGANISATIONAL]["parent_columns"] == [
        "What organizational barriers have you encountered? (Select all that apply): "
        "Lack of data sharing agreements",
        "What organizational barriers have you encountered? (Select all that apply): "
        "Bureaucratic delays",
        "What organizational barriers have you encountered? (Select all that apply): "
        "Lack of contact points or unclear responsibilities",
        "What organizational barriers have you encountered? (Select all that apply): "
        "Institutional reluctance to share data",
    ]


def test_production_schema_preserves_declared_zero_count_ordinal_category_order():
    """Declared ordinal storage bands remain ordered even when no response selects some bands."""
    question = questions_by_column(module.load_descriptive_schema(PRODUCTION_SCHEMA))[RETURNED_DATA_STORAGE]

    assert question["question_type"] == "ordinal"
    assert question["categories"] == [
        "I don't know",
        "<1TB",
        "1TB-10TB",
        "10TB-100TB",
        "100TB-1PB",
        ">1PB",
    ]


def test_production_schema_semicolon_inside_declared_ordinal_is_not_split():
    """An ordinal label containing semicolons is not treated as a multi-choice answer."""
    question = questions_by_column(module.load_descriptive_schema(PRODUCTION_SCHEMA))[TRACEABILITY_READINESS]

    assert question["question_type"] == "ordinal"
    assert question.get("delimiter") is None


def test_production_schema_declares_every_observed_non_other_structured_value():
    """Ordinary structured responses have an explicit declared category."""
    schema = module.load_descriptive_schema(PRODUCTION_SCHEMA)
    questions = questions_by_column(schema)
    workbook = openpyxl.load_workbook(PRODUCTION_WORKBOOK, read_only=True, data_only=True)
    try:
        rows = workbook.active.iter_rows(min_row=4, values_only=True)
        headers = list(next(rows))
        observed = [set() for _ in headers]
        for row in rows:
            for index, value in enumerate(row):
                if value not in (None, ""):
                    observed[index].add(value)
    finally:
        workbook.close()
    for index, header in enumerate(headers):
        question = questions.get(header)
        if question is None or question["question_type"] == "free_text" or question.get("parent_columns"):
            continue
        values = observed[index]
        if question["question_type"] == "multi_choice":
            values = {choice for value in values for choice in value.split(question["delimiter"])}
        assert values <= set(question["categories"]), header


def report_payload(*questions):
    """Return a minimal accepted payload for renderer contract tests."""
    return {
        "payload_type": "so2_descriptive_statistics",
        "payload_version": "1",
        "provenance": {
            "source_path": "survey.xlsx",
            "alias": "SO2_2025",
            "export_date": "2026-03-13T07:22:45",
            "source_sha256": "a" * 64,
            "worksheet": "Survey responses",
            "header_row": 4,
            "total_data_rows": 5,
            "included_response_rows": 3,
            "excluded_blank_rows": 2,
            "schema_version": "2026-09-16",
        },
        "diagnostics": {"duplicate_respondent_groups": []},
        "questions": list(questions),
    }


def structured_report_question(**overrides):
    """Return a small structured question with intentionally different denominators."""
    question = {
        "question_id": "q_009_institution_type",
        "column": "Institution type",
        "label": "Institution type",
        "question_type": "multi_choice",
        "population": {"N": 3, "A": 2, "M": 1, "blank_rows": 1},
        "categories": [
            {"value": "LIMS", "count": 1, "percent_base": 2, "percent": 50.0},
            {"value": "PACS", "count": 2, "percent_base": 2, "percent": 100.0},
            {"value": "Missing", "count": 1, "percent_base": 3, "percent": 33.3333},
        ],
        "pie_categories": [
            {"value": "LIMS", "count": 1, "percent_base": 2, "percent": 50.0,
             "excluded_from_chart": False},
            {"value": "PACS", "count": 2, "percent_base": 2, "percent": 100.0,
             "excluded_from_chart": False},
            {"value": "Missing", "count": 1, "percent_base": 3, "percent": 33.3333,
             "excluded_from_chart": True},
        ],
        "contributions": [],
        "free_text_rows": [],
        "diagnostics": {"duplicate_selections": [], "unexpected_selections": []},
        "applicability": {"status": "unknown"},
    }
    question.update(overrides)
    return question


def multi_choice_payload():
    """Return the count-bar payload used by renderer tests."""
    return report_payload(structured_report_question())


def single_choice_payload_with_missing():
    """Return a schema-designated pie payload that has missing rows."""
    return report_payload(structured_report_question(
        question_id="q_011_hosting_organisation",
        column="Hosting organisation",
        label="Hosting organisation",
        question_type="single_choice",
        chart="pie",
    ))


def payload_with_repeated_and_free_text():
    """Return literal contribution and narrative rows for table rendering."""
    structured = structured_report_question(contributions=[{
        "value": "PACS", "country": "Austria", "institution": "Alpha",
        "source_row": 5, "repeated_response": True,
    }])
    narrative = {
        "question_id": "q_010_other_barrier",
        "column": "Other barrier",
        "label": "Other barrier",
        "question_type": "free_text",
        "population": {"N": 3, "A": 1, "M": 2, "blank_rows": 2},
        "categories": [], "pie_categories": [], "contributions": [],
        "free_text_rows": [{
            "country": "Austria", "institution": "Alpha", "source_row": 5,
            "text": "Need legal support",
            "parent_answers": [{"column": "Barrier A", "value": "frequently"}],
        }],
        "diagnostics": {
            "duplicate_selections": [], "unexpected_selections": [],
            "missing_parent_answers": [], "unexpected_parent_answers": [],
        },
        "applicability": {"status": "unknown"},
    }
    return report_payload(structured, narrative)


def rendered_payload():
    """Render one bar chart for filesystem publication tests."""
    return module.render_descriptive_tex(multi_choice_payload(), chart_dir="charts")


def test_multi_choice_tex_is_count_bars_with_missing_and_percentage_labels():
    """Multi-choice charts retain selection counts and separate missing-row bases."""
    tex = module.render_descriptive_tex(multi_choice_payload(), chart_dir="charts").tex

    assert r"\begin{axis}[xbar" in tex
    assert "2 (100.0\\% of answering rows)" in tex
    assert "1 (33.3\\% of all included rows)" in tex
    assert "charts/09-institution-type.pdf" in tex


def test_bar_tex_locks_every_bar_to_its_category_row_and_reserves_label_space():
    """Separate colour plots must not be shifted away from their y-axis labels."""
    fragment = module.render_descriptive_tex(multi_choice_payload(), chart_dir=None).chart_fragments[
        "09-institution-type"
    ]

    assert "bar shift=0pt" in fragment
    assert "scale only axis" in fragment
    assert "yticklabel style={text width=" in fragment
    assert "anchor=west,font=\\scriptsize" in fragment


def test_report_tex_is_self_contained_and_displays_required_semantics():
    """Published TeX embeds charts and exposes provenance and question denominators."""
    payload = multi_choice_payload()

    tex = module.render_descriptive_tex(payload, chart_dir=None).tex

    assert r"\input{fragments/" not in tex
    assert tex.count(r"\begin{axis}[xbar") == 1
    assert "Source path: survey.xlsx" in tex
    assert "Source SHA-256: " + ("a" * 64) in tex
    assert "Worksheet: Survey responses" in tex
    assert "Header row: 4" in tex
    assert "Total data rows: 5" in tex
    assert "Included response rows: 3" in tex
    assert "Excluded blank rows: 2" in tex
    assert "Descriptive schema version: 2026-09-16" in tex
    assert "N/A/M: 3 / 2 / 1" in tex
    assert "Applicability: unknown" in tex
    assert r"\usepackage{relsize}" in tex
    assert r"\tableofcontents" in tex
    assert "\n\\clearpage\n\\section{" in tex


def test_empty_free_text_question_is_explicitly_reported():
    """An unanswered narrative question is not rendered as an unexplained empty table."""
    narrative = payload_with_repeated_and_free_text()["questions"][1]
    narrative["population"] = {"N": 3, "A": 0, "M": 3, "blank_rows": 3}
    narrative["free_text_rows"] = []

    tex = module.render_descriptive_tex(report_payload(narrative), chart_dir=None).tex

    assert "No text responses" in tex


def test_pie_eligible_single_choice_with_missing_has_two_variants():
    """A schema-designated pie exposes both missing-inclusive and answered-only views."""
    rendered = module.render_descriptive_tex(single_choice_payload_with_missing(), chart_dir=None)

    assert "including Missing" in rendered.tex
    assert "answered rows only" in rendered.tex
    assert set(rendered.chart_fragments) == {
        "11-hosting-organisation", "11-hosting-organisation-answered-only"
    }


def test_standalone_chart_has_context_and_report_relative_payload_path(tmp_path):
    """Standalone charts retain interpretation context and payload paths are portable."""
    payload = multi_choice_payload()
    report_path = tmp_path / "publication" / "report.tex"
    chart_dir = tmp_path / "publication" / "charts"

    rendered = module.render_descriptive_tex(
        payload, chart_dir=chart_dir, report_path=report_path,
    )

    key = "09-institution-type"
    assert rendered.chart_paths[key] == "charts/09-institution-type.pdf"
    assert payload["questions"][0]["chart_paths"] == ["charts/09-institution-type.pdf"]
    assert payload["chart_paths"] == {key: "charts/09-institution-type.pdf"}
    standalone = rendered.chart_documents[key]
    assert r"q\_009\_institution\_type" in standalone
    assert "Institution type" in standalone
    assert "Denominator: 2 answering rows; Missing uses 3 included rows" in standalone
    assert "Unit: submitted response rows selecting each value" in standalone
    assert "Missing: 1 of 3 included rows" in standalone
    assert rendered.chart_fragments[key] in standalone


def test_missing_bar_is_distinct_and_ordinal_exceptions_are_separated():
    """Missing and ordinal exceptions cannot visually masquerade as scale levels."""
    ordinal = structured_report_question(
        question_id="q_012_frequency",
        label="Frequency",
        question_type="ordinal",
        categories=[
            {"value": "Never", "count": 1, "percent_base": 2, "percent": 50.0},
            {"value": "Often", "count": 1, "percent_base": 2, "percent": 50.0},
            {"value": "Not applicable", "count": 0, "percent_base": 2, "percent": 0.0},
            {"value": "I don't know", "count": 0, "percent_base": 2, "percent": 0.0},
            {"value": "Missing", "count": 1, "percent_base": 3, "percent": 33.3333},
        ],
    )

    fragment = module.render_descriptive_tex(report_payload(ordinal), None).chart_fragments[
        "12-frequency"
    ]

    assert "Ordered scale" in fragment
    assert "Exceptional categories" in fragment
    assert "fill=bbmriGray" in fragment
    assert fragment.index("Ordered scale") < fragment.index("Exceptional categories")
    assert fragment.index("Exceptional categories") < fragment.index("I don't know")


def test_chart_key_bounds_long_sanitized_question_labels():
    """Staged TeX fragment filenames remain below filesystem component limits."""
    question = {
        "question_id": "q_018_long_question",
        "label": "One " + ("very long descriptive question label " * 20),
    }

    chart_key = module._chart_key(question)

    assert chart_key.startswith("18-")
    assert len(f"{chart_key}.tex".encode("utf-8")) <= 120


def test_contribution_table_prints_literal_repeated_rows_and_parent_context():
    """Evidence tables keep repeat warnings, row provenance, and free-text parent answers."""
    tex = module.render_descriptive_tex(payload_with_repeated_and_free_text(), chart_dir=None, include_contribution_tables=True).tex

    assert "suspected repeated response" in tex
    assert "Source row" in tex
    assert "Barrier A = frequently" in tex


def test_structured_evidence_table_groups_institutions_and_uses_compact_type():
    """Structured evidence has one row per value/country with literal institution entries."""
def test_short_report_omits_structured_contribution_tables():
    """Short reports retain charts while omitting verbose structured evidence."""
    tex = module.render_descriptive_tex(multi_choice_payload(), chart_dir=None).tex

    assert "Value & Country & Institutions" not in tex

    question = structured_report_question(contributions=[
        {"value": "PACS", "country": "Austria", "institution": "Alpha", "source_row": 5,
         "repeated_response": True},
        {"value": "PACS", "country": "Austria", "institution": "Beta", "source_row": 6,
         "repeated_response": False},
    ])

    tex = module.render_descriptive_tex(report_payload(question), chart_dir=None, include_contribution_tables=True).tex

    assert r"\smaller[3]" in tex
    assert "Value & Country & Institutions" in tex
    assert r"{\raggedright Alpha [suspected repeated response]; Beta\par}" in tex
    assert "Source row" not in tex


def test_free_text_evidence_table_uses_less_aggressive_compact_type():
    """Narrative evidence remains row-level but has a readable compact table size."""
    narrative = payload_with_repeated_and_free_text()["questions"][1]

    tex = module.render_descriptive_tex(report_payload(narrative), chart_dir=None).tex

    assert r"\smaller[1]" in tex
    assert "Source row" in tex


def test_chart_dir_must_be_new_or_empty(tmp_path):
    """Renderer refuses to mix generated chart PDFs with pre-existing files."""
    target = tmp_path / "charts"
    target.mkdir()
    (target / "old.pdf").write_bytes(b"old")

    with pytest.raises(module.InputError, match="new or empty"):
        module.render_descriptive_pdf(rendered_payload(), tmp_path / "report.tex", None, target)


def test_tex_only_render_does_not_require_a_compiler_or_render_chart_pdfs(tmp_path, monkeypatch):
    """Publishing TeX alone leaves PDF and standalone-chart compilation to explicit requests."""
    monkeypatch.setattr(
        module,
        "_run_xelatex",
        lambda *_args, **_kwargs: pytest.fail("TeX-only rendering must not invoke XeLaTeX"),
    )
    rendered = rendered_payload()
    report_tex = tmp_path / "report.tex"

    module.render_descriptive_pdf(rendered, report_tex, None, None)

    assert report_tex.read_text(encoding="utf-8") == rendered.tex


def test_pdf_render_stages_and_publishes_only_completed_outputs(tmp_path, monkeypatch):
    """Successful staged compiler outputs are atomically published to requested targets."""
    def fake_xelatex(command, **_kwargs):
        output_dir = Path(command[command.index("-output-directory") + 1])
        source = Path(command[-1])
        (output_dir / f"{source.stem}.pdf").write_bytes(b"%PDF-1.4\nmock")
        return __import__("subprocess").CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(module.subprocess, "run", fake_xelatex)
    rendered = rendered_payload()
    report_tex = tmp_path / "report.tex"
    report_pdf = tmp_path / "report.pdf"
    chart_dir = tmp_path / "charts"

    module.render_descriptive_pdf(rendered, report_tex, report_pdf, chart_dir)

    assert report_tex.read_text(encoding="utf-8") == rendered.tex
    assert report_pdf.read_bytes().startswith(b"%PDF")
    assert (chart_dir / "09-institution-type.pdf").read_bytes().startswith(b"%PDF")


def test_pdf_publication_never_replaces_across_filesystems(tmp_path, monkeypatch):
    """Every promoted artifact is first staged beside its destination."""
    def fake_xelatex(command, **_kwargs):
        output_dir = Path(command[command.index("-output-directory") + 1])
        source = Path(command[-1])
        (output_dir / f"{source.stem}.pdf").write_bytes(b"%PDF-1.4\nmock")
        return __import__("subprocess").CompletedProcess(command, 0, "", "")

    real_replace = module.os.replace

    def reject_cross_device_replace(source, destination):
        source_path = Path(source)
        destination_path = Path(destination)
        if source_path.parent.resolve() != destination_path.parent.resolve():
            raise OSError(__import__("errno").EXDEV, "simulated cross-device replace")
        return real_replace(source, destination)

    monkeypatch.setattr(module.subprocess, "run", fake_xelatex)
    monkeypatch.setattr(module.os, "replace", reject_cross_device_replace)

    module.render_descriptive_pdf(
        rendered_payload(), tmp_path / "report.tex", tmp_path / "report.pdf", tmp_path / "charts",
    )

    assert (tmp_path / "report.tex").is_file()
    assert (tmp_path / "report.pdf").is_file()
    assert (tmp_path / "charts" / "09-institution-type.pdf").is_file()


def test_chart_staging_failure_removes_target_filesystem_stages(tmp_path, monkeypatch):
    """A chart-copy failure removes every hidden target-side staging artifact."""
    def fake_xelatex(command, **_kwargs):
        output_dir = Path(command[command.index("-output-directory") + 1])
        source = Path(command[-1])
        (output_dir / f"{source.stem}.pdf").write_bytes(b"%PDF-1.4\\nmock")
        return __import__("subprocess").CompletedProcess(command, 0, "", "")

    real_copy2 = module.shutil.copy2

    def fail_chart_stage_copy(source, destination):
        if Path(destination).parent.name.startswith(".so2-charts-"):
            raise OSError("simulated chart staging failure")
        return real_copy2(source, destination)

    monkeypatch.setattr(module.subprocess, "run", fake_xelatex)
    monkeypatch.setattr(module.shutil, "copy2", fail_chart_stage_copy)
    report_tex = tmp_path / "report.tex"
    chart_dir = tmp_path / "charts"

    with pytest.raises(module.InputError, match="stage chart PDFs"):
        module.render_descriptive_pdf(rendered_payload(), report_tex, None, chart_dir)

    assert not report_tex.exists()
    assert not chart_dir.exists()
    assert list(tmp_path.iterdir()) == []


def test_pdf_render_keeps_final_outputs_absent_when_report_compilation_fails(
    tmp_path, monkeypatch,
):
    """A report compiler failure leaves no report or chart publication behind."""
    compilation_dirs = []

    def fake_xelatex(command, **_kwargs):
        output_dir = Path(command[command.index("-output-directory") + 1])
        source = Path(command[-1])
        compilation_dirs.append(output_dir)
        if source.stem == "report":
            return __import__("subprocess").CompletedProcess(command, 1, "report failed", "")
        (output_dir / f"{source.stem}.pdf").write_bytes(b"%PDF-1.4\nmock")
        return __import__("subprocess").CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(module.subprocess, "run", fake_xelatex)
    report_tex = tmp_path / "report.tex"
    report_pdf = tmp_path / "report.pdf"
    chart_dir = tmp_path / "charts"

    with pytest.raises(module.InputError, match="report.tex"):
        module.render_descriptive_pdf(rendered_payload(), report_tex, report_pdf, chart_dir)

    assert not report_tex.exists()
    assert not report_pdf.exists()
    assert not chart_dir.exists()
    assert len(set(compilation_dirs)) == 2


def test_pdf_render_rolls_back_all_outputs_when_publication_fails(tmp_path, monkeypatch):
    """A publication error removes every final artifact already promoted."""
    def fake_xelatex(command, **_kwargs):
        output_dir = Path(command[command.index("-output-directory") + 1])
        source = Path(command[-1])
        (output_dir / f"{source.stem}.pdf").write_bytes(b"%PDF-1.4\nmock")
        return __import__("subprocess").CompletedProcess(command, 0, "", "")

    real_replace = module.os.replace

    fail_once = True

    def fail_report_pdf_publication(source, destination):
        nonlocal fail_once
        if Path(destination).name == "report.pdf" and fail_once:
            fail_once = False
            raise OSError("simulated publication failure")
        return real_replace(source, destination)

    monkeypatch.setattr(module.subprocess, "run", fake_xelatex)
    monkeypatch.setattr(module.os, "replace", fail_report_pdf_publication)
    report_tex = tmp_path / "report.tex"
    report_pdf = tmp_path / "report.pdf"
    chart_dir = tmp_path / "charts"

    with pytest.raises(module.InputError, match="publish"):
        module.render_descriptive_pdf(rendered_payload(), report_tex, report_pdf, chart_dir)

    assert not report_tex.exists()
    assert not report_pdf.exists()
    assert not chart_dir.exists()


def test_pdf_render_restores_existing_report_outputs_when_publication_fails(
    tmp_path, monkeypatch,
):
    """Rollback preserves report files that existed before publication began."""
    def fake_xelatex(command, **_kwargs):
        output_dir = Path(command[command.index("-output-directory") + 1])
        source = Path(command[-1])
        (output_dir / f"{source.stem}.pdf").write_bytes(b"%PDF-1.4\nmock")
        return __import__("subprocess").CompletedProcess(command, 0, "", "")

    real_replace = module.os.replace

    fail_once = True

    def fail_report_pdf_publication(source, destination):
        nonlocal fail_once
        if Path(destination).name == "report.pdf" and fail_once:
            fail_once = False
            raise OSError("simulated publication failure")
        return real_replace(source, destination)

    monkeypatch.setattr(module.subprocess, "run", fake_xelatex)
    monkeypatch.setattr(module.os, "replace", fail_report_pdf_publication)
    report_tex = tmp_path / "report.tex"
    report_pdf = tmp_path / "report.pdf"
    report_tex.write_text("previous report", encoding="utf-8")
    report_pdf.write_bytes(b"previous PDF")

    with pytest.raises(module.InputError, match="publish"):
        module.render_descriptive_pdf(rendered_payload(), report_tex, report_pdf, None)

    assert report_tex.read_text(encoding="utf-8") == "previous report"
    assert report_pdf.read_bytes() == b"previous PDF"


def test_pdf_render_reports_chart_publication_and_restoration_failures(
    tmp_path, monkeypatch,
):
    """A failed chart rollback keeps the publication failure visible and actionable."""
    def fake_xelatex(command, **_kwargs):
        output_dir = Path(command[command.index("-output-directory") + 1])
        source = Path(command[-1])
        (output_dir / f"{source.stem}.pdf").write_bytes(b"%PDF-1.4\nmock")
        return __import__("subprocess").CompletedProcess(command, 0, "", "")

    real_replace = module.os.replace
    real_mkdir = Path.mkdir

    def fail_chart_publication(source, destination):
        if Path(destination).name == "charts" and Path(source).name.startswith(".so2-charts-"):
            raise OSError("simulated chart publication failure")
        return real_replace(source, destination)

    def fail_chart_directory_restoration(path, *args, **kwargs):
        if path == chart_dir:
            raise OSError("simulated chart restoration failure")
        return real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", fake_xelatex)
    monkeypatch.setattr(module.os, "replace", fail_chart_publication)
    report_tex = tmp_path / "report.tex"
    chart_dir = tmp_path / "charts"
    chart_dir.mkdir()
    monkeypatch.setattr(Path, "mkdir", fail_chart_directory_restoration)

    with pytest.raises(
        module.InputError,
        match="simulated chart publication failure.*rollback could not establish a clean state.*simulated chart restoration failure",
    ):
        module.render_descriptive_pdf(rendered_payload(), report_tex, None, chart_dir)


def test_pdf_render_rejects_empty_symlink_chart_output_directory(tmp_path, monkeypatch):
    """An empty symlink must not redirect chart publication outside the requested path."""
    def fake_xelatex(command, **_kwargs):
        output_dir = Path(command[command.index("-output-directory") + 1])
        source = Path(command[-1])
        (output_dir / f"{source.stem}.pdf").write_bytes(b"%PDF-1.4\nmock")
        return __import__("subprocess").CompletedProcess(command, 0, "", "")

    charts_target = tmp_path / "actual-charts"
    charts_target.mkdir()
    chart_link = tmp_path / "charts"
    chart_link.symlink_to(charts_target, target_is_directory=True)
    monkeypatch.setattr(module.subprocess, "run", fake_xelatex)

    with pytest.raises(module.InputError, match="must not be a symbolic link"):
        module.render_descriptive_pdf(rendered_payload(), tmp_path / "report.tex", None, chart_link)


@pytest.mark.skipif(shutil.which("xelatex") is None, reason="XeLaTeX is not installed")
def test_real_xelatex_renders_minimal_descriptive_report(tmp_path):
    """A minimal real report compiles to a vector PDF when XeLaTeX is available."""
    rendered = module.render_descriptive_tex(multi_choice_payload(), chart_dir=None)

    module.render_descriptive_pdf(rendered, tmp_path / "report.tex", tmp_path / "report.pdf", None)

    assert (tmp_path / "report.pdf").read_bytes().startswith(b"%PDF")


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda payload: payload.pop("provenance"), "provenance"),
        (
            lambda payload: payload["questions"][0].update(
                {"population": {"N": 3, "A": "2", "M": 1}}
            ),
            "population",
        ),
        (
            lambda payload: payload["questions"][0].update(
                {"question_type": "invented"}
            ),
            "question_type",
        ),
        (
            lambda payload: payload["questions"][0].update(
                {"categories": [{"value": "LIMS", "count": -1}]}
            ),
            "categories",
        ),
        (
            lambda payload: payload["questions"][0].update(
                {"contributions": [{"value": "PACS"}]}
            ),
            "contributions",
        ),
        (
            lambda payload: payload["questions"][0]["pie_categories"][0].pop("count"),
            "pie_categories",
        ),
    ],
)
def test_renderer_rejects_malformed_nested_payload_as_input_error(mutate, message):
    """Malformed external payloads never escape as incidental Python exceptions."""
    payload = deepcopy(multi_choice_payload())
    mutate(payload)

    with pytest.raises(module.InputError, match=message):
        module.render_descriptive_tex(payload, chart_dir=None)


def test_public_descriptive_apis_document_contracts():
    """Public APIs state their inputs, results, and user-facing failure modes."""
    public_functions = [
        module.load_descriptive_schema,
        module.is_nonblank_response_row,
        module.validate_descriptive_schema,
        module.read_descriptive_workbook,
        module.build_descriptive_payload,
        module.render_descriptive_tex,
        module.render_descriptive_pdf,
    ]

    for function in public_functions:
        docstring = inspect.getdoc(function) or ""
        assert "Args:" in docstring, function.__name__
        assert "Returns:" in docstring, function.__name__
        if function is not module.is_nonblank_response_row:
            assert "Raises:" in docstring, function.__name__


def test_target_filesystem_staging_write_failure_is_input_error_without_output(
    tmp_path, monkeypatch,
):
    """A target-side write error is actionable and leaves no published file."""
    rendered = rendered_payload()
    report_tex = tmp_path / "report.tex"
    real_write_text = Path.write_text

    def fail_publication_stage(path, *args, **kwargs):
        if path.parent == tmp_path and ".so2-stage-" in path.name:
            raise OSError("simulated target write failure")
        return real_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_publication_stage)

    with pytest.raises(module.InputError, match="stage.*simulated target write failure"):
        module.render_descriptive_pdf(rendered, report_tex, None, None)

    assert not report_tex.exists()
    assert not list(tmp_path.glob(".*.so2-stage-*"))


def test_chart_source_write_failure_is_input_error_without_output(tmp_path, monkeypatch):
    """Temporary chart-source write failures use the public error boundary."""
    rendered = rendered_payload()
    report_tex = tmp_path / "report.tex"
    chart_dir = tmp_path / "charts"
    real_write_text = Path.write_text

    def fail_chart_source(path, *args, **kwargs):
        if path.parent.name.startswith("so2-charts-"):
            raise OSError("simulated chart source write failure")
        return real_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_chart_source)

    with pytest.raises(module.InputError, match="chart source.*simulated chart source write"):
        module.render_descriptive_pdf(rendered, report_tex, None, chart_dir)

    assert not report_tex.exists()
    assert not chart_dir.exists()
