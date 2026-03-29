cmd_args <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", cmd_args, value = TRUE)
script_dir <- if (length(file_arg) == 0) {
  normalizePath(".", winslash = "/", mustWork = TRUE)
} else {
  normalizePath(dirname(sub("^--file=", "", file_arg[[1]])), winslash = "/", mustWork = TRUE)
}
source(file.path(script_dir, "map_config.R"))
source(file.path(script_dir, "map_common.R"))

bbmri_oec_hq_point <- function(node_df) {
  hq <- node_df[node_df$nodeType == "HQ", , drop = FALSE]
  if (nrow(hq) == 0) {
    stop("HQ point is missing from the OEC node overlay.", call. = FALSE)
  }
  hq[1, , drop = FALSE]
}

bbmri_shift_sf_points <- function(points, crs, dx = 0, dy = 0) {
  if (nrow(points) == 0) {
    return(points)
  }
  points_proj <- sf::st_transform(points, sf::st_crs(crs))
  coords <- sf::st_coordinates(points_proj)
  shifted <- sf::st_as_sf(
    data.frame(
      x = coords[, "X"] + dx,
      y = coords[, "Y"] + dy
    ),
    coords = c("x", "y"),
    crs = sf::st_crs(crs)
  )
  shifted
}

bbmri_oec_connector_source_point <- function(node_df, connector_cfg, inset_id) {
  source_type <- connector_cfg$source_node_type
  if (identical(source_type, "HQ")) {
    return(bbmri_oec_hq_point(node_df))
  }

  if (!is.null(connector_cfg$source_name) && !is.na(connector_cfg$source_name)) {
    source_node <- node_df[node_df$name == connector_cfg$source_name, , drop = FALSE]
    if (nrow(source_node) == 0) {
      stop(
        "Connector source '", connector_cfg$source_name, "' for OEC inset '", inset_id, "' was not found.",
        call. = FALSE
      )
    }
    return(source_node[1, , drop = FALSE])
  }

  stop(
    "Unsupported connector source configuration for OEC inset '", inset_id, "'.",
    call. = FALSE
  )
}

bbmri_oec_line_endpoint_npc <- function(node_lines, source_point, bbox, crs, endpoint = c("closest", "farthest"), fallback_target) {
  endpoint <- match.arg(endpoint)
  if (nrow(node_lines) == 0) {
    return(fallback_target)
  }

  bbox_poly <- sf::st_as_sfc(sf::st_bbox(
    c(
      xmin = bbox[["xmin"]],
      ymin = bbox[["ymin"]],
      xmax = bbox[["xmax"]],
      ymax = bbox[["ymax"]]
    ),
    crs = sf::st_crs(4326)
  ))
  bbox_proj <- sf::st_transform(bbox_poly, sf::st_crs(crs))
  node_lines_proj <- sf::st_transform(node_lines, sf::st_crs(crs))
  clipped <- suppressWarnings(sf::st_intersection(node_lines_proj, bbox_proj))
  if (nrow(clipped) == 0) {
    return(fallback_target)
  }

  geom_types <- as.character(sf::st_geometry_type(clipped))
  clipped_lines <- if (all(geom_types == "LINESTRING")) {
    clipped
  } else {
    sf::st_collection_extract(clipped, "LINESTRING")
  }
  if (nrow(clipped_lines) == 0) {
    return(fallback_target)
  }

  source_xy <- c(source_point$x[[1]], source_point$y[[1]])
  best <- NULL

  for (idx in seq_len(nrow(clipped_lines))) {
    coords <- sf::st_coordinates(clipped_lines[idx, ])
    if (nrow(coords) < 2) {
      next
    }

    endpoints <- rbind(coords[1, c("X", "Y")], coords[nrow(coords), c("X", "Y")])
    dists <- rowSums((endpoints - matrix(source_xy, nrow = 2, ncol = 2, byrow = TRUE))^2)
    boundary_xy <- endpoints[if (identical(endpoint, "closest")) which.min(dists) else which.max(dists), ]
    candidate <- bbmri_project_point_to_npc(boundary_xy[[1]], boundary_xy[[2]], bbox, crs)
    score <- if (identical(endpoint, "closest")) min(dists) else max(dists)

    if (is.null(best) || score < best$score) {
      best <- list(
        score = score,
        target = candidate
      )
    }
  }

  if (is.null(best)) {
    fallback_target
  } else {
    best$target
  }
}

