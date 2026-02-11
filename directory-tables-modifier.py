#!/usr/bin/python3

# Imports
import argparse
import asyncio
import csv
import logging
import os
import re
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from molgenis_emx2.directory_client.directory_client import DirectorySession

# Get credentials from .env
load_dotenv()

target = os.getenv("DIRECTORYTARGET")
username = os.getenv("DIRECTORYUSERNAME")
password = os.getenv("DIRECTORYPASSWORD")

# Get args from stdin
parser = argparse.ArgumentParser(description="Script for modifying/adding or deleting records from tables in BBMRI Directory staging area. Make sure you have an .env file in this folder, containing: DIRECTORYTARGET, DIRECTORYUSERNAME, DIRECTORYPASSWORD.")

# Keep these immediately after -h in help output
parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output. Includes detailed records to be added/deleted.")
parser.add_argument("-d", "--debug", action="store_true", help="Debug output. Implies verbose and includes connection/auth details.")
parser.add_argument("-n", "--dry-run", action="store_true", help="Show planned changes without modifying data.")
parser.add_argument("-f", "--force", action="store_true", help="Skip interactive approval for deletions.")
parser.add_argument("-q", "--quiet", action="store_true", help="Suppress non-error output on STDOUT.")

parser.add_argument("-s", "--schema", type=str, required=True, help="Schema (staging area name shown in Molgenis Navigator, e.g., BBMRI-EU).")

parser.add_argument("--directory-target", dest="directory_target", type=str, help="Directory base URL (overrides DIRECTORYTARGET env var).", default=None)
parser.add_argument("--directory-username", dest="directory_username", type=str, help="Directory username (overrides DIRECTORYUSERNAME env var).", default=None)
parser.add_argument("--directory-password", dest="directory_password", type=str, help="Directory password (overrides DIRECTORYPASSWORD env var).", default=None)

parser.add_argument("-T", "--table", dest="table", type=str, help="Target table name for import/delete/export.", default=None)

action_group = parser.add_mutually_exclusive_group(required=True)
action_group.add_argument("-i", "--import-data", dest="import_data", type=str, help="Path to the CSV/TSV file containing the records to modify/add.", default=None)
action_group.add_argument("-x", "--delete-data", dest="delete_data", nargs="?", const="__FILTER_ONLY__", type=str, help="Path to the CSV/TSV file containing the records to delete (or use --delete-filter-only with -R/-C).", default=None)
action_group.add_argument("-e", "--export-data", dest="export_data", type=str, help="Export table data to a CSV/TSV file without modifying it.", default=None)

parser.add_argument("--delete-filter-only", dest="delete_filter_only", action="store_true", help="Allow deletion using -R/-C filters without a delete file.")
parser.add_argument("--export-on-delete", dest="export_on_delete", type=str, help="Export (backup) rows that will be deleted to CSV/TSV before deletion.", default=None)

parser.add_argument("-N", "--national-node", dest="national_node", type=str, help="Set national_node for all imported rows when missing in the file.", default=None)
parser.add_argument("-F", "--file-format", dest="file_format", choices=["auto", "csv", "tsv"], default="auto", help="File format override (csv/tsv). Default: auto by extension.")
parser.add_argument("-R", "--id-regex", dest="id_regex", type=str, help="Regex filter on record IDs (default column: id). Applies to import/delete/export.", default=None)
parser.add_argument("-C", "--collection-id", dest="collection_ids", action="append", help="Collection ID filter (default column: collection; repeat or comma-separated). Applies to import/delete/export.", default=None)
parser.add_argument("--id-column", dest="id_column", type=str, help="Column name for -R filtering (default: id).", default=None)
parser.add_argument("--collection-column", dest="collection_column", type=str, help="Column name for -C filtering (default: collection).", default=None)
parser.add_argument("--tsvQuoteChar", type=str, default="\"", help="Quote character for TSV parsing. Default: \"")
parser.add_argument("--tsvEscapeChar", type=str, default=None, help="Escape character for TSV parsing. Example: \\\\")
parser.add_argument("--tsvQuoting", type=str, choices=["minimal", "all", "none"], default="minimal", help="TSV quoting mode. Default: minimal")
parser.add_argument("--tsvNoDoublequote", action="store_true", help="Disable double-quote escaping for TSV parsing.")

