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

    def dumpWarningsXLSX(self, filename : List[str], allBiobanks: dict, allCollections: dict, allNNs_sheet: bool = False):
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
            allNNs_worksheet.write_string(allNNs_row, 2, "Entity withdrawn", bold)
            allNNs_worksheet.set_column(2,2, 20)
            allNNs_worksheet.write_string(allNNs_row, 3, "Check", bold)
            allNNs_worksheet.set_column(3,3, 10)
            allNNs_worksheet.write_string(allNNs_row, 4, "Severity", bold)
            allNNs_worksheet.set_column(4,4, 120)
            allNNs_worksheet.write_string(allNNs_row, 5, "Message", bold)
            allNNs_worksheet.set_column(5,5, 120)
            allNNs_worksheet.write_string(allNNs_row, 6, "Action", bold)
            allNNs_worksheet.set_column(6,6, 50)
            allNNs_worksheet.write_string(allNNs_row, 7, "Email", bold)
            allNNs_worksheet.set_column(7,7, 50)

        if allBiobanks:
            # Print all biobanks present in Directory or in the given list, no matter if they have warnings or not
            allBBs_worksheet = workbook.add_worksheet("AllBiobanks")
            allBBs_row = 0

            allBBs_worksheet.write_string(allBBs_row, 0, "Entity ID", bold)
            allBBs_worksheet.set_column(0,0, 50)
            allBBs_worksheet.write_string(allBBs_row, 1, "Entity type", bold)
            allBBs_worksheet.set_column(1,1, 10)
            allBBs_worksheet.write_string(allBBs_row, 2, "Entity withdrawn", bold)
            allBBs_worksheet.set_column(2,2, 10)

        if allCollections:
            # Print all collections present in Directory or in the given list, no matter if they have warnings or not
            allColls_worksheet = workbook.add_worksheet("AllCollections")
            allColls_row = 0

            allColls_worksheet.write_string(allColls_row, 0, "Entity ID", bold)
            allColls_worksheet.set_column(0,0, 50)
            allColls_worksheet.write_string(allColls_row, 1, "Entity type", bold)
            allColls_worksheet.set_column(1,1, 10)
            allColls_worksheet.write_string(allColls_row, 2, "Entity withdrawn", bold)
            allColls_worksheet.set_column(2,2, 10)

        for nn in sorted(self.__warningsNNs):
            worksheet = workbook.add_worksheet(nn)
            worksheet_row = 0
            worksheet.write_string(worksheet_row, 0, "Entity ID", bold)
            worksheet.set_column(0,0, 50)
            worksheet.write_string(worksheet_row, 1, "Entity type", bold)
            worksheet.set_column(1,1, 10)
            worksheet.write_string(worksheet_row, 2, "Entity withdrawn", bold)
            worksheet.set_column(2,2, 20)
            worksheet.write_string(worksheet_row, 3, "Check", bold)
            worksheet.set_column(3,3, 10)
            worksheet.write_string(worksheet_row, 4, "Severity", bold)
            worksheet.set_column(4,4, 120)
            worksheet.write_string(worksheet_row, 5, "Message", bold)
            worksheet.set_column(5,5, 120)
            worksheet.write_string(worksheet_row, 6, "Action", bold)
            worksheet.set_column(6,6, 50)
            worksheet.write_string(worksheet_row, 7, "Email", bold)
            worksheet.set_column(7,7, 50)
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