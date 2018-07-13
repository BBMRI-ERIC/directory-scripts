import re

from yapsy.IPlugin import IPlugin
from customwarnings import WarningLevel,Warning

class CheckCollectionContents(IPlugin):
	def check(self, dir):
		warnings = []
		for collection in dir.getCollections():
			OoM = collection['order_of_magnitude']['id']

			materials = []
			if 'materials' in collection:
				for m in collection['materials']['items']:
					materials.append(m['id'])
			
			data_categories = []
			if 'data_categories' in collection:
				for c in collection['data_categories']['items']:
					data_categories.append(c['id'])

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

			if 'BIOLOGICAL_SAMPLES' in data_categories and len(materials) == 0:
				warning = Warning("", dir.getCollectionNN(collection['id']), WarningLevel.ERROR, "No material types are provided while biological samples are collected in " + collection['id'])
				warnings.append(warning)

			if 'IMAGING_DATA' in data_categories:
				modalities = []
				if 'imaging_modality' in collection:
					for m in collection['imaging_modality']['items']:
						modalities.append(m['id'])
				if len(modalities) < 1:
					warning = Warning("", dir.getCollectionNN(collection['id']), WarningLevel.ERROR, "No image modalities provided for image collection " + collection['id'])
					warnings.append(warning)

				image_dataset_types = []
				if 'image_dataset_type' in collection:
					for idt in collection['image_dataset_type']['items']:
						image_dataset_types.append(idt['id'])
				if len(image_dataset_types) < 1:
					warning = Warning("", dir.getCollectionNN(collection['id']), WarningLevel.WARNING, "No image dataset types provided for image collection " + collection['id'])
					warnings.append(warning)


		return warnings
