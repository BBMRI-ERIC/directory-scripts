# Survey Analysis

SO2 and Multi-Country Project (MuCP) tools are maintained on the public
`survey-analysis` branch. The default `master` branch contains Directory QC,
exporters, maintenance tools, maps and shared libraries without survey tooling.
Branch separation simplifies checkouts; it does not restrict public history.

## Getting Started

From an existing clone with a clean tracked working tree:

```sh
git fetch origin
git switch survey-analysis
python3 -m pip install -r requirements-surveys.txt
python3 survey-so2-directory.py --help
```

Run commands from the repository root. Shared `directory.py` and helpers are
imported directly from the clone; no separate Directory package is required.
Use `git switch master` to return to the core tools. Git may refuse a switch
that would overwrite local changes; commit or otherwise preserve those changes
deliberately rather than forcing the switch.

Private inputs, reviewed decisions, generated PDFs and runtime caches are not
distributed. Ignored local files remain on disk when switching branches. Do
not stage them or assume the public survey branch makes reports safe to share.

## Guides

- [SO2 workflows](so2.md): Directory analysis, descriptive statistics, form
  manifests, response merging, scoring and update-plan exports.
- [MuCP and combined reports](mucp.md): identity review, cohort selection,
  provenance, collection scope, quantities and report interpretation.
- [External UpSet charts](upsets.md): R generation, native and Termux/proot
  execution, validation and embedding.
- [Survey specifications](DEVELOPMENT.md): normative functionality contracts.
- [Survey agent instructions](AGENTS.md): implementation guardrails.
- [Separation design](branch-separation-design.md) and
  [execution plan](branch-separation-plan.md): ownership and migration evidence.

Optional chart compilation requires the documented TeX packages; external
ComplexUpset assets require R only for their separate rendering step. Normal
descriptive reporting does not launch R. EUS archive conversion is optional;
ordinary reports reuse the committed JSON form manifest.

## Maintenance

Keep shared fixes on `master` where practical, then merge `master` into
`survey-analysis` and validate core and survey tests. Never merge the entire
survey branch back to `master`; transfer genuine shared fixes individually.
Detailed survey knowledge belongs here, not in common root documentation.
Shared architecture and privacy rules remain in
[root DEVELOPMENT.md](../../DEVELOPMENT.md) and [root AGENTS.md](../../AGENTS.md).

```sh
python3 -m pip install -r requirements-test.txt
pytest -q
```

Synthetic fixtures support validation without private survey exports. Optional
source-bound replay requires separately held inputs and is not a substitute for
the portable tests.
