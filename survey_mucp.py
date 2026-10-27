"""Validate and project MuCP survey sources into lightweight immutable evidence."""

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from jsonschema import Draft202012Validator

from survey_evidence import SourceRecord, freeze


SUPPORTED_SCHEMA_VERSION = "1.0.0"
_RESPONSE_KEYS = {
    "response_id", "source_ids", "country", "record_type", "source_authority", "scope",
    "answers", "fields", "narrative_blocks", "collections", "structured_tables",
    "workbook_links", "consistency_warnings", "extraction_notes", "identity",
    "comments_and_qualifications", "full_evidence_source_ids", "normalization_status",
    "quantity_index", "collection_name", "raw_record", "raw_record_locator",
    "review_item_ids", "source_record_id", "transcription_method",
    "source_page_range", "submission_label", "source_links",
}
_RECORD_TYPES = {"submission", "country_workbook_row", "collection_workbook_row", "country_summary"}
_ROOT_KEYS = {"$schema", "schema_version", "metadata", "questionnaire", "country_coverage",
              "responses", "sources", "aggregate_workbook", "reconciliation", "validation"}
_BULK_KEYS = {"original_file", "extracted", "base64", "data_base64", "raw_bytes", "binary_content"}
_NORMALIZED_STATES = {"affirmed", "explicit_negative", "unknown", "conditional", "ambiguous_or_source_conflict"}
_BUNDLED_REPORTING_POLICY = Path(__file__).parent / "survey-mappings/mucp_reporting_policy.json"


@dataclass(frozen=True)
class MuCPQuestion:
    """Immutable questionnaire item retaining its complete source metadata.

    Attributes:
        data: Read-only mapping of the complete source question catalogue item, including its ID, part, group, type, wording, ordering metadata, aliases, and source-specific extensions.
    """

    data: Mapping[str, Any]

    def __post_init__(self) -> None:
        """Freeze questionnaire metadata after validating its identifier.

        Returns:
            None. Invalid catalogue rows raise ``ValueError``.
        """
        if not isinstance(self.data, Mapping) or not isinstance(self.data.get("id"), str):
            raise ValueError("MuCP question metadata requires a string id")
        object.__setattr__(self, "data", freeze(self.data))


