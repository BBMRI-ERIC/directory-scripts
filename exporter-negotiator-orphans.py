#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

import logging as log
import os.path
import pprint
import re

import pandas as pd

from cli_common import (
    add_logging_arguments,
    add_no_stdout_argument,
    add_purge_cache_arguments,
    add_xlsx_output_argument,
    build_parser,
    configure_logging,
)
from directory import Directory

QUALITY_LABELS = {'accredited', 'eric'}

cachesList = ['directory']

pp = pprint.PrettyPrinter(indent=4)


def parse_email_list(raw_value):
    if raw_value is None or (isinstance(raw_value, float) and pd.isna(raw_value)):
        return set()
    emails = []
    for item in str(raw_value).split(';'):
        item = item.strip().lower()
        if item:
            emails.append(item)
    return set(emails)

def _normalize_quality_value(value):
    if isinstance(value, dict):
        return value.get('id', '')
    return value if value is not None else ''


def _extract_quality_values(value):
    values = []
    if value is None:
        return values
    if isinstance(value, list):
        for item in value:
            values.append(_normalize_quality_value(item))
    else:
        values.append(_normalize_quality_value(value))
    return values


def get_country_code_from_id(collection_id):
    if not collection_id:
        return ""
    value = str(collection_id)
    if value.startswith("ID:"):
        value = value[3:]
    if ":" in value:
        value = value.split(":", 1)[0]
    if "_" in value:
        value = value.split("_", 1)[0]
    return value


def get_parent_chain_ids(collection, collection_map):
    parents = []
    seen = set()
    current = collection
    while 'parent_collection' in current:
        parent_id = current['parent_collection']['id']
        if parent_id in seen:
            log.warning("Parent cycle detected for %s at %s", collection['id'], parent_id)
            break
        seen.add(parent_id)
        parent = collection_map.get(parent_id)
        if parent is None:
            log.warning("Parent collection %s not found for %s", parent_id, collection['id'])
            break
        parents.append(parent_id)
        current = parent
    return parents


def get_nn_from_biobank_id(biobank_id):
    if not biobank_id:
        return ""
    match = re.search(r'ID:([^_]+)_', str(biobank_id))
    if match:
        return match.group(1)
    return ""


def get_nn_for_collection(collection_id, collection):
    if collection:
        biobank_id = collection['biobank']['id']
        return get_nn_from_biobank_id(biobank_id)
    return get_country_code_from_id(collection_id)


parser = build_parser()
parser.add_argument('input_xlsx', help='input XLSX (Negotiator representatives list)')
add_logging_arguments(parser)
add_xlsx_output_argument(parser)
add_no_stdout_argument(parser)
add_purge_cache_arguments(parser, ['directory'])
parser.set_defaults(purgeCaches=[])
args = parser.parse_args()

configure_logging(args)

if not os.path.exists(args.input_xlsx):
    raise FileNotFoundError(args.input_xlsx)

dir = Directory(purgeCaches=args.purgeCaches, debug=args.debug, pp=pp)

log.info('Total biobanks: ' + str(dir.getBiobanksCount()))
log.info('Total collections: ' + str(dir.getCollectionsCount()))

qual_col_df = dir.getQualColl()
collection_quality_ids = set()
if isinstance(qual_col_df, pd.DataFrame) and not qual_col_df.empty:
    if 'assess_level_col' in qual_col_df.columns and 'collection' in qual_col_df.columns:
        for _, row in qual_col_df.iterrows():
            if _normalize_quality_value(row.get('assess_level_col')) in QUALITY_LABELS:
                collection_id = _normalize_quality_value(row.get('collection'))
                if collection_id:
                    collection_quality_ids.add(collection_id)

biobank_quality_ids = set()
qual_bb_df = dir.getQualBB()
if isinstance(qual_bb_df, pd.DataFrame) and not qual_bb_df.empty:
    if 'assess_level_bio' in qual_bb_df.columns and 'biobank' in qual_bb_df.columns:
        for _, row in qual_bb_df.iterrows():
            if _normalize_quality_value(row.get('assess_level_bio')) in QUALITY_LABELS:
                biobank_id = _normalize_quality_value(row.get('biobank'))
                if biobank_id:
                    biobank_quality_ids.add(biobank_id)

