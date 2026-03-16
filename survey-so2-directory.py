#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

"""Analyze SO2 survey responses against the BBMRI Directory."""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import subprocess
import tempfile
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd

from cli_common import (
    add_directory_auth_arguments,
    add_directory_schema_argument,
    add_logging_arguments,
    build_parser,
    configure_logging,
)
from directory import Directory
from duo_terms import normalize_duo_term_ids
from fix_proposals import EntityFixProposal, compute_checksum


DEFAULT_MAPPING_FILE = Path("survey-mappings/so2_2025_directory_mapping.json")
DEFAULT_OBJECTIVES_MAPPING_FILE = Path("survey-mappings/so2_2025_question_to_strategic_objectives.json")

EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_INPUT_ERROR = 2

COUNTRY_NAME_TO_ISO2 = {
    "austria": "AT",
    "belgium": "BE",
    "bulgaria": "BG",
    "czech republic": "CZ",
    "denmark": "DK",
    "estonia": "EE",
    "finland": "FI",
    "france": "FR",
    "germany": "DE",
    "lithuania": "LT",
    "malta": "MT",
    "netherlands": "NL",
    "norway": "NO",
    "poland": "PL",
    "slovakia": "SK",
    "spain": "ES",
    "espana": "ES",
    "espana ": "ES",
    "sweden": "SE",
    "swiss": "CH",
    "switzerland": "CH",
}

GENERIC_TEXT_FIELDS = {"description", "access_description", "url", "access_uri", "name"}
BOOLEAN_UPDATE_FIELDS = {
    ("BIOBANK", "collaboration_non_for_profit"),
    ("BIOBANK", "collaboration_commercial"),
    ("COLLECTION", "collaboration_non_for_profit"),
    ("COLLECTION", "collaboration_commercial"),
    ("COLLECTION", "commercial_use"),
}

GENERIC_INSTITUTION_TOKENS = {
    "and",
    "bank",
    "biobank",
    "center",
    "centre",
    "de",
    "der",
    "des",
    "di",
    "faculty",
    "for",
    "hospital",
    "hospitals",
    "hopitaux",
    "infrastructure",
    "institute",
    "inst",
    "la",
    "medical",
    "of",
    "repository",
    "resource",
    "service",
    "services",
    "the",
    "universitaire",
    "universitaires",
    "university",
}
INSTITUTION_ACRONYM_STOPWORDS = {
    "and",
    "de",
    "der",
    "des",
    "di",
    "for",
    "la",
    "of",
    "the",
}

