# vim:ts=8:sw=8:tw=0:noet 

import re
import logging as log

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning,DataCheckEntityType

from directory import Directory

class CollectionContent(IPlugin):
	def check(self, dir, args):
		warnings = []
		log.info("Running collection content checks (CollectionContent)")
		orphacodes = dir.getOrphaCodesMapper()
		for collection in dir.getCollections():
			#OoM = collection['order_of_magnitude']['id'] # EMX2 OoM does not have ID, then:
			OoM = int(collection['order_of_magnitude'])
			#materials = Directory.getListOfEntityAttributeIds(collection, 'materials') EMX2 materials do not have id, then:
			materials = Directory.getListOfEntityAttributes(collection, 'materials')
			#data_categories = Directory.getListOfEntityAttributeIds(collection, 'data_categories') # EMX2 data_categories does not have ID, then:
			data_categories = Directory.getListOfEntityAttributes(collection, 'data_categories')
			#types = Directory.getListOfEntityAttributeIds(collection, 'type') # EMX2 types does not have ID, then:
			types = Directory.getListOfEntityAttributes(collection, 'type')

			diags = []
			diags_icd10 = []
			diags_orpha = []
			if 'diagnosis_available' in collection:
				diag_ranges = []
				for d in collection['diagnosis_available']:
					#diags.append(d['id'])  # EMX2 collection['diagnosis_available'] has name but not id (this applies to all times we call d in this loop)
					diags.append(d['name'])
					if re.search('-', d['name']):
						diag_ranges.append(d['name'])
					if re.search('^urn:miriam:icd:', d['name']):
						diags_icd10.append(re.sub('^urn:miriam:icd:','',d['name']))
					elif re.search('^ORPHA:', d['name']):
						if dir.issetOrphaCodesMapper():
							if orphacodes.isValidOrphaCode(d):
								diags_orpha.append(re.sub('^ORPHA:', '', d['name']))
							else:
								warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Invalid ORPHA code found: %s" % (d['name'])))
				if diag_ranges:
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "It seems that diagnoses contains range - this will render the diagnosis search ineffective for the given collection. Violating diagnosis term(s): " + '; '.join(diag_ranges)))


			if len(types) < 1:
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Collection type not provided"))

			if 'size' in collection and isinstance(collection['size'], int):
				if OoM > 1 and collection['size'] < 10**OoM or collection['size'] > 10**(OoM+1):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Size of the collection does not match its order of magnitude: size = " + str(collection['size']) + ", order of magnitude is %d (size between %d and %d)"%(OoM, 10**OoM, 10**(OoM+1))))

			if OoM > 4:
				subCollections = dir.getCollectionsDescendants(collection['id'])
				if len(subCollections) < 1:
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, "Suspicious situation: large collection (> 100,000 samples or cases) without subcollections; unless it is a really homogeneous collection, it is advisable to refine such a collection into sub-collections to give users better insight into what is stored there"))

			if OoM > 5:
				if (not 'size' in collection.keys()) or (collection['size'] == 0):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, "Suspicious situation: large collection (> 1,000,000 samples or cases) without exact size specified"))


			if any(x in types for x in ['HOSPITAL', 'DISEASE_SPECIFIC', 'RD']) and len(diags) < 1:
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "No diagnoses provide for HOSPITAL or DISEASE_SPECIFIC or RD collection"))

			if len(diags) > 0 and not any(x in types for x in ['HOSPITAL', 'DISEASE_SPECIFIC', 'RD']):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, "Diagnoses provided but none of HOSPITAL, DISEASE_SPECIFIC, RD is specified as collection type (this may be easily false positive check)"))

			if 'BIOLOGICAL_SAMPLES' in data_categories and len(materials) == 0:
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "No material types are provided while biological samples are collected"))

			if len(materials) > 0 and 'BIOLOGICAL_SAMPLES' not in data_categories:
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Sample types advertised but BIOLOGICAL_SAMPLES missing among its data categories"))

			if 'MEDICAL_RECORDS' in data_categories and len(diags) < 1:
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, "No diagnoses provide for a collection with MEDICAL_RECORDS among its data categories"))

			if len(diags) > 0 and 'MEDICAL_RECORDS' not in data_categories:
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, "Diagnoses provided but no MEDICAL_RECORDS among its data categories"))

			if 'RD' in types and len(diags_orpha) == 0:
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, "Rare disease (RD) collection without ORPHA code diagnoses"))
				if dir.issetOrphaCodesMapper():
					for d in diags_icd10:
						orpha = orphacodes.icd10ToOrpha(d)
						if orpha is not None and len(orpha) > 0:
							orphalist = ["%(code)s(%(name)s)/%(mapping_type)s" % {'code' : c['code'], 'name' : orphacodes.orphaToNamesString(c['code']), 'mapping_type' : c['mapping_type']} for c in orpha]
							warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, "Consider adding following ORPHA code(s) to the RD collection - based on mapping ICD-10 code %s to ORPHA codes: %s"%(d, ",".join(orphalist))))


			if len(diags_orpha) > 0 and 'RD' not in types:
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, "ORPHA code diagnoses provided, but collection not marked as rare disease (RD) collection"))

			if len(diags_orpha) > 0 and len(diags_icd10) == 0:
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, "ORPHA code diagnoses specified, but no ICD-10 equivalents provided, thus making collection impossible to find for users using ICD-10 codes"))

			if len(diags_orpha) > 0 and dir.issetOrphaCodesMapper():
				for d in diags_orpha:
					icd10codes = orphacodes.orphaToIcd10(d)
					for c in icd10codes:
						if 'urn:miriam:icd:' + c['code'] not in diags_icd10:
							warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, "ORPHA code %s provided, but its translation to ICD-10 as %s is not provided (mapping is of %s type). It is recommended to provide this translation explicitly until Directory implements full semantic mapping search."%(d,c['code'],c['mapping_type'])))

			modalities = []
			if 'imaging_modality' in collection:
				for m in collection['imaging_modality']:
					#modalities.append(m['id']) # EMX2 imaging_modality does not have id, then:
					modalities.append(m)

			image_dataset_types = []
			if 'image_dataset_type' in collection:
				for idt in collection['image_dataset_type']:
					#image_dataset_types.append(idt['id']) # EMX2 image_dataset_type does not have id, then:
					image_dataset_types.append(idt) # TODO: Check if this is OK!!

			if 'IMAGING_DATA' in data_categories:
				if len(modalities) < 1:
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "No image modalities provided for image collection"))

				if len(image_dataset_types) < 1:
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, "No image dataset types provided for image collection"))

			if (len(modalities) > 0 or len(image_dataset_types) > 0) and 'IMAGING_DATA' not in data_categories:
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Imaging modalities or image data set found, but IMAGING_DATA is not among data categories: image_modality = %s, image_dataset_type = %s"%(modalities,image_dataset_types)))

			age_unit = None
			if 'age_unit' in collection:
				age_units = collection['age_unit']
				if len(age_units) > 1:
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Ambiguous speification of age_unit - only one value is permitted. Provided values %s"%(age_units)))
				elif len(age_units) == 1:
					age_unit = age_units[0]
			if ('age_high' in collection or 'age_low' in collection) and ('age_low' not in collection or len(age_units) < 1):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, f"Missing age_unit for provided age range: {collection.get('age_low')}-{collection.get('age_high')}"))

			age_min_limit = -1
			if age_unit == "MONTH":
				age_min_limit = age_min_limit*12
			elif age_unit == "WEEK":
				age_min_limit = age_min_limit*52.1775
			elif age_unit == "DAY":
				age_min_limit = age_min_limit*365.2

			if ('age_high' in collection and collection['age_high'] < age_min_limit):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Age_high is below the minimum value limit (%d %s): offending value %d"%(age_min_limit, age_unit, collection['age_high'])))
			if ('age_low' in collection and collection['age_low'] < age_min_limit):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Age_low is below the minimum value limit (%d %s): offending value %d"%(age_min_limit, age_unit, collection['age_low'])))
			
			if ('age_high' in collection and 'age_low' in collection):
				if (collection['age_low'] > collection['age_high']):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Age_low (%d) is higher than age_high (%d)"%(collection['age_low'], collection['age_high'])))
				elif (collection['age_low'] == collection['age_high']):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, "Suspect situation: age_low == age_high == (%d) (may be false positive)"%(collection['age_low'])))

		return warnings
