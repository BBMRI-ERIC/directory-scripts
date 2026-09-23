"""Regression tests for Flourish National-Node point aggregation."""

from flourish_nn import COUNTRY_POINTS, FlourishPoint, assigned_country, build_points, dataframe, html_summary


def test_ext_country_switches():
    """EXT records require the requested inclusion switch and country scope."""
    assert assigned_country("EXT", "AT", include_ext=False, include_all_countries=False) is None
    assert assigned_country("EXT", "AT", include_ext=True, include_all_countries=False) == "AT"
    assert assigned_country("EXT", "US", include_ext=True, include_all_countries=False) is None
    assert assigned_country("EXT", "US", include_ext=False, include_all_countries=True) == "US"


def test_html_summary_and_points_columns():
    """Flourish HTML begins with a break and the dataframe uses reference columns."""
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
    """Selected biobanks and collections are assigned by Node with EXT opt-in."""
    class DirectoryFixture:
        def getBiobanks(self): return [{"id": "at"}, {"id": "ext"}]
        def getCollections(self): return [{"id": "at-c"}, {"id": "ext-c"}]
        def getBiobankNN(self, item): return {"at": "AT", "ext": "EXT"}[item]
        def getBiobankCountry(self, item): return "AT"
        def getCollectionNN(self, item): return "EXT" if item == "ext-c" else "AT"
        def getCollectionCountry(self, item): return "AT"

    points = build_points(DirectoryFixture(), include_ext=True, include_all_countries=False)
    assert len(points) == 1
    assert points[0].country_code == "AT"
    assert points[0].biobanks == frozenset({"at", "ext"})
    assert points[0].collections == frozenset({"at-c", "ext-c"})
