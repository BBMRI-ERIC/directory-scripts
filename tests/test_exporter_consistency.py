import copy
import io
import runpy
import sys
import types
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class SharedDirectoryStub:
    """Directory stub shared across exporter consistency tests."""

    BASE_BIOBANKS = [
        {
            "id": "bbmri-eric:ID:CZ_BB1",
            "name": "Biobank 1",
            "country": "CZ",
            "contact": {"id": "ct1"},
            "withdrawn": False,
        },
        {
            "id": "bbmri-eric:ID:EXT_BB2",
            "name": "Biobank 2",
            "country": "DE",
            "contact": {"id": "ct2"},
            "withdrawn": False,
        },
        {
            "id": "bbmri-eric:ID:NL_BB3",
            "name": "Biobank 3",
            "country": "NL",
            "contact": {"id": "ct3"},
            "withdrawn": True,
        },
    ]
    BASE_COLLECTIONS = [
        {
            "id": "col1",
            "name": "Collection 1",
            "biobank": {"id": "bbmri-eric:ID:CZ_BB1"},
            "country": "CZ",
            "contact": {"id": "ct1"},
            "type": ["DISEASE_SPECIFIC"],
            "materials": ["SERUM"],
            "order_of_magnitude": 2,
            "order_of_magnitude_donors": 1,
            "size": 100,
            "number_of_donors": 10,
            "withdrawn": False,
            "facts": [{"id": "f1"}],
        },
        {
            "id": "col2",
            "name": "Collection 2",
            "biobank": {"id": "bbmri-eric:ID:CZ_BB1"},
            "country": "CZ",
            "contact": {"id": "ct1"},
            "type": ["CASE_CONTROL"],
            "materials": ["DNA"],
            "parent_collection": {"id": "col1"},
            "order_of_magnitude": 1,
            "size": 5,
            "number_of_donors": 3,
            "withdrawn": False,
            "facts": [{"id": "f2"}],
        },
        {
            "id": "col3",
            "name": "Collection 3",
            "biobank": {"id": "bbmri-eric:ID:EXT_BB2"},
            "country": "DE",
            "contact": {"id": "ct2"},
            "type": ["POPULATION"],
            "materials": ["PLASMA"],
            "order_of_magnitude": 3,
            "order_of_magnitude_donors": 2,
            "withdrawn": False,
            "facts": [{"id": "f3"}],
        },
        {
            "id": "col4",
            "name": "Collection 4",
            "biobank": {"id": "bbmri-eric:ID:EXT_BB2"},
            "country": "DE",
            "contact": {"id": "ct2"},
            "type": ["LONGITUDINAL"],
            "materials": ["SERUM"],
            "order_of_magnitude": 1,
            "withdrawn": True,
            "facts": [{"id": "f4"}],
        },
        {
            "id": "col5",
            "name": "Collection 5",
            "biobank": {"id": "bbmri-eric:ID:NL_BB3"},
            "country": "NL",
            "contact": {"id": "ct3"},
            "type": ["CASE_CONTROL"],
            "materials": ["SERUM"],
            "order_of_magnitude": 2,
            "order_of_magnitude_donors": 2,
            "size": 12,
            "number_of_donors": 8,
            "withdrawn": False,
            "facts": [{"id": "f5"}],
        },
    ]
    BASE_CONTACTS = [
        {"id": "ct1", "email": "ct1@example.org", "country": "CZ"},
        {"id": "ct2", "email": "ct2@example.org", "country": "DE"},
        {"id": "ct3", "email": "ct3@example.org", "country": "NL"},
    ]
    BASE_FACTS = {
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
                "number_of_samples": 5,
                "number_of_donors": 3,
            }
        ],
        "col3": [
            {
                "id": "f3",
                "sex": "*",
                "age_range": "*",
                "sample_type": "*",
                "disease": "*",
                "number_of_samples": 1000,
                "number_of_donors": 100,
            }
        ],
        "col4": [
            {
                "id": "f4",
                "sex": "*",
                "age_range": "*",
                "sample_type": "*",
                "disease": "*",
                "number_of_samples": 10,
                "number_of_donors": 5,
            }
        ],
        "col5": [
            {
                "id": "f5",
                "sex": "*",
                "age_range": "*",
                "sample_type": "*",
                "disease": "*",
                "number_of_samples": 12,
                "number_of_donors": 8,
            }
        ],
    }
    BASE_SERVICES = [
        {"id": "svc1", "biobank": {"id": "bbmri-eric:ID:CZ_BB1"}, "serviceTypes": ["SEQUENCING"]},
        {"id": "svc2", "biobank": {"id": "bbmri-eric:ID:NL_BB3"}, "serviceTypes": ["BIOANALYTICAL_SERVICES"]},
    ]

    def __init__(self, *args, **kwargs):
        self.biobanks = copy.deepcopy(self.BASE_BIOBANKS)
        self.collections = copy.deepcopy(self.BASE_COLLECTIONS)
        self.contacts = copy.deepcopy(self.BASE_CONTACTS)
        self.services = copy.deepcopy(self.BASE_SERVICES)
        self.collectionFactMap = copy.deepcopy(self.BASE_FACTS)
        self.contactHashmap = {contact["id"]: contact for contact in self.contacts}

    def getBiobanks(self):
        return self.biobanks

    def getBiobanksCount(self):
        return len(self.biobanks)

    def getBiobankById(self, biobank_id, raise_on_missing=False):
        for biobank in self.biobanks:
            if biobank["id"] == biobank_id:
                return biobank
        if raise_on_missing:
            raise KeyError(biobank_id)
        return None

    def getCollections(self):
        return self.collections

    def getCollectionsCount(self):
        return len(self.collections)

    def getCollectionBiobankId(self, collection_id):
        return self.getCollectionById(collection_id)["biobank"]["id"]

    def getCollectionById(self, collection_id, raise_on_missing=False):
        for collection in self.collections:
            if collection["id"] == collection_id:
                return collection
        if raise_on_missing:
            raise KeyError(collection_id)
        return None

    def getCollectionFacts(self, collection_id):
        return self.collectionFactMap.get(collection_id, [])

    def getContact(self, contact_id):
        return self.contactHashmap[contact_id]

    def getServices(self):
        return self.services

    def isTopLevelCollection(self, collection_id):
        return "parent_collection" not in self.getCollectionById(collection_id)

    def isCountableCollection(self, collection_id, metric):
        collection = self.getCollectionById(collection_id)
        if metric not in collection or not isinstance(collection[metric], int):
            return False
        parent = collection.get("parent_collection")
        while parent is not None:
            parent_collection = self.getCollectionById(parent["id"])
            if metric in parent_collection and isinstance(parent_collection[metric], int):
                return False
            parent = parent_collection.get("parent_collection")
        return True


