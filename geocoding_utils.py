"""Resolve Directory map positions with explicit authority, freshness and provenance."""

from dataclasses import dataclass, field
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Mapping
import logging

from geojsonutils import get_entity_coordinates


@dataclass(frozen=True)
class LocationContext:
    """Current organizational location inputs, independent of coordinate caches.

    Attributes:
        biobank_id: Exact canonical Directory identifier, retaining case.
        biobank_name: Original display name used in operator diagnostics.
        institution: Juridical person, or explicitly labelled biobank-name fallback.
        institution_source: Whether institution came from juridical_person or biobank_name.
        country: Reported country identifier/text, not a staging-area prefix.
        address: Current street/address; empty means institution fallback is eligible.
        zip: Current postcode, retaining leading zeroes where provided as text.
        city: Current reported city used for queries and research freshness.
        longitude_raw: Unmodified source coordinate component for parsing/diagnostics.
        latitude_raw: Unmodified source coordinate component for parsing/diagnostics.
        contact_id: Internal legacy-cache lookup identifier; never exported in research.
    """

    biobank_id: str
    biobank_name: str
    institution: str
    institution_source: str
    country: str
    address: str = ""
    zip: str = ""
    city: str = ""
    longitude_raw: Any = None
    latitude_raw: Any = None
    contact_id: str = ""


@dataclass(frozen=True)
class LocationCatalogue:
    """Owned, validated snapshot authorizing one source for the current run.

    Attributes:
        kind: manual_overrides or institution_resolutions; never inferred from cache.
        entries: ID-indexed validated entries; callers must treat mappings as read-only.
        document: Complete owned JSON envelope retained for lossless carry-forward.
    """

    kind: str
    entries: Mapping[str, dict]
    document: dict


@dataclass(frozen=True)
class CoordinateResult:
    """One biobank's winning position or explained unresolved outcome.

    Attributes:
        coordinates: Valid longitude/latitude tuple, or None for unresolved outcomes.
        source: directory, manual, institution, address or unresolved winner.
        channel: input, cache, api or none, describing this run's successful source.
        query_fields: Address field names actually used, empty for non-query sources.
        reason: Human-readable selection/failure explanation.
        evidence: Owned provenance mapping; callers must not mutate it.
    """

    coordinates: tuple[float, float] | None
    source: str
    channel: str = "none"
    query_fields: tuple[str, ...] = ()
    reason: str = ""
    evidence: Mapping = field(default_factory=dict)


def _text(value: Any) -> str:
    """Normalize missing scalar/context reference values without inventing content.

    Args:
        value: Directory text, country reference, missing value or numeric postcode.

    Returns:
        Trimmed text; None and non-finite numbers become empty strings.
    """
    if value is None or isinstance(value, float) and not math.isfinite(value):
        return ""
    if isinstance(value, Mapping):
        value = value.get("id") or value.get("name") or ""
    return str(value).strip()


def make_location_context(biobank: Mapping, contact: Mapping | None) -> LocationContext:
    """Copy relevant current fields without mutating loaded Directory records.

    Args:
        biobank: Directory biobank record with identity and optional coordinates.
        contact: Current contact record, or None when no contact is available.

    Returns:
        Organizational context with missing text normalized and raw coordinates kept.

    Raises:
        ValueError: If the biobank has no identifier.
    """
    if not _text(biobank.get("id")):
        raise ValueError("Biobank has no identifier")
    contact = contact or {}
    institution = _text(biobank.get("juridical_person"))
    return LocationContext(
        _text(biobank["id"]), _text(biobank.get("name")),
        institution or _text(biobank.get("name")),
        "juridical_person" if institution else "biobank_name",
        _text(biobank.get("country")) or _text(contact.get("country")),
        _text(contact.get("address")), _text(contact.get("zip")), _text(contact.get("city")),
        biobank.get("longitude"), biobank.get("latitude"), _text(contact.get("id")),
    )


