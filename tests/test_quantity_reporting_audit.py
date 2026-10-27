"""Regression oracles for quantity reporting defects found by independent audit."""

from survey_combined_report import render_quantity_contributions, render_modality_quantity_totals
from survey_descriptive import build_mucp_cohort_profile
from survey_mucp_aggregation import aggregate_modality_quantities
from survey_mucp_quantities import extract_modality_quantities
from test_survey_mucp_quantities import DEFINITIONS, table_bank


def test_verified_collection_count_is_not_reported_missing():
    """Count proven table quantities without manufacturing a whole-bank size band.

    Returns:
        None. Collection quantities enter reporting inventories, not bank size bands.
    """
    profile = build_mucp_cohort_profile([table_bank()])["sizes"]["donors"]
    assert profile["biobanks_with_quantity_evidence"] == 1
    assert profile["biobanks_with_scoped_reported_sizes"] == 1
    assert profile["states"]["missing"] == 0
    assert profile["states"]["single_reported_scope"] == 1
    assert sum(profile["size_bands"].values()) == 0


def test_qualified_collection_counts_have_readable_support_and_time():
    """Keep source-proven bounds visibly excluded rather than dropping support rows.

    Returns:
        None. The support table names qualification, time and source quantity.
    """
    bank = table_bank("over 100 (historical)", "greater_than", "historical")
    summary = extract_modality_quantities([bank], DEFINITIONS)
    aggregates = aggregate_modality_quantities(summary, [bank])
    tex = render_quantity_contributions(aggregates, [bank], {})
    assert "100 donors" in tex and "historical" in tex
    assert "Approximate count or bound, not an exact total" in tex or "Historical or future count" in tex
    assert "Eligible source contributions" not in tex
    for excluded in aggregates["excluded_contributions"]:
        excluded.pop("scope_members", None)
    tex = render_quantity_contributions(aggregates, [bank], {})
    assert "Cancer follow-up cohort" in tex
    assert "Reported for this submission" not in tex


def test_rejected_submissions_are_not_called_eligible_contributions():
    """Explain ambiguous source candidates without falsely calling them eligible.

    Returns:
        None. Both source counts survive with their actual view exclusion reason.
    """
    from test_survey_mucp_aggregation import _audit_extract, _quantity

    summary, banks = _audit_extract([
        _quantity("A", "AT", rid, rid, None, 100, ["wgs"],
                  linkage="submission_size_context") for rid in ("R1", "R2")])
    aggregates = aggregate_modality_quantities(summary, banks)
    tex = render_quantity_contributions(aggregates, banks, {})
    assert "Population overlap between submissions unclear" in tex
    assert "Included in" not in tex
    assert "Eligible source contributions" not in tex
    data_row = next(line for line in tex.splitlines() if "[MuCP] 100 donors" in line)
    cells = data_row.split(" & ")
    assert "Population overlap between submissions unclear" in cells[2]
    assert "ambiguous submission scopes" not in cells[3]


def test_totals_exclusions_are_filtered_to_the_exact_reporting_view():
    """Keep reason cardinality aligned with modality, unit, basis and time totals.

    Returns:
        None. A country exclusion and another time/unit do not inflate this row.
    """
    base = {"modality_ids": ["wgs"], "basis": "collection", "unit": "donors",
            "temporal_status": "current", "reason": "covered_by_reporting_ancestor"}
    aggregates = {"modality_definitions": DEFINITIONS, "modality_totals": [{
        "modality_id": "wgs", "basis": "collection", "unit": "donors",
        "temporal_status": "current", "reported_total": 100,
        "contributing_biobanks": 1, "contributing_scopes": 1, "excluded_count": 1}],
        "excluded_contributions": [{**base, "view": "modality"},
            {**base, "view": "country"}, {**base, "view": "modality", "unit": "samples"},
            {**base, "view": "modality", "temporal_status": "historical"}]}
    tex = render_modality_quantity_totals(aggregates, {"modality_definitions": DEFINITIONS})
    assert "current" in tex
    assert "covered by reporting ancestor: 1" in tex
    assert "covered by reporting ancestor: 4" not in tex


def test_hyperlinked_table_names_sort_by_unescaped_human_names():
    """Separate sorting metadata from clickable TeX display labels.

    Returns:
        None. Human alphabetical order wins over dossier hash order.
    """
    from survey_combined_tables import render_biobank_table

    rows = [{"biobank_id": identifier, "country": "DE", "biobank_sort_label": name,
             "biobank_label": rf"\hyperref[dossier-{hash_value}]{{{name}}}", "cells": ["x"]}
            for identifier, name, hash_value in (("ID:Z", "Zulu Bank", "0000"),
                                                ("ID:A", "Alpha Bank", "ffff"))]
    tex = render_biobank_table(rows, "ll", ["Biobank", "Evidence"])
    assert tex.index("Alpha Bank") < tex.index("Zulu Bank")


def test_long_country_panels_have_breakable_page_local_legends(tmp_path):
    """Avoid repeating a full unbreakable cohort legend on every chart page.

    Args:
        tmp_path: Isolated source and PDF directory for legend pagination checks.

    Returns:
        None. Legends paginate with context and contain only the plotted banks.
    """
    from survey_combined_report import render_country_quantity_charts

    banks = [{"biobank_id": f"bank-{i:02d}", "country": f"Country {i:02d}",
              "name": f"Long institute name {i:02d} " * 3} for i in range(37)]
    totals = [{"country": bank["country"], "unit": "donors", "basis": "collection",
               "temporal_status": "current", "reported_total": i + 1,
               "segments": [{"biobank_id": bank["biobank_id"], "value": i + 1,
                             "quantity_ids": [str(i)]}]} for i, bank in enumerate(banks)]
    charts = render_country_quantity_charts({"country_totals": totals}, {"biobanks": banks})
    first = next(iter(charts.values()))
    assert "\\begin{minipage}" not in first
    assert "\\begin{longtable}" in first
    assert "Long institute name 36" not in first
    assert "Reporting-unit segments (continued)" in first
    import shutil
    import pytest
    from so2_descriptive_report import _preamble, _run_xelatex

    if not shutil.which("xelatex"):
        pytest.skip("XeLaTeX is required for legend overflow verification")
    source = tmp_path / "long-legend.tex"
    source.write_text("\n".join([_preamble(), r"\begin{document}", first,
                                 r"\end{document}"]), encoding="utf-8")
    _run_xelatex(source, tmp_path, passes=1)
    assert "Overfull \\vbox" not in source.with_suffix(".log").read_text()
