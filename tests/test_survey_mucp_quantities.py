"""Evidence-safe MuCP modality quantity extraction and chart regressions."""

import copy

import pytest

from survey_mucp_quantities import extract_modality_quantities


DEFINITIONS = [
    {"id": "gwas", "label": "GWAS", "question_id": "C.omics_data.gwas", "kind": "data_modality", "qualifier_measurement": "whole"},
    {"id": "wgs", "label": "WGS", "question_id": "C.omics_data.wgs", "kind": "data_modality", "qualifier_measurement": "whole"},
    {"id": "other", "label": "Other", "question_id": "C.omics_data.other", "kind": "data_modality", "qualifier_measurement": "curated_only"},
]


def table_bank(cell="100", relation="reported_value", temporal="unspecified", header="Num. individuals"):
    """Build one owned collection count with an exact table-cell source witness.

    Args:
        cell: Literal measurement wording retained in the referenced table cell.
        relation: Independently projected count relation to compare against the cell.
        temporal: Independently projected temporal status needing literal source proof.
        header: Literal column header proving the count unit and optional time.

    Returns:
        Synthetic combined biobank with one named collection and two modality links.
    """
    item = bank([])
    item["name"] = "Synthetic institute"
    scope = {"scope_id": "R1:collection:C1", "source_record_id": "R1", "kind": "collection",
             "label": "Cancer follow-up cohort", "collection_id": "C1",
             "input_json_pointer": "/responses/0/collections/0",
             "metadata": {"count": {"raw_text": "100", "reported_total": {
                 "value": 100, "unit": "individuals", "relation": relation, "temporal_status": temporal},
                 "evidence": [{"source_id": "SRC1", "locator": "table[1]:row[4]:cell[3]"}]}}}
    item["scopes"][scope["scope_id"]] = scope
    item["mucp_source_records"][0]["scopes"].append(copy.deepcopy(scope))
    item["mucp_source_records"][0]["metadata"]["structured_tables"] = [{"index": 0, "rows": [
        [{"text": "Collection", "xml_grid_span": "3"}],
        [{"text": "Criteria", "xml_grid_span": "3"}],
        [{"text": "Name"}, {"text": "Design"}, {"text": header}],
        [{"text": "C1"}, {"text": "Study"}, {"text": cell}]]}]
    for index, question in enumerate(("C.omics_data.gwas", "C.omics_data.wgs"), 1):
        answer = {"survey": "MuCP", "evidence_id": f"C-{index}", "source_record_id": "R1",
                  "question_id": question, "question_label": question, "scope_id": scope["scope_id"],
                  "kind": "structured_answer", "normalized_value": "affirmed", "qualifier_text": None,
                  "source_refs": [{"source_id": "SRC1", "locator": f"collections[0].answers[{index}]"}]}
        item["evidence"].append(answer)
        item["mucp_source_records"][0]["evidence"].append(copy.deepcopy(answer))
    return item


@pytest.mark.parametrize("cell,relation", [
    ("over 100", "greater_than"), ("more than 100", "greater_than"), (">100", "greater_than"),
    (">=100", "at_least"), ("at least 100", "at_least"),
    ("less than 100", "less_than"), ("<100", "less_than"),
    ("<=100", "at_most"), ("at most 100", "at_most"),
    ("about 100", "approximate"), ("approximately 100", "approximate"), ("approx. 100", "approximate")])
def test_table_count_bound_aliases_agree_with_source(cell, relation):
    """A literal table bound cannot become an exact quantity or be rejected as exact.

    Args:
        cell: Complete source count wording containing one approved relation alias.
        relation: Canonical typed relation independently expected from that alias.

    Returns:
        None. Source-matching bounds survive and source-disagreeing exact totals fail.
    """
    correct = extract_modality_quantities([table_bank(cell, relation)], DEFINITIONS)
    assert len(correct["observations"]) == 1
    row = correct["observations"][0]
    assert row["relation"] == relation and row["original_wording"] == cell
    assert row["unit_proof"]["relation"] == relation
    wrong = extract_modality_quantities([table_bank(cell, "reported_value")], DEFINITIONS)
    assert not wrong["observations"]
    assert any(item["reason"] == "missing_unit_proof" for item in wrong["unlinked_quantities"])


