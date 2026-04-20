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
stopifnot("SO:" %in% all_labels, all(as.character(1:8) %in% all_labels))
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
so_rect_idx <- which(vapply(so_plot$layers, function(layer) class(layer$geom)[[1]], character(1)) == "GeomRect")[1]
global_rect_idx <- which(vapply(global_plot$layers, function(layer) class(layer$geom)[[1]], character(1)) == "GeomRect" & vapply(global_built$data, function(df) any(!is.na(df$fill)), logical(1)))[1]
so_rect <- so_built$data[[so_rect_idx]]
global_rect <- global_built$data[[global_rect_idx]]
stopifnot(
  max(global_rect$xmax - global_rect$xmin) < max(so_rect$xmax - so_rect$xmin),
  max(global_rect$ymax - global_rect$ymin) < max(so_rect$ymax - so_rect$ymin)
)
global_text <- unique(unlist(lapply(global_built$data, function(df) if ("label" %in% names(df)) as.character(df$label) else character(0))))
stopifnot(any(trimws(global_text) == "SO:"), all(as.character(1:8) %in% global_text))
'''
    subprocess.run([rscript, "-e", script], check=True)


def test_global_bars_fallback_to_visible_label_anchor_for_norway():
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")

    script = r'''
source("R-maps/strategic_objectives_common.R")
source("R-maps/examples/00_setup.R")
spec <- bbmri_load_strategic_objectives_spec(file.path(script_dir, "data", "strategic-objectives-template.toml"))
so2_spec <- bbmri_so_subset_spec(spec, objective_ids = "SO2")
cfg_local <- cfg
layers <- bbmri_so_prepare_layers(cfg_local$standard_bbox, cfg_local)
raw_anchor <- bbmri_country_anchor_df(layers$countries, cfg_local$standard_crs, label_codes = c("NO"))
label_anchor <- bbmri_country_label_df(layers$countries, cfg_local, cfg_local$standard_crs, label_codes = c("NO"))
bar_anchor <- bbmri_so_bar_anchor_df(layers$countries, cfg_local, cfg_local$standard_crs, c("NO"))
stopifnot(
  nrow(raw_anchor) == 1L,
  nrow(label_anchor) == 1L,
  nrow(bar_anchor) == 1L,
  abs(bar_anchor$bar_y[[1]] - label_anchor$y[[1]]) < 1e-6,
  abs(bar_anchor$bar_y[[1]] - raw_anchor$y[[1]]) > 1e6
)
'''
    subprocess.run([rscript, "-e", script], check=True)


def test_global_bar_frames_do_not_overlap_or_touch_after_resolution():
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")

    script = r'''
source("R-maps/strategic_objectives_common.R")
source("R-maps/examples/00_setup.R")
spec <- bbmri_load_strategic_objectives_spec(file.path(script_dir, "data", "strategic-objectives-template.toml"))
global_plot <- bbmri_so_make_bars_plot(
  spec,
  level = "global",
  output_variant = "med",
  cfg = cfg,
  country_label_codes = cfg$standard_country_labels,
  objective_order = bbmri_so_objective_ids(spec)
)
built <- ggplot2::ggplot_build(global_plot)
frame_idx <- which(vapply(global_plot$layers, function(layer) class(layer$geom)[[1]], character(1)) == "GeomRect" & vapply(built$data, function(df) all(is.na(df$fill)), logical(1)))[1]
frames <- built$data[[frame_idx]]
if (nrow(frames) > 1) {
  touches <- FALSE
  for (i in seq_len(nrow(frames) - 1L)) {
    for (j in seq.int(i + 1L, nrow(frames))) {
      separated <- (
        frames$xmax[[i]] < frames$xmin[[j]] ||
        frames$xmax[[j]] < frames$xmin[[i]] ||
        frames$ymax[[i]] < frames$ymin[[j]] ||
        frames$ymax[[j]] < frames$ymin[[i]]
      )
      if (!separated) {
        touches <- TRUE
        break
      }
    }
    if (touches) {
      break
    }
  }
  stopifnot(!touches)
}
'''
    subprocess.run([rscript, "-e", script], check=True)


def test_global_bar_positions_are_named_by_size():
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")

    script = r'''
