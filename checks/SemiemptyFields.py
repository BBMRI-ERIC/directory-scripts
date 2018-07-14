import re
import urllib.request

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning

minDescWords = 3

def descriptionTooShort(s : str) -> bool:
	if len(s.split()) < minDescWords:
		return True
	else:
		return False

class CheckSemiemptyFields(IPlugin):
	def check(self, dir):
		warnings = []
		for biobank in dir.getBiobanks():
			if not 'description' in biobank or re.search('^\s*$', biobank['description']) or re.search('^\s*N/?A\s*$', biobank['description']):
				warning = DataCheckWarning("", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], "Missing description for biobank")
				warnings.append(warning)
			if 'description' in biobank and descriptionTooShort(biobank['description']):
				warning = DataCheckWarning("", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], "Suspiciously short description for biobank (< " + str(minDescWords) + " words)")
				warnings.append(warning)
			if not 'name' in biobank or re.search('^\s*$', biobank['name']) or re.search('^\s*N/?A\s*$', biobank['name']):
				warning = DataCheckWarning("", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], "Missing name for biobank")
				warnings.append(warning)

		for collection in dir.getCollections():
			if not 'description' in collection or re.search('^\s*$', collection['description']) or re.search('^\s*N/?A\s*$', collection['description']):
				warning = DataCheckWarning("", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], "Missing description for collection")
				warnings.append(warning)
			if 'description' in collection and descriptionTooShort(collection['description']):
				warning = DataCheckWarning("", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], "Suspiciously short description for collection (< " + str(minDescWords) + " words)")
				warnings.append(warning)
			if not 'name' in collection or re.search('^\s*$', collection['name']) or re.search('^\s*N/?A\s*$', collection['name']):
				warning = DataCheckWarning("", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], "Missing name for collection")
				warnings.append(warning)


		return warnings
