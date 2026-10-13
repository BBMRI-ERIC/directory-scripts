"""Shared MuCP quantity-unit and source-answer provenance primitives."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections import defaultdict
from typing import Any

from survey_evidence import plain


_EXACT_RELATION = "reported_value"
_ELIGIBLE_TIMES = frozenset({"unspecified", "current"})


_PERSON_UNITS = frozenset({"donor", "donors", "individual", "individuals",
                           "participant", "participants", "research participant",
                           "research participants"})
_SAMPLE_UNITS = frozenset({"sample", "samples"})
_ALIQUOT_UNITS = frozenset({"aliquot", "aliquots"})


def canonical_quantity_unit(unit: str | None) -> str:
    """Map supported source unit labels to the analysis unit without guessing.

    Args:
        unit: Literal or source-normalized unit label. ``None`` represents absent
            unit evidence; unsupported labels are deliberately not coerced.

    Returns:
        ``donors`` for donor/individual/participant synonyms, ``samples`` or
        ``aliquots`` for those distinct material units, otherwise ``unit_unclear``.
    """
    if not isinstance(unit, str):
        return "unit_unclear"
    normalized = " ".join(unit.casefold().split())
    if normalized in _PERSON_UNITS:
        return "donors"
    if normalized in _SAMPLE_UNITS:
        return "samples"
    if normalized in _ALIQUOT_UNITS:
        return "aliquots"
    return "unit_unclear"


def _reference_keys(refs: Any, source_ids: set[str]) -> tuple[set[tuple[str, str]], bool]:
    """Validate source references and return their source-ID/locator identities.

    Args:
        refs: Source reference sequence attached to an index mention or evidence item.
        source_ids: IDs declared by the projected source record metadata.

    Returns:
        Reference identity pairs and a flag indicating an undeclared source ID or
        malformed reference. No locator interpretation is invented.
    """
    if not isinstance(refs, Sequence) or isinstance(refs, (str, bytes)) or not refs:
        return set(), True
    identities = set()
    invalid = False
    for ref in refs:
        if not isinstance(ref, Mapping):
            invalid = True
            continue
        source_id, locator = ref.get("source_id"), ref.get("locator")
        if not isinstance(source_id, str) or source_id not in source_ids or not isinstance(locator, str) or not locator:
            invalid = True
            continue
        identities.add((source_id, locator))
    return identities, invalid


def recover_quantity_answer(record: Mapping[str, Any], mention: Mapping[str, Any]) -> dict[str, Any]:
    """Recover one complete quantity answer from its explicitly owned raw source.

    Args:
        record: Projected MuCP source record containing text-field evidence and
            source IDs declared in its metadata.
        mention: Quantity-index item with a source field and evidence locators. Its
            clipped context and classified unit are not accepted as source proof.

    Returns:
        A detached mapping with full ``answer_text``, source question/reference IDs,
        canonical and literal units when the complete answer proves one and agrees
        with the mention's integer, relation and time. Conflicting quantities retain
        readable text with ``unit_unclear`` and a diagnostic. Sequence references,
        including tuples, are accepted without modifying input evidence.
    """
    question_id = mention.get("field")
    refs = mention.get("evidence", [])
    copied_refs = plain(list(refs)) if isinstance(refs, Sequence) and not isinstance(refs, (str, bytes)) else []
    base = {"answer_text": None, "source_question_id": question_id if isinstance(question_id, str) else None,
            "source_refs": copied_refs, "unit": "unit_unclear", "source_unit": None,
            "unit_basis": None, "diagnostic": None}
    if not isinstance(question_id, str) or not question_id:
        base["diagnostic"] = "missing_source_question_id"
        return base
    metadata = record.get("metadata")
    source_ids = metadata.get("source_ids") if isinstance(metadata, Mapping) else None
    if (not isinstance(source_ids, Sequence) or isinstance(source_ids, (str, bytes))
            or any(not isinstance(value, str) or not value for value in source_ids)):
        base["diagnostic"] = "declared_source_ids_unavailable"
        return base
    if not isinstance(refs, Sequence) or isinstance(refs, (str, bytes)) or not refs:
        base["diagnostic"] = "source_reference_unavailable"
        return base
    declared_ids = set(source_ids)
    mention_keys, invalid_mention_refs = _reference_keys(refs, declared_ids)
    if invalid_mention_refs:
        base["diagnostic"] = "invalid_or_foreign_source_reference"
        return base

    owned_answers = []
    invalid_answer_refs = False
    for item in record.get("evidence", []):
        if (not isinstance(item, Mapping) or item.get("survey") != "MuCP"
                or item.get("kind") != "text_field" or item.get("question_id") != question_id
                or item.get("source_record_id", record.get("record_id")) != record.get("record_id")):
            continue
        evidence_keys, invalid_refs = _reference_keys(item.get("source_refs"), declared_ids)
        if invalid_refs:
            invalid_answer_refs = True
            continue
        if not mention_keys.intersection(evidence_keys):
            continue
        answer_text = item.get("raw_text")
        if isinstance(answer_text, str):
            owned_answers.append((answer_text, item.get("source_refs", [])))
    if not owned_answers:
        base["diagnostic"] = ("invalid_or_foreign_source_reference" if invalid_answer_refs
                              else "source_answer_not_found_at_reference")
        return base
    owners = {answer for answer, _ in owned_answers}
    if len(owners) != 1:
        base["diagnostic"] = "conflicting_source_answer_owners"
        return base
    answer_text = next(iter(owners))
    base["answer_text"] = answer_text
    owner_refs = []
    seen_refs = set()
    for text, refs_for_text in owned_answers:
        if text != answer_text:
            continue
        for ref in refs_for_text:
            key = (ref["source_id"], ref["locator"])
            if key not in seen_refs:
                seen_refs.add(key)
                owner_refs.append(plain(ref))
    base["source_refs"] = owner_refs
    # Import at call time because the extractor itself imports unit canonicalization.
    from survey_mucp_quantities import _count_measurement

    parsed = _count_measurement(answer_text)
    if parsed is None:
        parsed = _count_measurement(answer_text, numeric_only=True)
    if parsed is not None:
        base["source_unit"] = parsed["source_unit"]
        if (type(mention.get("value")) is not int or mention["value"] != parsed["value"]
                or mention.get("relation", "reported_value") != parsed["relation"]
                or mention.get("temporal_status", "unspecified") != parsed["temporal_status"]):
            base["diagnostic"] = "mention_quantity_disagrees_with_source"
            return base
        canonical = canonical_quantity_unit(parsed["unit"])
        if canonical != "unit_unclear":
            base.update(unit=canonical, unit_basis="literal_complete_answer")
    return base


def _quantity_scope_identity(bank_id: str, row: Mapping[str, Any], scope: Mapping[str, Any]) -> str:
    """Return only a source-proven identity for one collection/submission scope.

    Args:
        bank_id: Owning canonical Directory biobank ID.
        row: Extractor observation with its source response and scope IDs.
        scope: Matching scope metadata from that same biobank.

    Returns:
        Stable identity for a Directory/proven analytical collection, otherwise a
        source-response-scoped identity that cannot collide across submissions.
    """
    collection_id = row.get("collection_id")
    analytical_id = scope.get("analytical_scope_id")
    if (isinstance(collection_id, str) and collection_id.startswith("bbmri-eric:ID:")
            and collection_id != bank_id and not any(char.isspace() for char in collection_id)
            and scope.get("kind") == "collection"):
        return f"{bank_id}:directory-collection:{collection_id}"
    if (isinstance(analytical_id, str) and analytical_id
            and isinstance(scope.get("analytical_scope_basis"), str)
            and scope.get("analytical_scope_basis")):
        return f"{bank_id}:analytical-scope:{analytical_id}"
    return f"{bank_id}:native-scope:{row['source_record_id']}:{row['scope_id']}"


def _validated_aggregation_inputs(
    summary: Mapping[str, Any], biobanks: Sequence[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], dict[str, Mapping[str, Any]], dict[str, dict[str, Any]]]:
    """Validate aggregate inputs and resolve every observation's source owner.

    Args:
        summary: Extractor summary containing its observation sequence.
        biobanks: Combined biobank records owning source responses and scopes.

    Returns:
        Observations, bank index, and validated record/scope metadata by row index.

    Raises:
        TypeError: If either public input has an invalid container shape.
        ValueError: If IDs, ownership, source references or modality links are invalid.
    """
    if not isinstance(summary, Mapping):
        raise TypeError("Quantity summary must be a mapping")
    observations = summary.get("observations")
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
        raise TypeError("Quantity summary observations must be a sequence")
    if not isinstance(biobanks, Sequence) or isinstance(biobanks, (str, bytes)):
        raise TypeError("Combined biobanks must be a sequence")
    banks: dict[str, Mapping[str, Any]] = {}
    for bank in biobanks:
        if not isinstance(bank, Mapping):
            raise TypeError("Combined biobank entries must be mappings")
        bank_id = bank.get("biobank_id")
        if not isinstance(bank_id, str) or not bank_id or bank_id in banks:
            raise ValueError("Combined biobank IDs must be present and unique")
        banks[bank_id] = bank

    owners: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(observations):
        if not isinstance(row, Mapping):
            raise TypeError(f"Quantity observation {index} must be a mapping")
        bank_id, record_id, scope_id = (row.get("biobank_id"), row.get("source_record_id"),
                                        row.get("scope_id"))
        if bank_id not in banks:
            raise ValueError(f"Quantity observation references unknown biobank: {bank_id!r}")
        bank = banks[bank_id]
        if row.get("country") != (bank.get("country") or "unknown"):
            raise ValueError(f"Quantity observation country disagrees with owning biobank: {bank_id}")
        if not all(isinstance(value, str) and value for value in (record_id, scope_id)):
            raise ValueError("Quantity observations need a source record and scope ID")
        records = bank.get("mucp_source_records", [])
        matching_records = [record for record in records if isinstance(record, Mapping)
                            and record.get("record_id") == record_id
                            and record.get("survey", "MuCP") == "MuCP"]
        if len(matching_records) != 1:
            raise ValueError(f"Quantity observation has missing or ambiguous source ownership: {record_id}")
        record = matching_records[0]
        record_scopes = [scope for scope in record.get("scopes", [])
                         if isinstance(scope, Mapping) and scope.get("scope_id") == scope_id]
        top_scopes = bank.get("scopes", {})
        if len(record_scopes) != 1:
            raise ValueError(f"Quantity observation has missing or ambiguous scope ownership: {scope_id}")
        scope = dict(record_scopes[0])
        if isinstance(top_scopes, Mapping) and scope_id in top_scopes:
            top_scope = top_scopes[scope_id]
            if not isinstance(top_scope, Mapping):
                raise ValueError(f"Combined scope metadata is malformed: {scope_id}")
            for field in ("source_record_id", "kind", "collection_id"):
                if field in top_scope and top_scope[field] != scope.get(field):
                    raise ValueError(f"Combined and source scope metadata disagree: {scope_id}")
            scope.update(top_scope)
        if not scope:
            raise ValueError(f"Quantity observation references a dangling scope: {scope_id}")
        if scope.get("source_record_id") != record_id:
            raise ValueError(f"Quantity scope is foreign to source record {record_id}: {scope_id}")
        if row.get("collection_id") != scope.get("collection_id"):
            raise ValueError(f"Quantity collection ID disagrees with source scope: {scope_id}")
        if not isinstance(row.get("quantity_id"), str) or not row["quantity_id"]:
            raise ValueError("Quantity observation needs a stable quantity_id")
        if type(row.get("value")) is not int or row["value"] < 0:
            raise ValueError(f"Quantity value must be a nonnegative integer: {row['quantity_id']}")
        refs = row.get("source_refs")
        if not isinstance(refs, Sequence) or isinstance(refs, (str, bytes)):
            raise ValueError(f"Quantity source references must be a sequence: {row['quantity_id']}")
        metadata = record.get("metadata", {})
        declared_source_ids = metadata.get("source_ids", []) if isinstance(metadata, Mapping) else []
        if (not isinstance(declared_source_ids, Sequence)
                or isinstance(declared_source_ids, (str, bytes))
                or any(not isinstance(source_id, str) or not source_id
                       for source_id in declared_source_ids)):
            raise ValueError(f"Source record has invalid declared source IDs: {record_id}")
        for ref in refs:
            if not isinstance(ref, Mapping) or not isinstance(ref.get("locator"), str) or not ref["locator"]:
                raise ValueError(f"Malformed quantity source reference: {row['quantity_id']}")
            source_id = ref.get("source_id")
            if source_id is not None and source_id not in declared_source_ids:
                raise ValueError(f"Foreign quantity source reference: {row['quantity_id']}")
            if source_id is None and (not isinstance(ref.get("path"), str) or not ref["path"]):
                raise ValueError(f"Unowned quantity source reference: {row['quantity_id']}")
        links = row.get("modality_links")
        if (not isinstance(links, Sequence) or isinstance(links, (str, bytes)) or not links
                or any(not isinstance(link, Mapping) or not isinstance(link.get("modality_id"), str)
                       or not link["modality_id"] for link in links)):
            raise ValueError(f"Quantity has missing or malformed modality links: {row['quantity_id']}")
        for link in links:
            evidence_id = link.get("evidence_id")
            evidence = [item for item in record.get("evidence", [])
                        if isinstance(item, Mapping) and item.get("evidence_id") == evidence_id]
            if len(evidence) != 1:
                raise ValueError(f"Quantity has dangling modality evidence link: {row['quantity_id']}")
            evidence = evidence[0]
            if (evidence.get("survey") != "MuCP" or evidence.get("source_record_id") != record_id
                    or evidence.get("scope_id") != scope_id
                    or evidence.get("question_id") != link.get("question_id")
                    or evidence.get("normalized_value") != "affirmed"):
                raise ValueError(f"Quantity modality evidence is foreign to its source scope: {row['quantity_id']}")
            link_refs = link.get("source_refs")
            if not isinstance(link_refs, Sequence) or isinstance(link_refs, (str, bytes)) or not link_refs:
                raise ValueError(f"Quantity modality link lacks source references: {row['quantity_id']}")
            evidence_refs = evidence.get("source_refs", [])
            ref_key = lambda ref: (ref.get("source_id"), ref.get("path"), ref.get("locator"))
            if ({ref_key(ref) for ref in link_refs if isinstance(ref, Mapping)}
                    != {ref_key(ref) for ref in evidence_refs if isinstance(ref, Mapping)}):
                raise ValueError(f"Quantity modality link references disagree with source evidence: {row['quantity_id']}")
            for ref in link_refs:
                if (not isinstance(ref, Mapping) or not isinstance(ref.get("locator"), str)
                        or (ref.get("source_id") is not None
                            and ref.get("source_id") not in declared_source_ids)
                        or (ref.get("source_id") is None
                            and (not isinstance(ref.get("path"), str) or not ref["path"]))):
                    raise ValueError(f"Quantity modality link has a foreign source reference: {row['quantity_id']}")
        owners[str(index)] = {"bank": bank, "record": record, "scope": scope}
    return list(observations), banks, owners


def _excluded_row(
    row: Mapping[str, Any], identity: str, basis: str, reason: str, modality_ids: Sequence[str],
) -> dict[str, Any]:
    """Retain a source quantity with a machine-readable exclusion reason.

    Args:
        row: Extractor observation being excluded.
        identity: Proven source-scope or quantity identity.
        basis: Aggregate basis this observation would otherwise use.
        reason: Stable exclusion reason code.
        modality_ids: Explicit source modality links.

    Returns:
        Detached excluded-contribution record with original amount and provenance.
    """
    evidence_id = row.get("quantity_evidence_id")
    return {"contribution_id": row["quantity_id"], "biobank_id": row["biobank_id"],
            "country": row.get("country") or "unknown", "scope_id": row["scope_id"],
            "scope_identity": identity, "source_record_id": row["source_record_id"],
            "basis": basis, "unit": row.get("unit"), "source_unit": row.get("source_unit"),
            "value": row["value"], "relation": row.get("relation", _EXACT_RELATION),
            "temporal_status": row.get("temporal_status", "unspecified"),
            "modality_ids": list(modality_ids), "quantity_ids": [row["quantity_id"]],
            "quantity_evidence_ids": [evidence_id] if isinstance(evidence_id, str) else [],
            "source_refs": plain(row["source_refs"]), "reason": reason}


def _excluded_contribution(contribution: Mapping[str, Any], reason: str) -> dict[str, Any]:
    """Copy a reconciled contribution into exclusions without losing its evidence.

    Args:
        contribution: Reconciled exact scope contribution.
        reason: Stable exclusion reason code.

    Returns:
        Detached contribution record annotated with its exclusion reason.
    """
    return {**plain(contribution), "reason": reason}


def _contribution_groups(
    observations: Sequence[Mapping[str, Any]], owners: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Reconcile source rows into exact scope contributions and exclusions.

    Args:
        observations: Validated extractor observations.
        owners: Validated biobank, source-record and scope ownership by row index.

    Returns:
        Eligible and excluded contribution rows plus diagnostic rows.
    """
    grouped: dict[tuple[Any, ...], list[tuple[Mapping[str, Any], Mapping[str, Any]]]] = defaultdict(list)
    excluded: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for index, row in enumerate(observations):
        owner = owners[str(index)]
        bank_id, scope = row["biobank_id"], owner["scope"]
        linkage = row.get("linkage")
        unit = row.get("unit")
        canonical_unit = canonical_quantity_unit(unit) if isinstance(unit, str) else "unit_unclear"
        if linkage not in {"modality_specific", "collection_size_context", "submission_size_context"}:
            raise ValueError(f"Unsupported quantity linkage: {linkage!r}")
        if canonical_unit != unit and unit != "unit_unclear":
            raise ValueError(f"Quantity unit is not canonical: {unit!r}")
        modality_ids = sorted({link["modality_id"] for link in row["modality_links"]})
        if linkage == "modality_specific":
            identity = _quantity_scope_identity(bank_id, row, scope)
            basis = "direct_modality"
        elif linkage == "collection_size_context":
            if scope.get("kind") != "collection":
                raise ValueError(f"Collection quantity references non-collection scope: {row['scope_id']}")
            identity = _quantity_scope_identity(bank_id, row, scope)
            basis = "collection"
        else:
            if scope.get("kind") != "submission" or row.get("collection_id") is not None:
                raise ValueError(f"Submission quantity references a non-submission scope: {row['scope_id']}")
            identity = _quantity_scope_identity(bank_id, row, scope)
            basis = "submission_fallback"
        if canonical_unit == "unit_unclear":
            excluded.append(_excluded_row(row, identity, basis, "unsupported_unit", modality_ids))
            continue
        modality_groups = [[modality_id] for modality_id in modality_ids] if basis == "direct_modality" else [modality_ids]
        for group_modalities in modality_groups:
            group_key = (bank_id, identity, canonical_unit, basis,
                         tuple(group_modalities) if basis == "direct_modality" else ())
            grouped[group_key].append((row, {"scope": scope, "identity": identity, "basis": basis,
                                             "canonical_unit": canonical_unit, "modality_ids": group_modalities}))

    eligible: list[dict[str, Any]] = []
    for key, entries in sorted(grouped.items(), key=lambda pair: tuple(map(str, pair[0]))):
        entries.sort(key=lambda pair: (pair[0]["source_record_id"], pair[0]["scope_id"],
                                       pair[0]["quantity_id"]))
        signatures = {(entry[0]["value"], entry[0].get("relation", _EXACT_RELATION),
                       entry[0].get("temporal_status", "unspecified")) for entry in entries}
        representative = entries[0][0]
        union_modalities = sorted({modality for _, owner in entries for modality in owner["modality_ids"]})
        if len(signatures) != 1:
            reason = ("same_scope_mixed_temporal_status"
                      if len({signature[2] for signature in signatures}) > 1
                      and len({signature[:2] for signature in signatures}) == 1
                      else "same_scope_conflicting_quantities")
            for row, owner in entries:
                excluded.append(_excluded_row(row, owner["identity"], owner["basis"],
                                              reason, owner["modality_ids"]))
            diagnostics.append({"code": reason,
                                "biobank_id": representative["biobank_id"],
                                "scope_identity": entries[0][1]["identity"],
                                "quantity_ids": sorted({row["quantity_id"] for row, _ in entries})})
            continue
        value, relation, temporal = next(iter(signatures))
        refs: dict[tuple[Any, ...], Mapping[str, Any]] = {}
        quantity_ids, evidence_ids, source_units = [], [], set()
        for row, _ in entries:
            quantity_ids.append(row["quantity_id"])
            evidence_id = row.get("quantity_evidence_id")
            if isinstance(evidence_id, str) and evidence_id:
                evidence_ids.append(evidence_id)
            source_unit = row.get("source_unit")
            if isinstance(source_unit, str) and source_unit:
                source_units.add(source_unit)
            for ref in row["source_refs"]:
                refs[(ref.get("source_id"), ref.get("locator"), ref.get("path"))] = plain(ref)
        contribution = {
            "contribution_id": (f"{key[0]}:{entries[0][1]['identity']}:{key[2]}:{key[3]}:"
                                f"{','.join(key[4])}" if key[3] == "direct_modality"
                                else f"{key[0]}:{entries[0][1]['identity']}:{key[2]}:{key[3]}"),
            "biobank_id": representative["biobank_id"],
            "country": representative.get("country") or "unknown",
            "scope_id": representative["scope_id"],
            "scope_identity": entries[0][1]["identity"],
            "source_record_id": representative["source_record_id"],
            "basis": entries[0][1]["basis"], "unit": entries[0][1]["canonical_unit"],
            "source_unit": next(iter(source_units)) if len(source_units) == 1 else None,
            "source_units": sorted(source_units), "value": value, "relation": relation,
            "temporal_status": temporal, "modality_ids": union_modalities,
            "quantity_ids": sorted(set(quantity_ids)),
            "quantity_evidence_ids": sorted(set(evidence_ids)),
            "source_refs": [refs[ref_key] for ref_key in sorted(refs, key=lambda value: tuple(map(str, value)))],
            "scope_members": list({
                (row["source_record_id"], row["scope_id"]): plain(owner["scope"])
                for row, owner in entries
            }.values()),
        }
        if relation != _EXACT_RELATION:
            excluded.append(_excluded_contribution(contribution, "qualified_relation"))
        elif temporal not in _ELIGIBLE_TIMES:
            excluded.append(_excluded_contribution(contribution, "non_current_time"))
        else:
            eligible.append(contribution)
    eligible.sort(key=lambda item: (item["country"], item["biobank_id"], item["scope_identity"],
                                    item["unit"], item["basis"]))
    excluded.sort(key=lambda item: (item["country"], item["biobank_id"], item["scope_identity"],
                                    item["reason"]))
    return eligible, excluded, diagnostics


