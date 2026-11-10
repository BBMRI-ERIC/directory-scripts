"""Read pinned vocabulary sources and reconstruct their complete change history."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from pathlib import Path
from urllib.parse import quote

import requests

from vocabulary_guidance import content_hash

MIABIS_REVISION = "272d05e792e312f1fe56e24eac37d43ce9376bf1"
MIABIS_PATHS = (
    "all lists.md", "README.md", "Core/V3/Data-describing-Collection.md",
    "DatasetTypes/README.md", "BiobankServices/README.md",
    "BiobankServices/Data-describing-BiobankingBiomolecularServices.md",
)


def parse_vocabulary_csv(text: str) -> list[dict]:
    """Parse an upstream term table without guessing its column meanings.

    Args:
        text: UTF-8 decoded CSV vocabulary file with a name header.

    Returns:
        Ordered term mappings; blank values are omitted, names remain exact.

    Raises:
        ValueError: If headers, names or row widths make identities ambiguous.
    """
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if not reader.fieldnames or "name" not in reader.fieldnames:
        raise ValueError("Unsupported vocabulary CSV columns: name is required")
    result, seen = [], set()
    for row in reader:
        name = row.get("name")
        if None in row or not name or name in seen:
            raise ValueError("Invalid vocabulary CSV: missing/duplicate name or extra columns")
        seen.add(name)
        result.append({key: value for key, value in row.items() if value not in (None, "")})
    return result


def parse_model_csv(text: str) -> dict:
    """Read explicitly declared business columns from an upstream EMX2 model.

    Args:
        text: Model CSV with tableName, columnName and columnType headers.

    Returns:
        Metadata-shaped tables/columns mapping suitable for structural fingerprints.
        Omitted flags remain omitted; no read-only properties are inferred.

    Raises:
        ValueError: If required headers or unique table/column identities are absent.
    """
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")), skipinitialspace=True)
    if not {"tableName", "columnName", "columnType"}.issubset(reader.fieldnames or []):
        raise ValueError("Unsupported model CSV columns")
    tables = {}
    seen = set()
    for row in reader:
        table, name = row["tableName"], row["columnName"]
        if not table or None in row:
            raise ValueError("Unsupported model CSV row")
        columns = tables.setdefault(table, [])
        if not name:
            continue
        if (table, name) in seen:
            raise ValueError("Duplicate model table/column")
        seen.add((table, name))
        column = {"name": name, "columnType": row["columnType"] or "STRING"}
        for source, target in (("required", "required"), ("key", "key"), ("refSchema", "refSchemaName"),
                               ("refTable", "refTableName"), ("refBack", "refBackId")):
            if row.get(source):
                column[target] = row[source]
        columns.append(column)
    return {"tables": [{"name": name, "columns": columns} for name, columns in tables.items()]}


def parse_miabis_lists(text: str) -> dict[str, list[dict]]:
    """Read the two explicitly supported MIABIS controlled-list sections.

    Args:
        text: Complete all lists.md from one pinned official MIABIS revision.

    Returns:
        DataCategories and ServiceTypes term lists retaining definition, source,
        attribute code and source line. Attribute codes are not unique term IDs.

    Raises:
        ValueError: If a heading, declared table shape or unique term is missing.
    """
    result = {}
    lines = text.splitlines()
    for heading, table in (("Dataset Type", "DataCategories"), ("Service Type", "ServiceTypes")):
        matches = [idx for idx, line in enumerate(lines) if re.fullmatch(r"#{1,6}\s+" + re.escape(heading) + r"\s*", line)]
        if len(matches) != 1:
            raise ValueError(f"Unsupported MIABIS source: expected one {heading} heading")
        rows = []
        for idx in range(matches[0] + 1, len(lines)):
            line = lines[idx].strip()
            if line.startswith("#"):
                break
            if line.startswith("|"):
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                rows.append((idx + 1, cells))
        if len(rows) < 3 or rows[0][1] != ["Value Name", "Definition", "Source [Link]", "Attribute Codes"]:
            raise ValueError(f"Unsupported MIABIS {heading} columns")
        if any(not re.fullmatch(r":?-+:?", cell.replace(" ", "")) for cell in rows[1][1]):
            raise ValueError(f"Unsupported MIABIS {heading} table separator")
        parsed, seen = [], set()
        for line_number, cells in rows[2:]:
            if len(cells) != 4 or not cells[0] or cells[0] in seen:
                raise ValueError(f"Unsupported MIABIS {heading} row at line {line_number}")
            seen.add(cells[0])
            parsed.append(dict(zip(("name", "definition", "source", "attribute_codes"), cells), line=line_number))
        result[table] = parsed
    return result


def _miabis_attribute(text: str, code: str, path: str) -> dict:
    """Read one explicitly identified component attribute from a supported table.

    Args:
        text: Pinned component Markdown containing its attribute table.
        code: Exact MIABIS attribute code relevant to the supported audit scope.
        path: Source path included in unsupported-format diagnostics.

    Returns:
        Named attribute properties and the original source line number.

    Raises:
        ValueError: If the component table/header/selected row is missing or ambiguous.
    """
    header = None
    selected = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.lstrip().startswith("|"):
            continue
        cells = [value.strip() for value in line.strip().strip("|").split("|")]
        if cells[0] == "Attribute Code":
            if not {"Attribute Name", "Description", "Allowed Values", "Cardinality"}.issubset(cells):
                raise ValueError(f"Unsupported MIABIS component columns in {path}")
            header = cells
        elif cells[0] == code:
            if header is None or len(cells) != len(header):
                raise ValueError(f"Unsupported MIABIS component row for {code} in {path}")
            selected.append({**dict(zip(header, cells)), "line": number})
    if len(selected) != 1:
        raise ValueError(f"Unsupported MIABIS component {path}: expected one {code} row")
    return selected[0]


def validate_miabis_components(sources: dict[str, str], terms: dict[str, list[dict]]) -> dict:
    """Assess linked definitions, value lists and development-status context.

    Args:
        sources: Pinned required Markdown files mapped to their full source text.
        terms: Parsed all-lists Dataset Type and Service Type definitions.

    Returns:
        Relevant component attributes/cardinalities, explicit source conflicts,
        and development/publication context. Conflicts are reference ambiguities,
        never automatically Directory defects.

    Raises:
        ValueError: If linked sources use unsupported headings, links or table formats.
    """
    expected_headers = {
        "README.md": "# MIABIS:",
        "DatasetTypes/README.md": "# Scope of the MIABIS Dataset Types",
        "BiobankServices/README.md": "# Scope of the MIABIS Biobanking and Biomolecular Services",
    }
    for path, heading in expected_headers.items():
        if path not in sources or not sources[path].lstrip().startswith(heading):
            raise ValueError(f"Unsupported MIABIS component overview: {path}")
    for link in ("Core/V3/Data-describing-Collection.md", "DatasetTypes/README.md", "BiobankServices/README.md"):
        if link not in sources["README.md"]:
            raise ValueError(f"Unsupported MIABIS component link: {link}")
    service_path = "BiobankServices/Data-describing-BiobankingBiomolecularServices.md"
    if service_path not in sources["BiobankServices/README.md"]:
        raise ValueError("Unsupported MIABIS service component link")
    attributes, conflicts = {}, []
    for table, code, path in (
        ("DataCategories", "MIABIS-COLLECTION-13", "Core/V3/Data-describing-Collection.md"),
        ("ServiceTypes", "MIABIS-SERVICE-07", service_path),
    ):
        if path not in sources:
            raise ValueError(f"Missing MIABIS component {path}")
        attribute = _miabis_attribute(sources[path], code, path)
        values = attribute["Allowed Values"]
        if table == "ServiceTypes":
            linked = re.match(r"^\[Service type\]\(([^)]+/all(?:%20| )lists\.md#service-type)\)\s*", values)
            if linked is None:
                raise ValueError("Unsupported MIABIS service component controlled-list link")
            values = values[linked.end():]
        names = [name.strip() for name in values.rstrip(".").split(",")]
        if not names or any(not name for name in names) or len(names) != len(set(names)):
            raise ValueError(f"Unsupported MIABIS component allowed values for {code}")
        expected = {row["name"] for row in terms[table]}
        if set(names) != expected:
            conflicts.append({"table": table, "component": path, "attribute_code": code,
                              "component_only": sorted(set(names) - expected),
                              "all_lists_only": sorted(expected - set(names)),
                              "explanation": "The component and all-lists file give different allowed values; confirm the intended reference before asserting compliance."})
        attributes[table] = {"code": code, "path": path, "line": attribute["line"],
                             "description": attribute["Description"], "cardinality": attribute["Cardinality"],
                             "allowed_values": names}
    return {"attributes": attributes, "source_conflicts": conflicts,
            "publication_context": "Root README identifies aggregate-level components as under active development."
            if "under active development" in sources["README.md"] else "Component publication status is not established by this snapshot."}


def compare_terms(before: list[dict], after: list[dict]) -> dict:
    """Describe observed edits without declaring semantic rename equivalence.

    Args:
        before: Parsed term definitions at the earlier source revision.
        after: Parsed term definitions at the later source revision.

    Returns:
        Sorted added, removed and changed names; unchanged terms are omitted.
    """
    old = {row["name"]: row for row in before}
    new = {row["name"]: row for row in after}
    return {"added": sorted(new.keys() - old.keys()), "removed": sorted(old.keys() - new.keys()),
            "changed": sorted(name for name in old.keys() & new.keys() if old[name] != new[name])}


def _immutable(revision: str) -> None:
    """Require a full immutable Git revision rather than a moving branch.

    Args:
        revision: SHA-1 Git object identifier selected by the operator.

    Returns:
        None.

    Raises:
        ValueError: If the revision is not a full hexadecimal SHA.
    """
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Reference revision must be a full immutable GitHub commit SHA")


def _read_source(url: str, cache_dir: Path, *, offline: bool) -> bytes:
    """Retrieve immutable bytes or reuse their verified local cache.

    Args:
        url: Exact source URL, including pinned revision when serving Git files.
        cache_dir: Local source cache directory, separate from entity caches.
        offline: Forbid remote retrieval when the entry is not already cached.

    Returns:
        Raw response bytes, validated against the cached digest on reuse.

    Raises:
        RuntimeError: If cache integrity, availability or HTTP access fails.
    """
    path = Path(cache_dir) / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    if path.exists():
        record = json.loads(path.read_text(encoding="utf-8"))
        data = record["text"].encode("utf-8")
        if record["url"] != url or record["sha256"] != hashlib.sha256(data).hexdigest():
            raise RuntimeError(f"Source cache integrity mismatch for {url}")
        return data
    if offline:
        raise RuntimeError(f"No cached source for {url}; offline mode forbids retrieval")
    try:
        response = requests.get(url, timeout=60, headers={"Accept": "application/vnd.github+json"})
        response.raise_for_status()
        data = response.content
        text = data.decode("utf-8")
        record = {"url": url, "text": text, "sha256": hashlib.sha256(data).hexdigest()}
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
        return data
    except (requests.RequestException, UnicodeError) as exc:
        raise RuntimeError(f"Unable to retrieve source {url}: {exc}") from exc


def load_miabis_reference(*, revision: str, cache_dir: Path, offline: bool = False) -> dict:
    """Load the complete supported MIABIS reference profile at one revision.

    Args:
        revision: Immutable official BBMRI-ERIC/miabis Git commit.
        cache_dir: Directory for immutable source-byte cache entries.
        offline: Require cached sources and prohibit all requests.

    Returns:
        Reference terms, pinned linked documents/URLs/hashes, assessed component
        attributes, source_conflicts and publication-status context. A conflict
        between reference documents is not classified as a Directory defect.

    Raises:
        ValueError: If the revision or source format is unsupported.
        RuntimeError: If any required source is unavailable or corrupt.
    """
    _immutable(revision)
    sources = {}
    for path in MIABIS_PATHS:
        url = f"https://raw.githubusercontent.com/BBMRI-ERIC/miabis/{revision}/{quote(path)}"
        data = _read_source(url, cache_dir, offline=offline)
        sources[path] = {"url": url, "sha256": hashlib.sha256(data).hexdigest(), "text": data.decode("utf-8")}
    terms = parse_miabis_lists(sources["all lists.md"]["text"])
    components = validate_miabis_components({path: source["text"] for path, source in sources.items()}, terms)
    return {"repository": "BBMRI-ERIC/miabis", "revision": revision, "complete": True,
            "sources": sources, "terms": terms, **components}


def load_directory_history(*, repository: str, start_revision: str, end_revision: str,
                           paths: tuple[str, ...], cache_dir: Path, offline: bool = False) -> dict:
    """Reconstruct every relevant file edit within an explicit ancestry range.

    Args:
        repository: Official GitHub owner/repository containing Directory sources.
        start_revision: Inclusive baseline commit; changes after it are inspected.
        end_revision: Immutable descendant ending the historical comparison.
        paths: Model and reference paths to follow, including prior names on rename.
        cache_dir: Local cache for immutable API/file responses, not entity data.
        offline: Permit only previously cached responses.

    Returns:
        Ordered relevant transitions with commit/parent identities, before/after
        contents, hashes, observed term changes and endpoint snapshots. Missing
        inputs raise rather than imply completeness.

    Raises:
        ValueError: If revisions, ancestry or supported file identities are invalid.
        RuntimeError: If pagination, source files or remote history are incomplete.
    """
    _immutable(start_revision)
    _immutable(end_revision)
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repository):
        raise ValueError("Invalid GitHub repository")
    api = f"https://api.github.com/repos/{repository}"
    ordered = []
    page = 1
    total = None
    while total is None or len(ordered) < total:
        url = f"{api}/compare/{start_revision}...{end_revision}?per_page=100&page={page}"
        response = json.loads(_read_source(url, cache_dir, offline=offline))
        if response.get("status") not in {"ahead", "identical"}:
            raise ValueError("Directory history range must have an ancestral baseline")
        total = response["total_commits"]
        commits = response.get("commits", [])
        if not commits and len(ordered) < total:
            raise RuntimeError("Incomplete GitHub comparison pagination")
        ordered.extend(commits)
        page += 1
    if len(ordered) != total or len({item["sha"] for item in ordered}) != total:
        raise RuntimeError("GitHub comparison returned duplicate or inconsistent commits")
    allowed = {item["sha"] for item in ordered}
    relevant = {}
    pending = list(paths)
    visited = set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        page = 1
        while True:
            url = f"{api}/commits?sha={end_revision}&path={quote(path, safe='')}&per_page=100&page={page}"
            batch = json.loads(_read_source(url, cache_dir, offline=offline))
            if not isinstance(batch, list):
                raise RuntimeError("Unsupported GitHub path history response")
            if not batch:
                break
            for item in batch:
                sha = item["sha"]
                if sha not in allowed:
                    continue
                detail = json.loads(_read_source(f"{api}/commits/{sha}?per_page=100&page=1", cache_dir, offline=offline))
                files = list(detail.get("files", []))
                file_page = 2
                while len(files) % 100 == 0 and files:
                    if len(files) >= 3000:
                        raise RuntimeError("GitHub commit file limit reached; complete history cannot be established")
                    more = json.loads(_read_source(f"{api}/commits/{sha}?per_page=100&page={file_page}", cache_dir, offline=offline)).get("files", [])
                    if not more:
                        break
                    files.extend(more)
                    file_page += 1
                for file in files:
                    if file["filename"] != path and file.get("previous_filename") != path:
                        continue
                    old_path = file.get("previous_filename", file["filename"])
                    if file.get("previous_filename"):
                        pending.append(old_path)
                    key = (sha, file["filename"])
                    if key in relevant:
                        continue
                    parent = detail["parents"][0]["sha"]
                    before = b"" if file["status"] == "added" else _read_source(
                        f"https://raw.githubusercontent.com/{repository}/{parent}/{quote(old_path)}", cache_dir, offline=offline)
                    after = b"" if file["status"] == "removed" else _read_source(
                        f"https://raw.githubusercontent.com/{repository}/{sha}/{quote(file['filename'])}", cache_dir, offline=offline)
                    record = {"commit": sha, "parent": parent, "path": file["filename"], "previous_path": old_path,
                              "status": file["status"], "committed_at": detail["commit"]["committer"]["date"],
                              "before": before.decode("utf-8"), "after": after.decode("utf-8"),
                              "before_sha256": hashlib.sha256(before).hexdigest(), "after_sha256": hashlib.sha256(after).hexdigest()}
                    if file["filename"].endswith(("DataCategories.csv", "ServiceTypes.csv")):
                        record["changes"] = compare_terms(parse_vocabulary_csv(record["before"]) if before else [],
                                                           parse_vocabulary_csv(record["after"]) if after else [])
                    relevant[key] = record
            if len(batch) < 100:
                break
            page += 1
    order = {item["sha"]: idx for idx, item in enumerate(ordered)}
    transitions = sorted(relevant.values(), key=lambda item: (order[item["commit"]], item["path"]))
    snapshots = {}
    for path in paths:
        related = history_path_transitions({"transitions": transitions}, path)
        if related:
            first, last = related[0]["before"], related[-1]["after"]
        else:
            first = last = _read_source(
                f"https://raw.githubusercontent.com/{repository}/{end_revision}/{quote(path)}",
                cache_dir, offline=offline).decode("utf-8")
        snapshots[path] = {"at_start": first, "at_end": last}
    return {"repository": repository, "start_revision": start_revision, "end_revision": end_revision,
            "complete": True, "paths": sorted(visited), "transitions": transitions,
            "snapshots": snapshots, "content_hash": content_hash({"transitions": transitions, "snapshots": snapshots})}


def history_path_transitions(history: dict, path: str) -> list[dict]:
    """Select a source file's complete ordered history across recorded renames.

    Args:
        history: Retrieved history containing ordered transition records.
        path: Current or previous source path whose aliases must be followed.

    Returns:
        New list of shared transition records in repository order; callers must not
        mutate their contents or treat commit dates as deployment dates.
    """
    aliases = {path}
    while True:
        previous = len(aliases)
        for item in history.get("transitions", []):
            current, old = item["path"], item.get("previous_path", item["path"])
            if current in aliases or old in aliases:
                aliases.update((current, old))
        if len(aliases) == previous:
            break
    return [item for item in history.get("transitions", []) if item["path"] in aliases]
