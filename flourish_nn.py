"""Build Flourish country-point data from BBMRI Directory entities."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from directory import Directory
from nncontacts import NNContacts


@dataclass(frozen=True)
class CountryPoint:
    """Static display and map position metadata for one country."""

    name: str
    longitude: float
    latitude: float
    region: str


# Published Flourish point positions, retained as data rather than a runtime template.
COUNTRY_POINTS: Mapping[str, CountryPoint] = {
    "AT": CountryPoint("Austria", 16.3798, 48.2201, "Europe"),
    "BE": CountryPoint("Belgium", 4.36761, 50.8371, "Europe"),
    "BG": CountryPoint("Bulgaria", 23.3238, 42.7105, "Europe"),
    "CH": CountryPoint("Switzerland", 7.44821, 46.948, "Europe"),
    "CY": CountryPoint("Cyprus", 33.3736, 35.1676, "Asia"),
    "CZ": CountryPoint("Czech Republic", 14.4205, 50.0878, "Europe"),
    "DE": CountryPoint("Germany", 13.4115, 52.5235, "Europe"),
    "EE": CountryPoint("Estonia", 24.7586, 59.4392, "Europe"),
    "ES": CountryPoint("Spain", -3.70327, 40.4167, "Europe"),
    "FI": CountryPoint("Finland", 24.9525, 60.1608, "Europe"),
    "GR": CountryPoint("Greece", 23.7166, 37.9792, "Europe"),
    "HU": CountryPoint("Hungary", 19.0408, 47.4984, "Europe"),
    "IT": CountryPoint("Italy", 12.4823, 41.8955, "Europe"),
    "LT": CountryPoint("Lithuania", 25.2799, 54.6896, "Europe"),
    "LV": CountryPoint("Latvia", 24.1048, 56.9465, "Europe"),
    "MT": CountryPoint("Malta", 14.5189, 35.9042, "Europe"),
    "NL": CountryPoint("Netherlands", 4.89095, 52.3738, "Europe"),
    "NO": CountryPoint("Norway", 10.7387, 59.9138, "Europe"),
    "PL": CountryPoint("Poland", 21.02, 52.26, "Europe"),
    "SE": CountryPoint("Sweden", 18.0645, 59.3327, "Europe"),
    "SK": CountryPoint("Slovakia", 17.1073, 48.1484, "Europe"),
    "TR": CountryPoint("Türkiye", 32.3606, 39.7153, "Asia"),
    "AU": CountryPoint("Australia", 149.129, -35.282, "Oceania"),
    "CA": CountryPoint("Canada", -75.6919, 45.4215, "North America"),
    "FR": CountryPoint("France", 2.35097, 48.8566, "Europe"),
    "IL": CountryPoint("Israel", 35.2035, 31.7717, "Asia"),
    "PT": CountryPoint("Portugal", -9.13552, 38.7072, "Europe"),
    "QA": CountryPoint("Qatar", 51.5082, 25.2948, "Asia"),
    "SI": CountryPoint("Slovenia", 14.5044, 46.0546, "Europe"),
    "UG": CountryPoint("Uganda", 32.5729, 0.314269, "Africa"),
    "UK": CountryPoint("United Kingdom", -0.126236, 51.5002, "Europe"),
    "US": CountryPoint("United States", -77.032, 38.8895, "North America"),
    "VN": CountryPoint("Vietnam", 105.825, 21.0069, "Asia"),
}
TYPE_LABELS = {
    "SAMPLE": "Sample", "POPULATION_BASED": "Population-based", "HOSPITAL": "Hospital",
    "LONGITUDINAL": "Longitudinal", "DISEASE_SPECIFIC": "Disease specific",
    "IMAGE": "Image", "COHORT": "Cohort", "PROSPECTIVE_STUDY": "Prospective study",
    "PROSPECTIVE_COLLECTION": "Prospective study", "OTHER": "Other", "RD": "Rare disease",
    "NON_HUMAN": "Non-human", "CASE_CONTROL": "Case-control", "BIRTH_COHORT": "Birth cohort",
    "CROSS_SECTIONAL": "Cross-sectional", "QUALITY_CONTROL": "Quality control",
    "RARE_DISEASE": "Rare disease", "TWIN_STUDY": "Twin-study",
}


@dataclass(frozen=True)
class FlourishPoint:
    """Aggregated Directory observations for one displayed country."""

    country_code: str
    biobanks: frozenset[str]
    collections: frozenset[str]
    types: Mapping[str, int]


def assigned_country(staging_area: str, country: str, *, include_ext: bool, include_all_countries: bool) -> str | None:
    """Return the display country allowed by the Node/EXT selection switches.

    Args:
        staging_area: Entity staging-area code from its Directory identity.
        country: Entity's reported two-letter country code.
        include_ext: Whether EXT records in member/observer countries are included.
        include_all_countries: Whether every EXT reported country is included.

    Returns:
        Included output country code, or ``None`` when the entity is excluded.
    """
    if staging_area == "EXT" and (include_all_countries or (include_ext and NNContacts.is_member_node(country))):
        return country
    if staging_area == "EXT":
        return None
    if NNContacts.is_member_node(staging_area):
        return staging_area
    return None


def build_points(directory: Directory, *, include_ext: bool, include_all_countries: bool) -> list[FlourishPoint]:
    """Aggregate selected Directory entities into country-point observations.

    Args:
        directory: Loaded Directory restricted to the requested withdrawn scope.
        include_ext: Whether eligible EXT records augment member/observer points.
        include_all_countries: Whether non-member reported-country points are emitted.

    Returns:
        Country-name-sorted aggregate points.

    Raises:
        ValueError: If an emitted country has no checked-in Flourish metadata.
    """
    values: dict[str, dict[str, Any]] = defaultdict(lambda: {"biobanks": set(), "collections": set(), "types": Counter()})
    for biobank in directory.getBiobanks():
        bid = str(biobank["id"])
        code = assigned_country(directory.getBiobankNN(bid), directory.getBiobankCountry(bid), include_ext=include_ext, include_all_countries=include_all_countries)
        if code:
            values[code]["biobanks"].add(bid)
    for collection in directory.getCollections():
        cid = str(collection["id"])
        code = assigned_country(directory.getCollectionNN(cid), directory.getCollectionCountry(cid), include_ext=include_ext, include_all_countries=include_all_countries)
        if not code:
            continue
        values[code]["collections"].add(cid)
        values[code]["types"].update(Directory.getListOfEntityAttributeIds(collection, "type"))
    result = []
    for code, value in values.items():
        if code not in COUNTRY_POINTS:
            raise ValueError(f"No Flourish point metadata for emitted country {code!r}.")
        result.append(FlourishPoint(code, frozenset(value["biobanks"]), frozenset(value["collections"]), dict(value["types"])))
    return sorted(result, key=lambda point: COUNTRY_POINTS[point.country_code].name)


def html_summary(point: FlourishPoint, directory_url: str) -> str:
    """Return Flourish-compatible HTML collection-type and Directory-link text.

    Args:
        point: One country aggregate to render.
        directory_url: Directory base URL used for the catalogue hyperlink.

    Returns:
        HTML text for the Flourish Collection types column.
    """
    lines = ["<br>"]
    for type_id, count in sorted(point.types.items(), key=lambda item: (-item[1], TYPE_LABELS.get(item[0], item[0]))):
        if count:
            lines.append(f"• {TYPE_LABELS.get(type_id, type_id.title().replace('_', ' '))}: {count}<br>")
    url = directory_url.rstrip("/")
    lines.append(f'<a href="{url}/ERIC/directory/#/catalogue?Countries={point.country_code}" target="_blank">See all</a>')
    return "\n".join(lines)


def dataframe(points: list[FlourishPoint], directory_url: str) -> pd.DataFrame:
    """Return Flourish Points data in the reference workbook column order.

    Args:
        points: Country aggregates selected for output.
        directory_url: Directory base URL used for each summary hyperlink.

    Returns:
        Seven-column dataframe suitable for the ``Points`` worksheet.
    """
    return pd.DataFrame([{
        "Name": COUNTRY_POINTS[p.country_code].name, "Longitude": COUNTRY_POINTS[p.country_code].longitude,
        "Latitude": COUNTRY_POINTS[p.country_code].latitude, "Geographic regions": COUNTRY_POINTS[p.country_code].region,
        "Organisations": len(p.biobanks), "Collections": len(p.collections), "Collection types": html_summary(p, directory_url),
    } for p in points])