args = parser.parse_args()

# Get args to variables
schema = args.schema
table_name = args.table
csvImportData = args.import_data
delete_action = args.delete_data is not None
csvDeleteData = None if args.delete_data in {None, "__FILTER_ONLY__"} else args.delete_data
exportData = args.export_data
export_action = args.export_data is not None
import_action = args.import_data is not None
delete_filter_only = args.delete_filter_only
export_on_delete = args.export_on_delete
national_node = args.national_node
tsvQuoteChar = args.tsvQuoteChar
tsvEscapeChar = args.tsvEscapeChar
tsvQuoting = args.tsvQuoting
tsvNoDoublequote = args.tsvNoDoublequote
verbose = args.verbose or args.debug
debug = args.debug
dry_run = args.dry_run
force = args.force
quiet = args.quiet
file_format = args.file_format
id_regex = args.id_regex
collection_ids = args.collection_ids
id_column_override = args.id_column
collection_column_override = args.collection_column
if args.directory_target:
    target = args.directory_target
if args.directory_username:
    username = args.directory_username
if args.directory_password:
    password = args.directory_password

EXIT_OK = 0
EXIT_INPUT_ERROR = 2
EXIT_ABORTED = 3
EXIT_RUNTIME_ERROR = 1


class InputError(Exception):
    pass


class OperationAborted(Exception):
    pass


TSV_QUOTING_MAP = {
    "minimal": csv.QUOTE_MINIMAL,
    "all": csv.QUOTE_ALL,
    "none": csv.QUOTE_NONE,
}


def read_tsv_as_dataframe(file_path):
    if tsvQuoteChar is not None and len(tsvQuoteChar) != 1:
        raise ValueError("tsvQuoteChar must be a single character.")
    if tsvEscapeChar is not None and len(tsvEscapeChar) != 1:
        raise ValueError("tsvEscapeChar must be a single character.")
    quoting = TSV_QUOTING_MAP[tsvQuoting]
    if quoting == csv.QUOTE_NONE and tsvEscapeChar is None:
        logging.warning("TSV quoting is set to 'none' without an escape character. Tabs and quotes must be literal.")
    return pd.read_csv(
        file_path,
        sep="\t",
        dtype=str,
        keep_default_na=False,
        na_filter=False,
        quotechar=tsvQuoteChar,
        escapechar=tsvEscapeChar,
        doublequote=not tsvNoDoublequote,
        quoting=quoting,
        encoding="utf-8-sig",
    )


def read_csv_as_dataframe(file_path):
    return pd.read_csv(
        file_path,
        sep=",",
        dtype=str,
        keep_default_na=False,
        na_filter=False,
        encoding="utf-8-sig",
    )


def is_tsv(file_path):
    return Path(file_path).suffix.lower() in {".tsv", ".tab"}


def is_csv(file_path):
    return Path(file_path).suffix.lower() == ".csv"


def detect_format(file_path, explicit_format):
    if explicit_format and explicit_format != "auto":
        return explicit_format
    if is_tsv(file_path):
        return "tsv"
    if is_csv(file_path):
        return "csv"
    return None


def load_dataframe_for_file(file_path, file_format):
    if file_format == "tsv":
        return read_tsv_as_dataframe(file_path)
    if file_format == "csv":
        return read_csv_as_dataframe(file_path)
    return None


def log_records(action, table, df):
    if df is None:
        logging.info("%s records for table %s (record details unavailable).", action, table)
        return
    record_count = len(df.index)
    logging.info("%s %s record(s) for table %s.", action, record_count, table)
    if verbose:
        for index, row in df.iterrows():
            logging.info("%s record %s: %s", action, index + 1, row.to_dict())


def parse_collection_ids(values):
    if not values:
        return []
    parsed = []
    for item in values:
        if item is None:
            continue
        for part in str(item).split(","):
            part = part.strip()
            if part:
                parsed.append(part)
    return parsed


def resolve_id_column(df, override=None):
    if override:
        column_name = resolve_column_case_insensitive(df, override)
        if column_name is None:
            raise InputError(f"ID column {override!r} not found.")
        return column_name
    column_name = resolve_column_case_insensitive(df, "id")
    if column_name is None:
        return None
    return column_name


