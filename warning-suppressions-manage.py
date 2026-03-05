#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

"""Manage warning-suppressions.json entries safely."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from validation_models import WarningSuppressionEntryModel
from warning_suppressions import (
    DEFAULT_WARNING_SUPPRESSIONS_PATH,
    load_warning_suppressions_detailed,
    serialize_suppression_entries,
    summarize_suppression_diagnostics,
    write_suppression_entries,
)


EXIT_OK = 0
EXIT_INPUT_ERROR = 2
EXIT_RUNTIME_ERROR = 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage false-positive suppression records used by data-check.py."
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output.")
    parser.add_argument("-d", "--debug", action="store_true", help="Debug output. Implies verbose.")
    parser.add_argument(
        "-p",
        "--path",
        default=str(DEFAULT_WARNING_SUPPRESSIONS_PATH),
        help="Path to warning suppressions JSON file.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List current suppression entries.")
    list_parser.add_argument("--check-id", default=None, help="Optional exact check ID filter.")

    add_parser = subparsers.add_parser("add", help="Add or update one suppression entry.")
    add_parser.add_argument("--check-id", required=True, help="Check ID, e.g. FT:KAnonViolation.")
    add_parser.add_argument("--entity-id", required=True, help="Entity ID to suppress for the check.")
    add_parser.add_argument(
        "--entity-type",
        default="",
        help="Optional entity type: BIOBANK, COLLECTION, CONTACT, NETWORK.",
    )
    add_parser.add_argument("--reason", default="", help="Reason for suppression.")
    add_parser.add_argument("--added-by", default="", help="Who approved/added the suppression.")
    add_parser.add_argument(
        "--added-on",
        default=None,
        help="Date (YYYY-MM-DD). Defaults to current date when omitted.",
    )
    add_parser.add_argument("--expires-on", default="", help="Optional expiration date (YYYY-MM-DD).")
    add_parser.add_argument("--ticket", default="", help="Optional tracking ticket/reference.")
    add_parser.add_argument(
        "--no-upsert",
        action="store_true",
        help="Fail if the check_id/entity_id entry already exists.",
    )

    validate_parser = subparsers.add_parser("validate", help="Validate suppression file content and metadata.")
    validate_parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero exit code when diagnostics are found.",
    )

    prune_parser = subparsers.add_parser("prune-stale", help="Remove expired suppression entries.")
    prune_parser.add_argument("-n", "--dry-run", action="store_true", help="Show what would be removed.")
    prune_parser.add_argument(
        "--before",
        default=date.today().isoformat(),
        help="Prune entries with expires_on before this date (YYYY-MM-DD). Default: today.",
    )
    return parser


def configure_logging(args: argparse.Namespace) -> None:
    if args.debug:
        args.verbose = True
    level = logging.DEBUG if args.debug else (logging.INFO if args.verbose else logging.WARNING)
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def _load_entries(path: str | Path) -> list[WarningSuppressionEntryModel]:
    issues: list[str] = []
    result = load_warning_suppressions_detailed(path, warn=issues.append)
    for issue in issues:
        logging.warning("%s", issue)
    return result.entries


def _entry_key(entry: WarningSuppressionEntryModel) -> tuple[str, str]:
    return (entry.check_id, entry.entity_id)


def _parse_entry_from_args(args: argparse.Namespace) -> WarningSuppressionEntryModel:
    added_on = args.added_on.strip() if isinstance(args.added_on, str) else args.added_on
    if not added_on:
        added_on = date.today().isoformat()
    payload = {
        "check_id": args.check_id,
        "entity_id": args.entity_id,
        "entity_type": args.entity_type,
        "reason": args.reason,
        "added_by": args.added_by,
        "added_on": added_on,
        "expires_on": args.expires_on,
        "ticket": args.ticket,
    }
    return WarningSuppressionEntryModel.parse_obj(payload)


def command_list(args: argparse.Namespace) -> int:
    entries = _load_entries(args.path)
    if args.check_id:
        entries = [entry for entry in entries if entry.check_id == args.check_id]
    if not entries:
        print("No suppression entries found.")
        return EXIT_OK
    for entry in sorted(entries, key=lambda item: (item.check_id, item.entity_id)):
        pieces = [f"{entry.check_id} :: {entry.entity_id}"]
        if entry.entity_type:
            pieces.append(f"type={entry.entity_type}")
        if entry.reason:
            pieces.append(f"reason={entry.reason}")
        if entry.expires_on:
            pieces.append(f"expires={entry.expires_on}")
        if entry.ticket:
            pieces.append(f"ticket={entry.ticket}")
        print(" | ".join(pieces))
    return EXIT_OK


def command_add(args: argparse.Namespace) -> int:
    entries = _load_entries(args.path)
    record = _parse_entry_from_args(args)
    indexed = {_entry_key(entry): entry for entry in entries}
    key = _entry_key(record)
    if key in indexed and args.no_upsert:
        raise ValueError(f"Suppression entry already exists for {record.check_id}::{record.entity_id}.")
    indexed[key] = record
    output_entries = list(indexed.values())
    write_suppression_entries(args.path, output_entries)
    action = "Updated" if key in {_entry_key(entry) for entry in entries} else "Added"
    print(f"{action} suppression {record.check_id}::{record.entity_id} in {args.path}.")
    return EXIT_OK


def command_validate(args: argparse.Namespace) -> int:
    entries = _load_entries(args.path)
    diagnostics = summarize_suppression_diagnostics(entries)
    seen = set()
    duplicate_keys = []
    for entry in entries:
        key = _entry_key(entry)
        if key in seen:
            duplicate_keys.append(key)
        seen.add(key)
    if duplicate_keys:
        diagnostics.extend(
            [f"Duplicate suppression entry for {check_id}::{entity_id}." for check_id, entity_id in duplicate_keys]
        )
    if diagnostics:
        for message in diagnostics:
            logging.warning("%s", message)
        if args.strict:
            return EXIT_INPUT_ERROR
    print(f"Validated {len(entries)} suppression entries from {args.path}.")
    if diagnostics:
        print(f"Diagnostics: {len(diagnostics)}")
    return EXIT_OK


def command_prune_stale(args: argparse.Namespace) -> int:
    entries = _load_entries(args.path)
    prune_before = date.fromisoformat(args.before)
    kept = []
    removed = []
    for entry in entries:
        if entry.expires_on:
            try:
                expiry = date.fromisoformat(entry.expires_on)
            except ValueError:
                kept.append(entry)
                continue
            if expiry < prune_before:
                removed.append(entry)
                continue
        kept.append(entry)
    if not removed:
        print("No expired entries to prune.")
        return EXIT_OK
    print(f"Expired entries to prune: {len(removed)}")
    for entry in removed:
        print(f"- {entry.check_id}::{entry.entity_id} (expires {entry.expires_on})")
    if args.dry_run:
        print("Dry run enabled. No file changes written.")
        return EXIT_OK
    write_suppression_entries(args.path, kept)
    print(f"Pruned {len(removed)} entries from {args.path}.")
    return EXIT_OK


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(args)
    try:
        command = args.command
        if command == "list":
            return command_list(args)
        if command == "add":
            return command_add(args)
        if command == "validate":
            return command_validate(args)
        if command == "prune-stale":
            return command_prune_stale(args)
        raise ValueError(f"Unsupported command {command!r}.")
    except Exception as exc:
        logging.error("%s", exc)
        return EXIT_RUNTIME_ERROR


if __name__ == "__main__":
    sys.exit(main())
