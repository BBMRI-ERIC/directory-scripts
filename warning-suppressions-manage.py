#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

"""Manage warning-suppressions.json entries safely."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from cli_interrupts import log_keyboard_interrupt
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
    """Build subcommands for listing, adding, validating, and pruning entries.

    Returns:
        Parser with a shared suppression path and command-specific filters,
        metadata, strictness, cutoff-date, and dry-run options.
    """
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
        "--warning-only",
        action="store_true",
        help="Suppress only the runtime warning, not attached fix proposals.",
    )
    add_parser.add_argument(
        "--fix-only",
        action="store_true",
        help="Suppress only attached fix proposals, not the runtime warning.",
    )
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
    """Configure warning, verbose, or debug logging for a command.

    Args:
        args: Parsed namespace whose debug flag also enables verbose mode.

    Returns:
        None. Root logging is configured with a compact level/message format.
    """
    if args.debug:
        args.verbose = True
    level = logging.DEBUG if args.debug else (logging.INFO if args.verbose else logging.WARNING)
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def _load_entries(path: str | Path) -> list[WarningSuppressionEntryModel]:
    """Load canonical or legacy suppression JSON and log parser diagnostics.

    Args:
        path: JSON file to read. A missing file is handled by the shared loader
            according to its empty/default semantics.

    Returns:
        Validated suppression entries in source order. Recoverable loader
        issues are emitted as warnings.
    """
    issues: list[str] = []
    result = load_warning_suppressions_detailed(path, warn=issues.append)
    for issue in issues:
        logging.warning("%s", issue)
    return result.entries


def _entry_key(entry: WarningSuppressionEntryModel) -> tuple[str, str]:
    """Return the identity used for suppression upserts and duplicate checks.

    Args:
        entry: Validated suppression record.

    Returns:
        Pair of exact check ID and entity ID.
    """
    return (entry.check_id, entry.entity_id)


def _parse_entry_from_args(args: argparse.Namespace) -> WarningSuppressionEntryModel:
    """Build one validated suppression record from ``add`` arguments.

    Args:
        args: Add-command namespace containing target IDs, optional metadata,
            dates, and warning-only/fix-only switches. A blank ``added_on`` is
            replaced with today's ISO date.

    Returns:
        Validated canonical entry. By default it suppresses both the warning
        and attached fixes; the exclusive switches narrow that target.

    Raises:
        ValueError: If both target switches are supplied or any field fails the
            suppression model's format and semantic validation.
    """
    added_on = args.added_on.strip() if isinstance(args.added_on, str) else args.added_on
    if not added_on:
        added_on = date.today().isoformat()
    if args.warning_only and args.fix_only:
        raise ValueError("Use either --warning-only or --fix-only, not both.")
    suppress_warning = not args.fix_only
    suppress_fix = not args.warning_only
    payload = {
        "check_id": args.check_id,
        "entity_id": args.entity_id,
        "entity_type": args.entity_type,
        "suppress_warning": suppress_warning,
        "suppress_fix": suppress_fix,
        "reason": args.reason,
        "added_by": args.added_by,
        "added_on": added_on,
        "expires_on": args.expires_on,
        "ticket": args.ticket,
    }
    return WarningSuppressionEntryModel.parse_obj(payload)


def command_list(args: argparse.Namespace) -> int:
    """Print suppression entries, optionally filtered by exact check ID.

    Args:
        args: List-command namespace containing input path and optional check
            ID filter.

    Returns:
        ``EXIT_OK`` after printing sorted human-readable entries or an empty
        message. The JSON file is read but never changed.
    """
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
        targets = []
        if entry.suppress_warning:
            targets.append("warning")
        if entry.suppress_fix:
            targets.append("fix")
        pieces.append(f"targets={','.join(targets) if targets else 'none'}")
        if entry.reason:
            pieces.append(f"reason={entry.reason}")
        if entry.expires_on:
            pieces.append(f"expires={entry.expires_on}")
        if entry.ticket:
            pieces.append(f"ticket={entry.ticket}")
        print(" | ".join(pieces))
    return EXIT_OK


def command_add(args: argparse.Namespace) -> int:
    """Add or replace one suppression entry and rewrite canonical JSON.

    Args:
        args: Add-command namespace containing file path, entry fields, target
            switches, and the optional no-upsert guard.

    Returns:
        ``EXIT_OK`` after the local suppression file is rewritten in place and
        an Added/Updated message is printed. There is no prompt, dry-run mode,
        remote write, or rollback; a failed direct write can leave a partial
        file.

    Raises:
        ValueError: If the entry is invalid, warning-only and fix-only conflict,
            or no-upsert forbids replacement of an existing key.
        OSError: If the suppression file cannot be read or rewritten.
    """
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
    """Report metadata and duplicate-key diagnostics without changing the file.

    Args:
        args: Validate-command namespace containing path and strict flag.

    Returns:
        ``EXIT_INPUT_ERROR`` only when diagnostics exist in strict mode;
        otherwise ``EXIT_OK`` after printing entry and diagnostic counts.
    """
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
    """Remove entries whose valid expiration date is before a cutoff date.

    Args:
        args: Prune-command namespace containing suppression path, ISO cutoff,
            and dry-run flag. Entries expiring on the cutoff are retained, as
            are entries with blank or invalid expiration dates.

    Returns:
        ``EXIT_OK`` when nothing is stale, after previewing stale entries, or
        after rewriting the local JSON in place with retained entries. Dry-run
        performs no write. This command has no prompt, remote effect, or
        rollback, and a failed direct write can leave a partial file.

    Raises:
        ValueError: If the cutoff is not a valid ISO date.
        OSError: If the suppression file cannot be read or rewritten.
    """
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
    """Dispatch one suppression command and convert failures to CLI status.

    Returns:
        The selected command's status, or ``EXIT_RUNTIME_ERROR`` after logging
        Ctrl+C, validation, parsing, filesystem, or unsupported-command errors.
        Commands never contact the Directory and never ask for confirmation.
    """
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
    except KeyboardInterrupt:
        log_keyboard_interrupt("warning-suppressions-manage.py", action="command execution")
        return EXIT_RUNTIME_ERROR
    except Exception as exc:
        logging.error("%s", exc)
        return EXIT_RUNTIME_ERROR


if __name__ == "__main__":
    sys.exit(main())
