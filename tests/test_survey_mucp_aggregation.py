"""Unit normalization and source-owned MuCP quantity text recovery."""

import copy
from importlib.util import find_spec

import pytest


def aggregation_api():
    """Load the production API only after asserting its module exists.

    Returns:
        Pair containing the canonical unit and source recovery functions.
    """
    assert find_spec("survey_mucp_aggregation") is not None, "quantity aggregation API is not implemented"
    from survey_mucp_aggregation import canonical_quantity_unit, recover_quantity_answer
    return canonical_quantity_unit, recover_quantity_answer


def test_canonical_quantity_unit_groups_people_but_keeps_material_units_separate():
    """Normalize people synonyms while keeping samples and aliquots distinct.

    Returns:
        None. Every input label is classified without editing its source mapping.
    """
    units = {
        "donor": "donors", "individuals": "donors", "research participants": "donors",
        "sample": "samples", "aliquots": "aliquots", None: "unit_unclear",
        "cases": "unit_unclear", "FFPE blocks": "unit_unclear",
    }
    snapshot = copy.deepcopy(units)

    canonical_quantity_unit, _ = aggregation_api()
    assert {unit: canonical_quantity_unit(unit) for unit in units} == units
    assert units == snapshot


def test_recovery_uses_full_owned_answer_and_does_not_trust_index_unit():
    """Return exact answer ownership without treating index classification as proof.

    Returns:
        None. The complete answer and locator survive while its unit remains unclear.
    """
    record = {
        "record_id": "IRE-1",
        "metadata": {"source_ids": ["SRC-IRE"]},
        "evidence": [{"survey": "MuCP", "kind": "text_field", "question_id": "B.count",
            "source_record_id": "IRE-1", "raw_text": "Uterine cancer : 64",
            "source_refs": [{"source_id": "SRC-IRE", "locator": "word/document.xml:p[59]"}]}],
    }
    mention = {
        "field": "B.count", "unit": "individuals", "value": 64,
        "context": "rine cancer : 64",
        "evidence": [{"source_id": "SRC-IRE", "locator": "word/document.xml:p[59]"}],
    }
    before = (copy.deepcopy(record), copy.deepcopy(mention))

    _, recover_quantity_answer = aggregation_api()
    recovered = recover_quantity_answer(record, mention)

    assert recovered["answer_text"] == "Uterine cancer : 64"
    assert recovered["source_question_id"] == "B.count"
    assert recovered["source_refs"] == mention["evidence"]
    assert recovered["unit"] == "unit_unclear"
    assert recovered["unit_basis"] is None
    assert recovered["diagnostic"] is None
    assert (record, mention) == before


def test_recovery_rejects_missing_or_conflicting_source_owners():
    """Missing and ambiguous locators remain diagnostic rather than guessed text.

    Returns:
        None. Neither index context nor a conflicting raw source is reconstructed.
    """
    record = {"record_id": "IRE-1", "metadata": {"source_ids": ["SRC-IRE"]}, "evidence": [
        {"survey": "MuCP", "kind": "text_field", "question_id": "B.count",
         "source_record_id": "IRE-1", "raw_text": "64 individuals",
         "source_refs": [{"source_id": "SRC-IRE", "locator": "word/document.xml:p[59]"}]},
        {"survey": "MuCP", "kind": "text_field", "question_id": "B.count",
         "source_record_id": "IRE-1", "raw_text": "65 individuals",
         "source_refs": [{"source_id": "SRC-IRE", "locator": "word/document.xml:p[60]"}]},
    ]}
    mention = {"field": "B.count", "unit": "individuals", "context": "4 individuals",
               "evidence": [{"source_id": "SRC-IRE", "locator": "word/document.xml:p[59]"},
                            {"source_id": "SRC-IRE", "locator": "word/document.xml:p[60]"}]}
    _, recover_quantity_answer = aggregation_api()
    missing = recover_quantity_answer({"record_id": "IRE-2", "metadata": {"source_ids": []}, "evidence": []}, mention)
    conflicting = recover_quantity_answer(record, mention)

    assert missing["answer_text"] is None
    assert missing["unit"] == "unit_unclear"
    assert missing["diagnostic"]
    assert conflicting["answer_text"] is None
    assert conflicting["unit"] == "unit_unclear"
    assert conflicting["diagnostic"]


