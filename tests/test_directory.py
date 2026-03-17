import networkx as nx
import pandas as pd
import pytest

import directory as directory_module
from directory import Directory, get_directory_ontology_table


def _make_directory_stub():
    directory = Directory.__new__(Directory)
    directory.include_withdrawn_entities = True
    directory.only_withdrawn_entities = False
    directory._collection_withdrawn_cache = {}
    directory._Directory__package = "ERIC"
    directory._Directory__directoryURL = "https://directory.example.test"

    directory.biobanks = [
        {
            "id": "bb1",
            "country": "CZ",
            "contact": {"id": "ct1"},
            "withdrawn": False,
        },
        {
            "id": "bb2",
            "country": "DE",
            "contact": {"id": "ct1"},
            "withdrawn": True,
        },
        {
            "id": "bbmri-eric:ID:EXT_demo",
            "country": "US",
            "contact": {"id": "bbmri-eric:contactID:EXT_demo:main"},
            "withdrawn": False,
        },
    ]
    directory.collections = [
        {
            "id": "col1",
            "biobank": {"id": "bb1"},
            "contact": {"id": "ct1"},
            "size": 10,
            "withdrawn": False,
        },
        {
            "id": "col2",
            "biobank": {"id": "bb1"},
            "contact": {"id": "ct1"},
            "size": 5,
            "parent_collection": {"id": "col1"},
            "withdrawn": False,
        },
        {
            "id": "col3",
            "biobank": {"id": "bb2"},
            "contact": {"id": "ct1"},
            "size": 7,
            "withdrawn": False,
        },
        {
            "id": "col4",
            "biobank": {"id": "bb1"},
            "contact": {"id": "ct1"},
            "size": 2,
            "parent_collection": {"id": "col3"},
            "withdrawn": False,
        },
        {
            "id": "bbmri-eric:ID:EXT_demo:collection:col5",
            "biobank": {"id": "bbmri-eric:ID:EXT_demo"},
            "contact": {"id": "bbmri-eric:contactID:EXT_demo:main"},
            "country": "US",
            "size": 3,
            "withdrawn": False,
        },
    ]
    directory.contacts = [
        {"id": "ct1", "country": "CZ"},
        {"id": "bbmri-eric:contactID:EXT_demo:main", "country": "US"},
    ]
    directory.networks = [
        {"id": "net1", "country": {"id": "CZ"}},
        {"id": "bbmri-eric:networkID:EXT_demo:net1", "country": {"id": "US"}},
    ]
    directory.facts = [{"id": "fact1", "collection": {"id": "col1"}}]
    directory.services = [{"id": "svc1", "biobank": {"id": "bb1"}}]
    directory.qualBBtable = pd.DataFrame(
        [
            {
                "id": "qbb1",
                "biobank": "bb1",
                "quality_standard": "iso-1",
                "assess_level_bio": "eric",
            },
            {
                "id": "qbb2",
                "biobank": "bb2",
                "quality_standard": "iso-2",
                "assess_level_bio": "accredited",
            },
            {
                "id": "qbb3",
                "biobank": "bbmri-eric:ID:EXT_demo",
                "quality_standard": "iso-1",
                "assess_level_bio": "eric",
            },
        ]
    )
    directory.qualColltable = pd.DataFrame(
        [
            {
                "id": "qc1",
                "collection": "col1",
                "quality_standard": "iso-1",
                "assess_level_col": "eric",
            },
            {
                "id": "qc2",
                "collection": "col3",
                "quality_standard": "iso-2",
                "assess_level_col": "accredited",
            },
            {
                "id": "qc3",
                "collection": "bbmri-eric:ID:EXT_demo:collection:col5",
                "quality_standard": "iso-1",
                "assess_level_col": "eric",
            },
        ]
    )
    directory.contactHashmap = {
        "ct1": {"id": "ct1", "country": "CZ"},
        "bbmri-eric:contactID:EXT_demo:main": {
            "id": "bbmri-eric:contactID:EXT_demo:main",
            "country": "US",
        },
    }
    directory.collectionFactMap = {"col1": [{"id": "fact1"}]}
    directory.serviceHashmap = {"svc1": {"id": "svc1", "biobank": {"id": "bb1"}}}
    directory.biobankServiceMap = {"bb1": [{"id": "svc1", "biobank": {"id": "bb1"}}]}

    directory.directoryGraph = nx.DiGraph()
    directory.directoryGraph.add_node("bb1", data=directory.biobanks[0])
    directory.directoryGraph.add_node("bb2", data=directory.biobanks[1])
    directory.directoryGraph.add_node("bbmri-eric:ID:EXT_demo", data=directory.biobanks[2])
    for collection in directory.collections:
        directory.directoryGraph.add_node(collection["id"], data=collection)

    directory.directoryCollectionsDAG = nx.DiGraph()
    directory.directoryCollectionsDAG.add_edge("bb1", "col1")
    directory.directoryCollectionsDAG.add_edge("col1", "col2")
    directory.directoryCollectionsDAG.add_edge("bb2", "col3")
    directory.directoryCollectionsDAG.add_edge("col3", "col4")
    directory.directoryCollectionsDAG.add_edge(
        "bbmri-eric:ID:EXT_demo",
        "bbmri-eric:ID:EXT_demo:collection:col5",
    )

    directory.contactGraph = nx.DiGraph()
    directory.networkGraph = nx.DiGraph()
    directory.networkGraph.add_node("net1", data=directory.networks[0])
    directory.networkGraph.add_node(
        "bbmri-eric:networkID:EXT_demo:net1",
        data=directory.networks[1],
    )

    return directory


