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
    body <- sub("^--", "", arg)
    eq_pos <- regexpr("=", body, fixed = TRUE)[[1]]
    if (eq_pos < 0) {
      key <- body
      value <- TRUE
    } else {
      key <- substr(body, 1, eq_pos - 1)
      value <- substr(body, eq_pos + 1, nchar(body))
    }
    key <- gsub("-", "_", key, fixed = TRUE)
    if (!nzchar(key)) {
      stop("Unsupported empty option name in argument: ", arg, call. = FALSE)
    }
    args[[key]] <- value
  }

  args
}

bbmri_read_sf_quiet_warnings <- function(path) {
  withCallingHandlers(
    sf::st_read(path, quiet = TRUE),
    warning = function(w) {
      if (grepl("Non closed ring detected", conditionMessage(w), fixed = TRUE)) {
        invokeRestart("muffleWarning")
      }
    }
  )
}

bbmri_read_sf <- function(path, label) {
  if (!file.exists(path)) {
    stop(label, " not found: ", path, call. = FALSE)
  }
  bbmri_read_sf_quiet_warnings(path)
}

bbmri_read_optional_sf <- function(path) {
  if (is.null(path) || is.na(path) || identical(path, "")) {
    return(NULL)
  }
  if (!file.exists(path)) {
    return(NULL)
  }
  bbmri_read_sf_quiet_warnings(path)
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

  obj <- bbmri_read_sf_quiet_warnings(shp_files[[1]])
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

bbmri_svg_device_args <- function() {
  list(system_fonts = list(sans = "DejaVu Sans", serif = "DejaVu Serif", mono = "DejaVu Sans Mono"))
}

bbmri_normalize_svg_font_families <- function(path) {
  if (!file.exists(path)) {
    return(invisible(FALSE))
  }
  lines <- readLines(path, warn = FALSE, encoding = "UTF-8")
  lines <- gsub('font-family:[[:space:]]*"?Liberation Sans"?;', 'font-family: sans-serif;', lines, perl = TRUE)
  lines <- gsub('font-family:[[:space:]]*"?DejaVu Sans"?;', 'font-family: sans-serif;', lines, perl = TRUE)
  lines <- gsub('font-family:[[:space:]]*"?Nimbus Sans(?: L)?(?: Regular)?\"?;', 'font-family: sans-serif;', lines, perl = TRUE)
  lines <- gsub('font-family:[[:space:]]*"?sans"?;', 'font-family: sans-serif;', lines, perl = TRUE)
  lines <- gsub('font-family:[[:space:]]*"?DejaVu Sans Mono"?;', 'font-family: monospace;', lines, perl = TRUE)
  lines <- gsub('font-family:[[:space:]]*"?Liberation Mono"?;', 'font-family: monospace;', lines, perl = TRUE)
  lines <- gsub('font-family:[[:space:]]*"?Nimbus Mono PS"?;', 'font-family: monospace;', lines, perl = TRUE)
  lines <- gsub('font-family:[[:space:]]*"?mono"?;', 'font-family: monospace;', lines, perl = TRUE)
  lines <- gsub('font-family:[[:space:]]*"?Liberation Serif"?;', 'font-family: serif;', lines, perl = TRUE)
  lines <- gsub('font-family:[[:space:]]*"?DejaVu Serif"?;', 'font-family: serif;', lines, perl = TRUE)
  lines <- gsub('font-family:[[:space:]]*"?Nimbus Roman(?: No9 L)?(?: Regular)?\"?;', 'font-family: serif;', lines, perl = TRUE)
  lines <- gsub('font-family:[[:space:]]*"?serif"?;', 'font-family: serif;', lines, perl = TRUE)
  writeLines(lines, path, useBytes = TRUE)
  invisible(TRUE)
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

bbmri_union_bbox <- function(bboxes, label = "bbox union") {
  non_null <- Filter(Negate(is.null), bboxes)
  if (length(non_null) == 0) {
    stop(label, " requires at least one bbox.", call. = FALSE)
  }
  mins_x <- vapply(non_null, function(b) b[["xmin"]], numeric(1))
  mins_y <- vapply(non_null, function(b) b[["ymin"]], numeric(1))
  maxs_x <- vapply(non_null, function(b) b[["xmax"]], numeric(1))
  maxs_y <- vapply(non_null, function(b) b[["ymax"]], numeric(1))
  c(
    xmin = min(mins_x),
    ymin = min(mins_y),
    xmax = max(maxs_x),
    ymax = max(maxs_y)
  )
}

bbmri_projected_content_bbox <- function(layers, crs, label = "projected content bbox") {
  layer_bboxes <- lapply(layers, function(layer) {
    if (is.null(layer) || nrow(layer) == 0) {
      return(NULL)
    }
    projected_layer <- suppressWarnings(sf::st_transform(layer, sf::st_crs(crs)))
    sf::st_bbox(projected_layer)
  })
  bbmri_union_bbox(layer_bboxes, label = label)
}

bbmri_expand_projected_bbox <- function(projected_bbox, margins) {
  bbmri_require_bbox(projected_bbox, "Projected bbox to expand")
  required <- c("left", "right", "bottom", "top")
  missing <- setdiff(required, names(margins))
  if (length(missing) > 0) {
    stop("Projected bbox margins are missing required fields: ", paste(missing, collapse = ", "), call. = FALSE)
  }
  if (!all(vapply(required, function(name) is.finite(margins[[name]]), logical(1)))) {
    stop("Projected bbox margins must be finite numbers.", call. = FALSE)
  }
  width <- projected_bbox[["xmax"]] - projected_bbox[["xmin"]]
  height <- projected_bbox[["ymax"]] - projected_bbox[["ymin"]]
  c(
    xmin = projected_bbox[["xmin"]] - width * margins[["left"]],
    ymin = projected_bbox[["ymin"]] - height * margins[["bottom"]],
    xmax = projected_bbox[["xmax"]] + width * margins[["right"]],
    ymax = projected_bbox[["ymax"]] + height * margins[["top"]]
  )
}

bbmri_trim_projected_bbox_to_aspect <- function(projected_bbox, target_aspect, trim_bias = c(x = 0.5, y = 0.5)) {
  bbmri_require_bbox(projected_bbox, "Projected bbox to trim")
  if (!is.finite(target_aspect) || target_aspect <= 0) {
    stop("Target aspect must be a positive finite number.", call. = FALSE)
  }
  if (!all(c("x", "y") %in% names(trim_bias))) {
    stop("Trim bias must define x and y values.", call. = FALSE)
  }
  if (!all(vapply(trim_bias[c("x", "y")], function(value) is.finite(value) && value >= 0 && value <= 1, logical(1)))) {
    stop("Trim bias values must be finite numbers between 0 and 1.", call. = FALSE)
  }

  width <- projected_bbox[["xmax"]] - projected_bbox[["xmin"]]
  height <- projected_bbox[["ymax"]] - projected_bbox[["ymin"]]
  aspect <- width / height
  trimmed <- projected_bbox

  if (aspect > target_aspect) {
    target_width <- height * target_aspect
    extra_width <- width - target_width
    trim_left <- extra_width * trim_bias[["x"]]
    trim_right <- extra_width - trim_left
    trimmed[["xmin"]] <- projected_bbox[["xmin"]] + trim_left
    trimmed[["xmax"]] <- projected_bbox[["xmax"]] - trim_right
  } else if (aspect < target_aspect) {
    target_height <- width / target_aspect
    extra_height <- height - target_height
    trim_bottom <- extra_height * trim_bias[["y"]]
    trim_top <- extra_height - trim_bottom
    trimmed[["ymin"]] <- projected_bbox[["ymin"]] + trim_bottom
    trimmed[["ymax"]] <- projected_bbox[["ymax"]] - trim_top
  }

  bbmri_require_bbox(trimmed, "Trimmed projected bbox")
  trimmed
}

bbmri_expand_projected_bbox_to_aspect <- function(projected_bbox, target_aspect, expand_bias = c(x = 0.5, y = 0.5)) {
  bbmri_require_bbox(projected_bbox, "Projected bbox to expand to aspect")
  if (!is.finite(target_aspect) || target_aspect <= 0) {
    stop("Target aspect must be a positive finite number.", call. = FALSE)
  }
  if (!all(c("x", "y") %in% names(expand_bias))) {
    stop("Expand bias must define x and y values.", call. = FALSE)
  }
  if (!all(vapply(expand_bias[c("x", "y")], function(value) is.finite(value) && value >= 0 && value <= 1, logical(1)))) {
    stop("Expand bias values must be finite numbers between 0 and 1.", call. = FALSE)
  }

  width <- projected_bbox[["xmax"]] - projected_bbox[["xmin"]]
  height <- projected_bbox[["ymax"]] - projected_bbox[["ymin"]]
  aspect <- width / height
  expanded <- projected_bbox

  if (aspect < target_aspect) {
    target_width <- height * target_aspect
    extra_width <- target_width - width
    add_left <- extra_width * expand_bias[["x"]]
    add_right <- extra_width - add_left
    expanded[["xmin"]] <- projected_bbox[["xmin"]] - add_left
    expanded[["xmax"]] <- projected_bbox[["xmax"]] + add_right
  } else if (aspect > target_aspect) {
    target_height <- width / target_aspect
    extra_height <- target_height - height
    add_bottom <- extra_height * expand_bias[["y"]]
    add_top <- extra_height - add_bottom
    expanded[["ymin"]] <- projected_bbox[["ymin"]] - add_bottom
    expanded[["ymax"]] <- projected_bbox[["ymax"]] + add_top
  }

  bbmri_require_bbox(expanded, "Expanded projected bbox")
  expanded
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

bbmri_projected_parallel_y_cap <- function(latitude, bbox, crs, samples = 256) {
  bbmri_require_bbox(bbox, "Parallel projection bbox")
  if (!is.finite(latitude) || latitude < -90 || latitude > 90) {
    stop("Latitude cap must be a finite number in [-90, 90].", call. = FALSE)
  }
  if (!is.finite(samples) || samples < 2) {
    stop("Parallel projection sample count must be at least 2.", call. = FALSE)
  }

  pts <- sf::st_as_sf(
    data.frame(
      x = seq(bbox[["xmin"]], bbox[["xmax"]], length.out = as.integer(samples)),
      y = rep(latitude, as.integer(samples))
    ),
    coords = c("x", "y"),
    crs = 4326
  )
  pts_proj <- sf::st_transform(pts, sf::st_crs(crs))
  coords <- sf::st_coordinates(pts_proj)
  max(coords[, "Y"])
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

bbmri_strip_biobank_id_prefix <- function(value) {
  sub("^bbmri-eric:ID:", "", as.character(value))
}

bbmri_symbol_scale_for_output <- function(cfg, output_variant) {
  scale_value <- unname(cfg$symbol_scale_by_output[[output_variant]])
  if (is.na(scale_value) || !is.finite(scale_value) || scale_value <= 0) {
    scale_value <- 1.0
  }
  scale_value
}

bbmri_line_scale_for_output <- function(cfg, output_variant) {
  scale_value <- unname(cfg$line_scale_by_output[[output_variant]])
  if (is.na(scale_value) || !is.finite(scale_value) || scale_value <= 0) {
    scale_value <- 1.0
  }
  scale_value
}

bbmri_scaled_symbol_size <- function(value, cfg, output_variant) {
  value * bbmri_symbol_scale_for_output(cfg, output_variant)
}

bbmri_scaled_linewidth <- function(value, cfg, output_variant) {
  value * bbmri_line_scale_for_output(cfg, output_variant)
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

bbmri_place_local_labels <- function(points_df, bbox, crs, output_width_px, label_column = "biobankID", layout_variant = "default") {
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
  if (identical(layout_variant, "spread")) {
    candidates <- list(
      list(dx = 1.45, dy = 0.0, hjust = 0.0, vjust = 0.5),
      list(dx = 1.25, dy = 0.65, hjust = 0.0, vjust = 0.0),
      list(dx = 0.0, dy = 1.45, hjust = 0.5, vjust = 0.0),
      list(dx = -1.25, dy = 0.65, hjust = 1.0, vjust = 0.0),
      list(dx = -1.45, dy = 0.0, hjust = 1.0, vjust = 0.5),
      list(dx = -1.25, dy = -0.65, hjust = 1.0, vjust = 1.0),
      list(dx = 0.0, dy = -1.45, hjust = 0.5, vjust = 1.0),
      list(dx = 1.25, dy = -0.65, hjust = 0.0, vjust = 1.0),
      list(dx = 1.75, dy = 0.0, hjust = 0.0, vjust = 0.5),
      list(dx = -1.75, dy = 0.0, hjust = 1.0, vjust = 0.5),
      list(dx = 0.0, dy = 1.75, hjust = 0.5, vjust = 0.0),
      list(dx = 0.0, dy = -1.75, hjust = 0.5, vjust = 1.0)
    )
  } else if (identical(layout_variant, "spreadwide")) {
    candidates <- list(
      list(dx = 1.80, dy = 0.0, hjust = 0.0, vjust = 0.5),
      list(dx = 1.55, dy = 0.85, hjust = 0.0, vjust = 0.0),
      list(dx = 0.0, dy = 1.80, hjust = 0.5, vjust = 0.0),
      list(dx = -1.55, dy = 0.85, hjust = 1.0, vjust = 0.0),
      list(dx = -1.80, dy = 0.0, hjust = 1.0, vjust = 0.5),
      list(dx = -1.55, dy = -0.85, hjust = 1.0, vjust = 1.0),
      list(dx = 0.0, dy = -1.80, hjust = 0.5, vjust = 1.0),
      list(dx = 1.55, dy = -0.85, hjust = 0.0, vjust = 1.0),
      list(dx = 2.20, dy = 0.0, hjust = 0.0, vjust = 0.5),
      list(dx = -2.20, dy = 0.0, hjust = 1.0, vjust = 0.5),
      list(dx = 0.0, dy = 2.20, hjust = 0.5, vjust = 0.0),
      list(dx = 0.0, dy = -2.20, hjust = 0.5, vjust = 1.0),
      list(dx = 2.55, dy = 0.0, hjust = 0.0, vjust = 0.5),
      list(dx = -2.55, dy = 0.0, hjust = 1.0, vjust = 0.5),
      list(dx = 0.0, dy = 2.55, hjust = 0.5, vjust = 0.0),
      list(dx = 0.0, dy = -2.55, hjust = 0.5, vjust = 1.0)
    )
  } else if (identical(layout_variant, "globalwide")) {
    candidates <- list(
      list(dx = 1.10, dy = 0.0, hjust = 0.0, vjust = 0.5),
      list(dx = 0.95, dy = 0.55, hjust = 0.0, vjust = 0.0),
      list(dx = 0.0, dy = 1.15, hjust = 0.5, vjust = 0.0),
      list(dx = -0.95, dy = 0.55, hjust = 1.0, vjust = 0.0),
      list(dx = -1.10, dy = 0.0, hjust = 1.0, vjust = 0.5),
      list(dx = -0.95, dy = -0.55, hjust = 1.0, vjust = 1.0),
      list(dx = 0.0, dy = -1.15, hjust = 0.5, vjust = 1.0),
      list(dx = 0.95, dy = -0.55, hjust = 0.0, vjust = 1.0),
      list(dx = 1.45, dy = 0.0, hjust = 0.0, vjust = 0.5),
      list(dx = -1.45, dy = 0.0, hjust = 1.0, vjust = 0.5),
      list(dx = 0.0, dy = 1.45, hjust = 0.5, vjust = 0.0),
      list(dx = 0.0, dy = -1.45, hjust = 0.5, vjust = 1.0),
      list(dx = 1.85, dy = 0.0, hjust = 0.0, vjust = 0.5),
      list(dx = -1.85, dy = 0.0, hjust = 1.0, vjust = 0.5),
      list(dx = 0.0, dy = 1.85, hjust = 0.5, vjust = 0.0),
      list(dx = 0.0, dy = -1.85, hjust = 0.5, vjust = 1.0)
    )
  }
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

bbmri_prepare_biobank_label_df <- function(point_df, label_column = "biobankID", strip_prefix = TRUE) {
  if (!label_column %in% names(point_df)) {
    stop("Label column not found in point data: ", label_column, call. = FALSE)
  }
  label_df <- point_df
  label_df$label_text <- as.character(label_df[[label_column]])
  if (strip_prefix) {
    label_df$label_text <- bbmri_strip_biobank_id_prefix(label_df$label_text)
  }
  label_df
}

bbmri_add_biobank_label_layer <- function(
  plot,
  point_df,
  bbox,
  crs,
  output_width_px,
  label_style,
  label_column = "biobankID",
  strip_prefix = TRUE,
  layout_variant = "default",
  family = bbmri_font_family(),
  colour = "#4a4a4a",
  alpha = 0.95
) {
  if (nrow(point_df) == 0) {
    return(plot)
  }
  label_df <- bbmri_prepare_biobank_label_df(point_df, label_column = label_column, strip_prefix = strip_prefix)
  if (!"marker_width" %in% names(label_df)) {
    label_df$marker_width <- 1.15
  }
  label_df <- bbmri_place_local_labels(
    label_df,
    bbox = bbox,
    crs = crs,
    output_width_px = output_width_px,
    label_column = "label_text",
    layout_variant = layout_variant
  )
  plot + ggplot2::geom_text(
    data = label_df,
    mapping = ggplot2::aes(
      x = label_x,
      y = label_y,
      label = label_text,
      hjust = label_hjust,
      vjust = label_vjust
    ),
    size = label_style$size,
    family = family,
    colour = colour,
    alpha = alpha
  )
}

bbmri_order_points_back_to_front <- function(point_df, size_column = "marker_width") {
  if (nrow(point_df) == 0 || !size_column %in% names(point_df)) {
    return(point_df)
  }
  label_values <- if ("label_text" %in% names(point_df)) {
    as.character(point_df$label_text)
  } else {
    rep("", nrow(point_df))
  }
  label_values[is.na(label_values)] <- ""
  order_idx <- order(-point_df[[size_column]], -nchar(label_values))
  point_df[order_idx, , drop = FALSE]
}

bbmri_build_sized_biobank_map <- function(
  points_path,
  bbox,
  export_sizes,
  cfg,
  iarc_path = NA_character_,
  output_variant = "med",
  country_layout_variant = NULL,
  include_rivers = FALSE,
  required_columns = c("biobankID", "biobankName", "biobankType", "biobankSize"),
  point_fill_fn = NULL,
  point_fill_column = "fill_color",
  point_colour = NULL,
  point_alpha = 0.8,
  include_biobank_labels = TRUE,
  omit_biobank_labels_on_small = FALSE,
  biobank_label_column = "biobankID",
  biobank_label_layout_variant = "default",
  biobank_label_style = NULL,
  biobank_label_colour = "#4a4a4a",
  biobank_label_alpha = 0.95,
  label_output_width = NULL,
  point_size_value = NULL,
  point_size_column = "biobankSize",
  point_scale_by_output = NULL,
  point_min_by_output = NULL
) {
  if (is.null(point_colour)) {
    point_colour <- cfg$standard_colors$biobank_line
  }
  if (is.null(biobank_label_style)) {
    biobank_label_style <- cfg$sized_biobank_label_style
  }
  if (is.null(point_scale_by_output)) {
    point_scale_by_output <- cfg$sized_marker_scale_by_output
  }
  if (is.null(point_min_by_output)) {
    point_min_by_output <- cfg$sized_marker_min_by_output
  }
  if (is.null(country_layout_variant)) {
    country_layout_variant <- if (identical(output_variant, "small")) "small" else "default"
  }
  if (is.null(label_output_width)) {
    label_output_width <- if (output_variant %in% names(export_sizes$png)) {
      unname(export_sizes$png[[output_variant]][["width"]])
    } else {
      unname(export_sizes$vector[["width"]])
    }
  }

  layers <- bbmri_prepare_classic_layers(
    bbox,
    cfg,
    fill_fn = bbmri_assign_standard_country_fill,
    include_rivers = include_rivers
  )
  points <- bbmri_read_sf(points_path, "Biobank GeoJSON")
  bbmri_validate_geojson_columns(points, required_columns, "Biobank GeoJSON")
  iarc <- bbmri_read_optional_sf(iarc_path)
  country_label_style <- bbmri_country_label_style_for_output(cfg, output_variant)

  country_labels <- bbmri_country_label_df(layers$countries, cfg, cfg$standard_crs)
  point_df <- bbmri_biobank_points_df(points, cfg$standard_crs, label = "biobank points")

  if (!is.null(point_fill_fn)) {
    point_df[[point_fill_column]] <- point_fill_fn(point_df, cfg, output_variant)
  } else {
    point_df[[point_fill_column]] <- ifelse(
      point_df$biobankType == "standaloneCollection",
      cfg$standard_colors$standalone,
      cfg$standard_colors$biobank
    )
  }
  if (!"fill_color" %in% names(point_df)) {
    point_df$fill_color <- point_df[[point_fill_column]]
  }
  if (identical(output_variant, "small")) {
    country_labels <- bbmri_apply_label_offsets(country_labels, cfg$standard_small_label_offsets)
  }
  point_df$label_text <- bbmri_strip_biobank_id_prefix(as.character(point_df[[biobank_label_column]]))
  if (is.null(point_size_value)) {
    size_key <- as.character(point_df[[point_size_column]])
    size_key[is.na(size_key)] <- "0"
    point_df$marker_width <- unname(cfg$biobank_size_widths[size_key]) / 17 * unname(point_scale_by_output[[output_variant]])
    marker_min <- unname(point_min_by_output[[output_variant]])
    if (!is.na(marker_min) && is.finite(marker_min) && marker_min > 0) {
      point_df$marker_width <- pmax(point_df$marker_width, marker_min)
    }
  } else {
    point_df$marker_width <- bbmri_scaled_symbol_size(bbmri_mapnik_marker_size(point_size_value, cfg), cfg, output_variant)
  }
  point_df <- bbmri_place_local_labels(
    point_df,
    bbox = bbox,
    crs = cfg$standard_crs,
    output_width_px = label_output_width,
    label_column = "label_text",
    layout_variant = biobank_label_layout_variant
  )

  obstacle_df <- point_df[, c("x", "y")]
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
    output_width_px = label_output_width,
    label_size_scale = country_label_style$size / cfg$standard_label_style$size,
    layout_variant = country_layout_variant
  )

  plot <- bbmri_add_classic_base(
    ggplot2::ggplot(),
    layers = layers,
    bbox = bbox,
    crs = cfg$standard_crs,
    cfg = cfg,
    output_variant = output_variant
  )

  if (include_biobank_labels && (!omit_biobank_labels_on_small || !identical(output_variant, "small"))) {
    plot <- plot + ggplot2::geom_text(
      data = point_df,
      mapping = ggplot2::aes(
        x = label_x,
        y = label_y,
        label = label_text,
        hjust = label_hjust,
        vjust = label_vjust
      ),
      size = biobank_label_style$size,
      family = bbmri_font_family(),
      colour = biobank_label_colour,
      alpha = biobank_label_alpha
    )
  }

  point_df_plot <- bbmri_order_points_back_to_front(point_df)
  plot <- plot +
    ggplot2::geom_point(
      data = point_df_plot,
      ggplot2::aes(x = x, y = y, size = marker_width, fill = fill_color),
      shape = 21,
      stroke = 0.4 * bbmri_line_scale_for_output(cfg, output_variant),
      colour = point_colour,
      alpha = point_alpha
    ) +
    ggplot2::scale_fill_identity() +
    ggplot2::scale_size_identity()

  plot <- plot + bbmri_geom_text_halo(
    data = country_labels,
    mapping = ggplot2::aes(x = x, y = y, label = label),
    size = country_label_style$size,
    bbox = bbox,
    crs = cfg$standard_crs,
    output_width_px = label_output_width,
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
      output_width_px = label_output_width,
      output_variant = output_variant
    )
  }

  plot
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
  } else if (identical(layout_variant, "global")) {
    list(
      c(0, 0),
      c(0, -10),
      c(0, 10),
      c(-10, 0),
      c(10, 0),
      c(-14, -8),
      c(14, -8),
      c(-14, 8),
      c(14, 8),
      c(0, -18),
      c(0, 18),
      c(-18, 0),
      c(18, 0),
      c(-22, -12),
      c(22, -12),
      c(-22, 12),
      c(22, 12),
      c(-28, 0),
      c(28, 0),
      c(0, -26),
      c(0, 26),
      c(-32, -16),
      c(32, -16),
      c(-32, 16),
      c(32, 16)
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

  point_overlap_weight <- if (identical(layout_variant, "small")) 16 else if (identical(layout_variant, "globalwide")) 12 else if (identical(layout_variant, "global")) 14 else 12
  label_overlap_weight <- if (identical(layout_variant, "small")) 12 else if (identical(layout_variant, "globalwide")) 6 else if (identical(layout_variant, "global")) 8 else 4
  move_penalty_weight <- if (identical(layout_variant, "small")) 0.08 else if (identical(layout_variant, "globalwide")) 0.03 else if (identical(layout_variant, "global")) 0.05 else if (identical(layout_variant, "spread")) 0.14 else 0.2

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

  projected <- sf::st_transform(
    sf::st_point_on_surface(sf::st_geometry(label_countries)),
    crs
  )
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

bbmri_country_anchor_df <- function(countries, crs, label_codes = NULL) {
  if (!is.null(label_codes)) {
    countries <- countries[countries$iso_a2 %in% label_codes, ]
  }
  if (nrow(countries) == 0) {
    return(data.frame())
  }

  projected <- sf::st_transform(
    sf::st_point_on_surface(sf::st_geometry(countries)),
    crs
  )
  coords <- sf::st_coordinates(projected)
  data.frame(
    iso_a2 = countries$iso_a2,
    name = toupper(countries$name),
    x = coords[, "X"],
    y = coords[, "Y"],
    stringsAsFactors = FALSE
  )
}

bbmri_mapnik_marker_size <- function(marker_width, cfg) {
  marker_width / cfg$marker_width_scale
}

bbmri_assign_quality_point_style <- function(point_df, cfg) {
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
  point_df$legend_label <- ifelse(
    point_df$qual_id == "eric",
    "ERIC label",
    ifelse(point_df$qual_id == "accredited", "Accredited", "Other")
  )
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
  point_df
}

bbmri_add_quality_point_layers <- function(plot, point_df, cfg, output_variant = "med") {
  symbol_scale <- bbmri_symbol_scale_for_output(cfg, output_variant)
  line_scale <- bbmri_line_scale_for_output(cfg, output_variant)
  point_df$marker_width <- point_df$marker_width * symbol_scale
  plot +
    ggplot2::geom_point(
      data = subset(point_df, biobankType == "biobank"),
      ggplot2::aes(x = x, y = y, size = marker_width, fill = fill_color),
      shape = 21,
      stroke = 0.4 * line_scale,
      colour = cfg$quality_colors$line,
      alpha = cfg$quality_marker_style$alpha_biobank
    ) +
    ggplot2::geom_point(
      data = subset(point_df, biobankType != "biobank"),
      ggplot2::aes(x = x, y = y, size = marker_width, fill = fill_color),
      shape = 21,
      stroke = 0.35 * line_scale,
      colour = cfg$quality_colors$line,
      alpha = cfg$quality_marker_style$alpha_collection
    ) +
    ggplot2::scale_fill_identity() +
    ggplot2::scale_size_identity()
}

bbmri_add_quality_legend <- function(plot, bbox, crs, cfg, output_variant = "med") {
  symbol_scale <- bbmri_symbol_scale_for_output(cfg, output_variant)
  line_scale <- bbmri_line_scale_for_output(cfg, output_variant)
  bbmri_add_circle_legend(
    plot = plot,
    entries = data.frame(
      label = c("ERIC label", "Accredited", "Other"),
      fill = c(cfg$quality_colors$eric, cfg$quality_colors$accredited, cfg$quality_colors$other),
      colour = c(cfg$quality_colors$line, cfg$quality_colors$line, cfg$quality_colors$line),
      stroke = c(0.4, 0.4, 0.4),
      alpha = c(0.85, 0.85, 0.85),
      size = c(2.8, 2.8, 2.8),
      stringsAsFactors = FALSE
    ),
    bbox = bbox,
    crs = crs,
    box = cfg$quality_legend_box,
    title = "Quality",
    title_size = 2.6,
    text_size = 2.3,
    point_scale = symbol_scale,
    stroke_scale = line_scale,
    line_scale = line_scale
  )
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

bbmri_prepare_classic_layers <- function(bbox, cfg, fill_fn = bbmri_assign_standard_country_fill, include_rivers = FALSE) {
  list(
    countries = bbmri_crop_to_bbox(fill_fn(bbmri_load_countries(), cfg), bbox),
    states = bbmri_crop_to_bbox(bbmri_load_states(), bbox),
    lakes = bbmri_crop_to_bbox(bbmri_load_lakes(), bbox),
    rivers = NULL,
    glaciers = bbmri_crop_to_bbox(bbmri_load_glaciers(), bbox),
    geo_lines = bbmri_crop_to_bbox(bbmri_load_geo_lines(), bbox)
  )
}

bbmri_add_classic_base <- function(plot, layers, bbox, crs, cfg, output_variant = "med") {
  line_scale <- bbmri_line_scale_for_output(cfg, output_variant)
  plot <- plot +
    ggplot2::geom_sf(
      data = layers$countries,
      ggplot2::aes(fill = fill_group),
      colour = "white",
      linewidth = 0.2 * line_scale
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
      linewidth = 0.2 * line_scale
    ) +
    ggplot2::geom_sf(
      data = layers$geo_lines,
      colour = cfg$standard_colors$geo_line,
      linewidth = 0.18 * line_scale,
      alpha = 0.35,
      linetype = "dashed"
    ) +
    ggplot2::geom_sf(
      data = layers$states,
      colour = cfg$standard_colors$line,
      linewidth = 0.2 * line_scale,
      alpha = 0.25,
      linetype = "dashed"
    )

  plot +
    bbmri_coord_sf(bbox, crs) +
    bbmri_void_theme(cfg$standard_colors$water)
}

bbmri_add_standard_iarc <- function(plot, iarc_df, cfg, bbox, crs, output_width_px, include_label = TRUE, label_text = "IARC", label_style = cfg$standard_label_style, label_placement = cfg$standard_iarc_label_placement, output_variant = "med") {
  iarc_symbol <- cfg$standard_iarc_symbol
  symbol_scale <- bbmri_symbol_scale_for_output(cfg, output_variant)
  line_scale <- bbmri_line_scale_for_output(cfg, output_variant)
  plot <- plot +
    ggplot2::geom_point(
      data = iarc_df,
      ggplot2::aes(x = x, y = y),
      shape = 21,
      size = iarc_symbol$halo_size * symbol_scale,
      stroke = 0,
      fill = "white",
      colour = "white"
    ) +
    ggplot2::geom_point(
      data = iarc_df,
      ggplot2::aes(x = x, y = y),
      shape = 21,
      size = iarc_symbol$observer_size * symbol_scale,
      stroke = iarc_symbol$observer_stroke * line_scale,
      fill = cfg$standard_colors$iarc,
      colour = "black"
    ) +
    ggplot2::geom_point(
      data = iarc_df,
      ggplot2::aes(x = x, y = y),
      shape = 21,
      size = iarc_symbol$biobank_size * symbol_scale,
      stroke = iarc_symbol$biobank_stroke * line_scale,
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

bbmri_fractional_projected_point <- function(x_frac, y_frac, bbox, crs, projected_bbox = NULL) {
  proj_bbox <- if (is.null(projected_bbox)) bbmri_projected_bbox(bbox, crs) else projected_bbox
  bbmri_require_bbox(proj_bbox, "Legend projected bbox")
  c(
    x = proj_bbox[["xmin"]] + (proj_bbox[["xmax"]] - proj_bbox[["xmin"]]) * x_frac,
    y = proj_bbox[["ymin"]] + (proj_bbox[["ymax"]] - proj_bbox[["ymin"]]) * y_frac
  )
}

bbmri_add_circle_legend <- function(
  plot,
  entries,
  bbox,
  crs,
  box = list(x = 0.03, y = 0.04, width = 0.22, height = 0.15),
  title = NA_character_,
  background_fill = grDevices::adjustcolor("#ffffff", alpha.f = 0.90),
  border_colour = "#bbbbbb",
  title_size = 2.6,
  text_size = 2.3,
  point_size = 2.8,
  title_family = bbmri_font_family(),
  text_family = bbmri_font_family(),
  title_fontface = "bold",
  row_start_frac = NULL,
  row_step_frac = NULL,
  point_scale = 1.0,
  stroke_scale = 1.0,
  line_scale = 1.0
) {
  stopifnot(is.data.frame(entries))
  if (nrow(entries) == 0) {
    return(plot)
  }

  projected_bbox <- bbmri_projected_bbox(bbox, crs)
  lower_left <- bbmri_fractional_projected_point(box$x, box$y, bbox, crs, projected_bbox)
  upper_right <- bbmri_fractional_projected_point(box$x + box$width, box$y + box$height, bbox, crs, projected_bbox)
  box_width <- upper_right[["x"]] - lower_left[["x"]]
  box_height <- upper_right[["y"]] - lower_left[["y"]]

  plot <- plot + ggplot2::annotate(
    "rect",
    xmin = lower_left[["x"]],
    xmax = upper_right[["x"]],
    ymin = lower_left[["y"]],
    ymax = upper_right[["y"]],
    fill = background_fill,
    colour = border_colour,
    linewidth = 0.25 * line_scale
  )

  has_title <- !is.null(title) && !is.na(title) && nzchar(title)
  top_margin <- 0.16
  if (has_title) {
    title_xy <- c(
      x = lower_left[["x"]] + box_width * 0.08,
      y = upper_right[["y"]] - box_height * 0.10
    )
    plot <- plot + ggplot2::annotate(
      "text",
      x = title_xy[["x"]],
      y = title_xy[["y"]],
      label = title,
      hjust = 0,
      vjust = 1,
      size = title_size,
      family = title_family,
      fontface = title_fontface,
      colour = "#222222"
    )
    top_margin <- 0.34
  }

  if (is.null(row_start_frac)) {
    row_start_frac <- if (has_title) 1 - top_margin else 0.82
  }
  if (is.null(row_step_frac)) {
    row_step_frac <- if (nrow(entries) > 1) 0.18 else 0
  }
  for (idx in seq_len(nrow(entries))) {
    row_y_frac <- row_start_frac - (idx - 1) * row_step_frac
    row_y <- lower_left[["y"]] + box_height * row_y_frac
    point_x <- lower_left[["x"]] + box_width * 0.12
    label_x <- lower_left[["x"]] + box_width * 0.22
    entry <- entries[idx, , drop = FALSE]

    plot <- plot +
      ggplot2::annotate(
        "point",
        x = point_x,
        y = row_y,
        shape = 21,
        size = (if ("size" %in% names(entry)) entry$size[[1]] else point_size) * point_scale,
        stroke = (if ("stroke" %in% names(entry)) entry$stroke[[1]] else 0.4) * stroke_scale,
        fill = entry$fill[[1]],
        colour = if ("colour" %in% names(entry)) entry$colour[[1]] else "#333333",
        alpha = if ("alpha" %in% names(entry)) entry$alpha[[1]] else 1.0
      ) +
      ggplot2::annotate(
        "text",
        x = label_x,
        y = row_y,
        label = entry$label[[1]],
        hjust = 0,
        vjust = 0.5,
        size = text_size,
        family = text_family,
        colour = "#222222"
      )
  }

  plot
}

bbmri_add_rect_legend <- function(
  plot,
  entries,
  bbox,
  crs,
  box = list(x = 0.03, y = 0.04, width = 0.22, height = 0.15),
  title = NA_character_,
  background_fill = grDevices::adjustcolor("#ffffff", alpha.f = 0.90),
  border_colour = "#bbbbbb",
  title_size = 2.6,
  text_size = 2.3,
  rect_width_frac = 0.065,
  rect_height_frac = 0.040,
  title_family = bbmri_font_family(),
  text_family = bbmri_font_family(),
  title_fontface = "bold",
  row_start_frac = NULL,
  row_step_frac = NULL,
  line_scale = 1.0
) {
  stopifnot(is.data.frame(entries))
  if (nrow(entries) == 0) {
    return(plot)
  }

  projected_bbox <- bbmri_projected_bbox(bbox, crs)
  lower_left <- bbmri_fractional_projected_point(box$x, box$y, bbox, crs, projected_bbox)
  upper_right <- bbmri_fractional_projected_point(box$x + box$width, box$y + box$height, bbox, crs, projected_bbox)
  box_width <- upper_right[["x"]] - lower_left[["x"]]
  box_height <- upper_right[["y"]] - lower_left[["y"]]

  plot <- plot + ggplot2::annotate(
    "rect",
    xmin = lower_left[["x"]],
    xmax = upper_right[["x"]],
    ymin = lower_left[["y"]],
    ymax = upper_right[["y"]],
    fill = background_fill,
    colour = border_colour,
    linewidth = 0.25 * line_scale
  )

  has_title <- !is.null(title) && !is.na(title) && nzchar(title)
  top_margin <- 0.16
  if (has_title) {
    title_xy <- c(
      x = lower_left[["x"]] + box_width * 0.08,
      y = upper_right[["y"]] - box_height * 0.10
    )
    plot <- plot + ggplot2::annotate(
      "text",
      x = title_xy[["x"]],
      y = title_xy[["y"]],
      label = title,
      hjust = 0,
      vjust = 1,
      size = title_size,
      family = title_family,
      fontface = title_fontface,
      colour = "#222222"
    )
    top_margin <- 0.34
  }

  if (is.null(row_start_frac)) {
    row_start_frac <- if (has_title) 1 - top_margin else 0.82
  }
  if (is.null(row_step_frac)) {
    row_step_frac <- if (nrow(entries) > 1) 0.18 else 0
  }
  for (idx in seq_len(nrow(entries))) {
    row_y_frac <- row_start_frac - (idx - 1) * row_step_frac
    row_y <- lower_left[["y"]] + box_height * row_y_frac
    rect_x <- lower_left[["x"]] + box_width * 0.10
    label_x <- lower_left[["x"]] + box_width * 0.23
    rect_width <- box_width * rect_width_frac
    rect_height <- box_height * rect_height_frac
    entry <- entries[idx, , drop = FALSE]

    plot <- plot +
      ggplot2::annotate(
        "rect",
        xmin = rect_x - rect_width / 2,
        xmax = rect_x + rect_width / 2,
        ymin = row_y - rect_height / 2,
        ymax = row_y + rect_height / 2,
        fill = entry$fill[[1]],
        colour = if ("colour" %in% names(entry)) entry$colour[[1]] else "#333333",
        linewidth = (if ("linewidth" %in% names(entry)) entry$linewidth[[1]] else 0.25) * line_scale,
        alpha = if ("alpha" %in% names(entry)) entry$alpha[[1]] else 1.0
      ) +
      ggplot2::annotate(
        "text",
        x = label_x,
        y = row_y,
        label = entry$label[[1]],
        hjust = 0,
        vjust = 0.5,
        size = text_size,
        family = text_family,
        colour = "#222222"
      )
  }

  plot
}

bbmri_build_classic_standard_points_map <- function(
  points_path,
  bbox,
  export_sizes,
  cfg,
  iarc_path = NA_character_,
  output_variant = "med",
  include_rivers = FALSE,
  country_layout_variant = NULL,
  include_biobank_labels = FALSE,
  biobank_label_column = "biobankID",
  biobank_label_layout_variant = "default",
  biobank_label_style = NULL,
  biobank_label_colour = "#4a4a4a",
  biobank_label_alpha = 0.95
) {
  layers <- bbmri_prepare_classic_layers(bbox, cfg, fill_fn = bbmri_assign_standard_country_fill, include_rivers = include_rivers)
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
  if (include_biobank_labels) {
    if (is.null(biobank_label_style)) {
      biobank_label_style <- cfg$sized_biobank_label_style
    }
    point_df$marker_width <- rep(1.15, nrow(point_df))
    point_df <- bbmri_prepare_biobank_label_df(
      point_df,
      label_column = biobank_label_column,
      strip_prefix = TRUE
    )
    point_df <- bbmri_place_local_labels(
      point_df,
      bbox = bbox,
      crs = cfg$standard_crs,
      output_width_px = output_width_px,
      label_column = "label_text",
      layout_variant = biobank_label_layout_variant
    )
  }
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
  if (is.null(country_layout_variant)) {
    country_layout_variant <- if (identical(output_variant, "small")) "small" else "default"
  }

  country_labels <- bbmri_place_country_labels(
    country_labels,
    obstacle_df,
    bbox = bbox,
    crs = cfg$standard_crs,
    output_width_px = output_width_px,
    label_size_scale = country_label_style$size / cfg$standard_label_style$size,
    layout_variant = country_layout_variant
  )

  plot <- bbmri_add_classic_base(
    ggplot2::ggplot(),
    layers = layers,
    bbox = bbox,
    crs = cfg$standard_crs,
    cfg = cfg,
    output_variant = output_variant
  ) + ggplot2::scale_fill_identity()

  if (include_biobank_labels) {
    plot <- plot + ggplot2::geom_text(
      data = point_df,
      mapping = ggplot2::aes(
        x = label_x,
        y = label_y,
        label = label_text,
        hjust = label_hjust,
        vjust = label_vjust
      ),
      size = biobank_label_style$size,
      family = bbmri_font_family(),
      colour = biobank_label_colour,
      alpha = biobank_label_alpha
    )
  }

  plot <- plot +
    ggplot2::geom_point(
      data = point_df,
      ggplot2::aes(x = x, y = y, fill = fill_color),
      shape = 21,
      size = bbmri_scaled_symbol_size(bbmri_mapnik_marker_size(10, cfg), cfg, output_variant),
      stroke = bbmri_scaled_linewidth(0.4, cfg, output_variant),
      colour = cfg$standard_colors$biobank_line,
      alpha = 0.8
    )

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
      output_width_px = output_width_px,
      output_variant = output_variant
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

bbmri_select_export_sizes <- function(export_sizes, output_variants = NULL) {
  if (is.null(output_variants) || !length(output_variants)) {
    return(export_sizes)
  }

  selected_variants <- output_variants[output_variants %in% names(export_sizes$png)]
  if (!length(selected_variants)) {
    stop(
      "No matching export size variants found: ",
      paste(output_variants, collapse = ", "),
      call. = FALSE
    )
  }

  list(
    png = export_sizes$png[selected_variants],
    vector = export_sizes$vector
  )
}

bbmri_save_plot_formats <- function(plot, output_dir, prefix, export_sizes, output_variants = NULL, include_vector = TRUE, announce = TRUE) {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

  raster_sizes <- bbmri_select_export_sizes(export_sizes, output_variants)$png
  raster_dpi <- 300
  for (name in names(raster_sizes)) {
    size <- raster_sizes[[name]]
    if (isTRUE(announce)) {
      cat(prefix, "-", name, " ... ", sep = "")
    }
    ggplot2::ggsave(
      filename = file.path(output_dir, paste0(prefix, "-", name, ".png")),
      plot = plot,
      width = unname(size[["width"]]),
      height = unname(size[["height"]]),
      units = "px",
      bg = "white",
      limitsize = FALSE
    )
    if (isTRUE(announce)) {
      cat("PNG ", sep = "")
    }

    ggplot2::ggsave(
      filename = file.path(output_dir, paste0(prefix, "-", name, ".pdf")),
      plot = plot,
      width = unname(size[["width"]]) / raster_dpi,
      height = unname(size[["height"]]) / raster_dpi,
      units = "in",
      bg = "white",
      limitsize = FALSE
    )
    if (isTRUE(announce)) {
      cat("PDF ", sep = "")
    }

    if (requireNamespace("svglite", quietly = TRUE)) {
      svg_path <- file.path(output_dir, paste0(prefix, "-", name, ".svg"))
      do.call(
        ggplot2::ggsave,
        c(
          list(
            filename = svg_path,
            plot = plot,
            width = unname(size[["width"]]) / raster_dpi,
            height = unname(size[["height"]]) / raster_dpi,
            units = "in",
            bg = "white",
            device = svglite::svglite,
            limitsize = FALSE
          ),
          bbmri_svg_device_args()
        )
      )
      bbmri_normalize_svg_font_families(svg_path)
      if (isTRUE(announce)) {
        cat("SVG ", sep = "")
      }
    } else if (isTRUE(announce)) {
      cat("SVG(skipped) ", sep = "")
    }
    if (isTRUE(announce)) {
      cat("done\n", sep = "")
    }
  }

  if (isTRUE(include_vector)) {
    vector_size <- export_sizes$vector
    if (isTRUE(announce)) {
      cat(prefix, " ... ", sep = "")
    }
    ggplot2::ggsave(
      filename = file.path(output_dir, paste0(prefix, ".pdf")),
      plot = plot,
      width = unname(vector_size[["width"]]) / raster_dpi,
      height = unname(vector_size[["height"]]) / raster_dpi,
      units = "in",
      bg = "white",
      limitsize = FALSE
    )
    if (isTRUE(announce)) {
      cat("PDF ", sep = "")
    }

    if (requireNamespace("svglite", quietly = TRUE)) {
      svg_path <- file.path(output_dir, paste0(prefix, ".svg"))
      do.call(
        ggplot2::ggsave,
        c(
          list(
            filename = svg_path,
            plot = plot,
            width = unname(vector_size[["width"]]) / raster_dpi,
            height = unname(vector_size[["height"]]) / raster_dpi,
            units = "in",
            bg = "white",
            device = svglite::svglite,
            limitsize = FALSE
          ),
          bbmri_svg_device_args()
        )
      )
      bbmri_normalize_svg_font_families(svg_path)
      if (isTRUE(announce)) {
        cat("SVG ", sep = "")
      }
    } else {
      message("Skipping SVG export because package 'svglite' is not installed.")
      if (isTRUE(announce)) {
        cat("SVG(skipped) ", sep = "")
      }
    }
    if (isTRUE(announce)) {
      cat("done\n", sep = "")
    }
  }
}

bbmri_save_svg_variant <- function(plot, path, size, raster_dpi = 300) {
  if (!requireNamespace("svglite", quietly = TRUE)) {
    return(invisible(FALSE))
  }
  do.call(
    ggplot2::ggsave,
    c(
      list(
        filename = path,
        plot = plot,
        width = unname(size[["width"]]) / raster_dpi,
        height = unname(size[["height"]]) / raster_dpi,
        units = "in",
        bg = "white",
        device = svglite::svglite,
        limitsize = FALSE
      ),
      bbmri_svg_device_args()
    )
  )
  bbmri_normalize_svg_font_families(path)
  invisible(TRUE)
}

bbmri_save_plot_formats_from_builder <- function(build_plot, output_dir, prefix, export_sizes, output_variants = NULL, include_vector = TRUE, announce = TRUE) {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

  raster_sizes <- bbmri_select_export_sizes(export_sizes, output_variants)$png
  raster_dpi <- 300
  for (name in names(raster_sizes)) {
    size <- raster_sizes[[name]]
    plot <- build_plot(name)
    if (isTRUE(announce)) {
      cat(prefix, "-", name, " ... ", sep = "")
    }
    ggplot2::ggsave(
      filename = file.path(output_dir, paste0(prefix, "-", name, ".png")),
      plot = plot,
      width = unname(size[["width"]]),
      height = unname(size[["height"]]),
      units = "px",
      bg = "white",
      limitsize = FALSE
    )
    if (isTRUE(announce)) {
      cat("PNG ", sep = "")
    }

    ggplot2::ggsave(
      filename = file.path(output_dir, paste0(prefix, "-", name, ".pdf")),
      plot = plot,
      width = unname(size[["width"]]) / raster_dpi,
      height = unname(size[["height"]]) / raster_dpi,
      units = "in",
      bg = "white",
      limitsize = FALSE
    )
    if (isTRUE(announce)) {
      cat("PDF ", sep = "")
    }

    if (bbmri_save_svg_variant(
      plot = plot,
      path = file.path(output_dir, paste0(prefix, "-", name, ".svg")),
      size = size,
      raster_dpi = raster_dpi
    )) {
      if (isTRUE(announce)) {
        cat("SVG ", sep = "")
      }
    } else if (isTRUE(announce)) {
      cat("SVG(skipped) ", sep = "")
    }

    if (isTRUE(announce)) {
      cat("done\n", sep = "")
    }
  }

  if (isTRUE(include_vector)) {
    vector_size <- export_sizes$vector
    vector_plot <- build_plot("vector")
    if (isTRUE(announce)) {
      cat(prefix, " ... ", sep = "")
    }
    ggplot2::ggsave(
      filename = file.path(output_dir, paste0(prefix, ".pdf")),
      plot = vector_plot,
      width = unname(vector_size[["width"]]) / raster_dpi,
      height = unname(vector_size[["height"]]) / raster_dpi,
      units = "in",
      bg = "white",
      limitsize = FALSE
    )
    if (isTRUE(announce)) {
      cat("PDF ", sep = "")
    }

    if (requireNamespace("svglite", quietly = TRUE)) {
      svg_path <- file.path(output_dir, paste0(prefix, ".svg"))
      do.call(
        ggplot2::ggsave,
        c(
          list(
            filename = svg_path,
            plot = vector_plot,
            width = unname(vector_size[["width"]]) / raster_dpi,
            height = unname(vector_size[["height"]]) / raster_dpi,
            units = "in",
            bg = "white",
            device = svglite::svglite,
            limitsize = FALSE
          ),
          bbmri_svg_device_args()
        )
      )
      bbmri_normalize_svg_font_families(svg_path)
      if (isTRUE(announce)) {
        cat("SVG ", sep = "")
      }
    } else {
      message("Skipping SVG export because package 'svglite' is not installed.")
      if (isTRUE(announce)) {
        cat("SVG(skipped) ", sep = "")
      }
    }
    if (isTRUE(announce)) {
      cat("done\n", sep = "")
    }
  }
}
