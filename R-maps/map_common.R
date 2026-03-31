bbmri_script_dir <- function() {
  if (exists("script_dir", inherits = TRUE)) {
    return(get("script_dir", inherits = TRUE))
  }
  cmd_args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", cmd_args, value = TRUE)
  if (length(file_arg) == 0) {
    return(normalizePath(".", winslash = "/", mustWork = TRUE))
  }
  normalizePath(dirname(sub("^--file=", "", file_arg[[1]])), winslash = "/", mustWork = TRUE)
}

bbmri_enable_local_r_lib <- function() {
  local_lib <- file.path(bbmri_script_dir(), "r-lib")
  if (!dir.exists(local_lib)) {
    return(invisible(FALSE))
  }
  .libPaths(c(normalizePath(local_lib, winslash = "/", mustWork = TRUE), .libPaths()))
  invisible(TRUE)
}

bbmri_enable_local_r_lib()

bbmri_require_packages <- function(packages) {
  missing <- packages[!vapply(packages, requireNamespace, logical(1), quietly = TRUE)]
  if (length(missing) > 0) {
    stop(
      "Missing R packages: ",
      paste(missing, collapse = ", "),
      ". Install them before running the map scripts.",
      call. = FALSE
    )
  }
}

bbmri_parse_args <- function(defaults) {
  args <- defaults
  trailing <- commandArgs(trailingOnly = TRUE)
  if (length(trailing) == 0) {
    return(args)
  }

  for (arg in trailing) {
    if (!startsWith(arg, "--")) {
      stop("Unsupported argument format: ", arg, call. = FALSE)
    }
    parts <- strsplit(sub("^--", "", arg), "=", fixed = TRUE)[[1]]
    key <- gsub("-", "_", parts[[1]], fixed = TRUE)
    value <- if (length(parts) > 1) parts[[2]] else TRUE
    args[[key]] <- value
  }

  args
}

bbmri_read_sf <- function(path, label) {
  if (!file.exists(path)) {
    stop(label, " not found: ", path, call. = FALSE)
  }
  sf::st_read(path, quiet = TRUE)
}

bbmri_read_optional_sf <- function(path) {
  if (is.null(path) || is.na(path) || identical(path, "")) {
    return(NULL)
  }
  if (!file.exists(path)) {
    return(NULL)
  }
  sf::st_read(path, quiet = TRUE)
}

bbmri_map_cache_dir <- function() {
  dir <- file.path(bbmri_script_dir(), "cache", "natural-earth")
  dir.create(dir, recursive = TRUE, showWarnings = FALSE)
  dir
}

bbmri_cached_download <- function(url, filename) {
  dest <- file.path(bbmri_map_cache_dir(), filename)
  if (!file.exists(dest)) {
    utils::download.file(url, destfile = dest, mode = "wb", quiet = TRUE)
  }
  dest
}

bbmri_read_cached_zipped_layer <- function(url, zip_name, label) {
  zip_path <- bbmri_cached_download(url, zip_name)
  layer_dir <- file.path(
    bbmri_map_cache_dir(),
    tools::file_path_sans_ext(zip_name)
  )

  if (!dir.exists(layer_dir) || length(list.files(layer_dir, pattern = "\\.shp$", full.names = TRUE)) == 0) {
    dir.create(layer_dir, recursive = TRUE, showWarnings = FALSE)
    utils::unzip(zip_path, exdir = layer_dir)
  }

  shp_files <- list.files(layer_dir, pattern = "\\.shp$", full.names = TRUE)
  if (length(shp_files) == 0) {
    stop("No shapefile found after extracting ", label, " from ", url, call. = FALSE)
  }

  obj <- sf::st_read(shp_files[[1]], quiet = TRUE)
  names(obj) <- ifelse(is.na(names(obj)), names(obj), tolower(names(obj)))
  obj
}

bbmri_load_countries <- function() {
  bbmri_read_cached_zipped_layer(
    "https://mapbox-geodata.s3.amazonaws.com/natural-earth-1.4.0/cultural/10m-admin-0-countries.zip",
    "10m-admin-0-countries.zip",
    "countries"
  )
}

bbmri_load_states <- function() {
  states <- bbmri_read_cached_zipped_layer(
    "https://mapbox-geodata.s3.amazonaws.com/natural-earth-1.4.0/cultural/10m-admin-1-states-provinces-lines.zip",
    "10m-admin-1-states-provinces-lines.zip",
    "admin-1 states"
  )
  subset(states, adm0_a3 %in% c("USA", "CAN", "AUS"))
}

bbmri_load_lakes <- function() {
  bbmri_read_cached_zipped_layer(
    "https://mapbox-geodata.s3.amazonaws.com/natural-earth-1.4.0/physical/10m-lakes.zip",
    "10m-lakes.zip",
    "lakes"
  )
}

bbmri_load_rivers <- function() {
  bbmri_read_cached_zipped_layer(
    "https://mapbox-geodata.s3.amazonaws.com/natural-earth-1.4.0/physical/10m-rivers-lake-centerlines.zip",
    "10m-rivers-lake-centerlines.zip",
    "rivers"
  )
}

bbmri_load_glaciers <- function() {
  bbmri_read_cached_zipped_layer(
    "https://mapbox-geodata.s3.amazonaws.com/natural-earth-1.4.0/physical/10m-glaciated-areas.zip",
    "10m-glaciated-areas.zip",
    "glaciers"
  )
}

bbmri_load_geo_lines <- function() {
  bbmri_read_cached_zipped_layer(
    "https://mapbox-geodata.s3.amazonaws.com/natural-earth-1.4.0/physical/10m-geographic-lines.zip",
    "10m-geographic-lines.zip",
    "geographic lines"
  )
}

