# vim:ts=4:sw=4:tw=0:sts=4:et

"""Generate shareable AI-check cache payloads from current Directory data."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from ai_cache import (
    compute_entity_checksum,
    compute_source_checksum,
    get_withdrawn_scope_label,
)


GENERATOR_NAME = "codex-ai-review-v2"
ENTITY_TYPE = "COLLECTION"
SEVERITY = "WARNING"

RULES = {
    "AgeText": {
        "filename": "age-text.json",
        "fields": [
            "COLLECTION.name",
            "COLLECTION.description",
            "COLLECTION.age_low",
            "COLLECTION.age_high",
        ],
    },
    "StudyText": {
        "filename": "study-text.json",
        "fields": [
            "COLLECTION.name",
            "COLLECTION.description",
            "COLLECTION.type",
        ],
    },
    "FFPEText": {
        "filename": "ffpe-text.json",
        "fields": [
            "COLLECTION.name",
            "COLLECTION.description",
            "COLLECTION.materials",
        ],
    },
    "CovidText": {
        "filename": "covid-text.json",
        "fields": [
            "COLLECTION.name",
            "COLLECTION.description",
            "COLLECTION.diagnosis_available",
        ],
    },
}

PEDIATRIC_PATTERNS = [
    (re.compile(r"\bpediatric\b", re.IGNORECASE), "pediatric"),
    (re.compile(r"\bpaediatric\b", re.IGNORECASE), "paediatric"),
    (re.compile(r"\bchildren\b", re.IGNORECASE), "children"),
    (re.compile(r"\bchild\b", re.IGNORECASE), "child"),
    (re.compile(r"\binfant\b", re.IGNORECASE), "infant"),
    (re.compile(r"\bnewborn\b", re.IGNORECASE), "newborn"),
    (re.compile(r"\bneonat", re.IGNORECASE), "neonatal"),
]
ADULT_PATTERNS = [
    (re.compile(r"\badults?\b", re.IGNORECASE), "adult"),
    (re.compile(r"\belderly\b", re.IGNORECASE), "elderly"),
    (re.compile(r"\bgeriatric\b", re.IGNORECASE), "geriatric"),
]
AGE_SUPPRESSION_PATTERNS = [
    re.compile(r"adults? and pediatric|pediatric and adults?|adults? and children|children and adults?", re.IGNORECASE),
    re.compile(r"parents?|pregnan|mother|father|caretaker|family", re.IGNORECASE),
    re.compile(r"young adults?|adolescen", re.IGNORECASE),
]

LONGITUDINAL_PATTERNS = [
    (re.compile(r"\blongitudinal\b", re.IGNORECASE), "longitudinal"),
    (re.compile(r"\bfollow[- ]?up\b", re.IGNORECASE), "follow-up"),
    (re.compile(r"\brepeated visits?\b", re.IGNORECASE), "repeated visits"),
]
PROSPECTIVE_PATTERNS = [
    (re.compile(r"\bprospective\b", re.IGNORECASE), "prospective"),
]
CASE_CONTROL_PATTERNS = [
    (re.compile(r"\bcase[- ]control\b", re.IGNORECASE), "case-control"),
    (re.compile(r"\bcases? and controls?\b", re.IGNORECASE), "cases and controls"),
]
PROSPECTIVE_EQUIVALENTS = {"COHORT", "LONGITUDINAL", "BIRTH_COHORT"}

FFPE_PATTERNS = [
    (re.compile(r"\bffpe\b", re.IGNORECASE), "FFPE"),
    (re.compile(r"\bparaffin\b", re.IGNORECASE), "paraffin"),
    (
        re.compile(r"formalin[- ]fixed paraffin[- ]embedded", re.IGNORECASE),
        "formalin-fixed paraffin-embedded",
    ),
]
FFPE_STORAGE_PATTERNS = [
    re.compile(r"\bffpe blocks?\b", re.IGNORECASE),
    re.compile(r"\bparaffin blocks?\b", re.IGNORECASE),
    re.compile(r"\bparaffin[- ]embedded\b", re.IGNORECASE),
    re.compile(r"\bparaffin(?:ové)? blo", re.IGNORECASE),
]
FFPE_SLIDE_PATTERNS = [
    re.compile(r"whole slide", re.IGNORECASE),
    re.compile(r"\bwsi\b", re.IGNORECASE),
    re.compile(r"\bslides?\b", re.IGNORECASE),
    re.compile(r"\bsections?\b", re.IGNORECASE),
    re.compile(r"\bstain(?:ed|ing)?\b", re.IGNORECASE),
    re.compile(r"\bihc\b", re.IGNORECASE),
    re.compile(r"\bh&e\b", re.IGNORECASE),
]
FFPE_DERIVED_PATTERNS = [
    re.compile(r"isolated (?:dna|rna)", re.IGNORECASE),
    re.compile(r"(?:dna|rna).{0,60}from ffpe", re.IGNORECASE),
    re.compile(r"ffpe.{0,60}(?:dna|rna)", re.IGNORECASE),
    re.compile(r"extract(?:ed|ion)?.{0,60}ffpe", re.IGNORECASE),
]
DERIVED_MATERIALS = {"DNA", "RNA", "CF_DNA", "TUMOR_RNA"}

COVID_GENERAL_PATTERNS = [
    (re.compile(r"covid[- ]?19", re.IGNORECASE), "COVID-19"),
    (re.compile(r"sars[- ]?cov[- ]?2", re.IGNORECASE), "SARS-CoV-2"),
    (re.compile(r"\bcoronavirus\b", re.IGNORECASE), "Coronavirus"),
]
COVID_LONG_PATTERNS = [
    (re.compile(r"long[- ]covid", re.IGNORECASE), "long COVID"),
    (re.compile(r"post[- ]covid", re.IGNORECASE), "post-COVID"),
    (re.compile(r"ongoing covid", re.IGNORECASE), "ongoing COVID"),
]
COVID_NEGATIVE_PATTERNS = [
    re.compile(r"covid[- ]?19[^a-z0-9]{0,4}negative", re.IGNORECASE),
    re.compile(r"not detected", re.IGNORECASE),
    re.compile(r"negative for sars[- ]?cov[- ]?2", re.IGNORECASE),
    re.compile(r"seronegative", re.IGNORECASE),
]
COVID_VACCINATION_PATTERNS = [
    re.compile(r"vaccin", re.IGNORECASE),
    re.compile(r"booster", re.IGNORECASE),
    re.compile(r"immuni[sz]ation", re.IGNORECASE),
    re.compile(r"vaccinated", re.IGNORECASE),
]
COVID_CONTEXT_PATTERNS = [
    re.compile(r"pandemic", re.IGNORECASE),
    re.compile(r"lockdown", re.IGNORECASE),
    re.compile(r"questionnaire", re.IGNORECASE),
    re.compile(r"survey", re.IGNORECASE),
    re.compile(r"school closures", re.IGNORECASE),
    re.compile(r"day care", re.IGNORECASE),
    re.compile(r"serolog", re.IGNORECASE),
    re.compile(r"seroprevalence", re.IGNORECASE),
    re.compile(r"antibod", re.IGNORECASE),
    re.compile(r"impact on", re.IGNORECASE),
]
COVID_ACUTE_PATTERNS = [
    re.compile(r"covid[- ]?19 patients?", re.IGNORECASE),
    re.compile(r"recovered patients?", re.IGNORECASE),
    re.compile(r"convalescent", re.IGNORECASE),
    re.compile(r"after covid[- ]?19 infection", re.IGNORECASE),
    re.compile(r"covid[- ]?19 cohort", re.IGNORECASE),
    re.compile(r"hospitali[sz]ed.{0,30}covid", re.IGNORECASE),
]
COVID_ACUTE_DIAGNOSIS = re.compile(r"\bU07(?:\.1|\.2)?\b", re.IGNORECASE)
COVID_LONG_DIAGNOSIS = re.compile(r"\bU09(?:\.9)?\b", re.IGNORECASE)


def generate_payloads(directory: Any) -> list[dict[str, Any]]:
    """Generate all AI cache payloads for the current Directory scope."""
    collections = sorted(directory.getCollections(), key=lambda item: item["id"])
    scope = get_withdrawn_scope_label(directory)
    payloads = []
    for rule_name, spec in RULES.items():
        findings = []
        checked_entities = []
        for collection in collections:
            checked_entities.append(
                {
                    "entity_id": collection["id"],
                    "entity_type": ENTITY_TYPE,
                    "entity_checksum": compute_entity_checksum(collection),
                    "source_checksum": compute_source_checksum(
                        ENTITY_TYPE,
                        collection,
                        spec["fields"],
                    ),
                }
            )
            finding = _generate_finding(rule_name, collection, directory)
            if finding is not None:
                findings.append(finding)
        payloads.append(
            {
                "schema": directory.getSchema(),
                "rule": rule_name,
                "generator": GENERATOR_NAME,
                "generated_on": date.today().isoformat(),
                "withdrawn_scope": scope,
                "checked_fields": spec["fields"],
                "checked_entities": checked_entities,
                "findings": sorted(findings, key=lambda item: (item["entity_id"], item["message"])),
                "filename": spec["filename"],
            }
        )
    return payloads


def write_payloads(directory: Any, output_root: Path) -> dict[str, int]:
    """Write all AI cache payloads to disk and return per-rule finding counts."""
    payloads = generate_payloads(directory)
    schema_dir = output_root / directory.getSchema()
    schema_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for payload in payloads:
        filename = payload["filename"]
        path = schema_dir / filename
        serializable_payload = dict(payload)
        serializable_payload.pop("filename", None)
        path.write_text(
            json.dumps(serializable_payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        counts[payload["rule"]] = len(payload["findings"])
    return counts


def build_report_lines(payloads: Iterable[dict[str, Any]]) -> list[str]:
    """Return AI findings in the human-readable report format used for review."""
    lines: list[str] = []
    for payload in payloads:
        for finding in payload["findings"]:
            lines.append(
                f"Collection {finding['entity_id']} AI:{finding['rule']}/{finding['severity']}: "
                f"{finding['message']} {finding['action']}"
            )
    return sorted(lines)


def summarize_payloads(payloads: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Return finding counts per rule."""
    return dict(Counter(payload["rule"] for payload in payloads for _ in payload["findings"]))