def _digest(value: Any) -> str:
    """Fingerprint a JSON-compatible source using stable UTF-8 serialization.

    Args:
        value: Canonicalizable organizational/query/entry content.

    Returns:
        Lowercase SHA-256 digest independent of mapping insertion order.
    """
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                             separators=(",", ":")).encode()).hexdigest()


def context_fingerprint(context: LocationContext) -> str:
    """Bind researched positions to current biobank and organizational context.

    Args:
        context: Current identity, institution and coarse location; never personal fields.

    Returns:
        Deterministic digest of identity/institution/country/city/postcode with whitespace normalized.
    """
    return _digest([" ".join(value.split()) for value in (
        context.biobank_id, context.institution, context.country, context.city, context.zip)])


def parse_decimal_coordinates(longitude_raw: object, latitude_raw: object) -> list[float]:
    """Parse two decimal components, preserving combined invalid-source diagnostics.

    Args:
        longitude_raw: Numeric or decimal/comma-decimal longitude from source metadata.
        latitude_raw: Numeric or decimal/comma-decimal latitude from source metadata.

    Returns:
        New finite longitude/latitude float list.

    Raises:
        ValueError: If either component is malformed, boolean, non-finite or out of range.
    """
    values, issues = [], []
    for raw, label, lower, upper in ((longitude_raw, "longitude", -180, 180),
                                      (latitude_raw, "latitude", -90, 90)):
        try:
            if isinstance(raw, bool):
                raise ValueError("boolean coordinate")
            value = float(str(raw).replace(",", "."))
        except (ValueError, TypeError) as exc:
            issues.append(f"{label} parse error: {exc}")
            continue
        if not math.isfinite(value) or not lower <= value <= upper:
            issues.append(f"{label} out of range: {raw!r}")
        values.append(value)
    if issues:
        raise ValueError("; ".join(issues))
    return values


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    """Reject duplicate JSON object keys instead of silently retaining the last value.

    Args:
        pairs: Ordered object members supplied by the JSON decoder.

    Returns:
        Decoded object retaining each key once.

    Raises:
        ValueError: If any object repeats a key.
    """
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _require_text(entry: Mapping, keys: tuple[str, ...]) -> None:
    """Validate required nonblank JSON strings without coercing missing values.

    Args:
        entry: Local JSON object being validated.
        keys: Required organizational/contract field names.

    Returns:
        None. Leaves validated input unchanged.

    Raises:
        ValueError: If a required field is not nonblank text.
    """
    for key in keys:
        if not isinstance(entry.get(key), str) or not entry[key].strip():
            raise ValueError(f"{key} must be nonblank text")


