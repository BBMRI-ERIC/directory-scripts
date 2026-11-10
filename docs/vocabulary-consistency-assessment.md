# Dataset And Service Consistency Checks: Assessment

This assessment accompanies the reviewed guidance in `vocabulary-guidance.json`.
Only `VOC:DeprecatedValue` is implemented by this change. The candidates below
need separate rule approval; this document does not authorize new findings.

## Sources And Scope

Production metadata and reference vocabularies were checked on 2026-11-05.
The relevant history starts before network inheritance removal at
`e1319d600d95a445180deac3b8af4db06837fe73` and ends at the pinned upstream
revision `0aac60c44c68ff1733c3d10f3669ec9967951872`. Ten relevant file transitions
were retrieved, including both public and staging models. Dataset changes include
`82fe9dd831cc64455770598c810998cb105972b8`, restoration in
`27a725e3a594e6e26d4ad27352e4451f3cf9f098`, and definition/label changes in
`68d9d8d89130dbe0b8ce6795585c0c7a0c4f174e`. Service replacement is recorded in
`d96bb75b3ec62552e6b32e886bc43bcff95b5190`.

These are upstream revisions, not installation or migration dates. The separate
metadata-only checker compares against official MIABIS revision
`272d05e792e312f1fe56e24eac37d43ce9376bf1`; it does not inspect entity data.

## Candidate Rules

| Candidate | Existing coverage | Qualification and recommendation |
| --- | --- | --- |
| Specific imaging category should agree with imaging information | `CC:ImageCatMissing`, `CC:ImgDataMissing`, `CC:ImageTypeMissing` already cover generic imaging requirements | A mixed collection can legitimately hold several image types. Do not demand every imaging category or replace these existing checks. A new specific rule requires a reviewed modality-to-category table and positive/negative fixtures. Review-only for now. |
| Dataset category versus samples/clinical descriptions | `CC:SampleCatMismatch`, `CC:DiagCatMismatch`, `CC:MedRecDiagGap` | Preserve existing mixed-content logic. A description may be incomplete, not contradictory. No new broad text-based ERROR is justified. |
| Service type agrees with the advertised operation | No generic Services content check currently establishes this | Distinguish laboratory generation, computational analysis, consultation and research focus. Short service descriptions do not prove a mismatch. Candidate for review assistance, not a deterministic implication from keywords. |
| Service references satisfy required fields and category assignments | Schema requires `Services.serviceTypes` and `ServiceTypes.serviceCategory` | Missing/invalid references could support a future deterministic ERROR with coherent schema/snapshot evidence. Missing optional metadata or a historical cached vocabulary is not sufficient. Category assignment differences from MIABIS cannot be errors where MIABIS specifies no such grouping. |
| Retired term is no longer accepted | The new check intentionally tests explicit deprecation, not absence alone | A historical snapshot may predate migration. A future invalid-reference rule needs known compatible model/reference/data versions and separate approval. |

## Counterexamples To Unsafe Implications

- DNA samples do not imply that genomic datasets have been generated.
- Genomic datasets do not imply that DNA is stored locally.
- A sequencing service does not imply that the biobank holds genomic datasets.
- Research into cancer or rare disease does not by itself identify a service.
- An old combined physiological/biochemical value does not prove both categories.
- A registry or survey describes origin, not necessarily the scientific data type.

## Network Membership Review

`directory.py` constructs membership edges from explicit `network` fields. The
retired `combined_network` and `parent_network` fields must not reintroduce
inheritance in helpers or checks. Inverse links describe the same relationship,
not another independent source of membership.

`checks/BBMRICohorts.py` tests explicit collection network membership for cohort
requirements. `BCO:BBNetFlag` additionally enforces a cohort-specific policy that
membership is recorded on collections rather than biobanks. That policy is not a
general inheritance mechanism and has not been removed. Confirm its policy with
the network owner before proposing any behavior change.

The same plugin sums fact rows when deciding whether any counts are present.
That is not an authoritative sample/donor total, and must not be reused as one.
Changing that pre-existing predicate is outside this approved vocabulary work;
a future correction should use the canonical fact-sheet helpers and its own tests.

No new network/cohort warning predicates or automatic membership changes are
implemented by this assessment.
