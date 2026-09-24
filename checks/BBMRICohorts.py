# vim:ts=8:sw=8:tw=0:noet

"""Check metadata requirements for collections in BBMRI Cohorts networks."""

import re
import logging as log
import collections as py_collections

from yapsy.IPlugin import IPlugin
from customwarnings import DataCheckWarningLevel, DataCheckWarning, DataCheckEntityType, make_check_id

BBMRICohortsNetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts'
BBMRICohortsDNANetworkName = 'bbmri-eric:networkID:EU_BBMRI-ERIC:networks:BBMRI-Cohorts_DNA'
CHECK_ID_PREFIX = "BCO"

def checkCollabBB(self, dir, collection : dict, biobank : dict, warningsList):

	"""Append a collaboration warning when cohort collection and biobank flags both prohibit commercial use.

	Args:
	    dir: Loaded Directory view used for Node and collection-contact lookup.
	    collection: Cohort collection whose ``commercial_use`` flag is evaluated.
	    biobank: Owning biobank whose ``collaboration_commercial`` flag is evaluated.
	    warningsList: Mutable result list receiving at most one BCO:AccessConflict warning.

	Returns:
	    None. The supplied warning list is mutated only for a conflicting commercial-collaboration state.
	"""
	def checkAttribute (feature : str, entity : dict, state : bool):
		"""Compare one entity field with an expected boolean state.

		Args:
		    feature: Field name to inspect.
		    entity: Biobank or collection record containing the candidate field.
		    state: Boolean value that must match exactly.

		Returns:
		    ``True`` only when the field exists and equals the expected state.
		"""
		if feature in entity:
			if entity[feature] == state:
				return True
		return False

	def formatAttribute (feature : str, entity : dict):
		"""Format an entity field for a cohort warning message.

		Args:
		    feature: Field name whose current value is displayed.
		    entity: Biobank or collection record containing the field.

		Returns:
		    The string form of the field value, or ``not set`` when absent.
		"""
		if feature in entity:
			return f'{entity[feature]}'
		return f'not set'

	if checkAttribute('commercial_use', collection, True):
		return

	if checkAttribute('collaboration_commercial', biobank, True):
		# commercial collaboration must not be forbidden on the collection level
		if not checkAttribute('commercial_use', collection, False):
			return

	# If we got here, the previous checks failed
	warningsList.append(DataCheckWarning(make_check_id(self, "AccessConflict"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Collection and biobank are not available for commercial collaboration modes: collection[commercial_use] is {formatAttribute('commercial_use', collection)}, biobank[collaboration_commercial] is {formatAttribute('collaboration_commercial', biobank)}", "Check if this is true (that both are false): if so, remove the networks BBMRI Cohorts/BBMRI Cohorts DNA , otherwise correct the value of commercial availibility", dir.getCollectionContact(collection['id'])['email']))


# Machine-readable check documentation for the manual generator and other tooling.
# Keep severity/entity/fields aligned with the emitted DataCheckWarning(...) calls.
CHECK_DOCS = {'BCO:AccessConflict': {'entity': 'COLLECTION',
                                                 'fields': ['commercial_use',
                                                            'network'],
                                                 'fix': 'If the collection should '
                                                        'not support commercial '
                                                        'collaboration, remove the '
                                                        'BBMRI Cohorts / BBMRI '
                                                        'Cohorts DNA network flag '
                                                        'from the collection. '
                                                        'Otherwise correct the '
                                                        'commercial access settings, '
                                                        'including the parent '
                                                        'biobank field '
                                                        "'collaboration_commercial'.",
                                                 'severity': 'ERROR',
                                                 'summary': 'A collection is flagged '
                                                            'for BBMRI Cohorts or '
                                                            'BBMRI Cohorts DNA, but '
                                                            'commercial access is not '
                                                            'allowed on the '
                                                            'collection or on its '
                                                            'parent biobank.'},
 'BCO:FactsMissing': {'entity': 'COLLECTION',
                                              'fields': ['facts', 'network'],
                                              'fix': 'Prepare the facts table for the '
                                                     'collection and upload',
                                              'severity': 'ERROR',
                                              'summary': 'Collection in BBMRI cohorts '
                                                         '{BBMRICohortsList} but the '
                                                         'fact table is missing'},
 'BCO:BBNetFlag': {'entity': 'BIOBANK',
                                                 'fields': ['network'],
                                                 'fix': 'Remove the BBMRI Cohorts / '
                                                        'BBMRI Cohorts DNA network '
                                                        'flag from the biobank. '
                                                        'Apply these network flags '
                                                        'only to the specific '
                                                        'collections that belong in '
                                                        'the cohort programme.',
                                                 'severity': 'ERROR',
                                                 'summary': 'A biobank itself is '
                                                            'linked to a BBMRI '
                                                            'Cohorts network, but '
                                                            'these network flags must '
                                                            'be assigned only at '
                                                            'collection level.'}}

class BBMRICohorts(IPlugin):
	"""Validate BBMRI Cohorts network metadata and collaboration eligibility.

	The plugin checks cohort-network collections against commercial-use, access, longitudinal, sample, and donor metadata. Findings are returned as warnings and never applied directly.
	"""
	CHECK_ID_PREFIX = "BCO"

	def check(self, dir, args):
		"""Inspect BBMRI Cohorts network members and return cohort-specific consistency warnings.

		Args:
		    dir: Loaded Directory view providing network membership, parent biobanks, facts, and contacts.
		    args: Runner options accepted for the common plugin interface; this check does not read them.

		Returns:
		    Warnings for collections whose cohort metadata or collaboration flags conflict with network requirements.
		"""
		warnings = []
		log.info("Running content checks on BBMRI Cohorts (BBMRICohorts)")

		for collection in dir.getCollections():

			collsFactsSamples = 0
			collsFactsDonors = 0

			biobankId = dir.getCollectionBiobankId(collection['id'])
			biobank = dir.getBiobankById(biobankId)
			
			biobank_networks = []
			if 'network' in biobank:
				for n in biobank['network']:
					biobank_networks.append(n['id'])
			
			collection_networks = []
			if 'network' in collection:
				for n in collection['network']:
					collection_networks.append(n['id'])
			
			if BBMRICohortsNetworkName in collection_networks or BBMRICohortsDNANetworkName in collection_networks:
				#OoM = collection['order_of_magnitude']['id']  # EMX2 OoM does not have ID, then:
				if 'order_of_magnitude' not in collection:
					continue
				OoM = int(collection['order_of_magnitude'])
				
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

				# Check commercial use
				checkCollabBB(self, dir, collection, biobank, warnings)
				
				# Check presence of fact tables
				if 'facts' in collection.keys() and collection['facts'] != []: # TODO: if not, raise an error? # EMX2 change
					#if collection['facts'] != []:
					
					for fact in dir.getCollectionFacts(collection['id']):

						if 'number_of_samples' in fact:
							collsFactsSamples += fact['number_of_samples']
						if 'number_of_donors' in fact:
							collsFactsDonors += fact['number_of_donors']
					
					# TODO: should these check be generic and not just for BBMRI Cohorts?
					if collsFactsSamples > 0 or collsFactsDonors > 0:
						if BBMRICohortsNetworkName in collection_networks or BBMRICohortsDNANetworkName in collection_networks:
							log.info(f"Hooooray, we have found BBMRI Cohorts collection with the fact table populated: {collection['id']}")
						if BBMRICohortsNetworkName in biobank_networks or BBMRICohortsDNANetworkName in biobank_networks:
							log.info(f"Hooooray, we have found BBMRI Cohorts biobank with a collection with the fact table populated: {collection['id']}")

				else:
					if 'network' in collection and (BBMRICohortsNetworkName in collection_networks or BBMRICohortsDNANetworkName in collection_networks):
						BBMRICohortsList = set()
						if (BBMRICohortsNetworkName in collection_networks):
							BBMRICohortsList.add(BBMRICohortsNetworkName)
						if (BBMRICohortsDNANetworkName in collection_networks):
							BBMRICohortsList.add(BBMRICohortsDNANetworkName)
						warnings.append(DataCheckWarning(make_check_id(self, "FactsMissing"), "", dir.getCollectionNN(collection['id']), DataCheckWarningLevel.ERROR, collection['id'], DataCheckEntityType.COLLECTION, str(collection['withdrawn']), f"Collection in BBMRI cohorts {BBMRICohortsList} but the fact table is missing", "Prepare the facts table for the collection and upload", dir.getCollectionContact(collection['id'])['email']))
				
		for biobank in dir.getBiobanks():
			biobank_networks = []
			if 'network' in biobank:
				for n in biobank['network']:
					biobank_networks.append(n['id'])

			collections = dir.getGraphBiobankCollectionsFromBiobank(biobank['id'])
			collection_networks = set()  # set is sufficient since we only collect all the networks in which any of the collections of a biobank are participating
			for node_id in collections:
				collection = collections.nodes[node_id]['data']
				if 'network' in collection:
					for n in collection['network']:
						collection_networks.add(n['id'])

			for network in [BBMRICohortsNetworkName, BBMRICohortsDNANetworkName]:
				# if network in biobank_networks and not network in collection_networks:
					# warnings.append(DataCheckWarning(self.__class__.__name__, "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, f"Biobank in BBMRI-Cohorts network {network} but has no collections in the same network network."))
				 if network in biobank_networks:
					 warnings.append(DataCheckWarning(make_check_id(self, "BBNetFlag"), "", dir.getBiobankNN(biobank['id']), DataCheckWarningLevel.ERROR, biobank['id'], DataCheckEntityType.BIOBANK, str(biobank['withdrawn']), f"Biobanks are not expected to be part of BBMRI-Cohorts networks, only specific collections must be included. Biobank participates in BBMRI-Cohorts network: {network}.", "Remove BBMRI Cohorts/BBMRI Cohorts DNA network from the Biobank entry, check which collections shall be flagged with the networks BBMRI Cohorts / BBMRI Cohorts DNA and flag them", dir.getBiobankContact(biobank['id'])['email']))
		return warnings
