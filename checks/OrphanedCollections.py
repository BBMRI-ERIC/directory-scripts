from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning

class OrphanedCollections(IPlugin):
	def check(self, dir):
		warnings = []
		for collection in dir.getCollections():
			collections = dir.getGraphBiobankCollectionsFromCollection(collection['id'])
			if len(collections.edges) < 1:
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, collection['id'], "Orphaned collection")
				warnings.append(warning)
		return warnings