def test_literal_owned_answer_proves_unit_but_foreign_reference_is_rejected():
    """Only complete source answer text can verify a person unit.

    Returns:
        None. The owned literal proves donors; an undeclared source ID is rejected.
    """
    record = {"record_id": "IRE-1", "metadata": {"source_ids": ["SRC-IRE"]},
        "evidence": [{"survey": "MuCP", "kind": "text_field", "question_id": "B.count",
            "source_record_id": "IRE-1", "raw_text": "64 participants",
            "source_refs": [{"source_id": "SRC-IRE", "locator": "word/document.xml:p[59]"}]}]}
    mention = {"field": "B.count", "unit": "individuals", "value": 64,
        "evidence": [{"source_id": "SRC-IRE", "locator": "word/document.xml:p[59]"}]}
    _, recover_quantity_answer = aggregation_api()

    verified = recover_quantity_answer(record, mention)
    foreign = recover_quantity_answer(record, {**mention, "evidence": [
        {"source_id": "UNDECLARED", "locator": "word/document.xml:p[59]"}]})

    assert verified["unit"] == "donors"
    assert verified["source_unit"] == "participants"
    assert verified["unit_basis"] == "literal_complete_answer"
    assert foreign["unit"] == "unit_unclear"
    assert foreign["diagnostic"] == "invalid_or_foreign_source_reference"


@pytest.mark.parametrize("changes", [{"value": 65}, {"relation": "greater_than"},
                                     {"temporal_status": "future"}])
def test_recovery_withholds_units_when_mention_disagrees_with_answer(changes):
    """Require mention quantity semantics to agree with the complete owned answer.

    Args:
        changes: Value, relation or time disagreement inserted into the index mention.

    Returns:
        None. The original answer remains readable but cannot verify the mention unit.
    """
    refs = [{"source_id": "SRC", "locator": "word/document.xml:p[59]"}]
    record = {"record_id": "R", "metadata": {"source_ids": ["SRC"]}, "evidence": [
        {"survey": "MuCP", "kind": "text_field", "question_id": "B.count",
         "source_record_id": "R", "raw_text": "64 participants", "source_refs": refs}]}
    mention = {"field": "B.count", "value": 64, "evidence": refs, **changes}
    before = copy.deepcopy((record, mention))
    _, recover_quantity_answer = aggregation_api()
    result = recover_quantity_answer(record, mention)
    assert result["answer_text"] == "64 participants"
    assert result["unit"] == "unit_unclear"
    assert result["diagnostic"] == "mention_quantity_disagrees_with_source"
    assert (record, mention) == before


def test_recovery_accepts_immutable_reference_sequences_without_mutation():
    """Accept tuple references used by immutable projected source records.

    Returns:
        None. Literal units are recovered and both tuple inputs remain unchanged.
    """
    refs = ({"source_id": "SRC", "locator": "word/document.xml:p[59]"},)
    record = {"record_id": "R", "metadata": {"source_ids": ("SRC",)}, "evidence": (
        {"survey": "MuCP", "kind": "text_field", "question_id": "B.count",
         "source_record_id": "R", "raw_text": "64 participants", "source_refs": refs},)}
    mention = {"field": "B.count", "value": 64, "evidence": refs}
    before = copy.deepcopy((record, mention))
    _, recover_quantity_answer = aggregation_api()
    result = recover_quantity_answer(record, mention)
    assert result["unit"] == "donors"
    assert result["source_refs"] == list(refs)
    assert (record, mention) == before


def _quantity(bank_id, country, record_id, scope_id, collection_id, value, modality_ids,
              *, unit="donors", source_unit="participants", relation="reported_value",
              temporal_status="current", linkage="collection_size_context", quantity_id=None):
    """Build one small source-proven quantity row for aggregation tests.

    Args:
        bank_id: Owning combined Directory biobank ID.
        country: Directory country of that biobank.
        record_id: Source-native MuCP response identifier.
        scope_id: Source-native scope identifier within the response.
        collection_id: Collection ID, if the row is collection-scoped.
        value: Literal source-reported count.
        modality_ids: Explicit modality links carried by the source row.
        unit: Canonical analysis unit.
        source_unit: Literal spelling preserved from source evidence.
        relation: Source-reported exactness or bound relation.
        temporal_status: Source-reported time qualifier.
        linkage: Direct, collection-context or submission-context class.
        quantity_id: Stable source quantity ID, defaulting to a response/scope key.

    Returns:
        An extractor-shaped observation with stable evidence references.
    """
    qid = quantity_id or f"{record_id}:{scope_id}:{value}:{linkage}"
    return {
        "quantity_id": qid, "biobank_id": bank_id, "country": country,
        "source_record_id": record_id, "question_id": None, "scope_id": scope_id,
        "collection_id": collection_id, "value": value, "unit": unit,
        "source_unit": source_unit, "relation": relation,
        "temporal_status": temporal_status, "linkage": linkage,
        "quantity_evidence_id": "evidence:" + qid,
        "source_refs": [{"source_id": "SRC:" + record_id, "locator": "quantity:" + qid}],
        "modality_links": [
            {"modality_id": modality_id, "question_id": modality_id,
             "evidence_id": "link:" + qid + ":" + modality_id,
             "source_refs": [{"source_id": "SRC:" + record_id,
                              "locator": "link:" + qid + ":" + modality_id}]}
            for modality_id in modality_ids
        ],
    }


