"""Pin source parsing and history completeness independently of live GitHub."""

import pytest
import json


def test_csv_preserves_deprecated_terms_and_rejects_duplicate_names():
    """Retain original meanings and reject ambiguous source identities.

    Returns:
        None.
    """
    from vocabulary_sources import parse_vocabulary_csv
    rows = parse_vocabulary_csv("name,label,definition\nOLD,Old,Deprecated value\n")
    assert rows[0]["definition"] == "Deprecated value"
    with pytest.raises(ValueError, match="duplicate"):
        parse_vocabulary_csv("name,label\nx,X\nx,Other\n")


def test_miabis_parser_uses_declared_headings_and_columns():
    """Do not silently reinterpret changed upstream table layouts.

    Returns:
        None.
    """
    from vocabulary_sources import parse_miabis_lists
    text = "#### Dataset Type\n| Value Name | Definition | Source [Link] | Attribute Codes |\n| --- | --- | --- | --- |\n| Clinical dataset | Patient data | source | MIABIS-COLLECTION-13 |\n\n#### Service Type\n| Value Name | Definition | Source [Link] | Attribute Codes |\n| --- | --- | --- | --- |\n| Sample storage | Storage | source | MIABIS-SERVICE-07 |\n"
    result = parse_miabis_lists(text)
    assert result["DataCategories"][0]["name"] == "Clinical dataset"
    assert result["ServiceTypes"][0]["attribute_codes"] == "MIABIS-SERVICE-07"
    with pytest.raises(ValueError, match="columns"):
        parse_miabis_lists(text.replace("Value Name", "Meaning"))
    with pytest.raises(ValueError, match="Service Type"):
        parse_miabis_lists(text.split("#### Service Type")[0])


def test_transition_preserves_removal_and_restoration():
    """Keep intermediate changes rather than comparing only endpoint lists.

    Returns:
        None.
    """
    from vocabulary_sources import compare_terms
    initial = [{"name": "Biological samples", "definition": "Samples"}]
    assert compare_terms(initial, [])["removed"] == ["Biological samples"]
    assert compare_terms([], initial)["added"] == ["Biological samples"]
    assert compare_terms(initial, initial)["changed"] == []


def test_offline_missing_source_fails_without_fetching(tmp_path, monkeypatch):
    """An absent pinned cache is an incomplete input, not an empty vocabulary.

    Args:
        tmp_path: Temporary source-cache root.
        monkeypatch: Pytest manager installing a forbidden network operation.

    Returns:
        None.
    """
    import vocabulary_sources

    def forbidden(*args, **kwargs):
        """Fail on network use from an explicitly offline operation.

        Args:
            *args: Positional request arguments, deliberately unused.
            **kwargs: Keyword transport arguments, deliberately unused.

        Returns:
            None; raises immediately on an unexpected request.
        """
        raise AssertionError("offline attempted a request")

    monkeypatch.setattr(vocabulary_sources.requests, "get", forbidden)
    with pytest.raises(RuntimeError, match="cached"):
        vocabulary_sources.load_miabis_reference(revision="a" * 40, cache_dir=tmp_path, offline=True)


def test_model_csv_and_api_metadata_have_same_structural_fingerprint():
    """Compare model structure rather than target-specific labels and identifiers.

    Returns:
        None.
    """
    from vocabulary_sources import parse_model_csv
    from vocabulary_status import model_fingerprint
    csv_model = parse_model_csv("tableName,columnName,columnType,required,refSchema,refTable\nCollections,,,,,\nCollections,data_categories,ontology_array,true,DirectoryOntologies,DataCategories\n")
    api_model = {"id": "target-specific-schema", "tables": [{"name": "Collections", "columns": [
        {"name": "data_categories", "columnType": "ONTOLOGY_ARRAY", "required": "true",
         "refSchemaName": "DirectoryOntologies", "refTableName": "DataCategories", "position": 95},
        {"name": "mg_insertedOn", "columnType": "DATETIME"},
    ]}]}
    assert model_fingerprint(csv_model) == model_fingerprint(api_model)
    api_model["tables"][0]["columns"][0]["required"] = "false"
    assert model_fingerprint(csv_model) != model_fingerprint(api_model)


