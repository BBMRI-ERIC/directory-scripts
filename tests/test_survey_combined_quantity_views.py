"""Verify consolidated count charts pool compatible sources, never unlike units."""

import pytest


def test_report_pairs_country_charts_and_folds_dates_without_losing_context():
    """Show two country views per unit while retaining dated gray source descriptions.

    Returns:
        None. Both variants share countries and inclusive bars label confirmed/total.
    """
    from survey_combined_report import render_quantity_chart_views
    banks = [{"biobank_id": "b", "country": "Türkiye", "name": "Bank"}]
    views = {"source_coverage": [], "type_views": [], "country_views": [
        {"kind": "Country", "unit": "donors", "meaning": "collection_context",
         "temporal_status": time, "rows": [{"label": "Türkiye", "reported_total": exact,
          "confirmed_total": exact, "display_total": exact + uncertain, "segments": [
              {"id": "b", "value": exact, "quantity_ids": ["e-" + time], "biobank_ids": ["b"], "uncertain": False},
              {"id": time, "value": uncertain, "quantity_ids": [time], "biobank_ids": ["b"],
               "uncertain": True, "relation": "reported_value", "reasons": ["unconfirmed"]}]}]}
        for time, exact, uncertain in [("unspecified", 10, 0), ("cumulative", 0, 20), ("current", 0, 5)]]}
    rendered = render_quantity_chart_views(views, {"biobanks": banks})
    assert len(rendered) == 2
    confirmed = next(v for k, v in rendered.items() if "confirmed-only" in k)
    inclusive = next(v for k, v in rendered.items() if "inclusive" in k)
    assert "confirmed: 10, total: 35" in inclusive
    assert "mucpUncertainGray" not in confirmed and "mucpUncertainGray" in inclusive
    assert "cumulative" in inclusive and "current" in inclusive
    assert "TR" in inclusive and "Türkiye" not in inclusive
    assert "confirmed: 10, total: 35" not in confirmed


def test_report_country_codes_do_not_change_identity_inputs():
    """Use the requested reporting codes without changing canonical identity evidence.

    Returns:
        None. Country aliases normalize only in the reporting helper.
    """
    from survey_combined_quantity_views import report_country_code
    assert [report_country_code(c) for c in ("Türkiye", "Turkey", "TR", "Montenegro", "ME", "MNE")] == ["TR"] * 3 + ["MNE"] * 3
    assert report_country_code("Unknown") == "Unknown"


def test_date_folding_rejects_partial_overlap_and_deduplicates_complete_overlap():
    """Never drop partially shared source aggregates or count one quantity twice.

    Returns:
        None. Ambiguous partial overlap fails; identical exact/uncertain repeats share one mark.
    """
    from survey_combined_quantity_views import prepare_quantity_report_views
    views = {"country_views": [{"kind": "Country", "unit": "donors", "meaning": "collection_context",
        "temporal_status": time, "rows": [{"label": "CH", "segments": [
            {"id": "b" if not uncertain else "gray", "value": amount, "quantity_ids": qids,
             "biobank_ids": ["b"], "uncertain": uncertain, "reasons": ["unconfirmed"]}]}]}
        for time, amount, qids, uncertain in [("current", 30, ["q1", "q2"], False),
                                              ("cumulative", 50, ["q2", "q3"], False)]]}
    with pytest.raises(ValueError, match="overlap"):
        prepare_quantity_report_views(views)
    for index, view in enumerate(views["country_views"]):
        segment = view["rows"][0]["segments"][0]
        segment.update(value=30, quantity_ids=["q1"], uncertain=bool(index), id="b" if not index else "gray")
    prepared = prepare_quantity_report_views(views)
    row = prepared["country_views"][0]["rows"][0]
    assert row["display_total"] == 30 and row["confirmed_total"] == 0
    assert len(row["segments"]) == 1 and row["segments"][0]["uncertain"]
    assert set(row["segments"][0]["reporting_dates"]) == {"current", "cumulative"}