bbmri_clamp_npc <- function(value) {
  pmin(pmax(value, 0), 1)
}

bbmri_oec_panel_spec <- function(plot) {
  built <- ggplot2::ggplot_build(plot)
  panel_params <- built$layout$panel_params[[1]]
  list(
    x_range = panel_params$x_range,
    y_range = panel_params$y_range
  )
}

bbmri_oec_projected_xy_to_npc <- function(projected_xy, panel_spec) {
  x_value <- unname(projected_xy[[1]])
  y_value <- unname(projected_xy[[2]])
  out <- c(
    (x_value - panel_spec$x_range[[1]]) /
      (panel_spec$x_range[[2]] - panel_spec$x_range[[1]]),
    (y_value - panel_spec$y_range[[1]]) /
      (panel_spec$y_range[[2]] - panel_spec$y_range[[1]])
  )
  names(out) <- c("x", "y")
  out
}

bbmri_oec_hq_anchor_npc <- function(plot) {
  built <- ggplot2::ggplot_build(plot)
  hq_layer_idx <- NULL
  hq_layer_size <- -Inf

  for (idx in seq_along(built$data)) {
    layer <- built$data[[idx]]
    if (!all(c("shape", "size", "geometry") %in% colnames(layer))) {
      next
    }
    if (nrow(layer) != 1) {
      next
    }
    if (!identical(layer$shape[[1]], 22)) {
      next
    }
    if (layer$size[[1]] > hq_layer_size) {
      hq_layer_idx <- idx
      hq_layer_size <- layer$size[[1]]
    }
  }

  if (is.null(hq_layer_idx)) {
    stop("Failed to resolve the rendered HQ point from the OEC plot.", call. = FALSE)
  }

  panel_spec <- bbmri_oec_panel_spec(plot)
  coords <- sf::st_coordinates(built$data[[hq_layer_idx]]$geometry)
  bbmri_oec_projected_xy_to_npc(
    c(x = coords[1, "X"], y = coords[1, "Y"]),
    panel_spec
  )
}

bbmri_plot_panel_viewport_name <- function(plot) {
  grob <- ggplot2::ggplotGrob(plot)
  panel <- grob$layout[grob$layout$name == "panel", , drop = FALSE]
  if (nrow(panel) == 0) {
    stop("Plot grob does not contain a panel.", call. = FALSE)
  }
  sprintf(
    "panel.%d-%d-%d-%d",
    panel$t[[1]],
    panel$l[[1]],
    panel$b[[1]],
    panel$r[[1]]
  )
}

bbmri_resolve_plot_page_npc <- function(plot, plot_box, inner_npc, device_width_in = 10, device_height_in = 10) {
  if (!all(is.finite(c(plot_box$x, plot_box$y, plot_box$width, plot_box$height)))) {
    stop("Plot box must contain finite coordinates.", call. = FALSE)
  }
  if (!all(is.finite(c(inner_npc[["x"]], inner_npc[["y"]])))) {
    stop("Inner NPC anchor must contain finite coordinates.", call. = FALSE)
  }

  panel_vp_name <- bbmri_plot_panel_viewport_name(plot)
  plot_grob <- ggplot2::ggplotGrob(plot)
  tmp_pdf <- tempfile(fileext = ".pdf")

  grDevices::pdf(tmp_pdf, width = device_width_in, height = device_height_in)
  on.exit({
    grDevices::dev.off()
    unlink(tmp_pdf)
  }, add = TRUE)

  grid::grid.newpage()
  grid::pushViewport(grid::viewport(
    x = grid::unit(plot_box$x, "npc"),
    y = grid::unit(plot_box$y, "npc"),
    width = grid::unit(plot_box$width, "npc"),
    height = grid::unit(plot_box$height, "npc"),
    just = c("left", "bottom"),
    name = "bbmri_plot_box"
  ))
  grid::grid.draw(plot_grob)
  grid::seekViewport(panel_vp_name)
  loc <- grid::deviceLoc(
    x = grid::unit(inner_npc[["x"]], "npc"),
    y = grid::unit(inner_npc[["y"]], "npc"),
    valueOnly = FALSE
  )
  dev_dims <- grDevices::dev.size("in")
  c(
    x = grid::convertX(loc$x, "in", valueOnly = TRUE) / dev_dims[[1]],
    y = grid::convertY(loc$y, "in", valueOnly = TRUE) / dev_dims[[2]]
  )
}


