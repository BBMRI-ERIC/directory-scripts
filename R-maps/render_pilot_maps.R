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
source(file.path(script_dir, "render_global_nolabels.R"))
source(file.path(script_dir, "render_covid_nolabels.R"))
source(file.path(script_dir, "render_quality_maps_nolabels.R"))
source(file.path(script_dir, "render_federated_platform.R"))
source(file.path(script_dir, "render_crc_cohort_sized.R"))

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

bbmri_run_python_helper <- function(python_bin, script_path, helper_args) {
  args <- c(script_path, helper_args)
  status <- system2(python_bin, args = args)
  if (!identical(status, 0L)) {
    stop(basename(script_path), " failed with exit status ", status, call. = FALSE)
  }
}

bbmri_validate_map_set <- function(value) {
  allowed <- c("core", "extras", "all")
  if (!value %in% allowed) {
    stop("Unsupported map set ", shQuote(value), "; expected one of ", paste(allowed, collapse = ", "), call. = FALSE)
  }
  value
}

bbmri_all_map_ids <- function() {
  c(
    "bbmri-members-nolabels",
    "bbmri-members-sized",
    "bbmri-members-OEC-all",
    "global-nolabels",
    "covid-nolabels",
    "quality_maps-nolabels",
    "federated-platform",
    "CRC-cohort-sized"
  )
}

bbmri_map_ids_for_set <- function(map_set) {
  map_set <- bbmri_validate_map_set(map_set)
  switch(
    map_set,
    core = c("bbmri-members-nolabels", "bbmri-members-sized", "bbmri-members-OEC-all"),
    extras = c("global-nolabels", "covid-nolabels", "quality_maps-nolabels", "federated-platform", "CRC-cohort-sized"),
    all = bbmri_all_map_ids()
  )
}

bbmri_normalize_map_selection <- function(maps_value = "", map_set = "all") {
  if (is.null(maps_value) || identical(maps_value, FALSE) || identical(maps_value, TRUE)) {
    maps_value <- ""
  }
  if (!is.character(maps_value) || length(maps_value) != 1) {
    stop("Map selection must be a single string or empty.", call. = FALSE)
  }
  if (!is.null(maps_value) && nzchar(maps_value)) {
    map_ids <- trimws(strsplit(maps_value, ",", fixed = TRUE)[[1]])
    map_ids <- map_ids[nzchar(map_ids)]
    allowed <- bbmri_all_map_ids()
    invalid <- setdiff(map_ids, allowed)
    if (length(invalid) > 0) {
      stop(
        "Unsupported map id(s): ",
        paste(invalid, collapse = ", "),
        ". Allowed ids: ",
        paste(allowed, collapse = ", "),
        call. = FALSE
      )
    }
    return(unique(map_ids))
  }

  bbmri_map_ids_for_set(map_set)
}

