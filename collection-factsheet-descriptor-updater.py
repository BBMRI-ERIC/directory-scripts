#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

"""Propose and optionally apply collection descriptor updates from fact sheets."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from pprint import PrettyPrinter

import pandas as pd
from dotenv import load_dotenv
from molgenis_emx2.directory_client.directory_client import DirectorySession

from directory import Directory
from fact_descriptor_sync import (
    apply_descriptor_proposal_to_dataframe_row,
    build_collection_descriptor_proposal,
)
from nncontacts import NNContacts
from validation_helpers import format_validation_error
from validation_models import FactsheetUpdaterSettingsModel, ValidationError


load_dotenv()

DEFAULT_TARGET = os.getenv("DIRECTORYTARGET")
DEFAULT_USERNAME = os.getenv("DIRECTORYUSERNAME")
DEFAULT_PASSWORD = os.getenv("DIRECTORYPASSWORD")

EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_INPUT_ERROR = 2
EXIT_ABORTED = 3


class InputError(Exception):
    """Raised for user-facing input/configuration problems."""


class OperationAborted(Exception):
    """Raised when the user declines an interactive confirmation."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze one collection in the ERIC schema of the configured Directory target, "
            "derive descriptor updates from its fact sheet, and optionally apply the changes "
            "to the corresponding staging-area Collections table."
        )
    )
    parser.add_argument("-c", "--collection-id", required=True, help="Collection ID to analyze.")
    parser.add_argument(
        "-s",
        "--schema",
        required=True,
        help=(
            "Target staging-area schema to update (for example BBMRI-CZ or BBMRI-EU). "
            "The script analyzes facts from ERIC in the configured Directory target but "
            "writes to this schema."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output including derived fact-sheet values and notes.",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Debug output. Implies verbose and includes connection/auth details.",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Show proposed changes without writing them.",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Skip interactive confirmations and attempt the update directly.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress non-error stdout output.",
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help=(
            "Allow removal/replacement of existing multi-value descriptors that are not "
            "supported by the fact sheet. Without this option, only missing values are added."
        ),
    )
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
    parser.add_argument(
        "--suppress-validation-warnings",
        action="store_true",
        help="reserved for suppressing non-fatal local validation warnings",
    )
    return parser


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


def configure_logging(args: argparse.Namespace) -> None:
    level = "ERROR" if args.quiet else ("DEBUG" if args.debug else "INFO")
    logging.basicConfig(level=level, format=" %(levelname)s: %(name)s: %(message)s")
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def validate_args(args: argparse.Namespace) -> None:
    try:
        FactsheetUpdaterSettingsModel.parse_obj(
            {
                "schema": args.schema,
                "collection_id": args.collection_id,
                "directory_target": args.directory_target,
                "directory_username": args.directory_username,
                "directory_password": args.directory_password,
            }
        )
    except ValidationError as exc:
        raise InputError(
            format_validation_error(
                "Invalid collection-factsheet-descriptor-updater settings",
                exc,
            )
        ) from exc


def fetch_target_collection_row(
    session: DirectorySession,
    *,
    schema: str,
    collection_id: str,
) -> tuple[pd.DataFrame, pd.Series]:
    table_df = session.get(table="Collections", schema=schema, as_df=True)
    row_df = table_df[table_df["id"].astype(str) == collection_id]
    if row_df.empty:
        raise InputError(
            f"Collection {collection_id!r} does not exist in schema {schema!r}; no update was applied."
        )
    return table_df, row_df.iloc[0]


def render_change_value(value) -> str:
    if isinstance(value, list):
        return ",".join(value) if value else "<empty>"
    if value in (None, ""):
        return "<empty>"
    return str(value)


def log_proposal(
    collection_id: str,
    schema: str,
    proposal: dict,
    *,
    verbose: bool,
) -> None:
    logging.info("Proposed descriptor updates for %s in schema %s:", collection_id, schema)
    for change in proposal["changes"]:
        logging.info(
            "  %s: %s -> %s",
            change["field"],
            render_change_value(change["current"]),
            render_change_value(change["proposed"]),
        )
    if verbose:
        fact_values = proposal["fact_values"]
        logging.info("Derived fact diagnoses: %s", render_change_value(fact_values["diagnosis_available"]))
        logging.info("Derived fact materials: %s", render_change_value(fact_values["materials"]))
        logging.info("Derived fact sex values: %s", render_change_value(fact_values["sex"]))
        logging.info("All-star row present: %s", proposal["all_star_row_present"])
        for note in proposal["notes"]:
            logging.info("Note: %s", note)


def build_target_collection_for_proposal(target_row: pd.Series) -> dict:
    return target_row.to_dict()


def update_collection_from_facts(args: argparse.Namespace) -> int:
    pp = PrettyPrinter(indent=2)
    if args.debug:
        logging.debug("Preparing live ERIC analysis snapshot for %s.", args.collection_id)
    eric_directory = Directory(
        schema="ERIC",
        purgeCaches=["directory"],
        debug=args.debug,
        pp=pp,
        directory_url=args.directory_target,
        include_withdrawn_entities=True,
    )
    eric_directory.getCollectionById(args.collection_id, raise_on_missing=True)
    facts = eric_directory.getCollectionFacts(args.collection_id)
    if not facts:
        raise InputError(f"Collection {args.collection_id!r} has no fact-sheet rows in ERIC.")

    staging_area = NNContacts.extract_staging_area(args.collection_id)
    expected_schema = NNContacts.expected_schema_name(staging_area)
    if expected_schema and not NNContacts.schema_matches_staging_area(args.schema, staging_area):
        logging.warning(
            "Collection %s uses staging prefix %s, so the expected schema is %s; requested schema is %s.",
            args.collection_id,
            staging_area,
            expected_schema,
            args.schema,
        )
        confirm_action(
            f"Proceed with schema {args.schema} even though {args.collection_id} suggests {expected_schema}?",
            force=args.force,
        )

    if args.debug:
        logging.debug("Connecting to Directory target %s.", args.directory_target)
        logging.debug("Directory username: %s", args.directory_username)
        logging.debug("Directory password: %s", args.directory_password)

    with DirectorySession(url=args.directory_target) as session:
        session.signin(args.directory_username, args.directory_password)
        _, target_row = fetch_target_collection_row(
            session,
            schema=args.schema,
            collection_id=args.collection_id,
        )
        proposal = build_collection_descriptor_proposal(
            build_target_collection_for_proposal(target_row),
            facts,
            replace_existing=args.replace_existing,
        )

        if not proposal["changes"]:
            logging.info("No descriptor changes are needed for %s.", args.collection_id)
            return EXIT_OK

        log_proposal(
            args.collection_id,
            args.schema,
            proposal,
            verbose=args.verbose or args.debug,
        )

        if args.dry_run:
            logging.info("Dry run enabled. No data was written.")
            return EXIT_OK

        confirm_action(
            f"Apply {len(proposal['changes'])} descriptor update(s) to {args.collection_id} in schema {args.schema}?",
            force=args.force,
        )

        updated_row = apply_descriptor_proposal_to_dataframe_row(target_row.to_dict(), proposal)
        session.save_table(
            table="Collections",
            schema=args.schema,
            data=pd.DataFrame([updated_row]),
        )
        logging.info("Updated %s in schema %s.", args.collection_id, args.schema)
    return EXIT_OK


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.debug:
        args.verbose = True
    configure_logging(args)
    try:
        validate_args(args)
        return update_collection_from_facts(args)
    except OperationAborted as exc:
        logging.error("%s", exc)
        return EXIT_ABORTED
    except InputError as exc:
        logging.error("%s", exc)
        return EXIT_INPUT_ERROR


if __name__ == "__main__":
    sys.exit(main())