bbmri_coord_sf <- function(bbox, crs, projected_bbox = NULL) {
  if (is.null(projected_bbox)) {
    projected_bbox <- bbmri_projected_bbox(bbox, crs)
  }
  ggplot2::coord_sf(
    crs = sf::st_crs(crs),
    default_crs = sf::st_crs(crs),
    xlim = c(projected_bbox[["xmin"]], projected_bbox[["xmax"]]),
    ylim = c(projected_bbox[["ymin"]], projected_bbox[["ymax"]]),
    expand = FALSE
  )
}

bbmri_void_theme <- function(background_fill) {
  ggplot2::theme_void() +
    ggplot2::theme(
      panel.background = ggplot2::element_rect(fill = background_fill, colour = NA),
      plot.background = ggplot2::element_rect(fill = background_fill, colour = NA),
      plot.margin = ggplot2::margin(4, 4, 4, 4)
    )
}

bbmri_font_family <- function() {
  "sans"
}

bbmri_projected_bbox <- function(bbox, crs) {
  bbmri_require_bbox(bbox, "Projected bbox source")

  xs <- c(
    seq(bbox[["xmin"]], bbox[["xmax"]], length.out = 64),
    rep(bbox[["xmax"]], 64),
    seq(bbox[["xmax"]], bbox[["xmin"]], length.out = 64),
    rep(bbox[["xmin"]], 64)
  )
  ys <- c(
    rep(bbox[["ymin"]], 64),
    seq(bbox[["ymin"]], bbox[["ymax"]], length.out = 64),
    rep(bbox[["ymax"]], 64),
    seq(bbox[["ymax"]], bbox[["ymin"]], length.out = 64)
  )

  bbox_outline <- sf::st_as_sf(
    data.frame(x = xs, y = ys),
    coords = c("x", "y"),
    crs = 4326
  )
  bbox_outline_proj <- sf::st_transform(bbox_outline, sf::st_crs(crs))
  sf::st_bbox(bbox_outline_proj)
}

bbmri_crop_projected_bbox <- function(projected_bbox, crop) {
  if (is.null(crop)) {
    return(projected_bbox)
  }
  required <- c("left", "right", "bottom", "top")
  missing <- setdiff(required, names(crop))
  if (length(missing) > 0) {
    stop("Projected crop is missing required fields: ", paste(missing, collapse = ", "), call. = FALSE)
  }
  if (!all(vapply(required, function(name) is.finite(crop[[name]]) && crop[[name]] >= 0, logical(1)))) {
    stop("Projected crop values must be finite non-negative numbers.", call. = FALSE)
  }
  width <- projected_bbox[["xmax"]] - projected_bbox[["xmin"]]
  height <- projected_bbox[["ymax"]] - projected_bbox[["ymin"]]
  cropped <- projected_bbox
  cropped[["xmin"]] <- projected_bbox[["xmin"]] + width * crop[["left"]]
  cropped[["xmax"]] <- projected_bbox[["xmax"]] - width * crop[["right"]]
  cropped[["ymin"]] <- projected_bbox[["ymin"]] + height * crop[["bottom"]]
  cropped[["ymax"]] <- projected_bbox[["ymax"]] - height * crop[["top"]]
  if (cropped[["xmin"]] >= cropped[["xmax"]] || cropped[["ymin"]] >= cropped[["ymax"]]) {
    stop("Projected crop removed the entire map window.", call. = FALSE)
  }
  cropped
}

bbmri_require_bbox <- function(bbox, label = "bbox") {
  required <- c("xmin", "ymin", "xmax", "ymax")
  missing <- setdiff(required, names(bbox))
  if (length(missing) > 0) {
    stop(label, " is missing required fields: ", paste(missing, collapse = ", "), call. = FALSE)
  }
  if (!all(vapply(required, function(name) is.finite(bbox[[name]]), logical(1)))) {
    stop(label, " must contain only finite numeric values.", call. = FALSE)
  }
  if (bbox[["xmin"]] >= bbox[["xmax"]] || bbox[["ymin"]] >= bbox[["ymax"]]) {
    stop(label, " must satisfy xmin < xmax and ymin < ymax.", call. = FALSE)
  }
  invisible(bbox)
}

bbmri_project_point_to_npc <- function(x, y, bbox, crs, projected_bbox = NULL) {
  bbmri_require_bbox(bbox, "Projected NPC source bbox")
  if (!is.finite(x) || !is.finite(y)) {
    stop("Projected NPC source point must be finite.", call. = FALSE)
  }
  proj_bbox <- if (is.null(projected_bbox)) bbmri_projected_bbox(bbox, crs) else projected_bbox
  c(
    x = (x - proj_bbox[["xmin"]]) / (proj_bbox[["xmax"]] - proj_bbox[["xmin"]]),
    y = (y - proj_bbox[["ymin"]]) / (proj_bbox[["ymax"]] - proj_bbox[["ymin"]])
  )
}

bbmri_fit_box_to_aspect <- function(x, y, width, height, aspect, page_aspect = 1.0) {
  if (!is.finite(aspect) || aspect <= 0) {
    stop("Aspect ratio must be a positive finite number.", call. = FALSE)
  }
  if (!all(is.finite(c(x, y, width, height, page_aspect))) || width <= 0 || height <= 0 || page_aspect <= 0) {
    stop("Container box must use finite positive width and height.", call. = FALSE)
  }

  container_aspect <- (width * page_aspect) / height
  if (container_aspect >= aspect) {
    fit_height <- height
    fit_width <- (fit_height * aspect) / page_aspect
    fit_x <- x + (width - fit_width) / 2
    fit_y <- y
  } else {
    fit_width <- width
    fit_height <- (fit_width * page_aspect) / aspect
    fit_x <- x
    fit_y <- y + (height - fit_height) / 2
  }

  list(
    x = fit_x,
    y = fit_y,
    width = fit_width,
    height = fit_height
  )
}