def resolve_collection_column(df, override=None):
    if override:
        column_name = resolve_column_case_insensitive(df, override)
        if column_name is None:
            raise InputError(f"Collection column {override!r} not found.")
        return column_name
    column_name = resolve_column_case_insensitive(df, "collection")
    if column_name is None:
        return None
    return column_name


def resolve_column_case_insensitive(df, column_name):
    if column_name in df.columns:
        return column_name
    target = column_name.lower()
    for col in df.columns:
        if col.lower() == target:
            return col
    return None


def get_table_columns(session, schema, table):
    schema_metadata = session.get_schema_metadata(schema)
    table_meta = schema_metadata.get_table(by="name", value=table)
    return [col.name for col in table_meta.columns]


def fetch_existing_ids(session, schema, table, id_column):
    try:
        table_df = session.get(table=table, schema=schema, as_df=True)
    except Exception as exc:
        logging.warning("Failed to retrieve existing records for %s::%s: %s", schema, table, exc)
        return None
    try:
        id_column = resolve_id_column(table_df, id_column)
    except InputError as exc:
        logging.warning("Unable to identify an ID column in %s::%s: %s", schema, table, exc)
        return None
    if id_column is None:
        logging.warning("Unable to identify an ID column in %s::%s.", schema, table)
        return None
    return set(table_df[id_column].astype(str))


def report_column_mismatches(session, schema, table, df):
    try:
        columns = get_table_columns(session, schema, table)
    except Exception as exc:
        logging.warning("Failed to retrieve schema metadata for %s::%s: %s", schema, table, exc)
        return
    file_columns = [col for col in df.columns]
    extra = sorted({col for col in file_columns if col not in columns})
    missing = sorted({col for col in columns if col not in file_columns})
    if extra:
        logging.warning("File contains columns not present in %s::%s: %s", schema, table, extra)
    if missing:
        if verbose:
            logging.info("File is missing %s column(s) from %s::%s: %s", len(missing), schema, table, missing)
        else:
            logging.info("File is missing %s column(s) from %s::%s.", len(missing), schema, table)


def summarize_import(session, schema, table, df, id_column):
    if df is None:
        return None
    report_column_mismatches(session, schema, table, df)
    try:
        id_column = resolve_id_column(df, id_column)
    except InputError as exc:
        raise InputError(f"Import requires an ID column for summary: {exc}") from exc
    if id_column is None:
        logging.warning("Import file does not include an ID column; unable to compare with server data.")
        return {
            "total": len(df.index),
            "new": None,
            "update": None,
            "has_existing": False,
        }
    file_ids = set(df[id_column].astype(str))
    existing_ids = fetch_existing_ids(session, schema, table, id_column)
    if existing_ids is None:
        return {
            "total": len(df.index),
            "new": None,
            "update": None,
            "has_existing": False,
        }
    new_ids = sorted(file_ids - existing_ids)
    update_ids = sorted(file_ids & existing_ids)
    logging.info("Import summary for %s::%s: %s new, %s updates.", schema, table, len(new_ids), len(update_ids))
    if verbose:
        if new_ids:
            logging.info("New IDs: %s", new_ids)
        if update_ids:
            logging.info("Update IDs: %s", update_ids)
    return {
        "total": len(df.index),
        "new": new_ids,
        "update": update_ids,
        "has_existing": True,
    }


def summarize_delete(session, schema, table, df, id_column):
    if df is None:
        return
    report_column_mismatches(session, schema, table, df)
    try:
        id_column = resolve_id_column(df, id_column)
    except InputError as exc:
        raise InputError(f"Delete requires an ID column: {exc}") from exc
    if id_column is None:
        raise InputError("Delete file does not include an ID column.")
    file_ids = set(df[id_column].astype(str))
    existing_ids = fetch_existing_ids(session, schema, table, id_column)
    if existing_ids is None:
        return
    missing_ids = sorted(file_ids - existing_ids)
    present_ids = sorted(file_ids & existing_ids)
    logging.info("Delete summary for %s::%s: %s matching, %s missing.", schema, table, len(present_ids), len(missing_ids))
    if missing_ids:
        logging.warning("IDs not present on server: %s", missing_ids)
    if verbose and present_ids:
        logging.info("IDs to delete: %s", present_ids)


