"""Regression tests for conservative, evidence-preserving SO2 response merging."""

import pandas as pd
import pytest
from types import SimpleNamespace

import so2_descriptive_report as report


def test_merging_preserves_conflicts_sources_and_distinct_ids():
    """Verify one observation per trusted identity without losing raw evidence.

    Returns:
        None after checking merge counts, conflicts, and retained source records.
    """
    from so2_response_merging import merge_descriptive_responses

    question = report.QuestionDefinition("q", "Choice", "single_choice", "Choice", ("Yes", "No"), ";", (), None)
    multi = report.QuestionDefinition("m", "Multi", "multi_choice", "Multi", ("A", "B"), ";", (), None)
    text = report.QuestionDefinition("t", "Text", "free_text", "Text", (), ";", (), None)
    rows = pd.DataFrame([
        {"Institution": "Same", "Country": "Spain", "BiobankID in the Directory (if available)": "ES_A", "row": 5, "Choice": "Yes", "Multi": "A", "Text": "first"},
        {"Institution": "Same", "Country": "España", "BiobankID in the Directory (if available)": "bbmri-eric:ID:ES_A", "row": 6, "Choice": "No", "Multi": "B;A", "Text": "second"},
        {"Institution": "Same", "Country": "Spain", "BiobankID in the Directory (if available)": "ES_B", "row": 7, "Choice": "Yes", "Multi": "", "Text": ""},
    ])
    workbook = report.SurveyWorkbook("fixture.xlsx", "a" * 64, "Content", "SO2_2025", "date", 4, rows, 3, 0)
    schema = {"columns": {"institution_column": "Institution", "country_column": "Country"}, "output": {"source_row_column": "row"}}
    merged, summary = merge_descriptive_responses(workbook, schema, (question, multi, text), {"schema_version": 1, "reviewed_sources": {}, "country_overrides": {}})
    assert len(merged.responses) == 2
    assert summary["received_submissions"] == 3
    assert summary["merged_submissions"] == 1
    assert merged.responses.iloc[0]["Choice"] == "Conflicting answers"
    assert merged.responses.iloc[0]["Multi"] == "A;B"
    assert "first" in merged.responses.iloc[0]["Text"] and "second" in merged.responses.iloc[0]["Text"]
    assert summary["source_records"][1]["answers"]["Choice"] == "No"
    assert {item["question_id"] for item in summary["conflicts"]} == {"q", "m"}
    assert list(merged.responses["Country"]) == ["ES", "ES"]


def test_unidentified_institutions_are_not_name_merged():
    """Keep equal institution names separate when biobank identity is unknown.

    Returns:
        None after checking unresolved submission multiplicity.
    """
    from so2_response_merging import merge_descriptive_responses

    rows = pd.DataFrame([{"Institution": "Same", "Country": "", "row": 5}, {"Institution": "Same", "Country": "", "row": 6}])
    workbook = report.SurveyWorkbook("fixture", "a" * 64, "Content", "SO2", "date", 4, rows, 2, 0)
    schema = {"columns": {"institution_column": "Institution", "country_column": "Country"}, "output": {"source_row_column": "row"}}
    merged, summary = merge_descriptive_responses(workbook, schema, (), {"schema_version": 1, "reviewed_sources": {}, "country_overrides": {}})
    assert len(merged.responses) == 2
    assert summary["unresolved_identity_rows"] == [5, 6]


def test_country_codes_and_approved_aliases():
    """Recognize corrected codes without guessing an institution identity.

    Returns:
        None after checking reported-country normalization.
    """
    assert report._country_code("España") == "ES"
    assert report._country_code("SWISS") == "CH"
    assert report._country_code("SK") == "SK"


def test_merged_free_text_omits_placeholders_but_retains_raw_evidence():
    """Do not resurrect suppressed None text when another submission has content.

    Returns:
        None after checking readable text and unchanged source-answer evidence.
    """
    from so2_response_merging import merge_descriptive_responses

    question = report.QuestionDefinition("t", "Text", "free_text", "Text", (), ";", (), None)
    rows = pd.DataFrame([
        {"Institution": "Bank", "Country": "Spain", "BiobankID in the Directory (if available)": "ES_A", "row": 5, "Text": "None"},
        {"Institution": "Bank", "Country": "Spain", "BiobankID in the Directory (if available)": "ES_A", "row": 6, "Text": "Available technology"},
    ])
    workbook = report.SurveyWorkbook("fixture", "a" * 64, "Content", "SO2", "date", 4, rows, 2, 0)
    schema = {"columns": {"institution_column": "Institution", "country_column": "Country"}, "output": {"source_row_column": "row"}}
    merged, summary = merge_descriptive_responses(workbook, schema, (question,), {"schema_version": 1, "reviewed_sources": {}, "country_overrides": {}})
    assert merged.responses.iloc[0]["Text"] == "Available technology"
    assert summary["source_records"][0]["answers"]["Text"] == "None"
    assert summary["observation_sources"][0]["answer_sources"]["t"] == [5, 6]


