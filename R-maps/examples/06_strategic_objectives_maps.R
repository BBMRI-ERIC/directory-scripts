# Render the strategic-objectives family from the TOML scaffold.
#
# This is the recommended RStudio entrypoint for humans who want to inspect or
# extend the SO/SG framework without going through the shell wrapper.

source(file.path("R-maps", "examples", "00_setup.R"))
source(file.path(script_dir, "strategic_objectives_common.R"))

spec_path <- file.path(script_dir, "data", "strategic-objectives-template.toml")
strategy_spec <- bbmri_load_strategic_objectives_spec(spec_path)
so2_spec <- bbmri_so_subset_spec(strategy_spec, objective_ids = "SO2")

bbmri_save_strategic_objectives_formats(
  spec = so2_spec,
  output_dir = example_output_dir,
  output_prefix = "example-strategic-objectives-so2",
  levels = c("sg", "so", "global"),
  modes = c("recolor", "bars"),
  country_label_codes = cfg$standard_country_labels,
  objective_order = bbmri_so_objective_ids(strategy_spec)
)
