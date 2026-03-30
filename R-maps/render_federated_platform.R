cmd_args <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", cmd_args, value = TRUE)
script_dir <- if (length(file_arg) == 0) {
  normalizePath(".", winslash = "/", mustWork = TRUE)
} else {
  normalizePath(dirname(sub("^--file=", "", file_arg[[1]])), winslash = "/", mustWork = TRUE)
}
source(file.path(script_dir, "map_config.R"))
source(file.path(script_dir, "map_common.R"))

build_federated_platform_map <- function(points_path, iarc_path = NA_character_, output_variant = "med") {
  bbmri_require_packages(c("ggplot2", "sf"))

  cfg <- bbmri_map_config()
  bbox <- cfg$classic_europe_bbox
  export_sizes <- cfg$export_sizes
  country_label_style <- bbmri_country_label_style_for_output(cfg, output_variant)
  output_width_px <- bbmri_output_width_px(export_sizes, output_variant)
  layers <- bbmri_prepare_classic_layers(bbox, cfg, fill_fn = bbmri_assign_fedplat_country_fill)
  points <- bbmri_read_sf(points_path, "Federated-platform GeoJSON")
  bbmri_validate_geojson_columns(
    points,
    c("biobankType", "biobankLabel"),
    "Federated-platform GeoJSON"
  )
  iarc <- bbmri_read_optional_sf(iarc_path)

  point_df <- bbmri_biobank_points_df(points, cfg$standard_crs, label = "federated-platform points")
  point_df$fill_color <- ifelse(
    point_df$biobankType == "FinderBiobank",
    cfg$fedplat_colors$finder,
    cfg$fedplat_colors$locator
  )
  point_df$marker_width <- bbmri_mapnik_marker_size(10, cfg)
  point_df <- bbmri_place_local_labels(
    point_df,
    bbox = bbox,
    crs = cfg$standard_crs,
    output_width_px = output_width_px,
    label_column = "biobankLabel"
  )
  country_labels <- bbmri_country_label_df(
    layers$countries,
    cfg,
    cfg$standard_crs,
    label_codes = cfg$fedplat_country_labels,
    label_offsets = cfg$fedplat_label_offsets
  )
  country_labels <- bbmri_place_country_labels(
    country_labels,
    point_df,
    bbox = bbox,
    crs = cfg$standard_crs,
    output_width_px = output_width_px,
    label_size_scale = country_label_style$size / cfg$standard_label_style$size,
    layout_variant = if (identical(output_variant, "small")) "small" else "default"
  )

  plot <- bbmri_add_classic_base(
    ggplot2::ggplot(),
    layers = layers,
    bbox = bbox,
    crs = cfg$standard_crs,
    cfg = cfg
  ) +
    ggplot2::geom_point(
      data = point_df,
      ggplot2::aes(x = x, y = y, fill = fill_color, size = marker_width),
      shape = 21,
      stroke = 0.4,
      colour = cfg$fedplat_colors$point_line,
      alpha = 0.8
    ) +
    ggplot2::scale_fill_identity() +
    ggplot2::scale_size_identity() +
    ggplot2::geom_text(
      data = point_df,
      mapping = ggplot2::aes(
        x = label_x,
        y = label_y,
        label = biobankLabel,
        hjust = label_hjust,
        vjust = label_vjust
      ),
      size = cfg$fedplat_label_style$size,
      family = bbmri_font_family(),
      colour = cfg$fedplat_label_style$colour,
      alpha = cfg$fedplat_label_style$alpha
    ) +
    bbmri_geom_text_halo(
      data = country_labels,
      mapping = ggplot2::aes(x = x, y = y, label = label),
      size = country_label_style$size,
      bbox = bbox,
      crs = cfg$standard_crs,
      output_width_px = output_width_px,
      family = bbmri_font_family(),
      inner_halo_px = country_label_style$inner_halo_px,
      outer_halo_px = country_label_style$outer_halo_px,
      alpha = country_label_style$alpha
    )

  if (!is.null(iarc)) {
    iarc_df <- bbmri_biobank_points_df(iarc, cfg$standard_crs, label = "IARC points")
    plot <- plot +
      ggplot2::geom_point(
        data = iarc_df,
        ggplot2::aes(x = x, y = y),
        shape = 21,
        size = cfg$standard_iarc_symbol$observer_size,
        stroke = cfg$standard_iarc_symbol$observer_stroke,
        fill = cfg$standard_colors$iarc,
        colour = cfg$fedplat_colors$point_line
      )
  }

  plot
}

save_federated_platform_formats <- function(points_path, iarc_path, output_dir, prefix) {
  cfg <- bbmri_map_config()
  bbmri_save_plot_formats_from_builder(
    build_plot = function(output_variant) {
      build_federated_platform_map(points_path, iarc_path, output_variant = output_variant)
    },
    output_dir = output_dir,
    prefix = prefix,
    export_sizes = cfg$export_sizes
  )
}

main <- function() {
  args <- bbmri_parse_args(list(
    input = normalizePath(file.path(script_dir, "data", "federated-platform.geojson"), winslash = "/", mustWork = FALSE),
    iarc = NA_character_,
    output_dir = file.path(script_dir, "output"),
    output_prefix = "federated-platform"
  ))

  save_federated_platform_formats(args$input, args$iarc, args$output_dir, args$output_prefix)
}

if (sys.nframe() == 0) {
  main()
}
