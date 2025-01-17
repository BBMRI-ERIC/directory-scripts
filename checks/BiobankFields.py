# vim:ts=8:sw=8:tw=0:noet

import re
import urllib.request
import logging as log

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning,DataCheckEntityType

class BiobankFields(IPlugin):
	def check(self, dir, args):
		warnings = []
		log.info("Running biobank fields checks (BiobankFields)")
		for biobank in dir.getBiobanks():
			if not 'juridical_person' in biobank or re.search('^\s*$', biobank['juridical_person']):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, "Missing juridical person ('juridical_person' attribute is empty)"))
			elif re.search('^\s*N/?A\s*$', biobank['juridical_person'], re.IGNORECASE) or re.search('^\s*To be filled', biobank['juridical_person'], re.IGNORECASE) or re.search('\bunknown\b', biobank['juridical_person'], re.IGNORECASE):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, "Invalid juridical person ('juridical_person' attribute has an invalid value - offending value: '" + biobank['juridical_person'] + "')"))

#			if(not 'head_firstname' in biobank or re.search('^\s*$', biobank['head_firstname']) or 
#					not 'head_lastname' in biobank or re.search('^\s*$', biobank['head_lastname'])):
#				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, biobank['id'], DataCheckEntityType.BIOBANK, "Missing head person name ('head_firstname' and/or 'head_lastname' attributes are empty)"))
#
#			if not 'head_role' in biobank or re.search('^\s*$', biobank['head_role']):
#				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.INFO, biobank['id'], DataCheckEntityType.BIOBANK, "Missing head person role ('head_role' attribute is empty)"))

			if 'contact'  not in biobank or type(biobank['contact']) is not dict:
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, "Missing valid contact for the biobank"))

		return warnings
