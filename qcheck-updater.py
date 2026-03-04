#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

"""Review and optionally apply structured QC-derived collection updates."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path
from pprint import PrettyPrinter

import pandas as pd
from dotenv import load_dotenv
from molgenis_emx2.directory_client.directory_client import DirectorySession

from directory import Directory
from duo_terms import detect_duo_term_storage_style, normalize_duo_term_ids, serialize_duo_term_id
from fact_descriptor_sync import parse_collection_multi_value_field
from fix_proposals import EntityFixProposal, load_fix_plan
from nncontacts import NNContacts


load_dotenv()

DEFAULT_TARGET = os.getenv("DIRECTORYTARGET")
DEFAULT_USERNAME = os.getenv("DIRECTORYUSERNAME")
DEFAULT_PASSWORD = os.getenv("DIRECTORYPASSWORD")

MULTI_VALUE_FIELDS = {"data_use", "type", "diagnosis_available", "materials", "sex"}
INTEGER_FIELDS = {"age_low", "age_high", "size", "number_of_donors"}
SUPPORTED_ENTITY_TYPES = {"COLLECTION"}

EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_INPUT_ERROR = 2
EXIT_ABORTED = 3


class InputError(Exception):
    """Raised for user-facing input/configuration problems."""


class OperationAborted(Exception):
    """Raised when the user declines an interactive confirmation."""


class UpdateConflict(Exception):
    """Raised when incompatible fix proposals are selected together."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read a QC update-plan JSON file exported by data-check.py, filter the selected "
            "entity updates, list them in a human-readable form, or apply them to a staging schema."
        )
    )
    parser.add_argument("-i", "--input", required=True, help="Path to the JSON update-plan exported by data-check.py.")
    parser.add_argument(
        "-s",
        "--schema",
        required=True,
        help="Target staging-area schema to update (for example BBMRI-CZ or BBMRI-EU).",
    )
    parser.add_argument("--entity-id", help="Restrict to one exact entity ID.")
    parser.add_argument("--root-id", help="Restrict to one root biobank or collection ID hierarchy.")
    parser.add_argument("--staging-area", help="Comma-delimited staging-area filter (OR within the option).")
    parser.add_argument("--check-id", action="append", default=[], help="Restrict to one or more originating check IDs (repeat or comma-separate).")
    parser.add_argument("--update-id", action="append", default=[], help="Restrict to one or more update IDs (repeat or comma-separate).")
    parser.add_argument(
        "--module",
        action="append",
        default=[],
        help="Restrict to one or more fix modules/check-prefix families such as AP, CC, C19, FT, or TXT (repeat or comma-separate).",
    )
    parser.add_argument(
        "--confidence",
        default=None,
        help="Comma-delimited confidence filter. Supported values: certain, almost_certain, uncertain, all.",
    )
    parser.add_argument("--list", action="store_true", help="List selected updates in human-readable form without connecting to the staging schema.")
    parser.add_argument("-n", "--dry-run", action="store_true", help="Show what would be updated in the target schema without writing data.")
    parser.add_argument("-f", "--force", action="store_true", help="Apply all selected non-conflicting updates without interactive confirmation.")
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Allow replace/clear updates that remove or overwrite existing metadata values.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output.")
    parser.add_argument("-d", "--debug", action="store_true", help="Debug output. Implies verbose.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress non-error stdout output.")
    parser.add_argument(
        "--directory-target",
        default=DEFAULT_TARGET,
        help="Directory base URL (overrides DIRECTORYTARGET env var).",
    )
    parser.add_argument(
        "--directory-username",
        default=DEFAULT_USERNAME,
        help="Directory username (overrides DIRECTORYUSERNAME env var).",
    )
    parser.add_argument(
        "--directory-password",
        default=DEFAULT_PASSWORD,
        help="Directory password (overrides DIRECTORYPASSWORD env var).",
    )
    return parser


