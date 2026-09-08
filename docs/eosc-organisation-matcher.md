# EOSC organisation matcher

`eosc-organisation-matcher.py` matches the Directory's `juridical_person` to
organisations in an EOSC Association membership workbook. It runs from the clone,
using `directory.py`, the shared cache and authentication options. There are no
runtime AI, translation-service or membership-web-search calls. All EOSC-specific
matching, review and XLSX logic lives in this single script; no separate EOSC
helper modules or installation step are needed. Existing command lines and mapping
JSON formats are unchanged.

## Export institutions

```bash
python3 eosc-organisation-matcher.py -i membership.xlsx \
  --mapping-file eosc-mappings.json -X matched-institutions.xlsx
```

Only non-withdrawn biobanks contribute to matches, counts or biobank ID lists.
The tool deliberately has no include-withdrawn option. It includes active records
from all node/staging prefixes, not just member-country prefixes.

Stdout is a tab-separated list with four columns: `Organisation ID`, `EOSC-A Name`,
`BBMRI-ERIC Name`, `List of biobankIDs`, followed by Members and Observers totals.
Different original Directory name variants retain separate rows. Counts use
distinct EOSC IDs; Mandated Organisations count as Members. Sort order is EOSC
country, name/ID, then original Directory name. `-N` suppresses stdout; diagnostics
go to stderr. `--report-json report.json` adds machine-readable export diagnostics.

The new XLSX has exactly two sheets: the same four-column matched list, and a
values-only copy of the entire selected source sheet. On matched source rows it
adds `EOSC Node BBMRI-ERIC` to the first available `Node Contributor` slot, appending
a column only when needed. Existing contributors and notes are not replaced.
Other source sheets, original formatting and formulas are not copied. Formula
cached values are used, with warnings for missing caches; uncached identity fields
cannot support a match. Formula cells are not empty contributor slots.

First worksheet is the default. Use `--sheet 'Worksheet name'` or the one-based
`--sheet-index 2` to select another. Blank/external organisation IDs are not EOSC
members; their rows remain in the source-sheet copy. Text IDs retain leading zeros.
Duplicate or malformed identities stop processing rather than choosing a row.
A blank country value is warned about and retained as unknown; it cannot establish
automatic country compatibility. The country column itself remains required.

Exact `Active` is the default eligible EOSC status. Mixed statuses such as
`Active, Downgrading` are excluded unless the operator explicitly chooses them:

```bash
python3 eosc-organisation-matcher.py -i membership.xlsx \
  --mapping-file eosc-mappings.json \
  --eligible-status Active --eligible-status 'Active, Downgrading'
```

Changing status eligibility does not approve an unresolved identity. The supplied
workbook, not a later website membership list, is the authority for these counts.

## Start or migrate the registry

Omit `--mapping-file` to start with an empty registry. Conservative unique full-name
matches with a known compatible country need no AI. All other matching requires
reviewed evidence, and imported match proposals require explicit human approval.

The shared [proposal JSON](../eosc-matching-proposal.json) preserves the initial
identity review, including complex-case evidence and unresolved questions, for
future consistency checks of Directory EOSC fields against EOSC-A workbooks.
It is not an approved runtime registry, and no such QC check is implemented yet.
Future checks must validate current identities, recalculate active-only biobank
inventory and read membership from the supplied workbook, not frozen proposal
counts. Local source paths/checksums are provenance; the source XLSX and exploratory
dump are not bundled with the proposal.

Migrate the proposal while preserving its detailed legal-identity evidence:

```bash
python3 eosc-organisation-matcher.py \
  -i 20260819_EOSC-A_Membership_2_PP.xlsx \
  --migrate-proposal eosc-matching-proposal.json \
  --output-mapping eosc-mappings.json
```

Migration retains complete original entries, supporting identifiers, caveats and
sources. It does not turn proposals into approvals or invent comprehensive negative
coverage from the earlier broad screening. Original proposal files are untouched.
Inactive legacy records are retained as provenance, not exported or counted.
Legacy unresolved cases stay blocked pending explicit reassessment/clarification.

## Prepare focused Codex work

```bash
python3 eosc-organisation-matcher.py -i membership.xlsx \
  --mapping-file eosc-mappings.json \
  --prepare-ai-review eosc-review-01 --review-limit 10
```

