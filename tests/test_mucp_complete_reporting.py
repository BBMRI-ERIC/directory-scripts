"""Regression coverage for complete MuCP source inclusion and readable quantities."""

from survey_combined import build_combined_payload, group_sources
from survey_evidence import SourceRecord, ResolutionRecord
import pytest


@pytest.mark.parametrize("text,numeric_only,value,relation", [
    ("6 mio", True, 6000000, "reported_value"),
    ("~16.000", True, 16000, "approximate"),
    ("More than 150.000 donors.", False, 150000, "greater_than"),
    ("2 mio +", True, 2000000, "at_least"),
])
def test_source_count_formats(text, numeric_only, value, relation):
    """Interpret complete Danish count fields without mining narrative substrings.

    Args:
        text: Literal source count field with grouping or million abbreviation.
        numeric_only: Whether the questionnaire separately establishes the unit.
        value: Independently expected expanded integer count.
        relation: Expected exact, approximate or bound semantics.

    Returns:
        None. Whole-field parsing preserves magnitude and qualification.
    """
    from survey_mucp_quantities import _count_measurement
    result = _count_measurement(text, numeric_only)
    assert result is not None
    assert (result["value"], result["relation"]) == (value, relation)


def test_person_unit_synonyms_validate_without_erasing_bounds():
    """Accept donors versus individuals but reject incompatible source relations.

    Returns:
        None. Unit equivalence never changes an approximate count into an exact one.
    """
    from survey_mucp_quantities import _typed_total
    total = {"value": 150000, "unit": "individuals", "relation": "greater_than"}
    witness = {"value": 150000, "unit": "donors", "relation": "greater_than"}
    assert _typed_total(total, witness, canonical_person_units=True)
    assert not _typed_total({**total, "relation": "reported_value"}, witness, canonical_person_units=True)


def test_open_ended_count_retains_source_bound_over_projected_exact():
    """Correct the explicit trailing-plus bound without modifying raw evidence.

    Returns:
        None. The profile uses at-least semantics, retaining the projected value.
    """
    from survey_descriptive import build_mucp_cohort_profile
    evidence = {"survey": "MuCP", "source_record_id": "r", "scope_id": "s", "question_id": "C.count",
                "evidence_id": "e", "raw_text": "2 mio +", "source_refs": [],
                "extensions": {"reported_total": {"value": 2000000, "unit": "individuals", "relation": "reported_value"}}}
    bank = {"biobank_id": "b", "name": "Bank", "country": "DK", "mucp_source_records": [],
            "evidence": [evidence], "scopes": {}}
    row = build_mucp_cohort_profile([bank])["sizes"]["donors"]["rows"][0]
    assert row["relation"] == "at_least"
    assert row["reported_total"]["relation"] == "reported_value"


def test_nonadditive_counts_remain_visible_without_summing_scopes():
    """Show excluded Danish quantities as separate qualified observations.

    Returns:
        None. Repeated B/C evidence collapses visually, not arithmetically.
    """
    from survey_combined_report import render_nonadditive_quantity_charts
    rows = [{"quantity_id": key, "biobank_id": "b", "country": "DK", "source_record_id": "r",
             "scope_id": "s", "unit": "donors", "value": value, "relation": relation,
             "temporal_status": "unspecified", "question_id": question}
            for key, value, relation, question in [
                ("q1", 6000000, "reported_value", "B.count"),
                ("q2", 2000000, "at_least", "C.count"),
                ("q3", 150000, "greater_than", "B.count"),
                ("q4", 150000, "greater_than", "C.count")]]
    charts = render_nonadditive_quantity_charts({"observations": rows},
        {"excluded_contributions": [{"quantity_ids": [r["quantity_id"] for r in rows]}]},
        {"biobanks": [{"biobank_id": "b", "country": "DK", "name": "Danish bank"}]})
    tex = "\n".join(charts.values())
    assert "DK" in tex and "Danish bank" in tex
    assert "Part B" in tex and "Part C" in tex
    assert tex.count("coordinates {(150000,") == 1
    assert "Non-additive" in tex and "xmode=log" not in tex
    assert "8000000" not in tex


