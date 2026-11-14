#!/usr/bin/env bash
# Render a prepared SO2 participation bundle using the host-appropriate R runtime.
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$script_dir/survey-map-runtime.sh"
survey_map_main so2 "$@"