@dataclass(frozen=True)
class MuCPDocument:
    """Validated MuCP catalogue, source records, audit summaries, and input hashes.

    Attributes:
        questions: Ordered tuple of recursively read-only metadata mappings for every checkbox question in the source questionnaire.
        text_fields: Ordered tuple of recursively read-only metadata mappings for every configured narrative/text field.
        records: Immutable response-level ``SourceRecord`` wrappers containing identity, explicit scopes, source-linked evidence, and classified metadata.
        source_manifest: Ordered lightweight source-file mappings keyed by ``source_id``, with paths and hashes but without embedded file snapshots.
        reconciliation: Recursively read-only source reconciliation findings and checks retained for downstream diagnostics.
        coverage_audit: Recursively read-only catalogue, answer-state, text-field, record-type, and source-coverage counts and dispositions.
        source_sha256: Lowercase SHA-256 digest of the exact input JSON bytes, computed incrementally.
        schema_sha256: Lowercase SHA-256 digest of the exact local JSON Schema bytes, computed incrementally.
        schema_version: Validated source schema version; currently exactly ``1.0.0``.
    """

    questions: tuple[Mapping[str, Any], ...]
    text_fields: tuple[Mapping[str, Any], ...]
    records: tuple[SourceRecord, ...]
    source_manifest: tuple[Mapping[str, Any], ...]
    reconciliation: Mapping[str, Any]
    coverage_audit: Mapping[str, Any]
    source_sha256: str
    schema_sha256: str
    schema_version: str

    def __post_init__(self) -> None:
        """Freeze all document-level structures without retaining source containers.

        Returns:
            None. The document exposes recursively read-only mappings and tuples.
        """
        for name in ("questions", "text_fields", "records", "source_manifest"):
            object.__setattr__(self, name, tuple(freeze(item) for item in getattr(self, name)))
        object.__setattr__(self, "reconciliation", freeze(self.reconciliation))
        object.__setattr__(self, "coverage_audit", freeze(self.coverage_audit))


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a JSON object while rejecting ambiguous duplicate member names.

    Args:
        pairs: Ordered key/value pairs supplied by ``json.load``'s object hook.

    Returns:
        Dictionary containing the pairs if every member name is unique.
    """
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key {key!r}")
        result[key] = value
    return result


def _hash_file(path: Path) -> str:
    """Compute SHA-256 incrementally so hashing does not duplicate a large source.

    Args:
        path: Input JSON or schema file whose exact bytes identify the source.

    Returns:
        Lowercase hexadecimal SHA-256 digest.
    """
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    """Parse UTF-8 JSON while rejecting duplicate keys at every nesting level.

    Args:
        path: Existing JSON file to parse once.

    Returns:
        Parsed JSON value with ordinary dictionaries and lists.
    """
    with path.open(encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=_unique_object)


def _check_local_refs(value: Any, location: str = "schema") -> None:
    """Reject remote or malformed JSON Schema references before validation.

    Args:
        value: Schema subtree currently being inspected.
        location: JSON path used to make a failing reference actionable.

    Returns:
        None. Any reference not rooted at the current schema raises ``ValueError``.
    """
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in {"$ref", "$dynamicRef", "$recursiveRef"}:
                if not isinstance(item, str) or not item.startswith("#"):
                    raise ValueError(f"Remote or invalid schema reference at {location}/{key}: {item!r}")
            _check_local_refs(item, f"{location}/{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_local_refs(item, f"{location}/{index}")


def _source_refs(value: Any, known_source_ids: set[str], location: str) -> tuple[dict[str, Any], ...]:
    """Validate and enrich explicit source references without copying source bodies.

    Args:
        value: Source-reference list attached to one extracted answer or descriptor.
        known_source_ids: IDs present in the separately validated source manifest.
        location: Source record and answer location for actionable errors.

    Returns:
        Tuple of light source ID/locator references with no embedded file content.
    """
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"Source references at {location} must be a list")
    result = []
    for reference in value:
        if not isinstance(reference, Mapping):
            raise ValueError(f"Source reference at {location} must be an object")
        source_id = reference.get("source_id")
        if source_id not in known_source_ids:
            raise ValueError(f"Unknown source reference {source_id!r} at {location}")
        if not isinstance(reference.get("locator"), str):
            raise ValueError(f"Source locator at {location} must be a string")
        result.append(_safe_extra(reference))
    return tuple(result)


def _validate_nested_refs(value: Any, source_ids: set[str], location: str) -> None:
    """Validate source references embedded in supplemental nested structures.

    Args:
        value: Source record, collection, or supplemental mapping to inspect recursively.
        source_ids: IDs present in the validated source manifest.
        location: Source record/scope path used in an error message.

    Returns:
        None. Unknown or malformed explicit source references raise ``ValueError``.
    """
    if isinstance(value, Mapping):
        if "source_id" in value and "locator" in value:
            if value["source_id"] not in source_ids or not isinstance(value["locator"], str):
                raise ValueError(f"Unknown or malformed source reference at {location}: {value.get('source_id')!r}")
        for key, item in value.items():
            _validate_nested_refs(item, source_ids, f"{location}/{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _validate_nested_refs(item, source_ids, f"{location}/{index}")


def _safe_extra(value: Any) -> Any:
    """Retain lightweight supplemental fields while dropping embedded source files.

    Args:
        value: JSON-compatible source field or subtree.

    Returns:
        Detached scalar/list/mapping content with known bulk-file keys omitted.
    """
    if isinstance(value, Mapping):
        return {key: _safe_extra(item) for key, item in value.items() if key.lower() not in _BULK_KEYS}
    if isinstance(value, list):
        return [_safe_extra(item) for item in value]
    return value


def _answer_state(answer: Mapping[str, Any], registry: Mapping[str, Any], location: str) -> str:
    """Check an answer's registered state/value pairing and return its normalized state.

    Args:
        answer: Source answer object with exact ``value`` and ``answer_state`` fields.
        registry: Versioned registry mapping observed state names to allowed pairs.
        location: Response/scope/question locator included in diagnostics.

    Returns:
        Canonical analytical state named by the versioned answer-state registry.
    """
    state = answer.get("answer_state")
    item = registry.get(state)
    if item is None:
        raise ValueError(f"Unsupported MuCP answer_state {state!r} at {location}; update the versioned state registry")
    value = answer.get("value")
    if not any(value is allowed if allowed is None else type(value) is type(allowed) and value == allowed
               for allowed in item.get("allowed_values", ())):
        raise ValueError(f"Contradictory value/state pair {value!r}/{state!r} at {location}")
    if state == "text_reported" and value is True:
        return "affirmed"
    if state == "text_reported" and value is None:
        return "unknown"
    return item["normalized_state"]


def load_mucp_reporting_policy(path: Path) -> dict[str, Any]:
    """Load a versioned analytical policy separate from raw source validation.

    Args:
        path: JSON file defining the supported present-checkbox interpretation.

    Returns:
        Detached policy mapping with an exact content SHA-256 for audit trails.
    """
    policy_path = Path(path)
    policy = _load_json(policy_path)
    if (not isinstance(policy, dict) or set(policy) != {"policy_version", "rule", "question_types"}
            or policy["policy_version"] != "1" or policy["rule"] != "present_applicable_unmarked_is_no"
            or policy["question_types"] != ["checkbox", "checkbox_with_optional_qualifier"]):
        raise ValueError("Unsupported MuCP reporting policy")
    return {**policy, "sha256": _hash_file(policy_path)}


def interpret_checkbox_answer(answer: Mapping[str, Any], question: Mapping[str, Any],
                              policy: Mapping[str, Any]) -> dict[str, Any]:
    """Interpret an existing checkbox entry without inferring absent options.

    Args:
        answer: Present source answer with its original state and literal value.
        question: Matching source catalogue question, including checkbox type.
        policy: Validated reporting policy and its version, not a source-state registry.

    Returns:
        Derived normalized value, interpretation basis and policy version; no input is mutated.
    """
    if not isinstance(answer, Mapping) or not isinstance(question, Mapping):
        raise ValueError("Checkbox interpretation requires a present answer and question")
    if (question.get("type") not in policy.get("question_types", ())
            or policy.get("rule") != "present_applicable_unmarked_is_no"
            or policy.get("policy_version") != "1"):
        raise ValueError("Unsupported checkbox reporting policy or question type")
    state, value = answer.get("answer_state"), answer.get("value")
    if state in {"selected", "listed", "stated_yes"} and value is True:
        normalized, basis = "affirmed", "selected_or_stated_yes"
    elif state == "explicit_no" and value is False:
        normalized, basis = "explicit_negative", "explicit_no"
    elif state == "unmarked" and value is None:
        normalized, basis = "explicit_negative", policy["rule"]
    elif state in {"conditional", "conditional_text"} and value is None:
        normalized, basis = "conditional", state
    elif state in {"ambiguous_formatting", "ambiguous_mark", "multiple_scopes_or_conflict"} and value is None:
        normalized, basis = "ambiguous_or_source_conflict", state
    elif state == "text_reported" and value is True:
        normalized, basis = "affirmed", "text_reported_true"
    elif state in {"text_reported", "not_asked", "not_asked_or_not_recognized", "not_confirmed",
                   "not_listed", "not_reported", "not_reported_in_country_summary"} and value is None:
        normalized, basis = "unknown", state
    else:
        raise ValueError(f"Contradictory or unsupported MuCP checkbox value/state pair {value!r}/{state!r}")
    return {"normalized_value": normalized, "basis": basis, "policy_version": policy["policy_version"]}


def _evidence_id(response_id: str, scope_id: str, question_id: str, locator: str, index: int) -> str:
    """Create stable evidence IDs from source identity and physical provenance.

    Args:
        response_id: Immutable MuCP response identifier.
        scope_id: Explicit submission or nested collection scope identifier.
        question_id: Source questionnaire field or supplemental-evidence identifier.
        locator: Physical source locator or deterministic source path.
        index: Stable within-container ordinal for repeated evidence units.

    Returns:
        Survey-prefixed SHA-256 identifier independent of mutable display labels.
    """
    material = "\0".join(("MuCP", response_id, scope_id, question_id, locator, str(index)))
    return "mucp:" + sha256(material.encode("utf-8")).hexdigest()


def _normalize_answer(
    answer: Any,
    question: Mapping[str, Any],
    response_id: str,
    scope: Mapping[str, Any],
    registry: Mapping[str, Any],
    source_ids: set[str],
    evidence_index: int,
    reporting_policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Project one checkbox answer into the shared evidence data contract.

    Args:
        answer: Raw answer mapping from the source response/scope.
        question: Full questionnaire metadata for this answer's stable question ID.
        response_id: Source response identifier retained as record provenance.
        scope: Explicit scope mapping; no parent-scope values are inherited.
        registry: Validated state registry for schema version 1.0.0.
        source_ids: Validated source manifest IDs used by answer references.
        evidence_index: Stable ordinal within the containing source answer map.
        reporting_policy: Versioned analytical checkbox interpretation, separate from raw validation.

    Returns:
        Evidence mapping satisfying the shared provenance contract and retaining raw values.
    """
    if not isinstance(answer, Mapping):
        raise ValueError(f"Answer {question['id']!r} in {response_id} must be an object")
    refs = _source_refs(answer.get("evidence", []), source_ids, f"{response_id}/{question['id']}")
    locator = refs[0]["locator"] if refs else question["id"]
    state = answer.get("answer_state")
    _answer_state(answer, registry, f"{response_id}/{scope['scope_id']}/{question['id']}")
    interpretation = interpret_checkbox_answer(answer, question, reporting_policy)
    normalized = interpretation["normalized_value"]
    extensions = _safe_extra({key: value for key, value in answer.items()
                              if key not in {"value", "answer_state", "raw_text", "qualifier_text", "evidence"}})
    if answer.get("answer_state") == "unmarked":
        extensions["checkbox_interpretation"] = {key: interpretation[key] for key in ("basis", "policy_version")}
    result = {
        "evidence_id": _evidence_id(response_id, scope["scope_id"], question["id"], locator, evidence_index),
        "survey": "MuCP", "source_record_id": response_id, "question_id": question["id"],
        "question_label": question.get("label", question["id"]), "form_uid": None,
        "part": question.get("part"), "group": question.get("group"), "kind": "structured_answer",
        "normalized_value": normalized, "raw_answer": answer.get("value"),
        "answer_state": state, "raw_text": answer.get("raw_text"),
        "qualifier_text": answer.get("qualifier_text"), "source_refs": list(refs),
        "scope_id": scope["scope_id"], "scope_kind": scope["kind"],
        "scope_label": scope["label"], "collection_id": scope.get("collection_id"),
        "scope_relationship": scope.get("relationship"),
        "extensions": extensions,
    }
    return result


