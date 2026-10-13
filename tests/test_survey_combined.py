"""Test unique-biobank grouping, scope reductions and answer-level lineage."""

import importlib
import pytest

from survey_evidence import EvidenceItem, SourceRecord, ResolutionRecord


def test_thematic_groups_link_separate_source_contributions():
    """Retain source-qualified lineage under shared themes instead of merging assertions.

    Returns:
        None. Themes reference exact evidence and reject dangling contribution IDs.
    """
    from survey_combined import build_combined_payload, group_sources
    from survey_evidence import CombinedBiobank, plain, validate_evidence_links
    bid = "bbmri-eric:ID:AT_A"
    groups = []
    for survey, rid in (("SO2", "ROW-5"), ("MuCP", "RESP-001")):
        item = plain(answer(True, rid))
        item.update(survey=survey, source_record_id=rid, kind="structured_answer")
        record = SourceRecord({"record_id": rid, "survey": survey, "evidence": [item],
                               "scopes": [{"scope_id": rid, "source_record_id": rid, "survey": survey}]})
        resolution = ResolutionRecord({"source_record_id": rid, "status": "accepted", "biobank_id": bid})
        groups.append(group_sources([record], [resolution]))
    themes = {"themes": [{"title": "Serum", "questions": ["SO2:C.biospecimens.serum", "MuCP:C.biospecimens.serum"]},
                         {"title": "MuCP only", "questions": ["MuCP:C.biospecimens.serum"]}]}
    bb = build_combined_payload(*groups, {}, themes)["biobanks"][0]
    assert bb["thematic_groups"][0]["contribution_ids"] == sorted(item["evidence_id"] for item in bb["evidence"])
    assert len(bb["thematic_groups"][1]["contribution_ids"]) == 1
    assert len(bb["evidence"]) == len(bb["observations"]) == 2
    bb["thematic_groups"][0]["contribution_ids"] = ["missing"]
    with pytest.raises(ValueError, match="thematic contribution"):
        validate_evidence_links(CombinedBiobank(bb))


def answer(value, scope="s1", state=None):
    """Create one redacted MuCP answer with explicit source and scope evidence.

    Args:
        value: True, false or null source assertion to preserve exactly.
        scope: Reported scope identifier determining whether evidence contradicts.
        state: Optional raw extraction state; otherwise inferred for this synthetic fixture.

    Returns:
        Immutable evidence item for the synthetic serum question.
    """
    return EvidenceItem({"evidence_id": "e-" + scope + str(value), "survey": "MuCP",
                         "source_record_id": "RESP-001", "scope_id": scope,
                         "question_id": "C.biospecimens.serum", "question_label": "Serum",
                         "normalized_value": value, "raw_answer": value,
                         "source_refs": [{"path": "redacted.json", "locator": "/fixture/" + scope}],
                         "answer_state": state or ("selected" if value else "explicit_no" if value is False else "unmarked")})


def test_scope_reduction_retains_unknown_and_variation():
    """Separate missing, partial affirmative, contradictory and varying scope states.

    Returns:
        None. A collection-level positive is never converted to a universal biobank boolean.
    """
    module = importlib.import_module("survey_combined")
    assert module.reduce_mucp_question([answer(None)], {}).data["state"] == "unknown_or_unmarked"
    partial = module.reduce_mucp_question([answer(True), answer(None, "s2")], {})
    assert partial.data["state"] == "reported_yes_in_one_or_more_scopes"
    assert "partial_scope_coverage" in partial.data["flags"]
    assert module.reduce_mucp_question([answer(True), answer(False)], {}).data["state"] == "conflicting"
    scopes = {"s1": {"kind": "collection", "source_record_id": "RESP-001", "collection_id": "A"},
              "s2": {"kind": "collection", "source_record_id": "RESP-001", "collection_id": "B"}}
    result = module.reduce_mucp_question([answer(True), answer(False, "s2")], scopes)
    assert result.data["state"] == "varying_across_scopes"
    assert len(result.data["contribution_ids"]) == 2