bbmri_cover_box_to_aspect <- function(x, y, width, height, aspect, page_aspect = 1.0) {
  if (!is.finite(aspect) || aspect <= 0) {
    stop("Aspect ratio must be a positive finite number.", call. = FALSE)
  }
  if (!all(is.finite(c(x, y, width, height, page_aspect))) || width <= 0 || height <= 0 || page_aspect <= 0) {
    stop("Container box must use finite positive width and height.", call. = FALSE)
  }

  container_aspect <- (width * page_aspect) / height
  if (container_aspect >= aspect) {
    fit_width <- width
    fit_height <- (fit_width * page_aspect) / aspect
    fit_x <- x
    fit_y <- y - (fit_height - height) / 2
  } else {
    fit_height <- height
    fit_width <- (fit_height * aspect) / page_aspect
    fit_x <- x - (fit_width - width) / 2
    fit_y <- y
  }

  list(
    x = fit_x,
    y = fit_y,
    width = fit_width,
    height = fit_height
  )
}

bbmri_halo_step <- function(bbox, crs, output_width_px, px = 1.0) {
  proj_bbox <- bbmri_projected_bbox(bbox, crs)
  units_per_px <- (proj_bbox[["xmax"]] - proj_bbox[["xmin"]]) / output_width_px
  units_per_px * px
}

bbmri_output_width_px <- function(export_sizes, output_variant) {
  if (output_variant %in% names(export_sizes$png)) {
    return(unname(export_sizes$png[[output_variant]][["width"]]))
  }
  unname(export_sizes$vector[["width"]])
}

bbmri_country_label_style_for_output <- function(cfg, output_variant) {
  label_style <- cfg$standard_label_style
  scale_value <- unname(cfg$country_label_scale_by_output[[output_variant]])
  if (is.na(scale_value) || !is.finite(scale_value) || scale_value <= 0) {
    scale_value <- 1.0
  }
  halo_scale <- unname(cfg$country_label_halo_scale_by_output[[output_variant]])
  if (is.na(halo_scale) || !is.finite(halo_scale) || halo_scale <= 0) {
    halo_scale <- 1.0
  }
  label_style$size <- label_style$size * scale_value
  label_style$inner_halo_px <- label_style$inner_halo_px * halo_scale
  label_style$outer_halo_px <- label_style$outer_halo_px * halo_scale
  label_style
}

bbmri_geom_text_halo <- function(data, mapping, size, bbox, crs, output_width_px, family = bbmri_font_family(), colour = "black", halo_colour = "white", halo_px = 1.0, inner_halo_px = NULL, outer_halo_px = NULL, nudge_x = 0, nudge_y = 0, use_shadowtext = TRUE, ...) {
  if (is.null(inner_halo_px)) {
    inner_halo_px <- halo_px
  }
  if (is.null(outer_halo_px)) {
    outer_halo_px <- halo_px * 2
  }

  inner_step <- bbmri_halo_step(bbox, crs, output_width_px, inner_halo_px)
  outer_step <- bbmri_halo_step(bbox, crs, output_width_px, outer_halo_px)
  halo_offsets <- list(
    c(-1, 0),
    c(1, 0),
    c(0, -1),
    c(0, 1),
    c(-1, -1),
    c(-1, 1),
    c(1, -1),
    c(1, 1)
  )

  outer_layers <- lapply(
    halo_offsets,
    function(offset) {
      ggplot2::geom_text(
        data = data,
        mapping = mapping,
        family = family,
        colour = grDevices::adjustcolor(halo_colour, alpha.f = 0.25),
        position = ggplot2::position_nudge(
          x = nudge_x + offset[[1]] * outer_step,
          y = nudge_y + offset[[2]] * outer_step
        ),
        size = size,
        ...
      )
    }
  )

  inner_layers <- lapply(
    halo_offsets,
    function(offset) {
      ggplot2::geom_text(
        data = data,
        mapping = mapping,
        family = family,
        colour = halo_colour,
        position = ggplot2::position_nudge(
          x = nudge_x + offset[[1]] * inner_step,
          y = nudge_y + offset[[2]] * inner_step
        ),
        size = size,
        ...
      )
    }
  )

  c(
    outer_layers,
    inner_layers,
    list(
      ggplot2::geom_text(
        data = data,
        mapping = mapping,
        size = size,
        family = family,
        colour = colour,
        position = ggplot2::position_nudge(x = nudge_x, y = nudge_y),
        ...
      )
    )
  )
}

bbmri_overlap_area <- function(a, b) {
  width <- max(0, min(a$xmax, b$xmax) - max(a$xmin, b$xmin))
  height <- max(0, min(a$ymax, b$ymax) - max(a$ymin, b$ymin))
  width * height
}

