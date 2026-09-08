#!/usr/bin/env python3
"""Match active Directory juridical persons to EOSC-A and resume Codex reviews."""

import csv
import json
import logging
from pathlib import Path
import sys
import zipfile

from cli_common import (
    add_directory_auth_arguments, add_directory_schema_argument,
    add_logging_arguments, add_no_stdout_argument, add_optional_xlsx_output_argument,
    add_purge_cache_arguments, build_directory_kwargs, build_parser, configure_logging,
)
from eosc_organisation_matching import (
    approve_reviews, catalogue, group_biobanks, import_reviews, matched_institutions,
    migrate_proposal, new_registry, prepare_review, registry_diagnostics, render_review_markdown, validate_registry,
)


def _load_json(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"Non-finite JSON value: {value}")

    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=unique_object, parse_constant=invalid_constant)


def _json_text(value):
    return json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def _check_output_paths(paths):
    paths = [Path(path) for path in paths]
    if len({path.resolve() for path in paths}) != len(paths):
        raise ValueError("Output paths must be distinct")
    for path in paths:
        if path.exists() or path.is_symlink():
            raise ValueError(f"Output already exists; choose a new filename: {path}")
        if not path.parent.is_dir():
            raise ValueError(f"Output directory does not exist: {path.parent}")
    return paths


def _write_new_texts(outputs):
    paths = _check_output_paths([path for path, _ in outputs])
    created = []
    try:
        for path, (_, content) in zip(paths, outputs):
            # Exclusive creation protects source files even against path races.
            with path.open("x", encoding="utf-8") as stream:
                created.append(path)
                stream.write(content)
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise


def create_parser():
    """Return the offline argparse interface for exports and review operations."""
    parser = build_parser(description=__doc__)
    add_logging_arguments(parser)
    add_directory_auth_arguments(parser)
    add_directory_schema_argument(parser)
    add_purge_cache_arguments(parser, ["directory"])
    parser.set_defaults(purgeCaches=[])
    add_no_stdout_argument(parser)
    add_optional_xlsx_output_argument(parser, dest="outputXLSX", short_option="-X",
                                      long_option="--output-xlsx", help_text="write a new two-sheet XLSX")
    parser.add_argument("-i", "--input-xlsx", required=True, help="EOSC membership workbook (read-only)")
    sheet = parser.add_mutually_exclusive_group()
    sheet.add_argument("--sheet", help="exact worksheet name (default: first worksheet)")
    sheet.add_argument("--sheet-index", type=int, help="one-based worksheet index")
    parser.add_argument("--mapping-file", help="version 1 review registry; omit for an empty registry")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--prepare-ai-review", metavar="PREFIX", help="write Codex Markdown and JSON packets")
    actions.add_argument("--import-ai-review", metavar="JSON", help="import partial AI results without approval")
    actions.add_argument("--migrate-proposal", metavar="JSON", help="preserve the legacy 1.0-proposal in a new registry")
    actions.add_argument("--approve-review", nargs="+", metavar="REVIEW_ID", help="explicitly approve selected current matches")
    parser.add_argument("--review-packet", help="original packet JSON, required for importing results")
    parser.add_argument("--output-mapping", help="new registry filename; inputs are never overwritten")
    parser.add_argument("--reviewer", help="human reviewer name/identifier for explicit approval")
    parser.add_argument("--review-scope", choices=["incremental", "unresolved", "all"], default="incremental")
    parser.add_argument("--review-case", action="append", default=[], metavar="CASE_ID", help="reopen/select an exact case; repeatable")
    parser.add_argument("--review-limit", type=int, help="maximum cases in one packet")
    parser.add_argument("--eligible-status", action="append", help="eligible EOSC status; repeatable (default: exact Active)")
    parser.add_argument("--report-json", help="new diagnostic JSON filename for a normal export")
    parser.add_argument("--dry-run", action="store_true", help="validate migration/import/approval without writing")
    return parser


