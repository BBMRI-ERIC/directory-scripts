# Template for more complex overlays such as per-country bars or pies.
#
# This file is intentionally a template: the point is to keep the data contract
# explicit and to keep styling separate from data selection.

source(file.path("R-maps", "examples", "00_setup.R"))

overlay_spec <- data.frame(
  entity_type = c("country", "biobank"),
  chart_type = c("bar", "pie"),
  fill = c("#0098cc", "#f36f21"),
  line = c("#226688", "#004685"),
  size = c(1.0, 1.2),
  value_field = c("metric_value", "metric_value"),
  label_field = c("label", "label"),
  stringsAsFactors = FALSE
)

message("Overlay spec rows: ", nrow(overlay_spec))
message("Use the spec to decide which geometry to draw for each entity type.")
message("Keep chart colors and relative sizes in a shared spec object, not in scattered layer constants.")
