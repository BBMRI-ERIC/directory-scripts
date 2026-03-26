cmd_args <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", cmd_args, value = TRUE)
script_dir <- if (length(file_arg) == 0) {
  normalizePath(".", winslash = "/", mustWork = TRUE)
} else {
  normalizePath(dirname(sub("^--file=", "", file_arg[[1]])), winslash = "/", mustWork = TRUE)
}
source(file.path(script_dir, "map_config.R"))
source(file.path(script_dir, "map_common.R"))
source(file.path(script_dir, "render_bbmri_members_nolabels.R"))
source(file.path(script_dir, "render_bbmri_members_sized.R"))
source(file.path(script_dir, "render_bbmri_members_oec_all.R"))

bbmri_run_geocoding_export <- function(python_bin, geocoding_script, geocoding_config, out_path) {
  out_base <- tools::file_path_sans_ext(out_path)
  args <- c(
    geocoding_script,
    "--out-name", out_base,
    geocoding_config
  )
  status <- system2(python_bin, args = args)
  if (!identical(status, 0L)) {
    stop("geocoding_2022.py failed with exit status ", status, call. = FALSE)
  }
  if (!file.exists(out_path)) {
    stop("Expected GeoJSON was not created: ", out_path, call. = FALSE)
  }
}

main <- function() {
  cfg <- bbmri_map_config()
  repo_root <- normalizePath(file.path(script_dir, ".."), winslash = "/", mustWork = TRUE)
  args <- bbmri_parse_args(list(
    python = file.path(repo_root, ".venv-maps", "bin", "python"),
    geocoding_script = normalizePath(file.path(repo_root, "geocoding_2022.py"), winslash = "/", mustWork = TRUE),
    geocoding_config = normalizePath(file.path(repo_root, "geocoding.config"), winslash = "/", mustWork = TRUE),
    full_geojson = normalizePath(file.path(repo_root, "bbmri-directory-pilot.geojson"), winslash = "/", mustWork = FALSE),
    member_geojson = normalizePath(file.path(repo_root, "bbmri-directory-members-pilot.geojson"), winslash = "/", mustWork = FALSE),
    iarc = normalizePath(file.path(script_dir, "data", "IARC.geojson"), winslash = "/", mustWork = FALSE),
    node_points = normalizePath(file.path(script_dir, "data", "HQlineNN.geojson"), winslash = "/", mustWork = FALSE),
    node_lines = normalizePath(file.path(script_dir, "data", "onlyLinesHQlineNN.geojson"), winslash = "/", mustWork = FALSE),
    output_dir = file.path(script_dir, "pilot-output")
  ))

  if (!file.exists(args$python)) {
    stop("Pilot Python interpreter not found: ", args$python, call. = FALSE)
  }

  message("Using Python interpreter: ", args$python)
  message("Generating full biobank GeoJSON from the Directory cache...")
  bbmri_run_geocoding_export(
    python_bin = args$python,
    geocoding_script = args$geocoding_script,
    geocoding_config = args$geocoding_config,
    out_path = args$full_geojson
  )

  message("Deriving member/observer subset GeoJSON for OEC rendering...")
  full_points <- bbmri_read_sf(args$full_geojson, "Pilot full biobank GeoJSON")
  member_points <- bbmri_filter_member_observer_points(full_points, cfg)
  bbmri_write_geojson(member_points, args$member_geojson)

  message("Rendering bbmri-members-nolabels...")
  nolabels_plot <- build_members_nolabels_map(args$full_geojson, args$iarc)
  bbmri_save_plot_formats(nolabels_plot, args$output_dir, "bbmri-members-nolabels", cfg$export_sizes)

  message("Rendering bbmri-members-sized...")
  sized_plot <- build_members_sized_map(args$full_geojson, args$iarc)
  bbmri_save_plot_formats(sized_plot, args$output_dir, "bbmri-members-sized", cfg$export_sizes)

  message("Rendering bbmri-members-OEC-all...")
  oec_plot <- build_members_oec_all_map(
    points_path = args$member_geojson,
    iarc_path = args$iarc,
    node_points_path = args$node_points,
    node_lines_path = args$node_lines
  )
  bbmri_save_plot_formats(oec_plot, args$output_dir, "bbmri-members-OEC-all", cfg$export_sizes)

  message("Pilot renders written to: ", args$output_dir)
}

if (sys.nframe() == 0) {
  main()
}
