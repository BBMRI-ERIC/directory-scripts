"""Verify version inspection discovers vocabularies without reading entity data."""

import copy
from unittest.mock import MagicMock

import pandas as pd
import pytest

import directory


@pytest.fixture
def version_client(monkeypatch, tmp_path):
    """Provide metadata and vocabulary-only transport with isolated caches.

    Args:
        monkeypatch: Test patch manager replacing the Directory client/transport.
        tmp_path: Per-test cache directory.

    Returns:
        Client mock, context-managed session, and mutable response documents.
    """
    documents = {
        "model": {"name": "ERIC", "tables": [{"name": "Collections", "columns": [
            {"name": "type", "columnType": "ONTOLOGY_ARRAY", "refSchemaName": "DirectoryOntologies", "refTableName": "ExampleTypes"},
        ]}]},
        "ontologies": {"name": "DirectoryOntologies", "tables": [
            {"name": "ExampleTypes", "columns": [{"name": "parent", "refTableName": "Parents"}]},
            {"name": "Parents", "columns": [{"name": "parent", "refTableName": "Parents"}]},
        ]},
        "manifest": {"SpecificationVersion": "v13.209.1", "ImplementationVersion": "a" * 40},
    }
    client = MagicMock()
    session = client.return_value.__enter__.return_value
    session.get.side_effect = lambda *, table, as_df: pd.DataFrame([{"name": table, "definition": "Term"}])
    monkeypatch.setattr(directory, "Client", client)
    monkeypatch.setattr(directory, "_metadata_graphql", lambda session, endpoint, query:
        {"_manifest": copy.deepcopy(documents["manifest"])} if endpoint.endswith("eu/api/graphql")
        else {"_schema": copy.deepcopy(documents["ontologies" if "/DirectoryOntologies/" in endpoint else "model"])})
    monkeypatch.setenv("DIRECTORY_CACHE_ROOT", str(tmp_path))
    return client, session, documents


def test_discovery_includes_transitive_vocabularies(version_client):
    """Discover the reachable ontology graph while excluding entity reads.

    Args:
        version_client: Metadata/reference transport fixture.

    Returns:
        None. Both root and parent vocabularies are read from DirectoryOntologies.
    """
    _, session, _ = version_client
    snapshot = directory.get_directory_metadata_snapshot(ontology_tables=None)
    assert set(snapshot["ontologies"]) == {"ExampleTypes", "Parents"}
    assert snapshot["complete"]
    assert {call.kwargs["table"] for call in session.get.call_args_list} == {"ExampleTypes", "Parents"}
    assert session.set_schema.call_args.args == ("DirectoryOntologies",)


def test_discovery_offline_and_target_isolation(version_client):
    """Reuse original times offline without opening a Directory connection.

    Args:
        version_client: Transport fixture with a countable client constructor.

    Returns:
        None. Cached discovery is independent and unavailable targets fail closed.
    """
    client, _, _ = version_client
    first = directory.get_directory_metadata_snapshot(ontology_tables=None)
    client.reset_mock()
    cached = directory.get_directory_metadata_snapshot(ontology_tables=None, offline=True)
    assert cached["channel"] == "cache"
    assert cached["retrieved_at"] == first["retrieved_at"]
    client.assert_not_called()
    with pytest.raises(RuntimeError, match="cached"):
        directory.get_directory_metadata_snapshot(directory_url="https://other.test", ontology_tables=None, offline=True)


def test_version_report_does_not_invent_model_commit(version_client):
    """Inspect deployment evidence without constructing Directory or guessing commits.

    Args:
        version_client: Metadata/reference transport fixture.

    Returns:
        None. Software provenance and all discovered vocabularies remain explicit.
    """
    report = directory.get_directory_versions()
    assert report["software"]["reported_commit"] == "a" * 40
    assert report["model"]["reported_commit"] is None
    assert set(report["vocabularies"]) == {"ExampleTypes", "Parents"}
    assert report["scope"]["complete"]


def test_dynamic_subset_requires_a_known_reference(version_client):
    """Reject arbitrary ontology reads unless metadata declares their identities.

    Args:
        version_client: Metadata/reference transport fixture.

    Returns:
        None. The unknown table is never passed to the record retrieval API.
    """
    _, session, _ = version_client
    snapshot = directory.get_directory_metadata_snapshot(ontology_tables=("NotDeclared",))
    assert "NotDeclared" in snapshot["reference_errors"]
    session.get.assert_not_called()


def test_private_inspection_authenticates_before_schema_selection(version_client):
    """Keep explicit private-schema credentials separate from returned version data.

    Args:
        version_client: Session spy recording authentication and schema operations.

    Returns:
        None. Inspection authenticates first without retaining secrets in reports.
    """
    import json
    _, session, _ = version_client
    report = directory.get_directory_versions(schema="BBMRI-CZ", username="account", password="private-secret")
    operations = session.method_calls
    assert operations[0][0] == "signin"
    assert operations[1][0] == "set_schema"
    assert report["schema"] == "BBMRI-CZ"
    assert "private-secret" not in json.dumps(report)


