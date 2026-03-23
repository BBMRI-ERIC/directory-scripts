#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

import logging as log
import pprint

import pandas as pd

from cli_common import (
    add_directory_schema_argument,
    add_logging_arguments,
    add_no_stdout_argument,
    add_purge_cache_arguments,
    add_withdrawn_scope_arguments,
    add_xlsx_output_argument,
    build_directory_kwargs,
    build_parser,
    configure_logging,
)
from directory import Directory
from geojsonutils import get_entity_coordinates, make_point_feature, write_feature_collection
import pddfutils
from xlsxutils import write_xlsx_tables


cachesList = ['directory']
pp = pprint.PrettyPrinter(indent=4)


parser = build_parser()
add_logging_arguments(parser)
add_xlsx_output_argument(parser, default_filename='cMDR.xlsx')
add_no_stdout_argument(parser)
add_directory_schema_argument(parser, default="ERIC")
add_withdrawn_scope_arguments(parser)
add_purge_cache_arguments(parser, cachesList)
parser.add_argument(
    '-G',
    '--output-geojson',
    dest='outputGeoJSON',
    nargs=1,
    help='write linked collections and studies as GeoJSON point features',
)
parser.set_defaults(purgeCaches=[])
args = parser.parse_args()

configure_logging(args)

dir = Directory(**build_directory_kwargs(args, pp=pp))


def buildDirectoryEntityURL(entity_route: str, entity_id: str) -> str:
    base_url = dir.getDirectoryUrl().rstrip('/')
    return f"{base_url}/{dir.getSchema()}/directory/#/{entity_route}/{entity_id}"


def _sort_rows(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda row: (row.get('country', ''), row['id']))


def _grouped_stdout(rows: list[dict], entity_label: str, formatter) -> None:
    if not rows:
        print(f"{entity_label}: none")
        return
    current_country = None
    for row in rows:
        country = row.get('country', '')
        if country != current_country:
            current_country = country
            print(current_country if current_country else "(no country)")
        print(f"   {formatter(row)}")


def _reorder_columns(df: pd.DataFrame, preferred_columns: list[str]) -> pd.DataFrame:
    ordered_columns = [column for column in preferred_columns if column in df.columns]
    ordered_columns.extend(column for column in df.columns if column not in ordered_columns)
    return df.loc[:, ordered_columns]


def _build_country_summary(
    biobank_rows: list[dict],
    collection_rows: list[dict],
    study_rows: list[dict],
) -> list[dict[str, int | str]]:
    country_codes = sorted(
        {
            row.get('country', '')
            for row in biobank_rows
        }.union(
            {
                row.get('country', '')
                for row in collection_rows
            }
        ).union(
            {
                item
                for row in study_rows
                for item in str(row.get('country', '')).split(',')
                if item
            }
        )
    )
    summary_rows = []
    for country_code in country_codes:
        summary_rows.append(
            {
                'country': country_code,
                'biobanks': sum(1 for row in biobank_rows if row.get('country', '') == country_code),
                'collections': sum(1 for row in collection_rows if row.get('country', '') == country_code),
                'studies': sum(
                    1
                    for row in study_rows
                    if country_code in [item for item in str(row.get('country', '')).split(',') if item]
                ),
            }
        )
    return summary_rows


def _get_collection_coordinates(collection: dict) -> tuple[list[float] | None, str]:
    coordinates = get_entity_coordinates(collection)
    if coordinates is not None:
        return coordinates, 'collection'
    biobank = dir.getBiobankById(collection['biobank']['id'])
    if biobank is None:
        return None, ''
    coordinates = get_entity_coordinates(biobank)
    if coordinates is not None:
        return coordinates, 'biobank'
    return None, ''


def _get_study_coordinates(study_id: str) -> tuple[list[float] | None, str, str]:
    study = dir.getStudyById(study_id, raise_on_missing=True)
    coordinates = get_entity_coordinates(study)
    if coordinates is not None:
        return coordinates, 'study', study_id
    for collection_id in dir.getStudyCollectionIds(study_id):
        collection = dir.getCollectionById(collection_id, raise_on_missing=True)
        collection_coordinates = get_entity_coordinates(collection)
        if collection_coordinates is not None:
            return collection_coordinates, 'collection', collection_id
        biobank = dir.getBiobankById(collection['biobank']['id'])
        if biobank is None:
            continue
        biobank_coordinates = get_entity_coordinates(biobank)
        if biobank_coordinates is not None:
            return biobank_coordinates, 'biobank', biobank['id']
    return None, '', ''


