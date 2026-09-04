#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

"""Export likely collection-based fact-sheet emulation for expert review."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
import logging as log
import pprint
from typing import Any

import pandas as pd

from cli_common import (
    add_directory_auth_arguments,
    add_directory_schema_argument,
    add_logging_arguments,
    add_no_stdout_argument,
    add_purge_cache_arguments,
    add_withdrawn_scope_arguments,
    add_xlsx_output_argument,
    build_directory_kwargs,
    build_parser,
    configure_logging,
)
from directory import Directory
from fact_sheet_emulation import (
    analyze_directory,
    build_ai_review_packet,
    write_ai_review_packets,
)
from xlsxutils import write_xlsx_tables


CACHES = ["directory"]
SHEET_LAYOUT = (
    ("candidate_families", "Candidate families"),
    ("source_collections", "Source collections"),
    ("field_comparisons", "Field comparison"),
    ("boundary_evidence", "Boundary evidence"),
    ("proposed_facts", "Proposed facts"),
    ("unrepresentable_data", "Unrepresentable data"),
    ("migration_mapping", "Migration mapping"),
    ("dimension_candidates", "Dimension candidates"),
    ("dimension_values", "Dimension values"),
)
ADVANCED_XLSX_TABLES = frozenset({"field_comparisons", "boundary_evidence"})

TABLE_COLUMNS = {
    "candidate_families": [
        "country",
        "biobank_id",
        "family_id",
        "family_kind",
        "discovery_rule",
        "base_name",
        "member_count",
        "emulation_score",
        "emulation_confidence",
        "deterministic_classification",
        "review_only",
        "abstention_reason",
        "description_classification",
        "operational_boundary_categories",
        "operational_boundary_evidence_count",
        "identity_evidence",
        "migration_readiness",
        "target_collection_id",
        "operational_conflict_count",
        "operational_conflict_fields",
        "dimension_count",
        "requires_external_review",
    ],
    "source_collections": [
        "country",
        "biobank_id",
        "family_id",
        "family_kind",
        "collection_id",
        "name",
        "parent_collection_id",
        "size",
        "number_of_donors",
        "order_of_magnitude",
        "order_of_magnitude_donors",
    ],
    "field_comparisons": [
        "country",
        "biobank_id",
        "family_id",
        "field",
        "role",
        "status",
        "normalization",
        "collection_id",
        "value",
        "distinct_value_count",
        "missing_collection_count",
    ],
    "boundary_evidence": [
        "country",
        "biobank_id",
        "family_id",
        "collection_id",
        "source_field",
        "boundary_category",
        "marker",
        "qualifier",
        "date_or_time_expression",
        "snippet",
    ],
    "proposed_facts": [
        "country",
        "biobank_id",
        "family_id",
        "target_collection_id",
        "source_collection_id",
        "source_fact_id",
        "row_kind",
        "count_provenance",
        "sex",
        "age_range",
        "sample_type",
        "disease",
        "number_of_samples",
        "number_of_donors",
    ],
    "unrepresentable_data": [
        "country",
        "biobank_id",
        "family_id",
        "target_collection_id",
        "collection_id",
        "dimension",
        "source_field",
        "original_value",
        "normalized_value",
        "extraction_method",
        "review_status",
        "reason",
    ],
    "migration_mapping": [
        "country",
        "biobank_id",
        "family_id",
        "family_kind",
        "discovery_rule",
        "deterministic_classification",
        "description_classification",
        "operational_boundary_categories",
        "abstention_reason",
        "target_collection_id",
        "target_action",
        "source_collection_count",
        "readiness",
        "blockers",
        "unknown_operational_fields",
        "target_operational_conflict_fields",
        "target_unknown_operational_fields",
        "context_conflict_fields",
        "identity_evidence",
        "proposed_fact_rows",
        "target_total_evidence_source",
        "count_policy",
    ],
    "dimension_candidates": [
        "country",
        "biobank_id",
        "family_id",
        "dimension",
        "source_field",
        "classification",
        "representability",
        "ontology",
        "member_count",
        "member_coverage",
        "structured_member_coverage",
        "distinct_value_count",
        "multivalued_member_count",
        "confidence",
        "provenance",
        "generalizability",
        "privacy_risk",
    ],
    "dimension_values": [
        "country",
        "biobank_id",
        "family_id",
        "collection_id",
        "dimension",
        "source_field",
        "original_value",
        "normalized_value",
        "extraction_method",
        "review_status",
        "multivalued",
    ],
}


def _parse_country_values(values: list[str] | None) -> list[str]:
    """Normalize repeated, space-separated, or comma-separated country codes."""
    countries = []
    for value in values or []:
        for item in value.split(","):
            country = item.strip().upper()
            if country and country not in countries:
                countries.append(country)
    return countries


def _directory_url(directory: Directory, route: str, entity_id: str) -> str:
    """Return the Directory web-view URL for an entity."""
    if not entity_id:
        return ""
    base_url = directory.getDirectoryUrl().rstrip("/")
    return f"{base_url}/{directory.getSchema()}/directory/#/{route}/{entity_id}"


def _flatten_field_comparisons(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Put each compared collection value on its own bounded workbook row."""
    flattened = []
    for comparison in rows:
        base = {
            key: value
            for key, value in comparison.items()
            if key not in {
                "member_values",
                "distinct_values",
                "missing_collection_ids",
            }
        }
        base["distinct_value_count"] = len(comparison.get("distinct_values", []))
        base["missing_collection_count"] = len(
            comparison.get("missing_collection_ids", [])
        )
        for member_value in comparison["member_values"]:
            flattened.append(
                {
                    **base,
                    "collection_id": member_value["collection_id"],
                    "value": member_value["value"],
                }
            )
    return flattened


