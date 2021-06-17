#!/usr/bin/python3
# vim:ts=4:sw=4:tw=0:et

import re
from builtins import str, isinstance, len, set, int
from typing import List
import pandas as pd

def tidyCollectionDf (df : pd.DataFrame):
    for (col, attr) in [('country','id'),('biobank','name'),('parent_collection','id')]:
        if col in df:
            df[col] = df[col].map(lambda x: x[attr] if type(x) is dict and attr in x else x)
    for col in ('order_of_magnitude','order_of_magnitude_donors'):
        if col in df:
            df[col] = df[col].map(lambda x: "%d (%s)"%(x['id'],x['size']) if type(x) is dict else x)
    for col in ('type','also_known','data_categories','quality','sex','age_unit','body_part_examined','imaging_modality','image_dataset_type','materials','storage_temperatures','sub_collections','data_use'):
        df[col] = df[col].map(lambda x: ",".join([e['id'] for e in x]) )
    df['diagnosis_available'] = df['diagnosis_available'].map(lambda x: ",".join([re.sub('^urn:miriam:icd:','',e['id']) for e in x]) )
    df['contact_email'] = df['contact'].apply(lambda c: c['email'])
    df['contact_name'] = df['contact'].apply(lambda c: " ".join([x for x in [c.get('first_name'), c.get('last_name')] if x]))
    df['contact_name_with_titles'] = df['contact'].apply(lambda c: " ".join([x for x in [c.get('title_before_name'), c.get('first_name'), c.get('last_name'), c.get('title_after_name')] if x]))
    #del df['contact_priority']

