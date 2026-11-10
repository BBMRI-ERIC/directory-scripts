"""Compare Directory metadata with independent software/model source commits."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import quote

from vocabulary_guidance import content_hash
from vocabulary_sources import _read_source, parse_model_csv, parse_vocabulary_csv
from vocabulary_status import model_fingerprint

REPOSITORY = "molgenis/molgenis-emx2"
API = f"https://api.github.com/repos/{REPOSITORY}"
RAW = f"https://raw.githubusercontent.com/{REPOSITORY}"
COMMIT_URL = f"https://github.com/{REPOSITORY}/commit/"
MODEL_ROOT = "data/biobank-directory/"


def reference_scope(model: dict, ontology_model: dict) -> tuple[str, ...]:
    """Find model-linked vocabularies and their transitive local references.

    Args:
        model: Schema metadata; DirectoryOntologies links define the scope roots.
        ontology_model: Ontology schema declaring local reference relationships.

    Returns:
        Sorted reachable names, including undeclared targets for explicit diagnostics.
    """
    definitions = {table["name"]: table for table in ontology_model.get("tables", [])}
    pending = {column["refTableName"] for table in model.get("tables", [])
               for column in table.get("columns", [])
               if column.get("refSchemaName") == "DirectoryOntologies" and column.get("refTableName")}
    found = set()
    while pending:
        name = pending.pop()
        if name in found:
            continue
        found.add(name)
        for column in definitions.get(name, {}).get("columns", []):
            if column.get("refSchemaName") in (None, "", "DirectoryOntologies") and column.get("refTableName"):
                pending.add(column["refTableName"])
    return tuple(sorted(found))


def aggregate_status(states: list[str]) -> str:
    """Combine independently migrated components without hiding uncertainty.

    Args:
        states: Component statuses from schema and vocabulary comparisons.

    Returns:
        One aggregate direction, mixed for opposing migrations, or unknown when
        any component is unknown or no components were inspected.
    """
    values = set(states)
    if not values or "unknown" in values:
        return "unknown"
    if "diverged" in values:
        return "diverged"
    if "mixed" in values or {"older", "newer"} <= values:
        return "mixed"
    return "older" if "older" in values else "newer" if "newer" in values else "equal"


def _content_value(value):
    """Normalize a reference property without inventing multi-value delimiters.

    Args:
        value: CSV/API scalar or explicitly represented reference/list value.

    Returns:
        Stable scalar/list suitable for hashing; empty values normalize to None.

    Raises:
        ValueError: If an object has no unambiguous reference identity.
    """
    if value is None or value == "" or value == []:
        return None
    if isinstance(value, dict):
        if "name" not in value and "id" not in value:
            raise ValueError("Unsupported vocabulary reference object")
        return _content_value(value.get("name", value.get("id")))
    if isinstance(value, list):
        items = sorted((_content_value(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True))
        return items[0] if len(items) == 1 else items
    return str(value).lower() if isinstance(value, bool) else str(value)


def vocabulary_content_hash(rows: list[dict], field_types: dict | None = None) -> str:
    """Fingerprint all vocabulary business properties, including custom columns.

    Args:
        rows: Named term records from source CSV or a reference-schema table.
        field_types: Optional field-to-columnType mapping for numeric, boolean
            and derived inverse-reference normalization.

    Returns:
        Order-independent SHA-256; runtime mg_* fields and display order are
        excluded. Unsupported values raise rather than silently lose content.

    Raises:
        ValueError: If names are missing/duplicated or property values ambiguous.
    """
    terms = {}
    for row in rows:
        name = row.get("name")
        if not isinstance(name, str) or not name or name in terms:
            raise ValueError("Vocabulary has a missing or duplicate term name")
        term = {}
        for key, value in row.items():
            kind = (field_types or {}).get(key, "").upper()
            if key.startswith("mg_") or key == "order" or kind == "REFBACK":
                continue
            if value not in (None, "") and kind in {"INT", "LONG", "DECIMAL", "FLOAT", "DOUBLE"}:
                try:
                    number = Decimal(str(value))
                    if not number.is_finite():
                        raise ValueError("Non-finite vocabulary number")
                    value = str(number.normalize())
                except InvalidOperation as exc:
                    raise ValueError("Invalid numeric vocabulary property") from exc
            if value not in (None, "") and kind == "BOOL":
                if str(value).lower() not in {"true", "false"}:
                    raise ValueError("Unsupported boolean vocabulary property")
                value = str(value).lower()
            if kind in {"REF_ARRAY", "ONTOLOGY_ARRAY"} and isinstance(value, str) and value:
                try:
                    value = next(csv.reader([value], dialect=csv.excel, strict=True))
                except csv.Error as exc:
                    raise ValueError("Unsupported EMX2 CSV reference array") from exc
            normalized = _content_value(value)
            if normalized is not None:
                term[key] = normalized
        terms[name] = term
    return content_hash(terms)


def observed_model_fingerprint(metadata: dict) -> tuple[str | None, list[str]]:
    """Assess observed structure without replacing absent properties by defaults.

    Args:
        metadata: Observed tables/columns, not an upstream CSV whose omitted
            optional flags have defined default values.

    Returns:
        Comparable hash and missing-property paths. The hash is None if any
        assessed property is unavailable; layout/runtime columns are excluded.
    """
    missing = []
    if not isinstance(metadata.get("tables"), list) or not metadata["tables"]:
        return None, ["tables"]
    for table in metadata["tables"]:
        if not isinstance(table.get("columns"), list):
            missing.append(f"{table.get('name')}.columns")
            continue
        for column in table["columns"]:
            name = column.get("name", "")
            kind = (column.get("columnType") or "").upper()
            if name.startswith("mg_") or kind in {"HEADING", "SECTION"}:
                continue
            fields = ["columnType", "required", "key"]
            if kind and (kind.startswith("REF") or kind.startswith("ONTOLOGY")):
                fields += ["refSchemaName", "refTableName", "refBackId"]
            for field in fields:
                if field not in column or (field in {"columnType", "required"} and column[field] is None):
                    missing.append(f"{table.get('name')}.{name}.{field}")
    return (None if missing else model_fingerprint(metadata)), missing


def version_report(snapshot: dict, *, scope_complete: bool = True) -> dict:
    """Project a metadata envelope into compact, separately evidenced versions.

    Args:
        snapshot: Metadata-only envelope obtained by directory.py.
        scope_complete: Whether all reachable vocabularies were requested.

    Returns:
        Independent JSON-compatible report with software evidence and content
        fingerprints, never invented model/vocabulary deployment commits.
    """
    manifest = snapshot.get("server_manifest", {})
    reported = manifest.get("ImplementationVersion") or None
    full = reported if isinstance(reported, str) and re.fullmatch(r"[0-9a-f]{40}", reported) else None
    model = snapshot.get("schema_metadata", {})
    fingerprint, missing_properties = observed_model_fingerprint(model)
    diagnostics = [snapshot[key] for key in ("schema_error", "manifest_error", "refresh_error") if snapshot.get(key)]
    diagnostics.extend(f"{key}: {value}" for key, value in snapshot.get("reference_errors", {}).items())
    vocabularies = {}
    definitions = {table["name"]: {column["name"]: column.get("columnType", "")
                                  for column in table.get("columns", [])}
                   for table in snapshot.get("ontology_schema_metadata", {}).get("tables", [])}
    for name, rows in sorted(snapshot.get("ontologies", {}).items()):
        try:
            vocabularies[name] = {"fingerprint": vocabulary_content_hash(rows, definitions.get(name)), "term_count": len(rows), "status": "available"}
        except (ValueError, TypeError) as exc:
            vocabularies[name] = {"fingerprint": None, "status": "unknown", "diagnostic": str(exc)}
    missing = set(snapshot.get("resolved_ontology_tables", ())) | {
        name for name in snapshot.get("reference_errors", {}) if not name.startswith("__")}
    for name in sorted(missing - vocabularies.keys()):
        vocabularies[name] = {"fingerprint": None, "term_count": None, "status": "unknown",
                              "diagnostic": snapshot.get("reference_errors", {}).get(name, "Reference table unavailable")}
    for item in vocabularies.values():
        item["observed_at"] = snapshot["retrieved_at"] if item["fingerprint"] else None
    return {
        "format_version": 1, "target": snapshot["target"], "schema": snapshot["schema"],
        "retrieved_at": snapshot["retrieved_at"], "channel": snapshot["channel"],
        "scope": {"complete": scope_complete and bool(snapshot.get("complete")), "requested_all": scope_complete,
                  "ontology_tables": sorted(snapshot.get("resolved_ontology_tables", vocabularies))},
        "software": {"release": manifest.get("SpecificationVersion"), "reported_commit": reported,
                     "resolved_commit": full, "commit_url": COMMIT_URL + reported if isinstance(reported, str) and re.fullmatch(r"[0-9a-f]{7,40}", reported) else None,
                     "observed_at": snapshot.get("manifest_retrieved_at", snapshot["retrieved_at"])},
        "model": {"reported_commit": None, "fingerprint": fingerprint if not snapshot.get("schema_error") else None,
                  "observed_at": snapshot["retrieved_at"],
                  "missing_properties": missing_properties,
                  "basis": "business structure: type, required, key and references",
                  "unverified_properties": ["descriptions", "defaults", "validation", "readonly", "deployment commit"]},
        "vocabularies": vocabularies, "complete": bool(snapshot.get("complete"))
            and isinstance(reported, str) and bool(re.fullmatch(r"[0-9a-fA-F]{7,40}", reported))
            and not diagnostics and not missing_properties and all(item["status"] == "available" for item in vocabularies.values()),
        "diagnostics": diagnostics,
    }


class DirectoryVersionSources:
    """Read fixed-host GitHub evidence with immutable caching and bounded history."""

    def __init__(self, cache_dir: Path, *, offline: bool = False):
        """Configure reference access without Directory credentials.

        Args:
            cache_dir: Dedicated cache of verified upstream source bytes.
            offline: Prohibit every source request, using existing evidence only.
        """
        self.cache_dir = Path(cache_dir)
        self.offline = offline

    def json(self, path: str, *, refresh: bool = False):
        """Read a GitHub API document on the fixed upstream repository.

        Args:
            path: Internally built API path relative to the fixed repository.
            refresh: Refresh moving-tip lookups; offline always takes precedence.

        Returns:
            Decoded JSON evidence; malformed/absent sources raise.
        """
        result = json.loads(_read_source(API + path, self.cache_dir, offline=self.offline, refresh=refresh))
        if not isinstance(result, (dict, list)):
            raise RuntimeError("Unsupported GitHub response document")
        return result

    def resolve(self, revision: str, *, moving: bool = False, refresh: bool = False) -> str:
        """Resolve a hexadecimal commit ID or the explicit upstream search tip.

        Args:
            revision: Full/short 7-40 digit SHA; master only for a moving search tip.
            moving: Permit master as a history bound, never as an expected version.
            refresh: Refresh the moving lookup rather than reusing its cache.

        Returns:
            Full immutable SHA, validating prefix agreement for abbreviated IDs.

        Raises:
            ValueError: If input/returned identity is malformed or ambiguous.
        """
        if not isinstance(revision, str) or not (re.fullmatch(r"[0-9a-fA-F]{7,40}", revision) or (moving and revision == "master")):
            raise ValueError("Expected a hexadecimal 7-40 digit commit ID")
        if re.fullmatch(r"[0-9a-fA-F]{40}", revision):
            return revision.lower()
        result = self.json("/commits/" + revision, refresh=refresh)
        full = result.get("sha", "") if isinstance(result, dict) else ""
        if not re.fullmatch(r"[0-9a-f]{40}", full) or (revision != "master" and not full.startswith(revision.lower())):
            raise ValueError("GitHub returned an inconsistent commit identity")
        return full

    def order(self, expected: str, observed: str) -> str:
        """Compare immutable base/head ancestry, never hashes or timestamps.

        Args:
            expected: Full baseline commit SHA.
            observed: Full observed/candidate source SHA.

        Returns:
            equal, older, newer or diverged according to GitHub ancestry.

        Raises:
            RuntimeError: If ancestry evidence is unsupported or inconsistent.
        """
        if expected == observed:
            return "equal"
        result = self.json(f"/compare/{expected}...{observed}?per_page=1")
        statuses = {"identical": "equal", "ahead": "newer", "behind": "older", "diverged": "diverged"}
        if (not isinstance(result, dict) or result.get("status") not in statuses
                or not isinstance(result.get("base_commit"), dict) or result["base_commit"].get("sha") != expected
                or result.get("url") != f"{API}/compare/{expected}...{observed}"):
            raise RuntimeError("Unsupported GitHub ancestry comparison")
        return statuses[result["status"]]

    def file(self, revision: str, path: str) -> str:
        """Read a file at an immutable source revision.

        Args:
            revision: Resolved full source commit.
            path: Repository-relative model/reference path constructed internally.

        Returns:
            UTF-8 source text from the verified source cache or GitHub.
        """
        return _read_source(f"{RAW}/{revision}/{quote(path, safe='/')}", self.cache_dir, offline=self.offline).decode("utf-8")

    def file_history(self, path: str, tip: str, limit: int) -> tuple[list[dict], bool]:
        """Walk a file's bounded reachable history, following renamed source paths.

        Args:
            path: Current source path, whose prior names must also be assessed.
            tip: Independent immutable history search bound, not the binary commit.
            limit: Maximum file versions examined across all aliases.

        Returns:
            Source versions and completeness flag; capped scans never claim complete.

        Raises:
            RuntimeError: If pagination, duplicates or rename evidence is inconsistent.
        """
        pending, visited, seen, versions = [(path, tip)], set(), set(), []
        while pending:
            current, head = pending.pop()
            if (current, head) in visited:
                continue
            visited.add((current, head))
            page = 1
            while True:
                batch = self.json(f"/commits?sha={head}&path={quote(current, safe='')}&per_page=100&page={page}")
                if not isinstance(batch, list):
                    raise RuntimeError("Unsupported GitHub file history")
                for item in batch:
                    if not isinstance(item, dict):
                        raise RuntimeError("Malformed GitHub history item")
                    sha = item.get("sha", "")
                    if not re.fullmatch(r"[0-9a-f]{40}", sha) or (sha, current) in seen:
                        raise RuntimeError("Duplicate or malformed GitHub file revision")
                    if len(versions) >= limit:
                        return versions, False
                    seen.add((sha, current))
                    detail = self.json(f"/commits/{sha}?per_page=100&page=1")
                    if not isinstance(detail, dict) or not isinstance(detail.get("files"), list):
                        raise RuntimeError("Missing commit file evidence")
                    files = list(detail.get("files", []))
                    file_page = 2
                    while files and len(files) % 100 == 0:
                        if len(files) >= 3000:
                            raise RuntimeError("GitHub commit file limit prevents complete rename inspection")
                        page_record = self.json(f"/commits/{sha}?per_page=100&page={file_page}")
                        if not isinstance(page_record, dict) or not isinstance(page_record.get("files"), list):
                            raise RuntimeError("Incomplete commit-file pagination")
                        more = page_record["files"]
                        if not more:
                            break
                        files.extend(more)
                        file_page += 1
                    if any(not isinstance(entry, dict) for entry in files):
                        raise RuntimeError("Malformed commit file evidence")
                    matches = [entry for entry in files if entry.get("filename") == current]
                    if len(matches) != 1:
                        raise RuntimeError("File history has no unique matching source path")
                    entry = matches[0]
                    text = None if entry.get("status") == "removed" else self.file(sha, current)
                    versions.append({"revision": sha, "path": current, "text": text})
                    if entry.get("previous_filename"):
                        parents = detail.get("parents", [])
                        if not parents:
                            raise RuntimeError("Renamed source has no parent evidence")
                        parent = parents[0].get("sha") if isinstance(parents[0], dict) else None
                        if not isinstance(parent, str) or not re.fullmatch(r"[0-9a-f]{40}", parent):
                            raise RuntimeError("Invalid rename parent identity")
                        pending.append((entry["previous_filename"], parent))
                if len(batch) < 100:
                    break
                page += 1
        return versions, True

    def match_content(self, path: str, expected: str, tip: str, observed: str, fingerprint, limit: int) -> dict:
        """Match all inspected contents before inferring a single source direction.

        Args:
            path: Source file being compared, including rename history.
            expected: Full baseline commit supplied independently of the software.
            tip: Full independent upstream history bound.
            observed: Fingerprint of the observed model or vocabulary contents.
            fingerprint: Callable mapping source text to its comparable fingerprint.
            limit: Maximum inspected file versions; incomplete evidence stays unknown.

        Returns:
            Structured comparison with candidates, complete history and explicit
            uncertainty for repeated contents on both sides of the baseline.
        """
        versions, complete = self.file_history(path, tip, limit)
        candidates = [entry for entry in versions if entry["text"] is not None and fingerprint(entry["text"]) == observed]
        directions = {self.order(expected, entry["revision"]) for entry in candidates}
        status = next(iter(directions)) if complete and len(directions) == 1 else "unknown"
        return {"status": status, "basis": "source content history, not an installed model commit",
                "history_complete": complete, "history_tip": tip,
                "candidates": [{key: value for key, value in entry.items() if key != "text"} for entry in candidates],
                "diagnostic": None if status != "unknown" else "No unique complete source-history direction is established."}


def _compare_contents(source, path, revision, tip, observed, fingerprint, limit):
    """Compare expected source contents before requiring historical inference.

    Args:
        source: Configured DirectoryVersionSources transport/cache.
        path: Fixed repository-relative component file.
        revision: Full expected model/reference revision.
        tip: Lazy callable resolving an independent history bound when needed.
        observed: Available observed fingerprint, or None when unavailable.
        fingerprint: Callable producing the comparable hash from source text.
        limit: Maximum historical file versions inspected.

    Returns:
        Structured component status; unavailable sources or unsupported formats
        remain unknown with diagnostics rather than turning into false findings.
    """
    result = {"status": "unknown", "expected_commit": revision, "expected_commit_url": COMMIT_URL + revision,
              "path": path, "observed_fingerprint": observed, "candidates": []}
    if observed is None:
        result["diagnostic"] = "Observed component metadata is unavailable."
        return result
    try:
        expected_hash = fingerprint(source.file(revision, path))
        result["expected_fingerprint"] = expected_hash
        if observed == expected_hash:
            result.update(status="equal", basis="compatible assessed contents, not a deployment identity")
        else:
            result.update(source.match_content(path, revision, tip(), observed, fingerprint, limit))
    except (RuntimeError, ValueError, KeyError, TypeError, OSError) as exc:
        result["diagnostic"] = str(exc)
    return result


def validate_comparison_request(software: str, model: str, history_tip: str | None, limit: int) -> None:
    """Validate comparison inputs before any Directory or source network read.

    Args:
        software: Required software baseline hexadecimal commit ID.
        model: Required separate model/vocabulary baseline commit ID.
        history_tip: Optional immutable source-history search bound.
        limit: Positive maximum number of source versions inspected per file.

    Returns:
        None when every caller-supplied parameter is supported.

    Raises:
        ValueError: If a required commit ID or history limit is invalid.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("max_history_versions must be a positive integer")
    for revision in (software, model):
        if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-fA-F]{7,40}", revision):
            raise ValueError("Expected a hexadecimal 7-40 digit commit ID")
    if history_tip is not None and (not isinstance(history_tip, str) or not re.fullmatch(r"[0-9a-fA-F]{7,40}", history_tip)):
        raise ValueError("Expected an immutable hexadecimal history tip")