def test_multiple_records_have_one_overlapping_biobank():
    """Intersect accepted biobank IDs instead of joining source rows one to one.

    Returns:
        None. Multiple records retain their evidence but do not multiply cohort membership.
    """
    module = importlib.import_module("survey_combined")
    bid = "bbmri-eric:ID:AT_A"
    so2 = [SourceRecord({"record_id": str(i), "survey": "SO2", "evidence": [], "scopes": []}) for i in [1, 2]]
    mucp = [SourceRecord({"record_id": str(i), "survey": "MuCP", "evidence": [], "scopes": []}) for i in [3, 4, 5]]
    a = module.group_sources(so2, [ResolutionRecord({"source_record_id": r.data["record_id"], "status": "accepted", "biobank_id": bid}) for r in so2])
    b = module.group_sources(mucp, [ResolutionRecord({"source_record_id": r.data["record_id"], "status": "accepted", "biobank_id": bid}) for r in mucp])
    payload = module.build_combined_payload(a, b, {"biobanks": {bid: {"name": "Alpha", "country": "AT"}}}, {})
    assert payload["matching_summary"]["overlapping_biobanks"] == 1
    assert len(payload["biobanks"][0]["so2_source_records"]) == 2
    assert len(payload["biobanks"][0]["mucp_source_records"]) == 3


def matching_inventory_payload():
    """Build a redacted payload covering every stored matching-resolution status.

    Returns:
        Combined payload with overlap, accepted exclusives, repeats, unresolved records
        and an excluded country summary.
    """
    from survey_combined import build_combined_payload, group_sources

    overlap_id = "bbmri-eric:ID:AT_OVERLAP"
    so2_rows = [
        ("S-OVERLAP", "accepted", overlap_id, "Twin Institute", "Austria", "submission"),
        ("S-EXCLUSIVE", "accepted", "bbmri-eric:ID:AT_SO2", "Twin Institute", "AT", "submission"),
        ("S-UNMATCHED-1", "unmatched", None, "Unresolved Center", "Austria", "submission"),
        ("S-UNMATCHED-2", "unmatched", None, "Unresolved Center", "AT", "submission"),
        ("S-REVIEW", "review", None, "", "UnKnOwN", "submission"),
        ("S-COUNTRY", "excluded", None, "Austria country summary", "Austria", "country_summary"),
    ]
    mucp_rows = [
        ("M-OVERLAP", "accepted", overlap_id, "Overlap Hospital", "AT", "submission"),
        ("M-EXCLUSIVE", "accepted", "bbmri-eric:ID:DE_MUCP", "MuCP Center", "DE", "submission"),
        ("M-UNMATCHED", "unmatched", None, "Unresolved MuCP", "DE", "submission"),
        ("M-REVIEW", "review", None, "Review MuCP", "", "submission"),
        ("M-EXCLUDED", "excluded", None, "Country response", "Germany", "country_summary"),
    ]

    def make_groups(survey, rows):
        """Build a survey inventory with synthetic stored matching decisions.

        Args:
            survey: SO2 or MuCP source tag applied to every generated record.
            rows: Record ID, status, bank ID, institution, country and scope tuples.

        Returns:
            GroupedSources retaining all generated records and their resolutions.
        """
        records, resolutions = [], []
        for rid, status, bid, name, country, record_type in rows:
            records.append(SourceRecord({
                "record_id": rid, "survey": survey, "record_type": record_type,
                "country": country, "identity": {"institution_name": name,
                "email_addresses": ["private@example.org"], "contact_name": "Private Person"},
                "survey_row": rid, "scopes": [], "evidence": [],
            }))
            resolutions.append(ResolutionRecord({
                "source_record_id": rid, "survey": survey, "status": status,
                "biobank_id": bid, "reason": "not biobank-scoped" if status == "excluded" else "",
                "explanation": ("Country summary is not biobank-scoped evidence; contact private@example.org"
                                if status == "excluded" else ""),
                "candidate_ids": [],
            }))
        return group_sources(records, resolutions)

    return build_combined_payload(
        make_groups("SO2", so2_rows), make_groups("MuCP", mucp_rows),
        {"biobanks": {
            overlap_id: {"name": "Overlap Hospital", "country": "Austria"},
            "bbmri-eric:ID:AT_SO2": {"name": "Twin Institute", "country": "AT"},
            "bbmri-eric:ID:DE_MUCP": {"name": "MuCP Center", "country": "DE"},
        }}, {}, join="inner",
    )


