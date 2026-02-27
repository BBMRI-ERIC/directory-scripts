# vim:ts=8:sw=8:tw=0:noet

import re
import logging as log

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel, DataCheckWarning, DataCheckEntityType, make_check_id
from nncontacts import NNContacts

# Machine-readable check documentation for the manual generator and other tooling.
# Keep severity/entity/fields aligned with the emitted DataCheckWarning(...) calls.
CHECK_DOCS = {'VID:BBExtPrefix': {'entity': 'BIOBANK',
                                                 'fields': ['id'],
                                                 'severity': 'ERROR',
                                                 'summary': 'BiobankID is not '
                                                            'compliant with the '
                                                            'specification  (shall '
                                                            'start with '
                                                            '"bbmri-eric:ID:EXT_" '
                                                            'prefix for external '
                                                            'biobanks that have no '
                                                            'national node)'},
 'VID:BBExtFormat': {'entity': 'BIOBANK',
                                                  'fields': ['id'],
                                                  'severity': 'ERROR',
                                                  'summary': 'BiobankID is not '
                                                             'compliant with the '
                                                             'specification  (shall '
                                                             'start with '
                                                             '"bbmri-eric:ID:EXT_" '
                                                             'prefix for external '
                                                             'biobanks)'},
 'VID:BBPrefix': {'entity': 'BIOBANK',
                                                  'fields': ['id'],
                                                  'severity': 'ERROR',
                                                  'summary': 'BiobankID is not '
                                                             'compliant with the '
                                                             'specification  (shall '
                                                             'start with '
                                                             '"bbmri-eric:ID:_" '
                                                             'prefix)'},
 'VID:BBCharsInvalid': {'entity': 'BIOBANK',
                                          'fields': ['id'],
                                          'severity': 'ERROR',
                                          'summary': 'BiobankID contains illegal '
                                                     'characters  (shall be '
                                                     '"A-Za-z0-9:_-")'},
 'VID:BBEmptySeg': {'entity': 'BIOBANK',
                                                  'fields': ['id'],
                                                  'severity': 'ERROR',
                                                  'summary': 'BiobankID contains :: '
                                                             'indicating empty '
                                                             'component in ID '
                                                             'hierarchy'},
 'VID:CollExtPrefix': {'entity': 'COLLECTION',
                                       'fields': ['id'],
                                       'severity': 'ERROR',
                                       'summary': 'CollectionID is not compliant with '
                                                  'the specification  (shall start '
                                                  'with "bbmri-eric:ID:EXT_" prefix '
                                                  'for collections from external '
                                                  'biobanks that have no national '
                                                  'node)'},
 'VID:CollExtFormat': {'entity': 'COLLECTION',
                                        'fields': ['id'],
                                        'severity': 'ERROR',
                                        'summary': 'CollectionID is not compliant with '
                                                   'the specification  (shall start '
                                                   'with "bbmri-eric:ID:EXT_" prefix '
                                                   'for collections from external '
                                                   'biobanks)'},
 'VID:CollPrefix': {'entity': 'COLLECTION',
                                        'fields': ['id'],
                                        'severity': 'ERROR',
                                        'summary': 'CollectionID is not compliant with '
                                                   'the specification  (shall start '
                                                   'with "bbmri-eric:ID:_" prefix)'},
 'VID:CollCharsInvalid': {'entity': 'COLLECTION',
                                             'fields': ['id'],
                                             'severity': 'ERROR',
                                             'summary': 'CollectionID contains illegal '
                                                        'characters  (shall be '
                                                        '"A-Za-z0-9:_-")'},
 'VID:CollEmptySeg': {'entity': 'COLLECTION',
                                                'fields': ['id'],
                                                'severity': 'ERROR',
                                                'summary': 'CollectionID contains :: '
                                                           'indicating empty component '
                                                           'in ID hierarchy'},
 'VID:CollNoBBPrefix': {'entity': 'COLLECTION',
                                                 'fields': ['biobank', 'id'],
                                                 'severity': 'WARNING',
                                                 'summary': 'CollectionID does not '
                                                            'contain expected biobank '
                                                            'prefix  (should start '
                                                            'with :collection:)'},
 'VID:CtExtPrefix': {'entity': 'CONTACT',
                                                 'fields': ['id'],
                                                 'severity': 'ERROR',
                                                 'summary': 'ContactID is not '
                                                            'compliant with the '
                                                            'specification  (shall '
                                                            'start with '
                                                            '"bbmri-eric:ID:EXT_" '
                                                            'prefix for contacts for '
                                                            'external biobanks that '
                                                            'have no national node)'},
 'VID:CtExtFormat': {'entity': 'CONTACT',
                                                  'fields': ['id'],
                                                  'severity': 'ERROR',
                                                  'summary': 'ContactID is not '
                                                             'compliant with the '
                                                             'specification  (shall '
                                                             'start with '
                                                             '"bbmri-eric:contactID:EXT_" '
                                                             'prefix for contacts for '
                                                             'external biobanks)'},
 'VID:CtPrefix': {'entity': 'CONTACT',
                                                  'fields': ['id'],
                                                  'severity': 'ERROR',
                                                  'summary': 'ContactID is not '
                                                             'compliant with the '
                                                             'specification  (shall '
                                                             'start with '
                                                             '"bbmri-eric:contactID:_" '
                                                             'prefix)'},
 'VID:CtCharsInvalid': {'entity': 'CONTACT',
                                          'fields': ['id'],
                                          'severity': 'ERROR',
                                          'summary': 'ContactID contains illegal '
                                                     'characters  (shall be '
                                                     '"A-Za-z0-9:_-")'},
 'VID:CtEmptySeg': {'entity': 'CONTACT',
                                                  'fields': ['id'],
                                                  'severity': 'ERROR',
                                                  'summary': 'ContactID contains :: '
                                                             'indicating empty '
                                                             'component in ID '
                                                             'hierarchy'},
 'VID:NetExtPrefix': {'entity': 'NETWORK',
                                                 'fields': ['id'],
                                                 'severity': 'ERROR',
                                                 'summary': 'NetworkID is not '
                                                            'compliant with the '
                                                            'specification  (shall '
                                                            'start with '
                                                            '"bbmri-eric:ID:EXT_" '
                                                            'prefix for networks from '
                                                            'countries that have no '
                                                            'national node)'},
 'VID:NetPrefix': {'entity': 'NETWORK',
                                                  'fields': ['id'],
                                                  'severity': 'ERROR',
                                                  'summary': 'NetworkID is not '
                                                             'compliant with the '
                                                             'specification  (shall '
                                                             'start with '
                                                             '"bbmri-eric:networkID: '
                                                             'prefix)'},
 'VID:NetCharsInvalid': {'entity': 'NETWORK',
                                          'fields': ['id'],
                                          'severity': 'ERROR',
                                          'summary': 'NetworkID contains illegal '
                                                     'characters  (shall be '
                                                     '"A-Za-z0-9:_-")'},
 'VID:NetEmptySeg': {'entity': 'NETWORK',
                                                  'fields': ['id'],
                                                  'severity': 'ERROR',
                                                  'summary': 'NetworkID contains :: '
                                                             'indicating empty '
                                                             'component in ID '
                                                             'hierarchy'},
 'VID:NetCountry': {'entity': 'NETWORK',
                                               'fields': ['id'],
                                               'severity': 'WARNING',
                                               'summary': 'NetworkID has suspicious '
                                                          'country affiliation  '
                                                          '(should start with '
                                                          '"bbmri-eric:networkID:_" or '
                                                          '"bbmri-eric:networkID:EU_" '
                                                          'prefix)'}}