def _tabular_value(value: Any) -> Any:
    """Serialize nested evidence predictably while preserving scalar types."""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, ensure_ascii=True)
    return value


def _make_dataframe(
    table_name: str,
    rows: list[dict[str, Any]],
    directory: Directory,
) -> pd.DataFrame:
    """Create one sorted, hyperlink-ready report dataframe."""
    if table_name == "field_comparisons":
        rows = _flatten_field_comparisons(rows)
    output_rows = []
    for source in rows:
        row = {
            key: _tabular_value(value)
            for key, value in source.items()
            if not (
                table_name == "candidate_families"
                and key == "source_collection_ids"
            )
        }
        for column in (
            "collection_id",
            "source_collection_id",
            "target_collection_id",
            "parent_collection_id",
        ):
            if row.get(column):
                row[f"{column}_directory_url"] = _directory_url(
                    directory,
                    "collection",
                    str(row[column]),
                )
        output_rows.append(row)

    preferred = list(TABLE_COLUMNS[table_name])
    url_columns = [
        f"{column}_directory_url"
        for column in (
            "collection_id",
            "source_collection_id",
            "target_collection_id",
            "parent_collection_id",
        )
        if any(f"{column}_directory_url" in row for row in output_rows)
    ]
    extra = sorted(
        {
            key
            for row in output_rows
            for key in row
            if key not in preferred and key not in url_columns
        }
    )
    columns = [*preferred, *extra, *url_columns]
    dataframe = pd.DataFrame(output_rows, columns=columns)
    sort_columns = [
        column
        for column in ("country", "biobank_id", "family_id", "collection_id", "source_collection_id", "field", "dimension")
        if column in dataframe.columns
    ]
    if sort_columns and not dataframe.empty:
        dataframe.sort_values(by=sort_columns, inplace=True, kind="stable")
        dataframe.reset_index(drop=True, inplace=True)
    return dataframe


