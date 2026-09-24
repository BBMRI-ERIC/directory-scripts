# vim:ts=4:sw=4:tw=0:sts=4:et

"""Collect, filter, print, and export Directory data-quality warnings."""

import logging as log
from typing import List

import xlsxwriter

from customwarnings import DataCheckWarning
from nncontacts import NNContacts


QC_SHEET_HEADERS = (
    ("Entity ID", 50),
    ("Entity type", 12),
    ("Entity withdrawn", 8),
    ("Check", 24),
    ("Severity", 10),
    ("Message", 120),
    ("Action", 60),
    ("Email", 50),
)

ENTITY_LIST_HEADERS = (
    ("Entity ID", 50),
    ("Entity type", 12),
    ("Entity withdrawn", 8),
)


class WarningsContainer:
    """Accumulate QC warnings by national node and recipient group.

    Attributes:
        disabledChecks: Check-ID lookup of entity IDs to suppress. Values may be
            dictionaries carrying reasons or legacy sets.
        suppressedWarnings: Warning objects rejected by ``disabledChecks`` in
            arrival order. Retained warnings stay in private indexes.
    """
    def __init__(self, disabledChecks=None):
        """Initialize empty warning indexes and suppression state.

        Args:
            disabledChecks: Optional ``check_id -> entity_ids`` mapping. The
                mapping is retained by reference, so later caller mutations
                affect suppression; ``None`` creates a new empty map.
        """
        self.__warnings = {}
        self.__warningsNNs = {}
        self.disabledChecks = {} if disabledChecks is None else disabledChecks
        self.suppressedWarnings = []

    def _is_disabled(self, warning: DataCheckWarning) -> bool:
        """Return whether this warning's check and entity are suppressed.

        Args:
            warning: Warning whose check ID and Directory entity ID are looked
                up in the current ``disabledChecks`` mapping.

        Returns:
            ``True`` when the entity occurs in a reason dictionary or legacy set
            for the warning's check ID.
        """
        check_suppressions = self.disabledChecks.get(warning.dataCheckID, {})
        if isinstance(check_suppressions, set):
            return warning.directoryEntityID in check_suppressions
        return warning.directoryEntityID in check_suppressions

    def _suppression_reason(self, warning: DataCheckWarning) -> str:
        """Return the stored reason for a dictionary-based suppression.

        Args:
            warning: Warning whose check and entity keys select the reason.

        Returns:
            The mapped reason, or an empty string when the suppression is absent
            or represented by a legacy set.
        """
        check_suppressions = self.disabledChecks.get(warning.dataCheckID, {})
        if isinstance(check_suppressions, dict):
            return check_suppressions.get(warning.directoryEntityID, "")
        return ""

    def newWarning(self, warning : DataCheckWarning):
        """Store an enabled warning or retain a suppressed warning for debugging.

        Args:
            warning: Warning object to index. It is retained by reference rather
                than copied, so caller mutations remain visible in outputs.

        Returns:
            None.

        Side Effects:
            Appends to private node/recipient indexes or ``suppressedWarnings``
            and emits a debug log entry for suppression.
        """
        if self._is_disabled(warning):
            self.suppressedWarnings.append(warning)
            reason = self._suppression_reason(warning)
            if reason:
                log.debug(
                    "Suppressing %s for %s (%s).",
                    warning.dataCheckID,
                    warning.directoryEntityID,
                    reason,
                )
            else:
                log.debug(
                    "Suppressing %s for %s.",
                    warning.dataCheckID,
                    warning.directoryEntityID,
                )
            return
        self.__warningsNNs.setdefault(warning.NN,[]).append(warning)
        warning_key = NNContacts.compose_recipients(
            warning.NN,
            warning.recipients,
        )
        self.__warnings.setdefault(warning_key,[]).append(warning)

    def dumpWarnings(self):
        """Print retained warnings grouped by recipient key to standard output.

        Returns:
            None.

        Side Effects:
            Calls ``print`` and each warning's ``dump`` method. Groups are sorted
            lexicographically; warnings sort by entity ID then severity value.
        """
        for wk in sorted(self.__warnings):
            print(wk + ":")
            for w in sorted(self.__warnings[wk], key=lambda x: x.directoryEntityID + ":" + str(x.level.value)):
                w.dump()
            print("")

    def getWarnings(self):
        """Return all non-suppressed warnings as a flat list.

        Returns:
            A new flat list of retained warning references in recipient-group
            insertion order. Suppressed warnings are excluded.
        """
        warnings = []
        for warning_list in self.__warnings.values():
            warnings.extend(warning_list)
        return warnings

    def dumpSuppressedWarningsDebug(self, max_items: int = 100):
        """Log suppressed warnings for debug troubleshooting.

        Args:
            max_items: Maximum number of individual warnings to log after the
                summary. Negative values follow normal list-slice semantics.

        Returns:
            None.

        Side Effects:
            Emits debug logs, including stored reasons when available. Does not
            alter retained or suppressed warning objects.
        """
        total = len(self.suppressedWarnings)
        if total == 0:
            log.debug("No warnings were suppressed in this run.")
            return
        log.debug("Suppressed warnings in this run: %s", total)
        for warning in self.suppressedWarnings[:max_items]:
            reason = self._suppression_reason(warning)
            if reason:
                log.debug(
                    "Suppressed %s for %s (%s): %s",
                    warning.dataCheckID,
                    warning.directoryEntityID,
                    reason,
                    warning.message,
                )
            else:
                log.debug(
                    "Suppressed %s for %s: %s",
                    warning.dataCheckID,
                    warning.directoryEntityID,
                    warning.message,
                )
        if total > max_items:
            log.debug("Suppressed warning list truncated to %s entries.", max_items)

    @staticmethod
    def _write_headers(worksheet, headers, bold):
        """Write row-zero labels and configured widths to an XlsxWriter sheet.

        Args:
            worksheet: Open XlsxWriter worksheet receiving the header row.
            headers: Ordered ``(label, width)`` pairs to write from column zero.
            bold: XlsxWriter format applied to every header cell.

        Returns:
            None.

        Side Effects:
            Mutates ``worksheet`` by writing strings and column widths; XlsxWriter
            failures propagate.
        """
        for col_idx, (header, width) in enumerate(headers):
            worksheet.write_string(0, col_idx, header, bold)
            worksheet.set_column(col_idx, col_idx, width)

    @staticmethod
    def _write_cell(worksheet, row, col, value):
        """Write one cell while preserving booleans and blank values.

        Args:
            worksheet: Open XlsxWriter worksheet to mutate.
            row: Zero-based destination row.
            col: Zero-based destination column.
            value: ``bool`` is written as Boolean, ``None`` as blank, and every
                other value as its string representation.

        Returns:
            None.

        Side Effects:
            Writes directly to ``worksheet`` and propagates XlsxWriter failures.
        """
        if isinstance(value, bool):
            worksheet.write_boolean(row, col, value)
            return
        if value is None:
            worksheet.write_blank(row, col, None)
            return
        worksheet.write_string(row, col, str(value))

    def dumpWarningsXLSX(self, filename : List[str], allBiobanks: dict, allCollections: dict, allNNs_sheet: bool = False):
        """Write retained warnings and optional entity inventories to one workbook.

        Args:
            filename: Sequence whose first item is the XLSX destination path.
                Its parent directory must exist; the file is created or overwritten.
            allBiobanks: Optional ``biobank_id -> withdrawn`` inventory. A
                truthy mapping produces an ``AllBiobanks`` sheet.
            allCollections: Optional ``collection_id -> withdrawn`` inventory.
                A truthy mapping produces an ``AllCollections`` sheet.
            allNNs_sheet: Whether to add an ``ALL`` sheet duplicating every
                retained warning across node-specific sheets.

        Returns:
            None.

        Side Effects:
            Creates an XlsxWriter workbook at ``filename[0]`` and writes node,
            aggregate, and requested inventory sheets. The output is not staged
            or atomically published; failures from workbook creation, writes, or
            ``close`` propagate and can leave an incomplete output file.
        """
        workbook = xlsxwriter.Workbook(filename[0])
        bold = workbook.add_format({'bold': True})

        if allNNs_sheet:
            # Create a sheet containing content for all NNs together
            allNNs_worksheet = workbook.add_worksheet("ALL")
            allNNs_row = 0
            self._write_headers(allNNs_worksheet, QC_SHEET_HEADERS, bold)

        if allBiobanks:
            # Print all biobanks present in Directory or in the given list, no matter if they have warnings or not
            allBBs_worksheet = workbook.add_worksheet("AllBiobanks")
            allBBs_row = 0
            self._write_headers(allBBs_worksheet, ENTITY_LIST_HEADERS, bold)

        if allCollections:
            # Print all collections present in Directory or in the given list, no matter if they have warnings or not
            allColls_worksheet = workbook.add_worksheet("AllCollections")
            allColls_row = 0
            self._write_headers(allColls_worksheet, ENTITY_LIST_HEADERS, bold)

        for nn in sorted(self.__warningsNNs):
            worksheet = workbook.add_worksheet(nn)
            worksheet_row = 0
            self._write_headers(worksheet, QC_SHEET_HEADERS, bold)
            for w in sorted(self.__warningsNNs[nn], key=lambda x: x.directoryEntityID + ":" + str(x.level.value)):
                worksheet_row += 1
                self._write_cell(worksheet, worksheet_row, 0, w.directoryEntityID)
                self._write_cell(worksheet, worksheet_row, 1, w.directoryEntityType.value)
                self._write_cell(worksheet, worksheet_row, 2, w.directoryEntityWithdrawn)
                self._write_cell(worksheet, worksheet_row, 3, w.dataCheckID)
                self._write_cell(worksheet, worksheet_row, 4, w.level.name)
                self._write_cell(worksheet, worksheet_row, 5, w.message)
                self._write_cell(worksheet, worksheet_row, 6, w.action)
                self._write_cell(worksheet, worksheet_row, 7, w.emailTo)

                if allNNs_sheet:
                    # Populate the "ALL" sheet
                    allNNs_row += 1
                    self._write_cell(allNNs_worksheet, allNNs_row, 0, w.directoryEntityID)
                    self._write_cell(allNNs_worksheet, allNNs_row, 1, w.directoryEntityType.value)
                    self._write_cell(allNNs_worksheet, allNNs_row, 2, w.directoryEntityWithdrawn)
                    self._write_cell(allNNs_worksheet, allNNs_row, 3, w.dataCheckID)
                    self._write_cell(allNNs_worksheet, allNNs_row, 4, w.level.name)
                    self._write_cell(allNNs_worksheet, allNNs_row, 5, w.message)
                    self._write_cell(allNNs_worksheet, allNNs_row, 6, w.action)
                    self._write_cell(allNNs_worksheet, allNNs_row, 7, w.emailTo)
                    
        if allBiobanks:
            for biobankID,BBWithdrawn in allBiobanks.items():
                allBBs_row += 1
                self._write_cell(allBBs_worksheet, allBBs_row, 0, biobankID)
                self._write_cell(allBBs_worksheet, allBBs_row, 1, "Biobank")
                self._write_cell(allBBs_worksheet, allBBs_row, 2, BBWithdrawn)
        if allCollections:
            for collectionID,collWithdrawn in allCollections.items():
                allColls_row += 1
                self._write_cell(allColls_worksheet, allColls_row, 0, collectionID)
                self._write_cell(allColls_worksheet, allColls_row, 1, "Collection")
                self._write_cell(allColls_worksheet, allColls_row, 2, collWithdrawn)

                
            '''
            for biobank in biobanks:
                allBBs_row += 1
                allBBs_worksheet.write_string(allBBs_row, 0, biobank['id'])
                allBBs_worksheet.write_string(allBBs_row, 1, "Biobank")

        if collections:
            for e in collections:
                allColls_row += 1
                allColls_worksheet.write_string(allColls_row, 0, e['id'])
                allColls_worksheet.write_string(allColls_row, 1, "Collection")
            '''

        workbook.close()