def _banks_for(*rows):
    """Build source ownership and scope metadata corresponding to quantity rows.

    Args:
        rows: Extractor-shaped quantity observations.

    Returns:
        Combined biobank records with exact source-record and scope ownership.
    """
    banks = {}
    for row in rows:
        bank = banks.setdefault(row["biobank_id"], {
            "biobank_id": row["biobank_id"], "country": row["country"], "scopes": {},
            "mucp_source_records": [], "evidence": [],
        })
        record_id, scope_id = row["source_record_id"], row["scope_id"]
        kind = "collection" if row["collection_id"] is not None else "submission"
        bank["scopes"].setdefault(scope_id, {
            "scope_id": scope_id, "source_record_id": record_id, "kind": kind,
            "collection_id": row["collection_id"],
        })
        if not any(record["record_id"] == record_id for record in bank["mucp_source_records"]):
            bank["mucp_source_records"].append({
                "record_id": record_id, "survey": "MuCP", "scopes": [],
                "metadata": {"source_ids": ["SRC:" + record_id]}, "evidence": [],
            })
        record = next(record for record in bank["mucp_source_records"]
                      if record["record_id"] == record_id)
        if not any(scope["scope_id"] == scope_id for scope in record["scopes"]):
            record["scopes"].append(copy.deepcopy(bank["scopes"][scope_id]))
        for link in row["modality_links"]:
            evidence = {"evidence_id": link["evidence_id"], "survey": "MuCP",
                        "source_record_id": record_id, "question_id": link["question_id"],
                        "question_label": link["question_id"],
                        "scope_id": scope_id, "kind": "structured_answer",
                        "normalized_value": "affirmed", "source_refs": link["source_refs"]}
            if not any(item["evidence_id"] == evidence["evidence_id"] for item in record["evidence"]):
                record["evidence"].append(evidence)
                bank["evidence"].append(copy.deepcopy(evidence))
    return list(banks.values())


def test_aggregation_counts_collection_once_per_modality_and_once_in_country():
    """Use an independent arithmetic oracle for overlapping modalities and countries.

    Returns:
        None. Modality sums overlap while all-collection country sums do not.
    """
    from survey_mucp_aggregation import aggregate_modality_quantities

    rows = [
        _quantity("A", "AT", "RESP-A", "RESP-A-C1", "RESP-A-C1", 100, ["plasma", "wgs"]),
        _quantity("B", "AT", "RESP-B", "RESP-B-C1", "RESP-B-C1", 20, ["plasma"],
                  unit="donors", source_unit="individuals"),
        _quantity("C", "DE", "RESP-C", "RESP-C-C1", "RESP-C-C1", 30, ["wgs"],
                  source_unit="research participants"),
    ]
    banks = _banks_for(*rows)
    before = copy.deepcopy((rows, banks))
    result = aggregate_modality_quantities({"observations": rows}, banks)

    totals = {(item["modality_id"], item["unit"], item["basis"]): item["reported_total"]
              for item in result["modality_totals"]}
    assert totals[("plasma", "donors", "collection")] == 120
    assert totals[("wgs", "donors", "collection")] == 130
    countries = {(item["country"], item["unit"], item["basis"]): item["reported_total"]
                 for item in result["country_totals"]}
    assert countries[("AT", "donors", "collection")] == 120
    assert countries[("DE", "donors", "collection")] == 30
    for total in result["country_totals"]:
        assert sum(segment["value"] for segment in total["segments"]) == total["reported_total"]
    assert result["version"] == 1
    assert (rows, banks) == before
    assert result == aggregate_modality_quantities({"observations": list(reversed(rows))}, banks)


