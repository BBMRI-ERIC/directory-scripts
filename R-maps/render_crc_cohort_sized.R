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

build_crc_cohort_sized_map <- function(points_path, imaging_path, iarc_path = NA_character_, output_variant = "med") {
  bbmri_require_packages(c("ggplot2", "sf"))

  cfg <- bbmri_map_config()
  bbox <- cfg$classic_europe_bbox
  export_sizes <- cfg$export_sizes
  label_style <- bbmri_country_label_style_for_output(cfg, output_variant)
  symbol_scale <- bbmri_symbol_scale_for_output(cfg, output_variant)
  line_scale <- bbmri_line_scale_for_output(cfg, output_variant)
  output_width_px <- bbmri_output_width_px(export_sizes, output_variant)
  layers <- bbmri_prepare_classic_layers(
    bbox,
    cfg,
    fill_fn = bbmri_assign_standard_country_fill,
    include_rivers = FALSE
  )
  points <- bbmri_read_sf(points_path, "CRC cohort GeoJSON")
  bbmri_validate_geojson_columns(
    points,
    c("biobankID", "biobankName", "biobankType", "contribSize"),
    "CRC cohort GeoJSON"
  )
  imaging <- bbmri_read_sf(imaging_path, "CRC imaging GeoJSON")
  bbmri_validate_geojson_columns(
    imaging,
    c("biobankID", "biobankName", "biobankType", "contribSize"),
    "CRC imaging GeoJSON"
  )
  iarc <- bbmri_read_optional_sf(iarc_path)

  point_df <- bbmri_biobank_points_df(points, cfg$standard_crs, label = "CRC cohort points")
  imaging_df <- bbmri_biobank_points_df(imaging, cfg$standard_crs, label = "CRC imaging points")
  point_df$fill_color <- ifelse(
    point_df$biobankType == "standaloneCollection",
    cfg$crc_colors$standalone,
    cfg$crc_colors$cohort
  )
  point_df$marker_width_mapnik <- ifelse(
    point_df$contribSize < 50,
    cfg$crc_marker_style$cohort_min_width,
    cfg$crc_marker_style$cohort_high_base + point_df$contribSize * cfg$crc_marker_style$cohort_high_slope
  )
  point_df$marker_width <- bbmri_mapnik_marker_size(point_df$marker_width_mapnik, cfg) * symbol_scale
  imaging_df$marker_width <- bbmri_mapnik_marker_size(cfg$crc_marker_style$imaging_width, cfg) * symbol_scale
  country_labels <- bbmri_country_label_df(layers$countries, cfg, cfg$standard_crs)
  country_anchor_df <- rbind(
    point_df[, c("x", "y")],
    imaging_df[, c("x", "y")]
  )
  country_labels <- bbmri_place_country_labels(
    country_labels,
    country_anchor_df,
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
  ) +
    ggplot2::geom_point(
      data = point_df,
      ggplot2::aes(x = x, y = y, size = marker_width, fill = fill_color),
      shape = 21,
      stroke = 0.4 * line_scale,
      colour = cfg$crc_colors$cohort_line,
      alpha = cfg$crc_marker_style$main_alpha
    ) +
    ggplot2::geom_point(
      data = imaging_df,
      ggplot2::aes(x = x, y = y, size = marker_width),
      shape = 21,
      stroke = 0.4 * line_scale,
      colour = cfg$crc_colors$cohort_line,
      fill = cfg$crc_colors$imaging,
      alpha = cfg$crc_marker_style$imaging_alpha
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
      output_width_px = output_width_px,
      output_variant = output_variant
    )
  }

  plot
}

save_crc_cohort_sized_formats <- function(points_path, imaging_path, iarc_path, output_dir, prefix) {
  cfg <- bbmri_map_config()
  bbmri_save_plot_formats_from_builder(
    build_plot = function(output_variant) {
      build_crc_cohort_sized_map(points_path, imaging_path, iarc_path, output_variant = output_variant)
    },
    output_dir = output_dir,
    prefix = prefix,
    export_sizes = cfg$crc_export_sizes
  )
}

main <- function() {
  args <- bbmri_parse_args(list(
    input = normalizePath(file.path(script_dir, "data", "CRC-Cohort.geojson"), winslash = "/", mustWork = FALSE),
    imaging = normalizePath(file.path(script_dir, "data", "CRC-Cohort-imaging.geojson"), winslash = "/", mustWork = FALSE),
    iarc = NA_character_,
    output_dir = file.path(script_dir, "output"),
    output_prefix = "CRC-cohort-sized"
  ))

  save_crc_cohort_sized_formats(args$input, args$imaging, args$iarc, args$output_dir, args$output_prefix)
}

if (sys.nframe() == 0) {
  main()
}
