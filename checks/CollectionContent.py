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

			types = []
			if 'type' in collection:
				for t in collection['type']['items']:
					types.append(t['id'])

			if len(types) < 1:
				warning = Warning("", dir.getCollectionNN(collection['id']), WarningLevel.ERROR, "Collection type not provided " + collection['id'])
				warnings.append(warning)


			if OoM > 4:
				subCollections = dir.getCollectionsDescendants(collection['id'])
				if len(subCollections) < 1:
					warning = Warning("", dir.getCollectionNN(collection['id']), WarningLevel.INFO, "Suspicious situation: large collection without subcollections - " + collection['id'])
					warnings.append(warning)

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

			if 'HOSPITAL' in types or 'DISEASE_SPECIFIC' in types or 'RD' in types:
				diagnoses = []
				if 'diagnosis_available' in collection:
					for d in collection['diagnosis_available']['items']:
						diagnoses.append(d['id'])
				if len(diagnoses) < 1:
					warning = Warning("", dir.getCollectionNN(collection['id']), WarningLevel.ERROR, "No diagnoses provide for HOSPITAL or DISEASE_SPECIFIC or RD collection" + collection['id'])
					warnings.append(warning)


		return warnings