def test_aggregation_requires_proven_identity_and_withholds_conflicting_scope():
    """Do not deduplicate equal values across source-native scopes or display names.

    Returns:
        None. Only an explicit shared analytical identity can reduce repetitions.
    """
    from survey_mucp_aggregation import aggregate_modality_quantities

    same = _quantity("A", "AT", "RESP-A", "RESP-A-C1", "RESP-A-C1", 100, ["plasma"])
    repeat = {**same, "quantity_id": "repeat", "quantity_evidence_id": "evidence:repeat",
              "source_refs": [{"source_id": "SRC:RESP-A", "locator": "quantity:repeat"}]}
    repeated_result = aggregate_modality_quantities(
        {"observations": [same, repeat]}, _banks_for(same, repeat))
    assert repeated_result["country_totals"][0]["reported_total"] == 100
    contribution = repeated_result["contributions"][0]
    assert len(contribution["quantity_ids"]) == 2
    assert len(contribution["source_refs"]) == 2

    first = _quantity("A", "AT", "RESP-A", "RESP-A-C1", "RESP-A-C1", 100, ["plasma"])
    second = _quantity("A", "AT", "RESP-B", "RESP-B-C1", "RESP-B-C1", 100, ["plasma"])
    independent = aggregate_modality_quantities(
        {"observations": [first, second]}, _banks_for(first, second))
    assert independent["country_totals"][0]["reported_total"] is None
    assert any(row["code"] == "ambiguous_native_collection_repeats" for row in independent["diagnostics"])

    directory_id = "bbmri-eric:ID:AT_A:collection:101"
    directory_first = _quantity("A", "AT", "RESP-A", "RESP-A-C1", directory_id, 100, ["plasma"])
    directory_repeat = _quantity("A", "AT", "RESP-B", "RESP-B-C1", directory_id, 100, ["plasma"])
    proven = aggregate_modality_quantities(
        {"observations": [directory_first, directory_repeat]},
        _banks_for(directory_first, directory_repeat))
    assert proven["country_totals"][0]["reported_total"] == 100
    assert set(proven["contributions"][0]["quantity_ids"]) == {
        directory_first["quantity_id"], directory_repeat["quantity_id"]}

    scoped_first = _quantity("A", "AT", "RESP-A", "RESP-A-C1", "RESP-A-C1", 100, ["plasma"])
    scoped_repeat = _quantity("A", "AT", "RESP-B", "RESP-B-C1", "RESP-B-C1", 100, ["plasma"])
    scoped_banks = _banks_for(scoped_first, scoped_repeat)
    for scope_id in ("RESP-A-C1", "RESP-B-C1"):
        scoped_banks[0]["scopes"][scope_id].update(
            analytical_scope_id="reviewed-scope-1",
            analytical_scope_basis="reviewed_cross_record_identity",
        )
    scoped = aggregate_modality_quantities(
        {"observations": [scoped_first, scoped_repeat]}, scoped_banks)
    assert scoped["country_totals"][0]["reported_total"] == 100

    conflicting = {**first, "quantity_id": "conflict", "value": 90,
                   "quantity_evidence_id": "evidence:conflict"}
    conflict_result = aggregate_modality_quantities(
        {"observations": [first, conflicting]}, _banks_for(first, conflicting))
    assert conflict_result["country_totals"][0]["reported_total"] is None
    assert conflict_result["excluded_contributions"]
    assert any(item["code"] == "same_scope_conflicting_quantities"
               for item in conflict_result["diagnostics"])


def test_aggregation_collapses_equal_bc_counts_only_within_owned_submission_scope():
    """Part B/C repetitions collapse only when their source response scope agrees.

    Returns:
        None. The identical submission count contributes once and keeps both references.
    """
    from survey_mucp_aggregation import aggregate_modality_quantities

    part_b = _quantity("A", "AT", "RESP-A", "RESP-A", None, 100, ["wgs"],
                       linkage="submission_size_context", quantity_id="part-b")
    part_c = {**part_b, "quantity_id": "part-c", "quantity_evidence_id": "evidence:part-c",
              "source_refs": [{"source_id": "SRC:RESP-A", "locator": "quantity:part-c"}]}
    result = aggregate_modality_quantities(
        {"observations": [part_b, part_c]}, _banks_for(part_b, part_c))
    total = result["country_totals"][0]
    assert total["reported_total"] == 100
    assert total["basis"] == "submission_fallback"
    assert len(result["contributions"][0]["quantity_ids"]) == 2
    assert len(result["contributions"][0]["source_refs"]) == 2

    other_response = {**part_c, "source_record_id": "RESP-B", "scope_id": "RESP-B",
                      "quantity_id": "other-response",
                      "quantity_evidence_id": "evidence:other-response",
                      "source_refs": [{"source_id": "SRC:RESP-B", "locator": "quantity:other-response"}],
                      "modality_links": [{**part_c["modality_links"][0],
                          "source_refs": [{"source_id": "SRC:RESP-B", "locator": "link:other-response"}]}]}
    separate = aggregate_modality_quantities(
        {"observations": [part_b, other_response]}, _banks_for(part_b, other_response))
    assert separate["country_totals"][0]["reported_total"] is None
    assert any(item["code"] == "ambiguous_submission_scopes" for item in separate["diagnostics"])


