"""Check survey-independent descriptive statistics at the unique-biobank unit."""

import importlib


def test_missing_mucp_observation_counts_once_and_answered_pie_contains_only_no():
    """Count a missing question once alongside an explicit negative answer.

    Returns:
        None. Two biobanks contribute two category counts and only No enters the answered pie.
    """
    from survey_descriptive import build_combined_statistics
    from so2_descriptive_report import render_statistics_sections

    catalogue = {"SO2": [], "MuCP": [{"id": "C.serum", "label": "Serum", "type": "checkbox",
        "part": "C", "group": "biospecimens"}]}
    banks = [{"biobank_id": "NO", "country": "AT", "name": "No bank", "evidence": [],
        "observations": [{"survey": "MuCP", "question_id": "C.serum",
            "state": "explicitly_no_in_all_reported_applicable_scopes",
            "has_affirmative_evidence": False}]},
        {"biobank_id": "MISSING", "country": "AT", "name": "Missing bank", "evidence": [],
         "observations": []}]
    question = build_combined_statistics(banks, catalogue, {})["MuCP"]["questions"][0]

    assert question["population"] == {"N": 2, "A": 1, "M": 1}
    assert sum(category["count"] for category in question["categories"]) == 2
    assert [category for category in question["categories"] if category["value"] == "missing"] == []
    assert sum(category["count"] for category in question["categories"]
               if category["value"] == "Missing") == 1
    assert [(category["value"], category["count"]) for category in question["pie_categories"]
            if category["count"] and not category["excluded_from_chart"]] == [
                ("explicitly_no_in_all_reported_applicable_scopes", 1)]
    rendered = render_statistics_sections([{"survey": "MuCP", "questions": [question]}], {})
    answered = next(fragment for key, fragment in rendered.chart_fragments.items()
                    if key.endswith("answered-only"))
    assert "Explicit no in all reported applicable scopes" in answered
    assert "missing:" not in answered.casefold()
    assert answered.count(r"\path[fill=") == 1


def test_scope_summary_preserves_unknown_qualified_and_conflicting_categories():
    """Retain exceptional evidence states while representing missing once.

    Returns:
        None. Unknown, qualified and conflicting evidence stay distinct in categories and diagnostics.
    """
    from survey_descriptive import summarize_categorical

    states = ["unknown_or_unmarked", "qualified_only", "conflicting", "missing"]
    observations = [{"observation_id": str(index), "state": state}
                    for index, state in enumerate(states)]
    result = summarize_categorical({"question_id": "C.q", "scope_states": True,
        "question_type": "single_choice", "categories": states[:-1]}, observations,
        "unique_overlapping_biobank")
    assert {category["value"]: category["count"] for category in result["categories"]} == {
        "unknown_or_unmarked": 1, "qualified_only": 1, "conflicting": 1, "Missing": 1}
    assert result["diagnostics"]["states"] == dict.fromkeys(states, 1)
    assert [item["state"] for item in result["observations"]] == states


def test_unique_biobank_states_and_mucp_only_question():
    """Count each observation once and keep MuCP-only unknown states visible.

    Returns:
        None. Unknown state is not a negative response and repeated IDs are invalid.
    """
    module = importlib.import_module("survey_descriptive")
    definition = {"question_id": "C.unique", "label": "MuCP-only", "question_type": "single_choice",
                  "categories": ["reported_yes_in_one_or_more_scopes", "unknown_or_unmarked"]}
    observations = [{"observation_id": "A", "state": "reported_yes_in_one_or_more_scopes", "contribution_ids": ["a"]},
                    {"observation_id": "B", "state": "unknown_or_unmarked", "contribution_ids": ["b"]}]
    result = module.summarize_categorical(definition, observations, "unique_overlapping_biobank")
    assert result["population"]["N"] == 2
    assert result["question_id"] == "C.unique"
    assert {item["value"]: item["count"] for item in result["categories"]}["unknown_or_unmarked"] == 1
    assert result["population"] == {"N": 2, "A": 1, "M": 1}
    assert sum(row["count"] for row in result["pie_categories"]) == 2


def test_multiple_choice_percentage_uses_answering_biobanks():
    """Do not divide a multiselect frequency by the number of selections.

    Returns:
        None. Each option uses the same answering-biobank denominator.
    """
    module = importlib.import_module("survey_descriptive")
    definition = {"question_id": "q", "label": "Data", "question_type": "multi_choice", "categories": ["DNA", "Plasma"]}
    obs = [{"observation_id": "A", "state": "known", "selected_values": ["DNA", "Plasma"], "contribution_ids": ["a"]},
           {"observation_id": "B", "state": "known", "selected_values": ["DNA"], "contribution_ids": ["b"]}]
    result = module.summarize_categorical(definition, obs, "unique_overlapping_biobank")
    assert result["categories"][0]["percent"] == 100
    assert result["categories"][1]["percent"] == 50


