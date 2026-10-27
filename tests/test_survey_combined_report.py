"""Regression tests for combined survey dossier and report composition."""

import importlib
import shutil
import tempfile

import pytest


combined = importlib.import_module("survey_combined_report")
upsets = importlib.import_module("so2_descriptive_upsets")


def test_reader_first_layout_links_free_text_evidence_after_all_statistics():
    """Defer response tables without losing their provenance or changing describe defaults.

    Returns:
        None. Detailed evidence follows charts and precedes optional appendices.
    """
    payload = minimal_payload()
    question = payload["descriptive_statistics"]["SO2"]["questions"][0]
    question.update(question_type="free_text", free_text_rows=[
        {"country": "Montenegro", "institution": "Unique institution",
         "text": "Unique narrative retained", "observation_id": "b"}])
    tex = combined.render_combined_tex(payload, {}).tex
    boundary = tex.index(r"\section{Detailed evidence}")
    assert tex.index(r"\section{SO2}") < boundary < tex.index(r"\appendix")
    assert "Unique narrative retained" not in tex[:boundary]
    assert "Unique narrative retained" in tex[boundary:]
    assert r"\hyperref[evidence-" in tex[:boundary] and r"\label{evidence-" in tex[boundary:]
    assert "MNE" in tex[boundary:]
    assert r"\section{Biobank evidence dossiers}" not in tex


def test_generic_statistics_deferral_is_opt_in_and_retains_all_response_text():
    """Keep standalone describe's evidence placement unchanged unless requested.

    Returns:
        None. Deferral is reversible, source text is retained and defaults stay inline.
    """
    from copy import deepcopy
    from so2_descriptive_report import render_statistics_sections
    question = minimal_payload()["descriptive_statistics"]["SO2"]["questions"][0]
    question.update(question_type="free_text", free_text_rows=[
        {"country": "AT", "institution": "Bank", "text": "Full response retained"}])
    sections = [{"survey": "SO2", "questions": [question]}]
    before = deepcopy(sections)
    inline = render_statistics_sections(sections, {})
    deferred = render_statistics_sections(sections, {"defer_evidence_tables": True})
    assert "Full response retained" in inline.tex and not inline.evidence_fragments
    assert "Full response retained" not in deferred.tex
    assert "Full response retained" in "\n".join(deferred.evidence_fragments.values())
    assert sections == before


def test_report_country_copy_preserves_hash_bound_source_answers():
    """Normalize display countries without rewriting embedded original answer objects.

    Returns:
        None. Raw responses and provenance metadata retain their exact source values.
    """
    from copy import deepcopy
    payload = {"country": "Türkiye", "raw_answer": {"country": "Türkiye"},
               "metadata": {"original_response": {"country": "Montenegro"}},
               "mucp_source_records": [{"record_id": "r", "country": "Czech Republic"}],
               "so2_source_records": [{"record_id": "s", "country": "Montenegro"}],
               "unmatched_mucp": [{"record": {"record_id": "u", "country": "Türkiye"}}]}
    before = deepcopy(payload)
    rendered = combined._report_country_copy(payload)
    assert rendered["country"] == "TR"
    assert rendered["raw_answer"] == before["raw_answer"]
    assert rendered["metadata"] == before["metadata"]
    assert rendered["mucp_source_records"] == before["mucp_source_records"]
    assert rendered["so2_source_records"] == before["so2_source_records"]
    assert rendered["unmatched_mucp"] == before["unmatched_mucp"]
    assert payload == before


def test_part_a_context_is_retained_without_extra_major_toc_section():
    """Place institution submission context in evidence, not an extra main survey part.

    Returns:
        None. Part A narrative survives and the approved main-section order is intact.
    """
    from copy import deepcopy
    payload = minimal_payload()
    q = deepcopy(payload["descriptive_statistics"]["SO2"]["questions"][0])
    q.update(part="A", question_id="A.institution", label="Name of biobank and institution",
             question_type="free_text", free_text_rows=[{"country": "TR", "institution": "Bank",
                                                        "text": "Part A original institution"}])
    payload["descriptive_statistics"]["MuCP"]["questions"].append(q)
    tex = combined.render_combined_tex(payload, {}).tex
    boundary = tex.index(r"\section{Detailed evidence}")
    assert r"\section{MuCP A}" not in tex
    assert "Part A original institution" in tex[boundary:]


def test_quantity_point_context_uses_names_ordinals_and_scopes_in_default():
    """Default ordinary point tables use human source context for distinct amounts.

    Returns:
        None. Q mappings remain distinct and raw identifiers require extended evidence.
    """
    import copy
    from survey_mucp_quantities import extract_modality_quantities
    from test_survey_mucp_quantities import DEFINITIONS, table_bank

    item = table_bank()
    summary = extract_modality_quantities([item], DEFINITIONS)
    duplicate = copy.deepcopy(summary["observations"][0])
    duplicate.update(quantity_id="second-quantity", source_record_id="R2", scope_id="R2:collection:C2")
    summary["observations"].append(duplicate)
    record = copy.deepcopy(item["mucp_source_records"][0])
    record["record_id"] = "R2"
    item["mucp_source_records"].append(record)
    item["scopes"]["R2:collection:C2"] = {"scope_id": "R2:collection:C2", "kind": "collection",
        "source_record_id": "R2", "label": "Cancer follow-up cohort", "collection_id": "C2"}
    options = {"modality_definitions": DEFINITIONS, "biobanks": [item]}
    compact = "\n".join(combined.render_modality_quantity_charts(summary, options).values())
    assert "Synthetic institute" in compact and "Cancer follow-up cohort" in compact
    assert "Submission 1" in compact and "Submission 2" in compact
    assert "Q1" in compact and "Q2" in compact and compact.count("\\addplot+") == 2
    assert "bbmri-eric" not in compact and "R1:collection" not in compact and "R2" not in compact
    extended = "\n".join(combined.render_modality_quantity_charts(
        summary, {**options, "extended_evidence": True}).values())
    assert "R2" in extended and "bbmri-eric" in extended


def test_modality_quantity_totals_keep_units_bases_zero_and_missing_distinct():
    """Render source totals without blending scope bases or treating absence as zero.

    Returns:
        None. Every configured modality gets a row and each amount retains its unit/basis.
    """
    definitions = [
        {"id": "plasma", "label": "Plasma"},
        {"id": "wgs", "label": "WGS"},
        {"id": "empty", "label": "No counts"},
    ]
    aggregates = {
        "modality_totals": [
            {"modality_id": "plasma", "unit": "donors", "basis": "collection",
             "reported_total": 120, "contributing_biobanks": 2,
             "contributing_scopes": 3, "excluded_count": 1, "segments": []},
            {"modality_id": "plasma", "unit": "unit_unclear", "basis": "collection",
             "reported_total": None, "contributing_biobanks": 0,
             "contributing_scopes": 0, "excluded_count": 1, "segments": []},
            {"modality_id": "plasma", "unit": "donors", "basis": "submission_fallback",
             "reported_total": 800, "contributing_biobanks": 1,
             "contributing_scopes": 1, "excluded_count": 0, "segments": []},
            {"modality_id": "wgs", "unit": "samples", "basis": "direct_modality",
             "reported_total": 0, "contributing_biobanks": 1,
             "contributing_scopes": 1, "excluded_count": 0, "segments": []},
        ],
            "excluded_contributions": [
                {"modality_ids": ["plasma"], "unit": "unit_unclear", "basis": "collection",
                 "reason": "unsupported_unit"},
                {"modality_ids": ["plasma"], "unit": "donors", "basis": "collection",
                 "reason": "qualified_relation"},
        ],
        "diagnostics": [],
    }
    tex = combined.render_modality_quantity_totals(
        aggregates, {"modality_definitions": definitions},
    )
    assert "Plasma" in tex and "WGS" in tex and "No counts" in tex
    assert "120 donors" in tex and "800 donors" in tex and "0 samples" in tex
    assert "Not reported" in tex
    assert "donors in collections reporting this type" in tex
    assert "Count reported; collection not identified" in tex and "Count reported specifically for this type" in tex
    assert "Count unit unclear" in tex and "Approximate count or bound, not an exact total" in tex
    assert "Eligible measurement coverage" not in tex


def test_combined_report_uses_quantity_aggregates_instead_of_coverage_matrices():
    """The combined report renders canonical aggregates, not raw coverage matrices.

    Returns:
        None. Existing source observations are not a fallback source for aggregate totals.
    """
    payload = minimal_payload()
    payload["descriptive_statistics"]["MuCP"]["quantity_aggregates"] = {
        "modality_totals": [{"modality_id": "plasma", "unit": "donors", "basis": "collection",
            "reported_total": 120, "contributing_biobanks": 2, "contributing_scopes": 3,
            "excluded_count": 0, "segments": []}],
        "excluded_contributions": [], "diagnostics": [],
    }
    payload["descriptive_statistics"]["MuCP"]["modality_quantities"] = {
        "coverage": {"cohort_N": 3, "by_modality": []}, "observations": [],
    }
    rendered = combined.render_combined_tex(payload, {})
    assert "120 donors" in rendered.tex
    assert "Eligible measurement coverage" not in rendered.tex
    assert "0 / 3" not in rendered.tex
    assert "Numeric mentions and scopes are never summed" not in rendered.tex
    assert "exact totals add only counts checked against their sources and for repeated reports" in rendered.tex


def test_combined_report_wires_one_country_total_and_distinct_modality_stacks():
    """Use country totals once while rendering each linked modality as its own view.

    Returns:
        None. Multi-modality collections do not multiply the all-collection country total.
    """
    payload = minimal_payload()
    bank_id = payload["biobanks"][0]["biobank_id"]
    fallback_bank_id = "bbmri-eric:ID:XX_FALLBACK"
    payload["biobanks"].append({**payload["biobanks"][0], "biobank_id": fallback_bank_id,
                                "id": fallback_bank_id, "name": "Independent fallback bank"})
    def total(dimension, value, basis="collection"):
        """Build one independent synthetic total row for the chart wiring test.

        Args:
            dimension: Either country or configured modality dimension key/value.
            value: Exact aggregate value contributed by the single synthetic biobank.
            basis: Reporting basis; fallback belongs to an independent biobank.

        Returns:
            One valid aggregate row with a single attributable bank segment.
        """
        key, label = dimension
        return {key: label, "unit": "donors", "basis": basis, "temporal_status": "unspecified",
                "reported_total": value, "contributing_biobanks": 1, "contributing_scopes": 1,
                "excluded_count": 0, "segments": [{"biobank_id": fallback_bank_id if basis == "submission_fallback" else bank_id, "value": value,
                                                      "quantity_ids": [f"quantity-{label}-{basis}"]}]}

    payload["descriptive_statistics"]["MuCP"]["quantity_aggregates"] = {
        "country_totals": [total(("country", "XX"), 120)],
        "modality_totals": [total(("modality_id", "plasma"), 120),
                            total(("modality_id", "wgs"), 120),
                            total(("modality_id", "plasma"), 50, "submission_fallback")],
        "contributions": [], "excluded_contributions": [], "diagnostics": [],
    }
    payload["descriptive_statistics"]["MuCP"]["modality_quantities"] = {"observations": []}

    rendered = combined.render_combined_tex(payload, {})

    all_collection = next(value for key, value in rendered.chart_fragments.items() if key.startswith("country_views") and "-linear-" in key)
    plasma = next(value for key, value in rendered.chart_fragments.items() if key.startswith("type_views") and "Plasma" in value)
    wgs = next(value for key, value in rendered.chart_fragments.items() if key.startswith("type_views") and "WGS" in value)
    assert all_collection.count("120 donors") == 1
    assert "confirmed: 170, total: 170" in plasma and "confirmed: 120, total: 120" in wgs
    assert "Reported counts by country" in all_collection
    assert "Plasma" in plasma and "WGS" in wgs


