#!/usr/bin/python3
# vim:ts=4:sw=4:sts=4:tw=0:et

"""Normalize and reshape pandas DataFrames used by Directory exporters."""

import re
from builtins import str, isinstance, len, set, int
from typing import List
import pandas as pd


def _sort_by_existing_columns(df: pd.DataFrame, columns: list):
    """Sort a dataframe in place by the requested columns that are present.

    Args:
        df: Dataframe mutated when at least one requested column exists.
        columns: Priority-ordered candidate column names.

    Returns:
        None. ``df`` is sorted ascending in place or left unchanged.
    """
    sort_columns = [column for column in columns if column in df]
    if sort_columns:
        df.sort_values(by=sort_columns, ascending=True, inplace=True)

def extractContactDetails (df : pd.DataFrame):
    """Flatten the optional ``contact`` column into export-friendly fields.

    Args:
        df: Dataframe mutated in place; a mapping-valued ``contact`` column is
            replaced by email, name, address, and phone columns when present.

    Returns:
        None. The original ``contact`` column is removed after extraction.

    Raises:
        AssertionError: If ``df`` is not a pandas dataframe.
    """
    assert isinstance(df, pd.DataFrame)
    if 'contact' in df:
        df['contact_email'] = df['contact'].apply(lambda c: c['email'] if type(c) is dict and 'email' in c else "")
        df['contact_name'] = df['contact'].apply(lambda c: " ".join([x for x in [c.get('first_name'), c.get('last_name')] if x]) if type(c) is dict else "")
        df['contact_name_with_titles'] = df['contact'].apply(lambda c: " ".join([x for x in [c.get('title_before_name'), c.get('first_name'), c.get('last_name'), c.get('title_after_name')] if x]) if type(c) is dict else "")
        for e in ['address', 'zip', 'city', 'country', 'phone']:
            # country is a dict, hence the 'id' hack
            df['contact_'+e] = df['contact'].apply(lambda c: c[e]['id'] if (type (c) is dict and e in c and type(c[e]) is dict and 'id' in c[e]) else c[e] if (type (c) is dict and e in c) else "").apply(lambda c: c.replace("\n",", "))
        del df['contact']

def linearizeStructures (df : pd.DataFrame, rules : list):
    """Convert configured structured dataframe columns to comma-separated text.

    Args:
        df: Dataframe mutated in place for columns named by ``rules``.
        rules: ``(column, attribute)`` pairs selecting a dictionary attribute or
            string form for each list/scalar value.

    Returns:
        None. Missing columns are ignored and present columns are overwritten.
    """
    for (col, attr) in rules:
        if col in df:
            #df[col] = df[col].map(lambda v: ",".join(map(lambda x: x[attr] if type(x) is dict and attr in x else x, (v if type(v) is list else [v]))) if v and (type(v) is dict or type(v) is list) else "")
            # Allow those values that do not have id:
            df[col] = df[col].map(lambda v: ",".join(str(x.get(attr, '')) if isinstance(x, dict) and attr else str(x) for x in (v if isinstance(v, list) else [v])) if v else "")

def tidyCollectionDf (df : pd.DataFrame):
    """Normalize a collection export dataframe in place and sort it by identity.

    Args:
        df: Collection dataframe whose nested fields are flattened and whose
            contact and list columns are made spreadsheet-friendly.

    Returns:
        None. ``df`` is mutated and sorted by available ``country`` and ``id``.

    Raises:
        AssertionError: If ``df`` is not a pandas dataframe.
    """
    assert isinstance(df, pd.DataFrame)
    linearizeStructures(df, [('country',''),('biobank','name'),('network','name'),('parent_collection','id')])
    for col in ('order_of_magnitude','order_of_magnitude_donors'):
        if col in df:
            df[col] = df[col].map(lambda x: "%d (%s)"%(x['id'],x['size']) if type(x) is dict else x)
    for col in ('type','data_categories','categories','sex','age_unit','body_part_examined','imaging_modality','image_dataset_type','materials','storage_temperatures', 'data_use','access_fee','access_joint_project','combined_quality','sop'):
        if col in df:
            df[col] = df[col].map(lambda x: ",".join([e for e in x]) if isinstance(x, list) else x)
    for col in ('also_known','quality','sub_collections','combined_network','studies'):
        if col in df:
            df[col] = df[col].map(lambda x: ",".join([e['id'] for e in x]) if isinstance(x, list) else x)
    if 'diagnosis_available' in df:
        df['diagnosis_available'] = df['diagnosis_available'].map(lambda x: ",".join([re.sub('^urn:miriam:icd:','',e['name']) for e in x]) if isinstance(x, list) else x)
    for col in ('national_node','head'): # Get values from dictionaries that are dict
        if col in df:
            df[col] = df[col].map(lambda x: ",".join([x['id']]) if isinstance(x, dict) else x)
    extractContactDetails(df)
    _sort_by_existing_columns(df, ['country', 'id'])

