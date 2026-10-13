"""Synthetic tests for lossless, scope-safe MuCP source parsing."""

import json
import inspect
from pathlib import Path

import pytest

from survey_evidence import plain
from survey_mucp import (
    MuCPDocument,
    MuCPQuestion,
    discover_mucp_questions,
    load_mucp_document,
    mucp_source_records,
    interpret_checkbox_answer,
    load_mucp_reporting_policy,
)


def _write_fixture(tmp_path, *, questions=None, responses=None, sources=None, version="1.0.0"):
    """Write a minimal, non-sensitive MuCP input and local Draft 2020-12 schema.

    Args:
        tmp_path: Pytest-owned directory for isolated synthetic JSON files.
        questions: Optional checkbox-question metadata replacing the default catalogue.
        responses: Optional response mappings replacing the default synthetic response.
        sources: Optional source-manifest mappings replacing the default source.
        version: Declared source schema version used to exercise version validation.

    Returns:
        Tuple of synthetic source, schema, and state-registry paths.
    """
    question_rows = questions or [{
        "id": "B.test.answer", "part": "B", "group": "test", "key": "answer",
        "label": "Test answer", "type": "checkbox", "aliases": [],
    }]
    source_rows = sources or [{
        "source_id": "SRC-001", "path": "synthetic/source.pdf", "filename": "source.pdf",
        "role": "submission", "file_type": "pdf", "bytes": 12, "sha256": "a" * 64,
        "authority": "primary", "extracted": {}, "original_file": "private-bytes-must-not-copy",
    }]
    answer = {
        "value": True, "answer_state": "selected", "raw_text": "Selected",
        "qualifier_text": None, "evidence": [{"source_id": "SRC-001", "locator": "page 1"}],
    }
    response_rows = responses or [{
        "response_id": "R-001", "source_ids": ["SRC-001"], "country": "ZZ",
        "record_type": "submission", "source_authority": "primary", "scope": "submission",
        "answers": {"B.test.answer": answer},
        "fields": {"A.institution": "Synthetic institute", "A.submitter": "Synthetic person",
                   "A.email": "synthetic@example.invalid", "B.description": "Synthetic narrative",
                   "B.count": None, "C.description": None, "C.count": None},
        "narrative_blocks": [], "collections": [], "structured_tables": [], "workbook_links": [],
        "consistency_warnings": [], "extraction_notes": [],
        "identity": {"institution_name": "Synthetic institute", "email_addresses": ["synthetic@example.invalid"]},
        "raw_record": {"source_text": "Synthetic original row wording",
                       "embedded_asset": {"base64": "c3ludGhldGlj"}},
        "raw_record_locator": "synthetic row locator",
        "comments_and_qualifications": [], "full_evidence_source_ids": ["SRC-001"],
        "normalization_status": "complete", "quantity_index": [],
    }]
    source = {
        "schema_version": version,
        "metadata": {"survey": "MuCP", "version": version},
        "questionnaire": {"title": "Synthetic", "template_source_id": "SRC-001",
                           "checkbox_questions": question_rows,
                           "text_fields": [{"id": field_id, "type": "text", "label": field_id}
                                           for field_id in ("A.institution", "A.submitter", "A.email",
                                                            "B.description", "B.count", "C.description", "C.count")],
                           "answer_semantics": {}},
        "responses": response_rows, "sources": source_rows, "reconciliation": {}, "validation": {},
        "aggregate_workbook": {"extracted": "must-not-serialize"},
    }
    source_path = tmp_path / "source.json"
    schema_path = tmp_path / "schema.json"
    registry_path = tmp_path / "states.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object", "required": ["schema_version", "metadata", "questionnaire", "responses", "sources", "reconciliation", "validation"],
        "properties": {"schema_version": {"type": "string"}, "metadata": {"type": "object"},
                       "questionnaire": {"type": "object"}, "responses": {"type": "array"},
                       "sources": {"type": "array"}, "reconciliation": {"type": "object"},
                       "validation": {"type": "object"}},
        "additionalProperties": True,
    }
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    states = {
        "schema_version": "1.0.0",
        "states": {
            "selected": {"normalized_state": "affirmed", "allowed_values": [True]},
            "listed": {"normalized_state": "affirmed", "allowed_values": [True]},
            "stated_yes": {"normalized_state": "affirmed", "allowed_values": [True]},
            "explicit_no": {"normalized_state": "explicit_negative", "allowed_values": [False]},
            "conditional": {"normalized_state": "conditional", "allowed_values": [None]},
            "conditional_text": {"normalized_state": "conditional", "allowed_values": [None]},
            "text_reported": {"normalized_state": "unknown", "allowed_values": [True, None]},
            "ambiguous_formatting": {"normalized_state": "ambiguous_or_source_conflict", "allowed_values": [None]},
            "multiple_scopes_or_conflict": {"normalized_state": "ambiguous_or_source_conflict", "allowed_values": [None]},
            "not_asked": {"normalized_state": "unknown", "allowed_values": [None]},
            "not_asked_or_not_recognized": {"normalized_state": "unknown", "allowed_values": [None]},
            "not_confirmed": {"normalized_state": "unknown", "allowed_values": [None]},
            "not_listed": {"normalized_state": "unknown", "allowed_values": [None]},
            "not_reported": {"normalized_state": "unknown", "allowed_values": [None]},
            "not_reported_in_country_summary": {"normalized_state": "unknown", "allowed_values": [None]},
            "unmarked": {"normalized_state": "unknown", "allowed_values": [None]},
        },
    }
    registry_path.write_text(json.dumps(states), encoding="utf-8")
    return source_path, schema_path, registry_path