bbmri_oec_validate_inset_cfg <- function(inset_cfg, countries) {
  required_top <- c("id", "label", "mask_country_codes", "bbox", "placement", "connector", "frame")
  missing_top <- setdiff(required_top, names(inset_cfg))
  if (length(missing_top) > 0) {
    stop(
      "OEC inset configuration is missing fields: ",
      paste(missing_top, collapse = ", "),
      call. = FALSE
    )
  }

  bbmri_require_bbox(inset_cfg$bbox, paste0("OEC inset bbox '", inset_cfg$id, "'"))

  placement_required <- c("x", "y", "width", "height")
  placement_missing <- setdiff(placement_required, names(inset_cfg$placement))
  if (length(placement_missing) > 0) {
    stop(
      "OEC inset placement for '", inset_cfg$id, "' is missing fields: ",
      paste(placement_missing, collapse = ", "),
      call. = FALSE
    )
  }

  connector_required <- c("source_node_type", "target_x", "target_y", "linewidth")
  connector_missing <- setdiff(connector_required, names(inset_cfg$connector))
  if (length(connector_missing) > 0) {
    stop(
      "OEC inset connector for '", inset_cfg$id, "' is missing fields: ",
      paste(connector_missing, collapse = ", "),
      call. = FALSE
    )
  }

  frame_required <- c("border_colour", "border_linewidth", "background_fill")
  frame_missing <- setdiff(frame_required, names(inset_cfg$frame))
  if (length(frame_missing) > 0) {
    stop(
      "OEC inset frame for '", inset_cfg$id, "' is missing fields: ",
      paste(frame_missing, collapse = ", "),
      call. = FALSE
    )
  }

  placement_values <- unlist(inset_cfg$placement[placement_required], use.names = FALSE)
  if (!all(is.finite(placement_values))) {
    stop("OEC inset placement values for '", inset_cfg$id, "' must be finite.", call. = FALSE)
  }
  if (inset_cfg$placement$width <= 0 || inset_cfg$placement$height <= 0) {
    stop("OEC inset placement for '", inset_cfg$id, "' must have positive width and height.", call. = FALSE)
  }
  if (
    inset_cfg$placement$x < 0 ||
    inset_cfg$placement$y < 0 ||
    inset_cfg$placement$x + inset_cfg$placement$width > 1 ||
    inset_cfg$placement$y + inset_cfg$placement$height > 1
  ) {
    stop("OEC inset placement for '", inset_cfg$id, "' must stay within the canvas.", call. = FALSE)
  }

  if (!is.character(inset_cfg$connector$source_node_type) || length(inset_cfg$connector$source_node_type) != 1) {
    stop("OEC inset connector source_node_type for '", inset_cfg$id, "' must be a single string.", call. = FALSE)
  }
  numeric_connector_fields <- c("target_x", "target_y", "linewidth")
  numeric_connector_values <- unlist(inset_cfg$connector[numeric_connector_fields], use.names = FALSE)
  if (!all(is.finite(numeric_connector_values))) {
    stop("OEC inset numeric connector values for '", inset_cfg$id, "' must be finite.", call. = FALSE)
  }
  if (
    inset_cfg$connector$target_x < 0 ||
    inset_cfg$connector$target_x > 1 ||
    inset_cfg$connector$target_y < 0 ||
    inset_cfg$connector$target_y > 1
  ) {
    stop("OEC inset connector target for '", inset_cfg$id, "' must stay within the inset frame.", call. = FALSE)
  }

  missing_country_codes <- setdiff(inset_cfg$mask_country_codes, countries$iso_a2)
  if (length(missing_country_codes) > 0) {
    stop(
      "OEC inset '", inset_cfg$id, "' references unknown country codes: ",
      paste(missing_country_codes, collapse = ", "),
      call. = FALSE
    )
  }
}