def test_discovery_partial_refresh_preserves_complete_cache(version_client):
    """Keep the last usable ontology graph when its refreshed metadata is absent.

    Args:
        version_client: Mutable metadata fixture supporting an incomplete refresh.

    Returns:
        None. A failed discovery refresh cannot overwrite complete prior evidence.
    """
    _, _, documents = version_client
    first = directory.get_directory_metadata_snapshot(ontology_tables=None)
    documents["ontologies"] = {"tables": []}
    refreshed = directory.get_directory_metadata_snapshot(ontology_tables=None, refresh=True)
    assert refreshed["channel"] == "cache_fallback"
    assert refreshed["ontologies"] == first["ontologies"]


def test_complete_discovery_cache_cannot_omit_a_vocabulary(version_client):
    """Reject a truncated cache even when remaining per-table hashes are intact.

    Args:
        version_client: Metadata fixture providing a complete two-vocabulary cache.

    Returns:
        None. A missing term table cannot remain labelled complete offline.
    """
    directory.get_directory_metadata_snapshot(ontology_tables=None)
    with directory.Cache(directory._repo_cache_dir("data-check-cache", "directory-metadata-v1")) as cache:
        for key in list(cache):
            if not str(key).startswith("manifest:"):
                value = cache[key]
                value["ontologies"].pop("Parents")
                cache[key] = value
    with pytest.raises(RuntimeError, match="cached"):
        directory.get_directory_metadata_snapshot(ontology_tables=None, offline=True)


def test_new_reference_failure_preserves_previous_complete_cache(version_client):
    """Retain usable discovery evidence when a newly introduced reference fails.

    Args:
        version_client: Mutable schema/session fixture with an existing full cache.

    Returns:
        None. Refresh and subsequent offline reads retain the previous scope/time.
    """
    _, session, documents = version_client
    first = directory.get_directory_metadata_snapshot(ontology_tables=None)
    documents["model"]["tables"][0]["columns"].append({
        "name": "added", "refSchemaName": "DirectoryOntologies", "refTableName": "NewTerms"})
    documents["ontologies"]["tables"].append({"name": "NewTerms", "columns": []})
    def read_reference(*, table, as_df):
        """Read old references while simulating failure of only the new table.

        Args:
            table: Reference-schema table requested by the metadata loader.
            as_df: Client return-format flag, expected to request a dataframe.

        Returns:
            Existing term rows in dataframe form.

        Raises:
            RuntimeError: When the newly introduced vocabulary is requested.
        """
        if table == "NewTerms":
            raise RuntimeError("Reference temporarily unavailable")
        return pd.DataFrame([{"name": table, "definition": "Term"}])

    session.get.side_effect = read_reference
    refreshed = directory.get_directory_metadata_snapshot(ontology_tables=None, refresh=True)
    assert refreshed["channel"] == "cache_fallback"
    assert refreshed["retrieved_at"] == first["retrieved_at"]
    cached = directory.get_directory_metadata_snapshot(ontology_tables=None, offline=True)
    assert cached["ontologies"] == first["ontologies"]
    assert cached["complete"]


@pytest.mark.parametrize("value", [None, "master", "123", "z" * 40])
def test_bad_expected_commits_fail_before_network(version_client, value):
    """Validate expected identities without triggering Directory/GitHub requests.

    Args:
        version_client: Spy transport fixture proving no client construction.
        value: Unsupported software commit representation.

    Returns:
        None. Invalid user configuration is distinguished from unavailable evidence.
    """
    client, _, _ = version_client
    with pytest.raises(ValueError, match="commit"):
        directory.compare_directory_versions(value, "b" * 40)
    client.assert_not_called()


def test_existing_instance_version_helpers_preserve_target(monkeypatch):
    """Use configured instance context without retaining or exposing credentials.

    Args:
        monkeypatch: Patch manager replacing standalone inspection/orchestration.

    Returns:
        None. Convenience methods forward target/schema and reject overrides.
    """
    instance = object.__new__(directory.Directory)
    instance._Directory__directoryURL = "https://example.test"
    instance._Directory__package = "BBMRI-CZ"
    inspector = MagicMock(return_value={"inspected": True})
    comparator = MagicMock(return_value={"compared": True})
    monkeypatch.setattr(directory, "get_directory_versions", inspector)
    monkeypatch.setattr(directory, "compare_directory_versions", comparator)
    assert instance.getVersions(token="secret") == {"inspected": True}
    assert inspector.call_args.kwargs == {"directory_url": "https://example.test", "schema": "BBMRI-CZ", "token": "secret"}
    assert instance.compareVersions("a" * 40, "b" * 40) == {"compared": True}
    assert comparator.call_args.kwargs["schema"] == "BBMRI-CZ"
    with pytest.raises(ValueError, match="configured"):
        instance.getVersions(directory_url="https://other.test")
    assert not hasattr(instance, "token")
