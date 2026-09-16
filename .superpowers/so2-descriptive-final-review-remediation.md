# SO2 descriptive reporting final-review remediation

Date: 2026-09-16
Branch: `so2-descriptive-report-20260916`
Implementation baseline: `26a9b2f Complete SO2 descriptive statistics reporting`

## Scope completed

- Atomic target-local publication avoids cross-device `EXDEV` replacement and rolls back report/chart outputs and hidden staging files on failure.
- Reports include complete provenance, per-question `N`/`A`/`M` and applicability details, explicit `No text responses.`, and self-contained TeX.
- Standalone charts include question, denominator, unit, and missingness context; payload chart paths resolve relative to the report.
- Missing and ordinal exceptional categories use distinct visual semantics.
- Schema applicability and mutually exclusive category declarations are validated; contradictory selections remain counted and are diagnosed.
- Malformed payloads, existing file outputs, and output write failures cross the public `InputError` boundary.
- Public descriptive APIs document arguments, returns, and raised user-facing errors.
- Developer and operator documentation records the release contracts.

## TDD evidence

The final rollback gap was reproduced before its fix:

```text
pytest -q tests/test_so2_descriptive_report.py -k chart_staging_failure_removes_target_filesystem_stages
1 failed: .report.tex.so2-stage-* remained after simulated chart staging failure
```

After discarding report publication stages in the chart-copy failure branch:

```text
pytest -q tests/test_so2_descriptive_report.py -k 'chart_staging_failure_removes_target_filesystem_stages or publication_never_replaces_across_filesystems or rolls_back_all_outputs_when_publication_fails or keeps_final_outputs_absent_when_report_compilation_fails'
4 passed, 62 deselected
```

Focused verification:

```text
pytest -q tests/test_so2_descriptive_report.py tests/test_survey_so2_directory.py
115 passed in 8.65s
```

Static validation passed:

```text
python3 -m py_compile so2_descriptive_report.py survey-so2-directory.py tests/test_so2_descriptive_report.py tests/test_survey_so2_directory.py
python3 -m json.tool survey-mappings/so2_2025_descriptive_report.json
git diff --check
```

Repository-wide verification:

```text
pytest -q
579 passed, 39 skipped, 4 failed in 75.68s
```

All four failures are unrelated, pre-existing Python 3.14/Yapsy incompatibilities: Yapsy imports the removed `imp` module while collecting or invoking `data-check.py` and `exporter-bbmri-cohorts.py`. No SO2 test failed.

## Production smoke

Input:
`/storage/emulated/0/BBMRI-ERIC/directory-scripts/Content_Export_SO2_2025_20260313.xlsx`

Schema:
`survey-mappings/so2_2025_descriptive_report.json`

The real `describe` command completed with JSON, self-contained TeX, report PDF, and all standalone chart PDFs in:
`/data/data/com.termux/files/usr/tmp/so2-production-smoke.meJDCo`

Validated results:

- 105 questions, including 58 structured questions.
- 58 standalone chart PDFs and 58 payload chart paths; every path is relative and resolves from the report directory.
- Zero contradiction diagnostics in this production export.
- Report PDF: 837 pages, 1,066,023 bytes, produced by `xdvipdfmx`.
- Report JSON SHA-256: `4e5b94d61d9d6a32b65c39dc371dbed319ec31eb5956d84ba8c099831d3cc236`.
- Report TeX SHA-256: `a672d839757ed1f12c990757314c5f53e55776eabcc89b380fe215102909432b`.
- Report PDF SHA-256: `379d59ced728ef1ed2ffc013fbf75ddeb729d5892e4ac8715a2d3484d1571663`.
- The TeX contains no fragment `\\input` dependency and includes the explicit no-response text.

The image viewer could not access Termux's private temporary directory because of its filesystem sandbox. Visual page inspection was therefore not completed; real XeLaTeX compilation, artifact/path assertions, PDF metadata, and hashes passed.

The pre-existing untracked `cMDR.xlsx` and `task-4-rollback-review-report.md` artifacts were not read, modified, staged, or committed.