def test_country_quantity_charts_use_exact_raw_stacks_on_linear_axes_only():
    """Build comparable country stacks from per-bank eligible collection totals.

    Returns:
        None. Linear stacks retain raw boundaries; no logarithmic stack is emitted.
    """
    aggregates = {
        "country_totals": [{
            "country": "Zambia", "unit": "donors", "basis": "collection",
            "temporal_status": "unspecified", "reported_total": 30,
            "segments": [{"biobank_id": "bank-z", "value": 30, "quantity_ids": ["q-z"]}],
        }, {
            "country": "Austria", "unit": "donors", "basis": "collection",
            "temporal_status": "unspecified", "reported_total": 120,
            "segments": [
                {"biobank_id": "bank-a", "value": 100, "quantity_ids": ["q-a"]},
                {"biobank_id": "bank-b", "value": 20, "quantity_ids": ["q-b"]},
            ],
        }],
        "modality_totals": [], "excluded_contributions": [],
    }
    options = {"biobanks": [
        {"biobank_id": "bank-a", "country": "Austria", "name": "Long Austrian Institute"},
        {"biobank_id": "bank-b", "country": "Austria", "name": "Second Institute"},
        {"biobank_id": "bank-z", "country": "Zambia", "name": "Zambian Institute"},
    ]}

    charts = combined.render_country_quantity_charts(aggregates, options)

    assert len(charts) == 1
    linear = next(fragment for key, fragment in charts.items() if key.endswith("-linear-1"))
    for fragment in (linear,):
        assert "120 donors" in fragment and "30 donors" in fragment
        assert "raw cumulative boundaries: 0,100,120" in fragment
        assert "raw cumulative boundaries: 0,30" in fragment
        assert "Long Austrian Institute" in fragment and "Second Institute" in fragment
        assert "Zambian Institute" in fragment
    assert r"xmode=log" not in linear
    assert "xmin=0,xmax=120" in linear
    assert "y dir=reverse" in linear
    assert "Austria" in linear and "Zambia" in linear


def test_country_quantity_charts_keep_basis_modality_and_zero_one_rows_separate():
    """Separate modality/basis views and preserve non-visible zero/one evidence.

    Returns:
        None. Missing is not zero, direct amounts are distinct, and one stays identifiable.
    """
    bank_id = "bank-a"
    aggregates = {
        "country_totals": [{"country": "Austria", "unit": "samples", "basis": "collection",
            "temporal_status": "unspecified", "reported_total": 0,
            "segments": [{"biobank_id": bank_id, "value": 0, "quantity_ids": ["q-zero"]}]},
            {"country": "Austria", "unit": "donors", "basis": "submission_fallback",
             "temporal_status": "unspecified", "reported_total": 1,
             "segments": [{"biobank_id": bank_id, "value": 1, "quantity_ids": ["q-one"]}]}],
        "modality_totals": [{"modality_id": "plasma", "unit": "donors", "basis": "collection",
            "temporal_status": "unspecified", "reported_total": 1, "segments": [
                {"biobank_id": bank_id, "value": 1, "quantity_ids": ["q-one"]}]},
            {"modality_id": "plasma", "unit": "donors", "basis": "direct_modality",
             "temporal_status": "unspecified", "reported_total": 9000, "segments": [
                 {"biobank_id": bank_id, "value": 9000, "quantity_ids": ["q-direct"]}]},
            {"modality_id": "wgs", "unit": "donors", "basis": "collection",
             "temporal_status": "unspecified", "reported_total": None, "segments": []}],
        "excluded_contributions": [{"basis": "collection", "unit": "donors",
            "reason": "qualified_relation", "modality_ids": ["wgs"], "quantity_ids": ["q-bound"]}],
    }
    options = {"biobanks": [{"biobank_id": bank_id, "country": "Austria", "name": "Institute A"}],
               "modality_definitions": [{"id": "plasma", "label": "Plasma"},
                                        {"id": "wgs", "label": "Whole genome sequencing"}]}

    charts = combined.render_country_quantity_charts(aggregates, options)

    assert len(charts) == 4
    assert any("zero total" in fragment.casefold() and "0 samples" in fragment for fragment in charts.values())
    assert any("one-sized" in fragment.casefold() and "Institute A" in fragment for fragment in charts.values())
    assert any("submission fallback" in fragment.casefold() for fragment in charts.values())
    assert any("direct modality" in fragment.casefold() and "9000 donors" in fragment
               for fragment in charts.values())
    assert any("approximate count or bound" in fragment.casefold() and "not plotted" in fragment.casefold()
               for fragment in charts.values())
    assert not any("Not reported" in fragment and "0 donors" in fragment for fragment in charts.values())


def test_country_quantity_chart_pages_share_scales_colors_and_printable_sizing():
    """Use stable bank presentation and chart dimensions across country pages.

    Returns:
        None. Page count and row height, not surrounding TeX flow, determine panel size.
    """
    countries = [f"Country {index:02d}" for index in range(37)]
    banks = [{"biobank_id": f"bank-{index:02d}", "country": country,
              "name": f"Long biobank institution name {index:02d} " * 3}
             for index, country in enumerate(countries)]
    totals = [{"country": country, "unit": "donors", "basis": "collection",
               "temporal_status": "unspecified", "reported_total": index + 1,
               "segments": [{"biobank_id": f"bank-{index:02d}", "value": index + 1,
                             "quantity_ids": [f"quantity-{index:02d}"]}]}
              for index, country in enumerate(countries)]

    charts = combined.render_country_quantity_charts(
        {"country_totals": totals, "modality_totals": [], "excluded_contributions": []},
        {"biobanks": banks},
    )

    assert len(charts) == 3
    linear_pages = [text for key, text in charts.items()
                    if key.startswith("mucp-quantity-country") and "-linear-" in key]
    assert len(linear_pages) == 3
    page_heights = [float(text.split("height=", 1)[1].split("cm", 1)[0]) for text in linear_pages]
    assert page_heights[0] == page_heights[1] < 17
    assert 5 <= page_heights[2] < page_heights[0]
    assert all("xmax=37" in text for text in linear_pages)
    assert all("Long biobank institution name" in text and r"\parbox" in text for text in linear_pages)
    first_color = r"\definecolor{mucpBankColor0}{HTML}{"
    assert len({text[text.index(first_color) : text.index(first_color) + 46]
                for text in charts.values()}) == 1


def test_quantity_plot_keeps_sans_serif_ticks_and_math_number_format():
    """Local PGF font options retain the shared chart sans-serif family.

    Returns:
        None. Numeric formatting does not silently reintroduce serif math digits.
    """
    from survey_mucp_quantities import extract_modality_quantities
    from test_survey_mucp_quantities import DEFINITIONS, bank
    summary = extract_modality_quantities([bank([("C.omics_data.gwas", "100 participants")])], DEFINITIONS)
    text = next(iter(combined.render_modality_quantity_charts(
        summary, {"modality_definitions": DEFINITIONS}).values()))
    assert r"font=\sffamily\small" in text
    assert r"/pgf/number format/assume math mode=true" in text


def test_quantity_log_ticks_use_fixed_point_sans_numbers():
    """Log axes avoid PGF's serif mathematical power-label fallback.

    Returns:
        None. A real log-range panel requests fixed-point labels and shared sans style.
    """
    from survey_mucp_quantities import extract_modality_quantities
    from test_survey_mucp_quantities import DEFINITIONS, bank
    summary = extract_modality_quantities([bank([("C.omics_data.gwas", "1 participants"),
                                                 ("C.omics_data.wgs", "12000 participants")])], DEFINITIONS)
    text = next(iter(combined.render_modality_quantity_charts(
        summary, {"modality_definitions": DEFINITIONS}).values()))
    assert "xmode=log" in text
    assert "log ticks with fixed point" in text
    assert r"font=\sffamily\small" in text


def test_combined_profile_pies_use_short_exact_bases_without_changing_counts():
    """Omit evidence-presence pies instead of charting derived missingness.

    Returns:
        None. Cohort and numeric-evidence denominators/counts remain exact and legacy stays unchanged.
    """
    from copy import deepcopy

    profile = {"cohort_N": 59, "sizes": {"samples": {
        "states": {"single_reported_scope": 0, "multiple_scopes_or_values": 0,
                   "qualified_or_bound": 0, "numeric_mentions_only": 3, "missing": 56},
        "size_bands": {}}}}
    original = deepcopy(profile)
    questions = combined._profile_questions(profile)
    assert questions == []
    assert profile == original


def test_modality_quantity_charts_separate_direct_from_context_and_missing():
    """Render proven points, context panels and unsupported-unit notices distinctly.

    Returns:
        None. PGF never duplicates a context amount for each modality link.
    """
    from survey_mucp_quantities import extract_modality_quantities
    from test_survey_mucp_quantities import DEFINITIONS, bank

    summary = extract_modality_quantities([bank([("C.omics_data.gwas", "over 12,000 participants")])], DEFINITIONS)
    assert {row["unit"] for row in summary["observations"]} == {"donors"}
    assert {row["source_unit"] for row in summary["observations"]} == {"participants"}
    charts = combined.render_modality_quantity_charts(summary, {"modality_definitions": DEFINITIONS})
    assert any("donors" in key for key in charts)
    assert all("donors" in key and "samples" not in key for key in charts)
    assert any("\\begin{axis}" in fragment and "12000" in fragment for fragment in charts.values())
    payload = minimal_payload()
    payload["descriptive_statistics"]["MuCP"]["modality_quantities"] = summary
    rendered = combined.render_combined_tex(payload, {})
    assert not any(key.startswith("mucp-quantity-country") for key in rendered.chart_fragments)
    assert "Countries use Directory metadata where resolved, otherwise the survey's country" in rendered.tex
    assert "MuCP unknown/unmarked is included in M, never treated as negative" not in rendered.tex
    assert "Applicable unticked" in rendered.tex


def test_modality_quantity_country_panels_share_log_scale_and_list_zero():
    """Cross-country point scales stay comparable without logarithmic zero loss.

    Returns:
        None. Exact, bound and zero measurements remain distinct source points.
    """
    from survey_mucp_quantities import extract_modality_quantities
    from test_survey_mucp_quantities import DEFINITIONS, bank
    import copy

    first = bank([("C.omics_data.gwas", "1 participants")])
    second = bank([("C.omics_data.gwas", "over 12,000 participants")])
    second["biobank_id"] = "bbmri-eric:ID:DE_TWO"
    second["country"] = "DE"
    third = bank([("C.omics_data.gwas", "0 participants")])
    third["biobank_id"] = "bbmri-eric:ID:DE_THREE"
    third["country"] = "DE"
    summary = extract_modality_quantities([copy.deepcopy(third), second, first], DEFINITIONS)
    charts = combined.render_modality_quantity_charts(summary, {"modality_definitions": DEFINITIONS})
    assert len(charts) == 2
    assert all("xmode=log" in chart and "log scale" in chart for chart in charts.values())
    de = next(chart for key, chart in charts.items() if "-de-" in key)
    assert "12000" in de and "Zero-valued quantities or bounds in donors (not plotted on log axis): Q" in de
    assert de.count("\\addplot+") == 1


def test_zero_bound_log_notice_does_not_claim_a_zero_quantity():
    """Treat a zero lower-bound threshold differently from a reported zero count.

    Returns:
        None. The unplotted threshold keeps its bound relation without claiming absence.
    """
    from survey_mucp_quantities import extract_modality_quantities
    from test_survey_mucp_quantities import DEFINITIONS, bank

    source = bank([
        ("C.omics_data.gwas", "1 participants"),
        ("C.omics_data.wgs", "over 12000 participants"),
        ("C.omics_data.gwas", "over 0 participants"),
    ])
    summary = extract_modality_quantities([source], DEFINITIONS)
    chart = next(iter(combined.render_modality_quantity_charts(
        summary, {"modality_definitions": DEFINITIONS}).values()))
    assert "xmode=log" in chart
    assert "greater than 0 donors" in chart
    assert "Zero reported donors" not in chart
    assert "Zero-valued quantities or bounds" in chart


def test_quantity_chart_full_links_and_duplicate_modality_points_are_readable():
    """Full context links and duplicate modality rows use distinct evidence IDs.

    Returns:
        None. Sixteen points use short axes and a pageable full-link source table.
    """
    import copy
    import json
    from pathlib import Path
    from survey_mucp_quantities import extract_modality_quantities
    from test_survey_mucp_quantities import DEFINITIONS, bank

    template = extract_modality_quantities([bank([("C.omics_data.gwas", "1 participants")])],
                                           DEFINITIONS)["observations"][0]
    presentation = json.loads(Path("survey-mappings/so2_mucp_report_presentation.json").read_text())
    public_definitions = presentation["modality_quantities"]
    rows = []
    for index in range(16):
        row = copy.deepcopy(template)
        row["quantity_id"] = f"quantity-{index}"
        row["source_record_id"] = f"R-{index}"
        row["scope_id"] = f"R-{index}:collection:C-{index}"
        row["value"] = index + 1
        row["unit"] = "individuals"
        row["linkage"] = "collection_size_context"
        row["modality_links"] = [
            {"modality_id": definition["id"], "question_id": definition["question_id"],
             "evidence_id": f"linked-{index}-{offset}", "source_refs": [{"source_id": "SRC1", "locator": "synthetic"}]}
            for offset, definition in enumerate(public_definitions[:13])]
        rows.append(row)
    charts = combined.render_modality_quantity_charts(
        {"observations": rows}, {"modality_definitions": public_definitions})
    chart = next(iter(charts.values()))
    assert len(charts) == 1 and "yticklabels={{Q1},{Q2}" in chart
    assert "Q16" in chart and chart.count("\\addplot+") == 16
    assert r"\begin{longtable}" in chart and chart.count("GWAS") >= 16
    assert "Submission 16" in chart and "time not specified" in chart
    assert "R-15" not in chart
    assert "For bound markers only" in chart


