"""Verify metadata-only reads, isolated caching and offline compatibility."""

import copy

import pandas as pd
import pytest

import directory


class MetadataClient:
    """Spy client rejecting entity reads and recording authentication order.

    Attributes:
        calls: Ordered transport operations performed by all instances.
        fail: Whether construction simulates an unavailable server.
    """

    calls = []
    fail = False

    def __init__(self, url, **kwargs):
        """Record a target and simulate the minimal supported client surface.

        Args:
            url: Directory target being contacted.
            **kwargs: Optional token configuration passed to the shared client.
        """
        if self.fail:
            raise ConnectionError("offline")
        self.calls.append(("connect", url))
        self.url = url
        self.session = self

    def __enter__(self):
        """Return the active metadata-only test client.

        Returns:
            This client instance.
        """
        return self

    def __exit__(self, *args):
        """End the test session without suppressing errors.

        Args:
            *args: Exception details supplied by the context manager protocol.

        Returns:
            None.
        """

    def signin(self, username, password):
        """Record explicit credentials without retaining their values.

        Args:
            username: Test account identifier.
            password: Test credential, deliberately not recorded.

        Returns:
            None.
        """
        self.calls.append(("signin",))

    def set_schema(self, schema):
        """Record schema selection after authentication.

        Args:
            schema: Requested Directory schema name.

        Returns:
            None.
        """
        self.calls.append(("schema", schema))

    def post(self, url, *, json, timeout):
        """Allow only manifest and schema metadata GraphQL queries.

        Args:
            url: Exact endpoint selected by metadata access.
            json: GraphQL request object whose operation is checked.
            timeout: Bounded request timeout in seconds.

        Returns:
            Response-like object exposing the allowed response document.
        """
        query = json["query"]
        assert "mutation" not in query.lower()
        if "_manifest" in query:
            self.payload = {"data": {"_manifest": {
                "SpecificationVersion": "v13.209.1", "ImplementationVersion": "a" * 40,
                "DatabaseVersion": "36",
            }}}
        else:
            assert "_schema" in query
            self.payload = {"data": {"_schema": {
                "name": "ERIC", "tables": [{"name": "Collections", "columns": [{"name": "id"}]}],
            }}}
        self.calls.append(("post", url))
        return self

    def raise_for_status(self):
        """Accept the simulated HTTP status.

        Returns:
            None.
        """

    def json(self):
        """Return an independent response document.

        Returns:
            Copy of the most recent allowed GraphQL response.
        """
        return copy.deepcopy(self.payload)

    def get(self, *, table, as_df):
        """Allow only the explicitly requested reference ontology.

        Args:
            table: Reference table name; entity tables are forbidden.
            as_df: Whether a dataframe rather than response records is requested.

        Returns:
            One reference row with a declared deprecated term.
        """
        assert table == "DataCategories"
        assert as_df
        self.calls.append(("ontology", table))
        return pd.DataFrame([{"name": "IMAGING_DATA", "definition": "Deprecated value."}])


@pytest.fixture
def metadata_client(monkeypatch, tmp_path):
    """Install a transport spy and isolate the metadata cache.

    Args:
        monkeypatch: Pytest patch manager replacing network access and cache root.
        tmp_path: Temporary directory used for every cache written by this test.

    Returns:
        Spy client class with reset call history and failure mode.
    """
    MetadataClient.calls = []
    MetadataClient.fail = False
    monkeypatch.setattr(directory, "Client", MetadataClient)
    monkeypatch.setenv("DIRECTORY_CACHE_ROOT", str(tmp_path))
    return MetadataClient


def test_snapshot_is_metadata_only_and_cache_first(metadata_client):
    """Read metadata/reference tables without constructing entity graphs.

    Args:
        metadata_client: Installed spy client proving the read allowlist.

    Returns:
        None.
    """
    first = directory.get_directory_metadata_snapshot(ontology_tables=("DataCategories",))
    assert first["channel"] == "live"
    assert "readonly" not in first["schema_metadata"]["tables"][0]["columns"][0]
    calls = len(metadata_client.calls)
    second = directory.get_directory_metadata_snapshot(ontology_tables=("DataCategories",))
    assert second["channel"] == "cache"
    assert first["retrieved_at"] == second["retrieved_at"]
    assert len(metadata_client.calls) == calls
    assert second["ontologies"]["DataCategories"][0]["name"] == "IMAGING_DATA"


