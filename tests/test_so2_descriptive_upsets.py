"""Tests for deterministic SO2 descriptive UpSet registry and bundle helpers."""

import importlib
from pathlib import Path


module = importlib.import_module("so2_descriptive_upsets")
WORKTREE = Path(__file__).resolve().parents[1]


def test_production_registry_contains_the_eight_approved_definitions():
    """The registry preserves the user-approved figure selection and order.

    Returns:
        None. The registry preserves the user-approved figure selection and order.
    """
    definitions = module.load_upset_registry(WORKTREE / "survey-mappings/so2_2025_upsets.json")
    assert [item.definition_id for item in definitions] == [
        "q_009", "q_012", "q_018", "q_035", "q_042", "q_050",
        "q_042_q_044", "q_035_q_050",
    ]
    assert definitions[-1].question_selectors == ("q_035", "q_050")


def test_empty_asset_directory_is_a_deliberate_omission_state(tmp_path):
    """An explicit empty directory does not require R-rendered assets.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. An explicit empty directory does not require R-rendered assets.
    """
    assets = module.validate_upset_asset_bundle({}, WORKTREE / "survey-mappings/so2_2025_upsets.json", tmp_path)
    assert assets.state == "empty"
    assert assets.figures == {}


def test_generated_r_uses_the_supported_complexupset_set_size_api():
    """Generated R stays compatible with the repository's ComplexUpset renderer.

    Returns:
        None. Generated R stays compatible with the repository's ComplexUpset renderer.
    """
    source = module._renderer_source()
    assert "intersection_size" not in source
    assert "set_sizes = (" in source
    assert "ComplexUpset::upset_set_size()" in source


def test_upset_display_label_is_short_but_retains_source_question_prefix():
    """Long categories cannot make the UpSet set-size panel illegible.

    Returns:
        None. Long categories cannot make the UpSet set-size panel illegible.
    """
    label = "q_018::Other standards (any other terminologies, ontologies, common data models, or exchange formats) (please specify):"
    shortened = module._short_display_label(label)
    assert shortened == "q_018::Other standards (please specify)"
    assert len(shortened) <= 52


def test_single_question_display_labels_do_not_need_source_prefixes():
    """Only combined UpSets require question prefixes to prevent collisions.

    Returns:
        None. Only combined UpSets require question prefixes to prevent collisions.
    """
    assert module._short_display_label("Other standards (please specify):") == "Other standards (please specify)"
