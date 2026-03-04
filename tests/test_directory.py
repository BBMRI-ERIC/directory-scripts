import networkx as nx
import pandas as pd
import pytest

import directory as directory_module
from directory import Directory


def _make_directory_stub():
    directory = Directory.__new__(Directory)
    directory.include_withdrawn_entities = True
    directory.only_withdrawn_entities = False
    directory._collection_withdrawn_cache = {}
    directory._Directory__package = "ERIC"

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
