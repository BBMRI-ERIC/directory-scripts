"""Regression tests for Flourish National-Node point aggregation."""

from flourish_nn import COUNTRY_POINTS, FlourishPoint, assigned_country, build_points, dataframe, html_summary


def test_missing_nodes_and_iarc_follow_node_scope():
    """Represent SI and IARC directly, and Qatar's EXT records only with opt-in.

    Returns:
        None. Country/staging exceptions preserve normal EXT switch semantics.
    """
    for code in ("SI", "DK", "QA", "IARC"):
        assert assigned_country(code, "FR", include_ext=False, include_all_countries=False) == code
    assert assigned_country("EXT", "QA", include_ext=True, include_all_countries=False) == "QA"
    assert assigned_country("EXT", "QA", include_ext=False, include_all_countries=False) is None
    assert assigned_country("EU", "FR", include_ext=True, include_all_countries=True) is None


def test_iarc_premises_region_and_node_specific_link():
    """Use the IARC headquarters pin rather than a French-country aggregate/link.

    Returns:
        None. IARC coordinates match its official map and Cyprus is in Europe.
    """
    point = FlourishPoint("IARC", frozenset({"bbmri-eric:ID:IARC_IARC_Biobank"}), frozenset(), {})
    row = dataframe([point], "https://directory.bbmri-eric.eu").iloc[0]
    assert row["Name"] == "IARC / WHO"
    assert row["Longitude"] == 4.8273207
    assert row["Latitude"] == 45.7266385
    assert row["Geographic regions"] == "Europe"
    assert "#/biobank/bbmri-eric:ID:IARC_IARC_Biobank" in row["Collection types"]
    assert "Countries=IARC" not in row["Collection types"]
    assert COUNTRY_POINTS["CY"].region == "Europe"
    assert COUNTRY_POINTS["DK"].name == "Denmark"


def test_ext_country_switches():
    """EXT records require the requested inclusion switch and country scope.

    Returns:
        None. EXT records require the requested inclusion switch and country scope.
    """
    assert assigned_country("EXT", "AT", include_ext=False, include_all_countries=False) is None
    assert assigned_country("EXT", "AT", include_ext=True, include_all_countries=False) == "AT"
    assert assigned_country("EXT", "US", include_ext=True, include_all_countries=False) is None
    assert assigned_country("EXT", "US", include_ext=False, include_all_countries=True) == "US"


def test_iarc_collection_only_scope_retains_a_directory_link():
    """Link selected collections if their biobank is outside the withdrawn scope.

    Returns:
        None. Collection-only IARC output has a usable exact-entity link.
    """
    cid = "bbmri-eric:ID:IARC_IARC_Biobank:collection:IARC"
    point = FlourishPoint("IARC", frozenset(), frozenset({cid}), {"OTHER": 1})
    html = html_summary(point, "https://directory.bbmri-eric.eu")
    assert f"#/collection/{cid}" in html
    assert "Countries=IARC" not in html


def test_exception_aggregation_and_missing_denmark_warning(caplog):
    """Count real exception records and diagnose absent nodes without making up rows.

    Args:
        caplog: Pytest log capture used to check the missing-Directory warning.

    Returns:
        None. SI/IARC/Qatar counts are exact; DK appears automatically once populated.
    """
    from unittest.mock import Mock

    directory = Mock()
    banks = {"si": "SI", "iarc": "IARC", "qbb": "EXT"}
    countries = {"si": "SI", "iarc": "FR", "qbb": "QA"}
    directory.getBiobanks.return_value = [{"id": bid} for bid in banks]
    directory.getCollections.return_value = [{"id": bid, "type": [{"id": "SAMPLE"}]} for bid in banks]
    directory.getBiobankNN.side_effect = banks.__getitem__
    directory.getCollectionNN.side_effect = banks.__getitem__
    directory.getBiobankCountry.side_effect = countries.__getitem__
    directory.getCollectionCountry.side_effect = countries.__getitem__
    points = build_points(directory, include_ext=True, include_all_countries=False)
    assert {p.country_code for p in points} == {"SI", "IARC", "QA"}
    assert all(len(p.biobanks) == len(p.collections) == p.types["SAMPLE"] == 1 for p in points)
    assert "DK" in caplog.text and "no selected Directory records" in caplog.text
    banks["dk"], countries["dk"] = "DK", "DK"
    directory.getBiobanks.return_value.append({"id": "dk"})
    caplog.clear()
    points = build_points(directory, include_ext=True, include_all_countries=False)
    assert next(p for p in points if p.country_code == "DK").biobanks == frozenset({"dk"})
    assert "DK" not in caplog.text


def test_html_summary_and_points_columns():
    """Flourish HTML begins with a break and the dataframe uses reference columns.

    Returns:
        None. Flourish HTML begins with a break and the dataframe uses reference columns.
    """
    point = FlourishPoint("AT", frozenset({"bb1"}), frozenset({"c1", "c2"}), {"SAMPLE": 2})
    html = html_summary(point, "https://directory.bbmri-eric.eu")
    assert html.startswith("<br>")
    assert "• Sample: 2<br>" in html
    assert 'catalogue?Countries=AT" target="_blank">See all</a>' in html
    assert list(dataframe([point], "https://directory.bbmri-eric.eu").columns) == [
        "Name", "Longitude", "Latitude", "Geographic regions", "Organisations", "Collections", "Collection types",
    ]
    assert COUNTRY_POINTS["AT"].name == "Austria"


def test_build_points_aggregates_member_and_enabled_ext_records():
    """Selected biobanks and collections are assigned by Node with EXT opt-in.

    Returns:
        None. Selected biobanks and collections are assigned by Node with EXT opt-in.
    """
    class DirectoryFixture:
        """Provide directory fixture used to isolate the tested behavior.
        """
        def getBiobanks(self):
            """Return synthetic biobank records available to the code under test.

            Returns:
                The synthetic biobank records available to the code under test.
            """
            return [{"id": "at"}, {"id": "ext"}]
        def getCollections(self):
            """Return synthetic collection records available to the code under test.

            Returns:
                The synthetic collection records available to the code under test.
            """
            return [{"id": "at-c"}, {"id": "ext-c"}]
        def getBiobankNN(self, item):
            """Return fixture national-node code for the requested biobank.

            Args:
                item: Biobank identifier whose fixture national-node code this stub returns.

            Returns:
                The fixture national-node code for the requested biobank.
            """
            return {"at": "AT", "ext": "EXT"}[item]
        def getBiobankCountry(self, item):
            """Return fixture country code for the requested biobank.

            Args:
                item: Biobank identifier whose fixture country code this stub returns.

            Returns:
                The fixture country code for the requested biobank.
            """
            return "AT"
        def getCollectionNN(self, item):
            """Return fixture national-node code for the requested collection.

            Args:
                item: Collection identifier whose fixture national-node code this stub returns.

            Returns:
                The fixture national-node code for the requested collection.
            """
            return "EXT" if item == "ext-c" else "AT"
        def getCollectionCountry(self, item):
            """Return fixture country code for the requested collection.

            Args:
                item: Collection identifier whose fixture country code this stub returns.

            Returns:
                The fixture country code for the requested collection.
            """
            return "AT"

    points = build_points(DirectoryFixture(), include_ext=True, include_all_countries=False)
    assert len(points) == 1
    assert points[0].country_code == "AT"
    assert points[0].biobanks == frozenset({"at", "ext"})
    assert points[0].collections == frozenset({"at-c", "ext-c"})
