# vim:ts=8:sw=8:tw=0:noet

import re
import logging as log

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel, DataCheckWarning, DataCheckEntityType, make_check_id

covidNetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:COVID19'
covidProspectiveCollectionIdPattern =  '.*:COVID19PROSPECTIVE$'

# Machine-readable check documentation for the manual generator and other tooling.
# Keep severity/entity/fields aligned with the emitted DataCheckWarning(...) calls.
CHECK_DOCS = {'C19:BBNetMissing': {'entity': 'BIOBANK',
                                          'fields': [],
                                          'severity': 'ERROR',
                                          'summary': 'Biobank contains COVID '
                                                     'collection  but not marked as '
                                                     'part of '},
 'C19:BBCovidCapMissing': {'entity': 'BIOBANK',
                                           'fields': ['covid19'],
                                           'severity': 'ERROR',
                                           'summary': 'Biobank contains COVID '
                                                      'collection  but does not have '
                                                      '"covid19" attribute in '
                                                      '"capabilities" section of '
                                                      'attributes'},
 'C19:BBAttrNeedsNet': {'entity': 'BIOBANK',
                                  'fields': ['covid19'],
                                  'severity': 'ERROR',
                                  'summary': 'Biobank has covid19 among covid19biobank '
                                             'attributes but is not part of '},
 'C19:CapNeedsContent': {'entity': 'BIOBANK',
                                   'fields': ['covid19', 'id'],
                                   'severity': 'ERROR',
                                   'summary': 'Biobank has covid19 among capabilities '
                                              'but has no relevant services nor any '
                                              'collection of COVID-19 samples nor any '
                                              'collection of COVID-19 controls'},
 'C19:BBProsCollNoAttr': {'entity': 'BIOBANK',
                                        'fields': ['id'],
                                        'severity': 'ERROR',
                                        'summary': 'Biobank has prospective COVID-19 '
                                                   'collection defined but '
                                                   'ProspectiveCollections is not '
                                                   'among covid19biobank attributes'},
 'C19:BBProsAttrNoColl': {'entity': 'BIOBANK',
                                            'fields': ['id'],
                                            'severity': 'WARNING',
                                            'summary': 'Biobank has '
                                                       'ProspectiveCollections among '
                                                       'covid19biobank attributes but '
                                                       'has no prospective collection '
                                                       'defined (collection ID '
                                                       "matching '' regex pattern)"},
 'C19:BBNetNeedsAttr': {'entity': 'BIOBANK',
                                           'fields': ['covid19'],
                                           'severity': 'ERROR',
                                           'summary': 'Biobank is part of  but does '
                                                      'not have covid19 among '
                                                      'covid19biobank attributes'},
 'C19:AbilityNeedsPros': {'entity': 'COLLECTION',
                                          'fields': ['id', 'name'],
                                          'severity': 'ERROR',
                                          'summary': 'Collection having "ability to '
                                                     'collect" does not have '
                                                     'COVID19PROSPECTIVE label'},
 'C19:TypeMissing': {'entity': 'COLLECTION',
                                  'fields': [],
                                  'severity': 'ERROR',
                                  'summary': 'Collection type not provided'},
 'C19:CovidDiagMissing': {'entity': 'COLLECTION',
                                          'fields': ['id'],
                                          'severity': 'ERROR',
                                          'summary': 'COVID19 collection misses '
                                                     'COVID-19 diagnosis filled in'},
 'C19:ProsDataMissing': {'entity': 'COLLECTION',
                                        'fields': ['id'],
                                        'severity': 'ERROR',
                                        'summary': 'COVID19PROSPECTIVE collection '
                                                   'misses COVID-19 diagnosis or '
                                                   'COVID-19 controls filled in'},
 'C19:NeedsDisease': {'entity': 'COLLECTION',
                                          'fields': ['id'],
                                          'severity': 'ERROR',
                                          'summary': 'Existing COVID-19 collections '
                                                     'must have DISEASE_SPECIFIC as '
                                                     'one of its types'},
 'C19:ProsOoMNonZero': {'entity': 'COLLECTION',
                                     'fields': ['id', 'order_of_magnitude'],
                                     'severity': 'WARNING',
                                     'summary': 'Prospective collection type '
                                                'represents capability of setting up '
                                                'prospective collections - hence it '
                                                'should have zero order of magnitude'},
 'C19:AbilityOoMNonZero': {'entity': 'COLLECTION',
                                      'fields': ['id', 'name', 'order_of_magnitude'],
                                      'severity': 'WARNING',
                                      'summary': 'Prospective collection type '
                                                 'represents capability of setting up '
                                                 'prospective collections - hence it '
                                                 'should have zero order of magnitude'},
 'C19:ProsNeedsDisease': {'entity': 'COLLECTION',
                                         'fields': ['id'],
                                         'severity': 'ERROR',
                                         'summary': 'Prospective COVID-19 collections '
                                                    'must have DISEASE_SPECIFIC as one '
                                                    'of its types'},
 'C19:ProsNeedsType': {'entity': 'COLLECTION',
                                          'fields': ['id'],
                                          'severity': 'ERROR',
                                          'summary': 'Prospective COVID-19 collections '
                                                     'must have PROSPECTIVE_COLLECTION '
                                                     'as one of its types'},
 'C19:DiagRange': {'entity': 'COLLECTION',
                                           'fields': [],
                                           'severity': 'ERROR',
                                           'summary': 'It seems that diagnoses '
                                                      'contains range - this will '
                                                      'render the diagnosis search '
                                                      'ineffective for the given '
                                                      'collection. Violating diagnosis '
                                                      'term(s): '},
 'C19:BslFlagMissing': {'entity': 'COLLECTION',
                                       'fields': ['id'],
                                       'severity': 'WARNING',
                                       'summary': 'Suspect situation: collection '
                                                  'contains infectious material '
                                                  '(nasal/throat swabs, faeces) while '
                                                  'the parent biobank does not '
                                                  'indicate BSL2 nor BSL3 available'},
 'C19:MaterialsSuspect': {'entity': 'COLLECTION',
                                            'fields': ['id'],
                                            'severity': 'WARNING',
                                            'summary': 'Supect material types: '
                                                       'existing COVID-19 collection '
                                                       'does not have any of the '
                                                       'common material types: DNA, '
                                                       'PATHOGEN, '
                                                       'PERIPHERAL_BLOOD_CELLS, '
                                                       'PLASMA, RNA, SALIVA, SERUM, '
                                                       'WHOLE_BLOOD, FECES, '
                                                       'BUFFY_COAT, NASAL_SWAB, '
                                                       'THROAT_SWAB'}}