def _run_script(monkeypatch, script_name, argv):
    fake_directory_module = types.ModuleType("directory")
    fake_directory_module.Directory = SharedDirectoryStub
    monkeypatch.setitem(sys.modules, "directory", fake_directory_module)
    monkeypatch.setattr(sys, "argv", [script_name, *argv])

    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        globals_dict = runpy.run_path(
            str(REPO_ROOT / script_name),
            run_name="__main__",
        )
    return globals_dict, stdout.getvalue(), stderr.getvalue()


def test_directory_stats_matches_exporter_all_active_totals(monkeypatch):
    stats_globals, _, _ = _run_script(
        monkeypatch,
        "directory-stats.py",
        ["-N"],
    )
    exporter_globals, _, _ = _run_script(
        monkeypatch,
        "exporter-all.py",
        ["-N"],
    )

    summary = stats_globals["summary"]
    assert summary["withdrawn_biobanks"] == 0
    assert summary["biobanks_total"] == len(exporter_globals["allBiobanks"])
    assert summary["collection_records_total"] == len(exporter_globals["allCollections"])
    assert summary["samples_explicit"] == exporter_globals["allCollectionSamplesExplicit"]
    assert summary["donors_explicit"] == exporter_globals["allCollectionDonorsExplicit"]
    assert summary["samples_total"] == exporter_globals["allCollectionSamplesIncOoM"]
    assert summary["donors_total"] == exporter_globals["allCollectionDonorsIncOoM"]


def test_directory_stats_can_include_withdrawn_biobanks(monkeypatch):
    default_globals, _, _ = _run_script(
        monkeypatch,
        "directory-stats.py",
        ["-N"],
    )
    include_globals, _, _ = _run_script(
        monkeypatch,
        "directory-stats.py",
        ["-N", "-w"],
    )

    default_summary = default_globals["summary"]
    include_summary = include_globals["summary"]

    assert default_summary["biobanks_total"] == 2
    assert include_summary["biobanks_total"] == 3
    assert default_summary["withdrawn_biobanks"] == 0
    assert include_summary["withdrawn_biobanks"] == 1
    assert include_summary["collection_records_total"] == default_summary["collection_records_total"] + 1
    assert include_summary["samples_explicit"] == default_summary["samples_explicit"] + 12
    assert include_summary["donors_explicit"] == default_summary["donors_explicit"] + 8
    assert include_summary["services_total"] == default_summary["services_total"] + 1


def test_directory_stats_matches_exporter_all_when_oom_policy_changes(
    monkeypatch,
):
    monkeypatch.setenv("DIRECTORY_OOM_UPPER_BOUND_COEFFICIENT", "0.3")

    stats_globals, _, _ = _run_script(
        monkeypatch,
        "directory-stats.py",
        ["-N"],
    )
    exporter_globals, _, _ = _run_script(
        monkeypatch,
        "exporter-all.py",
        ["-N"],
    )

    summary = stats_globals["summary"]
    assert summary["oom_upper_bound_coefficient"] == 0.3
    assert summary["samples_total"] == exporter_globals["allCollectionSamplesIncOoM"]
    assert summary["donors_total"] == exporter_globals["allCollectionDonorsIncOoM"]


def test_directory_stats_script_applies_country_and_staging_area_filters(monkeypatch):
    globals_dict, _, _ = _run_script(
        monkeypatch,
        "directory-stats.py",
        ["-N", "-c", "DE", "-A", "EXT"],
    )

    stats_df = globals_dict["stats_df"]
    summary = globals_dict["summary"]

    assert stats_df["id"].tolist() == ["bbmri-eric:ID:EXT_BB2"]
    assert summary["biobanks_total"] == 1
    assert summary["country_filter"] == "DE"
    assert summary["staging_area_filter"] == "EXT"


def test_directory_stats_script_supports_comma_delimited_filters_and_collection_types(
    monkeypatch,
):
    globals_dict, _, _ = _run_script(
        monkeypatch,
        "directory-stats.py",
        ["-N", "-c", "CZ,DE", "-t", "CASE_CONTROL,POPULATION"],
    )

    stats_df = globals_dict["stats_df"]
    summary = globals_dict["summary"]

    assert stats_df["id"].tolist() == [
        "bbmri-eric:ID:CZ_BB1",
        "bbmri-eric:ID:EXT_BB2",
    ]
    assert summary["country_filter"] == "CZ,DE"
    assert summary["collection_type_filter"] == "CASE_CONTROL,POPULATION"
    assert summary["collection_records_total"] == 2