cmdrBiobanks = []
cmdrCollections = []
cmdrStudies = []

for biobank in dir.getBiobanks():
    linked_studies = dir.getBiobankStudies(biobank['id'])
    if not linked_studies:
        continue
    biobank_row = dict(biobank)
    biobank_row['country'] = dir.getBiobankCountry(biobank['id'])
    biobank_row['study_count'] = len(linked_studies)
    biobank_row['studies'] = [{'id': study['id']} for study in linked_studies]
    biobank_row['study_titles'] = ",".join(
        study.get('title', '') for study in linked_studies if study.get('title')
    )
    biobank_row['directoryURL'] = buildDirectoryEntityURL('biobank', biobank['id'])
    cmdrBiobanks.append(biobank_row)

for collection in dir.getCollections():
    linked_studies = dir.getCollectionStudies(collection['id'])
    if not linked_studies:
        continue
    collection_row = dict(collection)
    collection_row['country'] = dir.getCollectionCountry(collection['id'])
    collection_row['study_count'] = len(linked_studies)
    collection_row['studies'] = [{'id': study['id']} for study in linked_studies]
    collection_row['study_titles'] = ",".join(
        study.get('title', '') for study in linked_studies if study.get('title')
    )
    collection_row['directoryURL'] = buildDirectoryEntityURL('collection', collection['id'])
    cmdrCollections.append(collection_row)

for study in dir.getStudies():
    collection_ids = dir.getStudyCollectionIds(study['id'])
    if not collection_ids:
        continue
    study_row = dict(study)
    study_row['country'] = ",".join(dir.getStudyCountries(study['id']))
    study_row['collection_count'] = len(collection_ids)
    biobank_ids = dir.getStudyBiobankIds(study['id'])
    study_row['biobank_count'] = len(biobank_ids)
    study_row['collections'] = [{'id': collection_id} for collection_id in collection_ids]
    study_row['biobanks'] = [{'id': biobank_id} for biobank_id in biobank_ids]
    study_row['directoryURL'] = buildDirectoryEntityURL('study', study['id'])
    for index, collection_id in enumerate(collection_ids, start=1):
        study_row[f'collection_{index}'] = collection_id
        study_row[f'collection_{index}_directoryURL'] = buildDirectoryEntityURL('collection', collection_id)
    for index, biobank_id in enumerate(biobank_ids, start=1):
        study_row[f'biobank_{index}'] = biobank_id
        study_row[f'biobank_{index}_directoryURL'] = buildDirectoryEntityURL('biobank', biobank_id)
    cmdrStudies.append(study_row)

cmdrBiobanks = _sort_rows(cmdrBiobanks)
cmdrCollections = _sort_rows(cmdrCollections)
cmdrStudies = _sort_rows(cmdrStudies)
countrySummary = _build_country_summary(cmdrBiobanks, cmdrCollections, cmdrStudies)
studyBiobankColumnCount = max(
    (row.get('biobank_count', 0) for row in cmdrStudies),
    default=0,
)
studyCollectionColumnCount = max(
    (row.get('collection_count', 0) for row in cmdrStudies),
    default=0,
)

if not args.nostdout:
    print("Biobanks linked to one or more studies")
    _grouped_stdout(
        cmdrBiobanks,
        "Biobanks",
        lambda row: (
            f"{row['id']} - {row.get('name', '')} "
            f"[studies: {','.join(study['id'] for study in dir.getBiobankStudies(row['id']))}]"
        ),
    )
    print("")
    print("Collections linked to one or more studies")
    _grouped_stdout(
        cmdrCollections,
        "Collections",
        lambda row: (
            f"{row['id']} - {row.get('name', '')} "
            f"[studies: {','.join(study['id'] for study in dir.getCollectionStudies(row['id']))}]"
        ),
    )
    print("")
    print("Studies linked to one or more collections")
    _grouped_stdout(
        cmdrStudies,
        "Studies",
        lambda row: (
            f"{row['id']} - {row.get('title', '')} "
            f"[collections: {','.join(dir.getStudyCollectionIds(row['id']))}]"
        ),
    )
    print("")
    print("Per-country summary:")
    for row in countrySummary:
        label = row['country'] if row['country'] else "(no country)"
        print(
            f"- {label}: biobanks linked to studies = {row['biobanks']}, "
            f"collections linked to studies = {row['collections']}, "
            f"studies linked to collections = {row['studies']}"
        )
    print("")
    print("Totals:")
    print(f"- biobanks linked to studies: {len(cmdrBiobanks)}")
    print(f"- collections linked to studies: {len(cmdrCollections)}")
    print(f"- studies linked to collections: {len(cmdrStudies)}")