def confirm_action(prompt):
    if force:
        return
    if not sys.stdin.isatty():
        raise OperationAborted("Interactive confirmation required but stdin is not a TTY. Use --force to proceed.")
    sys.stderr.write(prompt + " [y/N]: ")
    sys.stderr.flush()
    response = sys.stdin.readline().strip().lower()
    if response not in {"y", "yes"}:
        raise OperationAborted("Operation cancelled by user.")


def apply_filters(df, id_regex, collections, id_column, collection_column, context):
    filtered = df
    if id_regex:
        try:
            pattern = re.compile(id_regex)
        except re.error as exc:
            raise InputError(f"Invalid ID regex: {exc}") from exc
        id_col = resolve_id_column(filtered, id_column)
        if id_col is None:
            raise InputError(f"{context} requires an ID column named 'id' or --id-column.")
        filtered = filtered[filtered[id_col].astype(str).str.contains(pattern)]
    if collections:
        collection_col = resolve_collection_column(filtered, collection_column)
        if collection_col is None:
            raise InputError(f"{context} requires a collection column named 'collection' or --collection-column.")
        filtered = filtered[filtered[collection_col].astype(str).isin(collections)]
    return filtered


def export_table_data(df, output_path, file_format):
    if file_format == "csv":
        df.to_csv(output_path, index=False, encoding="utf-8", quoting=csv.QUOTE_NONNUMERIC)
        return
    df.to_csv(
        output_path,
        index=False,
        sep="\t",
        encoding="utf-8",
        quoting=csv.QUOTE_MINIMAL,
        quotechar=tsvQuoteChar,
        escapechar=tsvEscapeChar,
        doublequote=not tsvNoDoublequote,
    )


