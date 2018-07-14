from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning

class CheckOrphanedCollection(IPlugin):
	def check(self, dir):
		warnings = []
		for collection in dir.getCollections():
			collections = dir.getGraphBiobankCollectionsFromCollection(collection['id'])
			if len(collections.edges) < 1:
				warning = DataCheckWarning("", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, "Orphaned collection " + collection['id'])
				warnings.append(warning)
		return warnings