def test_get_biobank_by_id_returns_none_and_logs_warning(caplog):
    directory = _make_directory_stub()
    with caplog.at_level("WARNING"):
        assert directory.getBiobankById("missing-id") is None
    assert "not found" in caplog.text


def test_get_biobank_by_id_raise_on_missing():
    directory = _make_directory_stub()
    with pytest.raises(KeyError):
        directory.getBiobankById("missing-id", raise_on_missing=True)


def test_get_collection_by_id_returns_none_and_logs_warning(caplog):
    directory = _make_directory_stub()
    with caplog.at_level("WARNING"):
        assert directory.getCollectionById("missing-id") is None
    assert "not found" in caplog.text


def test_get_collection_by_id_raise_on_missing():
    directory = _make_directory_stub()
    with pytest.raises(KeyError):
        directory.getCollectionById("missing-id", raise_on_missing=True)


def test_is_countable_collection_rejects_unsupported_metric():
    directory = _make_directory_stub()
    with pytest.raises(ValueError):
        directory.isCountableCollection("col1", "unsupported")


def test_is_countable_collection_for_top_level_metric():
    directory = _make_directory_stub()
    assert directory.isCountableCollection("col1", "size") is True


def test_is_countable_collection_for_child_with_countable_parent():
    directory = _make_directory_stub()
    assert directory.isCountableCollection("col2", "size") is False


def test_is_countable_collection_returns_false_for_missing_metric():
    directory = _make_directory_stub()
    assert directory.isCountableCollection("col1", "number_of_donors") is False


def test_get_collection_facts_returns_empty_list_for_missing_collection():
    directory = _make_directory_stub()
    assert directory.getCollectionFacts("missing-id") == []


def test_get_service_by_id_returns_none_and_logs_warning(caplog):
    directory = _make_directory_stub()
    with caplog.at_level("WARNING"):
        assert directory.getServiceById("missing-id") is None
    assert "not found" in caplog.text


def test_get_service_by_id_raise_on_missing():
    directory = _make_directory_stub()
    with pytest.raises(KeyError):
        directory.getServiceById("missing-id", raise_on_missing=True)


def test_get_biobank_services_returns_services_for_biobank():
    directory = _make_directory_stub()
    assert directory.getBiobankServices("bb1") == [{"id": "svc1", "biobank": {"id": "bb1"}}]


def test_get_entity_attribute_id_normalizes_dict_name_and_scalar_values():
    assert Directory.getEntityAttributeId({"id": "X1", "name": "Name"}) == "X1"
    assert Directory.getEntityAttributeId({"name": "Only Name"}) == "Only Name"
    assert Directory.getEntityAttributeId("PLASMA") == "PLASMA"
    assert Directory.getEntityAttributeId(None) is None
    assert Directory.getEntityAttributeId(float("nan")) is None


def test_get_list_of_entity_attribute_ids_accepts_mixed_emx2_shapes():
    entity = {
        "materials": ["DNA", {"id": "RNA"}, {"name": "SERUM"}, None, ""],
        "diagnosis_available": [{"name": "E11"}, {"id": "ORPHA:123"}],
        "order_of_magnitude": "3",
    }

    assert Directory.getListOfEntityAttributeIds(entity, "materials") == ["DNA", "RNA", "SERUM"]
    assert Directory.getListOfEntityAttributeIds(entity, "diagnosis_available") == ["E11", "ORPHA:123"]
    assert Directory.getListOfEntityAttributeIds(entity, "missing") == []
    assert Directory.getListOfEntityAttributeIds(entity, "order_of_magnitude") == ["3"]


