# Shared example setup for RStudio and script-based use.
#
# Run from the repository root. In RStudio, set the project working directory
# to /home/hopet/codex/directory-scripts before sourcing this file.

repo_root <- normalizePath(".", winslash = "/", mustWork = TRUE)
script_dir <- file.path(repo_root, "R-maps")
example_output_dir <- file.path(script_dir, "compare-temp", "examples")
dir.create(example_output_dir, recursive = TRUE, showWarnings = FALSE)

source(file.path(script_dir, "map_config.R"))
source(file.path(script_dir, "map_common.R"))

cfg <- bbmri_map_config()

pilot_geojson <- file.path(repo_root, "bbmri-directory-pilot.geojson")
member_geojson <- file.path(repo_root, "bbmri-directory-members-pilot.geojson")
covid_geojson <- file.path(repo_root, "bbmri-directory-covid-pilot.geojson")
quality_geojson <- file.path(repo_root, "bbmri-directory-quality-pilot.geojson")
iarc_geojson <- file.path(script_dir, "data", "IARC.geojson")
federated_geojson <- file.path(script_dir, "data", "federated-platform.geojson")
crc_geojson <- file.path(script_dir, "data", "CRC-Cohort.geojson")
crc_imaging_geojson <- file.path(script_dir, "data", "CRC-Cohort-imaging.geojson")
