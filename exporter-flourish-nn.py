#!/usr/bin/env python3
"""Export BBMRI Directory National-Node statistics for Flourish points maps."""

import pprint

from cli_common import (add_directory_schema_argument, add_logging_arguments, add_no_stdout_argument,
                        add_purge_cache_arguments, add_withdrawn_scope_arguments, add_xlsx_output_argument,
                        build_directory_kwargs, build_parser, configure_logging)
from directory import Directory
from flourish_nn import COUNTRY_POINTS, TYPE_LABELS, build_points, dataframe
from xlsxutils import write_xlsx_tables


def build_cli():
    """Build the standard exporter CLI.

    Returns:
        Configured argument parser for the Flourish exporter.
    """
    parser = build_parser()
    add_logging_arguments(parser); add_xlsx_output_argument(parser); add_no_stdout_argument(parser)
    add_directory_schema_argument(parser, default="ERIC"); add_withdrawn_scope_arguments(parser)
    add_purge_cache_arguments(parser, ["directory"])
    parser.add_argument("--include-ext", action="store_true", help="include EXT records reported in member/observer countries")
    parser.add_argument("--include-all-countries", action="store_true", help="include all represented reported countries; implies --include-ext")
    return parser


def main(argv=None):
    """Run the Flourish exporter and optionally write its Points XLSX worksheet.

    Args:
        argv: Optional command arguments; ``None`` reads process arguments.

    Returns:
        Zero after successful reporting and optional XLSX output.
    """
    args = build_cli().parse_args(argv)
    configure_logging(args)
    directory = Directory(**build_directory_kwargs(args, pp=pprint.PrettyPrinter(indent=4)))
    points = build_points(directory, include_ext=args.include_ext or args.include_all_countries, include_all_countries=args.include_all_countries)
    if not args.nostdout:
        for point in points:
            types = ", ".join(f"{TYPE_LABELS.get(key, key)}={value}" for key, value in sorted(point.types.items()))
            print(f"{point.country_code} ({COUNTRY_POINTS[point.country_code].name}): {len(point.biobanks)} organisations, {len(point.collections)} collections" + (f"; {types}" if types else ""))
    if args.outputXLSX:
        write_xlsx_tables(args.outputXLSX[0], [(dataframe(points, directory.getDirectoryUrl()), "Points", False)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
