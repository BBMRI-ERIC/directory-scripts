"""Pin commit ancestry, source-content matching and uncertainty aggregation."""

import pytest
from hypothesis import given, strategies as st

MODEL_CSV = "tableName,columnName,columnType,refSchema,refTable\nCollections,type,ontology_array,DirectoryOntologies,ExampleTypes\n"
ONTOLOGY_CSV = "tableName,columnName,columnType,refSchema,refTable\nExampleTypes,name,string,,\nExampleTypes,parent,ref,,Parents\nParents,name,string,,\n"


@given(st.lists(st.text(alphabet="abcdefghijklmnopqrstuvwxyz ,_-", min_size=1, max_size=20),
                min_size=1, max_size=15, unique=True))
def test_vocabulary_hash_preserves_order_and_runtime_invariance(names):
    """Check stable business-content hashing over varied term identities.

    Args:
        names: Generated unique term names including whitespace and punctuation.

    Returns:
        None. Row order/runtime fields have no effect; a business change does.
    """
    from directory_versions import vocabulary_content_hash
    original = [{"name": name, "definition": "Term"} for name in names]
    reordered = [{**row, "mg_insertedBy": "runtime", "order": index}
                 for index, row in enumerate(reversed(original))]
    assert vocabulary_content_hash(original) == vocabulary_content_hash(reordered)
    reordered[0]["definition"] = "Changed term"
    assert vocabulary_content_hash(original) != vocabulary_content_hash(reordered)


@pytest.fixture
def comparable_snapshot(monkeypatch):
    """Supply independently reproducible source/model contents without HTTP.

    Args:
        monkeypatch: Patch manager replacing only GitHub file reads.

    Returns:
        Metadata envelope and mutable upstream source-file dictionary.
    """
    from directory_versions import DirectoryVersionSources
    from vocabulary_sources import parse_model_csv
    files = {"data/biobank-directory/molgenis.csv": MODEL_CSV,
             "data/biobank-directory/ontologies/molgenis.csv": ONTOLOGY_CSV,
             "data/biobank-directory/ontologies/ExampleTypes.csv": "name,definition,custom\nA,Term,x\n",
             "data/biobank-directory/ontologies/Parents.csv": "name,definition\nP,Parent\n"}
    monkeypatch.setattr(DirectoryVersionSources, "file", lambda self, revision, path: files[path])
    model = parse_model_csv(MODEL_CSV)
    ontology_model = parse_model_csv(ONTOLOGY_CSV)
    for metadata in (model, ontology_model):
        for table in metadata["tables"]:
            for column in table["columns"]:
                for key, default in (("required", False), ("key", None),
                                     ("refSchemaName", None), ("refTableName", None), ("refBackId", None)):
                    column.setdefault(key, default)
    return {"target": "https://example.test", "schema": "ERIC", "channel": "cache",
            "retrieved_at": "2026-11-10T00:00:00+00:00", "complete": True,
            "server_manifest": {"SpecificationVersion": "v13.209.1", "ImplementationVersion": "a" * 40},
            "schema_metadata": model,
            "ontology_schema_metadata": ontology_model,
            "resolved_ontology_tables": ["ExampleTypes", "Parents"],
            "ontologies": {"ExampleTypes": [{"name": "A", "definition": "Term", "custom": "x"}],
                           "Parents": [{"name": "P", "definition": "Parent"}]}}, files


def test_equal_contents_need_no_history_tip(comparable_snapshot, tmp_path, monkeypatch):
    """Compare a complete unchanged model without any moving-tip requests.

    Args:
        comparable_snapshot: Metadata/source fixture with identical business contents.
        tmp_path: Per-test upstream cache directory.
        monkeypatch: Patch manager rejecting unwanted GitHub API lookups.

    Returns:
        None. Equality is qualified as content evidence, not an installed model SHA.
    """
    from directory_versions import DirectoryVersionSources, compare_version_report
    snapshot, _ = comparable_snapshot
    remote = []
    monkeypatch.setattr(DirectoryVersionSources, "json", lambda *args, **kwargs: remote.append(args))
    report = compare_version_report(snapshot, "a" * 40, "b" * 40, source_cache_dir=tmp_path)
    assert report["complete"]
    assert report["model_overall"]["status"] == "equal"
    assert report["comparisons"]["software"]["status"] == "equal"
    assert report["model"]["reported_commit"] is None
    assert not remote


