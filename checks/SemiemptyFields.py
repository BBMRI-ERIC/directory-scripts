# vim:ts=8:sw=8:tw=0:noet

"""Detect missing, placeholder, and insufficiently populated entity fields."""

import re
import urllib.request
import logging as log

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel, DataCheckWarning, DataCheckEntityType, make_check_id

minDescWords = 3
placeholderDescriptionPatterns = [
	re.compile(r'^\s*to be provided\.?\s*$', re.IGNORECASE),
	re.compile(r'^\s*description not available(?: yet)?\.?\s*$', re.IGNORECASE),
	re.compile(r'^\s*not specified\.?\s*$', re.IGNORECASE),
	re.compile(r'^\s*not available\.?\s*$', re.IGNORECASE),
]

def descriptionTooShort(s : str) -> bool:
	"""Return whether a description is below the configured informative-length threshold.

	Args:
	    s: Description value measured after the helper's existing normalization rules.

	Returns:
	    ``True`` when the description is considered too short; otherwise ``False``.
	"""
	if len(s.split()) < minDescWords:
		return True
	else:
		return False

def descriptionIsPlaceholder(s : str) -> bool:
	"""Return whether a description matches a known placeholder phrase.

	Args:
	    s: Description value checked case-insensitively against placeholder patterns.

	Returns:
	    ``True`` for placeholder content such as text still to be provided; otherwise ``False``.
	"""
	for pattern in placeholderDescriptionPatterns:
		if pattern.match(s):
			return True
	return False

# Machine-readable check documentation for the manual generator and other tooling.
# Keep severity/entity/fields aligned with the emitted DataCheckWarning(...) calls.
CHECK_DOCS = {'SE:BBDescMissing': {'entity': 'BIOBANK',
                                                   'fields': ['description'],
                                                   'severity': 'WARNING',
                                                   'summary': 'Missing description for '
                                                              "biobank ('description' "
                                                              'attribute is empty for '
                                                              'the biobank)'},
 'SE:CollDescMissing': {'entity': 'COLLECTION',
                                                      'fields': ['description'],
                                                      'severity': 'WARNING',
                                                      'summary': 'Missing description '
                                                                 'for collection '
                                                                 "('description' "
                                                                 'attribute is empty '
                                                                 'for the collection)'},
 'SE:BBNameMissing': {'entity': 'BIOBANK',
                                                   'fields': ['name'],
                                                   'severity': 'ERROR',
                                                   'summary': 'Missing name for '
                                                              "biobank ('name' "
                                                              'attribute is empty for '
                                                              'the biobank)'},
 'SE:CollNameMissing': {'entity': 'COLLECTION',
                                                      'fields': ['name'],
                                                      'severity': 'ERROR',
                                                      'summary': 'Missing name for '
                                                                 "collection ('name' "
                                                                 'attribute is empty '
                                                                 'for the collection)'},
 'SE:BBDescShort': {'entity': 'BIOBANK',
                                                  'fields': ['description'],
                                                  'severity': 'WARNING',
                                                  'summary': 'Suspiciously short '
                                                             'description for biobank '
                                                             "('description' attribute "
                                                             "{biobank['description']} "
                                                             'has less than '
                                                             '{str(minDescWords)} '
                                                             'words)'},
 'SE:CollDescShort': {'entity': 'COLLECTION',
                                                   'fields': ['description'],
                                                   'severity': 'WARNING',
                                                   'summary': 'Suspiciously short '
                                                              'description for '
                                                              'collection '
                                                              "('description' "
                                                              'attribute '
                                                              "{collection['description']} "
                                                              'has less than '
                                                              '{str(minDescWords)} '
                                                              'words)'},
 'SE:BBDescPlaceholder': {'entity': 'BIOBANK',
                                                  'fields': ['description'],
                                                  'severity': 'WARNING',
                                                  'summary': 'Biobank description uses '
                                                             'a placeholder value '
                                                             'instead of a real '
                                                             'description.'},
 'SE:CollDescPlaceholder': {'entity': 'COLLECTION',
                                                    'fields': ['description'],
                                                    'severity': 'WARNING',
                                                    'summary': 'Collection '
                                                               'description uses a '
                                                               'placeholder value '
                                                               'instead of a real '
                                                               'description.'}}

class SemiemptyFields(IPlugin):
	"""Detect missing, short, or placeholder descriptions and names.

	The plugin applies deterministic text thresholds and placeholder patterns to visible Directory entities. It returns findings without rewriting narrative fields.
	"""
	CHECK_ID_PREFIX = "SE"
	def check(self, dir, args):
		"""Inspect entity text fields and return semi-empty or placeholder-content warnings.

		Args:
		    dir: Loaded Directory view providing visible biobanks, collections, contacts, and node identifiers.
		    args: Runner options accepted for the common plugin interface; this check does not read them.

		Returns:
		    SEF warnings for missing, too-short, or placeholder names and descriptions.
		"""
		warnings = []
		log.info("Running empty or semi-empty fields checks (SemiemptyFields)")
		for biobank in dir.getBiobanks():
			if not 'description' in biobank or re.search(r'^\s*$', biobank['description']) or re.search(r'^\s*N/?A\s*$', biobank['description']):
				warnings.append(DataCheckWarning(make_check_id(self, "BBDescMissing"), "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "Missing description for biobank ('description' attribute is empty for the biobank)"))
			if 'description' in biobank and descriptionIsPlaceholder(biobank['description']):
				warnings.append(DataCheckWarning(make_check_id(self, "BBDescPlaceholder"), "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), f"Biobank description uses a placeholder value ('{biobank['description']}')"))
			elif 'description' in biobank and descriptionTooShort(biobank['description']):
				warnings.append(DataCheckWarning(make_check_id(self, "BBDescShort"), "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), f"Suspiciously short description for biobank ('description' attribute {biobank['description']} has less than {str(minDescWords)} words)"))
			if not 'name' in biobank or re.search(r'^\s*$', biobank['name']) or re.search(r'^\s*N/?A\s*$', biobank['name']):
				warnings.append(DataCheckWarning(make_check_id(self, "BBNameMissing"), "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "Missing name for biobank ('name' attribute is empty for the biobank)"))

		for collection in dir.getCollections():
			if not 'description' in collection or re.search(r'^\s*$', collection['description']) or re.search(r'^\s*N/?A\s*$', collection['description']):
				warnings.append(DataCheckWarning(make_check_id(self, "CollDescMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Missing description for collection ('description' attribute is empty for the collection)"))
			if 'description' in collection and descriptionIsPlaceholder(collection['description']):
				warnings.append(DataCheckWarning(make_check_id(self, "CollDescPlaceholder"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Collection description uses a placeholder value ('{collection['description']}')"))
			elif 'description' in collection and descriptionTooShort(collection['description']):
				warnings.append(DataCheckWarning(make_check_id(self, "CollDescShort"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Suspiciously short description for collection ('description' attribute {collection['description']} has less than {str(minDescWords)} words)"))
			if not 'name' in collection or re.search(r'^\s*$', collection['name']) or re.search(r'^\s*N/?A\s*$', collection['name']):
				warnings.append(DataCheckWarning(make_check_id(self, "CollNameMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Missing name for collection ('name' attribute is empty for the collection)"))


		return warnings
