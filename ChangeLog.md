# ChangeLog

This changelog is organized by date, newest first. Because the repository does not use version tags, each date groups all commits made on that day.

## 2026-03-03
- Hardened AI cache validation against in-memory mutation and improved fact-sheet synchronization behavior.

## 2026-03-02
- Added collection partitioning checks and introduced shareable AI-reviewed findings with a rerun workflow.
- Standardized schema handling and withdrawn-scope behavior across Directory-backed tools.
- Moved regex/heuristic text rules out of AI cache into deterministic plugins.
- Split developer architecture notes out of `README.md`, refined QC Excel node-based sheet splitting, and tightened the AI-check rerun workflow.

## 2026-02-28
- Added static placeholder-email checks and documented the distinction between static email validation and remote email checks.

## 2026-02-27
- Hardened the Directory client, added a broader pytest suite, and unified exporter CLI/XLSX handling.
- Reworked directory statistics, fact-sheet validation, and shared order-of-magnitude estimation.
- Unified node-area metadata, shortened check IDs for documentation, and improved `CHECK_DOCS` extraction and workflow guidance.

## 2026-02-26
- Added the `assertive-quality-gate` skill and formalized the repository quality gate.

## 2026-02-12
- Updated colors in repository documentation/assets.

## 2026-02-11
- Clarified schema usage and import behavior in `directory-tables-modifier.py`.
- Required confirmation for `ERIC` edits, unified modifier import/delete/export CLI, and added export-on-delete backup support.
- Refined credentials handling, import fallback behavior, and README examples.

## 2026-02-10
- Fixed missing documentation modules and refreshed installation instructions.
- Added TSV support, dry-run mode, verbose logging, stronger safeguards, and `national_node` import support to `directory-tables-modifier.py`.

## 2026-02-01
- Reworked check identifier mechanics to support linking repository checks into external documentation.

## 2026-01-26
- Improved negotiator/export formatting and added reporting for biobanks without collections.

## 2026-01-25
- Extended negotiator orphan reporting with Q-label-specific orphan summaries.

## 2026-01-16
- Refined negotiator exporter summary formatting and logic.

## 2026-01-15
- Added the negotiator-orphans exporter and its summaries/warnings.
- Documented scripts, agent guidelines, and adjusted negotiator NN handling and Whoosh locking.

## 2026-01-12
- General maintenance updates and merge synchronization.

## 2026-01-09
- Adapted `exporter-quality-label.py` based on quality-management feedback.

## 2025-10-03
- Hardened `full-text-search.py` against missing `also_known` attributes.

## 2025-09-26
- Merged the subcollection-network-membership plugin contribution.

## 2025-08-28
- Added a plugin checking that subcollections belong to the same network as their parent collections.

## 2025-07-17
- Added an exporter for Directory quality labels.

## 2025-06-26
- Added collection URL printing to `exporter-all.py`.

## 2025-06-25
- Fixed withdrawn-biobank handling and added collection/material-type filtering to `exporter-all.py`.

## 2025-06-11
- Adapted the main exporters and shared dataframe/XLSX utilities to EMX2.
- Updated `exporter-all.py`, cohorts, COVID, institutions, obesity, mission-cancer, diagnosis, and pediatric exporter support.

## 2025-05-30
- Fixed the pediatric exporter for the newer GraphQL behavior.

## 2025-05-27
- Added withdrawn-state printing and conditional OoM output for biobanks/collections.
- Merged updated `ContactFields` logic.

## 2025-05-14
- Applied a typo fix.

## 2025-05-13
- Made Yapsy plugin handling more robust.

## 2025-05-08
- Renamed `directoryTablesModifier.py` to `directory-tables-modifier.py`.

## 2025-05-07
- Added the first staging-area table modifier script.

## 2025-04-07
- Removed obsolete `covid19biobank` handling and fixed biobank email retrieval.

## 2025-04-04
- Fixed age-unit consistency reporting between collection metadata and fact tables.
- Merged the new EMX2 directory scripts branch.

## 2025-04-03
- Added an `ALL` tab to QC spreadsheet exports to aggregate per-country sheet data.

## 2025-04-02
- Adapted geocoding to EMX2, removed fixed biobank coordinates from geocoding config, and fixed age-unit checks.

## 2025-03-28
- Fixed BBMRI Cohorts fact-table detection and adapted contact-email handling to EMX2.
- Restored `validate_email` import in `ContactFields.py`.

## 2025-03-14
- Continued adapting scripts to EMX2.

## 2025-03-13
- Merged the EMX2 directory scripts line into the main branch.