def main(argv=None, *, directory_factory=None):
    """Execute the CLI with lazy Directory loading and optional test injection.

    Args:
        argv: Argument strings, or None to read sys.argv.
        directory_factory: Optional Directory-compatible factory for tests.
    Returns:
        Zero on success. argparse reports usage/input errors with exit status 2.
    """
    parser = create_parser()
    args = parser.parse_args(argv)
    configure_logging(args)
    write_action = bool(args.import_ai_review or args.migrate_proposal or args.approve_review)
    special = write_action or bool(args.prepare_ai_review)
    if write_action and not args.output_mapping and not args.dry_run:
        parser.error("migration/import/approval requires --output-mapping with a new filename")
    if args.output_mapping and not write_action:
        parser.error("--output-mapping requires migration, import or approval")
    if args.dry_run and not write_action:
        parser.error("--dry-run requires migration, import or approval")
    if args.import_ai_review and not args.review_packet:
        parser.error("--import-ai-review requires --review-packet")
    if args.approve_review and (not args.reviewer or not args.mapping_file):
        parser.error("--approve-review requires --reviewer and --mapping-file")
    if args.migrate_proposal and args.mapping_file:
        parser.error("migration creates a new registry; do not pass --mapping-file")
    if special and (args.outputXLSX or args.report_json):
        parser.error("use export outputs in a separate normal export invocation")
    if not args.prepare_ai_review and (args.review_case or args.review_limit is not None or args.review_scope != "incremental"):
        parser.error("review selection options require --prepare-ai-review")
    if args.review_packet and not args.import_ai_review:
        parser.error("--review-packet requires --import-ai-review")
    if args.reviewer and not args.approve_review:
        parser.error("--reviewer requires --approve-review")
    try:
        from eosc_membership_xlsx import read_membership, write_matches_xlsx

        outputs = []
        if not args.dry_run:
            outputs.extend(args.outputXLSX or [])
            outputs.extend([p for p in (args.report_json, args.output_mapping) if p])
            if args.prepare_ai_review:
                outputs.extend([args.prepare_ai_review + ".json", args.prepare_ai_review + ".md"])
        _check_output_paths(outputs)
        workbook = read_membership(args.input_xlsx, sheet=args.sheet, sheet_index=args.sheet_index)
        orgs = catalogue(workbook["organisations"])
        if directory_factory is None:
            from directory import Directory
            directory_factory = Directory
        directory = directory_factory(**build_directory_kwargs(args))
        scope = {"directory_target": directory.getDirectoryUrl().rstrip("/"), "schema": directory.getSchema()}
        # Do not trust IDs frozen in an old mapping as the current active inventory.
        active = [bank for bank in directory.getBiobanks() if not directory.isBiobankWithdrawn(bank["id"])]
        groups = group_biobanks(active)
        registry = _load_json(args.mapping_file) if args.mapping_file else new_registry(scope)
        validate_registry(registry)
        if registry["source_scope"] != scope:
            raise ValueError("Registry Directory target/schema differs from the current snapshot")
        if args.migrate_proposal:
            updated = migrate_proposal(_load_json(args.migrate_proposal), groups, orgs, scope)
        elif args.import_ai_review:
            updated = import_reviews(registry, _load_json(args.review_packet),
                                     _load_json(args.import_ai_review), groups, orgs)
        elif args.approve_review:
            updated = approve_reviews(registry, args.approve_review, args.reviewer, groups, orgs)
        if write_action:
            if not args.dry_run:
                _write_new_texts([(args.output_mapping, _json_text(updated))])
            print(f"{'Validated only' if args.dry_run else 'Wrote registry'}: {len(updated['decisions'])} decisions; "
                  f"{sum(d['approval'] == 'approved' for d in updated['decisions'])} approved.", file=sys.stderr)
            return 0
        if args.prepare_ai_review:
            packet = prepare_review(registry, groups, orgs, scope=args.review_scope,
                                    case_ids=args.review_case, limit=args.review_limit)
            _write_new_texts([(args.prepare_ai_review + ".json", _json_text(packet)),
                              (args.prepare_ai_review + ".md", render_review_markdown(packet))])
            print(f"Prepared {len(packet['cases'])} cases; {packet['omitted_by_limit']} deferred by limit. "
                  "No decisions or approvals changed.", file=sys.stderr)
            return 0
        statuses = args.eligible_status or ["Active"]
        if statuses != ["Active"]:
            logging.warning("Explicit EOSC membership-status policy: %s", statuses)
        rows, counts = matched_institutions(registry, groups, orgs, eligible_statuses=statuses)
        diagnostics = registry_diagnostics(registry, groups, orgs)
        stale = [d for d in diagnostics if d["status"].startswith("stale_")]
        if stale:
            logging.warning("%d stale identity/context decisions are excluded; prepare a review packet", len(stale))
        for issue in diagnostics:
            logging.debug("Registry decision %s: %s", issue["review_id"], issue["status"])
        pending = sum(d["status"] == "pending_approval" for d in diagnostics)
        if pending:
            logging.warning("%d match proposals await human approval; they are not exported", pending)
        if args.outputXLSX:
            write_matches_xlsx(workbook, rows, args.outputXLSX[0])
        if args.report_json:
            _write_new_texts([(args.report_json, _json_text({"source_scope": scope,
                "workbook_sha256": workbook["workbook_sha256"], "worksheet": workbook["sheet_name"],
                "matches": rows, "counts": counts, "eligible_statuses": statuses,
                "pending_match_proposals": pending, "registry_diagnostics": diagnostics}))])
        if not args.nostdout:
            writer = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
            writer.writerow(["Organisation ID", "EOSC-A Name", "BBMRI-ERIC Name", "List of biobankIDs"])
            for row in rows:
                writer.writerow([row["organisation_id"], row["eosc_name"], row["directory_juridical_person"],
                                 ",".join(row["biobank_ids"])])
            print(f"EOSC-A Members: {counts['Member']}\nEOSC-A Observers: {counts['Observer']}")
        return 0
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        if args.debug:
            logging.exception("EOSC operation failed")
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