def test_compact_evidence_folds_equal_values_without_losing_scope():
    """Fold equal fields per answer and omit absent qualifications/references.

    Returns:
        None. Compact output preserves question/source/scope and original JSON.
    """
    import copy
    bb = minimal_payload()["biobanks"][0]
    item = bb["evidence"][1]
    item.update(normalized_value="explicit_negative", raw_answer="WGS", raw_text="WGS", qualifier_text=None)
    before = copy.deepcopy(bb)
    text = combined.render_biobank_dossier(bb, {})
    assert "Normalized value / Raw answer / Raw text" not in text
    assert "No" in text
    assert "[MuCP] Qualifier" not in text
    assert "Collection C1" in text
    assert "source record:" not in text and "locator:" not in text
    assert r"p{0.30\linewidth}p{0.66\linewidth}" in text
    extended = combined.render_biobank_dossier(bb, {"extended_evidence": True})
    assert "source record:" in extended and "locator:" in extended
    assert bb == before


def test_mucp_statistics_precede_so2_and_dossiers_are_appendices():
    """Keep MuCP as the primary analytical view and dossiers at the back.

    Returns:
        None. Report order and monospaced font match the approved design.
    """
    payload = minimal_payload()
    tex = combined.render_combined_tex(payload, {"include_dossiers": True}).tex
    assert tex.index(r"\section{MuCP cohort profile}") < tex.index(r"\section{SO2}")
    assert tex.index(r"\section{SO2}") < tex.index(r"\appendix")
    assert tex.index(r"\appendix") < tex.index("Biobank dossier:")
    assert r"\usepackage[scaled=0.85]{inconsolata}" in tex
    assert r"\setmonofont[Scale=0.85" in tex


def test_more_than_26_dossiers_use_one_appendix_with_numbered_subsections():
    """Avoid LaTeX's A-Z appendix counter limit for a real multi-bank cohort.

    Returns:
        None. Each dossier remains independently linked under one appendix.
    """
    import copy
    payload = minimal_payload()
    template = payload["biobanks"][0]
    payload["biobanks"] = []
    for index in range(27):
        bb = copy.deepcopy(template)
        bb.update(biobank_id=f"bbmri-eric:ID:XX_{index}", name=f"Bank {index}")
        payload["biobanks"].append(bb)
    tex = combined.render_combined_tex(payload, {"include_dossiers": True}).tex
    appendix = tex.split(r"\appendix", 1)[1]
    assert r"\section{Biobank evidence dossiers}" in appendix
    assert appendix.count(r"\subsection{Biobank dossier:") == 27
    assert r"\section{Biobank dossier:" not in appendix


def test_combined_compiler_waits_for_stable_toc(monkeypatch):
    """A multi-page TOC can change pagination after the second compiler pass.

    Args:
        monkeypatch: Isolated compiler replacement writing successive TOC states.

    Returns:
        None. Publication waits for stable reference bytes rather than two passes.
    """
    calls = []

    def compiler(source, directory, passes):
        """Simulate a successful compiler whose reference files stabilize on pass three.

        Args:
            source: Temporary TeX input path whose stem selects reference files.
            directory: Temporary compilation output directory.
            passes: Number of compiler passes requested in this invocation.

        Returns:
            A synthetic complete PDF path beside the generated TOC.
        """
        calls.append(passes)
        source.with_suffix(".toc").write_text("initial" if len(calls) == 1 else "stable")
        pdf = directory / (source.stem + ".pdf")
        pdf.write_bytes(b"%PDF-1.4\n")
        return pdf

    monkeypatch.setattr(combined.descriptive, "_run_xelatex", compiler)
    pdf = combined._compile_document("test source", "stable-toc", passes=2)
    try:
        assert calls == [1, 1, 1]
    finally:
        shutil.rmtree(pdf.parent)


def test_unstable_references_fail_and_remove_compilation_stage(monkeypatch, tmp_path):
    """Unconverged reference files cannot publish a stale or partial combined PDF.

    Args:
        monkeypatch: Isolated compiler/temp-directory replacements for the failure path.
        tmp_path: Private test directory owning the compiler stage to be removed.

    Returns:
        None. The compiler stops after six passes and removes its temporary outputs.
    """
    stage = tmp_path / "compile"
    stage.mkdir()
    calls = []

    def make_directory(prefix):
        """Return the pre-created isolated compiler stage.

        Args:
            prefix: Requested temporary-directory prefix, unused by this fixture.

        Returns:
            String path to the stage whose cleanup is checked.
        """
        return str(stage)

    def unstable_compiler(source, directory, passes):
        """Simulate changing reference bytes on every otherwise successful pass.

        Args:
            source: Temporary TeX file selecting the corresponding TOC filename.
            directory: Stage receiving the synthetic PDF.
            passes: Requested single-pass count retained in the call ledger.

        Returns:
            A synthetic PDF path that must never be accepted for publication.
        """
        calls.append(passes)
        source.with_suffix(".toc").write_text(str(len(calls)))
        pdf = directory / "unstable.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        return pdf

    monkeypatch.setattr(combined.tempfile, "mkdtemp", make_directory)
    monkeypatch.setattr(combined.descriptive, "_run_xelatex", unstable_compiler)
    with pytest.raises(combined.descriptive.InputError, match="did not stabilize"):
        combined._compile_document("test source", "unstable")
    assert calls == [1] * 6
    assert not stage.exists()


def test_size_profile_charts_declare_derived_semantics_and_skip_empty_bands():
    """Omit missing-evidence charts and retain only nonempty derived size bands.

    Returns:
        None. Empty size distributions have no fabricated chart observations.
    """
    from survey_descriptive import build_mucp_cohort_profile
    questions = combined._profile_questions(build_mucp_cohort_profile([]))
    assert questions == []
    from test_mucp_cohort_profile import bank
    profile = build_mucp_cohort_profile([bank("A", [("individuals", 100, "reported_value")]),
        bank("B", [("individuals", 200, "at_most")])])
    questions = combined._profile_questions(profile)
    assert len(questions) == 1
    bands = questions[0]
    assert bands["question_id"] == "MuCP.size.donors.bands"
    assert bands["question_type"] == "ordinal" and bands["type"] == "derived scoped size bands"
    assert bands["population"] == {"N": 1, "A": 1, "M": 0}
    assert bands["categories"][2]["percent_base"] == 1
    assert not any("coverage" in question["question_id"] for question in questions)


def test_size_bands_keep_numeric_order_after_json_key_sorting():
    """Canonical JSON object order must not reorder ordinal magnitude bands.

    Returns:
        None. Re-rendering saved payloads retains the same ascending size scale.
    """
    import json
    from test_mucp_cohort_profile import bank
    from survey_descriptive import build_mucp_cohort_profile
    profile = json.loads(json.dumps(build_mucp_cohort_profile([
        bank("A", [("individuals", 100, "reported_value")])]), sort_keys=True))
    question = next(q for q in combined._profile_questions(profile) if q["question_id"].endswith("bands"))
    assert [c["value"] for c in question["categories"]] == ["0", "1-99", "100-999",
        "1,000-9,999", "10,000-99,999", "100,000+"]


def test_clinical_data_gets_immediate_source_labelled_interoperability_context():
    """Link affirmative MuCP clinical evidence to SO2 experience without merging claims.

    Returns:
        None. Enrichment retains scope and missing SO2 context explicitly.
    """
    payload = minimal_payload()
    bb = payload["biobanks"][0]
    bb["observations"] = [{"survey": "MuCP", "question_id": "B.available_data.clinical_phenotype",
        "state": "varying_across_scopes", "has_affirmative_evidence": True}]
    bb["evidence"].append({"survey": "SO2", "question_id": "q_018_does_the_staff_dedicated_or_not_managing_the_repository_have_experience_",
        "question_label": "Terminology experience", "normalized_value": ["HPO"], "raw_answer": "HPO",
        "raw_text": "HPO", "scope_label": "Submission", "answer_state": "answered"})
    tex = combined.render_combined_tex(payload, {}).tex
    main = tex.split(r"\appendix")[0]
    assert "Clinical data and SO2 interoperability" in main
    assert "HPO" in main and "[SO2]" in main and "[MuCP]" in main
    assert "at least one" in main and "Submission" not in main


def test_combined_hyperlinks_resolve_with_and_without_dossiers():
    """Optional dossiers never leave dead hyperlinks in the evidence tables.

    Returns:
        None. Every internal destination exists, with dossiers linked only when enabled.
    """
    import re

    payload = minimal_payload()
    payload["biobanks"][0]["observations"] = [{
        "survey": "MuCP", "question_id": "B.available_data.clinical_phenotype",
        "state": "reported_yes_in_one_or_more_scopes", "has_affirmative_evidence": True,
    }]
    for enabled in (False, True):
        tex = combined.render_combined_tex(payload, {"include_dossiers": enabled}).tex
        targets = set(re.findall(r"\\hyperref\[([^]]+)\]", tex))
        labels = set(re.findall(r"\\label\{([^}]+)\}", tex))
        assert targets <= labels
        assert any(target.startswith("dossier-") for target in targets) is enabled


def test_clinical_summary_uses_compact_labels_instead_of_repeating_long_questions():
    """Keep the main enrichment reader-oriented; full question wording is in dossiers.

    Returns:
        None. Repeated source submissions retain values without repeated long prompts.
    """
    bb = minimal_payload()["biobanks"][0]
    bb["observations"] = [{"survey": "MuCP", "question_id": "B.available_data.clinical_phenotype",
        "state": "reported_yes_in_one_or_more_scopes", "has_affirmative_evidence": True}]
    for value in ("HPO", "ICD-10"):
        bb["evidence"].append({"survey": "SO2",
            "question_id": "q_018_does_the_staff_dedicated_or_not_managing_the_repository_have_experience_",
            "question_label": "Very long repeated staff terminology question", "raw_answer": value,
            "scope_label": "Submission"})
    text = combined._clinical_enrichment([bb], False)
    assert text.count("Very long repeated staff terminology question") <= 1
    assert "HPO" in text and "ICD-10" in text and "[SO2]" in text


def test_clinical_context_retains_partial_positive_and_distinguishes_no_from_unknown():
    """Keep positive clinical evidence while distinguishing explicit No from unknown.

    Returns:
        None. Classified clinical patterns are visible and unknown patterns remain omitted.
    """
    no_bank = minimal_payload()["biobanks"][0]
    no_bank["biobank_id"] = "NO"
    no_bank["observations"] = [{"survey": "MuCP", "question_id": "B.available_data.clinical_phenotype",
        "state": "explicitly_no_in_all_reported_applicable_scopes", "has_affirmative_evidence": False,
        "flags": []}]
    unknown_bank = minimal_payload()["biobanks"][0]
    unknown_bank["biobank_id"] = "UNKNOWN"
    unknown_bank["observations"] = [{"survey": "MuCP", "question_id": "B.available_data.clinical_phenotype",
        "state": "unknown_or_unmarked", "has_affirmative_evidence": False, "flags": []}]
    partial_bank = minimal_payload()["biobanks"][0]
    partial_bank["biobank_id"] = "PARTIAL"
    partial_bank["observations"] = [{"survey": "MuCP", "question_id": "B.available_data.clinical_phenotype",
        "state": "reported_yes_in_one_or_more_scopes", "has_affirmative_evidence": True,
        "flags": ["partial_scope_coverage"]}]

    tex = combined._clinical_enrichment([no_bank, unknown_bank, partial_bank], False)

    assert "No in all reported applicable scopes" in tex
    assert "Clinical phenotype data: reported in at least one scope" in tex
    assert "unknown_or_unmarked" not in tex
    assert "UNKNOWN" not in tex


