from fact_sheet_summary import (
    build_fact_sheet_summary,
    build_fact_sheet_xlsx_tables,
    print_fact_sheet_summary,
)


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
        "allow_no_star_fact_sums": False,
        "collections_with_no_star_fallback": 0,
        "no_star_fallback_distribution_values": 0,
        "no_star_fallback_contributions": 0,
        "no_star_fallback_source_rows": 0,
        "fact_sheet_summary_warning": "",
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


def test_no_star_fallback_is_opt_in_per_missing_value_and_preserves_provenance(capsys):
    collections = [
        {"id": "fallback", "name": "Fallback collection"},
        {"id": "authoritative", "name": "Authoritative collection"},
        {"id": "ambiguous", "name": "Ambiguous collection"},
    ]
    directory = FactDirectoryStub(
        {
            "fallback": [
                {
                    "id": "fallback-all",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                    "number_of_samples": 100,
                    "number_of_donors": 80,
                },
                {
                    "id": "fallback-detail-1",
                    "sex": "FEMALE",
                    "age_range": "Adult",
                    "sample_type": "PLASMA",
                    "disease": {"id": "C50", "label": "Breast cancer"},
                    "number_of_samples": 30,
                    "number_of_donors": 20,
                },
                {
                    "id": "fallback-detail-2",
                    "sex": "MALE",
                    "age_range": "Adult",
                    "sample_type": "DNA",
                    "disease": {"id": "C50", "label": "Breast cancer"},
                    "number_of_samples": 25,
                    "number_of_donors": 15,
                },
            ],
            "authoritative": [
                {
                    "id": "authoritative-margin",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": {"id": "C50", "label": "Breast cancer"},
                    "number_of_samples": 40,
                    "number_of_donors": 30,
                },
                {
                    "id": "authoritative-detail",
                    "sex": "FEMALE",
                    "age_range": "Adult",
                    "sample_type": "PLASMA",
                    "disease": {"id": "C50", "label": "Breast cancer"},
                    "number_of_samples": 999,
                    "number_of_donors": 999,
                },
            ],
            "ambiguous": [
                {
                    "id": "ambiguous-margin-1",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": {"id": "C50", "label": "Breast cancer"},
                    "number_of_samples": 10,
                    "number_of_donors": 8,
                },
                {
                    "id": "ambiguous-margin-2",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": {"id": "C50", "label": "Breast cancer"},
                    "number_of_samples": 11,
                    "number_of_donors": 9,
                },
                {
                    "id": "ambiguous-detail",
                    "sex": "FEMALE",
                    "age_range": "Adult",
                    "sample_type": "PLASMA",
                    "disease": {"id": "C50", "label": "Breast cancer"},
                    "number_of_samples": 500,
                    "number_of_donors": 500,
                },
            ],
        }
    )

    without_fallback = build_fact_sheet_summary(collections, directory)
    with_fallback = build_fact_sheet_summary(
        collections,
        directory,
        allow_no_star_fact_sums=True,
    )

    without_c50 = next(
        row
        for row in without_fallback["all_but_one_value_rows"]
        if row["dimension"] == "disease" and row["value_id"] == "C50"
    )
    with_c50 = next(
        row
        for row in with_fallback["all_but_one_value_rows"]
        if row["dimension"] == "disease" and row["value_id"] == "C50"
    )
    assert without_c50["number_of_samples"] == 40
    assert without_c50["number_of_donors"] == 30
    assert with_c50["number_of_samples"] == 40
    assert with_c50["number_of_donors"] == 30
    assert with_c50["authoritative_collections"] == 1
    assert with_c50["no_star_fallback_collections"] == 0
    assert with_c50["assumption_violating"] is False
    assert with_fallback["totals"]["collections_with_no_star_fallback"] == 3
    assert with_fallback["totals"]["no_star_fallback_source_rows"] == 4
    assert with_fallback["totals"]["fact_sheet_summary_warning"].startswith(
        "No-star fact-sheet fallback is enabled"
    )
    fallback_c50 = next(
        row
        for row in with_fallback["no_star_fallback_value_rows"]
        if row["dimension"] == "disease" and row["value_id"] == "C50"
    )
    assert fallback_c50["number_of_samples"] == 55
    assert fallback_c50["number_of_donors"] == 35
    assert fallback_c50["authoritative_collections"] == 0
    assert fallback_c50["assumption_violating"] is True
    assert with_fallback["totals"]["all_star_samples_total_for_collections_with_all_star_rows"] == 100
    assert with_fallback["totals"]["all_star_donors_total_for_collections_with_all_star_rows"] == 80

    print_fact_sheet_summary(
        collections,
        directory,
        allow_no_star_fact_sums=True,
    )
    output = capsys.readouterr().out
    assert "WARNING: No-star fact-sheet fallback is enabled" in output
    assert (
        "- UNSAFE no-star fallback provenance: "
        "3 collections / 6 distribution values / 4 source rows"
    ) in output
    assert "UNSAFE no-star fallback distributions (not combined with all-but-one-star)" in output

    tables = build_fact_sheet_xlsx_tables(
        collections, directory, allow_no_star_fact_sums=True
    )
    assert tables[-1][1] == "Fact sheet no-star fallback"
    assert "fact_sheet_summary_warning" in tables[0][0].columns
    assert tables[0][0].iloc[0]["fact_sheet_summary_warning"].startswith(
        "No-star fact-sheet fallback is enabled"
    )