if args.outputXLSX is not None:
    pd_biobanks = pd.DataFrame(cmdrBiobanks)
    pd_collections = pd.DataFrame(cmdrCollections)
    pd_studies = pd.DataFrame(cmdrStudies)

    if not pd_biobanks.empty:
        pddfutils.tidyBiobankDf(pd_biobanks)
        pd_biobanks = _reorder_columns(
            pd_biobanks,
            ['country', 'id', 'name', 'study_count', 'studies', 'study_titles', 'directoryURL'],
        )
    if not pd_collections.empty:
        pddfutils.tidyCollectionDf(pd_collections)
        pd_collections = _reorder_columns(
            pd_collections,
            ['country', 'id', 'name', 'study_count', 'studies', 'study_titles', 'directoryURL'],
        )
    if not pd_studies.empty:
        pddfutils.tidyStudyDf(pd_studies)
        preferred_study_columns = [
            'country',
            'id',
            'title',
            'biobank_count',
            'collection_count',
            'biobanks',
            'collections',
            'directoryURL',
        ]
        for index in range(1, studyBiobankColumnCount + 1):
            preferred_study_columns.extend(
                [f'biobank_{index}', f'biobank_{index}_directoryURL']
            )
        for index in range(1, studyCollectionColumnCount + 1):
            preferred_study_columns.extend(
                [f'collection_{index}', f'collection_{index}_directoryURL']
            )
        pd_studies = _reorder_columns(pd_studies, preferred_study_columns)

    study_hyperlink_columns = [('id', 'directoryURL')]
    hidden_columns = ['directoryURL']
    for index in range(1, studyBiobankColumnCount + 1):
        display_column = f'biobank_{index}'
        url_column = f'biobank_{index}_directoryURL'
        study_hyperlink_columns.append((display_column, url_column))
        hidden_columns.append(url_column)
    for index in range(1, studyCollectionColumnCount + 1):
        display_column = f'collection_{index}'
        url_column = f'collection_{index}_directoryURL'
        study_hyperlink_columns.append((display_column, url_column))
        hidden_columns.append(url_column)

    write_xlsx_tables(
        args.outputXLSX[0],
        [
            (
                pd_biobanks,
                'Biobanks',
                False,
                {
                    'hyperlink_columns': [('id', 'directoryURL')],
                    'hide_columns': ['directoryURL'],
                },
            ),
            (
                pd_collections,
                'Collections',
                False,
                {
                    'hyperlink_columns': [('id', 'directoryURL')],
                    'hide_columns': ['directoryURL'],
                },
            ),
            (
                pd_studies,
                'Studies',
                False,
                {
                    'hyperlink_columns': study_hyperlink_columns,
                    'hide_columns': hidden_columns,
                },
            ),
        ],
    )

if args.outputGeoJSON is not None:
    features = []
    for collection in cmdrCollections:
        coordinates, source = _get_collection_coordinates(collection)
        if coordinates is None:
            log.warning("Skipping collection %s in GeoJSON output because no coordinates were found.", collection['id'])
            continue
        features.append(
            make_point_feature(
                {
                    'entity_type': 'collection',
                    'id': collection['id'],
                    'name': collection.get('name', ''),
                    'country': collection.get('country', ''),
                    'study_count': collection.get('study_count', 0),
                    'studies': dir.getCollectionStudyIds(collection['id']),
                    'coordinate_source': source,
                    'directoryURL': buildDirectoryEntityURL('collection', collection['id']),
                },
                coordinates,
            )
        )
    for study in cmdrStudies:
        coordinates, source, source_id = _get_study_coordinates(study['id'])
        if coordinates is None:
            log.warning("Skipping study %s in GeoJSON output because no coordinates were found.", study['id'])
            continue
        features.append(
            make_point_feature(
                {
                    'entity_type': 'study',
                    'id': study['id'],
                    'title': study.get('title', ''),
                    'country': study.get('country', ''),
                    'collection_count': study.get('collection_count', 0),
                    'collections': dir.getStudyCollectionIds(study['id']),
                    'coordinate_source': source,
                    'coordinate_source_id': source_id,
                    'directoryURL': buildDirectoryEntityURL('study', study['id']),
                },
                coordinates,
            )
        )
    output_geojson = args.outputGeoJSON[0]
    if not output_geojson.endswith('.geojson'):
        output_geojson = output_geojson + '.geojson'
    log.info("Writing GeoJSON export to %s", output_geojson)
    write_feature_collection(output_geojson, features)