@pytest.mark.parametrize("cell,header,temporal", [
    ("over 100 (historical)", "Num. individuals", "historical"),
    ("future: over 100", "Number of individuals", "future"),
    ("over 100", "Number of individuals (current)", "current"),
    ("over 100 (cumulative)", "Num. individuals", "cumulative"),
    ("over 100 (previous)", "Num. individuals", "previous")])
def test_table_count_time_requires_literal_source_proof(cell, header, temporal):
    """Time survives only when attached explicitly to the source cell or header.

    Args:
        cell: Exact count-cell wording, optionally carrying an explicit time label.
        header: Exact count-column header, optionally carrying an explicit time label.
        temporal: Expected status independently specified by that source label.

    Returns:
        None. Supported labels survive and a fabricated projected time is rejected.
    """
    result = extract_modality_quantities([table_bank(cell, "greater_than", temporal, header)], DEFINITIONS)
    assert len(result["observations"]) == 1
    row = result["observations"][0]
    assert row["temporal_status"] == temporal
    assert row["unit_proof"]["temporal_status"] == temporal
    unsupported = extract_modality_quantities([table_bank("over 100", "greater_than", temporal)], DEFINITIONS)
    assert not unsupported["observations"]


@pytest.mark.parametrize("corruption", ["unknown_header", "duplicate_header", "duplicate_table",
                                        "spanned_header", "spanned_value", "conflicting_time"])
def test_table_count_rejects_ambiguous_grid_and_header_witnesses(corruption):
    """Ambiguous count headers, table IDs, spans and time labels are ineligible.

    Args:
        corruption: Exact table/source ambiguity inserted into the owned fixture.

    Returns:
        None. No ambiguous cell becomes a count point under any context link.
    """
    item = table_bank("over 100", "greater_than")
    tables = item["mucp_source_records"][0]["metadata"]["structured_tables"]
    rows = tables[0]["rows"]
    if corruption == "unknown_header":
        rows[2][2]["text"] = "Num. subjects"
    elif corruption == "duplicate_header":
        rows[1] = copy.deepcopy(rows[2])
    elif corruption == "duplicate_table":
        tables.append(copy.deepcopy(tables[0]))
    elif corruption == "spanned_header":
        rows[2][0]["xml_grid_span"] = "2"
    elif corruption == "spanned_value":
        rows[3][0]["xml_grid_span"] = "2"
    else:
        rows[2][2]["text"] = "Num. individuals (historical)"
        rows[3][2]["text"] = "over 100 (future)"
    assert not extract_modality_quantities([item], DEFINITIONS)["observations"]


@pytest.mark.parametrize("header,unit", [("Num. samples", "samples"), ("Number of donors", "donors"),
                                        ("Participants", "participants"), ("number of individuals", "individuals")])
def test_table_unit_header_is_literal_independent_proof(header, unit):
    """Supported literal headers prove distinct units without conversion.

    Args:
        header: Literal count-column header naming one supported measurement unit.
        unit: Normalized source unit independently expected from that header.

    Returns:
        None. Header agreement retains the original unit and a bound relation.
    """
    item = table_bank("at most 100", "at_most", header=header)
    item["scopes"]["R1:collection:C1"]["metadata"]["count"]["reported_total"]["unit"] = unit
    rows = extract_modality_quantities([item], DEFINITIONS)["observations"]
    derived_unit = "donors" if unit in {"donors", "individuals", "participants"} else unit
    literal_unit = "Participants" if header == "Participants" else unit
    assert len(rows) == 1 and rows[0]["unit"] == derived_unit and rows[0]["source_unit"] == literal_unit
    assert rows[0]["relation"] == "at_most"


@pytest.mark.parametrize("raw,temporal", [("current: over 100 individuals", "current"),
                                         ("over 100 (future)", "future")])
