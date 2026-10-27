"""Regression coverage for semantic, wrapped SO2 association-heatmap labels."""

from dataclasses import replace

import pytest
import so2_descriptive_report as report


def test_three_answer_heatmap_shows_values_without_numeric_legend():
    """Show consultation/yes/no values directly, retaining their canonical order.

    Returns:
        None after checking chart ticks, wrapped semantic titles and metadata roundtrip.
    """
    definitions = report.load_association_heatmap_registry("survey-mappings/so2_2025_association_heatmaps.json")
    definition = next(item for item in definitions if item.definition_id == "personnel_infrastructure")
    pair = {"cells": {f"{row}|{column}": 0 for row in definition.row_categories for column in definition.column_categories}, "paired_denominator": 0}
    tex = report._association_heatmap_fragment(definition, pair)
    assert "Need more info" in tex
    assert "xticklabels={1,2,3}" not in tex
    assert "yticklabels={1,2,3}" not in tex
    assert r"\textbf{Key:}" not in tex
    assert "Sufficient IT personnel" in tex
    assert "Infrastructure to host" in tex
    assert r"\parbox" in tex and r"\raggedright" in tex
    encoded = report._association_definition_payload(definition)
    decoded = report._association_definition_from_payload(encoded, "definition")
    assert report._association_definition_payload(decoded) == encoded
    assert definition.row_categories[0].startswith("I would need a consultation")


def test_unconfigured_categorical_heatmap_keeps_actual_answer_ticks():
    """Never turn categorical axes into numbered keys without presentation metadata.

    Returns:
        None after verifying exact labels with punctuation and wrapping.
    """
    definitions = report.load_association_heatmap_registry("survey-mappings/so2_2025_association_heatmaps.json")
    definition = replace(definitions[-1], row_categories=("Low, qualified", "High"), column_categories=("Never", "Sometimes", "Always"))
    pair = {"cells": {f"{row}|{column}": 0 for row in definition.row_categories for column in definition.column_categories}, "paired_denominator": 0}
    tex = report._association_heatmap_fragment(definition, pair)
    assert "Low, qualified" in tex
    assert "Sometimes" in tex
    assert "xticklabels={1,2,3}" not in tex
    assert "yticklabels={1,2}" not in tex


def test_five_category_heatmap_tick_boxes_fit_between_cell_centres():
    """Constrain each horizontal label to its available cell pitch, not a fixed width.

    Returns:
        None after verifying narrow boxes for the five-answer readiness panel.
    """
    definition = next(item for item in report.load_association_heatmap_registry("survey-mappings/so2_2025_association_heatmaps.json") if item.definition_id == "technical_readiness_qms")
    pair = {"cells": {f"{row}|{column}": 0 for row in definition.row_categories for column in definition.column_categories}, "paired_denominator": 0}
    tex = report._association_heatmap_fragment(definition, pair)
    assert r"\parbox[t]{0.073\linewidth}" in tex
    assert "Not addressed" in tex
    assert "Fully supported" in tex


def test_heatmap_presentation_rejects_missing_category_and_excess_title_lines():
    """Fail on unreviewed tick coverage or axis headings exceeding three lines.

    Returns:
        None after checking malformed presentation fails clearly.
    """
    definition = next(item for item in report.load_association_heatmap_registry("survey-mappings/so2_2025_association_heatmaps.json") if item.definition_id == "personnel_infrastructure")
    encoded = report._association_definition_payload(definition)
    encoded["presentation"]["row_tick_labels"].pop(definition.row_categories[0])
    with pytest.raises(report.InputError, match="categories"):
        report._association_definition_from_payload(encoded, "definition")
    encoded = report._association_definition_payload(definition)
    encoded["presentation"]["row_axis_lines"] = ["one", "two", "three", "four"]
    with pytest.raises(report.InputError, match="three"):
        report._association_definition_from_payload(encoded, "definition")