def test_directory_filters_withdrawn_entities_when_requested():
    directory = _make_directory_stub()
    directory.include_withdrawn_entities = False
    directory.only_withdrawn_entities = False

    assert [biobank["id"] for biobank in directory.getBiobanks()] == [
        "bb1",
        "bbmri-eric:ID:EXT_demo",
    ]
    assert [collection["id"] for collection in directory.getCollections()] == [
        "col1",
        "col2",
        "bbmri-eric:ID:EXT_demo:collection:col5",
    ]
    assert directory.getBiobankById("bb2") is None
    assert directory.getCollectionById("col3") is None
    assert directory.getCollectionById("col4") is None


def test_is_collection_withdrawn_inherits_from_parent_biobank_and_collection():
    directory = _make_directory_stub()

    assert directory.isCollectionWithdrawn("col1") is False
    assert directory.isCollectionWithdrawn("col3") is True
    assert directory.isCollectionWithdrawn("col4") is True


def test_get_direct_subcollections_respects_withdrawn_filter():
    directory = _make_directory_stub()
    directory.include_withdrawn_entities = False
    directory.only_withdrawn_entities = False

    assert [collection["id"] for collection in directory.getDirectSubcollections("col1")] == ["col2"]
    assert directory.getDirectSubcollections("col3") == []


def test_quality_info_api_respects_scope_and_returns_copies():
    directory = _make_directory_stub()
    directory.include_withdrawn_entities = False
    directory.only_withdrawn_entities = False

    configured_biobank_quality = directory.getBiobankQualityInfo()
    all_biobank_quality = directory.getBiobankQualityInfo(scope="all")
    withdrawn_collection_quality = directory.getCollectionQualityInfo(scope="withdrawn")

    assert configured_biobank_quality["biobank"].tolist() == ["bb1", "bbmri-eric:ID:EXT_demo"]
    assert all_biobank_quality["biobank"].tolist() == ["bb1", "bb2", "bbmri-eric:ID:EXT_demo"]
    assert withdrawn_collection_quality["collection"].tolist() == ["col3"]

    configured_biobank_quality.loc[:, "biobank"] = "mutated"
    assert directory.getBiobankQualityInfo()["biobank"].tolist() == ["bb1", "bbmri-eric:ID:EXT_demo"]


def test_quality_info_wide_api_uses_instance_bound_ontology_labels(monkeypatch):
    directory = _make_directory_stub()
    calls = []
    ontology_df = pd.DataFrame(
        [
            {"name": "iso-1", "label": "ISO 1"},
            {"name": "iso-2", "label": "ISO 2"},
        ]
    )

    def fake_get_directory_ontology_table(table_name, *, directory_url=None, purge_cache=False):
        calls.append((table_name, directory_url, purge_cache))
        return ontology_df

    monkeypatch.setattr(directory_module, "get_directory_ontology_table", fake_get_directory_ontology_table)

    wide_df = directory.getBiobankQualityInfoWide(use_ontology_labels=True)

    assert "ISO 1" in wide_df.columns
    assert ("QualityStandards", "https://directory.example.test", False) in calls


def test_quality_info_api_rejects_invalid_scope():
    directory = _make_directory_stub()

    with pytest.raises(ValueError, match="Unsupported quality scope"):
        directory.getBiobankQualityInfo(scope="invalid")


def test_directory_authenticates_before_setting_private_schema(monkeypatch, tmp_path):
    calls = []

    class ClientStub:
        def __init__(self, url, **kwargs):
            calls.append(("init", url, kwargs))

        def __enter__(self):
            calls.append(("enter",))
            return self

        def __exit__(self, exc_type, exc, tb):
            calls.append(("exit",))
            return False

        def signin(self, username, password):
            calls.append(("signin", username, password))

        def set_schema(self, schema):
            calls.append(("set_schema", schema))
            return schema

        def get_graphql(self, table=None):
            calls.append(("get_graphql", table))
            return []

        def get(self, table=None, as_df=False):
            calls.append(("get", table, as_df))
            return pd.DataFrame()

    monkeypatch.setattr(directory_module, "Client", ClientStub)
    monkeypatch.chdir(tmp_path)

    directory = Directory(schema="BBMRI-EU", username="user", password="secret")

    assert directory.getSchema() == "BBMRI-EU"
    assert ("signin", "user", "secret") in calls
    assert ("set_schema", "BBMRI-EU") in calls
    assert calls.index(("signin", "user", "secret")) < calls.index(("set_schema", "BBMRI-EU"))


