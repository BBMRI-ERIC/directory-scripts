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
    if (file.exists(file.path(candidate, "strategic_objectives_common.R"))) {
      return(candidate)
    }
  }

  stop(
    "Unable to locate the R-maps directory. Set the working directory to the repository root or the R-maps directory before sourcing render_strategic_objectives.R.",
    call. = FALSE
  )
}

script_dir <- bbmri_detect_rmaps_dir()
source(file.path(script_dir, "strategic_objectives_common.R"))

bbmri_parse_csv_codes <- function(value) {
  if (is.null(value) || !nzchar(value)) {
    return(NULL)
  }
  codes <- trimws(strsplit(value, ",", fixed = TRUE)[[1]])
  codes <- toupper(codes[nzchar(codes)])
  if (!length(codes)) {
    return(NULL)
  }
  unique(codes)
}

bbmri_parse_csv_values <- function(value, allowed = NULL, label = "value") {
  if (is.null(value) || !nzchar(value)) {
    return(NULL)
  }
  values <- trimws(strsplit(value, ",", fixed = TRUE)[[1]])
  values <- values[nzchar(values)]
  if (!length(values)) {
    return(NULL)
  }
  if (!is.null(allowed)) {
    invalid <- setdiff(values, allowed)
    if (length(invalid)) {
      stop("Unsupported ", label, ": ", paste(invalid, collapse = ", "), call. = FALSE)
    }
  }
  unique(values)
}

main <- function() {
  repo_root <- normalizePath(file.path(script_dir, ".."), winslash = "/", mustWork = TRUE)
  args <- bbmri_parse_args(list(
    input = normalizePath(file.path(script_dir, "data", "strategic-objectives-template.toml"), winslash = "/", mustWork = FALSE),
    output_dir = file.path(script_dir, "pilot-output"),
    output_prefix = "strategic-objectives",
    levels = "sg,so,global",
    modes = "recolor,bars",
    objective = "",
    goal = "",
    country_label_codes = "",
    sizes = "",
    formats = "",
    target_name_style = "legacy",
    python = file.path(repo_root, ".venv-maps", "bin", "python")
  ))
  if (identical(args$target_name_style, "short") && identical(args$output_prefix, "strategic-objectives")) {
    args$output_prefix <- "SO"
  }

  spec <- bbmri_load_strategic_objectives_spec(args$input, python_bin = args$python)
  bbmri_save_strategic_objectives_formats(
    spec = spec,
    output_dir = args$output_dir,
    output_prefix = args$output_prefix,
    levels = trimws(strsplit(args$levels, ",", fixed = TRUE)[[1]]),
    modes = trimws(strsplit(args$modes, ",", fixed = TRUE)[[1]]),
    objective_filter = if (nzchar(args$objective)) args$objective else NULL,
    goal_filter = if (nzchar(args$goal)) args$goal else NULL,
    country_label_codes = bbmri_parse_csv_codes(args$country_label_codes),
    output_variants = bbmri_parse_csv_values(args$sizes, allowed = c("small", "med", "big"), label = "size"),
    output_formats = bbmri_parse_csv_values(args$formats, allowed = c("png", "pdf", "svg"), label = "format"),
    target_name_style = args$target_name_style
  )
}

if (sys.nframe() == 0) {
  main()
}