def _collection_hierarchy(
    banks: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, str], set[str], list[dict[str, Any]]]:
    """Resolve explicit source parent links and diagnose invalid collection graphs.

    Args:
        banks: Combined biobanks containing raw source and canonical scope metadata.

    Returns:
        Parent identities, unsafe hierarchy identities and source-backed diagnostics.
        Local parent IDs resolve within their response; Directory IDs resolve within
        their biobank. Ambiguous parents and cycles withhold affected branches.
    """
    nodes: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    local: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    directory: dict[tuple[str, str], set[str]] = defaultdict(set)
    bank_by_identity = {}
    for bank_id, bank in banks.items():
        scopes = bank.get("scopes", {})
        for record in bank.get("mucp_source_records", []):
            for raw_scope in record.get("scopes", []):
                scope = {**raw_scope, **scopes.get(raw_scope["scope_id"], {})}
                if scope.get("kind") != "collection":
                    continue
                identity = _quantity_scope_identity(bank_id, scope, scope)
                nodes[identity].append(scope)
                bank_by_identity[identity] = bank_id
                for local_id in (scope.get("collection_id"), scope["scope_id"]):
                    if isinstance(local_id, str) and local_id:
                        local[(bank_id, scope["source_record_id"], local_id)].add(identity)
                cid = scope.get("collection_id")
                if isinstance(cid, str) and cid.startswith("bbmri-eric:ID:"):
                    directory[(bank_id, cid)].add(identity)
    parents = {}
    blocked = set()
    diagnostics = []
    for identity, members in sorted(nodes.items()):
        resolved = set()
        ambiguous = False
        for scope in members:
            declarations = []
            for field in ("relationship", "metadata"):
                source = scope.get(field)
                if isinstance(source, Mapping) and source.get("parent_collection_id") not in (None, ""):
                    declarations.append(source["parent_collection_id"])
            for declaration in declarations:
                if isinstance(declaration, str):
                    values = [declaration]
                elif isinstance(declaration, Sequence) and not isinstance(declaration, (str, bytes)):
                    values = list(declaration)
                    ambiguous = len(set(map(str, values))) != 1 or ambiguous
                else:
                    values = []
                    ambiguous = True
                for parent_id in values:
                    if not isinstance(parent_id, str) or not parent_id:
                        ambiguous = True
                        continue
                    bank_id = bank_by_identity[identity]
                    candidates = (directory.get((bank_id, parent_id), set())
                                  if parent_id.startswith("bbmri-eric:ID:")
                                  else local.get((bank_id, scope["source_record_id"], parent_id), set()))
                    if len(candidates) != 1:
                        ambiguous = True
                    resolved.update(candidates)
        if ambiguous or len(resolved) > 1:
            blocked.update({identity} | resolved)
            diagnostics.append({"code": "ambiguous_collection_parent",
                                "biobank_id": bank_by_identity[identity],
                                "scope_identity": identity, "parent_candidates": sorted(resolved),
                                "scope_members": plain(members)})
        elif resolved:
            parents[identity] = next(iter(resolved))
    visited = set()
    for start in sorted(nodes):
        chain = []
        positions = {}
        current = start
        while current not in visited and current not in positions:
            positions[current] = len(chain)
            chain.append(current)
            if current not in parents:
                break
            current = parents[current]
        if current in positions and current in parents:
            cycle = chain[positions[current]:]
            blocked.update(cycle)
            diagnostics.append({"code": "collection_hierarchy_cycle",
                                "biobank_id": bank_by_identity[start],
                                "scope_identities": cycle})
        visited.update(chain)
    changed = True
    while changed:
        affected = {child for child, parent in parents.items() if parent in blocked}
        changed = bool(affected - blocked)
        blocked.update(affected)
    return parents, blocked, diagnostics