bbmri_oec_resolve_insets <- function(cfg, countries, points, node_points, node_lines) {
  insets <- cfg$oec_insets
  if (length(insets) == 0) {
    return(list())
  }

  lapply(
    insets,
    function(inset_cfg) {
      bbmri_oec_validate_inset_cfg(inset_cfg, countries)
      inset_cfg$mask <- countries[countries$iso_a2 %in% inset_cfg$mask_country_codes, , drop = FALSE]
      if (nrow(inset_cfg$mask) == 0) {
        stop("OEC inset '", inset_cfg$id, "' resolved to an empty country mask.", call. = FALSE)
      }
      inset_cfg$countries <- bbmri_clip_to_bbox(
        bbmri_crop_to_bbox(countries, inset_cfg$bbox),
        inset_cfg$bbox
      )
      if (nrow(inset_cfg$countries) == 0) {
        stop("OEC inset '", inset_cfg$id, "' resolved to an empty cropped map area.", call. = FALSE)
      }
      inset_cfg$points <- bbmri_filter_sf_by_mask(points, inset_cfg$mask, include = TRUE)
      inset_cfg$node_points <- bbmri_filter_sf_by_mask(node_points, inset_cfg$mask, include = TRUE)
      inset_cfg$node_lines <- bbmri_filter_sf_by_mask(node_lines, inset_cfg$mask, include = TRUE)
      inset_cfg$node_lines <- bbmri_clip_to_bbox(inset_cfg$node_lines, inset_cfg$bbox)
      if (isTRUE(inset_cfg$require_node) && nrow(inset_cfg$node_points) == 0) {
        stop("OEC inset '", inset_cfg$id, "' has no node point in the overlay data.", call. = FALSE)
      }
      inset_cfg
    }
  )
}