def configure_logging(args: argparse.Namespace) -> None:
    level = "ERROR" if args.quiet else ("DEBUG" if args.debug else "INFO")
    logging.basicConfig(level=level, format=" %(levelname)s: %(name)s: %(message)s")
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def validate_args(args: argparse.Namespace) -> None:
    if args.debug:
        args.verbose = True
    if not Path(args.input).exists():
        raise InputError(f"Update-plan file {args.input!r} does not exist.")
    if args.force and args.list:
        raise InputError("--force and --list cannot be used together.")
    if args.force and args.dry_run:
        raise InputError("--force and --dry-run cannot be used together.")
    if not args.list and (not args.directory_target or not args.directory_username or not args.directory_password):
        raise InputError(
            "Applying or simulating updates against a staging schema requires --directory-target, --directory-username, and --directory-password (or DIRECTORYTARGET/DIRECTORYUSERNAME/DIRECTORYPASSWORD in .env)."
        )


def confirm_action(prompt: str, *, force: bool) -> None:
    if force:
        return
    if not sys.stdin.isatty():
        raise OperationAborted(
            "Interactive confirmation required but stdin is not a TTY. Use --force to proceed."
        )
    sys.stderr.write(prompt + " [y/N]: ")
    sys.stderr.flush()
    response = sys.stdin.readline().strip().lower()
    if response not in {"y", "yes"}:
        raise OperationAborted("Operation cancelled by user.")


def prompt_yes_no(prompt: str, *, default_no: bool = True) -> bool:
    """Prompt the user for a yes/no decision and return the answer."""
    if not sys.stdin.isatty():
        raise OperationAborted(
            "Interactive confirmation required but stdin is not a TTY. Use --force to proceed."
        )
    suffix = " [y/N]: " if default_no else " [Y/n]: "
    sys.stderr.write(prompt + suffix)
    sys.stderr.flush()
    response = sys.stdin.readline().strip().lower()
    if not response:
        return not default_no
    return response in {"y", "yes"}


def _split_csv_values(raw_values: list[str] | str | None) -> set[str]:
    if raw_values is None:
        return set()
    if isinstance(raw_values, str):
        raw_values = [raw_values]
    values = set()
    for raw_value in raw_values:
        for part in str(raw_value).split(","):
            normalized = part.strip()
            if normalized:
                values.add(normalized)
    return values


def _module_filter_matches(update: EntityFixProposal, requested_modules: set[str]) -> bool:
    """Return True when requested module names match update modules or check prefixes."""
    if not requested_modules:
        return True
    candidates = {update.module}
    for check_id in update.source_check_ids:
        if ":" in check_id:
            candidates.add(check_id.split(":", 1)[0])
    return any(module in candidates for module in requested_modules)


def _confidence_filter(args: argparse.Namespace) -> set[str]:
    if args.confidence:
        requested = {value.strip() for value in args.confidence.split(",") if value.strip()}
        if "all" in requested:
            return {"certain", "almost_certain", "uncertain"}
        return requested
    if args.list:
        return {"certain", "almost_certain", "uncertain"}
    return {"certain", "almost_certain"}


def _load_eric_directory(args: argparse.Namespace) -> Directory:
    pp = PrettyPrinter(indent=2)
    return Directory(
        schema="ERIC",
        debug=args.debug,
        pp=pp,
        directory_url=args.directory_target,
        include_withdrawn_entities=True,
    )


def _entity_ids_for_root(directory: Directory, root_id: str) -> set[str]:
    if ":contactID:" in root_id:
        raise InputError("Contacts are not supported as hierarchy roots for update selection.")
    if ":collection:" in root_id:
        collection = directory.getCollectionById(root_id, raise_on_missing=True)
        descendants = set(directory.getCollectionsDescendants(collection["id"]))
        return descendants | {collection["id"]}
    biobank = directory.getBiobankById(root_id, raise_on_missing=True)
    graph = directory.getGraphBiobankCollectionsFromBiobank(biobank["id"])
    return set(graph.nodes())


