"""Verify requested BBMRI map memberships and effective country colours."""

from pathlib import Path
import importlib.util
import json
import shutil
import subprocess

import pytest

from nncontacts import NNContacts


@pytest.fixture
def rare_disease_prep():
    """Load the rare-disease preparation module without running its CLI.

    Returns:
        Module exposing the pure biobank membership classifier.
    """
    path = Path(__file__).resolve().parents[1] / "R-maps/prepare_rare_diseases_geojson.py"
    spec = importlib.util.spec_from_file_location("rare_disease_prep", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("country", sorted(NNContacts.MEMBER_NODE_CODES))
def test_rare_disease_nodes_and_ext_override(rare_disease_prep, country):
    """Member/observer biobanks are magenta unless managed in EXT.

    Args:
        rare_disease_prep: Imported preparation module.
        country: Member or observer country from the canonical Node registry.

    Returns:
        None. Every Node country follows the same EXT override rule.
    """
    biobank = {"id": f"bbmri-eric:ID:{country}_demo", "country": {"id": country}}
    assert rare_disease_prep.biobank_membership_role(biobank) == "member"
    biobank["id"] = "bbmri-eric:ID:EXT_demo"
    assert rare_disease_prep.biobank_membership_role(biobank) == "non_member"


@pytest.mark.parametrize("country", ["US", "FR", "", None])
def test_rare_disease_outside_nodes_is_green(rare_disease_prep, country):
    """Outside or unknown countries remain green even with a Node-like ID.

    Args:
        rare_disease_prep: Imported preparation module.
        country: Country outside the configured member/observer set.

    Returns:
        None. Country eligibility and EXT management are checked independently.
    """
    biobank = {"id": "bbmri-eric:ID:DE_demo", "country": country}
    assert rare_disease_prep.biobank_membership_role(biobank) == "non_member"


@pytest.fixture
def r_command():
    """Locate an R runtime without installing or modifying the environment.

    Returns:
        Command prefix for native Rscript or the existing Debian proot runtime;
        skips the test when neither runtime is available.
    """
    native = shutil.which("Rscript")
    if native:
        return [native]
    proot = shutil.which("proot-distro")
    if proot:
        command = [proot, "login", "debian", "--", "Rscript"]
        probe = subprocess.run(command + ["--version"], capture_output=True)
        if probe.returncode == 0:
            return command
    pytest.skip("Native Rscript or Debian proot Rscript required")


def test_requested_map_memberships_and_labels(r_command):
    """Check membership, observer status, labels and gray-list precedence.

    Args:
        r_command: Existing R runtime command prefix supplied by the fixture.

    Returns:
        None. All requested countries have unambiguous map classifications.
    """
    script = r'''
source("R-maps/map_config.R")
cfg <- bbmri_map_config()
members <- c("PT", "CY")
observers <- c("UA", "ME", "DK", "TR")
for (name in c("standard_country_groups", "oec_country_groups", "fedplat_country_groups")) {
  groups <- cfg[[name]]
  stopifnot(all(members %in% groups$member), all(observers %in% groups$observer))
  stopifnot(length(intersect(groups$member, groups$observer)) == 0)
  stopifnot(!any(c(members, observers) %in% groups$gray))
  stopifnot("QA" %in% groups$observer)
}
stopifnot(all(c(members, observers) %in% cfg$standard_country_labels))
stopifnot(all(c(members, observers) %in% cfg$fedplat_country_labels))
'''
    root = Path(__file__).resolve().parents[1]
    script = f"setwd({json.dumps(str(root))})\n" + script
    subprocess.run(r_command + ["-e", script], cwd=root, check=True)


def test_python_node_registry_matches_r_map_countries(r_command):
    """Keep Python classification aligned with the R member/observer palette.

    Args:
        r_command: Existing R runtime command prefix.

    Returns:
        None. Both languages recognize exactly the same Node countries.
    """
    script = '''
source("R-maps/map_config.R")
groups <- bbmri_map_config()$standard_country_groups
cat(paste(sort(unique(c(groups$member, groups$observer))), collapse = ","))
'''
    result = subprocess.run(r_command + ["-e", script], check=True, capture_output=True, text=True)
    assert set(result.stdout.strip().split(",")) == NNContacts.MEMBER_NODE_CODES


def test_rare_disease_circle_sizes_are_independent_of_color(r_command):
    """Use identical size scales for magenta and green points at every output size.

    Args:
        r_command: Existing R runtime command prefix.

    Returns:
        None. Fixed maps have one size; sized maps share two sizes across colors.
    """
    script = r'''
source("R-maps/render_rare_diseases_common.R")
points <- sf::st_as_sf(data.frame(
  biobankID = paste0("bbmri-eric:ID:DE_", 1:4),
  biobankName = paste("Test", 1:4),
  biobankType = "biobank",
  biobankSize = c("1", "5", "1", "5"),
  rdMembership = c("member", "member", "non_member", "non_member"),
  lon = c(9, 10, 11, 12), lat = c(49, 50, 51, 52)
), coords = c("lon", "lat"), crs = 4326)
path <- tempfile(fileext = ".geojson")
sf::st_write(points, path, quiet = TRUE)
cfg <- bbmri_map_config()
for (variant in c("small", "med", "big")) {
  for (sized in c(FALSE, TRUE)) {
    plot <- build_rare_diseases_map(
      path, output_variant = variant, include_biobank_labels = FALSE,
      point_size_value = if (sized) NULL else 10
    )
    index <- which(vapply(plot$layers, function(layer) inherits(layer$geom, "GeomPoint"), logical(1)))[[1]]
    data <- ggplot2::ggplot_build(plot)$data[[index]]
    magenta <- sort(data$size[data$fill == cfg$rd_colors$member])
    green <- sort(data$size[data$fill == cfg$rd_colors$non_member])
    stopifnot(length(magenta) == 2, identical(magenta, green))
    stopifnot(length(unique(magenta)) == if (sized) 2 else 1)
  }
}
'''
    subprocess.run(r_command + ["-e", script], check=True)


def test_nolabelcountry_omits_country_text_and_preserves_points(r_command):
    """Remove country labels in both scopes without changing their biobank dots.

    Args:
        r_command: Existing R runtime command prefix.

    Returns:
        None. New IDs are selectable; existing maps retain their country labels.
    """
    script = r'''
source("R-maps/render_pilot_maps.R")
ids <- c("bbmri-members-nolabelcountry", "global-nolabelcountry")
stopifnot(identical(bbmri_normalize_map_selection(paste(ids, collapse = ",")), ids))
stopifnot(ids[[1]] %in% bbmri_map_ids_for_set("core"))
stopifnot(ids[[2]] %in% bbmri_map_ids_for_set("extras"))
points <- sf::st_as_sf(data.frame(
  biobankID = "bbmri-eric:ID:DE_test", biobankType = "biobank", lon = 10, lat = 50
), coords = c("lon", "lat"), crs = 4326)
path <- tempfile(fileext = ".geojson")
sf::st_write(points, path, quiet = TRUE)
for (builder in list(build_members_nolabels_map, build_global_nolabels_map)) {
  original <- builder(path, output_variant = "med")
  hidden <- builder(path, output_variant = "med", include_country_labels = FALSE)
  is_text <- function(layer) inherits(layer$geom, "GeomText")
  stopifnot(any(vapply(original$layers, is_text, logical(1))))
  stopifnot(!any(vapply(hidden$layers, is_text, logical(1))))
  point_data <- function(plot) {
    index <- which(vapply(plot$layers, function(layer) inherits(layer$geom, "GeomPoint"), logical(1)))[[1]]
    ggplot2::ggplot_build(plot)$data[[index]]
  }
  stopifnot(identical(point_data(original), point_data(hidden)))
}
'''
    subprocess.run(r_command + ["-e", script], check=True)


def test_requested_map_colours_and_platform_overlay(r_command):
    """Exercise actual fill helpers without downloading a basemap or loading sf.

    Args:
        r_command: Existing R runtime command prefix supplied by the fixture.

    Returns:
        None. Member/observer fills propagate while Cyprus keeps its FP overlay.
    """
    script = r'''
source("R-maps/map_config.R")
source("R-maps/map_common.R")
cfg <- bbmri_map_config()
countries <- data.frame(iso_a2 = c("PT", "CY", "UA", "ME", "DK", "TR", "QA", "FR"))
for (variant in c("standard", "oec")) {
  fill <- get(paste0("bbmri_assign_", variant, "_country_fill"))(countries, cfg)$fill_group
  palette <- cfg[[paste0(variant, "_colors")]]
  stopifnot(all(fill[1:2] == palette$member), all(fill[3:7] == palette$observer))
}
fill <- bbmri_assign_fedplat_country_fill(countries, cfg)$fill_group
stopifnot(fill[1] == cfg$fedplat_colors$member, fill[2] == cfg$fedplat_colors$fedplat)
stopifnot(all(fill[3:7] == cfg$fedplat_colors$observer))
'''
    root = Path(__file__).resolve().parents[1]
    script = f"setwd({json.dumps(str(root))})\n" + script
    subprocess.run(r_command + ["-e", script], cwd=root, check=True)