def _validate_entry(entry: object, kind: str) -> None:
    """Validate one status-dependent local override/research record.

    Args:
        entry: Decoded JSON record; source Directory payloads are never passed here.
        kind: Authority kind selecting allowable policies and required evidence.

    Returns:
        None. The record remains unchanged for exact catalogue carry-forward.

    Raises:
        ValueError: If the entry violates the published local contract.
    """
    common = {"biobank_id", "policy", "status", "explanation", "longitude", "latitude", "address"}
    research = {"request_id", "context_fingerprint", "institution", "country", "evidence", "confidence", "qualifier"}
    if not isinstance(entry, dict) or set(entry) - (common | (research if kind == "institution_resolutions" else set())):
        raise ValueError("entry is not an object or contains unknown fields")
    _require_text(entry, ("biobank_id", "policy", "status", "explanation"))
    if (not entry["biobank_id"].startswith("bbmri-eric:ID:")
            or len(entry["biobank_id"]) <= len("bbmri-eric:ID:")
            or any(c.isspace() for c in entry["biobank_id"])):
        raise ValueError("biobank_id must be an exact canonical Directory ID")
    if entry["policy"] not in {"missing-location", "missing-coordinates", "always"}:
        raise ValueError("unknown policy")
    if entry["status"] not in {"resolved", "ambiguous", "unresolved"}:
        raise ValueError("unknown status")
    if kind == "manual_overrides" and entry["status"] != "resolved":
        raise ValueError("manual overrides require status resolved")
    if "address" in entry:
        address = entry["address"]
        if not isinstance(address, dict) or set(address) - {"address", "zip", "city", "country"}:
            raise ValueError("invalid address object")
        if not all(isinstance(v, str) for v in address.values()):
            raise ValueError("address components must be text")
    if kind == "institution_resolutions":
        _require_text(entry, ("request_id", "context_fingerprint", "institution", "country"))
        if entry["policy"] != "missing-location":
            raise ValueError("institution research requires missing-location policy")
        if "qualifier" in entry and not isinstance(entry["qualifier"], str):
            raise ValueError("qualifier must be text")
        if "confidence" in entry and (not isinstance(entry["confidence"], str)
                                      or entry["confidence"] not in {"high", "medium", "low"}):
            raise ValueError("unknown confidence")
        if "evidence" in entry:
            if not isinstance(entry["evidence"], list):
                raise ValueError("evidence must be a list")
            for item in entry["evidence"]:
                if not isinstance(item, dict) or set(item) - {"source", "note"}:
                    raise ValueError("invalid evidence object")
                _require_text(item, ("source",))
                if "note" in item and not isinstance(item["note"], str):
                    raise ValueError("evidence note must be text")
        if entry["status"] == "resolved":
            _require_text(entry.get("address", {}), ("address",))
            if not entry.get("evidence") or "confidence" not in entry:
                raise ValueError("resolved research requires evidence and confidence")
    if entry["status"] == "resolved" or "longitude" in entry or "latitude" in entry:
        if not all(isinstance(entry.get(k), (int, float)) and not isinstance(entry[k], bool)
                   for k in ("longitude", "latitude")):
            raise ValueError("coordinates must be two JSON numbers")
        parse_decimal_coordinates(entry["longitude"], entry["latitude"])


def load_location_catalogue(path: Path | None, expected_kind: str) -> LocationCatalogue:
    """Load one authoritative local snapshot, never substituting a coordinate cache.

    Args:
        path: Explicit input filename, or None to disable this source.
        expected_kind: manual_overrides or institution_resolutions expected by the flag.

    Returns:
        Owned validated snapshot and ID index, including unresolved research entries.

    Raises:
        ValueError: If the requested file is unreadable, malformed or incompatible.
    """
    if expected_kind not in {"manual_overrides", "institution_resolutions"}:
        raise ValueError(f"unknown catalogue kind: {expected_kind}")
    if path is None:
        document = {"schema_version": "1.0", "kind": expected_kind, "entries": []}
    else:
        try:
            document = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError(f"Cannot read location catalogue {path}: {exc}") from exc
    try:
        if not isinstance(document, dict) or set(document) != {"schema_version", "kind", "entries"}:
            raise ValueError("expected schema_version, kind and entries envelope")
        if document["schema_version"] != "1.0":
            raise ValueError("unsupported schema version")
        if document["kind"] != expected_kind:
            raise ValueError(f"expected kind {expected_kind}")
        if not isinstance(document["entries"], list):
            raise ValueError("entries must be a list")
        entries = {}
        for index, entry in enumerate(document["entries"]):
            try:
                _validate_entry(entry, expected_kind)
                if entry["biobank_id"] in entries:
                    raise ValueError("duplicate biobank ID")
            except ValueError as exc:
                raise ValueError(f"entry {index + 1}: {exc}") from exc
            entries[entry["biobank_id"]] = entry
    except ValueError as exc:
        raise ValueError(f"Invalid location catalogue {path or '<disabled>'}: {exc}") from exc
    return LocationCatalogue(expected_kind, entries, document)


