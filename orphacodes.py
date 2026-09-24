# vim:ts=4:sw=4:sts=4:tw=0:et

"""Parse Orphadata XML and expose ORPHA-to-ICD-10 crosswalk helpers."""

import logging as log
import re
import xml.etree.ElementTree as ET
from builtins import *
from typing import List, TypedDict

from icd10codeshelper import ICD10CodesHelper

class MappingWithType(TypedDict):
    """Describe an ORPHA/ICD-10 crosswalk entry and its directionality."""
    code : str
    mapping_type : str

class OrphaCodes:
    """Parse an Orphadata mapping file and expose in-memory diagnosis crosswalks."""

    def __init__(self, file = None):
        """Load ORPHA disorders, English names, and supported ICD-10 mappings.

        Args:
            file: Path to an Orphadata ``en_product1.xml`` file; the conventional
                local filename is used when omitted.

        Raises:
            OSError: If the XML file cannot be read.
            xml.etree.ElementTree.ParseError: If the XML content is malformed.
        """
        if file is None:
            file = 'en_product1.xml'
        orpha_tree = ET.parse(file)
        orpha_root = orpha_tree.getroot()
        #self.__orpha_to_icd10_code_map = Dict[str, List[MappingWithType]]
        #self.__icd10_to_orpha_code_map = Dict[str, List[MappingWithType]]
        self.__orpha_to_icd10_code_map = {}
        self.__icd10_to_orpha_code_map = {}
        self.__orpha_codes = []
        self.__orpha_cancer_codes = []
        self.__orpha_to_name_map = {}
        for disease in orpha_tree.findall('DisorderList/Disorder'):
            orpha_code = disease.findtext('OrphaCode')
            self.__orpha_codes.append(orpha_code)
            log.debug("Processing Orpha code %s"%(orpha_code))
            for name in disease.findall("Name[@lang='en']"):
                if orpha_code not in self.__orpha_to_name_map:
                    self.__orpha_to_name_map[orpha_code] = []
                self.__orpha_to_name_map[orpha_code].append(name.text)
            for external_code in disease.findall('ExternalReferenceList/ExternalReference'):
                source = external_code.findtext('Source')
                icd10_code = external_code.findtext('Reference')
                mapping_type = external_code.findtext('DisorderMappingRelation/Name')
                log.debug("Found %s mapping type"%(mapping_type))
                mapping_type = re.sub(r'^(\S+)\s.*$',r'\1', mapping_type)
                if mapping_type == "NTBT":
                    mapping_type_inverse = "BTNT"
                elif mapping_type == "BTNT":
                    mapping_type_inverse = "NTBT"
                elif mapping_type == "E":
                    mapping_type_inverse = "E"
                else:
                    log.debug("Ignoring unknown mapping type %s"%(mapping_type))
                    continue
                if source == "ICD-10":
                    if orpha_code not in self.__orpha_to_icd10_code_map:
                        self.__orpha_to_icd10_code_map[orpha_code] = []
                    if icd10_code not in self.__icd10_to_orpha_code_map:
                        self.__icd10_to_orpha_code_map[icd10_code] = []
                    self.__orpha_to_icd10_code_map[orpha_code].append(MappingWithType(code=icd10_code, mapping_type=mapping_type))
                    log.debug("Orpha code %s maps to ICD-10 codes %s" % (orpha_code, self.__orpha_to_icd10_code_map[orpha_code]))
                    self.__icd10_to_orpha_code_map[icd10_code].append(MappingWithType(code=orpha_code, mapping_type=mapping_type_inverse))
                    log.debug("ICD-10 code %s maps to Orpha codes %s" % (icd10_code, self.__icd10_to_orpha_code_map[icd10_code]))
                    if ICD10CodesHelper.isCancerCode(icd10_code):
                        self.__orpha_cancer_codes.append(orpha_code)

    def isValidOrphaCode(self, code : str) -> bool:
        """Return whether an ORPHA code occurs in the loaded source file.

        Args:
            code: ORPHA code text to test without normalization.

        Returns:
            ``True`` when the exact code was loaded; otherwise ``False``.
        """
        return True if code in self.__orpha_codes else False

    def isCancerOrphaCode(self, code : str) -> bool:
        """Return whether an ORPHA code has a mapped cancer ICD-10 code.

        Args:
            code: ORPHA code text to test without normalization.

        Returns:
            ``True`` when a loaded ICD-10 mapping is classified as cancer.
        """
        return True if code in self.__orpha_cancer_codes else False

    def orphaToIcd10(self, code : str) -> List[MappingWithType]:
        """Return loaded ICD-10 mappings for one ORPHA code.

        Args:
            code: Exact ORPHA code lookup key.

        Returns:
            Stored mapping list for a known key, or a newly allocated empty list.
            Callers must not mutate a non-empty returned list.
        """
        if code not in self.__orpha_to_icd10_code_map:
            return []
        return self.__orpha_to_icd10_code_map[code]

    def icd10ToOrpha(self, code : str) -> List[MappingWithType]:
        """Return loaded ORPHA mappings for one ICD-10 code.

        Args:
            code: Exact ICD-10 code lookup key.

        Returns:
            Stored inverse-mapping list, or a newly allocated empty list. Nonempty
            lists are shared parser state and should be treated as read-only.
        """
        if code not in self.__icd10_to_orpha_code_map:
            return []
        return self.__icd10_to_orpha_code_map[code]

    def orphaToNamesList(self, code : str) -> List[str]:
        """Return loaded English disorder names for an ORPHA code.

        Args:
            code: Exact ORPHA code lookup key.

        Returns:
            Stored name list, or a newly allocated empty list for unknown codes.
            Nonempty results are shared parser state and should be read-only.
        """
        if code not in self.__orpha_to_name_map:
            return []
        return self.__orpha_to_name_map[code]

    def orphaToNamesString(self, code : str) -> str:
        """Render loaded English names for an ORPHA code as one display string.

        Args:
            code: Exact ORPHA code lookup key.

        Returns:
            Comma-separated names, or the input code when no name was loaded.
        """
        names = self.orphaToNamesList(code)
        if not names:
            return code
        return ", ".join(names)
