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

    def __init__(self, disabledChecks = {}):
        # TODO
        self.__warnings = {}
        self.__warningsNNs = {}
        self.disabledChecks = disabledChecks

    def newWarning(self, warning : DataCheckWarning):
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
                if not (w.dataCheckID in self.disabledChecks and w.directoryEntityID in self.disabledChecks[w.dataCheckID]):
                    w.dump()
            print("")

    @staticmethod
    def _write_headers(worksheet, headers, bold):
        for col_idx, (header, width) in enumerate(headers):
            worksheet.write_string(0, col_idx, header, bold)
            worksheet.set_column(col_idx, col_idx, width)

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
                if not (w.dataCheckID in self.disabledChecks and w.directoryEntityID in self.disabledChecks[w.dataCheckID]):
                    worksheet_row += 1
                    worksheet.write_string(worksheet_row, 0, w.directoryEntityID)
                    worksheet.write_string(worksheet_row, 1, w.directoryEntityType.value)
                    worksheet.write_string(worksheet_row, 2, w.directoryEntityWithdrawn)
                    worksheet.write_string(worksheet_row, 3, w.dataCheckID)
                    worksheet.write_string(worksheet_row, 4, w.level.name)
                    worksheet.write_string(worksheet_row, 5, w.message)
                    worksheet.write_string(worksheet_row, 6, w.action)
                    worksheet.write_string(worksheet_row, 7, w.emailTo)

                    if allNNs_sheet:
                        # Populate the "ALL" sheet
                        allNNs_row += 1
                        allNNs_worksheet.write_string(allNNs_row, 0, w.directoryEntityID)
                        allNNs_worksheet.write_string(allNNs_row, 1, w.directoryEntityType.value)
                        allNNs_worksheet.write_string(allNNs_row, 2, w.directoryEntityWithdrawn)
                        allNNs_worksheet.write_string(allNNs_row, 3, w.dataCheckID)
                        allNNs_worksheet.write_string(allNNs_row, 4, w.level.name)
                        allNNs_worksheet.write_string(allNNs_row, 5, w.message)
                        allNNs_worksheet.write_string(allNNs_row, 6, w.action)
                        allNNs_worksheet.write_string(allNNs_row, 7, w.emailTo)
                    
        if allBiobanks:
            for biobankID,BBWithdrawn in allBiobanks.items():
                allBBs_row += 1
                allBBs_worksheet.write_string(allBBs_row, 0, biobankID)
                allBBs_worksheet.write_string(allBBs_row, 1, "Biobank")
                allBBs_worksheet.write_string(allBBs_row, 2, BBWithdrawn)
        if allCollections:
            for collectionID,collWithdrawn in allCollections.items():
                allColls_row += 1
                allColls_worksheet.write_string(allColls_row, 0, collectionID)
                allColls_worksheet.write_string(allColls_row, 1, "Collection")
                allColls_worksheet.write_string(allColls_row, 2, collWithdrawn)

                
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
