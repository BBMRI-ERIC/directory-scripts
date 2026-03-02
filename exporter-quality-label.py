#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

import pprint
import logging as log
from builtins import str, set

import pandas as pd

from cli_common import (
    add_directory_schema_argument,
    add_logging_arguments,
    add_no_stdout_argument,
    add_optional_xlsx_output_argument,
    add_purge_cache_arguments,
    add_withdrawn_scope_arguments,
    add_xlsx_output_argument,
    build_directory_kwargs,
    build_parser,
    configure_logging,
)
from directory import Directory
from molgenis_emx2_pyclient import Client
from xlsxutils import write_xlsx_tables

cachesList = ['directory']

pp = pprint.PrettyPrinter(indent=4)


parser = build_parser()
add_logging_arguments(parser)
add_xlsx_output_argument(parser, default_filename='QualityLabelsExporter.xlsx')
add_optional_xlsx_output_argument(
    parser,
    dest='outputXLSXwithdrawn',
    long_option='--output-xlsx-withdrawn',
    legacy_long_options=['--output-XLSX-withdrawn'],
    help_text='write withdrawn biobanks and collections to the provided XLSX file',
)
add_no_stdout_argument(parser)
add_directory_schema_argument(parser, default="ERIC")
add_withdrawn_scope_arguments(parser)
add_purge_cache_arguments(parser, cachesList)
parser.set_defaults(purgeCaches=[], filterCollType=[], filterMatType=[])
args = parser.parse_args()

if args.outputXLSXwithdrawn is not None and not (
    args.include_withdrawn or args.only_withdrawn
):
    parser.error(
        "--output-xlsx-withdrawn requires --include-withdrawn or --only-withdrawn."
    )

configure_logging(args)


### Initialize variables
qual_label = {}

### Functions
def reshape_quality_table(df, entity, assess_level, qualityStandardsOntology):
    """
    Adapt format of the quality table.

    Parameters:
        df: Input df with columns ['id', entity, 'quality_standard', assess_level]
        entity: Header of the second column of the dataframe
        assess_level: Name of the assess_level column
        qualityStandardsOntology: Ontology table from Directory

    Returns:
        df: Reshaped df with one row per entity
    """
    # Pivot table
    pivoted_df = df.pivot(index=['id', entity],
                          columns='quality_standard',
                          values=assess_level).reset_index()

    # Remove ID colum
    pivoted_df = pivoted_df.drop(columns='id')

    # Remove axis name from columns
    pivoted_df.columns.name = None

    # Merge rows with the same entity
    final_df = pivoted_df.groupby(entity, as_index=False).first()

    # Reorder columns
    final_df = final_df[[entity] + sorted(col for col in final_df.columns if col != entity)]

    # Replace name by the label in Quality Standards Ontology:
    mapping = dict(zip(qualityStandardsOntology["name"], qualityStandardsOntology["label"])) # Create mapping dict
    final_df = final_df.rename(columns=mapping)

    return final_df

def outputExcelBiobanksCollections(filename : str, dfBiobanks : pd.DataFrame, biobanksLabel : str, dfCollections : pd.DataFrame, collectionsLabel : str, dfCombinedQual : pd.DataFrame, combQualLabel : str):
    write_xlsx_tables(
        filename,
        [
            (dfBiobanks, biobanksLabel),
            (dfCollections, collectionsLabel),
            (dfCombinedQual, combQualLabel),
        ],
    )

def replacebyQMvalues(df, include_headers=False):
    ''' Replace values by more readable ones indicated by QM (hardcoded) '''
    
    QMmapping = {"accredited":"3rd-level audit (accredited)", "eric":"2nd-level audit (ERIC)"}

    df = df.replace(QMmapping)

    if include_headers:
        df = df.rename(columns=QMmapping)

    return df


def _normalize_quality_value(value):
    if isinstance(value, dict):
        return value.get("id", "")
    return value if value is not None else ""


def _filter_quality_table(df, column_name, allowed_ids):
    if df.empty or column_name not in df.columns:
        return df.copy()
    mask = df[column_name].apply(_normalize_quality_value).isin(allowed_ids)
    return df.loc[mask].copy()

#### Main

