#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

"""Export per-biobank sample, donor, collection, service, and fact-sheet statistics."""

import logging as log
import pprint
from collections import Counter

import pandas as pd

from cli_common import (
    add_directory_auth_arguments,
    add_directory_schema_argument,
    add_logging_arguments,
    add_no_stdout_argument,
    add_purge_cache_arguments,
    add_xlsx_output_argument,
    build_parser,
    configure_logging,
)
from directory import Directory
from directory_stats_utils import build_directory_stats, build_stats_summary
from oomutils import (
    describe_oom_estimate_policy,
    get_oom_upper_bound_coefficient,
)
from xlsxutils import write_xlsx_tables


CACHES_LIST = ["directory"]
pp = pprint.PrettyPrinter(indent=4)


def _build_warning_frame(rows: list[dict]) -> pd.DataFrame:
    """Return a warnings dataframe with stable columns even when empty."""
    return pd.DataFrame(
        rows,
        columns=[
            "biobank_id",
            "biobank_name",
            "collection_id",
            "collection_name",
            "code",
            "message",
            "expected",
            "actual",
        ],
    )


parser = build_parser()
add_logging_arguments(parser)
add_xlsx_output_argument(parser)
add_no_stdout_argument(parser)
add_directory_auth_arguments(parser)
add_directory_schema_argument(parser, default="ERIC")
add_purge_cache_arguments(parser, CACHES_LIST)
parser.add_argument(
    "-w",
    "--include-withdrawn-biobanks",
    dest="include_withdrawn_biobanks",
    action="store_true",
    help="include withdrawn biobanks and their associated collections/services in the statistics",
)
parser.add_argument(
    "-c",
    "--country",
    dest="countries",
    nargs="+",
    action="extend",
    default=[],
    help="limit statistics to one or more biobank country codes",
)
parser.add_argument(
    "-A",
    "--staging-area",
    dest="staging_areas",
    nargs="+",
    action="extend",
    default=[],
    help="limit statistics to one or more staging-area codes parsed from biobank IDs (for example CZ, UK, EXT)",
)
parser.add_argument(
    "-t",
    "--collection-type",
    dest="collection_types",
    nargs="+",
    action="extend",
    default=[],
    help="limit collection-based statistics to one or more collection types",
)
parser.set_defaults(purgeCaches=[])
args = parser.parse_args()

configure_logging(args)

directory_kwargs = {
    "schema": args.schema,
    "purgeCaches": args.purgeCaches,
    "debug": args.debug,
    "pp": pp,
}
if args.username is not None and args.password is not None:
    directory_kwargs["username"] = args.username
    directory_kwargs["password"] = args.password

dir = Directory(**directory_kwargs)

log.info("Total biobanks: %d", dir.getBiobanksCount())
log.info("Total collections: %d", dir.getCollectionsCount())
log.info("Total services: %d", len(dir.getServices()))
log.info(
    "OoM estimate policy: %s (coefficient=%s)",
    describe_oom_estimate_policy(),
    get_oom_upper_bound_coefficient(),
)

stats = build_directory_stats(
    dir,
    include_withdrawn_biobanks=args.include_withdrawn_biobanks,
    country_filters=args.countries,
    staging_area_filters=args.staging_areas,
    collection_type_filters=args.collection_types,
)
summary = build_stats_summary(stats["biobank_rows"])
summary["fact_sheet_warnings_total"] = len(stats["fact_sheet_warning_rows"])
summary["include_withdrawn_biobanks"] = int(args.include_withdrawn_biobanks)
summary["country_filter"] = ",".join(args.countries)
summary["staging_area_filter"] = ",".join(args.staging_areas)
summary["collection_type_filter"] = ",".join(args.collection_types)
summary["oom_upper_bound_coefficient"] = get_oom_upper_bound_coefficient()
summary["oom_estimate_policy"] = describe_oom_estimate_policy()

stats_df = pd.DataFrame(stats["biobank_rows"])
summary_df = pd.DataFrame([summary])
collection_type_df = pd.DataFrame(stats["collection_type_rows"])
collection_type_summary_df = pd.DataFrame(stats["collection_type_summary_rows"])
top_level_collection_type_summary_df = pd.DataFrame(
    stats["top_level_collection_type_summary_rows"]
)
subcollection_type_summary_df = pd.DataFrame(
    stats["subcollection_type_summary_rows"]
)
service_type_df = pd.DataFrame(stats["service_type_rows"])
service_type_summary_df = pd.DataFrame(stats["service_type_summary_rows"])
fact_warning_df = _build_warning_frame(stats["fact_sheet_warning_rows"])

if stats["fact_sheet_warning_rows"]:
    if args.verbose or args.debug:
        for warning in stats["fact_sheet_warning_rows"]:
            log.warning(
                "%s: %s (%s, expected=%r, actual=%r)",
                warning["collection_id"],
                warning["message"],
                warning["code"],
                warning["expected"],
                warning["actual"],
            )
    else:
        warning_code_counts = Counter(
            warning["code"] for warning in stats["fact_sheet_warning_rows"]
        )
        affected_collections = len(
            {warning["collection_id"] for warning in stats["fact_sheet_warning_rows"]}
        )
        log.warning(
            "Detected %d fact-sheet warnings across %d collections: %s",
            len(stats["fact_sheet_warning_rows"]),
            affected_collections,
            ", ".join(
                f"{code}={warning_code_counts[code]}"
                for code in sorted(warning_code_counts)
            ),
        )

if not args.nostdout:
    print(stats_df.to_csv(sep="\t", index=False), end="")
    print()
    print(summary_df.to_csv(sep="\t", index=False), end="")

if args.outputXLSX is not None:
    write_xlsx_tables(
        args.outputXLSX[0],
        [
            (stats_df, "Biobank stats", False),
            (summary_df, "Summary", False),
            (collection_type_df, "Collection types", False),
            (collection_type_summary_df, "Collection type totals", False),
            (top_level_collection_type_summary_df, "Top-level type totals", False),
            (subcollection_type_summary_df, "Subcollection type totals", False),
            (service_type_df, "Service types", False),
            (service_type_summary_df, "Service type totals", False),
            (fact_warning_df, "Fact sheet warnings", False),
        ],
    )
