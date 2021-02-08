# vim:ts=8:sw=8:tw=0:noet

import logging as log

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning,DataCheckEntityType

class OrphanedCollections(IPlugin):
	def check(self, dir, args):
		warnings = []
		log.info("Running orphaned collection checks (OrphanedCollections)")
		for collection in dir.getCollections():
			collections = dir.getGraphBiobankCollectionsFromCollection(collection['id'])
			if len(collections.edges) < 1:
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Orphaned collection"))
		return warnings
