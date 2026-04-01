# Render a current map from the existing framework.
#
# This recipe is useful in RStudio when you want to verify that the current
# pipeline still works before changing shared helpers or style constants.

source(file.path("R-maps", "examples", "00_setup.R"))
source(file.path(script_dir, "render_global_nolabels.R"))

save_global_nolabels_formats(
  points_path = pilot_geojson,
  iarc_path = iarc_geojson,
  output_dir = example_output_dir,
  prefix = "example-global-nolabels"
)