def test_model_csv_blank_type_uses_emx2_string_default():
    """Apply the model CSV import default without inventing omitted API properties.

    Returns:
        None.
    """
    from vocabulary_sources import parse_model_csv
    result = parse_model_csv("tableName,columnName,columnType\nOrganisations,id,\n")
    assert result["tables"][0]["columns"][0]["columnType"] == "STRING"


def test_history_does_not_stop_at_out_of_range_committer_dates(tmp_path, monkeypatch):
    """Exhaust pagination even when old commits precede an in-range edit in API order.

    Args:
        tmp_path: Isolated unused source-cache location for the transport fixture.
        monkeypatch: Pytest patch manager replacing only upstream byte retrieval.

    Returns:
        None.
    """
    import vocabulary_sources as sources
    start, finish = "0" * 40, "1" * 40
    path = "data/DataCategories.csv"

    def read(url, cache_dir, *, offline):
        """Return deliberately non-ancestral date ordering with one real transition.

        Args:
            url: Immutable API or raw-source request being simulated.
            cache_dir: Fixture cache root, not used because bytes are synthetic.
            offline: Offline policy passed through by the history reader.

        Returns:
            UTF-8 JSON or CSV response bytes for the requested history page.
        """
        if "/compare/" in url:
            payload = {"status": "ahead", "total_commits": 1, "commits": [{"sha": finish}]}
        elif "/commits?" in url:
            payload = ([{"sha": f"{100 + idx:040x}"} for idx in range(100)]
                       if url.endswith("&page=1") else [{"sha": finish}, {"sha": start}])
        elif "/commits/" in url:
            payload = {"parents": [{"sha": start}], "commit": {"committer": {"date": "2026-01-01T00:00:00Z"}},
                       "files": [{"filename": path, "status": "modified"}]}
        else:
            return ("name,definition\n" + ("OLD,Old\n" if start in url else "NEW,New\n")).encode()
        return json.dumps(payload).encode()

    monkeypatch.setattr(sources, "_read_source", read)
    result = sources.load_directory_history(repository="example/models", start_revision=start,
                                           end_revision=finish, paths=(path,), cache_dir=tmp_path)
    assert len(result["transitions"]) == 1
    assert result["transitions"][0]["changes"]["removed"] == ["OLD"]


def test_history_follows_previous_file_name_on_rename(tmp_path, monkeypatch):
    """Recover earlier edits from the former path, not just the renamed endpoint.

    Args:
        tmp_path: Isolated cache location passed through the synthetic history reader.
        monkeypatch: Pytest patch manager replacing upstream response retrieval.

    Returns:
        None.
    """
    import vocabulary_sources as sources
    start, middle, finish = "0" * 40, "1" * 40, "2" * 40

    def read(url, cache_dir, *, offline):
        """Supply a rename and its earlier edit under a different source path.

        Args:
            url: Immutable request identifying a commit, path or source file.
            cache_dir: Fixture cache root; no disk access is needed here.
            offline: Requested source policy, independent of the fake transport.

        Returns:
            JSON metadata or raw CSV bytes selected by the request identity.
        """
        if "/compare/" in url:
            payload = {"status": "ahead", "total_commits": 2,
                       "commits": [{"sha": middle}, {"sha": finish}]}
        elif "/commits?" in url:
            payload = [{"sha": middle if "old.csv" in url else finish}]
        elif "/commits/" in url:
            renamed = finish in url
            payload = {"parents": [{"sha": middle if renamed else start}],
                       "commit": {"committer": {"date": "2026-01-01T00:00:00Z"}},
                       "files": [{"filename": "data/DataCategories.csv" if renamed else "old.csv",
                                  "status": "renamed" if renamed else "modified",
                                  **({"previous_filename": "old.csv"} if renamed else {})}]}
        else:
            return b"name,definition\nA,Meaning\n"
        return json.dumps(payload).encode()

    monkeypatch.setattr(sources, "_read_source", read)
    result = sources.load_directory_history(repository="example/models", start_revision=start,
                                           end_revision=finish, paths=("data/DataCategories.csv",), cache_dir=tmp_path)
    assert [row["commit"] for row in result["transitions"]] == [middle, finish]
    assert "old.csv" in result["paths"]