def tidyBiobankDf (df : pd.DataFrame):
    """Normalize a biobank export dataframe in place and remove internal fields.

    Args:
        df: Biobank dataframe whose nested values and contact details are
            flattened before unsupported operational columns are removed.

    Returns:
        None. ``df`` is mutated and sorted by available ``country`` and ``id``.

    Raises:
        AssertionError: If ``df`` is not a pandas dataframe.
    """
    assert isinstance(df, pd.DataFrame)
    linearizeStructures(df, [('country','id'), ('network','name'), ('covid19biobank','id'), ('capabilities','id'), ('quality','id')])
    extractContactDetails(df)
    for col in ['it_support_available', 'it_staff_size', 'is_available', 'his_available', 'partner_charter_signed', 'collections','contact']:
        if col in df:
            del df[col]
    for col in ('national_node','head'): # Get values from dictionaries that are not lists
        if col in df:
            df[col] = df[col].map(lambda x: ",".join([x['id']]) if isinstance(x, dict) else x)
    for col in ['also_known']:
        if col in df:
            df[col] = df[col].map(lambda x: ",".join([e['id'] for e in x]) if isinstance(x, list) else x)
    assert isinstance(df, pd.DataFrame)
    _sort_by_existing_columns(df, ['country', 'id'])

def tidyServiceDf (df : pd.DataFrame):
    """Normalize service parent and type fields for spreadsheet export.

    Args:
        df: Service dataframe mutated in place; biobank and service-type
            structures are rendered as text and rows are sorted by ``id``.

    Returns:
        None. ``df`` is modified in place.

    Raises:
        AssertionError: If ``df`` is not a pandas dataframe.
    """
    assert isinstance(df, pd.DataFrame)
    if 'biobank' in df:
        df['biobank'] = df['biobank'].map(
            lambda x: x.get('name') or x.get('id', '') if isinstance(x, dict) else x
        )
    linearizeStructures(df, [('national_node', 'id')])
    if 'serviceTypes' in df:
        df['serviceTypes'] = df['serviceTypes'].map(
            lambda x: ",".join(
                [
                    e.get('id') or e.get('name', '')
                    for e in x
                    if isinstance(e, dict)
                ]
            ) if isinstance(x, list) else x
        )
    _sort_by_existing_columns(df, ['id'])

def tidyStudyDf (df : pd.DataFrame):
    """Normalize study metadata and linked collection identifiers in place.

    Args:
        df: Study dataframe whose country, sex, collection, and alias structures
            are flattened for export.

    Returns:
        None. ``df`` is modified and sorted by available ``country`` and ``id``.

    Raises:
        AssertionError: If ``df`` is not a pandas dataframe.
    """
    assert isinstance(df, pd.DataFrame)
    linearizeStructures(df, [('national_node', 'id'), ('country', '')])
    for col in ('sex',):
        if col in df:
            df[col] = df[col].map(lambda x: ",".join([e for e in x]) if isinstance(x, list) else x)
    for col in ('collections', 'also_known'):
        if col in df:
            df[col] = df[col].map(
                lambda x: ",".join(
                    [
                        e.get('id', '')
                        for e in x
                        if isinstance(e, dict)
                    ]
                ) if isinstance(x, list) else x
            )
    _sort_by_existing_columns(df, ['country', 'id'])

def tidyContactDf (df : pd.DataFrame):
    """Normalize contact country and entity-reference columns in place.

    Args:
        df: Contact dataframe whose linked biobank, collection, and network
            mappings are converted to comma-separated identifiers.

    Returns:
        None. ``df`` is modified and sorted by available ``country`` and ``id``.

    Raises:
        AssertionError: If ``df`` is not a pandas dataframe.
    """
    assert isinstance(df, pd.DataFrame)
    for col in ('country',):
        if col in df:
            df[col] = df[col].map(lambda x: x.get('id', '') if isinstance(x, dict) else x)
    for col in ('biobanks', 'collections', 'networks'):
        if col in df:
            df[col] = df[col].map(
                lambda x: ",".join(
                    [
                        e.get('id', '')
                        for e in x
                        if isinstance(e, dict)
                    ]
                ) if isinstance(x, list) else x
            )
    _sort_by_existing_columns(df, ['country', 'id'])

def tidyNetworkDf (df : pd.DataFrame):
    """Normalize network references and sort a dataframe for export.

    Args:
        df: Network dataframe whose country, contact, and entity-reference
            structures are flattened in place.

    Returns:
        None. ``df`` is modified and sorted by available ``country`` and ``id``.

    Raises:
        AssertionError: If ``df`` is not a pandas dataframe.
    """
    assert isinstance(df, pd.DataFrame)
    linearizeStructures(df, [('country', 'id'), ('contact', 'id')])
    for col in ('contacts', 'biobanks', 'collections'):
        if col in df:
            df[col] = df[col].map(
                lambda x: ",".join(
                    [
                        e.get('id', '')
                        for e in x
                        if isinstance(e, dict)
                    ]
                ) if isinstance(x, list) else x
            )
    _sort_by_existing_columns(df, ['country', 'id'])
            