def _audit_extract(rows, scope_updates=None):
    """Run synthetic source counts and qualifiers through the real extractor.

    Args:
        rows: Quantity fixtures specifying source counts, scopes and modalities.
        scope_updates: Source scope metadata, labels and relationships indexed by scope ID.

    Returns:
        Extractor summary and its owning biobanks, ready for pure aggregation.
    """
    from survey_mucp_quantities import extract_modality_quantities

    rows = copy.deepcopy(rows)
    questions = {"wgs": "C.omics_data.wgs", "plasma": "C.biospecimens.plasma"}
    definitions = [{"id": key, "label": key, "question_id": question,
                    "kind": "data_modality" if key == "wgs" else "biospecimen",
                    "qualifier_measurement": "whole"} for key, question in questions.items()]
    for row in rows:
        for link in row["modality_links"]:
            link["question_id"] = questions[link["modality_id"]]
    banks = _banks_for(*rows)
    for bank in banks:
        for scope in bank["scopes"].values():
            scope.update(copy.deepcopy((scope_updates or {}).get(scope["scope_id"], {})))
        for row in rows:
            if row["biobank_id"] != bank["biobank_id"]:
                continue
            record = next(item for item in bank["mucp_source_records"]
                          if item["record_id"] == row["source_record_id"])
            wording = f"{row['value']} {row['source_unit']}"
            total = {"value": row["value"], "unit": row["source_unit"],
                     "relation": row["relation"], "temporal_status": "unspecified"}
            if row["linkage"] == "collection_size_context":
                bank["scopes"][row["scope_id"]].setdefault("metadata", {})["count"] = {
                    "raw_text": wording, "reported_total": total,
                    "evidence": copy.deepcopy(row["source_refs"]),
                }
            elif row["linkage"] == "submission_size_context":
                bank["scopes"][row["scope_id"]]["input_json_pointer"] = "/responses/0"
                evidence = {"survey": "MuCP", "evidence_id": row["quantity_evidence_id"],
                            "source_record_id": row["source_record_id"], "scope_id": row["scope_id"],
                            "question_id": "B.count", "question_label": "Reported individuals",
                            "kind": "text_field", "raw_text": wording,
                            "extensions": {"reported_total": total},
                            "source_refs": copy.deepcopy(row["source_refs"])}
                record["evidence"].append(evidence)
                bank["evidence"].append(copy.deepcopy(evidence))
            else:
                for evidence in bank["evidence"] + record["evidence"]:
                    if evidence["evidence_id"] in {link["evidence_id"] for link in row["modality_links"]}:
                        evidence["qualifier_text"] = wording
            record["metadata"]["source_ids"] = sorted(set(record["metadata"]["source_ids"])
                | {ref["source_id"] for ref in row["source_refs"]})
        for record in bank["mucp_source_records"]:
            record["scopes"] = [copy.deepcopy(scope) for scope in bank["scopes"].values()
                                if scope["source_record_id"] == record["record_id"]]
    return extract_modality_quantities(banks, definitions), banks


def test_audit_unlinked_submissions_are_withheld_but_proven_identity_reconciles():
    """Repeated submissions need reporting-scope proof before addition or collapse.

    Returns:
        None. Unlinked counts are withheld; proven equal identities retain both references.
    """
    from survey_mucp_aggregation import aggregate_modality_quantities

    rows = [_quantity("A", "AT", rid, rid, None, 100, ["wgs"],
                      linkage="submission_size_context") for rid in ("R1", "R2")]
    summary, banks = _audit_extract(rows)
    before = copy.deepcopy((summary, banks))
    result = aggregate_modality_quantities(summary, banks)
    assert result["modality_totals"][0]["reported_total"] is None
    assert result["country_totals"][0]["reported_total"] is None
    assert any(row["code"] == "ambiguous_submission_scopes" for row in result["diagnostics"])
    assert (summary, banks) == before

    updates = {rid: {"analytical_scope_id": "whole-bank",
                    "analytical_scope_basis": "reviewed_cross_record_identity"} for rid in ("R1", "R2")}
    summary, banks = _audit_extract(rows, updates)
    proven = aggregate_modality_quantities(summary, banks)
    assert proven["country_totals"][0]["reported_total"] == 100
    assert len(proven["contributions"][0]["quantity_ids"]) == 2

    updates = {rid: {"analytical_scope_id": "population-" + rid,
                    "analytical_scope_basis": "reviewed_distinct_reporting_scope"} for rid in ("R1", "R2")}
    summary, banks = _audit_extract(rows, updates)
    distinct = aggregate_modality_quantities(summary, banks)
    assert distinct["country_totals"][0]["reported_total"] == 200


@pytest.mark.parametrize("parent_modalities,expected_wgs", [(["wgs", "plasma"], 100), (["plasma"], 20)])
def test_audit_hierarchy_prefers_reporting_ancestor_per_view(parent_modalities, expected_wgs):
    """Country and modality views select their own topmost reporting ancestor.

    Args:
        parent_modalities: Modalities explicitly reported by the parent collection.
        expected_wgs: WGS total after selecting only WGS-reporting ancestors.

    Returns:
        None. The country total is 100; a child-only modality remains represented.
    """
    from survey_mucp_aggregation import aggregate_modality_quantities

    rows = [_quantity("A", "AT", "R", "R:P", "P", 100, parent_modalities),
            _quantity("A", "AT", "R", "R:C", "C", 20, ["wgs"])]
    summary, banks = _audit_extract(rows, {"R:C": {"relationship": {"parent_collection_id": "P"}}})
    before = copy.deepcopy((summary, banks))
    result = aggregate_modality_quantities(summary, banks)
    assert result["country_totals"][0]["reported_total"] == 100
    totals = {row["modality_id"]: row["reported_total"] for row in result["modality_totals"]}
    assert totals == {"plasma": 100, "wgs": expected_wgs}
    assert any(row["reason"] == "covered_by_reporting_ancestor" for row in result["excluded_contributions"])
    assert (summary, banks) == before


