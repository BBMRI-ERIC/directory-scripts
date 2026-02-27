# vim:ts=8:sw=8:tw=0:noet 

import logging as log

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel, DataCheckWarning, DataCheckEntityType, make_check_id

# Machine-readable check documentation for the manual generator and other tooling.
# Keep severity/entity/fields aligned with the emitted DataCheckWarning(...) calls.
CHECK_DOCS = {'CollectionExistence:LeastOneCollectionBiobank': {'entity': 'BIOBANK',
                                                   'fields': ['id'],
                                                   'severity': 'ERROR',
                                                   'summary': 'Missing at least one '
                                                              'collection for biobank'}}

class CollectionExistence(IPlugin):
	def check(self, dir, args):
		warnings = []
		log.info("Running collection existence checks (CollectionExistence)")
		for biobank in dir.getBiobanks():
			collections = dir.getGraphBiobankCollectionsFromBiobank(biobank['id'])
			if len(collections.edges) < 1:
				warnings.append(DataCheckWarning(make_check_id(self, "LeastOneCollectionBiobank"), "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "Missing at least one collection for biobank"))
		return warnings
