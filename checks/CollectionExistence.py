from yapsy.IPlugin import IPlugin
from customwarnings import WarningLevel,Warning

class CheckCollectionExists(IPlugin):
	def check(self, dir):
		warnings = []
		for biobank in dir.getBiobanks():
			collections = dir.getGraphBiobankCollectionsFromBiobank(biobank['id'])
			if len(collections.edges) < 1:
				warning = Warning("", dir.getBiobankNN(biobank['id']), WarningLevel.ERROR, "Missing at least one collection for biobank " + biobank['id'])
				warnings.append(warning)
		return warnings
