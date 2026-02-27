from directory_stats_utils import (
    build_biobank_stats,
    build_directory_stats,
    build_stats_summary,
    extract_staging_area_from_id,
)


class DirectoryStatsStub:
    def __init__(self):
        self.biobanks = [
            {"id": "bb1", "name": "Biobank 1", "country": "CZ", "withdrawn": False},
            {
                "id": "bbmri-eric:ID:EXT_BB2",
                "name": "Biobank 2",
                "country": {"id": "DE"},
                "withdrawn": False,
            },
            {
                "id": "bbmri-eric:ID:EXT_BB4",
                "name": "Biobank 4",
                "country": {"id": "AT"},
                "withdrawn": False,
            },
            {
                "id": "bbmri-eric:ID:EXT_BB5",
                "name": "Biobank 5",
                "country": {"id": "AT"},
                "withdrawn": False,
            },
            {
                "id": "bbmri-eric:ID:NL_BB3",
                "name": "Biobank 3",
                "country": "NL",
                "withdrawn": True,
            },
        ]
        self.collections = [
            {
                "id": "col1",
                "name": "Collection 1",
                "biobank": {"id": "bb1"},
                "country": "CZ",
                "type": ["DISEASE_SPECIFIC"],
                "order_of_magnitude": 2,
                "order_of_magnitude_donors": 1,
                "facts": [{"id": "f1"}],
                "size": 100,
                "number_of_donors": 10,
                "withdrawn": False,
            },
            {
                "id": "col2",
                "name": "Collection 2",
                "biobank": {"id": "bb1"},
                "country": "CZ",
                "type": ["CASE_CONTROL"],
                "parent_collection": {"id": "col1"},
                "size": 5,
                "number_of_donors": 3,
                "facts": [{"id": "f2"}],
                "withdrawn": False,
            },
            {
                "id": "col3",
                "name": "Collection 3",
                "biobank": {"id": "bb1"},
                "country": "CZ",
                "type": ["POPULATION"],
                "size": 7,
                "order_of_magnitude_donors": 2,
                "withdrawn": False,
            },
            {
                "id": "col4",
                "name": "Collection 4",
                "biobank": {"id": "bbmri-eric:ID:EXT_BB2"},
                "country": "DE",
                "type": ["CASE_CONTROL", "POPULATION"],
                "order_of_magnitude": {"id": 3},
                "order_of_magnitude_donors": {"id": 2},
                "facts": [{"id": "f4"}],
                "withdrawn": False,
            },
            {
                "id": "col5",
                "name": "Collection 5",
                "biobank": {"id": "bbmri-eric:ID:EXT_BB4"},
                "country": "AT",
                "type": ["POPULATION"],
                "size": 11,
                "number_of_donors": 12,
                "withdrawn": False,
            },
            {
                "id": "col6",
                "name": "Collection 6",
                "biobank": {"id": "bbmri-eric:ID:EXT_BB5"},
                "country": "AT",
                "type": ["CASE_CONTROL"],
                "size": 13,
                "number_of_donors": 14,
                "withdrawn": False,
            },
        ]
        self.services = [
            {
                "id": "svc1",
                "biobank": {"id": "bb1"},
                "serviceTypes": ["BIOANALYTICAL_SERVICES", "SEQUENCING"],
            },
            {
                "id": "svc2",
                "biobank": {"id": "bb1"},
                "serviceTypes": ["SEQUENCING"],
            },
            {
                "id": "svc3",
                "biobank": {"id": "bbmri-eric:ID:EXT_BB2"},
                "serviceTypes": ["BIOINFORMATICS_AND_DATA_SCIENCES"],
            },
            {
                "id": "svc4",
                "biobank": {"id": "bbmri-eric:ID:EXT_BB4"},
                "serviceTypes": ["SEQUENCING"],
            },
        ]
        self.facts_by_collection = {
            "col1": [
                {
                    "id": "f1",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                    "number_of_samples": 100,
                    "number_of_donors": 10,
                }
            ],
            "col2": [
                {
                    "id": "f2",
                    "sex": "*",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                    "number_of_samples": 6,
                    "number_of_donors": 4,
                }
            ],
            "col4": [
                {
                    "id": "f4",
                    "sex": "FEMALE",
                    "age_range": "*",
                    "sample_type": "*",
                    "disease": "*",
                    "number_of_samples": 3,
                    "number_of_donors": 2,
                }
            ],
        }

    def getBiobanks(self):
        return self.biobanks

    def getBiobankById(self, biobank_id, raise_on_missing=False):
        for biobank in self.biobanks:
            if biobank["id"] == biobank_id:
                return biobank
        if raise_on_missing:
            raise KeyError(biobank_id)
        return None

    def getCollections(self):
        return self.collections

    def getServices(self):
        return self.services

    def getCollectionBiobankId(self, collection_id):
        return next(
            collection["biobank"]["id"]
            for collection in self.collections
            if collection["id"] == collection_id
        )

    def isTopLevelCollection(self, collection_id):
        collection = next(
            collection for collection in self.collections if collection["id"] == collection_id
        )
        return "parent_collection" not in collection

    def isCountableCollection(self, collection_id, metric):
        collection = next(
            collection for collection in self.collections if collection["id"] == collection_id
        )
        if metric not in collection or not isinstance(collection[metric], int):
            return False
        parent = collection.get("parent_collection")
        while parent is not None:
            parent_collection = next(
                item for item in self.collections if item["id"] == parent["id"]
            )
            if metric in parent_collection and isinstance(parent_collection[metric], int):
                return False
            parent = parent_collection.get("parent_collection")
        return True

    def getCollectionFacts(self, collection_id):
        return self.facts_by_collection.get(collection_id, [])


