# vim:ts=8:sw=8:tw=0:noet

import re
import urllib.request
import logging as log

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel, DataCheckWarning, DataCheckEntityType, make_check_id

from directory import Directory

# Machine-readable check documentation for the manual generator and other tooling.
# Keep severity/entity/fields aligned with the emitted DataCheckWarning(...) calls.
CHECK_DOCS = {'AccessPolicies:BiobankAvailableNeither': {'entity': 'BIOBANK',
                                            'fields': ['collaboration_commercial',
                                                       'collaboration_non_for_profit'],
                                            'severity': 'ERROR',
                                            'summary': 'Biobank is available neither '
                                                       'for commercial nor for '
                                                       'non-for-profit collaboration'},
 'AccessPolicies:CollectionContainsBiological': {'entity': 'COLLECTION',
                                                 'fields': ['data_use', 'materials'],
                                                 'severity': 'INFO',
                                                 'summary': 'Collection contains '
                                                            'biological material types '
                                                            "'{materials}' but ethics "
                                                            'approval needed '
                                                            "'{DUO_term_ethics_needed}' "
                                                            'is not specified in '
                                                            'data_use attribute (may '
                                                            'be false-positive). DUO '
                                                            'documentation available '
                                                            'at '
                                                            '{DUOs_to_url(DUO_term_ethics_needed)}'},
 'AccessPolicies:CollectionDiseaseSpecificDuoTerm': {'entity': 'COLLECTION',
                                                     'fields': ['data_use', 'type'],
                                                     'severity': 'INFO',
                                                     'summary': 'Collection is disease '
                                                                'specific but '
                                                                "'{DUO_term_disease_specific}' "
                                                                'is not specified in '
                                                                'data_use attribute '
                                                                '(may be '
                                                                'false-positive). DUO '
                                                                'documentation '
                                                                'available at '
                                                                '{DUOs_to_url(DUO_term_disease_specific)}'},
 'AccessPolicies:DataAccessModeEnabledDataAccess': {'entity': 'COLLECTION',
                                                    'fields': ['data_access_description',
                                                               'data_access_fee',
                                                               'data_access_joint_project',
                                                               'data_access_uri'],
                                                    'severity': 'ERROR',
                                                    'summary': 'No data access mode '
                                                               'enabled and no data '
                                                               'access policy '
                                                               '(description nor URI) '
                                                               'provided for '
                                                               'collection'},
 'AccessPolicies:DataReturnRequiredDuoTermData': {'entity': 'COLLECTION',
                                                  'fields': ['data_use'],
                                                  'severity': 'INFO',
                                                  'summary': 'Data return is not '
                                                             'required (missing '
                                                             '{DUO_term_data_return}) '
                                                             'in data_use attribute - '
                                                             'it is recommended for '
                                                             'biobanks to support it '
                                                             'based on BBMRI-ERIC '
                                                             'Access policy (but not '
                                                             'required). DUO '
                                                             'documentation available '
                                                             'at '
                                                             '{DUOs_to_url(DUO_term_data_return)}'},
 'AccessPolicies:DataUseOntologyDuoTermProvided': {'entity': 'COLLECTION',
                                                   'fields': ['data_use'],
                                                   'severity': 'WARNING',
                                                   'summary': 'No Data Use Ontology '
                                                              '(DUO) term provided in '
                                                              'data_use attribute'},
 'AccessPolicies:ImagingAccessModeEnabledImaging': {'entity': 'COLLECTION',
                                                    'fields': ['image_access_description',
                                                               'image_access_fee',
                                                               'image_access_uri',
                                                               'image_joint_project'],
                                                    'severity': 'ERROR',
                                                    'summary': 'No imaging access mode '
                                                               'enabled and no imaging '
                                                               'access policy '
                                                               '(description nor URI) '
                                                               'provided for a '
                                                               'collection which '
                                                               'contains imaging data'},
 'AccessPolicies:JointProjectsSampleDataImage': {'entity': 'COLLECTION',
                                                 'fields': ['data_use'],
                                                 'severity': 'WARNING',
                                                 'summary': 'Joint projects for '
                                                            'sample/data/image access '
                                                            'specified and '
                                                            '{DUO_term_joint_project} '
                                                            'is not specified in '
                                                            'data_use attribute. DUO '
                                                            'documentation available '
                                                            'at '
                                                            '{DUOs_to_url(DUO_term_joint_project)}'},
 'AccessPolicies:LeastOneAttributesSpecified': {'entity': 'COLLECTION',
                                                'fields': ['collaboration_commercial',
                                                           'collaboration_non_for_profit',
                                                           'data_use'],
                                                'severity': 'INFO',
                                                'summary': 'At least one of '
                                                           '{attributes} specified on '
                                                           'collection level but '
                                                           "'{DUO_term}' is not "
                                                           'specified in data_use '
                                                           'attribute (may be however '
                                                           'intentional). DUO '
                                                           'documentation available at '
                                                           '{DUOs_to_url(DUO_term)}'},
 'AccessPolicies:LeastOneAttributesSpecified2': {'entity': 'COLLECTION',
                                                 'fields': ['collaboration_commercial',
                                                            'collaboration_non_for_profit',
                                                            'data_use'],
                                                 'severity': 'INFO',
                                                 'summary': 'At least one of '
                                                            '{attributes} specified on '
                                                            'biobank level and not '
                                                            'overridden on collection '
                                                            "but '{DUO_term}' is not "
                                                            'specified in data_use '
                                                            'attribute (may be however '
                                                            'intentional). DUO '
                                                            'documentation available '
                                                            'at '
                                                            '{DUOs_to_url(DUO_term)}'},
 'AccessPolicies:LeastOneAttributesSpecified3': {'entity': 'COLLECTION',
                                                 'fields': ['collaboration_commercial',
                                                            'collaboration_non_for_profit',
                                                            'data_use'],
                                                 'severity': 'ERROR',
                                                 'summary': 'At least one of '
                                                            '{attributes} specified on '
                                                            'collection level but '
                                                            "conflicting '{DUO_term}' "
                                                            'is specified in data_use '
                                                            'attribute. DUO '
                                                            'documentation available '
                                                            'at '
                                                            '{DUOs_to_url(DUO_term)}'},
 'AccessPolicies:LeastOneAttributesSpecified4': {'entity': 'COLLECTION',
                                                 'fields': ['collaboration_commercial',
                                                            'collaboration_non_for_profit',
                                                            'data_use'],
                                                 'severity': 'ERROR',
                                                 'summary': 'At least one of '
                                                            '{attributes} specified on '
                                                            'biobank level and not '
                                                            'overridden on collection '
                                                            'but conflicting '
                                                            "'{DUO_term}' is specified "
                                                            'in data_use attribute. '
                                                            'DUO documentation '
                                                            'available at '
                                                            '{DUOs_to_url(DUO_term)}'},
 'AccessPolicies:NoneGenericResearchUsePurposes': {'entity': 'COLLECTION',
                                                   'fields': ['data_use'],
                                                   'severity': 'WARNING',
                                                   'summary': 'None of generic '
                                                              'research use purposes '
                                                              'provided '
                                                              '({DUO_terms_research}) '
                                                              'in data_use attribute - '
                                                              'suspect situation for a '
                                                              'biobank registered in '
                                                              'BBMRI-ERIC Directory, '
                                                              'which is for research '
                                                              'purposes. DUO '
                                                              'documentation available '
                                                              'at '
                                                              '{DUOs_to_url(DUO_terms_research)}'},
 'AccessPolicies:SampleAccessModeEnabledSample': {'entity': 'COLLECTION',
                                                  'fields': ['sample_access_description',
                                                             'sample_access_fee',
                                                             'sample_access_joint_project',
                                                             'sample_access_uri'],
                                                  'severity': 'ERROR',
                                                  'summary': 'No sample access mode '
                                                             'enabled and no sample '
                                                             'access policy '
                                                             '(description nor URI) '
                                                             'provided for collection'}}

