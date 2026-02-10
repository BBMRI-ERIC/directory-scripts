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


def is_tsv(file_path):
    return Path(file_path).suffix.lower() in {".tsv", ".tab"}

# Function
async def sync_directory():
    # Set up the logger
    logging.basicConfig(level="INFO", format=" %(levelname)s: %(name)s: %(message)s")
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Login to the directory with a DirectorySession
    with DirectorySession(url=target) as session:
        # Apply the 'signin' method with the username and password
        session.signin(username, password)
        session.set_schema(schema)

        #########################################################
        # UPLOAD CSV/TSV. Args: CSV/TSV path (the name MUST be: TableName.csv or TableName.tsv), schema.
        #########################################################
        # Behaviour: 
        # If the CSV contains rows with the same ID that the ones that are already in the staging area, the entire row in replaced by the one in the CSV (no need to delete it first from the staging are, it is just rewritten).
        # If the CSV contains rows with new IDs, they are added to the table (it does not check if the IDs are consecutive or not)
        # Those rows that are not present in the CSV are not modified nor deleted, just kept as they are.
        # The CSV must contain the header and a new line at the end (better way to have the right format is to download it from the staging area and modify as needed)
        if csvImportData:
            if is_tsv(csvImportData):
                import_path = Path(csvImportData)
                logging.info("Importing TSV data from %s into table %s", csvImportData, import_path.stem)
                data = read_tsv_as_dataframe(import_path)
                session.save_table(table=import_path.stem, schema=schema, data=data)
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
            if is_tsv(csvDeleteData):
                data = read_tsv_as_dataframe(csvDeleteData)
                session.delete_records(delTable, schema, data=data)
            else:
                session.delete_records(delTable, schema, csvDeleteData)
        elif csvDeleteData and not delTable:
            logging.error("File with records to delete provided but table not specified.")
            
# Main
if __name__ == "__main__":
    asyncio.run(sync_directory())
