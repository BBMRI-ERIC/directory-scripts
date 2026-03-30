cmd_args <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", cmd_args, value = TRUE)
script_dir <- if (length(file_arg) == 0) {
  normalizePath(".", winslash = "/", mustWork = TRUE)
} else {
  normalizePath(dirname(sub("^--file=", "", file_arg[[1]])), winslash = "/", mustWork = TRUE)
}
source(file.path(script_dir, "map_config.R"))
source(file.path(script_dir, "map_common.R"))

build_covid_nolabels_map <- function(points_path, iarc_path = NA_character_, output_variant = "med") {
  bbmri_require_packages(c("ggplot2", "sf"))
  cfg <- bbmri_map_config()
  bbmri_build_classic_standard_points_map(
    points_path = points_path,
    bbox = cfg$global_bbox,
    export_sizes = cfg$global_export_sizes,
    cfg = cfg,
    iarc_path = iarc_path,
    output_variant = output_variant
  )
}

save_covid_nolabels_formats <- function(points_path, iarc_path, output_dir, prefix) {
  cfg <- bbmri_map_config()
  bbmri_save_plot_formats_from_builder(
    build_plot = function(output_variant) {
      build_covid_nolabels_map(points_path, iarc_path, output_variant = output_variant)
    },
    output_dir = output_dir,
    prefix = prefix,
    export_sizes = cfg$global_export_sizes
  )
}

main <- function() {
  args <- bbmri_parse_args(list(
    input = normalizePath(file.path(script_dir, "..", "bbmri-directory-covid.geojson"), winslash = "/", mustWork = FALSE),
    iarc = NA_character_,
    output_dir = file.path(script_dir, "output"),
    output_prefix = "covid-nolabels"
  ))

  save_covid_nolabels_formats(args$input, args$iarc, args$output_dir, args$output_prefix)
}

if (sys.nframe() == 0) {
  main()
}
