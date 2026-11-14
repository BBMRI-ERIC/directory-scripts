"""Prepare and validate source-bound, externally rendered survey participation maps."""

from __future__ import annotations

import copy
import csv
from dataclasses import dataclass
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import tempfile

from survey_participation import (build_country_counts, collect_participation, digest,
                                  directory_inventory, participation_binding)

ROOT = Path(__file__).resolve().parent
LAYOUTS = ("bbmri-members", "oec")


@dataclass(frozen=True)
class ValidatedMapAssets:
    """Verified binary maps and their frozen input evidence.

    Attributes:
        state: empty for unrendered/empty bundles, otherwise ready.
        figures: Stable figure-key to verified PDF path mapping.
        manifest: Input evidence including participation, counts and Directory scope.
    """

    state: str
    figures: dict
    manifest: dict


def file_hash(path: Path) -> str:
    """Compute a file digest without decoding its content.

    Args:
        path: Existing input or rendered binary file.

    Returns:
        SHA-256 of exact file bytes.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_inventory(value: dict) -> dict:
    """Validate a frozen denominator before it is used without Directory access.

    Args:
        value: JSON inventory envelope produced by directory_inventory.

    Returns:
        Independently owned validated envelope.

    Raises:
        ValueError: If its identity, scope, IDs or digest are inconsistent.
    """
    material = {k: v for k, v in value.items() if k != "sha256"}
    if (value.get("schema_version") != 1 or value.get("sha256") != digest(material)
            or value.get("scope") not in {"active", "including-withdrawn", "only-withdrawn"}
            or not isinstance(value.get("target"), str) or not value.get("schema")):
        raise ValueError("Frozen Directory inventory metadata or hash is invalid")
    ids = [bank["id"] for bank in value["biobanks"]]
    if len(ids) != len(set(ids)) or any(not isinstance(bid, str) or not bid for bid in ids):
        raise ValueError("Frozen Directory inventory has duplicate/invalid IDs")
    return copy.deepcopy(value)


def expected_figures(kind: str, layouts) -> list[str]:
    """Enumerate exactly the map outputs expected for the requested report kind.

    Args:
        kind: so2 or mucp, defining the statistic and figure family.
        layouts: Ordered geographic layout names.

    Returns:
        Stable ordered figure keys, without output suffixes.

    Raises:
        ValueError: If report kind or any layout is unsupported.
    """
    if kind not in {"so2", "mucp"} or not layouts or any(x not in LAYOUTS for x in layouts):
        raise ValueError("Unsupported survey map kind/layout")
    modes = ("responses", "percentage") if kind == "so2" else ("comparison",)
    return [f"{kind}-{layout}-{mode}" for layout in layouts for mode in modes]


def write_map_bundle(participation: dict, inventory: dict, output_dir, *, kind: str,
                     layouts="both", overwrite: bool = False, so2_payload: dict | None = None) -> Path:
    """Transactionally prepare country CSVs and an external-R input manifest.

    Args:
        participation: Canonical source/identity roster; no answer bodies are exported.
        inventory: Frozen Directory denominator validated before any publication.
        output_dir: Destination bundle directory, separate from protected input files.
        kind: so2 or mucp, determining the expected figure set.
        layouts: both, one layout name, or an explicit ordered layout sequence.
        overwrite: Replace an existing bundle only after complete preparation.
        so2_payload: Optional descriptive input whose small identity snapshot enables
            combined-report validation without reopening its source JSON path.

    Returns:
        Published bundle directory. No R command is executed.

    Raises:
        ValueError: If an existing destination cannot be replaced safely.
    """
    frozen = validate_inventory(inventory)
    selected = list(LAYOUTS) if layouts == "both" else [layouts] if isinstance(layouts, str) else list(layouts)
    figures = expected_figures(kind, selected)
    output = Path(output_dir).resolve()
    if output.exists() and (not output.is_dir() or not overwrite):
        raise ValueError(f"Map output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.stage-", dir=output.parent))
    backup = None
    try:
        counts = build_country_counts(participation, frozen)
        columns = ["country", "directory_count", "so2_count", "mucp_count", "shared_count",
                   "so2_provisional_count", "mucp_provisional_count", "so2_percent"]
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(counts["countries"])
        (stage / "country-counts.csv").write_text(stream.getvalue(), encoding="utf-8")
        (stage / "directory-inventory.json").write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8")
        sources = ["R-maps/map_config.R", "R-maps/map_common.R",
                   "R-maps/render_bbmri_members_oec_all.R", "R-maps/render_survey_participation.R",
                   "R-maps/survey_participation_common.R"]
        manifest = {"schema_version": 1, "kind": kind, "layouts": selected, "figure_keys": figures,
                    "participation": participation, "canonical_sha256": digest(participation_binding(participation)),
                    "so2_participation_sha256": digest(participation_binding(participation, "SO2")),
                    "inventory_sha256": frozen["sha256"], "counts": counts,
                    "files": {name: file_hash(stage / name) for name in ("country-counts.csv", "directory-inventory.json")},
                    "render_spec": {"width_mm": 240, "height_mm": 135, "dpi": 300,
                                    "label_pt": 9, "minimum_label_pt": 8},
                    "renderer_sources": {name: file_hash(ROOT / name) for name in sources if (ROOT / name).exists()}}
        if so2_payload is not None:
            summary = so2_payload["responses_summary"]
            manifest["so2_snapshot"] = {"provenance": so2_payload["provenance"], "responses_summary": {
                "observation_sources": summary["observation_sources"],
                "country_corrections": summary.get("country_corrections", []),
                "source_records": [{"source_row": row["source_row"], "answers": {"Country": row["answers"].get("Country", "")}}
                                   for row in summary["source_records"]]}}
        (stage / "input-manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        if output.exists():
            backup = Path(tempfile.mkdtemp(prefix=f".{output.name}.backup-", dir=output.parent))
            backup.rmdir()
            os.replace(output, backup)
        try:
            os.replace(stage, output)
        except OSError:
            if backup is not None:
                os.replace(backup, output)
            raise
        if backup is not None:
            shutil.rmtree(backup)
        return output
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def _read_json(path: Path) -> dict:
    """Decode a required local JSON mapping with a user-facing input error.

    Args:
        path: Source input or manifest file.

    Returns:
        Decoded JSON object.

    Raises:
        ValueError: If the file is missing, malformed or not an object.
    """
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("expected JSON object")
        return value
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot load {path}: {exc}") from exc


def _validate_device_audit(record: dict, countries: list[str]) -> None:
    """Verify one physical output device's complete placement diagnostics.

    Args:
        record: Country boxes, reserved rectangles and collision result for one device.
        countries: Sorted countries that must each appear exactly once.

    Returns:
        None when all country groups are inside the device and mutually disjoint.

    Raises:
        ValueError: If country coverage, bounds or obstacle separation is invalid.
    """
    if record.get("collision_count") != 0:
        raise ValueError("Map collision audit failed")
    boxes = record.get("boxes", [])
    if record.get("countries") != countries or len(boxes) != len(countries):
        raise ValueError("Map layout audit omits or duplicates a country")
    obstacles = record.get("reserved_boxes", [])
    for box in [*boxes, *obstacles]:
        if (len(box) != 4 or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in box)
                or not 0 <= box[0] <= box[1] <= 240 or not 0 <= box[2] <= box[3] <= 135):
            raise ValueError("Invalid map layout audit bounds")
    for i, box in enumerate(boxes):
        for other in boxes[:i] + obstacles:
            if box[0] < other[1] and box[1] > other[0] and box[2] < other[3] and box[3] > other[2]:
                raise ValueError("Map country overlaps another country or reserved obstacle")


def validate_map_assets(participation: dict | None, assets_dir, *, expected_kind: str) -> ValidatedMapAssets:
    """Verify source-bound input and complete collision-checked external figure files.

    Args:
        participation: Recomputed roster, or None for input-only validation before replay.
        assets_dir: Prepared/rendered bundle directory; an empty directory is explicit.
        expected_kind: so2 or mucp report receiving the assets.

    Returns:
        Empty state for genuinely unrendered inputs, or verified PDF paths and manifest.

    Raises:
        ValueError: If inputs, rendered files, counts or layout diagnostics are stale/unsafe.
    """
    folder = Path(assets_dir).resolve()
    if not folder.is_dir():
        raise ValueError(f"Map asset directory is missing: {folder}")
    if not any(folder.iterdir()):
        return ValidatedMapAssets("empty", {}, {})
    manifest = _read_json(folder / "input-manifest.json")
    if manifest.get("schema_version") != 1 or manifest.get("kind") != expected_kind:
        raise ValueError("Map bundle version or report kind is incompatible")
    keys = expected_figures(expected_kind, manifest["layouts"])
    if manifest.get("figure_keys") != keys:
        raise ValueError("Map figure specification has changed")
    for name in ("country-counts.csv", "directory-inventory.json"):
        if (folder / name).is_symlink() or file_hash(folder / name) != manifest["files"].get(name):
            raise ValueError(f"Map input file hash changed: {name}")
    frozen = validate_inventory(_read_json(folder / "directory-inventory.json"))
    roster = participation if participation is not None else manifest["participation"]
    if (digest(participation_binding(roster)) != manifest["canonical_sha256"]
            or build_country_counts(roster, frozen) != manifest["counts"]
            or frozen["sha256"] != manifest["inventory_sha256"]):
        raise ValueError("Map participation, country counts or inventory have changed; regenerate maps")
    output_path = folder / "output-manifest.json"
    if not output_path.exists():
        if list(folder.glob("*.pdf")) or list(folder.glob("*.png")):
            raise ValueError("Partial map render lacks its output manifest")
        return ValidatedMapAssets("empty", {}, manifest)
    rendered = _read_json(output_path)
    if (rendered.get("canonical_sha256") != manifest["canonical_sha256"] or rendered.get("counts") != manifest["counts"]
            or rendered.get("input_manifest_sha256") != file_hash(folder / "input-manifest.json")
            or rendered.get("render_spec") != manifest["render_spec"]):
        raise ValueError("Rendered maps have stale input/count/render specification bindings")
    outputs = rendered.get("outputs", {})
    if set(outputs) != set(keys):
        raise ValueError("Rendered map set is incomplete")
    figures = {}
    for key in keys:
        record = outputs[key]
        if set(record.get("devices", {})) != {"pdf", "png"}:
            raise ValueError("Map device audits must cover both PDF and PNG")
        for audit in record["devices"].values():
            _validate_device_audit(audit, sorted(row["country"] for row in manifest["counts"]["countries"]))
        for extension in ("pdf", "png"):
            name = record.get(extension)
            if name != f"{key}.{extension}":
                raise ValueError("Unsafe map figure path")
            path = folder / name
            if path.is_symlink() or file_hash(path) != record.get(extension + "_sha256"):
                raise ValueError(f"Map figure hash changed: {name}")
            if extension == "pdf":
                if not path.read_bytes().startswith(b"%PDF-"):
                    raise ValueError("Map PDF is not a PDF document")
                figures[key] = path
            elif not path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("Map PNG is not a PNG image")
    return ValidatedMapAssets("ready", figures, manifest)


def export_map_inputs(args, directory_factory) -> Path:
    """Prepare map bundles using frozen input or the shared Directory constructor.

    Args:
        args: Parsed peer-command options, including JSON inputs and bundle destination.
        directory_factory: Shared constructor called only when no frozen inventory exists.

    Returns:
        Published map-input bundle path.

    Raises:
        ValueError: If inputs conflict, hashes disagree or frozen context is inconsistent.
    """
    kind = "so2" if args.command == "export-so2-map-r" else "mucp"
    paths = [Path(args.input_json)]
    combined = _read_json(paths[0]) if kind == "mucp" else None
    if kind == "mucp":
        paths.append(Path(args.so2_json))
    so2 = _read_json(paths[-1])
    if getattr(args, "directory_inventory", None):
        paths.append(Path(args.directory_inventory))
        frozen = validate_inventory(_read_json(paths[-1]))
        scope = "only-withdrawn" if getattr(args, "only_withdrawn", False) else "including-withdrawn" if getattr(args, "include_withdrawn", False) else "active"
        if (frozen["schema"] != args.schema or frozen["scope"] != scope or
                (args.directory_target and args.directory_target.rstrip("/") != frozen["target"].rstrip("/"))):
            raise ValueError("Frozen inventory target/schema/scope conflict with requested options")
    else:
        frozen = directory_inventory(directory_factory(args))
    identities = None
    if getattr(args, "participation_identities", None):
        paths.append(Path(args.participation_identities))
        identities = _read_json(paths[-1])
    output = Path(args.output_dir).resolve()
    if any(output == p.resolve() or output in p.resolve().parents or p.resolve() in output.parents for p in paths):
        raise ValueError("Map output overlaps a protected input")
    return write_map_bundle(collect_participation(so2, combined, identities), frozen, output,
                            kind=kind, layouts=args.map_layout, overwrite=args.overwrite, so2_payload=so2)
