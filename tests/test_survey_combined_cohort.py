"""Verify join selection and survey participation without source-row inflation."""

import pytest


@pytest.mark.parametrize("mode,expected", [
    ("inner", ["B"]), ("all-MuCP", ["B", "C"]),
    ("all-SO2", ["A", "B"]), ("outer", ["A", "B", "C"]),
])
def test_join_selection(mode, expected):
    """Select distinct IDs according to the requested survey join.

    Args:
        mode: Requested join option.
        expected: Independently specified sorted selected IDs.

    Returns:
        None. Selection and intersection are asserted separately.
    """
    from survey_combined_cohort import select_biobank_cohort
    result = select_biobank_cohort(["B", "A", "A"], ["C", "B"], mode)
    assert result["selected_ids"] == expected
    assert result["intersection_ids"] == ["B"]


def test_default_and_invalid_modes():
    """Default to all MuCP and reject undocumented join aliases.

    Returns:
        None. Invalid modes raise configuration errors.
    """
    from survey_combined_cohort import select_biobank_cohort
    assert select_biobank_cohort(["A"], ["B"])["selected_ids"] == ["B"]
    for value in ("left", "right", "all-mucp", ""):
        with pytest.raises(ValueError):
            select_biobank_cohort([], [], value)


def test_participation_filter():
    """Exclude absent surveys instead of manufacturing unanswered records.

    Returns:
        None. Both-survey analyses select only actual participants.
    """
    from survey_combined_cohort import survey_participating_biobanks
    banks = [{"biobank_id": "B", "survey_participation": {"SO2": True, "MuCP": True}},
             {"biobank_id": "C", "survey_participation": {"SO2": False, "MuCP": True}}]
    assert len(survey_participating_biobanks(banks, ["MuCP"])) == 2
    assert [b["biobank_id"] for b in survey_participating_biobanks(banks, ["SO2", "MuCP"])] == ["B"]


@pytest.mark.parametrize("mode,n", [("inner", 1), ("all-MuCP", 2), ("all-SO2", 2), ("outer", 3)])
def test_join_preserves_matching_inventory(mode, n):
    """Keep independent acceptance counts intact while selecting the cohort.

    Args:
        mode: Join mode to exercise against accepted exclusive records.
        n: Expected analytical bank count.

    Returns:
        None. All source status counts are conserved.
    """
    from survey_combined import build_combined_payload, group_sources
    from survey_evidence import SourceRecord, ResolutionRecord
    groups = []
    for survey, ids in (("SO2", ["A", "B"]), ("MuCP", ["B", "C"])):
        records = [SourceRecord({"record_id": survey + bid, "survey": survey, "evidence": [], "scopes": []}) for bid in ids]
        decisions = [ResolutionRecord({"source_record_id": r.data["record_id"], "status": "accepted", "biobank_id": "bbmri-eric:ID:AT_" + bid}) for r, bid in zip(records, ids)]
        groups.append(group_sources(records, decisions))
    payload = build_combined_payload(*groups, {}, {}, join=mode)
    assert len(payload["biobanks"]) == n
    assert payload["matching_summary"]["overlapping_biobanks"] == 1
    assert payload["metadata"]["cohort"]["join"] == mode
    for survey in ("SO2", "MuCP"):
        assert payload["matching_breakdown"]["surveys"][survey]["status_counts"]["accepted"] == 2


def test_statistics_distinguish_absent_survey():
    """Keep absent survey participants out of the questionnaire denominator.

    Returns:
        None. MuCP-only banks never create unanswered SO2 submissions.
    """
    from survey_descriptive import build_combined_statistics
    banks = [{"biobank_id": bid, "name": bid, "country": "AT", "evidence": [],
              "survey_participation": {"SO2": bid == "B", "MuCP": True},
              "observations": [{"survey": "SO2", "question_id": "q", "state": "known",
                                "selected_values": ["Yes"], "contribution_ids": []}] if bid == "B" else []}
             for bid in ("B", "C")]
    result = build_combined_statistics(banks, {"SO2": [{"question_id": "q", "label": "Question",
                                      "question_type": "single_choice", "categories": ["Yes", "No"]}],
                                      "MuCP": [{"question_id": "B.example", "label": "Example", "type": "checkbox", "part": "B", "group": "design"}]}, {})
    question = result["SO2"]["questions"][0]
    assert question["population"] == {"N": 1, "A": 1, "M": 0}
    assert result["SO2"]["participation"] == {"selected_N": 2, "participating_N": 1, "no_response_N": 1}
    assert result["MuCP"]["groups"][0]["analytical_unit"] == "unique_selected_biobank"


def test_shared_upset_excludes_absent_survey():
    """Never turn a missing questionnaire into an empty intersection.

    Returns:
        None. Shared matrix population is limited to both-survey participation.
    """
    from survey_descriptive import build_combined_upset_matrix
    banks = [{"biobank_id": bid, "name": bid, "country": "AT",
              "survey_participation": {"SO2": bid == "B", "MuCP": True},
              "observations": [{"survey": "SO2", "question_id": "q", "state": "known", "selected_values": []}] if bid == "B" else []}
             for bid in ("B", "C")]
    definition = {"id": "shared", "questions": ["SO2:q", "MuCP:C.q"],
                  "projection": "affirmative_evidence_pattern"}
    matrix = build_combined_upset_matrix(definition, banks)
    assert matrix["participating_N"] == 1
    assert matrix["no_survey_response_count"] == 1
    assert {row["observation_id"] for row in matrix["rows"]} == {"B"}


def test_version_two_requires_explicit_cohort():
    """Reject an edited v2 payload lacking its cohort membership contract.

    Returns:
        None. Wider-cohort semantics cannot silently fall back to legacy defaults.
    """
    from survey_combined import build_combined_payload, group_sources, validate_combined_payload
    payload = build_combined_payload(group_sources([], []), group_sources([], []), {}, {})
    payload.update(question_catalogues={"SO2": [], "MuCP": []}, source_manifest=[])
    del payload["metadata"]["cohort"]
    with pytest.raises(ValueError, match="cohort"):
        validate_combined_payload(payload)
