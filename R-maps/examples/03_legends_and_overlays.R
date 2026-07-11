# Demonstrate overlay layers and legend control.
#
# The pattern to copy is: prepare a tiny overlay data frame, style it from
# cfg, and then add it as a normal ggplot layer.

source(file.path("R-maps", "examples", "00_setup.R"))
bbmri_require_packages(c("ggplot2", "sf"))

layers <- bbmri_prepare_classic_layers(cfg$standard_bbox, cfg)

overlay_points <- data.frame(
  x = c(-3e6, 5e5),
  y = c(4.8e6, 5.6e6),
  label = c("Overlay A", "Overlay B"),
  fill = c(cfg$standard_colors$biobank, cfg$standard_colors$standalone),
  size = c(6, 4),
  stringsAsFactors = FALSE
)

legend_entries <- data.frame(
  label = c("Primary circle", "Secondary circle"),
  fill = c(cfg$standard_colors$biobank, cfg$standard_colors$standalone),
  colour = c(cfg$standard_colors$biobank_line, cfg$standard_colors$biobank_line),
  stroke = c(0.4, 0.4),
  alpha = c(0.85, 0.85),
  size = c(2.8, 2.8),
  stringsAsFactors = FALSE
)

plot <- bbmri_add_classic_base(
  ggplot2::ggplot(),
  layers = layers,
  bbox = cfg$standard_bbox,
  crs = cfg$standard_crs,
  cfg = cfg
) +
  ggplot2::geom_point(
    data = overlay_points,
    ggplot2::aes(x = x, y = y, fill = fill, size = size),
    shape = 21,
    stroke = 0.4,
    colour = cfg$standard_colors$biobank_line
  ) +
  ggplot2::scale_fill_identity() +
  ggplot2::scale_size_identity()

plot <- bbmri_add_circle_legend(
  plot = plot,
  entries = legend_entries,
  bbox = cfg$standard_bbox,
  crs = cfg$standard_crs,
  box = list(x = 0.03, y = 0.05, width = 0.24, height = 0.18),
  title = "Overlay legend",
  title_size = 2.5,
  text_size = 2.2,
  title_family = "serif",
  text_family = "serif"
)

print(plot)