def test_mixed_independent_migrations(comparable_snapshot, monkeypatch, tmp_path):
    """Keep an older schema and newer vocabulary distinct from the binary.

    Args:
        comparable_snapshot: Mutable snapshot whose components start at the baseline.
        monkeypatch: Patch manager providing a synthetic complete history.
        tmp_path: Per-test source cache path.

    Returns:
        None. The aggregate model state is mixed, not the software direction.
    """
    from directory_versions import DirectoryVersionSources, compare_version_report
    snapshot, _ = comparable_snapshot
    snapshot["schema_metadata"]["tables"][0]["columns"][0]["required"] = "true"
    snapshot["ontologies"]["ExampleTypes"][0]["custom"] = "new"
    monkeypatch.setattr(DirectoryVersionSources, "file_history", lambda self, path, tip, limit: ([
        {"revision": "1" * 40, "text": MODEL_CSV.replace("columnType,", "columnType,required,").replace("ontology_array,", "ontology_array,true,")}
        if path.endswith("directory/molgenis.csv") else
        {"revision": "3" * 40, "text": "name,definition,custom\nA,Term,new\n"}
    ], True))
    monkeypatch.setattr(DirectoryVersionSources, "order", lambda self, expected, observed:
                        "equal" if expected == observed else "older" if observed.startswith("1") else "newer")
    report = compare_version_report(snapshot, "a" * 40, "b" * 40, history_tip="d" * 40, source_cache_dir=tmp_path)
    assert report["comparisons"]["schema"]["status"] == "older"
    assert report["comparisons"]["vocabularies"]["ExampleTypes"]["status"] == "newer"
    assert report["model_overall"]["status"] == "mixed"
    assert report["comparisons"]["software"]["status"] == "equal"


def test_explicit_subset_cannot_claim_whole_model_equal(comparable_snapshot, tmp_path):
    """Label deliberately narrowed coverage separately from its scoped result.

    Args:
        comparable_snapshot: Complete fixture used with an explicit scope override.
        tmp_path: Per-test source cache directory.

    Returns:
        None. A valid scoped equal result cannot become global model equality.
    """
    from directory_versions import compare_version_report
    snapshot, _ = comparable_snapshot
    report = compare_version_report(snapshot, "a" * 40, "b" * 40, source_cache_dir=tmp_path, scope_complete=False)
    assert report["model_overall"]["status"] == "unknown"
    assert report["model_overall"]["scoped_status"] == "equal"
    assert not report["complete"]


def test_missing_binary_commit_does_not_disable_model(comparable_snapshot, tmp_path):
    """Keep usable model evidence when the manifest does not identify a binary.

    Args:
        comparable_snapshot: Model fixture with removable manifest identity.
        tmp_path: Per-test source cache path.

    Returns:
        None. Software remains unknown while schema/vocabularies can compare equal.
    """
    from directory_versions import compare_version_report
    snapshot, _ = comparable_snapshot
    snapshot["server_manifest"] = {}
    report = compare_version_report(snapshot, "a" * 40, "b" * 40, source_cache_dir=tmp_path)
    assert report["comparisons"]["software"]["status"] == "unknown"
    assert report["model_overall"]["status"] == "equal"
    assert not report["complete"]


def test_release_without_commit_is_partial_version_evidence(comparable_snapshot):
    """Preserve a release without claiming its software commit is known.

    Args:
        comparable_snapshot: Complete observed schema and vocabulary fixture.

    Returns:
        None. Removing only the software SHA makes version evidence incomplete.
    """
    from directory_versions import version_report
    snapshot, _ = comparable_snapshot
    assert version_report(snapshot)["complete"]
    snapshot["server_manifest"].pop("ImplementationVersion")
    report = version_report(snapshot)
    assert report["software"]["release"] == "v13.209.1"
    assert report["software"]["reported_commit"] is None
    assert not report["complete"]


