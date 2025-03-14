# vim:ts=4:sw=4:tw=0:sts=4:et
import logging
import os.path
import time

import networkx as nx
from diskcache import Cache
from molgenis_emx2_pyclient import Client

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("BBMRI Directory")

class Directory:

    def __init__(self, schema="ERIC", purgeCaches=None, debug=False, pp=None, username=None, password=None, token: str = None):
        if purgeCaches is None:
            purgeCaches = list()
        self.__pp = pp
        self.__package = schema
        log.debug('Checking data in schema: ' + schema)

        cache_dir = 'data-check-cache/directory'
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        cache = Cache(cache_dir)
        if 'directory' in purgeCaches:
            cache.clear()

        self.__directoryURL = "https://directory-acc.molgenis.net/"
        log.info('Retrieving directory content from ' + self.__directoryURL)
        session = Client(self.__directoryURL, schema=schema)
        if username is not None and password is not None:
            log.info("Logging in to MOLGENIS with a user account.")
            log.debug('username: ' + username)
            log.debug('password: ' + password)
            session.signin(username, password)
        elif token is not None:
            session.set_token(token)
        else:
            log.warning("Continuing without authorization.")
        log.info('   ... retrieving biobanks')
        if 'biobanks' in cache:
            self.biobanks = cache['biobanks']
            log.info(f'   ... retrieved {len(self.biobanks)} biobanks from cache')
        else:
            start_time = time.perf_counter()
            self.biobanks = session.get_graphql(table="Biobanks")
            cache['biobanks'] = self.biobanks
            end_time = time.perf_counter()
            log.info(f'   ... retrieved {len(self.biobanks)} biobanks in ' + "%0.3f" % (end_time-start_time) + 's')
        log.info('   ... retrieving collections')
        if 'collections' in cache:
            self.collections = cache['collections']
            log.info(f'   ... retrieved {len(self.collections)} collections from cache')
        else:
            start_time = time.perf_counter()
            self.collections = session.get_graphql(table="Collections")
            cache['collections'] = self.collections
            end_time = time.perf_counter()
            if debug and self.__pp is not None:
                for c in self.collections:
                    pp.pprint(c)
            log.info(f'   ... retrieved {len(self.collections)} collections in ' + "%0.3f" % (end_time-start_time) + 's')
        log.info('   ... retrieving contacts')
        if 'contacts' in cache:
            self.contacts = cache['contacts']
            log.info(f'   ... retrieved {len(self.contacts)} contacts from cache')
        else:
            start_time = time.perf_counter()
            self.contacts = session.get_graphql(table="Persons")
            cache['contacts'] = self.contacts
            end_time = time.perf_counter()
            log.info(f'   ... retrieved {len(self.contacts)} contacts in ' + "%0.3f" % (end_time-start_time) + 's')

        log.info('   ... retrieving networks')
        if 'networks' in cache:
            self.networks = cache['networks']
            log.info(f'   ... retrieved {len(self.networks)} networks from cache')
        else:
            start_time = time.perf_counter()
            self.networks = session.get_graphql("Networks")
            cache['networks'] = self.networks
            end_time = time.perf_counter()
            log.info(f'   ... retrieved {len(self.networks)} networks in ' + "%0.3f" % (end_time-start_time) + 's')
        if 'facts' in cache:
            self.facts = cache['facts']
            log.info(f'   ... retrieved {len(self.facts)} networks from cache')
        else:
            start_time = time.perf_counter()
            self.facts = session.get_graphql("CollectionFacts")
            cache['facts'] = self.facts
            end_time = time.perf_counter()
            log.info(f'   ... retrieved {len(self.facts)} facts in ' + "%0.3f" % (end_time-start_time) + 's')
        log.info('   ... all entities retrieved')

        self.contactHashmap = {}

        log.info('Processing directory data')
        # Graph containing only biobanks and collections
        self.directoryGraph = nx.DiGraph()
        # DAG containing only biobanks and collections
        self.directoryCollectionsDAG = nx.DiGraph()
        # Weighted graph linking contacts to biobanks/collections/networks
        self.contactGraph = nx.DiGraph()
        # Graph linking networks to biobanks/collections
        self.networkGraph = nx.DiGraph()
        for c in self.contacts:
            log.debug(f'Processing contact {c["id"]} into the graph')
            if self.contactGraph.has_node(c['id']):
                raise Exception('DirectoryStructure', 'Conflicting ID found in contactGraph: ' + c['id'])
            # XXX temporary hack -- adding contactID prefix
            self.contactGraph.add_node(c['id'], data=c)
            self.contactHashmap[c['id']] = c
            log.debug(f'Contact {c["id"]} added into contactHashmap')
        for b in self.biobanks:
            log.debug(f'Processing biobank {b["id"]} into the graph')
            if self.directoryGraph.has_node(b['id']):
                raise Exception('DirectoryStructure', 'Conflicting ID found in directoryGraph: ' + b['id'])
            self.directoryGraph.add_node(b['id'], data=b)
            self.directoryCollectionsDAG.add_node(b['id'], data=b)
            if self.contactGraph.has_node(b['id']):
                raise Exception('DirectoryStructure', 'Conflicting ID found in contactGraph: ' + b['id'])
            self.contactGraph.add_node(b['id'], data=b)
            if self.networkGraph.has_node(b['id']):
                raise Exception('DirectoryStructure', 'Conflicting ID found in networkGraph: ' + b['id'])
            self.networkGraph.add_node(b['id'], data=b)
        for c in self.collections:
            log.debug(f'Processing collection {c["id"]} into the graph')
            if self.directoryGraph.has_node(c['id']):
                raise Exception('DirectoryStructure', 'Conflicting ID found: ' + c['id'])
            self.directoryGraph.add_node(c['id'], data=c)
            self.directoryCollectionsDAG.add_node(c['id'], data=c)
            if self.contactGraph.has_node(c['id']):
                raise Exception('DirectoryStructure', 'Conflicting ID found in contactGraph: ' + c['id'])
            self.contactGraph.add_node(c['id'], data=c)
            if self.networkGraph.has_node(c['id']):
                raise Exception('DirectoryStructure', 'Conflicting ID found in networkGraph: ' + c['id'])
            self.networkGraph.add_node(c['id'], data=c)
        for n in self.networks:
            log.debug(f'Processing network {n["id"]} into the graph')
            if self.contactGraph.has_node(n['id']):
                raise Exception('DirectoryStructure', 'Conflicting ID found in contactGraph: ' + n['id'])
            self.contactGraph.add_node(n['id'], data=n)
            if self.networkGraph.has_node(n['id']):
                raise Exception('DirectoryStructure', 'Conflicting ID found in networkGraph: ' + n['id'])
            self.networkGraph.add_node(n['id'], data=n)

        self.collectionFactMap = {}
        for f in self.facts:
            if not f['collection']['id'] in self.collectionFactMap:
                self.collectionFactMap[f['collection']['id']] = [ f ]
            else:
                self.collectionFactMap[f['collection']['id']].append(f)

        # check forward pointers from biobanks
        for b in self.biobanks:
            for c in b.get('collections', []):
                if not self.directoryGraph.has_node(c['id']):
                    raise Exception('DirectoryStructure', 'Biobank refers non-existent collection ID: ' + c['id'])
        # add biobank contact and network edges
        for b in self.biobanks:
            if 'contact' in b:
                self.contactGraph.add_edge(b['id'], b['contact']['id'])
            for c in b.get('contacts', []):
                for n in c.get('networks', []):
                    self.networkGraph.add_edge(b['id'], n['id'])

        # now we have all the collections created and checked duplicates, so we create edges
        for c in self.collections:
            if 'parent_collection' in c:
                # some child collection
                self.directoryGraph.add_edge(c['id'], c['parent_collection']['id'])
            else:
                # some of root collections of a biobank
                # we add both edges as we can't extract this information from the biobank level (it contains pointers to all the child collections)
                self.directoryGraph.add_edge(c['id'], c['biobank']['id'])
                self.directoryGraph.add_edge(c['biobank']['id'], c['id'])
                self.directoryCollectionsDAG.add_edge(c['biobank']['id'], c['id'])
            # some of root collections of a biobank
            for sb in c.get('sub_collections', []):
                self.directoryGraph.add_edge(c['id'], sb['id'])
                self.directoryCollectionsDAG.add_edge(c['id'], sb['id'])
            if 'contact' in c:
                self.contactGraph.add_edge(c['id'],c['contact']['id'])
            for n in c.get('networks', []):
                self.networkGraph.add_edge(c['id'], n['id'])

        # processing network edges
        for n in self.networks:
            for b in n.get('biobanks', []):
                self.networkGraph.add_edge(n['id'], b['id'])
            # TODO remove once the datamodel is fixed
            for c in n.get('contacts', []):
                self.contactGraph.add_edge(n['id'], c['id'])
            if 'contact' in n:
                self.contactGraph.add_edge(n['id'], n['contact']['id'])
            for c in n.get('collections', []):
                self.networkGraph.add_edge(n['id'], c['id'])

        # processing edges from contacts
        for c in self.contacts:
            for b in c.get('biobanks', []):
                self.contactGraph.add_edge(c['id'], b['id'])
            for coll in c.get('collections', []):
                self.contactGraph.add_edge(c['id'], coll['id'])
            for n in c.get('networks', []):
                self.contactGraph.add_edge(c['id'], n['id'])

        log.info('Checks of directory data as graphs')
        # now we check if all the edges in the graph are in both directions
        for e in self.directoryGraph.edges():
            if not self.directoryGraph.has_edge(e[1],e[0]):
                #raise Exception('DirectoryStructure', 'directoryGraph: Missing edge: ' + e[1] + ' to ' + e[0])
                log.warning('DirectoryStructure - directoryGraph: Missing edge: ' + e[1] + ' to ' + e[0])
                self.directoryGraph.add_edge(e[1],e[0])
        for e in self.contactGraph.edges():
            if not self.contactGraph.has_edge(e[1],e[0]):
                #raise Exception('DirectoryStructure', 'contactGraph: Missing edge: ' + e[1] + ' to ' + e[0])
                log.warning('DirectoryStructure - contactGraph: Missing edge: ' + e[1] + ' to ' + e[0])
                self.contactGraph.add_edge(e[1],e[0])
        for e in self.networkGraph.edges():
            if not self.networkGraph.has_edge(e[1],e[0]):
                #raise Exception('DirectoryStructure', 'networkGraph: Missing edge: ' + e[1] + ' to ' + e[0])
                log.warning('DirectoryStructure - networkGraph: Missing edge: ' + e[1] + ' to ' + e[0])
                self.networkGraph.add_edge(e[1],e[0])

        # now make graphs immutable
        nx.freeze(self.directoryGraph)
        nx.freeze(self.directoryCollectionsDAG)
        nx.freeze(self.contactGraph)
        nx.freeze(self.networkGraph)

        # we check that DAG is indeed DAG :-)
        if not nx.algorithms.dag.is_directed_acyclic_graph(self.directoryCollectionsDAG):
            raise Exception('DirectoryStructure', 'Collection DAG is not DAG')

        log.info('Directory structure initialized')
        self.__orphacodesmapper = None

    def setOrphaCodesMapper(self, o):
        self.__orphacodesmapper = o

    def issetOrphaCodesMapper(self) -> bool:
        if self.__orphacodesmapper is not None:
            return True
        else:
            return False

    def getOrphaCodesMapper(self):
        return self.__orphacodesmapper

    def getBiobanks(self):
        return self.biobanks

    def getBiobankById(self, biobankId : str):
        for b in self.biobanks:
            if b['id'] == biobankId:
                return b

    def getBiobanksCount(self):
        return len(self.biobanks)

    def getBiobankNN(self, biobankID : str):
        # TODO: handle IARC!
        #data = nx.get_node_attributes(self.directoryGraph, 'data')
        #if self.pp is not None:
            #pp.pprint(data)
        #biobank = data[biobankID]
        biobank = self.directoryGraph.nodes[biobankID]['data']
        return biobank['country']

    def getCollections(self):
        return self.collections

    def getCollectionById(self, collectionId : str):
        for c in self.collections:
            if c['id'] == collectionId:
                return c

    def getCollectionsCount(self):
        return len(self.collections)

    def getCollectionBiobankId(self, collectionID : str):
        collection = self.directoryGraph.nodes[collectionID]['data']
        return collection['biobank']['id']

    def getCollectionContact(self, collectionID : str):
        collection = self.directoryGraph.nodes[collectionID]['data']
        return self.contactHashmap[collection['contact']['id']]

    def isTopLevelCollection(self, collectionID : str):
        collection = self.directoryGraph.nodes[collectionID]['data']
        return not 'parent_collection' in collection

    def isCountableCollection(self, collectionID : str, metric : str):
        assert metric == 'number_of_donors' or metric == 'size' 
        # note that this is intentionally not implemented for OoM - since OoM is a required parameter and thus any child collection would be double-counted
        collection = self.directoryGraph.nodes[collectionID]['data']
        if not (metric in collection and isinstance(collection[metric], int)):
            return False
        else:
            if not 'parent_collection' in collection:
                return True
            else:
                parent = self.getCollectionById(collection['parent_collection']['id'])
                parent_dist = 1
                while parent is not None:
                    if metric in parent and isinstance(parent[metric], int):
                        log.debug(f'Collection {collectionID} is not countable as it has countable parent {parent["id"]} (distance {parent_dist}) for metric {metric}.')
                        return False
                    if 'parent_collection' in parent:
                        parent = self.getCollectionById(parent['parent_collection']['id'])
                        parent_dist += 1
                    else:
                        if parent_dist > 1:
                            log.debug(f'Detected collection {collectionID} deeper than 1 from {parent["id"]} (distance {parent_dist}) for metric {metric}.')
                        parent = None
                return True
                

    def getCollectionNN(self, collectionID):
        # TODO: handle IARC!
        return self.getBiobankNN(self.getCollectionBiobankId(collectionID))

    # return the whole subgraph including the biobank itself
    def getGraphBiobankCollectionsFromBiobank(self, biobankID : str):
        return self.directoryCollectionsDAG.subgraph(nx.algorithms.dag.descendants(self.directoryCollectionsDAG, biobankID).union({biobankID}))

    # return the whole subgraph including some collection
    def getGraphBiobankCollectionsFromCollection(self, collectionID : str):
        return self.directoryCollectionsDAG.subgraph(nx.algorithms.dag.ancestors(self.directoryCollectionsDAG, collectionID).union(nx.algorithms.dag.descendants(self.directoryCollectionsDAG, collectionID)).union({collectionID}))

    def getCollectionsDescendants(self, collectionID : str):
        return nx.algorithms.dag.descendants(self.directoryCollectionsDAG, collectionID)

    def getContacts(self):
        return self.contacts

    def getContact(self, contactID : str):
        return self.contactHashmap[contactID]

    def getContactNN(self, contactID : str):
        # TODO: handle IARC!
        #return self.contactHashmap[contactID]['country']['id'] # EMX2 change: Country only contains the ID now, so:
        return self.contactHashmap[contactID]['country']


    def getNetworks(self):
        return self.networks

    def getFacts(self):
        return self.facts

    def getCollectionFacts(self, collectionID : str):
        return self.collectionFactMap[collectionID]

    def getNetworkNN(self, networkID : str):
        # TODO: review handling of IARC/EU/global collections
        network = self.networkGraph.nodes[networkID]['data']
        NN = ""
        if 'country' in network:
            NN = network['country']['id']
        elif 'contact' in network:
            NN = self.getContactNN(network['contact']['id'])
        else:
            NN = "EU"
        return NN

    @staticmethod
    def getListOfEntityAttributeIds(entity, key : str):
        return [ element['id'] for element in entity[key] ] if key in entity else []

    @staticmethod
    def getListOfEntityAttributes(entity, key : str):
        return [ element for element in entity[key] ] if key in entity else []