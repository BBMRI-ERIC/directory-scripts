import shutil
import subprocess
from pathlib import Path

import pytest


def test_strategic_objectives_common_and_renderer_parse():
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")

    for script_path in [
        Path("R-maps/strategic_objectives_common.R"),
        Path("R-maps/render_strategic_objectives.R"),
    ]:
        subprocess.run([rscript, "-e", f'parse(file="{script_path.as_posix()}")'], check=True)


def test_strategic_objectives_family_renders_outputs():
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")

    script = r'''
source("R-maps/strategic_objectives_common.R")
spec <- bbmri_load_strategic_objectives_spec("R-maps/data/strategic-objectives-template.toml")
so2_spec <- bbmri_so_subset_spec(spec, objective_ids = "SO2")
tmp_dir <- tempfile("so-sg-")
dir.create(tmp_dir)
bbmri_save_strategic_objectives_formats(
  spec = so2_spec,
  output_dir = tmp_dir,
  output_prefix = "demo-so2",
  levels = c("sg", "so", "global"),
  modes = c("recolor", "bars"),
)
stopifnot(
  file.exists(file.path(tmp_dir, "demo-so2-sg-SO2.1-recolor-small.png")),
  file.exists(file.path(tmp_dir, "demo-so2-so-SO2-recolor-small.png")),
  file.exists(file.path(tmp_dir, "demo-so2-so-SO2-bars-small.png")),
  file.exists(file.path(tmp_dir, "demo-so2-global-recolor-small.png")),
  file.exists(file.path(tmp_dir, "demo-so2-global-bars-small.png"))
)
if (requireNamespace("svglite", quietly = TRUE)) {
  stopifnot(
    file.exists(file.path(tmp_dir, "demo-so2-sg-SO2.1-recolor-small.svg")),
    file.exists(file.path(tmp_dir, "demo-so2-global-bars-small.svg"))
  )
}
'''
    subprocess.run([rscript, "-e", script], check=True)


def test_strategic_objectives_subset_helper_keeps_so2_only():
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")

    script = r'''
source("R-maps/strategic_objectives_common.R")
spec <- bbmri_load_strategic_objectives_spec("R-maps/data/strategic-objectives-template.toml")
so2_spec <- bbmri_so_subset_spec(spec, objective_ids = "SO2")
stopifnot(
  identical(vapply(so2_spec$objectives, function(obj) obj$id, character(1)), "SO2"),
  length(so2_spec$objectives[[1]]$goals) == 6
)
'''
    subprocess.run([rscript, "-e", script], check=True)


def test_global_bars_keep_all_so_labels_when_order_is_supplied():
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")

    script = r'''
source("R-maps/strategic_objectives_common.R")
source("R-maps/examples/00_setup.R")
spec <- bbmri_load_strategic_objectives_spec(file.path(script_dir, "data", "strategic-objectives-template.toml"))
so2_spec <- bbmri_so_subset_spec(spec, objective_ids = "SO2")
plot <- bbmri_so_make_bars_plot(
  so2_spec,
  level = "global",
  output_variant = "med",
  cfg = cfg,
  country_label_codes = cfg$standard_country_labels,
  objective_order = bbmri_so_objective_ids(spec)
)
built <- ggplot2::ggplot_build(plot)
all_labels <- unique(unlist(lapply(built$data, function(df) if ("label" %in% names(df)) as.character(df$label) else character(0))))
stopifnot("SO: 12345678" %in% all_labels)
'''
    subprocess.run([rscript, "-e", script], check=True)


def test_global_bars_are_compact_and_use_so_prefix_labels():
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")

    script = r'''
source("R-maps/strategic_objectives_common.R")
source("R-maps/examples/00_setup.R")
spec <- bbmri_load_strategic_objectives_spec(file.path(script_dir, "data", "strategic-objectives-template.toml"))
so2_spec <- bbmri_so_subset_spec(spec, objective_ids = "SO2")
so_plot <- bbmri_so_make_bars_plot(
  so2_spec,
  level = "so",
  objective_filter = "SO2",
  output_variant = "med",
  cfg = cfg,
  country_label_codes = cfg$standard_country_labels
)
global_plot <- bbmri_so_make_bars_plot(
  so2_spec,
  level = "global",
  output_variant = "med",
  cfg = cfg,
  country_label_codes = cfg$standard_country_labels,
  objective_order = bbmri_so_objective_ids(spec)
)
so_built <- ggplot2::ggplot_build(so_plot)
global_built <- ggplot2::ggplot_build(global_plot)
so_rect <- so_built$data[[which(vapply(so_plot$layers, function(layer) class(layer$geom)[[1]], character(1)) == "GeomRect")[1]]]
global_rect <- global_built$data[[which(vapply(global_plot$layers, function(layer) class(layer$geom)[[1]], character(1)) == "GeomRect")[1]]]
stopifnot(
  max(global_rect$xmax - global_rect$xmin) < max(so_rect$xmax - so_rect$xmin),
  max(global_rect$ymax - global_rect$ymin) < max(so_rect$ymax - so_rect$ymin)
)
global_text <- unique(unlist(lapply(global_built$data, function(df) if ("label" %in% names(df)) as.character(df$label) else character(0))))
stopifnot("SO: 12345678" %in% global_text)
'''
    subprocess.run([rscript, "-e", script], check=True)