df_input = pd.read_excel(args.input_xlsx)
required_columns = [
    'network_name',
    'biobank_name',
    'resource_name',
    'resource_source_id',
    'representatives_emails',
]
missing_columns = [c for c in required_columns if c not in df_input.columns]
if missing_columns:
    raise ValueError("Missing required columns: " + ", ".join(missing_columns))

rows_by_collection = {}
reps_by_collection = {}
for _, row in df_input.iterrows():
    collection_id = row.get('resource_source_id')
    if collection_id is None or (isinstance(collection_id, float) and pd.isna(collection_id)):
        log.warning("Row without resource_source_id found, skipping.")
        continue
    collection_id = str(collection_id).strip()
    reps = parse_email_list(row.get('representatives_emails'))
    if collection_id in reps_by_collection:
        log.warning("Duplicate resource_source_id in input: %s (merging representatives)", collection_id)
        reps_by_collection[collection_id] = reps_by_collection[collection_id].union(reps)
        existing = rows_by_collection[collection_id]
        for key in ['network_name', 'biobank_name', 'resource_name']:
            if not existing.get(key) and row.get(key):
                existing[key] = row.get(key)
    else:
        rows_by_collection[collection_id] = {
            'network_name': row.get('network_name') or "",
            'biobank_name': row.get('biobank_name') or "",
            'resource_name': row.get('resource_name') or "",
        }
        reps_by_collection[collection_id] = reps

collection_map_all = {}
collection_map_active = {}
biobank_to_collections = {}
biobank_to_collections_all = {}
biobank_to_collections_withdrawn = {}
biobank_to_collections_active = {}
for collection in dir.getCollections():
    collection_id = collection['id']
    collection_map_all[collection_id] = collection
    biobank_id = collection['biobank']['id']
    biobank_to_collections_all.setdefault(biobank_id, []).append(collection_id)
    if collection.get('withdrawn'):
        biobank_to_collections_withdrawn.setdefault(biobank_id, []).append(collection_id)
        continue
    collection_map_active[collection_id] = collection
    biobank_to_collections.setdefault(biobank_id, []).append(collection_id)
    biobank_to_collections_active.setdefault(biobank_id, []).append(collection_id)

biobank_map_all = {}
for biobank in dir.getBiobanks():
    biobank_map_all[biobank['id']] = biobank

for collection_id in collection_map_active:
    if collection_id not in rows_by_collection:
        log.warning("Collection %s not found in input XLSX", collection_id)

for collection_id in rows_by_collection:
    if collection_id not in collection_map_active:
        log.warning("Input collection %s not found in Directory or withdrawn", collection_id)

biobank_uniform_reps = {}
for biobank_id, collection_ids in biobank_to_collections.items():
    rep_sets = [reps_by_collection.get(cid, set()) for cid in collection_ids if reps_by_collection.get(cid, set())]
    if len(rep_sets) < 2:
        continue
    first = rep_sets[0]
    if all(rep_set == first for rep_set in rep_sets):
        biobank_uniform_reps[biobank_id] = first

