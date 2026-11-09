"""Check Portuguese island coverage without changing mainland or Qatar routing."""

import shutil
import subprocess

import pytest


def test_portugal_inset_configuration():
    """Check independent regional masks and connector-free, always-visible panels.

    Returns:
        None. Requires two disjoint PT regions while preserving Qatar settings.
    """
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript required")
    subprocess.run([rscript, "-e", '''
source("R-maps/map_config.R")
source("R-maps/render_bbmri_members_oec_all.R")
cfg <- bbmri_map_config()
insets <- setNames(cfg$oec_insets, vapply(cfg$oec_insets, `[[`, "", "id"))
stopifnot(all(c("azores", "madeira", "qa") %in% names(insets)))
for (id in c("azores", "madeira")) {
  panel <- insets[[id]]
  stopifnot(identical(panel$mask_country_codes, "PT"),
            identical(panel$mask_bbox, panel$bbox),
            identical(panel$draw_connector, FALSE), identical(panel$require_node, FALSE))
  bbmri_oec_validate_inset_cfg(panel, data.frame(iso_a2=c("PT", "QA")))
}
stopifnot(is.null(insets$qa$mask_bbox), insets$qa$require_node,
          insets$qa$connector$source_node_type == "HQ")
stopifnot(identical(cfg$portugal_regions$azores$label, "Azores (PT)"),
          identical(cfg$portugal_regions$madeira$label, "Madeira (PT)"))
theme <- bbmri_oec_panel_theme(cfg, insets$azores$frame, line_scale=1)
stopifnot(theme$panel.border$colour == insets$azores$frame$border_colour,
          is.na(theme$panel.border$fill),
          theme$panel.background$fill == insets$azores$frame$background_fill)
'''], check=True)


def test_portugal_geometry_and_labels():
    """Route island geometry and points once, retaining mainland and its node.

    Returns:
        None. Checks real sf geometry, country labels, and empty island inputs;
        explicitly skips when the local rendering dependencies are unavailable.
    """
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript required")
    result = subprocess.run([rscript, "-e", '''
if (!requireNamespace("sf", quietly = TRUE)) quit(status=77)
source("R-maps/render_bbmri_members_oec_all.R")
cfg <- bbmri_map_config()
rectangle <- function(x, y, w=0.2) sf::st_polygon(list(rbind(
  c(x,y), c(x+w,y), c(x+w,y+w), c(x,y+w), c(x,y))))
countries <- sf::st_sf(iso_a2=c("PT", "QA"), adm0_a3=c("PRT", "QAT"),
  name=c("Portugal", "Qatar"), geometry=sf::st_sfc(
    sf::st_multipolygon(list(unclass(rectangle(-9,39)), unclass(rectangle(-25.5,37.5)),
                            unclass(rectangle(-17,32.7)))), rectangle(51,25), crs=4326))
points <- sf::st_as_sf(data.frame(id=c("mainland", "azores", "madeira", "qa"),
  x=c(-8.9,-25.4,-16.9,51.1), y=c(39.1,37.6,32.8,25.1)), coords=c("x","y"), crs=4326)
nodes <- points[c(1,4),]
nodes$nodeType <- c("NN", "NN")
nodes$name <- c("PT", "QA")
lines <- points[0,]
resolved <- bbmri_oec_resolve_insets(cfg, countries, points, nodes, lines)
names(resolved) <- vapply(resolved, `[[`, "", "id")
stopifnot(identical(resolved$azores$points$id, "azores"),
          identical(resolved$madeira$points$id, "madeira"),
          nrow(resolved$azores$node_points) == 0)
mask <- do.call(rbind, lapply(resolved, `[[`, "mask"))
main <- bbmri_oec_main_countries(countries, cfg, "QA")
main <- bbmri_oec_remove_inset_regions(main, resolved)
stopifnot(nrow(main) > 0,
          identical(which(lengths(sf::st_intersects(points, main)) > 0), 1L),
          identical(bbmri_filter_sf_by_mask(points, mask, FALSE)$id, "mainland"))
labels <- bbmri_country_label_df(countries, cfg, cfg$standard_crs)
stopifnot(all(c("Azores (PT)", "Madeira (PT)") %in% labels$label))
stopifnot(nrow(bbmri_portugal_region_labels(countries, cfg, cfg$standard_crs, character())) == 0)
mainland <- bbmri_clip_to_bbox(countries[countries$iso_a2 == "PT",],
                              c(xmin=-10, ymin=38, xmax=-8, ymax=41))
stopifnot(nrow(bbmri_portugal_region_labels(mainland, cfg, cfg$standard_crs, "PT")) == 0)
cfg$oec_insets <- Filter(function(x) x$id != "qa", cfg$oec_insets)
empty <- bbmri_oec_resolve_insets(cfg, countries, points[0,], nodes[0,], lines)
stopifnot(length(empty) == 2)
'''], check=False)
    if result.returncode == 77:
        pytest.skip("sf unavailable: geometry and label integration not executed")
    result.check_returncode()
