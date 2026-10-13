"""Explicit-unit descriptive counts and canonical association/intersection inputs."""

from collections import Counter
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from survey_evidence import plain, fingerprint
from survey_mucp_aggregation import canonical_quantity_unit, recover_quantity_answer
from survey_mucp_quantities import _count_measurement, _typed_total, verified_collection_count


MUCP_STATES = ("reported_yes_in_one_or_more_scopes", "explicitly_no_in_all_reported_applicable_scopes",
               "varying_across_scopes", "incomplete_or_qualified", "qualified_only",
               "unknown_or_unmarked", "conflicting", "conflicting_or_scope_uncertain")

STATE_LABELS = {
    "reported_yes_in_one_or_more_scopes": "Reported yes in at least one scope",
    "explicitly_no_in_all_reported_applicable_scopes": "Explicit no in all reported applicable scopes",
    "varying_across_scopes": "Varies across distinct collection scopes",
    "incomplete_or_qualified": "Incomplete scope coverage or qualified",
    "qualified_only": "Qualified evidence only",
    "unknown_or_unmarked": "Unknown or indeterminate",
    "conflicting": "Conflicting evidence in the same scope",
    "conflicting_or_scope_uncertain": "Conflict or uncertain scope relationship",
    "conflicting_submissions": "Conflicting submissions",
}


