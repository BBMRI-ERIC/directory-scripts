# vim:ts=8:sw=8:tw=0:noet

import logging as log
import re
import xml.etree.ElementTree as ET
from builtins import *
from typing import List

from typing_extensions import TypedDict


class MappingWithType(TypedDict):
    code : str
    mapping_type : str

class OrphaCodes:

    def __init__(self, file = None):
        if file is None:
            file = 'en_product1.xml'
        orpha_tree = ET.parse(file)
        orpha_root = orpha_tree.getroot()
        #self.__orpha_to_icd10_code_map = Dict[str, List[MappingWithType]]
        #self.__icd10_to_orpha_code_map = Dict[str, List[MappingWithType]]
        self.__orpha_to_icd10_code_map = {}
        self.__icd10_to_orpha_code_map = {}
        self.__orpha_cancer_codes = []
        for disease in orpha_tree.findall('DisorderList/Disorder'):
            orpha_code = disease.findtext('OrphaCode')
            log.debug("Processing Orpha code %s"%(orpha_code))
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

    def orphaToIcd10(self, code : str) -> List[MappingWithType]:
        if code not in self.__orpha_to_icd10_code_map:
            return None
        return self.__orpha_to_icd10_code_map[code]

    def icd10ToOrpha(self, code : str) -> List[MappingWithType]:
        if code not in self.__icd10_to_orpha_code_map:
            return None
        return self.__icd10_to_orpha_code_map[code]

