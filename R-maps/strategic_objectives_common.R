bbmri_detect_rmaps_dir <- function() {
  cmd_args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", cmd_args, value = TRUE)
  if (length(file_arg) > 0) {
    candidate <- normalizePath(dirname(sub("^--file=", "", file_arg[[1]])), winslash = "/", mustWork = TRUE)
    while (TRUE) {
      if (file.exists(file.path(candidate, "map_config.R")) && file.exists(file.path(candidate, "map_common.R"))) {
        return(candidate)
      }
      parent <- normalizePath(file.path(candidate, ".."), winslash = "/", mustWork = TRUE)
      if (identical(parent, candidate)) {
        break
      }
      candidate <- parent
    }
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

  stop(
    "Unable to locate the R-maps directory. Set the working directory to the repository root or the R-maps directory before sourcing strategic_objectives_common.R.",
    call. = FALSE
  )
}

script_dir <- bbmri_detect_rmaps_dir()
source(file.path(script_dir, "map_config.R"))
source(file.path(script_dir, "map_common.R"))

`%||%` <- function(x, y) {
  if (is.null(x) || length(x) == 0 || (length(x) == 1 && is.na(x))) {
    return(y)
  }
  x
}

bbmri_has_text <- function(value) {
  !is.null(value) && length(value) == 1 && !is.na(value) && nzchar(value)
}

bbmri_strategic_objectives_python <- function() {
  repo_root <- normalizePath(file.path(script_dir, ".."), winslash = "/", mustWork = TRUE)
  candidates <- c(
    file.path(repo_root, ".venv-maps", "bin", "python"),
    Sys.which("python3"),
    Sys.which("python")
  )
  candidates <- candidates[nzchar(candidates)]
  if (length(candidates) == 0) {
    stop("No usable Python interpreter was found for strategic-objectives spec parsing.", call. = FALSE)
  }
  candidates[[1]]
}

bbmri_load_strategic_objectives_spec <- function(path, python_bin = NULL) {
  bbmri_require_packages(c("jsonlite"))
  if (is.null(python_bin) || !nzchar(python_bin)) {
    python_bin <- bbmri_strategic_objectives_python()
  }
  if (!file.exists(path)) {
    stop("Strategic objectives spec not found: ", path, call. = FALSE)
  }

  helper <- file.path(script_dir, "prepare_strategic_objectives_spec.py")
  if (!file.exists(helper)) {
    stop("Strategic objectives helper script not found: ", helper, call. = FALSE)
  }

  tmp_json <- tempfile("strategic-objectives-", fileext = ".json")
  on.exit({
    if (file.exists(tmp_json)) {
      unlink(tmp_json)
    }
  }, add = TRUE)
  status <- system2(python_bin, args = c(helper, "--input", path, "--output", tmp_json))
  if (!identical(status, 0L)) {
    stop("Strategic objectives spec normalization failed with exit status ", status, call. = FALSE)
  }
  jsonlite::fromJSON(tmp_json, simplifyVector = FALSE)
}

bbmri_so_subset_spec <- function(spec, objective_ids = NULL, goal_ids = NULL) {
  objectives <- spec$objectives %||% list()
  if (is.null(objective_ids) && is.null(goal_ids)) {
    return(spec)
  }
  objective_ids <- if (is.null(objective_ids)) NULL else unique(toupper(trimws(as.character(objective_ids))))
  goal_ids <- if (is.null(goal_ids)) NULL else unique(trimws(as.character(goal_ids)))
  filtered_objectives <- list()
  idx <- 0L
  for (objective in objectives) {
    objective_id <- as.character(objective$id %||% "")
    if (!nzchar(objective_id)) {
      next
    }
    if (!is.null(objective_ids) && !(objective_id %in% objective_ids)) {
      next
    }
    goals <- objective$goals %||% list()
    if (!is.null(goal_ids)) {
      goals <- Filter(function(goal) {
        goal_id <- as.character(goal$id %||% "")
        nzchar(goal_id) && goal_id %in% goal_ids
      }, goals)
    }
    if (length(goals) == 0) {
      next
    }
    idx <- idx + 1L
    filtered_objectives[[idx]] <- modifyList(objective, list(goals = goals))
  }
  spec$objectives <- filtered_objectives
  spec
}

bbmri_so_objective_ids <- function(spec, objective_filter = NULL) {
  objectives <- spec$objectives
  if (!length(objectives)) {
    return(character(0))
  }
  ids <- vapply(objectives, function(obj) as.character(obj$id %||% ""), character(1))
  ids <- ids[nzchar(ids)]
  if (bbmri_has_text(objective_filter)) {
    ids <- ids[ids == objective_filter]
  }
  ids
}

bbmri_so_goal_ids <- function(spec, objective_filter = NULL, goal_filter = NULL) {
  ids <- character(0)
  for (objective in spec$objectives) {
    objective_id <- as.character(objective$id %||% "")
    if (!nzchar(objective_id)) {
      next
    }
    if (bbmri_has_text(objective_filter) && objective_id != objective_filter) {
      next
    }
    for (goal in objective$goals %||% list()) {
      goal_id <- as.character(goal$id %||% "")
      if (!nzchar(goal_id)) {
        next
      }
      if (bbmri_has_text(goal_filter) && goal_id != goal_filter) {
        next
      }
      ids <- c(ids, goal_id)
    }
  }
  unique(ids)
}

bbmri_so_goal_parent_objective <- function(spec, goal_id) {
  for (objective in spec$objectives) {
    objective_id <- as.character(objective$id %||% "")
    if (!nzchar(objective_id)) {
      next
    }
    for (goal in objective$goals %||% list()) {
      if (identical(as.character(goal$id %||% ""), goal_id)) {
        return(objective_id)
      }
    }
  }
  NA_character_
}

bbmri_normalize_so_country_code <- function(code) {
  code <- toupper(trimws(as.character(code[[1]])))
  if (!nzchar(code)) {
    return("")
  }
  if (grepl("^HQ-[A-Z]{2}$", code)) {
    return(sub("^HQ-", "", code))
  }
  if (grepl("^[A-Z]{2}$", code)) {
    return(code)
  }
  ""
}

bbmri_so_role_rows <- function(spec, objective_filter = NULL, goal_filter = NULL) {
  rows <- list()
  idx <- 0L
  for (objective in spec$objectives) {
    objective_id <- as.character(objective$id %||% "")
    if (!nzchar(objective_id)) {
      next
    }
    if (bbmri_has_text(objective_filter) && objective_id != objective_filter) {
      next
    }
    for (goal in objective$goals %||% list()) {
      goal_id <- as.character(goal$id %||% "")
      if (!nzchar(goal_id)) {
        next
      }
      if (bbmri_has_text(goal_filter) && goal_id != goal_filter) {
        next
      }
      for (lead in goal$co_leads %||% list()) {
        lead_country <- bbmri_normalize_so_country_code(lead$country %||% "")
        if (!nzchar(lead_country)) {
          next
        }
        idx <- idx + 1L
        rows[[idx]] <- data.frame(
          objective_id = objective_id,
          goal_id = goal_id,
          country = lead_country,
          role = "lead",
          stringsAsFactors = FALSE
        )
      }
      contributors <- unique(toupper(trimws(unlist(goal$contributors_nn %||% character(0), use.names = FALSE))))
      for (country in contributors) {
        if (!nzchar(country) || !grepl("^[A-Z]{2}$", country)) {
          next
        }
        idx <- idx + 1L
        rows[[idx]] <- data.frame(
          objective_id = objective_id,
          goal_id = goal_id,
          country = country,
          role = "contributor",
          stringsAsFactors = FALSE
        )
      }
    }
  }

  if (!length(rows)) {
    return(data.frame(objective_id = character(0), goal_id = character(0), country = character(0), role = character(0), stringsAsFactors = FALSE))
  }
  do.call(rbind, rows)
}

bbmri_so_role_summary <- function(spec, level = c("sg", "so", "global"), objective_filter = NULL, goal_filter = NULL) {
  level <- match.arg(level)
  roles <- bbmri_so_role_rows(spec, objective_filter = objective_filter, goal_filter = goal_filter)
  if (nrow(roles) == 0) {
    return(data.frame(country = character(0), lead_count = integer(0), contributor_count = integer(0), role = character(0), stringsAsFactors = FALSE))
  }

  if (level == "sg") {
    keys <- list(list(field = "goal_id", value = goal_filter))
  } else if (level == "so") {
    keys <- list(list(field = "objective_id", value = objective_filter))
  } else {
    keys <- list(list(field = "global", value = "global"))
  }

  summary <- aggregate(
    list(
      lead_count = as.integer(roles$role == "lead"),
      contributor_count = as.integer(roles$role == "contributor")
    ),
    by = list(country = roles$country),
    FUN = sum
  )
  summary$role <- ifelse(summary$lead_count > 0, "lead", ifelse(summary$contributor_count > 0, "contributor", "base"))
  summary
}

bbmri_so_objective_summary <- function(spec, objective_filter = NULL, goal_filter = NULL) {
  roles <- bbmri_so_role_rows(spec, objective_filter = objective_filter, goal_filter = goal_filter)
  if (nrow(roles) == 0) {
    return(data.frame(objective_id = character(0), country = character(0), lead_count = integer(0), contributor_count = integer(0), stringsAsFactors = FALSE))
  }
  aggregate(
    list(
      lead_count = as.integer(roles$role == "lead"),
      contributor_count = as.integer(roles$role == "contributor")
    ),
    by = list(objective_id = roles$objective_id, country = roles$country),
    FUN = sum
  )
}

bbmri_so_goal_summary <- function(spec, objective_filter = NULL, goal_filter = NULL) {
  roles <- bbmri_so_role_rows(spec, objective_filter = objective_filter, goal_filter = goal_filter)
  if (nrow(roles) == 0) {
    return(data.frame(goal_id = character(0), country = character(0), lead_count = integer(0), contributor_count = integer(0), stringsAsFactors = FALSE))
  }
  aggregate(
    list(
      lead_count = as.integer(roles$role == "lead"),
      contributor_count = as.integer(roles$role == "contributor")
    ),
    by = list(goal_id = roles$goal_id, country = roles$country),
    FUN = sum
  )
}

bbmri_so_target_descriptors <- function(spec, levels = c("sg", "so", "global"), objective_filter = NULL, goal_filter = NULL, modes = c("recolor", "bars")) {
  levels <- intersect(levels, c("sg", "so", "global"))
  modes <- intersect(modes, c("recolor", "bars"))
  descriptors <- list()
  idx <- 0L
  objective_filter_resolved <- objective_filter
  if (!bbmri_has_text(objective_filter_resolved) && bbmri_has_text(goal_filter)) {
    objective_filter_resolved <- bbmri_so_goal_parent_objective(spec, goal_filter)
  }

  for (level in levels) {
    if (level == "sg") {
      goals <- bbmri_so_goal_ids(spec, objective_filter = objective_filter_resolved, goal_filter = goal_filter)
      for (goal_id in goals) {
        idx <- idx + 1L
        descriptors[[idx]] <- list(level = level, mode = "recolor", objective_id = sub("\\.[0-9]+$", "", goal_id), goal_id = goal_id)
      }
      next
    }
    if (level == "global") {
      for (mode in modes) {
        idx <- idx + 1L
        descriptors[[idx]] <- list(level = level, mode = mode, objective_id = NA_character_, goal_id = NA_character_)
      }
      next
    }
    objectives <- bbmri_so_objective_ids(spec, objective_filter = objective_filter_resolved)
    for (objective_id in objectives) {
      for (mode in modes) {
        idx <- idx + 1L
        descriptors[[idx]] <- list(level = level, mode = mode, objective_id = objective_id, goal_id = NA_character_)
      }
    }
  }

  descriptors
}

bbmri_so_target_prefix <- function(output_prefix, level, objective_id = NULL, goal_id = NULL, target_name_style = c("legacy", "short")) {
  target_name_style <- match.arg(target_name_style)
  if (target_name_style == "short") {
    if (level == "global") {
      return(output_prefix)
    }
    if (level == "so") {
      return(objective_id)
    }
    if (level == "sg") {
      return(goal_id)
    }
  }

  if (level == "sg") {
    return(paste0(output_prefix, "-sg-", goal_id))
  }
  if (level == "so") {
    return(paste0(output_prefix, "-so-", objective_id))
  }
  paste0(output_prefix, "-global")
}

bbmri_so_role_fill <- function(summary_df, cfg) {
  if (nrow(summary_df) == 0) {
    return(summary_df)
  }
  summary_df$fill_group <- cfg$so_colors$base_nonmember
  summary_df$fill_group[summary_df$role == "lead"] <- cfg$so_colors$lead
  summary_df$fill_group[summary_df$role == "contributor"] <- cfg$so_colors$contributor
  summary_df
}

bbmri_so_bar_anchor_df <- function(countries, cfg, crs, label_codes, bbox = cfg$standard_bbox) {
  anchor_df <- bbmri_country_anchor_df(countries, crs, label_codes = label_codes)
  label_anchor_df <- bbmri_country_label_df(countries, cfg, crs, label_codes = label_codes)
  if (nrow(anchor_df) == 0) {
    return(anchor_df)
  }

  anchor_df$label_x <- label_anchor_df$x[match(anchor_df$iso_a2, label_anchor_df$iso_a2)]
  anchor_df$label_y <- label_anchor_df$y[match(anchor_df$iso_a2, label_anchor_df$iso_a2)]
  anchor_df$bar_x <- anchor_df$x
  anchor_df$bar_y <- anchor_df$y

  proj_bbox <- bbmri_projected_bbox(bbox, crs)
  use_label_anchor <- is.na(anchor_df$bar_x) | is.na(anchor_df$bar_y) |
    anchor_df$bar_x < proj_bbox[["xmin"]] | anchor_df$bar_x > proj_bbox[["xmax"]] |
    anchor_df$bar_y < proj_bbox[["ymin"]] | anchor_df$bar_y > proj_bbox[["ymax"]]
  if (any(use_label_anchor, na.rm = TRUE)) {
    label_available <- !is.na(anchor_df$label_x) & !is.na(anchor_df$label_y)
    use_label_anchor <- use_label_anchor & label_available
    anchor_df$bar_x[use_label_anchor] <- anchor_df$label_x[use_label_anchor]
    anchor_df$bar_y[use_label_anchor] <- anchor_df$label_y[use_label_anchor]
  }

  anchor_df
}

bbmri_so_global_bar_positions_to_df <- function(positions, cfg) {
  if (is.null(positions) || !length(positions)) {
    return(NULL)
  }
  if (is.data.frame(positions)) {
    pos_df <- positions
  } else if (is.list(positions)) {
    pos_names <- names(positions)
    if (is.null(pos_names) || !length(pos_names)) {
      return(NULL)
    }
    pos_rows <- lapply(seq_along(positions), function(idx) {
      pos <- positions[[idx]]
      if (is.null(pos)) {
        return(NULL)
      }
      iso <- toupper(trimws(pos_names[[idx]]))
      if (!nzchar(iso)) {
        return(NULL)
      }
      lon <- NA_real_
      lat <- NA_real_
      if (is.list(pos) && !is.null(names(pos))) {
        lon_name <- intersect(names(pos), c("lon", "lng", "longitude", "x"))
        lat_name <- intersect(names(pos), c("lat", "latitude", "y"))
        if (length(lon_name) && length(lat_name)) {
          lon <- as.numeric(pos[[lon_name[[1]]]])
          lat <- as.numeric(pos[[lat_name[[1]]]])
        }
      }
      if ((!is.finite(lon) || !is.finite(lat)) && length(pos) >= 2) {
        pos_vec <- as.numeric(unlist(pos, use.names = FALSE))
        lon <- pos_vec[[1]]
        lat <- pos_vec[[2]]
      }
      if (!is.finite(lon) || !is.finite(lat)) {
        return(NULL)
      }
      data.frame(
        iso_a2 = iso,
        lon = lon,
        lat = lat,
        stringsAsFactors = FALSE
      )
    })
    pos_rows <- Filter(Negate(is.null), pos_rows)
    if (!length(pos_rows)) {
      return(NULL)
    }
    pos_df <- do.call(rbind, pos_rows)
  } else {
    return(NULL)
  }

  if (!all(c("iso_a2", "lon", "lat") %in% names(pos_df))) {
    return(NULL)
  }
  pos_df <- pos_df[is.finite(pos_df$lon) & is.finite(pos_df$lat), , drop = FALSE]
  if (nrow(pos_df) == 0) {
    return(NULL)
  }
  pos_sf <- sf::st_as_sf(pos_df, coords = c("lon", "lat"), crs = 4326, remove = FALSE)
  pos_sf <- sf::st_transform(pos_sf, cfg$standard_crs)
  coords <- sf::st_coordinates(pos_sf)
  data.frame(
    iso_a2 = toupper(trimws(pos_df$iso_a2)),
    bar_x = coords[, 1],
    bar_y = coords[, 2],
    stringsAsFactors = FALSE
  )
}

bbmri_apply_global_bar_positions <- function(anchor_df, positions, cfg) {
  if (nrow(anchor_df) == 0) {
    return(anchor_df)
  }
  pos_df <- bbmri_so_global_bar_positions_to_df(positions, cfg)
  if (is.null(pos_df) || nrow(pos_df) == 0) {
    return(anchor_df)
  }
  idx <- match(pos_df$iso_a2, anchor_df$iso_a2)
  hit <- !is.na(idx)
  if (!any(hit)) {
    return(anchor_df)
  }
  anchor_df$bar_x[idx[hit]] <- pos_df$bar_x[hit]
  anchor_df$bar_y[idx[hit]] <- pos_df$bar_y[hit]
  anchor_df
}

bbmri_so_global_bar_frame_box <- function(bar_x, bar_y, bar_width, bar_gap, unit_height, baseline_offset, objective_count, max_total_height, prefix_width = unit_height * 0.45, country_label_offset = unit_height * 1.12, country_label_width = NULL) {
  cluster_width <- objective_count * bar_width + max(0, objective_count - 1) * bar_gap
  start_x <- bar_x - cluster_width / 2
  baseline_y <- bar_y - baseline_offset
  label_y <- baseline_y - unit_height * 0.82
  label_bottom_y <- baseline_y - country_label_offset
  if (is.null(country_label_width) || !is.finite(country_label_width) || country_label_width <= 0) {
    country_label_width <- unit_height * 1.10
  }
  label_half_width <- country_label_width * 0.95 / 2
  list(
    xmin = min(
      start_x - bar_gap * 0.40,
      start_x - bar_gap * 0.50 - prefix_width - bar_gap * 0.03
    ),
    xmax = max(
      start_x + cluster_width + bar_gap * 0.03,
      bar_x + label_half_width + bar_gap * 0.06
    ),
    ymin = min(label_y - unit_height * 0.28, label_bottom_y - unit_height * 0.18),
    ymax = baseline_y + max_total_height * unit_height + unit_height * 0.06
  )
}

bbmri_so_global_bar_country_labels <- function(anchor_df, country_labels, baseline_offset) {
  if (nrow(anchor_df) == 0 || nrow(country_labels) == 0) {
    return(country_labels[0, , drop = FALSE])
  }
  anchor_match <- match(country_labels$iso_a2, anchor_df$iso_a2)
  valid <- !is.na(anchor_match)
  if (!any(valid)) {
    return(country_labels[0, , drop = FALSE])
  }
  labels <- country_labels[valid, , drop = FALSE]
  anchor_match <- anchor_match[valid]
  labels$x <- anchor_df$bar_x[anchor_match]
  labels$y <- anchor_df$bar_y[anchor_match] - baseline_offset
  labels$hjust <- 0.5
  labels$vjust <- 0.5
  labels
}

bbmri_so_resolve_global_bar_positions <- function(anchor_df, summary_df, cfg, bbox, export_sizes, output_variant, objective_order, bar_width, bar_gap, unit_height, baseline_offset, country_label_offset = unit_height * 1.18, country_label_width_map = NULL) {
  if (nrow(anchor_df) == 0) {
    return(anchor_df)
  }
  required <- c("iso_a2", "bar_x", "bar_y")
  if (!all(required %in% names(anchor_df))) {
    stop("Global bar anchors must provide iso_a2, bar_x, and bar_y.", call. = FALSE)
  }

  proj_bbox <- bbmri_projected_bbox(bbox, cfg$standard_crs)
  units_per_px <- (proj_bbox[["xmax"]] - proj_bbox[["xmin"]]) / bbmri_output_width_px(export_sizes, output_variant)
  touch_margin <- units_per_px * 4

  counts <- vapply(anchor_df$iso_a2, function(iso) {
    row <- summary_df[summary_df$country == iso, , drop = FALSE]
    if (nrow(row) == 0) {
      return(0)
    }
    max(row$lead_count[[1]] + row$contributor_count[[1]], 1)
  }, numeric(1))
  order_idx <- order(-counts, -anchor_df$bar_y, anchor_df$iso_a2)

  box_separated <- function(box, other, margin) {
    box$xmax < other$xmin - margin ||
      other$xmax < box$xmin - margin ||
      box$ymax < other$ymin - margin ||
      other$ymax < box$ymin - margin
  }

  chosen_boxes <- list()
  for (idx in order_idx) {
    x <- anchor_df$bar_x[[idx]]
    y <- anchor_df$bar_y[[idx]]
    max_total_height <- counts[[idx]]
    iso <- anchor_df$iso_a2[[idx]]
    label_width <- if (!is.null(country_label_width_map) && iso %in% names(country_label_width_map)) {
      as.numeric(country_label_width_map[[iso]])
    } else {
      NA_real_
    }
    best_box <- NULL

    for (iter in seq_len(120L)) {
      box <- bbmri_so_global_bar_frame_box(
        x,
        y,
        bar_width = bar_width,
        bar_gap = bar_gap,
        unit_height = unit_height,
        baseline_offset = baseline_offset,
        objective_count = length(objective_order),
        max_total_height = max_total_height,
        country_label_offset = country_label_offset,
        country_label_width = label_width
      )

      overlaps <- chosen_boxes[!vapply(chosen_boxes, box_separated, logical(1), other = box, margin = touch_margin)]
      if (!length(overlaps)) {
        best_box <- box
        break
      }

      move_x <- 0
      move_y <- 0
      overlap_count <- length(overlaps)
      box_cx <- (box$xmin + box$xmax) / 2
      box_cy <- (box$ymin + box$ymax) / 2
      for (other in overlaps) {
        other_cx <- (other$xmin + other$xmax) / 2
        other_cy <- (other$ymin + other$ymax) / 2
        overlap_x <- min(box$xmax, other$xmax) - max(box$xmin, other$xmin) + touch_margin
        overlap_y <- min(box$ymax, other$ymax) - max(box$ymin, other$ymin) + touch_margin
        step_x <- max(overlap_x * 0.35, units_per_px * 4)
        step_y <- max(overlap_y * 0.35, units_per_px * 4)
        move_x <- move_x + if (box_cx <= other_cx) -step_x else step_x
        move_y <- move_y + if (box_cy <= other_cy) -step_y else step_y
      }

      x <- x + move_x / overlap_count
      y <- y + move_y / overlap_count
      best_box <- box
    }

    anchor_df$bar_x[[idx]] <- x
    anchor_df$bar_y[[idx]] <- y
    chosen_boxes[[length(chosen_boxes) + 1L]] <- if (is.null(best_box)) {
      bbmri_so_global_bar_frame_box(
        x,
          y,
          bar_width = bar_width,
          bar_gap = bar_gap,
          unit_height = unit_height,
          baseline_offset = baseline_offset,
          objective_count = length(objective_order),
          max_total_height = max_total_height,
          country_label_offset = country_label_offset,
          country_label_width = label_width
        )
      } else {
      best_box
    }
  }

  if (nrow(anchor_df) > 1L) {
    for (iter in seq_len(80L)) {
      boxes <- lapply(seq_len(nrow(anchor_df)), function(idx) {
        bbmri_so_global_bar_frame_box(
          anchor_df$bar_x[[idx]],
          anchor_df$bar_y[[idx]],
          bar_width = bar_width,
          bar_gap = bar_gap,
          unit_height = unit_height,
          baseline_offset = baseline_offset,
          objective_count = length(objective_order),
          max_total_height = counts[[idx]],
          country_label_offset = country_label_offset,
          country_label_width = if (!is.null(country_label_width_map) && anchor_df$iso_a2[[idx]] %in% names(country_label_width_map)) as.numeric(country_label_width_map[[anchor_df$iso_a2[[idx]]]]) else NA_real_
        )
      })

      overlap_pairs <- list()
      pair_idx <- 0L
      for (i in seq_along(boxes)) {
        for (j in seq_len(i - 1L)) {
          if (box_separated(boxes[[i]], boxes[[j]], touch_margin)) {
            next
          }
          pair_idx <- pair_idx + 1L
          overlap_pairs[[pair_idx]] <- c(i, j)
        }
      }
      if (!length(overlap_pairs)) {
        break
      }

      shift_x <- numeric(nrow(anchor_df))
      shift_y <- numeric(nrow(anchor_df))
      for (pair in overlap_pairs) {
        i <- pair[[1]]
        j <- pair[[2]]
        box <- boxes[[i]]
        other <- boxes[[j]]
        overlap_x <- min(box$xmax, other$xmax) - max(box$xmin, other$xmin) + touch_margin
        overlap_y <- min(box$ymax, other$ymax) - max(box$ymin, other$ymin) + touch_margin
        box_cx <- (box$xmin + box$xmax) / 2
        box_cy <- (box$ymin + box$ymax) / 2
        other_cx <- (other$xmin + other$xmax) / 2
        other_cy <- (other$ymin + other$ymax) / 2

        if (overlap_x <= overlap_y) {
          step <- max(overlap_x / 3, units_per_px * 3)
          direction <- if (box_cx <= other_cx) -1 else 1
          shift_x[[i]] <- shift_x[[i]] + direction * step
          shift_x[[j]] <- shift_x[[j]] - direction * step
        } else {
          step <- max(overlap_y / 3, units_per_px * 3)
          direction <- if (box_cy <= other_cy) -1 else 1
          shift_y[[i]] <- shift_y[[i]] + direction * step
          shift_y[[j]] <- shift_y[[j]] - direction * step
        }
      }

      damp <- 0.40
      anchor_df$bar_x <- anchor_df$bar_x + shift_x * damp
      anchor_df$bar_y <- anchor_df$bar_y + shift_y * damp
    }
  }

  anchor_df
}

bbmri_so_prepare_layers <- function(bbox, cfg) {
  bbmri_prepare_classic_layers(bbox, cfg, fill_fn = bbmri_assign_standard_country_fill, include_rivers = FALSE)
}

bbmri_so_make_recolor_plot <- function(spec, level, objective_filter = NULL, goal_filter = NULL, output_variant = "med", bbox = NULL, export_sizes = NULL, cfg = NULL, country_label_codes = NULL) {
  bbmri_require_packages(c("ggplot2", "sf", "cowplot"))
  if (is.null(cfg)) {
    cfg <- bbmri_map_config()
  }
  if (is.null(bbox)) {
    bbox <- cfg$standard_bbox
  }
  if (is.null(export_sizes)) {
    export_sizes <- cfg$export_sizes
  }
  if (level == "global") {
    objective_filter <- NULL
    goal_filter <- NULL
  }
  layers <- bbmri_so_prepare_layers(bbox, cfg)
  if (level == "sg") {
    summary_df <- bbmri_so_role_summary(spec, level = level, objective_filter = objective_filter, goal_filter = goal_filter)
  } else {
    summary_df <- bbmri_so_role_summary(spec, level = level, objective_filter = objective_filter, goal_filter = goal_filter)
  }
  if (nrow(summary_df) > 0) {
    summary_df <- bbmri_so_role_fill(summary_df, cfg)
    layer_idx <- match(summary_df$country, layers$countries$iso_a2)
    hit <- !is.na(layer_idx)
    layers$countries$fill_group[layer_idx[hit]] <- summary_df$fill_group[hit]
  }

  if (is.null(country_label_codes)) {
    country_label_codes <- cfg$standard_country_labels
  }
  country_labels <- bbmri_country_label_df(layers$countries, cfg, cfg$standard_crs, label_codes = country_label_codes)
  if (identical(output_variant, "small")) {
    country_labels <- bbmri_apply_label_offsets(country_labels, cfg$standard_small_label_offsets)
  }
  plot <- bbmri_add_classic_base(
    ggplot2::ggplot(),
    layers = layers,
    bbox = bbox,
    crs = cfg$standard_crs,
    cfg = cfg,
    output_variant = output_variant
  ) + ggplot2::scale_fill_identity()
  plot <- plot + ggplot2::theme(plot.margin = ggplot2::margin(0, 0, 0, 0))
  plot <- plot + ggplot2::theme(plot.margin = ggplot2::margin(0, 0, 0, 0))
  plot <- plot + ggplot2::theme(plot.margin = ggplot2::margin(0, 0, 0, 0))
  plot <- plot + bbmri_geom_text_halo(
    data = country_labels,
    mapping = ggplot2::aes(x = x, y = y, label = label),
    size = bbmri_country_label_style_for_output(cfg, output_variant)$size,
    bbox = bbox,
    crs = cfg$standard_crs,
    output_width_px = bbmri_output_width_px(export_sizes, output_variant),
    family = bbmri_font_family(),
    inner_halo_px = bbmri_country_label_style_for_output(cfg, output_variant)$inner_halo_px,
    outer_halo_px = bbmri_country_label_style_for_output(cfg, output_variant)$outer_halo_px,
    alpha = bbmri_country_label_style_for_output(cfg, output_variant)$alpha
  )

  legend_entries <- data.frame(
    label = c(
      "Lead",
      "Contributor",
      "Member (without SO involvement)",
      "Observer (without SO involvement)"
    ),
    fill = c(
      cfg$so_colors$lead,
      cfg$so_colors$contributor,
      cfg$so_colors$base_member,
      cfg$so_colors$base_observer
    ),
    colour = c(
      cfg$so_colors$bar_border,
      cfg$so_colors$bar_border,
      cfg$so_colors$bar_border,
      cfg$so_colors$bar_border
    ),
    alpha = c(0.88, 0.88, 0.88, 0.88),
    linewidth = c(0.25, 0.25, 0.25, 0.25),
    stringsAsFactors = FALSE
  )
  plot <- bbmri_add_rect_legend(
    plot = plot,
    entries = legend_entries,
    bbox = bbox,
    crs = cfg$standard_crs,
    box = list(x = 0.03, y = 0.05, width = 0.23, height = 0.145),
    title = "Strategic involvement",
    text_size = 2.0,
    row_start_frac = 0.69,
    row_step_frac = 0.155
  )

  title_text <- switch(
    level,
    sg = if (bbmri_has_text(goal_filter)) paste0(goal_filter) else "Strategic goal",
    so = if (bbmri_has_text(objective_filter)) paste0(objective_filter) else "Strategic objective",
    global = "Strategic objectives overview"
  )
  plot + ggplot2::labs(title = title_text)
}

bbmri_so_make_bars_plot <- function(spec, level, objective_filter = NULL, goal_filter = NULL, output_variant = "med", bbox = NULL, export_sizes = NULL, cfg = NULL, country_label_codes = NULL, objective_order = NULL) {
  bbmri_require_packages(c("ggplot2", "sf", "cowplot"))
  if (level == "sg") {
    stop("Bars mode is not defined for per-SG views.", call. = FALSE)
  }
  if (is.null(cfg)) {
    cfg <- bbmri_map_config()
  }
  if (is.null(bbox)) {
    bbox <- cfg$standard_bbox
  }
  if (is.null(export_sizes)) {
    export_sizes <- cfg$export_sizes
  }
  if (level == "global") {
    objective_filter <- NULL
    goal_filter <- NULL
  }

  layers <- bbmri_so_prepare_layers(bbox, cfg)
  summary_df <- bbmri_so_objective_summary(spec, objective_filter = objective_filter, goal_filter = goal_filter)
  summary_df <- bbmri_so_role_fill(summary_df, cfg)

  proj_bbox <- bbmri_projected_bbox(bbox, cfg$standard_crs)
  plot <- bbmri_add_classic_base(
    ggplot2::ggplot(),
    layers = layers,
    bbox = bbox,
    crs = cfg$standard_crs,
    cfg = cfg,
    output_variant = output_variant
  ) + ggplot2::scale_fill_identity()
  plot <- plot + ggplot2::theme(plot.margin = ggplot2::margin(0, 0, 0, 0))

  width_units <- proj_bbox[["xmax"]] - proj_bbox[["xmin"]]
  height_units <- proj_bbox[["ymax"]] - proj_bbox[["ymin"]]
  bar_style <- cfg$so_bar_style
  global_bar_style <- cfg$so_global_bar_style %||% list(width_scale = 1, height_scale = 1)
  width_scale <- if (level == "global") as.numeric(global_bar_style$width_scale %||% 1) else 1
  height_scale <- if (level == "global") as.numeric(global_bar_style$height_scale %||% 1) else 1
  bar_width <- width_units * bar_style$bar_width_frac * width_scale
  bar_gap <- width_units * bar_style$bar_gap_frac * width_scale
  unit_height <- height_units * bar_style$unit_height_frac * height_scale
  baseline_offset <- height_units * bar_style$baseline_offset_frac
  country_label_offset <- unit_height * 1.18
  manual_global_positions <- NULL
  if (level == "global" && !is.null(cfg$so_global_bar_positions) && output_variant %in% names(cfg$so_global_bar_positions)) {
    manual_global_positions <- cfg$so_global_bar_positions[[output_variant]]
  }

  if (is.null(country_label_codes)) {
    country_label_codes <- cfg$standard_country_labels
  }
  if (level == "global") {
    bar_country_codes <- unique(summary_df$country)
    country_label_codes <- setdiff(country_label_codes, bar_country_codes)
  } else {
    bar_country_codes <- character(0)
  }
  country_labels <- bbmri_country_label_df(layers$countries, cfg, cfg$standard_crs, label_codes = country_label_codes)
  if (identical(output_variant, "small")) {
    country_labels <- bbmri_apply_label_offsets(country_labels, cfg$standard_small_label_offsets)
  }

  anchor_df <- bbmri_so_bar_anchor_df(layers$countries, cfg, cfg$standard_crs, unique(summary_df$country), bbox = bbox)
  if (level == "global" && nrow(anchor_df) > 0) {
    if (!is.null(manual_global_positions) && length(manual_global_positions) > 0) {
      anchor_df <- bbmri_apply_global_bar_positions(anchor_df, manual_global_positions, cfg)
    }
  }

  bar_country_labels <- NULL
  bar_country_label_width_map <- NULL
  bar_country_label_pool <- NULL
  if (level == "global" && nrow(anchor_df) > 0) {
    all_country_labels <- bbmri_country_label_df(layers$countries, cfg, cfg$standard_crs, label_codes = cfg$standard_country_labels)
    if (identical(output_variant, "small")) {
      all_country_labels <- bbmri_apply_label_offsets(all_country_labels, cfg$standard_small_label_offsets)
    }
    bar_country_label_pool <- all_country_labels[all_country_labels$iso_a2 %in% unique(summary_df$country), , drop = FALSE]
    if (nrow(bar_country_label_pool) > 0) {
      bar_country_label_width_map <- setNames(
        pmax(
          bbmri_country_label_style_for_output(cfg, output_variant)$size * 1.05,
          nchar(bar_country_label_pool$label) * bbmri_country_label_style_for_output(cfg, output_variant)$size * 0.24
        ),
        bar_country_label_pool$iso_a2
      )
    }
  }

  if (nrow(anchor_df) > 0) {
    bar_rows <- list()
    row_idx <- 0L

    if (is.null(objective_order) || !length(objective_order)) {
      objective_order <- if (level == "global") {
        bbmri_so_objective_ids(spec)
      } else {
        unique(summary_df$objective_id)
      }
    }
    if (!length(objective_order)) {
      objective_order <- unique(summary_df$objective_id)
    }
    objective_order <- unique(objective_order)

    if (level == "global" && isTRUE(cfg$so_global_bar_style$resolve_positions) && (is.null(manual_global_positions) || !length(manual_global_positions))) {
      anchor_df <- bbmri_so_resolve_global_bar_positions(
        anchor_df = anchor_df,
        summary_df = summary_df,
        cfg = cfg,
        bbox = bbox,
        export_sizes = export_sizes,
        output_variant = output_variant,
        objective_order = objective_order,
        bar_width = bar_width,
        bar_gap = bar_gap,
        unit_height = unit_height,
        baseline_offset = baseline_offset,
        country_label_offset = country_label_offset,
        country_label_width_map = bar_country_label_width_map
      )
    }

    if (level == "global" && !is.null(bar_country_label_pool) && nrow(bar_country_label_pool) > 0) {
      bar_country_labels <- bbmri_so_global_bar_country_labels(anchor_df, bar_country_label_pool, baseline_offset)
      if (nrow(bar_country_labels) > 0 && !is.null(bar_country_label_width_map)) {
        bar_country_label_width_map <- bar_country_label_width_map[bar_country_labels$iso_a2]
      }
      if (nrow(country_labels) > 0) {
        bar_country_iso <- unique(bar_country_labels$iso_a2)
        country_labels <- country_labels[!country_labels$iso_a2 %in% bar_country_iso, , drop = FALSE]
      }
    }

    slot_rows <- list()
    slot_idx <- 0L
    digit_rows <- list()
    digit_idx <- 0L
    prefix_rows <- list()
    prefix_idx <- 0L
    frame_rows <- list()
    frame_idx <- 0L

    for (anchor in seq_len(nrow(anchor_df))) {
      iso <- anchor_df$iso_a2[[anchor]]
      country_summary <- summary_df[summary_df$country == iso, , drop = FALSE]
      if (nrow(country_summary) == 0) {
        next
      }
      baseline_y <- anchor_df$bar_y[[anchor]] - baseline_offset
      max_total_height <- max(country_summary$lead_count + country_summary$contributor_count, na.rm = TRUE)
      if (!is.finite(max_total_height) || max_total_height < 1) {
        max_total_height <- 1
      }

      if (level == "so") {
        row_sum <- country_summary[1, , drop = FALSE]
        bar_total <- row_sum$lead_count[[1]] + row_sum$contributor_count[[1]]
        if (bar_total <= 0) {
          next
        }
        row_idx <- row_idx + 1L
        bar_rows[[row_idx]] <- data.frame(
          xmin = anchor_df$bar_x[[anchor]] - bar_width / 2,
          xmax = anchor_df$bar_x[[anchor]] + bar_width / 2,
          ymin = baseline_y,
          ymax = baseline_y + row_sum$lead_count[[1]] * unit_height,
          fill = cfg$so_colors$lead,
          role = "lead",
          country = iso,
          stringsAsFactors = FALSE
        )
        if (row_sum$contributor_count[[1]] > 0) {
          row_idx <- row_idx + 1L
          bar_rows[[row_idx]] <- data.frame(
            xmin = anchor_df$bar_x[[anchor]] - bar_width / 2,
            xmax = anchor_df$bar_x[[anchor]] + bar_width / 2,
            ymin = baseline_y + row_sum$lead_count[[1]] * unit_height,
            ymax = baseline_y + bar_total * unit_height,
            fill = cfg$so_colors$contributor,
            role = "contributor",
            country = iso,
            stringsAsFactors = FALSE
          )
        }
      } else {
        cluster_width <- length(objective_order) * bar_width + max(0, length(objective_order) - 1) * bar_gap
        start_x <- anchor_df$bar_x[[anchor]] - cluster_width / 2
        label_y <- baseline_y - unit_height * 0.85
        prefix_idx <- prefix_idx + 1L
        prefix_rows[[prefix_idx]] <- data.frame(
          x = start_x - unit_height * 0.45,
          y = label_y,
          label = "SO: ",
          colour = "#303030",
          hjust = 1,
          stringsAsFactors = FALSE
        )
        for (o_idx in seq_along(objective_order)) {
          objective_id <- objective_order[[o_idx]]
          obj_row <- country_summary[country_summary$objective_id == objective_id, , drop = FALSE]
          lead_ct <- if (nrow(obj_row) == 0) 0 else obj_row$lead_count[[1]]
          contrib_ct <- if (nrow(obj_row) == 0) 0 else obj_row$contributor_count[[1]]
          slot_x <- start_x + (o_idx - 1) * (bar_width + bar_gap)
          x1 <- slot_x
          x2 <- x1 + bar_width
          slot_idx <- slot_idx + 1L
          slot_rows[[slot_idx]] <- data.frame(
            xmin = x1,
            xmax = x2,
            ymin = baseline_y,
            ymax = baseline_y + unit_height,
            fill = grDevices::adjustcolor("#d9d9d9", alpha.f = 0.18),
            role = "slot",
            country = iso,
            objective_id = objective_id,
            stringsAsFactors = FALSE
          )
          digit_idx <- digit_idx + 1L
          digit_rows[[digit_idx]] <- data.frame(
            x = x1 + bar_width / 2,
            y = label_y,
            label = sub("^SO", "", objective_id),
            colour = if (lead_ct + contrib_ct > 0) "#303030" else "#8a8a8a",
            hjust = 0.5,
            stringsAsFactors = FALSE
          )
          if (lead_ct + contrib_ct <= 0) {
            next
          }
          if (lead_ct > 0) {
            row_idx <- row_idx + 1L
            bar_rows[[row_idx]] <- data.frame(
              xmin = x1,
              xmax = x2,
              ymin = baseline_y,
              ymax = baseline_y + lead_ct * unit_height,
              fill = cfg$so_colors$lead,
              role = "lead",
              country = iso,
              objective_id = objective_id,
              stringsAsFactors = FALSE
            )
          }
          if (contrib_ct > 0) {
            row_idx <- row_idx + 1L
            bar_rows[[row_idx]] <- data.frame(
              xmin = x1,
              xmax = x2,
              ymin = baseline_y + lead_ct * unit_height,
              ymax = baseline_y + (lead_ct + contrib_ct) * unit_height,
              fill = cfg$so_colors$contributor,
              role = "contributor",
              country = iso,
              objective_id = objective_id,
              stringsAsFactors = FALSE
            )
          }
        }
      }

      if (level == "global") {
        frame_box <- bbmri_so_global_bar_frame_box(
          bar_x = anchor_df$bar_x[[anchor]],
          bar_y = anchor_df$bar_y[[anchor]],
          bar_width = bar_width,
          bar_gap = bar_gap,
          unit_height = unit_height,
          baseline_offset = baseline_offset,
          objective_count = length(objective_order),
          max_total_height = max_total_height,
          country_label_offset = country_label_offset,
          country_label_width = if (!is.null(bar_country_label_width_map) && iso %in% names(bar_country_label_width_map)) {
            as.numeric(bar_country_label_width_map[[iso]])
          } else {
            NULL
          }
        )
        frame_idx <- frame_idx + 1L
        frame_rows[[frame_idx]] <- data.frame(
          xmin = frame_box$xmin,
          xmax = frame_box$xmax,
          ymin = frame_box$ymin,
          ymax = frame_box$ymax,
          stringsAsFactors = FALSE
        )
      }
    }

    if (level == "global" && length(frame_rows) > 0) {
      frames_df <- do.call(rbind, frame_rows)
      plot <- plot +
        ggplot2::geom_rect(
          data = frames_df,
          ggplot2::aes(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax),
          fill = NA,
          colour = "#000000",
          linewidth = 0.12
        )
    }
    if (length(bar_rows) > 0) {
      bars_df <- do.call(rbind, bar_rows)
      plot <- plot +
        ggplot2::geom_rect(
          data = bars_df,
          ggplot2::aes(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax, fill = fill),
          colour = cfg$so_colors$bar_border,
          linewidth = bar_style$outline_linewidth,
          alpha = bar_style$alpha
        ) +
        ggplot2::scale_fill_identity()
    }
    if (isTRUE(global_bar_style$show_slots) && length(slot_rows) > 0) {
      slots_df <- do.call(rbind, slot_rows)
      plot <- plot +
        ggplot2::geom_rect(
          data = slots_df,
          ggplot2::aes(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax, fill = fill),
          colour = grDevices::adjustcolor(cfg$so_colors$bar_border, alpha.f = 0.35),
          linewidth = bar_style$outline_linewidth * 0.8,
          alpha = 0.75
        ) +
        ggplot2::scale_fill_identity()
    }
    if (length(digit_rows) > 0) {
      digits_df <- do.call(rbind, digit_rows)
      plot <- plot +
        ggplot2::geom_text(
          data = digits_df,
          ggplot2::aes(x = x, y = y, label = label, colour = colour, hjust = hjust),
          family = bbmri_font_family(),
          size = 2.0,
          fontface = "plain",
          vjust = 1,
          show.legend = FALSE
        ) +
        ggplot2::scale_colour_identity()
    }
    if (length(prefix_rows) > 0) {
      prefix_df <- do.call(rbind, prefix_rows)
      plot <- plot +
        ggplot2::geom_text(
          data = prefix_df,
          ggplot2::aes(x = x, y = y, label = label, colour = colour, hjust = hjust),
          family = bbmri_font_family(),
          size = 2.0,
          fontface = "plain",
          vjust = 1,
          show.legend = FALSE
        ) +
        ggplot2::scale_colour_identity()
    }
  }

  if (level == "global" && !is.null(bar_country_labels) && nrow(bar_country_labels) > 0) {
    plot <- plot + bbmri_geom_text_halo(
      data = bar_country_labels,
      mapping = ggplot2::aes(x = x, y = y, label = label, hjust = hjust, vjust = vjust),
      size = bbmri_country_label_style_for_output(cfg, output_variant)$size,
      bbox = bbox,
      crs = cfg$standard_crs,
      output_width_px = bbmri_output_width_px(export_sizes, output_variant),
      family = bbmri_font_family(),
      inner_halo_px = bbmri_country_label_style_for_output(cfg, output_variant)$inner_halo_px,
      outer_halo_px = bbmri_country_label_style_for_output(cfg, output_variant)$outer_halo_px,
      alpha = bbmri_country_label_style_for_output(cfg, output_variant)$alpha
    )
  }

  plot <- plot + bbmri_geom_text_halo(
    data = country_labels,
    mapping = ggplot2::aes(x = x, y = y, label = label),
    size = bbmri_country_label_style_for_output(cfg, output_variant)$size,
    bbox = bbox,
    crs = cfg$standard_crs,
    output_width_px = bbmri_output_width_px(export_sizes, output_variant),
    family = bbmri_font_family(),
    inner_halo_px = bbmri_country_label_style_for_output(cfg, output_variant)$inner_halo_px,
    outer_halo_px = bbmri_country_label_style_for_output(cfg, output_variant)$outer_halo_px,
    alpha = bbmri_country_label_style_for_output(cfg, output_variant)$alpha
  )

  legend_entries <- data.frame(
    label = c("Lead", "Contributor", "Member", "Observer"),
    fill = c(cfg$so_colors$lead, cfg$so_colors$contributor, cfg$so_colors$base_member, cfg$so_colors$base_observer),
    colour = c(cfg$so_colors$bar_border, cfg$so_colors$bar_border, cfg$so_colors$bar_border, cfg$so_colors$bar_border),
    alpha = c(0.88, 0.88, 0.88, 0.88),
    linewidth = c(0.25, 0.25, 0.25, 0.25),
    stringsAsFactors = FALSE
  )
  plot <- bbmri_add_rect_legend(
    plot = plot,
    entries = legend_entries,
    bbox = bbox,
    crs = cfg$standard_crs,
    box = list(x = 0.03, y = 0.05, width = 0.27, height = 0.145),
    title = "Strategic involvement",
    text_size = 1.95,
    row_start_frac = 0.69,
    row_step_frac = 0.155
  )

  plot + ggplot2::labs(title = if (level == "global") "Strategic objectives overview" else if (bbmri_has_text(objective_filter)) objective_filter else "Strategic objectives")
}
bbmri_save_strategic_objectives_formats <- function(spec, output_dir, output_prefix, levels = c("sg", "so", "global"), modes = c("recolor", "bars"), objective_filter = NULL, goal_filter = NULL, country_label_codes = NULL, cfg = NULL, objective_order = NULL, output_variants = NULL, output_formats = NULL, target_name_style = c("legacy", "short")) {
  if (is.null(cfg)) {
    cfg <- bbmri_map_config()
  }
  target_name_style <- match.arg(target_name_style)
  descriptors <- bbmri_so_target_descriptors(spec, levels = levels, objective_filter = objective_filter, goal_filter = goal_filter, modes = modes)
  if (!length(descriptors)) {
    stop("No strategic-objectives render targets matched the requested filters.", call. = FALSE)
  }
  for (descriptor in descriptors) {
    level <- descriptor$level
    mode <- descriptor$mode
    objective_id <- descriptor$objective_id
    goal_id <- descriptor$goal_id
    if (level == "sg" && !identical(mode, "recolor")) {
      next
    }
    target_prefix <- paste0(
      bbmri_so_target_prefix(
        output_prefix = output_prefix,
        level = level,
        objective_id = objective_id,
        goal_id = goal_id,
        target_name_style = target_name_style
      ),
      "-",
      mode
    )
    bbmri_save_plot_formats_from_builder(
      build_plot = function(output_variant) {
        if (identical(mode, "recolor")) {
          bbmri_so_make_recolor_plot(
            spec = spec,
            level = level,
            objective_filter = objective_id,
            goal_filter = goal_id,
            output_variant = output_variant,
            cfg = cfg,
            country_label_codes = country_label_codes
          )
        } else {
          bbmri_so_make_bars_plot(
            spec = spec,
            level = level,
            objective_filter = objective_id,
            goal_filter = goal_id,
            output_variant = output_variant,
            cfg = cfg,
            country_label_codes = country_label_codes,
            objective_order = objective_order
        )
    }
      },
      output_dir = output_dir,
      prefix = target_prefix,
      export_sizes = cfg$export_sizes,
      output_variants = output_variants,
      output_formats = output_formats,
      include_vector = is.null(output_variants) && is.null(output_formats)
    )
  }
  invisible(TRUE)
}
