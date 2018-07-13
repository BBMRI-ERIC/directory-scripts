from yapsy.IPlugin import IPlugin
from customwarnings import WarningLevel,Warning

class CheckCollectionExists(IPlugin):
	def check(self, dir):
		warnings = []
		for collection in dir.getCollections():
			collections = dir.getGraphBiobankCollectionsFromCollection(collection['id'])
			if len(collections.edges) < 1:
				warning = Warning("", dir.getBiobankNN(biobank['id']), WarningLevel.ERROR, "Orphaned collection " + collection['id'])
				warnings.append(warning)
		return warnings
