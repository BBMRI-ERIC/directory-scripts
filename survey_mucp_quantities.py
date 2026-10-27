"""Extract source-proven MuCP modality quantities without allocating scope totals."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
import re
from typing import Any

from survey_mucp_aggregation import canonical_quantity_unit
from survey_evidence import EvidenceItem, fingerprint, plain


_UNITS = {"sample": "samples", "samples": "samples", "donor": "donors",
          "donors": "donors", "individual": "individuals", "individuals": "individuals",
          "participant": "participants", "participants": "participants",
          "research participant": "participants", "research participants": "participants",
          "aliquot": "aliquots", "aliquots": "aliquots"}
_RELATIONS = {"over": "greater_than", "more than": "greater_than", ">": "greater_than",
              "at least": "at_least", ">=": "at_least", "less than": "less_than",
              "<": "less_than", "at most": "at_most", "<=": "at_most",
              "about": "approximate", "approximately": "approximate", "approx.": "approximate",
              "~": "approximate"}
_INTEGER = r"(?:0|[1-9][0-9]*|[1-9][0-9]{0,2}(?:,[0-9]{3})+|[1-9][0-9]{0,2}(?:\.[0-9]{3})+|[1-9][0-9]{0,2}(?: [0-9]{3})+)"
_PREFIX = r"(?:(more than|less than|at least|at most|approximately|approx\.|over|about)\s+|(>=|<=|>|<|~)\s*)?"
_MEASUREMENT = re.compile(rf"^{_PREFIX}({_INTEGER})\s+(sample|samples|donor|donors|individual|individuals|participant|participants|research\s+participants?|aliquot|aliquots)$", re.I)
_NUMBER = re.compile(rf"^{_PREFIX}({_INTEGER})$", re.I)
_TABLE_LOCATOR = re.compile(r"^table\[([1-9][0-9]*)\]:row\[([1-9][0-9]*)\]:cell\[([1-9][0-9]*)\]$")
_ALLOWED_QUESTIONS = frozenset({
    "B.biospecimens.dna", "C.biospecimens.non_dna_available", "C.biospecimens.serum",
    "C.biospecimens.plasma", "C.biospecimens.pbmcs", "C.biospecimens.urine",
    "C.biospecimens.tissue", "C.biospecimens.rna", "C.biospecimens.proteins",
    "C.biospecimens.exosomes", "C.biospecimens.microbiome", "C.biospecimens.other",
    "C.biospecimens.repeated_samples", "C.omics_data.omics_data_available",
    "C.omics_data.gwas", "C.omics_data.wgs", "C.omics_data.wes", "C.omics_data.rna_seq",
    "C.omics_data.proteomics", "C.omics_data.metabolomics", "C.omics_data.exposomics",
    "C.omics_data.other", "C.available_data.medication_treatment",
    "C.available_data.clinical_laboratory", "C.available_data.longitudinal_outcomes",
    "C.available_data.link_health_databases", "C.available_data.lifestyle",
    "C.available_data.environmental_exposure", "C.available_data.real_world_data",
    "C.available_data.proms", "C.available_data.digital_wearables",
    "C.available_data.imaging", "C.available_data.functional_assays",
})
_NONCONCRETE = frozenset({"C.omics_data.omics_data_available", "C.omics_data.other",
                          "C.biospecimens.non_dna_available", "C.biospecimens.other",
                          "C.biospecimens.repeated_samples",
                          "C.available_data.link_health_databases"})


def _measurement(text: Any, numeric_only: bool = False) -> dict[str, Any] | None:
    """Parse a whole, source-authored number and optional unit.

    Args:
        text: Unchanged projected source wording to parse without substring mining.
        numeric_only: Permit a missing unit solely when separate count metadata proves it.

    Returns:
        Parsed value/relation/unit, or None when the entire wording is unsupported.
    """
    if not isinstance(text, str):
        return None
    normalized = re.sub(r"\s+", " ", text.strip()).rstrip(".")
    suffix_bound = normalized.endswith("+")
    if suffix_bound:
        normalized = normalized[:-1].strip()
    scale = 1
    million = re.fullmatch(rf"{_PREFIX}({_INTEGER})\s+(?:mio|million)(\s+.*)?", normalized, re.I)
    if million is not None:
        scale = 1000000
        normalized = "".join([((million.group(1) or million.group(2)) + " ")
                              if million.group(1) or million.group(2) else "",
                              million.group(3), million.group(4) or ""])
    match = (_NUMBER if numeric_only else _MEASUREMENT).fullmatch(normalized)
    if match is None:
        return None
    relation = _RELATIONS.get((match.group(1) or match.group(2) or "").lower(), "reported_value")
    if suffix_bound:
        if relation != "reported_value":
            return None
        relation = "at_least"
    source_unit = None if numeric_only else match.group(4)
    return {**({"source_suffix_bound": True} if suffix_bound else {}),
            "value": int(match.group(3).replace(",", "").replace(".", "").replace(" ", "")) * scale,
            "relation": relation, "unit": None if numeric_only else _UNITS[source_unit.lower()],
            "source_unit": source_unit}


def _count_source_parts(text: Any) -> tuple[str, str] | None:
    """Separate an explicitly labelled count time from its complete source wording.

    Args:
        text: Literal count cell, count field or unit header, without narrative mining.

    Returns:
        Remaining count/header wording and a source-proven time category, or None
        for conflicting labels. Unlabelled wording retains unspecified time.
    """
    if not isinstance(text, str):
        return None
    wording = re.sub(r"\s+", " ", text.strip())
    temporal = "unspecified"
    categories = "current|future|historical|cumulative|previous"
    prefix = re.fullmatch(rf"({categories})\s*:\s*(.+)", wording, re.I)
    if prefix:
        temporal, wording = prefix.group(1).lower(), prefix.group(2)
    suffix = re.fullmatch(rf"(.+?)\s+\(({categories})\)", wording, re.I)
    if suffix:
        if temporal not in {"unspecified", suffix.group(2).lower()}:
            return None
        wording, temporal = suffix.group(1), suffix.group(2).lower()
    return wording, temporal


def _count_measurement(text: Any, numeric_only: bool = False) -> dict[str, Any] | None:
    """Parse one complete context count with an explicit optional time label.

    Args:
        text: Source count field or cell with literal units or separate unit proof.
        numeric_only: Permit a missing unit when the caller validates its header/metadata.

    Returns:
        Source-derived amount, relation, unit and time, or None for unsupported text.
    """
    parts = _count_source_parts(text)
    if parts is None:
        return None
    parsed = _measurement(parts[0], numeric_only)
    return {**parsed, "temporal_status": parts[1]} if parsed is not None else None


def _definitions(definitions: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Validate public modality definitions without deriving unlisted prefixes.

    Args:
        definitions: Curated public concrete-question to modality mappings.

    Returns:
        Detached definitions in their caller-supplied stable order.
    """
    result = []
    ids: set[str] = set()
    questions: set[str] = set()
    for raw in definitions:
        if not isinstance(raw, Mapping) or set(raw) != {"id", "label", "question_id", "kind", "qualifier_measurement"}:
            raise ValueError("Invalid modality definition fields")
        item = dict(raw)
        if any(not isinstance(item[key], str) or not item[key].strip() for key in item):
            raise ValueError("Modality definitions need nonblank text fields")
        if item["id"] in ids or item["question_id"] in questions:
            raise ValueError("Duplicate modality ID or question")
        if item["question_id"] not in _ALLOWED_QUESTIONS or item["kind"] not in {"data_modality", "biospecimen"}:
            raise ValueError("Modality definition is not a known concrete MuCP question")
        if item["qualifier_measurement"] not in {"whole", "curated_only"} or (item["question_id"] in _NONCONCRETE and item["qualifier_measurement"] != "curated_only"):
            raise ValueError("Aggregate, permission and Other questions require curated-only measurement")
        ids.add(item["id"])
        questions.add(item["question_id"])
        result.append(item)
    return result