collection_results = {}
for collection_id, collection in collection_map_active.items():
    reps = reps_by_collection.get(collection_id, set())
    with_reps = bool(reps)
    biobank_id = collection['biobank']['id']
    inferred_by_biobank = False
    if not with_reps and biobank_id in biobank_uniform_reps:
        inferred_by_biobank = True

    parent_reps = None
    if not with_reps:
        for parent_id in get_parent_chain_ids(collection, collection_map_all):
            parent = collection_map_all.get(parent_id)
            if parent is None:
                continue
            if parent.get('withdrawn'):
                continue
            parent_rep_set = reps_by_collection.get(parent_id, set())
            if parent_rep_set:
                parent_reps = parent_rep_set
                break
    inferred_by_parent = not with_reps and parent_reps is not None

    reps_list = ";".join(sorted(reps))
    parent_collection_id = ""
    if 'parent_collection' in collection:
        parent_collection_id = collection['parent_collection']['id']

    has_collection_quality = collection_id in collection_quality_ids
    has_ancestor_quality = False
    for parent_id in get_parent_chain_ids(collection, collection_map_all):
        if parent_id in collection_quality_ids:
            has_ancestor_quality = True
            break
    has_biobank_quality = biobank_id in biobank_quality_ids

    missing_reps_with_collection_quality = False
    if not with_reps and (has_collection_quality or has_ancestor_quality):
        missing_reps_with_collection_quality = True

    missing_reps_with_biobank_quality = False
    if not with_reps and not missing_reps_with_collection_quality and has_biobank_quality:
        missing_reps_with_biobank_quality = True

    collection_results[collection_id] = {
        'with_reps': with_reps,
        'auto_by_biobank': inferred_by_biobank,
        'auto_by_parent': inferred_by_parent,
        'representatives_emails': reps_list,
        'number_of_registered_representatives': len(reps),
        'parent_collection': parent_collection_id,
        'collection_has_quality': has_collection_quality,
        'ancestor_has_quality': has_ancestor_quality,
        'biobank_has_quality': has_biobank_quality,
        'missing_reps_with_collection_quality': missing_reps_with_collection_quality,
        'missing_reps_with_biobank_quality': missing_reps_with_biobank_quality,
    }

output_rows = []
for collection_id, row in rows_by_collection.items():
    collection = collection_map_all.get(collection_id)
    result = collection_results.get(collection_id, {
        'with_reps': bool(reps_by_collection.get(collection_id, set())),
        'auto_by_biobank': False,
        'auto_by_parent': False,
        'representatives_emails': ";".join(sorted(reps_by_collection.get(collection_id, set()))),
        'number_of_registered_representatives': len(reps_by_collection.get(collection_id, set())),
        'parent_collection': "",
        'collection_has_quality': False,
        'ancestor_has_quality': False,
        'biobank_has_quality': False,
    })
    if collection and 'parent_collection' in collection:
        result['parent_collection'] = collection['parent_collection']['id']
    nn_code = get_nn_for_collection(collection_id, collection)
    if collection:
        if collection.get('withdrawn'):
            log.warning("Withdrawn collection %s present in output input set", collection_id)
        biobank_id = collection['biobank']['id']
        biobank = biobank_map_all.get(biobank_id)
        if biobank and biobank.get('withdrawn'):
            log.warning("Collection %s belongs to withdrawn biobank %s and is present in output input set", collection_id, biobank_id)
        country_code = dir.getCollectionNN(collection_id)
    else:
        country_code = get_country_code_from_id(collection_id)

    output_rows.append({
        'nn': nn_code,
        'country_code': country_code,
        'network_name': row.get('network_name', ''),
        'biobank_name': row.get('biobank_name', ''),
        'resource_name': row.get('resource_name', ''),
        'resource_source_id': collection_id,
        'parent_collection': result['parent_collection'],
        'representatives_emails': result['representatives_emails'],
        'number_of_registered_representatives': result['number_of_registered_representatives'],
        'collection_has_quality': result['collection_has_quality'],
        'ancestor_has_quality': result['ancestor_has_quality'],
        'biobank_has_quality': result['biobank_has_quality'],
        'with_reps': result['with_reps'],
        'auto_by_biobank': result['auto_by_biobank'],
        'auto_by_parent': result['auto_by_parent'],
    })

for collection_id, collection in collection_map_active.items():
    row = rows_by_collection.get(collection_id, {})
    if not row:
        biobank = collection.get('biobank', {})
        row = {
            'network_name': ";".join([n.get('name', '') for n in collection.get('networks', []) if n.get('name')]),
            'biobank_name': biobank.get('name', ''),
            'resource_name': collection.get('name', ''),
        }

    result = collection_results[collection_id]

    if not (result['with_reps'] or result['auto_by_biobank'] or result['auto_by_parent']):
        continue

    if collection_id not in rows_by_collection:
        output_rows.append({
            'nn': get_nn_from_biobank_id(collection['biobank']['id']),
            'country_code': dir.getCollectionNN(collection_id),
            'network_name': row.get('network_name', ''),
            'biobank_name': row.get('biobank_name', ''),
            'resource_name': row.get('resource_name', ''),
            'resource_source_id': collection_id,
            'parent_collection': result['parent_collection'],
            'representatives_emails': result['representatives_emails'],
            'number_of_registered_representatives': result['number_of_registered_representatives'],
            'collection_has_quality': result['collection_has_quality'],
            'ancestor_has_quality': result['ancestor_has_quality'],
            'biobank_has_quality': result['biobank_has_quality'],
            'with_reps': result['with_reps'],
            'auto_by_biobank': result['auto_by_biobank'],
            'auto_by_parent': result['auto_by_parent'],
        })

