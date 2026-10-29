#!/usr/bin/env python3
"""Export Directory biobank GeoJSON with explicit location sources and research packets."""

import argparse
import configparser
import json
import logging as log
import os
from pathlib import Path
import pprint
import shutil
import tempfile
import time

from diskcache import Cache
from flatten_json import flatten
import geopy.geocoders
import pandas as pd

from cli_common import (add_directory_auth_arguments, add_directory_schema_argument,
    add_logging_arguments, add_purge_cache_arguments, add_withdrawn_scope_arguments,
    build_directory_kwargs, build_parser, configure_logging)
from directory import Directory
from geojsonutils import make_point_feature, write_feature_collection
from geocoding_utils import (collect_institution_requests, format_statistics,
    load_location_catalogue, make_location_context, render_institution_review,
    resolve_coordinates, summarize_results)


geolocator = None
geocodingEnabled = True
geocodingNextRequestMonotonic = 0.0


def build_cli_parser() -> argparse.ArgumentParser:
    """Build shared Directory flags followed by tool-specific location/output inputs.

    Returns:
        Parser retaining positional INI input and hidden historical argument aliases.
    """
    parser = build_parser(description=__doc__)
    add_logging_arguments(parser)
    add_directory_auth_arguments(parser)
    add_directory_schema_argument(parser, default="ERIC")
    add_withdrawn_scope_arguments(parser)
    add_purge_cache_arguments(parser, ["directory", "geocoding"])
    parser.add_argument("config_file", help="INI selection/exclusions and GeoJSON properties")
    parser.add_argument("-o", "--output-prefix", default="bbmri-directory-5-0", help="Output prefix; .geojson is appended")
    parser.add_argument("--out-name", "--outName", dest="output_prefix", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    parser.add_argument("--print-filtered-dataframe", action="store_true", help="Print the selected biobank dataframe")
    parser.add_argument("--print-filtered-df", dest="print_filtered_dataframe", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--manual-overrides", type=Path, help="Authoritative ID-based manual location JSON")
    parser.add_argument("--institution-resolutions", type=Path, help="Authoritative externally researched institution JSON")
    parser.add_argument("--output-institution-review", type=Path, help="Write Markdown research instructions and complete carry-forward catalogue")
    parser.set_defaults(purgeCaches=[])
    return parser


def _new_geolocator():
    """Construct the historical Nominatim client without making a startup request.

    Returns:
        Geopy client using the existing user-agent and timeout configuration.
    """
    return geopy.geocoders.Nominatim(
        user_agent="Mozilla/5.0 (X11; Linux i686; rv:10.0) Gecko/20100101 Firefox/10.0", timeout=15)


def safe_geocode(query: str):
    """Perform the existing rate-limited/retrying address lookup only when needed.

    Args:
        query: Current organizational address text, never an AI/model prompt.

    Returns:
        Existing status/location protocol: resolved, not_found or disabled and optional location.
    """
    global geolocator, geocodingEnabled, geocodingNextRequestMonotonic
    if not geocodingEnabled:
        return "disabled", None
    if geolocator is None:
        geolocator = _new_geolocator()
    for attempt, backoff in enumerate((0.0, 3.0, 10.0), start=1):
        wait = max(0.0, geocodingNextRequestMonotonic - time.monotonic())
        if wait:
            time.sleep(wait)
        geocodingNextRequestMonotonic = time.monotonic() + 1.1
        try:
            location = geolocator.geocode(query)
        except (geopy.exc.GeocoderRateLimited, geopy.exc.GeocoderServiceError) as exc:
            if attempt < 3:
                log.warning("Geocoding attempt %d for %r failed: %s; retrying after %.1fs", attempt, query, exc, backoff)
                time.sleep(backoff)
                geocodingNextRequestMonotonic = max(geocodingNextRequestMonotonic, time.monotonic() + 1.1)
                continue
            log.warning("Geocoding failed for %r: %s; disabling live lookups", query, exc)
            geocodingEnabled = False
            return "disabled", None
        return ("resolved", location) if location else ("not_found", None)
    geocodingEnabled = False
    return "disabled", None


def read_config(path: Path) -> configparser.ConfigParser:
    """Read the existing INI, rejecting obsolete coordinate authority explicitly.

    Args:
        path: Current INI whose filters/exclusions remain authoritative.

    Returns:
        Parsed configuration retaining historical case-insensitive option access.

    Raises:
        ValueError: If required input/sections are unavailable or old positions need migration.
    """
    config = configparser.ConfigParser()
    try:
        with path.open(encoding="utf-8") as stream:
            config.read_file(stream)
    except (OSError, UnicodeError, configparser.Error) as exc:
        raise ValueError(f"Cannot read geocoding config {path}: {exc}") from exc
    required = {"Biobank config", "Override biobank position", "Skip biobank", "Skip ID",
                "Skip country", "Filter dataset", "Filter dataset exact string"}
    if required - set(config.sections()):
        raise ValueError("Missing INI sections: " + ", ".join(sorted(required - set(config.sections()))))
    if config["Override biobank position"]:
        raise ValueError("Legacy INI coordinate overrides must migrate to --manual-overrides JSON using exact biobank IDs and policy always; retain INI filters/exclusions")
    if config["Filter dataset exact string"].get("searchExactString", "No") not in {"Yes", "No"}:
        raise ValueError("searchExactString must be Yes or No")
    return config


def _csv_setting(config: configparser.ConfigParser, section: str, key: str) -> list[str]:
    """Read comma-delimited INI settings without treating blank entries as rules.

    Args:
        config: Current parsed INI.
        section: Existing INI section containing the optional option.
        key: Historical case-insensitive option name.

    Returns:
        Ordered trimmed nonblank items.
    """
    return [value.strip() for value in config[section].get(key, "").split(",") if value.strip()]


def select_biobanks(directory, config: configparser.ConfigParser, print_dataframe: bool) -> list[dict]:
    """Apply historical OR dataset filters and explicit exclusions before resolution.

    Args:
        directory: Loaded shared Directory object supplying configured withdrawn scope.
        config: INI selection and skip rules, including node-prefix country exclusions.
        print_dataframe: Whether to print selected flattened input as the legacy diagnostic.

    Returns:
        Original selected biobank records, once each, without mutation.

    Raises:
        ValueError: If a configured filter cannot be evaluated safely.
    """
    banks = list(directory.getBiobanks())
    frame = pd.DataFrame([flatten(bank, "-") for bank in banks])
    selected = set(range(len(banks)))
    if config["Filter dataset"]:
        selected = set()
        exact = config["Filter dataset exact string"].get("searchExactString", "No") == "Yes"
        for column, value in config["Filter dataset"].items():
            pattern = column.replace(">", "-[0-9]*-")
            columns = list(frame.filter(regex=pattern).columns) if "*" in pattern else list(frame.filter(items=[pattern]).columns)
            for condition in value.split(","):
                if exact:
                    matches = (frame[columns] == condition.strip("\n")).any(axis=1)
                else:
                    try:
                        matches = frame[columns].apply(lambda col: col.astype("string").str.contains(condition.strip("\n"), na=False)).any(axis=1)
                    except Exception as exc:
                        raise ValueError(f"Invalid dataset filter {column}: {exc}") from exc
                selected.update(frame.index[matches].tolist())
    skip_names = set(_csv_setting(config, "Skip biobank", "biobanksNameSkip"))
    skip_ids = set(_csv_setting(config, "Skip ID", "biobanksIDSkip"))
    skip_nodes = set(_csv_setting(config, "Skip country", "biobanksCountrySkip"))
    result = [bank for index, bank in enumerate(banks) if index in selected
              and bank.get("name") not in skip_names and bank["id"] not in skip_ids
              and directory.getBiobankNN(bank["id"]) not in skip_nodes]
    if print_dataframe:
        ids = {bank["id"] for bank in result}
        with pd.option_context("display.max_columns", None, "display.max_colwidth", None):
            print(frame[frame["id"].isin(ids)] if "id" in frame else frame)
    log.info("Biobanks selected after INI filters/exclusions: %d of %d", len(result), len(banks))
    return result


def feature_properties(bank: dict, collections: dict, names: list[str]) -> dict:
    """Build existing map properties without changing collection-size or COVID meaning.

    Args:
        bank: Selected Directory biobank, read-only.
        collections: Visible collection records indexed by ID, read-only.
        names: Configured historical property names to expose.

    Returns:
        New feature property mapping containing the existing map consumer schema.
    """
    properties = {}
    if "biobankID" in names:
        properties["biobankID"] = bank["id"]
    if "biobankName" in names:
        properties["biobankName"] = bank.get("name", "")
    if "biobankType" in names:
        properties["biobankType"] = "biobank"
    if "biobankSize" in names:
        sizes = []
        for reference in bank.get("collections", []):
            collection_id = reference.get("id") if isinstance(reference, dict) else reference
            collection = collections.get(collection_id)
            if collection and "order_of_magnitude" in collection:
                sizes.append(int(collection["order_of_magnitude"]))
        if sizes:
            properties["biobankSize"] = max(sizes)
    if any(isinstance(ref, dict) and "COVID19" in str(ref.get("_href", "")) for ref in bank.get("network", [])):
        properties["biobankCOVID"] = [{"name": "COVID19 Network"}]
    return properties


def validate_targets(inputs: list[Path], outputs: list[Path]) -> None:
    """Reject output aliases before loading Directory or making geocoding requests.

    Args:
        inputs: Current config and explicitly supplied JSON paths.
        outputs: Requested GeoJSON and optional Markdown destinations.

    Returns:
        None. Does not create or change input/output files.

    Raises:
        ValueError: If an output aliases an input/output or lacks a usable parent.
    """
    previous = list(inputs)
    for output in outputs:
        for other in previous:
            if output.resolve() == other.resolve() or output.exists() and other.exists() and os.path.samefile(output, other):
                raise ValueError(f"Output aliases input or another output: {output}")
        if not output.parent.is_dir() or output.is_dir():
            raise ValueError(f"Invalid output target or parent directory: {output}")
        previous.append(output)


def publish_outputs(products: dict[Path, bytes]) -> None:
    """Stage products and restore earlier bytes if multi-file publication fails.

    Args:
        products: Distinct validated target filenames mapped to serialized output bytes.

    Returns:
        None. Publishes all files, closing and removing task-created stages/backups.

    Raises:
        OSError: If staging, backup or publication fails; rollback is attempted first.
    """
    stages, backups, published, retained = {}, {}, [], set()
    try:
        for target, content in products.items():
            target = target.resolve()
            handle, name = tempfile.mkstemp(prefix=".geocoding-stage-", dir=target.parent)
            stage = Path(name)
            stages[target] = stage
            with os.fdopen(handle, "wb") as stream:
                stream.write(content)
            if target.exists():
                handle, name = tempfile.mkstemp(prefix=".geocoding-backup-", dir=target.parent)
                os.close(handle)
                backups[target] = Path(name)
                shutil.copyfile(target, backups[target])
        for target, stage in stages.items():
            os.replace(stage, target)
            published.append(target)
    except BaseException as failure:
        for target in reversed(published):
            try:
                if target in backups:
                    os.replace(backups[target], target)
                else:
                    target.unlink(missing_ok=True)
            except OSError:
                if target in backups:
                    retained.add(backups[target])
                else:
                    log.error("Could not remove partially published output: %s", target)
        if retained:
            raise OSError("Publication and rollback failed; original bytes retained at "
                          + ", ".join(str(path) for path in retained)) from failure
        raise
    finally:
        for path in [*stages.values(), *backups.values()]:
            if path not in retained:
                try:
                    path.unlink(missing_ok=True)
                except OSError as exc:
                    log.warning("Could not clean temporary geocoding file %s: %s", path, exc)


def main(argv=None) -> int:
    """Export positions and optional research instructions without implicit AI access.

    Args:
        argv: Optional argument vector; None reads the process command line.

    Returns:
        Zero on successful publication, two on input/I/O errors, or 130 on Ctrl+C.
    """
    global geolocator, geocodingEnabled, geocodingNextRequestMonotonic
    args = build_cli_parser().parse_args(argv)
    configure_logging(args)
    cache = None
    try:
        config_path = Path(args.config_file)
        config = read_config(config_path)
        manual = load_location_catalogue(args.manual_overrides, "manual_overrides")
        institutions = load_location_catalogue(args.institution_resolutions, "institution_resolutions")
        output = Path(args.output_prefix + ".geojson")
        outputs = [output] + ([args.output_institution_review] if args.output_institution_review else [])
        validate_targets([config_path] + [p for p in (args.manual_overrides, args.institution_resolutions) if p], outputs)
        schema = None
        if args.output_institution_review:
            schema = json.loads((Path(__file__).resolve().parent / "schemas/geocoding-locations-v1.schema.json").read_text())
        directory = Directory(**build_directory_kwargs(args, pp=pprint.PrettyPrinter(indent=4)))
        banks = select_biobanks(directory, config, args.print_filtered_dataframe)
        contacts = {p["id"]: p for p in directory.getContacts() if isinstance(p, dict) and "id" in p}
        collections = {c["id"]: c for c in directory.getCollections() if isinstance(c, dict) and "id" in c}
        cache_root = Path(os.environ.get("DIRECTORY_CACHE_ROOT", Path.cwd()))
        cache = Cache(str(cache_root / "data-check-cache" / "geocoding"))
        if "geocoding" in args.purgeCaches:
            cache.clear()
        geolocator, geocodingEnabled, geocodingNextRequestMonotonic = None, True, 0.0
        property_names = _csv_setting(config, "Biobank config", "biobankProperties") or ["biobankID", "biobankName", "biobankType", "covid19biobank", "biobankSize"]
        features, observations = [], []
        for bank in banks:
            contact_ref = bank.get("contact")
            contact_id = contact_ref.get("id") if isinstance(contact_ref, dict) else contact_ref
            context = make_location_context(bank, contacts.get(contact_id))
            result = resolve_coordinates(context, manual, institutions, cache, safe_geocode)
            observations.append((context, result))
            log.debug("%s: source=%s channel=%s query_fields=%s reason=%s", context.biobank_id,
                      result.source, result.channel, result.query_fields, result.reason)
            if result.coordinates:
                features.append(make_point_feature(feature_properties(bank, collections, property_names), list(result.coordinates)))
            else:
                log.warning("Skipping %s: %s", context.biobank_id, result.reason)
        with tempfile.TemporaryDirectory(prefix="geocoding-serialize-") as temporary:
            serialized = Path(temporary) / "points.geojson"
            write_feature_collection(str(serialized), features)
            products = {output: serialized.read_bytes()}
        if args.output_institution_review:
            requests = collect_institution_requests(observations, institutions)
            products[args.output_institution_review] = render_institution_review(requests, institutions, schema).encode("utf-8")
        publish_outputs(products)
        if args.verbose or args.debug:
            log.info("%s", format_statistics(summarize_results(observations)))
        return 0
    except KeyboardInterrupt:
        log.error("Interrupted by Ctrl+C; export stopped")
        return 130
    except (ValueError, OSError, configparser.Error) as exc:
        log.error("%s", exc)
        return 2
    finally:
        if cache is not None:
            cache.close()


if __name__ == "__main__":
    raise SystemExit(main())
