# vim:ts=8:sw=8:tw=0:noet

import re
import logging as log

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning,DataCheckEntityType
from nncontacts import NNContacts

class ValidateIDs(IPlugin):
	def check(self, dir, args):
		warnings = []
		log.info("Running identifier validation checks (ValidateIDs)")

		for biobank in dir.getBiobanks():
			NN = dir.getBiobankNN(biobank['id'])
			if NN not in NNContacts.NNtoEmails:
				if not re.search('^bbmri-eric:ID:EXT_', biobank['id']):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, "BiobankID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:EXT_" prefix for external biobanks that have no national node)'))
			if re.search('^bbmri-eric:ID:EXT', biobank['id']):
				if not re.search('^bbmri-eric:ID:EXT_', biobank['id']):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, "BiobankID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:EXT_" prefix for external biobanks)'))
			else:
				if not re.search('^bbmri-eric:ID:' + NN + '_', biobank['id']):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, "BiobankID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:' + NN + '_' + '" prefix)'))
			if re.search('[^A-Za-z0-9:_-]', biobank['id']):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, "BiobankID contains illegal characters " + ' (shall be "A-Za-z0-9:_-")'))
			if re.search('::', biobank['id']):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, "BiobankID contains :: indicating empty component in ID hierarchy"))

		for collection in dir.getCollections():
			NN = dir.getCollectionNN(collection['id'])
			if NN not in NNContacts.NNtoEmails:
				if not re.search('^bbmri-eric:ID:EXT_', collection['id']):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "CollectionID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:EXT_" prefix for collections from external biobanks that have no national node)'))
			if re.search('^bbmri-eric:ID:EXT', collection['id']):
				if not re.search('^bbmri-eric:ID:EXT_', collection['id']):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "CollectionID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:EXT_" prefix for collections from external biobanks)'))
			else:
				if not re.search('^bbmri-eric:ID:' + NN + '_', collection['id']):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "CollectionID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:' + NN + '_' + '" prefix)'))
			if re.search('[^A-Za-z0-9:_-]', collection['id']):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "CollectionID contains illegal characters " + ' (shall be "A-Za-z0-9:_-")'))
			biobankID = collection['biobank']['id']
			if not re.search('^'+biobankID+':collection:', collection['id']):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, "CollectionID does not contain expected biobank prefix " + ' (should start with ' + biobankID +':collection:' + ')'))
			if re.search('::', collection['id']):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "CollectionID contains :: indicating empty component in ID hierarchy"))

		for contact in dir.getContacts():
			NN = dir.getContactNN(contact['id'])
			if NN not in NNContacts.NNtoEmails:
				if not re.search('^bbmri-eric:ID:EXT_', contact['id']):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, "ContactID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:EXT_" prefix for contacts for external biobanks that have no national node)'))
			if re.search('^bbmri-eric:contactID:EXT', contact['id']):
				if not re.search('^bbmri-eric:contactID:EXT_', contact['id']):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, "ContactID is not compliant with the specification " + ' (shall start with "bbmri-eric:contactID:EXT_" prefix for contacts for external biobanks)'))
			else:
				if not re.search('^bbmri-eric:contactID:' + NN + '_', contact['id']):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, "ContactID is not compliant with the specification " +  ' (shall start with "bbmri-eric:contactID:' + NN + '_' + '" prefix)'))
			if re.search('[^A-Za-z0-9:_-]', contact['id']):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, "ContactID contains illegal characters " + ' (shall be "A-Za-z0-9:_-")'))
			if re.search('::', contact['id']):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, "ContactID contains :: indicating empty component in ID hierarchy"))

		for network in dir.getNetworks():
			NN = dir.getNetworkNN(network['id'])
			if NN not in NNContacts.NNtoEmails:
				if not re.search('^bbmri-eric:ID:EXT_', network['id']):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, network['id'], DataCheckEntityType.NETWORK, "NetworkID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:EXT_" prefix for networks from countries that have no national node)'))
			if not re.search('^bbmri-eric:networkID:', network['id']):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, network['id'], DataCheckEntityType.NETWORK, "NetworkID is not compliant with the specification " + ' (shall start with "bbmri-eric:networkID: prefix)'))
			else:
				if not re.search('^bbmri-eric:networkID:' + NN + '_', network['id']) and not re.search('^bbmri-eric:networkID:EU_', network['id']) and not re.search('^bbmri-eric:networkID:EXT_', network['id']):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.WARNING, network['id'], DataCheckEntityType.NETWORK, "NetworkID has suspicious country affiliation " + ' (should start with "bbmri-eric:networkID:' + NN + '_' + '" or "bbmri-eric:networkID:EU_" prefix)'))
			if re.search('[^A-Za-z0-9:_-]', network['id']):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, network['id'], DataCheckEntityType.NETWORK, "NetworkID contains illegal characters " + ' (shall be "A-Za-z0-9:_-")'))
			if re.search('::', network['id']):
				warnings.append(DataCheckWarning(self.__class__.__name__, "", NN, DataCheckWarningLevel.ERROR, network['id'], DataCheckEntityType.NETWORK, "NetworkID contains :: indicating empty component in ID hierarchy"))

		return warnings
