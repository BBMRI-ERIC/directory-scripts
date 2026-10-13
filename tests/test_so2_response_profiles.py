"""Test joint SO2 profiles and their integration without changing MuCP rendering."""

from collections import Counter
from copy import deepcopy

import pytest

from test_so2_descriptive_report import structured_report_question, report_payload


def profile_questions():
    """Build four synthetic legal-barrier items with joint and exceptional states.

    Returns:
        Four single-choice questions over three matched observation identities.
    """
    vectors = [("never",) * 4, ("frequently", "never", "Missing", "Conflicting answers"), ("never",) * 4]
    questions = []
    for index in range(4):
        values = [vector[index] for vector in vectors]
        counts = Counter(values)
        missing = counts["Missing"]
        categories = [{"value": value, "count": count, "percent_base": 3, "percent": 100*count/3}
                      for value, count in counts.items()]
        questions.append(structured_report_question(
            question_id=f"q_{63+index:03d}_legal", question_type="single_choice",
            label=f"Legal barriers: item {index+1}",
            form={"matrix_parent": "Legal barriers", "matrix_row": f"Item {index+1}"},
            population={"N": 3, "A": 3-missing, "M": missing, "blank_rows": missing},
            categories=categories, pie_categories=[{**c, "excluded_from_chart": c["value"] == "Missing"} for c in categories],
            contributions=[{"source_row": i+5, "value": value, "country": "CZ", "institution": "Test", "repeated_response": False}
                           for i,value in enumerate(values)],
        ))
    return questions


def test_profile_aggregation_is_joint_exact_and_immutable():
    """Each analytical observation belongs to one full, source-linked answer pattern.

    Returns:
        None. Missing/conflict survive, duplicates count once per observation, inputs stay unchanged.
    """
    from so2_response_profiles import build_profile_groups

    questions = profile_questions()
    before = deepcopy(questions)
    group = build_profile_groups(questions)[0]
    assert group["N"] == 3 and len(group["profiles"]) == 2
    assert group["profiles"][0]["count"] == 2
    assert group["profiles"][0]["source_rows"] == [5, 7]
    assert group["profiles"][1]["answers"] == ["frequently", "never", "Missing", "Conflicting answers"]
    assert sum(p["count"] for p in group["profiles"]) == 3
    assert questions == before


def test_profile_groups_fail_on_incomplete_or_duplicate_identities():
    """Reject alignment errors instead of silently manufacturing joint answers.

    Returns:
        None. Missing items and repeated or mismatched source identities fail clearly.
    """
    from so2_response_profiles import build_profile_groups

    questions = profile_questions()
    with pytest.raises(ValueError, match="four"):
        build_profile_groups(questions[:3])
    questions[0]["contributions"].append(deepcopy(questions[0]["contributions"][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        build_profile_groups(questions)
    questions = profile_questions()
    questions[0]["contributions"][0]["source_row"] = 99
    with pytest.raises(ValueError, match="identities"):
        build_profile_groups(questions)


def test_profile_categories_and_totals_are_not_silently_repaired():
    """Wrong answer scales and inconsistent aggregates fail instead of changing evidence.

    Returns:
        None. Incompatible ordinal categories and altered published totals fail clearly.
    """
    from so2_response_profiles import build_profile_groups

    questions = profile_questions()
    questions[0]["categories"][0]["count"] += 1
    with pytest.raises(ValueError, match="totals"):
        build_profile_groups(questions)
    questions = profile_questions()
    for row in questions[0]["contributions"]:
        if row["value"] == "never":
            row["value"] = "excellent"
    questions[0]["categories"][0]["value"] = "excellent"
    with pytest.raises(ValueError, match="category"):
        build_profile_groups(questions)


def test_duplicate_categories_and_missing_counts_fail_closed():
    """Never hide invalid aggregate counts behind a dictionary overwrite or missingness.

    Returns:
        None. Duplicate categories and contradictory A/M totals cannot produce profiles.
    """
    from so2_response_profiles import build_profile_groups

    questions = profile_questions()
    original = deepcopy(questions[0]["categories"][0])
    questions[0]["categories"][0]["count"] = 4
    questions[0]["categories"].append(original)
    with pytest.raises(ValueError, match="Duplicate category"):
        build_profile_groups(questions)
    questions = profile_questions()
    questions[0]["population"].update(A=2, M=1)
    with pytest.raises(ValueError, match="missing"):
        build_profile_groups(questions)


def test_short_profile_headers_preserve_barrier_polarity():
    """Negative barriers must not become positive availability labels when shortened.

    Returns:
        None. Lack, uncertainty and restrictions remain clear in figure headers.
    """
    from so2_response_profiles import PROFILE_GROUPS

    legal, organisational = PROFILE_GROUPS[:2]
    assert "Unclear" in legal[3][2]
    assert "restrictions" in legal[3][3]
    assert "Lack" in organisational[3][0]
    assert "unclear" in organisational[3][2]


def test_profile_rows_clear_three_line_headers():
    """Keep the first coloured row below the longest curated column header.

    Returns:
        None. Both profile variants reserve explicit clearance before row one.
    """
    from so2_response_profiles import build_profile_groups, profile_fragment

    group = build_profile_groups(profile_questions())[0]
    for complete in (False, True):
        assert "at (3,-20.00)" in profile_fragment(group, complete, str)


def test_profile_figures_and_paths_are_only_in_standalone_so2():
    """Both profile graphs stay in their matrix section and export like other figures.

    Returns:
        None. Two bounded fragments/paths are produced, but generic MuCP sections are untouched.
    """
    import so2_descriptive_report as report

    payload = report_payload(profile_questions()[0])
    payload["questions"] = profile_questions()
    result = report.render_descriptive_tex(payload, "charts")
    keys = [key for key in result.chart_fragments if key.startswith("profiles-")]
    assert keys == ["profiles-legal-barriers-top12", "profiles-legal-barriers-complete"]
    assert all(key in result.chart_documents and key in result.chart_paths for key in keys)
    assert "0.82\\textheight" in result.chart_fragments[keys[1]]
    assert "response_profiles" in payload
    generic = report.render_statistics_sections([{"survey": "MuCP", "questions": profile_questions()}], {})
    assert not any(key.startswith("profiles-") for key in generic.chart_fragments)
