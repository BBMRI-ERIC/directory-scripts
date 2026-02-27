from fact_sheet_utils import (
    analyze_collection_fact_sheet,
    count_star_dimensions,
    get_all_star_rows,
    get_matching_one_star_rows,
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
    }
