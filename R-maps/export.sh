#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)

rscript_bin=${RSCRIPT_BIN:-Rscript}
if [ -x "$repo_root/.venv-maps/bin/python" ]; then
  python_bin=${PYTHON_BIN:-"$repo_root/.venv-maps/bin/python"}
else
  python_bin=${PYTHON_BIN:-python3}
fi

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
map_set="all"
maps=""

usage() {
  cat <<EOF
Usage: $(basename "$0") [options] [MAP_ID ...]

Export one or more R maps. If no MAP_ID is given, all maps are exported.

Map ids:
  bbmri-members-nolabels
  bbmri-members-sized
  bbmri-members-OEC-all
  global-nolabels
  covid-nolabels
  quality_maps-nolabels
  federated-platform
  CRC-cohort-sized

Options:
  --rscript PATH              Rscript binary to use
  --python PATH               Python interpreter for geocoding_2022.py/helpers
  --geocoding-script PATH     geocoding_2022.py path
  --geocoding-config PATH     geocoding.config path
  --full-geojson PATH         full pilot GeoJSON output
  --member-geojson PATH       member/observer pilot GeoJSON output
  --covid-geojson PATH        derived COVID GeoJSON output
  --quality-geojson PATH      derived quality GeoJSON output
  --iarc PATH                 IARC overlay GeoJSON
  --node-points PATH          HQ/node point overlay GeoJSON
  --node-lines PATH           HQ/node line overlay GeoJSON
  --federated-geojson PATH    federated-platform snapshot GeoJSON
  --crc-geojson PATH          CRC cohort snapshot GeoJSON
  --crc-imaging-geojson PATH  CRC cohort imaging snapshot GeoJSON
  --output-dir PATH           render output directory

Compatibility:
  --map-set VALUE             legacy core|extras|all selector

  -h, --help                  show this help
EOF
}

append_map() {
  if [ -z "$maps" ]; then
    maps=$1
  else
    maps=$maps,$1
  fi
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --rscript)
      rscript_bin=$2
      shift 2
      ;;
    --python)
      python_bin=$2
      shift 2
      ;;
    --geocoding-script)
      geocoding_script=$2
      shift 2
      ;;
    --geocoding-config)
      geocoding_config=$2
      shift 2
      ;;
    --full-geojson)
      full_geojson=$2
      shift 2
      ;;
    --member-geojson)
      member_geojson=$2
      shift 2
      ;;
    --covid-geojson)
      covid_geojson=$2
      shift 2
      ;;
    --quality-geojson)
      quality_geojson=$2
      shift 2
      ;;
    --iarc)
      iarc=$2
      shift 2
      ;;
    --node-points)
      node_points=$2
      shift 2
      ;;
    --node-lines)
      node_lines=$2
      shift 2
      ;;
    --federated-geojson)
      federated_geojson=$2
      shift 2
      ;;
    --crc-geojson)
      crc_geojson=$2
      shift 2
      ;;
    --crc-imaging-geojson)
      crc_imaging_geojson=$2
      shift 2
      ;;
    --output-dir)
      output_dir=$2
      shift 2
      ;;
    --map-set)
      map_set=$2
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      while [ "$#" -gt 0 ]; do
        append_map "$1"
        shift
      done
      break
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      append_map "$1"
      shift
      ;;
    esac
done

cd "$repo_root"
export DIRECTORY_CACHE_ROOT="$repo_root"

exec "$rscript_bin" "$script_dir/render_pilot_maps.R" \
  --map-set="$map_set" \
  --maps="$maps" \
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