def _owned_records(bank: Mapping[str, Any]) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]], list[Mapping[str, Any]]]:
    """Validate native MuCP evidence, response, scope and source-ref ownership.

    Args:
        bank: One combined biobank retaining native evidence and projected source records.

    Returns:
        Record map, scope map and native MuCP evidence in original order.
    """
    records = {item["record_id"]: item for item in bank.get("mucp_source_records", [])}
    if len(records) != len(bank.get("mucp_source_records", [])):
        raise ValueError("Duplicate MuCP source record ID")
    scopes = bank.get("scopes", {})
    if not isinstance(scopes, Mapping):
        raise ValueError("Combined scopes must be a mapping")
    evidence = [item for item in bank.get("evidence", []) if item.get("survey") == "MuCP"]
    ids: set[str] = set()
    for item in evidence:
        EvidenceItem(item)
        eid = item["evidence_id"]
        if eid in ids:
            raise ValueError(f"Duplicate native MuCP evidence ID: {eid}")
        ids.add(eid)
        record = records.get(item["source_record_id"])
        scope = scopes.get(item["scope_id"])
        if record is None or scope is None or scope.get("source_record_id") != item["source_record_id"]:
            raise ValueError(f"Dangling MuCP record or scope: {eid}")
        source_ids = set(record.get("metadata", {}).get("source_ids", []))
        for ref in item["source_refs"]:
            if ref.get("source_id") and ref["source_id"] not in source_ids:
                raise ValueError(f"Foreign MuCP source reference: {eid}")
    return records, dict(scopes), evidence