def _make_scope(response_id: str, raw: Mapping[str, Any], *, collection: bool, index: int = 0) -> dict[str, Any]:
    """Create an explicit scope descriptor from exactly one source object.

    Args:
        response_id: Stable source response identifier.
        raw: Response or nested collection source mapping.
        collection: Whether ``raw`` is a nested collection, rather than response scope.
        index: Zero-based source collection position used only if its ID is absent.

    Returns:
        Scope with deterministic ID, source kind/label, and only explicit relationships.
    """
    if collection:
        local_id = raw.get("collection_id")
        suffix = str(local_id) if local_id not in (None, "") else str(index)
        kind = raw.get("scope")
        label = raw.get("name") or local_id or f"Collection {index + 1}"
        relation = {key: _safe_extra(raw[key]) for key in
                    ("parent_collection_id", "related_collection_id", "relationship", "relationships", "scope_link")
                    if key in raw}
        return {"scope_id": f"{response_id}:collection:{suffix}", "source_record_id": response_id,
                "kind": "collection", "source_scope_kind": kind,
                "label": label, "collection_id": local_id, "relationship": relation or None,
                "metadata": _safe_extra({key: value for key, value in raw.items()
                                          if key not in {"collection_id", "name", "scope", "answers", "fields"}})}
    return {"scope_id": f"{response_id}:submission", "source_record_id": response_id,
            "kind": raw.get("scope"), "source_scope_kind": raw.get("scope"),
            "label": raw.get("scope") or "Submission", "collection_id": None,
            "relationship": _safe_extra(raw.get("scope_relationship"))}