class AccessPolicies(IPlugin):
	def check(self, dir, args):
		warnings = []
		log.info("Running access policy checks (AccessPolicies)")
		for biobank in dir.getBiobanks():
			if((not 'collaboration_commercial' in biobank or biobank['collaboration_commercial'] == False) and
					(not 'collaboration_non_for_profit' in biobank or biobank['collaboration_non_for_profit'] == False)):
				warnings.append(DataCheckWarning(make_check_id(self, "BiobankAvailableNeither"), "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "Biobank is available neither for commercial nor for non-for-profit collaboration"))

		for collection in dir.getCollections():

			#materials = Directory.getListOfEntityAttributeIds(collection, 'materials') EMX2 materials do not have id, then:
			materials = [ material for material in collection['materials'] ] if 'materials' in collection else []
			#collection_types = Directory.getListOfEntityAttributeIds(collection, 'type') # EMX2 types does not have ID, then:
			collection_types = Directory.getListOfEntityAttributes(collection, 'type')
			#DUOs = Directory.getListOfEntityAttributeIds(collection, 'data_use') # EMX2 types does not have ID, then:
			DUOs = Directory.getListOfEntityAttributes(collection, 'data_use')
			data_categories = []
			other_data = False
			for c in collection.get('data_categories', []):
				data_categories.append(c)
				if c not in ['BIOLOGICAL_SAMPLES', 'IMAGING_DATA']:
					other_data = True

			biobankId = dir.getCollectionBiobankId(collection['id'])
			biobank = dir.getBiobankById(biobankId)
			
			if 'BIOLOGICAL_SAMPLES' in data_categories:
				if((not 'sample_access_fee' in collection or collection['sample_access_fee'] == False) and 
						(not 'sample_access_joint_project' in collection or collection['sample_access_joint_project'] == False) and 
						(not 'sample_access_description' in collection or collection['sample_access_description'] == False) and 
						(not 'sample_access_uri' in collection or re.search('^\s*$', collection['sample_access_uri']))):
					warnings.append(DataCheckWarning(make_check_id(self, "SampleAccessModeEnabledSample"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "No sample access mode enabled and no sample access policy (description nor URI) provided for collection"))

			if other_data:
				if((not 'data_access_fee' in collection or collection['data_access_fee'] == False) and 
						(not 'data_access_joint_project' in collection or collection['data_access_joint_project'] == False) and 
						(not 'data_access_description' in collection or collection['data_access_description'] == False) and 
						(not 'data_access_uri' in collection or re.search('^\s*$', collection['data_access_uri']))):
					warnings.append(DataCheckWarning(make_check_id(self, "DataAccessModeEnabledDataAccess"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "No data access mode enabled and no data access policy (description nor URI) provided for collection"))

			if 'IMAGING_DATA' in data_categories:
				if((not 'image_access_fee' in collection or collection['image_access_fee'] == False) and 
						(not 'image_joint_project' in collection or collection['image_joint_project'] == False) and 
						(not 'image_access_description' in collection or collection['image_access_description'] == False) and 
						(not 'image_access_uri' in collection or re.search('^\s*$', collection['image_access_uri']))):
					warnings.append(DataCheckWarning(make_check_id(self, "ImagingAccessModeEnabledImaging"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "No imaging access mode enabled and no imaging access policy (description nor URI) provided for a collection which contains imaging data"))

			# DUO specific checks
							
			if not DUOs:
				warnings.append(DataCheckWarning(make_check_id(self, "DataUseOntologyDuoTermProvided"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "No Data Use Ontology (DUO) term provided in data_use attribute"))

			# aux routine to translate DUO codes to URLs
			def DUOs_to_url(DUO_list):
				if not isinstance(DUO_list, list):
					DUO_list = [ DUO_list ]
				replacements = [
						(r':', '_'),
						(r'^', 'http://purl.obolibrary.org/obo/'),
						]
				DUO_urls = DUO_list
				for s, t in replacements:
					DUO_urls = [re.sub(s, t, i) for i in DUO_urls]
				return " ".join(DUO_urls)

			# Generic checks on allowing research
			DUO_terms_research = ['DUO:0000007', 'DUO:0000006', 'DUO:0000042']
			if  not any(x in DUOs for x in DUO_terms_research):
				warnings.append(DataCheckWarning(make_check_id(self, "NoneGenericResearchUsePurposes"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"None of generic research use purposes provided ({DUO_terms_research}) in data_use attribute - suspect situation for a biobank registered in BBMRI-ERIC Directory, which is for research purposes. DUO documentation available at {DUOs_to_url(DUO_terms_research)}"))

			# description of data reuse policy based on BBMRI-ERIC Access Policy
			DUO_term_data_return = 'DUO:0000029'
			if  not DUO_term_data_return in DUOs:
				warnings.append(DataCheckWarning(make_check_id(self, "DataReturnRequiredDuoTermData"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Data return is not required (missing {DUO_term_data_return}) in data_use attribute - it is recommended for biobanks to support it based on BBMRI-ERIC Access policy (but not required). DUO documentation available at {DUOs_to_url(DUO_term_data_return)}"))

			# checks on different modes of collaboration - this is still a bit messy as DUO does not fit perfectly to our needs
			DUO_term_joint_project = 'DUO:0000020'
			if any((x in collection and collection[x] == True) for x in ['sample_access_joint_project', 'data_access_joint_project', 'image_joint_projects']) and DUO_term_joint_project not in DUOs:
				warnings.append(DataCheckWarning(make_check_id(self, "JointProjectsSampleDataImage"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, f"Joint projects for sample/data/image access specified and {DUO_term_joint_project} is not specified in data_use attribute. DUO documentation available at {DUOs_to_url(DUO_term_joint_project)}"))

			# DUO term DUO:0000018 seems not only to allow non-for-profit collaboration, but also forbids commercial collaboration
			for attributes,negative_attributes,DUO_term in [(['collaboration_non_for_profit'], ['collaboration_commercial'], 'DUO:0000018')]:
				if any((x in collection and collection[x] == True) for x in attributes) and not (any((x in collection and collection[x] == True) for x in negative_attributes) or any((x not in collection and x in biobank and biobank[x] == True) for x in negative_attributes)) and DUO_term not in DUOs:
					warnings.append(DataCheckWarning(make_check_id(self, "LeastOneAttributesSpecified"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"At least one of {attributes} specified on collection level but '{DUO_term}' is not specified in data_use attribute (may be however intentional). DUO documentation available at {DUOs_to_url(DUO_term)}"))
				elif any((x not in collection and x in biobank and biobank[x] == True) for x in attributes) and not (any((x in collection and collection[x] == True) for x in negative_attributes) or any((x not in collection and x in biobank and biobank[x] == True) for x in negative_attributes)) and DUO_term not in DUOs:
					warnings.append(DataCheckWarning(make_check_id(self, "LeastOneAttributesSpecified2"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"At least one of {attributes} specified on biobank level and not overridden on collection but '{DUO_term}' is not specified in data_use attribute (may be however intentional). DUO documentation available at {DUOs_to_url(DUO_term)}"))

			for attributes,negative_DUO_term in [(['collaboration_commercial'], 'DUO:0000018')]:
				if any((x in collection and collection[x] == True) for x in attributes) and negative_DUO_term in DUOs:
					warnings.append(DataCheckWarning(make_check_id(self, "LeastOneAttributesSpecified3"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"At least one of {attributes} specified on collection level but conflicting '{DUO_term}' is specified in data_use attribute. DUO documentation available at {DUOs_to_url(DUO_term)}"))
				elif any((x not in collection and x in biobank and biobank[x] == True) for x in attributes) and negative_DUO_term in DUOs:
					warnings.append(DataCheckWarning(make_check_id(self, "LeastOneAttributesSpecified4"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"At least one of {attributes} specified on biobank level and not overridden on collection but conflicting '{DUO_term}' is specified in data_use attribute. DUO documentation available at {DUOs_to_url(DUO_term)}"))

			# DUO term DUO:0000007 is potentially relevant for DISEASE_SPECIFIC collections
			DUO_term_disease_specific = 'DUO:0000007'
			if 'DISEASE_SPECIFIC' in collection_types and DUO_term_disease_specific not in DUOs:
				warnings.append(DataCheckWarning(make_check_id(self, "CollectionDiseaseSpecificDuoTerm"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Collection is disease specific but '{DUO_term_disease_specific}' is not specified in data_use attribute (may be false-positive). DUO documentation available at {DUOs_to_url(DUO_term_disease_specific)}"))

			# DUO term DUO:0000021 (ethics approval needed) is usually needed for reuse of human biological material
			DUO_term_ethics_needed = 'DUO:0000021'
			if materials and DUO_term_ethics_needed not in DUOs:
				warnings.append(DataCheckWarning(make_check_id(self, "CollectionContainsBiological"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Collection contains biological material types '{materials}' but ethics approval needed '{DUO_term_ethics_needed}' is not specified in data_use attribute (may be false-positive). DUO documentation available at {DUOs_to_url(DUO_term_ethics_needed)}"))


		return warnings
