# Survey Participation Maps

Maps are optional on `survey-analysis`: Python prepares country counts, R renders
them, and ordinary report commands validate and embed the PDFs. SO2 `describe`
and rendering remain Directory-free and never launch R.

## Prepare

Generate the ordinary SO2 descriptive and MuCP combined JSON first. They must
refer to identical SO2 workbook bytes. A hash mismatch requires regenerating
matching inputs, not editing hashes.
MuCP JSON must contain a complete matching inventory and its
`metadata.mucp_source_coverage.input_records` declaration. Older JSON lacking
that evidence needs regeneration with the current `merge-mucp` command.

```sh
python3 survey-so2-directory.py export-so2-map-r \
  -i so2-2025-20260916-descriptive.json \
  --map-layout both --output-dir so2-participation-maps

python3 survey-so2-directory.py export-mucp-map-r \
  -i so2-mucp-readable.json \
  --so2-json so2-2025-20260916-descriptive.json \
  --directory-inventory so2-participation-maps/directory-inventory.json \
  --map-layout both --output-dir mucp-participation-maps
```

Layouts: `bbmri-members`, `oec`, or `both` (default). Both layouts produce four
SO2 maps (counts and percentages) and two MuCP comparison maps. Preparation does
not run R. Without `--directory-inventory`, it freezes the configured Directory
inventory using shared cache/authentication options. Reusing that file gives both
map families identical denominators without another connection.

Default Directory scope is active biobanks. `-w` includes withdrawn inventory;
`--only-withdrawn` selects withdrawn inventory only. These options change the
denominator, not the respondents. Supply matching schema/withdrawn options when
reusing an inventory. Private schemas require normal explicit authentication;
`--directory-target` selects another instance. Original observation time remains
unknown if the shared cache does not provide it; the inventory hash is preserved.

Export `--overwrite` replaces the prepared bundle after staging, including old
rendered maps; render again afterwards. Outputs must not contain source inputs.

## Render

```sh
bash scripts/render-so2-maps.sh so2-participation-maps
bash scripts/render-mucp-maps.sh mucp-participation-maps
```

The helpers locate the checkout independently of cwd. Options are `--overwrite`,
`--rscript PATH`, and `--` before a bundle name starting with a hyphen.

- Termux automatically uses Debian through `proot-distro` with the required binds.
- Cygwin automatically uses Windows `Rscript.exe`, never launches RStudio, and
  converts native paths through `cygpath`. Discovery checks `--rscript`, `RSCRIPT`,
  PATH, R_HOME and versioned R installations under Program Files.
- Other systems use `--rscript`, `RSCRIPT` or native `Rscript` on PATH.

```sh
# Example Windows executable override:
bash scripts/render-so2-maps.sh \
  --rscript '/cygdrive/c/Program Files/R/R-4.5.0/bin/Rscript.exe' \
  so2-participation-maps
```

R requires `ggplot2`, `sf`, `cowplot`, `jsonlite` and `digest`. Nothing is installed
automatically. An operator can explicitly install Debian dependencies:

```sh
proot-distro login debian -- apt-get update
proot-distro login debian -- apt-get install --no-install-recommends \
  r-base r-cran-ggplot2 r-cran-sf r-cran-cowplot r-cran-jsonlite r-cran-digest
```

The Debian packages also require geospatial libraries and other R packages;
`--no-install-recommends` avoids optional plotting and testing stacks.
Use the normal R package manager elsewhere. The existing Natural Earth loader
downloads basemaps on first use, then reuses `R-maps/cache/natural-earth`.
Uncached first rendering needs network access; questionnaires are not uploaded.
Renderer/config changes after preparation require re-exporting inputs.

Successful rendering publishes vector PDF, 300 dpi PNG and an output manifest
with counts, hashes, runtime evidence and physical collision-audit boxes. Failure
preserves the previous complete set instead of publishing partial maps.
PDF and PNG have separate device-measured audits. If restoring an old output
fails because the destination remains locked, the renderer retains a
`.map-backup-...` directory and reports its recovery path; keep those originals.

## Include

Add to the existing command, retaining all its ordinary input/output options:

```sh
# SO2 describe (or render-descriptive-report):
--map-assets-dir so2-participation-maps --overwrite

# MuCP merge-mucp:
--map-assets-dir mucp-participation-maps --overwrite
```

SO2 maps follow Responses Summary; MuCP maps appear in the opening overview.
MuCP comparison maps describe both complete surveys independently of `--join`.
A supplied unrendered bundle produces an omitted-map note; stale, partial,
wrong-kind or tampered rendered assets block publication.

Published TeX uses a portable sibling `map-assets-...` directory. Keep it with
the TeX when moving/recompiling; the original R bundle is not needed. Requested
standalone chart directories receive PDF copies as well.
Report outputs and their automatically named companion directories must be
disjoint from the source map bundle, including when `--overwrite` is enabled.

## Interpret

- Directory outline D, SO2 fill S, label `S of D`: S includes unresolved
  individuals and can exceed D. This compares participation with inventory, not
  strict coverage within registered biobanks. The inventory date may differ.
- Green maps show `100*S/D`, including values above 100. Grey/N/A is an absent
  denominator; S=0 with D>0 is a genuine zero, not missing data.
- MuCP M and SO2 S are adjacent totals. Their orange base segments show the
  same confirmed shared biobanks, not additional participants. Unknown possible
  matches are not guessed.
- Known duplicate submissions/scopes count once. Unlinked unresolved individual
  respondents remain provisional and are disclosed, not silently removed.
- A national summary itself counts zero. Only identifiable constituent biobanks
  extracted from owned scoped evidence can count, deduplicated against other
  responses. Neither collections nor an unassigned residual add extra biobanks.
- Country follows reported geography, not staging prefix: EXT may contribute
  to any country. Unknown-country individuals remain in the audit/footer; countries
  outside the geographic extent have explicitly identified callouts.
- If SO2 and MuCP report different countries for a shared identity absent from
  the frozen Directory inventory, each survey keeps its own country. Its shared
  linkage stays in the separate country-conflict audit until a reviewed country resolves
  the disagreement; MuCP cannot silently change SO2 geography.

For additional reviewed links, pass `--participation-identities PRIVATE.json` to
both exports. Start from `survey-mappings/survey_participation_identities.example.json`.
Groups require `unit_id`, `country`, `reason`, and `sources` containing `survey`,
`record_id` and optional owned collection `scope_id`. Enter actual SO2/MuCP source
hashes; known Directory identities retain their canonical ID. National-summary
references require individual scope decomposition. Keep review files, inventories,
source-bound manifests and generated reports private/local.
Country corrections apply only to the surveys named in that group's references;
include both survey references when correcting both. Rejected scope proposals
do not erase an otherwise unresolved individual response.

Portable tests validate counting, shell dispatch, source bindings and rollback.
Real R/grid tests measure font/glyph placement. Full geographic rendering requires
the geospatial packages. Cygwin dispatch mocks do not establish that an actual
Windows R installation is healthy; a real-host smoke check is separate evidence.
