# Inspect the strategic-objectives template that will drive future maps.
#
# This is intentionally a lightweight RStudio recipe, not a renderer. It makes
# the JSON scaffold easy to explore interactively while the actual visual
# encoding is still being finalized.

source(file.path("R-maps", "examples", "00_setup.R"))
bbmri_require_packages(c("jsonlite"))

template_path <- file.path("R-maps", "data", "strategic-objectives-template.json")
strategy_template <- jsonlite::fromJSON(template_path, simplifyVector = FALSE)

message("Template schema version: ", strategy_template$schema_version)
message("Filled objectives: ", paste(names(strategy_template)[startsWith(names(strategy_template), "SO")], collapse = ", "))
message("SO2 goals: ", paste(names(strategy_template$SO2), collapse = ", "))
message("Use this template to add the remaining strategic objectives/goals.")