bbmri_oec_panel_plot <- function(
  countries,
  point_sf,
  node_sf,
  node_lines,
  cfg,
  bbox,
  iarc_sf = NULL,
  draw_iarc_label = FALSE,
  frame = NULL,
  draw_node_lines = TRUE
) {
  iarc_symbol <- cfg$oec_iarc_symbol

  plot <- ggplot2::ggplot() +
    ggplot2::geom_sf(
      data = countries,
      ggplot2::aes(fill = fill_group),
      colour = cfg$oec_colors$country_line,
      linewidth = 0.45
    ) +
    ggplot2::scale_fill_identity() +
    bbmri_coord_sf(bbox, cfg$oec_crs) +
    bbmri_void_theme(cfg$oec_colors$background) +
    ggplot2::theme(plot.margin = ggplot2::margin(0, 0, 0, 0))

  if (isTRUE(draw_node_lines) && nrow(node_lines) > 0) {
    plot <- plot +
      ggplot2::geom_sf(
        data = node_lines,
        colour = "white",
        linewidth = 0.28
      ) +
      ggplot2::geom_sf(
        data = node_lines,
        colour = cfg$oec_colors$hq,
        linewidth = 0.12
      )
  }

  if (nrow(point_sf) > 0) {
    plot <- plot + ggplot2::geom_sf(
      data = point_sf,
      shape = 21,
      size = 1.1,
      stroke = 0.25,
      fill = cfg$oec_colors$biobank_fill,
      colour = cfg$oec_colors$biobank
    )
  }

  if (nrow(node_sf) > 0) {
    node_nn <- node_sf[node_sf$nodeType != "HQ", , drop = FALSE]
    node_hq <- node_sf[node_sf$nodeType == "HQ", , drop = FALSE]
    if (nrow(node_nn) > 0) {
      plot <- plot + ggplot2::geom_sf(
        data = node_nn,
        shape = 22,
        size = 2.5,
        stroke = 0.7,
        fill = cfg$oec_colors$hq,
        colour = "white"
      )
    }
    if (nrow(node_hq) > 0) {
      plot <- plot + ggplot2::geom_sf(
        data = node_hq,
        shape = 22,
        size = 3.2,
        stroke = 0.7,
        fill = cfg$oec_colors$hq,
        colour = "white"
      )
    }
  }

  if (!is.null(iarc_sf) && nrow(iarc_sf) > 0) {
    iarc_node_sf <- bbmri_shift_sf_points(iarc_sf, cfg$oec_crs, iarc_symbol$node_dx, iarc_symbol$node_dy)
    iarc_biobank_sf <- bbmri_shift_sf_points(iarc_sf, cfg$oec_crs, iarc_symbol$biobank_dx, iarc_symbol$biobank_dy)
    iarc_label_sf <- bbmri_shift_sf_points(iarc_sf, cfg$oec_crs, -32000, 32000)

    plot <- plot +
      ggplot2::geom_sf(
        data = iarc_sf,
        shape = 21,
        size = iarc_symbol$halo_size,
        stroke = 0,
        fill = "white",
        colour = "white"
      ) +
      ggplot2::geom_sf(
        data = iarc_sf,
        shape = 21,
        size = iarc_symbol$observer_size,
        stroke = iarc_symbol$observer_stroke,
        fill = cfg$oec_colors$observer,
        colour = "black"
      ) +
      ggplot2::geom_sf(
        data = iarc_node_sf,
        shape = 22,
        size = iarc_symbol$node_size,
        stroke = iarc_symbol$node_stroke,
        fill = cfg$oec_colors$hq,
        colour = "white"
      ) +
      ggplot2::geom_sf(
        data = iarc_biobank_sf,
        shape = 21,
        size = iarc_symbol$biobank_size,
        stroke = iarc_symbol$biobank_stroke,
        fill = cfg$oec_colors$biobank_fill,
        colour = cfg$oec_colors$biobank
      )

    if (isTRUE(draw_iarc_label)) {
      if (requireNamespace("shadowtext", quietly = TRUE)) {
        plot <- plot + shadowtext::geom_shadowtext(
          data = iarc_label_sf,
          ggplot2::aes(label = "IARC", geometry = geometry),
          stat = "sf_coordinates",
          size = 2.1,
          family = bbmri_font_family(),
          colour = "black",
          bg.colour = "white",
          bg.r = 0.12,
          hjust = 1,
          vjust = 0
        )
      } else {
        plot <- plot + ggplot2::geom_text(
          data = iarc_label_sf,
          ggplot2::aes(label = "IARC", geometry = geometry),
          stat = "sf_coordinates",
          size = 2.1,
          family = bbmri_font_family(),
          colour = "black",
          hjust = 1,
          vjust = 0
        )
      }
    }
  }

  if (!is.null(frame)) {
    plot <- plot + ggplot2::theme(
      panel.border = ggplot2::element_rect(
        fill = frame$background_fill,
        colour = frame$border_colour,
        linewidth = frame$border_linewidth
      ),
      plot.margin = ggplot2::margin(0, 0, 0, 0)
    )
  }

  plot
}