def test_confirmed_date_context_remains_in_folded_chart_legends():
    """Keep date-qualified confirmed contributions readable without separate panels.

    Returns:
        None. Both original reporting periods appear in the confirmed chart's source context.
    """
    from copy import deepcopy
    from survey_combined_report import render_quantity_chart_views
    views = {"source_coverage": [], "type_views": [], "country_views": [
        {"kind": "Country", "unit": "donors", "meaning": "collection_context", "temporal_status": time,
         "rows": [{"label": "CH", "confirmed_total": amount, "display_total": amount,
                   "reported_total": amount, "segments": [{"id": "b", "value": amount,
                   "quantity_ids": [time], "biobank_ids": ["b"], "uncertain": False}]}]}
        for time, amount in [("unspecified", 5), ("current", 10), ("cumulative", 20)]]}
    options = {"biobanks": [{"biobank_id": "b", "name": "Bank", "country": "CH"}]}
    before = deepcopy(options)
    charts = render_quantity_chart_views(views, options)
    tex = next(t for k, t in charts.items() if "confirmed-only" in k)
    assert "reporting period" in tex and "current" in tex and "cumulative" in tex
    assert options == before


def test_type_chart_reuses_country_legend_across_different_dates():
    """Keep a country legend unique when material rows have different dates.

    Returns:
        None. One type chart renders both material rows and their reporting periods.
    """
    from survey_combined_report import render_quantity_chart_views
    views = {"source_coverage": [], "country_views": [], "type_views": [
        {"kind": "Material type", "unit": "donors", "meaning": "collection_context", "temporal_status": date,
         "rows": [{"label": material, "reported_total": 10, "segments": [{"id": "CH", "value": 10,
                   "quantity_ids": [material], "biobank_ids": ["b"], "uncertain": False}]}]}
        for material, date in [("DNA", "current"), ("Plasma", "cumulative")]]}
    charts = render_quantity_chart_views(views, {"biobanks": [{"biobank_id": "b", "country": "CH", "name": "Bank"}]})
    assert len(charts) == 1
    tex = next(iter(charts.values()))
    assert all(word in tex for word in ("DNA", "Plasma", "current", "cumulative"))


def test_deduplicated_uncertain_width_keeps_all_source_qualifications():
    """Deduplicate one measured amount without discarding its independent qualifications.

    Returns:
        None. Width is retained once while both wording and reason contributions remain.
    """
    from survey_combined_quantity_views import prepare_quantity_report_views
    from survey_combined_report import render_quantity_chart_views
    views = {"source_coverage": [], "type_views": [], "country_views": [
        {"kind": "Country", "unit": "donors", "meaning": "collection_context", "temporal_status": date,
         "rows": [{"label": "CH", "segments": [{"id": date, "value": 10, "quantity_ids": ["q"],
                   "biobank_ids": ["b"], "uncertain": True, "relation": "reported_value",
                   "reasons": [reason], "qualifier_text": wording}]}]}
        for date, reason, wording in [("current", "qualified_relation", "first qualification"),
                                      ("cumulative", "ambiguous_submission_scopes", "second qualification")]]}
    prepared = prepare_quantity_report_views(views)
    row = prepared["country_views"][0]["rows"][0]
    assert row["display_total"] == 10
    assert set(row["segments"][0]["reasons"]) == {"qualified_relation", "ambiguous_submission_scopes"}
    tex = "\n".join(render_quantity_chart_views(views, {"biobanks": [{"biobank_id": "b", "country": "CH", "name": "Bank"}]}).values())
    assert "first qualification" in tex and "second qualification" in tex


def test_deduplicated_width_displays_each_differing_bound():
    """Retain conflicting bound claims explicitly when a physical count repeats.

    Returns:
        None. One width is shown with both original inequality qualifications.
    """
    from survey_combined_report import render_quantity_chart_views
    views = {"source_coverage": [], "type_views": [], "country_views": [
        {"kind": "Country", "unit": "donors", "meaning": "collection_context", "temporal_status": date,
         "rows": [{"label": "CH", "segments": [{"id": date, "value": 10, "quantity_ids": ["q"],
                   "biobank_ids": ["b"], "uncertain": True, "relation": relation,
                   "reasons": ["qualified_relation"]}]}]}
        for date, relation in [("current", "greater_than"), ("cumulative", "less_than")]]}
    tex = "\n".join(render_quantity_chart_views(views, {"biobanks": [{"biobank_id": "b", "country": "CH", "name": "Bank"}]}).values())
    assert "$>$10 donors" in tex and "$<$10 donors" in tex
    assert "Different reported bounds" in tex