def _load(paths):
    """Load a synthetic source through the public MuCP parser interface.

    Args:
        paths: Source, schema, and registry paths returned by ``_write_fixture``.

    Returns:
        Immutable parsed MuCP document.
    """
    return load_mucp_document(*paths)


def test_checkbox_interpretation_preserves_raw_evidence(tmp_path):
    """Interpret present options without changing their source answer or provenance.

    Args:
        tmp_path: Isolated directory for a synthetic present checkbox group.

    Returns:
        None. Raw null, text, references and evidence identity survive interpretation.
    """
    paths = _write_fixture(tmp_path)
    source = json.loads(paths[0].read_text(encoding="utf-8"))
    answer = source["responses"][0]["answers"]["B.test.answer"]
    answer.update(value=None, answer_state="unmarked", raw_text="WGS", qualifier_text="Source note")
    paths[0].write_text(json.dumps(source), encoding="utf-8")
    policy = load_mucp_reporting_policy(Path("survey-mappings/mucp_reporting_policy.json"))
    before = json.loads(json.dumps(answer))
    interpreted = interpret_checkbox_answer(answer, source["questionnaire"]["checkbox_questions"][0], policy)
    assert interpreted == {"normalized_value": "explicit_negative", "basis": "present_applicable_unmarked_is_no",
                           "policy_version": "1"}
    assert answer == before
    item = next(item for item in _load(paths).records[0].data["evidence"] if item["question_id"] == "B.test.answer")
    assert item["normalized_value"] == "explicit_negative"
    assert item["raw_answer"] is None and item["answer_state"] == "unmarked"
    assert item["raw_text"] == "WGS" and item["qualifier_text"] == "Source note"
    assert item["source_refs"][0]["locator"] == "page 1"
    assert item["evidence_id"].startswith("mucp:")
    assert item["extensions"]["checkbox_interpretation"] == {"basis": "present_applicable_unmarked_is_no",
                                                              "policy_version": "1"}
    assert _load(paths).coverage_audit["reporting_policy"]["sha256"]


def test_missing_question_is_not_unticked(tmp_path):
    """A catalogue option without an answer key creates no negative assertion.

    Args:
        tmp_path: Isolated directory for a response omitting its catalogue question.

    Returns:
        None. Missing and explicitly uncertain entries remain unknown or conditional.
    """
    paths = _write_fixture(tmp_path)
    source = json.loads(paths[0].read_text(encoding="utf-8"))
    source["responses"][0]["answers"] = {}
    paths[0].write_text(json.dumps(source), encoding="utf-8")
    assert not [item for item in _load(paths).records[0].data["evidence"]
                if item["question_id"] == "B.test.answer"]
    policy = load_mucp_reporting_policy(Path("survey-mappings/mucp_reporting_policy.json"))
    question = source["questionnaire"]["checkbox_questions"][0]
    for state, expected in (("not_asked", "unknown"), ("not_asked_or_not_recognized", "unknown"),
                            ("ambiguous_formatting", "ambiguous_or_source_conflict"),
                            ("conditional", "conditional"), ("not_reported", "unknown")):
        result = interpret_checkbox_answer({"value": None, "answer_state": state}, question, policy)
        assert result["normalized_value"] == expected
    assert interpret_checkbox_answer({"value": True, "answer_state": "selected"}, question, policy)["normalized_value"] == "affirmed"
    assert interpret_checkbox_answer({"value": False, "answer_state": "explicit_no"}, question, policy)["normalized_value"] == "explicit_negative"