def test_reviewed_local_id_and_blank_fill_are_hash_bound():
    """Apply reviewed local-ID correction only to the exact reviewed workbook.

    Returns:
        None after checking blanks, agreeing answers, country evidence and hash isolation.
    """
    from so2_response_merging import merge_descriptive_responses
    from dataclasses import replace

    question = report.QuestionDefinition("q", "Choice", "single_choice", "Choice", ("Yes", "No"), ";", (), None)
    rows = pd.DataFrame([
        {"Institution": "CHUV", "Country": "", "BiobankID in the Directory (if available)": "BB_038", "row": 5, "Choice": ""},
        {"Institution": "CHUV", "Country": "SWISS", "BiobankID in the Directory (if available)": "", "row": 6, "Choice": "Yes"},
    ])
    workbook = report.SurveyWorkbook("fixture", "a" * 64, "Content", "SO2", "date", 4, rows, 2, 0)
    schema = {"columns": {"institution_column": "Institution", "country_column": "Country"}, "output": {"source_row_column": "row"}}
    mapping = {"schema_version": 1, "country_overrides": {"CHUV": "CH"}, "reviewed_sources": {"a" * 64: {"5": {"biobank_id": "bbmri-eric:ID:CH_CHUV"}, "6": {"biobank_id": "bbmri-eric:ID:CH_CHUV"}}}}
    merged, summary = merge_descriptive_responses(workbook, schema, (question,), mapping)
    assert len(merged.responses) == 1
    assert merged.responses.iloc[0]["Choice"] == "Yes"
    assert merged.responses.iloc[0]["Country"] == "CH"
    assert not summary["conflicts"]
    assert summary["source_records"][0]["answers"]["Country"] == ""
    assert summary["observation_sources"][0]["source_rows"] == [5, 6]
    assert summary["observation_sources"][0]["answer_sources"]["q"] == [6]
    other, _ = merge_descriptive_responses(replace(workbook, source_sha256="b" * 64), schema, (question,), mapping)
    assert len(other.responses) == 2
    assert list(workbook.responses["Country"]) == ["", "SWISS"]
    mapping["reviewed_sources"]["a" * 64]["5"]["biobank_id"] = "invalid"
    with pytest.raises(report.InputError, match="Invalid reviewed biobank ID"):
        merge_descriptive_responses(workbook, schema, (question,), mapping)


def test_summary_and_rotated_upset_without_deviation():
    """Keep merging visible and rotate only the approved terminology chart.

    Returns:
        None after checking generated report TeX and R figure sizing.
    """
    from test_so2_descriptive_report import descriptive_workbook, minimal_schema
    from so2_descriptive_upsets import _renderer_source

    schema = minimal_schema()
    schema["questions"][0].update(question_id="q_018_choice", question_type="multi_choice", categories=["Yes", "No"], delimiter=";")
    workbook = descriptive_workbook([{"Name of Institution": "Bank", "Country": "SK", "Creation date": "", "Last update": "", "Digital maturity": "Yes"}])
    payload = report.build_descriptive_payload(workbook, schema)
    payload["responses_summary"] = {"received_submissions": 2, "merged_submissions": 1, "analytical_observations": 1, "duplicate_groups": [{"country": "SK", "institutions": ["Bank"], "source_rows": [5, 6]}], "conflicts": [], "unresolved_identity_rows": []}
    assets = SimpleNamespace(state="ready", figures={key: SimpleNamespace(upset_pdf=f"{key}-upset.pdf", deviation_pdf=f"{key}-deviation.pdf") for key in ["q_018", "q_042_q_044", "q_035_q_050"]})
    tex = report.render_descriptive_tex(payload, None, upset_assets=assets).tex
    assert tex.index("Abbreviations") < tex.index(r"\addsec{Responses Summary}") < tex.index(r"\section{Digital maturity}")
    assert "Bank" in tex and "5, 6" in tex
    assert "angle=90" in tex
    assert "-deviation.pdf" not in tex
    assert 'definition$id == "q_018"' in _renderer_source()
    assert 'height_ratio = if (definition$id == "q_018") 1.5 else 0.5' in _renderer_source()


def test_default_identity_path_works_without_private_mapping(tmp_path):
    """Prefer local reviewed data while keeping a fresh clone operational.

    Args:
        tmp_path: Temporary mapping directory without any real respondent decisions.

    Returns:
        None. The portable example is selected until a local private map exists.
    """
    from so2_response_merging import default_response_identity_path
    example = tmp_path / "so2_2025_response_identities.example.json"
    example.write_text('{"schema_version":1,"reviewed_sources":{},"country_overrides":{}}')
    assert default_response_identity_path(tmp_path) == example
    local = tmp_path / "so2_2025_response_identities.json"
    local.write_text(example.read_text())
    assert default_response_identity_path(tmp_path) == local