def test_build_biobank_stats_include_services_facts_and_subcollection_counts():
    rows = build_biobank_stats(DirectoryStatsStub())

    bb1 = next(row for row in rows if row["id"] == "bb1")
    assert bb1["top_level_collections"] == 2
    assert bb1["subcollections"] == 1
    assert bb1["collection_records_total"] == 3
    assert bb1["samples_explicit"] == 107
    assert bb1["samples_oom"] == 0
    assert bb1["samples_total"] == 107
    assert bb1["donors_explicit"] == 10
    assert bb1["donors_oom"] == 100
    assert bb1["donors_total"] == 110
    assert bb1["services_total"] == 2
    assert bb1["collections_with_facts"] == 2
    assert bb1["collections_with_all_star"] == 2
    assert bb1["collections_missing_valid_all_star"] == 0
    assert bb1["collections_all_star_inconsistent_samples"] == 1
    assert bb1["collections_all_star_inconsistent_donors"] == 1
    assert bb1["collection_type_breakdown"] == "CASE_CONTROL=1; DISEASE_SPECIFIC=1; POPULATION=1"
    assert bb1["service_type_breakdown"] == "BIOANALYTICAL_SERVICES=1; SEQUENCING=2"


def test_build_biobank_stats_supports_oom_fallback_services_and_missing_all_star():
    rows = build_biobank_stats(DirectoryStatsStub())

    bb2 = next(row for row in rows if row["id"] == "bbmri-eric:ID:EXT_BB2")
    assert bb2["country"] == "DE"
    assert bb2["staging_area"] == "EXT"
    assert bb2["samples_oom"] == 1000
    assert bb2["donors_oom"] == 100
    assert bb2["services_total"] == 1
    assert bb2["collections_with_facts"] == 1
    assert bb2["collections_with_all_star"] == 0
    assert bb2["collections_missing_valid_all_star"] == 1

    assert all(row["id"] != "bb3" for row in rows)


def test_build_directory_stats_emits_breakdown_and_warning_rows():
    stats = build_directory_stats(DirectoryStatsStub())

    assert stats["collection_type_summary_rows"] == [
        {"collection_type": "CASE_CONTROL", "count": 3},
        {"collection_type": "DISEASE_SPECIFIC", "count": 1},
        {"collection_type": "POPULATION", "count": 3},
    ]
    assert stats["top_level_collection_type_summary_rows"] == [
        {"collection_type": "CASE_CONTROL", "count": 2},
        {"collection_type": "DISEASE_SPECIFIC", "count": 1},
        {"collection_type": "POPULATION", "count": 3},
    ]
    assert stats["subcollection_type_summary_rows"] == [
        {"collection_type": "CASE_CONTROL", "count": 1},
    ]
    assert stats["service_type_summary_rows"] == [
        {"service_type": "BIOANALYTICAL_SERVICES", "count": 1},
        {"service_type": "BIOINFORMATICS_AND_DATA_SCIENCES", "count": 1},
        {"service_type": "SEQUENCING", "count": 3},
    ]

    warning_codes = {
        (row["collection_id"], row["code"])
        for row in stats["fact_sheet_warning_rows"]
    }
    assert warning_codes == {
        ("col2", "all_star_samples_mismatch"),
        ("col2", "all_star_donors_mismatch"),
        ("col4", "missing_all_star"),
    }