def test_offline_never_connects_and_targets_are_isolated(metadata_client):
    """Fail safely for absent target-specific cache without touching the network.

    Args:
        metadata_client: Transport spy whose call count must remain unchanged.

    Returns:
        None.
    """
    directory.get_directory_metadata_snapshot(directory_url="https://one.test")
    calls = len(metadata_client.calls)
    assert directory.get_directory_metadata_snapshot(directory_url="https://one.test", offline=True)["channel"] == "cache"
    with pytest.raises(RuntimeError, match="cached"):
        directory.get_directory_metadata_snapshot(directory_url="https://two.test", offline=True)
    assert len(metadata_client.calls) == calls


def test_refresh_failure_preserves_cached_snapshot(metadata_client):
    """Keep explicit fallback provenance without purging entity caches.

    Args:
        metadata_client: Spy configured to fail after a successful initial read.

    Returns:
        None.
    """
    first = directory.get_directory_metadata_snapshot()
    metadata_client.fail = True
    fallback = directory.get_directory_metadata_snapshot(refresh=True)
    assert fallback["channel"] == "cache_fallback"
    assert fallback["retrieved_at"] == first["retrieved_at"]
    assert "offline" in fallback["refresh_error"]


def test_private_schema_authenticates_before_selection(metadata_client):
    """Reject missing credentials and avoid selecting a private schema too early.

    Args:
        metadata_client: Spy recording session setup order.

    Returns:
        None.
    """
    with pytest.raises(ValueError, match="credentials"):
        directory.get_directory_metadata_snapshot(schema="BBMRI-CZ")
    assert not metadata_client.calls
    directory.get_directory_metadata_snapshot(schema="BBMRI-CZ", username="user", password="secret")
    assert metadata_client.calls.index(("signin",)) < metadata_client.calls.index(("schema", "BBMRI-CZ"))


def test_token_remains_a_valid_alternative_to_incomplete_account_defaults(metadata_client):
    """Do not disable token authentication because an unused username is configured.

    Args:
        metadata_client: Spy recording whether account sign-in was attempted.

    Returns:
        None.
    """
    result = directory.get_directory_metadata_snapshot(schema="BBMRI-CZ", token="test-token",
                                                        username="unused-default", password=None)
    assert result["schema"] == "BBMRI-CZ"
    assert ("signin",) not in metadata_client.calls


def test_entity_table_is_not_allowed(metadata_client):
    """Reject a request to turn the metadata API into an entity reader.

    Args:
        metadata_client: Spy proving rejection happens before any remote call.

    Returns:
        None.
    """
    with pytest.raises(ValueError, match="reference"):
        directory.get_directory_metadata_snapshot(ontology_tables=("Biobanks",))
    assert not metadata_client.calls


def test_unavailable_reference_does_not_disable_other_tables(metadata_client, monkeypatch):
    """Keep dataset checking possible when a service reference is unavailable.

    Args:
        metadata_client: Installed spy returning the available dataset reference.
        monkeypatch: Pytest manager injecting an absent optional service table.

    Returns:
        None.
    """
    original = metadata_client.get

    def get(self, *, table, as_df):
        """Expose one absent reference without failing the successful sibling read.

        Args:
            self: Active spy client instance performing the read.
            table: Reference vocabulary selected by the caller.
            as_df: Whether the result must be a pandas dataframe.

        Returns:
            Available dataset dataframe; service requests raise a table error.
        """
        if table == "ServiceTypes":
            raise RuntimeError("No ServiceTypes table")
        return original(self, table=table, as_df=as_df)

    monkeypatch.setattr(metadata_client, "get", get)
    result = directory.get_directory_metadata_snapshot(ontology_tables=("DataCategories", "ServiceTypes"))
    assert "DataCategories" in result["ontologies"]
    assert "ServiceTypes" in result["reference_errors"]