def _generate_finding(rule_name: str, collection: dict[str, Any], directory: Any) -> Optional[dict[str, Any]]:
    """Generate one rule-specific finding for a collection, if any."""
    if rule_name == "AgeText":
        return _generate_age_finding(collection, directory)
    if rule_name == "StudyText":
        return _generate_study_finding(collection, directory)
    if rule_name == "FFPEText":
        return _generate_ffpe_finding(collection, directory)
    if rule_name == "CovidText":
        return _generate_covid_finding(collection, directory)
    raise ValueError(f"Unsupported AI rule {rule_name!r}.")


def _generate_age_finding(collection: dict[str, Any], directory: Any) -> Optional[dict[str, Any]]:
    text = _collection_text(collection)
    if any(pattern.search(text) for pattern in AGE_SUPPRESSION_PATTERNS):
        return None

    pediatric_match = _first_match(PEDIATRIC_PATTERNS, text)
    adult_match = _first_match(ADULT_PATTERNS, text)
    if pediatric_match and adult_match:
        return None

    age_low = collection.get("age_low")
    age_high = collection.get("age_high")
    if pediatric_match and (age_high is None or age_high > 18):
        return _build_collection_finding(
            rule_name="AgeText",
            collection=collection,
            directory=directory,
            message=(
                f"Collection text suggests a pediatric population (matched '{pediatric_match}'), "
                f"but age_high is {age_high}."
            ),
            action=(
                "Review the age range metadata and the collection narrative. "
                "If the collection is pediatric, age_high should usually be <= 18."
            ),
        )
    if adult_match and (age_low is None or age_low < 18):
        return _build_collection_finding(
            rule_name="AgeText",
            collection=collection,
            directory=directory,
            message=(
                f"Collection text suggests an adult/geriatric population (matched '{adult_match}'), "
                f"but age_low is {age_low}."
            ),
            action=(
                "Review the age range metadata and the collection narrative. "
                "If the collection targets adults only, age_low should usually be >= 18."
            ),
        )
    return None


