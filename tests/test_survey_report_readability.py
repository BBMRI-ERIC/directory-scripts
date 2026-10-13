"""Pin combined-report readability, chart policies and optional dossier behavior."""


def test_default_dossiers_are_omitted():
    """Leave dossiers in JSON but omit their PDF appendix unless requested.

    Returns:
        None. Main report appendix inclusion follows the explicit option only.
    """
    from test_survey_combined_report import minimal_payload
    from survey_combined_report import render_combined_tex
    payload = minimal_payload()
    default = render_combined_tex(payload, {}).tex
    assert "Biobank evidence dossiers" not in default
    assert "Biobank evidence dossiers" in render_combined_tex(payload, {"include_dossiers": True}).tex
    assert "Matching and source review" in default


def test_quantity_labels_are_reader_facing():
    """Explain material/data count differences without implementation jargon.

    Returns:
        None. Literal source evidence remains separate from display terminology.
    """
    from survey_combined_quantity_views import quantity_display_labels
    assert quantity_display_labels({"kind": "biospecimen"})["kind"] == "Material type"
    assert quantity_display_labels({"kind": "data_modality"})["kind"] == "Data type"


def test_combined_all_only_pie_policy():
    """Combined question sections can request only the all-participant chart.

    Returns:
        None. Default standalone pie variant policy remains unchanged.
    """
    from so2_descriptive_report import render_statistics_sections
    item = {"question_id": "q", "label": "Question", "question_type": "single_choice",
            "population": {"N": 2, "A": 1, "M": 1},
            "categories": [{"value": "Yes", "count": 1}, {"value": "Missing", "count": 1}],
            "contributions": [], "free_text_rows": []}
    rendered = render_statistics_sections([{"survey": "MuCP", "label": "MuCP", "questions": [item]}], {"pie_variants": "all_only"})
    assert len(rendered.chart_fragments) == 1


def test_selected_cohort_chart_unit_is_not_response_rows():
    """Label selected-cohort marks as participating banks, not overlapping banks.

    Returns:
        None. Wider cohorts retain the correct survey-participant denominator.
    """
    from so2_descriptive_report import _chart_unit
    assert _chart_unit({"analytical_unit": "unique_selected_biobank", "question_type": "multi_choice"}) == "survey-participating biobanks"


def test_profile_uses_plain_language():
    """Keep technical reconciliation terminology out of reader explanations.

    Returns:
        None. JSON still retains full source reconciliation evidence.
    """
    from test_survey_combined_report import minimal_payload
    from survey_combined_report import render_combined_tex
    assert "provenance-reconciled" not in render_combined_tex(minimal_payload(), {}).tex
