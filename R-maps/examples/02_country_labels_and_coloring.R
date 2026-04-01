# Demonstrate the shared BBMRI country styling and label controls.
#
# The important part is that country colors come from the shared helpers and
# country labels are selected centrally rather than in a renderer-local way.

source(file.path("R-maps", "examples", "00_setup.R"))
bbmri_require_packages(c("ggplot2", "sf"))

countries <- bbmri_crop_to_bbox(
  bbmri_assign_standard_country_fill(bbmri_load_countries(), cfg),
  cfg$standard_bbox
)

labels_all <- bbmri_country_label_df(
  countries,
  cfg,
  cfg$standard_crs,
  label_codes = cfg$standard_country_labels
)
labels_member <- bbmri_country_label_df(
  countries,
  cfg,
  cfg$standard_crs,
  label_codes = cfg$standard_country_groups$member
)

message("All labels: ", nrow(labels_all), " countries")
message("Member labels: ", nrow(labels_member), " countries")

plot <- ggplot2::ggplot() +
  ggplot2::geom_sf(
    data = countries,
    ggplot2::aes(fill = fill_group),
    colour = "white",
    linewidth = 0.2
  ) +
  ggplot2::scale_fill_identity() +
  bbmri_coord_sf(cfg$standard_bbox, cfg$standard_crs) +
  bbmri_void_theme(cfg$standard_colors$water) +
  bbmri_geom_text_halo(
    data = labels_member,
    mapping = ggplot2::aes(x = x, y = y, label = label),
    size = cfg$standard_label_style$size,
    bbox = cfg$standard_bbox,
    crs = cfg$standard_crs,
    output_width_px = bbmri_output_width_px(cfg$export_sizes, "med"),
    family = bbmri_font_family(),
    inner_halo_px = cfg$standard_label_style$inner_halo_px,
    outer_halo_px = cfg$standard_label_style$outer_halo_px,
    alpha = cfg$standard_label_style$alpha
  )

print(plot)