def _known_scope(scope: Mapping[str, Any]) -> bool:
    """Determine whether a collection has identity evidence beyond a local ID.

    Args:
        scope: Source scope augmented with canonical analytical identity metadata.

    Returns:
        True for a Directory collection ID or an explicitly evidenced analytical ID.
    """
    cid = scope.get("collection_id")
    return (isinstance(cid, str) and cid.startswith("bbmri-eric:ID:")
            or bool(scope.get("analytical_scope_id") and scope.get("analytical_scope_basis")))


def _native_repeat(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    """Recognize unresolved cross-record collection repetitions without merging them.

    Args:
        left: Reconciled source contribution with its scope members and references.
        right: Another contribution from the same requested biobank/unit/view.

    Returns:
        True when different responses repeat a native ID, label or physical count
        reference and at least one scope lacks proven collection identity.
    """
    for a in left["scope_members"]:
        for b in right["scope_members"]:
            if (a.get("kind") != "collection" or b.get("kind") != "collection"
                    or a["source_record_id"] == b["source_record_id"]
                    or (_known_scope(a) and _known_scope(b))):
                continue
            local_ids = []
            for scope in (a, b):
                cid = str(scope.get("collection_id") or "")
                record_id = scope["source_record_id"]
                if cid.startswith(record_id):
                    cid = cid[len(record_id):].lstrip("-:_")
                local_ids.append(cid.casefold())
            labels = [" ".join(str(scope.get("label") or "").casefold().split()) for scope in (a, b)]
            if (local_ids[0] and local_ids[0] == local_ids[1]
                    or labels[0] and labels[0] == labels[1]):
                return True
            left_refs = {(ref.get("source_id"), ref.get("path"), ref.get("locator"))
                         for ref in left["source_refs"]}
            right_refs = {(ref.get("source_id"), ref.get("path"), ref.get("locator"))
                          for ref in right["source_refs"]}
            if left_refs & right_refs:
                return True
    return False


def _select_reporting_view(
    rows: Sequence[Mapping[str, Any]], parents: Mapping[str, str], blocked: set[str],
    view: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Select independently supported scopes for one modality or country view.

    Args:
        rows: Candidate contributions, with singleton modality lists for modality views.
        parents: Explicit collection parent identities.
        blocked: Identities involved in unresolved hierarchy branches.
        view: Modality or country view tag retained on excluded evidence.

    Returns:
        Selected contributions, excluded source rows and ambiguity/coverage diagnostics.
        Multiple unlinked submissions are withheld. Collection ancestors cover only
        descendants eligible for the same unit, temporal basis and requested modality.
    """
    grouped: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        modality = tuple(row["modality_ids"]) if view == "modality" else ()
        grouped[(row["biobank_id"], row["unit"], row["basis"], modality)].append(row)
    selected, excluded, diagnostics = [], [], []
    for key, candidates in sorted(grouped.items(), key=lambda pair: tuple(map(str, pair[0]))):
        rejected = {index: "invalid_collection_hierarchy" for index, row in enumerate(candidates)
                    if row["scope_identity"] in blocked}
        submissions = [index for index, row in enumerate(candidates)
                       if any(scope.get("kind") != "collection" for scope in row["scope_members"])]
        if (len({candidates[index]["scope_identity"] for index in submissions}) > 1
                and not all(all(scope.get("analytical_scope_basis") == "reviewed_distinct_reporting_scope"
                                for scope in candidates[index]["scope_members"])
                            for index in submissions)):
            for index in submissions:
                rejected[index] = "ambiguous_submission_scopes"
        for index, left in enumerate(candidates):
            for other_index in range(index + 1, len(candidates)):
                right = candidates[other_index]
                if left["scope_identity"] != right["scope_identity"] and _native_repeat(left, right):
                    rejected[index] = rejected[other_index] = "ambiguous_native_collection_repeats"
        eligible_ids = {(row["scope_identity"], row["temporal_status"])
                        for index, row in enumerate(candidates) if index not in rejected}
        for index, row in enumerate(candidates):
            ancestor = parents.get(row["scope_identity"])
            covering = None
            seen = set()
            while ancestor is not None and ancestor not in seen and row["scope_identity"] not in blocked:
                seen.add(ancestor)
                if (ancestor, row["temporal_status"]) in eligible_ids:
                    covering = ancestor
                ancestor = parents.get(ancestor)
            if index not in rejected and covering is not None:
                rejected[index] = "covered_by_reporting_ancestor"
            if index in rejected:
                reason = rejected[index]
                exclusion = {**plain(row), "reason": reason, "view": view}
                if reason == "covered_by_reporting_ancestor":
                    exclusion["covering_scope_identity"] = covering
                excluded.append(exclusion)
                diagnostics.append({"code": reason, "biobank_id": row["biobank_id"],
                                    "scope_identity": row["scope_identity"],
                                    "quantity_ids": list(row["quantity_ids"]), "view": view,
                                    "modality_ids": list(row["modality_ids"]) if view == "modality" else []})
            else:
                selected.append(plain(row))
    return selected, excluded, diagnostics


def _make_totals(
    contributions: Sequence[Mapping[str, Any]], excluded: Sequence[Mapping[str, Any]],
    dimension: str,
) -> list[dict[str, Any]]:
    """Build totals with null for groups that have no eligible source contribution.

    Args:
        contributions: Contributions currently eligible for this aggregate view.
        excluded: Evidence excluded from that view, including per-modality omissions.
        dimension: Either modality_id or country.

    Returns:
        Sorted totals with one segment per biobank and source IDs for every segment.
    """
    grouped: dict[tuple[str, str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    excluded_counts: dict[tuple[str, str, str, str], int] = defaultdict(int)
    for contribution in contributions:
        dimensions = contribution["modality_ids"] if dimension == "modality_id" else [contribution["country"]]
        for value in dimensions:
            grouped[(value, contribution["unit"], contribution["basis"],
                     contribution["temporal_status"])].append(contribution)
    for item in excluded:
        dimensions = item.get("modality_ids", []) if dimension == "modality_id" else [item.get("country", "unknown")]
        for value in dimensions:
            key = (value, item.get("unit", "unit_unclear"), item["basis"],
                   item.get("temporal_status", "unspecified"))
            excluded_counts[key] += 1
    totals = []
    for key in sorted(set(grouped) | set(excluded_counts)):
        rows = grouped.get(key, [])
        per_bank: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in rows:
            per_bank[row["biobank_id"]].append(row)
        segments = []
        for bank_id, bank_rows in sorted(per_bank.items()):
            segments.append({"biobank_id": bank_id, "value": sum(row["value"] for row in bank_rows),
                             "quantity_ids": sorted({quantity_id for row in bank_rows
                                                     for quantity_id in row["quantity_ids"]})})
        totals.append({
            dimension: key[0], "unit": key[1], "basis": key[2], "temporal_status": key[3],
            "reported_total": sum(segment["value"] for segment in segments) if segments else None,
            "contributing_biobanks": len(segments),
            "contributing_scopes": len({row["scope_identity"] for row in rows}),
            "excluded_count": excluded_counts.get(key, 0), "segments": segments,
        })
    return totals


def aggregate_modality_quantities(
    summary: Mapping[str, Any], biobanks: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate source-proven MuCP quantities without cross-modality double counting.

    Args:
        summary: Output of extract_modality_quantities with raw observations.
        biobanks: Combined biobank records used to prove source response, scope and
            Directory collection ownership for every observation.

    Returns:
        Versioned mapping with reconciled contributions, basis-separated modality and
        country totals, excluded evidence and diagnostics. Missing groups have null
        totals; explicitly reported zero remains a zero segment.

    Raises:
        TypeError: If public containers or source rows have invalid types.
        ValueError: If an observation has duplicate, dangling or foreign source ownership.
    """
    observations, banks, owners = _validated_aggregation_inputs(summary, biobanks)
    eligible, excluded, diagnostics = _contribution_groups(observations, owners)
    parents, blocked, hierarchy_diagnostics = _collection_hierarchy(banks)
    diagnostics.extend(hierarchy_diagnostics)
    modality_rows = [{**item, "modality_ids": [modality_id]}
                     for item in eligible if item["basis"] != "submission_fallback"
                     for modality_id in item["modality_ids"]]
    country_rows = [item for item in eligible if item["basis"] == "collection"]
    modality_contributions, modality_view_excluded, view_diagnostics = _select_reporting_view(
        modality_rows, parents, blocked, "modality")
    diagnostics.extend(view_diagnostics)
    country_contributions, country_view_excluded, view_diagnostics = _select_reporting_view(
        country_rows, parents, blocked, "country")
    diagnostics.extend(view_diagnostics)

    collection_modalities = {
        (item["biobank_id"], modality_id, item["unit"])
        for item in modality_contributions if item["basis"] == "collection"
        for modality_id in item["modality_ids"]
    }
    collection_units = {(item["biobank_id"], item["unit"])
                        for item in country_contributions}
    modality_excluded = list(excluded) + modality_view_excluded
    country_excluded = [item for item in excluded if item["basis"] != "direct_modality"] + country_view_excluded
    modality_fallback, country_fallback = [], []
    for item in eligible:
        if item["basis"] != "submission_fallback":
            continue
        remaining_modalities, omitted_modalities = [], []
        for modality_id in item["modality_ids"]:
            target = (item["biobank_id"], modality_id, item["unit"])
            (omitted_modalities if target in collection_modalities else remaining_modalities).append(modality_id)
        if remaining_modalities:
            modality_fallback.extend({**item, "modality_ids": [modality_id]}
                                     for modality_id in remaining_modalities)
        if omitted_modalities:
            modality_excluded.append({**item, "modality_ids": omitted_modalities,
                                      "reason": "collection_counts_preferred"})
        if (item["biobank_id"], item["unit"]) in collection_units:
            country_excluded.append({**item, "reason": "collection_counts_preferred", "view": "country"})
        else:
            country_fallback.append(item)

    fallback, fallback_excluded, view_diagnostics = _select_reporting_view(
        modality_fallback, parents, blocked, "modality")
    modality_contributions.extend(fallback)
    modality_excluded.extend(fallback_excluded)
    diagnostics.extend(view_diagnostics)
    fallback, fallback_excluded, view_diagnostics = _select_reporting_view(
        country_fallback, parents, blocked, "country")
    country_contributions.extend(fallback)
    country_excluded.extend(fallback_excluded)
    diagnostics.extend(view_diagnostics)

    for bank_id, bank in banks.items():
        scopes = bank.get("scopes", {})
        if isinstance(scopes, Mapping):
            collection_scope_ids = {scope_id for scope_id, scope in scopes.items()
                                    if isinstance(scope, Mapping) and scope.get("kind") == "collection"}
            reported_scope_ids = {
                row["scope_id"] for index, row in enumerate(observations)
                if row["biobank_id"] == bank_id
                and row.get("linkage") == "collection_size_context"
                and owners[str(index)]["scope"].get("kind") == "collection"
            }
            missing = sorted(collection_scope_ids - reported_scope_ids)
            if reported_scope_ids and missing:
                diagnostics.append({"code": "incomplete_collection_reporting", "biobank_id": bank_id,
                                    "reported_collection_scopes": len(reported_scope_ids),
                                    "unreported_collection_scopes": missing,
                                    "message": "Some collection scopes have no eligible reported quantity; totals cover reported scopes only."})

    return {
        "version": 1,
        "unit_policy": {"person_unit": "donors", "source_units_preserved": True,
                        "samples_and_aliquots_separate": True,
                        "exact_totals_require_reported_value_and_current_or_unspecified_time": True},
        "contributions": [plain(item) for item in eligible],
        "modality_totals": _make_totals(modality_contributions, modality_excluded, "modality_id"),
        "country_totals": _make_totals(country_contributions, country_excluded, "country"),
        "excluded_contributions": _unique_exclusions(modality_excluded, country_excluded),
        "diagnostics": sorted(diagnostics, key=lambda item: (item["code"], item.get("biobank_id", ""))),
    }


def _unique_exclusions(
    modality_excluded: Sequence[Mapping[str, Any]],
    country_excluded: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Combine exclusion views without repeating the same evidence record.

    Args:
        modality_excluded: Evidence omitted from modality totals.
        country_excluded: Evidence omitted from all-scope country totals.

    Returns:
        Stable exclusion rows; country-only suppression is tagged with its view.
    """
    rows: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in list(modality_excluded) + list(country_excluded):
        value = plain(item)
        key = (value.get("contribution_id"), value.get("reason"),
               tuple(value.get("modality_ids", ())), value.get("view"))
        rows[key] = value
    return [rows[key] for key in sorted(rows, key=lambda item: tuple(map(str, item)))]
