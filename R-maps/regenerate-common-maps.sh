#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

printf 'Generating common BBMRI maps into %s\n' "$script_dir/pilot-output"
exec "$script_dir/export.sh" \
  bbmri-members-nolabels \
  bbmri-members-labels \
  bbmri-members-sized \
  bbmri-members-OEC-all \
  global-nolabels \
  global-labels \
  global-sized \
  covid-nolabels \
  covid-labels \
  covid-sized \
  quality_maps-nolabels \
  federated-platform \
  CRC-cohort-sized \
  rare-diseases-nolabels \
  rare-diseases-labels \
  rare-diseases-sized