def _filter_updates(args: argparse.Namespace, payload: dict, directory: Directory | None) -> list[EntityFixProposal]:
    entity_filter = args.entity_id
    root_filter = args.root_id
    root_entities = _entity_ids_for_root(directory, root_filter) if root_filter else None
    staging_filter = {value.upper() for value in _split_csv_values(args.staging_area)}
    check_filter = _split_csv_values(args.check_id)
    update_filter = _split_csv_values(args.update_id)
    module_filter = _split_csv_values(args.module)
    confidence_filter = _confidence_filter(args)

    selected = []
    for raw_update in payload.get("updates", []):
        update = EntityFixProposal.from_dict(raw_update)
        if entity_filter and update.entity_id != entity_filter:
            continue
        if root_entities is not None and update.entity_id not in root_entities:
            continue
        if staging_filter and update.staging_area.upper() not in staging_filter:
            continue
        if check_filter and not any(check_id in check_filter for check_id in update.source_check_ids):
            continue
        if update_filter and update.update_id not in update_filter:
            continue
        if not _module_filter_matches(update, module_filter):
            continue
        if update.confidence not in confidence_filter:
            continue
        selected.append(update)
    return selected


def _normalize_scalar(value):
    if value in (None, ""):
        return None
    return value


def _normalize_live_row_value(row: dict, field: str):
    value = row.get(field)
    if field in MULTI_VALUE_FIELDS:
        values = parse_collection_multi_value_field(value)
        if field == "data_use":
            return normalize_duo_term_ids(values)
        return values
    if field in INTEGER_FIELDS:
        if value in (None, ""):
            return None
        return int(value)
    return _normalize_scalar(value)


def _canonical_field_value(field: str, value):
    """Return a comparison-stable value for one field."""
    if field in MULTI_VALUE_FIELDS:
        if value in (None, ""):
            return []
        values = parse_collection_multi_value_field(value)
        if field == "data_use":
            values = normalize_duo_term_ids(values)
        return sorted(str(item) for item in values)
    if field in INTEGER_FIELDS:
        if value in (None, ""):
            return None
        return int(value)
    return _normalize_scalar(value)