def test_root_context_preserves_source_relation_and_time(raw, temporal):
    """The submission count path obeys the same relation/time source agreement.

    Args:
        raw: Complete B.count wording with a literal unit or documented numeric unit.
        temporal: Time status explicitly present in the count wording.

    Returns:
        None. Source-backed submission context retains the bound and witnessed time.
    """
    item = bank([("C.omics_data.gwas", "")])
    count = {"survey": "MuCP", "evidence_id": "COUNT", "source_record_id": "R1", "question_id": "B.count",
             "question_label": "Number of individuals", "scope_id": "R1:submission", "kind": "text_field",
             "normalized_value": raw, "raw_text": raw, "source_refs": [{"source_id": "SRC1", "locator": "B.count"}],
             "extensions": {"reported_total": {"value": 100, "unit": "individuals", "relation": "greater_than",
                                                "temporal_status": temporal}}}
    item["evidence"].append(count)
    item["mucp_source_records"][0]["evidence"].append(copy.deepcopy(count))
    rows = extract_modality_quantities([item], DEFINITIONS)["observations"]
    assert len(rows) == 1 and rows[0]["linkage"] == "submission_size_context"
    assert rows[0]["relation"] == "greater_than" and rows[0]["temporal_status"] == temporal


def test_table_witness_cannot_be_overridden_by_projected_raw_text():
    """A literal-looking projected count cannot override a referenced source bound.

    Returns:
        None. Source disagreement remains ineligible even when raw_text looks exact.
    """
    item = table_bank("over 100", "reported_value")
    item["scopes"]["R1:collection:C1"]["metadata"]["count"]["raw_text"] = "100 individuals"
    assert not extract_modality_quantities([item], DEFINITIONS)["observations"]


def bank(qualifiers=None):
    """Build an owned synthetic submission with explicit answer locators.

    Args:
        qualifiers: Question/qualifier pairs for affirmed MuCP options.

    Returns:
        One detached combined biobank carrying native evidence and a source manifest.
    """
    qualifiers = qualifiers or []
    evidence = [{"survey": "MuCP", "evidence_id": f"E-{index}", "source_record_id": "R1",
                 "question_id": question, "question_label": question, "scope_id": "R1:submission",
                 "kind": "structured_answer", "normalized_value": "affirmed", "qualifier_text": qualifier,
                 "raw_text": qualifier, "source_refs": [{"source_id": "SRC1", "locator": f"answers[{index}]"}]}
                for index, (question, qualifier) in enumerate(qualifiers)]
    scope = {"scope_id": "R1:submission", "source_record_id": "R1", "kind": "submission",
             "input_json_pointer": "/responses/0", "collection_id": None}
    record = {"record_id": "R1", "survey": "MuCP", "scopes": [scope], "evidence": copy.deepcopy(evidence),
              "metadata": {"source_ids": ["SRC1"], "quantity_index": [], "structured_tables": []}}
    return {"biobank_id": "bbmri-eric:ID:AT_ONE", "country": "AT", "evidence": evidence,
            "scopes": {scope["scope_id"]: scope}, "mucp_source_records": [record]}


def test_direct_full_qualifiers_keep_units_bounds_and_provenance():
    """Full affirmed qualifiers, including participants and zero, are direct points.

    Returns:
        None. The result keeps source IDs, wording, references and source units.
    """
    item = bank([("C.omics_data.gwas", "over 12,000 participants"),
                 ("C.omics_data.wgs", "0 samples")])
    original = copy.deepcopy(item)
    result = extract_modality_quantities([item], DEFINITIONS)
    rows = result["observations"]
    assert [(r["value"], r["unit"], r["relation"]) for r in rows] == [
        (12000, "donors", "greater_than"), (0, "samples", "reported_value")]
    assert [row["source_unit"] for row in rows] == ["participants", "samples"]
    assert all(r["linkage"] == "modality_specific" for r in rows)
    assert rows[0]["quantity_evidence_id"] == rows[0]["modality_links"][0]["evidence_id"]
    assert rows[0]["source_record_id"] == "R1" and rows[0]["country"] == "AT"
    assert rows[0]["source_refs"] == [{"source_id": "SRC1", "locator": "answers[0]"}]
    assert rows[0]["original_wording"] == "over 12,000 participants"
    assert rows[0]["temporal_status"] == "unspecified"
    assert item == original
    assert result == extract_modality_quantities([item], DEFINITIONS)