def test_discovery_preserves_all_question_metadata_and_seven_text_fields(tmp_path):
    """Question discovery is independent and retains full questionnaire metadata.

    Args:
        tmp_path: Pytest-owned temporary directory for synthetic source files.

    Returns:
        None. Asserts the immutable catalogue and all seven configured text fields.
    """
    questions = [{"id": f"C.synthetic.q{i:02}", "part": "C", "group": "synthetic",
                  "key": f"q{i}", "label": f"Question {i}", "type": "checkbox",
                  "template_paragraph_index": i, "aliases": []} for i in range(63)]
    paths = _write_fixture(tmp_path, questions=questions,
                           responses=[{"response_id": "R-001", "source_ids": ["SRC-001"],
                                       "country": "ZZ", "record_type": "submission", "scope": "submission",
                                       "identity": {}, "answers": {}, "fields": {}, "collections": [],
                                       "narrative_blocks": [], "consistency_warnings": [],
                                       "comments_and_qualifications": []}])
    document = _load(paths)
    discovered = discover_mucp_questions(document)
    assert len(discovered) == 63
    assert discovered[0].data["id"] == "C.synthetic.q00"
    assert document.text_fields[0]["id"] == "A.institution"
    assert len(document.text_fields) == 7


def test_source_records_preserve_provenance_scope_and_false_null_states(tmp_path):
    """Every answer keeps its source locator, raw state, and explicit scope.

    Args:
        tmp_path: Pytest-owned temporary directory for synthetic source files.

    Returns:
        None. Asserts source/evidence links and distinct false and null values.
    """
    paths = _write_fixture(tmp_path)
    document = _load(paths)
    records = mucp_source_records(document)
    assert records[0].data["record_id"] == "R-001"
    assert records[0].data["survey"] == "MuCP"
    assert records[0].data["scopes"][0]["scope_id"] == "R-001:submission"
    assert records[0].data["scopes"][0]["source_record_id"] == "R-001"
    evidence = records[0].data["evidence"]
    assert evidence[0]["raw_answer"] is True
    assert evidence[0]["answer_state"] == "selected"
    assert evidence[0]["source_refs"][0]["locator"] == "page 1"
    assert "private-bytes-must-not-copy" not in repr(plain(records[0]))
    assert records[0].data["metadata"]["raw_record"]["source_text"] == "Synthetic original row wording"
    assert "base64" not in records[0].data["metadata"]["raw_record"]["embedded_asset"]
    assert records[0].data["metadata"]["raw_record_disposition"] == "retained_lightweight_source_record_bulk_fields_filtered"
    assert records[0].data["metadata"]["raw_record_locator"] == "synthetic row locator"


def test_missing_document_evidence_has_an_exact_input_json_pointer(tmp_path):
    """Retain exact answer lineage without inventing document evidence where none exists.

    Args:
        tmp_path: Isolated directory for a synthetic answer without an extraction locator.

    Returns:
        None. The fallback resolves to the original answer and states its evidence limitation.
    """
    paths = _write_fixture(tmp_path)
    source = json.loads(paths[0].read_text())
    source["responses"][0]["answers"]["B.test.answer"]["evidence"] = []
    paths[0].write_text(json.dumps(source))
    item = next(item for item in _load(paths).records[0].data["evidence"] if item["question_id"] == "B.test.answer")
    ref = item["source_refs"][0]
    assert ref["locator"] == "/responses/0/answers/B.test.answer"
    assert ref["kind"] == "input_json" and ref["document_evidence_status"] == "not_provided"


def test_positive_answer_and_narrative_qualifiers_have_dedicated_evidence_fields(tmp_path):
    """Structured and narrative qualification remains separately addressable.

    Args:
        tmp_path: Pytest-owned directory for synthetic qualified evidence.

    Returns:
        None. Asserts both qualifier strings survive as first-class evidence values.
    """
    paths = _write_fixture(tmp_path)
    source = json.loads(paths[0].read_text(encoding="utf-8"))
    answer = source["responses"][0]["answers"]["B.test.answer"]
    answer["qualifier_text"] = "Affirmed only for the named collection"
    source["responses"][0]["narrative_blocks"] = [{
        "text": "Availability varies by collection", "qualifier_text": "Submission-wide scope is uncertain",
        "evidence": [{"source_id": "SRC-001", "locator": "page 2"}],
    }]
    paths[0].write_text(json.dumps(source), encoding="utf-8")
    items = mucp_source_records(_load(paths))[0].data["evidence"]
    structured = next(item for item in items if item["kind"] == "structured_answer")
    narrative = next(item for item in items if item["kind"] == "narrative")
    assert structured["normalized_value"] == "affirmed"
    assert structured["qualifier_text"] == "Affirmed only for the named collection"
    assert narrative["raw_text"] == "Availability varies by collection"
    assert narrative["qualifier_text"] == "Submission-wide scope is uncertain"