@pytest.mark.parametrize("relationships,reason", [
    ({"R:P": {"parent_collection_id": "C"}, "R:C": {"parent_collection_id": "P"}}, "collection_hierarchy_cycle"),
    ({"R:C": {"parent_collection_id": ["P", "Q"]}}, "ambiguous_collection_parent"),
])
def test_audit_hierarchy_cycles_and_ambiguous_parents_are_withheld(relationships, reason):
    """Invalid parent evidence fails closed without recursive traversal.

    Args:
        relationships: Explicit source relationships keyed by local scope ID.
        reason: Required diagnostic code for the invalid hierarchy.

    Returns:
        None. No sum combines quantities belonging to an unresolved hierarchy.
    """
    from survey_mucp_aggregation import aggregate_modality_quantities

    rows = [_quantity("A", "AT", "R", "R:P", "P", 100, ["wgs"]),
            _quantity("A", "AT", "R", "R:C", "C", 20, ["wgs"])]
    updates = {sid: {"relationship": relationship} for sid, relationship in relationships.items()}
    summary, banks = _audit_extract(rows, updates)
    result = aggregate_modality_quantities(summary, banks)
    assert any(row["code"] == reason for row in result["diagnostics"])
    assert all(row["reported_total"] is None for row in result["country_totals"])


@pytest.mark.parametrize("same_id,same_label", [(True, False), (False, True)])
def test_audit_native_cross_record_collection_repeats_are_ambiguous(same_id, same_label):
    """Local ID or label repetitions across responses indicate unresolved overlap.

    Args:
        same_id: Whether both response-local collection identifiers match.
        same_label: Whether both source collection labels match.

    Returns:
        None. Repeated native scopes are withheld without guessing a merged identity.
    """
    from survey_mucp_aggregation import aggregate_modality_quantities

    rows = [_quantity("A", "AT", "R1", "R1:C1", "C1", 100, ["wgs"]),
            _quantity("A", "AT", "R2", "R2:C1", "C1" if same_id else "C2", 100, ["wgs"])]
    updates = {"R1:C1": {"label": "Cancer follow-up cohort"},
               "R2:C1": {"label": "Cancer follow-up cohort" if same_label else "Different wording"}}
    summary, banks = _audit_extract(rows, updates)
    result = aggregate_modality_quantities(summary, banks)
    assert result["country_totals"][0]["reported_total"] is None
    assert any(row["code"] == "ambiguous_native_collection_repeats" for row in result["diagnostics"])
    assert len(result["contributions"]) == 2


@pytest.mark.parametrize("canonical", [False, True])
def test_audit_known_distinct_and_same_record_local_collections_remain_additive(canonical):
    """Known distinct collections and distinct local scopes in one record sum safely.

    Args:
        canonical: Use different Directory IDs across responses instead of local IDs in one.

    Returns:
        None. The supported 100 plus 20 control still reports 120.
    """
    from survey_mucp_aggregation import aggregate_modality_quantities

    ids = ["bbmri-eric:ID:AT_A:collection:P", "bbmri-eric:ID:AT_A:collection:C"] if canonical else ["P", "C"]
    rows = [_quantity("A", "AT", "R1", "R1:P", ids[0], 100, ["wgs"]),
            _quantity("A", "AT", "R2" if canonical else "R1", "R2:C", ids[1], 20, ["wgs"])]
    summary, banks = _audit_extract(rows)
    result = aggregate_modality_quantities(summary, banks)
    assert result["country_totals"][0]["reported_total"] == 120


@pytest.mark.parametrize("second_value,expected", [(100, 100), (90, None)])
def test_audit_direct_canonical_collection_repeats_reconcile_per_modality(second_value, expected):
    """Same canonical collection direct counts reconcile independently of quantity IDs.

    Args:
        second_value: Repeated count, equal to or conflicting with the first source.
        expected: Reconciled direct total, or null when the sources conflict.

    Returns:
        None. Equal direct counts retain references; conflicts are withheld.
    """
    from survey_mucp_aggregation import aggregate_modality_quantities

    cid = "bbmri-eric:ID:AT_A:collection:shared"
    rows = [_quantity("A", "AT", "R1", "R1:C1", cid, 100, ["wgs"], linkage="modality_specific"),
            _quantity("A", "AT", "R2", "R2:C1", cid, second_value, ["wgs"], linkage="modality_specific")]
    summary, banks = _audit_extract(rows)
    result = aggregate_modality_quantities(summary, banks)
    assert result["modality_totals"][0]["reported_total"] == expected
    assert result["country_totals"] == []
    if expected is not None:
        assert len(result["contributions"]) == 1
        assert len(result["contributions"][0]["quantity_ids"]) == 2
        assert len(result["contributions"][0]["source_refs"]) == 2