def test_checkbox_frequency_clinical_heatmap_and_upset_reconcile_same_observations():
    """Reconcile answered No, affirmative, partial-positive and unknown observations across views.

    Returns:
        None. Frequencies retain positives, clinical text distinguishes No, heatmaps preserve states,
        and only the complete checkbox-pattern UpSet excludes incomplete coverage.
    """
    from survey_descriptive import (build_association_from_observations,
        build_combined_statistics, build_combined_upset_matrix)

    question_id = "B.available_data.clinical_phenotype"
    states = (
        ("YES", "reported_yes_in_one_or_more_scopes", True, []),
        ("NO", "explicitly_no_in_all_reported_applicable_scopes", False, []),
        ("PARTIAL", "reported_yes_in_one_or_more_scopes", True, ["partial_scope_coverage"]),
        ("UNKNOWN", "unknown_or_unmarked", False, []),
    )
    banks = [{"biobank_id": bid, "country": "AT", "name": bid, "evidence": [], "observations": [{
        "survey": "MuCP", "question_id": question_id, "state": state,
        "has_affirmative_evidence": affirmative, "flags": flags,
    }, {"survey": "SO2", "question_id": "dummy", "state": "known", "selected_values": ["Present"]}]}
        for bid, state, affirmative, flags in states]
    catalogues = {"SO2": [{"id": "dummy", "label": "Dummy", "type": "single_choice",
        "question_type": "single_choice",
        "categories": ["Present"]}], "MuCP": [{"id": question_id, "label": "Clinical phenotype",
        "type": "checkbox", "part": "B", "group": "clinical"}]}

    statistics = build_combined_statistics(banks, catalogues, {})
    stats = statistics["MuCP"]
    frequency = stats["groups"][0]
    observations = stats["questions"][0]["observations"]
    heatmap = build_association_from_observations({"id": "clinical", "questions": ["MuCP:" + question_id,
        "SO2:dummy"], "row_categories": [state for _, state, _, _ in states],
        "column_categories": ["Present"], "minimum_n": 1},
        {"MuCP:" + question_id: observations,
         "SO2:dummy": statistics["SO2"]["questions"][0]["observations"]})
    upset = build_combined_upset_matrix({"id": "clinical", "questions": ["MuCP:" + question_id],
        "projection": "reported_checkbox_pattern", "minimum_n": 1}, banks)
    clinical = combined._clinical_enrichment(banks, False)

    assert frequency["population"] == {"N": 4, "A": 3, "M": 1}
    assert frequency["categories"][0]["count"] == 2
    assert frequency["categories"][0]["percent_base"] == 3
    assert {key.split("|", 1)[0]: value for key, value in heatmap["pair"]["cells"].items()
            if value} == {"reported_yes_in_one_or_more_scopes": 2,
                "explicitly_no_in_all_reported_applicable_scopes": 1, "unknown_or_unmarked": 1}
    assert upset["matrix_N"] == 2 and upset["all_zero_biobanks"] == 1
    assert upset["exclusions"] == {"incomplete_scope_coverage": 1, "unknown_or_unmarked": 1}
    assert "No in all reported applicable scopes" in clinical
    assert "UNKNOWN" not in clinical


def test_scope_coverage_tables_are_absent_in_all_combined_modes():
    """Hide scope-state coverage tables in every combined mode, not standalone describe.

    Returns:
        None. Combined output omits diagnostic tables while the generic default remains compatible.
    """
    from copy import deepcopy
    import so2_descriptive_report as report

    payload = minimal_payload()
    payload["descriptive_statistics"]["MuCP"]["groups"] = [{
        "question_id": "MuCP.B.collection_design", "label": "Part B: Sample group",
        "question_type": "multi_choice", "population": {"N": 1, "A": 1, "M": 0},
        "categories": [{"value": "[MuCP] Serum", "count": 1, "percent": 100.0,
                        "percent_basis": "oIB"}], "contributions": [], "free_text_rows": [],
        "option_coverage": [{"label": "Serum", "unknown_or_partial_count": 0,
            "qualified_positive_count": 0, "varying_positive_count": 0}],
    }]
    cases = ({}, {"include_contribution_tables": True}, {"extended_evidence": True})
    for options in cases:
        tex = combined.render_combined_tex(deepcopy(payload), options).tex
        assert "Scope-state coverage" not in tex
        assert "Unknown / partial" not in tex
        assert "Qualified positive" not in tex

    legacy_question = payload["descriptive_statistics"]["MuCP"]["groups"][0]
    legacy = report.render_statistics_sections([{"survey": "MuCP", "questions": [legacy_question]}], {})
    combined_only = report.render_statistics_sections([{"survey": "MuCP", "questions": [legacy_question]}],
        {"include_scope_state_tables": False})
    assert "Scope-state coverage" in legacy.tex
    assert "Scope-state coverage" not in combined_only.tex


def test_scoped_size_wording_obeys_contact_opt_in():
    """Apply the existing contact policy to the new scoped-size summary path.

    Returns:
        None. Raw wording remains in JSON and is masked in default PDFs only.
    """
    from test_mucp_cohort_profile import bank
    payload = minimal_payload()
    bb = payload["biobanks"][0]
    bb["evidence"].extend(bank(bb["biobank_id"], [("samples", 100, "reported_value")])["evidence"])
    bb["evidence"][-1]["raw_text"] = "100 samples; contact sample@example.org"
    assert "sample@example.org" not in combined.render_combined_tex(payload, {}).tex
    assert "sample@example.org" in combined.render_combined_tex(payload, {"include_contact_details": True}).tex


def test_default_supplemental_context_hides_technical_source_references():
    """Compact collection/supplemental headings do not restore hidden source IDs.

    Returns:
        None. Extended mode retains technical context; default keeps scoped values.
    """
    bb = minimal_payload()["biobanks"][0]
    bb["scopes"] = [{"kind": "collection", "survey": "MuCP", "label": "Collection A",
        "source_record_id": "SECRET-RECORD-ID", "metadata": {"description": "Tissue scope"}}]
    bb["mucp_source_records"] = [{"record_id": "SECRET-RECORD-ID", "metadata": {"extraction_notes": ["Original wording"]}}]
    text = combined.render_biobank_dossier(bb, {})
    compact = text.replace(r"\allowbreak{}", "")
    assert "SECRET-RECORD-ID" in compact  # Response provenance inventory is explicit.
    assert "source record: SECRET-RECORD-ID" not in compact
    assert "Tissue scope" in text and "Original wording" in text
    assert "SECRET-RECORD-ID" in combined.render_biobank_dossier(bb, {"extended_evidence": True}).replace(r"\allowbreak{}", "")


def test_compact_nested_material_omits_locators_but_extended_retains_them():
    """Nested supplemental evidence respects the same extended-evidence switch.

    Returns:
        None. Locator metadata remains in JSON, not the compact PDF.
    """
    bb = minimal_payload()["biobanks"][0]
    bb["mucp_source_records"] = [{"record_id": "M", "metadata": {"quantity_index": [
        {"value": 42, "evidence": [{"source_id": "SRC-M", "locator": "word/document.xml:p[123]"}]}]}}]
    bb["evidence"][1]["raw_answer"] = {"value": False, "evidence": [
        {"source_id": "SRC-M", "locator": "word/document.xml:p[123]"}]}
    assert "document.xml" not in combined.render_biobank_dossier(bb, {})
    assert "document.xml" in combined.render_biobank_dossier(bb, {"extended_evidence": True})


def test_size_band_ineligibility_is_not_missing_quantity_evidence():
    """Distinguish no numeric evidence from qualified quantities excluded from bands.

    Returns:
        None. Size coverage and eligible-band denominators have explicit labels.
    """
    from test_mucp_cohort_profile import bank
    from survey_descriptive import build_mucp_cohort_profile
    profile = build_mucp_cohort_profile([bank("A", [("individuals", 100, "reported_value")]),
        bank("B", [("individuals", 200, "at_most")])])
    bands = next(q for q in combined._profile_questions(profile) if q["question_id"].endswith("donors.bands"))
    assert bands["population"] == {"N": 1, "A": 1, "M": 0}
    assert "eligible" in bands["population_labels"][1]
    assert bands["population_labels"][2] == "not applicable"
    assert profile["sizes"]["donors"]["states"]["qualified_or_bound"] == 1
    assert profile["sizes"]["donors"]["states"]["missing"] == 0


def test_contact_statistics_are_hidden_unless_explicitly_requested():
    """Apply the same contact privacy rule to statistics as to evidence dossiers.

    Returns:
        None. Dedicated submitter answers remain in JSON but not default PDF material.
    """
    payload = minimal_payload()
    payload["descriptive_statistics"]["MuCP"]["questions"] = [{
        "question_id": "A.submitter", "label": "Submitter name", "question_type": "free_text",
        "population": {"N": 1, "A": 1, "M": 0}, "categories": [], "contributions": [],
        "free_text_rows": [{"text": "Private Statistic Respondent", "country": "XX", "institution": "Test Institute"}]}]
    assert "Private Statistic Respondent" not in combined.render_combined_tex(payload, {}).tex
    assert "Private Statistic Respondent" in combined.render_combined_tex(payload, {"include_contact_details": True}).tex


def test_nested_matching_diagnostics_and_review_instructions_are_visible():
    """Render the actual nested record/resolution envelope used by the combined model.

    Returns:
        None. Both PDF review details and incremental override fingerprints remain usable.
    """
    payload = minimal_payload()
    payload["manual_review_matches"] = [{"record": {"survey": "MuCP", "record_id": "RESP-REVIEW",
        "country": "XX", "identity": {"institution_name": "Uncertain institution"}},
        "resolution": {"source_record_id": "RESP-REVIEW", "status": "review", "method": "approximate_candidates",
                       "explanation": "Ambiguous identity evidence", "candidate_ids": ["bbmri-eric:ID:XX_TEST"],
                       "identity_fingerprint": "a" * 64}}]
    assert "RESP-REVIEW" in combined.render_combined_tex(payload, {}).tex
    review = combined._markdown_review(payload)
    assert "identity_fingerprint" in review and "REVIEW_REQUIRED" in review


def test_matching_breakdown_renderer_is_grouped_private_and_in_section_one():
    """Show a status-first inventory in Section 1 without publishing contacts.

    Returns:
        None. Stored response counts and exclusion reasons remain visible while emails
        and submitter names stay masked.
    """
    from survey_combined import build_matching_breakdown
    from test_survey_combined import matching_inventory_payload

    payload = matching_inventory_payload()
    payload["matching_breakdown"] = build_matching_breakdown(payload)
    inventory = combined.render_matching_breakdown(payload["matching_breakdown"], {})
    tex = combined.render_combined_tex(payload, {}).tex

    assert r"\item Accepted" in inventory
    assert "Twin Institute" in inventory and "2 source records" in inventory
    assert r"\subsection*{Survey matching inventory}" in tex
    assert r"\item[SO2]" in tex and r"\item[MuCP]" in tex
    assert "Accepted Directory-ID intersection" in tex
    assert "1 source records" not in inventory
    assert "1 distinct Directory IDs" not in inventory
    assert "1 accepted only in this survey" in tex
    assert "unresolved identities may hide additional overlap" in tex
    assert "S-COUNTRY" in tex and "not biobank-scoped" in tex
    assert "private@example.org" not in tex and "Private Person" not in tex
    assert "contact redacted" in tex
    assert "overlapping biobanks: 1" in tex
    assert "so2 matched biobanks: 2" in tex


def test_collection_descriptors_and_structured_tables_remain_visible():
    """Preserve supplemental MuCP information beyond checklist and SO2 crosswalk fields.

    Returns:
        None. Original collection-specific counts and table material are source-labelled.
    """
    payload = minimal_payload()
    bb = payload["biobanks"][0]
    bb["scopes"] = {"collection-1": {"kind": "collection", "survey": "MuCP", "label": "Collection 1",
        "source_record_id": "M-1", "metadata": {"number_of_donors": 42, "description": "Descriptor evidence"}}}
    bb["mucp_source_records"] = [{"record_id": "M-1", "metadata": {"structured_tables": ["Original table material"]}}]
    text = combined.render_biobank_dossier(bb, {})
    assert "Descriptor evidence" in text and "42" in text
    assert "Original table material" in text


def test_nested_material_contact_names_follow_publication_opt_in():
    """Dedicated nested contact names must not leak through supplemental flattening.

    Returns:
        None. Default views hide nested contacts while opt-in preserves them.
    """
    value = {"contact": {"name": "Private Contact Person", "email": "person@example.org"},
             "submitter_name": "Private Submitter Name", "description": "Public description"}
    hidden = str(combined._material_rows(value, "Material", False))
    shown = str(combined._material_rows(value, "Material", True))
    assert "Private Contact Person" not in hidden and "person@example.org" not in hidden
    assert "Private Submitter Name" not in hidden
    assert "Private Contact Person" in shown and "Public description" in hidden