build_members_oec_all_map <- function(
  points_path,
  iarc_path,
  node_points_path,
  node_lines_path,
  device_width_in = 10,
  device_height_in = 10
) {
  bbmri_require_packages(c("ggplot2", "sf", "cowplot"))

  cfg <- bbmri_map_config()
  countries_all <- bbmri_assign_oec_country_fill(bbmri_load_countries(), cfg)
  points <- bbmri_read_sf(points_path, "Member biobank GeoJSON")
  iarc <- bbmri_read_sf(iarc_path, "IARC overlay")
  node_points <- bbmri_read_sf(node_points_path, "HQ/node overlay")
  node_lines <- bbmri_read_sf(node_lines_path, "HQ/node line overlay")

  points <- points[points$biobankID != "bbmri-eric:ID:EXT_NASBIO", ]
  resolved_insets <- bbmri_oec_resolve_insets(cfg, countries_all, points, node_points, node_lines)
  inset_country_codes <- unique(unlist(lapply(resolved_insets, function(inset_cfg) inset_cfg$mask_country_codes)))
  inset_mask <- countries_all[countries_all$iso_a2 %in% inset_country_codes, , drop = FALSE]

  visible_country_codes <- unique(c(
    cfg$oec_country_groups$member,
    cfg$oec_country_groups$observer,
    cfg$oec_country_groups$gray
  ))
  main_countries <- countries_all[
    countries_all$iso_a2 %in% visible_country_codes &
      !countries_all$iso_a2 %in% inset_country_codes,
    ,
    drop = FALSE
  ]
  main_countries <- bbmri_clip_to_bbox(main_countries, cfg$oec_bbox)
  main_points <- bbmri_filter_sf_by_mask(points, inset_mask, include = FALSE)
  main_node_points <- bbmri_filter_sf_by_mask(node_points, inset_mask, include = FALSE)
  main_node_lines <- bbmri_filter_sf_by_mask(node_lines, inset_mask, include = FALSE)
  main_node_lines <- bbmri_clip_to_bbox(main_node_lines, cfg$oec_bbox)
  main_point_sf <- bbmri_filter_valid_lonlat_points(main_points, "member biobank points")
  main_node_df <- bbmri_biobank_points_df(main_node_points, cfg$oec_crs, label = "HQ/node points")
  main_node_sf <- bbmri_filter_valid_lonlat_points(main_node_points, "HQ/node points")
  iarc_sf <- bbmri_filter_valid_lonlat_points(iarc, "IARC points")

  main_plot <- bbmri_oec_panel_plot(
    countries = main_countries,
    point_sf = main_point_sf,
    node_sf = main_node_sf,
    node_lines = main_node_lines,
    cfg = cfg,
    bbox = cfg$oec_bbox,
    iarc_sf = iarc_sf,
    draw_iarc_label = TRUE
  )

  main_panel <- cfg$oec_canvas
  main_plot_aspect <- {
    projected_bbox <- bbmri_projected_bbox(cfg$oec_bbox, cfg$oec_crs)
    (projected_bbox[["xmax"]] - projected_bbox[["xmin"]]) /
      (projected_bbox[["ymax"]] - projected_bbox[["ymin"]])
  }
  main_box <- bbmri_fit_box_to_aspect(
    x = main_panel$main_x,
    y = main_panel$main_y,
    width = main_panel$main_width,
    height = main_panel$main_height,
    aspect = main_plot_aspect
  )
  composed <- cowplot::ggdraw() + cowplot::draw_plot(
    main_plot,
    x = main_box$x,
    y = main_box$y,
    width = main_box$width,
    height = main_box$height
  )
  hq_overlay_npc <- bbmri_oec_hq_anchor_npc(main_plot)
  hq_overlay_xy <- bbmri_resolve_plot_page_npc(
    plot = main_plot,
    plot_box = main_box,
    inner_npc = hq_overlay_npc,
    device_width_in = device_width_in,
    device_height_in = device_height_in
  )

  for (inset_cfg in resolved_insets) {
    inset_node_df <- bbmri_biobank_points_df(
      inset_cfg$node_points,
      cfg$oec_crs,
      label = paste0(inset_cfg$id, " inset node points")
    )
    inset_point_sf <- bbmri_filter_valid_lonlat_points(
      inset_cfg$points,
      paste0(inset_cfg$id, " inset member biobank points")
    )
    inset_node_sf <- bbmri_filter_valid_lonlat_points(
      inset_cfg$node_points,
      paste0(inset_cfg$id, " inset node points")
    )
    inset_plot <- bbmri_oec_panel_plot(
      countries = inset_cfg$countries,
      point_sf = inset_point_sf,
      node_sf = inset_node_sf,
      node_lines = inset_cfg$node_lines,
      cfg = cfg,
      bbox = inset_cfg$bbox,
      iarc_sf = NULL,
      draw_iarc_label = FALSE,
      frame = inset_cfg$frame,
      draw_node_lines = FALSE
    )
    if (nrow(inset_cfg$node_points) > 0) {
      inset_label_sf <- bbmri_shift_sf_points(
        inset_cfg$node_points[1, , drop = FALSE],
        cfg$oec_crs,
        -55000,
        35000
      )
      inset_label_text <- toupper(inset_cfg$mask_country_codes[[1]])
      if (requireNamespace("shadowtext", quietly = TRUE)) {
        inset_plot <- inset_plot + shadowtext::geom_shadowtext(
          data = inset_label_sf,
          ggplot2::aes(label = inset_label_text, geometry = geometry),
          stat = "sf_coordinates",
          size = 2.0,
          family = bbmri_font_family(),
          colour = "black",
          bg.colour = "white",
          bg.r = 0.12,
          hjust = 1,
          vjust = 0
        )
      } else {
        inset_plot <- inset_plot + ggplot2::geom_text(
          data = inset_label_sf,
          ggplot2::aes(label = inset_label_text, geometry = geometry),
          stat = "sf_coordinates",
          size = 2.0,
          family = bbmri_font_family(),
          colour = "black",
          hjust = 1,
          vjust = 0
        )
      }
    }
    inset_plot_aspect <- {
      projected_bbox <- bbmri_projected_bbox(inset_cfg$bbox, cfg$oec_crs)
      (projected_bbox[["xmax"]] - projected_bbox[["xmin"]]) /
        (projected_bbox[["ymax"]] - projected_bbox[["ymin"]])
    }
    inset_box <- bbmri_fit_box_to_aspect(
      x = inset_cfg$placement$x,
      y = inset_cfg$placement$y,
      width = inset_cfg$placement$width,
      height = inset_cfg$placement$height,
      aspect = inset_plot_aspect
    )
    connector_npc <- if (identical(inset_cfg$connector$source_node_type, "HQ")) {
      hq_overlay_npc
    } else {
      connector_source <- bbmri_oec_connector_source_point(main_node_df, inset_cfg$connector, inset_cfg$id)
      bbmri_project_point_to_npc(
        connector_source$x[[1]],
        connector_source$y[[1]],
        cfg$oec_bbox,
        cfg$oec_crs
      )
    }
    connector_xy <- if (identical(inset_cfg$connector$source_node_type, "HQ")) {
      c(
        x = hq_overlay_xy[["x"]] + inset_cfg$connector$source_dx,
        y = hq_overlay_xy[["y"]] + inset_cfg$connector$source_dy
      )
    } else {
      c(
        x = main_box$x + main_box$width * connector_npc[["x"]] + inset_cfg$connector$source_dx,
        y = main_box$y + main_box$height * connector_npc[["y"]] + inset_cfg$connector$source_dy
      )
    }
    inset_target_npc <- if (nrow(inset_node_df) > 0) {
      bbmri_project_point_to_npc(
        inset_node_df$x[[1]],
        inset_node_df$y[[1]],
        inset_cfg$bbox,
        cfg$oec_crs
      )
    } else {
      c(
        x = inset_cfg$connector$target_x,
        y = inset_cfg$connector$target_y
      )
    }
    inset_xy <- c(
      x = inset_box$x + inset_box$width * inset_target_npc[["x"]],
      y = inset_box$y + inset_box$height * (inset_target_npc[["y"]] - 0.045)
    )
    connector_x <- bbmri_clamp_npc(connector_xy[["x"]])
    connector_y <- bbmri_clamp_npc(connector_xy[["y"]])
    inset_end_x <- bbmri_clamp_npc(inset_xy[["x"]])
    inset_end_y <- bbmri_clamp_npc(inset_xy[["y"]])
    composed <- composed +
      cowplot::draw_plot(
        inset_plot,
        x = inset_box$x,
        y = inset_box$y,
        width = inset_box$width,
        height = inset_box$height
      ) +
      cowplot::draw_line(
        x = c(connector_x, inset_end_x),
        y = c(connector_y, inset_end_y),
        colour = "white",
        linewidth = inset_cfg$connector$linewidth + 0.16
      ) +
      cowplot::draw_line(
        x = c(connector_x, inset_end_x),
        y = c(connector_y, inset_end_y),
        colour = cfg$oec_colors$hq,
        linewidth = inset_cfg$connector$linewidth
      )
  }

  if (nrow(main_node_sf[main_node_sf$nodeType == "HQ", , drop = FALSE]) > 0) {
    composed <- composed + ggplot2::annotate(
      "point",
      x = hq_overlay_xy[["x"]],
      y = hq_overlay_xy[["y"]],
      shape = 22,
      size = 3.2,
      stroke = 0.7,
      fill = cfg$oec_colors$hq,
      colour = "white"
    )
  }

  composed
}

