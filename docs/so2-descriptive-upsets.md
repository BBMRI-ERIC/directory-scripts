# SO2 Descriptive UpSet Assets

## Purpose

The SO2 descriptive report can optionally embed pre-rendered UpSet and
observed-minus-expected intersection-deviation figures. The main
`describe` command remains the only report-rendering command. R is not a
runtime dependency of normal descriptive reporting.

## Selected Definitions

The versioned UpSet-definition registry contains only these report figures:

- `q_009`
- `q_012`
- `q_018`
- `q_035`
- `q_042`
- `q_050`
- `q_042 + q_044`
- `q_035 + q_050`

For a combined definition, retain only submitted rows that answer every
source question. Prefix every set label with its source question identifier
so values from different questions cannot collide.

## Artifact Workflow

1. Generate a descriptive JSON payload with `describe`.
2. Run `export-descriptive-upset-r -i PAYLOAD --output-dir DIR`. It writes
   canonical respondent vectors, per-definition CSV files, an input manifest,
   and `render-descriptive-upsets.R`.
3. Run that R script in an R environment with `ComplexUpset`, `ggplot2`, and
   `jsonlite` installed. Native R and Debian-proot examples are below.
4. Re-run the normal `describe` command with `--upset-assets-dir DIR` and its
   requested TeX/PDF/chart outputs. It validates and embeds the figures.

The R renderer uses `ComplexUpset` for the UpSet figure and `ggplot2` for the
deviation figure. Each definition emits an UpSet PDF and a deviation PDF.
Respondent matrices and numeric distribution panels are not report artifacts
in this scope.

## Canonical Data Contract

Descriptive payloads must retain canonical respondent vectors for each
configured multi-choice question. A vector contains the source row, reported
country, reported institution, response state (`answered`, `missing`, or
`inapplicable`), and the selected declared categories. It is the sole source
for UpSet export; presentation-oriented contribution rows are not reversed to
reconstruct it.

The input manifest records a canonical SHA-256 hash of the normalized vectors,
the selected-definition registry, the descriptive schema, and the form
manifest. The R renderer writes an output manifest after all expected files
are created. A non-empty asset directory is accepted only when both manifests
agree and all expected PDFs exist. Unknown, stale, incomplete, or mismatching
assets are errors.

## Report Behavior

- Without `--upset-assets-dir`, descriptive reports omit the optional UpSet
  section.
- With an explicitly supplied empty directory, each configured definition has
  a titled note: `UpSet charts omitted: no rendered assets.`
- With a validated non-empty directory, the report embeds the corresponding
  UpSet and deviation PDFs in the related question section or combined-question
  subsection.

The final report PDF embeds the figures. The optional TeX source references
the validated asset directory and therefore requires that sidecar directory to
be retained for later TeX recompilation.

## Operator Commands

```sh
python3 survey-so2-directory.py describe \
  -i Content_Export_SO2_2025_20260916.xlsx \
  --descriptive-schema survey-mappings/so2_2025_descriptive_report.json \
  --form-json survey-mappings/so2_2025_form.json \
  -o so2-2025-20260916-descriptive.json \
  --overwrite

python3 survey-so2-directory.py export-descriptive-upset-r \
  -i so2-2025-20260916-descriptive.json \
  --output-dir so2-2025-20260916-upsets

# Native R, on a workstation or server with R installed.
Rscript -e 'install.packages(c("ComplexUpset", "ggplot2", "jsonlite"), repos="https://cloud.r-project.org")'
Rscript so2-2025-20260916-upsets/render-descriptive-upsets.R
```

### R in Termux Debian proot

R does not need to be installed in Termux itself. Install the Debian proot
once, then install R and the renderer dependencies inside that proot:

```sh
pkg install proot-distro
proot-distro install debian

proot-distro login debian \
  --bind /storage/emulated/0:/storage/emulated/0 \
  -- /bin/bash

# Run these commands inside the Debian shell.
apt update
apt install -y r-base r-cran-ggplot2 r-cran-jsonlite
Rscript -e 'install.packages("ComplexUpset", repos="https://cloud.r-project.org")'
exit
```

The `/storage/emulated/0` bind is required: it makes the generated bundle and
its input CSV files visible to R at the same path as Termux. Run the renderer
through that bound path whenever figures must be regenerated:

```sh
proot-distro login debian \
  --bind /storage/emulated/0:/storage/emulated/0 \
  -- /bin/bash

Rscript /storage/emulated/0/BBMRI-ERIC/directory-scripts/so2-2025-20260916-upsets/render-descriptive-upsets.R
exit
```

Continue in Termux with the normal `describe` command:

```sh
python3 survey-so2-directory.py describe \
  -i Content_Export_SO2_2025_20260916.xlsx \
  --descriptive-schema survey-mappings/so2_2025_descriptive_report.json \
  --form-json survey-mappings/so2_2025_form.json \
  -o so2-2025-20260916-descriptive.json \
  --output-tex so2-2025-20260916-descriptive.tex \
  --output-pdf so2-2025-20260916-descriptive.pdf \
  --output-chart-dir so2-2025-20260916-charts \
  --upset-assets-dir so2-2025-20260916-upsets \
  --overwrite
```

## Validation

Tests must cover vector construction, combined-question inner joins, stable
category prefixing, manifest hashes, empty-directory omission notes, complete
asset embedding, and every rejection path for stale or incomplete assets.
R execution tests are conditional on an available `Rscript`; static tests must
verify generated R syntax and required-package checks.