## 2025-03-06
- Removed obsolete biobank capabilities and expanded code documentation.
- Split BBMRI Cohorts and fact-table checks more cleanly and started cleanup of cohort checks.

## 2025-03-05
- Added fact-table checks for k-anonymity and donor/patient totals.

## 2025-02-25
- Improved missing fact-sheet reporting, loaded contacts/biobanks more fully, and added fact-table donor/patient checks.

## 2025-02-24
- Renamed Directory `package` to `schema`, added requirements and token authorization, and moved more access to GraphQL.
- Cleaned up contact loading, edge names, logging, and `AccessPolicies.py` behavior.

## 2025-01-17
- Added finer-grained juridical-person checks.

## 2024-12-16
- Added OoM donor counting and collection-type filtering to `exporter-all.py`, with related cleanup.

## 2024-12-06
- Updated Yapsy compatibility for Python 3.12+ and refreshed README documentation.

## 2024-11-01
- Fixed double counting in the global directory statistics exporter.

## 2024-10-21
- Improved robustness against missing links between biobanks, collections, and contacts, including missing `juridical_person` values.

## 2024-10-08
- Updated warning output formatting.

## 2024-10-07
- Added action messages and contact emails to BBMRI Cohorts checks.

## 2024-10-01
- Reclassified selected cohort findings from errors to warnings.

## 2024-09-30
- Added an `All NNs` sheet option and updated error/warning classification.

## 2024-09-27
- Updated warning reporting in `exporter-bbmri-cohorts.py`.

## 2024-09-25
- General maintenance updates.

## 2024-09-16
- General maintenance updates.

## 2024-07-25
- Added country and institution counters.

## 2024-07-18
- Fixed BBMRI Cohorts collaboration/material checks and split `warningscontainer` into its own module.

## 2024-06-27
- Continued cancer exporter work focused on pediatric statistics.

## 2024-06-26
- Fixed `also_known` handling and continued cancer exporter work for pediatric statistics.

## 2024-06-13
- Expanded BBMRI Cohorts checks with age logic, commercial-use checks, and richer warning/error output.
- Continued cleanup of both the cohort plugin and its exporter.

## 2024-06-12
- Added the BBMRI Cohorts check plugin scaffold and iterated rapidly on cohort-specific validation rules.

## 2024-06-11
- Continued updating `exporter-bbmri-cohorts.py` and synchronized with mainline changes.

## 2024-06-07
- Adapted `directory.py` to EMX2.

## 2024-06-04
- General maintenance updates.

## 2024-06-03
- Continued updating `exporter_bbmri_cohorts.py`.

## 2024-05-31
- Added the first BBMRI Cohorts exporter draft and renamed it to `exporter_bbmri_cohorts.py`.

## 2024-05-29
- General maintenance updates.

## 2024-05-16
- Fixed pediatric exporter logging.

## 2024-04-30
- Refreshed `exporter-all.py` and synchronized with upstream changes.

## 2023-11-23
- General maintenance updates.

## 2023-09-29
- Added defensive assertions to `pddfutils.py` around Molgenis attribute-list assumptions.

## 2023-04-25
- General maintenance updates.

## 2023-04-13
- Updated full-text search for newer Directory structures and added compact ID / hit-type filtering options.

## 2023-03-31
- Added XML export generation for the COVID-19 Data Portal.

## 2022-12-08
- Added an exporter for institution lists.

## 2022-09-01
- Refreshed README documentation.

## 2022-07-22
- Added an optional `print-filtered-df` argument.

## 2022-07-21
- Removed obsolete legacy geocoding scripts.

## 2022-07-20
- Adjusted scripts to data-model changes and made geocoding more flexible.
- Added purge-all-cache support and cleaned cache-argument documentation.
- Updated `directory.py` capabilities handling and removed `covid19` from it.

## 2022-05-20
- Updated node contact information.

## 2022-05-18
- Performed indentation cleanup.

## 2022-04-27
- Improved exception handling and added cohort/export helper scripts.

## 2022-02-14
- Fixed a bug in `exporter-obesity.py`.

## 2022-02-08
- Added a script for inserting ORPHA codes into a Directory EMX file.

## 2022-01-27
- Added the obesity exporter.

## 2022-01-18
- Added logging and error-email support.

## 2022-01-13
- Caught specific SSL exceptions more explicitly.

## 2021-12-20
- Added SSL import support plus more DMS options and country-skipping behavior.

## 2021-12-09
- Improved SSL certificate handling and cleaned import/user-agent behavior around related scripts.

## 2021-12-02
- Extended the contact generator.

## 2021-11-30
- Made directory-cache purging also purge the full-text-search index cache.

## 2021-11-22
- Added an option to skip biobanks without coordinates in geocoding.

