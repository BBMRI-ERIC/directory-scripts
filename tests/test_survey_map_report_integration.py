"""Verify external map replay and transactional publication alongside report outputs."""

import json
from pathlib import Path

import pytest

from test_survey_participation import sources, inventory


def rendered_bundle(tmp_path):
    """Create an invented rendered bundle with exact hash-bound output evidence.

    Args:
        tmp_path: Isolated bundle location.

    Returns:
        Descriptive payload and validated map figures with safe synthetic PDF bytes.
    """
    from survey_map_assets import write_map_bundle, file_hash
    from survey_participation import collect_participation
    so2, _ = sources()
    folder = tmp_path / "maps"
    write_map_bundle(collect_participation(so2), inventory(), folder, kind="so2", layouts="oec", so2_payload=so2)
    m = json.loads((folder / "input-manifest.json").read_text())
    output = {"input_manifest_sha256": file_hash(folder / "input-manifest.json"),
              "canonical_sha256": m["canonical_sha256"], "counts": m["counts"], "render_spec": m["render_spec"], "outputs": {}}
    for key in m["figure_keys"]:
        row = {"devices": {device: {"collision_count": 0, "boxes": [[2, 12, 20, 30]],
               "countries": ["AT"], "reserved_boxes": []} for device in ("pdf", "png")}}
        for ext in ("pdf", "png"):
            path = folder / f"{key}.{ext}"
            path.write_bytes(b"%PDF-fixture" if ext == "pdf" else b"\x89PNG\r\n\x1a\nfixture")
            row.update({ext: path.name, ext + "_sha256": file_hash(path)})
        output["outputs"][key] = row
    (folder / "output-manifest.json").write_text(json.dumps(output))
    return so2, folder


def test_ready_bundle_replay_and_staleness_are_offline(tmp_path):
    """Recompute current SO2 grouping and reject stale input without remote access.

    Args:
        tmp_path: Prepared input/output files generated only by the test.

    Returns:
        None. Valid assets load; changed source countries fail rather than publish.
    """
    from survey_map_report import load_report_map_assets, map_report_fragment
    payload, folder = rendered_bundle(tmp_path)
    assets = load_report_map_assets(payload, folder, "so2")
    fragment, binary = map_report_fragment(assets)
    assert len(binary) == 2 and r"\begin{landscape}" in fragment
    assert "unresolved" in fragment.lower() and "frozen" in fragment.lower()
    payload["responses_summary"]["source_records"][2]["answers"]["Country"] = "IT"
    with pytest.raises(ValueError, match="changed"):
        load_report_map_assets(payload, folder, "so2")


@pytest.mark.parametrize("combined", [False, True])
def test_tex_only_publication_copies_binary_maps_portably(tmp_path, combined):
    """Publish companion PDF assets without depending on the original bundle path.

    Args:
        tmp_path: Isolated report targets, bundle and portable asset directories.
        combined: Whether to use the combined or standalone publication function.

    Returns:
        None. Published TeX points only at its own sibling map assets.
    """
    from so2_descriptive_report import RenderedDescriptiveReport, render_descriptive_pdf
    from survey_map_report import map_report_fragment, load_report_map_assets
    payload, folder = rendered_bundle(tmp_path)
    fragment, binary = map_report_fragment(load_report_map_assets(payload, folder, "so2"))
    rendered = RenderedDescriptiveReport(fragment, {}, {}, {}, external_figures=binary)
    target = tmp_path / "report & spaces.tex"
    if combined:
        from survey_combined_report import publish_combined_outputs
        publish_combined_outputs({"biobanks": []}, rendered,
            {"output_json": tmp_path / "combined.json", "output_tex": target}, {}, (), False)
    else:
        render_descriptive_pdf(rendered, target, None, None)
    assert "__SURVEY_MAPS__" not in target.read_text()
    assert str(folder) not in target.read_text()
    assert len(list(tmp_path.glob("map-assets-*/*.pdf"))) == 2


def test_failed_binary_staging_keeps_all_report_sentinels(tmp_path, monkeypatch):
    """A copy failure cannot replace prior PDF, TeX, JSON or external maps.

    Args:
        tmp_path: Isolated report and asset targets containing original sentinel bytes.
        monkeypatch: Patch manager injecting a map staging failure before publication.

    Returns:
        None. Every existing output remains byte-identical.
    """
    from so2_descriptive_report import RenderedDescriptiveReport, render_descriptive_pdf
    import survey_map_report as maps
    payload, folder = rendered_bundle(tmp_path)
    fragment, binary = maps.map_report_fragment(maps.load_report_map_assets(payload, folder, "so2"))
    rendered = RenderedDescriptiveReport(fragment, {}, {}, {}, external_figures=binary)
    target = tmp_path / "report.tex"
    target.write_text("old tex")

    def fail(_root, _figures):
        """Simulate inability to stage an external map file.

        Args:
            _root: Temporary publication root.
            _figures: Binary figures that must not reach final targets.

        Returns:
            None; staging always raises in this test.
        """
        raise OSError("Map staging failed")

    monkeypatch.setattr(maps, "write_external_figures", fail)
    with pytest.raises(Exception, match="staging"):
        render_descriptive_pdf(rendered, target, None, None, overwrite=True)
    assert target.read_text() == "old tex"


