# Render the strategic-objectives family from the TOML scaffold.
#
# This is the recommended RStudio entrypoint for humans who want to inspect or
# extend the SO/SG framework without going through the shell wrapper.

source(file.path("R-maps", "examples", "00_setup.R"))
source(file.path(script_dir, "strategic_objectives_common.R"))

spec_path <- file.path(script_dir, "data", "strategic-objectives-template.toml")
strategy_spec <- bbmri_load_strategic_objectives_spec(spec_path)
so2_spec <- bbmri_so_subset_spec(strategy_spec, objective_ids = "SO2")

bbmri_so_parse_requested_target <- function(target, default_prefix = "example-strategic-objectives-so2") {
  size_match <- regexec("^(.*)-(small|med|big)$", target, perl = TRUE)
  size_parts <- regmatches(target, size_match)[[1]]
  output_variant <- NULL
  if (length(size_parts) > 0) {
    target <- size_parts[[2]]
    output_variant <- size_parts[[3]]
  }

  prefix <- paste0(default_prefix, "-")
  if (!startsWith(target, prefix)) {
    stop("Unsupported strategic-objectives target: ", target, call. = FALSE)
  }

  suffix <- substring(target, nchar(prefix) + 1L)
  parts <- strsplit(suffix, "-", fixed = TRUE)[[1]]
  if (length(parts) < 2L) {
    stop("Malformed strategic-objectives target: ", target, call. = FALSE)
  }

  level <- parts[[1]]
  mode <- parts[[length(parts)]]
  if (!mode %in% c("recolor", "bars")) {
    stop("Unsupported strategic-objectives mode in target: ", target, call. = FALSE)
  }

  if (identical(level, "global")) {
    if (length(parts) != 2L) {
      stop("Global targets must look like example-strategic-objectives-so2-global-recolor or ...-bars.", call. = FALSE)
    }
    return(list(
      spec = "strategy",
      levels = "global",
      modes = mode,
      objective_filter = NULL,
      goal_filter = NULL,
      output_variants = output_variant
    ))
  }

  if (identical(level, "so")) {
    if (length(parts) != 3L) {
      stop("SO targets must look like example-strategic-objectives-so2-so-SO2-recolor or ...-bars.", call. = FALSE)
    }
    objective_id <- parts[[2]]
    if (!identical(objective_id, "SO2")) {
      stop("This example runner currently supports only SO2-specific SO targets.", call. = FALSE)
    }
    return(list(
      spec = "so2",
      levels = "so",
      modes = mode,
      objective_filter = objective_id,
      goal_filter = NULL,
      output_variants = output_variant
    ))
  }

  if (identical(level, "sg")) {
    if (length(parts) != 3L) {
      stop("SG targets must look like example-strategic-objectives-so2-sg-SO2.6-recolor or ...-big.", call. = FALSE)
    }
    goal_id <- parts[[2]]
    if (!startsWith(goal_id, "SO2.")) {
      stop("SG targets must use an SO2.x goal id.", call. = FALSE)
    }
    if (!identical(mode, "recolor")) {
      stop("SG targets currently support recolor only.", call. = FALSE)
    }
    return(list(
      spec = "so2",
      levels = "sg",
      modes = "recolor",
      objective_filter = "SO2",
      goal_filter = goal_id,
      output_variants = output_variant
    ))
  }

  stop("Unsupported strategic-objectives level in target: ", target, call. = FALSE)
}

bbmri_so_render_request <- function(request) {
  spec <- if (identical(request$spec, "strategy")) {
    strategy_spec
  } else {
    so2_spec
  }
  cat(request$target, " ...\n", sep = "")
  bbmri_save_strategic_objectives_formats(
    spec = spec,
    output_dir = example_output_dir,
    output_prefix = "example-strategic-objectives-so2",
    levels = request$levels,
    modes = request$modes,
    objective_filter = request$objective_filter,
    goal_filter = request$goal_filter,
    country_label_codes = cfg$standard_country_labels,
    objective_order = bbmri_so_objective_ids(strategy_spec),
    output_variants = request$output_variants
  )
}

requested_targets <- commandArgs(trailingOnly = TRUE)

if (!length(requested_targets)) {
  cat("Generating strategic-objectives example maps: SO2 subset and global overview\n")
  cat("Output directory: ", example_output_dir, "\n", sep = "")
  bbmri_save_strategic_objectives_formats(
    spec = so2_spec,
    output_dir = example_output_dir,
    output_prefix = "example-strategic-objectives-so2",
    levels = c("sg", "so"),
    modes = c("recolor", "bars"),
    country_label_codes = cfg$standard_country_labels,
    objective_order = bbmri_so_objective_ids(strategy_spec)
  )

  bbmri_save_strategic_objectives_formats(
    spec = strategy_spec,
    output_dir = example_output_dir,
    output_prefix = "example-strategic-objectives-so2",
    levels = "global",
    modes = c("recolor", "bars"),
    country_label_codes = cfg$standard_country_labels,
    objective_order = bbmri_so_objective_ids(strategy_spec)
  )
} else {
  cat("Generating strategic-objectives example maps:\n")
  cat("Output directory: ", example_output_dir, "\n", sep = "")
  for (target in requested_targets) {
    request <- bbmri_so_parse_requested_target(target)
    request$target <- target
    bbmri_so_render_request(request)
  }
}
