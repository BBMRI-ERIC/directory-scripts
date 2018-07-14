import re

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning

class CheckIDs(IPlugin):
	def check(self, dir):
		warnings = []

		for biobank in dir.getBiobanks():
			NN = dir.getBiobankNN(biobank['id'])
			if not re.search('^bbmri-eric:ID:' + NN + '_', biobank['id']):
				warning = DataCheckWarning("", NN, DataCheckWarningLevel.ERROR, "BiobankID is not compliant with the specification " + biobank['id'] + ' (should start with "bbmri-eric:ID:' + NN + '_' + '" prefix)')
				warnings.append(warning)
			if re.search('[^A-Za-z0-9:_-]', biobank['id']):
				warning = DataCheckWarning("", NN, DataCheckWarningLevel.ERROR, "BiobankID contains illegal characters " + biobank['id'] + ' (should be "A-Za-z0-9:_-")')
				warnings.append(warning)

		for collection in dir.getCollections():
			NN = dir.getCollectionNN(collection['id'])
			if not re.search('^bbmri-eric:ID:' + NN + '_', collection['id']):
				warning = DataCheckWarning("", NN, DataCheckWarningLevel.ERROR, "CollectionID is not compliant with the specification " + collection['id'] + ' (should start with "bbmri-eric:ID:' + NN + '_' + '" prefix)')
				warnings.append(warning)
			if re.search('[^A-Za-z0-9:_-]', collection['id']):
				warning = DataCheckWarning("", NN, DataCheckWarningLevel.ERROR, "CollectionID contains illegal characters " + collection['id'] + ' (should be "A-Za-z0-9:_-")')
				warnings.append(warning)
			biobankID = collection['biobank']['id']
			if not re.search('^'+biobankID+':collection:', collection['id']):
				warning = DataCheckWarning("", NN, DataCheckWarningLevel.WARNING, "CollectionID does not contain expected biobank prefix " + collection['id'] + ' (should start with ' + '^'+biobankID+':collection:' + ')')
				warnings.append(warning)

		for contact in dir.getContacts():
			NN = dir.getContactNN(contact['id'])
			if not re.search('^bbmri-eric:contactID:' + NN + '_', contact['id']):
				warning = DataCheckWarning("", NN, DataCheckWarningLevel.ERROR, "ContactID is not compliant with the specification " + contact['id'] + ' (should start with "bbmri-eric:contactID:' + NN + '_' + '" prefix)')
				warnings.append(warning)
			if re.search('[^A-Za-z0-9:_-]', contact['id']):
				warning = DataCheckWarning("", NN, DataCheckWarningLevel.ERROR, "ContactID contains illegal characters " + contact['id'] + ' (should be "A-Za-z0-9:_-")')
				warnings.append(warning)

		for network in dir.getNetworks():
			NN = dir.getNetworkNN(network['id'])
			if not re.search('^bbmri-eric:networkID:' + NN + '_', contact['id']):
				warning = DataCheckWarning("", NN, DataCheckWarningLevel.ERROR, "NetworkID is not compliant with the specification " + network['id'] + ' (should start with "bbmri-eric:networkID:' + NN + '_' + '" prefix)')
				warnings.append(warning)
			if re.search('[^A-Za-z0-9:_-]', network['id']):
				warning = DataCheckWarning("", NN, DataCheckWarningLevel.ERROR, "NetworkID contains illegal characters " + network['id'] + ' (should be "A-Za-z0-9:_-")')
				warnings.append(warning)

		return warnings