def test_different_bc_populations_cannot_create_an_exact_country_stack():
    """Retain Denmark's two source counts without selecting a misleading total.

    Returns:
        None. Both complete fields reach conflict handling and remain plot evidence.
    """
    from test_survey_mucp_quantities import bank, DEFINITIONS
    from survey_mucp_quantities import extract_modality_quantities
    from survey_mucp_aggregation import aggregate_modality_quantities
    item = bank([("C.omics_data.gwas", "")])
    item["country"] = "DK"
    for question, text, value in [("B.count", "6 mio", 6000000), ("C.count", "2 mio +", 2000000)]:
        evidence = {"survey": "MuCP", "evidence_id": question, "source_record_id": "R1",
                    "question_id": question, "question_label": "Number of individuals",
                    "scope_id": "R1:submission", "kind": "text_field", "raw_text": text,
                    "extensions": {"reported_total": {"value": value, "unit": "individuals", "relation": "reported_value"}},
                    "source_refs": [{"source_id": "SRC1", "locator": f"fields[{question}]"}]}
        item["evidence"].append(evidence)
        item["mucp_source_records"][0]["evidence"].append(evidence)
    summary = extract_modality_quantities([item], DEFINITIONS)
    assert {(r["value"], r["relation"]) for r in summary["observations"]} == {
        (6000000, "reported_value"), (2000000, "at_least")}
    aggregates = aggregate_modality_quantities(summary, [item])
    assert not any(row.get("segments") for row in aggregates["country_totals"])
    assert {r["reason"] for r in aggregates["excluded_contributions"]} == {"same_scope_conflicting_quantities"}


def test_conflict_label_does_not_claim_responses_are_contradictory():
    """Explain why counts cannot be added without asserting population ambiguity.

    Returns:
        None. The reader-facing label identifies why different counts are not summed.
    """
    from survey_combined_report import _quantity_exclusion_label
    assert _quantity_exclusion_label("same_scope_conflicting_quantities") == (
        "Different reported counts; cannot safely add them")


@pytest.mark.parametrize("raw,value", [("6 mio", 6000000), ("2 mio +", 2000000), ("~16.000", 16000)])
def test_scaled_count_does_not_repeat_as_extra_source_sentence(raw, value):
    """Recognize scaled/grouped literal counts as the same displayed amount.

    Args:
        raw: Complete source count field containing no additional narrative.
        value: Independently expanded count represented by the display row.

    Returns:
        None. Raw wording remains in JSON, without a redundant second table row.
    """
    from survey_combined_report import _quantity_wording_adds_information
    assert not _quantity_wording_adds_information({"value": value}, raw)


@pytest.mark.parametrize("wording,values", [
    ("73 000 blood donors with biobank consent", [73000]),
    ("Consented prospective about 220 000 and tissue archive about 800 000", [220000, 800000]),
    ("approx. 500 and approx. 300 control", [500, 300]),
])
def test_scoped_table_reports_each_source_answer_once(wording, values):
    """Avoid duplicating parsed counts alongside the same literal source answer.

    Args:
        wording: Complete source answer containing one or several counts.
        values: Numeric mentions extracted from that one source answer.

    Returns:
        None. The displayed answer appears once without extra unit-unclear rows.
    """
    from test_survey_combined_report import minimal_payload
    from survey_combined_report import render_combined_tex
    payload = minimal_payload()
    bank = payload["biobanks"][0]
    rows = [{"biobank_id": bank["biobank_id"], "institution": bank["name"],
             "country": "FI", "source_record_id": "r", "scope_id": "s",
             "question_id": "B.count", "scope_label": "submission", "value": value,
             "unit": "unit_unclear", "kind": "numeric_mention_not_additive", "raw_text": wording}
            for value in values]
    from survey_descriptive import build_mucp_cohort_profile
    profile = build_mucp_cohort_profile(payload["biobanks"])
    profile["sizes"]["unit_unclear"]["rows"] = rows
    payload["descriptive_statistics"]["MuCP"]["cohort_profile"] = profile
    tex = render_combined_tex(payload, {}).tex
    table = tex.split(r"\subsection{Reported quantities and collection context}", 1)[1].split(r"\subsection", 1)[0]
    assert table.count(wording) == 1
    assert "number mentioned in the answer" not in table


