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

## Descriptive Bundle Integration

### Optional ComplexUpset figures

The descriptive report can embed the approved eight multi-choice UpSet and
observed-minus-expected deviation figures without making R a Termux runtime
dependency. First generate the JSON payload, then create the external bundle:

```bash
python3 survey-so2-directory.py export-descriptive-upset-r \
  -i so2-descriptive.json --output-dir so2-upsets
```

Run `so2-upsets/render-descriptive-upsets.R` in an R environment containing
`ComplexUpset`, `ggplot2`, and `jsonlite`. See
[SO2 Descriptive UpSet Assets](upsets.md) for native-R and
Termux Debian-proot installation and execution commands. Finally rerun the
normal `describe` command with `--upset-assets-dir so2-upsets`. An explicitly
empty existing assets directory
adds omission notes; a nonempty directory must contain a current completed
bundle whose canonical hash matches the newly generated payload. The final PDF
embeds the figures, while TeX references the sidecar PDFs and therefore needs
the validated bundle retained for later recompilation.


## Combined Report Assets

Every shared UpSet bar is labelled `I1`, `I2`, etc. Its immediately following table
lists the exact intersection's biobanks grouped by country. Bar heights are exclusive
intersection counts, not left-hand set totals. Bundle validation checks actual built
bar/matrix order and counts, including ties and empty patterns. New cohort or renderer
changes invalidate old bundles; regenerate both R and PDFs, never edit hashes.

For the current local workflow use `--join all-MuCP`, generate the new bundle with
`--output-upset-r-dir so2-mucp-all-MuCP-upsets`, run its generated R script, and rerun
the identical inputs with `--upset-assets-dir so2-mucp-all-MuCP-upsets --overwrite`.
Do not supply old overlap-only assets. Final outputs can continue to use
`so2-mucp-readable.json`, `.tex` and `.pdf`.

Default definitions include MuCP biospecimens, OMICs and available data, SO2
technology access, and two source-labelled cross-survey intersections pairing
MuCP OMICs or clinical/imaging data with SO2 technology access. These show
co-reported evidence at the biobank level, not that a technology generates the
reported data or that the same collection has both. Regenerate existing bundles
after changing these definitions or the reviewed overlap cohort.
The required SO2 `Other` and `I don't know` checkboxes are not concrete technology
access sets; their original answers remain in the descriptive statistics and
evidence dossiers. These figures cover the named technologies, not an inferred
availability of unspecified technologies.
Unknown technology answers and Other-only selections are excluded from these
matrices with a recorded reason, not converted into all-zero technology vectors.

Add `--output-upset-r-dir so2-mucp-upsets` to the initial merge command. Run:

```bash
Rscript so2-mucp-upsets/render-descriptive-upsets.R
```

Then rerun the same `merge-mucp` inputs with
`--upset-assets-dir so2-mucp-upsets --overwrite` and the desired PDF targets;
omit `--output-upset-r-dir` on that rerun. The folder is read-only input during
embedding. Empty/missing optional figures are clearly marked omitted; a supplied
nonempty stale or incomplete bundle blocks publication. For Termux, use the
Debian proot installation/bind workflow documented in the SO2 UpSet section below.
The validator checks the actual CSV vectors, renderer script and PDF hashes;
regenerate the bundle after analytical or renderer changes rather than editing
its integrity markers manually.

The default classified MuCP UpSet includes answered all-unticked groups as
all-zero rows. An absent dot means No reported in the represented applicable
scopes, not universal biological absence. Unknown, conditional, conflicting and
incomplete-scope patterns are excluded with reasons; cross-survey SO2 unknowns
remain unknown. Distinct collection reports may refer to different collections.
The external bundle still generates both UpSet and exploratory deviation PDFs,
but the combined report embeds only UpSets by default. Pass
`--include-upset-deviations` to include the exploratory independence-model
pages; they are not significance tests. Refresh the R bundle after changes to
source data, policy, cohort or curated presentation rather than editing hashes.
