"""Build auditable survey participation rosters without counting collections as biobanks."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter

from survey_identity import country_key


def digest(value: object) -> str:
    """Hash deterministic JSON material shared by the map preparation pipeline.

    Args:
        value: JSON-compatible source/count material, with finite numeric values.

    Returns:
        Hexadecimal SHA-256 of sorted UTF-8 JSON without insignificant whitespace.
    """
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def map_country(value: object) -> str | None:
    """Normalize country evidence without guessing a country from a staging ID.

    Args:
        value: Reported country name/code or a Directory name-reference mapping.

    Returns:
        ISO-style two-letter code, or None for absent/unrecognized evidence.
    """
    if isinstance(value, dict):
        value = value.get("name")
    code = country_key(value)
    code = {"MONTENEGRO": "ME", "QATAR": "QA", "NAMIBIA": "NA",
            "TÜRKIYE": "TR", "TURKIYE": "TR"}.get(code, code)
    code = {"MNE": "ME", "UK": "GB", "EL": "GR"}.get(code, code)
    return code if re.fullmatch(r"[A-Z]{2}", code) and code != "XX" else None


def directory_inventory(directory) -> dict:
    """Freeze the configured Directory denominator without using geocoded points.

    Args:
        directory: Existing read-only Directory exposing scoped biobanks and context.

    Returns:
        Sorted inventory, configured withdrawal scope, target/schema, honest
        observation time and a digest covering all inventory evidence.

    Raises:
        ValueError: If the selected inventory contains invalid or duplicate IDs.
    """
    banks = []
    seen = set()
    for bank in directory.getBiobanks():
        bid = bank.get("id")
        if not isinstance(bid, str) or not bid or bid in seen:
            raise ValueError("Directory inventory has missing or duplicate biobank IDs")
        seen.add(bid)
        banks.append({"id": bid, "country": map_country(bank.get("country")),
                      "withdrawn": bool(bank.get("withdrawn", False))})
    result = {"schema_version": 1, "target": directory.getDirectoryUrl(), "schema": directory.getSchema(),
              "scope": "only-withdrawn" if getattr(directory, "only_withdrawn_entities", False) else
                  "including-withdrawn" if getattr(directory, "include_withdrawn_entities", False) else "active",
              "observed_at": None, "biobanks": sorted(banks, key=lambda row: row["id"])}
    return {**result, "sha256": digest(result)}


def _mucp_inventory(payload: dict) -> dict:
    """Recover all MuCP source records, not only banks selected by the join.

    Args:
        payload: Combined report containing source arrays and full matching inventories.

    Returns:
        Source-ID keyed pairs of records and available identity decisions.

    Raises:
        ValueError: If repeated source records or accepted identities disagree.
    """
    result = {}

    def retain(record, decision):
        """Retain one source with consistent duplicate and identity validation.

        Args:
            record: MuCP source record; other survey records are ignored.
            decision: Original accepted/review/excluded identity resolution.

        Returns:
            None after updating the enclosing source index.
        """
        if record.get("survey") != "MuCP":
            return
        rid = record.get("record_id")
        if not isinstance(rid, str) or not rid:
            raise ValueError("MuCP source lacks a record_id")
        if rid in result and result[rid][0] != record:
            raise ValueError(f"Conflicting copies of MuCP source {rid}")
        previous = result.get(rid, (record, {}))[1]
        if previous.get("biobank_id") and decision.get("biobank_id") and previous["biobank_id"] != decision["biobank_id"]:
            raise ValueError(f"Conflicting identity decisions for {rid}")
        result[rid] = (copy.deepcopy(record), copy.deepcopy(decision or previous))

    for bank in payload.get("biobanks", []):
        decisions = {d["source_record_id"]: d for d in bank.get("identity_resolutions", [])}
        for record in bank.get("mucp_source_records", []):
            fallback = {"status": "accepted", "biobank_id": bank.get("directory_biobank_id") or
                        (bank.get("biobank_id") if str(bank.get("biobank_id", "")).startswith("bbmri-eric:ID:") else None)}
            retain(record, decisions.get(record["record_id"], fallback))
    for key in ("unmatched_mucp", "manual_review_matches", "excluded_source_records"):
        for item in payload.get(key, []):
            retain(item["record"], item.get("resolution", {}))
    return result


def collect_participation(so2_payload: dict, combined_payload: dict | None = None,
                          identities: dict | None = None) -> dict:
    """Combine full survey source identities without inferring fuzzy matches.

    Args:
        so2_payload: Descriptive JSON with original rows and reviewed observation groups.
        combined_payload: Optional combined JSON with complete MuCP matching inventory.
        identities: Optional source-hash-bound groups explicitly linking source records
            or decomposed national collection scopes to individual biobanks.

    Returns:
        Deterministic unit roster, source bindings, national-summary audit and
        reviewed decisions. Unlinked unresolved individuals remain provisional.

    Raises:
        ValueError: If sources, explicit review or duplicate identities are inconsistent.
    """
    so2_hash = so2_payload.get("provenance", {}).get("source_sha256")
    if not so2_hash or "responses_summary" not in so2_payload:
        raise ValueError("SO2 payload lacks source-bound response groups; regenerate describe JSON")
    inputs = {"so2": so2_hash}
    if combined_payload is not None:
        combined_inputs = combined_payload.get("inputs", {})
        if combined_inputs.get("so2_sha256") != so2_hash:
            raise ValueError("Combined and descriptive SO2 source hashes differ")
        inputs["mucp"] = combined_inputs.get("mucp_sha256")
        if not inputs["mucp"]:
            raise ValueError("Combined payload lacks the MuCP source hash; regenerate it")
    review = copy.deepcopy(identities or {"schema_version": 1, "inputs": inputs, "groups": []})
    if review.get("schema_version") != 1 or any(review.get("inputs", {}).get(k) != v for k, v in inputs.items()):
        raise ValueError("Participation identity review source hashes do not match")
    units, records, summaries = {}, {}, []

    def add(uid, ref, country, bid=None, reviewed=False):
        """Attach one owned source reference to a reporting identity.

        Args:
            uid: Stable local or canonical Directory identity.
            ref: Survey/record and optional collection-scope reference.
            country: Normalized reported country or None.
            bid: Accepted canonical Directory identity, when independently available.
            reviewed: Whether this addition explicitly overrides country evidence.

        Returns:
            None after retaining the source and country evidence in the roster.
        """
        unit = units.setdefault(uid, {"unit_id": uid, "directory_biobank_id": bid,
                                     "source_refs": [], "country_evidence": [], "country_overrides": {}})
        if bid and unit["directory_biobank_id"] not in (None, bid):
            raise ValueError("Reviewed group combines distinct Directory biobanks")
        unit["directory_biobank_id"] = unit["directory_biobank_id"] or bid
        if ref not in unit["source_refs"]:
            unit["source_refs"].append(ref)
        if country and country not in unit["country_evidence"]:
            unit["country_evidence"].append(country)
        if reviewed and country:
            if unit["country_overrides"].get(ref["survey"]) not in (None, country):
                raise ValueError("Reviewed country overrides conflict")
            unit["country_overrides"][ref["survey"]] = country

    summary = so2_payload["responses_summary"]
    rows = {r["source_row"]: r for r in summary["source_records"]}
    if len(rows) != len(summary["source_records"]):
        raise ValueError("SO2 source rows must have unique physical row identifiers")
    if any("Country" not in row.get("answers", {}) for row in rows.values()):
        raise ValueError("SO2 map inputs require the Country source column; a missing value may be blank, not an absent column")
    corrections = {r["source_row"]: r["country"] for r in summary.get("country_corrections", [])}
    sheet = so2_payload["provenance"].get("worksheet", "Content")
    seen_rows = set()
    for group in summary["observation_sources"]:
        if not group.get("source_rows") or seen_rows.intersection(group["source_rows"]):
            raise ValueError("SO2 source rows have overlapping or empty observation ownership")
        seen_rows.update(group["source_rows"])
        bid = group.get("biobank_id")
        uid = bid or f"so2:{sheet}:row:{min(group['source_rows'])}"
        for row in group["source_rows"]:
            if row not in rows:
                raise ValueError("SO2 group references an absent source row")
            rid = f"so2:{sheet}:row:{row}"
            country = map_country(corrections.get(row, rows[row]["answers"].get("Country")))
            records[("SO2", rid)] = ({"country": country}, {"biobank_id": bid})
            add(uid, {"survey": "SO2", "record_id": rid}, country, bid)
    if seen_rows != set(rows):
        raise ValueError("SO2 response groups do not cover every retained source row")
    mucp_sources = _mucp_inventory(combined_payload or {})
    expected_count = (combined_payload or {}).get("metadata", {}).get("mucp_source_coverage", {}).get("input_records")
    if combined_payload is not None and (type(expected_count) is not int or expected_count < 0 or len(mucp_sources) != expected_count):
        raise ValueError("Combined payload lacks a complete MuCP inventory; regenerate it")
    decomposed = {record.get("source_response_id") for record, decision in mucp_sources.values()
                  if record.get("record_type") == "scope_projection" and decision.get("biobank_id")
                  and decision.get("status") in {"accepted", "excluded"}}
    scoped_reviews = {(ref.get("survey"), ref.get("record_id"))
                      for group in review.get("groups", []) for ref in group.get("sources", []) if ref.get("scope_id")}
    whole_reviews = {(ref.get("survey"), ref.get("record_id"))
                     for group in review.get("groups", []) for ref in group.get("sources", []) if not ref.get("scope_id")}
    if scoped_reviews & whole_reviews:
        raise ValueError("A reviewed source cannot have both whole-record and collection-scope ownership")
    residuals = []
    for rid, (record, decision) in mucp_sources.items():
        records[("MuCP", rid)] = (record, decision)
        if record.get("record_type") == "country_summary":
            summaries.append({"record_id": rid, "country": map_country(record.get("country"))})
            continue
        if rid in decomposed or ("MuCP", rid) in scoped_reviews:
            residuals.append({"record_id": rid, "reason": "Individual owners counted through collection scopes"})
            continue
        bid = decision.get("biobank_id") if decision.get("status") in {"accepted", "excluded"} else None
        if record.get("record_type") == "scope_projection" and not bid:
            residuals.append({"record_id": rid, "reason": "Projected collection has no accepted individual owner"})
            continue
        uid = bid or "mucp:" + str(record.get("source_response_id") or rid)
        add(uid, {"survey": "MuCP", "record_id": rid}, map_country(record.get("country")), bid)
    assigned = set()
    for group in review.get("groups", []):
        if not group.get("unit_id") or not group.get("reason") or not group.get("sources"):
            raise ValueError("Reviewed groups require unit_id, reason and source references")
        refs = []
        bids = set()
        for ref in group["sources"]:
            key = (ref.get("survey"), ref.get("record_id"))
            if key[0] == "MuCP" and combined_payload is None:
                continue
            if key not in records:
                raise ValueError(f"Reviewed source reference does not exist: {key}")
            record, decision = records[key]
            scope = ref.get("scope_id")
            if scope and not any(s.get("scope_id") == scope and s.get("kind") == "collection" for s in record.get("scopes", [])):
                raise ValueError("Reviewed scope must be an owned collection scope")
            if record.get("record_type") == "country_summary" and not scope:
                raise ValueError("A national summary cannot count without individual scope decomposition")
            token = (*key, scope)
            if token in assigned:
                raise ValueError("Reviewed source belongs to multiple participation groups")
            assigned.add(token)
            refs.append(dict(ref))
            if decision.get("biobank_id") and decision.get("status", "accepted") in {"accepted", "excluded"}:
                bids.add(decision["biobank_id"])
        if len(bids) > 1 or (bids and group["unit_id"].startswith("bbmri-eric:ID:") and group["unit_id"] not in bids):
            raise ValueError("Reviewed group combines distinct Directory biobanks")
        if bids and group["unit_id"] not in bids:
            raise ValueError("Reviewed groups must retain a known canonical Directory identity")
        for ref in refs:
            for unit in units.values():
                if ref in unit["source_refs"]:
                    unit["source_refs"].remove(ref)
            reviewed_bid = next(iter(bids), None)
            if reviewed_bid is None and re.fullmatch(r"bbmri-eric:ID:[A-Z]{2,5}_[A-Za-z0-9_.:-]+", group["unit_id"]):
                reviewed_bid = group["unit_id"]
            add(group["unit_id"], ref, map_country(group.get("country")), reviewed_bid, reviewed=True)
    result_units = []
    for unit in units.values():
        if not unit["source_refs"]:
            continue
        refs = sorted(unit["source_refs"], key=lambda ref: (ref["survey"], ref["record_id"], ref.get("scope_id", "")))
        evidence = sorted({country for ref in refs if (country := map_country(
            records[(ref["survey"], ref["record_id"])][0].get("country")))})
        survey_countries = {}
        for survey in sorted({r["survey"] for r in refs}):
            values = {map_country(records[(r["survey"], r["record_id"])][0].get("country"))
                      for r in refs if r["survey"] == survey} - {None}
            survey_countries[survey] = unit["country_overrides"].get(survey) or (next(iter(values)) if len(values) == 1 else None)
        display_countries = set(survey_countries.values()) - {None}
        result_units.append({**unit, "country_evidence": evidence, "source_refs": refs,
                             "country_by_survey": survey_countries,
                             "country": next(iter(display_countries)) if len(display_countries) == 1 else None,
                             "surveys": sorted({r["survey"] for r in refs}),
                             "provisional": not bool(unit["directory_biobank_id"])})
    return {"schema_version": 1, "inputs": inputs, "units": sorted(result_units, key=lambda u: u["unit_id"]),
            "national_summaries": sorted(summaries, key=lambda r: r["record_id"]),
            "residual_sources": sorted(residuals, key=lambda r: r["record_id"]), "review": review}


def participation_binding(participation: dict, survey: str | None = None) -> dict:
    """Select canonical identity material independently of report layout or join.

    Args:
        participation: Source-bound roster from collect_participation.
        survey: Optional survey name for a separately comparable per-survey binding.

    Returns:
        Deterministic identity material suitable for digest and manifest validation.
    """
    units = []
    for unit in participation["units"]:
        refs = [r for r in unit["source_refs"] if survey is None or r["survey"] == survey]
        if refs:
            units.append({"unit_id": unit["unit_id"], "country": unit["country_by_survey"].get(survey) if survey else unit["country"], "source_refs": refs,
                          "directory_biobank_id": unit["directory_biobank_id"], "provisional": unit["provisional"]})
            if survey is None:
                units[-1]["country_by_survey"] = unit["country_by_survey"]
    return {"inputs": {k: v for k, v in participation["inputs"].items() if survey is None or k.lower() == survey.lower()},
            "units": units}


def build_country_counts(participation: dict, inventory: dict) -> dict:
    """Compute country numerators independently of the frozen Directory denominator.

    Args:
        participation: Canonical full-source unit roster.
        inventory: Frozen Directory inventory with matching reported-country grouping.

    Returns:
        Sorted country counts, unclamped percentages and explicit unknown-country totals.
    """
    banks = {b["id"]: b for b in inventory["biobanks"]}
    countries = {b["country"] for b in banks.values() if b["country"]}
    counts = {}
    shared_country_conflicts = []
    for unit in participation["units"]:
        authoritative_country = banks.get(unit["directory_biobank_id"], {}).get("country")
        placements = {}
        for survey in unit["surveys"]:
            country = unit["country_overrides"].get(survey) or authoritative_country or unit["country_by_survey"][survey]
            placements[survey] = country
            tally = counts.setdefault(country, Counter())
            key = survey.lower()
            tally[key + "_count"] += 1
            tally[key + "_provisional_count"] += int(unit["provisional"])
            if country:
                countries.add(country)
        if set(unit["surveys"]) == {"SO2", "MuCP"}:
            if placements["SO2"] == placements["MuCP"]:
                counts.setdefault(placements["SO2"], Counter())["shared_count"] += 1
            else:
                shared_country_conflicts.append({"unit_id": unit["unit_id"], "countries": placements})
    rows = []
    fields = ("so2_count", "mucp_count", "shared_count", "so2_provisional_count", "mucp_provisional_count")
    for country in sorted(countries):
        row = {"country": country, **{k: counts.get(country, {}).get(k, 0) for k in fields}}
        row["directory_count"] = sum(b["country"] == country for b in banks.values())
        row["so2_percent"] = 100 * row["so2_count"] / row["directory_count"] if row["directory_count"] else None
        rows.append(row)
    return {"countries": rows, "unknown_country": {k: counts.get(None, {}).get(k, 0) for k in fields},
            "shared_country_conflicts": shared_country_conflicts,
            "national_summaries": copy.deepcopy(participation["national_summaries"])}