class COVID(IPlugin):
	CHECK_ID_PREFIX = "C19"
	def check(self, dir, args):
		warnings = []
		log.info("Running COVID content checks (COVID)")
		biobankHasCovidCollection = {}
		biobankHasCovidProspectiveCollection = {}
		biobankHasCovidControls = {}

		for collection in dir.getCollections():
			biobankId = dir.getCollectionBiobankId(collection['id'])
			biobank = dir.getBiobankById(biobankId)
			biobank_capabilities = []
			if 'capabilities' in biobank:
				for c in biobank['capabilities']:
					biobank_capabilities.append(c['id'])
			biobank_networks = []
			if 'network' in biobank:
				for n in biobank['network']:
					biobank_networks.append(n['id'])

			#OoM = collection['order_of_magnitude']['id']  # EMX2 OoM does not have ID, then:
			if 'order_of_magnitude' in collection:
				OoM = int(collection['order_of_magnitude'])
			else:
				OoM = None

			materials = []
			if 'materials' in collection:
				for m in collection['materials']:
					#materials.append(m['id']) # EMX2 materials does not have ID, then:
					materials.append(m)
			
			data_categories = []
			if 'data_categories' in collection:
				for c in collection['data_categories']:
					#data_categories.append(c['id']) # EMX2 data_categories does not have ID, then:
					data_categories.append(c)

			types = []
			if 'type' in collection:
				for t in collection['type']:
					#types.append(t['id']) # EMX2 types does not have ID, then:
					types.append(t)
                        
			diags = []
			diag_ranges = []
			covid_diag = False
			covid_control = False

			# TODO: Raise a warning here if needed
			try:
				for d in collection['diagnosis_available']:
					#if re.search('-', d['id']): # EMX2 collection['diagnosis_available'] has name but not id (this applies to all times we call d in this loop)
					if re.search('-', d['name']):
							diag_ranges.append(d['name'])
					else:
							diags.append(d['name'])
			except KeyError:
					continue

			for d in diags+diag_ranges:
				# ICD-10
				if re.search('U07', d):
					covid_diag = True
				# ICD-10
				if re.search('Z03.818', d):
					covid_control = True
				# ICD-11
				if re.search('RA01', d):
					covid_diag = True
				# SNOMED CT
				if re.search('(840533007|840534001|840535000|840536004|840539006|840544004|840546002)', d):
					covid_diag = True

                        
			if covid_diag:
				biobankHasCovidCollection[biobank['id']] = True
			else:
				# just initialize the record if not yet set at all - otherwise don't touch!
				if not biobank['id'] in biobankHasCovidCollection:
					biobankHasCovidCollection[biobank['id']] = False

			if covid_control:
				biobankHasCovidControls[biobank['id']] = True
			else:
				# just initialize the record if not yet set at all - otherwise don't touch!
				if not biobank['id'] in biobankHasCovidControls:
					biobankHasCovidControls[biobank['id']] = False

			if (covid_diag or covid_control) and diag_ranges:
				warning = DataCheckWarning(make_check_id(self, "DiagRange"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "It seems that diagnoses contains range - this will render the diagnosis search ineffective for the given collection. Violating diagnosis term(s): " + '; '.join(diag_ranges))
				warnings.append(warning)

			if covid_diag or covid_control:
				if not covidNetworkName in biobank_networks:
					warnings.append(DataCheckWarning(make_check_id(self, "BBNetMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "Biobank contains COVID collection " + collection['id'] + ' but not marked as part of ' + covidNetworkName))
				if not 'covid19' in biobank_capabilities:
					warnings.append(DataCheckWarning(make_check_id(self, "BBCovidCapMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "Biobank contains COVID collection " + collection['id'] + ' but does not have "covid19" attribute in "capabilities" section of attributes'))


			if len(types) < 1:
				warnings.append(DataCheckWarning(make_check_id(self, "TypeMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Collection type not provided"))
                        
			if re.search(covidProspectiveCollectionIdPattern, collection['id']):
				biobankHasCovidProspectiveCollection[biobank['id']] = True
				if not 'DISEASE_SPECIFIC' in types:
					warnings.append(DataCheckWarning(make_check_id(self, "ProsNeedsDisease"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Prospective COVID-19 collections must have DISEASE_SPECIFIC as one of its types"))
				if not 'PROSPECTIVE_COLLECTION' in types:
					warnings.append(DataCheckWarning(make_check_id(self, "ProsNeedsType"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Prospective COVID-19 collections must have PROSPECTIVE_COLLECTION as one of its types"))
				if OoM and OoM > 0:
					warnings.append(DataCheckWarning(make_check_id(self, "ProsOoMNonZero"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Prospective collection type represents capability of setting up prospective collections - hence it should have zero order of magnitude"))
				if not covid_diag and not covid_control:
					warnings.append(DataCheckWarning(make_check_id(self, "ProsDataMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "COVID19PROSPECTIVE collection misses COVID-19 diagnosis or COVID-19 controls filled in"))

			if re.search('^Ability to collect', collection['name']) and (covid_diag or covid_control):
				if not re.search(covidProspectiveCollectionIdPattern, collection['id']):
					warnings.append(DataCheckWarning(make_check_id(self, "AbilityNeedsPros"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), 'Collection having "ability to collect" does not have COVID19PROSPECTIVE label'))
					# only report the following if it hasn't been reported above (hence only if the COVID19PROSPECTIVE does not match)
					if OoM and OoM > 0:
						warnings.append(DataCheckWarning(make_check_id(self, "AbilityOoMNonZero"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Prospective collection type represents capability of setting up prospective collections - hence it should have zero order of magnitude"))
			
			# also find other prospective collections containing COVID-19
			if not re.search(covidProspectiveCollectionIdPattern, collection['id']) and covid_diag and 'PROSPECTIVE_COLLECTION' in types:
				biobankHasCovidProspectiveCollection[biobank['id']] = True
				log.debug("Prospective COVID-19 collection found with non-standard identifier: %s (%s) in biobank %s (%s)" % (collection['id'], collection['name'], biobank['id'], biobank['name']))


			if re.search('.*:COVID19$', collection['id']):
				if not 'DISEASE_SPECIFIC' in types:
					warnings.append(DataCheckWarning(make_check_id(self, "NeedsDisease"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Existing COVID-19 collections must have DISEASE_SPECIFIC as one of its types"))
				if not 'DNA' in materials and not 'PATHOGEN' in materials and not 'PERIPHERAL_BLOOD_CELLS' in materials and not 'PLASMA' in materials and not 'RNA' in materials and not 'SALIVA' in materials and not 'SERUM' in materials and not 'WHOLE_BLOOD' in materials and not 'FECES' in materials and not 'BUFFY_COAT' in materials and not 'NASAL_SWAB' in materials and not 'THROAT_SWAB' in materials:
					warnings.append(DataCheckWarning(make_check_id(self, "MaterialsSuspect"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Supect material types: existing COVID-19 collection does not have any of the common material types: DNA, PATHOGEN, PERIPHERAL_BLOOD_CELLS, PLASMA, RNA, SALIVA, SERUM, WHOLE_BLOOD, FECES, BUFFY_COAT, NASAL_SWAB, THROAT_SWAB"))
				if 'NASAL_SWAB' in materials or 'THROAT_SWAB' in materials or 'FECES' in materials and not ('BSL2' in biobank_covid or 'BSL3' in biobank_covid):
					warnings.append(DataCheckWarning(make_check_id(self, "BslFlagMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.WARNING, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "Suspect situation: collection contains infectious material (nasal/throat swabs, faeces) while the parent biobank does not indicate BSL2 nor BSL3 available"))
				if not covid_diag:
					warnings.append(DataCheckWarning(make_check_id(self, "CovidDiagMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), "COVID19 collection misses COVID-19 diagnosis filled in"))


		for biobank in dir.getBiobanks():
			biobank_covid = []
			biobank_networks = []
			if 'network' in biobank:
				for n in biobank['network']:
					biobank_networks.append(n['id'])

			if covidNetworkName in biobank_networks and not 'covid19' in biobank_capabilities:
				warnings.append(DataCheckWarning(make_check_id(self, "BBNetNeedsAttr"), "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "Biobank is part of " + covidNetworkName + " but does not have covid19 among covid19biobank attributes"))
			if 'covid19' in biobank_capabilities and not covidNetworkName in biobank_networks:
				warnings.append(DataCheckWarning(make_check_id(self, "BBAttrNeedsNet"), "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "Biobank has covid19 among covid19biobank attributes but is not part of " + covidNetworkName))

			# This is a simple check if the biobank has other services than just the attribute of being a covid19 biobank
			other_covid_services = False
			for s in biobank_covid:
				if s != 'covid19':
					other_covid_services = True

			if 'covid19' in biobank_capabilities and not (biobank['id'] in biobankHasCovidCollection or biobank['id'] in biobankHasCovidControls or other_covid_services):
				warnings.append(DataCheckWarning(make_check_id(self, "CapNeedsContent"), "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "Biobank has covid19 among capabilities but has no relevant services nor any collection of COVID-19 samples nor any collection of COVID-19 controls"))
	
			if 'ProspectiveCollections' in biobank_capabilities and not biobank['id'] in biobankHasCovidProspectiveCollection:
				warnings.append(DataCheckWarning(make_check_id(self, "BBProsAttrNoColl"), "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.WARNING, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "Biobank has ProspectiveCollections among covid19biobank attributes but has no prospective collection defined (collection ID matching '" + covidProspectiveCollectionIdPattern + "' regex pattern)"))

			if biobank['id'] in biobankHasCovidProspectiveCollection and not 'ProspectiveCollections' in biobank_covid:
				warnings.append(DataCheckWarning(make_check_id(self, "BBProsCollNoAttr"), "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), "Biobank has prospective COVID-19 collection defined but ProspectiveCollections is not among covid19biobank attributes"))

		return warnings