def test_duplicate_all_but_one_rows_block_fallback_only_for_that_value():
    collections = [{"id": "duplicate", "name": "Duplicate"}]
    directory = FactDirectoryStub({"duplicate": [
        {"id": "m1", "sex": "FEMALE", "age_range": "*", "sample_type": "*", "disease": "*", "number_of_samples": 10, "number_of_donors": 5},
        {"id": "m2", "sex": "FEMALE", "age_range": "*", "sample_type": "*", "disease": "*", "number_of_samples": 11, "number_of_donors": 6},
        {"id": "d1", "sex": "FEMALE", "age_range": "Adult", "sample_type": "PLASMA", "disease": "C50", "number_of_samples": 99, "number_of_donors": 99},
    ]})
    summary = build_fact_sheet_summary(
        collections, directory, allow_no_star_fact_sums=True
    )
    fallback_keys = {
        (row["dimension"], row["value_id"])
        for row in summary["no_star_fallback_value_rows"]
    }
    assert ("sex", "FEMALE") not in fallback_keys
    assert fallback_keys == {
        ("age_range", "Adult"),
        ("sample_type", "PLASMA"),
        ("disease", "C50"),
    }


def test_empty_duplicate_all_but_one_row_blocks_authoritative_total():
    collections = [{"id": "duplicate", "name": "Duplicate"}]
    directory = FactDirectoryStub({"duplicate": [
        {"id": "m1", "sex": "FEMALE", "age_range": "*", "sample_type": "*", "disease": "*", "number_of_samples": 10, "number_of_donors": 5},
        {"id": "m2", "sex": "FEMALE", "age_range": "*", "sample_type": "*", "disease": "*", "number_of_samples": None, "number_of_donors": None},
    ]})

    summary = build_fact_sheet_summary(collections, directory)

    female = next(
        row
        for row in summary["all_but_one_value_rows"]
        if row["dimension"] == "sex" and row["value_id"] == "FEMALE"
    )
    assert female["collections_with_value"] == 1
    assert female["fact_rows_with_value"] == 2
    assert female["collections_with_single_value_row"] == 0
    assert female["authoritative_collections"] == 0
    assert female["number_of_samples"] == 0
    assert female["number_of_donors"] == 0


def test_no_star_fallback_provenance_prints_zero_use_counts(capsys):
    print_fact_sheet_summary(
        [{"id": "empty", "name": "Empty"}],
        FactDirectoryStub({"empty": []}),
        allow_no_star_fact_sums=True,
    )

    output = capsys.readouterr().out
    assert (
        "- UNSAFE no-star fallback provenance: "
        "0 collections / 0 distribution values / 0 source rows"
    ) in output
