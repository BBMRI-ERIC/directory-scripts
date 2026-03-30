cmd_args <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", cmd_args, value = TRUE)
script_dir <- if (length(file_arg) == 0) {
  normalizePath(".", winslash = "/", mustWork = TRUE)
} else {
  normalizePath(dirname(sub("^--file=", "", file_arg[[1]])), winslash = "/", mustWork = TRUE)
}
source(file.path(script_dir, "map_config.R"))
source(file.path(script_dir, "map_common.R"))

build_members_nolabels_map <- function(points_path, iarc_path = NA_character_, output_variant = "med") {
  bbmri_require_packages(c("ggplot2", "sf"))

  cfg <- bbmri_map_config()
  label_style <- bbmri_country_label_style_for_output(cfg, output_variant)
  iarc_symbol <- cfg$standard_iarc_symbol
  iarc_label_placement <- cfg$standard_iarc_label_placement
  output_width_px <- bbmri_output_width_px(cfg$export_sizes, output_variant)
  countries <- bbmri_crop_to_bbox(
    bbmri_assign_standard_country_fill(bbmri_load_countries(), cfg),
    cfg$standard_bbox
  )
  states <- bbmri_crop_to_bbox(bbmri_load_states(), cfg$standard_bbox)
  points <- bbmri_read_sf(points_path, "Biobank GeoJSON")
  iarc <- bbmri_read_optional_sf(iarc_path)

  country_labels <- bbmri_country_label_df(countries, cfg, cfg$standard_crs)
  point_df <- bbmri_biobank_points_df(points, cfg$standard_crs, label = "biobank points")
  obstacle_df <- point_df[, c("x", "y")]
  if (identical(output_variant, "small")) {
    country_labels <- bbmri_apply_label_offsets(country_labels, cfg$standard_small_label_offsets)
  }
  if (!is.null(iarc)) {
    iarc_df <- bbmri_biobank_points_df(iarc, cfg$standard_crs, label = "IARC points")
    obstacle_df <- rbind(obstacle_df, iarc_df[, c("x", "y")])
  } else {
    iarc_df <- NULL
  }
  country_labels <- bbmri_place_country_labels(
    country_labels,
    obstacle_df,
    bbox = cfg$standard_bbox,
    crs = cfg$standard_crs,
    output_width_px = output_width_px,
    label_size_scale = label_style$size / cfg$standard_label_style$size,
    layout_variant = if (identical(output_variant, "small")) "small" else "default"
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
    output_width_px = output_width_px,
    family = bbmri_font_family(),
    inner_halo_px = label_style$inner_halo_px,
    outer_halo_px = label_style$outer_halo_px,
    alpha = label_style$alpha
  )

  if (!is.null(iarc_df)) {
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
        output_width_px = output_width_px,
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

save_members_nolabels_formats <- function(points_path, iarc_path, output_dir, prefix) {
  cfg <- bbmri_map_config()
  bbmri_save_plot_formats_from_builder(
    build_plot = function(output_variant) {
      build_members_nolabels_map(points_path, iarc_path, output_variant = output_variant)
    },
    output_dir = output_dir,
    prefix = prefix,
    export_sizes = cfg$export_sizes
  )
}

main <- function() {
  args <- bbmri_parse_args(list(
    input = normalizePath(file.path(script_dir, "..", "bbmri-directory.geojson"), winslash = "/", mustWork = FALSE),
    iarc = NA_character_,
    output_dir = file.path(script_dir, "output"),
    output_prefix = "bbmri-members-nolabels"
  ))

  save_members_nolabels_formats(args$input, args$iarc, args$output_dir, args$output_prefix)
}

if (sys.nframe() == 0) {
  main()
}
