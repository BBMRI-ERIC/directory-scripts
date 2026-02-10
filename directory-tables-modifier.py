#!/usr/bin/python3

# Imports
import argparse
import asyncio
import csv
import logging
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from molgenis_emx2.directory_client.directory_client import DirectorySession

# Get credentials from .env
load_dotenv()

target = os.getenv("TARGET")
username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")

# Get args from stdin
parser = argparse.ArgumentParser(description="Script for modifying/adding or deleting records from tables in BBMRI Directory staging area. Make sure you have an .env file in this folder, containing: TARGET=target URL, USERNAME and PASSWORD.")

parser.add_argument("-schema", type=str, required=True, help="Schema")

parser.add_argument("--csvImportData", type=str, help="Path to the csv/tsv file containing the records to modify/add. The filename MUST be: TableName.csv or TableName.tsv", default=None)
parser.add_argument("--csvDeleteData", type=str, help="Path to the csv/tsv file containing the records to delete", default=None)
parser.add_argument("--delTable", type=str, help="Table name. Only required when deleting data.", default=None)
parser.add_argument("--tsvQuoteChar", type=str, default="\"", help="Quote character for TSV parsing. Default: \"")
parser.add_argument("--tsvEscapeChar", type=str, default=None, help="Escape character for TSV parsing. Example: \\\\")
parser.add_argument("--tsvQuoting", type=str, choices=["minimal", "all", "none"], default="minimal", help="TSV quoting mode. Default: minimal")
parser.add_argument("--tsvNoDoublequote", action="store_true", help="Disable double-quote escaping for TSV parsing.")
parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output. Includes detailed records to be added/deleted.")
parser.add_argument("-d", "--debug", action="store_true", help="Debug output. Implies verbose and includes connection/auth details.")
parser.add_argument("--dry-run", action="store_true", help="Show planned changes without modifying data.")

args = parser.parse_args()

# Get args to variables
schema = args.schema
csvImportData = args.csvImportData
csvDeleteData = args.csvDeleteData
delTable = args.delTable
tsvQuoteChar = args.tsvQuoteChar
tsvEscapeChar = args.tsvEscapeChar
tsvQuoting = args.tsvQuoting
tsvNoDoublequote = args.tsvNoDoublequote
verbose = args.verbose or args.debug
debug = args.debug
dry_run = args.dry_run

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


def load_dataframe_for_file(file_path):
    if is_tsv(file_path):
        return read_tsv_as_dataframe(file_path)
    if is_csv(file_path):
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


# Function
async def sync_directory():
    # Set up the logger
    logging.basicConfig(level="DEBUG" if debug else "INFO", format=" %(levelname)s: %(name)s: %(message)s")
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

        #########################################################
        # UPLOAD CSV/TSV. Args: CSV/TSV path (the name MUST be: TableName.csv or TableName.tsv), schema.
        #########################################################
        # Behaviour: 
        # If the CSV contains rows with the same ID that the ones that are already in the staging area, the entire row in replaced by the one in the CSV (no need to delete it first from the staging are, it is just rewritten).
        # If the CSV contains rows with new IDs, they are added to the table (it does not check if the IDs are consecutive or not)
        # Those rows that are not present in the CSV are not modified nor deleted, just kept as they are.
        # The CSV must contain the header and a new line at the end (better way to have the right format is to download it from the staging area and modify as needed)
        if csvImportData:
            import_path = Path(csvImportData)
            import_table = import_path.stem if (is_csv(import_path) or is_tsv(import_path)) else import_path.name
            data = None
            try:
                data = load_dataframe_for_file(import_path)
            except Exception as exc:
                logging.warning("Failed to read import file %s for record details: %s", csvImportData, exc)
            if data is None and not (is_csv(import_path) or is_tsv(import_path)):
                logging.info("Planned import from file %s (record details unavailable).", csvImportData)
            else:
                log_records("Planned import", import_table, data)
            if dry_run:
                logging.info("Dry run enabled. Skipping import for %s.", csvImportData)
            elif is_tsv(csvImportData):
                logging.info("Importing TSV data from %s into table %s", csvImportData, import_table)
                if data is None:
                    data = read_tsv_as_dataframe(import_path)
                session.save_table(table=import_table, schema=schema, data=data)
            else:
                logging.info("Importing data from %s", csvImportData)
                await session.upload_file(csvImportData, schema)

        #########################################################
        # DELETE RECORDS
        #########################################################
        # Input a file and delete the records that are included in it
        # Args: delete_records(self, table: str, schema: str = None, file: str = None, data: list | pd.DataFrame = None)
        # NOTE It does not raise a warning if the records are not present in the staging area
        if csvDeleteData and delTable:
            logging.info("Deleting the records contained in %s from table %s", csvDeleteData, delTable)
            delete_data = None
            try:
                delete_data = load_dataframe_for_file(csvDeleteData)
            except Exception as exc:
                logging.warning("Failed to read delete file %s for record details: %s", csvDeleteData, exc)
            log_records("Planned delete", delTable, delete_data)
            if dry_run:
                logging.info("Dry run enabled. Skipping delete for %s.", csvDeleteData)
            elif is_tsv(csvDeleteData):
                if delete_data is None:
                    delete_data = read_tsv_as_dataframe(csvDeleteData)
                session.delete_records(delTable, schema, data=delete_data)
            else:
                session.delete_records(delTable, schema, csvDeleteData)
        elif csvDeleteData and not delTable:
            logging.error("File with records to delete provided but table not specified.")
            
# Main
if __name__ == "__main__":
    asyncio.run(sync_directory())
