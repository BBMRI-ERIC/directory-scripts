"""Test source-preserving survey participation counts independently of rendering."""

import copy
from types import SimpleNamespace

import pytest
from hypothesis import given, strategies as st


def sources():
    """Build invented deduplicated SO2 and complete MuCP source inventories.

    Returns:
        Descriptive and combined payloads with one shared and two SO2-only units.
    """
    so2 = {"provenance": {"source_sha256": "a" * 64, "worksheet": "Content"},
           "responses_summary": {"source_records": [
               {"source_row": i, "answers": {"Country": "Austria"}} for i in (5, 6, 7, 8)],
               "country_corrections": [], "observation_sources": [
                   {"source_rows": [5, 6], "biobank_id": "bbmri-eric:ID:AT_A"},
                   {"source_rows": [7], "biobank_id": None},
                   {"source_rows": [8], "biobank_id": None}]}}
    record = {"record_id": "R1", "survey": "MuCP", "country": "AT", "record_type": "submission",
              "scopes": [{"scope_id": "c1", "kind": "collection"}, {"scope_id": "c2", "kind": "collection"}]}
    other = {"record_id": "R2", "survey": "MuCP", "country": "AT", "record_type": "submission"}
    combined = {"inputs": {"so2_sha256": "a" * 64, "mucp_sha256": "b" * 64},
                "metadata": {"mucp_source_coverage": {"input_records": 2}},
                "biobanks": [{"biobank_id": "bbmri-eric:ID:AT_A", "country": "AT",
                    "mucp_source_records": [record], "identity_resolutions": [
                        {"source_record_id": "R1", "status": "accepted", "biobank_id": "bbmri-eric:ID:AT_A"}]}],
                "unmatched_mucp": [{"record": other, "resolution": {"source_record_id": "R2", "status": "unmatched"}}]}
    return so2, combined


def inventory(count=5):
    """Create an invented frozen Directory with a known reported-country total.

    Args:
        count: Number of Austrian biobanks, including an EXT-staged biobank.

    Returns:
        Exported inventory envelope from the production Directory adapter.
    """
    from survey_participation import directory_inventory
    records = [{"id": "bbmri-eric:ID:AT_A", "country": "AT", "withdrawn": False}] if count else []
    records += [{"id": f"bbmri-eric:ID:EXT_{i}", "country": "AT", "withdrawn": False} for i in range(count - 1)]
    directory = SimpleNamespace(getBiobanks=lambda: records, getDirectoryUrl=lambda: "https://example.test",
                                getSchema=lambda: "ERIC", include_withdrawn_entities=False,
                                only_withdrawn_entities=False)
    return directory_inventory(directory)


def test_counts_include_unresolved_without_counting_scopes():
    """Count one shared biobank, unresolved individuals and no extra scopes.

    Returns:
        None. Counts are D=5/S=3/M=2/B=1 with source lineage retained.
    """
    from survey_participation import collect_participation, build_country_counts
    so2, combined = sources()
    data = collect_participation(so2, combined)
    row = build_country_counts(data, inventory())["countries"][0]
    assert [row[k] for k in ("directory_count", "so2_count", "mucp_count", "shared_count")] == [5, 3, 2, 1]
    assert row["so2_percent"] == 60
    assert row["so2_provisional_count"] == 2
    assert sum(len(u["source_refs"]) for u in data["units"]) == 6


@pytest.mark.parametrize("denominator,expected", [(2, 150), (0, None)])
def test_ratios_are_not_clamped(denominator, expected):
    """Retain percentages above 100 and distinguish an undefined denominator.

    Args:
        denominator: Directory biobank count for the respondent country.
        expected: Required percentage, or None when division is undefined.

    Returns:
        None. The respondent count always remains three.
    """
    from survey_participation import collect_participation, build_country_counts
    so2, _ = sources()
    row = build_country_counts(collect_participation(so2), inventory(denominator))["countries"][0]
    assert row["so2_count"] == 3 and row["so2_percent"] == expected


def test_zero_responses_and_unknown_country_remain_distinct():
    """Keep unassigned respondents out of invented country bars without dropping them.

    Returns:
        None. Known inventory zeroes differ from the unknown-country audit.
    """
    from survey_participation import collect_participation, build_country_counts
    so2, _ = sources()
    for item in so2["responses_summary"]["source_records"]:
        item["answers"]["Country"] = "??"
    so2["responses_summary"]["observation_sources"][0]["biobank_id"] = None
    counts = build_country_counts(collect_participation(so2), inventory())
    assert counts["countries"][0]["so2_percent"] == 0
    assert counts["unknown_country"]["so2_count"] == 3


