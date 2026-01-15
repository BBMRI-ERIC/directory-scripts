#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:sts=4:et

import argparse
import logging as log
import os.path
import pprint
import re

import pandas as pd

from directory import Directory

cachesList = ['directory', 'emails', 'geocoding', 'URLs']

pp = pprint.PrettyPrinter(indent=4)


class ExtendAction(argparse.Action):

    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest) or []
        items.extend(values)
        setattr(namespace, self.dest, items)


def parse_email_list(raw_value):
    if raw_value is None or (isinstance(raw_value, float) and pd.isna(raw_value)):
        return set()
    emails = []
    for item in str(raw_value).split(';'):
        item = item.strip().lower()
        if item:
            emails.append(item)
    return set(emails)


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


parser = argparse.ArgumentParser()
parser.register('action', 'extend', ExtendAction)
parser.add_argument('input_xlsx', help='input XLSX (Negotiator representatives list)')
parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help='verbose information on progress of the data checks')
parser.add_argument('-d', '--debug', dest='debug', action='store_true', help='debug information on progress of the data checks')
parser.add_argument('-X', '--output-XLSX', dest='outputXLSX', nargs=1, help='output of results into XLSX with filename provided as parameter')
parser.add_argument('-N', '--output-no-stdout', dest='nostdout', action='store_true', help='no output of results into stdout (default: enabled)')
parser.add_argument('--purge-all-caches', dest='purgeCaches', action='store_const', const=cachesList, help='disable all long remote checks (email address testing, geocoding, URLs')
parser.add_argument('--purge-cache', dest='purgeCaches', nargs='+', action='extend', choices=cachesList, help='disable particular long remote checks')
parser.set_defaults(disableChecksRemote=[], disablePlugins=[], purgeCaches=[])
args = parser.parse_args()

if args.debug:
    log.basicConfig(format="%(levelname)s: %(message)s", level=log.DEBUG)
elif args.verbose:
    log.basicConfig(format="%(levelname)s: %(message)s", level=log.INFO)
else:
    log.basicConfig(format="%(levelname)s: %(message)s")

if not os.path.exists(args.input_xlsx):
    raise FileNotFoundError(args.input_xlsx)

dir = Directory(purgeCaches=args.purgeCaches, debug=args.debug, pp=pp)

log.info('Total biobanks: ' + str(dir.getBiobanksCount()))
log.info('Total collections: ' + str(dir.getCollectionsCount()))

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
for collection in dir.getCollections():
    collection_id = collection['id']
    collection_map_all[collection_id] = collection
    if collection.get('withdrawn'):
        continue
    collection_map_active[collection_id] = collection
    biobank_id = collection['biobank']['id']
    biobank_to_collections.setdefault(biobank_id, []).append(collection_id)

for collection_id in collection_map_active:
    if collection_id not in rows_by_collection:
        log.warning("Collection %s not found in input XLSX", collection_id)

for collection_id in rows_by_collection:
    if collection_id not in collection_map_active:
        log.warning("Input collection %s not found in Directory or withdrawn", collection_id)

biobank_uniform_reps = {}
for biobank_id, collection_ids in biobank_to_collections.items():
    rep_sets = [reps_by_collection.get(cid, set()) for cid in collection_ids if reps_by_collection.get(cid, set())]
    if not rep_sets:
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

    collection_results[collection_id] = {
        'with_reps': with_reps,
        'auto_by_biobank': inferred_by_biobank,
        'auto_by_parent': inferred_by_parent,
        'representatives_emails': reps_list,
        'number_of_registered_representatives': len(reps),
        'parent_collection': parent_collection_id,
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
    })
    if collection and 'parent_collection' in collection:
        result['parent_collection'] = collection['parent_collection']['id']
    nn_code = get_nn_for_collection(collection_id, collection)
    if collection:
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

if not args.nostdout:
    print(df_output.to_csv(sep="\t", index=False))

if args.outputXLSX:
    filename = args.outputXLSX[0]
    log.info("Outputting results to Excel file " + filename)
    writer = pd.ExcelWriter(filename, engine='xlsxwriter')
    df_output.to_excel(writer, sheet_name='negotiator_orphans', index=False)
    biobank_rows = []
    for biobank_id, collection_ids in biobank_to_collections.items():
        biobank = dir.getBiobankById(biobank_id)
        with_reps_count = 0
        without_reps_count = 0
        auto_by_biobank_count = 0
        auto_by_parent_count = 0
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
        biobank_rows.append({
            'nn': get_nn_from_biobank_id(biobank_id),
            'country_code': dir.getBiobankNN(biobank_id),
            'biobank_name': biobank.get('name', '') if biobank else '',
            'biobank_id': biobank_id,
            'collections_with_reps': with_reps_count,
            'collections_without_reps': without_reps_count,
            'collections_auto_by_biobank': auto_by_biobank_count,
            'collections_auto_by_parent': auto_by_parent_count,
        })
    df_biobanks = pd.DataFrame(biobank_rows)
    if not df_biobanks.empty:
        df_biobanks.sort_values(by=['country_code', 'biobank_id'], inplace=True)
    df_biobanks.to_excel(writer, sheet_name='biobanks_summary', index=False)
    writer.close()