def test_directory_uses_schema_specific_cache_and_skips_missing_quality_tables(monkeypatch, tmp_path):
    calls = []

    class ClientStub:
        def __init__(self, url, **kwargs):
            self.url = url

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def set_schema(self, schema):
            calls.append(("set_schema", schema))
            return schema

        def get(self, table=None, as_df=False):
            calls.append(("get", table, as_df))
            if table in {"QualityInfoBiobanks", "QualityInfoCollections"}:
                raise directory_module.NoSuchTableException(f"{table} missing")
            return pd.DataFrame()

        def get_graphql(self, table=None):
            calls.append(("get_graphql", table))
            return []

    monkeypatch.setattr(directory_module, "Client", ClientStub)
    monkeypatch.chdir(tmp_path)

    directory = Directory(schema="BBMRI-EU")

    assert (tmp_path / "data-check-cache" / "directory-BBMRI-EU").exists()
    assert directory.getQualBB().empty
    assert directory.getQualColl().empty
    assert ("get", "QualityInfoBiobanks", True) in calls
    assert ("get", "QualityInfoCollections", True) in calls


def test_directory_uses_complete_cache_without_live_client(monkeypatch, tmp_path):
    cache_dir = tmp_path / "data-check-cache" / "directory-ERIC"
    cache_dir.mkdir(parents=True)
    from diskcache import Cache

    with Cache(str(cache_dir)) as cache:
        cache["biobanks"] = [{"id": "bb1"}]
        cache["collections"] = [{"id": "col1", "biobank": {"id": "bb1"}}]
        cache["contacts"] = [{"id": "ct1"}]
        cache["networks"] = []
        cache["facts"] = []
        cache["services"] = []
        cache["quality_info_biobanks"] = pd.DataFrame()
        cache["quality_info_collections"] = pd.DataFrame()

    class ClientStub:
        def __init__(self, *args, **kwargs):
            raise AssertionError("Live client should not be constructed when the cache is complete.")

    monkeypatch.setattr(directory_module, "Client", ClientStub)
    monkeypatch.chdir(tmp_path)

    directory = Directory(schema="ERIC")

    assert directory.biobanks == [{"id": "bb1"}]
    assert directory.collections == [{"id": "col1", "biobank": {"id": "bb1"}}]
    assert directory.contacts == [{"id": "ct1"}]
    assert directory.networks == []
    assert directory.facts == []
    assert directory.services == []


def test_directory_backfills_missing_quality_tables_for_complete_cache(monkeypatch, tmp_path):
    cache_dir = tmp_path / "data-check-cache" / "directory-ERIC"
    cache_dir.mkdir(parents=True)
    from diskcache import Cache

    with Cache(str(cache_dir)) as cache:
        cache["biobanks"] = [{"id": "bb1"}]
        cache["collections"] = [{"id": "col1", "biobank": {"id": "bb1"}}]
        cache["contacts"] = [{"id": "ct1"}]
        cache["networks"] = []
        cache["facts"] = []
        cache["services"] = []

    calls = []
    quality_biobanks = pd.DataFrame(
        [{"id": "qbb1", "biobank": "bb1", "quality_standard": "ISO", "assess_level_bio": "eric"}]
    )
    quality_collections = pd.DataFrame(
        [{"id": "qc1", "collection": "col1", "quality_standard": "ISO", "assess_level_col": "accredited"}]
    )

    class ClientStub:
        def __init__(self, url, **kwargs):
            calls.append(("init", url, kwargs))

        def __enter__(self):
            calls.append(("enter",))
            return self

        def __exit__(self, exc_type, exc, tb):
            calls.append(("exit",))
            return False

        def set_schema(self, schema):
            calls.append(("set_schema", schema))
            return schema

        def get(self, table=None, as_df=False):
            calls.append(("get", table, as_df))
            if table == "QualityInfoBiobanks":
                return quality_biobanks
            if table == "QualityInfoCollections":
                return quality_collections
            raise AssertionError(f"Unexpected table fetch: {table}")

    monkeypatch.setattr(directory_module, "Client", ClientStub)
    monkeypatch.chdir(tmp_path)

    directory = Directory(schema="ERIC")

    assert directory.biobanks == [{"id": "bb1"}]
    assert directory.collections == [{"id": "col1", "biobank": {"id": "bb1"}}]
    assert directory.getQualBB().equals(quality_biobanks)
    assert directory.getQualColl().equals(quality_collections)
    assert ("get", "QualityInfoBiobanks", True) in calls
    assert ("get", "QualityInfoCollections", True) in calls

    with Cache(str(cache_dir)) as cache:
        assert cache["quality_info_biobanks"].equals(quality_biobanks)
        assert cache["quality_info_collections"].equals(quality_collections)


