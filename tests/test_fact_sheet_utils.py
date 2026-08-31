from fact_sheet_utils import (
    analyze_collection_fact_sheet,
    count_star_dimensions,
    get_all_star_rows,
    get_matching_one_star_rows,
    get_no_star_rows,
    normalize_fact_dimension_value,
)


def test_normalize_fact_dimension_value_supports_dict_and_scalar_values():
    assert normalize_fact_dimension_value({"name": "ORPHA:1"}) == "ORPHA:1"
    assert normalize_fact_dimension_value({"id": "CZ"}) == "CZ"
    assert normalize_fact_dimension_value("*") == "*"


def test_get_all_star_rows_and_star_count_handle_disease_dicts():
    facts = [
        {
            "id": "f1",
            "sex": "*",
            "age_range": "*",
            "sample_type": "*",
            "disease": "*",
            "number_of_samples": 10,
            "number_of_donors": 8,
        },
        {
            "id": "f2",
            "sex": "*",
            "age_range": "*",
            "sample_type": "*",
            "disease": {"name": "ORPHA:1"},
            "number_of_samples": 4,
            "number_of_donors": 3,
        },
    ]

    assert [row["id"] for row in get_all_star_rows(facts)] == ["f1"]
    assert count_star_dimensions(facts[1]) == 3


def test_get_matching_one_star_rows_matches_normalized_values():
    facts = [
        {
            "id": "f1",
            "sex": "*",
            "age_range": "*",
            "sample_type": "*",
            "disease": "*",
        },
        {
            "id": "f2",
            "sex": "*",
            "age_range": "*",
            "sample_type": "*",
            "disease": {"name": "ORPHA:1"},
        },
    ]

    rows = get_matching_one_star_rows(facts, "disease", "ORPHA:1")
    assert [row["id"] for row in rows] == ["f2"]


def test_get_no_star_rows_requires_every_dimension_to_be_concrete():
    facts = [
        {
            "id": "complete",
            "sex": "FEMALE",
            "age_range": "Adult",
            "sample_type": "PLASMA",
            "disease": {"name": "ORPHA:1"},
        },
        {
            "id": "missing",
            "sex": "FEMALE",
            "age_range": "Adult",
            "sample_type": "PLASMA",
            "disease": None,
        },
        {
            "id": "aggregate",
            "sex": "FEMALE",
            "age_range": "Adult",
            "sample_type": "PLASMA",
            "disease": "*",
        },
    ]

    assert [row["id"] for row in get_no_star_rows(facts)] == ["complete"]


def test_blank_dimension_values_are_not_treated_as_concrete():
    facts = [
        {
            "id": "blank",
            "sex": "FEMALE",
            "age_range": "",
            "sample_type": "*",
            "disease": "*",
        }
    ]

    result = analyze_collection_fact_sheet({"id": "col"}, facts)

    assert result["all_but_one_rows"] == 0
    assert result["missing_all_but_one_values"] == [
        {"dimension": "sex", "value": "FEMALE", "rows": 0}
    ]


def test_analyze_collection_fact_sheet_reports_missing_and_mismatched_all_star():
    collection = {
        "id": "col1",
        "size": 10,
        "number_of_donors": 8,
        "facts": [{"id": "f1"}],
    }
    facts = [
        {
            "id": "f1",
            "sex": "*",
            "age_range": "*",
            "sample_type": "*",
            "disease": "*",
            "number_of_samples": 9,
            "number_of_donors": 7,
        }
    ]

    result = analyze_collection_fact_sheet(collection, facts)

    assert result["all_star_rows"] == 1
    assert {warning["code"] for warning in result["warnings"]} == {
        "all_star_samples_mismatch",
        "all_star_donors_mismatch",
        "missing_all_but_one",
    }


def test_analyze_collection_fact_sheet_reports_margin_coverage_duplicates_and_bounds():
    collection = {
        "id": "col1",
        "size": 100,
        "number_of_donors": 80,
        "order_of_magnitude": 2,
        "order_of_magnitude_donors": 1,
    }
    facts = [
        {
            "id": "all",
            "sex": "*",
            "age_range": "*",
            "sample_type": "*",
            "disease": "*",
            "number_of_samples": 100,
            "number_of_donors": 80,
        },
        {
            "id": "female-1",
            "sex": "FEMALE",
            "age_range": "*",
            "sample_type": "*",
            "disease": "*",
            "number_of_samples": 101,
            "number_of_donors": 81,
        },
        {
            "id": "female-2",
            "sex": "FEMALE",
            "age_range": "*",
            "sample_type": "*",
            "disease": "*",
            "number_of_samples": 50,
            "number_of_donors": 40,
        },
        {
            "id": "male-detail",
            "sex": "MALE",
            "age_range": "Adult",
            "sample_type": "PLASMA",
            "disease": "C50",
            "number_of_samples": 20,
            "number_of_donors": 10,
        },
    ]

    result = analyze_collection_fact_sheet(collection, facts)
    warning_codes = {warning["code"] for warning in result["warnings"]}

    assert result["all_but_one_rows"] == 2
    assert result["all_but_one_complete"] is False
    assert result["duplicate_all_but_one_values"] == [
        {"dimension": "sex", "value": "FEMALE", "rows": 2}
    ]
    assert ("sex", "MALE") in {
        (row["dimension"], row["value"])
        for row in result["missing_all_but_one_values"]
    }
    assert "multiple_all_but_one_value" in warning_codes
    assert "missing_all_but_one_value" in warning_codes
    assert "all_but_one_samples_above_all_star" in warning_codes
    assert "all_but_one_donors_above_all_star" in warning_codes


def test_analyze_collection_fact_sheet_checks_all_star_against_oom_intervals():
    collection = {
        "id": "col1",
        "order_of_magnitude": 3,
        "order_of_magnitude_donors": 2,
    }
    facts = [
        {
            "id": "all",
            "sex": "*",
            "age_range": "*",
            "sample_type": "*",
            "disease": "*",
            "number_of_samples": 999,
            "number_of_donors": 1000,
        }
    ]

    result = analyze_collection_fact_sheet(collection, facts)
    warning_codes = {warning["code"] for warning in result["warnings"]}

    assert "all_star_samples_oom_mismatch" in warning_codes
    assert "all_star_donors_oom_mismatch" in warning_codes


def test_boolean_counts_are_not_compared_as_numeric_totals():
    collection = {
        "id": "col1",
        "size": True,
        "number_of_donors": True,
    }
    facts = [
        {
            "id": "all",
            "sex": "*",
            "age_range": "*",
            "sample_type": "*",
            "disease": "*",
            "number_of_samples": 2,
            "number_of_donors": True,
        }
    ]

    result = analyze_collection_fact_sheet(collection, facts)
    warning_codes = {warning["code"] for warning in result["warnings"]}

    assert "all_star_samples_mismatch" not in warning_codes
    assert "all_star_donors_mismatch" not in warning_codes
    assert result["donors_present"] is False