class ValidateIDs(IPlugin):
	CHECK_ID_PREFIX = "VID"
	def check(self, dir, args):
		warnings = []
		log.info("Running identifier validation checks (ValidateIDs)")

		for biobank in dir.getBiobanks():
			NN = dir.getBiobankNN(biobank['id'])
			if not NNContacts.is_member_node(NN):
				if not re.search('^bbmri-eric:ID:EXT_', biobank['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "BBExtPrefix"), "", NN, DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "BiobankID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:EXT_" prefix for external biobanks that have no national node)'))
			if re.search('^bbmri-eric:ID:EXT', biobank['id']):
				if not re.search('^bbmri-eric:ID:EXT_', biobank['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "BBExtFormat"), "", NN, DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "BiobankID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:EXT_" prefix for external biobanks)'))
			else:
				if not re.search('^bbmri-eric:ID:' + NN + '_', biobank['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "BBPrefix"), "", NN, DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "BiobankID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:' + NN + '_' + '" prefix)'))
			if re.search('[^A-Za-z0-9:_-]', biobank['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "BBCharsInvalid"), "", NN, DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "BiobankID contains illegal characters " + ' (shall be "A-Za-z0-9:_-")'))
			if re.search('::', biobank['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "BBEmptySeg"), "", NN, DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "BiobankID contains :: indicating empty component in ID hierarchy"))

		for collection in dir.getCollections():
			NN = dir.getCollectionNN(collection['id'])
			if not NNContacts.is_member_node(NN):
				if not re.search('^bbmri-eric:ID:EXT_', collection['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "CollExtPrefix"), "", NN, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "CollectionID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:EXT_" prefix for collections from external biobanks that have no national node)'))
			if re.search('^bbmri-eric:ID:EXT', collection['id']):
				if not re.search('^bbmri-eric:ID:EXT_', collection['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "CollExtFormat"), "", NN, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "CollectionID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:EXT_" prefix for collections from external biobanks)'))
			else:
				if not re.search('^bbmri-eric:ID:' + NN + '_', collection['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "CollPrefix"), "", NN, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "CollectionID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:' + NN + '_' + '" prefix)'))
			if re.search('[^A-Za-z0-9:_-]', collection['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "CollCharsInvalid"), "", NN, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "CollectionID contains illegal characters " + ' (shall be "A-Za-z0-9:_-")'))
			biobankID = collection['biobank']['id']
			if not re.search('^'+biobankID+':collection:', collection['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "CollNoBBPrefix"), "", NN, DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "CollectionID does not contain expected biobank prefix " + ' (should start with ' + biobankID +':collection:' + ')'))
			if re.search('::', collection['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "CollEmptySeg"), "", NN, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "CollectionID contains :: indicating empty component in ID hierarchy"))

		for contact in dir.getContacts(): # TODO: Add withdrawn
			NN = dir.getContactNN(contact['id'])
			if not NNContacts.is_member_node(NN):
				if not re.search('^bbmri-eric:ID:EXT_', contact['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "CtExtPrefix"), "", NN, DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, 'NA', "ContactID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:EXT_" prefix for contacts for external biobanks that have no national node)'))
			if re.search('^bbmri-eric:contactID:EXT', contact['id']):
				if not re.search('^bbmri-eric:contactID:EXT_', contact['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "CtExtFormat"), "", NN, DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, 'NA', "ContactID is not compliant with the specification " + ' (shall start with "bbmri-eric:contactID:EXT_" prefix for contacts for external biobanks)'))
			else:
				if not re.search('^bbmri-eric:contactID:' + NN + '_', contact['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "CtPrefix"), "", NN, DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, 'NA', "ContactID is not compliant with the specification " +  ' (shall start with "bbmri-eric:contactID:' + NN + '_' + '" prefix)'))
			if re.search('[^A-Za-z0-9:_-]', contact['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "CtCharsInvalid"), "", NN, DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, 'NA', "ContactID contains illegal characters " + ' (shall be "A-Za-z0-9:_-")'))
			if re.search('::', contact['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "CtEmptySeg"), "", NN, DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, 'NA', "ContactID contains :: indicating empty component in ID hierarchy"))

		for network in dir.getNetworks(): # TODO: Add withdrawn
			NN = dir.getNetworkNN(network['id'])
			if not NNContacts.is_member_node(NN):
				if not re.search('^bbmri-eric:ID:EXT_', network['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "NetExtPrefix"), "", NN, DataCheckWarningLevel.ERROR, network['id'], DataCheckEntityType.NETWORK, 'NA', "NetworkID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:EXT_" prefix for networks from countries that have no national node)'))
			if not re.search('^bbmri-eric:networkID:', network['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "NetPrefix"), "", NN, DataCheckWarningLevel.ERROR, network['id'], DataCheckEntityType.NETWORK, 'NA', "NetworkID is not compliant with the specification " + ' (shall start with "bbmri-eric:networkID: prefix)'))
			else:
				if not re.search('^bbmri-eric:networkID:' + NN + '_', network['id']) and not re.search('^bbmri-eric:networkID:EU_', network['id']) and not re.search('^bbmri-eric:networkID:EXT_', network['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "NetCountry"), "", NN, DataCheckWarningLevel.WARNING, network['id'], DataCheckEntityType.NETWORK, 'NA', "NetworkID has suspicious country affiliation " + ' (should start with "bbmri-eric:networkID:' + NN + '_' + '" or "bbmri-eric:networkID:EU_" prefix)'))
			if re.search('[^A-Za-z0-9:_-]', network['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "NetCharsInvalid"), "", NN, DataCheckWarningLevel.ERROR, network['id'], DataCheckEntityType.NETWORK, 'NA', "NetworkID contains illegal characters " + ' (shall be "A-Za-z0-9:_-")'))
			if re.search('::', network['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "NetEmptySeg"), "", NN, DataCheckWarningLevel.ERROR, network['id'], DataCheckEntityType.NETWORK, 'NA', "NetworkID contains :: indicating empty component in ID hierarchy"))

		return warnings
