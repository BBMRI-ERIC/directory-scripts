"""Verify exact shared-UpSet membership and stable bar identity."""


def test_ties_and_empty_intersection_have_exact_members():
    """Resolve equal-height bars by bits and preserve the observed empty pattern.

    Returns:
        None. Every classifiable bank appears exactly once under a stable bar ID.
    """
    from survey_combined_intersections import build_intersection_catalogue
    matrix = {"sets": ["a", "b"], "set_labels": ["DNA", "Plasma"], "rows": [
        {"observation_id": "B", "country": "IT", "institution": "Same", "a": True, "b": False},
        {"observation_id": "A", "country": "CZ", "institution": "Same", "a": False, "b": True},
        {"observation_id": "C", "country": "AT", "institution": "Empty", "a": False, "b": False}]}
    result = build_intersection_catalogue(matrix)
    assert [r["bar_id"] for r in result] == ["I1", "I2", "I3"]
    assert [r["pattern"] for r in result] == [[False, False], [False, True], [True, False]]
    assert [r["biobank_ids"] for r in result] == [["C"], ["A"], ["B"]]
    assert sum(r["count"] for r in result) == 3


def test_duplicate_bank_is_not_counted_twice():
    """Reject multiple analytical matrix rows for a single canonical identity.

    Returns:
        None. Duplicated banks cannot inflate intersection heights.
    """
    import pytest
    from survey_combined_intersections import build_intersection_catalogue
    row = {"observation_id": "A", "country": "CZ", "institution": "A", "a": True}
    with pytest.raises(ValueError, match="Duplicate"):
        build_intersection_catalogue({"sets": ["a"], "rows": [row, row]})


def test_membership_table_names_pattern_and_country():
    """Place labelled country-grouped bank membership below a shared figure.

    Returns:
        None. Table identifies the corresponding exclusive intersection, not set size.
    """
    from survey_combined_intersections import build_intersection_catalogue
    from survey_combined_report import render_intersection_membership_table
    matrix = {"sets": ["a"], "set_labels": ["DNA"], "rows": [
        {"observation_id": "A", "country": "CZ", "institution": "Name & Lab", "a": True}]}
    tex = render_intersection_membership_table(build_intersection_catalogue(matrix), {})
    assert "I1" in tex and "DNA" in tex and "CZ" in tex and r"Name \& Lab" in tex
