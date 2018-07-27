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
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.INFO, biobank['id'], DataCheckEntityType.BIOBANK, "Biobank is available neither for commercial nor for non-for-profit collaboration")
				warnings.append(warning)

		for collection in dir.getCollections():

			if((not 'data_access_fee' in collection or collection['data_access_fee'] == False) and 
					(not 'data_access_joint_project' in collection or collection['data_access_joint_project'] == False) and 
					(not 'data_access_description' in collection or collection['data_access_description'] == False) and 
					(not 'data_access_uri' in collection or re.search('^\s*$', collection['data_access_uri']))):
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "No data access mode enabled and no data access policy (description nor URI) provided for collection")
				warnings.append(warning)

			if((not 'sample_access_fee' in collection or collection['sample_access_fee'] == False) and 
					(not 'sample_access_joint_project' in collection or collection['sample_access_joint_project'] == False) and 
					(not 'sample_access_description' in collection or collection['sample_access_description'] == False) and 
					(not 'sample_access_uri' in collection or re.search('^\s*$', collection['sample_access_uri']))):
				warning = DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "No sample access mode enabled and no sample access policy (description nor URI) provided for collection")
				warnings.append(warning)

			data_categories = []
			if 'data_categories' in collection:
				for c in collection['data_categories']['items']:
					data_categories.append(c['id'])
			
			if 'IMAGING_DATA' in data_categories:
				if((not 'image_access_fee' in collection or collection['image_access_fee'] == False) and 
						(not 'image_joint_project' in collection or collection['image_joint_project'] == False) and 
						(not 'image_access_description' in collection or collection['image_access_description'] == False) and 
						(not 'image_access_uri' in collection or re.search('^\s*$', collection['image_access_uri']))):
					warning = DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "No imaging access mode enabled and no imaging access policy (description nor URI) provided for a collection which contains imaging data")
					warnings.append(warning)
							

		return warnings
