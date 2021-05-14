# vim:ts=8:sw=8:tw=0:noet

import re
import urllib.request
import logging as log

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning,DataCheckEntityType

minDescWords = 3

def descriptionTooShort(s : str) -> bool:
	if len(s.split()) < minDescWords:
		return True
	else:
		return False

class SemiemptyFields(IPlugin):
	def check(self, dir, args):
		warnings = []
		log.info("Running empty or semi-empty fields checks (SemiemptyFields)")
		for biobank in dir.getBiobanks():
			if not 'description' in biobank or re.search('^\s*$', biobank['description']) or re.search('^\s*N/?A\s*$', biobank['description']):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, "Missing description for biobank ('description' attribute is empty for the biobank)"))
			if 'description' in biobank and descriptionTooShort(biobank['description']):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, biobank['id'], DataCheckEntityType.BIOBANK, f"Suspiciously short description for biobank ('description' attribute {biobank['description']} has less than {str(minDescWords)} words)"))
			if not 'name' in biobank or re.search('^\s*$', biobank['name']) or re.search('^\s*N/?A\s*$', biobank['name']):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, "Missing name for biobank ('name' attribute is empty for the biobank)"))

		for collection in dir.getCollections():
			if not 'description' in collection or re.search('^\s*$', collection['description']) or re.search('^\s*N/?A\s*$', collection['description']):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, "Missing description for collection ('description' attribute is empty for the collection)"))
			if 'description' in collection and descriptionTooShort(collection['description']):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, f"Suspiciously short description for collection ('description' attribute {collection['description']} has less than {str(minDescWords)} words)"))
			if not 'name' in collection or re.search('^\s*$', collection['name']) or re.search('^\s*N/?A\s*$', collection['name']):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Missing name for collection ('name' attribute is empty for the biobank)"))


		return warnings