def supplied_coordinates(context: LocationContext) -> tuple[float, float] | None:
    """Normalize valid Directory coordinates while permitting safe fallback on defects.

    Args:
        context: Current Directory components, possibly absent, numeric or formatted text.

    Returns:
        Finite validated coordinate pair, or None when either component is unusable.
    """
    try:
        if isinstance(context.longitude_raw, bool) or isinstance(context.latitude_raw, bool):
            return None
        pair = get_entity_coordinates({"longitude": context.longitude_raw, "latitude": context.latitude_raw})
        return tuple(parse_decimal_coordinates(*pair)) if pair else None
    except (ValueError, TypeError, OverflowError):
        return None


def geocoding_cache_key(contact_id: str, values: list[str]) -> str:
    """Reproduce the previous address-query key for provenance-checked cache reuse.

    Args:
        contact_id: Current contact ID, or empty for the old query-only key.
        values: Ordered, nonempty address fragments used by the legacy geocoder.

    Returns:
        Legacy key; use only when its stored query agrees with current fragments.
    """
    digest = sha256(" | ".join(value.strip() for value in values).encode()).hexdigest()
    return f"contact:{contact_id}:{digest}" if contact_id else f"query:{digest}"


def _cache_coordinates(entry: object) -> tuple[float, float] | None:
    """Validate an optional successful cache record before using its position.

    Args:
        entry: Decoded diskcache record or missing/malformed cached content.

    Returns:
        Validated pair for a resolved record, otherwise None without raising.
    """
    if not isinstance(entry, dict) or entry.get("status") != "resolved":
        return None
    pair = entry.get("coordinates")
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        return None
    try:
        return tuple(parse_decimal_coordinates(*pair))
    except (ValueError, TypeError):
        return None


def _institution_entry(context: LocationContext, catalogue: LocationCatalogue) -> dict | None:
    """Find current research only when both identity and context binding agree.

    Args:
        context: Current biobank identity and coarse organizational location.
        catalogue: Explicit current authoritative research snapshot, possibly empty.

    Returns:
        Read-only accepted resolved entry, or None for absent/stale/ambiguous research.
    """
    entry = catalogue.entries.get(context.biobank_id)
    if not entry or entry["status"] != "resolved":
        return None
    fingerprint = context_fingerprint(context)
    if (entry["context_fingerprint"] != fingerprint or entry["request_id"] != fingerprint
            or " ".join(entry["institution"].split()) != " ".join(context.institution.split())
            or " ".join(entry["country"].split()) != " ".join(context.country.split())):
        logging.warning("%s: ignoring stale institution-resolution context", context.biobank_id)
        return None
    return entry


