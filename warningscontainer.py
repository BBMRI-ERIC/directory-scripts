# vim:ts=4:sw=4:tw=0:sts=4:et

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

    def __init__(self, disabledChecks=None):
        # TODO
        self.__warnings = {}
        self.__warningsNNs = {}
        self.disabledChecks = {} if disabledChecks is None else disabledChecks
        self.suppressedWarnings = []

    def _is_disabled(self, warning: DataCheckWarning) -> bool:
        check_suppressions = self.disabledChecks.get(warning.dataCheckID, {})
        if isinstance(check_suppressions, set):
            return warning.directoryEntityID in check_suppressions
        return warning.directoryEntityID in check_suppressions

    def _suppression_reason(self, warning: DataCheckWarning) -> str:
        check_suppressions = self.disabledChecks.get(warning.dataCheckID, {})
        if isinstance(check_suppressions, dict):
            return check_suppressions.get(warning.directoryEntityID, "")
        return ""

    def newWarning(self, warning : DataCheckWarning):
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
        for wk in sorted(self.__warnings):
            print(wk + ":")
            for w in sorted(self.__warnings[wk], key=lambda x: x.directoryEntityID + ":" + str(x.level.value)):
                w.dump()
            print("")

    def getWarnings(self):
        """Return all non-suppressed warnings as a flat list."""
        warnings = []
        for warning_list in self.__warnings.values():
            warnings.extend(warning_list)
        return warnings

    def dumpSuppressedWarningsDebug(self, max_items: int = 100):
        """Log suppressed warnings for debug troubleshooting."""
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
        for col_idx, (header, width) in enumerate(headers):
            worksheet.write_string(0, col_idx, header, bold)
            worksheet.set_column(col_idx, col_idx, width)

    @staticmethod
    def _write_cell(worksheet, row, col, value):
        """Write a worksheet cell while preserving booleans and avoiding type errors."""
        if isinstance(value, bool):
            worksheet.write_boolean(row, col, value)
            return
        if value is None:
            worksheet.write_blank(row, col, None)
            return
        worksheet.write_string(row, col, str(value))

    def dumpWarningsXLSX(self, filename : List[str], allBiobanks: dict, allCollections: dict, allNNs_sheet: bool = False):
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
