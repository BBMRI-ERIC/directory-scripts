#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
output_dir="$script_dir/pilot-output"
history_root="$script_dir/compare-temp/history"
label=""
keep=8

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Copies the current rendered map outputs into a timestamped local history folder
for visual comparison. This is intended for manual/agentic review workflows and
stores files only under ignored paths.

Options:
  --output-dir PATH   directory containing current rendered outputs
  --history-root PATH directory where snapshots should be stored
  --label TEXT        short label appended to the snapshot directory name
  --keep N            number of most recent snapshot directories to keep
  -h, --help          show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      output_dir="$2"
      shift 2
      ;;
    --history-root)
      history_root="$2"
      shift 2
      ;;
    --label)
      label="$2"
      shift 2
      ;;
    --keep)
      keep="$2"
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

if [[ ! -d "$output_dir" ]]; then
  echo "Output directory not found: $output_dir" >&2
  exit 1
fi

if ! [[ "$keep" =~ ^[0-9]+$ ]] || [[ "$keep" -lt 1 ]]; then
  echo "--keep must be a positive integer" >&2
  exit 2
fi

map_files=(
  "$output_dir"/bbmri-members-*.png
  "$output_dir"/bbmri-members-*.pdf
)

shopt -s nullglob
resolved_files=()
for path in "${map_files[@]}"; do
  resolved_files+=("$path")
done
shopt -u nullglob

if [[ "${#resolved_files[@]}" -eq 0 ]]; then
  echo "No rendered map files found under: $output_dir" >&2
  exit 1
fi

timestamp="$(date +%Y%m%d-%H%M%S)"
safe_label=""
if [[ -n "$label" ]]; then
  safe_label="-$(printf '%s' "$label" | tr ' /' '__' | tr -cd '[:alnum:]_.-')"
fi

snapshot_dir="$history_root/$timestamp$safe_label"
mkdir -p "$snapshot_dir"

for path in "${resolved_files[@]}"; do
  cp -p "$path" "$snapshot_dir/"
done

{
  echo "timestamp=$timestamp"
  echo "label=${label:-}"
  echo "source_output_dir=$output_dir"
  echo "file_count=${#resolved_files[@]}"
} > "$snapshot_dir/manifest.txt"

mapfile -t snapshot_dirs < <(find "$history_root" -mindepth 1 -maxdepth 1 -type d | sort)
if [[ "${#snapshot_dirs[@]}" -gt "$keep" ]]; then
  remove_count=$(( ${#snapshot_dirs[@]} - keep ))
  for old_dir in "${snapshot_dirs[@]:0:$remove_count}"; do
    rm -rf "$old_dir"
  done
fi

echo "Archived ${#resolved_files[@]} files to $snapshot_dir"
