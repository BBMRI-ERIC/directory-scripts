#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)

cd "$repo_root"

if [ "$#" -gt 0 ]; then
  printf 'Generating strategic-objectives example maps into %s for: %s\n' "$script_dir/compare-temp/examples" "$*"
else
  printf 'Generating strategic-objectives example maps into %s\n' "$script_dir/compare-temp/examples"
fi
exec Rscript "$script_dir/examples/06_strategic_objectives_maps.R" "$@"