def resolve_address(context: LocationContext, cache: Any, geocode: Any) -> CoordinateResult:
    """Resolve current address suffixes cache-first, retaining the successful fields.

    Args:
        context: Current street/postcode/city/country fields after source precedence.
        cache: Mutable cache; v2 records include queries and full freshness signatures.
        geocode: Injected address-only callable returning status and a geopy-like location.

    Returns:
        Address-source success with cache/API channel, or an explained unresolved result.
    """
    parts = [(key, getattr(context, key)) for key in ("address", "zip", "city", "country") if getattr(context, key)]
    if not parts:
        return CoordinateResult(None, "unresolved", reason="missing_address_context")
    signature = _digest([context.biobank_id, parts])
    bank_key = f"address-biobank:v2:{signature}"
    bank_entry = cache.get(bank_key)
    if isinstance(bank_entry, dict) and bank_entry.get("signature") == signature:
        fields = bank_entry.get("query_fields")
        candidates = [tuple(key for key, value in parts[index:]) for index in range(len(parts))]
        pair = _cache_coordinates(bank_entry)
        if pair and isinstance(fields, (tuple, list)) and tuple(fields) in candidates:
            return CoordinateResult(pair, "address", "cache", tuple(fields), "cached_biobank_address")
    variants = []
    for start in range(len(parts)):
        variant = parts[start:]
        fields = tuple(key for key, value in variant)
        values = [value for key, value in variant]
        key = f"address:v2:{_digest(variant)}"
        entry = cache.get(key)
        legacy = False
        if entry is None:
            old = cache.get(geocoding_cache_key(context.contact_id, values))
            if isinstance(old, dict) and old.get("query") == values:
                entry, legacy = old, True
        pair = _cache_coordinates(entry)
        if pair and (legacy or isinstance(entry, dict) and entry.get("query") == values and entry.get("query_fields") == list(fields)):
            cache[bank_key] = {"status": "resolved", "coordinates": list(pair), "signature": signature,
                               "query_fields": list(fields)}
            return CoordinateResult(pair, "address", "cache", fields, "cached_address_query")
        negative = isinstance(entry, dict) and entry.get("status") == "not_found" and entry.get("query") == values
        variants.append((key, fields, values, negative))
    for key, fields, values, negative in variants:
        if negative:
            continue
        status, location = geocode(", ".join(values))
        if status == "resolved" and location is not None:
            try:
                pair = tuple(parse_decimal_coordinates(location.longitude, location.latitude))
            except (ValueError, TypeError, AttributeError):
                logging.warning("%s: geocoder returned invalid coordinates", context.biobank_id)
                continue
            cache[key] = {"status": "resolved", "coordinates": list(pair), "query": values,
                          "query_fields": list(fields)}
            cache[bank_key] = {"status": "resolved", "coordinates": list(pair), "signature": signature,
                               "query_fields": list(fields)}
            return CoordinateResult(pair, "address", "api", fields, "live_address_query")
        if status == "disabled":
            return CoordinateResult(None, "unresolved", reason="service_disabled")
        if status == "not_found":
            cache[key] = {"status": "not_found", "query": values, "query_fields": list(fields)}
    return CoordinateResult(None, "unresolved", reason="address_not_found")


def resolve_coordinates(context: LocationContext, manual: LocationCatalogue,
                        institutions: LocationCatalogue, cache: Any, geocode: Any) -> CoordinateResult:
    """Select one authorized source before consulting address or research caches.

    Args:
        context: Current Directory identity, contact address and raw coordinates.
        manual: Explicit current manual snapshot; absent entries have no authority.
        institutions: Explicit current research snapshot; cache alone grants no authority.
        cache: Mutable typed coordinate cache, never a substitute for current inputs.
        geocode: Injected rate-limited address geocoder; never an AI interface.

    Returns:
        Exactly one winning coordinate result or explained unresolved outcome.
    """
    coordinates = supplied_coordinates(context)
    override = manual.entries.get(context.biobank_id)
    if override and (override["policy"] == "always" or not coordinates and
                     (override["policy"] == "missing-coordinates" or not context.address)):
        pair = tuple(parse_decimal_coordinates(override["longitude"], override["latitude"]))
        return CoordinateResult(pair, "manual", "input", reason=override["explanation"],
                                evidence={"policy": override["policy"]})
    if coordinates:
        return CoordinateResult(coordinates, "directory", "input", reason="supplied_coordinates")
    if _text(context.longitude_raw) or _text(context.latitude_raw):
        logging.warning("%s: invalid supplied coordinates longitude=%r latitude=%r; trying fallbacks",
                        context.biobank_id, context.longitude_raw, context.latitude_raw)
    if not context.address:
        entry = _institution_entry(context, institutions)
        if entry:
            signature = _digest([context_fingerprint(context), entry])
            key = f"institution:v2:{signature}"
            expected = tuple(parse_decimal_coordinates(entry["longitude"], entry["latitude"]))
            cached = _cache_coordinates(cache.get(key))
            channel = "cache" if cached == expected else "input"
            cache[key] = {"status": "resolved", "coordinates": list(expected)}
            return CoordinateResult(expected, "institution", channel, reason=entry["explanation"],
                                    evidence=dict(entry))
    return resolve_address(context, cache, geocode)
