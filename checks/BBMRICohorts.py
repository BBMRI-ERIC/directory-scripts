# vim:ts=8:sw=8:tw=0:noet

import re
import logging as log
import collections

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel,DataCheckWarning,DataCheckEntityType

BBMRICohortsNetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts'
BBMRICohortsDNANetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts_DNA'

class BBMRICohorts(IPlugin):
	def check(self, dir):
		warnings = []
		log.info("Running content checks on BBMRI Cohorts (BBMRICohorts)")

		collectionFacts = []
		collFactsDiseases = []
		for collection in dir.getCollections():
			biobankId = dir.getCollectionBiobankId(collection['id'])
			biobank = dir.getBiobankById(biobankId)
			biobank_capabilities = []
			if 'capabilities' in biobank:
				for c in biobank['capabilities']:
					biobank_capabilities.append(c['id'])
			biobank_covid = []
			if 'covid19biobank' in biobank:
				for c in biobank['covid19biobank']:
					biobank_covid.append(c['id'])
			biobank_networks = []
			if 'network' in biobank:
				for n in biobank['network']:
					biobank_networks.append(n['id'])

			OoM = collection['order_of_magnitude']['id']

			materials = []
			if 'materials' in collection:
				for m in collection['materials']:
					materials.append(m['id'])
			
			data_categories = []
			if 'data_categories' in collection:
				for c in collection['data_categories']:
					data_categories.append(c['id'])

			types = []
			if 'type' in collection:
				for t in collection['type']:
					types.append(t['id'])
                        
			diags = []
			diag_ranges = []
			covid_diag = False
			covid_control = False

			for d in collection['diagnosis_available']:
				if re.search('-', d['id']):
					diag_ranges.append(d['id'])
				else:
					diags.append(d['id'])

			# Check presence of fact tables
			if collection['facts'] != []:
				for fact in dir.getFacts():
					if fact['collection']['id'] == collection['id']:
						#collectionFacts.append(fact) # We collect here all the facts for a given collection (maybe not needed)
						if 'disease' in fact:
							collFactsDiseases.append(fact['disease']['id']) # Collect all diagnoses from facts

				# TODO: check that the fact table contains all the diagnoses described in the collection
				if collFactsDiseases!= [] and collections.Counter(collFactsDiseases) != collections.Counter(diags):
					warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, "Collection and facts table do not match"))
			
			# TODO: check that the fact table contains all the age ranges and biological sex that are described in the collection
			# TODO: check that the fact table contains all the material types that are described in the collection
			# TODO: check that the total numbers of samples and donors are filled out
			# TODO: check that the total numbers of samples is matching total number of samples in the fact table (donor's are not aggregable)
			# TODO: check that if the DNA network, the fact table contains liquid materials from which DNA can be extracted

		for biobank in dir.getBiobanks():
			biobank_capabilities = []
			if 'capabilities' in biobank:
				for c in biobank['capabilities']:
					biobank_capabilities.append(c['id'])
			biobank_covid = []
			if 'covid19biobank' in biobank:
				for c in biobank['covid19biobank']:
					biobank_covid.append(c['id'])
			biobank_networks = []
			if 'network' in biobank:
				for n in biobank['network']:
					biobank_networks.append(n['id'])

			# TODO: check that if the biobank-level membership in BBMRI-Cohorts network network is provided, there is at least one collection which has the membership in the network

		return warnings
