"""Prepare readable type labels and safely pooled combined-report quantity views."""

from collections import defaultdict
from copy import deepcopy
import math
from typing import Any, Mapping, Sequence

from survey_evidence import fingerprint


def report_country_code(value: Any) -> str:
    """Normalize country labels for reporting without changing source identity.

    Args:
        value: Country name or code from Directory or a survey reporting row.

    Returns:
        TR for Turkey aliases, MNE for Montenegro aliases, otherwise the shared
        resolver's country key; missing country labels remain Unknown.
    """
    from survey_identity import country_key, literal_name
    key = literal_name(value)
    if key in {"", "unknown", "not reported", "none", "nan"}:
        return "Unknown"
    if key in {"turkey", "turkiye", "tr"}:
        return "TR"
    if key in {"montenegro", "me", "mne"}:
        return "MNE"
    return country_key(value) or "Unknown"


def prepare_quantity_report_views(views: Mapping[str, Any]) -> dict[str, Any]:
    """Fold date-specific display panels while retaining dated source contributions.

    Args:
        views: Detached confirmed/inclusive country and type views with source IDs.

    Returns:
        Reporting-only panels grouped by kind, unit and measurement meaning;
        every segment retains its reporting dates. Source aggregates stay unchanged.

    Raises:
        ValueError: If partially shared source IDs or inconsistent values/owners
            would make the folded quantity total ambiguous.
    """
    result = deepcopy(dict(views))
    for dimension in ("country_views", "type_views"):
        groups = {}
        for source_view in views.get(dimension, []):
            key = (source_view["kind"], source_view["unit"], source_view["meaning"])
            view = groups.setdefault(key, {**source_view, "temporal_status": "mixed_reported_dates", "rows": []})
            for source_row in source_view["rows"]:
                label = report_country_code(source_row["label"]) if dimension == "country_views" else source_row["label"]
                row = next((r for r in view["rows"] if r["label"] == label), None)
                if row is None:
                    row = {"label": label, "reported_total": 0, "confirmed_total": 0,
                           "uncertain_total": 0, "display_total": 0, "segments": []}
                    view["rows"].append(row)
                for source_segment in source_row["segments"]:
                    segment = deepcopy(source_segment)
                    if dimension == "type_views" and not segment.get("uncertain"):
                        segment["id"] = report_country_code(segment["id"])
                    date = source_view["temporal_status"]
                    dates = segment.get("reporting_dates") or [date]
                    segment["qualification_contributions"] = segment.get("qualification_contributions") or [{
                        key: deepcopy(segment.get(key)) for key in (
                            "source_record_id", "scope_id", "scope_label", "question_id", "source_refs",
                            "source_unit", "raw_text", "qualifier_text", "relation", "reasons", "quantity_ids")
                    }]
                    overlap = next((s for s in row["segments"]
                                    if set(s["quantity_ids"]) & set(segment["quantity_ids"])), None)
                    if overlap:
                        if (set(overlap["quantity_ids"]) != set(segment["quantity_ids"])
                                or overlap["value"] != segment["value"]
                                or set(overlap["biobank_ids"]) != set(segment["biobank_ids"])):
                            raise ValueError("Partial or conflicting quantity overlap cannot form a reporting total")
                        all_dates = sorted(set(overlap["reporting_dates"] + dates))
                        qualifications = {fingerprint(item): item for item in
                            overlap["qualification_contributions"] + segment["qualification_contributions"]}
                        reasons = set(overlap.get("reasons", [])) | set(segment.get("reasons", []))
                        if segment.get("uncertain") and not overlap.get("uncertain"):
                            overlap.update(segment)
                            overlap["id"] = "uncertain-reconciled:" + fingerprint(segment["quantity_ids"])
                            overlap["reasons"] = sorted(set(segment.get("reasons", [])) | {"overlapping_display_classifications"})
                        overlap["reporting_dates"] = all_dates
                        overlap["qualification_contributions"] = [item for _, item in sorted(qualifications.items())]
                        overlap["reasons"] = sorted(set(overlap.get("reasons", [])) | reasons)
                        continue
                    existing = next((s for s in row["segments"] if s["id"] == segment["id"]), None)
                    segment["reporting_dates"] = dates
                    if existing:
                        existing["value"] += segment["value"]
                        existing["quantity_ids"] += segment["quantity_ids"]
                        existing["biobank_ids"] = sorted(set(existing["biobank_ids"] + segment["biobank_ids"]))
                        existing["reporting_dates"] = sorted(set(existing["reporting_dates"] + dates))
                        qualifications = {fingerprint(item): item for item in
                            existing["qualification_contributions"] + segment["qualification_contributions"]}
                        existing["qualification_contributions"] = [item for _, item in sorted(qualifications.items())]
                        existing["reasons"] = sorted(set(existing.get("reasons", [])) | set(segment.get("reasons", [])))
                    else:
                        row["segments"].append(segment)
        result[dimension] = [view for _, view in sorted(groups.items())]
        for view in result[dimension]:
            view["rows"].sort(key=lambda row: row["label"])
            for row in view["rows"]:
                row["confirmed_total"] = sum(s["value"] for s in row["segments"] if not s.get("uncertain"))
                row["uncertain_total"] = sum(s["value"] for s in row["segments"] if s.get("uncertain"))
                row["reported_total"] = row["confirmed_total"]
                row["display_total"] = row["confirmed_total"] + row["uncertain_total"]
    return result


