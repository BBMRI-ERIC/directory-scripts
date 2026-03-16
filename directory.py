# vim:ts=4:sw=4:tw=0:sts=4:et
import copy
import logging
import os.path
import time
from typing import Any, Optional

import networkx as nx
import pandas as pd
from diskcache import Cache
from molgenis_emx2_pyclient import Client
from molgenis_emx2_pyclient.exceptions import NoSuchTableException
from nncontacts import NNContacts

#logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("BBMRI Directory")

class Directory:
    """Access, cache, and graph-model BBMRI Directory data for downstream checks."""

    def __init__(
        self,
        schema="ERIC",
        purgeCaches=None,
        debug=False,
        pp=None,
        username=None,
        password=None,
        token: str = None,
        directory_url: Optional[str] = None,
        include_withdrawn_entities: bool = False,
        only_withdrawn_entities: bool = False,
    ):
        """Initialize a directory snapshot and build query/helper graphs.

        Args:
            schema: Directory schema (staging area) name.
            purgeCaches: Cache names to purge before loading data.
            debug: Enable additional debug output.
            pp: Pretty-printer object used in debug mode.
            username: Username for session authentication.
            password: Password for session authentication.
            token: Access token for token-based authentication.
            directory_url: Base URL of the Directory instance to query.
            include_withdrawn_entities: When False, public biobank/collection
                accessors exclude entities that are withdrawn explicitly or
                inherit withdrawal from a parent biobank/collection.
            only_withdrawn_entities: When True, public biobank/collection
                accessors return only withdrawn entities. Implies
                include_withdrawn_entities.
        """
        if purgeCaches is None:
            purgeCaches = list()
        self.__pp = pp
        self.__package = schema
        self.only_withdrawn_entities = only_withdrawn_entities
        self.include_withdrawn_entities = include_withdrawn_entities or only_withdrawn_entities
        self._ai_checksum_snapshot = {}
        log.debug('Checking data in schema: ' + schema)

        schema_cache_suffix = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(schema))
        cache_dir = f'data-check-cache/directory-{schema_cache_suffix}'
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        cache = Cache(cache_dir)
        if 'directory' in purgeCaches:
            cache.clear()

        #self.__directoryURL = "https://directory-acc.molgenis.net/"
        self.__directoryURL = directory_url or "https://directory.bbmri-eric.eu"
        log.info('Retrieving directory content from ' + self.__directoryURL)
        client_kwargs = {}
        if token is not None:
            client_kwargs["token"] = token
        if self._has_complete_cached_snapshot(cache):
            self._load_cached_snapshot(cache, schema)
        else:
            try:
                with Client(self.__directoryURL, **client_kwargs) as session:
                    if username is not None and password is not None:
                        log.info("Logging in to MOLGENIS with a user account.")
                        log.debug('username: ' + username)
                        log.debug('password: ' + password)
                        session.signin(username, password)
                    elif token is None:
                        log.warning("Continuing without authorization.")
                    session.set_schema(schema)
                    self._load_live_snapshot(session, cache, schema, debug)
            except Exception as exc:
                if self._has_complete_cached_snapshot(cache):
                    log.warning(
                        "Unable to reach or refresh the live Directory for schema %s; reusing cached snapshot instead: %s",
                        schema,
                        exc,
                    )
                    self._load_cached_snapshot(cache, schema)
                else:
                    raise RuntimeError(
                        f"Unable to reach Directory schema {schema!r} and no complete cached snapshot is available."
                    ) from exc
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

        self.serviceHashmap = {}
        self.biobankServiceMap = {}
        for service in self.services:
            self.serviceHashmap[service['id']] = service
            biobank = service.get('biobank')
            if biobank and 'id' in biobank:
                self.biobankServiceMap.setdefault(biobank['id'], []).append(service)

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
        self._collection_withdrawn_cache = {}

    @staticmethod
    def _load_quality_table(session: Client, table_name: str, schema: str) -> pd.DataFrame:
        """Load an optional quality-info table or return an empty DataFrame when absent."""
        try:
            return session.get(table=table_name, as_df=True)
        except NoSuchTableException:
            log.info("Skipping optional quality table %s in schema %s.", table_name, schema)
            return pd.DataFrame()

    @staticmethod
    def _has_complete_cached_snapshot(cache: Cache) -> bool:
        """Return whether the cache contains the minimum full snapshot needed for offline reuse."""
        required_keys = ("biobanks", "collections", "contacts", "networks", "facts")
        return all(key in cache for key in required_keys)

    @staticmethod
    def _get_cached_dataframe(cache: Cache, key: str) -> pd.DataFrame:
        """Return a cached DataFrame value or an empty DataFrame when the cache key is absent."""
        if key in cache:
            cached_value = cache[key]
            if isinstance(cached_value, pd.DataFrame):
                return cached_value
        return pd.DataFrame()

    def _load_cached_snapshot(self, cache: Cache, schema: str) -> None:
        """Populate Directory tables from an existing cache snapshot without using the live API."""
        log.info("Using cached directory snapshot for schema %s.", schema)
        log.info('   ... retrieving biobanks')
        self.biobanks = cache['biobanks']
        log.info(f'   ... retrieved {len(self.biobanks)} biobanks from cache')
        log.info('   ... retrieving collections')
        self.qualBBtable = self._get_cached_dataframe(cache, 'quality_info_biobanks')
        if self.qualBBtable.empty and 'quality_info_biobanks' not in cache:
            log.info("Cached snapshot has no QualityInfoBiobanks table for schema %s.", schema)
        self.qualColltable = self._get_cached_dataframe(cache, 'quality_info_collections')
        if self.qualColltable.empty and 'quality_info_collections' not in cache:
            log.info("Cached snapshot has no QualityInfoCollections table for schema %s.", schema)
        self.collections = cache['collections']
        log.info(f'   ... retrieved {len(self.collections)} collections from cache')
        log.info('   ... retrieving contacts')
        self.contacts = cache['contacts']
        log.info(f'   ... retrieved {len(self.contacts)} contacts from cache')
        log.info('   ... retrieving networks')
        self.networks = cache['networks']
        log.info(f'   ... retrieved {len(self.networks)} networks from cache')
        self.facts = cache['facts']
        log.info(f'   ... retrieved {len(self.facts)} facts from cache')
        log.info('   ... retrieving services')
        self.services = cache['services'] if 'services' in cache else []
        if 'services' in cache:
            log.info(f'   ... retrieved {len(self.services)} services from cache')
        else:
            log.info('   ... cached snapshot has no services table; using empty list')

    def _load_live_snapshot(self, session: Client, cache: Cache, schema: str, debug: bool) -> None:
        """Populate Directory tables from the live API and cache the retrieved snapshot."""
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

        self.qualBBtable = self._load_quality_table(session, 'QualityInfoBiobanks', schema)
        cache['quality_info_biobanks'] = self.qualBBtable
        self.qualColltable = self._load_quality_table(session, 'QualityInfoCollections', schema)
        cache['quality_info_collections'] = self.qualColltable

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
                    self.__pp.pprint(c)
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
            log.info(f'   ... retrieved {len(self.facts)} facts from cache')
        else:
            start_time = time.perf_counter()
            self.facts = session.get_graphql("CollectionFacts")
            cache['facts'] = self.facts
            end_time = time.perf_counter()
            log.info(f'   ... retrieved {len(self.facts)} facts in ' + "%0.3f" % (end_time-start_time) + 's')
        log.info('   ... retrieving services')
        if 'services' in cache:
            self.services = cache['services']
            log.info(f'   ... retrieved {len(self.services)} services from cache')
        else:
            try:
                start_time = time.perf_counter()
                self.services = session.get_graphql("Services")
                cache['services'] = self.services
                end_time = time.perf_counter()
                log.info(f'   ... retrieved {len(self.services)} services in ' + "%0.3f" % (end_time-start_time) + 's')
            except Exception as exc:
                log.warning('Unable to retrieve services: %s', exc)
                self.services = []

    def prepare_ai_cache_checksum_state(self):
        """Capture pristine entities for AI-cache checksum validation.

        QC plugins may mutate in-memory Directory entities during a run. AI
        cache validation must therefore compare cached checksums against the
        original Directory snapshot, not the post-plugin mutated state.
        """
        if self._ai_checksum_snapshot:
            return
        self._ai_checksum_snapshot = {
            "BIOBANK": {
                biobank["id"]: copy.deepcopy(biobank) for biobank in self.biobanks
            },
            "COLLECTION": {
                collection["id"]: copy.deepcopy(collection)
                for collection in self.collections
            },
        }

    def get_ai_checksum_entity(self, entity_type: str, entity_id: str) -> Optional[dict[str, Any]]:
        """Return the pristine snapshot entity used for AI-cache checksums."""
        if not self._ai_checksum_snapshot:
            self.prepare_ai_cache_checksum_state()
        return self._ai_checksum_snapshot.get(entity_type, {}).get(entity_id)

    def setOrphaCodesMapper(self, o):
        """Attach an OrphaCodes mapper implementation."""
        self.__orphacodesmapper = o

    def issetOrphaCodesMapper(self) -> bool:
        """Return whether an OrphaCodes mapper is configured."""
        return self.__orphacodesmapper is not None

    def getOrphaCodesMapper(self):
        """Return the configured OrphaCodes mapper."""
        return self.__orphacodesmapper

    def getSchema(self) -> str:
        """Return the configured Directory schema/staging-area name."""
        return self.__package

    @staticmethod
    def _is_explicitly_withdrawn(entity: Optional[dict[str, Any]]) -> bool:
        """Return whether an entity is explicitly marked as withdrawn."""
        if not entity:
            return False
        return bool(entity.get("withdrawn"))

    def isBiobankWithdrawn(self, biobankID: str) -> bool:
        """Return whether a biobank is explicitly marked as withdrawn."""
        biobank = self.directoryGraph.nodes[biobankID]['data']
        return self._is_explicitly_withdrawn(biobank)

    def isCollectionWithdrawn(self, collectionID: str) -> bool:
        """Return whether a collection is withdrawn, including inherited state."""
        if collectionID in self._collection_withdrawn_cache:
            return self._collection_withdrawn_cache[collectionID]

        collection = self.directoryGraph.nodes[collectionID]['data']
        withdrawn = self._is_explicitly_withdrawn(collection)
        if not withdrawn:
            withdrawn = self.isBiobankWithdrawn(collection['biobank']['id'])
        if not withdrawn and 'parent_collection' in collection:
            withdrawn = self.isCollectionWithdrawn(collection['parent_collection']['id'])

        self._collection_withdrawn_cache[collectionID] = withdrawn
        return withdrawn

    def _matches_withdrawn_scope(self, is_withdrawn: bool) -> bool:
        """Return whether an entity matches the configured withdrawn scope."""
        if self.only_withdrawn_entities:
            return is_withdrawn
        if self.include_withdrawn_entities:
            return True
        return not is_withdrawn

    def getBiobanks(self):
        """Return all loaded biobanks."""
        return [
            biobank for biobank in self.biobanks
            if self._matches_withdrawn_scope(self.isBiobankWithdrawn(biobank['id']))
        ]
    
    def getQualBB(self):
        """Return the biobank quality-info table."""
        return self.qualBBtable
    
    def getQualColl(self):
        """Return the collection quality-info table."""
        return self.qualColltable

    def getBiobankById(self, biobankId: str, raise_on_missing: bool = False) -> Optional[dict[str, Any]]:
        """Return a biobank by id.

        Args:
            biobankId: Biobank identifier.
            raise_on_missing: Raise KeyError when not found.

        Returns:
            Matching biobank or None when not found and raise_on_missing is False.
        """
        for b in self.biobanks:
            if b['id'] == biobankId:
                if not self._matches_withdrawn_scope(self.isBiobankWithdrawn(biobankId)):
                    break
                return b
        if raise_on_missing:
            raise KeyError(f"Biobank {biobankId!r} not found in loaded directory snapshot.")
        log.warning("Biobank %r not found in loaded directory snapshot.", biobankId)
        return None

    def getBiobanksCount(self):
        """Return the number of loaded biobanks."""
        return len(self.getBiobanks())

    @staticmethod
    def _extract_country_code(value) -> str:
        """Return a country/staging code from a scalar or EMX-style wrapper."""
        if isinstance(value, dict):
            value = value.get("id", "")
        return str(value).strip().upper() if value is not None else ""

    def getBiobankNN(self, biobankID: str):
        """Return the node/staging-area code for a biobank id.

        The routing/grouping node is derived from the entity id prefix, not from
        the biobank country. This keeps non-member/global areas such as EXT/EU
        grouped under their staging area even when the hosted biobank country is
        a member-state code such as US/VN/DE.
        """
        biobank = self.directoryGraph.nodes[biobankID]['data']
        staging_area = NNContacts.extract_staging_area(biobankID)
        if staging_area:
            return staging_area
        return self._extract_country_code(biobank.get('country'))

    def getBiobankCountry(self, biobankID: str):
        """Return the reported country code for a biobank id."""
        biobank = self.directoryGraph.nodes[biobankID]['data']
        return self._extract_country_code(biobank.get('country'))

    def getCollections(self):
        """Return all loaded collections."""
        return [
            collection for collection in self.collections
            if self._matches_withdrawn_scope(self.isCollectionWithdrawn(collection['id']))
        ]

    def getCollectionById(self, collectionId: str, raise_on_missing: bool = False) -> Optional[dict[str, Any]]:
        """Return a collection by id.

        Args:
            collectionId: Collection identifier.
            raise_on_missing: Raise KeyError when not found.

        Returns:
            Matching collection or None when not found and raise_on_missing is False.
        """
        for c in self.collections:
            if c['id'] == collectionId:
                if not self._matches_withdrawn_scope(self.isCollectionWithdrawn(collectionId)):
                    break
                return c
        if raise_on_missing:
            raise KeyError(f"Collection {collectionId!r} not found in loaded directory snapshot.")
        log.warning("Collection %r not found in loaded directory snapshot.", collectionId)
        return None

    def getCollectionsCount(self):
        """Return the number of loaded collections."""
        return len(self.getCollections())

    def getCollectionBiobankId(self, collectionID: str):
        """Return the parent biobank id of the given collection id."""
        collection = self.directoryGraph.nodes[collectionID]['data']
        return collection['biobank']['id']

    def getCollectionContact(self, collectionID: str):
        """Return primary contact record for a collection id."""
        collection = self.directoryGraph.nodes[collectionID]['data']
        return self.contactHashmap[collection['contact']['id']]

    def getBiobankContact(self, biobankID: str):
        """Return primary contact record for a biobank id."""
        biobank = self.directoryGraph.nodes[biobankID]['data']
        return self.contactHashmap[biobank['contact']['id']]

    def isTopLevelCollection(self, collectionID: str):
        """Return True when collection has no parent_collection pointer."""
        collection = self.directoryGraph.nodes[collectionID]['data']
        return not 'parent_collection' in collection

    def isCountableCollection(self, collectionID: str, metric: str):
        """Return whether collection should be counted for a specific metric.

        A collection is countable when it has an integer value for `metric` and
        no ancestor collection has an integer value for the same metric.

        Args:
            collectionID: Collection identifier.
            metric: Supported metrics are `number_of_donors` and `size`.

        Raises:
            ValueError: If metric is unsupported.
        """
        if metric not in {'number_of_donors', 'size'}:
            raise ValueError(f"Unsupported metric {metric!r}; expected 'number_of_donors' or 'size'.")
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
        """Return the node/staging-area code for a collection id."""
        staging_area = NNContacts.extract_staging_area(collectionID)
        if staging_area:
            return staging_area
        return self.getBiobankNN(self.getCollectionBiobankId(collectionID))

    def getCollectionCountry(self, collectionID: str):
        """Return the reported country code for a collection id."""
        collection = self.directoryGraph.nodes[collectionID]['data']
        country = self._extract_country_code(collection.get('country'))
        if country:
            return country
        return self.getBiobankCountry(self.getCollectionBiobankId(collectionID))

    # return the whole subgraph including the biobank itself
    def getGraphBiobankCollectionsFromBiobank(self, biobankID: str):
        """Return subgraph containing a biobank and all descendant collections."""
        return self.directoryCollectionsDAG.subgraph(nx.algorithms.dag.descendants(self.directoryCollectionsDAG, biobankID).union({biobankID}))

    # return the whole subgraph including some collection
    def getGraphBiobankCollectionsFromCollection(self, collectionID: str):
        """Return subgraph containing a collection, its ancestors, and descendants."""
        return self.directoryCollectionsDAG.subgraph(nx.algorithms.dag.ancestors(self.directoryCollectionsDAG, collectionID).union(nx.algorithms.dag.descendants(self.directoryCollectionsDAG, collectionID)).union({collectionID}))

    def getCollectionsDescendants(self, collectionID: str):
        """Return descendant collection ids for a collection id."""
        return nx.algorithms.dag.descendants(self.directoryCollectionsDAG, collectionID)

    def getDirectSubcollections(self, collectionID: str):
        """Return direct child collections of a collection id."""
        children = []
        for childID in self.directoryCollectionsDAG.successors(collectionID):
            if childID not in self.directoryGraph.nodes:
                continue
            child = self.directoryGraph.nodes[childID]['data']
            if 'biobank' not in child:
                continue
            if not self._matches_withdrawn_scope(self.isCollectionWithdrawn(childID)):
                continue
            children.append(child)
        return children

    def getContacts(self):
        """Return all loaded contacts."""
        return self.contacts

    def getContact(self, contactID: str):
        """Return a contact by id."""
        return self.contactHashmap[contactID]

    def getContactNN(self, contactID: str):
        """Return the node/staging-area code for a contact id."""
        staging_area = NNContacts.extract_staging_area(contactID)
        if staging_area:
            return staging_area
        return self.getContactCountry(contactID)

    def getContactCountry(self, contactID: str):
        """Return the reported country code for a contact id."""
        return self._extract_country_code(self.contactHashmap[contactID].get('country'))


    def getNetworks(self):
        """Return all loaded networks."""
        return self.networks

    def getFacts(self):
        """Return all loaded collection facts."""
        return self.facts

    def getCollectionFacts(self, collectionID: str):
        """Return facts for a specific collection id."""
        return self.collectionFactMap.get(collectionID, [])

    def getServices(self):
        """Return all loaded services."""
        return [
            service for service in self.services
            if self._matches_withdrawn_scope(
                self.isBiobankWithdrawn(service['biobank']['id'])
            )
        ]

    def getServiceById(self, serviceID: str, raise_on_missing: bool = False) -> Optional[dict[str, Any]]:
        """Return a service by id."""
        if serviceID in self.serviceHashmap:
            return self.serviceHashmap[serviceID]
        if raise_on_missing:
            raise KeyError(f"Service {serviceID!r} not found in loaded directory snapshot.")
        log.warning("Service %r not found in loaded directory snapshot.", serviceID)
        return None

    def getBiobankServices(self, biobankID: str):
        """Return services belonging to a biobank id."""
        if not self._matches_withdrawn_scope(self.isBiobankWithdrawn(biobankID)):
            return []
        return self.biobankServiceMap.get(biobankID, [])

    def getNetworkNN(self, networkID: str):
        """Return the node/staging-area code for a network id."""
        staging_area = NNContacts.extract_staging_area(networkID)
        if staging_area:
            return staging_area
        network = self.networkGraph.nodes[networkID]['data']
        if 'country' in network:
            return self._extract_country_code(network['country'])
        elif 'contact' in network:
            return self.getContactNN(network['contact']['id'])
        return "EU"

    def getNetworkCountry(self, networkID: str):
        """Return the reported country code for a network id when present."""
        network = self.networkGraph.nodes[networkID]['data']
        if 'country' in network:
            return self._extract_country_code(network['country'])
        if 'contact' in network:
            return self.getContactCountry(network['contact']['id'])
        return ""

    @staticmethod
    def getListOfEntityAttributeIds(entity, key: str):
        """Return list of `id` values from an entity attribute list."""
        return [ element['id'] for element in entity[key] ] if key in entity else []

    @staticmethod
    def getListOfEntityAttributes(entity, key: str):
        """Return list value of an entity attribute when present, else empty list."""
        return [ element for element in entity[key] ] if key in entity else []
