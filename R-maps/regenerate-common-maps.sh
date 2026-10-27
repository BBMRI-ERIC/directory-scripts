#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
purge_directory_cache=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --purge-directory-cache)
      purge_directory_cache=1
      shift
      ;;
    -h|--help)
      cat <<EOF
Usage: $(basename "$0") [--purge-directory-cache]

Regenerate the common BBMRI map set via export.sh.
EOF
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
    *)
      echo "This wrapper only accepts --purge-directory-cache." >&2
      exit 2
      ;;
  esac
done

printf 'Generating common BBMRI maps into %s\n' "$script_dir/pilot-output"
if [ "$purge_directory_cache" -eq 1 ]; then
  set -- --purge-directory-cache
else
  set --
fi

exec "$script_dir/export.sh" "$@" \
  bbmri-members-nolabels \
  bbmri-members-nolabelcountry \
  bbmri-members-labels \
  bbmri-members-sized \
  bbmri-members-OEC-all \
  global-nolabels \
  global-nolabelcountry \
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
