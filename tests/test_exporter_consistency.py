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
            "network": [{"id": "net1"}],
            "withdrawn": False,
        },
        {
            "id": "bbmri-eric:ID:EXT_BB2",
            "name": "Biobank 2",
            "country": "DE",
            "contact": {"id": "ct2"},
            "network": [{"id": "net2"}],
            "withdrawn": False,
        },
        {
            "id": "bbmri-eric:ID:NL_BB3",
            "name": "Biobank 3",
            "country": "NL",
            "contact": {"id": "ct3"},
            "network": [{"id": "net3"}],
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
            "networks": [{"id": "net1"}],
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
            "networks": [{"id": "net1"}],
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
            "networks": [{"id": "net2"}],
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
            "networks": [{"id": "net2"}],
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
            "networks": [{"id": "net3"}],
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
    BASE_NETWORKS = [
        {"id": "net1", "name": "Network 1", "country": {"id": "CZ"}, "contact": {"id": "ct1"}},
        {"id": "net2", "name": "Network 2", "country": {"id": "DE"}, "contact": {"id": "ct2"}},
        {"id": "net3", "name": "Network 3", "country": {"id": "NL"}, "contact": {"id": "ct3"}},
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
    BASE_STUDIES = [
        {
            "id": "study1",
            "title": "Study 1",
            "collections": [{"id": "col1"}],
        },
        {
            "id": "study2",
            "title": "Study 2",
            "collections": [{"id": "col1"}, {"id": "col3"}],
        },
        {
            "id": "study3",
            "title": "Study 3",
            "collections": [{"id": "col5"}],
        },
    ]

    def __init__(self, *args, **kwargs):
        self.include_withdrawn_entities = kwargs.get("include_withdrawn_entities", False) or kwargs.get("only_withdrawn_entities", False)
        self.only_withdrawn_entities = kwargs.get("only_withdrawn_entities", False)
        self._schema = kwargs.get("schema", "ERIC")
        self._directory_url = kwargs.get("directory_url", "https://directory.example.test")
        self.biobanks = copy.deepcopy(self.BASE_BIOBANKS)
        self.collections = copy.deepcopy(self.BASE_COLLECTIONS)
        self.contacts = copy.deepcopy(self.BASE_CONTACTS)
        self.networks = copy.deepcopy(self.BASE_NETWORKS)
        self.services = copy.deepcopy(self.BASE_SERVICES)
        self.studies = copy.deepcopy(self.BASE_STUDIES)
        self.collectionFactMap = copy.deepcopy(self.BASE_FACTS)
        self.contactHashmap = {contact["id"]: contact for contact in self.contacts}

    def _matches_withdrawn_scope(self, is_withdrawn):
        if self.only_withdrawn_entities:
            return is_withdrawn
        if self.include_withdrawn_entities:
            return True
        return not is_withdrawn

    def getSchema(self):
        return self._schema

    def getDirectoryUrl(self):
        return self._directory_url

    def isBiobankWithdrawn(self, biobank_id):
        biobank = next(
            biobank for biobank in self.biobanks if biobank["id"] == biobank_id
        )
        return bool(biobank.get("withdrawn"))

    def isCollectionWithdrawn(self, collection_id):
        collection = next(
            collection for collection in self.collections if collection["id"] == collection_id
        )
        if bool(collection.get("withdrawn")):
            return True
        if self.isBiobankWithdrawn(collection["biobank"]["id"]):
            return True
        parent = collection.get("parent_collection")
        if parent is not None:
            return self.isCollectionWithdrawn(parent["id"])
        return False

    def getBiobanks(self):
        return [
            biobank
            for biobank in self.biobanks
            if self._matches_withdrawn_scope(self.isBiobankWithdrawn(biobank["id"]))
        ]

    def getBiobanksCount(self):
        return len(self.getBiobanks())

    def getBiobankById(self, biobank_id, raise_on_missing=False):
        for biobank in self.biobanks:
            if biobank["id"] == biobank_id:
                if not self._matches_withdrawn_scope(self.isBiobankWithdrawn(biobank_id)):
                    break
                return biobank
        if raise_on_missing:
            raise KeyError(biobank_id)
        return None

    def getCollections(self):
        return [
            collection
            for collection in self.collections
            if self._matches_withdrawn_scope(self.isCollectionWithdrawn(collection["id"]))
        ]

    def getCollectionsCount(self):
        return len(self.getCollections())

    def getCollectionBiobankId(self, collection_id):
        return self.getCollectionById(collection_id)["biobank"]["id"]

    def getCollectionById(self, collection_id, raise_on_missing=False):
        for collection in self.collections:
            if collection["id"] == collection_id:
                if not self._matches_withdrawn_scope(
                    self.isCollectionWithdrawn(collection_id)
                ):
                    break
                return collection
        if raise_on_missing:
            raise KeyError(collection_id)
        return None

    def getCollectionFacts(self, collection_id):
        return self.collectionFactMap.get(collection_id, [])

    def getContact(self, contact_id):
        return self.contactHashmap[contact_id]

    def getContacts(self):
        return self.contacts

    def getNetworks(self):
        return self.networks

    def getServices(self):
        return [
            service
            for service in self.services
            if self._matches_withdrawn_scope(
                self.isBiobankWithdrawn(service["biobank"]["id"])
            )
        ]

    def getServiceBiobankId(self, service_id):
        return next(
            service["biobank"]["id"]
            for service in self.services
            if service["id"] == service_id
        )

    def getStudies(self):
        visible_studies = []
        for study in self.studies:
            for collection_ref in study.get("collections", []):
                collection = self.getCollectionById(collection_ref["id"])
                if collection is not None:
                    visible_studies.append(study)
                    break
        return visible_studies

    def getStudyCollectionIds(self, study_id):
        study = next(study for study in self.studies if study["id"] == study_id)
        collection_ids = []
        for collection_ref in study.get("collections", []):
            collection_id = collection_ref["id"]
            if self.getCollectionById(collection_id) is not None:
                collection_ids.append(collection_id)
        return collection_ids

    def getStudyBiobankIds(self, study_id):
        biobank_ids = []
        for collection_id in self.getStudyCollectionIds(study_id):
            biobank_id = self.getCollectionBiobankId(collection_id)
            if biobank_id not in biobank_ids:
                biobank_ids.append(biobank_id)
        return biobank_ids

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


def test_exporter_all_collects_services_and_studies_in_active_scope(monkeypatch):
    exporter_globals, _, _ = _run_script(
        monkeypatch,
        "exporter-all.py",
        ["-N"],
    )

    assert [service["id"] for service in exporter_globals["allServices"]] == ["svc1"]
    assert [study["id"] for study in exporter_globals["allStudies"]] == ["study1", "study2"]
    assert [contact["id"] for contact in exporter_globals["allContacts"]] == ["ct1", "ct2"]
    assert [network["id"] for network in exporter_globals["allNetworks"]] == ["net1", "net2"]


def test_exporter_all_can_append_withdrawn_sheets_to_main_workbook(monkeypatch, tmp_path):
    workbook = tmp_path / "all.xlsx"
    _run_script(
        monkeypatch,
        "exporter-all.py",
        [
            "-N",
            "-w",
            "-X",
            str(workbook),
            "--include-withdrawn-sheets-in-output",
        ],
    )

    import pandas as pd

    sheet_names = pd.ExcelFile(workbook).sheet_names
    assert sheet_names == [
        "Biobanks",
        "Collections",
        "Services",
        "Studies",
        "Contacts",
        "Networks",
        "Withdrawn biobanks",
        "Withdrawn collections",
        "Withdrawn services",
        "Withdrawn studies",
        "Withdrawn contacts",
        "Withdrawn networks",
    ]


def test_exporter_all_writes_clickable_id_hyperlinks(monkeypatch, tmp_path):
    workbook = tmp_path / "links.xlsx"
    _run_script(
        monkeypatch,
        "exporter-all.py",
        [
            "-N",
            "-X",
            str(workbook),
        ],
    )

    from openpyxl import load_workbook

    wb = load_workbook(workbook)
    biobank_formula = wb["Biobanks"]["B2"].value
    collection_formula = wb["Collections"]["B2"].value
    service_formula = wb["Services"]["B2"].value
    study_formula = wb["Studies"]["B2"].value
    contact_formula = wb["Contacts"]["B2"].value
    network_formula = wb["Networks"]["B2"].value

    assert biobank_formula == '=HYPERLINK("https://directory.example.test/ERIC/directory/#/biobank/bbmri-eric:ID:CZ_BB1","bbmri-eric:ID:CZ_BB1")'
    assert collection_formula == '=HYPERLINK("https://directory.example.test/ERIC/directory/#/collection/col1","col1")'
    assert service_formula == '=HYPERLINK("https://directory.example.test/ERIC/directory/#/service/svc1","svc1")'
    assert study_formula == '=HYPERLINK("https://directory.example.test/ERIC/directory/#/study/study1","study1")'
    assert contact_formula == '=HYPERLINK("https://directory.example.test/ERIC/directory/#/person/ct1","ct1")'
    assert network_formula == '=HYPERLINK("https://directory.example.test/ERIC/directory/#/network/net1","net1")'


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
    assert include_summary["collection_records_total"] == default_summary["collection_records_total"] + 2
    assert include_summary["samples_explicit"] == default_summary["samples_explicit"] + 12
    assert include_summary["donors_explicit"] == default_summary["donors_explicit"] + 8
    assert include_summary["services_total"] == default_summary["services_total"] + 1


def test_directory_stats_can_select_only_withdrawn_biobanks(monkeypatch):
    only_globals, _, _ = _run_script(
        monkeypatch,
        "directory-stats.py",
        ["-N", "--only-withdrawn"],
    )

    only_summary = only_globals["summary"]

    assert only_summary["biobanks_total"] == 1
    assert only_summary["withdrawn_biobanks"] == 1
    assert only_summary["collection_records_total"] == 1


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
        ["-N", "-c", "CZ,DE", "-T", "CASE_CONTROL,POPULATION"],
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