bbmri_save_members_oec_all_formats <- function(args, export_sizes) {
  dir.create(args$output_dir, recursive = TRUE, showWarnings = FALSE)
  raster_sizes <- export_sizes$png
  raster_dpi <- 300

  for (name in names(raster_sizes)) {
    size <- raster_sizes[[name]]
    width_in <- unname(size[["width"]]) / raster_dpi
    height_in <- unname(size[["height"]]) / raster_dpi
    plot <- build_members_oec_all_map(
      points_path = args$input,
      iarc_path = args$iarc,
      node_points_path = args$node_points,
      node_lines_path = args$node_lines,
      device_width_in = width_in,
      device_height_in = height_in
    )

    ggplot2::ggsave(
      filename = file.path(args$output_dir, paste0(args$output_prefix, "-", name, ".png")),
      plot = plot,
      width = unname(size[["width"]]),
      height = unname(size[["height"]]),
      units = "px",
      bg = "white",
      limitsize = FALSE
    )
    ggplot2::ggsave(
      filename = file.path(args$output_dir, paste0(args$output_prefix, "-", name, ".pdf")),
      plot = plot,
      width = width_in,
      height = height_in,
      units = "in",
      bg = "white",
      limitsize = FALSE
    )
  }

  vector_size <- export_sizes$vector
  vector_width_in <- unname(vector_size[["width"]]) / raster_dpi
  vector_height_in <- unname(vector_size[["height"]]) / raster_dpi
  vector_plot <- build_members_oec_all_map(
    points_path = args$input,
    iarc_path = args$iarc,
    node_points_path = args$node_points,
    node_lines_path = args$node_lines,
    device_width_in = vector_width_in,
    device_height_in = vector_height_in
  )

  ggplot2::ggsave(
    filename = file.path(args$output_dir, paste0(args$output_prefix, ".pdf")),
    plot = vector_plot,
    width = vector_width_in,
    height = vector_height_in,
    units = "in",
    bg = "white",
    limitsize = FALSE
  )

  if (requireNamespace("svglite", quietly = TRUE)) {
    ggplot2::ggsave(
      filename = file.path(args$output_dir, paste0(args$output_prefix, ".svg")),
      plot = vector_plot,
      width = vector_width_in,
      height = vector_height_in,
      units = "in",
      bg = "white",
      device = svglite::svglite,
      limitsize = FALSE
    )
  } else {
    message("Skipping SVG export because package 'svglite' is not installed.")
  }
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

  bbmri_save_members_oec_all_formats(
    args = args,
    export_sizes = bbmri_map_config()$export_sizes
  )
}

if (sys.nframe() == 0) {
  main()
}