def _project_record(
    response: Mapping[str, Any],
    questions: Mapping[str, Mapping[str, Any]],
    text_fields: Mapping[str, Mapping[str, Any]],
    registry: Mapping[str, Any],
    source_ids: set[str],
    coverage: Counter,
    input_reference: Mapping[str, Any],
    source_pointer: str,
    reporting_policy: Mapping[str, Any],
) -> SourceRecord:
    """Project one submission and its explicitly scoped nested material.

    Args:
        response: One schema-validated response object from the source container.
        questions: Unique questionnaire items indexed by source question ID.
        text_fields: Unique text-field metadata indexed by source field ID.
        registry: Versioned registry for validating checkbox state/value combinations.
        source_ids: Source IDs from the validated manifest.
        coverage: Mutable question-evidence counter accumulated across all source scopes.
        input_reference: Input JSON path and content hash, not an invented document source.
        source_pointer: Exact JSON pointer to this response in the original input.
        reporting_policy: Versioned rule for derived checkbox values only.

    Returns:
        Immutable shared source record with scoped evidence and safe metadata only.
    """
    response_id = response.get("response_id")
    if not isinstance(response_id, str) or not response_id.strip():
        raise ValueError("MuCP response is missing response_id")
    if response.get("record_type") not in _RECORD_TYPES:
        raise ValueError(f"Unsupported MuCP record_type {response.get('record_type')!r} at {response_id}")
    unknown = set(response) - _RESPONSE_KEYS
    if unknown:
        raise ValueError(f"Unclassified MuCP response fields at {response_id}: {', '.join(sorted(unknown))}")
    for reference_key in ("source_ids", "full_evidence_source_ids"):
        for source_id in response.get(reference_key, ()) or ():
            if source_id not in source_ids:
                raise ValueError(f"Unknown source reference {source_id!r} in {response_id}/{reference_key}")
    _validate_nested_refs(response, source_ids, response_id)

    scopes = [_make_scope(response_id, response, collection=False)]
    nested_rows = response.get("collections", ())
    if not isinstance(nested_rows, list):
        raise ValueError(f"Collections at {response_id} must be a list")
    if any(not isinstance(item, Mapping) for item in nested_rows):
        raise ValueError(f"Every nested collection at {response_id} must be an object")
    scopes.extend(_make_scope(response_id, item, collection=True, index=i) for i, item in enumerate(nested_rows))
    for index, scope in enumerate(scopes):
        scope["input_json_pointer"] = source_pointer + (f"/collections/{index - 1}" if index else "")
    scope_ids = [scope["scope_id"] for scope in scopes]
    if len(scope_ids) != len(set(scope_ids)):
        raise ValueError(f"Duplicate scope ID in response {response_id}")

    evidence = []
    index = 0
    for scope, raw in zip(scopes, [response, *nested_rows]):
        answers = raw.get("answers", {}) or {}
        if not isinstance(answers, Mapping):
            raise ValueError(f"Answers at {response_id}/{scope['scope_id']} must be an object")
        unknown_questions = set(answers) - set(questions)
        if unknown_questions:
            raise ValueError(f"Unknown MuCP question IDs at {response_id}/{scope['scope_id']}: "
                             f"{', '.join(sorted(unknown_questions))}")
        for question_id, answer in answers.items():
            evidence.append(_normalize_answer(answer, questions[question_id], response_id, scope,
                                               registry, source_ids, index, reporting_policy))
            coverage[question_id] += 1
            index += 1

        fields = raw.get("fields", {}) or {}
        if not isinstance(fields, Mapping):
            raise ValueError(f"Text fields at {response_id}/{scope['scope_id']} must be an object")
        unknown_fields = set(fields) - set(text_fields)
        if unknown_fields:
            raise ValueError(f"Unknown MuCP text field IDs at {response_id}/{scope['scope_id']}: "
                             f"{', '.join(sorted(unknown_fields))}")
        for field_id, value in fields.items():
            field = text_fields[field_id]
            detail = value if isinstance(value, Mapping) else {}
            raw_text = detail.get("raw_text", detail.get("value")) if detail else value
            refs = _source_refs(detail.get("evidence", []), source_ids,
                                f"{response_id}/{scope['scope_id']}/{field_id}") if detail else ()
            evidence.append({
                "evidence_id": _evidence_id(response_id, scope["scope_id"], field_id,
                                            refs[0]["locator"] if refs else field_id, index),
                "survey": "MuCP", "source_record_id": response_id, "question_id": field_id,
                "question_label": field.get("label", field_id), "form_uid": None,
                "part": field.get("part"), "group": field.get("group"), "kind": "text_field",
                "normalized_value": raw_text, "raw_answer": value, "answer_state": "text_reported" if raw_text else "unmarked",
                "raw_text": raw_text, "qualifier_text": detail.get("qualifier_text") if detail else None,
                "source_refs": list(refs), "scope_id": scope["scope_id"], "scope_kind": scope["kind"],
                "scope_label": scope["label"], "collection_id": scope.get("collection_id"),
                "scope_relationship": scope.get("relationship"),
                "extensions": _safe_extra({k: v for k, v in detail.items()
                                            if k not in {"raw_text", "value", "evidence", "qualifier_text"}}),
            })
            index += 1

        for bucket in ("narrative_blocks", "comments_and_qualifications", "consistency_warnings"):
            entries = raw.get(bucket, [])
            if entries is None:
                entries = []
            if not isinstance(entries, list):
                raise ValueError(f"{bucket} at {response_id}/{scope['scope_id']} must be a list")
            for entry_index, entry in enumerate(entries):
                sanitized = _safe_extra(entry)
                refs = _source_refs(entry.get("evidence", []) if isinstance(entry, Mapping) else [],
                                    source_ids, f"{response_id}/{scope['scope_id']}/{bucket}/{entry_index}")
                identifier = f"supplemental:{bucket}:{entry_index}"
                text = entry.get("text", entry.get("value")) if isinstance(entry, Mapping) else entry
                evidence.append({
                    "evidence_id": _evidence_id(response_id, scope["scope_id"], identifier,
                                                refs[0]["locator"] if refs else identifier, index),
                    "survey": "MuCP", "source_record_id": response_id, "question_id": identifier,
                    "question_label": identifier, "form_uid": None, "part": None, "group": None,
                    "kind": "narrative" if bucket != "consistency_warnings" else "source_warning",
                    "normalized_value": _safe_extra(text), "raw_answer": sanitized,
                    "answer_state": "text_reported" if text else "unmarked", "raw_text": text if isinstance(text, str) else None,
                    "qualifier_text": (entry.get("qualifier_text", entry.get("qualifier"))
                                       if isinstance(entry, Mapping) else None),
                    "source_refs": list(refs), "scope_id": scope["scope_id"],
                    "scope_kind": scope["kind"], "scope_label": scope["label"],
                    "collection_id": scope.get("collection_id"), "scope_relationship": scope.get("relationship"),
                    "extensions": {"source_bucket": bucket},
                })
                index += 1

    scope_index = {scope["scope_id"]: scope for scope in scopes}
    for item in evidence:
        if not item["source_refs"]:
            qid = item["question_id"].replace("~", "~0").replace("/", "~1")
            if item["kind"] == "structured_answer":
                suffix = "/answers/" + qid
            elif item["kind"] == "text_field":
                suffix = "/fields/" + qid
            else:
                bucket = item["extensions"]["source_bucket"]
                suffix = "/" + bucket + "/" + item["question_id"].rsplit(":", 1)[1]
            item["source_refs"] = [{**input_reference, "kind": "input_json",
                "locator": scope_index[item["scope_id"]]["input_json_pointer"] + suffix,
                "document_evidence_status": "not_provided"}]
    identity = response.get("identity", {}) or {}
    if not isinstance(identity, Mapping):
        raise ValueError(f"Identity at {response_id} must be an object")
    country_summary = response["record_type"] == "country_summary"
    record_identity = {
        "name": None if country_summary else identity.get("institution_name"),
        "institution_name": None if country_summary else identity.get("institution_name"),
        "email_addresses": [] if country_summary else _safe_extra(identity.get("email_addresses", [])),
    }
    if not country_summary and "explicit_biobank_id" in identity:
        record_identity["explicit_biobank_id"] = identity["explicit_biobank_id"]
    metadata = {key: _safe_extra(value) for key, value in response.items()
                if key not in {"answers", "fields", "collections", "narrative_blocks",
                               "comments_and_qualifications", "consistency_warnings", "identity"}}
    identity_extras = {key: _safe_extra(value) for key, value in identity.items()
                       if key not in {"institution_name", "email_addresses", "explicit_biobank_id"}}
    if identity_extras:
        metadata["identity_extensions"] = identity_extras
    if "raw_record" in response:
        metadata["raw_record"] = _safe_extra(response["raw_record"])
        metadata["raw_record_disposition"] = "retained_lightweight_source_record_bulk_fields_filtered"
    if country_summary:
        metadata["identity_scope_disposition"] = "diagnostic_only_not_biobank_evidence"
    return SourceRecord({
        "record_id": response_id, "survey": "MuCP", "country": response.get("country"),
        "record_type": response["record_type"], "identity": record_identity, "scopes": scopes,
        "evidence": evidence, "metadata": metadata,
    })