def test_unreported_quantity_metadata_is_not_a_free_text_answer():
    """Do not print an extraction metadata dictionary as a substantive response.

    Returns:
        None. Empty quantity evidence stays missing; a reported zero remains an answer.
    """
    from survey_descriptive import summarize_text
    definition = {"question_id": "B.count", "label": "Count"}
    observation = [{"observation_id": "A", "contribution_ids": ["e1"]}]
    item = {"survey": "MuCP", "source_record_id": "R", "scope_id": "s1", "raw_text": None,
            "raw_answer": {"state": "not_reported", "reported_total": None, "numeric_mentions": []}}
    result = summarize_text(definition, observation, {"e1": item}, "unique_overlapping_biobank")
    assert result["population"] == {"N": 1, "A": 0, "M": 1}
    item["raw_answer"]["reported_total"] = 0
    result = summarize_text(definition, observation, {"e1": item}, "unique_overlapping_biobank")
    assert result["free_text_rows"][0]["text"] == "0"


def test_checkbox_groups_preserve_unknown_coverage_and_biobank_units():
    """Group bars must not relabel an unmarked questionnaire as an answered response row.

    Returns:
        None. Group population and rendering unit reflect explicit biobank evidence.
    """
    from survey_descriptive import build_combined_statistics
    catalogue = {"SO2": [], "MuCP": [{"id": "C.serum", "label": "Serum", "type": "checkbox_with_optional_qualifier", "part": "C", "group": "biospecimens"}]}
    biobanks = [{"biobank_id": "A", "country": "AT", "name": "A", "evidence": [], "observations": []}]
    group = build_combined_statistics(biobanks, catalogue, {})["MuCP"]["groups"][0]
    assert group["population"] == {"N": 1, "A": 0, "M": 1}
    assert group["analytical_unit"] == "unique_selected_biobank"
    assert group["option_coverage"][0]["unknown_or_partial_count"] == 1
    biobanks.append({"biobank_id": "B", "country": "AT", "name": "B", "evidence": [],
        "observations": [{"survey": "MuCP", "question_id": "C.serum", "state": "varying_across_scopes",
                          "has_affirmative_evidence": True, "flags": ["qualified", "partial_scope_coverage"]}]})
    group = build_combined_statistics(biobanks, catalogue, {})["MuCP"]["groups"][0]
    assert group["option_coverage"][0] == {"label": "Serum", "unknown_or_partial_count": 2,
                                          "qualified_positive_count": 1, "varying_positive_count": 1}


def test_all_unticked_group_is_classified_negative():
    """Keep an answered all-negative group distinct from a genuinely missing group.

    Returns:
        None. Eight explicit negatives form an all-zero pattern; unknown coverage is excluded.
    """
    from survey_descriptive import build_combined_statistics

    catalogue = {"SO2": [], "MuCP": [
        {"id": f"C.option_{index}", "label": f"Option {index}",
         "type": "checkbox_with_optional_qualifier", "part": "C", "group": "modalities"}
        for index in range(8)
    ]}
    no_bank = {"biobank_id": "NO", "country": "AT", "name": "No bank", "evidence": [],
        "observations": [{"survey": "MuCP", "question_id": f"C.option_{index}",
            "state": "explicitly_no_in_all_reported_applicable_scopes", "has_affirmative_evidence": False,
            "flags": [], "scope_ids": [f"no-{index}"]} for index in range(8)]}
    unknown_bank = {"biobank_id": "UNKNOWN", "country": "AT", "name": "Unknown bank", "evidence": [],
        "observations": []}

    group = build_combined_statistics([no_bank, unknown_bank], catalogue, {})["MuCP"]["groups"][0]

    assert group["population"] == {"N": 2, "A": 1, "M": 1}
    assert [item["count"] for item in group["categories"]] == [0] * 8
    assert [item["unknown_or_partial_count"] for item in group["option_coverage"]] == [1] * 8
    for question in build_combined_statistics([no_bank, unknown_bank], catalogue, {})["MuCP"]["questions"]:
        assert {item["observation_id"]: item["state"] for item in question["observations"]} == {
            "NO": "explicitly_no_in_all_reported_applicable_scopes", "UNKNOWN": "missing"}


def test_checkbox_frequency_retains_positive_with_incomplete_scope_coverage():
    """Keep known affirmative frequency while reserving scope exclusion for complete patterns.

    Returns:
        None. Frequency retains the reported Yes; a separate UpSet projection diagnoses scope gaps.
    """
    from survey_descriptive import build_combined_statistics

    catalogue = {"SO2": [], "MuCP": [
        {"id": "C.serum", "label": "Serum", "type": "checkbox", "part": "C", "group": "biospecimens"},
        {"id": "C.plasma", "label": "Plasma", "type": "checkbox", "part": "C", "group": "biospecimens"},
    ]}
    bank = {"biobank_id": "A", "country": "AT", "name": "A", "evidence": [], "observations": [
        {"survey": "MuCP", "question_id": "C.serum", "state": "reported_yes_in_one_or_more_scopes",
         "has_affirmative_evidence": True, "flags": ["partial_scope_coverage"]},
        {"survey": "MuCP", "question_id": "C.plasma", "state": "explicitly_no_in_all_reported_applicable_scopes",
         "has_affirmative_evidence": False, "flags": []},
    ]}

    group = build_combined_statistics([bank], catalogue, {})["MuCP"]["groups"][0]

    assert [item["count"] for item in group["categories"]] == [1, 0]
    assert group["population"] == {"N": 1, "A": 1, "M": 0}
    assert group["option_coverage"][0]["unknown_or_partial_count"] == 1
