import re
import logging as log

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning,DataCheckEntityType

class ValidateIDs(IPlugin):
	def check(self, dir, args):
		warnings = []
		log.info("Running identifier validation checks (ValidateIDs)")

		for biobank in dir.getBiobanks():
			NN = dir.getBiobankNN(biobank['id'])
			if not re.search('^bbmri-eric:ID:' + NN + '_', biobank['id']):
				warning = DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, "BiobankID is not compliant with the specification " + ' (should start with "bbmri-eric:ID:' + NN + '_' + '" prefix)')
				warnings.append(warning)
			if re.search('[^A-Za-z0-9:_-]', biobank['id']):
				warning = DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, "BiobankID contains illegal characters " + ' (should be "A-Za-z0-9:_-")')
				warnings.append(warning)
			if re.search('::', biobank['id']):
				warning = DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, "BiobankID contains :: indicating empty component in ID hierarchy")
				warnings.append(warning)

		for collection in dir.getCollections():
			NN = dir.getCollectionNN(collection['id'])
			if not re.search('^bbmri-eric:ID:' + NN + '_', collection['id']):
				warning = DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "CollectionID is not compliant with the specification " + ' (should start with "bbmri-eric:ID:' + NN + '_' + '" prefix)')
				warnings.append(warning)
			if re.search('[^A-Za-z0-9:_-]', collection['id']):
				warning = DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "CollectionID contains illegal characters " + ' (should be "A-Za-z0-9:_-")')
				warnings.append(warning)
			biobankID = collection['biobank']['id']
			if not re.search('^'+biobankID+':collection:', collection['id']):
				warning = DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, "CollectionID does not contain expected biobank prefix " + ' (should start with ' + biobankID +':collection:' + ')')
				warnings.append(warning)
			if re.search('::', collection['id']):
				warning = DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "CollectionID contains :: indicating empty component in ID hierarchy")
				warnings.append(warning)

		for contact in dir.getContacts():
			NN = dir.getContactNN(contact['id'])
			if not re.search('^bbmri-eric:contactID:' + NN + '_', contact['id']):
				warning = DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, "ContactID is not compliant with the specification " +  ' (should start with "bbmri-eric:contactID:' + NN + '_' + '" prefix)')
				warnings.append(warning)
			if re.search('[^A-Za-z0-9:_-]', contact['id']):
				warning = DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, "ContactID contains illegal characters " + ' (should be "A-Za-z0-9:_-")')
				warnings.append(warning)
			if re.search('::', contact['id']):
				warning = DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, "ContactID contains :: indicating empty component in ID hierarchy")
				warnings.append(warning)

		for network in dir.getNetworks():
			NN = dir.getNetworkNN(network['id'])
			if not re.search('^bbmri-eric:networkID:', network['id']):
				warning = DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, network['id'], DataCheckEntityType.NETWORK, "NetworkID is not compliant with the specification " + ' (should start with "bbmri-eric:networkID: prefix)')
				warnings.append(warning)
			else:
				if not re.search('^bbmri-eric:networkID:' + NN + '_', network['id']) and not re.search('^bbmri-eric:networkID:EU_', network['id']):
					warning = DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.WARNING, network['id'], DataCheckEntityType.NETWORK, "NetworkID has suspicious country affiliation " + ' (should start with "bbmri-eric:networkID:' + NN + '_' + '" or "bbmri-eric:networkID:EU_" prefix)')
					warnings.append(warning)
			if re.search('[^A-Za-z0-9:_-]', network['id']):
				warning = DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, network['id'], DataCheckEntityType.NETWORK, "NetworkID contains illegal characters " + ' (should be "A-Za-z0-9:_-")')
				warnings.append(warning)
			if re.search('::', network['id']):
				warning = DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, network['id'], DataCheckEntityType.NETWORK, "NetworkID contains :: indicating empty component in ID hierarchy")
				warnings.append(warning)

		return warnings