def test_projected_gwas_wgs_participant_qualifier_shape():
    """Audited GWAS/WGS whole qualifiers survive nonbreaking-space decoding.

    Returns:
        None. Two named omics options give separate donor-unit points, retaining source units.
    """
    item = bank([("C.omics_data.gwas", "over 12\u00a0000 participants"),
                 ("C.omics_data.wgs", "over 5\u202f000 participants")])
    rows = extract_modality_quantities([item], DEFINITIONS)["observations"]
    assert [(row["value"], row["unit"], row["relation"]) for row in rows] == [
        (12000, "donors", "greater_than"), (5000, "donors", "greater_than")]
    assert {row["source_unit"] for row in rows} == {"participants"}
    assert {row["question_id"] for row in rows} == {"C.omics_data.gwas", "C.omics_data.wgs"}


@pytest.mark.parametrize("qualifier", ["12,34 participants", "n=12", "12 participants and 4 samples",
                                      "about >12 participants", "metagenome sequencing 12 participants"])
def test_unsupported_qualifiers_are_unlinked(qualifier):
    """Do not mine numeric mentions or truncate mixed narrative into a point.

    Args:
        qualifier: Unsupported complete qualifier to exercise.

    Returns:
        None. The candidate remains reviewable but does not become a measurement.
    """
    question = "C.omics_data.other" if qualifier.startswith("metagenome") else "C.omics_data.gwas"
    result = extract_modality_quantities([bank([(question, qualifier)])], DEFINITIONS)
    assert not result["observations"]
    assert result["unlinked_quantities"][0]["reason"] in {"unsupported_qualifier", "no_explicit_link"}


def test_collection_context_once_for_two_links_not_modality_counts():
    """One table-proven collection size carries two links but no allocation.

    Returns:
        None. The collection count is one context row, not two direct counts.
    """
    item = bank([])
    scope = {"scope_id": "R1:collection:C1", "source_record_id": "R1", "kind": "collection",
             "collection_id": "C1", "input_json_pointer": "/responses/0/collections/0",
             "metadata": {"count": {"raw_text": "100", "reported_total": {"value": 100, "unit": "individuals",
                            "relation": "reported_value", "temporal_status": "unspecified"},
                            "evidence": [{"source_id": "SRC1", "locator": "table[1]:row[4]:cell[3]"}]}}}
    item["scopes"][scope["scope_id"]] = scope
    item["mucp_source_records"][0]["scopes"].append(copy.deepcopy(scope))
    item["mucp_source_records"][0]["metadata"]["structured_tables"] = [
        {"index": 0, "rows": [[{"text": "Collection", "xml_grid_span": "3"}],
                              [{"text": "Criteria", "xml_grid_span": "3"}],
                              [{"text": "Name"}, {"text": "Design"}, {"text": "Num. individuals"}],
                              [{"text": "C1"}, {"text": "Study"}, {"text": "100"}]]}]
    for index, question in enumerate(("C.omics_data.gwas", "C.omics_data.wgs"), 1):
        answer = {"survey": "MuCP", "evidence_id": f"C-{index}", "source_record_id": "R1",
                  "question_id": question, "question_label": question, "scope_id": scope["scope_id"],
                  "kind": "structured_answer", "normalized_value": "affirmed", "qualifier_text": None,
                  "source_refs": [{"source_id": "SRC1", "locator": f"collections[0].answers[{index}]"}]}
        item["evidence"].append(answer)
        item["mucp_source_records"][0]["evidence"].append(copy.deepcopy(answer))
    result = extract_modality_quantities([item], DEFINITIONS)
    assert len(result["observations"]) == 1
    row = result["observations"][0]
    assert row["linkage"] == "collection_size_context" and row["unit"] == "donors"
    assert row["source_unit"] == "individuals"
    assert {link["modality_id"] for link in row["modality_links"]} == {"gwas", "wgs"}
    assert row["value"] == 100 and row["unit_proof"]["kind"] == "table_header"


def test_duplicate_native_id_and_dangling_scope_rejected():
    """Corrupt ownership is a hard error rather than an unlinked measurement.

    Returns:
        None. Both identifier collisions and unknown scope IDs raise ValueError.
    """
    item = bank([("C.omics_data.gwas", "12 participants")])
    duplicated = copy.deepcopy(item)
    duplicated["evidence"].append(copy.deepcopy(duplicated["evidence"][0]))
    with pytest.raises(ValueError):
        extract_modality_quantities([duplicated], DEFINITIONS)
    dangling = copy.deepcopy(item)
    dangling["evidence"][0]["scope_id"] = "missing"
    with pytest.raises(ValueError):
        extract_modality_quantities([dangling], DEFINITIONS)