def _unlinked(bank_id: str, record_id: Any, scope_id: Any, question_id: Any,
              evidence_id: Any, refs: Any, wording: Any, reason: str) -> dict[str, Any]:
    """Retain a rejected candidate with a stable reason and source identity.

    Args:
        bank_id: Directory biobank ID.
        record_id: Projected source response ID.
        scope_id: Projected source scope ID.
        question_id: Source question ID or None for a scope count.
        evidence_id: Native or projected quantity evidence ID.
        refs: Existing source references, never fabricated.
        wording: Original projected wording or None.
        reason: Controlled reason why no plotted amount was accepted.

    Returns:
        Serializable unlinked-candidate mapping.
    """
    return {"candidate_id": fingerprint([bank_id, record_id, scope_id, question_id, evidence_id, refs, wording]),
            "biobank_id": bank_id, "source_record_id": record_id, "scope_id": scope_id,
            "question_id": question_id, "evidence_id": evidence_id, "source_refs": plain(refs or []),
            "original_wording": wording, "reason": reason}


def _links(evidence: Sequence[Mapping[str, Any]], definitions: Sequence[Mapping[str, str]],
           record_id: str, scope_id: str) -> list[dict[str, Any]]:
    """Find affirmed concrete evidence in exactly one source record and scope.

    Args:
        evidence: Validated native MuCP evidence.
        definitions: Validated public modality definitions.
        record_id: Source response owning the quantity.
        scope_id: Exact scope owning the quantity.

    Returns:
        Distinct modality evidence links without scope inheritance.
    """
    by_question = {item["question_id"]: item for item in definitions}
    return [{"modality_id": by_question[item["question_id"]]["id"],
             "question_id": item["question_id"], "evidence_id": item["evidence_id"],
             "source_refs": plain(item["source_refs"])} for item in evidence
            if item["source_record_id"] == record_id and item["scope_id"] == scope_id
            and item["kind"] == "structured_answer" and item.get("normalized_value") == "affirmed"
            and item["question_id"] in by_question
            and by_question[item["question_id"]]["qualifier_measurement"] == "whole"]


def _table_witness(record: Mapping[str, Any], ref: Mapping[str, Any], value: int) -> dict[str, Any] | None:
    """Prove a count unit from one unambiguous table cell and literal header.

    Args:
        record: Source record containing the structured table snapshot.
        ref: Count-field locator referring to the exact table cell.
        value: Independently typed count amount to compare with the cell.

    Returns:
        Header-based unit proof, or None when the grid/locator is ambiguous.
    """
    match = _TABLE_LOCATOR.fullmatch(str(ref.get("locator", "")))
    if match is None:
        return None
    table_number, row_number, column_number = map(int, match.groups())
    tables = record.get("metadata", {}).get("structured_tables", [])
    matching = [table for table in tables if table.get("index") == table_number - 1]
    if len(matching) != 1:
        return None
    rows = matching[0].get("rows", [])
    if row_number > len(rows) or row_number < 2:
        return None
    row = rows[row_number - 1]
    if column_number > len(row):
        return None
    cell = row[column_number - 1]
    if any(str(item.get("xml_grid_span") or "1") != "1" for item in row):
        return None
    parsed = _count_measurement(cell.get("text"), numeric_only=True)
    if parsed is None:
        parsed = _count_measurement(cell.get("text"))
    if parsed is None or parsed["value"] != value:
        return None
    headers = []
    for previous in rows[:row_number - 1]:
        if len(previous) != len(row) or any(str(item.get("xml_grid_span") or "1") != "1" for item in previous):
            continue
        headers.append(str(previous[column_number - 1].get("text", "")).strip())
    proven = []
    for header in headers:
        parts = _count_source_parts(header)
        if parts is None:
            continue
        unit_match = re.fullmatch(r"(?:(?:num\.|number of)\s+)?(samples?|donors?|individuals?|participants?|research\s+participants?|aliquots?)",
                                 parts[0], re.I)
        if unit_match:
            proven.append((header, _UNITS[unit_match.group(1).lower()], parts[1], unit_match.group(1)))
    if len(proven) != 1:
        return None
    header, unit, header_time, literal_header_unit = proven[0]
    if parsed["unit"] not in {None, unit}:
        return None
    cell_time = parsed["temporal_status"]
    if cell_time != "unspecified" and header_time not in {"unspecified", cell_time}:
        return None
    temporal = cell_time if cell_time != "unspecified" else header_time
    return {"kind": "table_header", "value": parsed["value"], "relation": parsed["relation"],
            "unit": unit, "source_unit": parsed.get("source_unit") or literal_header_unit,
            "temporal_status": temporal, "header": header, "cell_text": cell.get("text"),
            "locator": ref["locator"], "source_id": ref.get("source_id")}


