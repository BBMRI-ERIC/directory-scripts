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
source(file.path(script_dir, "map_config.R"))
source(file.path(script_dir, "map_common.R"))

build_global_nolabels_map <- function(points_path, iarc_path = NA_character_, output_variant = "med") {
  bbmri_require_packages(c("ggplot2", "sf"))
  cfg <- bbmri_map_config()
  bbmri_build_classic_standard_points_map(
    points_path = points_path,
    bbox = cfg$global_bbox,
    export_sizes = cfg$global_export_sizes,
    cfg = cfg,
    iarc_path = iarc_path,
    output_variant = output_variant,
    include_rivers = FALSE,
    country_layout_variant = if (identical(output_variant, "big")) "global" else "globalwide"
  )
}

save_global_nolabels_formats <- function(points_path, iarc_path, output_dir, prefix) {
  cfg <- bbmri_map_config()
  bbmri_save_plot_formats_from_builder(
    build_plot = function(output_variant) {
      build_global_nolabels_map(points_path, iarc_path, output_variant = output_variant)
    },
    output_dir = output_dir,
    prefix = prefix,
    export_sizes = cfg$global_export_sizes
  )
}

main <- function() {
  args <- bbmri_parse_args(list(
    input = normalizePath(file.path(script_dir, "..", "bbmri-directory-pilot.geojson"), winslash = "/", mustWork = FALSE),
    iarc = NA_character_,
    output_dir = file.path(script_dir, "output"),
    output_prefix = "global-nolabels"
  ))

  save_global_nolabels_formats(args$input, args$iarc, args$output_dir, args$output_prefix)
}

if (sys.nframe() == 0) {
  main()
}
