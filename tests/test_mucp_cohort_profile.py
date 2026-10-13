"""Tests for non-additive MuCP sizes and source-labelled SO2 enrichment."""

import copy

import pytest

import survey_descriptive


def bank(identifier, amounts):
    """Build a synthetic bank with explicit source quantity semantics.

    Args:
        identifier: Unique analytical biobank ID.
        amounts: Tuples of unit, value and relationship in distinct source scopes.

    Returns:
        Minimal dossier with scoped MuCP quantities and no invented totals.
    """
    return {"biobank_id": identifier, "country": "XX", "name": identifier,
        "mucp_source_records": [], "observations": [],
        "evidence": [{"survey": "MuCP", "question_id": "B.count", "evidence_id": f"{identifier}-{i}",
            "source_record_id": f"M-{i}", "scope_id": f"scope-{i}", "scope_label": f"Collection {i}",
            "extensions": {"reported_total": {"unit": unit, "value": value, "relation": relation,
                "temporal_status": "unspecified"}}, "raw_text":
                f"{ {'reported_value': '', 'at_most': 'at most '}.get(relation, '')}{value} {unit}"}
            for i, (unit, value, relation) in enumerate(amounts)]}


def test_sizes_count_banks_not_numeric_mentions_or_overlapping_scopes():
    """Retain scoped quantities without summing or treating bounds as exact.

    Returns:
        None. Profile states partition the unique-bank cohort for each unit.
    """
    banks = [bank("A", [("individuals", 100, "reported_value")]),
        bank("B", [("individuals", 100, "reported_value"), ("individuals", 200, "reported_value")]),
        bank("C", [("samples", 500, "at_most")]), bank("D", [])]
    profile = survey_descriptive.build_mucp_cohort_profile(banks)
    assert profile["cohort_N"] == 4
    donors = profile["sizes"]["donors"]
    assert donors["biobanks_with_quantity_evidence"] == 2
    assert donors["biobanks_with_scoped_reported_sizes"] == 2
    assert donors["states"] == {"single_reported_scope": 1, "multiple_scopes_or_values": 1,
        "qualified_or_bound": 0, "numeric_mentions_only": 0, "missing": 2}
    assert "total" not in donors
    assert len(donors["rows"]) == 3
    assert profile["sizes"]["samples"]["states"]["qualified_or_bound"] == 1


def test_index_units_are_unverified_and_year_mentions_stay_out_of_size_profile():
    """Retain plausible index quantities as unclear, not as source-proven units.

    Returns:
        None. The index sample unit is not proof and year values are excluded.
    """
    bb = bank("A", [])
    bb["mucp_source_records"] = [{"record_id": "M", "metadata": {"quantity_index": [
        {"unit": "samples", "value": 42, "field": "B.count", "context": "42 samples",
            "relation": "reported_value", "status": "reported_numeric_mention_not_additive"},
        {"unit": "years", "value": 10, "field": "B.count"}]}}]
    sizes = survey_descriptive.build_mucp_cohort_profile([bb])["sizes"]
    assert sizes["samples"]["states"]["numeric_mentions_only"] == 0
    assert sizes["samples"]["biobanks_with_quantity_evidence"] == 0
    assert sizes["unit_unclear"]["states"]["numeric_mentions_only"] == 1
    assert sizes["unit_unclear"]["rows"][0]["source_record_id"] == "M"
    assert sizes["unit_unclear"]["rows"][0]["source_unit"] is None
    assert sizes["unit_unclear"]["rows"][0]["index_unit"] == "samples"
    assert set(sizes) == {"donors", "samples", "aliquots", "unit_unclear"}


def test_equal_part_b_and_c_counts_are_not_one_scoped_quantity():
    """Identical numbers in different criteria do not establish the same cohort.

    Returns:
        None. Part B/C evidence stays separate and cannot create a single-size band.
    """
    import copy
    bb = bank("A", [("individuals", 100, "reported_value")])
    second = copy.deepcopy(bb["evidence"][0])
    second.update(question_id="C.count", evidence_id="A-C")
    bb["evidence"].append(second)
    summary = survey_descriptive.build_mucp_cohort_profile([bb])["sizes"]["donors"]
    assert summary["states"]["multiple_scopes_or_values"] == 1
    assert sum(summary["size_bands"].values()) == 0