def test_get_directory_ontology_table_uses_cached_copy_without_live_client(monkeypatch, tmp_path):
    cache_dir = tmp_path / "data-check-cache" / "directory-DirectoryOntologies"
    cache_dir.mkdir(parents=True)
    ontology_df = pd.DataFrame([{"name": "iso-1", "label": "ISO 1"}])
    cache_key = "table:https://directory.bbmri-eric.eu:QualityStandards"

    from diskcache import Cache

    with Cache(str(cache_dir)) as cache:
        cache[cache_key] = ontology_df

    class ClientStub:
        def __init__(self, *args, **kwargs):
            raise AssertionError("Live client should not be constructed when ontology cache exists.")

    monkeypatch.setattr(directory_module, "Client", ClientStub)
    monkeypatch.chdir(tmp_path)

    result = get_directory_ontology_table("QualityStandards")

    assert result.equals(ontology_df)


def test_get_directory_ontology_table_fetches_and_caches_live_copy(monkeypatch, tmp_path):
    calls = []
    ontology_df = pd.DataFrame([{"name": "iso-1", "label": "ISO 1"}])
    cache_key = "table:https://directory.bbmri-eric.eu:QualityStandards"

    class ClientStub:
        def __init__(self, url, **kwargs):
            calls.append(("init", url, kwargs))

        def __enter__(self):
            calls.append(("enter",))
            return self

        def __exit__(self, exc_type, exc, tb):
            calls.append(("exit",))
            return False

        def get(self, table=None, as_df=False):
            calls.append(("get", table, as_df))
            assert table == "QualityStandards"
            assert as_df is True
            return ontology_df

    monkeypatch.setattr(directory_module, "Client", ClientStub)
    monkeypatch.chdir(tmp_path)

    result = get_directory_ontology_table("QualityStandards")

    assert result.equals(ontology_df)
    assert ("get", "QualityStandards", True) in calls

    from diskcache import Cache

    with Cache(str(tmp_path / "data-check-cache" / "directory-DirectoryOntologies")) as cache:
        assert cache[cache_key].equals(ontology_df)


def test_directory_raises_clear_error_when_offline_without_complete_cache(monkeypatch, tmp_path):
    class ClientStub:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("offline")

    monkeypatch.setattr(directory_module, "Client", ClientStub)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError, match="no complete cached snapshot is available"):
        Directory(schema="ERIC")


def test_directory_can_return_only_withdrawn_entities():
    directory = _make_directory_stub()
    directory.include_withdrawn_entities = True
    directory.only_withdrawn_entities = True

    assert [biobank["id"] for biobank in directory.getBiobanks()] == ["bb2"]
    assert [collection["id"] for collection in directory.getCollections()] == ["col3", "col4"]
    assert [service["id"] for service in directory.getServices()] == []


def test_directory_nn_methods_prefer_staging_area_over_country():
    directory = _make_directory_stub()

    assert directory.getBiobankNN("bbmri-eric:ID:EXT_demo") == "EXT"
    assert directory.getBiobankCountry("bbmri-eric:ID:EXT_demo") == "US"
    assert directory.getCollectionNN("bbmri-eric:ID:EXT_demo:collection:col5") == "EXT"
    assert directory.getCollectionCountry("bbmri-eric:ID:EXT_demo:collection:col5") == "US"
    assert directory.getContactNN("bbmri-eric:contactID:EXT_demo:main") == "EXT"
    assert directory.getContactCountry("bbmri-eric:contactID:EXT_demo:main") == "US"
    assert directory.getNetworkNN("bbmri-eric:networkID:EXT_demo:net1") == "EXT"
    assert directory.getNetworkCountry("bbmri-eric:networkID:EXT_demo:net1") == "US"