def test_all_mucp_retains_unresolved_and_excluded_sources():
    """Retain every MuCP record without claiming unresolved Directory identities.

    Returns:
        None. Original decisions and independent Directory match counts survive.
    """
    records = [SourceRecord({"record_id": rid, "survey": "MuCP", "country": "CZ",
                             "identity": {"institution_name": rid},
                             "evidence": [], "scopes": []}) for rid in ("a", "b", "c")]
    decisions = [ResolutionRecord({"source_record_id": r.data["record_id"],
                                  "status": status, "biobank_id": bid})
                 for r, status, bid in zip(records, ("accepted", "review", "excluded"),
                                          ("bbmri-eric:ID:CZ_A", "bbmri-eric:ID:CZ_A", None))]
    payload = build_combined_payload(group_sources([], []), group_sources(records, decisions), {}, {})
    assert {r["record_id"] for b in payload["biobanks"] for r in b["mucp_source_records"]} == {"a", "b", "c"}
    assert payload["matching_summary"]["mucp_matched_biobanks"] == 1
    assert sum(b["directory_biobank_id"] is None for b in payload["biobanks"]) == 2
    assert payload["metadata"]["mucp_source_coverage"]["included_records"] == 3


def test_reviewed_quantities_replace_owned_index_mentions():
    """Avoid reporting one source quantity twice under contradictory units.

    Returns:
        None. Reviewed source-owned measurements supersede only matching mentions.
    """
    from survey_descriptive import build_mucp_cohort_profile
    record = {"record_id": "r", "metadata": {"reviewed_quantities": [
        {"value": 25000, "unit": "samples", "source_unit": "FFPE samples", "relation": "approximate",
         "scope_id": "s", "scope_label": "FFPE", "source_field": "B.count", "question_id": "B.count",
         "original_wording": "approximately 25000 FFPE samples", "source_refs": []}],
        "quantity_index": [{"field": "B.count", "value": 25000, "unit": None, "context": "25000"}]}}
    profile = build_mucp_cohort_profile([{"biobank_id": "b", "name": "Bank", "country": "CZ",
        "mucp_source_records": [record], "evidence": [], "scopes": {}}])
    assert [r["value"] for r in profile["sizes"]["samples"]["rows"]] == [25000]
    assert profile["sizes"]["unit_unclear"]["rows"] == []


def test_reviewed_catalogue_rejects_wrong_input(tmp_path):
    """Reject a deliberately supplied catalogue for a different source document.

    Args:
        tmp_path: Pytest-owned isolated output directory.

    Returns:
        None. Input hash mismatch fails before any catalogue correction is applied.
    """
    import json
    from survey_mucp_reviewed import apply_reviewed_quantities
    path = tmp_path / "review.json"
    path.write_text(json.dumps({"schema_version": 1, "source_sha256": "wrong", "measurements": []}))
    with pytest.raises(ValueError, match="hash"):
        apply_reviewed_quantities([], "actual", [], {}, path)


def test_provisional_cohort_chart_labels_do_not_claim_unique_biobanks():
    """Label unresolved observations honestly rather than as verified biobanks.

    Returns:
        None. Generic chart labels preserve the mixed reporting-unit denominator.
    """
    from so2_descriptive_report import _chart_unit
    assert _chart_unit({"analytical_unit": "source_reporting_unit", "question_type": "single_choice"}) == "survey reporting units"


def test_quantity_type_selection_preamble_is_not_repeated():
    """List all included types once for a source contribution shared by many views.

    Returns:
        None. The table preserves both type names under one inclusion preamble.
    """
    from survey_combined_report import render_quantity_contributions
    contribution = {"biobank_id": "b", "value": 10, "unit": "samples", "basis": "collection",
                    "temporal_status": "unspecified", "quantity_ids": ["q"], "modality_ids": ["DNA", "Plasma"]}
    totals = [{"modality_id": name, "unit": "samples", "basis": "collection", "temporal_status": "unspecified",
               "segments": [{"quantity_ids": ["q"]}]} for name in ("DNA", "Plasma")]
    tex = render_quantity_contributions({"contributions": [contribution], "modality_totals": totals},
                                        [{"biobank_id": "b", "name": "Bank", "country": "CZ"}], {})
    assert tex.count("Included in Material/data type:") == 1
    assert "DNA, Plasma" in tex