def compare_version_report(snapshot: dict, expected_software_commit: str, expected_model_commit: str, *,
                           source_cache_dir: Path, refresh: bool = True, offline: bool = False,
                           history_tip: str | None = None, max_history_versions: int = 100,
                           scope_complete: bool = True) -> dict:
    """Compare independently observed software/schema/vocabularies to source commits.

    Args:
        snapshot: Metadata-only Directory observation, including ontology schema.
        expected_software_commit: Full or short immutable software baseline SHA.
        expected_model_commit: Independent model/vocabulary baseline SHA.
        source_cache_dir: Dedicated source-response cache, separate from entity data.
        refresh: Refresh moving upstream history-tip lookups when needed.
        offline: Forbid all upstream requests, preserving original cache times.
        history_tip: Optional fixed independent history bound; default resolves master.
        max_history_versions: Positive cap on per-file history; capped scans are unknown.
        scope_complete: Whether every reachable reference vocabulary was requested.

    Returns:
        Version report plus per-component comparisons, expected references,
        conservative aggregate model state and explicit assessment limitations.

    Raises:
        ValueError: If a commit input or history limit is malformed.
    """
    validate_comparison_request(expected_software_commit, expected_model_commit, history_tip, max_history_versions)
    source = DirectoryVersionSources(source_cache_dir, offline=offline)
    report = version_report(snapshot, scope_complete=scope_complete)
    comparisons = {"software": {"status": "unknown"}, "schema": {"status": "unknown"},
                   "ontology_schema": {"status": "unknown"}, "vocabularies": {}}
    report["comparisons"] = comparisons
    report["expected"] = {"software": expected_software_commit, "model": expected_model_commit}
    try:
        software = source.resolve(expected_software_commit, refresh=refresh)
        report["expected"]["software"] = software
        observed = report["software"]["reported_commit"]
        if observed:
            observed = source.resolve(observed, refresh=refresh)
            report["software"].update(resolved_commit=observed, commit_url=COMMIT_URL + observed)
            comparisons["software"] = {"status": source.order(software, observed), "basis": "Git ancestry",
                                       "expected_commit": software, "expected_commit_url": COMMIT_URL + software,
                                       "observed_commit": observed, "observed_commit_url": COMMIT_URL + observed}
    except (RuntimeError, ValueError, KeyError, TypeError, OSError) as exc:
        comparisons["software"]["diagnostic"] = str(exc)
    resolved_tip = []

    def tip():
        """Resolve the history bound once, independently of the running software.

        Returns:
            Immutable upstream search bound, from an explicit SHA or a cached/live
            master lookup. Its original retrieval time remains separately visible.
        """
        if not resolved_tip:
            resolved_tip.append(source.resolve(history_tip or "master", moving=history_tip is None, refresh=refresh))
            report["history_tip"] = resolved_tip[0]
            if history_tip is None:
                url = API + "/commits/master"
                record_path = source.cache_dir / (hashlib.sha256(url.encode()).hexdigest() + ".json")
                report["history_tip_retrieved_at"] = json.loads(record_path.read_text()).get("retrieved_at") if record_path.exists() else None
        return resolved_tip[0]

    try:
        model = source.resolve(expected_model_commit, refresh=refresh)
        report["expected"]["model"] = model
        model_path = MODEL_ROOT + ("" if snapshot["schema"] == "ERIC" else "stagingArea/") + "molgenis.csv"
        expected_model = parse_model_csv(source.file(model, model_path))
        expected_ontology_model = parse_model_csv(source.file(model, MODEL_ROOT + "ontologies/molgenis.csv"))
        expected_model["name"] = snapshot["schema"]
        expected_ontology_model["name"] = "DirectoryOntologies"
        expected_tables = set(reference_scope(expected_model, expected_ontology_model))
        selected = set(report["scope"]["ontology_tables"])
        names = expected_tables | selected if scope_complete else selected
        comparisons["schema"] = _compare_contents(source, model_path, model, tip, report["model"]["fingerprint"],
                                                   lambda text: model_fingerprint({**parse_model_csv(text), "name": snapshot["schema"]}), max_history_versions)
        comparisons["schema"]["missing_properties"] = report["model"]["missing_properties"]
        ontology_model = snapshot.get("ontology_schema_metadata")
        explicit_tables = {table["name"] for table in expected_ontology_model["tables"]}
        declared_model = {**ontology_model, "tables": [table for table in ontology_model.get("tables", [])
                                                      if table["name"] in explicit_tables]} if ontology_model else None
        ontology_fingerprint, missing_properties = observed_model_fingerprint(declared_model or {})
        comparisons["ontology_schema"] = _compare_contents(source, MODEL_ROOT + "ontologies/molgenis.csv", model, tip,
            ontology_fingerprint,
            lambda text: model_fingerprint({**parse_model_csv(text), "name": "DirectoryOntologies"}), max_history_versions)
        comparisons["ontology_schema"]["missing_properties"] = missing_properties
        comparisons["ontology_schema"]["unverified_properties"] = ["software-generated ontology table definitions"]
        for name in sorted(names):
            observed = report["vocabularies"].get(name, {}).get("fingerprint")
            types = {column["name"]: column.get("columnType", "") for table in expected_ontology_model["tables"]
                     if table["name"] == name for column in table.get("columns", [])}
            if not types and ontology_model:
                types = {column["name"]: column.get("columnType", "") for table in ontology_model.get("tables", [])
                         if table["name"] == name for column in table.get("columns", [])}
            comparisons["vocabularies"][name] = _compare_contents(source, MODEL_ROOT + f"ontologies/{name}.csv", model,
                tip, observed, lambda text, field_types=types: vocabulary_content_hash(parse_vocabulary_csv(text), field_types), max_history_versions)
    except (RuntimeError, ValueError, KeyError, TypeError, OSError) as exc:
        report["diagnostics"].append(str(exc))
    states = [comparisons["schema"]["status"], comparisons["ontology_schema"]["status"]]
    states.extend(item["status"] for item in comparisons["vocabularies"].values())
    scoped = aggregate_status(states)
    report["model_overall"] = {"status": scoped if scope_complete and snapshot.get("complete") else "unknown",
                               "scoped_status": scoped, "basis": "assessed schema and vocabulary contents only"}
    report["complete"] = bool(report["complete"] and scope_complete and "unknown" not in states
                              and comparisons["software"]["status"] != "unknown")
    return copy.deepcopy(report)