## 2021-11-16
- Started reusing the directory cache in geocoding and added coordinate override/skip options.

## 2021-11-15
- Added the first Python geocoding implementation, config file, and biobank-size OoM handling.

## 2021-09-03
- Added a new exporter, refactored output handling, and introduced missing-biobank-contact checks.

## 2021-06-17
- Updated contact Excel export and renamed files to a more systematic naming scheme.

## 2021-06-10
- Updated scripts to match Directory-side changes.

## 2021-05-31
- Fixed Finland contact information.

## 2021-05-26
- Added a star-model converter stub and iterated on it.
- Added `.gitignore`, simplified code, and fixed the COVID exporter after standards-attribute changes.

## 2021-05-24
- Fixed warning handling for the email cache.

## 2021-05-14
- Improved self-explanatory warning/error text and reclassified selected severities.

## 2021-05-07
- Improved reporting of missing DUO terms.

## 2021-04-19
- Extended full-text search to include contact IDs for biobanks and collections.

## 2021-04-07
- Improved ID search behavior, enabled index reuse, and documented full-text-search usage examples.

## 2021-03-30
- General maintenance updates and better handling of variations and accents.

## 2021-03-17
- General maintenance updates.

## 2021-03-12
- Updated DUO handling from term `0005` to `0042` and made related fixes.

## 2021-03-09
- Updated geocoding checks and Excel export behavior.

## 2021-03-08
- Removed benign neoplasms from cancer ranges, improved XLSX output, and simplified human-readable reporting.

## 2021-02-23
- Added Windows-specific `DNS.Base.SocketError` exception handling.

## 2021-02-17
- Added login/package selection support and a workaround for database-structure inconsistencies.

## 2021-02-09
- Added pediatric statistics generation.

## 2021-02-08
- Updated pediatric cancer counts and refined age-low/age-high/age-unit checks.

## 2021-01-29
- Added the first Data Use Ontology checks.

## 2021-01-06
- Expanded ORPHA mapping checks and inverse mapping checks.
- Improved COVID prospective-collection validation, removed duplicate logic, and cleaned assorted checks.
- Renamed `PROSPECTIVE_STUDY` handling to `PROSPECTIVE_COLLECTION`.

## 2021-01-05
- Added rare-disease collection and ORPHA-code checks, plus related maintenance updates.

## 2020-11-24
- General maintenance updates.

## 2020-11-06
- Added checks for missing `data_categories` and missing `IMAGING_DATA` classification.

## 2020-10-22
- Improved COVID totals to show COVID-only case counts explicitly.

## 2020-10-21
- General maintenance updates.

## 2020-10-18
- Improved detection of missing diagnoses.

## 2020-10-14
- Started and improved SSL/TLS certificate handling and installation support.

## 2020-10-12
- Added totals to reporting/export output.

## 2020-10-10
- Refined collection-size checking and other maintenance updates.

## 2020-10-02
- Improved contact handling and geo checks.
- Added specific ID validation for external biobanks.

## 2020-07-17
- Moved the `Directory` class into a separate package.

## 2020-06-08
- Added an extra cross-check and formatting hints.

## 2020-06-05
- Added the first COVID checks and expanded them rapidly.
- Fixed XLSX generation and added infectious-material and diagnosis checks.

## 2020-05-04
- Fixed residual problems from the Molgenis Python module transition.

## 2020-04-28
- Continued migration to the newer Molgenis Python module and updated `molgenis-python`.

## 2020-04-03
- Started transitioning to the new Molgenis Python module.

## 2019-12-05
- Added an ID check for `::`.

## 2019-05-24
- Improved diagnosis-range reporting, raised its severity to `ERROR`, and fixed network-ID checking.

## 2019-03-05
- Added caching to URL checks and refined URL-check reporting.

## 2019-02-07
- Added a check for diagnosis code blocks.

## 2018-11-21
- Fixed a syntax error and improved reporting of invalid geocoordinates.

## 2018-10-04
- Continued work on the statistics script stub.

## 2018-10-03
- Added the first statistics script stub.

## 2018-08-16
- Updated README documentation.

## 2018-08-01
- General maintenance updates.

## 2018-07-31
- General maintenance updates.

## 2018-07-27
- Added entity-type information to warnings for easier node orientation, with additional maintenance updates.

## 2018-07-26
- General maintenance updates.

## 2018-07-25
- General maintenance updates.

## 2018-07-23
- General maintenance updates.

## 2018-07-18
- Split access-policies logic into its own check and added early Excel export functionality.

## 2018-07-14
- Continued early repository maintenance and iteration.

## 2018-07-13
- Initial repository bootstrap and first follow-up updates.