bbmri_place_local_labels <- function(points_df, bbox, crs, output_width_px, label_column = "biobankID") {
  if (nrow(points_df) == 0) {
    return(points_df)
  }

  proj_bbox <- bbmri_projected_bbox(bbox, crs)
  units_per_px <- (proj_bbox[["xmax"]] - proj_bbox[["xmin"]]) / output_width_px
  label_height <- units_per_px * 11
  char_width <- units_per_px * 4.6
  padding <- units_per_px * 2
  point_boxes <- vector("list", nrow(points_df))

  for (i in seq_len(nrow(points_df))) {
    point_radius <- units_per_px * (3 + points_df$marker_width[[i]] * 3)
    point_boxes[[i]] <- list(
      xmin = points_df$x[[i]] - point_radius,
      xmax = points_df$x[[i]] + point_radius,
      ymin = points_df$y[[i]] - point_radius,
      ymax = points_df$y[[i]] + point_radius
    )
  }

  candidates <- list(
    list(dx = 1.0, dy = 0.0, hjust = 0.0, vjust = 0.5),
    list(dx = 0.85, dy = 0.5, hjust = 0.0, vjust = 0.0),
    list(dx = 0.0, dy = 1.0, hjust = 0.5, vjust = 0.0),
    list(dx = -0.85, dy = 0.5, hjust = 1.0, vjust = 0.0),
    list(dx = -1.0, dy = 0.0, hjust = 1.0, vjust = 0.5),
    list(dx = -0.85, dy = -0.5, hjust = 1.0, vjust = 1.0),
    list(dx = 0.0, dy = -1.0, hjust = 0.5, vjust = 1.0),
    list(dx = 0.85, dy = -0.5, hjust = 0.0, vjust = 1.0)
  )
  if (!label_column %in% names(points_df)) {
    stop("Label column not found in point data: ", label_column, call. = FALSE)
  }

  label_values <- as.character(points_df[[label_column]])
  label_values[is.na(label_values)] <- ""
  order_idx <- order(-points_df$marker_width, -nchar(label_values))
  label_boxes <- vector("list", nrow(points_df))
  label_x <- numeric(nrow(points_df))
  label_y <- numeric(nrow(points_df))
  label_hjust <- numeric(nrow(points_df))
  label_vjust <- numeric(nrow(points_df))

  for (idx in order_idx) {
    label_width <- max(units_per_px * 18, nchar(label_values[[idx]]) * char_width)
    min_radius <- units_per_px * (5 + points_df$marker_width[[idx]] * 2.2)
    max_radius <- units_per_px * (12.5 + points_df$marker_width[[idx]] * 5.5)
    best <- NULL

    for (radius in seq(min_radius, max_radius, length.out = 7)) {
      for (candidate in candidates) {
        anchor_x <- points_df$x[[idx]] + candidate$dx * radius
        anchor_y <- points_df$y[[idx]] + candidate$dy * radius
        box <- list(
          xmin = anchor_x - label_width * candidate$hjust - padding,
          xmax = anchor_x + label_width * (1 - candidate$hjust) + padding,
          ymin = anchor_y - label_height * (1 - candidate$vjust) - padding,
          ymax = anchor_y + label_height * candidate$vjust + padding
        )

        score <- 0
        for (other_box in label_boxes) {
          if (!is.null(other_box)) {
            score <- score + 6 * bbmri_overlap_area(box, other_box)
          }
        }
        for (point_box in point_boxes) {
          score <- score + 2 * bbmri_overlap_area(box, point_box)
        }
        if (box$xmin < proj_bbox[["xmin"]]) score <- score + (proj_bbox[["xmin"]] - box$xmin) * label_height
        if (box$xmax > proj_bbox[["xmax"]]) score <- score + (box$xmax - proj_bbox[["xmax"]]) * label_height
        if (box$ymin < proj_bbox[["ymin"]]) score <- score + (proj_bbox[["ymin"]] - box$ymin) * label_width
        if (box$ymax > proj_bbox[["ymax"]]) score <- score + (box$ymax - proj_bbox[["ymax"]]) * label_width

        if (
          is.null(best) ||
          score < best$score ||
          (isTRUE(all.equal(score, best$score)) && radius < best$radius)
        ) {
          best <- list(
            score = score,
            radius = radius,
            x = anchor_x,
            y = anchor_y,
            hjust = candidate$hjust,
            vjust = candidate$vjust,
            box = box
          )
        }
      }
    }

    label_x[[idx]] <- best$x
    label_y[[idx]] <- best$y
    label_hjust[[idx]] <- best$hjust
    label_vjust[[idx]] <- best$vjust
    label_boxes[[idx]] <- best$box
  }

  points_df$label_x <- label_x
  points_df$label_y <- label_y
  points_df$label_hjust <- label_hjust
  points_df$label_vjust <- label_vjust
  points_df
}

