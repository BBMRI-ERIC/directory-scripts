import re

from yapsy.IPlugin import IPlugin
from customwarnings import WarningLevel,Warning

class CheckBiobankFields(IPlugin):
	def check(self, dir):
		warnings = []
		for biobank in dir.getBiobanks():
			if not 'juridical_person' in biobank or re.search('^\s*$', biobank['juridical_person']):
				warning = Warning("", dir.getBiobankNN(biobank['id']), WarningLevel.ERROR, "Missing juridical person for " + biobank['id'])
				warnings.append(warning)

			if(not 'head_firstname' in biobank or re.search('^\s*$', biobank['head_firstname']) or 
					not 'head_lastname' in biobank or re.search('^\s*$', biobank['head_lastname'])):
				warning = Warning("", dir.getBiobankNN(biobank['id']), WarningLevel.WARNING, "Missing head person name for " + biobank['id'])
				warnings.append(warning)

			if not 'head_role' in biobank or re.search('^\s*$', biobank['head_role']):
				warning = Warning("", dir.getBiobankNN(biobank['id']), WarningLevel.INFO, "Missing head person role for " + biobank['id'])
				warnings.append(warning)

		return warnings
