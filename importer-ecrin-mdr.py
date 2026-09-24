"""
Script that imports the ECRIN MDR studies into the BBMRI Directory Staging area.
The studies are associated to one or more collections. When a Study and a Collection are associated it means that
the Collection was created in the context of the Study

It gets in input:
    - a CSV file with three columns mdr_id,mdr_title,collection_id containing the id of the study in ECRIN, its title and
      the id of the corresponding collection in the directory
    - the url of the Directory where to store the data
    - the username and the password of the user or alternatively the token with insert rights in the Directory
    - the name of the schema to use as
    - whether to directly upload the generated data or just create the csv files

For each study in the CSV, the script:
  - gets the study information from the ECRIN MDR
  - creates a Study record
  - creates an AlsoKnownIn record with the link to the study in ECRIN MDR
  - updates the Collection with the reference to the associated Study
The CSVs are grouped in the generated National Nodes directories

------------------------------------------------------------------------------

Authors:

  - Vittorio Meloni <vittorio.meloni@crs4.it>

Acknowledgments:

  - This work has been partially funded by the EOSC Future project (EU H2020 programme, grant agreement N. 101017536)
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import sys
from collections import defaultdict

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
ECRIN_STUDY_ALTERNATIVE_URL = f"{ECRIN_URL}/api/Study"
ECRIN_STUDY_URL = f"{ECRIN_URL}/Study"

BBMRI_ALSO_KNOWN_IN = "AlsoKnownIn"
BBMRI_STUDY = "Studies"
BBMRI_COLLECTION = "Collections"
BBMRI_STUDY_ID_PREFIX = "bbmri-eric:studyID:"
BBMRI_AKI_ID_PREFIX = "bbmri-eric:akiID:"


def create_output_dir(output_dir):
    """Resolve and, when absent, create the top-level CSV output directory.

    Args:
        output_dir: Absolute path or path relative to the current directory.

    Returns:
        Absolute path string for the existing or newly created directory.

    Raises:
        OSError: If the single directory cannot be created. Parent directories
            are not created recursively, and an existing path is not verified
            to be a directory.
    """
    if not os.path.isabs(output_dir):
        absdir = os.path.abspath(os.path.join(os.path.curdir, output_dir))
    else:
        absdir = output_dir

    if not os.path.exists(absdir):
        os.mkdir(absdir)
    return absdir


def file_exist(file_argument):
    """Validate that an argparse file argument names an existing path.

    Args:
        file_argument: Path string supplied for ``--input-file``.

    Returns:
        The unchanged path string when it exists; directories also satisfy this
        existence-only check.

    Raises:
        argparse.ArgumentTypeError: If the path does not exist.
    """
    if os.path.exists(file_argument):
        return file_argument
    raise argparse.ArgumentTypeError("File {} does not exist".format(file_argument))


def get_studies_collections_link(input_file):
    """Read ECRIN-study to Directory-collection links from a CSV file.

    Args:
        input_file: CSV path whose header must contain exact ``mdr_id``,
            ``mdr_title``, and ``collection_id`` columns.

    Returns:
        Mapping from ``(mdr_id, mdr_title)`` to collection IDs normalized as
        ``bbmri-eric:ID:<collection_id>``. A later duplicate study/title row
        replaces the earlier mapping.

    Raises:
        KeyError: If a required column is absent from a data row.
        OSError: If the CSV cannot be opened or read.
    """
    with open(input_file) as f:
        reader = csv.DictReader(f)
        studies_collections = {}

        for match in reader:
            studies_collections[(match["mdr_id"], match["mdr_title"])] = f"bbmri-eric:ID:{match["collection_id"]}"

        return studies_collections


def get_age_unit(min_age, max_age):
    """Map ECRIN age-unit metadata to a Directory ontology value.

    Args:
        min_age: Minimum-age mapping with ``unit_name``, or a false value.
        max_age: Maximum-age mapping with ``unit_name``, or a false value.

    Returns:
        ``YEAR``, ``MONTH``, or ``WEEK`` for supported ECRIN units; ``None``
        when both ages are absent or the selected unit is unknown.

    Raises:
        AssertionError: If both age bounds exist but use different units.
        KeyError: If a supplied age mapping lacks ``unit_name``.
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
    """Translate an ECRIN gender-eligibility label to Directory sex values.

    Args:
        ecrin_gender_eligibility: Exact ECRIN label ``Male``, ``Female``,
            ``Not provided``, or ``All``.

    Returns:
        One Directory sex code, or ``[MALE, FEMALE]`` for ``All``.

    Raises:
        KeyError: If the ECRIN label is not one of the four supported values.
    """
    return {
        "Male": "MALE",
        "Female": "FEMALE",
        "Not provided": "NAV",
        "All": ["MALE", "FEMALE"]
    }[ecrin_gender_eligibility]


