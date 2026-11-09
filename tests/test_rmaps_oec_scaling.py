"""Verify OEC styling at equal display size across export variants."""

import shutil
import subprocess

import pytest


def test_oec_medium_is_midway_between_small_and_big():
    """Check page-relative marker and connector sizes without changing endpoints.

    Returns:
        None. Fails if the medium symbols or strokes are not the arithmetic
        midpoint of the small and big styles after fitting to the same width.
    """
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")
    subprocess.run([rscript, "-e", r'''
source("R-maps/map_config.R")
source("R-maps/map_common.R")
cfg <- bbmri_map_config()
variants <- c("small", "med", "big", "vector")
styles <- lapply(variants, function(v) bbmri_oec_scales_for_output(cfg, v))
names(styles) <- variants
widths <- c(small = 1920, med = 4800, big = 12840, vector = 2400)
for (field in c("symbol_scale", "line_scale")) {
  relative <- vapply(variants, function(v) styles[[v]][[field]] / widths[[v]], numeric(1))
  stopifnot(isTRUE(all.equal(relative[["med"]], mean(relative[c("small", "big")]))))
}
stopifnot(
  styles$small$symbol_scale == 1, styles$big$symbol_scale == 3,
  styles$small$line_scale == 1, styles$big$line_scale == 2,
  styles$vector$symbol_scale == 1, styles$vector$line_scale == 1,
  cfg$symbol_scale_by_output[["med"]] == 1,
  cfg$line_scale_by_output[["med"]] == 1
)
'''], check=True)


def test_oec_outlines_match_downscaled_big_for_every_variant():
    """Check width-relative polygon strokes for raster and unsuffixed vector maps.

    Returns:
        None. Fails if outlines differ at equal displayed map width or do not
        respond to changed export dimensions.
    """
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")
    subprocess.run([rscript, "-e", r'''
source("R-maps/map_config.R")
source("R-maps/map_common.R")
cfg <- bbmri_map_config()
for (width_factor in c(1, 1.5)) {
  cfg$oec_export_sizes$png$med <- cfg$oec_export_sizes$png$med * width_factor
  sizes <- c(cfg$oec_export_sizes$png, list(vector = cfg$oec_export_sizes$vector))
  for (v in names(sizes)) {
    style <- bbmri_oec_scales_for_output(cfg, v)
    stopifnot(isTRUE(all.equal(
      style$country_line_scale / unname(sizes[[v]][["width"]]),
      2 / 12840
    )))
  }
}
stopifnot(bbmri_oec_scales_for_output(cfg, "big")$country_line_scale == 2)
'''], check=True)


def test_oec_scaling_rejects_invalid_variant_and_dimensions():
    """Reject configuration errors instead of silently using incorrect proportions.

    Returns:
        None. Fails if an unknown variant or nonpositive export width is accepted.
    """
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")
    subprocess.run([rscript, "-e", r'''
source("R-maps/map_config.R")
source("R-maps/map_common.R")
cfg <- bbmri_map_config()
stopifnot(is.list(bbmri_oec_scales_for_output(cfg, "med")))
stopifnot(inherits(try(bbmri_oec_scales_for_output(cfg, "typo"), silent = TRUE), "try-error"))
cfg$oec_export_sizes$png$small[["width"]] <- 0
stopifnot(inherits(try(bbmri_oec_scales_for_output(cfg, "med"), silent = TRUE), "try-error"))
'''], check=True)


def test_oec_export_measures_connectors_on_actual_device_size():
    """Keep layout measurement and PNG/PDF/SVG physical dimensions identical.

    Returns:
        None. Fails if any export uses different physical dimensions from those
        supplied to its map builder, which would shift device-dependent anchors.
    """
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")
    subprocess.run([rscript, "-e", r'''
source("R-maps/render_bbmri_members_oec_all.R")
stopifnot(requireNamespace("ggplot2", quietly = TRUE))
measured <- list()
saved <- list()
build_members_oec_all_map <- function(..., output_variant, device_width_in, device_height_in) {
  measured[[output_variant]] <<- c(device_width_in, device_height_in)
  ggplot2::ggplot() + ggplot2::theme_void()
}
trace("ggsave", where = asNamespace("ggplot2"), print = FALSE, tracer = quote({
  saved[[length(saved) + 1]] <<- list(
    path = filename, size = c(width, height), units = units, dpi = dpi
  )
}))
output_dir <- tempfile("oec-device-test-")
sizes <- list(
  png = list(small = c(width = 120, height = 70), med = c(width = 240, height = 140),
             big = c(width = 360, height = 210)),
  vector = c(width = 240, height = 140)
)
bbmri_save_members_oec_all_formats(
  list(output_dir = output_dir, output_prefix = "test", input = "unused",
       iarc = "unused", node_points = "unused", node_lines = "unused"), sizes
)
untrace("ggsave", where = asNamespace("ggplot2"))
stopifnot(length(saved) >= 7)
for (export in saved) {
  stem <- sub("[.][^.]+$", "", basename(export$path))
  variant <- if (stem == "test") "vector" else sub("^test-", "", stem)
  physical_size <- if (export$units == "px") export$size / export$dpi else export$size
  stopifnot(isTRUE(all.equal(unname(physical_size), unname(measured[[variant]]))))
}
unlink(output_dir, recursive = TRUE)
'''], check=True)
