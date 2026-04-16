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

bbmri_so_role_fill <- function(summary_df, cfg) {
  if (nrow(summary_df) == 0) {
    return(summary_df)
  }
  summary_df$fill_group <- cfg$so_colors$base_nonmember
  summary_df$fill_group[summary_df$role == "lead"] <- cfg$so_colors$lead
  summary_df$fill_group[summary_df$role == "contributor"] <- cfg$so_colors$contributor
  summary_df
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

  if (nrow(summary_df) > 0) {
    plot <- bbmri_add_rect_legend(
      plot = plot,
      entries = data.frame(
        label = c("Lead", "Contributor"),
        fill = c(cfg$so_colors$lead, cfg$so_colors$contributor),
        colour = c(cfg$so_colors$bar_border, cfg$so_colors$bar_border),
        alpha = c(0.88, 0.88),
        linewidth = c(0.25, 0.25),
        stringsAsFactors = FALSE
      ),
      bbox = bbox,
      crs = cfg$standard_crs,
      box = list(x = 0.03, y = 0.05, width = 0.22, height = 0.12),
      title = "Strategic involvement",
      text_size = 2.1
    )
  }

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

  anchor_df <- bbmri_country_anchor_df(layers$countries, cfg$standard_crs, label_codes = unique(summary_df$country))
  if (nrow(anchor_df) > 0) {
    proj_bbox <- bbmri_projected_bbox(bbox, cfg$standard_crs)
    width_units <- proj_bbox[["xmax"]] - proj_bbox[["xmin"]]
    height_units <- proj_bbox[["ymax"]] - proj_bbox[["ymin"]]
    bar_style <- cfg$so_bar_style
    global_bar_style <- cfg$so_global_bar_style %||% list(width_scale = 1, height_scale = 1)
    if (level == "global") {
      bar_style <- modifyList(bar_style, list())
    }
    width_scale <- if (level == "global") as.numeric(global_bar_style$width_scale %||% 1) else 1
    height_scale <- if (level == "global") as.numeric(global_bar_style$height_scale %||% 1) else 1
    bar_width <- width_units * bar_style$bar_width_frac * width_scale
    bar_gap <- width_units * bar_style$bar_gap_frac * width_scale
    unit_height <- height_units * bar_style$unit_height_frac * height_scale
    baseline_offset <- height_units * bar_style$baseline_offset_frac
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
    label_rows <- list()
    label_idx <- 0L

    for (anchor in seq_len(nrow(anchor_df))) {
      iso <- anchor_df$iso_a2[[anchor]]
      country_summary <- summary_df[summary_df$country == iso, , drop = FALSE]
      if (nrow(country_summary) == 0) {
        next
      }
      baseline_y <- anchor_df$y[[anchor]] - baseline_offset
      if (level == "so") {
        row_sum <- country_summary[1, , drop = FALSE]
        bar_total <- row_sum$lead_count[[1]] + row_sum$contributor_count[[1]]
        if (bar_total <= 0) {
          next
        }
        row_idx <- row_idx + 1L
        bar_rows[[row_idx]] <- data.frame(
          xmin = anchor_df$x[[anchor]] - bar_width / 2,
          xmax = anchor_df$x[[anchor]] + bar_width / 2,
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
            xmin = anchor_df$x[[anchor]] - bar_width / 2,
            xmax = anchor_df$x[[anchor]] + bar_width / 2,
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
        start_x <- anchor_df$x[[anchor]] - cluster_width / 2
        label_y <- baseline_y - unit_height * 0.85
        label_idx <- label_idx + 1L
        label_rows[[label_idx]] <- data.frame(
          x = anchor_df$x[[anchor]],
          y = label_y,
          label = paste0("SO: ", paste(sub("^SO", "", objective_order), collapse = "")),
          colour = "#303030",
          hjust = 0.5,
          stringsAsFactors = FALSE
        )
        for (o_idx in seq_along(objective_order)) {
          objective_id <- objective_order[[o_idx]]
          obj_row <- country_summary[country_summary$objective_id == objective_id, , drop = FALSE]
          lead_ct <- if (nrow(obj_row) == 0) 0 else obj_row$lead_count[[1]]
          contrib_ct <- if (nrow(obj_row) == 0) 0 else obj_row$contributor_count[[1]]
          if (lead_ct + contrib_ct <= 0) {
            next
          }
          x1 <- start_x + (o_idx - 1) * (bar_width + bar_gap)
          x2 <- x1 + bar_width
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
    if (length(label_rows) > 0) {
      labels_df <- do.call(rbind, label_rows)
      plot <- plot +
        ggplot2::geom_text(
          data = labels_df,
          ggplot2::aes(x = x, y = y, label = label, colour = colour, hjust = hjust),
          family = "mono",
          size = 2.0,
          fontface = "plain",
          vjust = 1,
          show.legend = FALSE
        ) +
        ggplot2::scale_colour_identity()
    }
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
    label = c("Lead", "Contributor"),
    fill = c(cfg$so_colors$lead, cfg$so_colors$contributor),
    colour = c(cfg$so_colors$bar_border, cfg$so_colors$bar_border),
    alpha = c(0.88, 0.88),
    linewidth = c(0.25, 0.25),
    stringsAsFactors = FALSE
  )
  plot <- bbmri_add_rect_legend(
    plot = plot,
    entries = legend_entries,
    bbox = bbox,
    crs = cfg$standard_crs,
    box = list(x = 0.03, y = 0.05, width = 0.22, height = 0.12),
    title = "Strategic involvement",
    text_size = 2.1
  )
  plot + ggplot2::labs(title = if (level == "global") "Strategic objectives overview" else if (bbmri_has_text(objective_filter)) objective_filter else "Strategic objectives")
}

bbmri_save_strategic_objectives_formats <- function(spec, output_dir, output_prefix, levels = c("sg", "so", "global"), modes = c("recolor", "bars"), objective_filter = NULL, goal_filter = NULL, country_label_codes = NULL, cfg = NULL, objective_order = NULL) {
  if (is.null(cfg)) {
    cfg <- bbmri_map_config()
  }
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
    target_prefix <- if (level == "sg") {
      paste0(output_prefix, "-sg-", goal_id, "-", mode)
    } else if (level == "so") {
      paste0(output_prefix, "-so-", objective_id, "-", mode)
    } else {
      paste0(output_prefix, "-global-", mode)
    }
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
      export_sizes = cfg$export_sizes
    )
  }
  invisible(TRUE)
}
