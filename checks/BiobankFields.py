import re
import urllib.request

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning

class BiobankFields(IPlugin):
	def check(self, dir):
		warnings = []
		for biobank in dir.getBiobanks():
			if not 'juridical_person' in biobank or re.search('^\s*$', biobank['juridical_person']) or re.search('^\s*N/?A\s*$', biobank['juridical_person']):
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], "Missing juridical person")
				warnings.append(warning)

			if(not 'head_firstname' in biobank or re.search('^\s*$', biobank['head_firstname']) or 
					not 'head_lastname' in biobank or re.search('^\s*$', biobank['head_lastname'])):
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, biobank['id'], "Missing head person name")
				warnings.append(warning)

			if not 'head_role' in biobank or re.search('^\s*$', biobank['head_role']):
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.INFO, biobank['id'], "Missing head person role")
				warnings.append(warning)

			if((not 'collaboration_commercial' in biobank or biobank['collaboration_commercial'] == False) and
					(not 'collaboration_non_for_profit' in biobank or biobank['collaboration_non_for_profit'] == False)):
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.INFO, biobank['id'], "Biobank is available neither for commercial nor for non-for-profit collaboration")
				warnings.append(warning)


		return warnings
