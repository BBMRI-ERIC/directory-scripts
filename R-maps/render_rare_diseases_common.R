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
source(file.path(script_dir, "render_bbmri_members_sized.R"))

build_rare_diseases_map <- function(
  points_path,
  iarc_path = NA_character_,
  output_variant = "med",
  include_biobank_labels = TRUE,
  omit_biobank_labels_on_small = FALSE,
  biobank_label_layout_variant = NULL,
  point_size_value = 10
) {
  bbmri_require_packages(c("ggplot2", "sf"))
  cfg <- bbmri_map_config()
  if (is.null(biobank_label_layout_variant)) {
    biobank_label_layout_variant <- if (identical(output_variant, "small")) "small" else if (identical(output_variant, "med")) "spread" else "default"
  }

  bbmri_build_sized_biobank_map(
    points_path = points_path,
    bbox = cfg$standard_bbox,
    export_sizes = cfg$export_sizes,
    cfg = cfg,
    iarc_path = iarc_path,
    output_variant = output_variant,
    country_layout_variant = if (identical(output_variant, "small")) "small" else "default",
    include_rivers = FALSE,
    required_columns = c("biobankID", "biobankName", "biobankType", "biobankSize", "rdMembership"),
    point_fill_fn = function(point_df, cfg, output_variant) {
      ifelse(
        point_df$rdMembership == "non_member",
        cfg$rd_colors$non_member,
        cfg$rd_colors$member
      )
    },
    include_biobank_labels = include_biobank_labels,
    omit_biobank_labels_on_small = omit_biobank_labels_on_small,
    biobank_label_column = "biobankID",
    biobank_label_layout_variant = biobank_label_layout_variant,
    biobank_label_style = cfg$sized_biobank_label_style,
    biobank_label_colour = cfg$sized_biobank_label_style$colour,
    biobank_label_alpha = cfg$sized_biobank_label_style$alpha,
    point_size_value = point_size_value
  )
}

save_rare_diseases_formats <- function(
  points_path,
  iarc_path,
  output_dir,
  prefix,
  include_biobank_labels = TRUE,
  omit_biobank_labels_on_small = FALSE,
  biobank_label_layout_variant = NULL,
  point_size_value = 10
) {
  cfg <- bbmri_map_config()
  bbmri_save_plot_formats_from_builder(
    build_plot = function(output_variant) {
      build_rare_diseases_map(
        points_path = points_path,
        iarc_path = iarc_path,
        output_variant = output_variant,
        include_biobank_labels = include_biobank_labels,
        omit_biobank_labels_on_small = omit_biobank_labels_on_small,
        biobank_label_layout_variant = biobank_label_layout_variant,
        point_size_value = point_size_value
      )
    },
    output_dir = output_dir,
    prefix = prefix,
    export_sizes = cfg$export_sizes
  )
}