def load_mucp_document(path: Path, schema_path: Path, state_registry_path: Path,
                       reporting_policy_path: Path | None = None) -> MuCPDocument:
    """Validate and parse a complete MuCP source once into immutable light records.

    Args:
        path: Source-complete MuCP JSON input; loaded once and never retained whole.
        schema_path: Local Draft 2020-12 source schema, permitting only internal refs.
        state_registry_path: Versioned registry of supported source answer-state/value pairs.
        reporting_policy_path: Optional analytical policy file; defaults to the bundled version.

    Returns:
        Immutable catalogue, source records, reconciliation, coverage audit, and SHA-256s.
    """
    source_path = Path(path)
    schema_file = Path(schema_path)
    registry_file = Path(state_registry_path)
    reporting_policy = load_mucp_reporting_policy(reporting_policy_path or _BUNDLED_REPORTING_POLICY)
    schema = _load_json(schema_file)
    if not isinstance(schema, Mapping) or schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise ValueError("MuCP source schema must declare JSON Schema Draft 2020-12")
    _check_local_refs(schema)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    registry_doc = _load_json(registry_file)
    if not isinstance(registry_doc, Mapping) or registry_doc.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        raise ValueError(f"Answer-state registry must target schema version {SUPPORTED_SCHEMA_VERSION}")
    state_registry = registry_doc.get("states")
    if not isinstance(state_registry, Mapping) or not state_registry:
        raise ValueError("Answer-state registry requires a non-empty states object")
    for state, definition in state_registry.items():
        if (not isinstance(state, str) or not isinstance(definition, Mapping)
                or definition.get("normalized_state") not in _NORMALIZED_STATES
                or not isinstance(definition.get("allowed_values"), list)
                or any(value is not None and type(value) is not bool for value in definition["allowed_values"])):
            raise ValueError(f"Invalid answer-state registry entry for {state!r}")
    registry_states = set(state_registry)
    source = _load_json(source_path)
    errors = sorted(validator.iter_errors(source), key=lambda error: list(map(str, error.absolute_path)))
    if errors:
        first = errors[0]
        locator = "/".join(map(str, first.absolute_path)) or "<root>"
        raise ValueError(f"MuCP schema validation failed at {locator}: {first.message}")
    if source.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        raise ValueError(f"Unsupported MuCP schema_version {source.get('schema_version')!r}; expected {SUPPORTED_SCHEMA_VERSION}")
    unknown_root_keys = set(source) - _ROOT_KEYS
    if unknown_root_keys:
        raise ValueError(f"Unclassified MuCP source fields: {', '.join(sorted(unknown_root_keys))}")

    questionnaire = source.get("questionnaire")
    question_rows = questionnaire.get("checkbox_questions") if isinstance(questionnaire, Mapping) else None
    text_rows = questionnaire.get("text_fields") if isinstance(questionnaire, Mapping) else None
    if not isinstance(question_rows, list) or not isinstance(text_rows, list):
        raise ValueError("MuCP questionnaire must contain checkbox_questions and text_fields arrays")
    questions = {}
    for row in question_rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("id"), str) or not row["id"].strip():
            raise ValueError("Every MuCP checkbox question requires a non-empty string id")
        if row["id"] in questions:
            raise ValueError(f"Duplicate MuCP question ID {row['id']!r}")
        if row.get("type") not in {"checkbox", "checkbox_with_optional_qualifier"}:
            raise ValueError(f"Unsupported MuCP question type {row.get('type')!r} for {row['id']}")
        questions[row["id"]] = row
    text_fields = {}
    for row in text_rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("id"), str) or not row["id"].strip():
            raise ValueError("Every MuCP text field requires a non-empty string id")
        if row["id"] in text_fields or row["id"] in questions:
            raise ValueError(f"Duplicate MuCP catalogue ID {row['id']!r}")
        if row.get("type") not in {"text", "free_text_with_source_evidence"}:
            raise ValueError(f"Unsupported MuCP text field type {row.get('type')!r} for {row['id']}")
        text_fields[row["id"]] = row

    source_manifest = []
    source_ids = set()
    for item in source.get("sources", ()):
        source_id = item.get("source_id") if isinstance(item, Mapping) else None
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("Every MuCP source manifest row requires source_id")
        if source_id in source_ids:
            raise ValueError(f"Duplicate MuCP source ID {source_id!r}")
        source_ids.add(source_id)
        source_fields = {key: _safe_extra(value) for key, value in item.items()
                         if key not in _BULK_KEYS}
        source_manifest.append(source_fields)

    response_ids = set()
    for response in source.get("responses", ()):
        response_id = response.get("response_id") if isinstance(response, Mapping) else None
        if not isinstance(response_id, str) or not response_id:
            raise ValueError("Every MuCP response requires response_id")
        if response_id in response_ids:
            raise ValueError(f"Duplicate MuCP response ID {response_id!r}")
        response_ids.add(response_id)
    coverage = Counter()
    source_hash = _hash_file(source_path)
    input_reference = {"path": str(source_path.resolve()), "sha256": source_hash}
    records = tuple(_project_record(response, questions, text_fields, state_registry, source_ids, coverage,
                                   input_reference, f"/responses/{index}", reporting_policy)
                    for index, response in enumerate(source.get("responses", ())))
    from survey_mucp_reviewed import apply_reviewed_quantities
    records = apply_reviewed_quantities(records, source_hash, source_manifest,
                                       {r["response_id"]: r for r in source.get("responses", ())})
    coverage_audit = {
        "question_count": len(questions), "text_field_count": len(text_fields),
        "answer_counts_by_question": dict(coverage),
        "questions_without_any_answer": [question_id for question_id in questions if not coverage[question_id]],
        "record_type_counts": dict(Counter(record.data["record_type"] for record in records)),
        "text_field_dispositions": {
            field_id: sum(1 for record in records for item in record.data["evidence"]
                          if item["kind"] == "text_field" and item["question_id"] == field_id)
            for field_id in text_fields
        },
        "answer_state_counts": dict(Counter(item["answer_state"] for record in records
                                              for item in record.data["evidence"]
                                              if item["kind"] == "structured_answer")),
        "source_metadata": _safe_extra(source.get("metadata", {})),
        "questionnaire_metadata": _safe_extra({key: value for key, value in questionnaire.items()
                                                if key not in {"checkbox_questions", "text_fields"}}),
        "country_coverage": _safe_extra(source.get("country_coverage", [])),
        "source_validation": _safe_extra(source.get("validation", {})),
        "aggregate_workbook_metadata": _safe_extra(source.get("aggregate_workbook", {})),
        "record_count": len(records), "nested_scope_count": sum(max(0, len(record.data["scopes"]) - 1) for record in records),
        "registered_state_count": len(registry_states),
        "reporting_policy": {"policy_version": reporting_policy["policy_version"],
                             "rule": reporting_policy["rule"], "sha256": reporting_policy["sha256"]},
    }
    reconciliation = _safe_extra(source.get("reconciliation", {}))
    schema_hash = _hash_file(schema_file)
    del source
    return MuCPDocument(tuple(questions.values()), tuple(text_fields.values()), records,
                        tuple(source_manifest), reconciliation, coverage_audit,
                        source_hash, schema_hash, SUPPORTED_SCHEMA_VERSION)


def discover_mucp_questions(document: MuCPDocument) -> tuple[MuCPQuestion, ...]:
    """Return the complete MuCP question catalogue independently of thematic mappings.

    Args:
        document: Validated MuCP document with immutable question metadata.

    Returns:
        Ordered tuple of MuCP question wrappers preserving every catalogue property.
    """
    return tuple(MuCPQuestion(question) for question in document.questions)


def mucp_source_records(document: MuCPDocument) -> tuple[SourceRecord, ...]:
    """Expose validated source records without leaking the original JSON container.

    Args:
        document: Validated MuCP document produced by ``load_mucp_document``.

    Returns:
        Immutable source records with scoped evidence and provenance links.
    """
    return document.records