def test_same_scope_equal_counts_need_source_identity_proof():
    """Preserve equal measurements with distinct source locators in one scope.

    Returns:
        None. Coincidentally equal counts are not deduplicated without evidence.
    """
    from survey_combined_quantity_views import build_reported_quantity_chart_views
    banks = [{"biobank_id": "b", "country": "DK", "name": "Bank",
              "mucp_source_records": [{"record_id": "r"}]}]
    rows = [{"biobank_id": "b", "source_record_id": "r", "scope_id": "s",
             "unit": "donors", "value": 10, "quantity_ids": [loc],
             "source_refs": [{"source_id": "src", "locator": loc}], "reason": "unconfirmed"}
            for loc in ("p1", "p2")]
    views = build_reported_quantity_chart_views({"excluded_contributions": rows}, banks, [], {})
    assert views["country_views"][0]["rows"][0]["display_total"] == 20
    for row in rows:
        row["source_refs"] = [{"source_id": "src", "locator": "same paragraph"}]
    views = build_reported_quantity_chart_views({"excluded_contributions": rows}, banks, [], {})
    assert views["country_views"][0]["rows"][0]["display_total"] == 20


def test_unclear_unit_legend_preserves_source_wording_and_qualifications():
    """Retain the source unit and qualification in an unclear-unit gray legend.

    Returns:
        None. Human readers can identify what the uncertain number describes.
    """
    from survey_combined_quantity_views import build_reported_quantity_chart_views
    from survey_combined_report import render_quantity_chart_views
    banks = [{"biobank_id": "b", "country": "DK", "name": "Bank",
              "mucp_source_records": [{"record_id": "r"}]}]
    q = {"biobank_id": "b", "source_record_id": "r", "scope_id": "s",
         "unit": "unit_unclear", "source_unit": "pets", "value": 219,
         "raw_text": "219 pets", "qualifier_text": "mainly cats and dogs"}
    views = build_reported_quantity_chart_views({}, banks, [], {"sizes": {"unit_unclear": {"rows": [q]}}})
    tex = "\n".join(render_quantity_chart_views(views, {"biobanks": banks}).values())
    assert "pets" in tex and "mainly cats and dogs" in tex


def test_missing_count_roster_preserves_response_multiplicity():
    """Expose repeated missing-count responses without repeating institution names.

    Returns:
        None. The compact roster reports two responses rather than silently one.
    """
    from survey_combined_report import render_quantity_source_coverage
    rows = [{"country": "DK", "institution": "Bank", "status": "count_not_reported",
             "source_record_id": rid} for rid in ("r1", "r2")]
    tex = render_quantity_source_coverage({"source_coverage": rows}, {})
    assert "2 responses" in tex


def test_reviewed_profile_copy_uses_measurement_evidence_identity():
    """Link a reviewed profile copy by its hash-bound measurement, not paragraph.

    Returns:
        None. The aggregate and reviewed profile display one amount with provenance.
    """
    from survey_evidence import fingerprint
    from survey_combined_quantity_views import build_reported_quantity_chart_views
    reviewed = {"value": 73000, "unit": "donors", "scope_id": "s",
                "scope_label": "submission", "measurement_label": "blood donors",
                "original_wording": "73000 blood donors", "question_id": "B.count"}
    banks = [{"biobank_id": "b", "country": "FI", "name": "Bank",
              "mucp_source_records": [{"record_id": "r", "metadata": {"reviewed_quantities": [reviewed]}}]}]
    quantity = {"biobank_id": "b", "source_record_id": "r", "scope_id": "s",
                "unit": "donors", "value": 73000, "quantity_ids": ["q"],
                "quantity_evidence_ids": ["reviewed_quantity:" + fingerprint(reviewed)], "reason": "unconfirmed"}
    profile = {**reviewed, "biobank_id": "b", "source_record_id": "r", "scope_label": "blood donors"}
    views = build_reported_quantity_chart_views({"excluded_contributions": [quantity]}, banks, [],
                                              {"sizes": {"donors": {"rows": [profile]}}})
    assert views["country_views"][0]["rows"][0]["display_total"] == 73000
    assert len(views["country_views"][0]["rows"][0]["segments"]) == 1


