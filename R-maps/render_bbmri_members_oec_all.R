cmd_args <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", cmd_args, value = TRUE)
script_dir <- if (length(file_arg) == 0) {
  normalizePath(".", winslash = "/", mustWork = TRUE)
} else {
  normalizePath(dirname(sub("^--file=", "", file_arg[[1]])), winslash = "/", mustWork = TRUE)
}
source(file.path(script_dir, "map_config.R"))
source(file.path(script_dir, "map_common.R"))

build_members_oec_all_map <- function(points_path, iarc_path, node_points_path, node_lines_path) {
  bbmri_require_packages(c("ggplot2", "sf"))

  cfg <- bbmri_map_config()
  iarc_symbol <- cfg$oec_iarc_symbol
  countries <- bbmri_crop_to_bbox(
    bbmri_assign_oec_country_fill(bbmri_load_countries(), cfg),
    cfg$oec_bbox
  )
  points <- bbmri_read_sf(points_path, "Member biobank GeoJSON")
  iarc <- bbmri_read_sf(iarc_path, "IARC overlay")
  node_points <- bbmri_read_sf(node_points_path, "HQ/node overlay")
  node_lines <- bbmri_read_sf(node_lines_path, "HQ/node line overlay")

  points <- points[points$biobankID != "bbmri-eric:ID:EXT_NASBIO", ]
  point_df <- bbmri_biobank_points_df(points, cfg$oec_crs, label = "member biobank points")
  iarc_df <- bbmri_biobank_points_df(iarc, cfg$oec_crs, label = "IARC points")
  iarc_node_df <- iarc_df
  iarc_node_df$x <- iarc_node_df$x + iarc_symbol$node_dx
  iarc_node_df$y <- iarc_node_df$y + iarc_symbol$node_dy
  iarc_biobank_df <- iarc_df
  iarc_biobank_df$x <- iarc_biobank_df$x + iarc_symbol$biobank_dx
  iarc_biobank_df$y <- iarc_biobank_df$y + iarc_symbol$biobank_dy
  node_df <- bbmri_biobank_points_df(node_points, cfg$oec_crs, label = "HQ/node points")

  plot <- ggplot2::ggplot() +
    ggplot2::geom_sf(data = countries, ggplot2::aes(fill = fill_group), colour = "white", linewidth = 0.4) +
    ggplot2::geom_sf(data = node_lines, colour = cfg$oec_colors$hq, linewidth = 0.12) +
    ggplot2::geom_point(
      data = point_df,
      ggplot2::aes(x = x, y = y),
      shape = 21,
      size = 1.1,
      stroke = 0.25,
      fill = cfg$oec_colors$biobank_fill,
      colour = cfg$oec_colors$biobank
    ) +
    ggplot2::geom_point(
      data = node_df,
      ggplot2::aes(x = x, y = y),
      shape = 22,
      size = ifelse(node_df$nodeType == "HQ", 3.2, 2.5),
      stroke = 0.7,
      fill = cfg$oec_colors$hq,
      colour = "white"
    ) +
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
      fill = cfg$oec_colors$observer,
      colour = "black"
    ) +
    ggplot2::geom_point(
      data = iarc_node_df,
      ggplot2::aes(x = x, y = y),
      shape = 22,
      size = iarc_symbol$node_size,
      stroke = iarc_symbol$node_stroke,
      fill = cfg$oec_colors$hq,
      colour = "white"
    ) +
    ggplot2::geom_point(
      data = iarc_biobank_df,
      ggplot2::aes(x = x, y = y),
      shape = 21,
      size = iarc_symbol$biobank_size,
      stroke = iarc_symbol$biobank_stroke,
      fill = cfg$oec_colors$biobank_fill,
      colour = cfg$oec_colors$biobank
    ) +
    ggplot2::scale_fill_identity() +
    bbmri_coord_sf(cfg$oec_bbox, cfg$oec_crs) +
    bbmri_void_theme(cfg$oec_colors$background)

  plot <- plot + bbmri_geom_text_halo(
    data = iarc_df,
    mapping = ggplot2::aes(x = x, y = y, label = "IARC"),
    size = 2.1,
    bbox = cfg$oec_bbox,
    crs = cfg$oec_crs,
    output_width_px = unname(cfg$export_sizes$vector[["width"]]),
    family = bbmri_font_family(),
    inner_halo_px = 1.0,
    outer_halo_px = 3.0,
    hjust = 1,
    vjust = 0,
    nudge_x = -32000,
    nudge_y = 32000
  )

  plot
}

main <- function() {
  args <- bbmri_parse_args(list(
    input = normalizePath(file.path(script_dir, "..", "bbmri-directory-members.geojson"), winslash = "/", mustWork = FALSE),
    iarc = NA_character_,
    node_points = NA_character_,
    node_lines = NA_character_,
    output_dir = file.path(script_dir, "output"),
    output_prefix = "bbmri-members-OEC-all"
  ))

  required <- c(args$iarc, args$node_points, args$node_lines)
  if (any(is.na(required) | required == "")) {
    stop(
      paste(
        "The OEC map requires explicit overlay inputs:",
        "--iarc=...",
        "--node-points=...",
        "--node-lines=..."
      ),
      call. = FALSE
    )
  }

  plot <- build_members_oec_all_map(
    points_path = args$input,
    iarc_path = args$iarc,
    node_points_path = args$node_points,
    node_lines_path = args$node_lines
  )
  bbmri_save_plot_formats(plot, args$output_dir, args$output_prefix, bbmri_map_config()$export_sizes)
}

if (sys.nframe() == 0) {
  main()
}
