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
source(file.path(script_dir, "render_rare_diseases_common.R"))

main <- function() {
  args <- bbmri_parse_args(list(
    input = normalizePath(file.path(script_dir, "..", "bbmri-directory-rare-diseases-pilot.geojson"), winslash = "/", mustWork = FALSE),
    iarc = NA_character_,
    output_dir = file.path(script_dir, "output"),
    output_prefix = "rare-diseases-nolabels"
  ))

  save_rare_diseases_formats(
    points_path = args$input,
    iarc_path = args$iarc,
    output_dir = args$output_dir,
    prefix = args$output_prefix,
    include_biobank_labels = FALSE,
    point_size_value = 10
  )
}

if (sys.nframe() == 0) {
  main()
}