bbmri_place_country_labels <- function(label_df, point_df, bbox, crs, output_width_px, label_size_scale = 1.0, layout_variant = "default") {
  if (nrow(label_df) == 0) {
    return(label_df)
  }

  proj_bbox <- bbmri_projected_bbox(bbox, crs)
  units_per_px <- (proj_bbox[["xmax"]] - proj_bbox[["xmin"]]) / output_width_px
  if (!is.finite(label_size_scale) || label_size_scale <= 0) {
    label_size_scale <- 1.0
  }
  label_height <- units_per_px * 14 * label_size_scale
  char_width <- units_per_px * 7 * label_size_scale
  padding <- units_per_px * 3 * max(0.8, label_size_scale)
  point_radius <- units_per_px * 5
  point_boxes <- vector("list", nrow(point_df))
  label_boxes <- vector("list", nrow(label_df))
  label_x <- numeric(nrow(label_df))
  label_y <- numeric(nrow(label_df))

  for (i in seq_len(nrow(point_df))) {
    point_boxes[[i]] <- list(
      xmin = point_df$x[[i]] - point_radius,
      xmax = point_df$x[[i]] + point_radius,
      ymin = point_df$y[[i]] - point_radius,
      ymax = point_df$y[[i]] + point_radius
    )
  }

  candidates <- if (identical(layout_variant, "small")) {
    list(
      c(0, 0),
      c(0, -8),
      c(0, 8),
      c(-8, 0),
      c(8, 0),
      c(0, -14),
      c(0, 14),
      c(-12, -8),
      c(12, -8),
      c(-12, 8),
      c(12, 8),
      c(-16, 0),
      c(16, 0),
      c(0, -18),
      c(0, 18),
      c(-18, -12),
      c(18, -12),
      c(-18, 12),
      c(18, 12),
      c(-24, 0),
      c(24, 0),
      c(0, -24),
      c(0, 24)
    )
  } else {
    list(
      c(0, 0),
      c(0, -8),
      c(0, 8),
      c(-8, 0),
      c(8, 0),
      c(0, -14),
      c(0, 14),
      c(-12, -8),
      c(12, -8),
      c(-12, 8),
      c(12, 8)
    )
  }

  point_overlap_weight <- if (identical(layout_variant, "small")) 16 else 12
  label_overlap_weight <- if (identical(layout_variant, "small")) 12 else 4
  move_penalty_weight <- if (identical(layout_variant, "small")) 0.08 else 0.2

  for (idx in seq_len(nrow(label_df))) {
    label_width <- max(units_per_px * 26, nchar(label_df$label[[idx]]) * char_width)
    best <- NULL

    for (candidate in candidates) {
      anchor_x <- label_df$x[[idx]] + candidate[[1]] * units_per_px
      anchor_y <- label_df$y[[idx]] + candidate[[2]] * units_per_px
      box <- list(
        xmin = anchor_x - label_width / 2 - padding,
        xmax = anchor_x + label_width / 2 + padding,
        ymin = anchor_y - label_height / 2 - padding,
        ymax = anchor_y + label_height / 2 + padding
      )

      score <- 0
      for (point_box in point_boxes) {
        score <- score + point_overlap_weight * bbmri_overlap_area(box, point_box)
      }
      for (other_box in label_boxes) {
        if (!is.null(other_box)) {
          score <- score + label_overlap_weight * bbmri_overlap_area(box, other_box)
        }
      }
      if (box$xmin < proj_bbox[["xmin"]]) score <- score + (proj_bbox[["xmin"]] - box$xmin) * label_height
      if (box$xmax > proj_bbox[["xmax"]]) score <- score + (box$xmax - proj_bbox[["xmax"]]) * label_height
      if (box$ymin < proj_bbox[["ymin"]]) score <- score + (proj_bbox[["ymin"]] - box$ymin) * label_width
      if (box$ymax > proj_bbox[["ymax"]]) score <- score + (box$ymax - proj_bbox[["ymax"]]) * label_width
      score <- score + (abs(candidate[[1]]) + abs(candidate[[2]])) * units_per_px * label_height * move_penalty_weight

      if (
        is.null(best) ||
        score < best$score
      ) {
        best <- list(
          score = score,
          x = anchor_x,
          y = anchor_y,
          box = box
        )
      }
    }

    label_x[[idx]] <- best$x
    label_y[[idx]] <- best$y
    label_boxes[[idx]] <- best$box
  }

  label_df$x <- label_x
  label_df$y <- label_y
  label_df
}

bbmri_apply_label_offsets <- function(label_df, offsets_df) {
  if (nrow(label_df) == 0 || is.null(offsets_df) || nrow(offsets_df) == 0) {
    return(label_df)
  }
  offsets_by_iso <- split(offsets_df, offsets_df$iso_a2)
  for (idx in seq_len(nrow(label_df))) {
    iso_code <- label_df$iso_a2[[idx]]
    offset_row <- offsets_by_iso[[iso_code]]
    if (is.null(offset_row) || nrow(offset_row) == 0) {
      next
    }
    label_df$x[[idx]] <- label_df$x[[idx]] + offset_row$dx[[1]]
    label_df$y[[idx]] <- label_df$y[[idx]] + offset_row$dy[[1]]
  }
  label_df
}

bbmri_geom_text_repel_halo <- function(data, mapping, size, family = bbmri_font_family(), colour = "black", halo_colour = "white", halo_scale = 1.0, seed = 42, ...) {
  list(
    ggrepel::geom_text_repel(
      data = data,
      mapping = mapping,
      size = size * halo_scale,
      family = family,
      colour = halo_colour,
      seed = seed,
      ...
    ),
    ggrepel::geom_text_repel(
      data = data,
      mapping = mapping,
      size = size,
      family = family,
      colour = colour,
      seed = seed,
      ...
    )
  )
}

bbmri_crop_to_bbox <- function(layer, bbox) {
  bbox_sfc <- sf::st_as_sfc(sf::st_bbox(
    c(
      xmin = bbox[["xmin"]],
      ymin = bbox[["ymin"]],
      xmax = bbox[["xmax"]],
      ymax = bbox[["ymax"]]
    ),
    crs = sf::st_crs(4326)
  ))
  target_bbox <- sf::st_bbox(sf::st_transform(bbox_sfc, sf::st_crs(layer)))
  geom_bboxes <- lapply(sf::st_geometry(layer), sf::st_bbox)
  hits <- vapply(
    geom_bboxes,
    function(gbox) {
      !(gbox[["xmax"]] < target_bbox[["xmin"]] ||
        gbox[["xmin"]] > target_bbox[["xmax"]] ||
        gbox[["ymax"]] < target_bbox[["ymin"]] ||
        gbox[["ymin"]] > target_bbox[["ymax"]])
    },
    logical(1)
  )
  layer[hits, ]
}

