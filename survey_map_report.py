"""Replay participation evidence and compose portable external map figures."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from survey_map_assets import validate_map_assets
from survey_participation import collect_participation, digest

TOKEN = "__SURVEY_MAPS__"


def validate_report_map_paths(directory, outputs, tex_path=None) -> None:
    """Protect a source map bundle from explicit and derived report outputs.

    Args:
        directory: Protected prepared/rendered map bundle directory.
        outputs: Optional report file/directory destinations, including JSON.
        tex_path: Optional final TeX path defining a generated companion directory.

    Returns:
        None after proving every output disjoint from the protected bundle.

    Raises:
        ValueError: If an output equals, contains or is contained by the bundle.
    """
    protected = Path(directory).resolve()
    targets = [Path(path).resolve() for path in outputs if path is not None]
    if tex_path is not None:
        tex = Path(tex_path).resolve()
        targets.append(tex.parent / ("map-assets-" + digest(tex.name)[:12]))
    if any(target == protected or target in protected.parents or protected in target.parents for target in targets):
        raise ValueError("Report outputs overlap the protected map input bundle")


def load_report_map_assets(payload: dict, directory, kind: str):
    """Validate rendered maps against current survey identity evidence offline.

    Args:
        payload: Current descriptive or combined report data.
        directory: Prepared/rendered map asset directory.
        kind: so2 or mucp, defining the expected report and replay sources.

    Returns:
        Validated map assets with immutable binary-file hash evidence.

    Raises:
        ValueError: If survey inputs, identities or rendered files no longer match.
    """
    assets = validate_map_assets(None, directory, expected_kind=kind)
    if not assets.manifest:
        return assets
    manifest = assets.manifest
    so2 = payload if kind == "so2" else manifest.get("so2_snapshot")
    if not so2:
        raise ValueError("Map bundle lacks frozen SO2 grouping; regenerate map inputs")
    roster = collect_participation(so2, payload if kind == "mucp" else None,
                                   manifest["participation"]["review"])
    validated = validate_map_assets(roster, directory, expected_kind=kind)
    payload["participation_maps"] = {"canonical_sha256": manifest["canonical_sha256"],
        "inventory_sha256": manifest["inventory_sha256"], "counts": manifest["counts"],
        "kind": kind, "layouts": manifest["layouts"], "state": validated.state}
    return validated


def map_report_fragment(assets) -> tuple[str, dict[str, bytes]]:
    """Compose landscape map pages and their immutable binary asset payloads.

    Args:
        assets: Validated map bundle, or None when the option was not requested.

    Returns:
        TeX fragment and safe placeholder-relative PDF bytes. Missing options
        produce no content; requested unrendered bundles produce an explicit note.
    """
    if assets is None:
        return "", {}
    if assets.state != "ready":
        return r"\par\emph{Participation maps omitted: the supplied bundle has not been rendered.}\par", {}
    from so2_descriptive_report import _tex
    output, figures = [], {}
    inventory_scope = assets.manifest["counts"]
    national = len(inventory_scope.get("national_summaries", []))
    conflicts = len(inventory_scope.get("shared_country_conflicts", []))
    caption = (
        "Unresolved respondents included. Frozen Directory inventory; responses may exceed it. "
        "Percentages above 100% are possible; N/A means no denominator. "
        if assets.manifest["kind"] == "so2" else
        "Both full surveys, independently of the report cohort; unresolved respondents included. "
        "Shared segments: confirmed matches only. Directory outlines: frozen inventory. "
    )
    caption += f"National summaries count zero ({national} retained)."
    if conflicts:
        caption += f" {conflicts} shared matches have unresolved countries and no country segment."
    for i, (key, path) in enumerate(assets.figures.items()):
        relative = f"{TOKEN}/{key}.pdf"
        figures[relative] = path.read_bytes()
        output.extend([r"\clearpage", r"\begin{landscape}", r"\thispagestyle{plain}"])
        if i == 0:
            output.append(r"\phantomsection\addcontentsline{toc}{section}{Survey participation maps}")
        output.extend([r"\begingroup\setlength{\parskip}{0pt}",
            rf"\noindent\includegraphics[width=240mm,height=135mm,keepaspectratio]{{\detokenize{{{relative}}}}}\par",
            r"\smaller[2]\noindent " + _tex(caption) + r"\par\endgroup", r"\end{landscape}"])
    return "\n".join(output), figures


def bind_external_figures(rendered, tex_path):
    """Replace map placeholders with a safe portable sibling-directory name.

    Args:
        rendered: Existing RenderedDescriptiveReport with optional map binary bytes.
        tex_path: Final TeX filename, used only to allocate its stable asset basename.

    Returns:
        Updated frozen rendered object and asset-directory basename, or None when empty.
    """
    if not rendered.external_figures:
        return rendered, None
    name = "map-assets-" + digest(Path(tex_path).name)[:12]
    figures = {key.replace(TOKEN, name): value for key, value in rendered.external_figures.items()}
    return replace(rendered, tex=rendered.tex.replace(TOKEN, name), external_figures=figures), name


def write_external_figures(root: Path, figures: dict) -> None:
    """Stage binary map bytes beneath a controlled compilation/publication root.

    Args:
        root: Temporary staging root; all derived filenames must remain underneath it.
        figures: Relative PDF filenames mapped to validated immutable bytes.

    Returns:
        None after every external PDF has been written.

    Raises:
        ValueError: If an external figure attempts path traversal or has non-PDF bytes.
        OSError: If staging cannot complete; publication callers must roll back.
    """
    for name, content in figures.items():
        relative = Path(name)
        if (relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 2
                or relative.suffix != ".pdf" or not isinstance(content, bytes) or not content.startswith(b"%PDF-")):
            raise ValueError("Unsafe external map figure")
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