def test_render_audit_cannot_drop_a_country_or_overlap_a_legend(tmp_path):
    """Reject incomplete group geometry even when PDF byte hashes are intact.

    Args:
        tmp_path: Isolated rendered bundle with mutable output diagnostics.

    Returns:
        None. Country omissions and group/legend intersections block map loading.
    """
    from survey_map_report import load_report_map_assets
    payload, folder = rendered_bundle(tmp_path)
    path = folder / "output-manifest.json"
    original = json.loads(path.read_text())
    first = next(iter(original["outputs"]))
    for update in ({"countries": []}, {"reserved_boxes": [[1, 15, 19, 31]]}):
        from copy import deepcopy
        output = deepcopy(original)
        output["outputs"][first]["devices"]["pdf"].update(update)
        path.write_text(json.dumps(output))
        with pytest.raises(ValueError, match="country|obstacle"):
            load_report_map_assets(payload, folder, "so2")


def test_external_map_target_cannot_overlap_chart_output(tmp_path):
    """Reject two publication directories claiming the same map/chart target.

    Args:
        tmp_path: Isolated report targets whose sentinels must remain untouched.

    Returns:
        None. Overlapping targets fail before any old output can be replaced.
    """
    from so2_descriptive_report import RenderedDescriptiveReport, render_descriptive_pdf
    from survey_map_report import bind_external_figures
    target = tmp_path / "report.tex"
    rendered = RenderedDescriptiveReport("x", {}, {}, {}, external_figures={"__SURVEY_MAPS__/figure.pdf": b"%PDF-fixture"})
    _, name = bind_external_figures(rendered, target)
    with pytest.raises(Exception, match="overlap"):
        render_descriptive_pdf(rendered, target, None, tmp_path / name)
    assert not target.exists()


