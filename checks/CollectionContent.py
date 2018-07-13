import re

from yapsy.IPlugin import IPlugin
from customwarnings import WarningLevel,Warning

class CheckCollectionContents(IPlugin):
	def check(self, dir):
		warnings = []
		for collection in dir.getCollections():
			OoM = collection['order_of_magnitude']['id']
			if 'materials' in collection:
				materials = collection['materials']['items']
			else:
				materials = []
			if 'data_categories' in collection:
				data_categories = collection['data_categories']['items']
			else:
				data_categories = []

			if OoM > 4:
				# TODO check that it has subcollections, since it is collection with 100.000+ samples and hence very likely not homogenous
				pass

			if((not 'data_access_fee' in collection or collection['data_access_fee'] == False) and 
					(not 'data_access_joint_project' in collection or collection['data_access_joint_project'] == False) and 
					(not 'data_access_uri' in collection or re.search('^\s*$', collection['data_access_uri']))):
				warning = Warning("", dir.getCollectionNN(collection['id']), WarningLevel.ERROR, "No data access mode enabled and no data access policy URI provided for collection " + collection['id'])
				warnings.append(warning)

			if((not 'sample_access_fee' in collection or collection['sample_access_fee'] == False) and 
					(not 'sample_access_joint_project' in collection or collection['sample_access_joint_project'] == False) and 
					(not 'sample_access_uri' in collection or re.search('^\s*$', collection['sample_access_uri']))):
				warning = Warning("", dir.getCollectionNN(collection['id']), WarningLevel.ERROR, "No sample access mode enabled and no sample access policy URI provided for collection " + collection['id'])
				warnings.append(warning)

		return warnings