source("R-maps/map_config.R")
cfg_local <- bbmri_map_config()
stopifnot(
  all(c("small", "med", "big") %in% names(cfg_local$so_global_bar_positions)),
  all(vapply(cfg_local$so_global_bar_position_seed, function(pos) all(c("lon", "lat") %in% names(pos)), logical(1)))
)
'''
    subprocess.run([rscript, "-e", script], check=True)


def test_global_bar_position_seed_contains_country_centers():
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")

    script = r'''
source("R-maps/map_config.R")
cfg_local <- bbmri_map_config()
seed <- cfg_local$so_global_bar_position_seed
stopifnot(
  length(seed$NO) == 2L,
  all(is.finite(unlist(seed))),
  abs(seed$DE[["lon"]] - 10.392360) < 1e-6,
  abs(seed$CY[["lat"]] - 34.915276) < 1e-6
)
'''
    subprocess.run([rscript, "-e", script], check=True)


def test_global_bar_country_labels_follow_resolved_anchor_positions():
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")

    script = r'''
source("R-maps/strategic_objectives_common.R")
anchor_df <- data.frame(
  iso_a2 = c("NO"),
  bar_x = c(12.5),
  bar_y = c(7.75),
  stringsAsFactors = FALSE
)
country_labels <- data.frame(
  iso_a2 = c("NO"),
  label = c("NORWAY"),
  x = c(0),
  y = c(0),
  stringsAsFactors = FALSE
)
label_df <- bbmri_so_global_bar_country_labels(anchor_df, country_labels, baseline_offset = 1.25)
stopifnot(
  nrow(label_df) == 1L,
  abs(label_df$x[[1]] - 12.5) < 1e-9,
  abs(label_df$y[[1]] - 6.5) < 1e-9,
  identical(label_df$hjust[[1]], 0.5),
  identical(label_df$vjust[[1]], 0.5)
)
'''
    subprocess.run([rscript, "-e", script], check=True)


def test_global_bars_do_not_duplicate_labels_for_bar_countries():
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")

    script = r'''
source("R-maps/strategic_objectives_common.R")
source("R-maps/examples/00_setup.R")
spec <- bbmri_load_strategic_objectives_spec(file.path(script_dir, "data", "strategic-objectives-template.toml"))
plot <- bbmri_so_make_bars_plot(
  spec,
  level = "global",
  output_variant = "med",
  cfg = cfg,
  country_label_codes = cfg$standard_country_labels,
  objective_order = bbmri_so_objective_ids(spec)
)
built <- ggplot2::ggplot_build(plot)
label_layers <- built$data[vapply(built$data, function(df) "label" %in% names(df), logical(1))]
label_sizes <- vapply(label_layers, nrow, integer(1))
bar_layer <- label_layers[[which.max(label_sizes)]]
other_labels <- unique(unlist(lapply(label_layers[label_sizes < max(label_sizes)], function(df) as.character(df$label))))
bar_labels <- unique(as.character(bar_layer$label))
stopifnot(length(intersect(bar_labels, other_labels)) == 0L)
'''
    subprocess.run([rscript, "-e", script], check=True)


def test_recolor_legend_includes_member_and_observer_without_so_involvement():
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")

    script = r'''
source("R-maps/strategic_objectives_common.R")
source("R-maps/examples/00_setup.R")
spec <- bbmri_load_strategic_objectives_spec(file.path(script_dir, "data", "strategic-objectives-template.toml"))
so2_spec <- bbmri_so_subset_spec(spec, objective_ids = "SO2")
plot <- bbmri_so_make_recolor_plot(
  so2_spec,
  level = "global",
  output_variant = "med",
  cfg = cfg,
  country_label_codes = cfg$standard_country_labels
)
built <- ggplot2::ggplot_build(plot)
all_labels <- unique(unlist(lapply(built$data, function(df) if ("label" %in% names(df)) as.character(df$label) else character(0))))
stopifnot(
  "Member (without SO involvement)" %in% all_labels,
  "Observer (without SO involvement)" %in% all_labels
)
'''
    subprocess.run([rscript, "-e", script], check=True)