def test_inventory_numbers_are_not_counts_and_distinct_scopes_remain():
    """Keep incidental numeric text outside bars and equal different scopes distinct.

    Returns:
        None. Ages/codes remain in the inventory and source coverage, not bar widths.
    """
    from survey_combined_quantity_views import build_reported_quantity_chart_views
    banks = [{"biobank_id": "b", "country": "DK", "name": "Bank",
              "mucp_source_records": [{"record_id": "r"}, {"record_id": "age"}]}]
    base = {"biobank_id": "b", "source_record_id": "r", "unit": "donors",
            "value": 20, "kind": "unverified_scoped_quantity"}
    rows = [{**base, "scope_id": scope} for scope in ("first", "second")]
    incidental = {**base, "source_record_id": "age", "unit": "unit_unclear",
                  "value": 19, "raw_text": "COVID-19", "kind": "numeric_mention_not_additive"}
    views = build_reported_quantity_chart_views({}, banks, [], {
        "sizes": {"donors": {"rows": rows}, "unit_unclear": {"rows": [incidental]}}})
    assert len(views["country_views"]) == 1
    assert views["country_views"][0]["rows"][0]["display_total"] == 40
    assert len(views["country_views"][0]["rows"][0]["segments"]) == 2
    assert views["uninterpreted_answers"] == [incidental]
    assert next(r for r in views["source_coverage"] if r["source_record_id"] == "age")["status"] == "numeric_answer_needs_interpretation"


def test_eligible_but_view_excluded_quantity_is_displayed_once():
    """Retain eligible measurements omitted by later country reconciliation in gray.

    Returns:
        None. Internal eligibility does not substitute for actual chart attribution.
    """
    from survey_combined_quantity_views import build_reported_quantity_chart_views
    banks = [{"biobank_id": "b", "country": "DK", "name": "Bank",
              "mucp_source_records": [{"record_id": "r"}]}]
    q = {"biobank_id": "b", "source_record_id": "r", "scope_id": "s",
         "unit": "donors", "value": 10, "quantity_ids": ["q"], "basis": "submission_fallback"}
    excluded = {**q, "reason": "collection_counts_preferred", "view": "country"}
    views = build_reported_quantity_chart_views({"contributions": [q],
        "excluded_contributions": [excluded]}, banks, [], {"sizes": {}})
    assert views["country_views"][0]["rows"][0]["uncertain_total"] == 10
    views = build_reported_quantity_chart_views({"contributions": [q],
        "country_totals": [total("DK", "b", 10, qid="q")],
        "excluded_contributions": [excluded]}, banks, [], {"sizes": {}})
    assert views["country_views"][0]["rows"][0]["display_total"] == 10
    assert views["country_views"][0]["rows"][0]["uncertain_total"] == 0


def test_uncertain_sources_join_country_stacks_without_changing_exact_totals():
    """Display all source counts while preserving the audited exact subtotal.

    Returns:
        None. Denmark includes distinct gray scopes and agreeing repeats only once.
    """
    from survey_combined_quantity_views import build_reported_quantity_chart_views
    banks = [{"biobank_id": "D", "name": "Danish bank", "country": "DK",
              "mucp_source_records": [{"record_id": "r"}, {"record_id": "missing"}]}]
    excluded = [{"biobank_id": "D", "source_record_id": "r", "scope_id": "s",
                 "value": value, "unit": "donors", "relation": relation,
                 "temporal_status": "unspecified", "basis": "submission_fallback",
                 "reason": "same_scope_conflicting_quantities", "quantity_ids": [qid], "modality_ids": ["dna"]}
                for value, relation, qid in [(6000000, "reported_value", "b"), (2000000, "at_least", "c")]]
    aggregates = {"country_totals": [], "modality_totals": [], "excluded_contributions": excluded + [dict(excluded[1])]}
    profile = {"sizes": {"donors": {"rows": []}}}
    views = build_reported_quantity_chart_views(aggregates, banks,
        [{"id": "dna", "label": "DNA", "kind": "biospecimen"}], profile)
    row = views["country_views"][0]["rows"][0]
    assert row["label"] == "DK" and row["display_total"] == 8000000
    assert row["confirmed_total"] == 0 and row["uncertain_total"] == 8000000
    assert len(row["segments"]) == 2 and all(s["uncertain"] for s in row["segments"])
    assert {s["relation"] for s in row["segments"]} == {"reported_value", "at_least"}
    assert next(r for r in views["source_coverage"] if r["source_record_id"] == "missing")["status"] == "count_not_reported"
    assert aggregates["country_totals"] == []