def _xlsx_options(dataframe: pd.DataFrame) -> dict[str, Any]:
    """Return hyperlink and hidden-column options for a report dataframe."""
    hyperlink_columns = []
    hidden_columns = []
    for column in (
        "collection_id",
        "source_collection_id",
        "target_collection_id",
        "parent_collection_id",
    ):
        url_column = f"{column}_directory_url"
        if column in dataframe.columns and url_column in dataframe.columns:
            hyperlink_columns.append((column, url_column))
            hidden_columns.append(url_column)
    return {
        "hyperlink_columns": hyperlink_columns,
        "hide_columns": hidden_columns,
    }


def _print_report(analysis: dict[str, list[dict[str, Any]]]) -> None:
    """Print country-grouped candidate details and totals."""
    families = analysis["candidate_families"]
    migration_by_family = {
        row["family_id"]: row for row in analysis["migration_mapping"]
    }
    sources_by_family = defaultdict(list)
    for row in analysis["source_collections"]:
        sources_by_family[row["family_id"]].append(row["collection_id"])

    print("Fact-sheet emulation candidate families")
    if not families:
        print("None")
    current_country = None
    for family in families:
        if family["country"] != current_country:
            current_country = family["country"]
            print(current_country or "(no country)")
        migration = migration_by_family[family["family_id"]]
        print(
            f"   {family['family_id']} - {family['base_name']} "
            f"[{family['deterministic_classification']}; "
            f"{family['emulation_confidence']} confidence; {migration['readiness']}; "
            f"rule: {family['discovery_rule']}; sources: {family['member_count']}]"
        )
        if family["target_collection_id"]:
            print(f"      target: {family['target_collection_id']}")
        source_ids = sources_by_family[family["family_id"]]
        displayed_ids = source_ids[:10]
        source_text = ", ".join(displayed_ids)
        if len(source_ids) > len(displayed_ids):
            source_text += f", ... ({len(source_ids) - len(displayed_ids)} more)"
        print(f"      source IDs: {source_text}")
        if family["operational_boundary_categories"]:
            print(
                "      boundary evidence: "
                + ", ".join(family["operational_boundary_categories"])
            )
        if family["abstention_reason"]:
            print(f"      abstention: {family['abstention_reason']}")
        if migration["blockers"]:
            print(f"      blockers: {', '.join(migration['blockers'])}")

    print("")
    print("Per-country summary:")
    families_by_country = defaultdict(list)
    for family in families:
        families_by_country[family["country"]].append(family)
    for country in sorted(families_by_country):
        country_families = families_by_country[country]
        readiness = Counter(
            migration_by_family[family["family_id"]]["readiness"]
            for family in country_families
        )
        print(
            f"- {country or '(no country)'}: families = {len(country_families)}, "
            f"source collections = {sum(family['member_count'] for family in country_families)}, "
            f"high confidence = {sum(family['emulation_confidence'] == 'high' for family in country_families)}, "
            f"ready_current_fact_schema = {readiness['ready_current_fact_schema']}, "
            f"external review = {sum(family['requires_external_review'] for family in country_families)}"
        )
    if not families_by_country:
        print("- none")

    print("")
    print("Per-biobank summary:")
    families_by_biobank = defaultdict(list)
    for family in families:
        families_by_biobank[(family["country"], family["biobank_id"])].append(
            family
        )
    for (country, biobank_id), biobank_families in sorted(
        families_by_biobank.items()
    ):
        readiness = Counter(
            migration_by_family[family["family_id"]]["readiness"]
            for family in biobank_families
        )
        print(
            f"- {country or '(no country)'} / {biobank_id or '(no biobank)'}: "
            f"families = {len(biobank_families)}, "
            f"source collections = "
            f"{sum(family['member_count'] for family in biobank_families)}, "
            f"high confidence = "
            f"{sum(family['emulation_confidence'] == 'high' for family in biobank_families)}, "
            f"ready_current_fact_schema = {readiness['ready_current_fact_schema']}, "
            f"external review = "
            f"{sum(family['requires_external_review'] for family in biobank_families)}"
        )
    if not families_by_biobank:
        print("- none")

    print("")
    print("Totals:")
    print(f"- candidate families: {len(families)}")
    print(f"- source collections: {len(analysis['source_collections'])}")
    print(f"- proposed fact rows: {len(analysis['proposed_facts'])}")
    print(f"- candidate future/unsupported dimensions: {sum(row['representability'] != 'current_fact_schema' for row in analysis['dimension_candidates'])}")
    print(f"- families requiring external review: {sum(family['requires_external_review'] for family in families)}")
    classifications = Counter(
        family["deterministic_classification"] for family in families
    )
    print(f"- likely emulation families: {classifications['likely_emulation']}")
    print(f"- review-only/unresolved families: {classifications['review_only'] + classifications['unresolved_candidate']}")
    print(f"- operationally distinct/mixed families: {classifications['operationally_distinct'] + classifications['mixed_or_operationally_distinct']}")
    print(f"- scientific-question/data-element catalogues: {classifications['scientific_question_catalogue']}")


