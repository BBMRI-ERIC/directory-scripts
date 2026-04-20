import shutil
import subprocess

import pytest


def test_rmaps_big_output_scales_are_explicitly_larger():
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")

    script = r'''
source("R-maps/map_config.R")
cfg <- bbmri_map_config()

stopifnot(
  identical(unname(cfg$symbol_scale_by_output[["big"]]), 3.0),
  identical(unname(cfg$line_scale_by_output[["big"]]), 2.0),
  identical(unname(cfg$symbol_scale_by_output[["small"]]), 1.0),
  identical(unname(cfg$symbol_scale_by_output[["med"]]), 1.0),
  identical(unname(cfg$symbol_scale_by_output[["vector"]]), 1.0),
  identical(unname(cfg$line_scale_by_output[["small"]]), 1.0),
  identical(unname(cfg$line_scale_by_output[["med"]]), 1.0),
  identical(unname(cfg$line_scale_by_output[["vector"]]), 1.0)
)
'''
    subprocess.run([rscript, "-e", script], check=True)


def test_rmaps_save_formats_emit_size_specific_svgs():
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")

    script = r'''
source("R-maps/map_config.R")
source("R-maps/map_common.R")
if (!requireNamespace("svglite", quietly = TRUE)) {
  quit(status = 0)
}
cfg <- bbmri_map_config()
tmp_dir <- tempfile("rmaps-svg-")
dir.create(tmp_dir)
build_plot <- function(output_variant) {
  ggplot2::ggplot(data.frame(x = 1, y = 1)) +
    ggplot2::geom_point(ggplot2::aes(x = x, y = y), size = 2)
}
bbmri_save_plot_formats_from_builder(build_plot, tmp_dir, "demo", cfg$export_sizes)
stopifnot(
  file.exists(file.path(tmp_dir, "demo-small.svg")),
  file.exists(file.path(tmp_dir, "demo-med.svg")),
  file.exists(file.path(tmp_dir, "demo-big.svg")),
  file.exists(file.path(tmp_dir, "demo.svg"))
)
'''
    subprocess.run([rscript, "-e", script], check=True)