INLINE_BREAK_PATTERN = re.compile(
    r"bbmri-eric:[A-Za-z0-9:._-]+|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)
WHOLE_IDENTIFIER_PATTERN = re.compile(r"^(?:\([A-Z]{2}\)\s+)?(?:BIOBANK|COLLECTION|CONTACT|NETWORK)\s+bbmri-eric:[A-Za-z0-9:._-]+$|^bbmri-eric:[A-Za-z0-9:._-]+$|^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$|^[A-Z]{2}_[A-Za-z0-9._-]+$")

FINDING_TYPE_METADATA = {
    "row_resolution": {
        "directory_fields": ["BIOBANK.id", "BIOBANK.name", "BIOBANK.country", "COLLECTION.id"],
        "comparison_description": (
            "Resolve the survey row conservatively: explicit network/biobank ID first, explicit collection IDs second, "
            "then exact respondent-email contact matching, then institution-name matching (certain or approximate). "
            "Approximate name matches remain analysis-only."
        ),
    },
    "geo.country": {
        "directory_fields": ["BIOBANK.country"],
        "comparison_description": "Normalize the survey country to ISO-2 and compare it exactly with the mapped Directory biobank country.",
    },
    "biobank.name": {
        "directory_fields": ["BIOBANK.name"],
        "comparison_description": (
            "Normalize institution names (case, accents, common aliases) and compare them textually. "
            "Differences remain manual-review findings because naming conventions differ."
        ),
    },
    "contact.email": {
        "directory_fields": ["CONTACT.email"],
        "comparison_description": "Compare the respondent email with the mapped Directory contact email case-insensitively.",
    },
    "promotion.partnership_interest": {
        "directory_fields": ["BIOBANK.collaboration_non_for_profit", "BIOBANK.collaboration_commercial"],
        "comparison_description": (
            "Translate the survey partnership-interest answer into expected collaboration flags directionally only. "
            "This is intentionally a plausible/manual mapping, not an exact semantic equivalence."
        ),
    },
    "promotion.partnership_interest.duo": {
        "directory_fields": ["COLLECTION.data_use", "COLLECTION.collaboration_commercial", "BIOBANK.collaboration_commercial"],
        "comparison_description": (
            "For a survey row mapped to exactly one collection, treat an academic-only promotion answer as a plausible "
            "signal for the existing AccessPolicies DUO restriction DUO:0000018 (not-for-profit, non-commercial use only), "
            "but only when the collection is not already commercial."
        ),
    },
    "sample_types.materials": {
        "directory_fields": ["COLLECTION.materials"],
        "comparison_description": (
            "Map structured survey sample-type answers to Directory material terms. Compare at aggregate scope across the "
            "mapped collections; emit collection-level update proposals only when the survey row maps to exactly one collection."
        ),
    },
    "imaging.wsi_presence": {
        "directory_fields": [
            "COLLECTION.type",
            "COLLECTION.data_categories",
            "COLLECTION.imaging_modality",
            "COLLECTION.image_dataset_type",
            "COLLECTION.description",
        ],
        "comparison_description": (
            "The Directory has no dedicated WSI field. Compare the survey WSI answer against generic imaging support "
            "signals plus unstructured text hints only."
        ),
    },
}


class InputError(Exception):
    """Raised for user-facing input/configuration problems."""


def build_cli() -> argparse.ArgumentParser:
    parser = build_parser(description="Analyze the SO2 Datafication survey against the BBMRI Directory.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Analyze survey responses and write findings JSON.")
    _add_common_cli(analyze)
    analyze.add_argument("-i", "--survey-file", required=True, help="Path to the SO2 survey XLSX export.")
    analyze.add_argument(
        "-m",
        "--mapping-file",
        default=str(DEFAULT_MAPPING_FILE),
        help="Path to the editable survey-to-Directory mapping JSON.",
    )
    analyze.add_argument(
        "--objectives-mapping-file",
        default=str(DEFAULT_OBJECTIVES_MAPPING_FILE),
        help="Path to the survey-question to strategic-objective mapping JSON.",
    )
    analyze.add_argument("-o", "--output-json", required=True, help="Write findings JSON to this path.")
    analyze.add_argument("--output-tex", help="Optional path for the rendered TeX report.")
    analyze.add_argument("--output-pdf", help="Optional path for the rendered PDF report.")

    render = subparsers.add_parser("render-report", help="Render TeX/PDF from an existing findings JSON file.")
    add_logging_arguments(render)
    render.add_argument("-i", "--input-json", required=True, help="Findings JSON produced by analyze.")
    render.add_argument("--output-tex", required=True, help="Write rendered TeX to this path.")
    render.add_argument("--output-pdf", help="Optional path for the rendered PDF report.")

    export = subparsers.add_parser("export-update-plan", help="Export qcheck-updater-compatible JSON from findings.")
    add_logging_arguments(export)
    export.add_argument("-i", "--input-json", required=True, help="Findings JSON produced by analyze.")
    export.add_argument("-o", "--output-json", required=True, help="Write update-plan JSON to this path.")
    export.add_argument(
        "--min-confidence",
        default="uncertain",
        choices=["uncertain", "almost_certain", "certain"],
        help="Minimum confidence to export into the update plan.",
    )
    return parser


def _add_common_cli(parser: argparse.ArgumentParser) -> None:
    add_logging_arguments(parser)
    add_directory_auth_arguments(parser)
    add_directory_schema_argument(parser, default="ERIC")
    parser.add_argument(
        "--directory-target",
        default=None,
        help="Optional Directory base URL; defaults to the standard production Directory.",
    )


def load_mapping(path: str | Path) -> dict[str, Any]:
    mapping_path = Path(path)
    if not mapping_path.exists():
        raise InputError(f"Mapping JSON {mapping_path} does not exist.")
    payload = json.loads(mapping_path.read_text(encoding="utf-8"))
    if "entity_resolution" not in payload or "field_mappings" not in payload:
        raise InputError(f"Mapping JSON {mapping_path} is missing entity_resolution or field_mappings.")
    return payload


def load_objectives_mapping(path: str | Path) -> dict[str, Any]:
    mapping_path = Path(path)
    if not mapping_path.exists():
        raise InputError(f"Strategic-objective mapping JSON {mapping_path} does not exist.")
    payload = json.loads(mapping_path.read_text(encoding="utf-8"))
    if "strategic_objectives" not in payload or "question_mappings" not in payload:
        raise InputError(
            f"Strategic-objective mapping JSON {mapping_path} is missing strategic_objectives or question_mappings."
        )
    return payload


def load_survey(mapping: dict[str, Any], survey_file: str | Path) -> pd.DataFrame:
    survey_path = Path(survey_file)
    if not survey_path.exists():
        raise InputError(f"Survey file {survey_path} does not exist.")
    header_row = int(mapping.get("survey", {}).get("header_row", 4)) - 1
    return pd.read_excel(survey_path, sheet_name=mapping["survey"]["sheet"], header=header_row)


def build_directory(args: argparse.Namespace) -> Directory:
    if args.schema != "ERIC" and not args.token and not (args.username and args.password):
        raise InputError(
            "Reading a non-ERIC schema requires -t/--token or -u/--username and -p/--password."
        )
    kwargs: dict[str, Any] = {
        "schema": args.schema,
        "debug": args.debug,
        "directory_url": args.directory_target,
        "include_withdrawn_entities": False,
    }
    if args.token:
        kwargs["token"] = args.token
    elif args.schema != "ERIC":
        kwargs["username"] = args.username
        kwargs["password"] = args.password
    return Directory(**kwargs)


def normalize_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    text = text.strip().casefold()
    text = re.sub(r"[\\.,;:/()\[\]{}_-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    replacements = {
        "berne": "bern",
        "geneva": "geneve",
        "universitair": "university",
        "universitaire": "university",
        "universitaires": "university",
        "universite": "university",
        "universiteit": "university",
        "universitaet": "university",
        "medical center": "medical centre",
        "umc": "university medical centre",
        "bb ": "biobank ",
    }
    for source, target in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        text = re.sub(rf"(?<![a-z0-9]){re.escape(source)}(?![a-z0-9])", target, text)
    return re.sub(r"\s+", " ", text).strip()


def normalized_institution_signature(value: Any) -> tuple[str, ...]:
    tokens = [
        token
        for token in normalize_text(value).split()
        if token and token not in GENERIC_INSTITUTION_TOKENS
    ]
    return tuple(sorted(dict.fromkeys(tokens)))


def normalize_country(value: Any) -> str:
    if value is None:
        return ""
    text = normalize_text(value)
    if not text:
        return ""
    return COUNTRY_NAME_TO_ISO2.get(text, str(value).strip().upper())


def split_semicolon_values(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    parts = [part.strip() for part in str(value).split(";")]
    return [part for part in parts if part]


def cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def get_row_value(row: pd.Series, *column_names: str) -> Any:
    for column_name in column_names:
        if column_name in row.index:
            return row.get(column_name)
    normalized_columns = {
        normalize_text(column_name): column_name
        for column_name in row.index
        if isinstance(column_name, str)
    }
    for column_name in column_names:
        matched_column = normalized_columns.get(normalize_text(column_name))
        if matched_column is not None:
            return row.get(matched_column)
    return None


def parse_material_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = [part.strip() for part in str(value).split(",")]
    return [str(item).strip() for item in items if str(item).strip()]


def escape_latex(value: Any) -> str:
    text = "" if value is None else str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_\allowbreak{}",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def escape_latex_breakable_identifier(value: Any) -> str:
    text = "" if value is None else str(value)
    return latex_breakable_token(text)


def escape_latex_breakable_entity(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", "-", text)
    return latex_breakable_token(text)


def escape_latex_breakable_email(value: Any) -> str:
    text = "" if value is None else str(value)
    return latex_breakable_token(text)


def latex_breakable_token(value: Any) -> str:
    text = "" if value is None else str(value)
    pdf_text = text.replace("{", "").replace("}", "")
    return rf"\texorpdfstring{{\nolinkurl{{{text}}}}}{{{pdf_text}}}"


def escape_latex_with_inline_breaks(value: Any) -> str:
    text = "" if value is None else str(value)
    fragments: list[str] = []
    last_index = 0
    for match in INLINE_BREAK_PATTERN.finditer(text):
        fragments.append(escape_latex(text[last_index:match.start()]))
        token = match.group(0)
        if "@" in token:
            fragments.append(escape_latex_breakable_email(token))
        else:
            fragments.append(escape_latex_breakable_entity(token))
        last_index = match.end()
    fragments.append(escape_latex(text[last_index:]))
    return "".join(fragments)


STATUS_COLORS = {
    "consistent": "soGreen",
    "inconsistent": "soRed",
    "manual_review": "soOrange",
    "missing_in_directory": "soRed",
    "missing_from_directory": "soOrange",
    "ambiguous": "soOrange",
    "ambiguous_resolution": "soOrange",
    "unresolved_row": "soOrange",
    "not_comparable": "soBlue",
}

STATUS_SECTION_INTROS = {
    "consistent": (
        "These findings indicate that the survey answer is reflected consistently in the mapped Directory entity under the current comparison rule."
    ),
    "inconsistent": (
        "These findings indicate a concrete mismatch between the survey answer and the mapped Directory metadata under the applied comparison rule."
    ),
    "missing_in_directory": (
        "These findings are linked to a concrete Directory entity, but the corresponding survey-reported metadata or "
        "capability is not reflected in the current Directory record."
    ),
    "manual_review": (
        "These findings have a plausible survey-to-Directory relation, but the evidence is not strong enough for an "
        "automatic consistency judgement."
    ),
    "missing_from_directory": (
        "These findings cover survey respondents or identifiers that could not be mapped confidently to a current "
        "Directory entity."
    ),
    "ambiguous": (
        "These findings indicate that the available survey and Directory evidence supports more than one plausible interpretation or mapping."
    ),
    "ambiguous_resolution": (
        "These findings indicate that the survey row could not be resolved to a single confident Directory target because multiple plausible matches remain."
    ),
    "unresolved_row": (
        "These findings indicate that the survey row could not be evaluated meaningfully because no sufficiently reliable mapping or comparison basis was established."
    ),
    "not_comparable": (
        "These findings indicate that the survey answer and the current Directory metadata are related in topic, but not directly comparable under the implemented rules."
    ),
}

STATUS_DISPLAY_ORDER = [
    "consistent",
    "inconsistent",
    "missing_in_directory",
    "manual_review",
    "missing_from_directory",
    "ambiguous",
    "ambiguous_resolution",
    "unresolved_row",
    "not_comparable",
]

STABLE_STATUS_SECTIONS = {
    "missing_in_directory",
    "manual_review",
    "missing_from_directory",
}


def ordered_statuses(statuses: list[str]) -> list[str]:
    order = {status: index for index, status in enumerate(STATUS_DISPLAY_ORDER)}
    return sorted(statuses, key=lambda status: (order.get(status, len(order)), status))


def latex_label(value: Any) -> str:
    text = "" if value is None else str(value)
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower() or "item"


def serialize_report_value(value: Any) -> str:
    if value is None:
        return "<empty>"
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else "<empty>"
    if isinstance(value, float) and pd.isna(value):
        return "<empty>"
    if isinstance(value, (list, dict, bool, int, float)):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    text = str(value).strip()
    return text if text else "<empty>"


def summarize_detail(value: Any, max_len: int = 220) -> str:
    text = serialize_report_value(value)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def summarize_sequence(value: Any) -> str:
    if isinstance(value, list):
        items = [str(item) for item in value if str(item).strip()]
        return ", ".join(items) if items else "<empty>"
    return serialize_report_value(value)


def format_finding_values(finding: dict[str, Any]) -> tuple[str, str]:
    mapping_id = str(finding.get("mapping_id", ""))
    survey_value = finding.get("survey_value")
    directory_value = finding.get("directory_value")
    if mapping_id == "sample_types.materials":
        survey_expected = set(survey_value.get("expected_materials", []) if isinstance(survey_value, dict) else survey_value or [])
        directory_observed = set(directory_value.get("observed_materials", []) if isinstance(directory_value, dict) else directory_value or [])
        missing = sorted(survey_expected - directory_observed)
        extra = sorted(directory_observed - survey_expected)
        return summarize_sequence(missing), summarize_sequence(extra)
    if mapping_id == "promotion.partnership_interest":
        if isinstance(survey_value, dict):
            survey_text = (
                f"interest={serialize_report_value(survey_value.get('interest'))}, "
                f"expected_non_profit={serialize_report_value(survey_value.get('expected_non_profit'))}, "
                f"expected_commercial={serialize_report_value(survey_value.get('expected_commercial'))}"
            )
        else:
            survey_text = serialize_report_value(survey_value)
        if isinstance(directory_value, dict):
            directory_text = (
                f"collaboration_non_for_profit={serialize_report_value(directory_value.get('collaboration_non_for_profit'))}, "
                f"collaboration_commercial={serialize_report_value(directory_value.get('collaboration_commercial'))}"
            )
        else:
            directory_text = serialize_report_value(directory_value)
        return survey_text, directory_text
    if mapping_id == "promotion.partnership_interest.duo":
        if isinstance(survey_value, dict):
            survey_text = (
                f"interest={serialize_report_value(survey_value.get('interest'))}, "
                f"expected_duo={serialize_report_value(survey_value.get('expected_duo'))}"
            )
        else:
            survey_text = serialize_report_value(survey_value)
        if isinstance(directory_value, dict):
            directory_text = (
                f"data_use={serialize_report_value(directory_value.get('data_use'))}, "
                f"collaboration_commercial={serialize_report_value(directory_value.get('collaboration_commercial'))}"
            )
        else:
            directory_text = serialize_report_value(directory_value)
        return survey_text, directory_text
    if mapping_id == "imaging.wsi_presence":
        if isinstance(survey_value, dict):
            survey_text = f"answer={serialize_report_value(survey_value.get('answer'))}"
        else:
            survey_text = serialize_report_value(survey_value)
        if isinstance(directory_value, dict):
            directory_text = (
                f"has_image_support={serialize_report_value(directory_value.get('has_image_support'))}, "
                f"has_wsi_hint={serialize_report_value(directory_value.get('has_wsi_hint'))}"
            )
        else:
            directory_text = serialize_report_value(directory_value)
        return survey_text, directory_text
    return summarize_detail(survey_value), summarize_detail(directory_value)


def escape_report_value(value: str) -> str:
    text = "" if value is None else str(value)
    if WHOLE_IDENTIFIER_PATTERN.fullmatch(text):
        if "@" in text:
            return escape_latex_breakable_email(text)
        return escape_latex_breakable_entity(text)
    return escape_latex_with_inline_breaks(text)


def finding_link(mapping_id: str) -> str:
    label = latex_label(f"appendix-{mapping_id}")
    return rf"\hyperref[{label}]{{{escape_latex_breakable_identifier(mapping_id)} {escape_latex('(appendix)')}}}"


STATUS_DISPLAY_LABELS = {
    "missing_in_directory": "Survey Data Missing from the Directory",
    "manual_review": "Data Requiring Manual Review",
    "missing_from_directory": "Entities Not Mapped to the Directory",
}


def colored_status_text(status: str) -> str:
    color = STATUS_COLORS.get(status, "black")
    label = STATUS_DISPLAY_LABELS.get(status, status.replace('_', ' ').title())
    return rf"\textcolor{{{color}}}{{{escape_latex(label)}}}"


def format_finding_result(finding: dict[str, Any], *, concise_consistent: bool) -> str:
    status = str(finding.get("status", ""))
    explanation = str(finding.get("explanation", "")).strip()
    if concise_consistent and status == "consistent":
        return "Consistent."
    survey_value, directory_value = format_finding_values(finding)
    if str(finding.get("mapping_id", "")) == "sample_types.materials":
        return f"{explanation} Missing in Directory={survey_value}; Extra in Directory={directory_value}."
    return f"{explanation} Survey={survey_value}; Directory={directory_value}."


def build_appendix_entries(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for finding in report.get("findings", []):
        mapping_id = str(finding.get("mapping_id", "")).strip()
        if not mapping_id:
            continue
        current = entries.setdefault(
            mapping_id,
            {
                "mapping_id": mapping_id,
                "why_relevant": str(finding.get("why_relevant", "")).strip(),
                "relation_type": str(finding.get("relation_type", "")).strip(),
                "reliability_levels": set(),
                "survey_fields": set(),
                "directory_fields": set(FINDING_TYPE_METADATA.get(mapping_id, {}).get("directory_fields", [])),
                "comparison_description": str(FINDING_TYPE_METADATA.get(mapping_id, {}).get("comparison_description", "")).strip(),
                "strategic_objectives": set(),
            },
        )
        if finding.get("why_relevant") and not current["why_relevant"]:
            current["why_relevant"] = str(finding.get("why_relevant", "")).strip()
        if finding.get("relation_type") and not current["relation_type"]:
            current["relation_type"] = str(finding.get("relation_type", "")).strip()
        current["reliability_levels"].add(str(finding.get("reliability", "")).strip())
        current["survey_fields"].update(str(item) for item in finding.get("survey_fields", []) if str(item).strip())
        current["directory_fields"].update(
            str(item) for item in finding.get("directory_fields", []) if str(item).strip()
        )
        if finding.get("comparison_description") and not current["comparison_description"]:
            current["comparison_description"] = str(finding.get("comparison_description", "")).strip()
        current["strategic_objectives"].update(
            str(item) for item in finding.get("strategic_objectives", []) if str(item).strip()
        )
    for entry in entries.values():
        entry["reliability_levels"] = sorted(item for item in entry["reliability_levels"] if item)
        entry["survey_fields"] = sorted(entry["survey_fields"])
        entry["directory_fields"] = sorted(entry["directory_fields"])
        entry["strategic_objectives"] = sorted(entry["strategic_objectives"])
    return dict(sorted(entries.items()))


def choose_contact(
    scope: dict[str, Any],
    *,
    biobank_index: dict[str, dict[str, Any]],
    collection_index: dict[str, dict[str, Any]],
    contact_index: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if scope["collection_ids"]:
        contact_ids = []
        for collection_id in scope["collection_ids"]:
            collection = collection_index.get(collection_id)
            if collection and collection.get("contact"):
                contact_value = collection["contact"]
                contact_ids.append(contact_value["id"] if isinstance(contact_value, dict) else contact_value)
        unique_ids = sorted(set(contact_ids))
        if len(unique_ids) == 1:
            return contact_index.get(unique_ids[0])
    biobank_id = scope.get("biobank_id")
    if biobank_id:
        biobank = biobank_index.get(biobank_id)
        if biobank and biobank.get("contact"):
            contact_value = biobank["contact"]
            contact_id = contact_value["id"] if isinstance(contact_value, dict) else contact_value
            return contact_index.get(contact_id)
    return None


def get_collections_ids_from_biobank(directory: Directory, biobank_id: str) -> list[str]:
    graph = directory.getGraphBiobankCollectionsFromBiobank(biobank_id)
    return sorted(node_id for node_id in graph.nodes() if ":collection:" in str(node_id))


def summarize_collection_scope(
    matched_collection_ids: list[str],
    all_biobank_collection_ids: list[str],
) -> str:
    matched = sorted(dict.fromkeys(matched_collection_ids))
    all_collections = sorted(dict.fromkeys(all_biobank_collection_ids))
    if not matched:
        return "<none>"
    if matched == all_collections:
        return "all collections"
    unmatched = [collection_id for collection_id in all_collections if collection_id not in set(matched)]
    if len(all_collections) > 5 and 0 < len(unmatched) < 5:
        return "All except " + ", ".join(unmatched)
    return ", ".join(matched)


def aggregate_scope(scope: dict[str, Any], collection_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    collections = [collection_index.get(collection_id) for collection_id in scope["collection_ids"]]
    collections = [collection for collection in collections if collection]
    materials = sorted({item for collection in collections for item in parse_material_value(collection.get("materials")) if item != "NAV"})
    types = sorted({item for collection in collections for item in parse_material_value(collection.get("type"))})
    data_categories = sorted({item for collection in collections for item in parse_material_value(collection.get("data_categories")) if item != "NAV"})
    imaging_modalities = sorted({item for collection in collections for item in parse_material_value(collection.get("imaging_modality"))})
    image_dataset_types = sorted({item for collection in collections for item in parse_material_value(collection.get("image_dataset_type"))})
    descriptions = [str(collection.get("description") or "") for collection in collections]
    exact_sizes = [int(collection["size"]) for collection in collections if collection.get("size") not in (None, "")]
    return {
        "collections": collections,
        "materials": materials,
        "types": types,
        "data_categories": data_categories,
        "imaging_modalities": imaging_modalities,
        "image_dataset_types": image_dataset_types,
        "has_image_support": bool(
            "IMAGE" in types
            or "IMAGING_DATA" in data_categories
            or imaging_modalities
            or image_dataset_types
        ),
        "has_wsi_hint": bool(
            any(
                hint in normalize_text(description)
                for description in descriptions
                for hint in ("whole slide", "wsi", "histopath", "digital pathology", "slide microscopy")
            )
            or "SM" in imaging_modalities
        ),
        "size_sum": sum(exact_sizes) if exact_sizes else None,
        "size_known_collection_count": len(exact_sizes),
        "collection_count": len(collections),
    }


def normalize_collection_id(value: str) -> str:
    collection_id = cell_text(value)
    if not collection_id:
        return ""
    if collection_id.startswith("bbmri-eric:ID:"):
        return collection_id
    if ":collection:" in collection_id:
        return f"bbmri-eric:ID:{collection_id}"
    return collection_id


def normalize_biobank_id(value: str) -> str:
    biobank_id = cell_text(value)
    if not biobank_id:
        return ""
    if biobank_id.startswith("bbmri-eric:ID:"):
        return biobank_id
    if ":collection:" in biobank_id:
        return normalize_collection_id(biobank_id)
    if ":" not in biobank_id:
        return f"bbmri-eric:ID:{biobank_id}"
    return biobank_id


def normalize_network_id(value: str) -> str:
    network_id = cell_text(value)
    if network_id.startswith("bbmri-eric:networkID:"):
        return network_id
    return ""


def institution_aliases(value: Any) -> set[str]:
    raw_text = cell_text(value)
    normalized = normalize_text(raw_text)
    aliases = {normalized} if normalized else set()
    normalized_tokens = [token for token in normalized.split() if token and token not in INSTITUTION_ACRONYM_STOPWORDS]
    if len(normalized_tokens) >= 2:
        aliases.add("".join(token[0] for token in normalized_tokens))
    trimmed_tokens = [token for token in normalized_tokens if token not in {"bank", "biobank", "repository", "resource", "service", "services"}]
    if len(trimmed_tokens) >= 2:
        aliases.add("".join(token[0] for token in trimmed_tokens))
    raw_upper_tokens = re.findall(r"\b[A-Z]{2,}\b", raw_text)
    aliases.update(token.casefold() for token in raw_upper_tokens)
    return {alias for alias in aliases if alias}


def biobank_id_aliases(value: Any) -> set[str]:
    normalized_id = normalize_biobank_id(value)
    aliases = {normalized_id.casefold()} if normalized_id else set()
    if normalized_id.startswith("bbmri-eric:ID:"):
        suffix = normalized_id.removeprefix("bbmri-eric:ID:")
        aliases.add(suffix.casefold())
        if "_" in suffix:
            _, local_id = suffix.split("_", 1)
            aliases.add(local_id.casefold())
            if local_id.endswith("BB") and len(local_id) > 2:
                aliases.add(local_id[:-2].casefold())
    return {alias for alias in aliases if alias}


def match_biobank_alias_candidates(
    aliases: set[str],
    biobanks_by_alias: dict[str, list[dict[str, Any]]],
    *,
    country: str,
) -> list[dict[str, Any]]:
    candidates_by_id: dict[str, dict[str, Any]] = {}
    for alias in aliases:
        for candidate in biobanks_by_alias.get(alias, []):
            if country and str(candidate.get("country") or "").upper() != country:
                continue
            candidates_by_id[candidate["id"]] = candidate
    return [candidates_by_id[biobank_id] for biobank_id in sorted(candidates_by_id)]


def build_contact_usage_indexes(
    biobank_index: dict[str, dict[str, Any]],
    collection_index: dict[str, dict[str, Any]],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    biobank_ids_by_contact: dict[str, set[str]] = defaultdict(set)
    collection_ids_by_contact: dict[str, set[str]] = defaultdict(set)
    for biobank in biobank_index.values():
        contact_value = biobank.get("contact")
        if not contact_value:
            continue
        contact_id = contact_value["id"] if isinstance(contact_value, dict) else str(contact_value)
        biobank_ids_by_contact[contact_id].add(biobank["id"])
    for collection in collection_index.values():
        contact_value = collection.get("contact")
        if not contact_value:
            continue
        contact_id = contact_value["id"] if isinstance(contact_value, dict) else str(contact_value)
        collection_ids_by_contact[contact_id].add(collection["id"])
    return (
        {contact_id: set(ids) for contact_id, ids in biobank_ids_by_contact.items()},
        {contact_id: set(ids) for contact_id, ids in collection_ids_by_contact.items()},
    )


def extract_email_domain(value: Any) -> str:
    email = cell_text(value).lower()
    if "@" not in email:
        return ""
    return email.split("@", 1)[1]


def build_collection_contact_domain_counts(
    collection_index: dict[str, dict[str, Any]],
    contact_index: dict[str, dict[str, Any]],
) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for collection in collection_index.values():
        contact_value = collection.get("contact")
        if not contact_value:
            continue
        contact_id = contact_value["id"] if isinstance(contact_value, dict) else str(contact_value)
        contact = contact_index.get(contact_id) or {}
        domain = extract_email_domain(contact.get("email"))
        if not domain:
            continue
        biobank_value = collection.get("biobank")
        biobank_id = biobank_value["id"] if isinstance(biobank_value, dict) else str(biobank_value)
        counts[domain][biobank_id] += 1
    return {domain: dict(per_biobank) for domain, per_biobank in counts.items()}


def infer_collection_scope_from_row(
    row: pd.Series,
    candidate_collection_ids: list[str],
    collection_index: dict[str, dict[str, Any]],
) -> tuple[list[str], str]:
    if len(candidate_collection_ids) <= 1:
        return candidate_collection_ids, ""
    survey_context = " ".join(
        filter(
            None,
            [
                cell_text(row.get("Name of Institution")),
                cell_text(row.get("Research field")),
                cell_text(row.get("What field of research does your biobank or biomolecular resource support? (Select all that apply)")),
                cell_text(row.get("What is the origin of samples in your biobank? (Select all that apply)")),
            ],
        )
    )
    normalized_context = normalize_text(survey_context)
    veterinary_signal = any(keyword in normalized_context for keyword in ("animal", "vetsuisse", "veterinary"))
    human_signal = any(keyword in normalized_context for keyword in ("medical", "public health", "clinical", "patient", "human"))
    pathogen_signal = any(keyword in normalized_context for keyword in ("pathogen", "infectious", "microorganism", "microbiology"))

    collections = [collection_index[collection_id] for collection_id in candidate_collection_ids if collection_id in collection_index]
    if not collections:
        return candidate_collection_ids, ""

    if veterinary_signal:
        narrowed = [
            collection["id"]
            for collection in collections
            if "NON_HUMAN" in parse_material_value(collection.get("type"))
            or "vet" in normalize_text(collection.get("name"))
            or "animal" in normalize_text(collection.get("description"))
        ]
        if len(narrowed) == 1:
            return narrowed, "Survey wording indicates veterinary/animal scope; collection scope was narrowed accordingly."

    if pathogen_signal:
        narrowed = [
            collection["id"]
            for collection in collections
            if "PATHOGEN" in parse_material_value(collection.get("materials"))
            or "pathogen" in normalize_text(collection.get("description"))
            or "infectious" in normalize_text(collection.get("description"))
        ]
        if len(narrowed) == 1:
            return narrowed, "Survey wording indicates pathogen/infectious-disease scope; collection scope was narrowed accordingly."

    if human_signal:
        narrowed = []
        for collection in collections:
            collection_types = set(parse_material_value(collection.get("type")))
            collection_materials = set(parse_material_value(collection.get("materials")))
            if "NON_HUMAN" in collection_types:
                continue
            if "PATHOGEN" in collection_materials:
                continue
            narrowed.append(collection["id"])
        if len(narrowed) == 1:
            return narrowed, "Survey wording indicates human/medical scope; collection scope was narrowed accordingly."

    return candidate_collection_ids, ""


def resolve_row(
    row: pd.Series,
    row_index: int,
    directory: Directory,
    biobank_index: dict[str, dict[str, Any]],
    collection_index: dict[str, dict[str, Any]],
    network_index: dict[str, dict[str, Any]],
    contacts_by_email: dict[str, list[dict[str, Any]]],
    biobank_ids_by_contact: dict[str, set[str]],
    collection_ids_by_contact: dict[str, set[str]],
    biobanks_by_normalized_name: dict[str, list[dict[str, Any]]],
    biobanks_by_alias: dict[str, list[dict[str, Any]]],
    biobanks_by_signature: dict[tuple[str, ...], list[dict[str, Any]]],
    collection_contact_domain_counts: dict[str, dict[str, int]],
) -> dict[str, Any]:
    survey_row = row_index + 5
    raw_biobank_id = cell_text(get_row_value(row, "BiobankID in the Directory (if available)"))
    biobank_id = normalize_biobank_id(raw_biobank_id)
    network_id = normalize_network_id(raw_biobank_id)
    collection_ids = [
        normalized_collection_id
        for normalized_collection_id in (
            normalize_collection_id(value)
            for value in split_semicolon_values(
                get_row_value(
                    row,
                    'List of CollectionID in the Directory (if you only represent a part of a biobank; please use ";" as separator in case of more than 1 ID)',
                    "List of CollectionID in the Directory (if you only represent a part of a biobank; please use ';' as separator in case of more than 1 ID)",
                )
            )
        )
        if normalized_collection_id
    ]
    institution_name = cell_text(row.get("Name of Institution"))
    normalized_institution = normalize_text(institution_name)
    institution_signature = normalized_institution_signature(institution_name)
    survey_aliases = institution_aliases(institution_name)
    survey_aliases.update(biobank_id_aliases(raw_biobank_id))
    country = normalize_country(row.get("Country"))
    survey_email = cell_text(row.get("E-Mail address")).lower()
    survey_email_domain = extract_email_domain(row.get("E-Mail address"))
    result = {
        "survey_row": survey_row,
        "institution_name": institution_name,
        "biobank_id_from_survey": raw_biobank_id,
        "collection_ids_from_survey": collection_ids,
        "resolution_status": "missing_from_directory",
        "resolution_reliability": "low",
        "resolution_explanation": "",
        "matched_biobank_ids": [],
        "matched_network_ids": [],
        "matched_collection_ids": [],
        "matched_contact_ids": [],
    }
    explicit_biobank_resolution_note = ""

    if network_id:
        network = network_index.get(network_id)
        if network is not None:
            result["matched_network_ids"] = [network_id]
            result["resolution_status"] = "resolved_by_network_id"
            result["resolution_reliability"] = "high"
            result["resolution_explanation"] = f"Resolved via explicit network ID {network_id}."
            return result
        explicit_biobank_resolution_note = f"Survey network ID {raw_biobank_id} does not exist in schema {directory.getSchema()}."

    if biobank_id:
        if ":collection:" in biobank_id and biobank_id not in collection_ids:
            collection_ids = [normalize_collection_id(biobank_id)] + collection_ids
            biobank_id = ""
        biobank = biobank_index.get(biobank_id) if biobank_id else None
        if biobank is None:
            if raw_biobank_id and not explicit_biobank_resolution_note:
                explicit_biobank_resolution_note = (
                    f"Survey biobank ID {raw_biobank_id} does not exist in schema {directory.getSchema()}."
                )
        else:
            result["matched_biobank_ids"] = [biobank_id]
            result["resolution_status"] = "resolved_by_biobank_id"
            result["resolution_reliability"] = "high"
            if collection_ids:
                existing_collection_ids = []
                missing_collection_ids = []
                for collection_id in collection_ids:
                    collection = collection_index.get(collection_id)
                    if collection is None:
                        missing_collection_ids.append(collection_id)
                        continue
                    existing_collection_ids.append(collection_id)
                result["matched_collection_ids"] = existing_collection_ids
                if missing_collection_ids:
                    result["resolution_explanation"] = (
                        f"Resolved via biobank ID {biobank_id}; some collection IDs are missing in the Directory: {', '.join(missing_collection_ids)}."
                    )
                else:
                    result["resolution_explanation"] = f"Resolved via biobank ID {biobank_id} and explicit collection scope."
            else:
                candidate_collection_ids = get_collections_ids_from_biobank(directory, biobank_id)
                narrowed_collection_ids, narrowing_note = infer_collection_scope_from_row(
                    row,
                    candidate_collection_ids,
                    collection_index,
                )
                result["matched_collection_ids"] = narrowed_collection_ids
                result["resolution_explanation"] = f"Resolved via biobank ID {biobank_id}; collection scope is all collections of the mapped biobank."
                if narrowing_note:
                    result["resolution_explanation"] += " " + narrowing_note
            return result

    if collection_ids:
        existing_collections = []
        parent_biobanks = set()
        for collection_id in collection_ids:
            collection = collection_index.get(collection_id)
            if collection:
                existing_collections.append(collection_id)
                if collection.get("biobank"):
                    biobank_value = collection["biobank"]
                    parent_biobanks.add(biobank_value["id"] if isinstance(biobank_value, dict) else str(biobank_value))
        if existing_collections and len(parent_biobanks) == 1:
            result["matched_collection_ids"] = existing_collections
            result["matched_biobank_ids"] = sorted(parent_biobanks)
            result["resolution_status"] = "resolved_by_collection_ids"
            result["resolution_reliability"] = "high"
            result["resolution_explanation"] = "Resolved via explicit collection IDs."
            return result

    if survey_email:
        exact_contact_matches = contacts_by_email.get(survey_email, [])
        if exact_contact_matches:
            resolved_biobank_ids: set[str] = set()
            resolved_collection_ids: set[str] = set()
            dangling_biobank_ids: set[str] = set()
            result["matched_contact_ids"] = sorted(contact["id"] for contact in exact_contact_matches)
            for contact in exact_contact_matches:
                contact_id = contact["id"]
                for linked_biobank in contact.get("biobanks", []) or []:
                    linked_biobank_id = linked_biobank["id"] if isinstance(linked_biobank, dict) else str(linked_biobank)
                    if linked_biobank_id in biobank_index:
                        resolved_biobank_ids.add(linked_biobank_id)
                    else:
                        dangling_biobank_ids.add(linked_biobank_id)
                for linked_collection in contact.get("collections", []) or []:
                    linked_collection_id = linked_collection["id"] if isinstance(linked_collection, dict) else str(linked_collection)
                    if linked_collection_id in collection_index:
                        resolved_collection_ids.add(linked_collection_id)
                resolved_biobank_ids.update(biobank_ids_by_contact.get(contact_id, set()))
                resolved_collection_ids.update(collection_ids_by_contact.get(contact_id, set()))
            for collection_id in resolved_collection_ids:
                collection = collection_index.get(collection_id)
                if collection and collection.get("biobank"):
                    collection_biobank = collection["biobank"]
                    resolved_biobank_ids.add(
                        collection_biobank["id"] if isinstance(collection_biobank, dict) else str(collection_biobank)
                    )
            if len(resolved_biobank_ids) == 1:
                biobank_id_from_contact = next(iter(resolved_biobank_ids))
                result["matched_biobank_ids"] = [biobank_id_from_contact]
                result["matched_collection_ids"] = (
                    sorted(resolved_collection_ids)
                    if resolved_collection_ids
                    else get_collections_ids_from_biobank(directory, biobank_id_from_contact)
                )
                result["resolution_status"] = "resolved_by_contact_email"
                result["resolution_reliability"] = "high"
                result["resolution_explanation"] = (
                    f"Resolved by exact respondent email match to Directory contact(s) for {biobank_id_from_contact}."
                )
                if explicit_biobank_resolution_note:
                    result["resolution_explanation"] = (
                        explicit_biobank_resolution_note + " " + result["resolution_explanation"]
                    )
                return result
            if dangling_biobank_ids and not resolved_biobank_ids:
                result["resolution_status"] = "manual_review"
                result["resolution_reliability"] = "medium"
                result["resolution_explanation"] = (
                    "Respondent email matches Directory contact(s), but those contacts reference biobank IDs "
                    "that are not present in the current schema snapshot: "
                    + ", ".join(sorted(dangling_biobank_ids))
                    + "."
                )
                if explicit_biobank_resolution_note:
                    result["resolution_explanation"] = (
                        explicit_biobank_resolution_note + " " + result["resolution_explanation"]
                    )
                return result
            if len(resolved_biobank_ids) > 1:
                result["matched_biobank_ids"] = sorted(resolved_biobank_ids)
                result["matched_collection_ids"] = sorted(resolved_collection_ids)
                result["resolution_status"] = "ambiguous"
                result["resolution_reliability"] = "medium"
                result["resolution_explanation"] = (
                    "Respondent email matches Directory contact(s) linked to multiple biobanks; human review is required."
                )
                if explicit_biobank_resolution_note:
                    result["resolution_explanation"] = (
                        explicit_biobank_resolution_note + " " + result["resolution_explanation"]
                    )
                return result

    exact_name_candidates = list(biobanks_by_normalized_name.get(normalized_institution, []))
    if country:
        exact_name_candidates = [candidate for candidate in exact_name_candidates if str(candidate.get("country") or "").upper() == country]
    if len(exact_name_candidates) == 1:
        biobank = exact_name_candidates[0]
        result["matched_biobank_ids"] = [biobank["id"]]
        result["matched_collection_ids"] = get_collections_ids_from_biobank(directory, biobank["id"])
        result["resolution_status"] = "resolved_by_institution_name_certain"
        result["resolution_reliability"] = "medium"
        result["resolution_explanation"] = f"Resolved by unambiguous normalized institution-name match to {biobank['id']}."
        if explicit_biobank_resolution_note:
            result["resolution_explanation"] = explicit_biobank_resolution_note + " " + result["resolution_explanation"]
        return result
    if len(exact_name_candidates) > 1:
        result["matched_biobank_ids"] = sorted(candidate["id"] for candidate in exact_name_candidates)
        result["resolution_status"] = "ambiguous"
        result["resolution_explanation"] = "Multiple biobanks share the same normalized institution name."
        return result

    alias_candidates = match_biobank_alias_candidates(survey_aliases, biobanks_by_alias, country=country)
    if len(alias_candidates) == 1:
        biobank = alias_candidates[0]
        result["matched_biobank_ids"] = [biobank["id"]]
        result["matched_collection_ids"] = get_collections_ids_from_biobank(directory, biobank["id"])
        result["resolution_status"] = "resolved_by_institution_name_certain"
        result["resolution_reliability"] = "medium"
        result["resolution_explanation"] = f"Resolved by institution alias/acronym match to {biobank['id']}."
        if explicit_biobank_resolution_note:
            result["resolution_explanation"] = explicit_biobank_resolution_note + " " + result["resolution_explanation"]
        return result
    if len(alias_candidates) > 1:
        result["matched_biobank_ids"] = sorted(candidate["id"] for candidate in alias_candidates)
        result["resolution_status"] = "ambiguous"
        result["resolution_explanation"] = "Multiple biobanks match the same institution alias or acronym."
        return result

    signature_candidates = list(biobanks_by_signature.get(institution_signature, []))
    if country:
        signature_candidates = [candidate for candidate in signature_candidates if str(candidate.get("country") or "").upper() == country]
    if len(signature_candidates) == 1:
        biobank = signature_candidates[0]
        result["matched_biobank_ids"] = [biobank["id"]]
        result["matched_collection_ids"] = get_collections_ids_from_biobank(directory, biobank["id"])
        result["resolution_status"] = "resolved_by_institution_name_certain"
        result["resolution_reliability"] = "medium"
        result["resolution_explanation"] = f"Resolved by institution-name signature match to {biobank['id']}."
        if explicit_biobank_resolution_note:
            result["resolution_explanation"] = explicit_biobank_resolution_note + " " + result["resolution_explanation"]
        return result
    if len(signature_candidates) > 1:
        result["matched_biobank_ids"] = sorted(candidate["id"] for candidate in signature_candidates)
        result["resolution_status"] = "ambiguous"
        result["resolution_explanation"] = "Multiple biobanks share the same institution-name signature."
        return result

    approximate_candidates = []
    for biobank in directory.getBiobanks():
        if country and str(biobank.get("country") or "").upper() != country:
            continue
        candidate_keys = institution_aliases(biobank.get("name"))
        candidate_keys.update(biobank_id_aliases(biobank.get("id")))
        candidate_signature = normalized_institution_signature(biobank.get("name"))
        score = 0.0
        for survey_key in survey_aliases or {normalized_institution}:
            if not survey_key:
                continue
            for candidate_key in candidate_keys or {normalize_text(biobank.get("name"))}:
                if not candidate_key:
                    continue
                score = max(score, SequenceMatcher(None, survey_key, candidate_key).ratio())
        if (
            score < 0.9
            and institution_signature
            and candidate_signature
            and not set(institution_signature).intersection(candidate_signature)
            and not survey_aliases.intersection(candidate_keys)
        ):
            continue
        domain_bonus = 0.0
        if survey_email_domain:
            domain_counts = collection_contact_domain_counts.get(survey_email_domain, {})
            domain_bonus = min(domain_counts.get(biobank["id"], 0), 3) * 0.03
        score += domain_bonus
        if score >= 0.82:
            approximate_candidates.append((score, biobank))
    approximate_candidates.sort(key=lambda item: item[0], reverse=True)
    if approximate_candidates:
        top_score, top_biobank = approximate_candidates[0]
        second_score = approximate_candidates[1][0] if len(approximate_candidates) > 1 else 0.0
        if top_score >= 0.9 or top_score - second_score >= 0.08:
            result["matched_biobank_ids"] = [top_biobank["id"]]
            result["matched_collection_ids"] = get_collections_ids_from_biobank(directory, top_biobank["id"])
            result["resolution_status"] = "resolved_by_institution_name_approximate"
            result["resolution_reliability"] = "low"
            result["resolution_explanation"] = (
                f"Resolved approximately by institution-name similarity to {top_biobank['id']} (score {top_score:.2f})."
            )
            if explicit_biobank_resolution_note:
                result["resolution_explanation"] = explicit_biobank_resolution_note + " " + result["resolution_explanation"]
            return result
        result["matched_biobank_ids"] = [biobank["id"] for _, biobank in approximate_candidates[:5]]
        result["resolution_status"] = "ambiguous"
        result["resolution_explanation"] = "Multiple approximate institution-name matches require human review."
        return result

    result["resolution_status"] = "missing_from_directory"
    result["resolution_explanation"] = "No exact-ID, contact-email, or institution-name-based match was found in the Directory."
    if explicit_biobank_resolution_note:
        result["resolution_explanation"] = explicit_biobank_resolution_note + " " + result["resolution_explanation"]
    return result


def make_finding(
    *,
    row_resolution: dict[str, Any],
    mapping_id: str,
    entity_type: str,
    entity_id: str,
    status: str,
    survey_value: Any,
    directory_value: Any,
    relation_type: str,
    reliability: str,
    why_relevant: str,
    explanation: str,
    survey_fields: list[str] | None = None,
    strategic_objectives: list[str] | None = None,
    directory_fields: list[str] | None = None,
    comparison_description: str = "",
    proposed_update: dict[str, Any] | None = None,
    export_update_plan: bool = False,
) -> dict[str, Any]:
    survey_row = row_resolution["survey_row"]
    return {
        "finding_id": f"{mapping_id}:{entity_type}:{entity_id}:row{survey_row}",
        "survey_row": survey_row,
        "mapping_id": mapping_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "resolution_status": row_resolution["resolution_status"],
        "status": status,
        "survey_value": survey_value,
        "directory_value": directory_value,
        "relation_type": relation_type,
        "reliability": reliability,
        "why_relevant": why_relevant,
        "explanation": explanation,
        "survey_fields": list(survey_fields or []),
        "directory_fields": list(directory_fields or []),
        "comparison_description": comparison_description,
        "strategic_objectives": list(strategic_objectives or []),
        "manual_notes": "",
        "export_update_plan": export_update_plan,
        "proposed_update": proposed_update,
    }


def build_update(
    *,
    mapping_id: str,
    module: str,
    entity_type: str,
    entity_id: str,
    field: str,
    mode: str,
    confidence: str,
    current_value: Any,
    proposed_value: Any,
    explanation: str,
    rationale: str,
    source_check_id: str,
) -> dict[str, Any]:
    proposal = EntityFixProposal(
        update_id=mapping_id,
        module=module,
        entity_type=entity_type,
        entity_id=entity_id,
        field=field,
        mode=mode,
        confidence=confidence,
        current_value_at_export=current_value,
        expected_current_value=current_value,
        proposed_value=proposed_value,
        human_explanation=explanation,
        rationale=rationale,
        source_check_ids=[source_check_id],
        source_warning_messages=[],
        source_warning_actions=[],
    )
    proposal.finalize_checksum()
    return proposal.to_dict()


def index_question_objectives(objectives_mapping: dict[str, Any]) -> dict[str, list[str]]:
    indexed: dict[str, list[str]] = {}
    for item in objectives_mapping.get("question_mappings", []):
        survey_field = str(item.get("survey_field") or "").strip()
        if not survey_field:
            continue
        indexed[survey_field] = list(item.get("strategic_objectives", []))
    return indexed


def objectives_for_fields(question_objectives: dict[str, list[str]], survey_fields: list[str]) -> list[str]:
    result: set[str] = set()
    for field in survey_fields:
        result.update(question_objectives.get(field, []))
    return sorted(result)


def analyze_survey(args: argparse.Namespace) -> dict[str, Any]:
    mapping = load_mapping(args.mapping_file)
    objectives_mapping = load_objectives_mapping(args.objectives_mapping_file)
    question_objectives = index_question_objectives(objectives_mapping)
    survey = load_survey(mapping, args.survey_file)
    directory = build_directory(args)

    biobank_index = {biobank["id"]: biobank for biobank in directory.getBiobanks()}
    collection_index = {collection["id"]: collection for collection in directory.getCollections()}
    contact_index = {contact["id"]: contact for contact in directory.getContacts()}
    network_index = {network["id"]: network for network in directory.getNetworks()}
    contacts_by_email: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for contact in contact_index.values():
        email = cell_text(contact.get("email")).lower()
        if email:
            contacts_by_email[email].append(contact)
    biobank_ids_by_contact, collection_ids_by_contact = build_contact_usage_indexes(biobank_index, collection_index)
    biobanks_by_normalized_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    biobanks_by_alias: dict[str, list[dict[str, Any]]] = defaultdict(list)
    biobanks_by_signature: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for biobank in biobank_index.values():
        biobanks_by_normalized_name[normalize_text(biobank.get("name"))].append(biobank)
        for alias in institution_aliases(biobank.get("name")).union(biobank_id_aliases(biobank.get("id"))):
            biobanks_by_alias[alias].append(biobank)
        biobanks_by_signature[normalized_institution_signature(biobank.get("name"))].append(biobank)
    collection_contact_domain_counts = build_collection_contact_domain_counts(collection_index, contact_index)

    row_resolutions = []
    findings = []
    for row_index, row in survey.iterrows():
        if all(
            value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == ""
            for value in row.tolist()
        ):
            continue

        resolution = resolve_row(
            row,
            int(row_index),
            directory,
            biobank_index,
            collection_index,
            network_index,
            contacts_by_email,
            biobank_ids_by_contact,
            collection_ids_by_contact,
            biobanks_by_normalized_name,
            biobanks_by_alias,
            biobanks_by_signature,
            collection_contact_domain_counts,
        )
        row_resolutions.append(resolution)
        if resolution["resolution_status"] in {"missing_from_directory", "ambiguous", "manual_review"}:
            survey_country = normalize_country(row.get("Country"))
            entity_type = "NETWORK" if resolution.get("matched_network_ids") else "BIOBANK"
            entity_id = (
                (resolution.get("matched_network_ids") or [None])[0]
                or resolution["biobank_id_from_survey"]
                or resolution["institution_name"]
                or f"row-{resolution['survey_row']}"
            )
            findings.append(
                make_finding(
                    row_resolution=resolution,
                    mapping_id="row_resolution",
                    entity_type=entity_type,
                    entity_id=entity_id,
                    status=resolution["resolution_status"],
                    survey_value={
                        "institution_name": resolution["institution_name"],
                        "biobank_id": resolution["biobank_id_from_survey"],
                        "collection_ids": resolution["collection_ids_from_survey"],
                        "country": survey_country,
                    },
                    directory_value={
                        "matched_biobank_ids": resolution["matched_biobank_ids"],
                        "matched_network_ids": resolution.get("matched_network_ids", []),
                        "matched_contact_ids": resolution.get("matched_contact_ids", []),
                    },
                    relation_type="entity_resolution",
                    reliability=resolution["resolution_reliability"],
                    why_relevant="The survey row must be mapped to a Directory scope before any consistency analysis is meaningful.",
                    explanation=resolution["resolution_explanation"],
                    survey_fields=[
                        "BiobankID in the Directory (if available)",
                        "List of CollectionID in the Directory (if you only represent a part of a biobank; please use \";\" as separator in case of more than 1 ID)",
                        "Name of Institution",
                        "Country",
                    ],
                    strategic_objectives=[],
                )
            )
            continue

        if resolution["resolution_status"] == "resolved_by_network_id":
            continue

        if len(resolution.get("matched_biobank_ids", [])) == 1:
            biobank_collection_ids = get_collections_ids_from_biobank(directory, resolution["matched_biobank_ids"][0])
            resolution["collection_scope_display"] = summarize_collection_scope(
                resolution.get("matched_collection_ids", []),
                biobank_collection_ids,
            )

        biobank_id = resolution["matched_biobank_ids"][0]
        biobank = biobank_index.get(biobank_id)
        if biobank is None:
            continue
        scope = {
            "biobank_id": biobank_id,
            "collection_ids": resolution["matched_collection_ids"],
        }
        aggregate = aggregate_scope(scope, collection_index)
        contact = choose_contact(
            scope,
            biobank_index=biobank_index,
            collection_index=collection_index,
            contact_index=contact_index,
        )

        survey_country = normalize_country(row.get("Country"))
        findings.append(
            make_finding(
                row_resolution=resolution,
                mapping_id="geo.country",
                entity_type="BIOBANK",
                entity_id=biobank_id,
                status="consistent" if survey_country == str(biobank.get("country") or "").upper() else "inconsistent",
                survey_value=survey_country,
                directory_value=str(biobank.get("country") or "").upper(),
                relation_type="exact_field",
                reliability="high",
                why_relevant="Country is a direct biobank-level comparison and also validates the overall row-to-biobank mapping.",
                explanation=(
                    "Survey country matches Directory country."
                    if survey_country == str(biobank.get("country") or "").upper()
                    else "Survey country differs from Directory country."
                ),
                survey_fields=["Country"],
                strategic_objectives=objectives_for_fields(question_objectives, ["Country"]),
            )
        )

        findings.append(
            make_finding(
                row_resolution=resolution,
                mapping_id="biobank.name",
                entity_type="BIOBANK",
                entity_id=biobank_id,
                status="consistent" if normalize_text(row.get("Name of Institution")) == normalize_text(biobank.get("name")) else "manual_review",
                survey_value=row.get("Name of Institution"),
                directory_value=biobank.get("name"),
                relation_type="normalized_text",
                reliability="medium",
                why_relevant="Institution naming is one of the core mapping checks between the survey respondent and the Directory biobank.",
                explanation=(
                    "Institution name matches after normalization."
                    if normalize_text(row.get("Name of Institution")) == normalize_text(biobank.get("name"))
                    else "Institution name differs after normalization."
                ),
                survey_fields=["Name of Institution"],
                strategic_objectives=objectives_for_fields(question_objectives, ["Name of Institution"]),
            )
        )

        if contact is not None:
            survey_email = cell_text(row.get("E-Mail address")).lower()
            if survey_email:
                findings.append(
                    make_finding(
                        row_resolution=resolution,
                        mapping_id="contact.email",
                        entity_type="CONTACT",
                        entity_id=contact["id"],
                        status="consistent" if survey_email == str(contact.get("email") or "").strip().lower() else "manual_review",
                        survey_value=survey_email,
                        directory_value=str(contact.get("email") or "").strip().lower(),
                        relation_type="exact_field",
                        reliability="high",
                        why_relevant="Respondent email is the strongest contact-level comparison once the row is resolved to a Directory contact.",
                        explanation=(
                            "Respondent email matches Directory contact email."
                            if survey_email == str(contact.get("email") or "").strip().lower()
                            else "Respondent email differs from Directory contact email."
                        ),
                        survey_fields=["E-Mail address"],
                        strategic_objectives=objectives_for_fields(question_objectives, ["E-Mail address"]),
                    )
                )

        interest_value = str(
            row.get("Are you interested in promoting your biobank resources to new partners?")
            or row.get("Are you interested in promoting your biobank resources to new research or industry partners?")
            or ""
        ).strip()
        if interest_value:
            expected_non_profit = None
            expected_commercial = None
            confidence = "uncertain"
            if interest_value == "Yes - academic":
                expected_non_profit = True
            elif interest_value == "Yes - industrial and academic":
                expected_non_profit = True
                expected_commercial = True
            elif interest_value == "Yes":
                expected_non_profit = True
            survey_profile = {
                "interest": interest_value,
                "expected_non_profit": expected_non_profit,
                "expected_commercial": expected_commercial,
            }
            directory_profile = {
                "collaboration_non_for_profit": biobank.get("collaboration_non_for_profit"),
                "collaboration_commercial": biobank.get("collaboration_commercial"),
            }
            status = "manual_review"
            proposed_update = None
            export_update_plan = False
            explanation = "Survey partner-promotion answer only plausibly maps to Directory collaboration flags."
            if expected_non_profit is True and biobank.get("collaboration_non_for_profit") not in (True, "true", "True", 1):
                status = "inconsistent"
                explanation = "Survey partner-promotion answer differs from Directory collaboration flags."
                proposed_update = build_update(
                    mapping_id="survey_so2.biobank.collaboration_non_profit",
                    module="SO2",
                    entity_type="BIOBANK",
                    entity_id=biobank_id,
                    field="collaboration_non_for_profit",
                    mode="set",
                    confidence=confidence,
                    current_value=biobank.get("collaboration_non_for_profit"),
                    proposed_value=True,
                    explanation="Enable non-profit collaboration on the biobank because the SO2 survey states interest in promoting the biobank to academic partners.",
                    rationale="This is a plausible survey-to-Directory alignment, but the survey question is about willingness to promote rather than a strict legal access condition.",
                    source_check_id="SO2:PromotionInterest",
                )
                export_update_plan = True
            findings.append(
                make_finding(
                    row_resolution=resolution,
                    mapping_id="promotion.partnership_interest",
                    entity_type="BIOBANK",
                    entity_id=biobank_id,
                    status=status,
                    survey_value=survey_profile,
                    directory_value=directory_profile,
                    relation_type="derived_policy_mapping",
                    reliability="low",
                    why_relevant="The survey captures willingness to promote the biobank to academic and/or industry partners, which is directionally related to Directory collaboration flags.",
                    explanation=explanation,
                    survey_fields=[
                        "Are you interested in promoting your biobank resources to new partners?",
                        "Are you interested in promoting your biobank resources to new research or industry partners?",
                    ],
                    strategic_objectives=objectives_for_fields(
                        question_objectives,
                        [
                            "Are you interested in promoting your biobank resources to new partners?",
                            "Are you interested in promoting your biobank resources to new research or industry partners?",
                        ],
                    ),
                    proposed_update=proposed_update,
                    export_update_plan=export_update_plan,
                )
            )

            if len(scope["collection_ids"]) == 1:
                collection_id = scope["collection_ids"][0]
                collection = collection_index.get(collection_id)
                if collection is not None:
                    collection_duos = normalize_duo_term_ids(collection.get("data_use") or [])
                    collection_commercial = bool(
                        collection.get("collaboration_commercial") in (True, "true", "True", 1)
                        or biobank.get("collaboration_commercial") in (True, "true", "True", 1)
                    )
                    expected_duo = None
                    duo_status = "manual_review"
                    duo_explanation = "Survey partner-promotion answer does not imply a clear DUO restriction for the mapped collection."
                    duo_proposed_update = None
                    duo_export_update_plan = False
                    if interest_value == "Yes - academic" and not collection_commercial:
                        expected_duo = "DUO:0000018"
                        if expected_duo in collection_duos:
                            duo_status = "consistent"
                            duo_explanation = "Academic-only promotion answer is already reflected by the non-commercial DUO restriction."
                        else:
                            duo_status = "inconsistent"
                            duo_explanation = "Academic-only promotion answer suggests a non-commercial DUO restriction is missing."
                            duo_proposed_update = build_update(
                                mapping_id="survey_so2.collection.duo_non_profit_non_commercial_from_promotion_interest",
                                module="SO2",
                                entity_type="COLLECTION",
                                entity_id=collection_id,
                                field="data_use",
                                mode="append",
                                confidence="uncertain",
                                current_value=collection.get("data_use"),
                                proposed_value=[expected_duo],
                                explanation="Add DUO:0000018 (not for profit, non commercial use only) because the SO2 survey says the mapped collection should be promoted only to academic partners.",
                                rationale="This reuses the same DUO interpretation as the AccessPolicies checks, but the survey answer is still only a directional policy signal and needs curator confirmation.",
                                source_check_id="SO2:PromotionInterestDuo",
                            )
                            duo_export_update_plan = True
                    findings.append(
                        make_finding(
                            row_resolution=resolution,
                            mapping_id="promotion.partnership_interest.duo",
                            entity_type="COLLECTION",
                            entity_id=collection_id,
                            status=duo_status,
                            survey_value={"interest": interest_value, "expected_duo": expected_duo},
                            directory_value={
                                "data_use": collection_duos,
                                "collaboration_commercial": collection.get("collaboration_commercial", biobank.get("collaboration_commercial")),
                            },
                            relation_type="derived_policy_mapping",
                            reliability="low",
                            why_relevant="Academic-only survey promotion answers can also imply a collection-level DUO non-commercial restriction when the mapped collection scope is unambiguous.",
                            explanation=duo_explanation,
                            survey_fields=[
                                "Are you interested in promoting your biobank resources to new partners?",
                                "Are you interested in promoting your biobank resources to new research or industry partners?",
                            ],
                            strategic_objectives=objectives_for_fields(
                                question_objectives,
                                [
                                    "Are you interested in promoting your biobank resources to new partners?",
                                    "Are you interested in promoting your biobank resources to new research or industry partners?",
                                ],
                            ),
                            proposed_update=duo_proposed_update,
                            export_update_plan=duo_export_update_plan,
                        )
                    )

        survey_sample_types = set(split_semicolon_values(row.get("Which types of samples do you manage?")))
        survey_sample_type_notes = set(split_semicolon_values(row.get("Sample types")))
        value_map = mapping.get("value_maps", {}).get("sample_types_to_materials", {})
        expected_materials = set()
        for sample_type in survey_sample_types:
            expected_materials.update(value_map.get(sample_type, []))
        scope_materials = set(aggregate["materials"])
        missing_materials = sorted(expected_materials - scope_materials)
        if survey_sample_types or survey_sample_type_notes:
            proposed_update = None
            export_update_plan = False
            if len(scope["collection_ids"]) == 1 and missing_materials:
                collection_id = scope["collection_ids"][0]
                collection = collection_index.get(collection_id)
                proposed_update = build_update(
                    mapping_id="survey_so2.collection.materials_from_sample_types",
                    module="SO2",
                    entity_type="COLLECTION",
                    entity_id=collection_id,
                    field="materials",
                    mode="append",
                    confidence="uncertain",
                    current_value=collection.get("materials"),
                    proposed_value=missing_materials,
                    explanation="Append missing collection materials based on the SO2 survey sample-type answers.",
                    rationale="This is only safe enough to propose automatically when the survey row maps to exactly one collection. Multi-collection survey scope remains aggregate-only.",
                    source_check_id="SO2:SampleTypes",
                )
                export_update_plan = True
            findings.append(
                make_finding(
                    row_resolution=resolution,
                    mapping_id="sample_types.materials",
                    entity_type="BIOBANK" if len(scope["collection_ids"]) != 1 else "COLLECTION",
                    entity_id=biobank_id if len(scope["collection_ids"]) != 1 else scope["collection_ids"][0],
                    status="consistent" if not missing_materials else "inconsistent",
                    survey_value={
                        "selected_sample_types": sorted(survey_sample_types),
                        "free_text_sample_types": sorted(survey_sample_type_notes),
                        "expected_materials": sorted(expected_materials),
                    },
                    directory_value={"observed_materials": sorted(scope_materials)},
                    relation_type="controlled_vocabulary_mapping",
                    reliability="medium",
                    why_relevant="Survey sample-type selections are the clearest structured source for comparing Directory collection materials.",
                    explanation=(
                        "Material types are consistent between survey and Directory scope."
                        if not missing_materials
                        else "Inconsistent material types between survey and Directory collection."
                    ),
                    survey_fields=["Which types of samples do you manage?", "Sample types"],
                    strategic_objectives=objectives_for_fields(question_objectives, ["Which types of samples do you manage?", "Sample types"]),
                    proposed_update=proposed_update,
                    export_update_plan=export_update_plan,
                )
            )

        wsi_answer = str(row.get("Does your biobank provide access to whole-slide image (WSI) histopathology datasets? E.g., disease-focused cohorts with clinical and/or molecular annotations or normal-tissue reference histology across multiple organs from non-diseased donors?") or "").strip()
        wsi_info = str(row.get("You can provide more information about available digital pathology imaging data here (e.g., focus of the collections, more details on modalities):") or "").strip()
        if wsi_answer:
            wants_wsi = wsi_answer.startswith("Yes")
            status = "consistent"
            explanation = "Survey-reported WSI availability is reflected by generic imaging metadata or text."
            proposed_update = None
            export_update_plan = False
            if wants_wsi and not aggregate["has_image_support"] and not aggregate["has_wsi_hint"]:
                status = "missing_in_directory"
                explanation = "Survey-reported WSI availability is not reflected by generic imaging metadata or text."
                if len(scope["collection_ids"]) == 1:
                    collection_id = scope["collection_ids"][0]
                    collection = collection_index.get(collection_id)
                    current_types = parse_material_value(collection.get("type"))
                    current_categories = parse_material_value(collection.get("data_categories"))
                    if "IMAGE" not in current_types:
                        proposed_update = build_update(
                            mapping_id="survey_so2.collection.image_type_from_wsi",
                            module="SO2",
                            entity_type="COLLECTION",
                            entity_id=collection_id,
                            field="type",
                            mode="append",
                            confidence="uncertain",
                            current_value=collection.get("type"),
                            proposed_value=["IMAGE"],
                            explanation="Add IMAGE collection type because the SO2 survey reports WSI availability for the mapped collection scope.",
                            rationale="The Directory has no WSI-specific field, so the safest structured alignment is the generic IMAGE collection type, and only when the survey row maps to exactly one collection.",
                            source_check_id="SO2:WSIPresence",
                        )
                        export_update_plan = True
                    elif "IMAGING_DATA" not in current_categories:
                        proposed_update = build_update(
                            mapping_id="survey_so2.collection.imaging_data_from_wsi",
                            module="SO2",
                            entity_type="COLLECTION",
                            entity_id=collection_id,
                            field="data_categories",
                            mode="append",
                            confidence="uncertain",
                            current_value=collection.get("data_categories"),
                            proposed_value=["IMAGING_DATA"],
                            explanation="Add IMAGING_DATA to the collection because the SO2 survey reports WSI availability for the mapped collection scope.",
                            rationale="The survey provides only generic WSI presence; no WSI-specific structured Directory field exists yet.",
                            source_check_id="SO2:WSIPresence",
                        )
                        export_update_plan = True
            findings.append(
                make_finding(
                    row_resolution=resolution,
                    mapping_id="imaging.wsi_presence",
                    entity_type="BIOBANK" if len(scope["collection_ids"]) != 1 else "COLLECTION",
                    entity_id=biobank_id if len(scope["collection_ids"]) != 1 else scope["collection_ids"][0],
                    status=status,
                    survey_value={"answer": wsi_answer, "details": wsi_info},
                    directory_value={
                        "has_image_support": aggregate["has_image_support"],
                        "has_wsi_hint": aggregate["has_wsi_hint"],
                        "types": aggregate["types"],
                        "data_categories": aggregate["data_categories"],
                        "imaging_modalities": aggregate["imaging_modalities"],
                    },
                    relation_type="derived_presence_and_text_support",
                    reliability="medium",
                    why_relevant="WSI availability can currently only be compared through generic imaging attributes and free text in the Directory.",
                    explanation=explanation,
                    survey_fields=[
                        "Does your biobank provide access to whole-slide image (WSI) histopathology datasets? E.g., disease-focused cohorts with clinical and/or molecular annotations or normal-tissue reference histology across multiple organs from non-diseased donors?",
                        "You can provide more information about available digital pathology imaging data here (e.g., focus of the collections, more details on modalities):",
                    ],
                    strategic_objectives=objectives_for_fields(
                        question_objectives,
                        [
                            "Does your biobank provide access to whole-slide image (WSI) histopathology datasets? E.g., disease-focused cohorts with clinical and/or molecular annotations or normal-tissue reference histology across multiple organs from non-diseased donors?",
                            "You can provide more information about available digital pathology imaging data here (e.g., focus of the collections, more details on modalities):",
                        ],
                    ),
                    proposed_update=proposed_update,
                    export_update_plan=export_update_plan,
                )
            )

    summary = {
        "survey_rows": len(row_resolutions),
        "resolved_rows": sum(1 for item in row_resolutions if item["resolution_status"].startswith("resolved_")),
        "missing_rows": sum(1 for item in row_resolutions if item["resolution_status"] == "missing_from_directory"),
        "ambiguous_rows": sum(1 for item in row_resolutions if item["resolution_status"] == "ambiguous"),
        "findings_by_status": dict(sorted((status, sum(1 for finding in findings if finding["status"] == status)) for status in sorted({finding["status"] for finding in findings}))),
        "proposed_update_findings": sum(1 for finding in findings if finding.get("proposed_update")),
    }
    return {
        "report_metadata": {
            "tool": "survey-so2-directory.py",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "directory_schema": directory.getSchema(),
        },
        "survey_metadata": {
            "survey_file": str(args.survey_file),
            "mapping_file": str(args.mapping_file),
            "objectives_mapping_file": str(args.objectives_mapping_file),
        },
        "strategic_objectives": objectives_mapping.get("strategic_objectives", {}),
        "row_resolutions": row_resolutions,
        "findings": findings,
        "summary": summary,
    }


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def build_biobank_summary(report: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    findings_by_row: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for finding in report.get("findings", []):
        findings_by_row[int(finding["survey_row"])].append(finding)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for resolution in report.get("row_resolutions", []):
        if not str(resolution.get("resolution_status", "")).startswith("resolved_"):
            continue
        matched_biobank_ids = resolution.get("matched_biobank_ids", [])
        if not matched_biobank_ids:
            continue
        for biobank_id in matched_biobank_ids:
            grouped[biobank_id].append(
                {
                    "survey_row": int(resolution["survey_row"]),
                    "institution_name": resolution.get("institution_name", ""),
                    "resolution_status": resolution.get("resolution_status", ""),
                    "resolution_reliability": resolution.get("resolution_reliability", ""),
                    "resolution_explanation": resolution.get("resolution_explanation", ""),
                    "matched_collection_ids": list(resolution.get("matched_collection_ids", [])),
                    "collection_scope_display": resolution.get("collection_scope_display", ""),
                    "findings": sorted(
                        findings_by_row.get(int(resolution["survey_row"]), []),
                        key=lambda item: (str(item.get("status", "")), str(item.get("mapping_id", "")), str(item.get("entity_id", ""))),
                    ),
                }
            )
    for biobank_id in grouped:
        grouped[biobank_id].sort(key=lambda item: item["survey_row"])
    return dict(sorted(grouped.items()))


def build_objective_summary(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    objective_metadata = report.get("strategic_objectives", {})
    summary: dict[str, dict[str, Any]] = {}
    for objective_id, metadata in objective_metadata.items():
        summary[objective_id] = {
            "title": metadata.get("title", objective_id),
            "description": metadata.get("description", ""),
            "findings": [],
            "biobanks": defaultdict(list),
        }
    for finding in report.get("findings", []):
        for objective_id in finding.get("strategic_objectives", []):
            if objective_id not in summary:
                summary[objective_id] = {
                    "title": objective_id,
                    "description": "",
                    "findings": [],
                    "biobanks": defaultdict(list),
                }
            summary[objective_id]["findings"].append(finding)
            biobank_key = "<unresolved>"
            entity_id = str(finding.get("entity_id") or "")
            if finding.get("entity_type") == "BIOBANK":
                biobank_key = entity_id
            else:
                row_biobanks = []
                for resolution in report.get("row_resolutions", []):
                    if int(resolution.get("survey_row", -1)) == int(finding.get("survey_row", -2)):
                        row_biobanks = list(resolution.get("matched_biobank_ids", []))
                        break
                if row_biobanks:
                    biobank_key = row_biobanks[0]
            summary[objective_id]["biobanks"][biobank_key].append(finding)
    return summary


def display_entity_label(finding: dict[str, Any]) -> str:
    entity_label = f"{finding['entity_type']} {finding['entity_id']}"
    if str(finding.get("status", "")) == "missing_from_directory":
        survey_value = finding.get("survey_value")
        if isinstance(survey_value, dict):
            country = cell_text(survey_value.get("country"))
            if country:
                return f"({country}) {entity_label}"
    return entity_label


def render_entity_label_latex(label: str) -> str:
    match = re.fullmatch(r"(\([A-Z]{2}\)\s+)?(BIOBANK|COLLECTION|CONTACT|NETWORK)\s+(.+)", label)
    if not match:
        return escape_report_value(label)
    country_prefix = match.group(1) or ""
    entity_type = match.group(2)
    entity_id = match.group(3)
    prefix = f"{country_prefix}{entity_type} "
    return escape_latex(prefix) + escape_latex_breakable_entity(entity_id)


def render_tex(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    findings = report.get("findings", [])
    grouped = defaultdict(list)
    for finding in findings:
        grouped[finding["status"]].append(finding)
    biobank_summary = build_biobank_summary(report)
    objective_summary = build_objective_summary(report)
    appendix_entries = build_appendix_entries(report)
    lines = [
        r"\documentclass[11pt,a4paper]{article}",
        r"\usepackage{fontspec}",
        r"\usepackage[a4paper,margin=2.3cm]{geometry}",
        r"\usepackage{array}",
        r"\usepackage{longtable}",
        r"\usepackage{booktabs}",
        r"\usepackage[table]{xcolor}",
        r"\usepackage{hyperref}",
        r"\usepackage{xurl}",
        r"\setmainfont{DejaVu Serif}",
        r"\urlstyle{same}",
        r"\definecolor{soGreen}{HTML}{1F6F3F}",
        r"\definecolor{soRed}{HTML}{9E2A2B}",
        r"\definecolor{soOrange}{HTML}{B26A00}",
        r"\definecolor{soBlue}{HTML}{1D4E89}",
        r"\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}",
        r"\setcounter{tocdepth}{2}",
        r"\title{BBMRI-ERIC SO2 Survey vs Directory Report}",
        r"\date{" + escape_latex(report["report_metadata"]["generated_at"]) + "}",
        r"\begin{document}",
        r"\maketitle",
        r"\tableofcontents",
        r"\clearpage",
        r"\section{Summary}",
        r"\begin{itemize}",
        rf"\item Survey rows analyzed: {summary.get('survey_rows', 0)}",
        rf"\item Resolved rows: {summary.get('resolved_rows', 0)}",
        rf"\item Missing-from-Directory rows: {summary.get('missing_rows', 0)}",
        rf"\item Ambiguous rows: {summary.get('ambiguous_rows', 0)}",
        rf"\item Findings with proposed updates: {summary.get('proposed_update_findings', 0)}",
        r"\end{itemize}",
    ]
    if biobank_summary:
        lines.append(r"\section{Biobank-Oriented Summary}")
        lines.append(
            "This section regroups resolved survey responses by mapped Directory biobank. "
            "If the same biobank submitted multiple survey answers, each answer is summarized separately."
        )
        for biobank_id, survey_answers in biobank_summary.items():
            row_count = len(survey_answers)
            lines.append(
                r"\subsection{"
                + escape_latex_breakable_entity(biobank_id)
                + escape_latex(f" ({row_count} survey answer{'s' if row_count != 1 else ''})")
                + "}"
            )
            for answer in survey_answers:
                lines.append(
                    r"\subsubsection*{"
                    + escape_latex_with_inline_breaks(
                        f"Survey row {answer['survey_row']}: {answer['institution_name'] or '<unnamed respondent>'}"
                    )
                    + "}"
                )
                lines.append(
                    escape_latex_with_inline_breaks(
                        f"Resolution: {answer['resolution_status']} ({answer['resolution_reliability']}). {answer['resolution_explanation']}"
                    )
                    + r"\\"
                )
                if answer["matched_collection_ids"]:
                    collection_scope_display = answer.get(
                        "collection_scope_display",
                        ", ".join(answer["matched_collection_ids"]),
                    )
                    lines.append(
                        escape_latex_with_inline_breaks(
                            "Mapped collections: " + collection_scope_display
                        )
                        + r"\\"
                    )
                lines.append(r"\begin{itemize}")
                if answer["findings"]:
                    for finding in answer["findings"]:
                        entity_label = f"{finding['entity_type']} {finding['entity_id']}"
                        update_suffix = " [proposed update]" if finding.get("proposed_update") else ""
                        lines.append(
                            r"\item "
                            + colored_status_text(str(finding["status"]))
                            + escape_latex(": ")
                            + finding_link(str(finding["mapping_id"]))
                            + escape_latex(" -> ")
                            + render_entity_label_latex(entity_label)
                            + escape_latex(". ")
                            + escape_report_value(
                                f"{format_finding_result(finding, concise_consistent=True)}{update_suffix}"
                            )
                        )
                else:
                    lines.append(r"\item No findings were recorded for this survey row.")
                lines.append(r"\end{itemize}")
    if objective_summary:
        lines.append(r"\section{Strategic-Objective Summary}")
        lines.append(
            "This section aggregates findings by BBMRI SO2 strategic objective and then regroups the same findings by biobank within each objective."
        )
        for objective_id in sorted(objective_summary):
            objective = objective_summary[objective_id]
            objective_findings = objective["findings"]
            status_counts = defaultdict(int)
            survey_rows = set()
            for finding in objective_findings:
                status_counts[str(finding.get("status", ""))] += 1
                survey_rows.add(int(finding.get("survey_row", -1)))
            title = objective.get("title", objective_id)
            lines.append(r"\subsection{" + escape_latex(f"{objective_id} - {title}") + "}")
            if objective.get("description"):
                lines.append(escape_latex(objective["description"]))
            lines.append(r"\begin{itemize}")
            lines.append(r"\item " + escape_latex(f"Findings: {len(objective_findings)}"))
            lines.append(r"\item " + escape_latex(f"Survey responses represented: {len(survey_rows)}"))
            lines.append(r"\item " + escape_latex(f"Biobanks represented: {len(objective['biobanks'])}"))
            status_summary = ", ".join(f"{status}={count}" for status, count in sorted(status_counts.items())) or "none"
            lines.append(r"\item " + escape_latex(f"Statuses: {status_summary}"))
            lines.append(r"\end{itemize}")
            if objective_findings:
                lines.append(r"\begin{longtable}{L{1.5cm}L{3.2cm}L{3.2cm}L{6.5cm}}")
                lines.append(r"\toprule Row & Mapping & Entity & Explanation \\ \midrule")
                for finding in sorted(
                    objective_findings,
                    key=lambda item: (int(item.get("survey_row", 0)), str(item.get("mapping_id", "")), str(item.get("entity_id", ""))),
                ):
                    entity_label = display_entity_label(finding)
                    lines.append(
                        f"{escape_latex(finding['survey_row'])} & "
                        f"{finding_link(str(finding['mapping_id']))} & "
                        f"{render_entity_label_latex(entity_label)} & "
                        f"{escape_report_value(format_finding_result(finding, concise_consistent=True))} \\\\"
                    )
                lines.append(r"\bottomrule")
                lines.append(r"\end{longtable}")
            else:
                lines.append("No findings were mapped to this strategic objective in the current report.")
            lines.append(r"\subsubsection*{Per biobank}")
            if objective["biobanks"]:
                for biobank_id in sorted(objective["biobanks"]):
                    lines.append(r"\paragraph{}" + escape_latex_breakable_entity(biobank_id) + r"\\")
                    lines.append(r"\begin{itemize}")
                    for finding in sorted(
                        objective["biobanks"][biobank_id],
                        key=lambda item: (int(item.get("survey_row", 0)), str(item.get("mapping_id", "")), str(item.get("entity_id", ""))),
                    ):
                        lines.append(
                            r"\item "
                            + escape_latex(
                                f"Row {finding['survey_row']}: "
                            )
                            + colored_status_text(str(finding["status"]))
                            + escape_latex(" / ")
                            + finding_link(str(finding["mapping_id"]))
                            + escape_latex(" / ")
                            + render_entity_label_latex(display_entity_label(finding))
                            + escape_latex(
                                " / "
                            )
                            + escape_report_value(format_finding_result(finding, concise_consistent=True))
                        )
                    lines.append(r"\end{itemize}")
            else:
                lines.append("No biobank-level grouping is available because this objective currently has no mapped findings.")
    statuses_to_render = ordered_statuses(
        list(set(grouped.keys()) | STABLE_STATUS_SECTIONS)
    ) if grouped else []
    if statuses_to_render:
        lines.append(r"\section{Findings by Status}")
    for status in statuses_to_render:
        lines.append(r"\subsection{" + colored_status_text(status) + "}")
        intro = STATUS_SECTION_INTROS.get(str(status))
        if intro:
            lines.append(escape_latex_with_inline_breaks(intro))
        status_findings = grouped.get(status, [])
        if not status_findings:
            lines.append("No findings with this status in the current report.")
            continue
        lines.append(r"\begin{longtable}{L{1.5cm}L{3.2cm}L{3.2cm}L{6.5cm}}")
        lines.append(r"\toprule Row & Mapping & Entity & Explanation \\ \midrule")
        for finding in status_findings:
            entity_label = display_entity_label(finding)
            lines.append(
                f"{escape_latex(finding['survey_row'])} & "
                f"{finding_link(str(finding['mapping_id']))} & "
                f"{render_entity_label_latex(entity_label)} & "
                f"{escape_report_value(format_finding_result(finding, concise_consistent=True))} \\\\"
            )
        lines.append(r"\bottomrule")
        lines.append(r"\end{longtable}")
    if appendix_entries:
        lines.append(r"\appendix")
        lines.append(r"\section{Finding-Type Reference}")
        lines.append(
            "Each finding type is documented here once. Links in the main report point to these appendix entries."
        )
        for mapping_id, entry in appendix_entries.items():
            label = latex_label(f"appendix-{mapping_id}")
            lines.append(r"\subsection{" + escape_latex(mapping_id) + r"\label{" + label + "}}")
            if entry["why_relevant"]:
                lines.append(r"\textbf{Purpose:} " + escape_latex(entry["why_relevant"]) + r"\\")
            if entry["relation_type"]:
                lines.append(r"\textbf{Relation type:} " + escape_latex(entry["relation_type"]) + r"\\")
            if entry["reliability_levels"]:
                lines.append(
                    r"\textbf{Reliability seen in report:} "
                    + escape_latex(", ".join(entry["reliability_levels"]))
                    + r"\\"
                )
            if entry["survey_fields"]:
                lines.append(
                    r"\textbf{Survey field(s):} "
                    + escape_latex_with_inline_breaks("; ".join(entry["survey_fields"]))
                    + r"\\"
                )
            if entry["directory_fields"]:
                lines.append(
                    r"\textbf{Directory field(s):} "
                    + escape_latex_with_inline_breaks("; ".join(entry["directory_fields"]))
                    + r"\\"
                )
            if entry["comparison_description"]:
                lines.append(
                    r"\textbf{Comparison method:} "
                    + escape_latex_with_inline_breaks(entry["comparison_description"])
                    + r"\\"
                )
            if entry["strategic_objectives"]:
                lines.append(
                    r"\textbf{Strategic objective(s):} "
                    + escape_latex(", ".join(entry["strategic_objectives"]))
                    + r"\\"
                )
    lines.append(r"\end{document}")
    return "\n".join(lines) + "\n"


def render_pdf(tex_content: str, tex_path: str | Path, pdf_path: str | Path | None) -> None:
    tex_output_path = Path(tex_path)
    tex_output_path.write_text(tex_content, encoding="utf-8")
    if pdf_path is None:
        return
    latexmk = shutil.which("latexmk")
    xelatex = shutil.which("xelatex")
    if latexmk is None and xelatex is None:
        raise InputError("Neither latexmk nor XeLaTeX is installed or on PATH; cannot render PDF.")
    pdf_output_path = Path(pdf_path)
    with tempfile.TemporaryDirectory(prefix="survey-so2-tex-") as build_dir:
        build_dir_path = Path(build_dir)
        build_tex_path = build_dir_path / tex_output_path.name
        build_tex_path.write_text(tex_content, encoding="utf-8")
        if latexmk is not None:
            subprocess.run(
                [latexmk, "-pdfxe", "-interaction=nonstopmode", "-halt-on-error", build_tex_path.name],
                cwd=build_dir,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        else:
            for _ in range(2):
                subprocess.run(
                    [xelatex, "-interaction=nonstopmode", "-halt-on-error", build_tex_path.name],
                    cwd=build_dir,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
        built_pdf_path = build_dir_path / (build_tex_path.stem + ".pdf")
        if not built_pdf_path.exists():
            raise InputError("XeLaTeX finished without producing the expected PDF.")
        pdf_output_path.write_bytes(built_pdf_path.read_bytes())


def confidence_at_least(confidence: str, minimum: str) -> bool:
    order = {"uncertain": 0, "almost_certain": 1, "certain": 2}
    return order[confidence] >= order[minimum]


def export_update_plan_from_report(report: dict[str, Any], output_json: str | Path, min_confidence: str) -> dict[str, Any]:
    updates = []
    for finding in report.get("findings", []):
        if not finding.get("export_update_plan"):
            continue
        proposal = finding.get("proposed_update")
        if not proposal:
            continue
        if not confidence_at_least(proposal["confidence"], min_confidence):
            continue
        updates.append(proposal)
    payload = {
        "format_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": {
            "tool": "survey-so2-directory.py",
            "source": "SO2 survey",
            "report_generated_at": report.get("report_metadata", {}).get("generated_at", ""),
        },
        "updates": updates,
    }
    payload["file_checksum"] = compute_checksum({key: value for key, value in payload.items() if key != "file_checksum"})
    write_json(output_json, payload)
    return payload


def run_analyze(args: argparse.Namespace) -> int:
    report = analyze_survey(args)
    write_json(args.output_json, report)
    if args.output_tex or args.output_pdf:
        tex_path = args.output_tex or (str(Path(args.output_json).with_suffix(".tex")))
        render_pdf(render_tex(report), tex_path, args.output_pdf)
    return EXIT_OK


def run_render(args: argparse.Namespace) -> int:
    report = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    render_pdf(render_tex(report), args.output_tex, args.output_pdf)
    return EXIT_OK


def run_export_update_plan(args: argparse.Namespace) -> int:
    report = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    export_update_plan_from_report(report, args.output_json, args.min_confidence)
    return EXIT_OK


def main() -> int:
    parser = build_cli()
    args = parser.parse_args()
    configure_logging(args)
    try:
        if args.command == "analyze":
            return run_analyze(args)
        if args.command == "render-report":
            return run_render(args)
        if args.command == "export-update-plan":
            return run_export_update_plan(args)
        raise InputError(f"Unsupported command {args.command!r}.")
    except InputError as exc:
        logging.error("%s", exc)
        return EXIT_INPUT_ERROR
    except subprocess.CalledProcessError as exc:
        logging.error("XeLaTeX failed: %s", exc.stdout or exc)
        return EXIT_RUNTIME_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