def test_dossier_has_a_directory_navigation_link():
    """Dossiers link their canonical identity to the configured Directory web view.

    Returns:
        None. The link uses the selected target/schema, not a fixed production URL.
    """
    text = combined.render_biobank_dossier(minimal_payload()["biobanks"][0], {
        "directory_target": "https://directory.example.invalid", "directory_schema": "TEST"})
    assert r"\href{https://directory.example.invalid/TEST/directory/\#/biobank/" in text


def test_long_source_material_is_paginated_without_giant_table_cells():
    """Split long answers and summarize locator lists without dropping JSON evidence.

    Returns:
        None. Longtable cells remain page-sized and source wording is fully represented.
    """
    text = "Start " + "source wording " * 500 + " end"
    rows = combined._material_rows({"description": text, "evidence": [
        {"source_id": "SRC-1", "locator": f"row {index}"} for index in range(600)]}, "Material", False)
    assert len(rows) > 3
    assert all(len(value) < 2500 for _, value in rows)
    assert any("600" in value and "JSON" in value for _, value in rows)
    assert any("Start" in value for _, value in rows) and any("end" in value for _, value in rows)


def test_dossier_source_rows_join_each_response_to_manifest_filenames_only():
    """Inventory every deduplicated source filename without exposing local paths.

    Returns:
        None. Source IDs resolve to basename-only filenames in stable response order.
    """
    biobank = {"mucp_source_records": [
        {"record_id": "RESP-2", "metadata": {"response_id": "RESP-2",
         "source_ids": ["SRC-B", "SRC-A"], "full_evidence_source_ids": ["SRC-A"]}},
        {"record_id": "RESP-1", "metadata": {"response_id": "RESP-1",
         "source_ids": ["SRC-C"]}},
    ]}
    manifest = [
        {"source_id": "SRC-A", "filename": "private/folder/source_a.xlsx", "path": "/private/a"},
        {"source_id": "SRC-B", "filename": "source_b.pdf", "path": "/private/b"},
        {"source_id": "SRC-LONG", "filename": "survey_" + "segment_" * 30 + ".xlsx"},
        {"source_id": "SRC-C", "filename": "folder\\source_c.docx", "path": "/private/c"},
    ]
    biobank["mucp_source_records"][0]["metadata"]["source_ids"].append("SRC-LONG")

    rows = combined.dossier_source_rows(biobank, manifest)

    assert rows == [
        {"response_id": "RESP-1", "filename": "source_c.docx"},
        {"response_id": "RESP-2", "filename": "source_a.xlsx"},
        {"response_id": "RESP-2", "filename": "source_b.pdf"},
        {"response_id": "RESP-2", "filename": "survey_" + "segment_" * 30 + ".xlsx"},
    ]
    assert all("path" not in str(row) and "private" not in str(row) for row in rows)


def test_source_inventory_keeps_responses_without_source_ids_and_uses_known_refs():
    """Keep every response visible without guessing files for absent provenance.

    Returns:
        None. Exact source refs may join the manifest; no-ref responses stay explicit.
    """
    biobank = {"mucp_source_records": [
        {"record_id": "RESP-A", "metadata": {"response_id": "RESP-A"}},
        {"record_id": "RESP-B", "metadata": {"response_id": "RESP-B", "source_ids": []}},
    ], "evidence": [{"survey": "MuCP", "source_record_id": "RESP-A",
        "source_refs": [{"source_id": "SRC-A", "locator": "answer[1]"}]}]}
    manifest = [{"source_id": "SRC-A", "filename": "source-a.xlsx", "path": "/private/source-a.xlsx"}]

    rows = combined.dossier_source_rows(biobank, manifest)

    assert rows == [
        {"response_id": "RESP-A", "filename": "source-a.xlsx"},
        {"response_id": "RESP-B", "filename": "Filename not supplied"},
    ]
    dossier = combined.render_biobank_dossier(biobank, {"source_manifest": manifest})
    dossier = dossier.replace(r"\allowbreak{}", "")
    assert "RESP-B" in dossier and "Filename not supplied" in dossier


def test_dossier_numbers_distinct_responses_and_links_them_to_inventory():
    """Keep same-question contributions distinguishable without repeating IDs.

    Returns:
        None. Human response numbers map to response IDs and filenames in inventory.
    """
    biobank = minimal_payload()["biobanks"][0]
    biobank["mucp_source_records"] = [
        {"record_id": "RESP-2", "metadata": {"response_id": "RESP-2", "source_ids": ["SRC-2"]}},
        {"record_id": "RESP-1", "metadata": {"response_id": "RESP-1", "source_ids": ["SRC-1"]}},
    ]
    biobank["evidence"] = [{"survey": "MuCP", "source_record_id": f"RESP-{index}",
        "scope_label": "Collection reported", "question_id": "C.omics_data.wgs",
        "question_label": "WGS", "kind": "structured_answer", "normalized_value": "affirmed",
        "answer_state": "listed", "raw_answer": "X WGS"} for index in (1, 2)]
    biobank["thematic_groups"] = []

    text = combined.render_biobank_dossier(biobank, {"source_manifest": [
        {"source_id": "SRC-1", "filename": "one.pdf"},
        {"source_id": "SRC-2", "filename": "two.pdf"},
    ]})

    plain = text.replace(r"\allowbreak{}", "")
    assert "Response 1 (RESP-1)" in plain and "Response 2 (RESP-2)" in plain
    assert "[MuCP] WGS (Response 1; Collection reported)" in plain
    assert "[MuCP] WGS (Response 2; Collection reported)" in plain


def test_default_answers_use_normalized_checkbox_state_and_preserve_qualification():
    """Render plain answers, not machine triplets or raw option labels.

    Returns:
        None. Corrected normalized No, conditionality and qualifiers remain legible.
    """
    unmarked = {"survey": "MuCP", "question_id": "C.omics_data.wgs", "question_label": "WGS",
                "kind": "structured_answer", "answer_state": "unmarked",
                "normalized_value": "explicit_negative",
                "raw_answer": "WGS", "raw_text": None}
    selected = {**unmarked, "answer_state": "listed", "normalized_value": "affirmed",
                "raw_answer": "X WGS"}
    conditional = {"survey": "MuCP", "question_label": "Storage conditions", "kind": "text_field",
                   "answer_state": "conditional", "normalized_value": None,
                   "raw_text": "Only where consent permits", "qualifier_text": "subject to review"}

    assert combined.human_answer_rows(unmarked, False) == [("[MuCP] WGS", "No")]
    assert combined.human_answer_rows(selected, False) == [("[MuCP] WGS", "Yes")]
    not_asked = {**unmarked, "answer_state": "not_asked", "normalized_value": "unknown"}
    assert combined.human_answer_rows(not_asked, False) == [("[MuCP] WGS", "Unknown")]
    rows = combined.human_answer_rows(conditional, False)
    assert rows == [("[MuCP] Storage conditions", "Only where consent permits; subject to review")]
    extended = combined.human_answer_rows(unmarked, True)
    assert any("Normalized value" in label for label, _ in extended)
    assert any("Answer state" in label for label, _ in extended)


def test_structured_answers_follow_every_registry_normalized_state():
    """Use normalized semantic states across the complete raw MuCP registry.

    Returns:
        None. Compact output follows normalized state; raw registry states stay extended-only.
    """
    import json
    from pathlib import Path

    registry = json.loads((Path(__file__).parents[1] /
        "survey-mappings/mucp_answer_states_v1.json").read_text())
    labels = {"affirmed": "Yes", "explicit_negative": "No", "unknown": "Unknown",
              "conditional": "Conditional",
              "ambiguous_or_source_conflict": "Unknown (ambiguous or conflicting source evidence)"}
    for raw_state, specification in registry["states"].items():
        normalized = "explicit_negative" if raw_state == "unmarked" else specification["normalized_state"]
        item = {"survey": "MuCP", "kind": "structured_answer", "question_id": "C.omics_data.wgs",
                "question_label": "WGS", "answer_state": raw_state, "normalized_value": normalized,
                "raw_answer": "WGS" if normalized == "explicit_negative" else None, "raw_text": None}
        rows = combined.human_answer_rows(item, False)
        assert rows == [("[MuCP] WGS", labels[normalized])], raw_state
        extended = combined.human_answer_rows(item, True)
        assert any(value == raw_state for label, value in extended if label == "Answer state")
        assert raw_state not in str(rows)


def test_checkbox_text_keeps_substantive_original_wording_and_unknown_qualifiers():
    """Retain source detail after the readable state without repeating bare options.

    Returns:
        None. Tick/question duplicates may disappear, but substantive wording remains exact.
    """
    selected = {"survey": "MuCP", "kind": "structured_answer", "question_label": "WGS",
        "question_id": "C.omics_data.wgs", "normalized_value": "affirmed", "answer_state": "listed",
        "raw_answer": "X WGS (>5000 participants)", "raw_text": "X WGS (>5000 participants)"}
    bare = {**selected, "raw_text": "X WGS"}
    unknown = {"survey": "MuCP", "kind": "structured_answer", "question_label": "WGS",
        "question_id": "C.omics_data.wgs", "normalized_value": "unknown",
        "answer_state": "not_confirmed", "raw_answer": None, "raw_text": None,
        "qualifier_text": "Not confirmed by the submitting source"}

    selected_text = combined.human_answer_rows(selected, False)[0][1]
    bare_text = combined.human_answer_rows(bare, False)[0][1]
    unknown_text = combined.human_answer_rows(unknown, False)[0][1]

    assert selected_text.startswith("Yes") and ">5000 participants" in selected_text
    assert bare_text == "Yes"
    assert unknown_text == "Unknown; Not confirmed by the submitting source"


def test_dossier_starts_with_manifest_inventory_and_marks_missing_filenames():
    """Show manifest-backed files before answers and diagnose absent filenames.

    Returns:
        None. Inventories remain basename-only and missing data is never guessed.
    """
    biobank = minimal_payload()["biobanks"][0]
    biobank["mucp_source_records"] = [{"record_id": "RESP-1", "metadata": {
        "response_id": "RESP-1", "source_ids": ["SRC-1", "SRC-MISSING", "SRC-LONG"]}}]
    text = combined.render_biobank_dossier(biobank, {"source_manifest": [
        {"source_id": "SRC-1", "filename": "uploads/response one_50%.xlsx", "path": "/private/path"},
        {"source_id": "SRC-LONG", "filename": "survey_" + "segment_" * 30 + ".xlsx"},
        {"source_id": "SRC-MISSING", "path": "/must/not/show"},
    ]})

    assert text.index("MuCP response source files") < text.index("Complementary data access")
    assert r"response one\_50\%.xlsx" in text.replace(r"\allowbreak{}", "")
    clean_text = text.replace(r"\allowbreak{}", "")
    assert "Filename not supplied" in clean_text and "Diagnostic" in clean_text
    assert "survey" in text and ".xlsx" in text and r"\allowbreak{}" in text
    assert "/private/path" not in text and "must/not/show" not in text


def test_reported_quantity_uses_exact_bound_and_temporal_meanings():
    """Format quantity semantics without conflating strict and inclusive limits.

    Returns:
        None. TeX symbols preserve relation, approximation, time and qualifications.
    """
    format_quantity = combined.format_reported_quantity
    assert format_quantity({"value": 100, "unit": "samples", "relation": "less_than"}) == r"$<$100 samples"
    assert format_quantity({"value": 100, "unit": "samples", "relation": "at_most"}) == r"$\leq$100 samples"
    assert format_quantity({"value": 100, "unit": "samples", "relation": "approximately"}) == r"$\approx$100 samples"
    assert "approximately at most 100" in format_quantity({
        "value": 100, "unit": "samples", "relation": "approximate_upper_bound"})
    assert "0 individuals" in format_quantity({"value": 0, "unit": "individuals", "relation": "reported_value"})
    future = format_quantity({"value": 12, "unit": "individuals", "relation": "reported_value",
                              "temporal_status": "future", "qualifier_text": "after recruitment"})
    assert "future" in future and "after recruitment" in future
    assert "cumulative" in format_quantity({"value": 100, "unit": "individuals",
        "relation": "reported_value", "temporal_status": "cumulative"})
    assert "previous" in format_quantity({"value": 100, "unit": "individuals",
        "relation": "reported_value", "temporal_status": "previous"})