def build_argument_parser():
    """Build the standalone exporter argument parser."""
    parser = build_parser(
        description=(
            "Detect collection families that may historically emulate fact sheets. "
            "The exporter is read-only and all migration output is advisory."
        )
    )
    add_logging_arguments(parser)
    add_directory_auth_arguments(parser)
    add_xlsx_output_argument(parser)
    add_no_stdout_argument(parser)
    add_directory_schema_argument(parser, default="ERIC")
    add_withdrawn_scope_arguments(parser)
    add_purge_cache_arguments(parser, CACHES)
    parser.add_argument(
        "--scope",
        choices=("all", "siblings", "top-level"),
        default="all",
        help="candidate family scope (default: all)",
    )
    parser.add_argument(
        "--min-confidence",
        choices=("low", "medium", "high"),
        default="low",
        help="lowest deterministic emulation confidence to include",
    )
    parser.add_argument(
        "-c",
        "--country",
        dest="countries",
        nargs="+",
        action="extend",
        help="limit source collections to one or more country codes",
    )
    parser.add_argument(
        "--ai-review-prefix",
        help=(
            "write matching <prefix>-ai-review.json and .md advisory packets "
            "for unresolved cases"
        ),
    )
    parser.add_argument(
        "--advanced-reporting",
        action="store_true",
        help="include Field comparison and Boundary evidence diagnostic worksheets",
    )
    parser.set_defaults(purgeCaches=[], countries=[])
    return parser


def main() -> None:
    """Run the fact-sheet emulation exporter."""
    parser = build_argument_parser()
    args = parser.parse_args()
    configure_logging(args)

    directory = Directory(
        **build_directory_kwargs(args, pp=pprint.PrettyPrinter(indent=4))
    )
    countries = _parse_country_values(args.countries)
    analysis = analyze_directory(
        directory,
        scope=args.scope,
        min_confidence=args.min_confidence,
        countries=countries,
    )

    if not args.nostdout:
        _print_report(analysis)

    if args.outputXLSX is not None:
        sheets = []
        for table_name, sheet_name in SHEET_LAYOUT:
            if table_name in ADVANCED_XLSX_TABLES and not args.advanced_reporting:
                continue
            dataframe = _make_dataframe(table_name, analysis[table_name], directory)
            sheets.append((dataframe, sheet_name, False, _xlsx_options(dataframe)))
        write_xlsx_tables(args.outputXLSX[0], sheets)

    if args.ai_review_prefix:
        packet = build_ai_review_packet(analysis)
        json_path, markdown_path = write_ai_review_packets(
            args.ai_review_prefix,
            packet,
        )
        log.info("Wrote advisory AI/expert review packets to %s and %s", json_path, markdown_path)


if __name__ == "__main__":
    main()