@pytest.mark.parametrize("state,value", [
    ("selected", True), ("listed", True), ("stated_yes", True), ("explicit_no", False),
    ("conditional", None), ("conditional_text", None), ("text_reported", True),
    ("text_reported", None), ("ambiguous_formatting", None),
    ("multiple_scopes_or_conflict", None), ("not_asked", None),
    ("not_asked_or_not_recognized", None), ("not_confirmed", None),
    ("not_listed", None), ("not_reported", None),
    ("not_reported_in_country_summary", None), ("unmarked", None),
])
def test_all_registered_state_value_pairs_are_preserved(tmp_path, state, value):
    """Every observed state/value form parses without collapsing false or null.

    Args:
        tmp_path: Pytest-owned directory for each isolated source fixture.
        state: Observed MuCP answer_state label from schema version 1.0.0.
        value: Literal source value paired with the state, including null.

    Returns:
        None. Asserts the parsed evidence retains the exact source pair.
    """
    paths = _write_fixture(tmp_path)
    source_path = paths[0]
    source = json.loads(source_path.read_text(encoding="utf-8"))
    answer = source["responses"][0]["answers"]["B.test.answer"]
    answer.update(value=value, answer_state=state)
    source_path.write_text(json.dumps(source), encoding="utf-8")
    record = mucp_source_records(_load(paths))[0]
    item = record.data["evidence"][0]
    assert item["raw_answer"] is value or item["raw_answer"] == value
    assert item["answer_state"] == state


@pytest.mark.parametrize("mutation,match", [
    ("version", "schema_version"), ("type", "record_type"), ("state", "answer_state"),
    ("duplicate_id", "duplicate"), ("duplicate_question", "duplicate"),
    ("duplicate_source", "duplicate"), ("unknown_question", "question"),
    ("unknown_source", "source"), ("unclassified", "unclassified"),
])
def test_invalid_versions_types_states_and_references_are_rejected(tmp_path, mutation, match):
    """Malformed source contracts fail with actionable validation errors.

    Args:
        tmp_path: Pytest-owned directory for isolated synthetic files.
        mutation: Invalid source condition to introduce before parsing.
        match: Expected diagnostic fragment for that condition.

    Returns:
        None. Asserts invalid input never yields a partially trusted document.
    """
    paths = _write_fixture(tmp_path, version="2.0.0" if mutation == "version" else "1.0.0")
    source = json.loads(paths[0].read_text(encoding="utf-8"))
    response = source["responses"][0]
    if mutation == "type":
        response["record_type"] = "future_type"
    elif mutation == "state":
        response["answers"]["B.test.answer"]["answer_state"] = "future_state"
    elif mutation == "duplicate_id":
        source["responses"].append(dict(response))
    elif mutation == "duplicate_question":
        source["questionnaire"]["checkbox_questions"].append(
            dict(source["questionnaire"]["checkbox_questions"][0]))
    elif mutation == "duplicate_source":
        source["sources"].append(dict(source["sources"][0]))
    elif mutation == "unknown_question":
        response["answers"]["future.question"] = response["answers"].pop("B.test.answer")
    elif mutation == "unknown_source":
        response["answers"]["B.test.answer"]["evidence"][0]["source_id"] = "SRC-999"
    elif mutation == "unclassified":
        response["future_structured_field"] = {"unexpected": True}
    paths[0].write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises((ValueError, RuntimeError), match=f"(?i){match}"):
        _load(paths)


def test_nested_unlinked_collection_scope_does_not_inherit_response_answers(tmp_path):
    """A nested collection scope receives only answers physically present there.

    Args:
        tmp_path: Pytest-owned directory for synthetic source files.

    Returns:
        None. Asserts nested scope identity is stable and evidence is not inherited.
    """
    paths = _write_fixture(tmp_path)
    source = json.loads(paths[0].read_text(encoding="utf-8"))
    source["responses"][0]["collections"] = [{
        "collection_id": "LOCAL-7", "name": "Synthetic collection",
        "answers": {}, "fields": {}, "evidence": [],
    }]
    paths[0].write_text(json.dumps(source), encoding="utf-8")
    record = mucp_source_records(_load(paths))[0]
    nested = [scope for scope in record.data["scopes"] if scope["scope_id"].endswith(":collection:LOCAL-7")]
    assert nested and nested[0]["kind"] == "collection"
    assert nested[0]["source_scope_kind"] is None
    assert nested[0]["source_record_id"] == "R-001"
    assert all(item["scope_id"] != nested[0]["scope_id"] for item in record.data["evidence"])