def test_scoped_quantity_table_has_source_prefixed_quantity_and_readable_scope():
    """Use strict source-unit proof and show compact tagged quantity context.

    Returns:
        None. Quantity semantics appear in the value column, not machine-code fields.
    """
    payload = minimal_payload()
    payload["biobanks"][0]["evidence"].append({
        "survey": "MuCP", "question_id": "C.sample_count", "scope_id": "scope-quantity",
        "question_label": "Sample count",
        "scope_label": "Collection with a distinctive name", "source_record_id": "RESP-1",
        "evidence_id": "E-Q", "extensions": {"reported_total": {
            "value": 100, "unit": "samples", "relation": "at_most", "temporal_status": "current"}},
        "raw_text": "at most 100 samples (current)", "qualifier_text": "subject to consent",
    })

    tex = combined.render_combined_tex(payload, {}).tex
    table = tex.split(r"\subsection{Reported quantities and collection context}", 1)[1].split(r"\subsection", 1)[0]

    assert r"p{0.20\linewidth}p{0.74\linewidth}" in table
    assert "[MuCP] Scope / criterion" not in table and "Scope / criterion" not in table
    assert "[MuCP]" in table
    assert r"$\leq$100 samples" in table
    assert r"reported\_value" not in table and "unspecified" not in table
    assert "Collection with a distinctive name" in table and "subject to consent" in table
    assert "Scope: submission;" not in table and "Original wording" not in table


def test_narrative_numeric_mentions_do_not_claim_the_indexed_unit():
    """Keep unowned index text absent and display its amount with unclear unit.

    Returns:
        None. Numeric mentions are not presented as authoritative classified totals.
    """
    payload = minimal_payload()
    payload["biobanks"][0]["mucp_source_records"] = [{"record_id": "RESP-1", "metadata": {
        "quantity_index": [{"field": "C.count", "value": 42, "unit": "individuals",
                            "relation": "reported_value", "context": "about 42 aliquots",
                            "qualifier_text": "across several preparations"}]}}]

    tex = combined.render_combined_tex(payload, {}).tex
    table = tex.split(r"\subsection{Reported quantities and collection context}", 1)[1].split(r"\subsection", 1)[0]

    assert "number mentioned in the answer, not a verified collection total" in table
    assert "[MuCP] [" in table and "42 unit unclear" in table
    assert "about 42 aliquots" not in table
    assert "across several preparations" in table


def test_owned_narrative_answer_is_retained_without_repeating_index_windows():
    """Render verified owned text once while retaining its full evidence in JSON.

    Returns:
        None. Index snippets alone remain absent; the complete owning answer is source tagged.
    """
    payload = minimal_payload()
    bank = payload["biobanks"][0]
    bank["mucp_source_records"] = [{"record_id": "RESP-OWNED", "metadata": {
        "response_id": "RESP-OWNED", "source_ids": ["SRC-OWNED"],
        "quantity_index": [{"field": "C.count", "value": 42, "unit": "individuals",
            "relation": "reported_value", "context": "rine cancer : 42", "evidence": [
                {"source_id": "SRC-OWNED", "locator": "word/document.xml:p[59]"}]}]},
        "evidence": [{"survey": "MuCP", "kind": "text_field", "question_id": "C.count",
            "source_record_id": "RESP-OWNED", "raw_text": "Uterine cancer : 42",
            "source_refs": [{"source_id": "SRC-OWNED", "locator": "word/document.xml:p[59]"}]}]}]
    bank["evidence"].append({"survey": "MuCP", "question_id": "C.count",
        "scope_id": "RESP-OWNED:submission", "scope_label": "Reported for this submission",
        "source_record_id": "RESP-OWNED", "evidence_id": "E-OWNED",
        "kind": "numeric_mention_not_additive", "value": 42, "unit": "unit_unclear",
        "raw_text": "Uterine cancer : 42", "answer_type": None,
        "source_refs": [{"source_id": "SRC-OWNED", "locator": "word/document.xml:p[59]"}]})
    # The cohort profile derives this row from evidence; preserve an independent raw snapshot.
    raw_snapshot = repr(bank["mucp_source_records"])

    tex = combined.render_combined_tex(payload, {}).tex
    table = tex.split(r"\subsection{Reported quantities and collection context}", 1)[1].split(r"\subsection", 1)[0]

    assert table.count("Uterine cancer : 42") == 1
    assert "context: rine cancer : 42" not in table
    assert "unit unclear" in table and "[MuCP]" in table
    assert repr(bank["mucp_source_records"]) == raw_snapshot


def test_combined_free_text_table_groups_by_canonical_id_and_masks_contacts():
    """Group combined free-text institution rows by IDs while preserving privacy.

    Returns:
        None. Shared names remain separate banks, repeated cells obey dtto, and
        standalone rendering without the combined option remains unchanged.
    """
    from so2_descriptive_report import _question_tables, render_statistics_sections

    question = {
        "question_type": "free_text",
        "free_text_rows": [
            {"country_code": "DE", "country": "DE", "institution": "Shared Name",
             "observation_id": "ID:DE_A", "text": "answer one",
             "raw_parent_answers": []},
            {"country_code": "DE", "country": "DE", "institution": "Shared Name",
             "observation_id": "ID:DE_A", "text": "answer two",
             "raw_parent_answers": []},
            {"country_code": "FR", "country": "FR", "institution": "Shared Name",
             "observation_id": "ID:FR_A", "text": "person@example.org",
             "raw_parent_answers": []},
        ],
    }
    ordinary = _question_tables(question)
    empty = _question_tables(question, table_biobank_repeated_entries="empty")
    combined = _question_tables(question, table_biobank_repeated_entries="dtto")
    assert ordinary.count("Shared Name") == 3
    assert empty.count("Shared Name &") == 2
    assert r"\emph{dtto}" not in empty
    assert combined.count("Shared Name &") == 2
    assert r"\emph{dtto}" in combined
    institution_list = _question_tables({
        "question_type": "single_choice",
        "contributions": [{"value": "Yes", "country": "DE", "institution": "Shared Name",
                           "repeated_response": False}],
    }, table_biobank_repeated_entries="dtto")
    assert "Value & Country & Institutions" in institution_list
    assert "Continued:" not in institution_list

    payload = {
        "question_id": "free-text", "label": "Free text", "question_type": "free_text",
        "population": {"N": 2, "A": 2, "M": 0}, "categories": [], "contributions": [],
        "free_text_rows": question["free_text_rows"],
    }
    rendered = render_statistics_sections(
        [{"survey": "SO2", "questions": [payload]}],
        {"table_biobank_repeated_entries": "empty"},
    ).tex
    assert "person@example.org" not in rendered
    assert "[contact redacted]" in rendered


def test_eligible_quantity_contribution_table_groups_and_labels_source_unit_scope():
    """Keep aggregate support rows attributable to a bank, source, unit and scope.

    Returns:
        None. Unclear units stay explicit and repeated bank cells use the selected
        combined-only mode without altering the aggregate payload.
    """
    aggregates = {"contributions": [
        {"biobank_id": "ID:DE_A", "unit": "unit_unclear", "value": 12,
         "basis": "submission_fallback", "modality_ids": ["wgs"],
         "scope_members": [{"label": "Cancer cohort"}]},
        {"biobank_id": "ID:DE_A", "unit": "donors", "value": 5,
         "basis": "collection", "modality_ids": ["wgs"],
         "scope_members": [{"label": "Rare disease collection"}]},
    ]}
    banks = [{"biobank_id": "ID:DE_A", "country": "DE", "name": "Bank & Institute"}]
    source_snapshot = repr(aggregates)

    tex = combined.render_quantity_contributions(
        aggregates, banks, {"table_biobank_repeated_entries": "dtto"})

    assert "[MuCP] 12 unit unclear" in tex
    assert "[MuCP] 5 donors" in tex
    assert "Cancer cohort" in tex and "Rare disease collection" in tex
    assert "Bank \\& Institute" in tex and r"\emph{dtto}" in tex
    assert repr(aggregates) == source_snapshot


def test_long_quantity_wording_uses_source_tagged_page_sized_answer_rows():
    """Split verbose owned source wording into tagged pageable answer rows.

    Returns:
        None. No single longtable row owns the complete source narrative cell.
    """
    payload = minimal_payload()
    long_text = "Opening source wording " + "retained qualifier phrase " * 1200 + "closing wording."
    payload["biobanks"][0]["evidence"].append({
        "survey": "MuCP", "question_id": "B.count", "scope_id": "scope-long",
        "question_label": "Number of individuals", "scope_label": "Collection Long",
        "source_record_id": "RESP-LONG", "evidence_id": "E-LONG",
        "extensions": {"reported_total": {"value": 42, "unit": "individuals",
            "relation": "reported_value", "temporal_status": "current"}},
        "raw_text": long_text,
    })

    tex = combined.render_combined_tex(payload, {}).tex
    table = tex.split(r"\subsection{Reported quantities and collection context}", 1)[1].split(r"\subsection", 1)[0]

    assert table.count("[MuCP] Reported answer") > 1
    assert "Original wording" not in table
    assert "Opening source wording" in table and "closing wording." in table


def test_extended_answer_rows_keep_plain_question_ids_for_single_tex_escape():
    """Return plain IDs from the helper so callers escape them exactly once.

    Returns:
        None. Extended evidence exposes raw IDs without pre-escaped TeX fragments.
    """
    item = {"survey": "MuCP", "kind": "structured_answer", "question_id": "C.omics_data.wgs",
        "question_label": "Whole-genome sequencing", "normalized_value": "affirmed",
        "answer_state": "listed", "raw_answer": True, "raw_text": None}

    rows = combined.human_answer_rows(item, True)
    source_row = next(value for label, value in rows if label == "Source / question / scope")

    assert "C.omics_data.wgs" in source_row
    assert r"\texttt{" not in source_row


def test_presentation_config_is_versioned_and_maps_group_ids_to_curated_titles(tmp_path):
    """Reject unversioned/bad presentation metadata and keep stable group labels.

    Args:
        tmp_path: Isolated directory for malformed presentation configuration JSON.

    Returns:
        None. Curated metadata is validated before being used for report labels.
    """
    import json
    from pathlib import Path

    config = combined.load_report_presentation(
        Path(__file__).parents[1] / "survey-mappings/so2_mucp_report_presentation.json")
    assert config["version"] == 1
    assert config["group_titles"]["MuCP.C.omics_data"] == "[MuCP] Part C: Reported OMICs data"
    catalogue = {
        "B": ["collection_design", "consent_and_policy", "demographics", "biospecimens",
              "available_data", "collection_infrastructure"],
        "C": ["consent_and_policy", "demographics", "biospecimens", "available_data",
              "omics_data", "collection_infrastructure"],
    }
    discovered_group_ids = {
        f"MuCP.{part}.{group}"
        for part, groups in catalogue.items()
        for group in groups
    }
    assert set(config["group_titles"]) == discovered_group_ids
    assert "MuCP.B.collection_design" in config["group_titles"]
    assert "MuCP.C.omics_data" in config["group_titles"]
    assert "MuCP.C.collection_design" not in config["group_titles"]
    assert "MuCP.B.omics_data" not in config["group_titles"]
    assert "affirmative evidence" not in " ".join(config["group_titles"].values()).casefold()
    path = tmp_path / "invalid-presentation.json"
    path.write_text(json.dumps({"version": "1", "group_titles": {}}))
    with pytest.raises(ValueError, match="version"):
        combined.load_report_presentation(path)


def test_curated_headings_cover_every_group_in_catalogue_fixture():
    """Render all known catalogue groups and require their curated headings.

    Returns:
        None. Catalogue coverage is checked from every discovered group, not a
        subset selected by report-interest filters.
    """
    from pathlib import Path

    config = combined.load_report_presentation(
        Path(__file__).parents[1] / "survey-mappings/so2_mucp_report_presentation.json")
    catalogue = {
        "B": ["collection_design", "consent_and_policy", "demographics", "biospecimens",
              "available_data", "collection_infrastructure"],
        "C": ["consent_and_policy", "demographics", "biospecimens", "available_data",
              "omics_data", "collection_infrastructure"],
    }
    discovered_groups = [
        {"question_id": f"MuCP.{part}.{group}", "label": f"Internal {group}", "part": part,
         "question_type": "multi_choice", "population": {"N": 1, "A": 1, "M": 0},
         "categories": [], "contributions": [], "free_text_rows": []}
        for part, groups in catalogue.items()
        for group in groups
    ]
    payload = minimal_payload()
    payload["descriptive_statistics"]["MuCP"]["groups"] = discovered_groups

    rendered = combined.render_combined_tex(payload, {})

    for group in discovered_groups:
        title = config["group_titles"][group["question_id"]]
        assert title in rendered.tex
    assert len(discovered_groups) == 12
    assert not any("curated title" in item for item in rendered.diagnostics)