def _generate_study_finding(collection: dict[str, Any], directory: Any) -> Optional[dict[str, Any]]:
    text = _collection_text(collection)
    current_types = set(_as_sorted_strings(collection.get("type")))
    suggestions: list[str] = []
    matched_terms: list[str] = []

    longitudinal_match = _first_match(LONGITUDINAL_PATTERNS, text)
    if longitudinal_match and "LONGITUDINAL" not in current_types:
        suggestions.append("LONGITUDINAL")
        matched_terms.append(longitudinal_match)

    prospective_match = _first_match(PROSPECTIVE_PATTERNS, text)
    if (
        prospective_match
        and "PROSPECTIVE_COLLECTION" not in current_types
        and not (current_types & PROSPECTIVE_EQUIVALENTS)
    ):
        suggestions.append("PROSPECTIVE_COLLECTION")
        matched_terms.append(prospective_match)

    case_control_match = _first_match(CASE_CONTROL_PATTERNS, text)
    if case_control_match and "CASE_CONTROL" not in current_types:
        suggestions.append("CASE_CONTROL")
        matched_terms.append(case_control_match)

    if not suggestions:
        return None

    return _build_collection_finding(
        rule_name="StudyText",
        collection=collection,
        directory=directory,
        message=(
            f"Collection text suggests structured type(s) {suggestions} based on terms {matched_terms}, "
            f"but the current type list is {_as_sorted_strings(collection.get('type'))}."
        ),
        action=(
            "Review the narrative and add the missing structured collection type(s) "
            "if the text really describes the collection design."
        ),
    )


