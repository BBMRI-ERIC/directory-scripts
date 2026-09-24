# vim:ts=8:sw=8:tw=0:noet

"""Report collections that are not connected to a parent biobank."""

import logging as log

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel, DataCheckWarning, DataCheckEntityType, make_check_id

# Machine-readable check documentation for the manual generator and other tooling.
# Keep severity/entity/fields aligned with the emitted DataCheckWarning(...) calls.
CHECK_DOCS = {'OC:Orphan': {'entity': 'COLLECTION',
                                            'fields': ['id'],
                                            'severity': 'ERROR',
                                            'summary': 'Orphaned collection'}}

class OrphanedCollections(IPlugin):
	"""Report collections whose referenced parent biobank is not loaded.

	The plugin checks collection ownership relationships in the active snapshot and returns warnings without repairing references.
	"""
	CHECK_ID_PREFIX = "OC"
	def check(self, dir, args):
		"""Inspect visible collections and return orphaned-parent warnings.

		Args:
		    dir: Loaded Directory view providing collections, loaded biobank lookups, contacts, and node identifiers.
		    args: Runner options accepted for the common plugin interface; this check does not read them.

		Returns:
		    OC warnings for collections that reference an absent biobank.
		"""
		warnings = []
		log.info("Running orphaned collection checks (OrphanedCollections)")
		for collection in dir.getCollections():
			collections = dir.getGraphBiobankCollectionsFromCollection(collection['id'])
			if len(collections.edges) < 1:
				warnings.append(DataCheckWarning(make_check_id(self, "Orphan"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Orphaned collection"))
		return warnings