def test_actual_pdf_compiles_with_portable_map_assets(tmp_path):
    """Compile a real external PDF through report staging rather than only mocks.

    Args:
        tmp_path: Isolated figure source, generated PDF and final report targets.

    Returns:
        None. A real XeLaTeX report includes its staged external PDF successfully.
    """
    import shutil
    import subprocess
    if not shutil.which("xelatex"):
        pytest.skip("XeLaTeX unavailable for actual external-PDF compilation")
    import so2_descriptive_report as report
    source = tmp_path / "figure.tex"
    source.write_text(r"\documentclass{standalone}\begin{document}Synthetic map figure\end{document}")
    result = subprocess.run(["xelatex", "-interaction=batchmode", "-halt-on-error", "-output-directory=" + str(tmp_path), str(source)],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout
    tex = r"\documentclass{article}\usepackage{graphicx}\begin{document}\includegraphics{__SURVEY_MAPS__/figure.pdf}\end{document}"
    rendered = report.RenderedDescriptiveReport(tex, {}, {}, {},
        external_figures={"__SURVEY_MAPS__/figure.pdf": source.with_suffix(".pdf").read_bytes()})
    report.render_descriptive_pdf(rendered, tmp_path / "report.tex", tmp_path / "report.pdf", None)
    assert (tmp_path / "report.pdf").read_bytes().startswith(b"%PDF-")
    assert "__SURVEY_MAPS__" not in (tmp_path / "report.tex").read_text()


@pytest.mark.parametrize("target_kind", ["inside", "parent", "companion"])
def test_input_bundle_is_protected_from_report_outputs(tmp_path, target_kind):
    """Reject direct, ancestor and generated-companion overwrites of map inputs.

    Args:
        tmp_path: Isolated protected map bundle and proposed report paths.
        target_kind: Alias relationship that must fail even with overwrite enabled.

    Returns:
        None. Safety validation leaves all input bytes untouched.
    """
    from survey_map_report import validate_report_map_paths
    from survey_participation import digest
    tex = tmp_path / "report.tex"
    bundle = tmp_path / ("map-assets-" + digest(tex.name)[:12]) if target_kind == "companion" else tmp_path / "maps"
    bundle.mkdir()
    sentinel = bundle / "input-manifest.json"
    sentinel.write_text("protected")
    target = sentinel if target_kind == "inside" else tmp_path if target_kind == "parent" else tex
    with pytest.raises(ValueError, match="overlap"):
        validate_report_map_paths(bundle, [target], tex)
    assert sentinel.read_text() == "protected"


def test_pdf_device_geometry_is_validated_independently_of_png(tmp_path):
    """Reject a colliding PDF even when PNG placement is valid.

    Args:
        tmp_path: Isolated rendered bundle with separate device audit fixtures.

    Returns:
        None. The report cannot rely only on the raster device's diagnostics.
    """
    from copy import deepcopy
    from survey_map_report import load_report_map_assets
    payload, folder = rendered_bundle(tmp_path)
    path = folder / "output-manifest.json"
    output = json.loads(path.read_text())
    for row in output["outputs"].values():
        audit = row["devices"]["png"]
        row["devices"] = {"pdf": deepcopy(audit), "png": deepcopy(audit)}
        row["devices"]["pdf"]["reserved_boxes"] = [[1, 15, 19, 31]]
    path.write_text(json.dumps(output))
    with pytest.raises(ValueError, match="obstacle"):
        load_report_map_assets(payload, folder, "so2")


@pytest.mark.parametrize("combined", [False, True])
def test_promotion_failure_restores_portable_maps_and_all_prior_outputs(tmp_path, monkeypatch, combined):
    """Exercise rollback after report/map promotion has begun, not just staging.

    Args:
        tmp_path: Isolated source bundle and old report/chart/map sentinels.
        monkeypatch: Patch manager injecting one destination replacement failure.
        combined: Whether to exercise the MuCP or SO2 publication transaction.

    Returns:
        None. Original JSON, TeX, chart and companion bytes survive the failure.
    """
    import os
    from so2_descriptive_report import RenderedDescriptiveReport, render_descriptive_pdf
    from survey_map_report import bind_external_figures
    rendered = RenderedDescriptiveReport("new tex", {}, {}, {},
        external_figures={"__SURVEY_MAPS__/figure.pdf": b"%PDF-new"})
    tex = tmp_path / "report.tex"
    result = tmp_path / "report.json"
    charts = tmp_path / "charts"
    _, name = bind_external_figures(rendered, tex)
    maps = tmp_path / name
    for directory in (charts, maps):
        directory.mkdir()
        (directory / "sentinel").write_bytes(b"old directory")
    tex.write_bytes(b"old tex")
    result.write_bytes(b"old json")
    original = os.replace
    failed = False

    def fail_once(source, target):
        """Fail one promotion while permitting all subsequent rollback moves.

        Args:
            source: Temporary promoted file/directory or old backup.
            target: Final destination being replaced.

        Returns:
            The underlying os.replace result except for one injected OSError.
        """
        nonlocal failed
        if not failed and Path(target) == (maps if combined else result):
            failed = True
            raise OSError("Injected promotion failure")
        return original(source, target)

    monkeypatch.setattr(os, "replace", fail_once)
    with pytest.raises(Exception, match="promotion failure"):
        if combined:
            from survey_combined_report import publish_combined_outputs
            publish_combined_outputs({"biobanks": []}, rendered,
                {"output_json": result, "output_tex": tex, "output_chart_dir": charts}, {}, (), True)
        else:
            render_descriptive_pdf(rendered, tex, None, charts, overwrite=True,
                additional_text_outputs={result: "new json"})
    assert failed
    assert tex.read_bytes() == b"old tex" and result.read_bytes() == b"old json"
    for directory in (charts, maps):
        assert [path.name for path in directory.iterdir()] == ["sentinel"]
        assert (directory / "sentinel").read_bytes() == b"old directory"


@pytest.mark.parametrize("kind,conflicts", [("so2", 0), ("mucp", 0), ("mucp", 2)])
def test_map_and_caption_fit_one_koma_landscape_page(tmp_path, kind, conflicts):
    """Compile the actual full-size map fragment with the reports' KOMA page geometry.

    Args:
        tmp_path: Isolated synthetic 240x135 mm figure and compiled report copy.
        kind: Report family whose source-specific interpretation caption must fit.
        conflicts: Number of audited unresolved shared-country matches disclosed.

    Returns:
        None. One map and its interpretation caption occupy exactly one page.
    """
    import shutil
    import subprocess
    from so2_descriptive_report import RenderedDescriptiveReport, render_descriptive_pdf
    from survey_map_assets import ValidatedMapAssets
    from survey_map_report import map_report_fragment
    if not shutil.which("xelatex") or not shutil.which("pdfinfo"):
        pytest.skip("XeLaTeX/pdfinfo unavailable for actual map page-fit validation")
    source = tmp_path / "map.tex"
    source.write_text(r"\documentclass{standalone}\begin{document}\rule{240mm}{135mm}\end{document}")
    subprocess.run(["xelatex", "-interaction=batchmode", "-halt-on-error", "-output-directory=" + str(tmp_path), str(source)],
                   capture_output=True, text=True, check=True, timeout=120)
    assets = ValidatedMapAssets("ready", {kind + "-oec-responses": source.with_suffix(".pdf")},
        {"kind": kind, "counts": {"national_summaries": [], "shared_country_conflicts": [{}] * conflicts}})
    fragment, images = map_report_fragment(assets)
    tex = (r"\documentclass[11pt]{scrartcl}\KOMAoptions{parskip=half}\usepackage{libertine}"
           r"\usepackage{relsize}\usepackage{graphicx}\usepackage{hyperref}\usepackage{pdflscape}"
           r"\begin{document}" + fragment + r"\end{document}")
    render_descriptive_pdf(RenderedDescriptiveReport(tex, {}, {}, {}, external_figures=images),
                           tmp_path / "report.tex", tmp_path / "report.pdf", None)
    info = subprocess.run(["pdfinfo", str(tmp_path / "report.pdf")], capture_output=True, text=True, check=True)
    assert next(line.split(":", 1)[1].strip() for line in info.stdout.splitlines() if line.startswith("Pages:")) == "1"