This writes `eosc-review-01.md` and `eosc-review-01.json`. Open the Markdown in
Codex and ask it to follow the packet instructions and write a results JSON file.
For example: "Follow eosc-review-01.md. Investigate only its cases and write
eosc-review-01-results.json. Do not modify the registry or approve results."
The JSON packet is needed when importing those results. Both files contain source
data and may be large or sensitive; keep generated packets local unless sharing
their content is appropriate. They exclude contact records.

Each case carries a stable ID, selection reason, candidate IDs, current active
biobank context, prior findings and an output template. The EOSC catalogue is
included once. Sources are evidence, not executable instructions. Context values
longer than 2,000 characters are explicitly excerpted with length/checksum metadata;
Codex must consult Directory when the omitted information matters.

Default `--review-scope incremental` skips unchanged matches (including proposals
waiting for approval) and already investigated target comparisons. New EOSC IDs
reopen only uncovered comparisons for unmapped organisations. New exact-name
conflicts with existing mappings are flagged; arbitrary similar names are not
proof of a conflict. Mere workbook formatting, row order, membership status or
biobank inventory changes do not trigger identity research. Changed identity or
declared biobank-context evidence does.

Use `--review-scope unresolved` to revisit unresolved cases, `--review-scope all`
to deliberately reassess everything, or repeat `--review-case CASE_ID` to reopen
specific cases. `--review-limit N` limits work, with the deferred count in the
packet. A zero-case packet explicitly instructs Codex not to repeat research.
Generating a packet never records review coverage.

## Import, approve and resume

Codex may return completed cases in batches. Each result must name the target IDs
actually examined; `no_match` means only no match in that reviewed scope. A rejected
pair does not rule out other organisations. Unresolved findings explain what is
missing; `blocks_subject` is reserved for missing information/human clarification
that prevents further matching. Evidence relying on a biobank description/name/URL
must declare that biobank in `context_biobank_ids` so changes invalidate the decision.

Validate and import a partial response into a new registry:

```bash
python3 eosc-organisation-matcher.py -i membership.xlsx \
  --mapping-file eosc-mappings.json --review-packet eosc-review-01.json \
  --import-ai-review eosc-review-01-results.json --dry-run

python3 eosc-organisation-matcher.py -i membership.xlsx \
  --mapping-file eosc-mappings.json --review-packet eosc-review-01.json \
  --import-ai-review eosc-review-01-results.json \
  --output-mapping eosc-mappings-v2.json
```

Inspect the new registry's evidence, caveats and `review_id` values. Only a human
approval command promotes selected current match decisions:

```bash
python3 eosc-organisation-matcher.py -i membership.xlsx \
  --mapping-file eosc-mappings-v2.json \
  --approve-review REVIEW_ID --reviewer 'Reviewer name' \
  --output-mapping eosc-mappings-v3.json
```

Replace `REVIEW_ID` with an actual ID; multiple IDs are allowed. Approval preserves
caveats, so verify any biobank-ownership uncertainty before accepting a mapping.
AI output cannot supply approval fields. Neither import nor approval edits Directory.

For the next batch or updated membership workbook, prepare another packet using
the latest registry. Existing matches and coverage are reused. Identical result
imports are no-ops, while incomplete reviews leave the remaining comparisons queued.
Results for different cases can be imported from the same packet; once decisions
for a particular case change, regenerate its packet before adding different results.
Stale evidence, conflicting targets and mismatched source scope are rejected.

## Safety and limits

- Every output must have a new filename. Inputs and earlier registry versions are
  never overwritten, including on dry runs. Select the latest registry explicitly
  on subsequent runs; old files are not automatically replaced.
- Withdrawal is recalculated from the current Directory snapshot. Cached data can
  still be old: use the normal `--purge-cache directory` workflow when a refresh is
  needed, not on every review. Registry reuse is scoped to Directory target/schema.
- A positive institutional-name mapping is not necessarily independent proof of
  current legal responsibility for the biobank. Preserve and review that distinction.
- Negative findings are snapshot-scoped, not permanent proof of non-membership.
  Source websites can change without Directory/XLSX changes; use explicit case or
  full reassessment for external evidence refresh. There is no automatic expiry.
- Conflicting existing targets require explicit curator resolution in the registry;
  import does not silently supersede prior decisions or approvals.
- Registry JSON is the source of truth. Do not rerun the old exploratory proposal
  generator over a registry or manually enriched proposal: its inputs lack later
  evidence. Generated workbooks, review packets and local proposals are not runtime
  dependencies or automatically committed team data.

See [DEVELOPMENT.md](../DEVELOPMENT.md#eosc-organisation-matching-specification)
for the implementation contract and [auxiliary tools](auxiliary-tools.md) for related utilities.