def test_audit_direct_unlinked_submissions_do_not_sum_populations():
    """Direct measurements from unlinked submissions need independent scope proof.

    Returns:
        None. Direct modality totals withhold unresolved repeated populations.
    """
    from survey_mucp_aggregation import aggregate_modality_quantities

    rows = [_quantity("A", "AT", rid, rid, None, 100, ["wgs"], linkage="modality_specific")
            for rid in ("R1", "R2")]
    summary, banks = _audit_extract(rows)
    result = aggregate_modality_quantities(summary, banks)
    assert result["modality_totals"][0]["reported_total"] is None
    assert result["country_totals"] == []


def test_aggregation_separates_direct_counts_and_submission_fallback():
    """Prefer collection totals over submission fallback and never mix direct points.

    Returns:
        None. Distinct reporting bases retain independent totals and explanations.
    """
    from survey_mucp_aggregation import aggregate_modality_quantities

    collection = _quantity("A", "AT", "RESP-A", "RESP-A-C1", "RESP-A-C1", 100, ["wgs"])
    submission = _quantity("A", "AT", "RESP-A", "RESP-A", None, 150, ["wgs"],
                           linkage="submission_size_context")
    direct_gwas = _quantity("A", "AT", "RESP-A", "RESP-A-C1", "RESP-A-C1", 12,
                            ["gwas"], linkage="modality_specific", quantity_id="direct-gwas")
    result = aggregate_modality_quantities(
        {"observations": [collection, submission, direct_gwas]},
        _banks_for(collection, submission, direct_gwas))

    totals = {(item["modality_id"], item["basis"]): item["reported_total"]
              for item in result["modality_totals"]}
    assert totals[("wgs", "collection")] == 100
    assert totals[("wgs", "submission_fallback")] is None
    assert totals[("gwas", "direct_modality")] == 12
    assert all(total["basis"] != "direct_modality" for total in result["country_totals"])
    assert any(item.get("reason") == "collection_counts_preferred"
               for item in result["excluded_contributions"])

    direct_wgs = _quantity("B", "DE", "RESP-B", "RESP-B-C1", "RESP-B-C1", 5000,
                           ["wgs"], linkage="modality_specific", quantity_id="direct-wgs")
    direct_gwas = _quantity("B", "DE", "RESP-B", "RESP-B-C1", "RESP-B-C1", 12000,
                            ["gwas"], linkage="modality_specific", quantity_id="direct-gwas")
    direct_result = aggregate_modality_quantities(
        {"observations": [direct_gwas, direct_wgs]}, _banks_for(direct_gwas, direct_wgs))
    direct_totals = {item["modality_id"]: item["reported_total"]
                     for item in direct_result["modality_totals"]}
    assert direct_totals == {"gwas": 12000, "wgs": 5000}
    assert direct_result["country_totals"] == []
    assert {row["modality_id"] for row in result["modality_totals"]} == {"gwas", "wgs"}


def test_aggregation_keeps_zero_distinct_from_missing_and_excludes_qualified_time_or_unit():
    """Only exact, compatible, supported-unit reports enter aggregate bars.

    Returns:
        None. Zero is a contribution; bounds, non-current periods and unclear units stay excluded.
    """
    from survey_mucp_aggregation import aggregate_modality_quantities

    rows = [
        _quantity("A", "AT", "RESP-A", "RESP-A-C0", "RESP-A-C0", 0, ["plasma"]),
        _quantity("A", "AT", "RESP-A", "RESP-A-C1", "RESP-A-C1", 5, ["plasma"],
                  relation="approximate", quantity_id="approx"),
        _quantity("A", "AT", "RESP-A", "RESP-A-C4", "RESP-A-C4", 6, ["plasma"],
                  relation="less_than", quantity_id="upper-bound"),
        _quantity("A", "AT", "RESP-A", "RESP-A-C5", "RESP-A-C5", 8, ["plasma"],
                  relation="greater_than", quantity_id="lower-bound"),
        _quantity("A", "AT", "RESP-A", "RESP-A-C2", "RESP-A-C2", 7, ["plasma"],
                  temporal_status="historical", quantity_id="historical"),
        _quantity("A", "AT", "RESP-A", "RESP-A-C3", "RESP-A-C3", 9, ["plasma"],
                  unit="unit_unclear", source_unit="FFPE blocks", quantity_id="unclear"),
    ]
    result = aggregate_modality_quantities({"observations": rows}, _banks_for(*rows))
    assert result["country_totals"][0]["reported_total"] == 0
    assert result["country_totals"][0]["segments"][0]["value"] == 0
    reasons = {item["reason"] for item in result["excluded_contributions"]}
    assert {"qualified_relation", "non_current_time", "unsupported_unit"} <= reasons
    assert {"upper-bound", "lower-bound"} <= {
        quantity_id for item in result["excluded_contributions"] for quantity_id in item["quantity_ids"]}