def test_root_count_does_not_inherit_child_and_bc_are_distinct():
    """Submission count links only root answers and Part B/C stay independent.

    Returns:
        None. Equal numbers in two questions never collapse or allocate to a child.
    """
    item = bank([("C.omics_data.gwas", "")])
    for index, qid in enumerate(("B.count", "C.count"), 1):
        count = {"survey": "MuCP", "evidence_id": f"Q-{index}", "source_record_id": "R1",
                 "question_id": qid, "question_label": "Number of individuals", "scope_id": "R1:submission",
                 "kind": "text_field", "normalized_value": "100", "raw_text": "100",
                 "extensions": {"reported_total": {"value": 100, "unit": "individuals",
                                                  "relation": "reported_value"}},
                 "source_refs": [{"source_id": "SRC1", "locator": f"fields[{qid}]"}]}
        item["evidence"].append(count)
        item["mucp_source_records"][0]["evidence"].append(copy.deepcopy(count))
    child = {"scope_id": "R1:collection:C1", "kind": "collection", "source_record_id": "R1",
             "collection_id": "C1", "input_json_pointer": "/responses/0/collections/0"}
    item["scopes"][child["scope_id"]] = child
    item["mucp_source_records"][0]["scopes"].append(child)
    child_answer = {"survey": "MuCP", "evidence_id": "CHILD", "source_record_id": "R1",
                    "question_id": "C.omics_data.wgs", "question_label": "WGS", "scope_id": child["scope_id"],
                    "kind": "structured_answer", "normalized_value": "affirmed", "qualifier_text": None,
                    "source_refs": [{"source_id": "SRC1", "locator": "collections[0].answers[wgs]"}]}
    item["evidence"].append(child_answer)
    item["mucp_source_records"][0]["evidence"].append(copy.deepcopy(child_answer))
    rows = extract_modality_quantities([item], DEFINITIONS)["observations"]
    assert len(rows) == 2 and len({row["quantity_id"] for row in rows}) == 2
    assert {row["question_id"] for row in rows} == {"B.count", "C.count"}
    assert all(row["linkage"] == "submission_size_context" for row in rows)
    assert all([link["modality_id"] for link in row["modality_links"]] == ["gwas"] for row in rows)


def test_country_points_are_not_summed_or_relabelled():
    """Directory country partitions distinct direct points without aggregation.

    Returns:
        None. Each source measurement remains one point under its bank country.
    """
    first = bank([("C.omics_data.gwas", "12 participants")])
    second = bank([("C.omics_data.wgs", "at most 7 donors")])
    second["biobank_id"] = "bbmri-eric:ID:DE_TWO"
    second["country"] = "DE"
    second["mucp_source_records"][0]["country"] = "FR"
    result = extract_modality_quantities([second, first], DEFINITIONS)
    assert [(row["country"], row["value"], row["unit"]) for row in result["observations"]] == [
        ("AT", 12, "donors"), ("DE", 7, "donors")]
    assert result["observations"][0]["source_unit"] == "participants"
    assert result["coverage"]["cohort_N"] == 2
    gwas = next(row for row in result["coverage"]["by_modality"] if row["modality_id"] == "gwas")
    participants = next(row for row in gwas["by_unit"] if row["unit"] == "donors"
                        and row["linkage"] == "modality_specific")
    assert participants["point_count"] == 1
    assert participants["biobanks_with_source_points"] == 1
    assert participants["biobanks_without_eligible_points"] == 1
    assert "Directory biobank reported country" in result["interpretation"]["country_facet"]