def test_source_cache_offline_and_moving_refresh(monkeypatch, tmp_path):
    """Never confuse a refreshed lookup time with a commit's own timestamp.

    Args:
        monkeypatch: Patch manager replacing HTTP with a source response spy.
        tmp_path: Dedicated test cache, containing no Directory credentials.

    Returns:
        None. Offline uses original verified bytes, while live refresh updates the tip.
    """
    import json
    from unittest.mock import MagicMock
    from directory_versions import DirectoryVersionSources
    from vocabulary_sources import requests
    response = MagicMock()
    response.content = json.dumps({"sha": "a" * 40}).encode()
    network = MagicMock(return_value=response)
    monkeypatch.setattr(requests, "get", network)
    source = DirectoryVersionSources(tmp_path)
    assert source.resolve("master", moving=True, refresh=True) == "a" * 40
    network.reset_mock()
    offline = DirectoryVersionSources(tmp_path, offline=True)
    assert offline.resolve("master", moving=True, refresh=True) == "a" * 40
    network.assert_not_called()
    response.content = json.dumps({"sha": "b" * 40}).encode()
    assert source.resolve("master", moving=True, refresh=True) == "b" * 40
    assert "auth" not in network.call_args.kwargs
    assert "Authorization" not in network.call_args.kwargs["headers"]


def test_rename_history_covers_previous_path(monkeypatch, tmp_path):
    """Follow a rename into its parent history before claiming source coverage.

    Args:
        monkeypatch: Patch manager substituting controlled GitHub response documents.
        tmp_path: Per-test cache directory.

    Returns:
        None. Versions from both current and former paths are retained once.
    """
    from directory_versions import DirectoryVersionSources
    source = DirectoryVersionSources(tmp_path)
    responses = {
        "/commits?sha=" + "c" * 40 + "&path=new.csv&per_page=100&page=1": [{"sha": "b" * 40}],
        "/commits/" + "b" * 40 + "?per_page=100&page=1": {"files": [{"filename": "new.csv", "previous_filename": "old.csv", "status": "renamed"}], "parents": [{"sha": "a" * 40}]},
        "/commits?sha=" + "a" * 40 + "&path=old.csv&per_page=100&page=1": [{"sha": "a" * 40}],
        "/commits/" + "a" * 40 + "?per_page=100&page=1": {"files": [{"filename": "old.csv", "status": "added"}], "parents": []},
    }
    monkeypatch.setattr(source, "json", lambda path: responses[path])
    monkeypatch.setattr(source, "file", lambda revision, path: path)
    versions, complete = source.file_history("new.csv", "c" * 40, 100)
    assert complete
    assert [item["path"] for item in versions] == ["new.csv", "old.csv"]


def test_typed_numbers_and_inverse_edges_are_not_false_changes():
    """Normalize declared numeric properties and exclude derived inverse references.

    Returns:
        None. Source lexical formatting and API-generated children are not migrations.
    """
    from directory_versions import vocabulary_content_hash
    types = {"n": "INT", "children": "REFBACK"}
    assert vocabulary_content_hash([{"name": "A", "n": "1.0"}], types) == vocabulary_content_hash(
        [{"name": "A", "n": 1, "children": [{"name": "B"}]}], types)


def test_reference_arrays_use_emx2_csv_quoting_not_naive_splitting():
    """Preserve commas inside identifiers using the client's nested CSV format.

    Returns:
        None. API lists and CSV values agree without merging distinct identities
        or parsing a scalar's JSON-looking text as an array.
    """
    from directory_versions import vocabulary_content_hash
    types = {"parent": "REF_ARRAY"}
    source = [{"name": "A", "parent": '"B,C",D'}]
    live = [{"name": "A", "parent": [{"name": "D"}, {"name": "B,C"}]}]
    assert vocabulary_content_hash(source, types) == vocabulary_content_hash(live, types)
    assert vocabulary_content_hash(source, types) != vocabulary_content_hash([{"name": "A", "parent": "B,C,D"}], types)
    assert vocabulary_content_hash([{"name": "A", "definition": '["X"]'}]) != vocabulary_content_hash(
        [{"name": "A", "definition": "X"}])