df_output = pd.DataFrame(output_rows)
if not df_output.empty:
    df_output.sort_values(
        by=['with_reps', 'auto_by_biobank', 'auto_by_parent', 'resource_source_id'],
        ascending=[False, False, False, True],
        inplace=True,
    )

output_collection_ids = {row['resource_source_id'] for row in output_rows}
for collection_id in collection_map_active:
    if collection_id not in output_collection_ids:
        log.warning("Directory collection %s not present in output", collection_id)

output_biobank_ids = set()
for collection_id in output_collection_ids:
    collection = collection_map_all.get(collection_id)
    if collection:
        output_biobank_ids.add(collection['biobank']['id'])
for biobank_id, biobank in biobank_map_all.items():
    if biobank.get('withdrawn'):
        continue
    if biobank_id not in output_biobank_ids:
        total_collections = len(biobank_to_collections_all.get(biobank_id, []))
        withdrawn_collections = len(biobank_to_collections_withdrawn.get(biobank_id, []))
        active_collections = len(biobank_to_collections_active.get(biobank_id, []))
        if total_collections == 0:
            reason = "no collections"
        elif active_collections == 0:
            reason = "only withdrawn collections"
        else:
            reason = "active collections"
        log.warning(
            "Active Directory biobank %s not present in output (%s, total=%d, withdrawn=%d, active=%d)",
            biobank_id,
            reason,
            total_collections,
            withdrawn_collections,
            active_collections,
        )

if not args.nostdout:
    print(df_output.to_csv(sep="\t", index=False))