def _same_reported_quantity(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    """Identify repeated source counts without merging different populations or times.

    Args:
        left: A represented exact, excluded or profile quantity with source ownership.
        right: A candidate profile/excluded quantity with unchanged source references.

    Returns:
        Whether both quantities describe the same source-local amount, proven by
        shared quantity or answer-evidence IDs. Paragraph locators and equal amounts
        alone never prove identity; different known scopes never collapse.
    """
    if any(left.get(key) != right.get(key) for key in ("biobank_id", "source_record_id", "value")):
        return False
    if left.get("scope_id") and right.get("scope_id") and left["scope_id"] != right["scope_id"]:
        return False
    refs_left = {(ref.get("source_id"), ref.get("locator")) for ref in left.get("source_refs", [])}
    refs_right = {(ref.get("source_id"), ref.get("locator")) for ref in right.get("source_refs", [])}
    overlap = bool(refs_left & refs_right)
    if left.get("unit") != right.get("unit") and not (overlap and right.get("unit") == "unit_unclear"):
        return False
    if left.get("temporal_status", "unspecified") != right.get("temporal_status", "unspecified"):
        return False
    if left.get("relation", "reported_value") != right.get("relation", "reported_value"):
        return False
    left_evidence = set(left.get("quantity_evidence_ids", []))
    right_evidence = set(right.get("quantity_evidence_ids", []))
    if left.get("evidence_id"):
        left_evidence.add(left["evidence_id"])
    if right.get("evidence_id"):
        right_evidence.add(right["evidence_id"])
    return bool(left_evidence & right_evidence or
                set(left.get("quantity_ids", [])) & set(right.get("quantity_ids", [])))


def build_reported_quantity_chart_views(
    aggregates: Mapping[str, Any], biobanks: Sequence[Mapping[str, Any]],
    definitions: Sequence[Mapping[str, Any]], profile: Mapping[str, Any],
) -> dict[str, Any]:
    """Include uncertain source counts in reporting views without changing exact totals.

    Args:
        aggregates: Audited exact country/type aggregates and excluded source quantities.
        biobanks: Selected reporting units retaining their original MuCP source records.
        definitions: Curated material/data labels; only existing scope-proven links apply.
        profile: Source-owned size inventory, including unlinked counts and unclear units.

    Returns:
        Country/type views with separate confirmed, uncertain and display widths;
        source coverage includes nonnumeric responses. Gray widths are reported
        numbers, not validated additive totals. Unknown units have separate views.

    Raises:
        ValueError: If a candidate lacks ownership, a valid unit or a finite count.
    """
    result = deepcopy(build_quantity_chart_views(aggregates, biobanks, definitions))
    result["uninterpreted_answers"] = []
    banks = {bank["biobank_id"]: bank for bank in biobanks}
    labels = {definition["id"]: definition for definition in definitions}
    represented = list(aggregates.get("contributions", []))
    covered = defaultdict(set)
    for quantity in represented:
        covered[(quantity["biobank_id"], quantity["source_record_id"])].add("confirmed")
    for dimension in ("country_views", "type_views"):
        for view in result[dimension]:
            for row in view["rows"]:
                row.update(confirmed_total=row["reported_total"], uncertain_total=0,
                           display_total=row["reported_total"])
                for segment in row["segments"]:
                    segment["uncertain"] = False

    def add_uncertain(quantity: Mapping[str, Any], reasons: Sequence[str], include_types: bool) -> None:
        """Append an attributed gray amount to compatible reporting-only views.

        Args:
            quantity: One deduplicated source-owned count, not an aggregate guess.
            reasons: All retained reasons the amount cannot enter confirmed totals.
            include_types: Whether source-proven type links may create type segments.

        Returns:
            None. Updates detached views and coverage without changing input evidence.
        """
        bid, rid = quantity.get("biobank_id"), quantity.get("source_record_id")
        bank = banks.get(bid)
        if bank is None or rid not in {r["record_id"] for r in bank.get("mucp_source_records", [])}:
            raise ValueError("Uncertain quantity lacks source-record ownership")
        unit, value = quantity.get("unit"), quantity.get("value")
        if unit not in {"donors", "samples", "aliquots", "unit_unclear"} or isinstance(value, bool) \
                or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("Uncertain quantity needs a known analysis unit and finite nonnegative value")
        covered[(bid, rid)].add("uncertain")
        time = quantity.get("temporal_status", "unspecified")
        meaning = "direct" if quantity.get("basis") == "direct_modality" else "collection_context"
        qids = sorted(quantity.get("quantity_ids", [])) or ["profile:" + fingerprint(quantity)]
        dimensions = [("country_views", "Country", str(bank.get("country") or "Unknown"))]
        if include_types and unit != "unit_unclear":
            for type_id in sorted(set(quantity.get("modality_ids", []))):
                if type_id not in labels:
                    raise ValueError(f"Uncertain quantity links an unknown type: {type_id}")
                dimensions.append(("type_views", quantity_display_labels(labels[type_id])["kind"], labels[type_id]["label"]))
        for dimension, kind, label in dimensions:
            if dimension == "country_views" and meaning == "direct":
                continue  # Type-specific measurements must not become whole-bank counts.
            view = next((v for v in result[dimension] if (v["kind"], v["unit"], v["temporal_status"], v["meaning"])
                         == (kind, unit, time, meaning)), None)
            if view is None:
                view = {"kind": kind, "unit": unit, "temporal_status": time, "meaning": meaning, "rows": []}
                result[dimension].append(view)
            row = next((r for r in view["rows"] if r["label"] == label), None)
            if row is None:
                row = {"label": label, "reported_total": 0, "confirmed_total": 0,
                       "uncertain_total": 0, "display_total": 0, "segments": []}
                view["rows"].append(row)
            if any(set(qids) & set(segment["quantity_ids"]) for segment in row["segments"]):
                continue
            sid = "uncertain:" + fingerprint([bid, rid, quantity.get("scope_id"), unit, value,
                                              quantity.get("relation"), time, qids])
            row["segments"].append({"id": sid, "value": value, "quantity_ids": qids, "biobank_ids": [bid],
                "uncertain": True, "source_record_id": rid, "scope_id": quantity.get("scope_id"),
                "relation": quantity.get("relation", "reported_value"), "reasons": sorted(set(reasons)),
                "source_refs": deepcopy(quantity.get("source_refs", [])), "raw_text": quantity.get("raw_text"),
                "qualifier_text": quantity.get("qualifier_text"), "question_id": quantity.get("question_id"),
                "scope_label": quantity.get("scope_label"), "source_unit": quantity.get("source_unit")})
            row["uncertain_total"] += value
            row["display_total"] += value
    excluded_groups = []
    for quantity in aggregates.get("excluded_contributions", []):
        previous = next((entry for entry in excluded_groups if _same_reported_quantity(entry[0], quantity)), None)
        if previous is not None:
            previous[1].add(quantity.get("reason", "unconfirmed"))
            previous[0]["modality_ids"] = sorted(set(previous[0].get("modality_ids", [])) | set(quantity.get("modality_ids", [])))
            previous[0]["quantity_ids"] = sorted(set(previous[0].get("quantity_ids", [])) | set(quantity.get("quantity_ids", [])))
        else:
            excluded_groups.append([deepcopy(quantity), {quantity.get("reason", "unconfirmed")}])
    for quantity, reasons in excluded_groups:
        add_uncertain(quantity, sorted(reasons), True)
        represented.append(quantity)
    for unit, summary in profile.get("sizes", {}).items():
        for source_quantity in summary.get("rows", []):
            quantity = deepcopy(source_quantity)
            bank = banks.get(quantity.get("biobank_id"), {})
            record = next((r for r in bank.get("mucp_source_records", [])
                           if r["record_id"] == quantity.get("source_record_id")), {})
            for reviewed in record.get("metadata", {}).get("reviewed_quantities", []):
                # The profile copies the hash-bound reviewed measurement; its
                # scope display label alone can differ from the source label.
                if all(quantity.get(key) == value for key, value in reviewed.items() if key != "scope_label"):
                    quantity["evidence_id"] = "reviewed_quantity:" + fingerprint(reviewed)
            if any(_same_reported_quantity(q, quantity) for q in represented):
                continue
            if quantity.get("kind") == "numeric_mention_not_additive":
                # This inventory contains ages, dates and code fragments as well
                # as counts. Keep the source answer visible, never invent widths.
                result["uninterpreted_answers"].append(deepcopy(quantity))
                covered[(quantity["biobank_id"], quantity["source_record_id"])].add("answer_inventory")
                continue
            reason = "unit_or_interpretation_unclear" if unit == "unit_unclear" else "not_in_confirmed_totals"
            add_uncertain(quantity, [reason], False)
            represented.append(quantity)
    for dimension in ("country_views", "type_views"):
        result[dimension].sort(key=lambda view: (view["kind"], view["unit"], view["temporal_status"], view["meaning"]))
        for view in result[dimension]:
            view["rows"].sort(key=lambda row: row["label"])
            for row in view["rows"]:
                row["segments"].sort(key=lambda segment: (segment["uncertain"], segment["id"]))
    result["source_coverage"] = [{"biobank_id": bank["biobank_id"], "source_record_id": record["record_id"],
        "country": bank.get("country") or "Unknown", "institution": bank.get("name") or bank["biobank_id"],
        "status": ("counts_displayed" if covered[(bank["biobank_id"], record["record_id"])] & {"confirmed", "uncertain"}
                   else "numeric_answer_needs_interpretation" if "answer_inventory" in covered[(bank["biobank_id"], record["record_id"])]
                   else "count_not_reported"),
        "representations": sorted(covered[(bank["biobank_id"], record["record_id"])])}
        for bank in sorted(biobanks, key=lambda b: (b.get("country") or "Unknown", b["biobank_id"]))
        for record in sorted(bank.get("mucp_source_records", []), key=lambda r: r["record_id"])]
    return result


def quantity_display_labels(definition: Mapping[str, Any]) -> dict[str, str]:
    """Name a quantity definition according to materials versus data.

    Args:
        definition: Registry definition with biospecimen or data_modality kind.

    Returns:
        Reader-facing kind label and optional original type label.

    Raises:
        ValueError: If an explicitly supplied registry kind is unsupported.
    """
    kind = definition.get("kind", "biospecimen")
    if kind not in {"biospecimen", "data_modality"}:
        raise ValueError(f"Unsupported quantity definition kind: {kind!r}")
    return {"kind": "Material type" if kind == "biospecimen" else "Data type",
            "label": str(definition.get("label", ""))}


def build_quantity_chart_views(aggregates: Mapping[str, Any], biobanks: Sequence[Mapping[str, Any]],
                               definitions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Pool compatible, already reconciled exact totals into country and type charts.

    Args:
        aggregates: Audited country/type totals containing exact biobank segments.
        biobanks: Owning bank records supplying canonical countries and human names.
        definitions: Material/data definitions carrying IDs, labels and kinds.

    Returns:
        Country and type view lists with unit/time/meaning, totals and attributed segments.
        Excluded evidence remains unchanged and is never used to create segments.

    Raises:
        ValueError: If attribution is missing/duplicated or arithmetic is inconsistent.
    """
    banks = {bank["biobank_id"]: bank for bank in biobanks}
    labels = {definition["id"]: definition for definition in definitions}
    grouped = defaultdict(dict)
    seen = set()
    bank_bases = defaultdict(set)
    for dimension, totals in (("country", aggregates.get("country_totals", [])),
                               ("type", aggregates.get("modality_totals", []))):
        for total in totals:
            if total.get("reported_total") is None or not total.get("segments"):
                continue
            unit, basis = total["unit"], total["basis"]
            if unit not in {"donors", "samples", "aliquots"}:
                raise ValueError("Charts require known donor/sample/aliquot units")
            meaning = "direct" if basis == "direct_modality" else "collection_context"
            if dimension == "country" and meaning == "direct":
                continue
            type_id = total.get("modality_id")
            if dimension == "type" and type_id not in labels:
                raise ValueError(f"Unknown chart type: {type_id}")
            kind = quantity_display_labels(labels[type_id])["kind"] if dimension == "type" else "Country"
            key = (dimension, kind, unit, total.get("temporal_status", "unspecified"), meaning)
            label = labels[type_id]["label"] if dimension == "type" else total["country"]
            row = grouped[key].setdefault(label, {"label": label, "reported_total": 0, "segments": {}})
            if sum(segment["value"] for segment in total["segments"]) != total["reported_total"]:
                raise ValueError("Quantity total disagrees with attributed segments")
            for segment in total["segments"]:
                bank_id = segment["biobank_id"]
                if bank_id not in banks or not segment.get("quantity_ids"):
                    raise ValueError("Quantity segment lacks source/bank attribution")
                basis_key = (key, label, bank_id)
                bank_bases[basis_key].add(basis)
                if {"collection", "submission_fallback"} <= bank_bases[basis_key]:
                    raise ValueError("overlapping collection and whole-biobank fallback attribution")
                for qid in segment["quantity_ids"]:
                    identity = (key, label, bank_id, qid)
                    if identity in seen:
                        raise ValueError("duplicate or overlapping quantity attribution")
                    seen.add(identity)
                segment_id = str(banks[bank_id].get("country") or "Unknown") if dimension == "type" else bank_id
                entry = row["segments"].setdefault(segment_id, {"id": segment_id, "value": 0, "quantity_ids": [], "biobank_ids": []})
                entry["value"] += segment["value"]
                entry["quantity_ids"].extend(segment["quantity_ids"])
                entry["biobank_ids"].append(bank_id)
                row["reported_total"] += segment["value"]
    result = {"country_views": [], "type_views": [], "excluded_contributions": aggregates.get("excluded_contributions", [])}
    for key, rows in sorted(grouped.items()):
        prepared = []
        for label, row in sorted(rows.items()):
            segments = []
            for _, segment in sorted(row["segments"].items()):
                segments.append({**segment, "quantity_ids": sorted(set(segment["quantity_ids"])),
                                 "biobank_ids": sorted(set(segment["biobank_ids"]))})
            prepared.append({**row, "segments": segments})
        result["country_views" if key[0] == "country" else "type_views"].append({
            "kind": key[1], "unit": key[2], "temporal_status": key[3], "meaning": key[4], "rows": prepared})
    return result
