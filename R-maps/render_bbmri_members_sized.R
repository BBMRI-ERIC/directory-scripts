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

build_members_sized_map <- function(
  points_path,
  iarc_path = NA_character_,
  output_variant = "med",
  bbox = NULL,
  export_sizes = NULL,
  country_layout_variant = NULL,
  biobank_label_layout_variant = NULL,
  include_biobank_labels = TRUE
) {
  bbmri_require_packages(c("ggplot2", "sf"))

  cfg <- bbmri_map_config()
  if (is.null(bbox)) {
    bbox <- cfg$standard_bbox
  }
  if (is.null(export_sizes)) {
    export_sizes <- cfg$export_sizes
  }
  if (is.null(country_layout_variant)) {
    country_layout_variant <- if (identical(output_variant, "small")) "small" else "default"
  }
  if (is.null(biobank_label_layout_variant)) {
    biobank_label_layout_variant <- if (identical(output_variant, "med")) "spread" else if (identical(output_variant, "small")) "small" else "default"
  }

  point_fill_fn <- function(point_df, cfg, output_variant) {
    ifelse(
      point_df$biobankType == "standaloneCollection",
      cfg$standard_colors$standalone,
      cfg$standard_colors$biobank
    )
  }

  bbmri_build_sized_biobank_map(
    points_path = points_path,
    bbox = bbox,
    export_sizes = export_sizes,
    cfg = cfg,
    iarc_path = iarc_path,
    output_variant = output_variant,
    country_layout_variant = country_layout_variant,
    include_rivers = FALSE,
    required_columns = c("biobankID", "biobankName", "biobankType", "biobankSize"),
    point_fill_fn = point_fill_fn,
    include_biobank_labels = include_biobank_labels,
    omit_biobank_labels_on_small = TRUE,
    biobank_label_column = "biobankID",
    biobank_label_layout_variant = biobank_label_layout_variant,
    biobank_label_style = cfg$sized_biobank_label_style,
    biobank_label_colour = cfg$sized_biobank_label_style$colour,
    biobank_label_alpha = cfg$sized_biobank_label_style$alpha
  )
}

save_members_sized_formats <- function(points_path, iarc_path, output_dir, prefix, biobank_label_layout_variant = NULL) {
  cfg <- bbmri_map_config()
  bbmri_save_plot_formats_from_builder(
    build_plot = function(output_variant) {
      build_members_sized_map(
        points_path,
        iarc_path,
        output_variant = output_variant,
        biobank_label_layout_variant = biobank_label_layout_variant
      )
    },
    output_dir = output_dir,
    prefix = prefix,
    export_sizes = cfg$export_sizes
  )
}

main <- function() {
  args <- bbmri_parse_args(list(
    input = normalizePath(file.path(script_dir, "..", "bbmri-directory-pilot.geojson"), winslash = "/", mustWork = FALSE),
    iarc = NA_character_,
    output_dir = file.path(script_dir, "output"),
    output_prefix = "bbmri-members-sized",
    biobank_label_layout_variant = ""
  ))

  if (!nzchar(args$biobank_label_layout_variant)) {
    args$biobank_label_layout_variant <- NULL
  }
  save_members_sized_formats(
    args$input,
    args$iarc,
    args$output_dir,
    args$output_prefix,
    biobank_label_layout_variant = args$biobank_label_layout_variant
  )
}

if (sys.nframe() == 0) {
  main()
}