def test_unknown_units_and_unlinked_counts_remain_separate():
    """Retain unlinked sources without turning unknown units into donor counts.

    Returns:
        None. A typed unlinked count and an unclear-unit number use separate panels.
    """
    from survey_combined_quantity_views import build_reported_quantity_chart_views
    banks = [{"biobank_id": "b", "country": "DK", "name": "Bank",
              "mucp_source_records": [{"record_id": "r"}]}]
    rows = [{"biobank_id": "b", "source_record_id": "r", "scope_id": "s", "value": n,
             "unit": u, "relation": "approximate", "kind": "unverified_scoped_quantity",
             "source_refs": [{"source_id": "src", "locator": loc}], "question_id": "B.count"}
            for n, u, loc in [(500, "donors", "p1"), (300, "unit_unclear", "p2")]]
    profile = {"sizes": {u: {"rows": [r for r in rows if r["unit"] == u]} for u in ("donors", "unit_unclear")}}
    views = build_reported_quantity_chart_views({}, banks, [], profile)
    assert {v["unit"] for v in views["country_views"]} == {"donors", "unit_unclear"}
    assert views["type_views"] == []
    assert all(s["uncertain"] for v in views["country_views"] for r in v["rows"] for s in r["segments"])


def test_confirmed_quantity_does_not_reappear_from_profile():
    """Deduplicate source-local profile evidence already represented by an exact segment.

    Returns:
        None. The typed count remains colored and the profile copy adds no gray width.
    """
    from survey_combined_quantity_views import build_reported_quantity_chart_views
    banks = [{"biobank_id": "b", "country": "FI", "name": "Bank", "mucp_source_records": [{"record_id": "r"}]}]
    aggregate = total("FI", "b", 73000, qid="q")
    contribution = {"biobank_id": "b", "source_record_id": "r", "scope_id": "s", "value": 73000,
                    "unit": "donors", "relation": "reported_value", "temporal_status": "unspecified",
                    "quantity_ids": ["q"], "source_refs": [{"source_id": "src", "locator": "p1"}]}
    profile = {"sizes": {"donors": {"rows": [{**contribution, "raw_text": "73000 donors"}]}}}
    views = build_reported_quantity_chart_views({"country_totals": [aggregate], "contributions": [contribution]}, banks, [], profile)
    row = views["country_views"][0]["rows"][0]
    assert row["confirmed_total"] == row["display_total"] == 73000
    assert row["uncertain_total"] == 0 and len(row["segments"]) == 1


def test_main_stacks_use_gray_and_mark_unconfirmed_display_total():
    """Render uncertain contributions in the main linear chart rather than separate dots.

    Returns:
        None. Legend qualifiers and gray-fill identity are present beside confirmed values.
    """
    from survey_combined_quantity_views import build_reported_quantity_chart_views
    from survey_combined_report import render_quantity_chart_views
    banks = [{"biobank_id": "b", "country": "DK", "name": "Danish bank", "mucp_source_records": [{"record_id": "r"}]}]
    excluded = {"biobank_id": "b", "source_record_id": "r", "scope_id": "s", "value": 150000,
                "unit": "donors", "relation": "greater_than", "temporal_status": "unspecified",
                "basis": "submission_fallback", "reason": "qualified_relation", "quantity_ids": ["q"], "modality_ids": []}
    views = build_reported_quantity_chart_views({"excluded_contributions": [excluded]}, banks, [], {"sizes": {}})
    tex = "\n".join(render_quantity_chart_views(views, {"biobanks": banks}).values())
    assert "DK" in tex and "Danish bank" in tex and "150000" in tex
    assert "uncertain" in tex.casefold() and "not a verified total" in tex
    assert "gray" in tex and "$>$" in tex
    assert "xmode=log" not in tex