def _generate_ffpe_finding(collection: dict[str, Any], directory: Any) -> Optional[dict[str, Any]]:
    materials = set(_as_sorted_strings(collection.get("materials")))
    if "TISSUE_PARAFFIN_EMBEDDED" in materials:
        return None

    text = _collection_text(collection)
    matched_term = _first_match(FFPE_PATTERNS, text)
    if not matched_term:
        return None

    storage_signal = any(pattern.search(text) for pattern in FFPE_STORAGE_PATTERNS)
    slide_signal = any(pattern.search(text) for pattern in FFPE_SLIDE_PATTERNS)
    derived_signal = any(pattern.search(text) for pattern in FFPE_DERIVED_PATTERNS)

    if slide_signal and "TISSUE_STAINED" in materials and not storage_signal:
        return None
    if derived_signal and materials and materials <= DERIVED_MATERIALS:
        return None

    return _build_collection_finding(
        rule_name="FFPEText",
        collection=collection,
        directory=directory,
        message=(
            f"Collection text mentions '{matched_term}', but materials do not include "
            f"TISSUE_PARAFFIN_EMBEDDED (current materials: {_as_sorted_strings(collection.get('materials'))})."
        ),
        action=(
            "Review whether the collection really contains FFPE/paraffin-embedded tissue. "
            "If yes, add TISSUE_PARAFFIN_EMBEDDED to materials; otherwise clarify the narrative "
            "when the text only refers to slides, sections, images, or derived DNA/RNA."
        ),
    )


