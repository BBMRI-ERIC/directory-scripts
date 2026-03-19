# vim:ts=8:sw=8:tw=0:noet 

import re
import logging as log

from yapsy.IPlugin import IPlugin
from check_fix_helpers import make_collection_multi_value_fix
from customwarnings import DataCheckWarningLevel, DataCheckWarning, DataCheckEntityType, make_check_id

from directory import Directory

# Machine-readable check documentation for the manual generator and other tooling.
# Keep severity/entity/fields aligned with the emitted DataCheckWarning(...) calls.
CHECK_DOCS = {'CC:AgeHighBelowMin': {'entity': 'COLLECTION',
                                                       'fields': ['age_high'],
                                                       'severity': 'ERROR',
                                                       'summary': 'Age_high is below '
                                                                  'the minimum value '
                                                                  'limit (%d %s): '
                                                                  'offending value %d'},
 'CC:AgeLowBelowMin': {'entity': 'COLLECTION',
                                                      'fields': ['age_low'],
                                                      'severity': 'ERROR',
                                                      'summary': 'Age_low is below the '
                                                                 'minimum value limit '
                                                                 '(%d %s): offending '
                                                                 'value %d'},
 'CC:AgeRangeInverted': {'entity': 'COLLECTION',
                                                 'fields': ['age_high', 'age_low'],
                                                 'severity': 'ERROR',
                                                 'summary': 'Age_low (%d) is higher '
                                                            'than age_high (%d)'},
 'CC:AgeUnitMissing': {'entity': 'COLLECTION',
                                               'fields': ['age_high',
                                                          'age_low',
                                                          'age_unit'],
                                               'severity': 'ERROR',
                                               'summary': 'Missing age_unit for '
                                                          'provided age range: '
                                                          "{collection.get('age_low')}-{collection.get('age_high')}"},
 'CC:AgeUnitAmbiguous': {'entity': 'COLLECTION',
                                                       'fields': ['age_unit'],
                                                       'severity': 'ERROR',
                                                       'summary': 'Ambiguous '
                                                                  'speification of '
                                                                  'age_unit - only one '
                                                                  'value is permitted. '
                                                                  'Provided values %s'},
 'CC:TypeMissing': {'entity': 'COLLECTION',
                                              'fields': ['type'],
                                              'severity': 'ERROR',
                                              'summary': 'Collection type not '
                                                         'provided'},
 'CC:RDOrphaSuggest': {'entity': 'COLLECTION',
                                                        'fields': ['type'],
                                                        'severity': 'INFO',
                                                        'summary': 'Consider adding '
                                                                   'following ORPHA '
                                                                   'code(s) to the RD '
                                                                   'collection - based '
                                                                   'on mapping ICD-10 '
                                                                   'code %s to ORPHA '
                                                                   'codes: %s'},
 'CC:MedRecDiagGap': {'entity': 'COLLECTION',
                                                  'fields': ['data_categories'],
                                                  'severity': 'WARNING',
                                                  'summary': 'No diagnoses provide for '
                                                             'a collection with '
                                                             'MEDICAL_RECORDS among '
                                                             'its data categories'},
 'CC:DiagMissingDisease': {'entity': 'COLLECTION',
                                                       'fields': ['type'],
                                                       'severity': 'ERROR',
                                                       'summary': 'No diagnoses '
                                                                  'provide for '
                                                                  'HOSPITAL or '
                                                                  'DISEASE_SPECIFIC or '
                                                                  'RD collection'},
 'CC:DiagCatMismatch': {'entity': 'COLLECTION',
                                                       'fields': ['data_categories'],
                                                       'severity': 'WARNING',
                                                       'summary': 'Diagnoses provided '
                                                                  'but no '
                                                                  'MEDICAL_RECORDS '
                                                                  'among its data '
                                                                  'categories'},
 'CC:DiagTypeMismatch': {'entity': 'COLLECTION',
                                                     'fields': ['type'],
                                                     'severity': 'INFO',
                                                     'summary': 'Diagnoses provided '
                                                                'but none of HOSPITAL, '
                                                                'DISEASE_SPECIFIC, RD '
                                                                'is specified as '
                                                                'collection type (this '
                                                                'may be easily false '
                                                                'positive check)'},
 'CC:ImgDataMissing': {'entity': 'COLLECTION',
                                                      'fields': ['data_categories'],
                                                      'severity': 'WARNING',
                                                      'summary': 'No image dataset '
                                                                 'types provided for '
                                                                 'image collection'},
 'CC:ImgModMissing': {'entity': 'COLLECTION',
                                                    'fields': ['data_categories'],
                                                    'severity': 'ERROR',
                                                    'summary': 'No image modalities '
                                                               'provided for image '
                                                               'collection'},
 'CC:ImageCatMissing': {'entity': 'COLLECTION',
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
 'CC:ImageTypeMissing': {'entity': 'COLLECTION',
                                                      'fields': ['type'],
                                                      'severity': 'ERROR',
                                                      'summary': 'Imaging modalities or '
                                                                 'image data set found, '
                                                                 'but collection type '
                                                                 'does not include '
                                                                 'IMAGE.'},
 'CC:MaterialsMissing': {'entity': 'COLLECTION',
                                                  'fields': ['data_categories',
                                                             'materials'],
                                                  'severity': 'ERROR',
                                                  'summary': 'No material types are '
                                                             'provided while '
                                                             'biological samples are '
                                                             'collected'},
 'CC:OrphaNeedsRDType': {'entity': 'COLLECTION',
                                                  'fields': ['type'],
                                                  'severity': 'WARNING',
                                                  'summary': 'ORPHA code diagnoses '
                                                             'provided, but collection '
                                                             'not marked as rare '
                                                             'disease (RD) collection'},
 'CC:OrphaNeedsIcd': {'entity': 'COLLECTION',
                                                        'fields': ['diagnosis_available'],
                                                        'fix': 'Add the relevant '
                                                               'ICD-10 diagnosis '
                                                               'codes alongside the '
                                                               'existing ORPHA codes '
                                                               'so the collection can '
                                                               'also be found by '
                                                               'users searching via '
                                                               'ICD-10.',
                                                        'severity': 'WARNING',
                                                        'summary': 'The collection '
                                                                   'uses ORPHA '
                                                                   'diagnosis codes '
                                                                   'but does not '
                                                                   'provide matching '
                                                                   'ICD-10 diagnosis '
                                                                   'values.'},
 'CC:OrphaInvalid': {'entity': 'COLLECTION',
                                       'fields': ['diagnosis_available', 'name'],
                                       'severity': 'ERROR',
                                       'summary': 'Invalid ORPHA code found: %s'},
 'CC:OrphaIcdSuggest': {'entity': 'COLLECTION',
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
 'CC:RDOrphaMissing': {'entity': 'COLLECTION',
                                                      'fields': ['type'],
                                                      'severity': 'WARNING',
                                                      'summary': 'Rare disease (RD) '
                                                                 'collection without '
                                                                 'ORPHA code '
                                                                 'diagnoses'},
 'CC:SampleCatMismatch': {'entity': 'COLLECTION',
                                                       'fields': ['data_categories',
                                                                  'materials'],
                                                       'severity': 'ERROR',
                                                       'summary': 'Sample types '
                                                                  'advertised but '
                                                                  'BIOLOGICAL_SAMPLES '
                                                                  'missing among its '
                                                                  'data categories'},
 'CC:DiagRange': {'entity': 'COLLECTION',
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
 'CC:AgeRangePoint': {'entity': 'COLLECTION',
                                                       'fields': ['age_high',
                                                                  'age_low'],
                                                       'severity': 'INFO',
                                                       'summary': 'Suspect situation: '
                                                                  'age_low == age_high '
                                                                  '== (%d) (may be '
                                                                  'false positive)'},
 'CC:SizeOoMMismatch': {'entity': 'COLLECTION',
                                                    'fields': ['order_of_magnitude',
                                                               'size'],
                                                    'severity': 'ERROR',
                                                    'summary': 'Size of the collection '
                                                               'does not match its '
                                                               'order of magnitude: '
                                                               'size = , order of '
                                                               'magnitude is %d (size '
                                                               'between %d and %d)'},
 'CC:LargeNoSubcoll': {'entity': 'COLLECTION',
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
 'CC:LargeOoMOnly': {'entity': 'COLLECTION',
                                                 'fields': ['order_of_magnitude',
                                                            'size'],
                                                 'severity': 'INFO',
                                                 'summary': 'Suspicious situation: '
                                                            'large collection (> '
                                                            '1,000,000 samples or '
                                                            'cases) without exact size '
                                                            'specified'},
	'CC:DiagCrosswalkOrphaSuggest': {
		'entity': 'COLLECTION',
		'fields': ['diagnosis_available', 'type'],
		'severity': 'INFO',
		'fix': 'Append the missing ORPHA diagnosis code inferred conservatively from an existing ICD-10 diagnosis.',
		'summary': 'Conservative ICD-10 to ORPHA crosswalk suggests adding ORPHA code(s) %s based on ICD-10 diagnosis %s (%s mapping).',
	},
	'CC:DiagCrosswalkOrphaAmbiguous': {
		'entity': 'COLLECTION',
		'fields': ['diagnosis_available', 'type'],
		'severity': 'INFO',
		'summary': 'ICD-10 diagnosis %s has multiple or risky ORPHA crosswalk candidates %s; automatic ORPHA update skipped.',
	},
	'CC:DiagCrosswalkIcdSuggest': {
		'entity': 'COLLECTION',
		'fields': ['diagnosis_available'],
		'severity': 'INFO',
		'fix': 'Append the missing ICD-10 diagnosis code inferred conservatively from an existing ORPHA diagnosis.',
		'summary': 'Conservative ORPHA to ICD-10 crosswalk suggests adding ICD-10 code(s) %s based on ORPHA diagnosis %s (%s mapping).',
	},
	'CC:DiagCrosswalkIcdAmbiguous': {
		'entity': 'COLLECTION',
		'fields': ['diagnosis_available'],
		'severity': 'INFO',
		'summary': 'ORPHA diagnosis %s has multiple or risky ICD-10 crosswalk candidates %s; automatic ICD-10 update skipped.',
	}}


def _ordered_unique(values):
	ordered = []
	seen = set()
	for value in values:
		if not value or value in seen:
			continue
		seen.add(value)
		ordered.append(value)
	return ordered


def _orpha_code_core(value):
	return re.sub('^ORPHA:', '', value)


def _icd_to_orpha_safe_missing(plugin, collection, collection_nn, icd_code, mappings, existing_orpha_codes, *, allow_ntbt):
	missing_exact = []
	missing_ntbt = []
	risky = []
	for mapping in mappings:
		orpha_code = mapping['code']
		mapping_type = mapping['mapping_type']
		if orpha_code in existing_orpha_codes:
			continue
		if mapping_type == 'E':
			missing_exact.append(orpha_code)
		elif mapping_type == 'NTBT':
			if allow_ntbt:
				missing_ntbt.append(orpha_code)
		else:
			risky.append("%s/%s" % (orpha_code, mapping_type))
	safe_missing = _ordered_unique(missing_exact + missing_ntbt)
	if len(safe_missing) == 1:
		target = safe_missing[0]
		mapping_kind = "exact" if target in missing_exact else "narrower ICD to broader ORPHA"
		confidence = 'certain' if target in missing_exact else 'almost_certain'
		return DataCheckWarning(
			"CC:DiagCrosswalkOrphaSuggest",
			"",
			collection_nn,
			DataCheckWarningLevel.INFO,
			collection['id'],
			DataCheckEntityType.COLLECTION,
			str(collection['withdrawn']),
			"Conservative ICD-10 to ORPHA crosswalk suggests adding ORPHA code(s) ORPHA:%s based on ICD-10 diagnosis %s (%s mapping)." % (target, icd_code, mapping_kind),
			fix_proposals=[
				make_collection_multi_value_fix(
					update_id='diagnosis_available.add.orpha_from_icd10',
					module='CC',
					collection=collection,
					field='diagnosis_available',
					proposed_values=['ORPHA:%s' % (target)],
					confidence=confidence,
					human_explanation='Add ORPHA diagnosis ORPHA:%s inferred from ICD-10 diagnosis %s.' % (target, icd_code),
					rationale='The ICD-10 diagnosis crosswalk maps conservatively to ORPHA in a direction accepted for automatic metadata enrichment.',
				)
			],
		)
	if len(safe_missing) > 1 or risky:
		candidates = _ordered_unique(["ORPHA:%s" % code for code in safe_missing] + risky)
		if candidates:
			return DataCheckWarning(
				"CC:DiagCrosswalkOrphaAmbiguous",
				"",
				collection_nn,
				DataCheckWarningLevel.INFO,
				collection['id'],
				DataCheckEntityType.COLLECTION,
				str(collection['withdrawn']),
				"ICD-10 diagnosis %s has multiple or risky ORPHA crosswalk candidates %s; automatic ORPHA update skipped." % (icd_code, ",".join(candidates)),
			)
	return None


def _orpha_to_icd_safe_missing(plugin, collection, collection_nn, orpha_code, mappings, existing_icd10_codes):
	missing_exact = []
	missing_ntbt = []
	risky = []
	for mapping in mappings:
		icd10_code = mapping['code']
		mapping_type = mapping['mapping_type']
		if icd10_code in existing_icd10_codes:
			continue
		if mapping_type == 'E':
			missing_exact.append(icd10_code)
		elif mapping_type == 'NTBT':
			missing_ntbt.append(icd10_code)
		else:
			risky.append("%s/%s" % (icd10_code, mapping_type))
	safe_missing = _ordered_unique(missing_exact + missing_ntbt)
	if len(safe_missing) == 1:
		target = safe_missing[0]
		mapping_kind = "exact" if target in missing_exact else "narrower ORPHA to broader ICD-10"
		confidence = 'certain' if target in missing_exact else 'almost_certain'
		return DataCheckWarning(
			"CC:DiagCrosswalkIcdSuggest",
			"",
			collection_nn,
			DataCheckWarningLevel.INFO,
			collection['id'],
			DataCheckEntityType.COLLECTION,
			str(collection['withdrawn']),
			"Conservative ORPHA to ICD-10 crosswalk suggests adding ICD-10 code(s) %s based on ORPHA diagnosis %s (%s mapping)." % (target, orpha_code, mapping_kind),
			fix_proposals=[
				make_collection_multi_value_fix(
					update_id='diagnosis_available.add.icd10_from_orpha',
					module='CC',
					collection=collection,
					field='diagnosis_available',
					proposed_values=['urn:miriam:icd:%s' % (target)],
					confidence=confidence,
					human_explanation='Add ICD-10 diagnosis %s inferred from ORPHA diagnosis %s.' % (target, orpha_code),
					rationale='The ORPHA diagnosis crosswalk maps conservatively to ICD-10 in a direction accepted for automatic metadata enrichment.',
				)
			],
		)
	if len(safe_missing) > 1 or risky:
		candidates = _ordered_unique(safe_missing + risky)
		if candidates:
			return DataCheckWarning(
				"CC:DiagCrosswalkIcdAmbiguous",
				"",
				collection_nn,
				DataCheckWarningLevel.INFO,
				collection['id'],
				DataCheckEntityType.COLLECTION,
				str(collection['withdrawn']),
				"ORPHA diagnosis %s has multiple or risky ICD-10 crosswalk candidates %s; automatic ICD-10 update skipped." % (orpha_code, ",".join(candidates)),
			)
	return None

class CollectionContent(IPlugin):
	CHECK_ID_PREFIX = "CC"
	def check(self, dir, args):
		warnings = []
		log.info("Running collection content checks (CollectionContent)")
		orphacodes = dir.getOrphaCodesMapper()
		for collection in dir.getCollections():
			collection_nn = dir.getCollectionNN(collection['id'])
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
							orpha_code = _orpha_code_core(d['name'])
							if orphacodes.isValidOrphaCode(orpha_code):
								diags_orpha.append(orpha_code)
							else:
								warnings.append(DataCheckWarning(make_check_id(self, "OrphaInvalid"), "", collection_nn, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Invalid ORPHA code found: %s" % (d['name'])))
				if diag_ranges:
					warnings.append(DataCheckWarning(make_check_id(self, "DiagRange"), "", collection_nn, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "It seems that diagnoses contains range - this will render the diagnosis search ineffective for the given collection. Violating diagnosis term(s): " + '; '.join(diag_ranges)))


			if len(types) < 1:
				warnings.append(DataCheckWarning(make_check_id(self, "TypeMissing"), "", collection_nn, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Collection type not provided"))

			if 'size' in collection and isinstance(collection['size'], int) and OoM:
				if OoM > 1 and (collection['size'] < 10**OoM or collection['size'] > 10**(OoM+1)):
					warnings.append(DataCheckWarning(make_check_id(self, "SizeOoMMismatch"), "", collection_nn, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Size of the collection does not match its order of magnitude: size = " + str(collection['size']) + ", order of magnitude is %d (size between %d and %d)"%(OoM, 10**OoM, 10**(OoM+1))))

			if OoM and OoM > 4:
				subCollections = dir.getCollectionsDescendants(collection['id'])
				if len(subCollections) < 1:
					warnings.append(DataCheckWarning(make_check_id(self, "LargeNoSubcoll"), "", collection_nn, DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Suspicious situation: large collection (> 100,000 samples or cases) without subcollections; unless it is a really homogeneous collection, it is advisable to refine such a collection into sub-collections to give users better insight into what is stored there"))

			if OoM and OoM > 5:
				if (not 'size' in collection.keys()) or (collection['size'] == 0):
					warnings.append(DataCheckWarning(make_check_id(self, "LargeOoMOnly"), "", collection_nn, DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Suspicious situation: large collection (> 1,000,000 samples or cases) without exact size specified"))


			if any(x in types for x in ['HOSPITAL', 'DISEASE_SPECIFIC', 'RD']) and len(diags) < 1:
				warnings.append(DataCheckWarning(make_check_id(self, "DiagMissingDisease"), "", collection_nn, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "No diagnoses provide for HOSPITAL or DISEASE_SPECIFIC or RD collection"))

			if len(diags) > 0 and not any(x in types for x in ['HOSPITAL', 'DISEASE_SPECIFIC', 'RD']):
				warnings.append(DataCheckWarning(make_check_id(self, "DiagTypeMismatch"), "", collection_nn, DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Diagnoses provided but none of HOSPITAL, DISEASE_SPECIFIC, RD is specified as collection type (this may be easily false positive check)"))

			if 'BIOLOGICAL_SAMPLES' in data_categories and len(materials) == 0:
				warnings.append(DataCheckWarning(make_check_id(self, "MaterialsMissing"), "", collection_nn, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "No material types are provided while biological samples are collected"))

			if len(materials) > 0 and 'BIOLOGICAL_SAMPLES' not in data_categories:
				warnings.append(DataCheckWarning(make_check_id(self, "SampleCatMismatch"), "", collection_nn, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Sample types advertised but BIOLOGICAL_SAMPLES missing among its data categories"))

			if 'MEDICAL_RECORDS' in data_categories and len(diags) < 1:
				warnings.append(DataCheckWarning(make_check_id(self, "MedRecDiagGap"), "", collection_nn, DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "No diagnoses provide for a collection with MEDICAL_RECORDS among its data categories"))

			if len(diags) > 0 and 'MEDICAL_RECORDS' not in data_categories:
				warnings.append(DataCheckWarning(make_check_id(self, "DiagCatMismatch"), "", collection_nn, DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Diagnoses provided but no MEDICAL_RECORDS among its data categories"))

			has_crosswalk_orpha_fix = False
			crosswalk_handled_orpha_sources = set()
			if dir.issetOrphaCodesMapper() and ('RD' in types or len(diags_orpha) > 0):
				for d in diags_icd10:
					crosswalk_warning = _icd_to_orpha_safe_missing(
						self,
						collection,
						collection_nn,
						d,
						orphacodes.icd10ToOrpha(d),
						set(diags_orpha),
						allow_ntbt=('RD' in types),
					)
					if crosswalk_warning is not None:
						warnings.append(crosswalk_warning)
						if getattr(crosswalk_warning, 'fix_proposals', None):
							has_crosswalk_orpha_fix = True
				for d in diags_orpha:
					crosswalk_warning = _orpha_to_icd_safe_missing(
						self,
						collection,
						collection_nn,
						d,
						orphacodes.orphaToIcd10(d),
						set(diags_icd10),
					)
					if crosswalk_warning is not None:
						warnings.append(crosswalk_warning)
						crosswalk_handled_orpha_sources.add(d)

			if 'RD' in types and len(diags_orpha) == 0:
				warnings.append(DataCheckWarning(make_check_id(self, "RDOrphaMissing"), "", collection_nn, DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Rare disease (RD) collection without ORPHA code diagnoses"))
				if dir.issetOrphaCodesMapper() and not has_crosswalk_orpha_fix:
					for d in diags_icd10:
						orpha = orphacodes.icd10ToOrpha(d)
						if orpha:
							orphalist = ["%(code)s(%(name)s)/%(mapping_type)s" % {'code' : c['code'], 'name' : orphacodes.orphaToNamesString(c['code']), 'mapping_type' : c['mapping_type']} for c in orpha]
							warnings.append(DataCheckWarning(make_check_id(self, "RDOrphaSuggest"), "", collection_nn, DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Consider adding following ORPHA code(s) to the RD collection - based on mapping ICD-10 code %s to ORPHA codes: %s"%(d, ",".join(orphalist))))


			if len(diags_orpha) > 0 and 'RD' not in types:
				warnings.append(DataCheckWarning(make_check_id(self, "OrphaNeedsRDType"), "", collection_nn, DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "ORPHA code diagnoses provided, but collection not marked as rare disease (RD) collection", fix_proposals=[
					make_collection_multi_value_fix(
						update_id='collection_type.add.rd',
						module='CC',
						collection=collection,
						field='type',
						proposed_values=['RD'],
						confidence='almost_certain',
						human_explanation='Add collection type RD because the collection already advertises ORPHA diagnoses.',
						rationale='Structured ORPHA diagnoses strongly suggest a rare-disease collection type.',
					)
				]))

			if len(diags_orpha) > 0 and len(diags_icd10) == 0:
				warnings.append(DataCheckWarning(make_check_id(self, "OrphaNeedsIcd"), "", collection_nn, DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "ORPHA code diagnoses specified, but no ICD-10 equivalents provided, thus making collection impossible to find for users using ICD-10 codes"))

			if len(diags_orpha) > 0 and dir.issetOrphaCodesMapper():
				for d in diags_orpha:
					if d in crosswalk_handled_orpha_sources:
						continue
					icd10codes = orphacodes.orphaToIcd10(d)
					for c in icd10codes:
						if c['code'] not in diags_icd10:
							warnings.append(DataCheckWarning(make_check_id(self, "OrphaIcdSuggest"), "", collection_nn, DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "ORPHA code %s provided, but its translation to ICD-10 as %s is not provided (mapping is of %s type). It is recommended to provide this translation explicitly until Directory implements full semantic mapping search."%(d,c['code'],c['mapping_type'])))

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
					warnings.append(DataCheckWarning(make_check_id(self, "ImgModMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "No image modalities provided for image collection"))

				if len(image_dataset_types) < 1:
					warnings.append(DataCheckWarning(make_check_id(self, "ImgDataMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "No image dataset types provided for image collection"))

			if (len(modalities) > 0 or len(image_dataset_types) > 0) and 'IMAGING_DATA' not in data_categories:
				warnings.append(DataCheckWarning(make_check_id(self, "ImageCatMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Imaging modalities or image data set found, but IMAGING_DATA is not among data categories: image_modality = %s, image_dataset_type = %s"%(modalities,image_dataset_types)))
			if (len(modalities) > 0 or len(image_dataset_types) > 0) and 'IMAGE' not in types:
				warnings.append(DataCheckWarning(make_check_id(self, "ImageTypeMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Imaging modalities or image data set found, but collection type does not include IMAGE", fix_proposals=[
					make_collection_multi_value_fix(
						update_id='collection_type.add.image',
						module='CC',
						collection=collection,
						field='type',
						proposed_values=['IMAGE'],
						confidence='certain',
						human_explanation='Add collection type IMAGE because imaging modalities or image dataset types are already present.',
						rationale='Structured imaging metadata deterministically implies IMAGE collection type.',
					)
				]))

			age_unit = None
			age_units = []
			if 'age_unit' in collection:
				age_units = collection['age_unit']
				if len(age_units) > 1:
					warnings.append(DataCheckWarning(make_check_id(self, "AgeUnitAmbiguous"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Ambiguous speification of age_unit - only one value is permitted. Provided values %s"%(age_units)))
				elif len(age_units) == 1:
					age_unit = age_units[0]
			if ('age_high' in collection or 'age_low' in collection) and ('age_low' not in collection or len(age_units) < 1):
				warnings.append(DataCheckWarning(make_check_id(self, "AgeUnitMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Missing age_unit for provided age range: {collection.get('age_low')}-{collection.get('age_high')}"))

			age_min_limit = -1
			if age_unit == "MONTH":
				age_min_limit = age_min_limit*12
			elif age_unit == "WEEK":
				age_min_limit = age_min_limit*52.1775
			elif age_unit == "DAY":
				age_min_limit = age_min_limit*365.2

			if ('age_high' in collection and collection['age_high'] < age_min_limit):
				warnings.append(DataCheckWarning(make_check_id(self, "AgeHighBelowMin"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Age_high is below the minimum value limit (%d %s): offending value %d"%(age_min_limit, age_unit, collection['age_high'])))
			if ('age_low' in collection and collection['age_low'] < age_min_limit):
				warnings.append(DataCheckWarning(make_check_id(self, "AgeLowBelowMin"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Age_low is below the minimum value limit (%d %s): offending value %d"%(age_min_limit, age_unit, collection['age_low'])))
			
			if ('age_high' in collection and 'age_low' in collection):
				if (collection['age_low'] > collection['age_high']):
					warnings.append(DataCheckWarning(make_check_id(self, "AgeRangeInverted"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Age_low (%d) is higher than age_high (%d)"%(collection['age_low'], collection['age_high'])))
				elif (collection['age_low'] == collection['age_high']):
					warnings.append(DataCheckWarning(make_check_id(self, "AgeRangePoint"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Suspect situation: age_low == age_high == (%d) (may be false positive)"%(collection['age_low'])))

		return warnings
