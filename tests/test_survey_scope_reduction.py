"""Exercise planned reusable redacted fixtures and explicit source-scope reductions."""

from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import openpyxl
import pandas as pd

from so2_descriptive_report import QuestionDefinition
from survey_combined import canonicalize_linked_scopes, load_bound_so2_resolutions, reduce_mucp_question, so2_source_records
from survey_evidence import EvidenceItem
from survey_identity import MatchOverrides
from survey_mucp import load_mucp_document


FIXTURES = Path(__file__).parent / "fixtures/so2_mucp"


def test_scoped_fixture_preserves_unknown_qualifications_and_noninheritance():
    """Read scoped source fixtures without copying a positive into its sibling.

    Returns:
        None. A present unmarked sibling is No; missing options remain unknown.
    """
    document = load_mucp_document(FIXTURES / "mucp-responses.json", FIXTURES / "mucp-schema.json",
                                  Path("survey-mappings/mucp_answer_states_v1.json"))
    record = document.records[0]
    scopes = canonicalize_linked_scopes([record])
    serum = [EvidenceItem(item) for item in record.data["evidence"] if item["question_id"] == "C.serum"]
    result = reduce_mucp_question(serum, scopes).data
    assert result["state"] == "varying_across_scopes"
    assert "qualified" in result["flags"] and "partial_scope_coverage" in result["flags"]
    assert serum[1].data["raw_answer"] is None
    assert serum[1].data["normalized_value"] == "explicit_negative"
    plasma = [EvidenceItem(item) for item in record.data["evidence"] if item["question_id"] == "C.plasma"]
    assert len(plasma) == 1 and plasma[0].data["raw_answer"] is False
    assert reduce_mucp_question(plasma, scopes).data["state"] == "incomplete_or_qualified"


def test_three_unlinked_wgs_submissions_retain_different_answers(tmp_path):
    """Two unticked and one selected WGS response differ without a scope guess.

    Args:
        tmp_path: Isolated directory for the redacted A.1-shaped source input.

    Returns:
        None. Each response retains its own answer and the reduction is scope-uncertain.
    """
    source = json.loads((FIXTURES / "mucp-responses.json").read_text(encoding="utf-8"))
    source["questionnaire"]["checkbox_questions"] = [{"id": "C.WGS", "part": "C", "group": "OMICS",
        "key": "WGS", "label": "WGS", "type": "checkbox", "aliases": []}]
    original = source["responses"][0]
    source["responses"] = []
    for index, selected in enumerate((False, False, True), start=1):
        response = {**original, "response_id": f"RESP-{index}", "collections": [], "answers": {
            "C.WGS": {"value": True if selected else None, "answer_state": "selected" if selected else "unmarked",
                      "raw_text": "X WGS" if selected else "WGS", "qualifier_text": None,
                      "evidence": [{"source_id": "SYNTHETIC", "locator": f"page {index}"}]}}}
        source["responses"].append(response)
    path = tmp_path / "redacted-wgs.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    document = load_mucp_document(path, FIXTURES / "mucp-schema.json",
                                  Path("survey-mappings/mucp_answer_states_v1.json"))
    scopes = canonicalize_linked_scopes(document.records)
    items = [EvidenceItem(item) for record in document.records for item in record.data["evidence"]
             if item["question_id"] == "C.WGS"]
    assert [item.data["normalized_value"] for item in items] == ["explicit_negative", "explicit_negative", "affirmed"]
    result = reduce_mucp_question(items, scopes).data
    assert result["state"] == "conflicting_or_scope_uncertain"
    assert result["scope_assessment"] == "responses_differ_scope_uncertain"
    assert result["analytical_claim_count"] == 3
    assert len(result["contribution_ids"]) == 3
    agreeing = reduce_mucp_question([items[2], items[2]], scopes).data
    assert agreeing["state"] == "reported_yes_in_one_or_more_scopes"
    assert agreeing["analytical_claim_count"] == 1
    same_scope_no = {**items[2].data, "evidence_id": "mucp:" + "f" * 64,
                     "normalized_value": "explicit_negative", "raw_answer": None,
                     "answer_state": "unmarked"}
    contradiction = reduce_mucp_question([items[2], EvidenceItem(same_scope_no)], scopes).data
    assert contradiction["state"] == "conflicting"
    assert contradiction["scope_assessment"] == "same_scope_contradiction"


def test_distinct_collection_negatives_do_not_inherit():
    """A collection's present No neither overrides nor inherits its sibling's Yes.

    Returns:
        None. The existing fixture remains explicit collection variation.
    """
    document = load_mucp_document(FIXTURES / "mucp-responses.json", FIXTURES / "mucp-schema.json",
                                  Path("survey-mappings/mucp_answer_states_v1.json"))
    record = document.records[0]
    scopes = canonicalize_linked_scopes([record])
    serum = [EvidenceItem(item) for item in record.data["evidence"] if item["question_id"] == "C.serum"]
    result = reduce_mucp_question(serum, scopes).data
    assert result["state"] == "varying_across_scopes"
    assert result["scope_assessment"] == "distinct_collections_vary"
    assert result["has_affirmative_evidence"] is True
    assert {item.data["scope_id"]: item.data["normalized_value"] for item in serum} == {
        "SYNTHETIC-001:collection:LOCAL-1": "affirmed",
        "SYNTHETIC-001:collection:LOCAL-2": "explicit_negative",
    }


def test_workbook_and_findings_fixtures_preserve_repeated_physical_rows(tmp_path):
    """Materialize the redacted worksheet fixture and bind its frozen findings by hash.

    Args:
        tmp_path: Isolated directory for the generated XLSX and bound findings JSON.

    Returns:
        None. Both agreeing submissions retain raw answers and physical row identities.
    """
    source = json.loads((FIXTURES / "so2-workbook.json").read_text())
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = source["worksheet"]
    for row in source["service_rows"] + [source["headers"]] + source["responses"]:
        sheet.append(row)
    path = tmp_path / "synthetic.xlsx"
    book.save(path)
    frame = pd.read_excel(path, sheet_name=source["worksheet"], header=3)
    frame["source_row"] = range(5, 5 + len(frame))
    workbook = SimpleNamespace(responses=frame, worksheet=source["worksheet"], source_path=str(path),
                               source_sha256=sha256(path.read_bytes()).hexdigest())
    question = QuestionDefinition("q_synthetic", "Samples", "multi_choice", "Samples", ("Serum", "Plasma"), ";", (), None)
    records = so2_source_records(workbook, [question], {"questions": {}})
    findings = json.loads((FIXTURES / "so2-findings.json").read_text())
    findings["survey_metadata"]["survey_sha256"] = workbook.source_sha256
    target = tmp_path / "findings.json"
    target.write_text(json.dumps(findings))
    decisions = load_bound_so2_resolutions(target, workbook, MatchOverrides({}, ()))
    assert len(records) == len(decisions) == 2
    assert [record.data["evidence"][0]["survey_row"] for record in records] == [5, 6]
    assert all(record.data["evidence"][0]["raw_answer"] == "Serum;Plasma" for record in records)
