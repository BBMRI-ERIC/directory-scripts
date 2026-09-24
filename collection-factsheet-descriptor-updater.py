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

from cli_interrupts import log_keyboard_interrupt
from directory import Directory
from directory_session_compat import DirectorySession
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
DEFAULT_TOKEN = os.getenv("DIRECTORYTOKEN")

EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_INPUT_ERROR = 2
EXIT_ABORTED = 3


class InputError(Exception):
    """Raised for user-facing input/configuration problems."""


class OperationAborted(Exception):
    """Raised when the user declines an interactive confirmation."""


def build_parser() -> argparse.ArgumentParser:
    """Build the collection fact-sheet descriptor updater CLI parser.

    Returns:
        Parser defining ERIC source selection, staging-schema authentication,
        replacement authority, logging, dry-run, and confirmation controls.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Analyze one collection in the ERIC schema of the configured Directory target, "
            "derive descriptor updates from its fact sheet, and optionally apply the changes "
            "to the corresponding staging-area Collections table."
        )
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
        "--replace-existing",
        action="store_true",
        help=(
            "Allow removal/replacement of existing multi-value descriptors that are not "
            "supported by the fact sheet. Without this option, only missing values are added."
        ),
    )
    parser.add_argument(
        "--directory-token",
        default=DEFAULT_TOKEN,
        help="Directory access token (overrides DIRECTORYTOKEN env var, alternative to username/password).",
    )
    parser.add_argument(
        "--suppress-validation-warnings",
        action="store_true",
        help="reserved for suppressing non-fatal local validation warnings",
    )
    return parser


def confirm_action(prompt: str, *, force: bool) -> None:
    """Require explicit terminal approval unless force mode is enabled.

    Args:
        prompt: Schema-mismatch or final-write question sent to standard error.
        force: Whether to approve without reading stdin.

    Returns:
        None. Interactive continuation requires ``y`` or ``yes``.

    Raises:
        OperationAborted: If stdin is not a TTY or the response is not
            affirmative.
    """
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
    """Configure root and HTTP logging from quiet/debug CLI flags.

    Args:
        args: Parsed namespace containing ``quiet`` and ``debug``.

    Returns:
        None. Root logging uses ERROR, DEBUG, or INFO; HTTP libraries use
        WARNING.
    """
    level = "ERROR" if args.quiet else ("DEBUG" if args.debug else "INFO")
    logging.basicConfig(level=level, format=" %(levelname)s: %(name)s: %(message)s")
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def validate_args(args: argparse.Namespace) -> None:
    """Validate collection, schema, target, and write authentication settings.

    Args:
        args: Parsed namespace containing collection ID, target schema, target
            URL, and token or username/password credentials.

    Returns:
        None. Validation performs no Directory reads or writes.

    Raises:
        InputError: If required identifiers, target settings, or credentials do
            not satisfy the shared updater settings model.
    """
    try:
        FactsheetUpdaterSettingsModel.parse_obj(
            {
                "schema": args.schema,
                "collection_id": args.collection_id,
                "directory_target": args.directory_target,
                "directory_username": args.directory_username,
                "directory_password": args.directory_password,
                "directory_token": args.directory_token,
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
    """Read Collections from a staging schema and select one exact ID.

    Args:
        session: Authenticated Directory client used for the table read.
        schema: Staging schema containing the writable Collections table.
        collection_id: Exact collection ID to select.

    Returns:
        Pair of the complete Collections frame and the first matching row. The
        returned series retains every table column needed for a full-width save.

    Raises:
        InputError: If the collection is absent from the target schema.
    """
    table_df = session.get(table="Collections", schema=schema, as_df=True)
    row_df = table_df[table_df["id"].astype(str) == collection_id]
    if row_df.empty:
        raise InputError(
            f"Collection {collection_id!r} does not exist in schema {schema!r}; no update was applied."
        )
    return table_df, row_df.iloc[0]


def render_change_value(value) -> str:
    """Render descriptor values for concise proposal logging.

    Args:
        value: Descriptor list, scalar, or blank value.

    Returns:
        Comma-joined list text, ``<empty>`` for empty values, or scalar text.
    """
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
    """Log proposed descriptor changes and optional fact-derived evidence.

    Args:
        collection_id: Collection receiving the proposed staging update.
        schema: Target staging schema shown in the summary.
        proposal: Descriptor proposal containing ``changes``, derived
            ``fact_values``, all-star presence, and notes.
        verbose: Whether to log derived diagnoses, materials, sex, all-star
            presence, and proposal notes in addition to changed fields.

    Returns:
        None. This function only emits logs and does not change local or remote
        data.
    """
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
    """Convert the live staging row to the proposal helper's mapping shape.

    Args:
        target_row: Full-width Collections row fetched from the target schema.

    Returns:
        New dictionary containing the row's columns and live values.
    """
    return target_row.to_dict()


def update_collection_from_facts(args: argparse.Namespace) -> int:
    """Derive ERIC fact descriptors and optionally update one staging row.

    The source side purges and refreshes the local Directory cache for a public
    ERIC snapshot without signing in, verifies the collection, and requires at
    least one CollectionFacts row. Thus dry-run may still replace that runtime
    cache even though it creates no report or update file.
    The write side authenticates separately, reads the exact collection from
    the requested staging schema, and derives changes against that live row.
    Without ``--replace-existing``, multivalue diagnosis, material, and sex
    descriptors are append-only; numeric all-star totals may still be replaced
    according to the shared proposal helper.

    A collection-prefix/schema mismatch requires its own ``y``/``yes`` prompt
    unless force is active. Dry-run logs the concrete proposal and returns
    before the final prompt and remote save. A real update prompts once more,
    then saves one full-width Collections row. The save has no rollback; client
    read, authentication, cache, and write failures propagate unchanged.

    Args:
        args: Validated target, collection, schema, authentication, replacement,
            dry-run, force, and logging settings.

    Returns:
        ``EXIT_OK`` when no change is needed, dry-run completes, or the remote
        Collections save succeeds.

    Raises:
        InputError: If ERIC has no fact rows or the target schema lacks the
            collection.
        OperationAborted: If required mismatch or write approval is unavailable
            or declined.
        KeyError: If the collection is absent from the fresh ERIC snapshot.
    """
    pp = PrettyPrinter(indent=2)
    if args.debug:
        logging.debug("Preparing live ERIC analysis snapshot for %s.", args.collection_id)
    directory_kwargs = dict(
        schema="ERIC",
        purgeCaches=["directory"],
        debug=args.debug,
        pp=pp,
        directory_url=args.directory_target,
        include_withdrawn_entities=True,
    )
    directory_token = getattr(args, "directory_token", None)
    if directory_token:
        directory_kwargs["token"] = directory_token
    eric_directory = Directory(**directory_kwargs)
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

    client_kwargs = {"url": args.directory_target}
    if directory_token:
        client_kwargs["token"] = directory_token
    with DirectorySession(**client_kwargs) as session:
        if directory_token:
            logging.debug("Using token-based authentication.")
        else:
            if args.debug:
                logging.debug("Signing in to Directory as %s.", args.directory_username)
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
    """Run the CLI and map expected validation or refusal failures to status.

    Returns:
        0 on success, 2 for invalid input, or 3 for declined/Ctrl+C operations.
        Unexpected Directory and filesystem failures propagate visibly.
    """
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
    except KeyboardInterrupt:
        log_keyboard_interrupt("collection-factsheet-descriptor-updater.py", action="interactive review/apply")
        return EXIT_ABORTED
    except InputError as exc:
        logging.error("%s", exc)
        return EXIT_INPUT_ERROR


if __name__ == "__main__":
    sys.exit(main())
