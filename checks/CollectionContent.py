# vim:ts=8:sw=8:tw=0:noet 

import re
import logging as log

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel, DataCheckWarning, DataCheckEntityType, make_check_id

from directory import Directory

# Machine-readable check documentation for the manual generator and other tooling.
# Keep severity/entity/fields aligned with the emitted DataCheckWarning(...) calls.
CHECK_DOCS = {'CollectionContent:AgeHighBelowMinimumValueLimitDS': {'entity': 'COLLECTION',
                                                       'fields': ['age_high'],
                                                       'severity': 'ERROR',
                                                       'summary': 'Age_high is below '
                                                                  'the minimum value '
                                                                  'limit (%d %s): '
                                                                  'offending value %d'},
 'CollectionContent:AgeLowBelowMinimumValueLimitDS': {'entity': 'COLLECTION',
                                                      'fields': ['age_low'],
                                                      'severity': 'ERROR',
                                                      'summary': 'Age_low is below the '
                                                                 'minimum value limit '
                                                                 '(%d %s): offending '
                                                                 'value %d'},
 'CollectionContent:AgeLowDHigherThanAgeHighD': {'entity': 'COLLECTION',
                                                 'fields': ['age_high', 'age_low'],
                                                 'severity': 'ERROR',
                                                 'summary': 'Age_low (%d) is higher '
                                                            'than age_high (%d)'},
 'CollectionContent:AgeUnitProvidedAgeRange': {'entity': 'COLLECTION',
                                               'fields': ['age_high',
                                                          'age_low',
                                                          'age_unit'],
                                               'severity': 'ERROR',
                                               'summary': 'Missing age_unit for '
                                                          'provided age range: '
                                                          "{collection.get('age_low')}-{collection.get('age_high')}"},
 'CollectionContent:AmbiguousSpeificationAgeUnitOne': {'entity': 'COLLECTION',
                                                       'fields': ['age_unit'],
                                                       'severity': 'ERROR',
                                                       'summary': 'Ambiguous '
                                                                  'speification of '
                                                                  'age_unit - only one '
                                                                  'value is permitted. '
                                                                  'Provided values %s'},
 'CollectionContent:CollectionTypeProvided': {'entity': 'COLLECTION',
                                              'fields': ['type'],
                                              'severity': 'ERROR',
                                              'summary': 'Collection type not '
                                                         'provided'},
 'CollectionContent:ConsiderAddingFollowingOrphaCode': {'entity': 'COLLECTION',
                                                        'fields': ['type'],
                                                        'severity': 'INFO',
                                                        'summary': 'Consider adding '
                                                                   'following ORPHA '
                                                                   'code(s) to the RD '
                                                                   'collection - based '
                                                                   'on mapping ICD-10 '
                                                                   'code %s to ORPHA '
                                                                   'codes: %s'},
 'CollectionContent:DiagnosesProvideCollection': {'entity': 'COLLECTION',
                                                  'fields': ['data_categories'],
                                                  'severity': 'WARNING',
                                                  'summary': 'No diagnoses provide for '
                                                             'a collection with '
                                                             'MEDICAL_RECORDS among '
                                                             'its data categories'},
 'CollectionContent:DiagnosesProvideHospitalDisease': {'entity': 'COLLECTION',
                                                       'fields': ['type'],
                                                       'severity': 'ERROR',
                                                       'summary': 'No diagnoses '
                                                                  'provide for '
                                                                  'HOSPITAL or '
                                                                  'DISEASE_SPECIFIC or '
                                                                  'RD collection'},
 'CollectionContent:DiagnosesProvidedMedicalRecords': {'entity': 'COLLECTION',
                                                       'fields': ['data_categories'],
                                                       'severity': 'WARNING',
                                                       'summary': 'Diagnoses provided '
                                                                  'but no '
                                                                  'MEDICAL_RECORDS '
                                                                  'among its data '
                                                                  'categories'},
 'CollectionContent:DiagnosesProvidedNoneHospital': {'entity': 'COLLECTION',
                                                     'fields': ['type'],
                                                     'severity': 'INFO',
                                                     'summary': 'Diagnoses provided '
                                                                'but none of HOSPITAL, '
                                                                'DISEASE_SPECIFIC, RD '
                                                                'is specified as '
                                                                'collection type (this '
                                                                'may be easily false '
                                                                'positive check)'},
 'CollectionContent:ImageDatasetTypesProvidedImage': {'entity': 'COLLECTION',
                                                      'fields': ['data_categories'],
                                                      'severity': 'WARNING',
                                                      'summary': 'No image dataset '
                                                                 'types provided for '
                                                                 'image collection'},
 'CollectionContent:ImageModalitiesProvidedImage': {'entity': 'COLLECTION',
                                                    'fields': ['data_categories'],
                                                    'severity': 'ERROR',
                                                    'summary': 'No image modalities '
                                                               'provided for image '
                                                               'collection'},
 'CollectionContent:ImagingModalitiesImageDataSet': {'entity': 'COLLECTION',
                                                     'fields': ['data_categories'],
                                                     'severity': 'ERROR',
                                                     'summary': 'Imaging modalities or '
                                                                'image data set found, '
                                                                'but IMAGING_DATA is '
                                                                'not among data '
                                                                'categories: '
                                                                'image_modality = %s, '
                                                                'image_dataset_type = '
                                                                '%s'},
 'CollectionContent:MaterialTypesProvidedWhile': {'entity': 'COLLECTION',
                                                  'fields': ['data_categories',
                                                             'materials'],
                                                  'severity': 'ERROR',
                                                  'summary': 'No material types are '
                                                             'provided while '
                                                             'biological samples are '
                                                             'collected'},
 'CollectionContent:OrphaCodeDiagnosesProvided': {'entity': 'COLLECTION',
                                                  'fields': ['type'],
                                                  'severity': 'WARNING',
                                                  'summary': 'ORPHA code diagnoses '
                                                             'provided, but collection '
                                                             'not marked as rare '
                                                             'disease (RD) collection'},
 'CollectionContent:OrphaCodeDiagnosesSpecifiedIcd10': {'entity': 'COLLECTION',
                                                        'fields': [],
                                                        'severity': 'WARNING',
                                                        'summary': 'ORPHA code '
                                                                   'diagnoses '
                                                                   'specified, but no '
                                                                   'ICD-10 equivalents '
                                                                   'provided, thus '
                                                                   'making collection '
                                                                   'impossible to find '
                                                                   'for users using '
                                                                   'ICD-10 codes'},
 'CollectionContent:OrphaCodeFoundS': {'entity': 'COLLECTION',
                                       'fields': ['diagnosis_available', 'name'],
                                       'severity': 'ERROR',
                                       'summary': 'Invalid ORPHA code found: %s'},
 'CollectionContent:OrphaCodeSProvidedTranslationIcd': {'entity': 'COLLECTION',
                                                        'fields': ['code'],
                                                        'severity': 'INFO',
                                                        'summary': 'ORPHA code %s '
                                                                   'provided, but its '
                                                                   'translation to '
                                                                   'ICD-10 as %s is '
                                                                   'not provided '
                                                                   '(mapping is of %s '
                                                                   'type). It is '
                                                                   'recommended to '
                                                                   'provide this '
                                                                   'translation '
                                                                   'explicitly until '
                                                                   'Directory '
                                                                   'implements full '
                                                                   'semantic mapping '
                                                                   'search.'},
 'CollectionContent:RareDiseaseRdCollectionWithout': {'entity': 'COLLECTION',
                                                      'fields': ['type'],
                                                      'severity': 'WARNING',
                                                      'summary': 'Rare disease (RD) '
                                                                 'collection without '
                                                                 'ORPHA code '
                                                                 'diagnoses'},
 'CollectionContent:SampleTypesAdvertisedBiological': {'entity': 'COLLECTION',
                                                       'fields': ['data_categories',
                                                                  'materials'],
                                                       'severity': 'ERROR',
                                                       'summary': 'Sample types '
                                                                  'advertised but '
                                                                  'BIOLOGICAL_SAMPLES '
                                                                  'missing among its '
                                                                  'data categories'},
 'CollectionContent:SeemsDiagnosesContainsRangeWill': {'entity': 'COLLECTION',
                                                       'fields': ['diagnosis_available'],
                                                       'severity': 'ERROR',
                                                       'summary': 'It seems that '
                                                                  'diagnoses contains '
                                                                  'range - this will '
                                                                  'render the '
                                                                  'diagnosis search '
                                                                  'ineffective for the '
                                                                  'given collection. '
                                                                  'Violating diagnosis '
                                                                  'term(s): '},
 'CollectionContent:SituationAgeLowAgeHighDPositive': {'entity': 'COLLECTION',
                                                       'fields': ['age_high',
                                                                  'age_low'],
                                                       'severity': 'INFO',
                                                       'summary': 'Suspect situation: '
                                                                  'age_low == age_high '
                                                                  '== (%d) (may be '
                                                                  'false positive)'},
 'CollectionContent:SizeCollectionDoesMatchOrder': {'entity': 'COLLECTION',
                                                    'fields': ['order_of_magnitude',
                                                               'size'],
                                                    'severity': 'ERROR',
                                                    'summary': 'Size of the collection '
                                                               'does not match its '
                                                               'order of magnitude: '
                                                               'size = , order of '
                                                               'magnitude is %d (size '
                                                               'between %d and %d)'},
 'CollectionContent:SuspiciousSituationLarge': {'entity': 'COLLECTION',
                                                'fields': ['id', 'order_of_magnitude'],
                                                'severity': 'INFO',
                                                'summary': 'Suspicious situation: '
                                                           'large collection (> '
                                                           '100,000 samples or cases) '
                                                           'without subcollections; '
                                                           'unless it is a really '
                                                           'homogeneous collection, it '
                                                           'is advisable to refine '
                                                           'such a collection into '
                                                           'sub-collections to give '
                                                           'users better insight into '
                                                           'what is stored there'},
 'CollectionContent:SuspiciousSituationLarge2': {'entity': 'COLLECTION',
                                                 'fields': ['order_of_magnitude',
                                                            'size'],
                                                 'severity': 'INFO',
                                                 'summary': 'Suspicious situation: '
                                                            'large collection (> '
                                                            '1,000,000 samples or '
                                                            'cases) without exact size '
                                                            'specified'}}

