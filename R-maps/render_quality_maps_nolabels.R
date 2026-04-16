bbmri_detect_rmaps_dir <- function() {
  cmd_args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", cmd_args, value = TRUE)
  if (length(file_arg) > 0) {
    return(normalizePath(dirname(sub("^--file=", "", file_arg[[1]])), winslash = "/", mustWork = TRUE))
  }
  candidates <- c(
    normalizePath(".", winslash = "/", mustWork = TRUE),
    normalizePath(file.path(".", "R-maps"), winslash = "/", mustWork = FALSE)
  )
  for (candidate in unique(candidates)) {
    if (file.exists(file.path(candidate, "map_config.R")) && file.exists(file.path(candidate, "map_common.R"))) {
      return(candidate)
    }
  }
  stop("Unable to locate the R-maps directory.", call. = FALSE)
}

script_dir <- bbmri_detect_rmaps_dir()
source(file.path(script_dir, "map_config.R"))
source(file.path(script_dir, "map_common.R"))

build_quality_maps_nolabels_map <- function(points_path, iarc_path = NA_character_, output_variant = "med") {
  bbmri_require_packages(c("ggplot2", "sf"))

  cfg <- bbmri_map_config()
  bbox <- cfg$standard_bbox
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
  point_df <- bbmri_assign_quality_point_style(point_df, cfg)
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
    cfg = cfg,
    output_variant = output_variant
  )
  plot <- bbmri_add_quality_point_layers(plot, point_df, cfg, output_variant = output_variant)
  plot <- bbmri_add_quality_legend(plot, bbox, cfg$standard_crs, cfg, output_variant = output_variant)

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
      output_width_px = output_width_px,
      output_variant = output_variant
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
