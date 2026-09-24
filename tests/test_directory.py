"""Test directory behavior."""

import networkx as nx
import pandas as pd
import pytest

import directory as directory_module
from directory import Directory, get_directory_ontology_table


def _make_directory_stub():
    """Build an in-memory Directory with linked entities without fetching remote data.

    Returns:
        Directory instance constructed via __new__ with ERIC identity, populated
        entity graphs and lookups, and active plus withdrawn visibility enabled.
    """
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
            "studies": [{"id": "study1"}, {"id": "study2"}, {"id": "study3"}],
        },
        {
            "id": "col2",
            "biobank": {"id": "bb1"},
            "contact": {"id": "ct1"},
            "size": 5,
            "parent_collection": {"id": "col1"},
            "withdrawn": False,
            "studies": [{"id": "study2"}],
        },
        {
            "id": "col3",
            "biobank": {"id": "bb2"},
            "contact": {"id": "ct1"},
            "size": 7,
            "withdrawn": False,
            "studies": [{"id": "study4"}],
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
            "studies": [{"id": "study3"}],
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
    directory.services = [
        {"id": "svc1", "biobank": {"id": "bb1"}},
        {
            "id": "bbmri-eric:serviceID:EXT_demo:svc2",
            "biobank": {"id": "bbmri-eric:ID:EXT_demo"},
        },
    ]
    directory.studies = [
        {"id": "study1", "collections": [{"id": "col1"}]},
        {"id": "study2", "collections": [{"id": "col1"}, {"id": "col2"}]},
        {
            "id": "study3",
            "collections": [{"id": "col1"}, {"id": "bbmri-eric:ID:EXT_demo:collection:col5"}],
        },
        {"id": "study4", "collections": [{"id": "col3"}]},
    ]
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
    directory.serviceHashmap = {
        "svc1": {"id": "svc1", "biobank": {"id": "bb1"}},
        "bbmri-eric:serviceID:EXT_demo:svc2": {
            "id": "bbmri-eric:serviceID:EXT_demo:svc2",
            "biobank": {"id": "bbmri-eric:ID:EXT_demo"},
        },
    }
    directory.biobankServiceMap = {
        "bb1": [{"id": "svc1", "biobank": {"id": "bb1"}}],
        "bbmri-eric:ID:EXT_demo": [
            {
                "id": "bbmri-eric:serviceID:EXT_demo:svc2",
                "biobank": {"id": "bbmri-eric:ID:EXT_demo"},
            }
        ],
    }
    directory.studyHashmap = {
        "study1": {"id": "study1", "collections": [{"id": "col1"}]},
        "study2": {"id": "study2", "collections": [{"id": "col1"}, {"id": "col2"}]},
        "study3": {
            "id": "study3",
            "collections": [{"id": "col1"}, {"id": "bbmri-eric:ID:EXT_demo:collection:col5"}],
        },
        "study4": {"id": "study4", "collections": [{"id": "col3"}]},
    }
    directory.collectionStudyMap = {
        "col1": [directory.studyHashmap["study1"], directory.studyHashmap["study2"], directory.studyHashmap["study3"]],
        "col2": [directory.studyHashmap["study2"]],
        "bbmri-eric:ID:EXT_demo:collection:col5": [directory.studyHashmap["study3"]],
        "col3": [directory.studyHashmap["study4"]],
    }
    directory.studyCollectionIdMap = {
        "study1": ["col1"],
        "study2": ["col1", "col2"],
        "study3": ["col1", "bbmri-eric:ID:EXT_demo:collection:col5"],
        "study4": ["col3"],
    }
    directory.biobankStudyMap = {
        "bb1": [directory.studyHashmap["study1"], directory.studyHashmap["study2"], directory.studyHashmap["study3"]],
        "bbmri-eric:ID:EXT_demo": [directory.studyHashmap["study3"]],
        "bb2": [directory.studyHashmap["study4"]],
    }

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
    directory.directoryServicesGraph = nx.DiGraph()
    directory.directoryServicesGraph.add_node("bb1", data=directory.biobanks[0])
    directory.directoryServicesGraph.add_node("bb2", data=directory.biobanks[1])
    directory.directoryServicesGraph.add_node("bbmri-eric:ID:EXT_demo", data=directory.biobanks[2])
    for service in directory.services:
        directory.directoryServicesGraph.add_node(service["id"], data=service)
    directory.directoryServicesGraph.add_edge("bb1", "svc1")
    directory.directoryServicesGraph.add_edge("svc1", "bb1")
    directory.directoryServicesGraph.add_edge(
        "bbmri-eric:ID:EXT_demo",
        "bbmri-eric:serviceID:EXT_demo:svc2",
    )
    directory.directoryServicesGraph.add_edge(
        "bbmri-eric:serviceID:EXT_demo:svc2",
        "bbmri-eric:ID:EXT_demo",
    )
    directory.directoryServicesDAG = nx.DiGraph()
    directory.directoryServicesDAG.add_edge("bb1", "svc1")
    directory.directoryServicesDAG.add_edge(
        "bbmri-eric:ID:EXT_demo",
        "bbmri-eric:serviceID:EXT_demo:svc2",
    )
    directory.directoryStudiesGraph = nx.DiGraph()
    directory.directoryStudiesGraph.add_node("bb1", data=directory.biobanks[0])
    directory.directoryStudiesGraph.add_node("bb2", data=directory.biobanks[1])
    directory.directoryStudiesGraph.add_node("bbmri-eric:ID:EXT_demo", data=directory.biobanks[2])
    for collection in directory.collections:
        directory.directoryStudiesGraph.add_node(collection["id"], data=collection)
    for study in directory.studies:
        directory.directoryStudiesGraph.add_node(study["id"], data=study)
    directory.directoryStudiesGraph.add_edge("bb1", "col1")
    directory.directoryStudiesGraph.add_edge("col1", "bb1")
    directory.directoryStudiesGraph.add_edge("col1", "col2")
    directory.directoryStudiesGraph.add_edge("col2", "col1")
    directory.directoryStudiesGraph.add_edge("bb2", "col3")
    directory.directoryStudiesGraph.add_edge("col3", "bb2")
    directory.directoryStudiesGraph.add_edge("col3", "col4")
    directory.directoryStudiesGraph.add_edge("col4", "col3")
    directory.directoryStudiesGraph.add_edge(
        "bbmri-eric:ID:EXT_demo",
        "bbmri-eric:ID:EXT_demo:collection:col5",
    )
    directory.directoryStudiesGraph.add_edge(
        "bbmri-eric:ID:EXT_demo:collection:col5",
        "bbmri-eric:ID:EXT_demo",
    )
    directory.directoryStudiesGraph.add_edge("col1", "study1")
    directory.directoryStudiesGraph.add_edge("study1", "col1")
    directory.directoryStudiesGraph.add_edge("col1", "study2")
    directory.directoryStudiesGraph.add_edge("study2", "col1")
    directory.directoryStudiesGraph.add_edge("col2", "study2")
    directory.directoryStudiesGraph.add_edge("study2", "col2")
    directory.directoryStudiesGraph.add_edge("col1", "study3")
    directory.directoryStudiesGraph.add_edge("study3", "col1")
    directory.directoryStudiesGraph.add_edge("bbmri-eric:ID:EXT_demo:collection:col5", "study3")
    directory.directoryStudiesGraph.add_edge("study3", "bbmri-eric:ID:EXT_demo:collection:col5")
    directory.directoryStudiesGraph.add_edge("col3", "study4")
    directory.directoryStudiesGraph.add_edge("study4", "col3")
    directory.directoryStudiesDAG = nx.DiGraph()
    directory.directoryStudiesDAG.add_edge("bb1", "col1")
    directory.directoryStudiesDAG.add_edge("col1", "col2")
    directory.directoryStudiesDAG.add_edge("bb2", "col3")
    directory.directoryStudiesDAG.add_edge("col3", "col4")
    directory.directoryStudiesDAG.add_edge(
        "bbmri-eric:ID:EXT_demo",
        "bbmri-eric:ID:EXT_demo:collection:col5",
    )
    directory.directoryStudiesDAG.add_edge("col1", "study1")
    directory.directoryStudiesDAG.add_edge("col1", "study2")
    directory.directoryStudiesDAG.add_edge("col2", "study2")
    directory.directoryStudiesDAG.add_edge("col1", "study3")
    directory.directoryStudiesDAG.add_edge("bbmri-eric:ID:EXT_demo:collection:col5", "study3")
    directory.directoryStudiesDAG.add_edge("col3", "study4")

    directory.contactGraph = nx.DiGraph()
    directory.networkGraph = nx.DiGraph()
    directory.networkGraph.add_node("net1", data=directory.networks[0])
    directory.networkGraph.add_node(
        "bbmri-eric:networkID:EXT_demo:net1",
        data=directory.networks[1],
    )

    return directory


def test_get_biobank_by_id_returns_none_and_logs_warning(caplog):
    """Verify get biobank by id returns none and logs warning.

    Args:
        caplog: Pytest log-capture fixture used to inspect emitted log records.

    Returns:
        None. Verifies get biobank by id returns none and logs warning.
    """
    directory = _make_directory_stub()
    with caplog.at_level("WARNING"):
        assert directory.getBiobankById("missing-id") is None
    assert "not found" in caplog.text


def test_get_biobank_by_id_raise_on_missing():
    """Verify get biobank by id raise on missing.

    Returns:
        None. Verifies get biobank by id raise on missing.
    """
    directory = _make_directory_stub()
    with pytest.raises(KeyError):
        directory.getBiobankById("missing-id", raise_on_missing=True)


def test_get_collection_by_id_returns_none_and_logs_warning(caplog):
    """Verify get collection by id returns none and logs warning.

    Args:
        caplog: Pytest log-capture fixture used to inspect emitted log records.

    Returns:
        None. Verifies get collection by id returns none and logs warning.
    """
    directory = _make_directory_stub()
    with caplog.at_level("WARNING"):
        assert directory.getCollectionById("missing-id") is None
    assert "not found" in caplog.text


def test_get_collection_by_id_raise_on_missing():
    """Verify get collection by id raise on missing.

    Returns:
        None. Verifies get collection by id raise on missing.
    """
    directory = _make_directory_stub()
    with pytest.raises(KeyError):
        directory.getCollectionById("missing-id", raise_on_missing=True)


def test_bidirectional_graph_validation_reports_and_repairs_missing_reverse_edges(
    caplog,
):
    """Verify bidirectional graph validation reports and repairs missing reverse edges.

    Args:
        caplog: Pytest log-capture fixture used to inspect emitted log records.

    Returns:
        None. Verifies bidirectional graph validation reports and repairs missing reverse edges.
    """
    graph = nx.DiGraph()
    graph.add_node("source", data={"id": "source"})
    graph.add_node("target", data={"id": "target"})
    graph.add_edge("source", "target")

    with caplog.at_level("DEBUG", logger="BBMRI Directory"):
        Directory._ensure_bidirectional_edges(graph, "contactGraph")

    assert graph.has_edge("target", "source")
    assert "contactGraph has 1 edge(s) without a reverse edge" in caplog.text
    assert "source -> target" in caplog.text
    assert "target -> source" in caplog.text
    assert "offending node source data" in caplog.text
    assert "offending node target data" in caplog.text


def test_dag_validation_reports_offending_graph_cycle_and_debug_node_data(caplog):
    """Verify dag validation reports offending graph cycle and debug node data.

    Args:
        caplog: Pytest log-capture fixture used to inspect emitted log records.

    Returns:
        None. Verifies dag validation reports offending graph cycle and debug node data.
    """
    graph = nx.DiGraph()
    graph.add_node("biobank1", data={"id": "biobank1", "name": "Biobank"})
    graph.add_node("collection1", data={"id": "collection1", "name": "Collection"})
    graph.add_edge("biobank1", "collection1")
    graph.add_edge("collection1", "biobank1")

    with caplog.at_level("DEBUG", logger="BBMRI Directory"):
        with pytest.raises(Exception) as exc_info:
            Directory._validate_directed_acyclic_graph(
                graph,
                "directoryCollectionsDAG",
                "Collection DAG",
            )

    error_message = str(exc_info.value)
    assert "Collection DAG is not DAG" in error_message
    assert "directoryCollectionsDAG" in error_message
    assert "directed acyclic graph requirement" in error_message
    assert "offending cycle" in error_message
    assert "cycle edges" in error_message
    assert "biobank1" in error_message
    assert "collection1" in error_message
    assert "offending node biobank1 data" in caplog.text
    assert "offending node collection1 data" in caplog.text


def test_directory_dag_validation_emergency_skip_allows_cyclic_graph(caplog):
    """Verify directory dag validation emergency skip allows cyclic graph.

    Args:
        caplog: Pytest log-capture fixture used to inspect emitted log records.

    Returns:
        None. Verifies directory dag validation emergency skip allows cyclic graph.
    """
    cyclic_collections = nx.DiGraph()
    cyclic_collections.add_edge("collection1", "collection2")
    cyclic_collections.add_edge("collection2", "collection1")
    empty_services = nx.DiGraph()
    empty_studies = nx.DiGraph()

    with caplog.at_level("WARNING", logger="BBMRI Directory"):
        Directory._validate_directory_dags(
            cyclic_collections,
            empty_services,
            empty_studies,
            skip_validation=True,
        )

    assert "Emergency mode enabled" in caplog.text
    assert "Proceed at own risk" in caplog.text


def test_directory_dag_validation_rejects_cyclic_graph_without_emergency_skip():
    """Verify directory dag validation rejects cyclic graph without emergency skip.

    Returns:
        None. Verifies directory dag validation rejects cyclic graph without emergency skip.
    """
    cyclic_collections = nx.DiGraph()
    cyclic_collections.add_edge("collection1", "collection2")
    cyclic_collections.add_edge("collection2", "collection1")

    with pytest.raises(Exception):
        Directory._validate_directory_dags(
            cyclic_collections,
            nx.DiGraph(),
            nx.DiGraph(),
            skip_validation=False,
        )


def test_collection_withdrawn_inheritance_handles_parent_cycle(caplog):
    """Verify collection withdrawn inheritance handles parent cycle.

    Args:
        caplog: Pytest log-capture fixture used to inspect emitted log records.

    Returns:
        None. Verifies collection withdrawn inheritance handles parent cycle.
    """
    directory = Directory.__new__(Directory)
    directory._collection_withdrawn_cache = {}
    directory.directoryGraph = nx.DiGraph()
    directory.directoryGraph.add_node(
        "biobank1",
        data={"id": "biobank1", "withdrawn": False},
    )
    directory.directoryGraph.add_node(
        "collection1",
        data={
            "id": "collection1",
            "biobank": {"id": "biobank1"},
            "parent_collection": {"id": "collection2"},
            "withdrawn": False,
        },
    )
    directory.directoryGraph.add_node(
        "collection2",
        data={
            "id": "collection2",
            "biobank": {"id": "biobank1"},
            "parent_collection": {"id": "collection1"},
            "withdrawn": False,
        },
    )

    with caplog.at_level("WARNING", logger="BBMRI Directory"):
        assert directory.isCollectionWithdrawn("collection1") is False

    assert "collection withdrawal inheritance cycle detected" in caplog.text
    assert "collection1 -> collection2 -> collection1" in caplog.text


def test_is_countable_collection_rejects_unsupported_metric():
    """Verify is countable collection rejects unsupported metric.

    Returns:
        None. Verifies is countable collection rejects unsupported metric.
    """
    directory = _make_directory_stub()
    with pytest.raises(ValueError):
        directory.isCountableCollection("col1", "unsupported")


def test_is_countable_collection_for_top_level_metric():
    """Verify is countable collection for top level metric.

    Returns:
        None. Verifies is countable collection for top level metric.
    """
    directory = _make_directory_stub()
    assert directory.isCountableCollection("col1", "size") is True


def test_is_countable_collection_for_child_with_countable_parent():
    """Verify is countable collection for child with countable parent.

    Returns:
        None. Verifies is countable collection for child with countable parent.
    """
    directory = _make_directory_stub()
    assert directory.isCountableCollection("col2", "size") is False


def test_is_countable_collection_returns_false_for_missing_metric():
    """Verify is countable collection returns false for missing metric.

    Returns:
        None. Verifies is countable collection returns false for missing metric.
    """
    directory = _make_directory_stub()
    assert directory.isCountableCollection("col1", "number_of_donors") is False


def test_get_collection_facts_returns_empty_list_for_missing_collection():
    """Verify get collection facts returns empty list for missing collection.

    Returns:
        None. Verifies get collection facts returns empty list for missing collection.
    """
    directory = _make_directory_stub()
    assert directory.getCollectionFacts("missing-id") == []


def test_get_service_by_id_returns_none_and_logs_warning(caplog):
    """Verify get service by id returns none and logs warning.

    Args:
        caplog: Pytest log-capture fixture used to inspect emitted log records.

    Returns:
        None. Verifies get service by id returns none and logs warning.
    """
    directory = _make_directory_stub()
    with caplog.at_level("WARNING"):
        assert directory.getServiceById("missing-id") is None
    assert "not found" in caplog.text


def test_get_service_by_id_raise_on_missing():
    """Verify get service by id raise on missing.

    Returns:
        None. Verifies get service by id raise on missing.
    """
    directory = _make_directory_stub()
    with pytest.raises(KeyError):
        directory.getServiceById("missing-id", raise_on_missing=True)


def test_get_biobank_services_returns_services_for_biobank():
    """Verify get biobank services returns services for biobank.

    Returns:
        None. Verifies get biobank services returns services for biobank.
    """
    directory = _make_directory_stub()
    assert directory.getBiobankServices("bb1") == [{"id": "svc1", "biobank": {"id": "bb1"}}]


def test_service_helpers_resolve_parent_biobank_contact_and_scope():
    """Verify service helpers resolve parent biobank contact and scope.

    Returns:
        None. Verifies service helpers resolve parent biobank contact and scope.
    """
    directory = _make_directory_stub()
    assert directory.getServiceBiobankId("svc1") == "bb1"
    assert directory.getServiceContact("svc1") == {"id": "ct1", "country": "CZ"}
    assert directory.getServiceNN("bbmri-eric:serviceID:EXT_demo:svc2") == "EXT"
    assert directory.getServiceCountry("bbmri-eric:serviceID:EXT_demo:svc2") == "US"


def test_study_helpers_resolve_collections_biobanks_and_contacts():
    """Verify study helpers resolve collections biobanks and contacts.

    Returns:
        None. Verifies study helpers resolve collections biobanks and contacts.
    """
    directory = _make_directory_stub()

    assert [study["id"] for study in directory.getStudies()] == ["study1", "study2", "study3", "study4"]
    assert [study["id"] for study in directory.getCollectionStudies("col1")] == ["study1", "study2", "study3"]
    assert directory.getCollectionStudyIds("col1") == ["study1", "study2", "study3"]
    assert [study["id"] for study in directory.getBiobankStudies("bb1")] == ["study1", "study2", "study3"]
    assert directory.getBiobankStudyIds("bb1") == ["study1", "study2", "study3"]
    assert directory.getStudyCollectionIds("study2") == ["col1", "col2"]
    assert directory.getStudyCountries("study3") == ["CZ", "US"]
    assert directory.getStudyBiobankIds("study2") == ["bb1"]
    assert directory.getStudyBiobankId("study2") == "bb1"
    assert directory.getStudyContact("study2") == {"id": "ct1", "country": "CZ"}
    assert [contact["id"] for contact in directory.getStudyContacts("study3")] == [
        "ct1",
        "bbmri-eric:contactID:EXT_demo:main",
    ]
    assert directory.getStudyContact("study3") is None


def test_service_and_study_graph_helpers_return_expected_subgraphs():
    """Verify service and study graph helpers return expected subgraphs.

    Returns:
        None. Verifies service and study graph helpers return expected subgraphs.
    """
    directory = _make_directory_stub()

    assert set(directory.getGraphBiobankServicesFromBiobank("bb1").nodes()) == {"bb1", "svc1"}
    assert set(directory.getGraphBiobankStudiesFromBiobank("bb1").nodes()) == {
        "bb1",
        "col1",
        "col2",
        "study1",
        "study2",
        "study3",
    }
    assert set(directory.getGraphBiobankStudiesFromStudy("study3").nodes()) == {
        "bb1",
        "col1",
        "study3",
        "bbmri-eric:ID:EXT_demo",
        "bbmri-eric:ID:EXT_demo:collection:col5",
    }


def test_get_entity_attribute_id_normalizes_dict_name_and_scalar_values():
    """Verify get entity attribute id normalizes dict name and scalar values.

    Returns:
        None. Verifies get entity attribute id normalizes dict name and scalar values.
    """
    assert Directory.getEntityAttributeId({"id": "X1", "name": "Name"}) == "X1"
    assert Directory.getEntityAttributeId({"name": "Only Name"}) == "Only Name"
    assert Directory.getEntityAttributeId("PLASMA") == "PLASMA"
    assert Directory.getEntityAttributeId(None) is None
    assert Directory.getEntityAttributeId(float("nan")) is None


def test_get_list_of_entity_attribute_ids_accepts_mixed_emx2_shapes():
    """Verify get list of entity attribute ids accepts mixed emx2 shapes.

    Returns:
        None. Verifies get list of entity attribute ids accepts mixed emx2 shapes.
    """
    entity = {
        "materials": ["DNA", {"id": "RNA"}, {"name": "SERUM"}, None, ""],
        "diagnosis_available": [{"name": "E11"}, {"id": "ORPHA:123"}],
        "order_of_magnitude": "3",
    }

    assert Directory.getListOfEntityAttributeIds(entity, "materials") == ["DNA", "RNA", "SERUM"]
    assert Directory.getListOfEntityAttributeIds(entity, "diagnosis_available") == ["E11", "ORPHA:123"]
    assert Directory.getListOfEntityAttributeIds(entity, "missing") == []
    assert Directory.getListOfEntityAttributeIds(entity, "order_of_magnitude") == ["3"]


def test_get_parent_biobank_returns_visible_owner():
    """Verify get parent biobank returns visible owner.

    Returns:
        None. Verifies get parent biobank returns visible owner.
    """
    directory = _make_directory_stub()

    assert directory.getParentBiobank("col1") == directory.biobanks[0]


def test_get_parent_biobank_handles_missing_collection():
    """Verify get parent biobank handles missing collection.

    Returns:
        None. Verifies get parent biobank handles missing collection.
    """
    directory = _make_directory_stub()

    assert directory.getParentBiobank("absent") is None
    with pytest.raises(KeyError, match="absent"):
        directory.getParentBiobank("absent", raise_on_missing=True)


@pytest.mark.parametrize("bad_owner", [None, "bb1", {}, {"id": ""}, {"id": "  "}])
def test_get_parent_biobank_rejects_malformed_ownership(bad_owner):
    """Verify get parent biobank rejects malformed ownership.

    Args:
        bad_owner: Malformed ownership value used to verify parent validation.

    Returns:
        None. Verifies get parent biobank rejects malformed ownership.
    """
    directory = _make_directory_stub()
    directory.collections[0]["biobank"] = bad_owner

    with pytest.raises(ValueError, match="col1"):
        directory.getParentBiobank("col1")


def test_get_parent_biobank_rejects_missing_ownership_field():
    """Verify get parent biobank rejects missing ownership field.

    Returns:
        None. Verifies get parent biobank rejects missing ownership field.
    """
    directory = _make_directory_stub()
    directory.collections[0].pop("biobank")

    with pytest.raises(ValueError, match="col1"):
        directory.getParentBiobank("col1")


def test_get_parent_biobank_handles_missing_parent():
    """Verify get parent biobank handles missing parent.

    Returns:
        None. Verifies get parent biobank handles missing parent.
    """
    directory = _make_directory_stub()
    directory.biobanks = directory.biobanks[1:]

    assert directory.getParentBiobank("col1") is None
    with pytest.raises(KeyError, match="bb1"):
        directory.getParentBiobank("col1", raise_on_missing=True)


def test_get_parent_biobank_handles_parent_missing_from_graph():
    """Verify get parent biobank handles parent missing from graph.

    Returns:
        None. Verifies get parent biobank handles parent missing from graph.
    """
    directory = _make_directory_stub()
    directory.biobanks = directory.biobanks[1:]
    directory.directoryGraph.remove_node("bb1")

    assert directory.getParentBiobank("col1") is None
    with pytest.raises(KeyError, match="bb1"):
        directory.getParentBiobank("col1", raise_on_missing=True)


def test_get_parent_biobank_handles_placeholder_parent():
    """Verify get parent biobank handles placeholder parent.

    Returns:
        None. Verifies get parent biobank handles placeholder parent.
    """
    directory = _make_directory_stub()
    directory.directoryGraph.nodes["bb1"].clear()

    assert directory.getParentBiobank("col1") is None
    with pytest.raises(KeyError, match="bb1"):
        directory.getParentBiobank("col1", raise_on_missing=True)


def test_get_parent_biobank_does_not_treat_biobank_as_collection():
    """Verify get parent biobank does not treat biobank as collection.

    Returns:
        None. Verifies get parent biobank does not treat biobank as collection.
    """
    directory = _make_directory_stub()

    assert directory.getParentBiobank("bb1") is None


def test_get_parent_biobank_excludes_withdrawn_collection_in_active_scope():
    """Verify get parent biobank excludes withdrawn collection in active scope.

    Returns:
        None. Verifies get parent biobank excludes withdrawn collection in active scope.
    """
    directory = _make_directory_stub()
    directory.include_withdrawn_entities = False
    directory.only_withdrawn_entities = False

    assert directory.getParentBiobank("col3") is None
    with pytest.raises(KeyError, match="col3"):
        directory.getParentBiobank("col3", raise_on_missing=True)


def test_negotiator_queries_require_loaded_state():
    """Verify negotiator queries require loaded state.

    Returns:
        None. Verifies negotiator queries require loaded state.
    """
    directory = _make_directory_stub()

    assert directory.hasNegotiatorData() is False
    with pytest.raises(RuntimeError, match="Negotiator data have not been loaded"):
        directory.getNegotiatorCoverage()


def test_set_negotiator_representatives_normalizes_immutable_sets():
    """Verify set negotiator representatives normalizes immutable sets.

    Returns:
        None. Verifies set negotiator representatives normalizes immutable sets.
    """
    directory = _make_directory_stub()

    directory.setNegotiatorRepresentatives({
        "col1": {
            "network_name": "Network",
            "biobank_name": "Biobank",
            "resource_name": "Collection",
            "representatives": {" REP@example.org ", "rep@example.org"},
        }
    })

    assert directory.hasNegotiatorData() is True
    assert directory.getCollectionNegotiatorRepresentatives("col1") == frozenset({"rep@example.org"})


@pytest.mark.parametrize("source", ["injection", "xlsx"])
def test_negotiator_query_respects_visibility_and_injection_tracks_unmatched(source, tmp_path):
    """Verify negotiator query respects visibility and injection tracks unmatched.

    Args:
        source: Registration route: injection for in-memory records, otherwise the representative XLSX loader.
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies negotiator query respects visibility and injection tracks unmatched.
    """
    directory = _make_directory_stub()
    directory.include_withdrawn_entities = False
    directory.only_withdrawn_entities = False

    records = {
        "col1": {"representatives": {"visible@example.org"}},
        "col3": {"representatives": {"withdrawn@example.org"}},
        "unknown": {"representatives": {"unknown@example.org"}},
    }
    if source == "injection":
        directory.setNegotiatorRepresentatives(records)
    else:
        workbook = tmp_path / "scope.xlsx"
        pd.DataFrame([
            {"network_name": "N", "biobank_name": "B", "resource_name": "C",
             "resource_source_id": cid,
             "representatives_emails": ";".join(row["representatives"])}
            for cid, row in records.items()
        ]).to_excel(workbook, index=False)
        directory.loadNegotiatorRepresentatives(workbook)

    assert directory.getCollectionNegotiatorRepresentatives("col1") == frozenset({"visible@example.org"})
    assert directory.getCollectionNegotiatorRepresentatives("col3") == frozenset()
    assert directory.getCollectionNegotiatorRepresentatives("unknown") == frozenset()
    assert directory.getUnmatchedNegotiatorResourceIds() == ("col3", "unknown")


def test_negotiator_replacement_is_atomic_on_invalid_ownership():
    """Verify negotiator replacement is atomic on invalid ownership.

    Returns:
        None. Verifies negotiator replacement is atomic on invalid ownership.
    """
    directory = _make_directory_stub()
    directory.setNegotiatorRepresentatives({"col1": {"representatives": {"old@example.org"}}})
    previous = directory.getNegotiatorResources()
    directory.collections[0].pop("biobank")

    with pytest.raises(ValueError, match="ownership"):
        directory.setNegotiatorRepresentatives({"col1": {"representatives": {"new@example.org"}}})

    assert directory.getNegotiatorResources() == previous
    assert directory.getUnmatchedNegotiatorResourceIds() == ()


def test_negotiator_coverage_uses_direct_representatives_only():
    """Verify negotiator coverage uses direct representatives only.

    Returns:
        None. Verifies negotiator coverage uses direct representatives only.
    """
    directory = _make_directory_stub()
    directory.setNegotiatorRepresentatives({"col1": {"representatives": {"a@example.org"}}})

    coverage = directory.getBiobankNegotiatorCoverage("bb1")

    assert coverage.status == "partially"
    assert coverage.active_collection_count == 3
    assert coverage.represented_collection_count == 1
    assert coverage.unrepresented_collection_count == 2


def test_load_negotiator_representatives_merges_duplicate_rows(tmp_path, caplog):
    """Verify load negotiator representatives merges duplicate rows.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        caplog: Pytest log-capture fixture used to inspect emitted log records.

    Returns:
        None. Verifies load negotiator representatives merges duplicate rows.
    """
    workbook = tmp_path / "representatives.xlsx"
    pd.DataFrame([
        {"network_name": "N", "biobank_name": "B", "resource_name": "C", "resource_source_id": "col1", "representatives_emails": "A@example.org; b@example.org"},
        {"network_name": "Other", "biobank_name": "B", "resource_name": "C", "resource_source_id": "col1", "representatives_emails": "b@example.org;c@example.org"},
    ]).to_excel(workbook, index=False)
    directory = _make_directory_stub()

    directory.loadNegotiatorRepresentatives(workbook)

    assert directory.getCollectionNegotiatorRepresentatives("col1") == frozenset({"a@example.org", "b@example.org", "c@example.org"})
    assert "conflicting metadata" in caplog.text


def test_load_negotiator_orphans_report_uses_collection_stats_sheet(tmp_path):
    """Verify load negotiator orphans report uses collection stats sheet.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies load negotiator orphans report uses collection stats sheet.
    """
    workbook = tmp_path / "orphans.xlsx"
    with pd.ExcelWriter(workbook) as writer:
        pd.DataFrame([{"summary_only": 1}]).to_excel(
            writer, sheet_name="nn_summary", index=False
        )
        pd.DataFrame([
            {
                "network_name": "N",
                "biobank_name": "B",
                "resource_name": "C1",
                "resource_source_id": "col1",
                "representatives_emails": "Rep@example.org",
                "auto_by_parent": False,
                "auto_by_biobank": False,
            },
            {
                "network_name": "N",
                "biobank_name": "B",
                "resource_name": "C2",
                "resource_source_id": "col2",
                "representatives_emails": "",
                "auto_by_parent": True,
                "auto_by_biobank": True,
            },
        ]).to_excel(
            writer, sheet_name="negotiator_collection_stats", index=False
        )
    directory = _make_directory_stub()

    directory.loadNegotiatorOrphansReport(workbook)

    assert directory.getCollectionNegotiatorRepresentatives("col1") == frozenset({
        "rep@example.org"
    })
    assert directory.getCollectionNegotiatorRepresentatives("col2") == frozenset()


def test_load_negotiator_orphans_report_requires_collection_stats_sheet(tmp_path):
    """Verify load negotiator orphans report requires collection stats sheet.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies load negotiator orphans report requires collection stats sheet.
    """
    workbook = tmp_path / "orphans.xlsx"
    pd.DataFrame([{"summary_only": 1}]).to_excel(
        workbook, sheet_name="nn_summary", index=False
    )
    directory = _make_directory_stub()

    with pytest.raises(ValueError, match="negotiator_collection_stats"):
        directory.loadNegotiatorOrphansReport(workbook)


def test_load_negotiator_orphans_report_validates_collection_stats_columns(tmp_path):
    """Verify load negotiator orphans report validates collection stats columns.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies load negotiator orphans report validates collection stats columns.
    """
    workbook = tmp_path / "orphans.xlsx"
    pd.DataFrame([{"resource_source_id": "col1"}]).to_excel(
        workbook, sheet_name="negotiator_collection_stats", index=False
    )
    directory = _make_directory_stub()

    with pytest.raises(ValueError, match="representatives_emails"):
        directory.loadNegotiatorOrphansReport(workbook)


def test_directory_filters_withdrawn_entities_when_requested():
    """Verify directory filters withdrawn entities when requested.

    Returns:
        None. Verifies directory filters withdrawn entities when requested.
    """
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
    assert [service["id"] for service in directory.getServices()] == ["svc1", "bbmri-eric:serviceID:EXT_demo:svc2"]
    assert [study["id"] for study in directory.getStudies()] == ["study1", "study2", "study3"]
    assert directory.getStudyById("study4") is None


def test_get_loaded_biobank_by_id_ignores_withdrawn_scope():
    """Verify get loaded biobank by id ignores withdrawn scope.

    Returns:
        None. Verifies get loaded biobank by id ignores withdrawn scope.
    """
    directory = _make_directory_stub()
    directory.include_withdrawn_entities = False
    directory.only_withdrawn_entities = False

    assert directory.getBiobankById("bb2") is None
    assert directory.getLoadedBiobankById("bb2") == directory.biobanks[1]


def test_get_loaded_collections_ignores_withdrawn_scope():
    """Verify get loaded collections ignores withdrawn scope.

    Returns:
        None. Verifies get loaded collections ignores withdrawn scope.
    """
    directory = _make_directory_stub()
    directory.include_withdrawn_entities = False
    directory.only_withdrawn_entities = False

    assert [collection["id"] for collection in directory.getCollections()] == [
        "col1",
        "col2",
        "bbmri-eric:ID:EXT_demo:collection:col5",
    ]
    assert directory.getLoadedCollections() == directory.collections
    assert directory.getLoadedCollections() is not directory.collections


def test_is_countable_collection_checks_ancestors_outside_withdrawn_scope():
    """Verify is countable collection checks ancestors outside withdrawn scope.

    Returns:
        None. Verifies is countable collection checks ancestors outside withdrawn scope.
    """
    directory = _make_directory_stub()
    directory.include_withdrawn_entities = False
    directory.only_withdrawn_entities = False

    assert directory.getCollectionById("col3") is None
    assert directory.isCountableCollection("col4", "size") is False


def test_is_collection_withdrawn_inherits_from_parent_biobank_and_collection():
    """Verify is collection withdrawn inherits from parent biobank and collection.

    Returns:
        None. Verifies is collection withdrawn inherits from parent biobank and collection.
    """
    directory = _make_directory_stub()

    assert directory.isCollectionWithdrawn("col1") is False
    assert directory.isCollectionWithdrawn("col3") is True
    assert directory.isCollectionWithdrawn("col4") is True


def test_get_direct_subcollections_respects_withdrawn_filter():
    """Verify get direct subcollections respects withdrawn filter.

    Returns:
        None. Verifies get direct subcollections respects withdrawn filter.
    """
    directory = _make_directory_stub()
    directory.include_withdrawn_entities = False
    directory.only_withdrawn_entities = False

    assert [collection["id"] for collection in directory.getDirectSubcollections("col1")] == ["col2"]
    assert directory.getDirectSubcollections("col3") == []


def test_quality_info_api_respects_scope_and_returns_copies():
    """Verify quality info api respects scope and returns copies.

    Returns:
        None. Verifies quality info api respects scope and returns copies.
    """
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
    """Verify quality info wide api uses instance bound ontology labels.

    Args:
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Verifies quality info wide api uses instance bound ontology labels.
    """
    directory = _make_directory_stub()
    calls = []
    ontology_df = pd.DataFrame(
        [
            {"name": "iso-1", "label": "ISO 1"},
            {"name": "iso-2", "label": "ISO 2"},
        ]
    )

    def fake_get_directory_ontology_table(table_name, *, directory_url=None, purge_cache=False):
        """Record the ontology request and return the shared QualityStandards DataFrame.

        Args:
            table_name: Ontology table name requested from the patched loader.
            directory_url: Directory URL observed by the patched ontology loader.
            purge_cache: Cache-purge flag observed by the fake ontology-table loader.

        Returns:
            The shared QualityStandards DataFrame after recording table, target URL, and purge flag.
        """
        calls.append((table_name, directory_url, purge_cache))
        return ontology_df

    monkeypatch.setattr(directory_module, "get_directory_ontology_table", fake_get_directory_ontology_table)

    wide_df = directory.getBiobankQualityInfoWide(use_ontology_labels=True)

    assert "ISO 1" in wide_df.columns
    assert ("QualityStandards", "https://directory.example.test", False) in calls


def test_quality_info_api_rejects_invalid_scope():
    """Verify quality info api rejects invalid scope.

    Returns:
        None. Verifies quality info api rejects invalid scope.
    """
    directory = _make_directory_stub()

    with pytest.raises(ValueError, match="Unsupported quality scope"):
        directory.getBiobankQualityInfo(scope="invalid")


@pytest.mark.parametrize("skip_dag", [False, True])
def test_directory_authenticates_before_setting_private_schema(monkeypatch, tmp_path, skip_dag):
    """Verify directory authenticates before setting private schema.

    Args:
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        skip_dag: DAG-validation flag passed to the Directory constructor.

    Returns:
        None. Verifies directory authenticates before setting private schema.
    """
    calls = []

    class ClientStub:
        """Record client entry, authentication, schema selection, and empty table reads in order.
        """
        def __init__(self, url, **kwargs):
            """Intercept client construction for the enclosing cache/authentication scenario.

            Args:
                url: Directory endpoint retained by the session test double.
                **kwargs: Client-constructor options accepted for API compatibility; no network session is opened.
            """
            calls.append(("init", url, kwargs))

        def __enter__(self):
            """Enter the context-manager test double.

            Returns:
                The context-manager test double entered by the with statement.
            """
            calls.append(("enter",))
            return self

        def __exit__(self, exc_type, exc, tb):
            """Exit the context-manager test double.

            Args:
                exc_type: Exception class accepted by the context-manager exit hook and deliberately not suppressed.
                exc: Exception instance accepted by the context-manager exit hook and deliberately not suppressed.
                tb: Traceback accepted by the context-manager exit hook and deliberately not suppressed.

            Returns:
                False, so exceptions raised inside the with block propagate to the caller.
            """
            calls.append(("exit",))
            return False

        def signin(self, username, password):
            """Record the sign-in call on the Directory-session double.

            Args:
                username: Credential value recorded by the fake sign-in call.
                password: Credential value recorded by the fake sign-in call.

            Returns:
                None. Record the sign-in call on the Directory-session double.
            """
            calls.append(("signin", username, password))

        def set_schema(self, schema):
            """Record the configured schema on this test double.

            Args:
                schema: Directory schema value retained by the session fixture.

            Returns:
                The same schema-name argument after recording the schema-selection call.
            """
            calls.append(("set_schema", schema))
            return schema

        def get_graphql(self, table=None):
            """Return fixture GraphQL result returned for the requested Directory table.

            Args:
                table: Directory table name recorded by the GraphQL session fixture.

            Returns:
                The fixture GraphQL result returned for the requested Directory table.
            """
            calls.append(("get_graphql", table))
            return []

        def get(self, table=None, as_df=False):
            """Return DataFrame fixture returned for the requested Directory table.

            Args:
                table: Directory table whose fixture rows the fake session returns.
                as_df: Flag selecting the DataFrame-shaped fixture result expected by the caller.

            Returns:
                The DataFrame fixture returned for the requested Directory table.
            """
            calls.append(("get", table, as_df))
            return pd.DataFrame()

    monkeypatch.setattr(directory_module, "Client", ClientStub)
    monkeypatch.chdir(tmp_path)

    directory = Directory(schema="BBMRI-EU", username="user", password="secret",
                          skip_graph_dag_validation=skip_dag)

    assert directory.getSchema() == "BBMRI-EU"
    assert directory.skip_graph_dag_validation is skip_dag
    assert ("signin", "user", "secret") in calls
    assert ("set_schema", "BBMRI-EU") in calls
    assert calls.index(("signin", "user", "secret")) < calls.index(("set_schema", "BBMRI-EU"))


def test_directory_uses_schema_specific_cache_and_skips_missing_quality_tables(monkeypatch, tmp_path):
    """Verify directory uses schema specific cache and skips missing quality tables.

    Args:
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies directory uses schema specific cache and skips missing quality tables.
    """
    calls = []

    class ClientStub:
        """Raise NoSuchTableException for optional quality tables while returning empty core tables.
        """
        def __init__(self, url, **kwargs):
            """Intercept client construction for the enclosing cache/authentication scenario.

            Args:
                url: Directory endpoint retained by the session test double.
                **kwargs: Client-constructor options accepted for API compatibility; no network session is opened.
            """
            self.url = url

        def __enter__(self):
            """Enter the context-manager test double.

            Returns:
                The context-manager test double entered by the with statement.
            """
            return self

        def __exit__(self, exc_type, exc, tb):
            """Exit the context-manager test double.

            Args:
                exc_type: Exception class accepted by the context-manager exit hook and deliberately not suppressed.
                exc: Exception instance accepted by the context-manager exit hook and deliberately not suppressed.
                tb: Traceback accepted by the context-manager exit hook and deliberately not suppressed.

            Returns:
                False, so exceptions raised inside the with block propagate to the caller.
            """
            return False

        def set_schema(self, schema):
            """Record the configured schema on this test double.

            Args:
                schema: Directory schema value retained by the session fixture.

            Returns:
                The same schema-name argument after recording the schema-selection call.
            """
            calls.append(("set_schema", schema))
            return schema

        def get(self, table=None, as_df=False):
            """Return DataFrame fixture returned for the requested Directory table.

            Args:
                table: Directory table whose fixture rows the fake session returns.
                as_df: Flag selecting the DataFrame-shaped fixture result expected by the caller.

            Returns:
                The DataFrame fixture returned for the requested Directory table.
            """
            calls.append(("get", table, as_df))
            if table in {"QualityInfoBiobanks", "QualityInfoCollections"}:
                raise directory_module.NoSuchTableException(f"{table} missing")
            return pd.DataFrame()

        def get_graphql(self, table=None):
            """Return fixture GraphQL result returned for the requested Directory table.

            Args:
                table: Directory table name recorded by the GraphQL session fixture.

            Returns:
                The fixture GraphQL result returned for the requested Directory table.
            """
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
    """Verify directory uses complete cache without live client.

    Args:
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies directory uses complete cache without live client.
    """
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
        cache["studies"] = []
        cache["quality_info_biobanks"] = pd.DataFrame()
        cache["quality_info_collections"] = pd.DataFrame()

    class ClientStub:
        """Reject live client creation when a complete Directory snapshot is cached.
        """
        def __init__(self, *args, **kwargs):
            """Intercept client construction for the enclosing cache/authentication scenario.

            Args:
                *args: Client-constructor positional arguments accepted solely to reject live access in this scenario.
                **kwargs: Client-constructor options accepted for API compatibility; no network session is opened.
            """
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
    assert directory.studies == []


def test_directory_backfills_missing_quality_tables_for_complete_cache(monkeypatch, tmp_path):
    """Verify directory backfills missing quality tables for complete cache.

    Args:
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies directory backfills missing quality tables for complete cache.
    """
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
        cache["studies"] = []

    calls = []
    quality_biobanks = pd.DataFrame(
        [{"id": "qbb1", "biobank": "bb1", "quality_standard": "ISO", "assess_level_bio": "eric"}]
    )
    quality_collections = pd.DataFrame(
        [{"id": "qc1", "collection": "col1", "quality_standard": "ISO", "assess_level_col": "accredited"}]
    )

    class ClientStub:
        """Record cache-backfill API calls and provide the requested fixture tables.
        """
        def __init__(self, url, **kwargs):
            """Intercept client construction for the enclosing cache/authentication scenario.

            Args:
                url: Directory endpoint retained by the session test double.
                **kwargs: Client-constructor options accepted for API compatibility; no network session is opened.
            """
            calls.append(("init", url, kwargs))

        def __enter__(self):
            """Enter the context-manager test double.

            Returns:
                The context-manager test double entered by the with statement.
            """
            calls.append(("enter",))
            return self

        def __exit__(self, exc_type, exc, tb):
            """Exit the context-manager test double.

            Args:
                exc_type: Exception class accepted by the context-manager exit hook and deliberately not suppressed.
                exc: Exception instance accepted by the context-manager exit hook and deliberately not suppressed.
                tb: Traceback accepted by the context-manager exit hook and deliberately not suppressed.

            Returns:
                False, so exceptions raised inside the with block propagate to the caller.
            """
            calls.append(("exit",))
            return False

        def set_schema(self, schema):
            """Record the configured schema on this test double.

            Args:
                schema: Directory schema value retained by the session fixture.

            Returns:
                The same schema-name argument after recording the schema-selection call.
            """
            calls.append(("set_schema", schema))
            return schema

        def get(self, table=None, as_df=False):
            """Return DataFrame fixture returned for the requested Directory table.

            Args:
                table: Directory table whose fixture rows the fake session returns.
                as_df: Flag selecting the DataFrame-shaped fixture result expected by the caller.

            Returns:
                The DataFrame fixture returned for the requested Directory table.
            """
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
    assert directory.studies == []
    assert directory.getQualBB().equals(quality_biobanks)
    assert directory.getQualColl().equals(quality_collections)
    assert ("get", "QualityInfoBiobanks", True) in calls
    assert ("get", "QualityInfoCollections", True) in calls

    with Cache(str(cache_dir)) as cache:
        assert cache["quality_info_biobanks"].equals(quality_biobanks)
        assert cache["quality_info_collections"].equals(quality_collections)


def test_get_directory_ontology_table_uses_cached_copy_without_live_client(monkeypatch, tmp_path):
    """Verify get directory ontology table uses cached copy without live client.

    Args:
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies get directory ontology table uses cached copy without live client.
    """
    cache_dir = tmp_path / "data-check-cache" / "directory-DirectoryOntologies"
    cache_dir.mkdir(parents=True)
    ontology_df = pd.DataFrame([{"name": "iso-1", "label": "ISO 1"}])
    cache_key = "table:https://directory.bbmri-eric.eu:QualityStandards"

    from diskcache import Cache

    with Cache(str(cache_dir)) as cache:
        cache[cache_key] = ontology_df

    class ClientStub:
        """Reject live client creation when the quality ontology is cached.
        """
        def __init__(self, *args, **kwargs):
            """Intercept client construction for the enclosing cache/authentication scenario.

            Args:
                *args: Client-constructor positional arguments accepted solely to reject live access in this scenario.
                **kwargs: Client-constructor options accepted for API compatibility; no network session is opened.
            """
            raise AssertionError("Live client should not be constructed when ontology cache exists.")

    monkeypatch.setattr(directory_module, "Client", ClientStub)
    monkeypatch.chdir(tmp_path)

    result = get_directory_ontology_table("QualityStandards")

    assert result.equals(ontology_df)


def test_get_directory_ontology_table_fetches_and_caches_live_copy(monkeypatch, tmp_path):
    """Verify get directory ontology table fetches and caches live copy.

    Args:
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies get directory ontology table fetches and caches live copy.
    """
    calls = []
    ontology_df = pd.DataFrame([{"name": "iso-1", "label": "ISO 1"}])
    cache_key = "table:https://directory.bbmri-eric.eu:QualityStandards"

    class ClientStub:
        """Serve the QualityStandards DataFrame and record context-manager and table-read calls.
        """
        def __init__(self, url, **kwargs):
            """Intercept client construction for the enclosing cache/authentication scenario.

            Args:
                url: Directory endpoint retained by the session test double.
                **kwargs: Client-constructor options accepted for API compatibility; no network session is opened.
            """
            calls.append(("init", url, kwargs))

        def __enter__(self):
            """Enter the context-manager test double.

            Returns:
                The context-manager test double entered by the with statement.
            """
            calls.append(("enter",))
            return self

        def __exit__(self, exc_type, exc, tb):
            """Exit the context-manager test double.

            Args:
                exc_type: Exception class accepted by the context-manager exit hook and deliberately not suppressed.
                exc: Exception instance accepted by the context-manager exit hook and deliberately not suppressed.
                tb: Traceback accepted by the context-manager exit hook and deliberately not suppressed.

            Returns:
                False, so exceptions raised inside the with block propagate to the caller.
            """
            calls.append(("exit",))
            return False

        def get(self, table=None, as_df=False):
            """Return DataFrame fixture returned for the requested Directory table.

            Args:
                table: Directory table whose fixture rows the fake session returns.
                as_df: Flag selecting the DataFrame-shaped fixture result expected by the caller.

            Returns:
                The DataFrame fixture returned for the requested Directory table.
            """
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
    """Verify directory raises clear error when offline without complete cache.

    Args:
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies directory raises clear error when offline without complete cache.
    """
    class ClientStub:
        """Simulate unavailable networking by raising RuntimeError during client construction.
        """
        def __init__(self, *args, **kwargs):
            """Intercept client construction for the enclosing cache/authentication scenario.

            Args:
                *args: Client-constructor positional arguments accepted solely to reject live access in this scenario.
                **kwargs: Client-constructor options accepted for API compatibility; no network session is opened.
            """
            raise RuntimeError("offline")

    monkeypatch.setattr(directory_module, "Client", ClientStub)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError, match="no complete cached snapshot is available"):
        Directory(schema="ERIC")


