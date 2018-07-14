import re
import urllib.request

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning

class CheckBiobankFields(IPlugin):
	def check(self, dir):
		warnings = []
		for biobank in dir.getBiobanks():
			if not 'juridical_person' in biobank or re.search('^\s*$', biobank['juridical_person']):
				warning = DataCheckWarning("", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, "Missing juridical person for " + biobank['id'])
				warnings.append(warning)

			if(not 'head_firstname' in biobank or re.search('^\s*$', biobank['head_firstname']) or 
					not 'head_lastname' in biobank or re.search('^\s*$', biobank['head_lastname'])):
				warning = DataCheckWarning("", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, "Missing head person name for " + biobank['id'])
				warnings.append(warning)

			if not 'head_role' in biobank or re.search('^\s*$', biobank['head_role']):
				warning = DataCheckWarning("", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.INFO, "Missing head person role for " + biobank['id'])
				warnings.append(warning)

		return warnings
