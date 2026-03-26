cmd_args <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", cmd_args, value = TRUE)
script_dir <- if (length(file_arg) == 0) {
  normalizePath(".", winslash = "/", mustWork = TRUE)
} else {
  normalizePath(dirname(sub("^--file=", "", file_arg[[1]])), winslash = "/", mustWork = TRUE)
}
source(file.path(script_dir, "map_config.R"))
source(file.path(script_dir, "map_common.R"))

build_members_nolabels_map <- function(points_path, iarc_path = NA_character_) {
  bbmri_require_packages(c("ggplot2", "sf"))

  cfg <- bbmri_map_config()
  label_style <- cfg$standard_label_style
  iarc_symbol <- cfg$standard_iarc_symbol
  iarc_label_placement <- cfg$standard_iarc_label_placement
  countries <- bbmri_crop_to_bbox(
    bbmri_assign_standard_country_fill(bbmri_load_countries(), cfg),
    cfg$standard_bbox
  )
  states <- bbmri_crop_to_bbox(bbmri_load_states(), cfg$standard_bbox)
  points <- bbmri_read_sf(points_path, "Biobank GeoJSON")
  iarc <- bbmri_read_optional_sf(iarc_path)

  country_labels <- bbmri_country_label_df(countries, cfg, cfg$standard_crs)
  point_df <- bbmri_biobank_points_df(points, cfg$standard_crs, label = "biobank points")
  country_labels <- bbmri_place_country_labels(
    country_labels,
    point_df,
    bbox = cfg$standard_bbox,
    crs = cfg$standard_crs,
    output_width_px = unname(cfg$export_sizes$vector[["width"]])
  )
  point_df$fill_color <- ifelse(
    point_df$biobankType == "standaloneCollection",
    cfg$standard_colors$standalone,
    cfg$standard_colors$biobank
  )

  plot <- ggplot2::ggplot() +
    ggplot2::geom_sf(data = countries, ggplot2::aes(fill = fill_group), colour = "white", linewidth = 0.2) +
    ggplot2::geom_sf(data = states, colour = cfg$standard_colors$line, linewidth = 0.2, alpha = 0.25, linetype = "dashed") +
    ggplot2::geom_point(
      data = point_df,
      ggplot2::aes(x = x, y = y, fill = fill_color),
      shape = 21,
      size = 1.15,
      stroke = 0.4,
      colour = cfg$standard_colors$biobank_line,
      alpha = 0.8
    ) +
    ggplot2::scale_fill_identity() +
    bbmri_coord_sf(cfg$standard_bbox, cfg$standard_crs) +
    bbmri_void_theme(cfg$standard_colors$water)

  plot <- plot + bbmri_geom_text_halo(
    data = country_labels,
    mapping = ggplot2::aes(x = x, y = y, label = label),
    size = label_style$size,
    bbox = cfg$standard_bbox,
    crs = cfg$standard_crs,
    output_width_px = unname(cfg$export_sizes$vector[["width"]]),
    family = bbmri_font_family(),
    inner_halo_px = label_style$inner_halo_px,
    outer_halo_px = label_style$outer_halo_px,
    alpha = label_style$alpha
  )

  if (!is.null(iarc)) {
    iarc_df <- bbmri_biobank_points_df(iarc, cfg$standard_crs, label = "IARC points")
    plot <- plot +
      ggplot2::geom_point(
        data = iarc_df,
        ggplot2::aes(x = x, y = y),
        shape = 21,
        size = iarc_symbol$halo_size,
        stroke = 0,
        fill = "white",
        colour = "white"
      ) +
      ggplot2::geom_point(
        data = iarc_df,
        ggplot2::aes(x = x, y = y),
        shape = 21,
        size = iarc_symbol$observer_size,
        stroke = iarc_symbol$observer_stroke,
        fill = cfg$standard_colors$iarc,
        colour = "black"
      ) +
      ggplot2::geom_point(
        data = iarc_df,
        ggplot2::aes(x = x, y = y),
        shape = 21,
        size = iarc_symbol$biobank_size,
        stroke = iarc_symbol$biobank_stroke,
        fill = cfg$standard_colors$biobank,
        colour = cfg$standard_colors$biobank_line
      ) +
      bbmri_geom_text_halo(
        data = iarc_df,
        mapping = ggplot2::aes(x = x, y = y, label = "IARC"),
        size = label_style$size,
        bbox = cfg$standard_bbox,
        crs = cfg$standard_crs,
        output_width_px = unname(cfg$export_sizes$vector[["width"]]),
        family = bbmri_font_family(),
        inner_halo_px = label_style$inner_halo_px,
        outer_halo_px = label_style$outer_halo_px,
        alpha = label_style$alpha,
        hjust = iarc_label_placement$hjust,
        vjust = iarc_label_placement$vjust,
        nudge_x = iarc_label_placement$nudge_x,
        nudge_y = iarc_label_placement$nudge_y
      )
  } else {
    message("IARC overlay not provided; rendering without the IARC marker.")
  }

  plot
}

main <- function() {
  args <- bbmri_parse_args(list(
    input = normalizePath(file.path(script_dir, "..", "bbmri-directory.geojson"), winslash = "/", mustWork = FALSE),
    iarc = NA_character_,
    output_dir = file.path(script_dir, "output"),
    output_prefix = "bbmri-members-nolabels"
  ))

  plot <- build_members_nolabels_map(args$input, args$iarc)
  bbmri_save_plot_formats(plot, args$output_dir, args$output_prefix, bbmri_map_config()$export_sizes)
}

if (sys.nframe() == 0) {
  main()
}