bbmri_clip_to_bbox <- function(layer, bbox) {
  if (nrow(layer) == 0) {
    return(layer)
  }

  bbox_sfc <- sf::st_as_sfc(sf::st_bbox(
    c(
      xmin = bbox[["xmin"]],
      ymin = bbox[["ymin"]],
      xmax = bbox[["xmax"]],
      ymax = bbox[["ymax"]]
    ),
    crs = sf::st_crs(4326)
  ))
  bbox_on_layer_crs <- sf::st_transform(bbox_sfc, sf::st_crs(layer))
  layer_valid <- suppressWarnings(sf::st_make_valid(layer))
  clipped <- suppressWarnings(sf::st_intersection(layer_valid, bbox_on_layer_crs))
  clipped[!sf::st_is_empty(clipped), , drop = FALSE]
}

bbmri_clip_to_projected_bbox <- function(layer, bbox, crs) {
  if (nrow(layer) == 0) {
    return(layer)
  }

  bbox_sfc <- sf::st_as_sfc(sf::st_bbox(
    c(
      xmin = bbox[["xmin"]],
      ymin = bbox[["ymin"]],
      xmax = bbox[["xmax"]],
      ymax = bbox[["ymax"]]
    ),
    crs = sf::st_crs(4326)
  ))
  bbox_on_target_crs <- sf::st_transform(bbox_sfc, sf::st_crs(crs))
  layer_on_target_crs <- suppressWarnings(sf::st_make_valid(sf::st_transform(layer, sf::st_crs(crs))))
  clipped <- suppressWarnings(sf::st_intersection(layer_on_target_crs, bbox_on_target_crs))
  clipped[!sf::st_is_empty(clipped), , drop = FALSE]
}

bbmri_exclude_bbox <- function(layer, bbox) {
  if (nrow(layer) == 0) {
    return(layer)
  }

  bbox_sfc <- sf::st_as_sfc(sf::st_bbox(
    c(
      xmin = bbox[["xmin"]],
      ymin = bbox[["ymin"]],
      xmax = bbox[["xmax"]],
      ymax = bbox[["ymax"]]
    ),
    crs = sf::st_crs(4326)
  ))
  exclusion_on_layer_crs <- sf::st_transform(bbox_sfc, sf::st_crs(layer))
  layer_valid <- suppressWarnings(sf::st_make_valid(layer))
  trimmed <- suppressWarnings(sf::st_difference(layer_valid, exclusion_on_layer_crs))
  trimmed[!sf::st_is_empty(trimmed), , drop = FALSE]
}

bbmri_filter_sf_by_mask <- function(layer, mask, include = TRUE) {
  if (nrow(layer) == 0 || nrow(mask) == 0) {
    return(if (include) layer[0, ] else layer)
  }

  layer_on_mask_crs <- sf::st_transform(layer, sf::st_crs(mask))
  hits <- lengths(sf::st_intersects(layer_on_mask_crs, mask)) > 0
  layer[if (include) hits else !hits, ]
}

bbmri_assign_standard_country_fill <- function(countries, cfg) {
  countries$fill_group <- cfg$standard_colors$default_country
  countries$fill_group[countries$iso_a2 %in% cfg$standard_country_groups$member] <- cfg$standard_colors$member
  countries$fill_group[countries$iso_a2 %in% cfg$standard_country_groups$observer] <- cfg$standard_colors$observer
  countries
}

bbmri_assign_fedplat_country_fill <- function(countries, cfg) {
  countries$fill_group <- cfg$fedplat_colors$default_country
  countries$fill_group[countries$iso_a2 %in% cfg$fedplat_country_groups$member] <- cfg$fedplat_colors$member
  countries$fill_group[countries$iso_a2 %in% cfg$fedplat_country_groups$observer] <- cfg$fedplat_colors$observer
  countries$fill_group[countries$iso_a2 %in% cfg$fedplat_country_groups$fedplat] <- cfg$fedplat_colors$fedplat
  countries
}

bbmri_assign_oec_country_fill <- function(countries, cfg) {
  countries$fill_group <- cfg$oec_colors$default_country
  countries$fill_group[countries$iso_a2 %in% cfg$oec_country_groups$member] <- cfg$oec_colors$member
  countries$fill_group[countries$iso_a2 %in% cfg$oec_country_groups$observer] <- cfg$oec_colors$observer
  countries$fill_group[countries$iso_a2 %in% cfg$oec_country_groups$gray] <- cfg$oec_colors$gray_country
  countries$fill_group[countries$adm0_a3 %in% c("CYN", "CNM", "KAS", "KNM")] <- cfg$oec_colors$gray_country
  countries
}

bbmri_country_label_df <- function(countries, cfg, crs, label_codes = cfg$standard_country_labels, label_offsets = cfg$standard_label_offsets) {
  label_countries <- countries[countries$iso_a2 %in% label_codes, ]
  if (nrow(label_countries) == 0) {
    return(data.frame())
  }

  projected <- sf::st_transform(sf::st_point_on_surface(label_countries), crs)
  coords <- sf::st_coordinates(projected)
  labels <- data.frame(
    iso_a2 = label_countries$iso_a2,
    label = toupper(label_countries$name),
    x = coords[, "X"],
    y = coords[, "Y"],
    stringsAsFactors = FALSE
  )

  offsets <- label_offsets
  labels <- merge(labels, offsets, by = "iso_a2", all.x = TRUE, sort = FALSE)
  labels$dx[is.na(labels$dx)] <- 0
  labels$dy[is.na(labels$dy)] <- 0
  labels$x <- labels$x + labels$dx
  labels$y <- labels$y + labels$dy
  labels
}