class CollectionContent(IPlugin):
	def check(self, dir, args):
		warnings = []
		log.info("Running collection content checks (CollectionContent)")
		orphacodes = dir.getOrphaCodesMapper()
		for collection in dir.getCollections():
			#OoM = collection['order_of_magnitude']['id'] # EMX2 OoM does not have ID, then:
			if 'order_of_magnitude' in collection:
				OoM = int(collection['order_of_magnitude'])
			else:
				OoM = None
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
								warnings.append(DataCheckWarning(make_check_id(self, "OrphaCodeFoundS"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Invalid ORPHA code found: %s" % (d['name'])))
				if diag_ranges:
					warnings.append(DataCheckWarning(make_check_id(self, "SeemsDiagnosesContainsRangeWill"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "It seems that diagnoses contains range - this will render the diagnosis search ineffective for the given collection. Violating diagnosis term(s): " + '; '.join(diag_ranges)))


			if len(types) < 1:
				warnings.append(DataCheckWarning(make_check_id(self, "CollectionTypeProvided"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Collection type not provided"))

			if 'size' in collection and isinstance(collection['size'], int) and OoM:
				if OoM > 1 and collection['size'] < 10**OoM or collection['size'] > 10**(OoM+1):
					warnings.append(DataCheckWarning(make_check_id(self, "SizeCollectionDoesMatchOrder"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Size of the collection does not match its order of magnitude: size = " + str(collection['size']) + ", order of magnitude is %d (size between %d and %d)"%(OoM, 10**OoM, 10**(OoM+1))))

			if OoM and OoM > 4:
				subCollections = dir.getCollectionsDescendants(collection['id'])
				if len(subCollections) < 1:
					warnings.append(DataCheckWarning(make_check_id(self, "SuspiciousSituationLarge"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Suspicious situation: large collection (> 100,000 samples or cases) without subcollections; unless it is a really homogeneous collection, it is advisable to refine such a collection into sub-collections to give users better insight into what is stored there"))

			if OoM and OoM > 5:
				if (not 'size' in collection.keys()) or (collection['size'] == 0):
					warnings.append(DataCheckWarning(make_check_id(self, "SuspiciousSituationLarge2"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Suspicious situation: large collection (> 1,000,000 samples or cases) without exact size specified"))


			if any(x in types for x in ['HOSPITAL', 'DISEASE_SPECIFIC', 'RD']) and len(diags) < 1:
				warnings.append(DataCheckWarning(make_check_id(self, "DiagnosesProvideHospitalDisease"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "No diagnoses provide for HOSPITAL or DISEASE_SPECIFIC or RD collection"))

			if len(diags) > 0 and not any(x in types for x in ['HOSPITAL', 'DISEASE_SPECIFIC', 'RD']):
				warnings.append(DataCheckWarning(make_check_id(self, "DiagnosesProvidedNoneHospital"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Diagnoses provided but none of HOSPITAL, DISEASE_SPECIFIC, RD is specified as collection type (this may be easily false positive check)"))

			if 'BIOLOGICAL_SAMPLES' in data_categories and len(materials) == 0:
				warnings.append(DataCheckWarning(make_check_id(self, "MaterialTypesProvidedWhile"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "No material types are provided while biological samples are collected"))

			if len(materials) > 0 and 'BIOLOGICAL_SAMPLES' not in data_categories:
				warnings.append(DataCheckWarning(make_check_id(self, "SampleTypesAdvertisedBiological"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Sample types advertised but BIOLOGICAL_SAMPLES missing among its data categories"))

			if 'MEDICAL_RECORDS' in data_categories and len(diags) < 1:
				warnings.append(DataCheckWarning(make_check_id(self, "DiagnosesProvideCollection"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "No diagnoses provide for a collection with MEDICAL_RECORDS among its data categories"))

			if len(diags) > 0 and 'MEDICAL_RECORDS' not in data_categories:
				warnings.append(DataCheckWarning(make_check_id(self, "DiagnosesProvidedMedicalRecords"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Diagnoses provided but no MEDICAL_RECORDS among its data categories"))

			if 'RD' in types and len(diags_orpha) == 0:
				warnings.append(DataCheckWarning(make_check_id(self, "RareDiseaseRdCollectionWithout"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Rare disease (RD) collection without ORPHA code diagnoses"))
				if dir.issetOrphaCodesMapper():
					for d in diags_icd10:
						orpha = orphacodes.icd10ToOrpha(d)
						if orpha is not None and len(orpha) > 0:
							orphalist = ["%(code)s(%(name)s)/%(mapping_type)s" % {'code' : c['code'], 'name' : orphacodes.orphaToNamesString(c['code']), 'mapping_type' : c['mapping_type']} for c in orpha]
							warnings.append(DataCheckWarning(make_check_id(self, "ConsiderAddingFollowingOrphaCode"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Consider adding following ORPHA code(s) to the RD collection - based on mapping ICD-10 code %s to ORPHA codes: %s"%(d, ",".join(orphalist))))


			if len(diags_orpha) > 0 and 'RD' not in types:
				warnings.append(DataCheckWarning(make_check_id(self, "OrphaCodeDiagnosesProvided"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "ORPHA code diagnoses provided, but collection not marked as rare disease (RD) collection"))

			if len(diags_orpha) > 0 and len(diags_icd10) == 0:
				warnings.append(DataCheckWarning(make_check_id(self, "OrphaCodeDiagnosesSpecifiedIcd10"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "ORPHA code diagnoses specified, but no ICD-10 equivalents provided, thus making collection impossible to find for users using ICD-10 codes"))

			if len(diags_orpha) > 0 and dir.issetOrphaCodesMapper():
				for d in diags_orpha:
					icd10codes = orphacodes.orphaToIcd10(d)
					for c in icd10codes:
						if 'urn:miriam:icd:' + c['code'] not in diags_icd10:
							warnings.append(DataCheckWarning(make_check_id(self, "OrphaCodeSProvidedTranslationIcd"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "ORPHA code %s provided, but its translation to ICD-10 as %s is not provided (mapping is of %s type). It is recommended to provide this translation explicitly until Directory implements full semantic mapping search."%(d,c['code'],c['mapping_type'])))

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
					warnings.append(DataCheckWarning(make_check_id(self, "ImageModalitiesProvidedImage"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "No image modalities provided for image collection"))

				if len(image_dataset_types) < 1:
					warnings.append(DataCheckWarning(make_check_id(self, "ImageDatasetTypesProvidedImage"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "No image dataset types provided for image collection"))

			if (len(modalities) > 0 or len(image_dataset_types) > 0) and 'IMAGING_DATA' not in data_categories:
				warnings.append(DataCheckWarning(make_check_id(self, "ImagingModalitiesImageDataSet"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Imaging modalities or image data set found, but IMAGING_DATA is not among data categories: image_modality = %s, image_dataset_type = %s"%(modalities,image_dataset_types)))

			age_unit = None
			if 'age_unit' in collection:
				age_units = [collection['age_unit']]
				if len(age_units) > 1:
					warnings.append(DataCheckWarning(make_check_id(self, "AmbiguousSpeificationAgeUnitOne"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Ambiguous speification of age_unit - only one value is permitted. Provided values %s"%(age_units)))
				elif len(age_units) == 1:
					age_unit = age_units[0]
			if ('age_high' in collection or 'age_low' in collection) and ('age_low' not in collection or len(age_units) < 1):
				warnings.append(DataCheckWarning(make_check_id(self, "AgeUnitProvidedAgeRange"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Missing age_unit for provided age range: {collection.get('age_low')}-{collection.get('age_high')}"))

			age_min_limit = -1
			if age_unit == "MONTH":
				age_min_limit = age_min_limit*12
			elif age_unit == "WEEK":
				age_min_limit = age_min_limit*52.1775
			elif age_unit == "DAY":
				age_min_limit = age_min_limit*365.2

			if ('age_high' in collection and collection['age_high'] < age_min_limit):
				warnings.append(DataCheckWarning(make_check_id(self, "AgeHighBelowMinimumValueLimitDS"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Age_high is below the minimum value limit (%d %s): offending value %d"%(age_min_limit, age_unit, collection['age_high'])))
			if ('age_low' in collection and collection['age_low'] < age_min_limit):
				warnings.append(DataCheckWarning(make_check_id(self, "AgeLowBelowMinimumValueLimitDS"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Age_low is below the minimum value limit (%d %s): offending value %d"%(age_min_limit, age_unit, collection['age_low'])))
			
			if ('age_high' in collection and 'age_low' in collection):
				if (collection['age_low'] > collection['age_high']):
					warnings.append(DataCheckWarning(make_check_id(self, "AgeLowDHigherThanAgeHighD"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Age_low (%d) is higher than age_high (%d)"%(collection['age_low'], collection['age_high'])))
				elif (collection['age_low'] == collection['age_high']):
					warnings.append(DataCheckWarning(make_check_id(self, "SituationAgeLowAgeHighDPositive"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Suspect situation: age_low == age_high == (%d) (may be false positive)"%(collection['age_low'])))

		return warnings
