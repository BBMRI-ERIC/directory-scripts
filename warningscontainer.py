# vim:ts=4:sw=4:tw=0:sts=4:et

import logging as log
from typing import List

import xlsxwriter

from customwarnings import DataCheckWarning
from nncontacts import NNContacts

class WarningsContainer:

    def __init__(self, disabledChecks = {}):
        # TODO
        self.__warnings = {}
        self.__warningsNNs = {}
        self.disabledChecks = disabledChecks

    def newWarning(self, warning : DataCheckWarning):
        warning_key = ""
        self.__warningsNNs.setdefault(warning.NN,[]).append(warning)
        if warning.recipients != "":
            warning_key = recipients + ", "
        try: 
            warning_key += NNContacts.NNtoEmails[warning.NN]
        except KeyError:
            warning_key += 'petr.holub@bbmri-eric.eu, e.van.enckevort@rug.nl, a.w.hodselmans@rug.nl'
        self.__warnings.setdefault(warning_key,[]).append(warning)

    def dumpWarnings(self):
        for wk in sorted(self.__warnings):
            print(wk + ":")
            for w in sorted(self.__warnings[wk], key=lambda x: x.directoryEntityID + ":" + str(x.level.value)):
                if not (w.dataCheckID in self.disabledChecks and w.directoryEntityID in self.disabledChecks[w.dataCheckID]):
                    w.dump()
            print("")

    def dumpWarningsXLSX(self, filename : List[str], allNNs_sheet: bool = False):
        workbook = xlsxwriter.Workbook(filename[0])
        bold = workbook.add_format({'bold': True})

        if allNNs_sheet:
            # Create a sheet containing content for all NNs together
            allNNs_worksheet = workbook.add_worksheet("ALL")
            allNNs_row = 0

            allNNs_worksheet.write_string(allNNs_row, 0, "Entity ID", bold)
            allNNs_worksheet.set_column(0,0, 50)
            allNNs_worksheet.write_string(allNNs_row, 1, "Entity type", bold)
            allNNs_worksheet.set_column(1,1, 10)
            allNNs_worksheet.write_string(allNNs_row, 2, "Check", bold)
            allNNs_worksheet.set_column(2,2, 20)
            allNNs_worksheet.write_string(allNNs_row, 3, "Severity", bold)
            allNNs_worksheet.set_column(3,3, 10)
            allNNs_worksheet.write_string(allNNs_row, 4, "Message", bold)
            allNNs_worksheet.set_column(4,4, 120)
            allNNs_worksheet.write_string(allNNs_row, 5, "Action", bold)
            allNNs_worksheet.set_column(5,5, 120)
            allNNs_worksheet.write_string(allNNs_row, 6, "Email", bold)
            allNNs_worksheet.set_column(6,6, 50)

        for nn in sorted(self.__warningsNNs):
            worksheet = workbook.add_worksheet(nn)
            worksheet_row = 0
            worksheet.write_string(worksheet_row, 0, "Entity ID", bold)
            worksheet.set_column(0,0, 50)
            worksheet.write_string(worksheet_row, 1, "Entity type", bold)
            worksheet.set_column(1,1, 10)
            worksheet.write_string(worksheet_row, 2, "Check", bold)
            worksheet.set_column(2,2, 20)
            worksheet.write_string(worksheet_row, 3, "Severity", bold)
            worksheet.set_column(3,3, 10)
            worksheet.write_string(worksheet_row, 4, "Message", bold)
            worksheet.set_column(4,4, 120)
            worksheet.write_string(worksheet_row, 5, "Action", bold)
            worksheet.set_column(5,5, 120)
            worksheet.write_string(worksheet_row, 6, "Email", bold)
            worksheet.set_column(6,6, 50)
            for w in sorted(self.__warningsNNs[nn], key=lambda x: x.directoryEntityID + ":" + str(x.level.value)):
                if not (w.dataCheckID in self.disabledChecks and w.directoryEntityID in self.disabledChecks[w.dataCheckID]):
                    worksheet_row += 1
                    worksheet.write_string(worksheet_row, 0, w.directoryEntityID)
                    worksheet.write_string(worksheet_row, 1, w.directoryEntityType.value)
                    worksheet.write_string(worksheet_row, 2, w.dataCheckID)
                    worksheet.write_string(worksheet_row, 3, w.level.name)
                    worksheet.write_string(worksheet_row, 4, w.message)
                    worksheet.write_string(worksheet_row, 5, w.action)
                    worksheet.write_string(worksheet_row, 6, w.emailTo)

                    if allNNs_sheet:
                        # Populate the "ALL" sheet
                        allNNs_row += 1
                        allNNs_worksheet.write_string(allNNs_row, 0, w.directoryEntityID)
                        allNNs_worksheet.write_string(allNNs_row, 1, w.directoryEntityType.value)
                        allNNs_worksheet.write_string(allNNs_row, 2, w.dataCheckID)
                        allNNs_worksheet.write_string(allNNs_row, 3, w.level.name)
                        allNNs_worksheet.write_string(allNNs_row, 4, w.message)
                        allNNs_worksheet.write_string(allNNs_row, 5, w.action)
                        allNNs_worksheet.write_string(allNNs_row, 6, w.emailTo)
        workbook.close()