def classify_reported_checkbox_observation(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Classify one reduced MuCP checkbox observation for reported-pattern views.

    Args:
        observation: Reduced observation retaining its state, scope-coverage flags,
            unreported scope IDs and affirmative-evidence indicator.

    Returns:
        Eligibility, affirmative membership, variation note and exclusion reason.
        A dot means affirmative evidence in a represented scope; explicit No is an
        eligible false value. Unknown, conditional, conflicting and incomplete-scope
        observations are ineligible rather than converted to No.
    """
    state = str(observation.get("state", "missing"))
    incomplete = ("partial_scope_coverage" in observation.get("flags", [])
                  or bool(observation.get("unreported_scope_ids")))
    if state in {"reported_yes_in_one_or_more_scopes", "varying_across_scopes"}:
        if incomplete:
            return {"eligible": False, "affirmative": True,
                    "varies_by_collection": state == "varying_across_scopes",
                    "reason": "incomplete_scope_coverage"}
        elif state == "varying_across_scopes" and not observation.get("has_affirmative_evidence"):
            reason = "varying_without_affirmative_evidence"
        else:
            return {"eligible": True, "affirmative": True,
                    "varies_by_collection": state == "varying_across_scopes", "reason": None}
    elif state == "explicitly_no_in_all_reported_applicable_scopes":
        if incomplete:
            reason = "incomplete_scope_coverage"
        else:
            return {"eligible": True, "affirmative": False, "varies_by_collection": False, "reason": None}
    elif state == "incomplete_or_qualified":
        reason = "incomplete_scope_coverage"
    elif state == "conflicting_or_scope_uncertain":
        reason = "scope_uncertain"
    elif state == "missing":
        reason = "missing"
    else:
        reason = state
    return {"eligible": False, "affirmative": None, "varies_by_collection": False, "reason": reason}


def text_chunks(text: str, limit: int = 1400) -> list[str]:
    """Split long source text between tokens for printable table continuation rows.

    Args:
        text: Literal source wording to retain in presentation order.
        limit: Preferred maximum characters per chunk; single URL tokens stay intact.

    Returns:
        Nonempty list of ordered text chunks without truncating source tokens.
    """
    chunks: list[str] = []
    current = ""
    for part in re.findall(r"\S+\s*", text):
        if current and len(current) + len(part) > limit:
            chunks.append(current)
            current = ""
        current += part
    if current or not chunks:
        chunks.append(current)
    return chunks


def percentage(count: int, base: int) -> float | None:
    """Calculate a percentage without manufacturing a zero-denominator result.

    Args:
        count: Nonnegative number of included observations in the category.
        base: Explicit observation denominator, not number of selected options.

    Returns:
        Percentage rounded to four decimals, or null when no base exists.
    """
    return None if base == 0 else round(count * 100 / base, 4)


def select_chart_kind(statistics: Mapping[str, Any], policy: Mapping[str, Any] | None = None) -> str:
    """Choose shared chart semantics from declared response type, not answer wording.

    Args:
        statistics: Question summary with declared question_type and population.
        policy: Optional minimum-N cutoff; omitted retains existing SO2 chart selection.

    Returns:
        pie, bar, table or omitted according to semantics and explicit plotting policy.
    """
    kind = statistics["question_type"]
    if kind == "free_text":
        return "table"
    if statistics.get("population", {}).get("N", 0) < (policy or {}).get("minimum_n", 0):
        return "omitted"
    if kind == "single_choice":
        return "pie"
    if kind in {"multi_choice", "ordinal"}:
        return "bar"
    raise ValueError(f"Unsupported descriptive question type: {kind}")


def summarize_categorical(definition: Mapping[str, Any], observations: Sequence[Mapping[str, Any]], unit: str) -> dict[str, Any]:
    """Summarize one observation per biobank with explicit state and frequency bases.

    Args:
        definition: Declared question ID, label/type, category order and optional scope-state flag.
        observations: Already reduced biobank observations, including unknown/conflicting states.
        unit: Explicit analytical identity convention recorded with every question summary.

    Returns:
        Renderer-compatible counts plus canonical observation/evidence identities and
        denominators. Missing observations contribute only to the canonical Missing
        category; original unknown, qualified and conflicting states remain distinct.
    """
    if len({item["observation_id"] for item in observations}) != len(observations):
        raise ValueError("Duplicate analytical observation_id")
    state_mode = definition.get("scope_states", False) or any(item.get("state") in MUCP_STATES for item in observations)
    counts = Counter({category: 0 for category in definition.get("categories", [])})
    answering = sum(item.get("state") == "known" for item in observations)
    if state_mode:
        answering = sum(item.get("state") not in {"missing", "unknown_or_unmarked"} for item in observations)
    contributions = []
    diagnostics = Counter()
    for item in observations:
        state = item.get("state", "missing")
        values = [] if state == "missing" else [state] if state_mode else item.get("selected_values", []) if state == "known" else [state]
        for value in dict.fromkeys(values):
            counts[value] += 1
            contributions.append({"value": value, "observation_id": item["observation_id"],
                                  "contribution_ids": item.get("contribution_ids", []),
                                  "institution": item.get("institution", item["observation_id"]),
                                  "country": item.get("country", ""), "repeated_response": False})
        diagnostics[state] += 1
    n = len(observations)
    missing = diagnostics["missing"] + (diagnostics["unknown_or_unmarked"] if state_mode else 0)
    categories = []
    for value, count in counts.items():
        exceptional = state_mode or value in {"conflicting_submissions", "varying_across_scopes"}
        base = n if exceptional else answering
        categories.append({"value": value, "count": count, "percent": percentage(count, base),
                           "percent_base": base, "percent_basis": "oIB" if exceptional else "oAB"})
    categories.append({"value": "Missing", "count": diagnostics["missing"], "percent": percentage(diagnostics["missing"], n), "percent_base": n, "percent_basis": "oIB"})
    return {**plain(definition), "analytical_unit": unit, "cohort_N": n,
            "population": {"N": n, "A": answering, "M": missing}, "categories": categories,
            "pie_categories": [{**category, "excluded_from_chart": category["value"] in {"Missing", "unknown_or_unmarked"}}
                               for category in categories],
            "contributions": contributions, "free_text_rows": [], "observations": plain(observations),
            "diagnostics": {"states": dict(diagnostics)}, "applicability": {"status": "source_scope_evidence"},
            "denominator": {"selection_percent": "reporting units with answers" if unit == "source_reporting_unit" else "known answering biobanks",
                            "state_percent": "survey reporting units" if unit == "source_reporting_unit" else "survey-participating biobanks" if unit == "unique_selected_biobank" else "all overlapping biobanks"}}


def summarize_text(definition: Mapping[str, Any], observations: Sequence[Mapping[str, Any]],
                   evidence: Mapping[str, Mapping[str, Any]], unit: str) -> dict[str, Any]:
    """List source text contributions without concatenating or averaging scope narratives.

    Args:
        definition: Source question metadata for one text field or qualification table.
        observations: Unique-biobank observations whose contributor IDs select evidence.
        evidence: Original answer items indexed by evidence ID.
        unit: Explicit unique-biobank counting convention for answered/missing summaries.

    Returns:
        A text-table question payload with per-answer source/scope labels and retained lineage.
    """
    rows = []
    answered = set()
    for obs in observations:
        for eid in obs.get("contribution_ids", []):
            item = evidence[eid]
            text = item.get("raw_text") or item.get("qualifier_text")
            if text is None or text == "":
                raw = item.get("raw_answer")
                if isinstance(raw, Mapping):
                    text = next((raw[key] for key in ("raw_text", "value", "reported_total", "numeric_mentions")
                                 if raw.get(key) is not None and raw.get(key) != "" and raw.get(key) != []), None)
                else:
                    text = raw
            if text is None or str(text).strip().casefold() in {"", "none", "n/a", "not applicable"}:
                continue
            answered.add(obs["observation_id"])
            rows.append({"text": str(text), "survey": item["survey"], "source_record_id": item["source_record_id"],
                         "scope_label": item.get("scope_label", item["scope_id"]), "scope_id": item["scope_id"],
                         "institution": obs.get("institution", obs["observation_id"]), "country": obs.get("country", ""),
                         "country_code": obs.get("country", ""),
                         "observation_id": obs["observation_id"], "evidence_id": eid})
            rows[-1]["raw_parent_answers"] = plain(item.get("raw_parent_answers", []))
    rows.sort(key=lambda item: (item["country"], item["observation_id"], item["source_record_id"], item["evidence_id"]))
    n = len(observations)
    return {**plain(definition), "analytical_unit": unit, "cohort_N": n, "question_type": "free_text",
            "population": {"N": n, "A": len(answered), "M": n - len(answered)}, "categories": [],
            "contributions": [], "free_text_rows": rows, "applicability": {"status": "source_scope_evidence"}}


def build_mucp_cohort_profile(biobanks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Describe scoped quantities and source-owned mentions without additive totals.

    Args:
        biobanks: Unique overlapping dossiers containing MuCP evidence, source
            records and non-authoritative quantity indexes. Source units remain on
            rows; only verified person units map to the donor analysis unit.

    Returns:
        Canonical-unit bank states, single-scope size bands and source rows retaining
        raw units, full owned answer text, answer classification and provenance.
        No quantities are summed.
    """
    if len({bb["biobank_id"] for bb in biobanks}) != len(biobanks):
        raise ValueError("MuCP profile requires unique biobank IDs")
    states = ("single_reported_scope", "multiple_scopes_or_values", "qualified_or_bound",
              "numeric_mentions_only", "missing")
    sizes = {unit: {"states": dict.fromkeys(states, 0), "rows": [],
                    "biobanks_with_quantity_evidence": 0, "biobanks_with_scoped_reported_sizes": 0,
                    "size_bands": dict.fromkeys(
                        ("0", "1-99", "100-999", "1,000-9,999", "10,000-99,999", "100,000+"), 0)}
             for unit in ("donors", "samples", "aliquots", "unit_unclear")}
    for bb in sorted(biobanks, key=lambda value: value["biobank_id"]):
        quantities = []
        records = {record["record_id"]: record for record in bb.get("mucp_source_records", [])}
        for record in records.values():
            for quantity in record.get("metadata", {}).get("reviewed_quantities", []):
                quantities.append({**quantity, "kind": "reported_collection_total" if ":collection:" in quantity["scope_id"] else "reported_scoped_total",
                    "source_record_id": record["record_id"], "raw_text": quantity["original_wording"],
                    "scope_label": quantity.get("measurement_label") or quantity["scope_label"],
                    "answer_type": "structured", "review_note": quantity.get("explanation"),
                    "qualifier_text": quantity.get("qualifier_text")})
        scopes = bb.get("scopes", {})
        scope_entries = scopes.items() if isinstance(scopes, Mapping) else (
            (scope.get("scope_id"), scope) for scope in scopes)
        for scope_id, scope in scope_entries:
            record = records.get(scope.get("source_record_id"))
            verified = verified_collection_count(scope, record) if record else None
            if any(q["source_record_id"] == scope.get("source_record_id") and q["scope_id"] == scope_id for q in quantities):
                continue
            if verified is not None:
                quantities.append({**verified, "unit": canonical_quantity_unit(verified["unit"]),
                    "source_unit": verified.get("source_unit") or verified["unit"],
                    "kind": "reported_collection_total", "question_id": None,
                    "scope_id": scope_id, "scope_label": scope.get("label") or "Reported collection",
                    "source_record_id": record["record_id"], "raw_text": verified["original_wording"],
                    "answer_type": "structured"})
        for item in bb.get("evidence", []):
            if item.get("survey") != "MuCP":
                continue
            total = item.get("extensions", {}).get("reported_total")
            from survey_mucp_reviewed import reviewed_quantity_covers
            if reviewed_quantity_covers(records.get(item["source_record_id"], {}), item, (total or {}).get("value")):
                continue
            if any(q["source_record_id"] == item["source_record_id"] and q.get("source_field") == item["question_id"]
                   and q.get("value") == (total or {}).get("value") for q in quantities):
                continue
            if not isinstance(total, Mapping):
                continue
            witness = _count_measurement(item.get("raw_text"))
            if witness is None and item.get("question_id") in {"B.count", "C.count"}:
                witness = _count_measurement(item.get("raw_text"), numeric_only=True)
                if witness is not None:
                    witness["unit"] = "individuals"
            verified = witness is not None and _typed_total(
                total, witness, canonical_person_units=item.get("question_id") in {"B.count", "C.count"})
            quantities.append({**plain(total),
                **({"relation": witness["relation"]} if verified else {}),
                "reported_total": plain(total),
                "unit": canonical_quantity_unit(witness["unit"]) if verified else "unit_unclear",
                "source_unit": witness.get("source_unit") if witness else None,
                "kind": "reported_scoped_total" if verified else "unverified_scoped_quantity",
                "validation_diagnostic": ("source_suffix_bound_preserved" if verified and witness.get("source_suffix_bound")
                                          else None if verified else "typed_total_disagrees_with_or_lacks_source_proof"),
                "question_id": item["question_id"], "scope_id": item["scope_id"],
                "scope_label": item.get("scope_label", item["scope_id"]),
                "source_record_id": item["source_record_id"], "evidence_id": item["evidence_id"],
                "source_refs": plain(item.get("source_refs", [])), "raw_text": item.get("raw_text"),
                "qualifier_text": item.get("qualifier_text"),
                "answer_type": "reported_scoped_total" if verified else None})
        for record in bb.get("mucp_source_records", []):
            for mention in record.get("metadata", {}).get("quantity_index", []):
                if any(q["source_record_id"] == record["record_id"] and q.get("source_field") == mention.get("field")
                       and (q.get("value") == mention.get("value") or mention.get("value") in q.get("superseded_index_values", [])) for q in quantities):
                    continue
                if any(q["source_record_id"] == record["record_id"] and
                       (q["question_id"] == mention.get("field") or q["question_id"] is None and q.get("response_id") == record["record_id"])
                       and q.get("value") == mention.get("value")
                       and {(r.get("source_id"), r.get("locator")) for r in q.get("source_refs", [])}.intersection(
                           (r.get("source_id"), r.get("locator")) for r in mention.get("evidence", []))
                       for q in quantities):
                    continue
                recovered = recover_quantity_answer(record, mention)
                index_unit = mention.get("unit")
                if (recovered["answer_text"] is None and
                        canonical_quantity_unit(index_unit) == "unit_unclear"):
                    continue
                quantities.append({**plain(mention), "unit": recovered["unit"],
                    "source_unit": recovered["source_unit"], "index_unit": index_unit,
                    "kind": "numeric_mention_not_additive",
                    "question_id": mention.get("field"), "source_record_id": record["record_id"],
                    "scope_label": "Source narrative; exact collection scope not inferred",
                    "scope_id": None, "raw_text": recovered["answer_text"],
                    "index_context": mention.get("context"),
                    "source_question_id": recovered["source_question_id"],
                    "index_status": mention.get("status"), "unit_basis": recovered["unit_basis"],
                    "recovery_diagnostic": recovered["diagnostic"],
                    "source_refs": recovered["source_refs"] or plain(mention.get("evidence", []))})
        for unit, summary in sizes.items():
            rows = [{**q, "biobank_id": bb["biobank_id"], "institution": bb["name"],
                     "country": bb.get("country", ""), "survey": "MuCP"}
                    for q in quantities if q.get("unit") == unit and
                    isinstance(q.get("value"), (int, float)) and not isinstance(q.get("value"), bool)
                    and q["value"] >= 0]
            summary["rows"].extend(rows)
            totals = [q for q in rows if q["kind"] in {"reported_scoped_total", "reported_collection_total"}]
            signatures = {(q["source_record_id"], q["question_id"], q["scope_id"], q["value"],
                           q.get("relation"), q.get("temporal_status")) for q in totals}
            if not rows:
                state = "missing"
            elif not totals:
                state = "numeric_mentions_only"
            elif len(signatures) > 1:
                state = "multiple_scopes_or_values"
            elif (unit == "unit_unclear" or
                  any(q.get("qualifier_text") or q.get("relation") != "reported_value" or
                      q.get("temporal_status") not in (None, "unspecified", "current") for q in totals)
                  or len(rows) > len(totals)):
                state = "qualified_or_bound"
            else:
                state = "single_reported_scope"
                value = totals[0]["value"]
                band = "0" if value == 0 else "1-99" if value < 100 else "100-999" if value < 1000 else (
                    "1,000-9,999" if value < 10000 else "10,000-99,999" if value < 100000 else "100,000+")
                if totals[0]["kind"] != "reported_collection_total":
                    summary["size_bands"][band] += 1
            summary["states"][state] += 1
            summary["biobanks_with_quantity_evidence"] += bool(rows)
            summary["biobanks_with_scoped_reported_sizes"] += bool(totals)
    return {"cohort_N": len(biobanks), "analytical_unit": "unique_overlapping_biobank", "sizes": sizes,
            "interpretation": "Sizes refer to reported scopes, not whole-biobank totals. Verified donors, individuals and participants share the donor analysis unit while source_unit retains literal wording; samples and aliquots remain separate. Quantity-index units are not proof. Numeric mentions and scopes are never summed. Missing means no source-classified numeric size evidence, not necessarily an unanswered question. Qualified, mentions-only and multi-scope evidence is excluded from size bands, not relabelled as missing."}


def build_combined_statistics(biobanks: Sequence[Mapping[str, Any]], catalogues: Mapping[str, Any],
                              visualization_registry: Mapping[str, Any]) -> dict[str, Any]:
    """Cover both discovered questionnaires independently of cross-survey mappings.

    Args:
        biobanks: Unique overlapping biobank dossiers with reduced observations/evidence.
        catalogues: Complete SO2 and MuCP question metadata, including text fields.
        visualization_registry: Approved group/pair definitions; does not restrict basic questions.

    Returns:
        SO2, MuCP and enrichment sections with a shared unique-biobank denominator.
    """
    output = {"SO2": {"questions": []}, "MuCP": {"questions": [], "groups": []}, "cross_survey": {}}
    from survey_combined_cohort import survey_participating_biobanks
    evidence = {item["evidence_id"]: item for bb in biobanks for item in bb["evidence"]}
    for survey in ("SO2", "MuCP"):
        participants = survey_participating_biobanks(biobanks, [survey])
        mixed_units = any(bb.get("reporting_unit_kind") in {"unresolved_source_reporting_unit", "national_summary"} for bb in participants)
        analytical_unit = "source_reporting_unit" if mixed_units else "unique_selected_biobank"
        unit_label = "reporting units" if mixed_units else "biobanks"
        output[survey]["participation"] = {"selected_N": len(biobanks), "participating_N": len(participants),
                                            "no_response_N": len(biobanks) - len(participants)}
        for source_definition in catalogues[survey]:
            definition = plain(source_definition)
            qid = definition.get("question_id", definition.get("id"))
            definition.update(question_id=qid, label=definition.get("label", qid))
            if survey == "MuCP":
                is_text = definition.get("type") in {"text", "free_text", "free_text_with_source_evidence"}
                if not definition.get("part") and qid.split(".", 1)[0] in {"A", "B", "C"}:
                    definition["part"] = qid.split(".", 1)[0]
                definition.update(question_type="free_text" if is_text else "single_choice",
                                  scope_states=not is_text, categories=[] if is_text else list(MUCP_STATES))
            observations = []
            for bb in participants:
                obs = next((value for value in bb["observations"] if value["survey"] == survey and value["question_id"] == qid),
                           {"question_id": qid, "state": "missing", "selected_values": [], "contribution_ids": []})
                observations.append({**obs, "observation_id": bb["biobank_id"], "country": bb["country"], "institution": bb["name"]})
            detail = summarize_text(definition, observations, evidence, analytical_unit) if definition["question_type"] == "free_text" else summarize_categorical(definition, observations, analytical_unit)
            detail["pie_basis_labels"] = {"all": f"selected {unit_label} with {survey} responses",
                                           "answered_only": f"{unit_label} with answers"}
            for category in detail.get("categories", []):
                if category.get("percent_basis") == "oIB":
                    category["percent_basis_label"] = f"selected {unit_label} with {survey} responses"
            output[survey]["questions"].append(detail)
    groups = {}
    for question in output["MuCP"]["questions"]:
        if question["question_type"] != "free_text":
            key = (question.get("part", ""), question.get("group", ""))
            groups.setdefault(key, []).append(question)
    for (part, group), questions in groups.items():
        n = output["MuCP"]["participation"]["participating_N"]
        informative_ids = {
            obs["observation_id"] for q in questions for obs in q["observations"]
            if obs.get("state") not in {"unknown_or_unmarked", "missing"}
        }
        categories = []
        option_coverage = []
        for q in questions:
            affirmative = [obs for obs in q["observations"]
                           if obs.get("has_affirmative_evidence") and "conflict" not in obs.get("state", "")]
            count = len(affirmative)
            categories.append({"value": q["label"], "count": count,
                               "percent": percentage(count, len(informative_ids)),
                               "percent_base": len(informative_ids), "percent_basis": "oAB"})
            option_coverage.append({"label": q["label"],
                "unknown_or_partial_count": sum(obs.get("state") in {"unknown_or_unmarked", "missing"}
                    or "partial_scope_coverage" in obs.get("flags", []) for obs in q["observations"]),
                "qualified_positive_count": sum("qualified" in obs.get("flags", []) for obs in affirmative),
                "varying_positive_count": sum(obs.get("state") == "varying_across_scopes" for obs in affirmative)})
        output["MuCP"]["groups"].append({"question_id": f"MuCP.{part}.{group}", "label": f"Part {part}: {group.replace('_', ' ')} - affirmative evidence reported",
                                          "question_type": "multi_choice", "population": {"N": n, "A": len(informative_ids), "M": n - len(informative_ids)}, "categories": categories,
                                          "analytical_unit": "source_reporting_unit" if any(q["analytical_unit"] == "source_reporting_unit" for q in questions) else "unique_selected_biobank",
                                          "coverage": {"informative_biobanks": len(informative_ids), "unknown_or_unmarked_biobanks": n - len(informative_ids)},
                                          "option_coverage": option_coverage,
                                          "questions": [q["question_id"] for q in questions], "contributions": [], "free_text_rows": []})
    output["MuCP"]["cohort_profile"] = build_mucp_cohort_profile(survey_participating_biobanks(biobanks, ["MuCP"]))
    output["MuCP"]["cohort_profile"]["analytical_unit"] = "unique_selected_biobank"
    if any(bb.get("reporting_unit_kind") in {"unresolved_source_reporting_unit", "national_summary"} for bb in biobanks):
        output["MuCP"]["cohort_profile"]["analytical_unit"] = "source_reporting_unit"
    return output


def load_visualization_registry(path: Path, catalogues: Mapping[str, Any]) -> dict[str, Any]:
    """Validate approved chart definitions against both complete question catalogues.

    Args:
        path: Editable visualization registry defining interpretable groups and pairs.
        catalogues: Source question metadata used to verify IDs and avoid undocumented axes.

    Returns:
        Validated registry with explicit small-N thresholds and question selectors.
    """
    root = json.loads(Path(path).read_text())
    if root.get("schema_version") != "1":
        raise ValueError("Unsupported visualization registry version")
    ids = {f"{survey}:{q.get('question_id', q.get('id'))}" for survey, questions in catalogues.items() for q in questions}
    for item in root.get("heatmaps", []) + root.get("upsets", []):
        selectors = item.get("questions", [])
        if any(selector not in ids for selector in selectors):
            raise ValueError(f"Visualization has unknown question: {item['id']}")
    return root


def load_thematic_crosswalk(path: Path, catalogues: Mapping[str, Any]) -> dict[str, Any]:
    """Read thematic links without using them to limit question discovery or statistics.

    Args:
        path: Editable source-qualified crosswalk with relationship explanations.
        catalogues: Complete question IDs used to reject stale thematic mappings.

    Returns:
        Validated themes distinguishing comparable and complementary relationships.
    """
    root = load_visualization_registry(path, catalogues)
    ids = {f"{survey}:{q.get('question_id', q.get('id'))}" for survey, questions in catalogues.items() for q in questions}
    for theme in root.get("themes", []):
        if theme.get("relationship") not in {"equivalent_or_comparable", "related_or_complementary"} or not theme.get("explanation"):
            raise ValueError("Thematic relationship requires explicit classification and explanation")
        if any(q not in ids for q in theme.get("questions", [])):
            raise ValueError("Crosswalk references unknown source question")
    return root


def reviewed_so2_heatmaps(path: Path) -> list[dict[str, Any]]:
    """Adapt reviewed default SO2 relationships to unique-biobank observations.

    Args:
        path: Existing SO2 association registry containing ordered semantic categories.

    Returns:
        Non-exploratory paired definitions retaining labels, order and interpretation.
    """
    from so2_descriptive_report import load_association_heatmap_registry
    return [{"id": "so2-" + item.definition_id, "title": item.title,
             "questions": ["SO2:" + item.row_question_id, "SO2:" + item.column_question_id],
             "row_categories": list(item.row_categories), "column_categories": list(item.column_categories),
             "interpretation": item.interpretation.replace("submitted response rows", "paired survey-participating biobanks"), "minimum_n": 5}
            for item in load_association_heatmap_registry(path) if item.mode == "default"]


def build_association_from_observations(definition: Mapping[str, Any], observations: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    """Construct one interpretable paired-biobank contingency table with state coverage.

    Args:
        definition: Approved two-question relationship including labels and minimum-N policy.
        observations: Source-qualified question IDs mapped to unique-biobank observations.

    Returns:
        Fixed semantic axes, zero-inclusive counts, paired denominator and omission reason.
        An axis without declared categories or observations remains empty; no
        synthetic response category is added. Unpaired source categories remain
        available for presentation validation even when the panel is omitted.
    """
    selectors = definition["questions"]
    if len(selectors) != 2:
        raise ValueError("Heatmap must reference exactly two questions")
    axes = []
    for selector in selectors:
        values = {}
        for item in observations.get(selector, []):
            if item["observation_id"] in values:
                raise ValueError("Duplicate heatmap observation_id")
            selected = item.get("selected_values", [])
            values[item["observation_id"]] = selected[0] if item.get("state") == "known" and len(selected) == 1 else item.get("state", "unknown_or_unmarked")
        axes.append(values)
    paired = sorted(set(axes[0]) & set(axes[1]))
    row_categories = list(definition.get("row_categories") or [])
    column_categories = list(definition.get("column_categories") or [])
    row_categories += sorted(set(axes[0].values()) - set(row_categories))
    column_categories += sorted(set(axes[1].values()) - set(column_categories))
    cells = {f"{row}|{column}": 0 for row in row_categories for column in column_categories}
    for bid in paired:
        key = f"{axes[0][bid]}|{axes[1][bid]}"
        if key not in cells:
            raise ValueError("Heatmap observation outside declared categories")
        cells[key] += 1
    metadata = {"definition_id": definition["id"], "title": definition.get("title", definition["id"]),
                "row_question_id": selectors[0], "column_question_id": selectors[1],
                "row_categories": list(row_categories), "column_categories": list(column_categories),
                "interpretation": definition.get("interpretation", "Descriptive association of reported biobank states, not causality."),
                "conditional_summary": False}
    unresolved = {"missing", "unknown_or_unmarked", "conflicting", "conflicting_submissions", "conflicting_or_scope_uncertain"}
    classifiable = [bid for bid in paired if all(axis[bid] not in unresolved for axis in axes)]
    variation = [len({axis[bid] for bid in classifiable}) for axis in axes]
    omit = len(classifiable) < definition.get("minimum_n", 5) or min(variation, default=0) < 2
    return {"definition": metadata, "pair": {"paired_denominator": len(paired), "cells": cells,
                                              "observation_ids": paired, "classifiable_denominator": len(classifiable)},
            "omission_reason": "Insufficient paired biobanks or category variation" if omit else None}


def combined_upset_definition(configured: Mapping[str, Any], questions: Mapping[str, Any]) -> dict[str, Any]:
    """Expand source-qualified selectors into labelled concrete evidence sets.

    Args:
        configured: Approved UpSet registry entry with ordered survey selectors.
        questions: Complete questionnaire metadata indexed by survey-qualified ID.

    Returns:
        Independent definition with source-tagged sets for cross-survey plots.
        Uninformative Other/unknown technology checkboxes are not access sets;
        their original answer evidence remains unchanged in the source model.
    """
    definition = plain(configured)
    cross = len({selector.split(":", 1)[0] for selector in definition["questions"]}) > 1
    sets = []
    for selector in definition["questions"]:
        question = questions[selector]
        prefix = "[" + selector.split(":", 1)[0] + "] " if cross else ""
        if selector.startswith("SO2:"):
            for category in question["categories"]:
                if selector.startswith("SO2:q_035_") and (
                    category.casefold().startswith("other") or "know" in category.casefold()):
                    continue
                sets.append({"question": selector, "category": category, "label": prefix + category})
        else:
            sets.append({"question": selector, "label": prefix + question["label"] + " reported"})
    definition["sets"] = sets
    return definition


def build_combined_upset_matrix(definition: Mapping[str, Any], biobanks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Project explicitly named evidence events while preserving the original scope states.

    Args:
        definition: Approved question/set list and projection selector. The
            ``reported_checkbox_pattern`` projection treats present applicable No
            as an all-zero membership while excluding incomplete/unknown patterns.
        biobanks: Unique overlapping biobank dossiers with source-derived observations.

    Returns:
        Boolean event matrix, unchanged original state matrix, exclusion reasons and
        denominator diagnostics. In the reported checkbox projection, variation
        across distinct collections retains an affirmative dot with a non-universality caveat.
    """
    projection = definition.get("projection", "affirmative_evidence_pattern")
    from survey_combined_cohort import survey_participating_biobanks
    selected_n = len(biobanks)
    required_surveys = sorted({qid.split(":", 1)[0] for qid in definition["questions"]})
    biobanks = survey_participating_biobanks(biobanks, required_surveys)
    if projection not in {"affirmative_evidence_pattern", "explicit_availability_complete_case",
                          "reported_checkbox_pattern"}:
        raise ValueError("Unsupported UpSet projection")
    sets = definition.get("sets") or [{"question": qid, "label": qid.split(":", 1)[1] + " reported"} for qid in definition["questions"]]
    rows, state_matrix, exclusions = [], {}, Counter()
    for bb in sorted(biobanks, key=lambda item: item["biobank_id"]):
        obs = {f"{item['survey']}:{item['question_id']}": item for item in bb["observations"]}
        row = {"observation_id": bb["biobank_id"], "country": bb["country"], "institution": bb["name"]}
        states = {}
        reason = None
        for index, option in enumerate(sets, 1):
            missing_state = "missing" if projection == "reported_checkbox_pattern" else "unknown_or_unmarked"
            item = obs.get(option["question"], {"state": missing_state, "has_affirmative_evidence": False})
            state = item["state"]
            states[option["question"]] = state
            if "conflict" in state:
                reason = state
            if projection == "reported_checkbox_pattern" and option["question"].startswith("MuCP:"):
                classification = classify_reported_checkbox_observation(item)
                if not classification["eligible"]:
                    reason = classification["reason"]
                positive = classification["affirmative"] is True
            elif option["question"].startswith("SO2:"):
                if state != "known":
                    reason = state
                if option["question"].startswith("SO2:q_035_"):
                    selected = item.get("selected_values", [])
                    concrete = {entry.get("category") for entry in sets
                                if entry["question"] == option["question"]}
                    if any("know" in str(value).casefold() for value in selected):
                        reason = "uncertain_technology_access"
                    elif state == "known" and not concrete.intersection(selected):
                        reason = "no_concrete_technology_selection"
                positive = option.get("category") in item.get("selected_values", [])
            else:
                positive = item.get("has_affirmative_evidence", False)
                if projection == "explicit_availability_complete_case" and not positive and state != "explicitly_no_in_all_reported_applicable_scopes":
                    reason = state
            row[f"set_{index:03d}"] = bool(positive)
        state_matrix[bb["biobank_id"]] = states
        if reason:
            exclusions[reason] += 1
        else:
            rows.append(row)
    columns = [f"set_{index:03d}" for index in range(1, len(sets) + 1)]
    nonempty = sum(any(row[column] for row in rows) for column in columns)
    minimum = definition.get("minimum_n", 5)
    interpretation = (
        "MuCP dots mean a reported Yes in a represented scope; for MuCP sets, no dot means explicit No across reported applicable scopes. SO2 dots mean selected technology-access categories, not MuCP availability. A varying MuCP pattern means at least one reported collection, not universal coverage. Unknown or incomplete checkbox patterns are excluded."
        if projection == "reported_checkbox_pattern" else
        "An absent dot does not establish absence of the property. Reports may refer to different collections."
        if projection == "affirmative_evidence_pattern" else
        "Complete-case availability over explicitly reported applicable scopes only."
    )
    return {"id": definition["id"], "title": definition.get("title", definition["id"]), "questions": definition["questions"],
            "projection": projection, "rows": rows, "sets": columns, "set_labels": [option["label"] for option in sets],
            "state_matrix": state_matrix, "cohort_N": selected_n, "selected_cohort_N": selected_n,
            "participating_N": len(biobanks), "no_survey_response_count": selected_n - len(biobanks), "matrix_N": len(rows),
            "exclusions": dict(exclusions), "all_zero_biobanks": sum(not any(row[column] for column in columns) for row in rows),
            "omission_reason": "Insufficient classifiable biobanks or nonempty sets" if len(rows) < minimum or nonempty < 2 else None,
            "interpretation": interpretation}
