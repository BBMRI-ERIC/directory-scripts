"""Verify requested BBMRI map memberships and effective country colours."""

from pathlib import Path
import json
import shutil
import subprocess

import pytest


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
