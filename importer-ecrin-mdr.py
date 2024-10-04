"""
Script that imports the ECRIN MDR studies into the BBMRI Directory.
The studies are associated to one or more collections. When a Study and a Collection are associated it means that
the Colection was created in the context of the Study

It gets in input:
    - a CSV file with three columns mdr_id,mdr_title,collection_id containing the id of the study in ECRIN, its title and
      the id of the corresponding collection in the directory
    - the url of the Directory where to store the data
    - the username and the password of the user with insert rights in the Directory

For each study in the CSV, the script:
  - gets the study information from the ECRIN MDR
  - creates a Study record in the Directory
  - creates an AlsoKnownIn record with the link to the study in ECRIN MDR
  - updates the Collection with the reference to the associated Study
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import sys
from collections import defaultdict, OrderedDict

import requests
from molgenis_emx2_pyclient import client
from molgenis_emx2_pyclient.exceptions import PyclientException

#
logger = logging.getLogger("ecrin_mdr_importer")
logger.setLevel(logging.INFO)

fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

hdlr = logging.StreamHandler()
hdlr.setLevel(logging.INFO)
hdlr.setFormatter(fmt)
logger.addHandler(hdlr)

ECRIN_URL = "https://newmdr.ecrin.org"
ECRIN_STUDY_API_ENDPOINT = f"{ECRIN_URL}/api/Study/AllDetails"
ECRIN_STUDY_URL = f"{ECRIN_URL}/Study"
ECRIN_STUDY_ALTERNATIVE_URL = "https://newmdr.ecrin.org/api/Study/ByRegId/11"

BBMRI_ALSO_KNOWN_IN = "AlsoKnownIn"
BBMRI_STUDY = "Studies"
BBMRI_COLLECTION = "Collections"
BBMRI_STUDY_ID_PREFIX = "bbmri_eric:studyID:"
BBMRI_AKI_ID_PREFIX = "ecrin-mdr:"

# These MDR IDS, for some reason, cannot be found using the ECRIN Study URL.
# They can be retrieved using the study identifier.
MISSING_MDR_IDS = {
    '2541233': '2021-001072-41',
    '2541230': '2021-001054-57',
    '2537617': '2017-004737-85',
    '2541424': '2021-002327-38',
    '2541631': '2021-005051-37'
}


def create_output_dir(output_dir):
    """
    Checks whether the directory to store the csv files exists. If not, it creates it

    :return: the abspath of the directory
    """
    if not os.path.isabs(output_dir):
        absdir = os.path.abspath(os.path.join(os.path.curdir, output_dir))
    else:
        absdir = output_dir

    if not os.path.exists(absdir):
        os.mkdir(absdir)
    return absdir


def file_exist(file_argument):
    """
    ArgumentParser validator to check whether the input file exist
    """
    if os.path.exists(file_argument):
        return file_argument
    raise argparse.ArgumentTypeError("File {} does not exist".format(file_argument))


def get_studies_collections_link(input_file):
    """
    Reads the csv file and generates a dictionary with the mapping between the mdr study and the bbmri collection
    """
    with open(input_file) as f:
        reader = csv.DictReader(f)
        studies_collections = {}

        for match in reader:
            studies_collections[(match["mdr_id"], match["mdr_title"])] = f"bbmri-eric:ID:{match["collection_id"]}"

        return studies_collections


def get_age_unit(min_age, max_age):
    """
    Maps age unit values of the MDR to the ones in the BBMRI Directory.
    """
    mapping = {
        "Years": "YEAR",
        "Months": "MONTH",
        "Weeks": "WEEK"
    }

    if min_age and max_age:
        assert min_age["unit_name"] == max_age["unit_name"]
    unit = (min_age or max_age).get("unit_name") if (min_age or max_age) else None
    return mapping.get(unit)


def get_sex_value(ecrin_gender_eligibility):
    return {
        "Male": "MALE",
        "Female": "FEMALE",
        "Not provided": "NAV",
        "All": ["MALE", "FEMALE"]
    }[ecrin_gender_eligibility]


def get_study_details_from_ecrin_mdr(mdr_id):
    """
    Gets the details of the study with id :mdr_id: from the ECRIN MDR

    :param mdr_id: the id of the study
    :return: a dict with the study details if the study was found, None otherwise
    """
    logger.debug("Getting study details")
    res = requests.get(f"{ECRIN_STUDY_API_ENDPOINT}/{mdr_id}")
    if res.status_code == 200:
        return res.json()["full_study"]
    else:
        logger.info("Failed getting the study with the MDR ID. Using the alternative: %s" % MISSING_MDR_IDS[mdr_id])
        alternative_id = MISSING_MDR_IDS[mdr_id]
        res = requests.get(f"{ECRIN_STUDY_ALTERNATIVE_URL}/{alternative_id}")
        if res.status_code == 200:
            # The structure of the json of the alternative MDR url is different
            data = json.loads(res.json()[0])
            return {
                "id": data["study_id"],
                "brief_description": data["description"],
                "study_enrolment": "",
                "min_age": {"value": data["min_age"], "unit_name": "YEAR"} if data["min_age"] is not None else None,
                "max_age": {"value": data["max_age"], "unit_name": "YEAR"} if data["max_age"] is not None else None,
                "study_type": {"name": data["type_name"]},
                "study_gender_elig": {"name": data["gender_elig"]},
                "display_title": data["study_name"]
            }


def create_studies_records(mdr_data, mdr_title):
    """
    Creates the records to be stored in EMX2

    In particular, it creates two records:
     - study, with data of the ECRIN MDR study
     - also_known_in, to link the newly created study to its record in ECRIN MDR.
    It also updates the collections linked to the study with the reference to the newly created study
    """

    also_known_id = f"{BBMRI_AKI_ID_PREFIX}{mdr_data["id"]}"  # internal bbmri id of the "also_known_entity" corresponding to the study
    study_id = f"{BBMRI_STUDY_ID_PREFIX}{mdr_data["id"]}"  # internal bbmri id of the study
    # creates the also known record
    also_known = {
        "id": also_known_id,
        "name_system": "ECRIN MDR",
        "pid": mdr_data["id"],
        "url": f"{ECRIN_STUDY_URL}/{mdr_data["id"]}",
        "national_node": "EXT",
        "label": mdr_data["display_title"]
    }

    try:
        number_of_subject = int(mdr_data["study_enrolment"])
    except (ValueError, TypeError):
        number_of_subject = None
    # creates the study record
    sex = get_sex_value(mdr_data["study_gender_elig"]["name"])

    study = {
        "id": study_id,
        "title": mdr_title,
        "description": mdr_data["brief_description"],
        "type": mdr_data["study_type"]["name"],
        "number_of_subjects": number_of_subject,
        "sex": sex if isinstance(sex, str) else ",".join(sex),
        "age_low": mdr_data["min_age"].get("value") if mdr_data["min_age"] is not None else None,
        "age_high": mdr_data["max_age"].get("value") if mdr_data["max_age"] is not None else None,
        "age_unit": get_age_unit(mdr_data["min_age"], mdr_data["max_age"]),
        "also_known": also_known_id,
        "national_node": "EXT"
    }

    return {
        "AlsoKnownIn": also_known,
        "Studies": study
    }


def create_collection_records(eric_client, collections):
    new_collections = []
    for collection_id, studies_ids in collections.items():
        try:
            collection = eric_client.get(table="Collections", query_filter=f"id=={collection_id}", schema="ERIC")[0]
        except IndexError:
            logger.error(collection_id)
        collection["study"] = ",".join(set(collection["study"].split(",")).union(set(studies_ids)))
        new_collections.append(collection)
    return new_collections


async def upload_files_to_directory(emx2_client, entities, output_dir):
    for k, v in entities.items():
        logger.info("Created %d records of type %s", len(v), k)
        with open(f"{output_dir}/{k}.csv", "w") as outfile:
            fieldnames = list(v[0].keys())
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(v)

    for filename in ("AlsoKnownIn.csv", "Studies.csv", "Collections.csv"):
        try:
            await emx2_client.upload_file(file_path=f"{output_dir}/{filename}", schema="ERIC")
        except PyclientException:
            logger.error(f"Error uploading {filename}")
            sys.exit(-1)


async def main(input_file, url, username, password, output_dir):
    studies_collections = get_studies_collections_link(input_file)

    with client.Client(url=url) as emx2_client:
        emx2_client.signin(username, password)
        entities = OrderedDict({
            "AlsoKnownIn": [],
            "Studies": []
        })
        collections_studies = defaultdict(list)
        failed_studies = []
        for (mdr_id, mdr_title), collection_id in studies_collections.items():
            # for collections, we first collect only the ids of the studies
            logger.info("Processing study %s" % mdr_id)
            study_details = get_study_details_from_ecrin_mdr(mdr_id)
            if study_details is None:
                logger.error("Couldn't find details for study %s" % mdr_id)
                failed_studies.append(mdr_id)
            else:
                logger.info("Found study details. Creating records")
                collections_studies[collection_id].append(f"{BBMRI_STUDY_ID_PREFIX}{mdr_id}")
                records = create_studies_records(study_details, mdr_title)
                entities["AlsoKnownIn"].append(records["AlsoKnownIn"])
                entities["Studies"].append(records["Studies"])

        entities["Collections"] = create_collection_records(emx2_client, collections_studies)
        await upload_files_to_directory(emx2_client, entities, output_dir)
        logger.error(f"Failed studies {failed_studies}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", "-i", dest="input_file", type=file_exist, required=True,
                        help="CSV file with mdr and csv matchings")
    parser.add_argument("--url", "-u", type=str, required=True, help="the url of the BBMRI directory")
    parser.add_argument("--username", "-U", type=str, required=True,
                        help="the user name of the user of the BBMRI directory")
    parser.add_argument("--password", "-P", type=str, required=True,
                        help="the password of the user of the BBMRI directory")
    parser.add_argument("--output-dir", "-o", type=str, required=False,
                        help="The director that will contain the csv to be uploaded", default="./ecrin-data")

    args = parser.parse_args()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    outdir = create_output_dir(args.output_dir)

    try:
        asyncio.run(main(args.input_file, args.url, args.username, args.password, outdir))
    except KeyboardInterrupt:
        pass