# Get ontology info from Directory
directoryURL = "https://directory.bbmri-eric.eu"
log.info('Retrieving directory content from ' + directoryURL)
session = Client(directoryURL, schema='DirectoryOntologies')

qualityStandardsOntology = session.get(table = 'QualityStandards', as_df= True)

# Get data
dir = Directory(**build_directory_kwargs(args, pp=pp))

log.info('Total biobanks: ' + str(dir.getBiobanksCount()))
log.info('Total collections: ' + str(dir.getCollectionsCount()))

selected_biobank_ids = {biobank["id"] for biobank in dir.getBiobanks()}
selected_collection_ids = {collection["id"] for collection in dir.getCollections()}
withdrawn_biobank_ids = {
    biobank_id for biobank_id in selected_biobank_ids if dir.isBiobankWithdrawn(biobank_id)
}
withdrawn_collection_ids = {
    collection_id
    for collection_id in selected_collection_ids
    if dir.isCollectionWithdrawn(collection_id)
}

### Get combined quality info

for collection in dir.getCollections():
    log.debug("Analyzing collection " + collection['id'])
    biobankId = dir.getCollectionBiobankId(collection['id'])
    biobank = dir.getBiobankById(biobankId)
    
    if 'contact' in collection:
        collection['contact'] = dir.getContact(collection['contact']['id'])

    if 'combined_quality' in collection:
        qual_label[collection['id']] = collection['combined_quality']

## Format combined quality table
# parse to columns
all_creds = sorted(set(cred for creds in qual_label.values() for cred in creds))

# Yes/No
rows = []
for key, creds in qual_label.items():
    row = [key] + [ "Yes" if cred in creds else "No" for cred in all_creds ]
    rows.append(row)

# df
columns = ["Key"] + all_creds
combinedQualitydf = pd.DataFrame(rows, columns=columns)


### Get quality info

qualBBdf = dir.getQualBB()
qualColldf = dir.getQualColl()

qualBBdf = _filter_quality_table(qualBBdf, 'biobank', selected_biobank_ids)
qualColldf = _filter_quality_table(qualColldf, 'collection', selected_collection_ids)

qualBBfinaldf = reshape_quality_table(qualBBdf, 'biobank', 'assess_level_bio', qualityStandardsOntology)
qualCollfinaldf = reshape_quality_table(qualColldf, 'collection', 'assess_level_col', qualityStandardsOntology)

# Replace values by those indicated by QM:
qualBBfinaldf = replacebyQMvalues(qualBBfinaldf)
qualCollfinaldf = replacebyQMvalues(qualCollfinaldf)
combinedQualitydf = replacebyQMvalues(combinedQualitydf, include_headers=True)

outputExcelBiobanksCollections(args.outputXLSX[0], qualBBfinaldf, "Biobanks", qualCollfinaldf, "Collections", combinedQualitydf, "CombinedQuality")

if args.outputXLSXwithdrawn is not None:
    qualBBwithdrawndf = _filter_quality_table(
        dir.getQualBB(), 'biobank', withdrawn_biobank_ids
    )
    qualCollwithdrawndf = _filter_quality_table(
        dir.getQualColl(), 'collection', withdrawn_collection_ids
    )
    qualBBwithdrawnfinaldf = reshape_quality_table(
        qualBBwithdrawndf, 'biobank', 'assess_level_bio', qualityStandardsOntology
    )
    qualCollwithdrawnfinaldf = reshape_quality_table(
        qualCollwithdrawndf, 'collection', 'assess_level_col', qualityStandardsOntology
    )
    qualBBwithdrawnfinaldf = replacebyQMvalues(qualBBwithdrawnfinaldf)
    qualCollwithdrawnfinaldf = replacebyQMvalues(qualCollwithdrawnfinaldf)
    combinedQualityWithdrawndf = replacebyQMvalues(
        combinedQualitydf[combinedQualitydf["Key"].isin(withdrawn_collection_ids)].copy(),
        include_headers=False,
    )
    outputExcelBiobanksCollections(
        args.outputXLSXwithdrawn[0],
        qualBBwithdrawnfinaldf,
        "Withdrawn biobanks",
        qualCollwithdrawnfinaldf,
        "Withdrawn collections",
        combinedQualityWithdrawndf,
        "Withdrawn combined quality",
    )
