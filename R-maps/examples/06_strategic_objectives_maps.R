# Render the strategic-objectives family from the TOML scaffold.
#
# This is the recommended RStudio entrypoint for humans who want to inspect or
# extend the SO/SG framework without going through the shell wrapper.

source(file.path("R-maps", "examples", "00_setup.R"))
source(file.path(script_dir, "strategic_objectives_common.R"))

spec_path <- file.path(script_dir, "data", "strategic-objectives-template.toml")
strategy_spec <- bbmri_load_strategic_objectives_spec(spec_path)

bbmri_so_parse_cli <- function() {
  trailing <- commandArgs(trailingOnly = TRUE)
  options <- list()
  targets <- character(0)
  for (arg in trailing) {
    if (!startsWith(arg, "--")) {
      targets <- c(targets, arg)
      next
    }
    body <- substring(arg, 3L)
    eq_pos <- regexpr("=", body, fixed = TRUE)[[1]]
    if (eq_pos < 0) {
      key <- gsub("-", "_", body, fixed = TRUE)
      value <- TRUE
    } else {
      key <- gsub("-", "_", substr(body, 1L, eq_pos - 1L), fixed = TRUE)
      value <- substr(body, eq_pos + 1L, nchar(body))
    }
    options[[key]] <- value
  }
  list(options = options, targets = targets)
}

bbmri_so_parse_csv <- function(value, allowed = NULL, label = "value") {
  if (is.null(value) || identical(value, FALSE) || identical(value, TRUE) || !nzchar(value)) {
    return(NULL)
  }
  values <- trimws(strsplit(value, ",", fixed = TRUE)[[1]])
  values <- values[nzchar(values)]
  if (is.null(allowed)) {
    return(unique(values))
  }
  invalid <- setdiff(values, allowed)
  if (length(invalid)) {
    stop("Unsupported ", label, ": ", paste(invalid, collapse = ", "), call. = FALSE)
  }
  unique(values)
}

bbmri_so_normalize_requested_target <- function(target) {
  size_match <- regexec("^(.*)-(small|med|big)$", target, perl = TRUE)
  size_parts <- regmatches(target, size_match)[[1]]
  output_variant <- NULL
  if (length(size_parts) > 0) {
    target <- size_parts[[2]]
    output_variant <- size_parts[[3]]
  }

  legacy_prefix <- "example-strategic-objectives-so2-"
  if (startsWith(target, legacy_prefix)) {
    legacy_suffix <- substring(target, nchar(legacy_prefix) + 1L)
    if (startsWith(legacy_suffix, "global-")) {
      return(list(target = sub("^global-", "SO-", legacy_suffix), output_variant = output_variant))
    }
    if (startsWith(legacy_suffix, "so-")) {
      parts <- strsplit(legacy_suffix, "-", fixed = TRUE)[[1]]
      if (length(parts) < 3L) {
        stop("Malformed legacy strategic-objectives target: ", target, call. = FALSE)
      }
      objective_id <- parts[[2]]
      mode <- parts[[3]]
      return(list(target = paste0(objective_id, "-", mode), output_variant = output_variant))
    }
    if (startsWith(legacy_suffix, "sg-")) {
      parts <- strsplit(legacy_suffix, "-", fixed = TRUE)[[1]]
      if (length(parts) < 3L) {
        stop("Malformed legacy strategic-objectives target: ", target, call. = FALSE)
      }
      goal_id <- parts[[2]]
      mode <- parts[[3]]
      return(list(target = paste0(goal_id, "-", mode), output_variant = output_variant))
    }
    stop("Unsupported legacy strategic-objectives target: ", target, call. = FALSE)
  }

  list(target = target, output_variant = output_variant)
}