def test_summary_only_counts_identifiable_decomposed_biobanks():
    """A national summary contributes zero unless its biobanks are identified.

    Returns:
        None. Two reviewed constituents count twice, not once per source appearance.
    """
    from survey_participation import collect_participation, build_country_counts
    so2, combined = sources()
    summary = {"record_id": "N", "survey": "MuCP", "country": "AT", "record_type": "country_summary",
               "scopes": [{"scope_id": "n1", "kind": "collection"}, {"scope_id": "n2", "kind": "collection"}]}
    combined["unmatched_mucp"] = [{"record": summary, "resolution": {"status": "unmatched"}}]
    before = collect_participation(so2, combined)
    assert build_country_counts(before, inventory())["countries"][0]["mucp_count"] == 1
    review = {"schema_version": 1, "inputs": {"so2": "a" * 64, "mucp": "b" * 64}, "groups": [
        {"unit_id": "bbmri-eric:ID:AT_A", "country": "AT", "reason": "Reviewed same biobank", "sources": [
            {"survey": "MuCP", "record_id": "N", "scope_id": "n1"}, {"survey": "MuCP", "record_id": "R1"}]},
        {"unit_id": "reviewed-other", "country": "AT", "reason": "Reviewed separate biobank", "sources": [
            {"survey": "MuCP", "record_id": "N", "scope_id": "n2"}]}]}
    after = collect_participation(so2, combined, review)
    assert build_country_counts(after, inventory())["countries"][0]["mucp_count"] == 2
    assert after["national_summaries"][0]["record_id"] == "N"


def test_source_identity_review_is_hash_bound():
    """Reject a reviewed roster for another input rather than changing counts.

    Returns:
        None. Stale review decisions fail before a usable roster is returned.
    """
    from survey_participation import collect_participation
    so2, combined = sources()
    with pytest.raises(ValueError, match="source"):
        collect_participation(so2, combined, {"schema_version": 1, "inputs": {"so2": "wrong"}, "groups": []})


def test_full_inventory_and_unusual_countries_are_not_silently_omitted():
    """Reject partial historical cohorts and retain valid non-European countries.

    Returns:
        None. Explicit inventory coverage and country names are interpreted honestly.
    """
    from survey_participation import collect_participation, map_country
    assert map_country("NA") == "NA"
    assert map_country("Montenegro") == "ME"
    assert map_country("Qatar") == "QA"
    so2, combined = sources()
    combined["metadata"] = {"mucp_source_coverage": {"input_records": 3}}
    with pytest.raises(ValueError, match="inventory"):
        collect_participation(so2, combined)


def test_duplicate_record_conflicts_fail_and_join_does_not_filter():
    """Count full matching inventories, but reject contradictory copies of a source.

    Returns:
        None. Cohort join metadata cannot alter the source-based participation hash.
    """
    from survey_participation import collect_participation, participation_binding
    so2, combined = sources()
    expected = participation_binding(collect_participation(so2, combined))
    combined["metadata"]["cohort"] = {"join": "inner", "selected_ids": []}
    assert participation_binding(collect_participation(so2, combined)) == expected
    combined["manual_review_matches"] = [copy.deepcopy(combined["unmatched_mucp"][0])]
    combined["manual_review_matches"][0]["record"]["country"] = "IT"
    with pytest.raises(ValueError, match="Conflicting"):
        collect_participation(so2, combined)


@pytest.mark.parametrize("join", ["inner", "all-MuCP", "all-SO2", "outer"])
def test_join_repartition_cannot_remove_mucp_only_respondents(join):
    """Retain accepted MuCP-only identities wherever the selected join stores them.

    Args:
        join: Combined-cohort policy moving MuCP-only records into or out of bank groups.

    Returns:
        None. Full-survey country counts and canonical bindings remain identical.
    """
    from survey_participation import collect_participation, participation_binding, build_country_counts
    so2, combined = sources()
    extra = combined["unmatched_mucp"][0]
    extra["resolution"].update(status="accepted", biobank_id="bbmri-eric:ID:AT_B")
    expected = participation_binding(collect_participation(so2, combined))
    combined["metadata"]["cohort"] = {"join": join}
    if join in {"all-MuCP", "outer"}:
        combined["biobanks"].append({"biobank_id": "bbmri-eric:ID:AT_B",
            "mucp_source_records": [extra["record"]], "identity_resolutions": [extra["resolution"]]})
        combined["unmatched_mucp"] = []
    roster = collect_participation(so2, combined)
    assert participation_binding(roster) == expected
    row = build_country_counts(roster, inventory())["countries"][0]
    assert [row[k] for k in ("so2_count", "mucp_count", "shared_count")] == [3, 2, 1]


