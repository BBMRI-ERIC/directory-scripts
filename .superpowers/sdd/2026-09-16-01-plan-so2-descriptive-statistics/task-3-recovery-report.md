# Task 3 Recovery Report

## Status
Task 3 payload work is implemented and verified.

## Scope
- Preserve every literal structured response, including unexpected selections, as a counted and contributed category.
- Keep duplicate and unexpected selection diagnostics traceable by source row.
- Evaluate declared applicability without dropping submitted answers, distinguishing eligible unanswered rows, structural skips, and out-of-route answers.
- Emit versioned payload metadata, schema provenance, and free-text parent-answer inconsistency diagnostics.

## RED Evidence
The inherited tests were run before production changes:

```text
pytest -q tests/test_so2_descriptive_report.py -k 'preserves_unexpected or declared_applicability or schema_provenance'
3 failed, 27 deselected
```

The failures were exactly the missing unexpected-value category/count behavior, missing declared-applicability counters, and missing payload/schema provenance plus free-text parent diagnostics.

A first GREEN attempt retained unexpected values but exposed two follow-up failures in the same focused test: repeated unexpected literals were no longer diagnosed after being added to counts, then diagnostics were not source-row ordered. Both were corrected while preserving the original RED test.

## GREEN Evidence

```text
pytest -q tests/test_so2_descriptive_report.py -k 'preserves_unexpected or declared_applicability or schema_provenance'
3 passed, 27 deselected

pytest -q tests/test_so2_descriptive_report.py
30 passed

python3 -m py_compile so2_descriptive_report.py tests/test_so2_descriptive_report.py
passed

git diff --check
passed with no output
```

## Commit Scope
- `so2_descriptive_report.py`
- `tests/test_so2_descriptive_report.py`
- `.superpowers/sdd/2026-09-16-01-plan-so2-descriptive-statistics/task-3-recovery-report.md`

Pre-existing untracked `cMDR.xlsx` remains untouched and is excluded.
