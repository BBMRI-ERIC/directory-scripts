#!/usr/bin/python3
# vim:ts=4:sw=4:sts=4:tw=0:et

import re
from builtins import str, isinstance, len, set, int
from typing import List
import pandas as pd

def extractContactDetails (df : pd.DataFrame):
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
    for (col, attr) in rules:
        if col in df:
            #df[col] = df[col].map(lambda v: ",".join(map(lambda x: x[attr] if type(x) is dict and attr in x else x, (v if type(v) is list else [v]))) if v and (type(v) is dict or type(v) is list) else "")
            # Allow those values that do not have id:
            df[col] = df[col].map(lambda v: ",".join(str(x.get(attr, '')) if isinstance(x, dict) and attr else str(x) for x in (v if isinstance(v, list) else [v])) if v else "")

def tidyCollectionDf (df : pd.DataFrame):
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
    df.sort_values(by=['country','id'],ascending=True,inplace=True)

def tidyBiobankDf (df : pd.DataFrame):
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
    df.sort_values(by=['country','id'],ascending=True,inplace=True)
            