def test_review_cannot_split_a_known_directory_identity():
    """A local review label must not duplicate an already identified biobank.

    Returns:
        None. Reviewed groups containing a known ID must use that canonical ID.
    """
    from survey_participation import collect_participation
    so2, combined = sources()
    review = {"schema_version": 1, "inputs": {"so2": "a" * 64, "mucp": "b" * 64}, "groups": [
        {"unit_id": "invented-local-alias", "reason": "Duplicate identity candidate", "country": "AT",
         "sources": [{"survey": "SO2", "record_id": "so2:Content:row:5"}]}]}
    with pytest.raises(ValueError, match="canonical"):
        collect_participation(so2, combined, review)


def test_missing_coverage_requires_regeneration():
    """Reject historical selected-cohort payloads without completeness evidence.

    Returns:
        None. A source hash alone cannot establish complete MuCP coverage.
    """
    from survey_participation import collect_participation
    so2, combined = sources()
    del combined["metadata"]
    with pytest.raises(ValueError, match="complete MuCP inventory"):
        collect_participation(so2, combined)


def test_residual_and_reviewed_scopes_do_not_fabricate_extra_biobanks():
    """Count projected/reviewed owners once while retaining residual evidence.

    Returns:
        None. A decomposed source does not also count as an unresolved biobank.
    """
    from survey_participation import collect_participation, build_country_counts
    so2, combined = sources()
    original = combined["unmatched_mucp"][0]["record"]
    original["scopes"] = [{"scope_id": "owned", "kind": "collection"}]
    projection = copy.deepcopy(original)
    projection.update(record_id="P", source_response_id="R2", record_type="scope_projection")
    combined["biobanks"][0]["mucp_source_records"].append(projection)
    combined["metadata"]["mucp_source_coverage"]["input_records"] = 3
    counts = build_country_counts(collect_participation(so2, combined), inventory())
    assert counts["countries"][0]["mucp_count"] == 1
    combined["biobanks"][0]["mucp_source_records"].pop()
    combined["metadata"]["mucp_source_coverage"]["input_records"] = 2
    review = {"schema_version": 1, "inputs": {"so2": "a" * 64, "mucp": "b" * 64}, "groups": [
        {"unit_id": "bbmri-eric:ID:AT_A", "country": "AT", "reason": "Owned collection", "sources": [
            {"survey": "MuCP", "record_id": "R2", "scope_id": "owned"}]}]}
    counts = build_country_counts(collect_participation(so2, combined, review), inventory())
    assert counts["countries"][0]["mucp_count"] == 1


def test_mucp_country_does_not_change_frozen_so2_country():
    """Preserve source-survey geography and audit a shared country disagreement.

    Returns:
        None. SO2 bindings/counts stay stable even outside the denominator snapshot.
    """
    from survey_participation import collect_participation, participation_binding, build_country_counts
    so2, combined = sources()
    combined["biobanks"][0]["mucp_source_records"][0]["country"] = "IT"
    standalone = collect_participation(so2)
    shared = collect_participation(so2, combined)
    assert participation_binding(standalone, "SO2") == participation_binding(shared, "SO2")
    counts = build_country_counts(shared, inventory(0))
    by_country = {r["country"]: r for r in counts["countries"]}
    assert by_country["AT"]["so2_count"] == 3
    assert by_country["IT"]["mucp_count"] == 1
    assert counts["unknown_country"]["shared_count"] == 0
    assert counts["shared_country_conflicts"] == [{"unit_id": "bbmri-eric:ID:AT_A", "countries": {"SO2": "AT", "MuCP": "IT"}}]


def test_rejected_projection_retains_evidence_without_counting_a_scope_as_a_bank():
    """An unassigned projected collection is not a newly identified biobank.

    Returns:
        None. Rejected scope evidence adds no provisional or national biobank count.
    """
    from survey_participation import collect_participation, build_country_counts
    so2, combined = sources()
    source = combined["unmatched_mucp"][0]
    source["record"].update(record_type="scope_projection", source_response_id="ROOT")
    source["resolution"]["status"] = "rejected"
    counts = build_country_counts(collect_participation(so2, combined), inventory())
    assert counts["countries"][0]["mucp_count"] == 1