def get_study_details_from_ecrin_mdr(mdr_id):
    """Fetch and normalize one study from the ECRIN MDR HTTP API.

    Args:
        mdr_id: ECRIN study identifier appended directly to both API URLs.

    Returns:
        The primary response's ``full_study`` mapping on HTTP 200. Otherwise a
        reduced mapping is built from the first JSON-encoded record returned by
        the alternative endpoint on HTTP 200. Returns ``None`` when both
        endpoints return non-200 responses.

    Raises:
        requests.exceptions.RequestException: If either HTTP request fails. No
            timeout or retry is configured.
        KeyError: If a successful response lacks a required field.
        IndexError: If the alternative successful response contains no record.
        json.JSONDecodeError: If returned JSON or its embedded record is invalid.
    """
    logger.debug("Getting study details")
    res = requests.get(f"{ECRIN_STUDY_API_ENDPOINT}/{mdr_id}")
    if res.status_code == 200:
        return res.json()["full_study"]
    else:
        logger.info("Failed getting the study with the MDR ID. ")
        res = requests.get(f"{ECRIN_STUDY_ALTERNATIVE_URL}/{mdr_id}")
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


def create_records(mdr_data, mdr_title, national_node):
    """Build Directory AlsoKnownIn and Studies rows from ECRIN metadata.

    Args:
        mdr_data: Normalized study mapping with ID, display title, description,
            type, enrolment, gender eligibility, and optional age bounds.
        mdr_title: Title from the input-link CSV; this becomes ``Studies.title``
            instead of the MDR display title.
        national_node: Node code embedded in generated IDs and stored on both
            records.

    Returns:
        Pair ``(also_known_in, study)``. Invalid or blank enrolment becomes
        ``None``; ``All`` sex is serialized as ``MALE,FEMALE``; age values and
        their shared mapped unit are copied without remote or local writes.

    Raises:
        KeyError: If required MDR fields are absent or gender eligibility is
            unsupported.
        AssertionError: If minimum and maximum ages use different units.
    """

    also_known_id = f"{BBMRI_AKI_ID_PREFIX}{national_node}_{mdr_data["id"]}"  # internal bbmri id of the "also_known_entity" corresponding to the study
    study_id = f"{BBMRI_STUDY_ID_PREFIX}{national_node}_{mdr_data["id"]}"  # internal bbmri id of the study
    # creates the also known record
    also_known = {
        "id": also_known_id,
        "name_system": "ECRIN MDR",
        "pid": mdr_data["id"],
        "url": f"{ECRIN_STUDY_URL}/{mdr_data["id"]}",
        "national_node": national_node,
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
        "national_node": national_node
    }

    return also_known, study


def get_collection_data_from_directory(eric_client, schema, collection_id):
    """Fetch the first exact-ID Collections record from a Directory schema.

    Args:
        eric_client: Active EMX2 client used for a remote table query.
        schema: Schema containing the source Collections table.
        collection_id: Canonical collection ID interpolated into ``id==...``.

    Returns:
        First returned collection mapping, or ``None`` after logging the ID when
        the response list is empty.
    """
    try:
        return eric_client.get(table="Collections", query_filter=f"id=={collection_id}", schema=schema)[0]
    except IndexError:
        logger.error(collection_id)


async def save_and_upload_files_to_directory(emx2_client, entities_by_national_node, schema, upload_data, output_dir):
    """Write node-grouped CSVs and optionally upload them to node schemas.

    Args:
        emx2_client: Active EMX2 client used for optional file uploads.
        entities_by_national_node: Nested mapping from node code to entity name
            and nonempty record lists with uniform keys.
        schema: Base schema name combined with ``-<node>`` for uploads.
        upload_data: Whether to upload the three fixed CSV filenames after
            writing each node directory.
        output_dir: Existing top-level directory receiving one subdirectory per
            non-UK node.

    Returns:
        None. For every node except ``UK``, creates its directory if absent and
        overwrites each entity CSV with headers taken from the first record.
        When uploads are enabled, sends ``AlsoKnownIn.csv``, ``Studies.csv``,
        and ``Collections.csv`` in that order to ``<schema>-<node>``. There is
        no prompt, dry-run, cleanup, transaction, or rollback; partial local
        files and earlier remote uploads remain after a later failure.

    Raises:
        IndexError: If an entity record list is empty when headers are derived.
        OSError: If a node directory or CSV cannot be created or overwritten.
        SystemExit: With status ``-1`` after a ``PyclientException`` from any
            upload; the client message and filename are logged first.
    """
    for nn, entities in entities_by_national_node.items():
        if nn != "UK":
            nn_dir = f"{output_dir}/{nn}"
            if not os.path.exists(nn_dir):
                os.mkdir(f"{nn_dir}")

            for k, v in entities.items():
                logger.info("Created %d records of type %s for national node %s", len(v), k, nn)
                with open(f"{nn_dir}/{k}.csv", "w") as outfile:
                    fieldnames = list(v[0].keys())
                    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(v)
            if upload_data:
                for filename in (f"AlsoKnownIn.csv", f"Studies.csv", f"Collections.csv"):
                    try:
                        await emx2_client.upload_file(file_path=f"{nn_dir}/{filename}", schema=f"{schema}-{nn}")
                    except PyclientException as ex:
                        logger.error(ex)
                        logger.error(f"Error uploading {filename}")
                        sys.exit(-1)