bbmri_so_parse_requested_target <- function(target) {
  normalized <- bbmri_so_normalize_requested_target(target)
  target <- normalized$target
  output_variant <- normalized$output_variant

  if (identical(target, "SO") || startsWith(target, "SO-")) {
    parts <- strsplit(target, "-", fixed = TRUE)[[1]]
    mode <- if (length(parts) >= 2L) parts[[2]] else NULL
    modes <- if (is.null(mode)) c("recolor", "bars") else mode
    if (length(parts) > 2L) {
      stop("Global SO targets must look like SO, SO-recolor, or SO-bars.", call. = FALSE)
    }
    return(list(
      spec = "strategy",
      levels = "global",
      modes = modes,
      objective_filter = NULL,
      goal_filter = NULL,
      output_variants = output_variant
    ))
  }

  goal_match <- regexec("^(SO[0-9]+\\.[0-9]+)(?:-(recolor|bars))?$", target, perl = TRUE)
  goal_parts <- regmatches(target, goal_match)[[1]]
  if (length(goal_parts) > 0) {
    goal_id <- goal_parts[[2]]
    mode <- goal_parts[[3]]
    modes <- if (nzchar(mode %||% "")) mode else "recolor"
    if (identical(mode, "bars")) {
      stop("Strategic goal targets support recolor only.", call. = FALSE)
    }
    return(list(
      spec = "full",
      levels = "sg",
      modes = modes,
      objective_filter = sub("\\.[0-9]+$", "", goal_id),
      goal_filter = goal_id,
      output_variants = output_variant
    ))
  }

  so_match <- regexec("^(SO[0-9]+)(?:-(recolor|bars))?$", target, perl = TRUE)
  so_parts <- regmatches(target, so_match)[[1]]
  if (length(so_parts) > 0) {
    objective_id <- so_parts[[2]]
    mode <- so_parts[[3]]
    modes <- if (nzchar(mode %||% "")) mode else c("recolor", "bars")
    return(list(
      spec = "full",
      levels = "so",
      modes = modes,
      objective_filter = objective_id,
      goal_filter = NULL,
      output_variants = output_variant
    ))
  }

  stop(
    "Unsupported strategic-objectives target: ",
    target,
    ". Expected SO, SO-recolor, SO-bars, SOx, SOx-recolor, SOx-bars, or SOx.y-recolor.",
    call. = FALSE
  )
}

bbmri_so_render_request <- function(request, output_formats = NULL, default_output_variants = NULL, name_style = "short") {
  output_variants <- request$output_variants %||% default_output_variants
  cat(request$target, " ...\n", sep = "")
  bbmri_save_strategic_objectives_formats(
    spec = strategy_spec,
    output_dir = example_output_dir,
    output_prefix = "SO",
    levels = request$levels,
    modes = request$modes,
    objective_filter = request$objective_filter,
    goal_filter = request$goal_filter,
    country_label_codes = cfg$standard_country_labels,
    objective_order = bbmri_so_objective_ids(strategy_spec),
    output_variants = output_variants,
    output_formats = output_formats,
    target_name_style = name_style
  )
}

cli <- bbmri_so_parse_cli()
output_formats <- bbmri_so_parse_csv(cli$options$formats, allowed = c("png", "pdf", "svg"), label = "format")
output_variants <- bbmri_so_parse_csv(cli$options$sizes, allowed = c("small", "med", "big"), label = "size")
name_style <- if (!is.null(cli$options$name_style) && nzchar(cli$options$name_style)) {
  cli$options$name_style
} else {
  "short"
}
if (!name_style %in% c("short", "legacy")) {
  stop("Unsupported SO output name style: ", name_style, call. = FALSE)
}

if (!length(cli$targets)) {
  cat("Generating strategic-objectives example maps: all objectives, goals, and global overview\n")
  if (!is.null(output_variants)) {
    cat("Sizes: ", paste(output_variants, collapse = ", "), "\n", sep = "")
  } else {
    cat("Sizes: small, med, big\n")
  }
  if (!is.null(output_formats)) {
    cat("Formats: ", paste(output_formats, collapse = ", "), "\n", sep = "")
  } else {
    cat("Formats: png, pdf, svg\n")
  }
  cat("Output directory: ", example_output_dir, "\n", sep = "")
  bbmri_save_strategic_objectives_formats(
    spec = strategy_spec,
    output_dir = example_output_dir,
    output_prefix = "SO",
    levels = c("sg", "so", "global"),
    modes = c("recolor", "bars"),
    country_label_codes = cfg$standard_country_labels,
    objective_order = bbmri_so_objective_ids(strategy_spec),
    output_variants = output_variants,
    output_formats = output_formats,
    target_name_style = name_style
  )
} else {
  cat("Generating strategic-objectives example maps:\n")
  if (!is.null(output_variants)) {
    cat("Sizes: ", paste(output_variants, collapse = ", "), "\n", sep = "")
  }
  if (!is.null(output_formats)) {
    cat("Formats: ", paste(output_formats, collapse = ", "), "\n", sep = "")
  }
  cat("Output directory: ", example_output_dir, "\n", sep = "")
  for (target in cli$targets) {
    request <- bbmri_so_parse_requested_target(target)
    request$target <- target
    bbmri_so_render_request(request, output_formats = output_formats, default_output_variants = output_variants, name_style = name_style)
  }
}
