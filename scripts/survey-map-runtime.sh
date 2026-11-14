#!/usr/bin/env bash
# Shared runtime selection; sourced by the two survey map entry scripts.

survey_map_main() {
    local kind=$1 runtime=${RSCRIPT:-} bundle='' overwrite='' host repo renderer
    shift
    while (($#)); do
        case "$1" in
            --rscript)
                (($# >= 2)) || { echo 'Missing --rscript executable path' >&2; return 2; }
                runtime=$2; shift 2 ;;
            --overwrite) overwrite=--overwrite; shift ;;
            --) shift; break ;;
            -h|--help)
                echo "Usage: bash render-$kind-maps.sh [--rscript PATH] [--overwrite] [--] BUNDLE_DIR"
                return 0 ;;
            -*) echo "Unknown option: $1" >&2; return 2 ;;
            *) break ;;
        esac
    done
    (($# == 1)) || { echo 'Provide exactly one prepared map bundle directory' >&2; return 2; }
    bundle=$(cd -- "$1" && pwd) || return 2
    repo=$(cd -- "$script_dir/.." && pwd)
    renderer=$repo/R-maps/render_survey_participation.R
    python3 -c 'import json,sys; m=json.load(open(sys.argv[1],encoding="utf-8")); sys.exit(0 if m.get("kind")==sys.argv[2] else 2)' \
        "$bundle/input-manifest.json" "$kind" || { echo "Not a prepared $kind map bundle" >&2; return 2; }
    host=$(uname -s)
    local -a args=("$renderer" "--bundle=$bundle" "--kind=$kind")
    [[ -z $overwrite ]] || args+=("$overwrite")
    if [[ $host == CYGWIN* ]]; then
        command -v cygpath >/dev/null || { echo 'Cygwin cygpath is required' >&2; return 2; }
        if [[ -z $runtime ]]; then
            runtime=$(command -v Rscript.exe || true)
        fi
        if [[ -z $runtime && -n ${R_HOME:-} ]]; then
            runtime="$(cygpath -u "$R_HOME")/bin/Rscript.exe"
            [[ -f $runtime ]] || runtime=''
        fi
        if [[ -z $runtime ]]; then
            local program_files
            program_files=$(cygpath -u "${PROGRAMFILES:-C:\\Program Files}") || return 2
            runtime=$(python3 -c 'import glob,re,sys; from pathlib import Path; candidates=glob.glob(sys.argv[1]+"/R/R-*/bin/Rscript.exe"); print(max(candidates,key=lambda p:(tuple(map(int,re.findall(r"\d+",Path(p).parts[-3]))),p)) if candidates else "")' "$program_files")
        fi
        [[ -n $runtime ]] || { echo 'Windows Rscript.exe not found; use --rscript or RSCRIPT (RStudio is not launched)' >&2; return 2; }
        runtime=$(cygpath -u "$runtime")
        args=("$(cygpath -am "$renderer")" "--bundle=$(cygpath -am "$bundle")" "--kind=$kind")
        [[ -z $overwrite ]] || args+=("$overwrite")
        echo "Rendering $kind maps with Windows Rscript.exe: $runtime" >&2
        "$runtime" "${args[@]}"
    elif [[ -n ${TERMUX_VERSION:-} || ${PREFIX:-} == */com.termux/files/usr ]]; then
        command -v proot-distro >/dev/null || { echo 'Termux requires proot-distro and a Debian installation with R' >&2; return 2; }
        local -a binds=(--bind "$repo:$repo")
        if [[ $bundle != "$repo" && $bundle != "$repo/"* ]]; then
            binds+=(--bind "$bundle:$bundle")
        fi
        echo "Rendering $kind maps with Rscript inside Debian proot" >&2
        proot-distro login debian "${binds[@]}" -- "${runtime:-Rscript}" "${args[@]}"
    else
        runtime=${runtime:-Rscript}
        command -v "$runtime" >/dev/null || { echo 'Rscript not found; install R or set --rscript/RSCRIPT' >&2; return 2; }
        echo "Rendering $kind maps with $runtime" >&2
        "$runtime" "${args[@]}"
    fi
}