def test_history_pagination_and_cap(monkeypatch, tmp_path):
    """Require the terminating history page before reporting complete coverage.

    Args:
        monkeypatch: Patch manager supplying exactly one full API page.
        tmp_path: Isolated source cache directory.

    Returns:
        None. A full page needs continuation and a capped scan remains incomplete.
    """
    from directory_versions import DirectoryVersionSources
    source = DirectoryVersionSources(tmp_path)
    pages = []

    def response(path):
        """Supply history pages and minimal unchanged file details.

        Args:
            path: Internal GitHub API path requested by the source walker.

        Returns:
            A complete page, terminal empty page, or valid commit file evidence.
        """
        if path.startswith("/commits?"):
            pages.append(path)
            return [{"sha": f"{index:040x}"} for index in range(100)] if path.endswith("page=1") else []
        return {"files": [{"filename": "file.csv", "status": "modified"}], "parents": []}

    monkeypatch.setattr(source, "json", response)
    monkeypatch.setattr(source, "file", lambda revision, path: "content")
    versions, complete = source.file_history("file.csv", "a" * 40, 101)
    assert len(versions) == 100 and complete
    assert len(pages) == 2
    assert source.file_history("file.csv", "a" * 40, 5)[1] is False


def test_unavailable_one_component_preserves_other_evidence(comparable_snapshot, monkeypatch, tmp_path):
    """Keep supported reference comparisons active when one source file is absent.

    Args:
        comparable_snapshot: Model/source fixture with two reference vocabularies.
        monkeypatch: Patch manager replacing the missing upstream file read.
        tmp_path: Per-test source cache directory.

    Returns:
        None. The failed vocabulary remains unknown without disabling its sibling.
    """
    from directory_versions import DirectoryVersionSources, compare_version_report
    snapshot, files = comparable_snapshot

    def read_file(self, revision, path):
        """Fail the selected source without returning an invented empty table.

        Args:
            self: Configured upstream source reader.
            revision: Requested immutable source identity.
            path: Model or vocabulary path being retrieved.

        Returns:
            Existing fixture text for independently available components.

        Raises:
            RuntimeError: If the requested vocabulary file is unavailable.
        """
        if path.endswith("ExampleTypes.csv"):
            raise RuntimeError("Source unavailable")
        return files[path]

    monkeypatch.setattr(DirectoryVersionSources, "file", read_file)
    report = compare_version_report(snapshot, "a" * 40, "b" * 40, source_cache_dir=tmp_path)
    assert report["comparisons"]["vocabularies"]["ExampleTypes"]["status"] == "unknown"
    assert report["comparisons"]["vocabularies"]["Parents"]["status"] == "equal"
    assert report["model_overall"]["status"] == "unknown"


def test_short_sha_resolution_and_malformed_order_fail_closed(monkeypatch, tmp_path):
    """Resolve reported abbreviations, rejecting inconsistent or malformed evidence.

    Args:
        monkeypatch: Patch manager substituting GitHub JSON documents.
        tmp_path: Dedicated source cache path.

    Returns:
        None. A short SHA is never accepted by prefix coincidence without resolution.
    """
    from directory_versions import DirectoryVersionSources
    source = DirectoryVersionSources(tmp_path)
    monkeypatch.setattr(source, "json", lambda path, **kwargs: {"sha": "a" * 40})
    assert source.resolve("a" * 9) == "a" * 40
    with pytest.raises(ValueError, match="identity"):
        source.resolve("b" * 9)
    monkeypatch.setattr(source, "json", lambda path, **kwargs: {"status": "ahead", "base_commit": None})
    with pytest.raises(RuntimeError, match="comparison"):
        source.order("a" * 40, "b" * 40)