main <- function() {
  cfg <- bbmri_map_config()
  repo_root <- normalizePath(file.path(script_dir, ".."), winslash = "/", mustWork = TRUE)
  args <- bbmri_parse_args(list(
    map_set = "all",
    maps = "",
    python = file.path(repo_root, ".venv-maps", "bin", "python"),
    geocoding_script = normalizePath(file.path(repo_root, "geocoding_2022.py"), winslash = "/", mustWork = TRUE),
    geocoding_config = normalizePath(file.path(repo_root, "geocoding.config"), winslash = "/", mustWork = TRUE),
    covid_prep_script = normalizePath(file.path(script_dir, "prepare_covid_geojson.py"), winslash = "/", mustWork = TRUE),
    quality_prep_script = normalizePath(file.path(script_dir, "prepare_quality_geojson.py"), winslash = "/", mustWork = TRUE),
    full_geojson = normalizePath(file.path(repo_root, "bbmri-directory-pilot.geojson"), winslash = "/", mustWork = FALSE),
    member_geojson = normalizePath(file.path(repo_root, "bbmri-directory-members-pilot.geojson"), winslash = "/", mustWork = FALSE),
    covid_geojson = normalizePath(file.path(repo_root, "bbmri-directory-covid-pilot.geojson"), winslash = "/", mustWork = FALSE),
    quality_geojson = normalizePath(file.path(repo_root, "bbmri-directory-quality-pilot.geojson"), winslash = "/", mustWork = FALSE),
    iarc = normalizePath(file.path(script_dir, "data", "IARC.geojson"), winslash = "/", mustWork = FALSE),
    node_points = normalizePath(file.path(script_dir, "data", "HQlineNN.geojson"), winslash = "/", mustWork = FALSE),
    node_lines = normalizePath(file.path(script_dir, "data", "onlyLinesHQlineNN.geojson"), winslash = "/", mustWork = FALSE),
    federated_geojson = normalizePath(file.path(script_dir, "data", "federated-platform.geojson"), winslash = "/", mustWork = FALSE),
    crc_geojson = normalizePath(file.path(script_dir, "data", "CRC-Cohort.geojson"), winslash = "/", mustWork = FALSE),
    crc_imaging_geojson = normalizePath(file.path(script_dir, "data", "CRC-Cohort-imaging.geojson"), winslash = "/", mustWork = FALSE),
    output_dir = file.path(script_dir, "pilot-output")
  ))
  args$map_set <- bbmri_validate_map_set(args$map_set)
  selected_maps <- bbmri_normalize_map_selection(args$maps, args$map_set)

  needs_full_geojson <- any(selected_maps %in% c(
    "bbmri-members-nolabels",
    "bbmri-members-sized",
    "bbmri-members-OEC-all",
    "global-nolabels",
    "covid-nolabels"
  ))
  needs_python <- needs_full_geojson || any(selected_maps %in% c("quality_maps-nolabels", "covid-nolabels"))

  if (needs_python && !file.exists(args$python)) {
    stop("Pilot Python interpreter not found: ", args$python, call. = FALSE)
  }
  if (needs_python) {
    message("Using Python interpreter: ", args$python)
  }
  if (needs_full_geojson) {
    message("Generating full biobank GeoJSON from the Directory cache...")
    bbmri_run_geocoding_export(
      python_bin = args$python,
      geocoding_script = args$geocoding_script,
      geocoding_config = args$geocoding_config,
      out_path = args$full_geojson
    )
  }

  if ("bbmri-members-OEC-all" %in% selected_maps) {
    message("Deriving member/observer subset GeoJSON for OEC rendering...")
    full_points <- bbmri_read_sf(args$full_geojson, "Pilot full biobank GeoJSON")
    member_points <- bbmri_filter_member_observer_points(full_points, cfg)
    bbmri_write_geojson(member_points, args$member_geojson)
  }

  if ("bbmri-members-nolabels" %in% selected_maps) {
    message("Rendering bbmri-members-nolabels...")
    save_members_nolabels_formats(args$full_geojson, args$iarc, args$output_dir, "bbmri-members-nolabels")
  }

  if ("bbmri-members-sized" %in% selected_maps) {
    message("Rendering bbmri-members-sized...")
    save_members_sized_formats(args$full_geojson, args$iarc, args$output_dir, "bbmri-members-sized")
  }

  if ("bbmri-members-OEC-all" %in% selected_maps) {
    message("Rendering bbmri-members-OEC-all...")
    bbmri_save_members_oec_all_formats(
      args = list(
        input = args$member_geojson,
        iarc = args$iarc,
        node_points = args$node_points,
        node_lines = args$node_lines,
        output_dir = args$output_dir,
        output_prefix = "bbmri-members-OEC-all"
      ),
      export_sizes = cfg$oec_export_sizes
    )
  }

  if ("covid-nolabels" %in% selected_maps) {
    message("Deriving COVID subset GeoJSON...")
    bbmri_run_python_helper(
      python_bin = args$python,
      script_path = args$covid_prep_script,
      helper_args = c("--input", args$full_geojson, "--output", args$covid_geojson)
    )
  }

  if ("quality_maps-nolabels" %in% selected_maps) {
    message("Deriving quality map GeoJSON...")
    bbmri_run_python_helper(
      python_bin = args$python,
      script_path = args$quality_prep_script,
      helper_args = c("--output", args$quality_geojson)
    )
  }

  if ("global-nolabels" %in% selected_maps) {
    message("Rendering global-nolabels...")
    save_global_nolabels_formats(args$full_geojson, args$iarc, args$output_dir, "global-nolabels")
  }

  if ("covid-nolabels" %in% selected_maps) {
    message("Rendering covid-nolabels...")
    save_covid_nolabels_formats(args$covid_geojson, args$iarc, args$output_dir, "covid-nolabels")
  }

  if ("quality_maps-nolabels" %in% selected_maps) {
    message("Rendering quality_maps-nolabels...")
    save_quality_maps_nolabels_formats(args$quality_geojson, args$iarc, args$output_dir, "quality_maps-nolabels")
  }

  if ("federated-platform" %in% selected_maps) {
    message("Rendering federated-platform...")
    save_federated_platform_formats(args$federated_geojson, args$iarc, args$output_dir, "federated-platform")
  }

  if ("CRC-cohort-sized" %in% selected_maps) {
    message("Rendering CRC-cohort-sized...")
    save_crc_cohort_sized_formats(args$crc_geojson, args$crc_imaging_geojson, args$iarc, args$output_dir, "CRC-cohort-sized")
  }

  message("Pilot renders written to: ", args$output_dir)
}

if (sys.nframe() == 0) {
  main()
}