def test_unmapped_group_uses_diagnostic_not_an_inferred_title():
    """Require curation for future groups without exposing internal group keys.

    Returns:
        None. Missing title mappings are reported and never title-cased automatically.
    """
    payload = minimal_payload()
    payload["descriptive_statistics"]["MuCP"]["groups"] = [{
        "question_id": "MuCP.C.future_internal_group", "label": "Part C: hidden group - affirmative evidence reported",
        "part": "C", "question_type": "multi_choice", "population": {"N": 1, "A": 1, "M": 0},
        "categories": [], "contributions": [], "free_text_rows": [],
    }]

    rendered = combined.render_combined_tex(payload, {})

    assert "hidden internal group" not in rendered.tex
    assert "affirmative evidence reported" not in rendered.tex
    assert any("MuCP.C.future_internal_group" in item and "curated title" in item
               for item in rendered.diagnostics)


@pytest.mark.parametrize("literal", [
    "Complete this submission; then seek approval.",
    'Preserve the quotation "RESP-A: source wording" exactly.',
    "Explain collection_or_submission_as_reported: in the source prose.",
])
def test_compact_cleanup_preserves_literal_prose_and_quoted_response_tokens(literal):
    """Keep provenance-like tokens inside substantive prose unchanged.

    Args:
        literal: Source sentence containing a token also used by serialization.

    Returns:
        None. Cleanup and human answers preserve the entire source sentence.
    """
    assert combined._compact_source_context(literal) == literal
    item = {"survey": "SO2", "kind": "text_field", "question_label": "Source question",
            "raw_text": literal}
    assert combined.human_answer_rows(item, False) == [("[SO2] Source question", literal)]
    assert combined._compact_source_context(
        "RESP-A: collection_or_submission_as_reported: submission: source_record_id: retained"
    ) == "retained"


def test_inventory_deduplicates_original_response_across_assigned_scope_records():
    """Aggregate nested assigned scopes by their original response and source ID.

    Returns:
        None. Shared sources appear once, equal filenames for distinct sources
        remain separate, and a response lacking provenance is still represented.
    """
    biobank = {"mucp_source_records": [
        {"record_id": "RESP-A::assigned::one", "metadata": {"response_id": "RESP-A",
            "source_ids": ["SRC-1"]}},
        {"record_id": "RESP-A::assigned::two", "metadata": {"response_id": "RESP-A",
            "source_ids": ["SRC-1", "SRC-2"], "full_evidence_source_ids": ["SRC-1"]}},
        {"record_id": "RESP-A::assigned::three", "metadata": {"response_id": "RESP-A"}},
        {"record_id": "RESP-B::assigned::one", "metadata": {"response_id": "RESP-B"}},
    ], "evidence": [{"source_record_id": "RESP-A::assigned::two",
        "source_refs": [{"source_id": "SRC-3"}]}]}
    manifest = [{"source_id": "SRC-1", "filename": "one.pdf"},
                {"source_id": "SRC-2", "filename": "one.pdf"},
                {"source_id": "SRC-3", "filename": "three.pdf"}]

    assert combined.dossier_source_rows(biobank, manifest) == [
        {"response_id": "RESP-A", "filename": "one.pdf"},
        {"response_id": "RESP-A", "filename": "one.pdf"},
        {"response_id": "RESP-A", "filename": "three.pdf"},
        {"response_id": "RESP-B", "filename": "Filename not supplied"},
    ]


def test_compact_table_puts_long_public_question_in_wide_value_column():
    """Keep a complete long prompt out of repeated narrow answer labels.

    Returns:
        None. The public 628-character prompt appears once, answer continuations
        use short source-tagged labels, and helper literal-pair semantics remain.
    """
    import json
    from pathlib import Path

    schema = json.loads((Path(__file__).parents[1] /
        "survey-mappings/so2_2025_descriptive_report.json").read_text())
    question = max(schema["questions"], key=lambda entry: len(entry["label"]))
    assert len(question["label"]) == 628
    answer = "Opening answer. " + "Synthetic source wording retained. " * 300 + "Closing answer."
    item = {"survey": "SO2", "kind": "text_field", "question_label": question["label"],
        "question_id": question["question_id"], "raw_text": answer,
        "scope_label": "Collection example", "response_label": "Response 2"}
    literal_label = f"[SO2] {question['label']} (Response 2; Collection example)"
    assert combined.human_answer_rows(item, False) == [(literal_label, answer)]

    tex = combined._evidence_table([item], False)

    assert "{}[SO2] Question & " + combined._tex(literal_label) in tex
    assert "{}[SO2] Answer & " in tex and "{}[SO2] Answer (continued) & " in tex
    assert tex.count(combined._tex(question["label"])) == 1
    assert "Opening answer." in tex and "Closing answer." in tex
    assert r"p{0.30\linewidth}p{0.66\linewidth}" in tex


def minimal_payload():
    """Build a redacted payload with source-labelled SO2 and MuCP narratives.

    Returns:
        Combined report payload for one synthetic overlapping biobank.
    """
    return {
        "biobanks": [{
            "biobank_id": "bbmri-eric:ID:XX_TEST",
            "id": "bbmri-eric:ID:XX_TEST",
            "name": "Test Institute",
            "country": "XX",
            "evidence": [
                {"survey": "SO2", "scope_id": "scope-1", "scope_label": "Biobank-wide",
                 "source_record_id": "S-1", "evidence_id": "E-1", "question_id": "so2_text_01",
                 "question_label": "SO2 topic", "kind": "text_field", "answer_state": "answered",
                 "normalized_value": "text", "raw_answer": "raw source answer",
                 "raw_text": "Answer at https://example.org/a_b?x=1; literal 50%_value; contact user@example.org",
                 "qualifier_text": "only under stated conditions",
                 "source_refs": [{"locator": "Sheet!row[4]"}]},
                {"survey": "MuCP", "scope_id": "scope-2", "scope_label": "Collection C1",
                 "source_record_id": "M-1", "evidence_id": "E-2", "question_id": "C.omics_data.wgs",
                 "question_label": "Whole-genome sequencing", "kind": "structured_answer",
                 "answer_state": "explicit_no", "normalized_value": "explicit_negative", "raw_answer": "No",
                 "raw_text": "No", "qualifier_text": "unless consent allows",
                 "source_refs": [{"locator": "responses[7]"}]},
                {"survey": "MuCP", "scope_id": "scope-2", "scope_label": "Collection C1",
                 "source_record_id": "M-1", "evidence_id": "E-3", "question_id": "A.submitter",
                 "question_label": "A.submitter", "kind": "respondent_context",
                 "raw_answer": "Ada Lovelace", "raw_text": "Ada Lovelace"},
                {"survey": "SO2", "scope_id": "scope-1", "scope_label": "Submission",
                 "source_record_id": "S-1", "evidence_id": "E-6", "question_id": "SO2.context.name",
                 "question_label": "Name", "kind": "respondent_context",
                 "raw_answer": "Grace Hopper", "raw_text": "Grace Hopper"},
                {"survey": "MuCP", "scope_id": "scope-2", "scope_label": "Collection C1",
                 "source_record_id": "M-1", "evidence_id": "E-4", "question_id": "A.email",
                 "question_label": "A.email", "kind": "respondent_context",
                 "raw_answer": "ada@example.org", "raw_text": "ada@example.org"},
            ],
            "scopes": [],
            "observations": [],
            "so2_source_records": [],
            "mucp_source_records": [],
            "thematic_groups": [{
                "title": "Complementary data access", "relationship": "related_or_complementary",
                "explanation": "Distinct source claims remain separate.",
                "questions": ["SO2:so2_text_01", "MuCP:C.omics_data.wgs"],
            }],
        }],
        "descriptive_statistics": {
            "SO2": {"questions": [{
                "question_id": "so2_text_01", "label": "SO2 topic", "question_type": "free_text",
                "population": {"N": 1, "A": 1, "M": 0}, "categories": [], "contributions": [],
                "free_text_rows": [{"text": "Answer at https://example.org/a_b?x=1; literal 50%_value; contact user@example.org",
                                    "survey": "SO2", "scope_label": "Biobank-wide", "source_record_id": "S-1",
                                    "evidence_id": "E-1", "institution": "Test Institute", "country": "XX"}],
            }]},
            "MuCP": {"questions": [], "groups": []},
            "cross_survey": {},
        },
    }


def test_every_answer_in_combined_report_has_source_tag_and_email_is_masked():
    """Combined text rows visibly identify the source while hiding contact details.

    Returns:
        None. Rendered report and dossier contain a source tag and no email address.
    """
    import re

    payload = minimal_payload()
    tex = combined.render_combined_tex(payload, {}).tex
    dossier = combined.render_biobank_dossier(payload["biobanks"][0], {})

    assert "[SO2]" in tex and "[SO2]" in dossier
    assert not re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", tex + dossier)
    assert r"50\%\_value" in tex
    assert r"\detokenize{https://example.org/a_b?x=1;}" in tex
    assert "No" in dossier and r"explicit\_no" not in dossier and "false" not in dossier
    assert "unless consent allows" in dossier and "only under stated conditions" in dossier
    assert "Collection C1" in dossier
    extended = combined.render_biobank_dossier(payload["biobanks"][0], {"extended_evidence": True})
    assert "responses[" in extended and "7]" in extended
    assert "M-1" in extended and "S-1" in extended
    assert "raw source answer" in dossier and "Answer at" in dossier
    assert "Ada Lovelace" not in dossier and "ada@example.org" not in dossier
    assert "Grace Hopper" not in dossier
    assert "Complementary data access" in dossier
    assert "user@example.org" in payload["descriptive_statistics"]["SO2"]["questions"][0]["free_text_rows"][0]["text"]


def test_explicit_contact_opt_in_shows_contact_fields_and_preserves_email():
    """Explicit contact opt-in exposes dedicated contact evidence and email text.

    Returns:
        None. Contact fields and email-shaped text appear with the opt-in.
    """
    dossier = combined.render_biobank_dossier(
        minimal_payload()["biobanks"][0], {"include_contact_details": True},
    )

    assert "Ada Lovelace" in dossier
    assert "Grace Hopper" in dossier
    assert "ada@example.org" in dossier
    assert "user@example.org" in dossier
    rendered = combined.render_combined_tex(
        minimal_payload(), {"include_contact_details": True},
    )
    assert "user@example.org" in rendered.tex


def test_theme_keeps_individual_sources_and_unmapped_evidence():
    """Theme grouping does not replace individual source contributions.

    Returns:
        None. Thematic sources remain separate and non-theme evidence is retained.
    """
    biobank = minimal_payload()["biobanks"][0]
    biobank["evidence"].append({
        "survey": "MuCP", "scope_id": "scope-3", "scope_label": "Collection C2",
        "source_record_id": "M-2", "evidence_id": "a" * 64, "question_id": "B.material.other",
        "question_label": "Other material", "kind": "text_field", "raw_answer": "tissue",
        "raw_text": "tissue", "answer_state": "text_reported",
        "source_refs": [{"locator": "source-record-" + "b" * 64}],
    })
    dossier = combined.render_biobank_dossier(biobank, {"extended_evidence": True})

    assert dossier.count("E-1") >= 1 and dossier.count("E-2") >= 1
    assert "Other material" in dossier and "tissue" in dossier and "Collection C2" in dossier
    assert "[SO2]" in dossier and "[MuCP]" in dossier
    assert r"\allowbreak{}" in dossier
    assert "a" * 64 not in dossier


def test_dossier_retains_root_narratives_and_warnings():
    """Dossier rendering keeps root narratives and source warnings visible.

    Returns:
        None. Source labels and warning/narrative wording survive composition.
    """
    biobank = minimal_payload()["biobanks"][0]
    biobank["narratives"] = [{"survey": "MuCP", "question_id": "narrative.root",
                               "raw_text": "Root narrative content", "scope_label": "Biobank-wide"}]
    biobank["warnings"] = [{"survey": "SO2", "message": "Source warning text",
                             "source_record_id": "S-1"}]

    dossier = combined.render_biobank_dossier(biobank, {})

    assert "Root narrative content" in dossier and "Source warning text" in dossier
    assert "[MuCP]" in dossier and "[SO2]" in dossier


