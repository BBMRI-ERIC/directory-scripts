#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

"""Regenerate the shareable AI check cache from current Directory data."""

from __future__ import annotations

import logging as log
from pathlib import Path

from ai_cache import AI_CACHE_ROOT
from ai_check_generation import build_report_lines, generate_payloads, write_payloads
from cli_common import (
    add_directory_auth_arguments,
    add_directory_schema_argument,
    add_logging_arguments,
    add_purge_cache_arguments,
    add_withdrawn_scope_arguments,
    build_directory_kwargs,
    build_parser,
    configure_logging,
)
from directory import Directory


parser = build_parser(description="Generate the shareable AI check cache from current Directory data.")
add_logging_arguments(parser)
add_purge_cache_arguments(parser, ["directory"], include_purge_all=False)
add_withdrawn_scope_arguments(
    parser,
    include_help_text="include withdrawn biobanks/collections when generating AI findings",
    only_help_text="generate AI findings only for withdrawn biobanks/collections",
)
add_directory_auth_arguments(parser)
add_directory_schema_argument(parser, default="ERIC")
parser.add_argument(
    "--output-dir",
    default=str(AI_CACHE_ROOT),
    help="output directory that will receive the ai-check-cache/<schema> JSON files",
)
parser.add_argument(
    "--report",
    help="optional text file that receives the human-readable AI findings report",
)
args = parser.parse_args()

configure_logging(args)

directory = Directory(**build_directory_kwargs(args))
output_dir = Path(args.output_dir)
payloads = generate_payloads(directory)
counts = write_payloads(directory, output_dir)
report_lines = build_report_lines(payloads)

if args.report:
    report_path = Path(args.report)
    report_path.write_text("\n".join(report_lines) + ("\n" if report_lines else ""), encoding="utf-8")
    log.info("Wrote AI findings report to %s", report_path)

for rule_name in sorted(counts):
    log.info("%s: %s findings", rule_name, counts[rule_name])
log.info("Total AI findings: %s", len(report_lines))
