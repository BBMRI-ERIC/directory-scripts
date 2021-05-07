# vim:ts=8:sw=8:tw=0:noet

import re
import urllib.request
import logging as log

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning,DataCheckEntityType

class AccessPolicies(IPlugin):
	def check(self, dir, args):
		warnings = []
		log.info("Running access policy checks (AccessPolicies)")
		for biobank in dir.getBiobanks():
			if((not 'collaboration_commercial' in biobank or biobank['collaboration_commercial'] == False) and
					(not 'collaboration_non_for_profit' in biobank or biobank['collaboration_non_for_profit'] == False)):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.INFO, biobank['id'], DataCheckEntityType.BIOBANK, "Biobank is available neither for commercial nor for non-for-profit collaboration"))

		for collection in dir.getCollections():

			data_categories = []
			materials = []
			collection_types = []
			other_data = False
			DUOs = []
			if 'data_categories' in collection:
				for c in collection['data_categories']:
					data_categories.append(c['id'])
					if ('BIOLOGICAL_SAMPLES' != c['id'] and 'IMAGING_DATA' != c['id']):
						other_data = True
			if 'materials' in collection:
				for c in collection['materials']:
					materials.append(c['id'])
			if 'type' in collection:
				for t in collection['type']:
					collection_types.append(t['id'])
			if 'data_use' in collection:
				for t in collection['data_use']:
					DUOs.append(t['id'])

			biobankId = dir.getCollectionBiobank(collection['id'])
			biobank = dir.getBiobankById(biobankId)
			
			if 'BIOLOGICAL_SAMPLES' in data_categories:
				if((not 'sample_access_fee' in collection or collection['sample_access_fee'] == False) and 
						(not 'sample_access_joint_project' in collection or collection['sample_access_joint_project'] == False) and 
						(not 'sample_access_description' in collection or collection['sample_access_description'] == False) and 
						(not 'sample_access_uri' in collection or re.search('^\s*$', collection['sample_access_uri']))):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "No sample access mode enabled and no sample access policy (description nor URI) provided for collection"))

			if other_data:
				if((not 'data_access_fee' in collection or collection['data_access_fee'] == False) and 
						(not 'data_access_joint_project' in collection or collection['data_access_joint_project'] == False) and 
						(not 'data_access_description' in collection or collection['data_access_description'] == False) and 
						(not 'data_access_uri' in collection or re.search('^\s*$', collection['data_access_uri']))):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "No data access mode enabled and no data access policy (description nor URI) provided for collection"))

			if 'IMAGING_DATA' in data_categories:
				if((not 'image_access_fee' in collection or collection['image_access_fee'] == False) and 
						(not 'image_joint_project' in collection or collection['image_joint_project'] == False) and 
						(not 'image_access_description' in collection or collection['image_access_description'] == False) and 
						(not 'image_access_uri' in collection or re.search('^\s*$', collection['image_access_uri']))):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "No imaging access mode enabled and no imaging access policy (description nor URI) provided for a collection which contains imaging data"))

			# DUO specific checks
							
			if not DUOs:
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, "No Data Use Ontology (DUO) term provided in data_use attribute"))

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
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, f"None of generic research use purposes provided ({DUO_terms_research}) in data_use attribute - suspect situation for a biobank registered in BBMRI-ERIC Directory, which is for research purposes. DUO documentation available at {DUOs_to_url(DUO_terms_research)}"))

			# description of data reuse policy based on BBMRI-ERIC Access Policy
			DUO_term_data_return = 'DUO:0000029'
			if  not DUO_term_data_return in DUOs:
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, f"Data return is not required (missing {DUO_term_data_return}) in data_use attribute - it is recommended for biobanks to support it based on BBMRI-ERIC Access policy (but not required). DUO documentation available at {DUOs_to_url(DUO_term_data_return)}"))

			# checks on different modes of collaboration - this is still a bit messy as DUO does not fit perfectly to our needs
			DUO_term_joint_project = 'DUO:0000020'
			if any((x in collection and collection[x] == True) for x in ['sample_access_joint_project', 'data_access_joint_project', 'image_joint_projects']) and DUO_term_joint_project not in DUOs:
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, f"Joint projects for sample/data/image access specified and {DUO_term_joint_project} is not specified in data_use attribute. DUO documentation available at {DUOs_to_url(DUO_term_joint_project)}"))

			# DUO term DUO:0000018 seems not only to allow non-for-profit collaboration, but also forbids commercial collaboration
			for attributes,negative_attributes,DUO_term in [(['collaboration_non_for_profit'], ['collaboration_commercial'], 'DUO:0000018')]:
				if any((x in collection and collection[x] == True) for x in attributes) and not (any((x in collection and collection[x] == True) for x in negative_attributes) or any((x not in collection and x in biobank and biobank[x] == True) for x in negative_attributes)) and DUO_term not in DUOs:
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, f"At least one of {attributes} specified on collection level but '{DUO_term}' is not specified in data_use attribute (may be however intentional). DUO documentation available at {DUOs_to_url(DUO_term)}"))
				elif any((x not in collection and x in biobank and biobank[x] == True) for x in attributes) and not (any((x in collection and collection[x] == True) for x in negative_attributes) or any((x not in collection and x in biobank and biobank[x] == True) for x in negative_attributes)) and DUO_term not in DUOs:
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, f"At least one of {attributes} specified on biobank level and not overridden on collection but '{DUO_term}' is not specified in data_use attribute (may be however intentional). DUO documentation available at {DUOs_to_url(DUO_term)}"))

			for attributes,negative_DUO_term in [(['collaboration_commercial'], 'DUO:0000018')]:
				if any((x in collection and collection[x] == True) for x in attributes) and negative_DUO_term in DUOs:
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, f"At least one of {attributes} specified on collection level but conflicting '{DUO_term}' is specified in data_use attribute. DUO documentation available at {DUOs_to_url(DUO_term)}"))
				elif any((x not in collection and x in biobank and biobank[x] == True) for x in attributes) and negative_DUO_term in DUOs:
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, f"At least one of {attributes} specified on biobank level and not overridden on collection but conflicting '{DUO_term}' is specified in data_use attribute. DUO documentation available at {DUOs_to_url(DUO_term)}"))

			# DUO term DUO:0000007 is potentially relevant for DISEASE_SPECIFIC collections
			DUO_term_disease_specific = 'DUO:0000007'
			if 'DISEASE_SPECIFIC' in collection_types and DUO_term_disease_specific not in DUOs:
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, f"Collection is disease specific but '{DUO_term_disease_specific}' is not specified in data_use attribute (may be false-positive). DUO documentation available at {DUOs_to_url(DUO_term_disease_specific)}"))

			# DUO term DUO:0000021 (ethics approval needed) is usually needed for reuse of human biological material
			DUO_term_ethics_needed = 'DUO:0000021'
			if materials and DUO_term_ethics_needed not in DUOs:
				warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.INFO, collection['id'], DataCheckEntityType.COLLECTION, f"Collection contains biological material types '{materials}' but ethics approval needed '{DUO_term_ethics_needed}' is not specified in data_use attribute (may be false-positive). DUO documentation available at {DUOs_to_url(DUO_term_ethics_needed)}"))


		return warnings
