from fact_sheet_summary import build_fact_sheet_summary, print_fact_sheet_summary


class FactDirectoryStub:
    def __init__(self, facts_by_collection):
        self.facts_by_collection = facts_by_collection

    def getCollectionFacts(self, collection_id):
        return self.facts_by_collection.get(collection_id, [])


def test_fact_sheet_summary_keeps_fact_values_as_observations():
    collections = [
        {"id": "col1", "name": "Collection 1"},
        {"id": "col2", "name": "Collection 2"},
        {"id": "col3", "name": "Collection 3"},
        {"id": "col4", "name": "Collection 4"},
    ]
    directory = FactDirectoryStub(
        {
            "col1": [
                {
                    "id": "f1",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                    "number_of_samples": 100,
                    "number_of_donors": 10,
                },
                {
                    "id": "f2",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": {"id": "urn:miriam:icd:C50", "label": "Breast cancer"},
                    "number_of_samples": 60,
                    "number_of_donors": 6,
                },
                {
                    "id": "f3",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": {"id": "urn:miriam:icd:C50", "label": "Breast cancer"},
                    "number_of_samples": 15,
                    "number_of_donors": 2,
                },
                {
                    "id": "f4",
                    "sex": {"id": "FEMALE", "label": "Female"},
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                    "number_of_samples": 70,
                    "number_of_donors": 7,
                },
            ],
            "col2": [
                {
                    "id": "f5",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                    "number_of_samples": 20,
                    "number_of_donors": 2,
                },
                {
                    "id": "f6",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                    "number_of_samples": 30,
                    "number_of_donors": 3,
                },
            ],
            "col4": [
                {
                    "id": "f7",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": {"id": "DNA", "label": "DNA"},
                    "disease": "*",
                }
            ],
        }
    )

    summary = build_fact_sheet_summary(collections, directory)

    assert summary["totals"] == {
        "collections": 4,
        "collections_with_fact_sheets": 3,
        "collections_with_populated_all_star_rows": 2,
        "collections_with_populated_all_but_one_star_rows": 1,
        "collections_with_populated_all_but_one_star_rows_and_single_all_star_total": 1,
        "collections_with_single_all_star_total": 1,
        "populated_all_star_rows": 3,
        "populated_all_but_one_star_rows": 3,
        "all_star_samples_total_for_collections_with_all_star_rows": 100,
        "all_star_donors_total_for_collections_with_all_star_rows": 10,
        "all_star_samples_total_for_collections_with_all_but_one_rows": 100,
        "all_star_donors_total_for_collections_with_all_but_one_rows": 10,
    }
    assert "all_but_one_samples_total" not in summary["totals"]
    assert [
        (row["collection_id"], row["fact_id"], row["number_of_samples"])
        for row in summary["all_star_rows"]
    ] == [
        ("col1", "f1", 100),
        ("col2", "f5", 20),
        ("col2", "f6", 30),
    ]
    disease_row = next(
        row
        for row in summary["all_but_one_value_rows"]
        if row["dimension"] == "disease" and row["value_id"] == "urn:miriam:icd:C50"
    )
    assert disease_row["collections_with_value"] == 1
    assert disease_row["fact_rows_with_value"] == 2
    assert disease_row["collections_with_single_value_row"] == 0
    assert disease_row["number_of_samples"] == 0
    assert disease_row["number_of_donors"] == 0
    assert disease_row["sample_values"] == "col1:f2=60; col1:f3=15"
    assert disease_row["donor_values"] == "col1:f2=6; col1:f3=2"


def test_fact_sheet_summary_prints_all_star_totals_and_value_distributions(capsys):
    collections = [{"id": "col1", "name": "Collection 1"}]
    directory = FactDirectoryStub(
        {
            "col1": [
                {
                    "id": "f1",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                    "number_of_samples": 100,
                    "number_of_donors": 10,
                },
                {
                    "id": "f2",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": {"id": "urn:miriam:icd:C50", "label": "Breast cancer"},
                    "number_of_samples": 60,
                    "number_of_donors": 6,
                },
                {
                    "id": "f3",
                    "sex": {"id": "FEMALE", "label": "Female"},
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                    "number_of_samples": 70,
                    "number_of_donors": 7,
                },
            ],
        }
    )

    print_fact_sheet_summary(collections, directory)

    output = capsys.readouterr().out
    assert (
        "- all-star totals from collections with populated all-star rows: "
        "100 samples / 10 donors (from 1 collections with one populated all-star row)"
    ) in output
    assert "- all-but-one-star distributions by variable:" in output
    assert "  - disease:" in output
    assert (
        "    - Breast cancer (urn:miriam:icd:C50): "
        "60 samples / 6 donors from 1 collections"
    ) in output
    assert "1 collections, 1 rows" not in output
    assert "  - sex:" in output
    assert "    - Female (FEMALE): 70 samples / 7 donors from 1 collections" in output
