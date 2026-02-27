# vim:ts=8:sw=8:tw=0:noet

import re
import logging as log

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel, DataCheckWarning, DataCheckEntityType, make_check_id
from nncontacts import NNContacts

# Machine-readable check documentation for the manual generator and other tooling.
# Keep severity/entity/fields aligned with the emitted DataCheckWarning(...) calls.
CHECK_DOCS = {'ValidateIDs:BiobankidCompliantSpecification': {'entity': 'BIOBANK',
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
 'ValidateIDs:BiobankidCompliantSpecification2': {'entity': 'BIOBANK',
                                                  'fields': ['id'],
                                                  'severity': 'ERROR',
                                                  'summary': 'BiobankID is not '
                                                             'compliant with the '
                                                             'specification  (shall '
                                                             'start with '
                                                             '"bbmri-eric:ID:EXT_" '
                                                             'prefix for external '
                                                             'biobanks)'},
 'ValidateIDs:BiobankidCompliantSpecification3': {'entity': 'BIOBANK',
                                                  'fields': ['id'],
                                                  'severity': 'ERROR',
                                                  'summary': 'BiobankID is not '
                                                             'compliant with the '
                                                             'specification  (shall '
                                                             'start with '
                                                             '"bbmri-eric:ID:_" '
                                                             'prefix)'},
 'ValidateIDs:BiobankidContainsIllegal': {'entity': 'BIOBANK',
                                          'fields': ['id'],
                                          'severity': 'ERROR',
                                          'summary': 'BiobankID contains illegal '
                                                     'characters  (shall be '
                                                     '"A-Za-z0-9:_-")'},
 'ValidateIDs:BiobankidContainsIndicatingEmpty': {'entity': 'BIOBANK',
                                                  'fields': ['id'],
                                                  'severity': 'ERROR',
                                                  'summary': 'BiobankID contains :: '
                                                             'indicating empty '
                                                             'component in ID '
                                                             'hierarchy'},
 'ValidateIDs:CollectionidCompliant': {'entity': 'COLLECTION',
                                       'fields': ['id'],
                                       'severity': 'ERROR',
                                       'summary': 'CollectionID is not compliant with '
                                                  'the specification  (shall start '
                                                  'with "bbmri-eric:ID:EXT_" prefix '
                                                  'for collections from external '
                                                  'biobanks that have no national '
                                                  'node)'},
 'ValidateIDs:CollectionidCompliant2': {'entity': 'COLLECTION',
                                        'fields': ['id'],
                                        'severity': 'ERROR',
                                        'summary': 'CollectionID is not compliant with '
                                                   'the specification  (shall start '
                                                   'with "bbmri-eric:ID:EXT_" prefix '
                                                   'for collections from external '
                                                   'biobanks)'},
 'ValidateIDs:CollectionidCompliant3': {'entity': 'COLLECTION',
                                        'fields': ['id'],
                                        'severity': 'ERROR',
                                        'summary': 'CollectionID is not compliant with '
                                                   'the specification  (shall start '
                                                   'with "bbmri-eric:ID:_" prefix)'},
 'ValidateIDs:CollectionidContainsIllegal': {'entity': 'COLLECTION',
                                             'fields': ['id'],
                                             'severity': 'ERROR',
                                             'summary': 'CollectionID contains illegal '
                                                        'characters  (shall be '
                                                        '"A-Za-z0-9:_-")'},
 'ValidateIDs:CollectionidContainsIndicating': {'entity': 'COLLECTION',
                                                'fields': ['id'],
                                                'severity': 'ERROR',
                                                'summary': 'CollectionID contains :: '
                                                           'indicating empty component '
                                                           'in ID hierarchy'},
 'ValidateIDs:CollectionidDoesContainExpected': {'entity': 'COLLECTION',
                                                 'fields': ['biobank', 'id'],
                                                 'severity': 'WARNING',
                                                 'summary': 'CollectionID does not '
                                                            'contain expected biobank '
                                                            'prefix  (should start '
                                                            'with :collection:)'},
 'ValidateIDs:ContactidCompliantSpecification': {'entity': 'CONTACT',
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
 'ValidateIDs:ContactidCompliantSpecification2': {'entity': 'CONTACT',
                                                  'fields': ['id'],
                                                  'severity': 'ERROR',
                                                  'summary': 'ContactID is not '
                                                             'compliant with the '
                                                             'specification  (shall '
                                                             'start with '
                                                             '"bbmri-eric:contactID:EXT_" '
                                                             'prefix for contacts for '
                                                             'external biobanks)'},
 'ValidateIDs:ContactidCompliantSpecification3': {'entity': 'CONTACT',
                                                  'fields': ['id'],
                                                  'severity': 'ERROR',
                                                  'summary': 'ContactID is not '
                                                             'compliant with the '
                                                             'specification  (shall '
                                                             'start with '
                                                             '"bbmri-eric:contactID:_" '
                                                             'prefix)'},
 'ValidateIDs:ContactidContainsIllegal': {'entity': 'CONTACT',
                                          'fields': ['id'],
                                          'severity': 'ERROR',
                                          'summary': 'ContactID contains illegal '
                                                     'characters  (shall be '
                                                     '"A-Za-z0-9:_-")'},
 'ValidateIDs:ContactidContainsIndicatingEmpty': {'entity': 'CONTACT',
                                                  'fields': ['id'],
                                                  'severity': 'ERROR',
                                                  'summary': 'ContactID contains :: '
                                                             'indicating empty '
                                                             'component in ID '
                                                             'hierarchy'},
 'ValidateIDs:NetworkidCompliantSpecification': {'entity': 'NETWORK',
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
 'ValidateIDs:NetworkidCompliantSpecification2': {'entity': 'NETWORK',
                                                  'fields': ['id'],
                                                  'severity': 'ERROR',
                                                  'summary': 'NetworkID is not '
                                                             'compliant with the '
                                                             'specification  (shall '
                                                             'start with '
                                                             '"bbmri-eric:networkID: '
                                                             'prefix)'},
 'ValidateIDs:NetworkidContainsIllegal': {'entity': 'NETWORK',
                                          'fields': ['id'],
                                          'severity': 'ERROR',
                                          'summary': 'NetworkID contains illegal '
                                                     'characters  (shall be '
                                                     '"A-Za-z0-9:_-")'},
 'ValidateIDs:NetworkidContainsIndicatingEmpty': {'entity': 'NETWORK',
                                                  'fields': ['id'],
                                                  'severity': 'ERROR',
                                                  'summary': 'NetworkID contains :: '
                                                             'indicating empty '
                                                             'component in ID '
                                                             'hierarchy'},
 'ValidateIDs:NetworkidHasSuspiciousCountry': {'entity': 'NETWORK',
                                               'fields': ['id'],
                                               'severity': 'WARNING',
                                               'summary': 'NetworkID has suspicious '
                                                          'country affiliation  '
                                                          '(should start with '
                                                          '"bbmri-eric:networkID:_" or '
                                                          '"bbmri-eric:networkID:EU_" '
                                                          'prefix)'}}

class ValidateIDs(IPlugin):
	def check(self, dir, args):
		warnings = []
		log.info("Running identifier validation checks (ValidateIDs)")

		for biobank in dir.getBiobanks():
			NN = dir.getBiobankNN(biobank['id'])
			if not NNContacts.is_member_node(NN):
				if not re.search('^bbmri-eric:ID:EXT_', biobank['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "BiobankidCompliantSpecification"), "", NN, DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "BiobankID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:EXT_" prefix for external biobanks that have no national node)'))
			if re.search('^bbmri-eric:ID:EXT', biobank['id']):
				if not re.search('^bbmri-eric:ID:EXT_', biobank['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "BiobankidCompliantSpecification2"), "", NN, DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "BiobankID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:EXT_" prefix for external biobanks)'))
			else:
				if not re.search('^bbmri-eric:ID:' + NN + '_', biobank['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "BiobankidCompliantSpecification3"), "", NN, DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "BiobankID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:' + NN + '_' + '" prefix)'))
			if re.search('[^A-Za-z0-9:_-]', biobank['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "BiobankidContainsIllegal"), "", NN, DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "BiobankID contains illegal characters " + ' (shall be "A-Za-z0-9:_-")'))
			if re.search('::', biobank['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "BiobankidContainsIndicatingEmpty"), "", NN, DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "BiobankID contains :: indicating empty component in ID hierarchy"))

		for collection in dir.getCollections():
			NN = dir.getCollectionNN(collection['id'])
			if not NNContacts.is_member_node(NN):
				if not re.search('^bbmri-eric:ID:EXT_', collection['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "CollectionidCompliant"), "", NN, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "CollectionID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:EXT_" prefix for collections from external biobanks that have no national node)'))
			if re.search('^bbmri-eric:ID:EXT', collection['id']):
				if not re.search('^bbmri-eric:ID:EXT_', collection['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "CollectionidCompliant2"), "", NN, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "CollectionID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:EXT_" prefix for collections from external biobanks)'))
			else:
				if not re.search('^bbmri-eric:ID:' + NN + '_', collection['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "CollectionidCompliant3"), "", NN, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "CollectionID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:' + NN + '_' + '" prefix)'))
			if re.search('[^A-Za-z0-9:_-]', collection['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "CollectionidContainsIllegal"), "", NN, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "CollectionID contains illegal characters " + ' (shall be "A-Za-z0-9:_-")'))
			biobankID = collection['biobank']['id']
			if not re.search('^'+biobankID+':collection:', collection['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "CollectionidDoesContainExpected"), "", NN, DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "CollectionID does not contain expected biobank prefix " + ' (should start with ' + biobankID +':collection:' + ')'))
			if re.search('::', collection['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "CollectionidContainsIndicating"), "", NN, DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "CollectionID contains :: indicating empty component in ID hierarchy"))

		for contact in dir.getContacts(): # TODO: Add withdrawn
			NN = dir.getContactNN(contact['id'])
			if not NNContacts.is_member_node(NN):
				if not re.search('^bbmri-eric:ID:EXT_', contact['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "ContactidCompliantSpecification"), "", NN, DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, 'NA', "ContactID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:EXT_" prefix for contacts for external biobanks that have no national node)'))
			if re.search('^bbmri-eric:contactID:EXT', contact['id']):
				if not re.search('^bbmri-eric:contactID:EXT_', contact['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "ContactidCompliantSpecification2"), "", NN, DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, 'NA', "ContactID is not compliant with the specification " + ' (shall start with "bbmri-eric:contactID:EXT_" prefix for contacts for external biobanks)'))
			else:
				if not re.search('^bbmri-eric:contactID:' + NN + '_', contact['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "ContactidCompliantSpecification3"), "", NN, DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, 'NA', "ContactID is not compliant with the specification " +  ' (shall start with "bbmri-eric:contactID:' + NN + '_' + '" prefix)'))
			if re.search('[^A-Za-z0-9:_-]', contact['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "ContactidContainsIllegal"), "", NN, DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, 'NA', "ContactID contains illegal characters " + ' (shall be "A-Za-z0-9:_-")'))
			if re.search('::', contact['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "ContactidContainsIndicatingEmpty"), "", NN, DataCheckWarningLevel.ERROR, contact['id'], DataCheckEntityType.CONTACT, 'NA', "ContactID contains :: indicating empty component in ID hierarchy"))

		for network in dir.getNetworks(): # TODO: Add withdrawn
			NN = dir.getNetworkNN(network['id'])
			if not NNContacts.is_member_node(NN):
				if not re.search('^bbmri-eric:ID:EXT_', network['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "NetworkidCompliantSpecification"), "", NN, DataCheckWarningLevel.ERROR, network['id'], DataCheckEntityType.NETWORK, 'NA', "NetworkID is not compliant with the specification " + ' (shall start with "bbmri-eric:ID:EXT_" prefix for networks from countries that have no national node)'))
			if not re.search('^bbmri-eric:networkID:', network['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "NetworkidCompliantSpecification2"), "", NN, DataCheckWarningLevel.ERROR, network['id'], DataCheckEntityType.NETWORK, 'NA', "NetworkID is not compliant with the specification " + ' (shall start with "bbmri-eric:networkID: prefix)'))
			else:
				if not re.search('^bbmri-eric:networkID:' + NN + '_', network['id']) and not re.search('^bbmri-eric:networkID:EU_', network['id']) and not re.search('^bbmri-eric:networkID:EXT_', network['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "NetworkidHasSuspiciousCountry"), "", NN, DataCheckWarningLevel.WARNING, network['id'], DataCheckEntityType.NETWORK, 'NA', "NetworkID has suspicious country affiliation " + ' (should start with "bbmri-eric:networkID:' + NN + '_' + '" or "bbmri-eric:networkID:EU_" prefix)'))
			if re.search('[^A-Za-z0-9:_-]', network['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "NetworkidContainsIllegal"), "", NN, DataCheckWarningLevel.ERROR, network['id'], DataCheckEntityType.NETWORK, 'NA', "NetworkID contains illegal characters " + ' (shall be "A-Za-z0-9:_-")'))
			if re.search('::', network['id']):
				warnings.append(DataCheckWarning(make_check_id(self, "NetworkidContainsIndicatingEmpty"), "", NN, DataCheckWarningLevel.ERROR, network['id'], DataCheckEntityType.NETWORK, 'NA', "NetworkID contains :: indicating empty component in ID hierarchy"))

		return warnings
