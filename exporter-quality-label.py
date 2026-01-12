#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

import pprint
import argparse
import logging as log
from builtins import str, set

import pandas as pd

from directory import Directory

cachesList = ['directory', 'emails', 'geocoding', 'URLs']

pp = pprint.PrettyPrinter(indent=4)


class ExtendAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        from builtins import getattr, setattr
        items = getattr(namespace, self.dest) or []
        items.extend(values)
        setattr(namespace, self.dest, items)


parser = argparse.ArgumentParser()
parser.register('action', 'extend', ExtendAction)
parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                    help='verbose information on progress of the data checks')
parser.add_argument('-d', '--debug', dest='debug', action='store_true',
                    help='debug information on progress of the data checks')
parser.add_argument('-X', '--output-XLSX', dest='outputXLSX', nargs=1,
                    help='output of results into an XLSX with filename provided as parameter')
parser.add_argument('--output-XLSX-withdrawn', dest='outputXLSXwithdrawn', nargs=1,
                    help='output withdrawn biobanks and collections into an XLSX with filename provided as parameter')
parser.add_argument('-N', '--output-no-stdout', dest='nostdout', action='store_true',
                    help='no output of results into stdout (default: enabled)')
parser.add_argument('--purge-all-caches', dest='purgeCaches', action='store_const', const=cachesList,
                    help='disable all long remote checks (email address testing, geocoding, URLs')
parser.add_argument('--purge-cache', dest='purgeCaches', nargs='+', action='extend', choices=cachesList,
                    help='disable particular long remote checks')


parser.set_defaults(disableChecksRemote=[], disablePlugins=[], purgeCaches=[], filterCollType=[], filterMatType=[])
args = parser.parse_args()

if args.debug:
    log.basicConfig(format="%(levelname)s: %(message)s", level=log.DEBUG)
elif args.verbose:
    log.basicConfig(format="%(levelname)s: %(message)s", level=log.INFO)
else:
    log.basicConfig(format="%(levelname)s: %(message)s")


### Initialize variables
qual_label = {}

### Functions
def reshape_quality_table(df, entity, assess_level):
    """
    Adapt format of the quality table.

    Parameters:
        df: Input df with columns ['id', entity, 'quality_standard', assess_level]
        entity: Header of the second column of the dataframe
        assess_level: Name of the assess_level column

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

    return final_df

def outputExcelBiobanksCollections(filename : str, dfBiobanks : pd.DataFrame, biobanksLabel : str, dfCollections : pd.DataFrame, collectionsLabel : str, dfCombinedQual : pd.DataFrame, combQualLabel : str):
    log.info("Outputting warnings in Excel file " + filename)
    writer = pd.ExcelWriter(filename, engine='xlsxwriter')
    dfBiobanks.to_excel(writer, sheet_name=biobanksLabel)
    dfCollections.to_excel(writer, sheet_name=collectionsLabel)
    dfCombinedQual.to_excel(writer, sheet_name=combQualLabel)
    writer.close()

#### Main

dir = Directory(purgeCaches=args.purgeCaches, debug=args.debug, pp=pp)

log.info('Total biobanks: ' + str(dir.getBiobanksCount()))
log.info('Total collections: ' + str(dir.getCollectionsCount()))

### Get combined quality info

for collection in dir.getCollections():
    log.debug("Analyzing collection " + collection['id'])
    biobankId = dir.getCollectionBiobankId(collection['id'])
    biobank = dir.getBiobankById(biobankId)
    
    if 'contact' in collection:
        collection['contact'] = dir.getContact(collection['contact']['id'])

    collection_withdrawn = False
    if 'withdrawn' in collection and collection['withdrawn']:
        log.debug("Detected a withdrawn collection: " + collection['id'])
        collection_withdrawn = True
    if 'withdrawn' in biobank and biobank['withdrawn']:
        if not collection_withdrawn:
            log.debug("Detected a withdrawn collection " + collection['id'] + " because a withdrawn biobank: " + biobankId)
            collection_withdrawn = True
    if collection_withdrawn:
        continue

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

qualBBfinaldf = reshape_quality_table(qualBBdf, 'biobank', 'assess_level_bio')
qualCollfinaldf = reshape_quality_table(qualColldf, 'collection', 'assess_level_col')

outputExcelBiobanksCollections('QualityLabelsExporter.xlsx', qualBBfinaldf, "Biobanks", qualCollfinaldf, "Collections", combinedQualitydf, "CombinedQuality")