bbmri_mapnik_marker_size <- function(marker_width, cfg) {
  marker_width / cfg$marker_width_scale
}

bbmri_validate_geojson_columns <- function(obj, required_columns, label) {
  missing <- setdiff(required_columns, names(obj))
  if (length(missing) > 0) {
    stop(
      label,
      " is missing required columns: ",
      paste(missing, collapse = ", "),
      call. = FALSE
    )
  }
  invisible(obj)
}

bbmri_prepare_classic_layers <- function(bbox, cfg, fill_fn = bbmri_assign_standard_country_fill) {
  list(
    countries = bbmri_crop_to_bbox(fill_fn(bbmri_load_countries(), cfg), bbox),
    states = bbmri_crop_to_bbox(bbmri_load_states(), bbox),
    lakes = bbmri_crop_to_bbox(bbmri_load_lakes(), bbox),
    rivers = bbmri_crop_to_bbox(bbmri_load_rivers(), bbox),
    glaciers = bbmri_crop_to_bbox(bbmri_load_glaciers(), bbox),
    geo_lines = bbmri_crop_to_bbox(bbmri_load_geo_lines(), bbox)
  )
}

bbmri_add_classic_base <- function(plot, layers, bbox, crs, cfg) {
  plot +
    ggplot2::geom_sf(
      data = layers$countries,
      ggplot2::aes(fill = fill_group),
      colour = "white",
      linewidth = 0.2
    ) +
    ggplot2::geom_sf(
      data = layers$glaciers,
      fill = cfg$standard_colors$glacier,
      colour = NA,
      alpha = 0.5
    ) +
    ggplot2::geom_sf(
      data = layers$lakes,
      fill = cfg$standard_colors$water,
      colour = grDevices::adjustcolor(cfg$standard_colors$water, alpha.f = 0.8),
      linewidth = 0.2
    ) +
    ggplot2::geom_sf(
      data = layers$rivers,
      colour = cfg$standard_colors$line,
      linewidth = 0.15,
      alpha = 0.4,
      lineend = "round"
    ) +
    ggplot2::geom_sf(
      data = layers$geo_lines,
      colour = cfg$standard_colors$geo_line,
      linewidth = 0.18,
      alpha = 0.35,
      linetype = "dashed"
    ) +
    ggplot2::geom_sf(
      data = layers$states,
      colour = cfg$standard_colors$line,
      linewidth = 0.2,
      alpha = 0.25,
      linetype = "dashed"
    ) +
    bbmri_coord_sf(bbox, crs) +
    bbmri_void_theme(cfg$standard_colors$water)
}

bbmri_add_standard_iarc <- function(plot, iarc_df, cfg, bbox, crs, output_width_px, include_label = TRUE, label_text = "IARC", label_style = cfg$standard_label_style, label_placement = cfg$standard_iarc_label_placement) {
  iarc_symbol <- cfg$standard_iarc_symbol
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
    )

  if (!include_label) {
    return(plot)
  }

  plot + bbmri_geom_text_halo(
    data = iarc_df,
    mapping = ggplot2::aes(x = x, y = y, label = label_text),
    size = label_style$size,
    bbox = bbox,
    crs = crs,
    output_width_px = output_width_px,
    family = bbmri_font_family(),
    inner_halo_px = label_style$inner_halo_px,
    outer_halo_px = label_style$outer_halo_px,
    alpha = label_style$alpha,
    hjust = label_placement$hjust,
    vjust = label_placement$vjust,
    nudge_x = label_placement$nudge_x,
    nudge_y = label_placement$nudge_y
  )
}