def _render_value(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "<empty>"
    if value in (None, ""):
        return "<empty>"
    return str(value)


def _render_field_value(field: str, value) -> str:
    """Return a display-stable value for one field."""
    return _render_value(_canonical_field_value(field, value))


def _effective_field_value(field: str, current_value, update: EntityFixProposal):
    """Return the effective post-update value for display/review purposes."""
    if update.mode == "append" and field in MULTI_VALUE_FIELDS:
        merged = list(_canonical_field_value(field, current_value))
        for value in _canonical_field_value(field, update.proposed_value):
            if value not in merged:
                merged.append(value)
        return merged
    return update.proposed_value


def _merge_updates(selected_updates: list[EntityFixProposal]) -> tuple[list[EntityFixProposal], list[str]]:
    grouped = defaultdict(list)
    conflicts = []
    for update in selected_updates:
        grouped[(update.entity_id, update.field)].append(update)

    merged_updates = []
    for (entity_id, field), updates in grouped.items():
        group_conflicts = []
        exclusive_groups = defaultdict(list)
        for update in updates:
            if update.exclusive_group:
                exclusive_groups[update.exclusive_group].append(update)
        for group_name, group_updates in exclusive_groups.items():
            if len(group_updates) > 1:
                group_conflicts.append(
                    f"{entity_id} field {field} has mutually exclusive updates in group {group_name}: "
                    + ", ".join(update.update_id for update in group_updates)
                )
        if group_conflicts:
            conflicts.extend(group_conflicts)
            continue

        modes = {update.mode for update in updates}
        if len(modes) > 1:
            conflicts.append(
                f"{entity_id} field {field} has incompatible update modes: "
                + ", ".join(sorted(modes))
            )
            continue
        mode = next(iter(modes))
        if mode == "append" and field in MULTI_VALUE_FIELDS:
            base = updates[0]
            proposed_values = []
            source_check_ids = []
            source_messages = []
            source_actions = []
            term_explanations = []
            confidences = []
            blocking_reasons = []
            for update in updates:
                if _canonical_field_value(field, update.current_value_at_export) != _canonical_field_value(field, base.current_value_at_export):
                    conflicts.append(f"{entity_id} field {field} has inconsistent expected current values across append updates.")
                    break
                for value in update.proposed_value:
                    if value not in proposed_values:
                        proposed_values.append(value)
                for check_id in update.source_check_ids:
                    if check_id not in source_check_ids:
                        source_check_ids.append(check_id)
                for message in update.source_warning_messages:
                    if message not in source_messages:
                        source_messages.append(message)
                for action in update.source_warning_actions:
                    if action not in source_actions:
                        source_actions.append(action)
                for explanation in update.term_explanations:
                    if explanation not in term_explanations:
                        term_explanations.append(explanation)
                confidences.append(update.confidence)
                if update.blocking_reason:
                    blocking_reasons.append(update.blocking_reason)
            else:
                base.proposed_value = proposed_values
                base.source_check_ids = source_check_ids
                base.source_warning_messages = source_messages
                base.source_warning_actions = source_actions
                base.term_explanations = term_explanations
                if "uncertain" in confidences:
                    base.confidence = "uncertain"
                elif "almost_certain" in confidences:
                    base.confidence = "almost_certain"
                else:
                    base.confidence = "certain"
                if blocking_reasons:
                    base.blocking_reason = " ".join(dict.fromkeys(blocking_reasons))
                base.finalize_checksum()
                merged_updates.append(base)
            continue

        unique_payloads = {
            (_canonical_field_value(field, update.proposed_value), update.confidence)
            for update in updates
        }
        if len(unique_payloads) > 1:
            conflicts.append(
                f"{entity_id} field {field} has conflicting target values: "
                + ", ".join(sorted(update.update_id for update in updates))
            )
            continue
        merged_updates.append(updates[0])
    return merged_updates, conflicts


def _list_updates(selected_updates: list[EntityFixProposal], *, verbose: bool) -> None:
    by_entity = defaultdict(list)
    for update in selected_updates:
        by_entity[update.entity_id].append(update)

    for entity_id in sorted(by_entity):
        print(entity_id)
        for update in sorted(by_entity[entity_id], key=lambda item: (item.module, item.field, item.update_id)):
            effective_value = _effective_field_value(update.field, update.current_value_at_export, update)
            print(
                f"  [{update.confidence}] {update.module}/{update.update_id} -> {update.field}: "
                f"{_render_field_value(update.field, update.current_value_at_export)} -> {_render_field_value(update.field, effective_value)}"
            )
            if update.mode == "append":
                print(f"    add: {_render_field_value(update.field, update.proposed_value)}")
            print(f"    checks: {', '.join(update.source_check_ids)}")
            print(f"    why: {update.human_explanation}")
            if update.term_explanations:
                for explanation in update.term_explanations:
                    print(
                        f"    term: {explanation['term_id']} = {explanation['label']} -- {explanation['definition']}"
                    )
            if verbose and update.rationale:
                print(f"    rationale: {update.rationale}")
            if update.blocking_reason:
                print(f"    note: {update.blocking_reason}")
        print("")


def _review_updates_interactively(
    updates: list[EntityFixProposal],
    live_rows: dict[str, dict],
    *,
    verbose: bool,
) -> list[EntityFixProposal]:
    """Return the subset of updates approved interactively by the user."""
    approved_updates = []
    total = len(updates)
    for index, update in enumerate(updates, start=1):
        live_value = _normalize_live_row_value(live_rows[update.entity_id], update.field)
        effective_value = _effective_field_value(update.field, live_value, update)
        sys.stderr.write(
            f"Review {index}/{total}: {update.entity_id} [{update.confidence}] {update.module}/{update.update_id}\n"
        )
        sys.stderr.write(f"  field: {update.field}\n")
        sys.stderr.write(f"  live: {_render_field_value(update.field, live_value)}\n")
        sys.stderr.write(f"  expected at export: {_render_field_value(update.field, update.expected_current_value)}\n")
        sys.stderr.write(f"  target after update: {_render_field_value(update.field, effective_value)}\n")
        if update.mode == "append":
            sys.stderr.write(f"  add: {_render_field_value(update.field, update.proposed_value)}\n")
        sys.stderr.write(f"  checks: {', '.join(update.source_check_ids)}\n")
        sys.stderr.write(f"  why: {update.human_explanation}\n")
        if update.term_explanations:
            for explanation in update.term_explanations:
                sys.stderr.write(
                    f"  term: {explanation['term_id']} = {explanation['label']} -- {explanation['definition']}\n"
                )
        if verbose and update.rationale:
            sys.stderr.write(f"  rationale: {update.rationale}\n")
        if update.blocking_reason:
            sys.stderr.write(f"  note: {update.blocking_reason}\n")
        if prompt_yes_no("  Select this update?", default_no=True):
            approved_updates.append(update)
        sys.stderr.write("\n")
    return approved_updates


def _fetch_target_rows(session: DirectorySession, schema: str, entity_ids: list[str]) -> tuple[pd.DataFrame, dict[str, dict]]:
    table_df = session.get(table="Collections", schema=schema, as_df=True)
    rows = {}
    for entity_id in entity_ids:
        row_df = table_df[table_df["id"].astype(str) == entity_id]
        if row_df.empty:
            raise InputError(f"Collection {entity_id!r} does not exist in schema {schema!r}; no update was applied.")
        rows[entity_id] = row_df.iloc[0].to_dict()
    return table_df, rows


def _apply_update_to_row(row: dict, update: EntityFixProposal) -> dict:
    updated = dict(row)
    if update.field in MULTI_VALUE_FIELDS:
        current_values = parse_collection_multi_value_field(updated.get(update.field))
        proposed_values = list(update.proposed_value)
        if update.field == "data_use":
            storage_style = detect_duo_term_storage_style(current_values)
            current_values = [serialize_duo_term_id(value, style=storage_style) for value in normalize_duo_term_ids(current_values)]
            proposed_values = [serialize_duo_term_id(value, style=storage_style) for value in normalize_duo_term_ids(proposed_values)]
        if update.mode == "append":
            merged = list(current_values)
            for value in proposed_values:
                if value not in merged:
                    merged.append(value)
            updated[update.field] = ",".join(merged)
        elif update.mode == "replace":
            updated[update.field] = ",".join(proposed_values)
        elif update.mode == "clear":
            updated[update.field] = ""
        else:
            raise InputError(f"Unsupported multi-value update mode {update.mode!r} for field {update.field!r}.")
        return updated

    if update.mode == "clear":
        updated[update.field] = ""
        return updated
    if update.mode in {"set", "replace", "enable_flag", "disable_flag"}:
        value = update.proposed_value
        updated[update.field] = "" if value is None else str(value)
        return updated
    raise InputError(f"Unsupported scalar update mode {update.mode!r} for field {update.field!r}.")


def _schema_consistency_warning(args: argparse.Namespace, selected_updates: list[EntityFixProposal]) -> None:
    staging_areas = {update.staging_area for update in selected_updates if update.staging_area}
    expected_schemas = {NNContacts.expected_schema_name(code) for code in staging_areas if code}
    if expected_schemas and args.schema not in expected_schemas:
        logging.warning(
            "Selected updates target staging areas %s, so expected schema(s) are %s; requested schema is %s.",
            ", ".join(sorted(staging_areas)),
            ", ".join(sorted(expected_schemas)),
            args.schema,
        )
        confirm_action(
            f"Proceed with schema {args.schema} even though the selected updates suggest {', '.join(sorted(expected_schemas))}?",
            force=args.force,
        )


def run_updater(args: argparse.Namespace) -> int:
    plan = load_fix_plan(args.input)
    for issue in plan.issues:
        logging.warning("%s", issue)

    needs_directory = bool(args.root_id)
    directory = _load_eric_directory(args) if needs_directory else None
    selected_updates = _filter_updates(args, plan.payload, directory)
    if not selected_updates:
        logging.info("No updates matched the selected filters.")
        return EXIT_OK

    _list_updates(selected_updates, verbose=args.verbose or args.debug)
    if args.list:
        return EXIT_OK

    unsupported = [update for update in selected_updates if update.entity_type not in SUPPORTED_ENTITY_TYPES]
    if unsupported:
        unsupported_ids = ", ".join(sorted({f"{update.entity_type}:{update.entity_id}" for update in unsupported}))
        raise InputError(
            "The current updater implementation supports collection updates only. Unsupported selected updates: "
            + unsupported_ids
        )

    _schema_consistency_warning(args, selected_updates)
    merged_updates, conflicts = _merge_updates(selected_updates)
    for conflict in conflicts:
        logging.warning("%s", conflict)
    if not merged_updates:
        logging.info("All selected updates are conflicting or unsupported; nothing to apply.")
        return EXIT_OK

    with DirectorySession(url=args.directory_target) as session:
        session.signin(args.directory_username, args.directory_password)
        entity_ids = sorted({update.entity_id for update in merged_updates})
        table_df, live_rows = _fetch_target_rows(session, args.schema, entity_ids)
        updated_rows = []
        mismatch_updates = []
        skipped_replace_required = []
        for update in merged_updates:
            live_value = _normalize_live_row_value(live_rows[update.entity_id], update.field)
            if _canonical_field_value(update.field, live_value) != _canonical_field_value(update.field, update.expected_current_value):
                mismatch_updates.append(update)
            if update.replace_required and not args.replace_existing:
                skipped_replace_required.append(update)
                continue
            updated_rows.append(update)

        if skipped_replace_required:
            for update in skipped_replace_required:
                logging.warning(
                    "Skipping %s for %s because it requires --replace-existing.",
                    update.update_id,
                    update.entity_id,
                )

        if mismatch_updates:
            for update in mismatch_updates:
                logging.warning(
                    "Live value mismatch for %s on %s.%s: expected %s but found %s.",
                    update.update_id,
                    update.entity_id,
                    update.field,
                    _render_field_value(update.field, update.expected_current_value),
                    _render_field_value(update.field, _normalize_live_row_value(live_rows[update.entity_id], update.field)),
                )
            confirm_action(
                f"Proceed even though {len(mismatch_updates)} selected updates no longer match the exported expected values?",
                force=args.force,
            )

        if not args.force:
            updated_rows = _review_updates_interactively(
                updated_rows,
                live_rows,
                verbose=args.verbose or args.debug,
            )
            if not updated_rows:
                logging.info("No updates were approved during interactive review.")
                return EXIT_OK

        confirm_action(
            (
                f"Dry run selected {len(updated_rows)} update(s) for schema {args.schema}. Proceed with the simulated apply?"
                if args.dry_run
                else f"Apply {len(updated_rows)} update(s) to schema {args.schema}?"
            ),
            force=args.force,
        )

        if args.dry_run:
            logging.info("Dry run enabled. No data was written.")
            return EXIT_OK

        updated_df = table_df.copy()
        changed_entity_ids = set()
        for update in updated_rows:
            current_row = live_rows[update.entity_id]
            next_row = _apply_update_to_row(current_row, update)
            if next_row == current_row:
                continue
            live_rows[update.entity_id] = next_row
            changed_entity_ids.add(update.entity_id)
            updated_df.loc[updated_df["id"].astype(str) == update.entity_id, list(next_row.keys())] = pd.Series(next_row)

        if not changed_entity_ids:
            logging.info("All approved updates were no-ops against the live data. Nothing was written.")
            return EXIT_OK

        changed_rows = updated_df[updated_df["id"].astype(str).isin(changed_entity_ids)]
        session.save_table(table="Collections", schema=args.schema, data=changed_rows)
        logging.info("Applied %d update(s) affecting %d collection(s) in schema %s.", len(updated_rows), len(changed_entity_ids), args.schema)
    return EXIT_OK


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(args)
    try:
        validate_args(args)
        return run_updater(args)
    except OperationAborted as exc:
        logging.error("%s", exc)
        return EXIT_ABORTED
    except InputError as exc:
        logging.error("%s", exc)
        return EXIT_INPUT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