def test_literal_count_does_not_reappear_as_unknown_unit_index():
    """Suppress a source-local duplicate even when index unit wording is missing.

    Returns:
        None. The authoritative count retains its bound and proved person unit.
    """
    from survey_descriptive import build_mucp_cohort_profile
    refs = [{"source_id": "src", "locator": "paragraph1"}]
    record = {"record_id": "r", "metadata": {"source_ids": ["src"], "quantity_index": [
        {"field": "B.count", "value": 500000, "unit": "individuals", "relation": "greater_than", "evidence": refs}]}}
    evidence = {"survey": "MuCP", "question_id": "B.count", "scope_id": "s", "source_record_id": "r",
                "evidence_id": "e", "raw_text": "> 500 000", "kind": "text_field", "source_refs": refs,
                "extensions": {"reported_total": {"value": 500000, "unit": "individuals", "relation": "greater_than"}}}
    record["evidence"] = [evidence]
    profile = build_mucp_cohort_profile([{"biobank_id": "b", "name": "Bank", "country": "BE",
        "mucp_source_records": [record], "evidence": [evidence], "scopes": {}}])
    assert len(profile["sizes"]["donors"]["rows"]) == 1
    assert profile["sizes"]["unit_unclear"]["rows"] == []


def test_review_audit_note_is_not_a_source_qualification():
    """Keep audit explanations separate from source-authored statistical qualifiers.

    Returns:
        None. An exact current single-scope count remains eligible for a size band.
    """
    from survey_descriptive import build_mucp_cohort_profile
    row = {"value": 11200, "unit": "donors", "source_unit": "individuals", "relation": "reported_value",
           "scope_id": "s", "scope_label": "Reported collection", "source_field": "B.count", "question_id": "B.count",
           "original_wording": "11200", "explanation": "Original source header proves individuals", "source_refs": []}
    profile = build_mucp_cohort_profile([{"biobank_id": "b", "name": "Bank", "country": "CZ",
        "mucp_source_records": [{"record_id": "r", "metadata": {"reviewed_quantities": [row]}}], "evidence": [], "scopes": {}}])
    assert profile["sizes"]["donors"]["states"]["single_reported_scope"] == 1


def test_workbook_reviewed_count_deduplicates_cell_owned_index():
    """Recognize identical workbook cell evidence without manufacturing a question ID.

    Returns:
        None. One reviewed unclear-unit cell appears once, not twice.
    """
    from survey_descriptive import build_mucp_cohort_profile
    refs = [{"source_id": "src", "locator": "sheet!H5"}]
    row = {"response_id": "r", "value": 318, "unit": "unit_unclear", "source_unit": "Information2",
           "relation": "reported_value", "scope_id": "s", "scope_label": "Collection", "source_field": None,
           "question_id": None, "original_wording": "318", "source_refs": refs}
    record = {"record_id": "r", "metadata": {"reviewed_quantities": [row],
        "quantity_index": [{"field": "B.count", "value": 318, "unit": "individuals", "evidence": refs}]}}
    evidence = {"survey": "MuCP", "question_id": "B.count", "scope_id": "s", "source_record_id": "r",
                "evidence_id": "e", "raw_text": "318", "kind": "text_field", "source_refs": refs,
                "extensions": {"reported_total": {"value": 318, "unit": "individuals", "relation": "reported_value"}}}
    profile = build_mucp_cohort_profile([{"biobank_id": "b", "name": "Bank", "country": "CH",
        "mucp_source_records": [record], "evidence": [evidence], "scopes": {}}])
    assert len(profile["sizes"]["unit_unclear"]["rows"]) == 1
    assert profile["sizes"]["donors"]["rows"] == []


def test_reviewed_count_cannot_suppress_a_sibling_scope():
    """Keep equal counts from different collections distinct even in one paragraph.

    Returns:
        None. A shared source locator never establishes shared collection scope.
    """
    from survey_mucp_reviewed import reviewed_quantity_covers
    refs = [{"source_id": "src", "locator": "paragraph1"}]
    record = {"metadata": {"reviewed_quantities": [{"scope_id": "collection-A", "source_field": "B.count",
        "value": 10, "source_refs": refs}]}}
    assert not reviewed_quantity_covers(record, {"scope_id": "collection-B", "question_id": "B.count", "source_refs": refs}, 10)