def test_directory_can_return_only_withdrawn_entities():
    """Verify directory can return only withdrawn entities.

    Returns:
        None. Verifies directory can return only withdrawn entities.
    """
    directory = _make_directory_stub()
    directory.include_withdrawn_entities = True
    directory.only_withdrawn_entities = True

    assert [biobank["id"] for biobank in directory.getBiobanks()] == ["bb2"]
    assert [collection["id"] for collection in directory.getCollections()] == ["col3", "col4"]
    assert [service["id"] for service in directory.getServices()] == []
    assert [study["id"] for study in directory.getStudies()] == ["study4"]


def test_directory_nn_methods_prefer_staging_area_over_country():
    """Verify directory nn methods prefer staging area over country.

    Returns:
        None. Verifies directory nn methods prefer staging area over country.
    """
    directory = _make_directory_stub()

    assert directory.getBiobankNN("bbmri-eric:ID:EXT_demo") == "EXT"
    assert directory.getBiobankCountry("bbmri-eric:ID:EXT_demo") == "US"
    assert directory.getCollectionNN("bbmri-eric:ID:EXT_demo:collection:col5") == "EXT"
    assert directory.getCollectionCountry("bbmri-eric:ID:EXT_demo:collection:col5") == "US"
    assert directory.getContactNN("bbmri-eric:contactID:EXT_demo:main") == "EXT"
    assert directory.getContactCountry("bbmri-eric:contactID:EXT_demo:main") == "US"
    assert directory.getNetworkNN("bbmri-eric:networkID:EXT_demo:net1") == "EXT"
    assert directory.getNetworkCountry("bbmri-eric:networkID:EXT_demo:net1") == "US"