def test_rate_limits_leave_independent_model_comparison_available(comparable_snapshot, monkeypatch, tmp_path):
    """Convert source-access failures into component diagnostics without false order.

    Args:
        comparable_snapshot: Valid observed model and vocabulary evidence.
        monkeypatch: Patch manager simulating unavailable GitHub source access.
        tmp_path: Dedicated upstream cache location.

    Returns:
        None. Software unavailability leaves usable model comparisons unchanged.
    """
    from directory_versions import DirectoryVersionSources, compare_version_report
    snapshot, _ = comparable_snapshot
    snapshot["server_manifest"]["ImplementationVersion"] = "c" * 9

    def unavailable(*args, **kwargs):
        """Simulate API limits or unreadable cached lookup evidence.

        Args:
            *args: Source reader and requested GitHub path.
            **kwargs: Request refresh policy, unused by this failure simulation.

        Returns:
            None; this simulated source never returns normally, because the
            failure is intentional test input.

        Raises:
            RuntimeError: Always, representing a GitHub rate limit.
        """
        raise RuntimeError("GitHub rate limit")

    monkeypatch.setattr(DirectoryVersionSources, "json", unavailable)
    report = compare_version_report(snapshot, "a" * 40, "b" * 40, source_cache_dir=tmp_path)
    assert report["comparisons"]["software"]["status"] == "unknown"
    assert "rate limit" in report["comparisons"]["software"]["diagnostic"]
    assert report["model_overall"]["status"] == "equal"


def test_corrupt_offline_source_cache_does_not_trigger_http(monkeypatch, tmp_path):
    """Reject altered source evidence without silently fetching replacement data.

    Args:
        monkeypatch: Test patch manager installing an HTTP request spy.
        tmp_path: Isolated cache containing one intentionally corrupted envelope.

    Returns:
        None. Integrity failure remains explicit and offline mode performs no HTTP.
    """
    import hashlib
    import json
    from unittest.mock import MagicMock
    from directory_versions import API, DirectoryVersionSources
    from vocabulary_sources import requests
    url = API + "/commits/" + "a" * 9
    path = tmp_path / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    path.write_text(json.dumps({"url": url, "text": "altered", "sha256": "0" * 64}))
    network = MagicMock()
    monkeypatch.setattr(requests, "get", network)
    with pytest.raises(RuntimeError, match="integrity"):
        DirectoryVersionSources(tmp_path, offline=True).resolve("a" * 9)
    network.assert_not_called()


@pytest.mark.parametrize("states,expected", [
    (["equal", "equal"], "equal"), (["older", "equal"], "older"),
    (["newer", "equal"], "newer"), (["older", "newer"], "mixed"),
    (["equal", "unknown"], "unknown"), (["diverged", "equal"], "diverged"),
    ([], "unknown"),
])
def test_aggregate_version_states(states, expected):
    """Require complete, consistent evidence before one aggregate direction.

    Args:
        states: Component comparison statuses, including unavailable evidence.
        expected: Conservative combined status required by the API contract.

    Returns:
        None. Mixed independent migrations and unavailable evidence stay explicit.
    """
    from directory_versions import aggregate_status
    assert aggregate_status(states) == expected


def test_vocabulary_contents_include_custom_fields_and_ignore_order():
    """Compare every supported business property rather than only known meanings.

    Returns:
        None. Runtime metadata and row/display order are ignored, not custom fields.
    """
    from directory_versions import vocabulary_content_hash
    left = [{"name": "A", "custom": "value", "order": "1"}, {"name": "B"}]
    right = [{"name": "B", "mg_insertedOn": "today"}, {"name": "A", "custom": "value", "order": 2}]
    assert vocabulary_content_hash(left) == vocabulary_content_hash(right)
    right[1]["custom"] = "different"
    assert vocabulary_content_hash(left) != vocabulary_content_hash(right)
    with pytest.raises(ValueError, match="duplicate"):
        vocabulary_content_hash([{"name": "A"}, {"name": "A"}])


def test_empty_trailing_csv_cells_do_not_hide_populated_extra_fields():
    """Accept upstream CSV padding but reject unlabelled nonempty properties.

    Returns:
        None. ServiceCategories-style empty padding preserves every named value.
    """
    from vocabulary_sources import parse_vocabulary_csv
    assert parse_vocabulary_csv("name,label\nA,Alpha,,\n") == [{"name": "A", "label": "Alpha"}]
    with pytest.raises(ValueError, match="extra"):
        parse_vocabulary_csv("name,label\nA,Alpha,hidden\n")