def test_individual_documents_use_safe_hashed_filenames_and_shared_dossier_body():
    """Per-biobank documents reuse dossier content and avoid raw IDs in filenames.

    Returns:
        None. One stable safe filename maps to a standalone document with the dossier text.
    """
    payload = minimal_payload()
    documents = combined.render_individual_biobank_documents(payload, {})

    assert len(documents) == 1
    filename, tex = next(iter(documents.items()))
    assert ":" not in filename and filename.endswith(".tex")
    assert "[SO2]" in tex


def test_mucp_group_metadata_renders_a_distinct_group_bar_chart():
    """MuCP B/C group summaries are rendered as their own bar-chart questions.

    Returns:
        None. The group label and one stable standalone chart are present.
    """
    payload = minimal_payload()
    payload["descriptive_statistics"]["MuCP"]["groups"] = [{
        "question_id": "MuCP.B.biospecimens",
        "label": "Internal biospecimens",
        "question_type": "multi_choice",
        "population": {"N": 1, "A": 1, "M": 0},
        "categories": [{"value": "[MuCP] Serum", "count": 1, "percent": 100.0,
                        "percent_basis": "oIB"}],
        "contributions": [], "free_text_rows": [],
    }]

    payload["descriptive_statistics"]["MuCP"]["groups"][0]["option_coverage"] = [{
        "label": "Serum", "unknown_or_partial_count": 0,
        "qualified_positive_count": 0, "varying_positive_count": 0}]
    rendered = combined.render_combined_tex(payload, {})
    assert "Scope-state coverage" not in rendered.tex

    assert "[MuCP] Part B: Reported biospecimens" in rendered.tex
    assert "Internal biospecimens" not in rendered.tex
    assert any("mucp-b-biospecimens" in key for key in rendered.chart_documents)


def test_validated_upset_asset_object_renders_complete_and_empty_states():
    """ValidatedUpSetAssets state and UpSetFigure fields drive optional figures.

    Returns:
        None. Complete figures use valid single-backslash TeX commands; empty state is noted.
    """
    payload = minimal_payload()
    payload["upset_matrices"] = [{"id": "sample_sets", "sets": [], "rows": []}]
    complete = upsets.ValidatedUpSetAssets(
        "complete", {"sample_sets": upsets.UpSetFigure("sets.pdf", "deviation.pdf")},
    )
    rendered = combined.render_combined_tex(payload, {}, complete)
    empty = upsets.ValidatedUpSetAssets("empty", {})
    omitted = combined.render_combined_tex(payload, {}, empty)

    assert r"\includegraphics[width=\linewidth,height=0.82\textheight,keepaspectratio]{\detokenize{sets.pdf}}" in rendered.tex
    assert "Affirmative source evidence" not in rendered.tex
    assert r"\includegraphics[width=\linewidth,height=0.82\textheight,keepaspectratio]{\detokenize{deviation.pdf}}" not in rendered.tex
    opt_in = combined.render_combined_tex(payload, {"include_upset_deviations": True}, complete)
    assert r"\includegraphics[width=\linewidth,height=0.82\textheight,keepaspectratio]{\detokenize{deviation.pdf}}" in opt_in.tex
    assert "independence" in opt_in.tex.casefold()
    assert "not a significance test" in opt_in.tex.casefold()
    assert "omitted" in omitted.tex.casefold()


def test_classified_upset_title_and_caveat_replace_affirmative_jargon():
    """Render the curated title and limited no-dot interpretation for classified sets.

    Returns:
        None. The PDF does not reuse the old blanket absent-dot disclaimer.
    """
    payload = minimal_payload()
    payload["upset_matrices"] = [{"id": "mucp-biospecimens",
        "sets": [], "rows": [],
        "title": "[MuCP] Part C: Reported biospecimens", "cohort_N": 5, "matrix_N": 4,
        "interpretation": "For MuCP sets, no dot means explicit No across reported applicable scopes. Reports may vary by collection."}]
    assets = upsets.ValidatedUpSetAssets("complete", {
        "mucp-biospecimens": upsets.UpSetFigure("sets.pdf", "deviation.pdf")})
    tex = combined.render_combined_tex(payload, {}, assets).tex
    assert "Part C: Reported biospecimens" in tex
    assert "no dot means explicit No across reported applicable scopes" in tex
    assert "An absent dot does not establish absence" not in tex
    assert "affirmative reports" not in tex.casefold()


def test_report_sections_follow_mucp_enrichment_so2_appendix_order():
    """Combined report uses the approved MuCP-led major-section order.

    Returns:
        None. MuCP and enrichment precede remaining SO2 and appendix dossiers/review.
    """
    payload = minimal_payload()
    payload["descriptive_statistics"]["cross_survey"]["heatmaps"] = [{
        "definition": {"definition_id": "pair", "row_question_id": "q1",
                       "column_question_id": "q2", "row_categories": ["A", "B"],
                       "column_categories": ["C", "D"], "title": "Pair",
                       "interpretation": "Exploratory.", "conditional_summary": False},
        "pair": {"cells": {"A|C": 0, "A|D": 0, "B|C": 0, "B|D": 1}, "paired_denominator": 1},
        "question_labels": ["Question one", "Question two"],
    }]
    rendered = combined.render_combined_tex(payload, {})
    titles = ["Cohort overview", "MuCP cohort profile", "MuCP",
              "Cross-survey enrichment", "SO2", "Matching and source review"]
    positions = [rendered.tex.index(rf"\section{{{title}}}") for title in titles]

    assert positions == sorted(positions)
    assert "Question one" in rendered.tex and "Question two" in rendered.tex
    assert "Paired survey-participating biobanks: 1" in rendered.tex
    assert "Paired answering rows" not in rendered.tex


def test_heatmap_ticks_and_full_question_context():
    """Put short curated labels on axes and full original prompts below one heading.

    Returns:
        None. Combined panels use semantic labels without numeric keys or duplicate headings.
    """
    from pathlib import Path
    presentation = combined.load_report_presentation(
        Path("survey-mappings/so2_mucp_report_presentation.json"))["heatmaps"]["so2-returned_data_policy"]
    definition = {"definition_id": "so2-returned_data_policy", "row_question_id": "Y",
                  "column_question_id": "X", "row_categories": ["No", "Yes"],
                  "column_categories": ["No", "Yes"], "title": "Legacy x title",
                  "interpretation": "Descriptive.", "presentation": presentation}
    pair = {"cells": {f"{row}|{column}": 1 for row in ("No", "Yes") for column in ("No", "Yes")},
            "paired_denominator": 4}
    body, fragments, diagnostics = combined._render_heatmaps(
        {"heatmaps": [{"definition": definition, "pair": pair,
                       "question_labels": {"Y": "Full Y prompt?", "X": "Full X prompt?"}}]}, {})
    text = "\n".join(body)
    assert not diagnostics
    assert r"\subsection{Data-return experience and policy}" in text
    assert text.count("Data-return experience and policy") == 1
    assert r"\textbf{Y-axis question:} Full Y prompt?" in text
    assert r"\textbf{X-axis question:} Full X prompt?" in text
    assert "Legacy x title" not in text and "R1" not in text and "C1" not in text
    assert "xticklabels={{no},{yes}}" in text and "yticklabels={{no},{yes}}" in text
    assert fragments


def test_standalone_curated_heatmap_has_same_title_and_full_questions_once():
    """Exported chart documents carry the same curated context as combined panels.

    Returns:
        None. Heading and original Y/X questions appear exactly once in both views.
    """
    from pathlib import Path
    presentation = combined.load_report_presentation(
        Path("survey-mappings/so2_mucp_report_presentation.json"))["heatmaps"]["so2-returned_data_policy"]
    definition = {"definition_id": "so2-returned_data_policy", "row_question_id": "Y",
                  "column_question_id": "X", "row_categories": ["No", "Yes"],
                  "column_categories": ["No", "Yes"], "title": "Legacy x title",
                  "interpretation": "Descriptive.", "presentation": presentation}
    pair = {"cells": {f"{row}|{column}": 1 for row in ("No", "Yes") for column in ("No", "Yes")},
            "paired_denominator": 4}
    payload = minimal_payload()
    payload["descriptive_statistics"]["cross_survey"]["heatmaps"] = [{
        "definition": definition, "pair": pair,
        "question_labels": {"Y": "Full Y prompt?", "X": "Full X prompt?"}}]
    rendered = combined.render_combined_tex(payload, {})
    document = rendered.chart_documents["heatmap-so2-returned-data-policy"]
    for text in (rendered.tex, document):
        assert text.count("Data-return experience and policy") == 1
        assert text.count(r"\textbf{Y-axis question:} Full Y prompt?") == 1
        assert text.count(r"\textbf{X-axis question:} Full X prompt?") == 1
        assert "Legacy x title" not in text


def test_unknown_tick_category_requires_curated_mapping():
    """Reject unforeseen categories instead of inventing numeric fallback ticks.

    Returns:
        None. Unknown category fails before TeX or PDF publication.
    """
    from pathlib import Path
    presentation = combined.load_report_presentation(
        Path("survey-mappings/so2_mucp_report_presentation.json"))["heatmaps"]["so2-returned_data_policy"]
    definition = {"definition_id": "so2-returned_data_policy", "row_question_id": "Y",
                  "column_question_id": "X", "row_categories": ["Unknown future"],
                  "column_categories": ["No"], "title": "Pair", "interpretation": "Descriptive.",
                  "presentation": presentation}
    with pytest.raises(ValueError, match="curated.*category"):
        combined._render_heatmaps({"heatmaps": [{"definition": definition,
            "pair": {"cells": {"Unknown future|No": 1}, "paired_denominator": 1}}]}, {})


def test_unknown_combined_state_label_does_not_equate_unmarked_with_unknown():
    """Keep legacy state IDs but describe unresolved human evidence accurately.

    Returns:
        None. The PDF label does not contradict the present-unticked-is-No policy.
    """
    from survey_descriptive import STATE_LABELS
    assert STATE_LABELS["unknown_or_unmarked"] == "Unknown or indeterminate"


def test_presentation_preflight_rejects_new_category_even_for_omitted_pair():
    """Validate axes before rendering so omission cannot hide stale curation.

    Returns:
        None. An unknown category blocks all publication, not only chart output.
    """
    from pathlib import Path
    presentation = combined.load_report_presentation(
        Path("survey-mappings/so2_mucp_report_presentation.json"))
    definition = {"definition_id": "so2-returned_data_policy", "row_categories": ["Future"],
                  "column_categories": ["No"]}
    with pytest.raises(ValueError, match="curated.*category"):
        combined.validate_heatmap_presentation([definition], presentation)


def test_mucp_question_part_metadata_produces_distinct_b_and_c_headings():
    """MuCP question metadata preserves mandatory Part B and additional Part C sections.

    Returns:
        None. Both template parts retain their own question labels and headings.
    """
    payload = minimal_payload()
    question = {
        "question_type": "single_choice", "population": {"N": 1, "A": 1, "M": 0},
        "categories": [{"value": "unknown_or_unmarked", "count": 1, "percent": 100,
                        "percent_basis": "oIB"}], "contributions": [], "free_text_rows": [],
    }
    payload["descriptive_statistics"]["MuCP"]["questions"] = [
        {**question, "question_id": "mucp_b_q", "label": "Mandatory", "part": "B"},
        {**question, "question_id": "mucp_c_q", "label": "Additional", "part": "C"},
    ]

    rendered = combined.render_combined_tex(payload, {})

    assert "MuCP Part B: mandatory criteria" in rendered.tex
    assert "MuCP Part C: additional criteria" in rendered.tex
    assert "Mandatory" in rendered.tex and "Additional" in rendered.tex


@pytest.mark.skipif(shutil.which("xelatex") is None, reason="XeLaTeX is unavailable")
def test_redacted_combined_report_and_dossier_compile_in_two_passes():
    """XeLaTeX compiles combined and standalone dossier documents without partial output.

    Returns:
        None. Both self-contained documents compile through the standard two-pass path.
    """
    compiled_roots = []
    try:
        rendered = combined.render_combined_tex(minimal_payload(), {})
        pdf = combined._compile_document(rendered.tex, "combined-test", passes=2)
        compiled_roots.append(pdf.parent)
        assert "Font shape `TU/zi4/m/n' undefined" not in pdf.with_suffix(".log").read_text()
        dossier_tex = next(iter(combined.render_individual_biobank_documents(minimal_payload(), {}).values()))
        compiled_roots.append(combined._compile_document(dossier_tex, "dossier-test", passes=2).parent)
    finally:
        for root in compiled_roots:
            shutil.rmtree(root, ignore_errors=True)
