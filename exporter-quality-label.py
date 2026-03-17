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

#### Main

# Get data
dir = Directory(**build_directory_kwargs(args, pp=pp))
qualityStandardsOntology = dir.getQualityStandardsOntology(
    purge_cache="directory" in args.purgeCaches
)

log.info('Total biobanks: ' + str(dir.getBiobanksCount()))
log.info('Total collections: ' + str(dir.getCollectionsCount()))

withdrawn_collection_ids = {
    collection["id"]
    for collection in dir.getCollections()
    if dir.isCollectionWithdrawn(collection["id"])
}

### Get combined quality info

for collection in dir.getCollections():
    log.debug("Analyzing collection " + collection['id'])
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

qualBBfinaldf = dir.getBiobankQualityInfoWide(
    scope="configured",
    use_ontology_labels=True,
    quality_standards_ontology=qualityStandardsOntology,
)
qualCollfinaldf = dir.getCollectionQualityInfoWide(
    scope="configured",
    use_ontology_labels=True,
    quality_standards_ontology=qualityStandardsOntology,
)

# Replace values by those indicated by QM:
qualBBfinaldf = replacebyQMvalues(qualBBfinaldf)
qualCollfinaldf = replacebyQMvalues(qualCollfinaldf)
combinedQualitydf = replacebyQMvalues(combinedQualitydf, include_headers=True)

outputExcelBiobanksCollections(args.outputXLSX[0], qualBBfinaldf, "Biobanks", qualCollfinaldf, "Collections", combinedQualitydf, "CombinedQuality")

if args.outputXLSXwithdrawn is not None:
    qualBBwithdrawnfinaldf = dir.getBiobankQualityInfoWide(
        scope="withdrawn",
        use_ontology_labels=True,
        quality_standards_ontology=qualityStandardsOntology,
    )
    qualCollwithdrawnfinaldf = dir.getCollectionQualityInfoWide(
        scope="withdrawn",
        use_ontology_labels=True,
        quality_standards_ontology=qualityStandardsOntology,
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