@pytest.mark.parametrize("remote,status", [("ahead", "newer"), ("behind", "older"), ("identical", "equal"), ("diverged", "diverged")])
def test_software_order_uses_ancestry(monkeypatch, tmp_path, remote, status):
    """Use GitHub base/head ancestry without sorting hashes or commit dates.

    Args:
        monkeypatch: Patch manager replacing immutable GitHub response reads.
        tmp_path: Per-test source cache path.
        remote: GitHub comparison status for expected base versus observed head.
        status: Corresponding public API comparison direction.

    Returns:
        None. Expected and observed order is checked independently of SHA spelling.
    """
    from directory_versions import DirectoryVersionSources
    source = DirectoryVersionSources(tmp_path)
    monkeypatch.setattr(source, "json", lambda path, **kwargs: {
        "status": remote, "base_commit": {"sha": "b" * 40},
        "url": f"https://api.github.com/repos/molgenis/molgenis-emx2/compare/{'b' * 40}...{'a' * 40}"})
    result = source.order("b" * 40, "a" * 40)
    assert result == status


def test_ancestry_rejects_wrong_head_identity(monkeypatch, tmp_path):
    """Reject a plausible ancestry status returned for another observed commit.

    Args:
        monkeypatch: Patch manager returning a wrong-head comparison document.
        tmp_path: Isolated upstream cache path.

    Returns:
        None. A valid base cannot compensate for an unrelated head identity.
    """
    from directory_versions import DirectoryVersionSources
    source = DirectoryVersionSources(tmp_path)
    monkeypatch.setattr(source, "json", lambda path: {
        "status": "ahead", "base_commit": {"sha": "b" * 40},
        "url": f"https://api.github.com/repos/molgenis/molgenis-emx2/compare/{'b' * 40}...{'c' * 40}"})
    with pytest.raises(RuntimeError, match="ancestry"):
        source.order("b" * 40, "a" * 40)


@pytest.mark.parametrize("field", ["required", "columnType", "key", "refTableName"])
def test_missing_observed_model_property_is_not_equal(comparable_snapshot, tmp_path, field):
    """Keep omitted assessed metadata distinct from an explicitly observed default.

    Args:
        comparable_snapshot: Fully evidenced model/source fixture.
        tmp_path: Isolated upstream source cache.
        field: Assessed property removed from the observed reference column.

    Returns:
        None. Incomplete observed schema stays unknown while vocabularies compare.
    """
    from directory_versions import compare_version_report
    snapshot, _ = comparable_snapshot
    snapshot["schema_metadata"]["tables"][0]["columns"][0].pop(field)
    report = compare_version_report(snapshot, "a" * 40, "b" * 40, source_cache_dir=tmp_path)
    assert report["comparisons"]["schema"]["status"] == "unknown"
    assert field in " ".join(report["model"]["missing_properties"])
    assert report["comparisons"]["vocabularies"]["ExampleTypes"]["status"] == "equal"
    assert not report["complete"]


def test_reversions_and_history_limits_remain_unknown(monkeypatch, tmp_path):
    """Keep ambiguous repeated contents and incomplete scans out of version ordering.

    Args:
        monkeypatch: Patch manager replacing source-history retrieval.
        tmp_path: Per-test cache directory.

    Returns:
        None. History must be complete and point in one direction to imply order.
    """
    from directory_versions import DirectoryVersionSources
    source = DirectoryVersionSources(tmp_path)
    monkeypatch.setattr(source, "file_history", lambda *args: ([
        {"revision": "a" * 40, "text": "observed"},
        {"revision": "c" * 40, "text": "observed"},
    ], True))
    monkeypatch.setattr(source, "order", lambda expected, actual: "older" if actual.startswith("a") else "newer")
    result = source.match_content("path.csv", "b" * 40, "d" * 40, "observed", lambda text: text, 100)
    assert result["status"] == "unknown"
    assert len(result["candidates"]) == 2
    monkeypatch.setattr(source, "file_history", lambda *args: ([{"revision": "a" * 40, "text": "observed"}], False))
    assert source.match_content("path.csv", "b" * 40, "d" * 40, "observed", lambda text: text, 1)["status"] == "unknown"