# Function
async def sync_directory():
    # Set up the logger
    log_level = "ERROR" if quiet else ("DEBUG" if debug else "INFO")
    logging.basicConfig(level=log_level, format=" %(levelname)s: %(name)s: %(message)s")
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Login to the directory with a DirectorySession
    if debug:
        logging.debug("Preparing DirectorySession for target %s.", target)
    with DirectorySession(url=target) as session:
        # Apply the 'signin' method with the username and password
        if debug:
            logging.debug("Signing in to Directory as %s.", username or "<missing username>")
        session.signin(username, password)
        if debug:
            signin_status = getattr(session, "signin_status", None)
            if signin_status is not None:
                logging.debug("Signin status: %s.", signin_status)
        session.set_schema(schema)
        if debug:
            logging.debug("Schema set to %s.", schema)
        collections = parse_collection_ids(collection_ids)

        #########################################################
        # UPLOAD CSV/TSV. Args: CSV/TSV path, schema, and table name (use -T/--table).
        #########################################################
        # Behaviour: 
        # If the CSV contains rows with the same ID that the ones that are already in the staging area, the entire row in replaced by the one in the CSV (no need to delete it first from the staging are, it is just rewritten).
        # If the CSV contains rows with new IDs, they are added to the table (it does not check if the IDs are consecutive or not)
        # Those rows that are not present in the CSV are not modified nor deleted, just kept as they are.
        # The CSV must contain the header and a new line at the end (better way to have the right format is to download it from the staging area and modify as needed)
        if csvImportData:
            import_path = Path(csvImportData)
            resolved_format = detect_format(import_path, file_format)
            if resolved_format is None:
                if import_path.suffix.lower() in {".xlsx", ".zip"}:
                    logging.info("Planned import from file %s (record details unavailable).", csvImportData)
                else:
                    raise InputError("Import format could not be determined. Use --file-format or a .csv/.tsv file.")
            import_table = table_name
            data = None
            skip_import = False
            if resolved_format in {"csv", "tsv"}:
                try:
                    data = load_dataframe_for_file(import_path, resolved_format)
                except Exception as exc:
                    logging.warning("Failed to read import file %s for record details: %s", csvImportData, exc)
            added_national_node = False
            if national_node and resolved_format in {"csv", "tsv"}:
                if data is None:
                    raise InputError("national_node was provided but the import file could not be parsed.")
                column_name = resolve_column_case_insensitive(data, "national_node")
                if column_name is None:
                    data["national_node"] = national_node
                    logging.info("Added national_node=%s to %s imported record(s).", national_node, len(data.index))
                    added_national_node = True
                else:
                    logging.warning("Import file already contains %s column; --national-node will be ignored.", column_name)
            if (id_regex or collection_ids) and resolved_format not in {"csv", "tsv"}:
                raise InputError("Filtering with -R/-C is only supported for CSV/TSV imports.")
            if data is None and resolved_format in {"csv", "tsv"}:
                logging.info("Planned import from file %s (record details unavailable).", csvImportData)
            else:
                log_records("Planned import", import_table, data)
            if data is not None and (id_regex or collection_ids):
                data = apply_filters(
                    data,
                    id_regex,
                    collections,
                    id_column_override,
                    collection_column_override,
                    "Import filtering",
                )
                if data.empty:
                    logging.info("Import filters matched no rows. Skipping import for %s.", csvImportData)
                    skip_import = True
            import_summary = None
            if data is not None:
                import_summary = summarize_import(session, schema, import_table, data, id_column_override)
            if data is not None and data.empty:
                logging.info("Import file contains no records. Skipping import for %s.", csvImportData)
                skip_import = True
            if not dry_run and not skip_import:
                needs_confirmation = False
                if resolved_format in {"csv", "tsv"}:
                    if data is None:
                        needs_confirmation = True
                    else:
                        if import_summary is None:
                            needs_confirmation = True
                        elif import_summary["new"] is None or import_summary["update"] is None:
                            needs_confirmation = True
                        elif (len(import_summary["new"]) + len(import_summary["update"])) > 0:
                            needs_confirmation = True
                else:
                    needs_confirmation = True
                if needs_confirmation:
                    if import_summary and import_summary["new"] is not None and import_summary["update"] is not None:
                        confirm_action(
                            f"Proceed with importing {import_summary['total']} record(s) into {import_table}? "
                            f"({len(import_summary['new'])} new, {len(import_summary['update'])} updates)"
                        )
                    else:
                        confirm_action(f"Proceed with importing data into {import_table}?")
            if skip_import:
                pass
            elif dry_run:
                logging.info("Dry run enabled. Skipping import for %s.", csvImportData)
            elif resolved_format == "tsv":
                logging.info("Importing TSV data from %s into table %s", csvImportData, import_table)
                if data is None:
                    data = read_tsv_as_dataframe(import_path)
                try:
                    session.save_table(table=import_table, schema=schema, data=data)
                except Exception as exc:
                    if (not national_node) and "national_node" in str(exc).lower():
                        logging.warning(
                            "Import failed due to missing national_node. Using schema %s as fallback for all rows.",
                            schema,
                        )
                        column_name = resolve_column_case_insensitive(data, "national_node")
                        if column_name is None:
                            data["national_node"] = schema
                        session.save_table(table=import_table, schema=schema, data=data)
                    else:
                        raise
            elif resolved_format == "csv":
                logging.info("Importing data from %s", csvImportData)
                if import_path.suffix.lower() == ".csv" and not added_national_node:
                    try:
                        await session.upload_file(csvImportData, schema)
                    except Exception as exc:
                        if (not national_node) and "national_node" in str(exc).lower():
                            logging.warning(
                                "Import failed due to missing national_node. Using schema %s as fallback for all rows.",
                                schema,
                            )
                            if data is None:
                                data = read_csv_as_dataframe(import_path)
                            column_name = resolve_column_case_insensitive(data, "national_node")
                            if column_name is None:
                                data["national_node"] = schema
                            session.save_table(table=import_table, schema=schema, data=data)
                        else:
                            raise
                else:
                    if data is None:
                        data = read_csv_as_dataframe(import_path)
                    try:
                        session.save_table(table=import_table, schema=schema, data=data)
                    except Exception as exc:
                        if (not national_node) and "national_node" in str(exc).lower():
                            logging.warning(
                                "Import failed due to missing national_node. Using schema %s as fallback for all rows.",
                                schema,
                            )
                            column_name = resolve_column_case_insensitive(data, "national_node")
                            if column_name is None:
                                data["national_node"] = schema
                            session.save_table(table=import_table, schema=schema, data=data)
                        else:
                            raise
            else:
                logging.info("Importing data from %s", csvImportData)
                await session.upload_file(csvImportData, schema)

        #########################################################
        # DELETE RECORDS
        #########################################################
        # Input a file and delete the records that are included in it
        # Args: delete_records(self, table: str, schema: str = None, file: str = None, data: list | pd.DataFrame = None)
        # NOTE It does not raise a warning if the records are not present in the staging area
        if delete_action:
            if csvDeleteData:
                logging.info("Deleting the records contained in %s from table %s", csvDeleteData, table_name)
                delete_path = Path(csvDeleteData)
                resolved_format = detect_format(delete_path, file_format)
                if resolved_format is None:
                    raise InputError("Delete format could not be determined. Use --file-format or a .csv/.tsv file.")
                delete_data = None
                try:
                    delete_data = load_dataframe_for_file(delete_path, resolved_format)
                except Exception as exc:
                    logging.warning("Failed to read delete file %s for record details: %s", csvDeleteData, exc)
                if delete_data is None:
                    raise InputError("Unable to parse delete file for record details.")
                if id_regex or collection_ids:
                    delete_data = apply_filters(
                        delete_data,
                        id_regex,
                        collections,
                        id_column_override,
                        collection_column_override,
                        "Delete filtering",
                    )
                    if delete_data.empty:
                        logging.info("Delete filters matched no rows. Skipping delete for %s.", csvDeleteData)
                        delete_data = None
                if delete_data is not None:
                    log_records("Planned delete", table_name, delete_data)
                    if export_on_delete:
                        backup_path = Path(export_on_delete)
                        backup_format = detect_format(backup_path, file_format)
                        if backup_format is None:
                            raise InputError("Export-on-delete format could not be determined. Use --file-format or a .csv/.tsv filename.")
                        export_table_data(delete_data, backup_path, backup_format)
                        logging.info("Exported %s record(s) slated for deletion to %s.", len(delete_data.index), backup_path)
                    summarize_delete(session, schema, table_name, delete_data, id_column_override)
                    if delete_data.empty:
                        logging.info("Delete file contains no records. Skipping delete for %s.", csvDeleteData)
                    else:
                        confirm_action(f"Proceed with deleting {len(delete_data.index)} record(s) from {table_name}?")
                        if dry_run:
                            logging.info("Dry run enabled. Skipping delete for %s.", csvDeleteData)
                        else:
                            session.delete_records(table_name, schema, data=delete_data)
            else:
                table_df = session.get(table=table_name, schema=schema, as_df=True)
                filtered = apply_filters(
                    table_df,
                    id_regex,
                    collections,
                    id_column_override,
                    collection_column_override,
                    "Delete filtering",
                )
                if filtered.empty:
                    logging.info("No records matched the delete filters.")
                else:
                    log_records("Planned delete", table_name, filtered)
                    if export_on_delete:
                        backup_path = Path(export_on_delete)
                        backup_format = detect_format(backup_path, file_format)
                        if backup_format is None:
                            raise InputError("Export-on-delete format could not be determined. Use --file-format or a .csv/.tsv filename.")
                        export_table_data(filtered, backup_path, backup_format)
                        logging.info("Exported %s record(s) slated for deletion to %s.", len(filtered.index), backup_path)
                    id_column = resolve_id_column(filtered, id_column_override)
                    if id_column is None:
                        raise InputError("Delete requires an ID column named 'id' or --id-column.")
                    delete_ids = filtered[[id_column]]
                    confirm_action(f"Proceed with deleting {len(delete_ids.index)} record(s) from {table_name}?")
                    if dry_run:
                        logging.info("Dry run enabled. Skipping delete for filtered records.")
                    else:
                        session.delete_records(table_name, schema, data=delete_ids)

        if export_action:
            output_path = Path(exportData)
            resolved_export_format = detect_format(output_path, file_format)
            if resolved_export_format is None:
                raise InputError("Export format could not be determined. Use --file-format or a .csv/.tsv file.")
            export_df = session.get(table=table_name, schema=schema, as_df=True)
            if id_regex or collection_ids:
                export_df = apply_filters(
                    export_df,
                    id_regex,
                    collections,
                    id_column_override,
                    collection_column_override,
                    "Export filtering",
                )
            if export_df.empty:
                logging.info("No records matched the export filters.")
            export_table_data(export_df, output_path, resolved_export_format)
            logging.info("Exported %s record(s) to %s.", len(export_df.index), output_path)
    return EXIT_OK
            