def _generate_covid_finding(collection: dict[str, Any], directory: Any) -> Optional[dict[str, Any]]:
    text = _collection_text(collection)
    general_match = _first_match(COVID_GENERAL_PATTERNS, text)
    long_match = _first_match(COVID_LONG_PATTERNS, text)
    if not general_match and not long_match:
        return None
    if any(pattern.search(text) for pattern in COVID_NEGATIVE_PATTERNS):
        return None

    diagnosis_names = _diagnosis_names(collection)
    current_diagnoses = " ".join(diagnosis_names)
    has_long_covid_diagnosis = bool(COVID_LONG_DIAGNOSIS.search(current_diagnoses))
    has_acute_covid_diagnosis = bool(COVID_ACUTE_DIAGNOSIS.search(current_diagnoses))

    if long_match:
        if has_long_covid_diagnosis:
            return None
        return _build_collection_finding(
            rule_name="CovidText",
            collection=collection,
            directory=directory,
            message=(
                f"Collection text suggests post-/long-COVID context (matched '{long_match}'), "
                f"but diagnosis_available does not contain U09.9 or another post-COVID diagnosis "
                f"(current diagnoses: {diagnosis_names})."
            ),
            action=(
                "Review whether the collection really targets post-/long-COVID cases. "
                "If yes, add U09.9 or the relevant structured post-COVID diagnosis; otherwise reword the narrative."
            ),
        )

    vaccination_only = any(pattern.search(text) for pattern in COVID_VACCINATION_PATTERNS)
    context_only = any(pattern.search(text) for pattern in COVID_CONTEXT_PATTERNS)
    acute_signal = any(pattern.search(text) for pattern in COVID_ACUTE_PATTERNS)

    if vaccination_only and not acute_signal:
        return None
    if context_only and not acute_signal:
        return None
    if has_acute_covid_diagnosis:
        return None

    return _build_collection_finding(
        rule_name="CovidText",
        collection=collection,
        directory=directory,
        message=(
            f"Collection text suggests COVID-19 disease context (matched '{general_match or long_match}'), "
            f"but diagnosis_available does not contain recognized COVID-19 diagnoses such as U07.1/U07.2 "
            f"(current diagnoses: {diagnosis_names})."
        ),
        action=(
            "Review whether the collection really targets COVID-19 cases or convalescents. "
            "If yes, add the relevant structured COVID-19 diagnosis; otherwise reword the narrative to avoid misleading discovery."
        ),
    )


def _build_collection_finding(
    *,
    rule_name: str,
    collection: dict[str, Any],
    directory: Any,
    message: str,
    action: str,
) -> dict[str, Any]:
    """Build one shareable AI finding record for a collection."""
    fields = RULES[rule_name]["fields"]
    return {
        "rule": rule_name,
        "entity_id": collection["id"],
        "entity_type": ENTITY_TYPE,
        "severity": SEVERITY,
        "fields": fields,
        "message": message,
        "action": action,
        "withdrawn": str(directory.isCollectionWithdrawn(collection["id"])),
        "entity_checksum": compute_entity_checksum(collection),
        "source_checksum": compute_source_checksum(ENTITY_TYPE, collection, fields),
    }


def _collection_text(collection: dict[str, Any]) -> str:
    """Return a normalized narrative text for a collection."""
    name = collection.get("name") or ""
    description = collection.get("description") or ""
    return f"{name} {description}".replace("\n", " ")


def _first_match(patterns: Iterable[tuple[re.Pattern[str], str]], text: str) -> Optional[str]:
    """Return the label of the first regex that matches the text."""
    for pattern, label in patterns:
        if pattern.search(text):
            return label
    return None


def _as_sorted_strings(values: Any) -> list[str]:
    """Return a stable sorted list of string-like values."""
    if not values:
        return []
    if isinstance(values, list):
        normalized = []
        for value in values:
            if isinstance(value, dict):
                normalized.append(str(value.get("name") or value.get("id") or value))
            else:
                normalized.append(str(value))
        return sorted(normalized)
    return [str(values)]


def _diagnosis_names(collection: dict[str, Any]) -> list[str]:
    """Return sorted diagnosis names for a collection."""
    diagnoses = collection.get("diagnosis_available")
    if not diagnoses:
        return []
    names = []
    for diagnosis in diagnoses:
        if isinstance(diagnosis, dict):
            names.append(str(diagnosis.get("name") or diagnosis.get("id") or diagnosis))
        else:
            names.append(str(diagnosis))
    return sorted(names)