def test_aggregation_withholds_same_scope_mixed_time_evidence():
    """Same-scope current and future reports cannot be reconciled into one value.

    Returns:
        None. Both source rows remain excluded under a temporal-conflict diagnostic.
    """
    from survey_mucp_aggregation import aggregate_modality_quantities

    current = _quantity("A", "AT", "RESP-A", "RESP-A-C1", "RESP-A-C1", 10, ["plasma"])
    future = _quantity("A", "AT", "RESP-A", "RESP-A-C1", "RESP-A-C1", 10, ["plasma"],
                       temporal_status="future", quantity_id="future-same-scope")
    result = aggregate_modality_quantities(
        {"observations": [current, future]}, _banks_for(current, future))
    assert result["country_totals"][0]["reported_total"] is None
    assert all(item["reason"] == "same_scope_mixed_temporal_status"
               for item in result["excluded_contributions"])
    assert result["diagnostics"][0]["code"] == "same_scope_mixed_temporal_status"


def test_aggregation_keeps_temporal_totals_separate_and_reports_unreported_siblings():
    """Do not mix historical/current rows and identify missing sibling count scopes.

    Returns:
        None. Exact views retain temporal basis while diagnostics describe incomplete reporting.
    """
    from survey_mucp_aggregation import aggregate_modality_quantities

    current = _quantity("A", "AT", "RESP-A", "RESP-A-C1", "RESP-A-C1", 10, ["plasma"])
    future = _quantity("A", "AT", "RESP-A", "RESP-A-C2", "RESP-A-C2", 20, ["plasma"],
                       temporal_status="future", quantity_id="future")
    banks = _banks_for(current, future)
    banks[0]["scopes"]["RESP-A-C3"] = {
        "scope_id": "RESP-A-C3", "source_record_id": "RESP-A", "kind": "collection",
        "collection_id": "RESP-A-C3",
    }
    result = aggregate_modality_quantities({"observations": [current, future]}, banks)
    exact = [total for total in result["country_totals"] if total["basis"] == "collection"]
    assert {(row["temporal_status"], row["reported_total"]) for row in exact} == {
        ("current", 10), ("future", None)}
    assert any(row["reason"] == "non_current_time" for row in result["excluded_contributions"])
    assert any(item["code"] == "incomplete_collection_reporting"
               and item["unreported_collection_scopes"] == ["RESP-A-C3"]
               for item in result["diagnostics"])


def test_aggregation_rejects_dangling_and_foreign_quantity_scope_references():
    """Invalid source ownership is a hard error rather than silently omitted data.

    Returns:
        None. A source row outside its declared bank/scope cannot enter totals.
    """
    from survey_mucp_aggregation import aggregate_modality_quantities

    row = _quantity("A", "AT", "RESP-A", "RESP-A-C1", "RESP-A-C1", 100, ["plasma"])
    with pytest.raises(ValueError, match="scope|ownership|biobank"):
        aggregate_modality_quantities({"observations": [row]}, [])


def test_aggregation_rejects_foreign_modality_evidence_links():
    """A source modality link must be owned by that response and exact scope.

    Returns:
        None. Foreign or dangling link references fail closed.
    """
    from survey_mucp_aggregation import aggregate_modality_quantities

    row = _quantity("A", "AT", "RESP-A", "RESP-A-C1", "RESP-A-C1", 100, ["plasma"])
    bank = _banks_for(row)
    bank[0]["mucp_source_records"][0]["evidence"] = []
    with pytest.raises(ValueError, match="modality|evidence|link"):
        aggregate_modality_quantities({"observations": [row]}, bank)


@pytest.mark.parametrize(("wording", "canonical", "literal"), [
    ("100 research participants", "donors", "research participants"),
    ("100 aliquots", "aliquots", "aliquots"),
])
def test_extractor_accepts_approved_literal_unit_aliases(wording, canonical, literal):
    """Parse approved full-answer aliases and preserve the literal source unit.

    Args:
        wording: Exact source qualifier spelling.
        canonical: Expected analysis unit.
        literal: Expected untouched token in ``source_unit``.

    Returns:
        None. Parsing and canonicalization do not rewrite source wording.
    """
    from tests.test_survey_mucp_quantities import DEFINITIONS, bank
    from survey_mucp_quantities import extract_modality_quantities

    result = extract_modality_quantities([bank([("C.omics_data.gwas", wording)])], DEFINITIONS)
    assert len(result["observations"]) == 1
    assert result["observations"][0]["unit"] == canonical
    assert result["observations"][0]["source_unit"] == literal