async def main(input_file, url, username, password, token, schema, output_dir, upload_data):
    """Import linked ECRIN studies into generated CSVs and optional schemas.

    The input CSV is reduced to one collection per unique MDR ID/title pair.
    The client uses a token when supplied, otherwise signs in only when both
    username and password are present; missing authentication is allowed for
    local-file generation and any server permissions fail at the client call.
    Collections are read from ``schema``, cached by ID, and mutated so each
    successfully resolved study ID is appended to the existing comma-delimited
    ``studies`` value. Missing MDR studies or collections are logged and skipped.

    Args:
        input_file: CSV with exact ``mdr_id``, ``mdr_title``, and
            ``collection_id`` headers.
        url: EMX2 Directory base URL for collection reads and optional uploads.
        username: Optional username used only when no token is supplied and a
            password is also present.
        password: Optional password paired with ``username``.
        token: Optional access token, preferred over username/password.
        schema: Source schema for collection reads and base name for destination
            ``<schema>-<national_node>`` uploads.
        output_dir: Existing output directory for node subdirectories and CSVs.
        upload_data: Whether generated files are also uploaded remotely.

    Returns:
        None. Local CSV generation always occurs for non-UK resolved nodes;
        remote writes occur only when ``upload_data`` is true. No confirmation,
        dry-run, duplicate-study prevention, rollback, or local cleanup exists.

    Raises:
        SystemExit: If an optional upload is rejected by the EMX2 client.
        OSError: If input or generated CSV files cannot be read or written.
        requests.exceptions.RequestException: If an ECRIN API request fails.
        KeyError: If required CSV, ECRIN, or Directory fields are absent.
    """
    studies_collections = get_studies_collections_link(input_file)

    with client.Client(url=url) as emx2_client:
        if token is not None:
            emx2_client.set_token(token)
        elif username is not None and password is not None:
            emx2_client.signin(username, password)
        entities_by_national_node = defaultdict(lambda: defaultdict(list))
        collections = {}
        failed_studies = []
        for (mdr_id, mdr_title), collection_id in studies_collections.items():
            logger.info("Processing study %s" % mdr_id)
            study_details = get_study_details_from_ecrin_mdr(mdr_id)
            if study_details is None:
                logger.error("Couldn't find details for study %s" % mdr_id)
                failed_studies.append(mdr_id)
            else:
                if collections.get(collection_id) is None:
                    collections[collection_id] = get_collection_data_from_directory(emx2_client, schema, collection_id)
                if collections[collection_id] is None:
                    logger.error("Collection %s not found in directory, skipping study %s" % (collection_id, mdr_id))
                    failed_studies.append(mdr_id)
                    continue
                national_node = collections[collection_id]["national_node"]
                logger.info("Found study details. Creating records")
                aki, study = create_records(study_details, mdr_title, national_node)
                entities_by_national_node[national_node]["AlsoKnownIn"].append(aki)
                entities_by_national_node[national_node]["Studies"].append(study)

                collections[collection_id]["studies"] = f'{collections[collection_id]["studies"]},{study["id"]}' if \
                    collections[collection_id]["studies"] else f'{study["id"]}'
        for cid, collection in collections.items():
            entities_by_national_node[collection['national_node']]["Collections"].append(collection)

        await save_and_upload_files_to_directory(emx2_client, entities_by_national_node, schema, upload_data, output_dir)
        logger.error(f"Failed studies {failed_studies}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-file", "-i", dest="input_file", type=file_exist, required=True,
                        help="CSV file with mdr and csv matchings")
    parser.add_argument("--url", "-u", type=str, required=True, help="the url of the BBMRI directory")
    parser.add_argument("--username", "-U", type=str, required=False,
                        help="the user name of the user of the BBMRI directory")
    parser.add_argument("--password", "-P", type=str, required=False,
                        help="the password of the user of the BBMRI directory")
    parser.add_argument("--output-dir", "-o", type=str, required=False,
                        help="The director that will contain the csv to be uploaded", default="./ecrin-data")
    parser.add_argument("--token", "-t", type=str, required=False,
                        help="Token to use to write in Molgenis EMX2")
    parser.add_argument("--schema", "-s", type=str, required=False, default="ERIC", help="name of the Molgenis schema")
    parser.add_argument("--upload-data", "-d", action="store_true",
                        help="flag to activate or not the upload of the generated data. If false it just creates the csv files")

    args = parser.parse_args()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    outdir = create_output_dir(args.output_dir)

    try:
        asyncio.run(main(args.input_file, args.url, args.username, args.password, args.token, args.schema, outdir, args.upload_data))
    except KeyboardInterrupt:
        pass