def test_build_stats_summary_aggregates_all_metrics():
    rows = build_biobank_stats(DirectoryStatsStub())
    summary = build_stats_summary(rows)

    assert summary["biobanks_total"] == 4
    assert summary["withdrawn_biobanks"] == 0
    assert summary["biobanks_with_collections"] == 4
    assert summary["biobanks_with_services"] == 3
    assert summary["collection_records_total"] == 6
    assert summary["top_level_collections"] == 5
    assert summary["subcollections"] == 1
    assert summary["samples_explicit"] == 131
    assert summary["samples_oom"] == 1000
    assert summary["samples_total"] == 1131
    assert summary["donors_explicit"] == 36
    assert summary["donors_oom"] == 200
    assert summary["donors_total"] == 236
    assert summary["services_total"] == 4
    assert summary["collections_with_facts"] == 3
    assert summary["collections_with_all_star"] == 2
    assert summary["collections_missing_valid_all_star"] == 1
    assert summary["collections_all_star_inconsistent_samples"] == 1
    assert summary["collections_all_star_inconsistent_donors"] == 1
    assert summary["top_level_collection_type_breakdown"] == "CASE_CONTROL=2; DISEASE_SPECIFIC=1; POPULATION=3"
    assert summary["subcollection_type_breakdown"] == "CASE_CONTROL=1"
    assert summary["service_type_breakdown"] == "BIOANALYTICAL_SERVICES=1; BIOINFORMATICS_AND_DATA_SCIENCES=1; SEQUENCING=3"


def test_build_biobank_stats_excludes_withdrawn_biobanks_by_default():
    rows = build_biobank_stats(DirectoryStatsStub())

    assert [row["id"] for row in rows] == [
        "bb1",
        "bbmri-eric:ID:EXT_BB2",
        "bbmri-eric:ID:EXT_BB4",
        "bbmri-eric:ID:EXT_BB5",
    ]


def test_build_biobank_stats_can_include_withdrawn_biobanks():
    rows = build_biobank_stats(
        DirectoryStatsStub(),
        include_withdrawn_biobanks=True,
    )

    bb3 = next(row for row in rows if row["id"] == "bbmri-eric:ID:NL_BB3")
    assert bb3["withdrawn"] is True


def test_extract_staging_area_from_id_supports_directory_ids():
    assert extract_staging_area_from_id("bbmri-eric:ID:EXT_POB") == "EXT"
    assert extract_staging_area_from_id("bbmri-eric:ID:CZ_REVMA") == "CZ"


def test_build_directory_stats_supports_country_and_staging_area_filters():
    stats = build_directory_stats(
        DirectoryStatsStub(),
        country_filters=["DE"],
        staging_area_filters=["EXT"],
    )

    assert [row["id"] for row in stats["biobank_rows"]] == ["bbmri-eric:ID:EXT_BB2"]
    assert stats["top_level_collection_type_summary_rows"] == [
        {"collection_type": "CASE_CONTROL", "count": 1},
        {"collection_type": "POPULATION", "count": 1},
    ]


def test_build_directory_stats_supports_comma_delimited_or_filters_and_collection_type():
    stats = build_directory_stats(
        DirectoryStatsStub(),
        country_filters=["CZ,DE"],
        staging_area_filters=[],
        collection_type_filters=["CASE_CONTROL,POPULATION"],
    )

    assert [row["id"] for row in stats["biobank_rows"]] == [
        "bb1",
        "bbmri-eric:ID:EXT_BB2",
    ]
    bb1 = next(row for row in stats["biobank_rows"] if row["id"] == "bb1")
    bb2 = next(
        row for row in stats["biobank_rows"] if row["id"] == "bbmri-eric:ID:EXT_BB2"
    )
    assert bb1["collection_records_total"] == 2
    assert bb1["top_level_collections"] == 1
    assert bb1["subcollections"] == 1
    assert bb1["collection_type_breakdown"] == "CASE_CONTROL=1; POPULATION=1"
    assert bb2["collection_records_total"] == 1
    assert bb2["collection_type_breakdown"] == "CASE_CONTROL=1; POPULATION=1"


def test_build_directory_stats_sorts_ext_rows_by_country_then_id():
    stats = build_directory_stats(
        DirectoryStatsStub(),
        staging_area_filters=["EXT"],
    )

    assert [row["id"] for row in stats["biobank_rows"]] == [
        "bbmri-eric:ID:EXT_BB4",
        "bbmri-eric:ID:EXT_BB5",
        "bbmri-eric:ID:EXT_BB2",
    ]
