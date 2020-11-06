# vim:ts=8:sw=8:tw=0:noet 

import re
import logging as log

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning,DataCheckEntityType

class CollectionContent(IPlugin):
	def check(self, dir, args):
		warnings = []
		log.info("Running collection content checks (CollectionContent)")
		for collection in dir.getCollections():
			OoM = collection['order_of_magnitude']['id']

			materials = []
			if 'materials' in collection:
				for m in collection['materials']:
					materials.append(m['id'])
			
			data_categories = []
			if 'data_categories' in collection:
				for c in collection['data_categories']:
					data_categories.append(c['id'])

			types = []
			if 'type' in collection:
				for t in collection['type']:
					types.append(t['id'])
			diags = []
			if 'diagnosis_available' in collection:
				diag_ranges = []
				for d in collection['diagnosis_available']:
					diags.append(d['id'])
					if re.search('-', d['id']):
						diag_ranges.append(d['id'])
				if diag_ranges:
					warning = DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "It seems that diagnoses contains range - this will render the diagnosis search ineffective for the given collection. Violating diagnosis term(s): " + '; '.join(diag_ranges))
					warnings.append(warning)


			if len(types) < 1:
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Collection type not provided")
				warnings.append(warning)

			if 'size' in collection and isinstance(collection['size'], int):
				if OoM > 1 and collection['size'] < 10**OoM or collection['size'] > 10**(OoM+1):
					warning = DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Size of the collection does not match its order of magnitude: size = " + str(collection['size']) + ", order of magnitude is %d (size between %d and %d)"%(OoM, 10**OoM, 10**(OoM+1)))
					warnings.append(warning)

			if OoM > 4:
				subCollections = dir.getCollectionsDescendants(collection['id'])
				if len(subCollections) < 1:
					warning = DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, "Suspicious situation: large collection (> 100,000 samples or cases) without subcollections; unless it is a really homogeneous collection, it is advisable to refine such a collection into sub-collections to give users better insight into what is stored there")
					warnings.append(warning)

			if OoM > 5:
				if (not 'size' in collection.keys()) or (collection['size'] == 0):
					warning = DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, "Suspicious situation: large collection (> 1,000,000 samples or cases) without exact size specified")
					warnings.append(warning)


			if any(x in types for x in ['HOSPITAL', 'DISEASE_SPECIFIC', 'RD']) and len(diags) < 1:
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "No diagnoses provide for HOSPITAL or DISEASE_SPECIFIC or RD collection")
				warnings.append(warning)

			if 'BIOLOGICAL_SAMPLES' in data_categories and len(materials) == 0:
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "No material types are provided while biological samples are collected")
				warnings.append(warning)

			if 'MEDICAL_RECORDS' in data_categories and len(diags) < 1:
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, "No diagnoses provide for a collection with MEDICAL_RECORDS among its data categories")
				warnings.append(warning)

			modalities = []
			if 'imaging_modality' in collection:
				for m in collection['imaging_modality']:
					modalities.append(m['id'])

			image_dataset_types = []
			if 'image_dataset_type' in collection:
				for idt in collection['image_dataset_type']:
					image_dataset_types.append(idt['id'])

			if 'IMAGING_DATA' in data_categories:
				if len(modalities) < 1:
					warning = DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "No image modalities provided for image collection")
					warnings.append(warning)

				if len(image_dataset_types) < 1:
					warning = DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, "No image dataset types provided for image collection")
					warnings.append(warning)

			if (len(modalities) > 0 or len(image_dataset_types) > 0) and 'IMAGING_DATA' not in data_categories:
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Imaging modalities or image data set found, but IMAGING_DATA is not among data categories: image_modality = %s, image_dataset_type = %s"%(modalities,image_dataset_types))
				warnings.append(warning)

		return warnings