def test_profile_recovers_owned_answer_text_without_adopting_index_unit():
    """Use full source text only through an exact owning question reference.

    Returns:
        None. Recovered narrative and unverified unit remain separately visible.
    """
    bb = bank("IRE", [])
    bb["mucp_source_records"] = [{"record_id": "M-IRE",
        "evidence": [{"survey": "MuCP", "kind": "text_field", "question_id": "B.count",
            "source_record_id": "M-IRE", "raw_text": "Uterine cancer : 64",
            "source_refs": [{"source_id": "SRC", "locator": "word/document.xml:p[59]"}]}],
        "metadata": {"source_ids": ["SRC"], "quantity_index": [{"field": "B.count", "unit": "individuals", "value": 64,
            "context": "rine cancer : 64", "status": "reported_numeric_mention_not_additive",
            "evidence": [{"source_id": "SRC", "locator": "word/document.xml:p[59]"}]}]},
    }]

    profile = survey_descriptive.build_mucp_cohort_profile([bb])

    row = profile["sizes"]["unit_unclear"]["rows"][0]
    assert row["raw_text"] == "Uterine cancer : 64"
    assert row["source_question_id"] == "B.count"
    assert row["unit"] == "unit_unclear"
    assert row["source_unit"] is None
    assert row["index_unit"] == "individuals"
    assert row["index_status"] == "reported_numeric_mention_not_additive"
    assert "answer_type" not in row
    assert profile["sizes"]["donors"]["states"]["numeric_mentions_only"] == 0


def test_profile_prefers_owned_literal_unit_over_conflicting_index_classification():
    """Keep source and index unit labels distinct when their classifications disagree.

    Returns:
        None. A source-proven sample answer cannot enter donor-size statistics.
    """
    bb = bank("IRE", [])
    bb["mucp_source_records"] = [{"record_id": "M-IRE",
        "evidence": [{"survey": "MuCP", "kind": "text_field", "question_id": "B.count",
            "source_record_id": "M-IRE", "raw_text": "64 samples",
            "source_refs": [{"source_id": "SRC", "locator": "word/document.xml:p[59]"}]}],
        "metadata": {"source_ids": ["SRC"], "quantity_index": [{"field": "B.count",
            "unit": "individuals", "value": 64, "context": "64 samples",
            "evidence": [{"source_id": "SRC", "locator": "word/document.xml:p[59]"}]}]},
    }]

    profile = survey_descriptive.build_mucp_cohort_profile([bb])

    row = profile["sizes"]["samples"]["rows"][0]
    assert row["unit"] == "samples"
    assert row["source_unit"] == "samples"
    assert row["index_unit"] == "individuals"
    assert profile["sizes"]["donors"]["states"]["numeric_mentions_only"] == 0


@pytest.mark.parametrize("raw", ["12 samples", "13 individuals", "over 12 individuals",
                                 "future: 12 individuals", "12 FFPE blocks"])
def test_profile_withholds_source_disagreeing_typed_totals(raw):
    """Withhold typed totals contradicted by their literal source answer.

    Args:
        raw: Literal answer disagreeing with the projected unit, value, relation or time.

    Returns:
        None. Evidence survives as unclear without an authoritative donor count.
    """
    bb = bank("A", [("individuals", 12, "reported_value")])
    bb["evidence"][0]["raw_text"] = raw
    before = copy.deepcopy(bb)
    profile = survey_descriptive.build_mucp_cohort_profile([bb])
    assert profile["sizes"]["donors"]["biobanks_with_scoped_reported_sizes"] == 0
    row = profile["sizes"]["unit_unclear"]["rows"][0]
    assert row["raw_text"] == raw
    assert row["kind"] != "reported_scoped_total"
    assert row["validation_diagnostic"]
    assert bb == before