if args.outputXLSX:
    filename = args.outputXLSX[0]
    log.info("Outputting results to Excel file " + filename)
    writer = pd.ExcelWriter(filename, engine='xlsxwriter')
    biobank_rows = []
    # Include biobanks without any collections: biobank_to_collections is derived from iterating
    # active (non-withdrawn) collections, which misses biobanks that have no collections at all.
    for biobank_id, biobank_stub in biobank_map_all.items():
        if biobank_stub.get('withdrawn'):
            continue
        collection_ids = biobank_to_collections.get(biobank_id, [])
        biobank = dir.getBiobankById(biobank_id)
        with_reps_count = 0
        without_reps_count = 0
        auto_by_biobank_count = 0
        auto_by_parent_count = 0
        missing_reps_with_collection_quality = 0
        missing_reps_with_biobank_quality = 0
        for collection_id in collection_ids:
            result = collection_results.get(collection_id)
            if result is None:
                continue
            if result['with_reps']:
                with_reps_count += 1
            else:
                without_reps_count += 1
            if result['auto_by_biobank']:
                auto_by_biobank_count += 1
            if result['auto_by_parent']:
                auto_by_parent_count += 1
            if result['missing_reps_with_collection_quality']:
                missing_reps_with_collection_quality += 1
            if result['missing_reps_with_biobank_quality']:
                missing_reps_with_biobank_quality += 1
        biobank_rows.append({
            'nn': get_nn_from_biobank_id(biobank_id),
            'country_code': dir.getBiobankNN(biobank_id),
            'biobank_name': biobank.get('name', '') if biobank else '',
            'biobank_id': biobank_id,
            'total_collections': len(biobank_to_collections_all.get(biobank_id, [])),
            'collections_with_reps': with_reps_count,
            'collections_without_reps': without_reps_count,
            'collections_auto_by_biobank': auto_by_biobank_count,
            'collections_auto_by_parent': auto_by_parent_count,
            'collections_without_reps_with_collection_quality': missing_reps_with_collection_quality,
            'collections_without_reps_with_biobank_quality': missing_reps_with_biobank_quality,
        })
    df_biobanks = pd.DataFrame(biobank_rows)
    if not df_biobanks.empty:
        df_biobanks.sort_values(by=['country_code', 'biobank_id'], inplace=True)
    if not df_biobanks.empty:
        nn_groups = []
        for nn, group in df_biobanks.groupby('nn'):
            active_collections = group['collections_with_reps'] + group['collections_without_reps']
            nn_groups.append({
                'nn': nn,
                'sum_biobanks': len(group),
                'sum_biobanks_without_missing_reps': int(((active_collections > 0) & (group['collections_without_reps'] == 0)).sum()),
                'sum_biobanks_missing_and_with_reps': int(((active_collections > 0) & (group['collections_without_reps'] != 0) & (group['collections_with_reps'] != 0)).sum()),
                'sum_biobanks_without_reps': int(((active_collections > 0) & (group['collections_with_reps'] == 0)).sum()),
                'sum_biobanks_without_collections': int((group['total_collections'] == 0).sum()),
                'sum_collections_with_reps': int(group['collections_with_reps'].sum()),
                'sum_collections_without_reps': int(group['collections_without_reps'].sum()),
                'sum_collections_without_reps_with_collection_quality': int(group['collections_without_reps_with_collection_quality'].sum()),
                'sum_collections_without_reps_with_biobank_quality': int(group['collections_without_reps_with_biobank_quality'].sum()),
                'sum_collections_auto_by_biobank': int(group['collections_auto_by_biobank'].sum()),
                'sum_collections_auto_by_parent': int(group['collections_auto_by_parent'].sum()),
            })
        df_nn = pd.DataFrame(nn_groups)
        df_nn.sort_values(by=['nn'], inplace=True)
        active_collections_all = df_biobanks['collections_with_reps'] + df_biobanks['collections_without_reps']
        totals = {
            'nn': 'TOTAL',
            'sum_biobanks': int(df_biobanks.shape[0]),
            'sum_biobanks_without_missing_reps': int(((active_collections_all > 0) & (df_biobanks['collections_without_reps'] == 0)).sum()),
            'sum_biobanks_missing_and_with_reps': int(((active_collections_all > 0) & (df_biobanks['collections_without_reps'] != 0) & (df_biobanks['collections_with_reps'] != 0)).sum()),
            'sum_biobanks_without_reps': int(((active_collections_all > 0) & (df_biobanks['collections_with_reps'] == 0)).sum()),
            'sum_biobanks_without_collections': int((df_biobanks['total_collections'] == 0).sum()),
            'sum_collections_with_reps': int(df_biobanks['collections_with_reps'].sum()),
            'sum_collections_without_reps': int(df_biobanks['collections_without_reps'].sum()),
            'sum_collections_without_reps_with_collection_quality': int(df_biobanks['collections_without_reps_with_collection_quality'].sum()),
            'sum_collections_without_reps_with_biobank_quality': int(df_biobanks['collections_without_reps_with_biobank_quality'].sum()),
            'sum_collections_auto_by_biobank': int(df_biobanks['collections_auto_by_biobank'].sum()),
            'sum_collections_auto_by_parent': int(df_biobanks['collections_auto_by_parent'].sum()),
        }
        df_nn = pd.concat([pd.DataFrame([totals]), df_nn], ignore_index=True)
        column_map = {
            'nn': 'National Node\n(staging area)',
            'sum_biobanks': 'Number of biobanks',
            'sum_biobanks_without_missing_reps': 'Number of biobanks completely represented in the Negotiator',
            'sum_biobanks_missing_and_with_reps': 'Number of biobanks partially represented in the Negotiator',
            'sum_biobanks_without_reps': 'Number of biobanks not represented in the Negotiator at all',
            'sum_biobanks_without_collections': 'Number of biobanks without collections',
            'sum_collections_with_reps': 'Number of collections with assigned representatives',
            'sum_collections_without_reps': 'Number of collections without assigned representatives',
            'sum_collections_without_reps_with_collection_quality': 'Number of Q-labeled collections without assigned representatives',
            'sum_collections_without_reps_with_biobank_quality': 'Number of other collections from Q-labeled biobanks without assigned representatives',
            'sum_collections_auto_by_parent': 'Number of collections which can be assigned representatives from their parent',
            'sum_collections_auto_by_biobank': 'Number of collections which potentially could be assigned representatives from other collections',
        }
        output_columns = [
            'nn',
            'sum_biobanks',
            'sum_biobanks_without_missing_reps',
            'sum_biobanks_missing_and_with_reps',
            'sum_biobanks_without_reps',
            'sum_biobanks_without_collections',
            'sum_collections_with_reps',
            'sum_collections_without_reps',
            'sum_collections_without_reps_with_collection_quality',
            'sum_collections_without_reps_with_biobank_quality',
            'sum_collections_auto_by_parent',
            'sum_collections_auto_by_biobank',
        ]
        df_nn = df_nn[output_columns].rename(columns=column_map)
        workbook = writer.book
        ws_summary = workbook.add_worksheet('nn_summary')
        writer.sheets['nn_summary'] = ws_summary
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#000000',
            'font_color': '#FFFFFF',
        })
        total_base = {
            'bold': True,
            'bg_color': '#FDD3B5',
        }
        row_white_base = {'bg_color': '#FFFFFF'}
        row_blue_base = {'bg_color': '#E6EEF6'}

        old_headers = output_columns
        ws_summary.write_row(0, 0, old_headers)
        ws_summary.set_row(0, None, None, {'hidden': True})
        ws_summary.write_row(1, 0, list(df_nn.columns), header_format)

        last_row_index = len(df_nn) - 1
        last_col_index = len(output_columns) - 1

        def border_flags(is_top=False, is_bottom=False, is_left=False, is_right=False):
            flags = {}
            if is_top:
                flags['top'] = 2
            if is_bottom:
                flags['bottom'] = 2
            if is_left:
                flags['left'] = 2
            if is_right:
                flags['right'] = 2
            return flags

        def make_format(base, italic=False, bold=False, borders=None):
            fmt = dict(base)
            if italic:
                fmt['italic'] = True
            if bold:
                fmt['bold'] = True
            if borders:
                fmt.update(borders)
            return workbook.add_format(fmt)

        header_formats = []
        for col_idx in range(len(output_columns)):
            borders = border_flags(
                is_top=True,
                is_bottom=True,
                is_left=(col_idx == 0),
                is_right=(col_idx == last_col_index),
            )
            header_formats.append(make_format({
                'bg_color': '#000000',
                'font_color': '#FFFFFF',
                'bold': True,
                'text_wrap': True,
            }, borders=borders))
        for col_idx, value in enumerate(list(df_nn.columns)):
            ws_summary.write(1, col_idx, value, header_formats[col_idx])

        red_columns = {3, 4, 5, 7, 8, 9}
        for i, row in enumerate(df_nn.itertuples(index=False), start=0):
            excel_row = i + 2
            is_total = i == 0
            is_last = i == last_row_index
            use_blue = i % 2 == 1
            for col_idx, value in enumerate(row):
                borders = border_flags(
                    is_top=is_total,
                    is_bottom=is_total or is_last,
                    is_left=(col_idx == 0),
                    is_right=(col_idx == last_col_index),
                )
                needs_red = False
                if col_idx in red_columns and isinstance(value, (int, float)) and value != 0:
                    needs_red = True
                if is_total:
                    base = dict(total_base)
                    fmt = make_format(base, italic=(col_idx == 0), bold=True, borders=borders)
                else:
                    base = dict(row_blue_base if use_blue else row_white_base)
                    fmt = make_format(base, italic=(col_idx == 0), borders=borders)
                if needs_red:
                    base['font_color'] = '#CE0000'
                    fmt = make_format(base, italic=(col_idx == 0), bold=True, borders=borders)
                ws_summary.write(excel_row, col_idx, value, fmt)
        header_labels = list(df_nn.columns)
        for col_idx, label in enumerate(header_labels):
            words = label.replace("\n", " ").split()
            longest = max((len(w) for w in words), default=10)
            width = min(max(longest + 2, 12), 30)
            ws_summary.set_column(col_idx, col_idx, width)

    df_output.to_excel(writer, sheet_name='negotiator_collection_stats', index=False)
    df_biobanks.to_excel(writer, sheet_name='biobanks_summary', index=False)
    writer.close()