def component_sources():
    """Build supported component documents for linked-source consistency tests.

    Returns:
        Source-path-to-text mappings containing only the two relevant attributes.
    """
    return {
        "README.md": "# MIABIS: Minimum Information About BIobank data Sharing\n[Collection](Core/V3/Data-describing-Collection.md)\n[Dataset Types](DatasetTypes/README.md) - under active development\n[Services](BiobankServices/README.md) - under active development\n",
        "DatasetTypes/README.md": "# Scope of the MIABIS Dataset Types\n## Objective & Scope\nProposed dataset entities.\n",
        "BiobankServices/README.md": "# Scope of the MIABIS Biobanking and Biomolecular Services\n## Objective & Scope\n[Component](https://github.com/BBMRI-ERIC/miabis/blob/master/BiobankServices/Data-describing-BiobankingBiomolecularServices.md)\n",
        "Core/V3/Data-describing-Collection.md": "# Data describing Collection entity\n## Attribute list\n| Attribute Code | Attribute Name | Allowed Data Types | Description | Constraints | Allowed Values | Cardinality |\n| --- | --- | --- | --- | --- | --- | --- |\n| MIABIS-COLLECTION-13 | Dataset type | Enumerated values | Data types | | Clinical dataset. | 1 |\n",
        "BiobankServices/Data-describing-BiobankingBiomolecularServices.md": "## Definition\n| Attribute Code | Attribute Name | Description | Data Type | Allowed Values | Constraints | Cardinality |\n| --- | --- | --- | --- | --- | --- | --- |\n| MIABIS-SERVICE-07 | Service type | Offered service | value set | [Service type](https://github.com/BBMRI-ERIC/miabis/blob/master/all%20lists.md#service-type) Sample storage | | 1..n |\n",
    }


def test_linked_components_are_validated_and_conflicts_are_reported():
    """Inspect inline controlled values instead of merely downloading linked files.

    Returns:
        None.
    """
    from vocabulary_sources import validate_miabis_components
    sources = component_sources()
    terms = {"DataCategories": [{"name": "Clinical dataset"}], "ServiceTypes": [{"name": "Sample storage"}]}
    result = validate_miabis_components(sources, terms)
    assert result["source_conflicts"] == []
    assert result["attributes"]["DataCategories"]["cardinality"] == "1"
    sources["Core/V3/Data-describing-Collection.md"] = sources["Core/V3/Data-describing-Collection.md"].replace("Clinical dataset.", "Unknown dataset.")
    conflict = validate_miabis_components(sources, terms)["source_conflicts"][0]
    assert conflict["table"] == "DataCategories"
    assert "Unknown dataset" in conflict["component_only"]
    sources["Core/V3/Data-describing-Collection.md"] = "Unsupported component body"
    with pytest.raises(ValueError, match="component"):
        validate_miabis_components(sources, terms)


def test_model_csv_supports_whitespace_before_quoted_semantics():
    """Read historical EMX2 CSV using its supported quoted-field spacing.

    Returns:
        None.
    """
    from vocabulary_sources import parse_model_csv
    text = 'tableName,columnName,columnType,semantics\nCatalogs,url,hyperlink, "foaf:homepage,dcat:landingPage"\n'
    assert parse_model_csv(text)["tables"][0]["columns"][0]["columnType"] == "hyperlink"