def _typed_total(total: Any, witness: Mapping[str, Any], canonical_person_units: bool = False) -> bool:
    """Check a projected total against source-proven amount, relation and unit.

    Args:
        total: Projected reported_total mapping, which cannot prove itself.
        witness: Parsed source wording or table-header witness.
        canonical_person_units: Accept synonymous person units only for the B/C
            individual-count questions; table/header comparisons remain literal.
            These fields also accept a literal trailing-plus lower bound when the
            projection omitted it, never an exact value overriding a source bound.

    Returns:
        True only when unit, amount, relation and explicitly witnessed time agree.
    """
    return (isinstance(total, Mapping) and type(total.get("value")) is int and total["value"] >= 0
            and total["value"] == witness["value"]
            and (total.get("unit") == witness["unit"] or canonical_person_units
                 and canonical_quantity_unit(total.get("unit")) == "donors"
                 and canonical_quantity_unit(witness["unit"]) == "donors")
            and (total.get("relation", "reported_value") == witness["relation"]
                 or canonical_person_units and witness.get("source_suffix_bound") is True
                 and witness["relation"] == "at_least" and total.get("relation", "reported_value") == "reported_value")
            and total.get("temporal_status", "unspecified") == witness.get("temporal_status", "unspecified"))


def verified_collection_count(scope: Mapping[str, Any], record: Mapping[str, Any]) -> dict[str, Any] | None:
    """Verify a collection quantity against its owned literal field/table witness.

    Args:
        scope: Collection scope carrying count metadata and source references.
        record: Owning MuCP response with declared sources and structured tables.

    Returns:
        Source-proven value, relation, literal unit, time, wording and references;
        None when ownership, units, values or source witnesses are unproven.
    """
    if scope.get("kind") != "collection" or scope.get("source_record_id") != record.get("record_id"):
        return None
    count = scope.get("metadata", {}).get("count", {})
    total = count.get("reported_total") if isinstance(count, Mapping) else None
    if not isinstance(total, Mapping):
        return None
    refs = count.get("evidence", [])
    if not refs or any(not isinstance(ref, Mapping) or not ref.get("locator")
                       or (not ref.get("source_id") and not ref.get("path"))
                       or (ref.get("source_id") and ref["source_id"] not in
                           set(record.get("metadata", {}).get("source_ids", []))) for ref in refs):
        return None
    parsed = _count_measurement(count.get("raw_text"))
    proof = {"kind": "literal_count_field", **parsed,
             "source_text": count.get("raw_text")} if parsed else None
    wording = count.get("raw_text")
    table_refs = [ref for ref in refs if _TABLE_LOCATOR.fullmatch(str(ref.get("locator", "")))]
    if table_refs:
        parsed = proof = None
        if type(total.get("value")) is int:
            witnesses = [_table_witness(record, ref, total["value"]) for ref in table_refs]
            keys = ("value", "unit", "relation", "temporal_status")
            if all(witness is not None for witness in witnesses) and len({
                    tuple(witness[key] for key in keys) for witness in witnesses}) == 1:
                proof = witnesses[0]
                parsed = {key: proof[key] for key in (*keys, "source_unit")}
                wording = proof["cell_text"]
    if parsed is None or not _typed_total(total, parsed):
        return None
    return {**parsed, "unit_proof": proof, "original_wording": wording,
            "source_refs": plain(refs)}