def test_matching_breakdown_accounts_stored_statuses_and_identity_without_name_dedup():
    """Count every response once and derive accepted overlap from stored Directory IDs.

    Returns:
        None. Duplicate representations deduplicate by record ID while distinct banks
        sharing a display name remain distinct.
    """
    from survey_combined import build_matching_breakdown

    payload = matching_inventory_payload()
    before = build_matching_breakdown(payload)
    payload["unmatched_so2"].append(payload["biobanks"][0]["so2_source_records"][0:1] and {
        "record": payload["biobanks"][0]["so2_source_records"][0],
        "resolution": payload["biobanks"][0]["identity_resolutions"][0],
    })
    after = build_matching_breakdown(payload)

    assert before == after
    assert after["accepted_overlap"] == {"count": 1, "directory_ids": ["bbmri-eric:ID:AT_OVERLAP"]}
    so2 = after["surveys"]["SO2"]
    assert so2["total_records"] == 6
    assert so2["status_counts"] == {"accepted": 2, "unmatched": 2, "review": 1, "excluded": 1}
    assert sum(so2["status_counts"].values()) == so2["total_records"]
    assert so2["distinct_accepted_directory_ids"] == 2
    assert so2["accepted_exclusive_directory_ids"] == ["bbmri-eric:ID:AT_SO2"]
    assert so2["accepted_exclusive_directory_id_count"] == 1
    accepted_at = next(group for group in so2["country_groups"]["accepted"] if group["country"] == "AT")
    twin = next(entry for entry in accepted_at["institutions"] if entry["name"] == "Twin Institute")
    assert twin["record_count"] == 2 and twin["distinct_directory_ids"] == 2
    unmatched_at = next(group for group in so2["country_groups"]["unmatched"] if group["country"] == "AT")
    unresolved = next(entry for entry in unmatched_at["institutions"] if entry["name"] == "Unresolved Center")
    assert unresolved["record_count"] == 2
    assert unresolved["distinct_directory_ids"] is None
    assert so2["country_summary_records"][0]["record_id"] == "S-COUNTRY"
    assert so2["country_summary_records"][0]["status"] == "excluded"
    assert so2["country_groups"]["excluded"] == []
    assert any(group["country"] == "DE"
               for group in after["surveys"]["MuCP"]["country_groups"]["accepted"])
    assert after["surveys"]["SO2"]["country_groups"]["review"][0]["country"] == "Unknown"
    import json
    from pathlib import Path
    from jsonschema import Draft202012Validator
    schema = json.loads(Path("survey-mappings/so2_mucp_combined.schema.json").read_text())
    fragment = {"$schema": schema["$schema"], "$defs": schema["$defs"],
                "$ref": "#/$defs/matching_breakdown"}
    assert Draft202012Validator(fragment).is_valid(after)


