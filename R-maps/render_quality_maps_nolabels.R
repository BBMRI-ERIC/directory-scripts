cmd_args <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", cmd_args, value = TRUE)
script_dir <- if (length(file_arg) == 0) {
  normalizePath(".", winslash = "/", mustWork = TRUE)
} else {
  normalizePath(dirname(sub("^--file=", "", file_arg[[1]])), winslash = "/", mustWork = TRUE)
}
source(file.path(script_dir, "map_config.R"))
source(file.path(script_dir, "map_common.R"))

build_quality_maps_nolabels_map <- function(points_path, iarc_path = NA_character_, output_variant = "med") {
  bbmri_require_packages(c("ggplot2", "sf"))

  cfg <- bbmri_map_config()
  bbox <- cfg$classic_europe_bbox
  export_sizes <- cfg$export_sizes
  label_style <- bbmri_country_label_style_for_output(cfg, output_variant)
  output_width_px <- bbmri_output_width_px(export_sizes, output_variant)
  layers <- bbmri_prepare_classic_layers(bbox, cfg, fill_fn = bbmri_assign_standard_country_fill)
  points <- bbmri_read_sf(points_path, "Quality map GeoJSON")
  bbmri_validate_geojson_columns(
    points,
    c("biobankID", "biobankName", "biobankType", "qual_id"),
    "Quality map GeoJSON"
  )
  iarc <- bbmri_read_optional_sf(iarc_path)

  point_df <- bbmri_biobank_points_df(points, cfg$standard_crs, label = "quality map points")
  point_df$qual_id[is.na(point_df$qual_id)] <- "Other"
  point_df$fill_color <- ifelse(
    point_df$qual_id == "eric",
    cfg$quality_colors$eric,
    ifelse(
      point_df$qual_id == "accredited",
      cfg$quality_colors$accredited,
      cfg$quality_colors$other
    )
  )
  point_df$line_color <- point_df$fill_color
  point_df$marker_width <- ifelse(
    point_df$biobankType == "biobank",
    bbmri_mapnik_marker_size(cfg$quality_marker_style$biobank_width, cfg),
    bbmri_mapnik_marker_size(cfg$quality_marker_style$collection_width, cfg)
  )
  point_df$marker_alpha <- ifelse(
    point_df$biobankType == "biobank",
    cfg$quality_marker_style$alpha_biobank,
    cfg$quality_marker_style$alpha_collection
  )
  country_labels <- bbmri_country_label_df(layers$countries, cfg, cfg$standard_crs)
  country_labels <- bbmri_place_country_labels(
    country_labels,
    point_df,
    bbox = bbox,
    crs = cfg$standard_crs,
    output_width_px = output_width_px,
    label_size_scale = label_style$size / cfg$standard_label_style$size,
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
      data = subset(point_df, biobankType == "biobank"),
      ggplot2::aes(x = x, y = y, size = marker_width, fill = fill_color),
      shape = 21,
      stroke = 0.4,
      colour = cfg$quality_colors$line,
      alpha = cfg$quality_marker_style$alpha_biobank
    ) +
    ggplot2::geom_point(
      data = subset(point_df, biobankType != "biobank"),
      ggplot2::aes(x = x, y = y, size = marker_width, fill = fill_color),
      shape = 21,
      stroke = 0.35,
      colour = cfg$quality_colors$line,
      alpha = cfg$quality_marker_style$alpha_collection
    ) +
    ggplot2::scale_fill_identity() +
    ggplot2::scale_size_identity()

  plot <- plot + bbmri_geom_text_halo(
    data = country_labels,
    mapping = ggplot2::aes(x = x, y = y, label = label),
    size = label_style$size,
    bbox = bbox,
    crs = cfg$standard_crs,
    output_width_px = output_width_px,
    family = bbmri_font_family(),
    inner_halo_px = label_style$inner_halo_px,
    outer_halo_px = label_style$outer_halo_px,
    alpha = label_style$alpha
  )

  if (!is.null(iarc)) {
    iarc_df <- bbmri_biobank_points_df(iarc, cfg$standard_crs, label = "IARC points")
    plot <- bbmri_add_standard_iarc(
      plot = plot,
      iarc_df = iarc_df,
      cfg = cfg,
      bbox = bbox,
      crs = cfg$standard_crs,
      output_width_px = output_width_px
    )
  }

  plot
}

save_quality_maps_nolabels_formats <- function(points_path, iarc_path, output_dir, prefix) {
  cfg <- bbmri_map_config()
  bbmri_save_plot_formats_from_builder(
    build_plot = function(output_variant) {
      build_quality_maps_nolabels_map(points_path, iarc_path, output_variant = output_variant)
    },
    output_dir = output_dir,
    prefix = prefix,
    export_sizes = cfg$export_sizes
  )
}

main <- function() {
  args <- bbmri_parse_args(list(
    input = normalizePath(file.path(script_dir, "..", "bbmri-directory-quality.geojson"), winslash = "/", mustWork = FALSE),
    iarc = NA_character_,
    output_dir = file.path(script_dir, "output"),
    output_prefix = "quality_maps-nolabels"
  ))

  save_quality_maps_nolabels_formats(args$input, args$iarc, args$output_dir, args$output_prefix)
}

if (sys.nframe() == 0) {
  main()
}
