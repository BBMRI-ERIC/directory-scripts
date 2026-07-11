# Inspect the strategic-objectives template that will drive future maps.
#
# This is intentionally a lightweight RStudio recipe, not a renderer. It makes
# the TOML source of truth easy to explore interactively while the actual
# visual encoding is still being finalized.

source(file.path("R-maps", "examples", "00_setup.R"))
source(file.path(script_dir, "strategic_objectives_common.R"))

template_path <- file.path("R-maps", "data", "strategic-objectives-template.toml")
strategy_template <- bbmri_load_strategic_objectives_spec(template_path)

message("Template schema version: ", strategy_template$schema_version)
message("Filled objectives: ", paste(vapply(strategy_template$objectives, `[[`, character(1), "id"), collapse = ", "))
message("SO2 goals: ", paste(vapply(strategy_template$objectives[[2]]$goals, `[[`, character(1), "id"), collapse = ", "))
message("Use this template to add the remaining strategic objectives/goals.")