@pytest.mark.parametrize("invalid", ["duplicate", "missing-country"])
def test_invalid_so2_source_ownership_is_not_silently_normalized(invalid):
    """Reject lost source rows or absent country columns before counting.

    Args:
        invalid: Source-row defect whose normalization could silently discard evidence.

    Returns:
        None. Malformed inventories produce an actionable validation error.
    """
    from survey_participation import collect_participation
    so2, _ = sources()
    records = so2["responses_summary"]["source_records"]
    if invalid == "duplicate":
        records.append(copy.deepcopy(records[0]))
    else:
        del records[0]["answers"]["Country"]
    with pytest.raises(ValueError, match="source rows|Country"):
        collect_participation(so2)


@pytest.mark.parametrize("national", [False, True])
def test_rejected_only_projections_preserve_individual_but_not_national_counts(national):
    """Rejected collection assignments cannot erase an individual questionnaire.

    Args:
        national: Whether the original response is a non-countable national summary.

    Returns:
        None. Individual roots count once; national roots and rejected scopes count zero.
    """
    from survey_participation import collect_participation, build_country_counts
    so2, combined = sources()
    source = combined["unmatched_mucp"][0]
    source["record"]["record_type"] = "country_summary" if national else "submission"
    projected = copy.deepcopy(source)
    projected["record"].update(record_id="P", source_response_id="R2", record_type="scope_projection",
                               original_record_type=source["record"]["record_type"])
    projected["resolution"].update(source_record_id="P", status="rejected")
    combined["excluded_source_records"] = [projected]
    combined["metadata"]["mucp_source_coverage"]["input_records"] = 3
    counts = build_country_counts(collect_participation(so2, combined), inventory())
    assert counts["countries"][0]["mucp_count"] == (1 if national else 2)


def test_mucp_only_review_cannot_override_so2_country():
    """Apply a reviewed MuCP correction only to its contributing survey evidence.

    Returns:
        None. Identical SO2 bindings/counts survive the same review in both exports.
    """
    from survey_participation import collect_participation, participation_binding, build_country_counts
    so2, combined = sources()
    review = {"schema_version": 1, "inputs": {"so2": "a" * 64, "mucp": "b" * 64}, "groups": [
        {"unit_id": "bbmri-eric:ID:AT_A", "country": "IT", "reason": "MuCP country correction", "sources": [
            {"survey": "MuCP", "record_id": "R1"}]}]}
    standalone = collect_participation(so2, identities=review)
    shared = collect_participation(so2, combined, review)
    assert participation_binding(standalone, "SO2") == participation_binding(shared, "SO2")
    counts = build_country_counts(shared, inventory())
    by_country = {row["country"]: row for row in counts["countries"]}
    assert by_country["AT"]["so2_count"] == 3 and by_country["IT"]["mucp_count"] == 1


def test_reviewed_shared_identity_has_same_so2_binding_in_both_exports():
    """An explicitly reviewed link must not silently change SO2 grouping by report kind.

    Returns:
        None. Per-SO2 identity material is identical with and without MuCP records.
    """
    from survey_participation import collect_participation, participation_binding
    so2, combined = sources()
    review = {"schema_version": 1, "inputs": {"so2": "a" * 64, "mucp": "b" * 64}, "groups": [
        {"unit_id": "bbmri-eric:ID:AT_B", "country": "AT", "reason": "Reviewed explicit source linkage", "sources": [
            {"survey": "SO2", "record_id": "so2:Content:row:7"}, {"survey": "MuCP", "record_id": "R2"}]}]}
    combined["unmatched_mucp"][0]["resolution"].update(status="accepted",biobank_id="bbmri-eric:ID:AT_B")
    assert participation_binding(collect_participation(so2, identities=review), "SO2") == \
        participation_binding(collect_participation(so2, combined, review), "SO2")


@given(st.permutations([5, 6, 7, 8]))
def test_source_order_does_not_change_counts(order):
    """Make reproducible bindings independent of source-record ordering.

    Args:
        order: Permutation of four physical worksheet row identifiers.

    Returns:
        None. Canonical bindings are unchanged by input order.
    """
    from survey_participation import collect_participation, participation_binding
    so2, combined = sources()
    expected = participation_binding(collect_participation(so2, combined))
    rows = so2["responses_summary"]["source_records"]
    so2["responses_summary"]["source_records"] = [next(r for r in rows if r["source_row"] == i) for i in order]
    assert participation_binding(collect_participation(so2, combined)) == expected