# Main
def setup_logging():
    log_level = "ERROR" if quiet else ("DEBUG" if debug else "INFO")
    logging.basicConfig(level=log_level, format=" %(levelname)s: %(name)s: %(message)s")


def validate_inputs():
    if not target:
        raise InputError("DIRECTORYTARGET is not set. Define it in the .env file or pass --directory-target.")
    if not username or not password:
        raise InputError("DIRECTORYUSERNAME or DIRECTORYPASSWORD is not set. Define them in the .env file or pass --directory-username/--directory-password.")
    if schema.strip().upper() == "ERIC":
        logging.warning(
            "Schema ERIC should not be edited with this script; it is auto-populated nightly from per-node staging areas."
        )
        confirm_action("Proceed anyway with schema ERIC?")
    if not table_name:
        raise InputError("Table name is required. Use -T/--table.")
    if not (import_action or delete_action or export_action):
        raise InputError("No action specified. Provide import (-i), delete (-x), or export (-e) options.")
    if csvImportData:
        import_path = Path(csvImportData)
        if not import_path.exists():
            raise InputError(f"Import file not found: {csvImportData}")
        if file_format in {"csv", "tsv"} and import_path.suffix.lower() not in {".csv", ".tsv", ".tab", ""}:
            logging.warning("File format forced to %s for file %s.", file_format, csvImportData)
    if delete_filter_only and not delete_action:
        raise InputError("--delete-filter-only can only be used with -x/--delete-data.")
    if delete_action:
        if csvDeleteData:
            delete_path = Path(csvDeleteData)
            if not delete_path.exists():
                raise InputError(f"Delete file not found: {csvDeleteData}")
            if delete_filter_only:
                raise InputError("Do not use --delete-filter-only with a delete file.")
            if file_format in {"csv", "tsv"} and delete_path.suffix.lower() not in {".csv", ".tsv", ".tab", ""}:
                logging.warning("File format forced to %s for file %s.", file_format, csvDeleteData)
        else:
            if not delete_filter_only:
                raise InputError("Delete requires a filename unless --delete-filter-only is set.")
            if not (id_regex or collection_ids):
                raise InputError("--delete-filter-only requires -R and/or -C filters.")
    if exportData:
        export_path = Path(exportData)
        if not export_path.parent.exists():
            raise InputError(f"Export directory not found: {export_path.parent}")
        if file_format in {"csv", "tsv"} and export_path.suffix.lower() not in {".csv", ".tsv", ".tab", ""}:
            logging.warning("File format forced to %s for file %s.", file_format, exportData)
    if export_on_delete:
        export_path = Path(export_on_delete)
        if not export_path.parent.exists():
            raise InputError(f"Export-on-delete directory not found: {export_path.parent}")
        if file_format in {"csv", "tsv"} and export_path.suffix.lower() not in {".csv", ".tsv", ".tab", ""}:
            logging.warning("File format forced to %s for file %s.", file_format, export_on_delete)


def main():
    setup_logging()
    try:
        validate_inputs()
        exit_code = asyncio.run(sync_directory())
        sys.exit(exit_code)
    except OperationAborted as exc:
        logging.error("%s", exc)
        sys.exit(EXIT_ABORTED)
    except InputError as exc:
        logging.error("%s", exc)
        sys.exit(EXIT_INPUT_ERROR)
    except ValueError as exc:
        logging.error("%s", exc)
        sys.exit(EXIT_INPUT_ERROR)
    except Exception as exc:
        logging.error("Unexpected error: %s", exc)
        sys.exit(EXIT_RUNTIME_ERROR)


if __name__ == "__main__":
    main()