def test_matching_breakdown_rejects_contradictory_status_for_source_record_id():
    """Reject duplicate source record IDs whose stored status decisions conflict.

    Returns:
        None. A record cannot be silently classified under two matching outcomes.
    """
    from survey_combined import build_matching_breakdown

    payload = matching_inventory_payload()
    duplicate = next(item for item in payload["unmatched_so2"]
                     if item["resolution"]["status"] == "unmatched")
    payload["manual_review_matches"].append({
        "record": duplicate["record"],
        "resolution": {**duplicate["resolution"], "status": "review"},
    })
    with pytest.raises(ValueError, match="(?i)contradictory.*S-UNMATCHED-1"):
        build_matching_breakdown(payload)


def test_missing_collection_question_prevents_all_scope_negative_claim():
    """Do not copy a negative answer into another collection lacking the question.

    Returns:
        None. Unanswered scopes stay explicitly unresolved, with no fabricated evidence.
    """
    from survey_combined import reduce_mucp_question
    scopes = {"s1": {"source_record_id": "RESP-001", "kind": "collection"},
              "s2": {"source_record_id": "RESP-001", "kind": "collection"}}
    result = reduce_mucp_question([answer(False)], scopes).data
    assert result["state"] == "incomplete_or_qualified"
    assert result["unreported_scope_ids"] == ("s2",)
    assert len(result["contribution_ids"]) == 1


def test_other_unanswered_source_record_is_not_an_all_scope_negative():
    """Include entirely unanswered MuCP records in source coverage diagnostics.

    Returns:
        None. A second source contributes unknown coverage even without an answer item.
    """
    from survey_combined import reduce_mucp_question
    scopes = {"s1": {"survey": "MuCP", "source_record_id": "RESP-001"},
              "s2": {"survey": "MuCP", "source_record_id": "RESP-002"}}
    assert reduce_mucp_question([answer(False)], scopes).data["state"] == "incomplete_or_qualified"


def test_explicit_workbook_links_deduplicate_scope_claims_not_evidence():
    """Linked representations share an analytical scope only through exact source-row links.

    Returns:
        None. Agreeing duplicates have one scope claim and contradictory duplicates conflict.
    """
    from survey_combined import canonicalize_linked_scopes, reduce_mucp_question
    records = [SourceRecord({"record_id": rid, "survey": "MuCP", "scopes": [{"scope_id": sid, "source_record_id": rid}],
                             "metadata": {"workbook_links": [{"workbook_source_id": "SRC-1", "aggregate_id": 1, "data_rows": [5]}]}})
               for rid, sid in [("RESP-001", "s1"), ("RESP-002", "s2")]]
    scopes = canonicalize_linked_scopes(records)
    assert scopes["s1"]["analytical_scope_id"] == scopes["s2"]["analytical_scope_id"]
    yes1, yes2 = answer(True), answer(True, "s2")
    agreeing = reduce_mucp_question([yes1, yes2], scopes).data
    assert agreeing["analytical_claim_count"] == 1
    assert len(agreeing["contribution_ids"]) == 2
    assert reduce_mucp_question([yes1, answer(False, "s2")], scopes).data["state"] == "conflicting"


@pytest.mark.parametrize("values,expected", [
    ([True], "reported_yes_in_one_or_more_scopes"),
    ([False], "explicitly_no_in_all_reported_applicable_scopes"),
    ([None], "unknown_or_unmarked"),
    ([False, None], "incomplete_or_qualified"),
    ([True, None], "reported_yes_in_one_or_more_scopes"),
    ([True, False], "conflicting_or_scope_uncertain"),
])
def test_mucp_state_truth_table(values, expected):
    """Exercise every basic multi-scope affirmative/negative/unknown reduction.

    Args:
        values: Independent synthetic source assertions with unresolved scope relationships.
        expected: Approved exclusive statistical state for that evidence combination.

    Returns:
        None. Evidence contributors remain intact across all truth-table cases.
    """
    module = importlib.import_module("survey_combined")
    items = [answer(value, f"scope-{index}") for index, value in enumerate(values)]
    result = module.reduce_mucp_question(items, {})
    assert result.data["state"] == expected
    assert len(result.data["contribution_ids"]) == len(values)
