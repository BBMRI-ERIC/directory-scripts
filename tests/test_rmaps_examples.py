import shutil
import subprocess
from pathlib import Path

import pytest


EXAMPLE_SCRIPTS = [
    Path("R-maps/examples/00_setup.R"),
    Path("R-maps/examples/01_render_existing_map.R"),
    Path("R-maps/examples/02_country_labels_and_coloring.R"),
    Path("R-maps/examples/03_legends_and_overlays.R"),
    Path("R-maps/examples/04_complex_overlay_template.R"),
]


@pytest.mark.parametrize("script_path", EXAMPLE_SCRIPTS)
def test_rmaps_example_scripts_parse(script_path):
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript not available")

    script = script_path.as_posix()
    subprocess.run([rscript, "-e", f'parse(file="{script}")'], check=True)