def extract_modality_quantities(
    biobanks: Sequence[Mapping[str, Any]], modality_definitions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Extract direct measurements and separately labelled scope-size context.

    Args:
        biobanks: Unique overlapping combined biobanks with native MuCP evidence.
        modality_definitions: Public, validated concrete-question modality metadata.

    Returns:
        Deterministic observations, coverage, unlinked candidates and interpretation;
        derived person units use ``donors`` with a separate literal ``source_unit``;
        no result allocates a scope count to its modality links or sums measurements.
    """
    definitions = _definitions(modality_definitions)
    by_question = {item["question_id"]: item for item in definitions}
    observations: list[dict[str, Any]] = []
    unlinked: list[dict[str, Any]] = []
    bank_ids: set[str] = set()
    for bank in biobanks:
        bid = bank.get("biobank_id")
        if not isinstance(bid, str) or not bid or bid in bank_ids:
            raise ValueError("Duplicate or missing combined biobank ID")
        bank_ids.add(bid)
        country = bank.get("country") or "unknown"
        records, scopes, evidence = _owned_records(bank)
        reviewed_keys = set()
        for record in records.values():
            for quantity in record.get("metadata", {}).get("reviewed_quantities", []):
                scope_id = quantity["scope_id"]
                scope = scopes.get(scope_id)
                if scope is None or scope.get("source_record_id") != record["record_id"]:
                    raise ValueError("Reviewed quantity references another record's scope")
                reviewed_keys.add((record["record_id"], scope_id, quantity.get("source_field")))
                if quantity["unit"] not in {"samples", "donors"}:
                    continue
                links = _links(evidence, definitions, record["record_id"], scope_id)
                if not links:
                    continue
                refs = plain(quantity["source_refs"])
                eid = "reviewed_quantity:" + fingerprint(quantity)
                observations.append({"quantity_id": fingerprint([bid, eid]), "biobank_id": bid,
                    "country": country, "source_record_id": record["record_id"], "question_id": quantity.get("question_id"),
                    "scope_id": scope_id, "collection_id": scope.get("collection_id"),
                    "value": quantity["value"], "relation": quantity["relation"], "unit": quantity["unit"],
                    "source_unit": quantity["source_unit"], "temporal_status": quantity["temporal_status"],
                    "linkage": "collection_size_context" if scope.get("kind") == "collection" else "submission_size_context",
                    "linkage_basis": "source_hash_bound_independently_reviewed_count",
                    "quantity_evidence_id": eid, "quantity_locator": refs[0]["locator"],
                    "original_wording": quantity["original_wording"], "source_refs": refs,
                    "unit_proof": {"kind": "source_hash_bound_review", "unit": quantity["unit"],
                                   "basis": quantity["basis"], "explanation": quantity.get("explanation")},
                    "modality_links": links})
        for item in evidence:
            qid = item["question_id"]
            definition = by_question.get(qid)
            if item.get("extensions", {}).get("modality_quantity_bindings"):
                raise ValueError("Curated modality quantity bindings require a separately validated implementation")
            if definition is not None and item["kind"] == "structured_answer" and item.get("normalized_value") == "affirmed" and item.get("qualifier_text"):
                parsed = _measurement(item["qualifier_text"]) if definition["qualifier_measurement"] == "whole" else None
                if parsed is None:
                    unlinked.append(_unlinked(bid, item["source_record_id"], item["scope_id"], qid,
                                              item["evidence_id"], item["source_refs"], item["qualifier_text"],
                                              "unsupported_qualifier" if definition["qualifier_measurement"] == "whole" else "no_explicit_link"))
                else:
                    observations.append({"quantity_id": fingerprint([bid, item["source_record_id"], item["evidence_id"], item["source_refs"]]),
                        "biobank_id": bid, "country": country, "source_record_id": item["source_record_id"],
                        "question_id": qid, "scope_id": item["scope_id"], "collection_id": scopes[item["scope_id"]].get("collection_id"),
                        "value": parsed["value"], "relation": parsed["relation"],
                        "unit": canonical_quantity_unit(parsed["unit"]), "source_unit": parsed["source_unit"],
                        "temporal_status": "unspecified", "linkage": "modality_specific",
                        "linkage_basis": "affirmed_structured_answer_whole_qualifier", "quantity_evidence_id": item["evidence_id"],
                        "quantity_locator": item["source_refs"][0]["locator"],
                        "original_wording": item.get("raw_text") or item["qualifier_text"],
                        "source_refs": plain(item["source_refs"]), "unit_proof": {"kind": "literal_qualifier", "unit": parsed["unit"],
                            "source_unit": parsed["source_unit"]},
                        "modality_links": [{"modality_id": definition["id"], "question_id": qid,
                                            "evidence_id": item["evidence_id"], "source_refs": plain(item["source_refs"])}]})
            elif definition is not None and item["kind"] == "structured_answer" and item.get("normalized_value") == "affirmed":
                unlinked.append(_unlinked(bid, item["source_record_id"], item["scope_id"], qid,
                                          item["evidence_id"], item["source_refs"], item.get("qualifier_text"),
                                          "missing_quantity"))
            if qid in {"B.count", "C.count"} and item["kind"] == "text_field":
                from survey_mucp_reviewed import reviewed_quantity_covers
                total = item.get("extensions", {}).get("reported_total")
                if reviewed_quantity_covers(records[item["source_record_id"]], item, (total or {}).get("value")):
                    continue
                if (item["source_record_id"], item["scope_id"], qid) in reviewed_keys:
                    continue
                total = item.get("extensions", {}).get("reported_total")
                if total is None:
                    continue
                parsed = _count_measurement(item.get("raw_text"))
                proof = {"kind": "literal_count_field", "unit": parsed["unit"],
                         "source_text": item.get("raw_text"), "temporal_status": parsed["temporal_status"]} if parsed else None
                if parsed is None:
                    parsed = _count_measurement(item.get("raw_text"), numeric_only=True)
                    if parsed is not None:
                        parsed["unit"] = "individuals"
                        proof = {"kind": "count_question_metadata", "unit": "individuals", "question_id": qid,
                                 "source_text": item.get("raw_text"), "temporal_status": parsed["temporal_status"]}
                if parsed is None or not _typed_total(total, parsed, canonical_person_units=True):
                    unlinked.append(_unlinked(bid, item["source_record_id"], item["scope_id"], qid,
                                              item["evidence_id"], item["source_refs"], item.get("raw_text"), "missing_unit_proof"))
                    continue
                scope = scopes[item["scope_id"]]
                record_scope = next((s for s in records[item["source_record_id"]].get("scopes", [])
                                     if s.get("scope_id") == item["scope_id"]), {})
                pointer = record_scope.get("input_json_pointer")
                if scope.get("kind") != "submission" or record_scope.get("kind") != "submission" or not isinstance(pointer, str) or "/collections/" in pointer:
                    unlinked.append(_unlinked(bid, item["source_record_id"], item["scope_id"], qid,
                                              item["evidence_id"], item["source_refs"], item.get("raw_text"), "scope_mismatch"))
                    continue
                links = _links(evidence, definitions, item["source_record_id"], item["scope_id"])
                if links:
                    observations.append({"quantity_id": fingerprint([bid, item["source_record_id"], item["evidence_id"], item["source_refs"]]),
                        "biobank_id": bid, "country": country, "source_record_id": item["source_record_id"],
                        "question_id": qid, "scope_id": item["scope_id"], "collection_id": None,
                        "value": parsed["value"], "relation": parsed["relation"],
                        "unit": canonical_quantity_unit(parsed["unit"]), "source_unit": parsed["source_unit"],
                        "temporal_status": parsed["temporal_status"], "linkage": "submission_size_context",
                        "linkage_basis": "same_source_submission_only", "quantity_evidence_id": item["evidence_id"],
                        "quantity_locator": item["source_refs"][0]["locator"], "original_wording": item["raw_text"],
                        "source_refs": plain(item["source_refs"]), "unit_proof": proof, "modality_links": links})
                else:
                    unlinked.append(_unlinked(bid, item["source_record_id"], item["scope_id"], qid,
                                              item["evidence_id"], item["source_refs"], item.get("raw_text"), "no_explicit_link"))
        for scope_id, scope in scopes.items():
            if any(key[:2] == (scope.get("source_record_id"), scope_id) for key in reviewed_keys):
                continue
            if scope.get("kind") != "collection" or scope.get("source_record_id") not in records:
                continue
            count = scope.get("metadata", {}).get("count", {})
            total = count.get("reported_total") if isinstance(count, Mapping) else None
            if total is None:
                continue
            record_id = scope["source_record_id"]
            refs = count.get("evidence", [])
            for ref in refs:
                if not isinstance(ref, Mapping) or not ref.get("locator") or (not ref.get("source_id") and not ref.get("path")) or (ref.get("source_id") and ref["source_id"] not in set(records[record_id].get("metadata", {}).get("source_ids", []))):
                    raise ValueError("Collection count has foreign or malformed source reference")
            parsed = verified_collection_count(scope, records[record_id])
            proof = parsed["unit_proof"] if parsed else None
            original_wording = parsed["original_wording"] if parsed else count.get("raw_text")
            eid = "projected_scope_count:" + fingerprint([bid, record_id, scope_id, refs])
            if parsed is None or not _typed_total(total, parsed) or not refs:
                unlinked.append(_unlinked(bid, record_id, scope_id, None, eid, refs, count.get("raw_text"), "missing_unit_proof"))
                continue
            links = _links(evidence, definitions, record_id, scope_id)
            if not links:
                unlinked.append(_unlinked(bid, record_id, scope_id, None, eid, refs, count.get("raw_text"), "scope_mismatch"))
                continue
            observations.append({"quantity_id": fingerprint([bid, record_id, scope_id, refs]),
                "biobank_id": bid, "country": country, "source_record_id": record_id, "question_id": None,
                "scope_id": scope_id, "collection_id": scope.get("collection_id"),
                "value": parsed["value"], "relation": parsed["relation"],
                "unit": canonical_quantity_unit(parsed["unit"]), "source_unit": parsed.get("source_unit") or parsed["unit"],
                "temporal_status": parsed["temporal_status"],
                "linkage": "collection_size_context",
                "linkage_basis": "same_owned_collection_scope_only", "quantity_evidence_id": eid,
                "quantity_locator": refs[0]["locator"], "original_wording": original_wording,
                "source_refs": plain(refs), "unit_proof": proof, "modality_links": links})
        for record in records.values():
            for index, candidate in enumerate(record.get("metadata", {}).get("quantity_index", [])):
                unlinked.append({**_unlinked(bid, record["record_id"], None, candidate.get("field"),
                                  f"unverified_index:{record['record_id']}:{index}", candidate.get("evidence", []),
                                  candidate.get("raw_token"), "no_explicit_link"),
                                 "unverified_index": plain(candidate)})
    observations.sort(key=lambda row: (str(row["country"]), row["biobank_id"], row["source_record_id"],
                                       row["scope_id"], row["quantity_id"]))
    unlinked.sort(key=lambda row: (row["biobank_id"], str(row["source_record_id"]),
                                   str(row["scope_id"]), row["candidate_id"]))
    by_modality = []
    for definition in definitions:
        unit_rows = []
        for unit in ("samples", "aliquots", "donors"):
            for linkage in ("modality_specific", "collection_size_context", "submission_size_context"):
                matched = [row for row in observations if row["unit"] == unit and row["linkage"] == linkage
                           and any(link["modality_id"] == definition["id"] for link in row["modality_links"])]
                present = {row["biobank_id"] for row in matched}
                unit_rows.append({"unit": unit, "linkage": linkage, "point_count": len(matched),
                                  "biobanks_with_source_points": len(present),
                                  "biobanks_without_eligible_points": len(bank_ids - present)})
        by_modality.append({"modality_id": definition["id"], "by_unit": unit_rows})
    return {"observations": observations, "coverage": {"cohort_N": len(bank_ids), "by_modality": by_modality},
            "unlinked_quantities": unlinked,
            "interpretation": {"grammar_version": "whole-qualifier-v1", "country_facet": "Directory biobank reported country, not donor residence or cohort origin",
                               "units": "Verified donors, individuals and participants share the donor analysis unit; source_unit preserves literal wording. Samples and aliquots remain distinct.",
                               "additivity": "No country, modality, scope or Part B/C totals; no sibling or parent inheritance",
                               "context": "Collection/submission sizes describe the reporting scope, not modality coverage"}}