def test_duplicate_json_keys_and_remote_schema_references_are_rejected(tmp_path):
    """The parser rejects ambiguous JSON objects and schemas requiring network access.

    Args:
        tmp_path: Pytest-owned directory for isolated synthetic source files.

    Returns:
        None. Asserts strict duplicate-key and local-reference-only policies.
    """
    paths = _write_fixture(tmp_path)
    paths[0].write_text('{"schema_version":"1.0.0","schema_version":"1.0.0"}', encoding="utf-8")
    with pytest.raises((ValueError, RuntimeError), match="(?i)duplicate"):
        _load(paths)
    paths = _write_fixture(tmp_path)
    schema = json.loads(paths[1].read_text(encoding="utf-8"))
    schema["properties"]["metadata"] = {"$ref": "https://example.invalid/schema.json"}
    paths[1].write_text(json.dumps(schema), encoding="utf-8")
    with pytest.raises((ValueError, RuntimeError), match="(?i)remote"):
        _load(paths)


def test_country_summary_is_not_biobank_evidence(tmp_path):
    """Country-level source records remain diagnosable but cannot assert biobank evidence.

    Args:
        tmp_path: Pytest-owned directory for isolated synthetic source files.

    Returns:
        None. Asserts summary records are explicitly typed and carry no analytical identity.
    """
    paths = _write_fixture(tmp_path)
    source = json.loads(paths[0].read_text(encoding="utf-8"))
    source["responses"][0]["record_type"] = "country_summary"
    paths[0].write_text(json.dumps(source), encoding="utf-8")
    record = mucp_source_records(_load(paths))[0]
    assert record.data["record_type"] == "country_summary"
    assert record.data["identity"].get("explicit_biobank_id") is None
    assert record.data["identity"]["institution_name"] is None


def test_nested_collection_supplemental_material_and_source_links_are_retained(tmp_path):
    """Nested scalar/mapping material remains attached to its own collection scope.

    Args:
        tmp_path: Pytest-owned temporary directory for synthetic source files.

    Returns:
        None. Asserts collection counts, descriptors, and source locators survive projection.
    """
    paths = _write_fixture(tmp_path)
    source = json.loads(paths[0].read_text(encoding="utf-8"))
    source["responses"][0]["collections"] = [{
        "collection_id": "LOCAL-7", "name": "Synthetic collection", "scope": "collection",
        "answers": {}, "fields": {}, "samples": 23, "biospecimens_raw": ["serum"],
        "evidence": [{"source_id": "SRC-001", "locator": "table 2"}],
    }]
    paths[0].write_text(json.dumps(source), encoding="utf-8")
    record = mucp_source_records(_load(paths))[0]
    nested = next(scope for scope in record.data["scopes"] if scope["collection_id"] == "LOCAL-7")
    assert nested["metadata"]["samples"] == 23
    assert nested["metadata"]["biospecimens_raw"] == ("serum",)
    assert nested["metadata"]["evidence"][0]["locator"] == "table 2"


def test_contradictory_state_value_pair_is_rejected(tmp_path):
    """A registered state cannot legitimize a contradictory source value.

    Args:
        tmp_path: Pytest-owned directory for the synthetic invalid answer.

    Returns:
        None. Asserts value/state contradictions fail before producing a document.
    """
    paths = _write_fixture(tmp_path)
    source = json.loads(paths[0].read_text(encoding="utf-8"))
    source["responses"][0]["answers"]["B.test.answer"]["value"] = False
    paths[0].write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ValueError, match="Contradictory"):
        _load(paths)


def test_public_dataclass_docstrings_describe_every_field():
    """Public immutable model documentation names every concrete data attribute.

    Returns:
        None. Asserts each dataclass field is documented in its Attributes section.
    """
    for model in (MuCPQuestion, MuCPDocument):
        documentation = inspect.getdoc(model) or ""
        assert "Attributes:" in documentation
        attributes = documentation.split("Attributes:", 1)[1]
        for field_name in model.__dataclass_fields__:
            assert f"{field_name}:" in attributes