bbmri_build_classic_standard_points_map <- function(points_path, bbox, export_sizes, cfg, iarc_path = NA_character_, output_variant = "med") {
  layers <- bbmri_prepare_classic_layers(bbox, cfg, fill_fn = bbmri_assign_standard_country_fill)
  points <- bbmri_read_sf(points_path, "Biobank GeoJSON")
  iarc <- bbmri_read_optional_sf(iarc_path)
  country_label_style <- bbmri_country_label_style_for_output(cfg, output_variant)
  output_width_px <- bbmri_output_width_px(export_sizes, output_variant)

  country_labels <- bbmri_country_label_df(layers$countries, cfg, cfg$standard_crs)
  point_df <- bbmri_biobank_points_df(points, cfg$standard_crs, label = "biobank points")
  point_df$fill_color <- ifelse(
    point_df$biobankType == "standaloneCollection",
    cfg$standard_colors$standalone,
    cfg$standard_colors$biobank
  )
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
      ggplot2::aes(x = x, y = y, fill = fill_color),
      shape = 21,
      size = bbmri_mapnik_marker_size(10, cfg),
      stroke = 0.4,
      colour = cfg$standard_colors$biobank_line,
      alpha = 0.8
    ) +
    ggplot2::scale_fill_identity()

  plot <- plot + bbmri_geom_text_halo(
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

  if (!is.null(iarc_df)) {
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

bbmri_filter_valid_lonlat_points <- function(points, label = "points", max_abs_lat = 85.05113) {
  points_4326 <- sf::st_transform(points, 4326)
  coords <- sf::st_coordinates(points_4326)
  if (is.null(dim(coords))) {
    coords <- matrix(coords, ncol = 2, byrow = TRUE)
  }
  if (is.null(colnames(coords))) {
    colnames(coords) <- c("X", "Y")
  }
  keep <- (
    is.finite(coords[, "X"]) &
    is.finite(coords[, "Y"]) &
    abs(coords[, "X"]) <= 180 &
    abs(coords[, "Y"]) <= max_abs_lat
  )

  dropped <- sum(!keep)
  if (dropped > 0) {
    message("Dropping ", dropped, " ", label, " with invalid lon/lat values before projection.")
  }

  points_4326[keep, ]
}

bbmri_biobank_points_df <- function(points, crs, label = "points") {
  filtered <- bbmri_filter_valid_lonlat_points(points, label = label)
  projected <- sf::st_transform(filtered, crs)
  coords <- sf::st_coordinates(projected)
  out <- data.frame(
    sf::st_drop_geometry(projected),
    x = coords[, "X"],
    y = coords[, "Y"],
    stringsAsFactors = FALSE
  )

  out[is.finite(out$x) & is.finite(out$y), , drop = FALSE]
}

bbmri_filter_member_observer_points <- function(points, cfg) {
  allowed_codes <- union(
    cfg$standard_country_groups$member,
    cfg$standard_country_groups$observer
  )
  props <- sf::st_drop_geometry(points)
  id_values <- if ("biobankID" %in% names(props)) {
    props$biobankID
  } else if ("id" %in% names(props)) {
    props$id
  } else {
    rep(NA_character_, nrow(props))
  }
  nn_codes <- sub("^bbmri-eric:ID:([A-Z]+)_.*$", "\\1", id_values)
  parsed_ok <- grepl("^bbmri-eric:ID:[A-Z]+_", id_values)
  keep <- parsed_ok & nn_codes %in% allowed_codes
  filtered <- points[keep, ]

  if (nrow(filtered) == 0) {
    stop("Member/observer point filtering produced no features.", call. = FALSE)
  }

  filtered
}

bbmri_write_geojson <- function(obj, path) {
  obj_4326 <- sf::st_transform(obj, 4326)
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  if (file.exists(path)) {
    file.remove(path)
  }
  sf::st_write(obj_4326, path, driver = "GeoJSON", quiet = TRUE)
}

bbmri_save_plot_formats <- function(plot, output_dir, prefix, export_sizes) {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

  raster_sizes <- export_sizes$png
  raster_dpi <- 300
  for (name in names(raster_sizes)) {
    size <- raster_sizes[[name]]
    ggplot2::ggsave(
      filename = file.path(output_dir, paste0(prefix, "-", name, ".png")),
      plot = plot,
      width = unname(size[["width"]]),
      height = unname(size[["height"]]),
      units = "px",
      bg = "white",
      limitsize = FALSE
    )

    ggplot2::ggsave(
      filename = file.path(output_dir, paste0(prefix, "-", name, ".pdf")),
      plot = plot,
      width = unname(size[["width"]]) / raster_dpi,
      height = unname(size[["height"]]) / raster_dpi,
      units = "in",
      bg = "white",
      limitsize = FALSE
    )
  }

  vector_size <- export_sizes$vector
  ggplot2::ggsave(
    filename = file.path(output_dir, paste0(prefix, ".pdf")),
    plot = plot,
    width = unname(vector_size[["width"]]) / raster_dpi,
    height = unname(vector_size[["height"]]) / raster_dpi,
    units = "in",
    bg = "white",
    limitsize = FALSE
  )

  if (requireNamespace("svglite", quietly = TRUE)) {
    ggplot2::ggsave(
      filename = file.path(output_dir, paste0(prefix, ".svg")),
      plot = plot,
      width = unname(vector_size[["width"]]) / raster_dpi,
      height = unname(vector_size[["height"]]) / raster_dpi,
      units = "in",
      bg = "white",
      device = svglite::svglite,
      limitsize = FALSE
    )
  } else {
    message("Skipping SVG export because package 'svglite' is not installed.")
  }
}

bbmri_save_plot_formats_from_builder <- function(build_plot, output_dir, prefix, export_sizes) {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

  raster_sizes <- export_sizes$png
  raster_dpi <- 300
  for (name in names(raster_sizes)) {
    size <- raster_sizes[[name]]
    plot <- build_plot(name)
    ggplot2::ggsave(
      filename = file.path(output_dir, paste0(prefix, "-", name, ".png")),
      plot = plot,
      width = unname(size[["width"]]),
      height = unname(size[["height"]]),
      units = "px",
      bg = "white",
      limitsize = FALSE
    )

    ggplot2::ggsave(
      filename = file.path(output_dir, paste0(prefix, "-", name, ".pdf")),
      plot = plot,
      width = unname(size[["width"]]) / raster_dpi,
      height = unname(size[["height"]]) / raster_dpi,
      units = "in",
      bg = "white",
      limitsize = FALSE
    )
  }

  vector_size <- export_sizes$vector
  vector_plot <- build_plot("vector")
  ggplot2::ggsave(
    filename = file.path(output_dir, paste0(prefix, ".pdf")),
    plot = vector_plot,
    width = unname(vector_size[["width"]]) / raster_dpi,
    height = unname(vector_size[["height"]]) / raster_dpi,
    units = "in",
    bg = "white",
    limitsize = FALSE
  )

  if (requireNamespace("svglite", quietly = TRUE)) {
    ggplot2::ggsave(
      filename = file.path(output_dir, paste0(prefix, ".svg")),
      plot = vector_plot,
      width = unname(vector_size[["width"]]) / raster_dpi,
      height = unname(vector_size[["height"]]) / raster_dpi,
      units = "in",
      bg = "white",
      device = svglite::svglite,
      limitsize = FALSE
    )
  } else {
    message("Skipping SVG export because package 'svglite' is not installed.")
  }
}
