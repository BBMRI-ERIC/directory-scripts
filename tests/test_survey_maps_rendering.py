"""Run real R/grid glyph and collision assertions independently of geospatial packages."""

from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_real_r_measures_and_separates_country_groups():
    """Validate actual device font widths, exact counts and dense-country placement.

    Returns:
        None. Real R assertions pass; lack of all R runtimes is an explicit skip.
    """
    runtime = shutil.which("Rscript")
    if runtime:
        command = [runtime]
    elif shutil.which("proot-distro"):
        command = ["proot-distro", "login", "debian", "--bind", f"{ROOT}:{ROOT}", "--", "Rscript"]
    else:
        pytest.skip("No Rscript or Debian proot for real grid measurement")
    result = subprocess.run(command + [str(ROOT / "tests/r/test_survey_participation.R"), str(ROOT)],
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stderr
    assert "glyph and collision assertions passed" in result.stdout


def test_real_geospatial_bundle_renders_and_validates(tmp_path):
    """Render all six real map variants when an operator prepared R and basemaps.

    Args:
        tmp_path: Isolated SO2/MuCP bundles and output-manifest destinations.

    Returns:
        None. Real PDF/PNG device audits validate; unavailable dependencies skip explicitly.
    """
    from test_survey_participation import sources, inventory
    from survey_participation import collect_participation
    from survey_map_assets import write_map_bundle, validate_map_assets
    runtime = shutil.which("Rscript")
    if runtime:
        command = [runtime]
    elif shutil.which("proot-distro"):
        command = ["proot-distro", "login", "debian", "--bind", f"{ROOT}:{ROOT}",
                   "--bind", f"{tmp_path}:{tmp_path}", "--", "Rscript"]
    else:
        pytest.skip("No R runtime for geographic validation")
    probe = subprocess.run(command + ["-e", "quit(status=if(all(vapply(c('sf','cowplot','digest','ggplot2','jsonlite'),requireNamespace,logical(1),quietly=TRUE))) 0 else 77)"],
                           capture_output=True, text=True, timeout=120)
    if probe.returncode == 77:
        pytest.skip("R geospatial packages missing; installation requires operator approval")
    assert probe.returncode == 0, probe.stderr
    if not (ROOT / "R-maps/cache/natural-earth/10m-admin-0-countries.zip").is_file():
        pytest.skip("Natural Earth country cache missing; first-use network fetch needs operator setup")
    so2, combined = sources()
    for kind in ("so2", "mucp"):
        roster = collect_participation(so2, combined if kind == "mucp" else None)
        folder = tmp_path / kind
        write_map_bundle(roster, inventory(7), folder, kind=kind, so2_payload=so2)
        result = subprocess.run(command + [str(ROOT / "R-maps/render_survey_participation.R"),
            "--bundle=" + str(folder), "--kind=" + kind], capture_output=True, text=True, timeout=600)
        assert result.returncode == 0, result.stderr
        assets = validate_map_assets(roster, folder, expected_kind=kind)
        assert assets.state == "ready" and len(assets.figures) == (4 if kind == "so2" else 2)
