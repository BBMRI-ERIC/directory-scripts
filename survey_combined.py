"""Evidence-preserving SO2 adapters and scope-aware unique-biobank cohort assembly."""

from collections import defaultdict
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from survey_evidence import (AnalyticalObservation, CombinedBiobank, EvidenceItem,
                             ResolutionRecord, SourceRecord, fingerprint, plain,
                             validate_evidence_links)
from survey_identity import MatchOverrides, country_key, identity_fingerprint, resolve_source_identity, resolve_scoped_sources


@dataclass(frozen=True)
class GroupedSources:
    """Accepted biobank groups alongside retained unmatched and review records.

    Attributes:
        groups: Canonical biobank IDs mapped to all contributing source records.
        resolutions: Every identity decision indexed by source record ID.
        records: Original source records retained for excluded/missing diagnostics.
    """

    groups: Mapping[str, tuple[SourceRecord, ...]]
    resolutions: Mapping[str, ResolutionRecord]
    records: tuple[SourceRecord, ...]


def build_matching_breakdown(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build a complete source-record inventory from stored identity resolutions.

    Args:
        payload: Combined model with overlapping biobank records and resolution envelopes.

    Returns:
        Versioned per-survey status counts, accepted Directory-ID sets and country/name
        display groups. Source records are counted once per survey and record ID.

    Raises:
        ValueError: If record identities/statuses conflict or accepted counts disagree
            with the legacy matching summary.
    """
    statuses = ("accepted", "unmatched", "review", "excluded")
    records: dict[str, dict[str, dict[str, Any]]] = {"SO2": {}, "MuCP": {}}

    def add(record: Mapping[str, Any], resolution: Mapping[str, Any] | None,
            survey_hint: str | None = None, member_id: str | None = None) -> None:
        """Add a source record while checking repeated identity decisions.

        Args:
            record: Survey source record with respondent identity and record ID.
            resolution: Stored matching decision, or None for an overlap member.
            survey_hint: Survey name used when the record omits its survey tag.
            member_id: Canonical overlap biobank ID used for implicit acceptance.

        Returns:
            None. Updates the enclosing inventory without counting repeats twice.
        """
        survey = str(record.get("survey") or (resolution or {}).get("survey") or survey_hint or "")
        if survey not in records:
            raise ValueError(f"Unsupported survey for matching record: {survey!r}")
        record_id = str(record.get("record_id") or (resolution or {}).get("source_record_id") or "").strip()
        if not record_id:
            raise ValueError("Matching source record is missing record_id")
        resolution = resolution or {}
        resolved_record_id = str(resolution.get("source_record_id") or record_id)
        if resolved_record_id != record_id:
            raise ValueError(f"Matching resolution record ID disagrees for source record {record_id}")
        status = resolution.get("status")
        if status is None and member_id is not None:
            status = "accepted"
        if status not in {"accepted", "unmatched", "review", "excluded", "rejected"}:
            raise ValueError(f"Matching source record {record_id} has no supported stored resolution status")
        status = "excluded" if status == "rejected" else status
        biobank_id = resolution.get("biobank_id")
        if status == "accepted" and not biobank_id:
            biobank_id = member_id
        if status == "accepted" and not biobank_id:
            raise ValueError(f"Accepted matching source record {record_id} has no Directory ID")
        existing = records[survey].get(record_id)
        current = {"record": dict(record), "status": status, "biobank_id": biobank_id,
                   "reason": str(resolution.get("reason") or resolution.get("explanation") or ""),
                   "record_type": str(record.get("record_type") or "submission")}
        if existing is not None:
            if (existing["status"], existing.get("biobank_id")) != (status, biobank_id):
                raise ValueError(f"Contradictory matching resolution for source record {record_id}")
            return
        records[survey][record_id] = current

    for biobank in payload.get("biobanks", ()):
        biobank_id = str(biobank.get("biobank_id") or biobank.get("id") or "")
        resolutions = {}
        for decision in biobank.get("identity_resolutions", ()):
            source_id = str(decision.get("source_record_id") or "")
            if source_id:
                resolutions[source_id] = decision
        for survey, key in (("SO2", "so2_source_records"), ("MuCP", "mucp_source_records")):
            for record in biobank.get(key, ()):
                record_id = str(record.get("record_id") or "")
                add(record, resolutions.get(record_id), survey, biobank_id)

    for key, survey_hint in (("unmatched_so2", "SO2"), ("unmatched_mucp", "MuCP"),
                             ("manual_review_matches", None), ("excluded_source_records", None)):
        for item in payload.get(key, ()):
            record = item.get("record", item)
            resolution = item.get("resolution")
            if not isinstance(record, Mapping) or not isinstance(resolution, Mapping):
                raise ValueError(f"Malformed matching source record in {key}")
            add(record, resolution, survey_hint)

    accepted_by_survey = {
        survey: {item["biobank_id"] for item in inventory.values() if item["status"] == "accepted"}
        for survey, inventory in records.items()
    }
    overlap = accepted_by_survey["SO2"] & accepted_by_survey["MuCP"]

    def normalized_country(value: Any) -> str:
        """Normalize known country aliases and collapse explicit missing markers.

        Args:
            value: Country name/code or missing marker from a source response.

        Returns:
            Normalized country code, or Unknown for an explicitly missing country.
        """
        country = country_key(value)
        return "Unknown" if country.casefold() in {
            "", "nan", "none", "unknown", "not reported", "n/a", "na",
        } else country

    def category_groups(inventory: Mapping[str, Mapping[str, Any]], status: str) -> list[dict[str, Any]]:
        """Group one matching status by country and reported institution.

        Args:
            inventory: Source-record-ID mapping containing records and decisions.
            status: Matching category whose respondent names should be grouped.

        Returns:
            Country-sorted groups with institution multiplicities and source IDs;
            country-summary records are excluded from institution lists.
        """
        countries: dict[str, dict[str, list[Mapping[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        for source_id, item in inventory.items():
            if item["status"] != status or item["record_type"] == "country_summary":
                continue
            source = item["record"]
            country = normalized_country(source.get("country"))
            identity = source.get("identity", {})
            raw_name = str(identity.get("institution_name") or "")
            name = " ".join(raw_name.split()) or "(institution not reported)"
            countries[country][name].append({**item, "source_record_id": source_id,
                                             "source_institution_name": raw_name})
        result = []
        for country, institution_map in sorted(countries.items()):
            institutions = []
            for name, entries in sorted(institution_map.items(), key=lambda pair: pair[0].casefold()):
                ids = sorted({str(entry["biobank_id"]) for entry in entries if entry.get("biobank_id")})
                institutions.append({
                    "name": name,
                    "source_names": sorted({entry["source_institution_name"] for entry in entries}),
                    "record_count": len(entries),
                    "source_record_ids": sorted(entry["source_record_id"] for entry in entries),
                    "distinct_directory_ids": len(ids) if status == "accepted" else None,
                    "directory_ids": ids if status == "accepted" else [],
                    "exclusion_reasons": sorted({entry["reason"] for entry in entries
                                                  if status == "excluded" and entry["reason"]}),
                })
            result.append({"country": country, "record_count": sum(row["record_count"] for row in institutions),
                           "institutions": institutions})
        return result

    surveys: dict[str, Any] = {}
    for survey, inventory in records.items():
        counts = {status: sum(item["status"] == status for item in inventory.values()) for status in statuses}
        accepted_ids = sorted(accepted_by_survey[survey])
        country_summary = []
        for source_id, item in sorted(inventory.items()):
            if item["record_type"] == "country_summary":
                country_summary.append({
                    "record_id": source_id,
                    "country": normalized_country(item["record"].get("country")),
                    "status": item["status"], "reason": item["reason"],
                })
        survey_info = {
            "total_records": len(inventory),
            "status_counts": counts,
            "distinct_accepted_directory_ids": len(accepted_ids),
            "accepted_directory_ids": accepted_ids,
            "accepted_exclusive_directory_ids": sorted(set(accepted_ids) - overlap),
            "accepted_exclusive_directory_id_count": len(set(accepted_ids) - overlap),
            "country_groups": {status: category_groups(inventory, status) for status in statuses},
            "country_summary_records": country_summary,
        }
        surveys[survey] = survey_info

    summary = payload.get("matching_summary", {})
    expected_counts = {"SO2": summary.get("so2_matched_biobanks"),
                       "MuCP": summary.get("mucp_matched_biobanks")}
    for survey, expected in expected_counts.items():
        if expected is not None and surveys[survey]["distinct_accepted_directory_ids"] != expected:
            raise ValueError(f"{survey} accepted Directory-ID count disagrees with matching_summary")
    if summary.get("overlapping_biobanks") is not None and len(overlap) != summary["overlapping_biobanks"]:
        raise ValueError("Accepted Directory-ID intersection disagrees with matching_summary")
    has_explicit_membership_records = any(
        item.get("so2_source_records") or item.get("mucp_source_records")
        for item in payload.get("biobanks", ())
    )
    expected_members = set(payload.get("metadata", {}).get("cohort", {}).get("selected_ids", overlap))
    if summary.get("overlapping_biobanks") is not None and has_explicit_membership_records and expected_members != {
        str(item.get("biobank_id") or item.get("id")) for item in payload.get("biobanks", ())
    }:
        raise ValueError("Accepted Directory-ID intersection disagrees with combined biobank membership")
    return {"version": 1, "surveys": surveys,
            "accepted_overlap": {"count": len(overlap), "directory_ids": sorted(overlap)}}


def so2_source_records(workbook: Any, questions: Sequence[Any], form: Mapping[str, Any]) -> tuple[SourceRecord, ...]:
    """Adapt every validated SO2 row into answer-level source evidence.

    Args:
        workbook: SurveyWorkbook retaining original worksheet row numbers and hashes.
        questions: Validated descriptive question definitions, covering all reportable columns.
        form: Authoritative form metadata used to preserve field UIDs and dependencies.

    Returns:
        Immutable SO2 source responses, including raw answers and contextual source columns.
    """
    import pandas as pd
    import so2_descriptive_report as descriptive
    source_column = "source_row" if "source_row" in workbook.responses.columns else next((column for column in workbook.responses.columns if column.startswith("__")), None)
    if source_column is None:
        raise ValueError("SO2 workbook lacks physical source-row column")
    records = []
    for _, row in workbook.responses.iterrows():
        source_row = int(row[source_column])
        record_id = f"so2:{workbook.worksheet}:row:{source_row}"
        supplied_collections = []
        for column in workbook.responses.columns:
            if column.startswith("List of CollectionID"):
                supplied_collections = [value.strip() for value in str(row[column] or "").split(";")
                                        if value.strip() and value.strip().lower() != "nan"]
        scope_id = record_id + ":scope"
        scope = {"scope_id": scope_id, "kind": "collection_subset" if supplied_collections else "submission",
                 "label": "; ".join(supplied_collections) or "Submission; collection coverage not independently inferred",
                 "source_record_id": record_id, "collection_ids": supplied_collections}
        evidence = []
        known_columns = set()
        for question in questions:
            known_columns.add(question.column)
            raw = row[question.column]
            raw = None if pd.isna(raw) else raw.item() if hasattr(raw, "item") else raw
            if question.question_type == "free_text":
                normalized = None if raw is None else str(raw)
            else:
                normalized, _ = descriptive.normalize_structured_answer(question, raw)
            item = {"evidence_id": fingerprint(["SO2", record_id, question.question_id]),
                    "survey": "SO2", "source_record_id": record_id, "survey_row": source_row,
                    "question_id": question.question_id, "question_label": question.label,
                    "form_uid": question.form_uid, "question_type": question.question_type,
                    "scope_id": scope_id, "scope_kind": scope["kind"], "scope_label": scope["label"],
                    "kind": "text_field" if question.question_type == "free_text" else "structured_answer",
                    "raw_answer": raw, "raw_text": None if raw is None else str(raw), "normalized_value": normalized,
                    "answer_state": "missing" if normalized is None or normalized == [] else "answered",
                    "source_refs": [{"path": workbook.source_path, "sha256": workbook.source_sha256,
                                     "locator": f"{workbook.worksheet}!row[{source_row}]:{question.column}"}],
                    "form": plain(form.get("questions", {}).get(descriptive._form_label(question.column), {}))}
            if question.parent_columns:
                item["raw_parent_answers"] = [{"column": column,
                    "value": None if pd.isna(row[column]) else str(row[column])} for column in question.parent_columns]
            EvidenceItem(item)
            evidence.append(item)
        for column in workbook.responses.columns:
            if column in known_columns or column == source_column:
                continue
            raw = row[column]
            raw = None if pd.isna(raw) else str(raw)
            qid = "SO2.context." + fingerprint(column)[:12]
            evidence.append({"evidence_id": fingerprint([record_id, qid]), "survey": "SO2",
                             "source_record_id": record_id, "survey_row": source_row, "question_id": qid,
                             "question_label": column, "scope_id": scope_id, "scope_kind": scope["kind"],
                             "scope_label": scope["label"], "kind": "respondent_context", "raw_answer": raw,
                             "raw_text": raw, "normalized_value": raw, "source_refs": [{"path": workbook.source_path,
                             "sha256": workbook.source_sha256, "locator": f"{workbook.worksheet}!row[{source_row}]:{column}"}]})
        email = str(row.get("E-Mail address") or "").strip()
        explicit_id = str(row.get("BiobankID in the Directory (if available)") or "").strip()
        if explicit_id.lower() == "nan":
            explicit_id = ""
        records.append(SourceRecord({"record_id": record_id, "survey": "SO2", "record_type": "submission",
                                     "country": country_key(row.get("Country")), "survey_row": source_row,
                                     "identity": {"institution_name": str(row.get("Name of Institution") or ""),
                                                  "email_addresses": [email] if "@" in email else [],
                                                  "collection_ids": supplied_collections,
                                                  "explicit_biobank_id": explicit_id},
                                     "scopes": [scope], "evidence": evidence,
                                     "metadata": {"source_path": workbook.source_path, "source_sha256": workbook.source_sha256}}))
    return tuple(records)


def load_bound_so2_resolutions(path: Path, workbook: Any, overrides: MatchOverrides) -> Mapping[str, ResolutionRecord]:
    """Reuse reviewed SO2 identities only when source content is explicitly bound.

    Args:
        path: Existing findings JSON containing physical-row resolution records.
        workbook: Current validated source workbook including its SHA-256.
        overrides: Reviewed workbook/findings hash bindings for legacy artifacts.

    Returns:
        Frozen resolution records keyed by SO2 physical source identity.
    """
    from hashlib import sha256
    report = json.loads(Path(path).read_text())
    findings_hash = sha256(Path(path).read_bytes()).hexdigest()
    bound = report.get("survey_metadata", {}).get("survey_sha256") == workbook.source_sha256
    for binding in overrides.input_bindings:
        if (binding.get("so2_sha256") == workbook.source_sha256 and binding.get("findings_sha256") == findings_hash
                and binding.get("reviewer") and binding.get("reason")):
            bound = True
    if not bound:
        raise ValueError(f"SO2 findings require reviewed input binding: so2_sha256={workbook.source_sha256}; findings_sha256={findings_hash}")
    source_column = "source_row" if "source_row" in workbook.responses.columns else next(column for column in workbook.responses.columns if column.startswith("__"))
    rows = {int(row[source_column]): row for _, row in workbook.responses.iterrows()}
    resolutions = {}
    for value in report.get("row_resolutions", []):
        row_num = value.get("survey_row")
        if row_num not in rows or row_num in resolutions:
            raise ValueError("SO2 findings row coverage is duplicate or incompatible")
        row = rows[row_num]
        if str(row.get("Name of Institution") or "") != str(value.get("institution_name") or ""):
            raise ValueError(f"SO2 findings institution differs at row {row_num}")
        bids = value.get("matched_biobank_ids", [])
        method = value.get("resolution_status", "")
        accepted = len(bids) == 1 and method in {"resolved_by_biobank_id", "resolved_by_collection_ids", "resolved_by_contact_email"}
        rid = f"so2:{workbook.worksheet}:row:{row_num}"
        resolutions[row_num] = ResolutionRecord({"source_record_id": rid, "survey": "SO2", "status": "accepted" if accepted else "review",
                                                 "biobank_id": bids[0] if accepted else None, "candidate_ids": bids,
                                                 "method": "frozen:" + method, "reliability": value.get("resolution_reliability"),
                                                 "explanation": value.get("resolution_explanation"), "original_resolution": value})
    if set(resolutions) != set(rows):
        raise ValueError("SO2 findings do not cover every source response")
    return {item.data["source_record_id"]: item for item in resolutions.values()}


def resolve_so2_records(records: Sequence[SourceRecord], catalogue: Any,
                        existing: Mapping[str, ResolutionRecord], overrides: MatchOverrides) -> tuple[ResolutionRecord, ...]:
    """Apply conservative acceptance and optional reviewed overrides to SO2 sources.

    Args:
        records: Immutable SO2 response records, preserving repeated submissions.
        catalogue: Complete Directory identity catalogue with configured reporting scope.
        existing: Source-bound frozen findings resolutions; empty requests fresh matching.
        overrides: Current fingerprint-bound accept/reject decisions.

    Returns:
        Auditable decisions in input-record order with out-of-scope identities excluded.
    """
    result = []
    for record in records:
        rid = record.data["record_id"]
        if ("SO2", rid, "") in overrides.decisions or rid not in existing:
            resolution = resolve_source_identity(record, catalogue, overrides)
        else:
            data = plain(existing[rid])
            data["identity_fingerprint"] = identity_fingerprint(record)
            bid = data.get("biobank_id")
            current = plain(resolve_source_identity(record, catalogue, overrides))
            if data["status"] == "accepted" and (current["status"] in {"review", "unmatched"}
                    or current.get("biobank_id") and current["biobank_id"] != bid):
                data.update(status="review", candidate_ids=current.get("candidate_ids", []),
                            explanation="Frozen findings conflict with current source identity evidence",
                            current_identity_resolution=current)
            elif data["status"] == "accepted" and bid not in catalogue.biobanks:
                data.update(status="review", explanation="Frozen Directory identity is no longer loaded")
            elif data["status"] == "accepted" and bid not in catalogue.eligible_ids:
                data.update(status="excluded", explanation="Outside configured withdrawn scope")
            resolution = ResolutionRecord(data)
        result.append(resolution)
    return tuple(result)


def group_sources(records: Sequence[SourceRecord], resolutions: Sequence[ResolutionRecord]) -> GroupedSources:
    """Group only accepted sources by canonical biobank without losing other responses.

    Args:
        records: All contributing source responses for one survey.
        resolutions: One identity decision per source record.

    Returns:
        Accepted groups and the complete retained source/decision inventory.
    """
    index = {item.data["source_record_id"]: item for item in resolutions}
    record_ids = [item.data["record_id"] for item in records]
    if (len(index) != len(resolutions) or len(record_ids) != len(set(record_ids))
            or set(index) != set(record_ids)):
        raise ValueError("Source records and resolutions must have unique, exactly matching identities")
    groups = defaultdict(list)
    for record in records:
        resolution = index[record.data["record_id"]].data
        if resolution["status"] == "accepted":
            groups[resolution["biobank_id"]].append(record)
    return GroupedSources({bid: tuple(sorted(items, key=lambda item: item.data["record_id"])) for bid, items in groups.items()}, index, tuple(records))


def canonicalize_linked_scopes(records: Sequence[SourceRecord]) -> dict[str, Any]:
    """Identify duplicate source-row representations without deducing scope from names.

    Args:
        records: Accepted source records with original scopes and explicit workbook links.

    Returns:
        Original scopes indexed by ID, with analytical equivalence IDs only where
        exact workbook, aggregate and data-row links establish the same representation.
        Nested collection scopes are never linked through their parent's workbook links.
    """
    result = {}
    for record in records:
        links = record.data.get("metadata", {}).get("workbook_links", ())
        exact_links = []
        for link in links:
            rows = link.get("data_rows", ())
            if (link.get("workbook_source_id") and type(link.get("aggregate_id")) is int
                    and rows and all(type(row) is int for row in rows)):
                exact_links.append([link["workbook_source_id"], link["aggregate_id"], sorted(rows)])
        for scope in record.data.get("scopes", ()):
            value = {**plain(scope), "survey": record.data["survey"], "analytical_scope_id": scope["scope_id"]}
            if exact_links and len(exact_links) == len(links) and scope.get("kind") != "collection":
                value.update(analytical_scope_id="linked-workbook:" + fingerprint(sorted(exact_links)),
                             analytical_scope_basis="exact_workbook_aggregate_data_rows")
            result[scope["scope_id"]] = value
    return result


def reduce_mucp_question(items: Sequence[EvidenceItem], scopes: Mapping[str, Any]) -> AnalyticalObservation:
    """Derive a scoped evidence state without equating unknown with negative availability.

    Args:
        items: All source assertions for one MuCP question within a biobank.
        scopes: Explicit scope definitions used to distinguish variation from contradiction.

    Returns:
        Exclusive statistical state, qualification flags and all contributing evidence IDs.
    """
    values = [item.data for item in items]
    canonical_scopes = {item["scope_id"]: scopes.get(item["scope_id"], {}).get("analytical_scope_id", item["scope_id"])
                        for item in values}
    yes = [item for item in values if item.get("normalized_value") is True or item.get("normalized_value") == "affirmed"]
    no = [item for item in values if item.get("normalized_value") is False or item.get("normalized_value") == "explicit_negative"]
    unknown = [item for item in values if item not in yes and item not in no]
    conditional = [item for item in unknown if item.get("answer_state") in {"conditional", "conditional_text"}]
    represented = {item["scope_id"] for item in values}
    source_ids = {item["source_record_id"] for item in values}
    represented_canonical = set(canonical_scopes.values())
    unreported = sorted(scope_id for scope_id, scope in scopes.items()
                        if (scope.get("source_record_id") in source_ids or scope.get("survey") == "MuCP")
                        and scope_id not in represented
                        and scope.get("analytical_scope_id", scope_id) not in represented_canonical)
    flags = []
    if any(item.get("qualifier_text") for item in values):
        flags.append("qualified")
    if unknown or unreported:
        flags.append("partial_scope_coverage")
    if any(item.get("answer_state") in {"multiple_scopes_or_conflict", "ambiguous_formatting", "ambiguous_mark"} for item in values):
        state = "conflicting"
        scope_assessment = "source_ambiguous"
    elif yes and no:
        if {canonical_scopes[item["scope_id"]] for item in yes} & {canonical_scopes[item["scope_id"]] for item in no}:
            state = "conflicting"
            scope_assessment = "same_scope_contradiction"
        else:
            relevant = [scopes.get(item["scope_id"], {}) for item in yes + no]
            distinct = (all(scope.get("kind") == "collection" and scope.get("collection_id") for scope in relevant)
                        and len({scope.get("source_record_id") for scope in relevant}) == 1
                        and len({scope.get("collection_id") for scope in relevant}) == len(relevant))
            state = "varying_across_scopes" if distinct else "conflicting_or_scope_uncertain"
            scope_assessment = "distinct_collections_vary" if distinct else "responses_differ_scope_uncertain"
    elif yes:
        state = "reported_yes_in_one_or_more_scopes"
        scope_assessment = "reported_scopes_only"
    elif no:
        state = "incomplete_or_qualified" if unknown or unreported else "explicitly_no_in_all_reported_applicable_scopes"
        scope_assessment = "reported_scopes_only"
    elif conditional:
        state = "qualified_only"
        scope_assessment = "reported_scopes_only"
    else:
        state = "unknown_or_unmarked"
        scope_assessment = "reported_scopes_only"
    return AnalyticalObservation({"survey": "MuCP", "question_id": values[0]["question_id"] if values else "",
                                  "state": state, "scope_assessment": scope_assessment,
                                  "selected_values": [], "flags": flags,
                                  "has_affirmative_evidence": bool(yes), "scope_ids": sorted({item["scope_id"] for item in values}),
                                  "unreported_scope_ids": unreported,
                                  "analytical_claim_count": len({(canonical_scopes[item["scope_id"]],
                                                                  fingerprint(item.get("normalized_value"))) for item in values}),
                                  "raw_state_counts": {key: sum(item.get("answer_state") == key for item in values)
                                                       for key in sorted({str(item.get("answer_state")) for item in values})},
                                  "contribution_ids": sorted({item["evidence_id"] for item in values})})


def reduce_so2_question(items: Sequence[EvidenceItem], scopes: Mapping[str, Any]) -> AnalyticalObservation:
    """Collapse agreeing SO2 answers once while preserving contradictory submissions.

    Args:
        items: Source responses to one SO2 question, including blank responses.
        scopes: Reported collection-subset context, never inferred from institution labels.

    Returns:
        One analytical category/set or an explicit conflict/varying/missing state.
    """
    values = [item.data for item in items]
    populated = [item for item in values if item.get("normalized_value") not in (None, "", (), [])]
    signatures = {fingerprint(sorted(item["normalized_value"]) if isinstance(item["normalized_value"], (list, tuple)) else item["normalized_value"])
                  for item in populated}
    state = "known" if len(signatures) == 1 else "conflicting_submissions" if signatures else "missing"
    if len(signatures) > 1:
        scope_sets = [set(scopes.get(item["scope_id"], {}).get("collection_ids", ())) for item in populated]
        if all(scope_sets) and all(not a.intersection(b) for i, a in enumerate(scope_sets) for b in scope_sets[i + 1:]):
            state = "varying_across_scopes"
    selected = populated[0]["normalized_value"] if state == "known" else []
    if isinstance(selected, str):
        selected = [selected]
    return AnalyticalObservation({"survey": "SO2", "question_id": values[0]["question_id"] if values else "",
                                  "state": state, "selected_values": plain(selected),
                                  "flags": ["partial_response_coverage"] if len(populated) < len(values) and populated else [],
                                  "scope_ids": sorted({item["scope_id"] for item in values}),
                                  "contribution_ids": sorted({item["evidence_id"] for item in values})})


def build_combined_payload(so2: GroupedSources, mucp: GroupedSources, inputs: Mapping[str, Any], crosswalk: Mapping[str, Any], *, join: str = "all-MuCP") -> dict[str, Any]:
    """Build a deterministic intersection cohort with separately retained source evidence.

    Args:
        so2: SO2 accepted groups plus all unmatched/review records.
        mucp: MuCP accepted groups plus the complete unresolved/excluded source inventory.
        inputs: Input hashes/catalogues and Directory metadata used for output provenance.
        crosswalk: Explicit thematic relationships; never determines question inclusion.
        join: Selection policy; all-MuCP and outer retain every MuCP source,
            using source-only reporting identities for unaccepted matches.

    Returns:
        Canonical combined-analysis JSON material, ready for statistics and rendering.
    """
    biobanks = []
    from survey_combined_cohort import select_biobank_cohort
    reporting_groups = dict(mucp.groups)
    names = dict(inputs.get("biobanks", {}))
    if join in {"all-MuCP", "outer"}:
        included = {record.data["record_id"] for records in reporting_groups.values() for record in records}
        for record in mucp.records:
            if record.data["record_id"] in included:
                continue
            decision = mucp.resolutions[record.data["record_id"]].data
            bid = "mucp-source:" + record.data["record_id"]
            reporting_groups[bid] = reporting_groups.get(bid, ()) + (record,)
            names.setdefault(bid, {"name": record.data.get("identity", {}).get("institution_name") or record.data["record_id"],
                                   "country": record.data.get("country"),
                                   "withdrawn": None})
    cohort = select_biobank_cohort(list(so2.groups), list(reporting_groups), join)
    for bid in sorted(cohort["selected_ids"], key=lambda value: (country_key(names.get(value, {}).get("country")), value)):
        so2_records, mucp_records = so2.groups.get(bid, ()), reporting_groups.get(bid, ())
        records = so2_records + mucp_records
        evidence = sorted([plain(item) for record in records for item in record.data.get("evidence", ())], key=lambda item: item["evidence_id"])
        scopes = canonicalize_linked_scopes(records)
        grouped = defaultdict(list)
        for item in evidence:
            if item.get("kind") in {"structured_answer", "text_field"}:
                grouped[(item["survey"], item["question_id"])].append(EvidenceItem(item))
        observations = []
        for (survey, qid), items in sorted(grouped.items()):
            if items[0].data.get("kind") == "text_field":
                obs = {"survey": survey, "question_id": qid, "state": "text", "selected_values": [], "flags": [],
                       "contribution_ids": sorted(item.data["evidence_id"] for item in items)}
            else:
                obs = plain(reduce_so2_question(items, scopes) if survey == "SO2" else reduce_mucp_question(items, scopes))
            observations.append({**obs, "observation_id": bid})
        resolutions = [plain((so2 if record.data["survey"] == "SO2" else mucp).resolutions[record.data["record_id"]]) for record in records]
        bb = {"biobank_id": bid, "name": names.get(bid, {}).get("name", bid), "country": country_key(names.get(bid, {}).get("country")),
              "directory_biobank_id": bid if bid.startswith("bbmri-eric:ID:") else None,
              "reporting_unit_kind": "national_summary" if any(r.data.get("record_type") == "country_summary" for r in mucp_records)
                  else "resolved_biobank" if bid in mucp.groups or bid in so2.groups else "unresolved_source_reporting_unit",
              "withdrawn": names.get(bid, {}).get("withdrawn", False), "identity_resolutions": resolutions,
              "survey_participation": {"SO2": bool(so2_records), "MuCP": bool(mucp_records)},
              "so2_source_records": [plain(item) for item in so2_records], "mucp_source_records": [plain(item) for item in mucp_records],
              "scopes": scopes, "evidence": evidence, "observations": observations,
              "conflicts": [item for item in observations if "conflict" in item["state"] or item["state"] == "varying_across_scopes"],
              "thematic_groups": [{**plain(theme), "contribution_ids": sorted(
                  item["evidence_id"] for item in evidence
                  if f'{item["survey"]}:{item["question_id"]}' in theme.get("questions", ()))
                  } for theme in crosswalk.get("themes", [])]}
        validate_evidence_links(CombinedBiobank(bb))
        biobanks.append(bb)
    payload = {"payload_type": "so2_mucp_combined_analysis", "payload_version": "2",
               "metadata": {"analytical_unit": "source_reporting_unit" if any(b["reporting_unit_kind"] != "resolved_biobank" for b in biobanks) else "unique_selected_biobank", "cohort": cohort},
               "inputs": {key: plain(value) for key, value in inputs.items() if key != "biobanks"},
               "matching_summary": {"selected_biobanks": sum(b["reporting_unit_kind"] == "resolved_biobank" for b in biobanks),
                                    "selected_reporting_units": len(biobanks), "overlapping_biobanks": len(cohort["intersection_ids"]), "so2_matched_biobanks": len(so2.groups), "mucp_matched_biobanks": len(mucp.groups)},
               "biobanks": biobanks, "unmatched_so2": [], "unmatched_mucp": [], "manual_review_matches": [],
               "excluded_source_records": [], "descriptive_statistics": {}, "coverage_audit": {}}
    for groups, key in ((so2, "unmatched_so2"), (mucp, "unmatched_mucp")):
        for record in sorted(groups.records, key=lambda item: item.data["record_id"]):
            resolution = groups.resolutions[record.data["record_id"]]
            item = {"record": plain(record), "resolution": plain(resolution)}
            status = resolution.data["status"]
            if status == "review":
                payload["manual_review_matches"].append(item)
            elif status in {"excluded", "rejected"}:
                payload["excluded_source_records"].append(item)
            elif status == "unmatched" or resolution.data.get("biobank_id") not in {bb["biobank_id"] for bb in biobanks}:
                payload[key].append(item)
    payload["matching_breakdown"] = build_matching_breakdown(payload)
    retained = {r["record_id"] for bank in biobanks for r in bank["mucp_source_records"]}
    if join in {"all-MuCP", "outer"} and retained != {r.data["record_id"] for r in mucp.records}:
        raise ValueError("Complete MuCP cohort must retain every source record exactly once")
    payload["metadata"]["mucp_source_coverage"] = {"input_records": len(mucp.records),
        "included_records": len(retained), "omitted_record_ids": sorted(r.data["record_id"] for r in mucp.records if r.data["record_id"] not in retained),
        "interpretation": "Unresolved sources remain separate reporting units, not verified distinct biobanks; national summaries retain their national scope."}
    return payload


def render_match_review(payload: Mapping[str, Any]) -> str:
    """Produce incremental manual/Codex matching instructions for unresolved identities.

    Args:
        payload: Combined payload containing unresolved source records and candidate evidence.

    Returns:
        Markdown instructions and exact fingerprint-bound decision material, without auto-acceptance.
    """
    lines = ["# SO2 / MuCP identity review", "", "Review only the unresolved records below. Do not guess or broadcast national/institutional answers.",
             "Add accepted/rejected decisions to the overrides JSON with reason, reviewer and reviewed_on; preserve the identity_fingerprint.", ""]
    for item in payload.get("manual_review_matches", []) + payload.get("unmatched_so2", []) + payload.get("unmatched_mucp", []):
        record, decision = item["record"], item["resolution"]
        if decision["status"] == "accepted":
            continue
        lines.extend([f"## {record['survey']} / {record['record_id']}", f"Institution: {record.get('identity', {}).get('institution_name', '')}",
                      f"Country: {record.get('country', '')}", f"Candidates: {', '.join(decision.get('candidate_ids', [])) or 'none'}",
                      f"Explanation: {decision.get('explanation', '')}",
                      "```json", json.dumps({"survey": record["survey"], "source_record_id": record["record_id"],
                                             "identity_fingerprint": decision.get("identity_fingerprint"), "action": "accept",
                                             "biobank_id": "REVIEW_REQUIRED", "reason": "", "reviewer": "", "reviewed_on": ""}, indent=2), "```", ""])
    return "\n".join(lines)


def validate_combined_payload(payload: Mapping[str, Any]) -> None:
    """Validate the combined JSON envelope and cross-reference provenance invariants.

    Args:
        payload: Fully assembled analytical payload, including discovered question catalogues.

    Returns:
        None. Unsupported versions, duplicate biobanks or dangling answer links raise ValueError.
    """
    from jsonschema import Draft202012Validator
    schema = json.loads((Path(__file__).parent / "survey-mappings/so2_mucp_combined.schema.json").read_text())
    errors = list(Draft202012Validator(schema).iter_errors(plain(payload)))
    if errors:
        raise ValueError("Invalid combined payload: " + errors[0].message)
    ids = [bb["biobank_id"] for bb in payload["biobanks"]]
    if payload["payload_version"] == "2":
        from survey_combined_cohort import select_biobank_cohort
        cohort = payload["metadata"].get("cohort")
        if not isinstance(cohort, Mapping):
            raise ValueError("Version-2 combined payload requires explicit cohort metadata")
        derived = select_biobank_cohort(cohort["so2_ids"], cohort["mucp_ids"], cohort["join"])
        if cohort != derived:
            raise ValueError("Combined cohort membership disagrees with survey identity sets")
        for bank in payload["biobanks"]:
            expected_participation = {survey: bank["biobank_id"] in cohort[key]
                                      for survey, key in (("SO2", "so2_ids"), ("MuCP", "mucp_ids"))}
            if bank.get("survey_participation") != expected_participation:
                raise ValueError("Combined cohort survey participation mismatch")
            if any(bool(bank[field]) != expected_participation[survey]
                   for survey, field in (("SO2", "so2_source_records"), ("MuCP", "mucp_source_records"))):
                raise ValueError("Combined survey participation disagrees with source records")
    expected = payload["metadata"].get("cohort", {}).get("selected_ids", ids)
    if len(ids) != len(set(ids)) or set(ids) != set(expected):
        raise ValueError("Combined cohort count/identity mismatch")
    for bb in payload["biobanks"]:
        validate_evidence_links(CombinedBiobank(bb))


def execute_merge(args: Any, directory_factory: Any) -> dict[str, Any]:
    """Orchestrate validated source matching, scope-aware statistics and safe publication.

    Args:
        args: Parsed merge-mucp source, report, registry and safety options.
        directory_factory: Existing CLI factory accepting args and returning read-only Directory.

    Returns:
        Published combined payload, allowing CLI summary reporting without rereading outputs.
    """
    from hashlib import sha256
    import so2_descriptive_report as descriptive
    from survey_mucp import load_mucp_document
    from survey_identity import build_identity_catalogue, load_match_overrides
    from survey_descriptive import (build_combined_statistics, load_thematic_crosswalk,
                                     load_visualization_registry, build_association_from_observations,
                                     build_combined_upset_matrix, reviewed_so2_heatmaps)
    from so2_descriptive_upsets import validate_matrix_upset_bundle
    from survey_combined_report import (render_combined_tex, render_individual_biobank_documents,
                                        publish_combined_outputs, load_report_presentation,
                                        validate_heatmap_presentation)
    from survey_mucp_quantities import extract_modality_quantities
    from survey_mucp_aggregation import aggregate_modality_quantities
    input_names = ("survey_file", "descriptive_schema", "form_json", "so2_findings", "mucp_json", "mucp_schema",
                   "mucp_reporting_policy",
                   "match_overrides", "crosswalk", "visualization_registry", "upset_assets_dir")
    output_names = ("output_json", "output_tex", "output_pdf", "output_chart_dir", "output_biobank_pdf_dir",
                    "output_match_review", "output_upset_r_dir")
    input_paths = [Path(getattr(args, name)).resolve() for name in input_names if getattr(args, name, None)]
    mappings = Path(__file__).parent / "survey-mappings"
    registry_path = mappings / "mucp_answer_states_v1.json"
    reporting_policy_path = Path(getattr(args, "mucp_reporting_policy", None) or mappings / "mucp_reporting_policy.json")
    presentation_path = mappings / "so2_mucp_report_presentation.json"
    quantity_review_path = mappings / "mucp_reviewed_quantities.json"
    association_path = mappings / "so2_2025_association_heatmaps.json"
    combined_schema_path = mappings / "so2_mucp_combined.schema.json"
    input_paths.extend(path.resolve() for path in (registry_path,reporting_policy_path,presentation_path,quantity_review_path,association_path,combined_schema_path))
    targets = {name: getattr(args, name, None) for name in output_names}
    render_requested = any(targets[name] for name in ("output_tex", "output_pdf", "output_chart_dir", "output_biobank_pdf_dir"))
    if render_requested and not targets["output_tex"]:
        targets["output_tex"] = str(Path(args.output_json).with_suffix(".tex"))
    output_paths = [Path(value).resolve() for value in targets.values() if value]
    all_paths = input_paths + output_paths
    if len(output_paths) != len(set(output_paths)):
        raise ValueError("Duplicate combined output target")
    for output in output_paths:
        for other in all_paths:
            if other == output and other not in input_paths:
                continue
            if output == other or output in other.parents or other in output.parents:
                raise ValueError("Combined outputs must be distinct from inputs and nested targets")
        if output.exists() and not args.overwrite:
            if not (output.is_dir() and not any(output.iterdir()) and output in [Path(value).resolve() for key, value in targets.items() if key.endswith("_dir") and value]):
                raise ValueError(f"Output already exists: {output}; use --overwrite")
    schema = descriptive.load_descriptive_schema(args.descriptive_schema)
    form = descriptive.load_form_manifest_structure(args.form_json)
    workbook = descriptive.read_descriptive_workbook(args.survey_file, schema)
    legacy_descriptive = descriptive.build_descriptive_payload(workbook, schema, form)
    questions = descriptive.validate_descriptive_schema(schema, [column for column in workbook.responses.columns if column != schema["output"]["source_row_column"]])
    records_so2 = so2_source_records(workbook, questions, form)
    catalogues = {"SO2": [{"question_id": q.question_id, "column": q.column, "label": q.label, "question_type": q.question_type,
                           "categories": list(q.categories), "form": legacy_descriptive["questions"][index].get("form")}
                          for index, q in enumerate(questions)]}
    presentation = load_report_presentation(presentation_path)
    document = load_mucp_document(Path(args.mucp_json), Path(args.mucp_schema), registry_path,
                                  reporting_policy_path)
    catalogues["MuCP"] = plain(document.questions + document.text_fields)
    hashes = {"so2_sha256": workbook.source_sha256, "mucp_sha256": document.source_sha256,
              "mucp_schema_sha256": document.schema_sha256,
              "mucp_states_sha256": sha256(registry_path.read_bytes()).hexdigest(),
              "mucp_reporting_policy_sha256": document.coverage_audit["reporting_policy"]["sha256"],
              "report_presentation_sha256": sha256(presentation_path.read_bytes()).hexdigest()}
    if quantity_review_path.exists():
        hashes["mucp_quantity_review_sha256"] = sha256(quantity_review_path.read_bytes()).hexdigest()
    for name in ("descriptive_schema", "form_json", "so2_findings", "match_overrides", "crosswalk", "visualization_registry"):
        path = getattr(args, name, None)
        if path:
            hashes[name + "_sha256"] = sha256(Path(path).read_bytes()).hexdigest()
    overrides = load_match_overrides(Path(args.match_overrides), hashes)
    frozen = load_bound_so2_resolutions(Path(args.so2_findings), workbook, overrides) if args.so2_findings else {}
    registry = load_visualization_registry(Path(args.visualization_registry), catalogues)
    available_so2 = {"SO2:" + question["question_id"] for question in catalogues["SO2"]}
    registry["heatmaps"] = [item for item in reviewed_so2_heatmaps(association_path)
                            if set(item["questions"]) <= available_so2] + registry.get("heatmaps", [])
    from so2_descriptive_report import load_association_heatmap_registry
    qms_categories = next(item.column_categories for item in load_association_heatmap_registry(association_path)
                          if item.definition_id == "technical_readiness_qms")
    for definition in registry["heatmaps"]:
        if definition["id"] == "qms-sops":
            definition["row_categories"] = list(qms_categories)
    hashes["so2_associations_sha256"] = sha256(association_path.read_bytes()).hexdigest()
    crosswalk = load_thematic_crosswalk(Path(args.crosswalk), catalogues)
    directory = directory_factory(args)
    catalogue = build_identity_catalogue(directory)
    so2 = group_sources(records_so2, resolve_so2_records(records_so2, catalogue, frozen, overrides))
    mucp_records, mucp_resolutions = resolve_scoped_sources(document.records, catalogue, overrides)
    mucp = group_sources(mucp_records, mucp_resolutions)
    inputs = {**hashes, "biobanks": plain(catalogue.biobanks), "directory_target": directory.getDirectoryUrl(),
              "directory_schema": directory.getSchema(), "directory_catalogue_sha256": fingerprint(catalogue.biobanks)}
    payload = build_combined_payload(so2, mucp, inputs, crosswalk, join=getattr(args, "join", "all-MuCP"))
    payload.update(question_catalogues=catalogues, source_manifest=plain(document.source_manifest),
                   coverage_audit=plain(document.coverage_audit), reconciliation=plain(document.reconciliation))
    payload["descriptive_statistics"] = build_combined_statistics(payload["biobanks"], catalogues, registry)
    payload["descriptive_statistics"]["MuCP"]["modality_quantities"] = extract_modality_quantities(
        payload["biobanks"], presentation["modality_quantities"])
    payload["descriptive_statistics"]["MuCP"]["quantity_aggregates"] = aggregate_modality_quantities(
        payload["descriptive_statistics"]["MuCP"]["modality_quantities"], payload["biobanks"])
    from survey_combined_quantity_views import build_reported_quantity_chart_views
    mucp_stats = payload["descriptive_statistics"]["MuCP"]
    mucp_stats["quantity_chart_views"] = build_reported_quantity_chart_views(
        mucp_stats["quantity_aggregates"], payload["biobanks"], presentation["modality_quantities"],
        mucp_stats["cohort_profile"])
    observation_index = {f"{survey}:{q['question_id']}": q.get("observations", []) for survey in ("SO2", "MuCP")
                         for q in payload["descriptive_statistics"][survey]["questions"]}
    question_index = {f"{survey}:{q.get('question_id', q.get('id'))}": q for survey, qs in catalogues.items() for q in qs}
    heatmaps = [build_association_from_observations(definition, observation_index) for definition in registry.get("heatmaps", [])]
    for item in heatmaps:
        item["pair"]["selected_cohort_N"] = len(payload["biobanks"])
        item["pair"]["participating_N"] = item["pair"]["paired_denominator"]
        item["pair"]["no_survey_response_count"] = len(payload["biobanks"]) - item["pair"]["paired_denominator"]
        item["question_labels"] = {qid: question_index[qid]["label"] for qid in (item["definition"]["row_question_id"], item["definition"]["column_question_id"])}
        definition_id = item["definition"]["definition_id"]
        if definition_id in presentation["heatmaps"]:
            item["definition"]["presentation"] = presentation["heatmaps"][definition_id]
    registry_definitions = [{"definition_id": "so2-" + item.definition_id,
                             "row_categories": item.row_categories, "column_categories": item.column_categories}
                            for item in load_association_heatmap_registry(association_path)]
    validate_heatmap_presentation(registry_definitions + [item["definition"] for item in heatmaps], presentation)
    payload["descriptive_statistics"]["cross_survey"]["heatmaps"] = heatmaps
    matrices = []
    from survey_descriptive import combined_upset_definition
    for configured in registry.get("upsets", []):
        definition = combined_upset_definition(configured, question_index)
        matrices.append(build_combined_upset_matrix(definition, payload["biobanks"]))
    from survey_combined_intersections import build_intersection_catalogue
    for matrix in matrices:
        matrix["intersections"] = build_intersection_catalogue(matrix)
    payload["upset_matrices"] = matrices
    asset_material = {"payload_version": "2", "input_hashes": hashes, "cohort": payload["metadata"]["cohort"], "cohort_ids": [bb["biobank_id"] for bb in payload["biobanks"]]}
    payload["upset_canonical_material"] = asset_material
    validate_combined_payload(payload)
    assets = validate_matrix_upset_bundle(matrices, asset_material, Path(args.upset_assets_dir)) if args.upset_assets_dir else None
    numerator, denominator = (float(value) for value in args.max_piechart_ratio.split(":"))
    if not math.isfinite(numerator) or not math.isfinite(denominator) or numerator <= 0 or denominator <= 0:
        raise ValueError("Piechart ratio must contain two positive values")
    options = {"include_contact_details": args.include_contact_details, "include_contribution_tables": args.long_report,
               "include_dossiers": getattr(args, "include_dossiers", False),
               "extended_evidence": getattr(args, "extended_evidence", False),
               "directory_target": directory.getDirectoryUrl(), "directory_schema": directory.getSchema(),
               "include_parent_context": args.include_parent_context, "max_piechart_ratio": numerator / denominator,
               "include_upset_deviations": getattr(args, "include_upset_deviations", False),
               "table_biobank_repeated_entries": getattr(args, "table_biobank_repeated_entries", "empty"),
               "chart_dir": args.output_chart_dir, "report_path": targets["output_tex"], "upset_matrices": matrices}
    rendered = render_combined_tex(payload, options, assets) if render_requested else None
    dossiers = render_individual_biobank_documents(payload, options) if args.output_biobank_pdf_dir else {}
    if args.output_upset_r_dir:
        import tempfile
        from so2_descriptive_upsets import write_matrix_upset_bundle
        with tempfile.TemporaryDirectory(prefix="combined-upset-") as temporary:
            stage = Path(temporary) / "bundle"
            write_matrix_upset_bundle(matrices, stage, asset_material)
            targets["upset_bundle_stage"] = stage
            publish_combined_outputs(payload, rendered, targets, dossiers, matrices, args.overwrite)
    else:
        publish_combined_outputs(payload, rendered, targets, dossiers, matrices, args.overwrite)
    return payload
