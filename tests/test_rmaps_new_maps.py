import json
import shutil
import subprocess
from pathlib import Path

import pytest


R_SCRIPTS = [
    Path("R-maps/render_bbmri_members_labels.R"),
    Path("R-maps/render_global_labels.R"),
    Path("R-maps/render_global_sized.R"),
    Path("R-maps/render_covid_labels.R"),
    Path("R-maps/render_covid_sized.R"),
    Path("R-maps/render_rare_diseases_common.R"),
    Path("R-maps/render_rare_diseases_nolabels.R"),
    Path("R-maps/render_rare_diseases_labels.R"),
    Path("R-maps/render_rare_diseases_sized.R"),
    Path("R-maps/strategic_objectives_common.R"),
    Path("R-maps/render_strategic_objectives.R"),
    Path("R-maps/render_pilot_maps.R"),
]


@pytest.mark.parametrize("script_path", R_SCRIPTS)
def test_new_rmaps_scripts_parse(script_path):
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")

    subprocess.run([rscript, "-e", f'parse(file="{script_path.as_posix()}")'], check=True)


def test_rare_disease_prep_script_compiles():
    py = shutil.which("python3")
    if py is None:
        pytest.skip("python3 not available")
    subprocess.run([py, "-m", "py_compile", "R-maps/prepare_rare_diseases_geojson.py"], check=True)


def test_label_layer_order_and_rare_disease_fixed_sizes():
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")

    script = r'''
source("R-maps/render_bbmri_members_labels.R")
source("R-maps/render_rare_diseases_common.R")

labels_plot <- build_members_labels_map(
  "bbmri-directory-pilot.geojson",
  NA_character_,
  output_variant = "med"
)
geom_names <- vapply(labels_plot$layers, function(layer) class(layer$geom)[[1]], character(1))
point_idx <- match("GeomPoint", geom_names)
text_idxs <- which(geom_names == "GeomText")
stopifnot(length(text_idxs) > 0, any(text_idxs < point_idx), any(text_idxs > point_idx))

rd_plot <- build_rare_diseases_map(
  "bbmri-directory-rare-diseases-pilot.geojson",
  NA_character_,
  output_variant = "med",
  include_biobank_labels = FALSE
)
rd_geom_names <- vapply(rd_plot$layers, function(layer) class(layer$geom)[[1]], character(1))
rd_point_idx <- match("GeomPoint", rd_geom_names)
rd_build <- ggplot2::ggplot_build(rd_plot)
rd_sizes <- rd_build$data[[rd_point_idx]]$size
stopifnot(length(unique(round(rd_sizes, 6))) == 1)
'''
    subprocess.run([rscript, "-e", script], check=True)


def test_strategic_objectives_template_is_valid_toml_and_normalizes():
    py = shutil.which("python3")
    if py is None:
        pytest.skip("python3 not available")

    template_path = Path("R-maps/data/strategic-objectives-template.toml")
    helper = Path("R-maps/prepare_strategic_objectives_spec.py")
    tmp_json = Path("R-maps/compare-temp") / "strategic-objectives-template.json"
    tmp_json.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([py, str(helper), "--input", str(template_path), "--output", str(tmp_json)], check=True)

    with tmp_json.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    assert data["schema_version"] == 1
    assert [obj["id"] for obj in data["objectives"]] == ["SO1", "SO2", "SO3", "SO4", "SO5", "SO6", "SO7", "SO8"]
    so2 = next(obj for obj in data["objectives"] if obj["id"] == "SO2")
    assert len(so2["goals"]) == 6