def test_manifest_remains_available_when_schema_query_is_unsupported(metadata_client, monkeypatch):
    """Report old software even when its schema API lacks requested metadata fields.

    Args:
        metadata_client: Spy exposing independent schema and server endpoints.
        monkeypatch: Pytest patch manager injecting only schema-query incompatibility.

    Returns:
        None.
    """
    original = directory._metadata_graphql

    def query(session, endpoint, graphql):
        """Simulate an older server with a supported manifest but unsupported schema.

        Args:
            session: Open metadata-only spy client.
            endpoint: Target metadata endpoint selected by the caller.
            graphql: Internal GraphQL query to route independently.

        Returns:
            Older software manifest; schema requests raise a compatibility error.
        """
        if "_schema" in graphql:
            raise RuntimeError("unsupported schema query")
        data = original(session, endpoint, graphql)
        data["_manifest"]["SpecificationVersion"] = "v13.100.0"
        return data

    monkeypatch.setattr(directory, "_metadata_graphql", query)
    result = directory.get_directory_metadata_snapshot(ontology_tables=("DataCategories",))
    assert result["server_manifest"]["SpecificationVersion"] == "v13.100.0"
    assert "unsupported" in result["schema_error"]
    assert "DataCategories" in result["ontologies"]


def test_partial_refresh_preserves_last_complete_offline_reference(metadata_client, monkeypatch):
    """Do not replace a usable reference envelope with a transient partial fetch.

    Args:
        metadata_client: Spy client initially exposing both requested vocabularies.
        monkeypatch: Pytest manager removing the service table only on refresh.

    Returns:
        None.
    """
    original = metadata_client.get

    def get(self, *, table, as_df):
        """Provide a complete first reference snapshot for the cache.

        Args:
            self: Active metadata spy client instance.
            table: One of the requested reference vocabularies.
            as_df: Whether the caller requests dataframe output.

        Returns:
            Synthetic service terms or the original dataset dataframe.
        """
        if table == "ServiceTypes":
            return pd.DataFrame([{"name": "Service", "definition": "Available service"}])
        return original(self, table=table, as_df=as_df)

    monkeypatch.setattr(metadata_client, "get", get)
    first = directory.get_directory_metadata_snapshot(ontology_tables=("DataCategories", "ServiceTypes"))

    def partial(self, *, table, as_df):
        """Fail only the previously available service reference during refresh.

        Args:
            self: Active metadata spy client instance.
            table: Reference table selected by the refresh.
            as_df: Whether the requested result is a dataframe.

        Returns:
            Dataset dataframe; ServiceTypes raises a simulated transient failure.
        """
        if table == "ServiceTypes":
            raise RuntimeError("temporary service reference failure")
        return original(self, table=table, as_df=as_df)

    monkeypatch.setattr(metadata_client, "get", partial)
    refreshed = directory.get_directory_metadata_snapshot(ontology_tables=("DataCategories", "ServiceTypes"), refresh=True)
    assert refreshed["channel"] == "cache_fallback"
    assert refreshed["retrieved_at"] == first["retrieved_at"]
    offline = directory.get_directory_metadata_snapshot(ontology_tables=("DataCategories", "ServiceTypes"), offline=True)
    assert offline["ontologies"]["ServiceTypes"] == first["ontologies"]["ServiceTypes"]


def test_corrupted_metadata_cache_is_not_used_as_verified_evidence(metadata_client, tmp_path):
    """Reject changed cached definitions when their recorded fingerprints no longer agree.

    Args:
        metadata_client: Spy proving that offline rejection does not contact the server.
        tmp_path: Isolated metadata-cache root established by the fixture.

    Returns:
        None.
    """
    from diskcache import Cache
    directory.get_directory_metadata_snapshot(ontology_tables=("DataCategories",))
    with Cache(str(tmp_path / "data-check-cache" / "directory-metadata-v1")) as cache:
        for key in cache.iterkeys():
            if str(key).startswith("manifest:"):
                continue
            record = cache[key]
            record["ontologies"]["DataCategories"][0]["definition"] = "Changed without updating its fingerprint"
            cache[key] = record
    calls = len(metadata_client.calls)
    with pytest.raises(RuntimeError, match="cached"):
        directory.get_directory_metadata_snapshot(ontology_tables=("DataCategories",), offline=True)
    assert len(metadata_client.calls) == calls
