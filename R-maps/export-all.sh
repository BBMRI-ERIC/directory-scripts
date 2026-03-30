#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

rscript_bin="${RSCRIPT_BIN:-Rscript}"
python_bin="$repo_root/.venv-maps/bin/python"
geocoding_script="$repo_root/geocoding_2022.py"
geocoding_config="$repo_root/geocoding.config"
full_geojson="$repo_root/bbmri-directory-pilot.geojson"
member_geojson="$repo_root/bbmri-directory-members-pilot.geojson"
covid_geojson="$repo_root/bbmri-directory-covid-pilot.geojson"
quality_geojson="$repo_root/bbmri-directory-quality-pilot.geojson"
iarc="$script_dir/data/IARC.geojson"
node_points="$script_dir/data/HQlineNN.geojson"
node_lines="$script_dir/data/onlyLinesHQlineNN.geojson"
federated_geojson="$script_dir/data/federated-platform.geojson"
crc_geojson="$script_dir/data/CRC-Cohort.geojson"
crc_imaging_geojson="$script_dir/data/CRC-Cohort-imaging.geojson"
output_dir="$script_dir/pilot-output"
map_set="core"

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Runs the R map export pipeline:
  core:
    1. refreshes the pilot GeoJSON from geocoding_2022.py
    2. derives the member/observer subset GeoJSON
    3. renders nolabels, sized, and OEC-all outputs
  extras:
    1. refreshes the pilot GeoJSON from geocoding_2022.py
    2. derives the COVID and quality GeoJSONs
    3. renders global-nolabels, covid-nolabels, quality_maps-nolabels,
       federated-platform, and CRC-cohort-sized outputs

Options:
  --map-set VALUE          core, extras, or all (default: core)
  --rscript PATH            Rscript binary to use
  --python PATH             Python interpreter for geocoding_2022.py
  --geocoding-script PATH   geocoding_2022.py path
  --geocoding-config PATH   geocoding.config path
  --full-geojson PATH       full pilot GeoJSON output
  --member-geojson PATH     member/observer pilot GeoJSON output
  --covid-geojson PATH      derived COVID GeoJSON output
  --quality-geojson PATH    derived quality GeoJSON output
  --iarc PATH               IARC overlay GeoJSON
  --node-points PATH        HQ/node point overlay GeoJSON
  --node-lines PATH         HQ/node line overlay GeoJSON
  --federated-geojson PATH  federated-platform snapshot GeoJSON
  --crc-geojson PATH        CRC cohort snapshot GeoJSON
  --crc-imaging-geojson PATH CRC cohort imaging snapshot GeoJSON
  --output-dir PATH         render output directory
  -h, --help                show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --map-set)
      map_set="$2"
      shift 2
      ;;
    --rscript)
      rscript_bin="$2"
      shift 2
      ;;
    --python)
      python_bin="$2"
      shift 2
      ;;
    --geocoding-script)
      geocoding_script="$2"
      shift 2
      ;;
    --geocoding-config)
      geocoding_config="$2"
      shift 2
      ;;
    --full-geojson)
      full_geojson="$2"
      shift 2
      ;;
    --member-geojson)
      member_geojson="$2"
      shift 2
      ;;
    --covid-geojson)
      covid_geojson="$2"
      shift 2
      ;;
    --quality-geojson)
      quality_geojson="$2"
      shift 2
      ;;
    --iarc)
      iarc="$2"
      shift 2
      ;;
    --node-points)
      node_points="$2"
      shift 2
      ;;
    --node-lines)
      node_lines="$2"
      shift 2
      ;;
    --federated-geojson)
      federated_geojson="$2"
      shift 2
      ;;
    --crc-geojson)
      crc_geojson="$2"
      shift 2
      ;;
    --crc-imaging-geojson)
      crc_imaging_geojson="$2"
      shift 2
      ;;
    --output-dir)
      output_dir="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

exec "$rscript_bin" "$script_dir/render_pilot_maps.R" \
  --map-set="$map_set" \
  --python="$python_bin" \
  --geocoding-script="$geocoding_script" \
  --geocoding-config="$geocoding_config" \
  --full-geojson="$full_geojson" \
  --member-geojson="$member_geojson" \
  --covid-geojson="$covid_geojson" \
  --quality-geojson="$quality_geojson" \
  --iarc="$iarc" \
  --node-points="$node_points" \
  --node-lines="$node_lines" \
  --federated-geojson="$federated_geojson" \
  --crc-geojson="$crc_geojson" \
  --crc-imaging-geojson="$crc_imaging_geojson" \
  --output-dir="$output_dir"