def total(country, bank, value, unit="donors", basis="collection", qid=None, type_id=None):
    """Create one previously reconciled total with exact source attribution.

    Args:
        country: Country grouping label.
        bank: Canonical bank identifier.
        value: Exact reported count.
        unit: Donors, samples or aliquots.
        basis: Collection, submission_fallback or direct_modality.
        qid: Optional unique source quantity identifier.
        type_id: Optional material/data type identifier for a type total.

    Returns:
        Audited summary-shaped fixture containing one biobank segment.
    """
    return {("modality_id" if type_id else "country"): type_id or country,
            "unit": unit, "basis": basis, "temporal_status": "unspecified", "reported_total": value,
            "contributing_biobanks": 1, "contributing_scopes": 1, "excluded_count": 0,
            "segments": [{"biobank_id": bank, "value": value, "quantity_ids": [qid or bank + unit]}]}


def test_country_sources_are_pooled_without_mixing_units():
    """Combine compatible countries/sources into one country view per count unit.

    Returns:
        None. Excluded overlapping fallback counts never enter exact stacks.
    """
    from survey_combined_quantity_views import build_quantity_chart_views
    banks = [{"biobank_id": bid, "name": bid, "country": country} for bid, country in (("A", "IT"), ("B", "IT"), ("C", "CZ"))]
    aggregates = {"country_totals": [total("IT", "A", 10), total("IT", "B", 20, basis="submission_fallback"),
                                     total("CZ", "C", 5), total("IT", "A", 7, unit="samples")],
                  "modality_totals": [], "excluded_contributions": [{"value": 100, "reason": "collection_counts_preferred"}]}
    views = build_quantity_chart_views(aggregates, banks, [])
    donors = next(v for v in views["country_views"] if v["unit"] == "donors")
    assert {r["label"]: r["reported_total"] for r in donors["rows"]} == {"CZ": 5, "IT": 30}
    assert len(views["country_views"]) == 2


def test_all_material_types_share_linear_graph():
    """Show all materials together while retaining country stacks and separate units.

    Returns:
        None. Type charts emit one consolidated linear material graph.
    """
    from survey_combined_quantity_views import build_quantity_chart_views
    from survey_combined_report import render_quantity_chart_views
    banks = [{"biobank_id": bid, "name": bid, "country": cc} for bid, cc in (("A", "IT"), ("B", "CZ"))]
    defs = [{"id": "dna", "label": "DNA", "kind": "biospecimen"}, {"id": "plasma", "label": "Plasma", "kind": "biospecimen"}]
    aggregates = {"country_totals": [], "modality_totals": [total("IT", "A", 10, type_id="dna"),
                    total("CZ", "B", 5, type_id="dna"), total("IT", "A", 10, type_id="plasma")], "excluded_contributions": []}
    views = build_quantity_chart_views(aggregates, banks, defs)
    assert len(views["type_views"]) == 1
    rendered = render_quantity_chart_views(views, {"biobanks": banks})
    assert len(rendered) == 1
    tex = next(iter(rendered.values()))
    assert "DNA" in tex and "Plasma" in tex and "IT" in tex and "CZ" in tex
    assert "xmode=normal" in tex and "xmode=log" not in tex
    assert "( donors" not in tex


def test_duplicate_count_attribution_is_rejected():
    """Fail rather than double-add a source quantity across count bases.

    Returns:
        None. Reused quantity IDs inside a country view are rejected.
    """
    from survey_combined_quantity_views import build_quantity_chart_views
    a = total("IT", "A", 10)
    with pytest.raises(ValueError, match="duplicate|overlap"):
        build_quantity_chart_views({"country_totals": [a, {**a, "basis": "submission_fallback"}], "modality_totals": []},
                                   [{"biobank_id": "A", "name": "A", "country": "IT"}], [])


def test_same_bank_collection_and_fallback_cannot_be_pooled():
    """Reject distinct source IDs that overlap at collection/fallback bank level.

    Returns:
        None. Different source identifiers do not establish independent counts.
    """
    from survey_combined_quantity_views import build_quantity_chart_views
    with pytest.raises(ValueError, match="overlap"):
        build_quantity_chart_views(
            {"country_totals": [total("IT", "A", 10, qid="collection"),
                                total("IT", "A", 20, basis="submission_fallback", qid="whole-bank")]},
            [{"biobank_id": "A", "name": "A", "country": "IT"}], [])