def test_index_unit_and_disagreeing_typed_total_are_not_source_proof():
    """A numeric index or inconsistent projected total cannot certify units.

    Returns:
        None. Source wording wins over projected unit labels and remains unplotted.
    """
    item = bank([("C.omics_data.gwas", "")])
    count = {"survey": "MuCP", "evidence_id": "COUNT", "source_record_id": "R1",
             "question_id": "B.count", "question_label": "Number of individuals", "scope_id": "R1:submission",
             "kind": "text_field", "normalized_value": "12 samples", "raw_text": "12 samples",
             "extensions": {"reported_total": {"value": 12, "unit": "individuals",
                                              "relation": "reported_value"}},
             "source_refs": [{"source_id": "SRC1", "locator": "fields[B.count]"}]}
    item["evidence"].append(count)
    item["mucp_source_records"][0]["evidence"].append(copy.deepcopy(count))
    item["mucp_source_records"][0]["metadata"]["quantity_index"] = [
        {"field": "B.count", "value": 12, "unit": "individuals", "raw_token": "12",
         "evidence": [{"source_id": "SRC1", "locator": "fields[B.count]"}]}]
    result = extract_modality_quantities([item], DEFINITIONS)
    assert not result["observations"]
    assert any(row["reason"] == "missing_unit_proof" for row in result["unlinked_quantities"])
    assert any("unverified_index" in row for row in result["unlinked_quantities"])


@pytest.mark.parametrize("raw,expected", [("over12 participants", False), ("12.5 samples", False),
                                          ("1,000 000 donors", False), ("approx. 9 individuals", True),
                                          ("at least 2 samples", True), ("0 donors", True)])
def test_whole_grammar_rejects_mixed_or_partial_numbers(raw, expected):
    """Whole qualifier parsing does not silently trim, coerce or ignore clauses.

    Args:
        raw: Complete synthetic answer qualifier.
        expected: Whether exactly one direct point is semantically supported.

    Returns:
        None. Supported grammar matches exactly and rejects mixed separators.
    """
    result = extract_modality_quantities([bank([("C.omics_data.gwas", raw)])], DEFINITIONS)
    assert bool(result["observations"]) is expected


def test_derived_people_unit_is_canonical_and_literal_source_unit_is_retained():
    """Canonical donor units retain the literal participant wording separately.

    Returns:
        None. Only the derived unit is normalized; source evidence remains literal.
    """
    result = extract_modality_quantities([bank([("C.omics_data.gwas", "12 participants")])], DEFINITIONS)

    row = result["observations"][0]
    assert row["unit"] == "donors"
    assert row["source_unit"] == "participants"
    assert row["original_wording"] == "12 participants"
    assert result["coverage"]["by_modality"][0]["by_unit"]
    assert {item["unit"] for item in result["coverage"]["by_modality"][0]["by_unit"]} == {
        "donors", "samples", "aliquots"}


def test_canonical_aliases_do_not_mask_literal_total_unit_disagreement():
    """Validate total/header units literally before deriving canonical donor units.

    Returns:
        None. Individuals and participants both map to donors, but cannot satisfy
        a source-header mismatch merely through their shared analysis unit.
    """
    item = table_bank("100", header="Num. individuals")
    item["scopes"]["R1:collection:C1"]["metadata"]["count"]["reported_total"]["unit"] = "participants"

    result = extract_modality_quantities([item], DEFINITIONS)

    assert result["observations"] == []
    assert any(row["reason"] == "missing_unit_proof" for row in result["unlinked_quantities"])


def test_source_unit_retains_literal_token_spelling():
    """Do not lowercase or canonicalize the source-unit evidence field.

    Returns:
        None. ``unit`` is canonical while ``source_unit`` matches source spelling.
    """
    result = extract_modality_quantities([bank([("C.omics_data.gwas", "12 Participants")])], DEFINITIONS)

    row = result["observations"][0]
    assert row["unit"] == "donors"
    assert row["source_unit"] == "Participants"


def test_table_source_unit_retains_singular_header_token():
    """Carry the literal header token through validated collection projections.

    Returns:
        None. Singular donor wording remains separate from the canonical donors unit.
    """
    item = table_bank("100", header="Number of donor")
    item["scopes"]["R1:collection:C1"]["metadata"]["count"]["reported_total"]["unit"] = "donors"
    before = copy.deepcopy(item)
    row = extract_modality_quantities([item], DEFINITIONS)["observations"][0]
    assert row["unit"] == "donors"
    assert row["source_unit"] == "donor"
    assert item == before
