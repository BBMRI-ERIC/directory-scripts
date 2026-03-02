import networkx as nx
import pytest

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
        }
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
    ]
    directory.contacts = [{"id": "ct1", "country": "CZ"}]
    directory.networks = [{"id": "net1", "country": {"id": "CZ"}}]
    directory.facts = [{"id": "fact1", "collection": {"id": "col1"}}]
    directory.services = [{"id": "svc1", "biobank": {"id": "bb1"}}]
    directory.contactHashmap = {"ct1": {"id": "ct1", "country": "CZ"}}
    directory.collectionFactMap = {"col1": [{"id": "fact1"}]}
    directory.serviceHashmap = {"svc1": {"id": "svc1", "biobank": {"id": "bb1"}}}
    directory.biobankServiceMap = {"bb1": [{"id": "svc1", "biobank": {"id": "bb1"}}]}

    directory.directoryGraph = nx.DiGraph()
    directory.directoryGraph.add_node("bb1", data=directory.biobanks[0])
    directory.directoryGraph.add_node("bb2", data=directory.biobanks[1])
    for collection in directory.collections:
        directory.directoryGraph.add_node(collection["id"], data=collection)

    directory.directoryCollectionsDAG = nx.DiGraph()
    directory.directoryCollectionsDAG.add_edge("bb1", "col1")
    directory.directoryCollectionsDAG.add_edge("col1", "col2")
    directory.directoryCollectionsDAG.add_edge("bb2", "col3")
    directory.directoryCollectionsDAG.add_edge("col3", "col4")

    directory.contactGraph = nx.DiGraph()
    directory.networkGraph = nx.DiGraph()
    directory.networkGraph.add_node("net1", data=directory.networks[0])

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

    assert [biobank["id"] for biobank in directory.getBiobanks()] == ["bb1"]
    assert [collection["id"] for collection in directory.getCollections()] == ["col1", "col2"]
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


def test_directory_can_return_only_withdrawn_entities():
    directory = _make_directory_stub()
    directory.include_withdrawn_entities = True
    directory.only_withdrawn_entities = True

    assert [biobank["id"] for biobank in directory.getBiobanks()] == ["bb2"]
    assert [collection["id"] for collection in directory.getCollections()] == ["col3", "col4"]
    assert [service["id"] for service in directory.getServices()] == []
