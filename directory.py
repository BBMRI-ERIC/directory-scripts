# vim:ts=4:sw=4:tw=0:sts=4:et

"""Provide cache-backed access and graph traversal for Directory entities."""

import copy
import logging
import os
import os.path
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import networkx as nx
import pandas as pd
from diskcache import Cache
from molgenis_emx2_pyclient import Client
from molgenis_emx2_pyclient.exceptions import NoSuchTableException
from nncontacts import NNContacts

#logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("BBMRI Directory")
REPO_ROOT = Path(__file__).resolve().parent
NEGOTIATOR_ORPHANS_SHEET = "negotiator_collection_stats"
NEGOTIATOR_REPRESENTATIVE_COLUMNS = (
    "network_name",
    "biobank_name",
    "resource_name",
    "resource_source_id",
    "representatives_emails",
)


@dataclass(frozen=True)
class NegotiatorResource:
    """Normalized representatives registered for one Negotiator resource.

    Attributes:
        resource_source_id: Source collection identifier used to join the resource.
        network_name: Normalized network name supplied by the source row.
        biobank_name: Normalized biobank name supplied by the source row.
        resource_name: Normalized human-readable resource name from the source.
        representatives: Lower-cased, de-duplicated direct representative emails.
    """

    resource_source_id: str
    network_name: str
    biobank_name: str
    resource_name: str
    representatives: frozenset[str]


@dataclass(frozen=True)
class NegotiatorCoverage:
    """Actual direct Negotiator representative coverage for one biobank.

    Attributes:
        biobank_id: Directory biobank identifier covered by this summary.
        active_collection_count: Collections visible in the configured scope and
            considered for coverage.
        represented_collection_count: Visible collections with direct registrations.
        unrepresented_collection_count: Visible collections without direct registrations.
        status: ``fully``, ``partially``, ``missing``, or ``no_collections``.
    """

    biobank_id: str
    active_collection_count: int
    represented_collection_count: int
    unrepresented_collection_count: int
    status: str


def _cache_root() -> Path:
    """Return the base directory for persistent caches.

    Returns:
        A path from ``DIRECTORY_CACHE_ROOT`` when configured; otherwise the
        process working directory.
    """
    cache_root = os.environ.get("DIRECTORY_CACHE_ROOT")
    if cache_root:
        return Path(cache_root)
    return Path.cwd()


def _repo_cache_dir(*parts: str) -> str:
    """Return a cache path anchored to the configured cache root.

    Args:
        *parts: Path components appended without resolving or creating them.

    Returns:
        String form of the cache-root-relative path.
    """
    return str(_cache_root().joinpath(*parts))


def get_directory_ontology_table(
    table_name: str,
    *,
    directory_url: Optional[str] = None,
    purge_cache: bool = False,
) -> pd.DataFrame:
    """Return a cached DirectoryOntologies table, refreshing it live when needed.

    Args:
        table_name: Table read from the ``DirectoryOntologies`` schema.
        directory_url: Directory base URL; the public production URL is used
            when omitted. The cache is partitioned by this value.
        purge_cache: Whether to discard this table's cached entry before the
            read attempt.

    Returns:
        Cached or freshly fetched DataFrame. Callers must treat it as read-only.

    Raises:
        RuntimeError: If fetching fails and no cached DataFrame is available.
    """
    base_url = directory_url or "https://directory.bbmri-eric.eu"
    cache_dir = _repo_cache_dir("data-check-cache", "directory-DirectoryOntologies")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    cache = Cache(cache_dir)
    cache_key = f"table:{base_url}:{table_name}"

    try:
        if purge_cache and cache_key in cache:
            del cache[cache_key]

        cached_value = cache.get(cache_key)
        if isinstance(cached_value, pd.DataFrame):
            log.info("Using cached DirectoryOntologies/%s table.", table_name)
            return cached_value

        log.info("Retrieving DirectoryOntologies/%s from %s", table_name, base_url)
        with Client(base_url, schema="DirectoryOntologies") as session:
            table_df = session.get(table=table_name, as_df=True)
        cache[cache_key] = table_df
        return table_df
    except Exception as exc:
        cached_value = cache.get(cache_key)
        if isinstance(cached_value, pd.DataFrame):
            log.warning(
                "Unable to refresh DirectoryOntologies/%s; reusing cached copy instead: %s",
                table_name,
                exc,
            )
            return cached_value
        raise RuntimeError(
            f"Unable to load DirectoryOntologies table {table_name!r} and no cached copy is available."
        ) from exc
    finally:
        cache.close()

class Directory:
    """Provide a cache-first, read-only Directory snapshot and its relationship graphs.

    Loaded entity mappings are shared with the snapshot and graph node data;
    callers must treat them as read-only. Biobank, collection, service, and
    study selectors document whether they apply configured withdrawal scope;
    contacts, networks, and facts deliberately expose the loaded snapshot.
    """

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
        skip_graph_dag_validation: bool = False,
    ):
        """Initialize a directory snapshot and build query/helper graphs.

        Args:
            schema: Directory schema/staging area to load and cache.
            purgeCaches: Cache names to clear; ``directory`` clears this
                schema's snapshot before loading.
            debug: Whether to pretty-print collection payloads when ``pp`` is
                supplied during a live collection fetch.
            pp: Pretty-printer exposing ``pprint`` for the debug payload log.
            username: Optional account name used only with ``password``.
            password: Optional account password used only with ``username``.
            token: Optional client token; it takes the unauthenticated branch
                only when absent and no username/password pair is supplied.
            directory_url: Directory base URL; defaults to production. Cache
                directories are schema-specific, not URL-specific.
            include_withdrawn_entities: Include both active and withdrawn
                entities in scoped public selectors.
            only_withdrawn_entities: Restrict scoped public selectors to
                withdrawn entities; also enables ``include_withdrawn_entities``.
            skip_graph_dag_validation: Emergency escape hatch which leaves
                graph construction active but skips hierarchy acyclicity checks.

        Raises:
            RuntimeError: If neither a complete cached snapshot nor a live
                Directory connection is available.
            Exception: If loaded graph structure is inconsistent or a checked
                hierarchy is cyclic.
        """
        if purgeCaches is None:
            purgeCaches = list()
        self.__pp = pp
        self.__package = schema
        self.skip_graph_dag_validation = bool(skip_graph_dag_validation)
        self._negotiator_resources: Optional[dict[str, NegotiatorResource]] = None
        self._negotiator_unmatched_resource_ids: tuple[str, ...] = ()
        self.only_withdrawn_entities = only_withdrawn_entities
        self.include_withdrawn_entities = include_withdrawn_entities or only_withdrawn_entities
        self._ai_checksum_snapshot = {}
        log.debug('Checking data in schema: ' + schema)

        schema_cache_suffix = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(schema))
        cache_dir = _repo_cache_dir("data-check-cache", f'directory-{schema_cache_suffix}')
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
            self._refresh_missing_optional_quality_tables(
                cache=cache,
                schema=schema,
                client_kwargs=client_kwargs,
                username=username,
                password=password,
                token=token,
            )
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
        # Graph/DAG containing only biobanks and services
        self.directoryServicesGraph = nx.DiGraph()
        self.directoryServicesDAG = nx.DiGraph()
        # Graph/DAG containing biobanks, collections, and studies
        self.directoryStudiesGraph = nx.DiGraph()
        self.directoryStudiesDAG = nx.DiGraph()
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
            self.directoryServicesGraph.add_node(b['id'], data=b)
            self.directoryServicesDAG.add_node(b['id'], data=b)
            self.directoryStudiesGraph.add_node(b['id'], data=b)
            self.directoryStudiesDAG.add_node(b['id'], data=b)
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
            self.directoryStudiesGraph.add_node(c['id'], data=c)
            self.directoryStudiesDAG.add_node(c['id'], data=c)
            if self.contactGraph.has_node(c['id']):
                raise Exception('DirectoryStructure', 'Conflicting ID found in contactGraph: ' + c['id'])
            self.contactGraph.add_node(c['id'], data=c)
            if self.networkGraph.has_node(c['id']):
                raise Exception('DirectoryStructure', 'Conflicting ID found in networkGraph: ' + c['id'])
            self.networkGraph.add_node(c['id'], data=c)
        for service in self.services:
            log.debug(f'Processing service {service["id"]} into the graph')
            if self.directoryServicesGraph.has_node(service['id']):
                raise Exception('DirectoryStructure', 'Conflicting ID found in directoryServicesGraph: ' + service['id'])
            self.directoryServicesGraph.add_node(service['id'], data=service)
            self.directoryServicesDAG.add_node(service['id'], data=service)
        for study in self.studies:
            log.debug(f'Processing study {study["id"]} into the graph')
            if self.directoryStudiesGraph.has_node(study['id']):
                raise Exception('DirectoryStructure', 'Conflicting ID found in directoryStudiesGraph: ' + study['id'])
            self.directoryStudiesGraph.add_node(study['id'], data=study)
            self.directoryStudiesDAG.add_node(study['id'], data=study)
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
        self.studyHashmap = {}
        self.collectionStudyMap = {}
        self.studyCollectionIdMap = {}
        self.biobankStudyMap = {}
        for study in self.studies:
            self.studyHashmap[study['id']] = study
        for collection in self.collections:
            collection_id = collection['id']
            biobank_id = collection['biobank']['id']
            seen_study_ids = set()
            for study_id in self.getListOfEntityAttributeIds(collection, 'studies'):
                if not study_id or study_id in seen_study_ids:
                    continue
                seen_study_ids.add(study_id)
                study = self.studyHashmap.get(study_id)
                if study is None:
                    log.warning(
                        "Collection %r refers non-existent study ID %r in studies field.",
                        collection_id,
                        study_id,
                    )
                    continue
                self.collectionStudyMap.setdefault(collection_id, []).append(study)
                self.studyCollectionIdMap.setdefault(study_id, []).append(collection_id)
                existing_studies = self.biobankStudyMap.setdefault(biobank_id, [])
                if study not in existing_studies:
                    existing_studies.append(study)

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
                self.directoryStudiesGraph.add_edge(c['id'], c['parent_collection']['id'])
                self.directoryStudiesGraph.add_edge(c['parent_collection']['id'], c['id'])
                self.directoryStudiesDAG.add_edge(c['parent_collection']['id'], c['id'])
            else:
                # some of root collections of a biobank
                # we add both edges as we can't extract this information from the biobank level (it contains pointers to all the child collections)
                self.directoryGraph.add_edge(c['id'], c['biobank']['id'])
                self.directoryGraph.add_edge(c['biobank']['id'], c['id'])
                self.directoryCollectionsDAG.add_edge(c['biobank']['id'], c['id'])
                self.directoryStudiesGraph.add_edge(c['id'], c['biobank']['id'])
                self.directoryStudiesGraph.add_edge(c['biobank']['id'], c['id'])
                self.directoryStudiesDAG.add_edge(c['biobank']['id'], c['id'])
            # some of root collections of a biobank
            for sb in c.get('sub_collections', []):
                self.directoryGraph.add_edge(c['id'], sb['id'])
                self.directoryCollectionsDAG.add_edge(c['id'], sb['id'])
                self.directoryStudiesGraph.add_edge(c['id'], sb['id'])
                self.directoryStudiesGraph.add_edge(sb['id'], c['id'])
                self.directoryStudiesDAG.add_edge(c['id'], sb['id'])
            if 'contact' in c:
                self.contactGraph.add_edge(c['id'],c['contact']['id'])
            for n in c.get('networks', []):
                self.networkGraph.add_edge(c['id'], n['id'])
        for service in self.services:
            biobank = service.get('biobank')
            if biobank is None or 'id' not in biobank:
                continue
            if not self.directoryServicesGraph.has_node(biobank['id']):
                raise Exception('DirectoryStructure', 'Service refers non-existent biobank ID: ' + biobank['id'])
            self.directoryServicesGraph.add_edge(service['id'], biobank['id'])
            self.directoryServicesGraph.add_edge(biobank['id'], service['id'])
            self.directoryServicesDAG.add_edge(biobank['id'], service['id'])
        for study_id, collection_ids in self.studyCollectionIdMap.items():
            for collection_id in collection_ids:
                if not self.directoryStudiesGraph.has_node(collection_id):
                    raise Exception('DirectoryStructure', 'Study refers non-existent collection ID: ' + collection_id)
                self.directoryStudiesGraph.add_edge(study_id, collection_id)
                self.directoryStudiesGraph.add_edge(collection_id, study_id)
                self.directoryStudiesDAG.add_edge(collection_id, study_id)

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
        self._ensure_bidirectional_edges(self.directoryGraph, "directoryGraph")
        self._ensure_bidirectional_edges(self.contactGraph, "contactGraph")
        self._ensure_bidirectional_edges(
            self.directoryServicesGraph,
            "directoryServicesGraph",
        )
        self._ensure_bidirectional_edges(
            self.directoryStudiesGraph,
            "directoryStudiesGraph",
        )
        self._ensure_bidirectional_edges(self.networkGraph, "networkGraph")

        # now make graphs immutable
        nx.freeze(self.directoryGraph)
        nx.freeze(self.directoryCollectionsDAG)
        nx.freeze(self.directoryServicesGraph)
        nx.freeze(self.directoryServicesDAG)
        nx.freeze(self.directoryStudiesGraph)
        nx.freeze(self.directoryStudiesDAG)
        nx.freeze(self.contactGraph)
        nx.freeze(self.networkGraph)

        # we check that DAG is indeed DAG :-)
        self._validate_directory_dags(
            self.directoryCollectionsDAG,
            self.directoryServicesDAG,
            self.directoryStudiesDAG,
            skip_validation=skip_graph_dag_validation,
        )

        log.info('Directory structure initialized')
        self.__orphacodesmapper = None
        self._collection_withdrawn_cache = {}

    @staticmethod
    def _edge_label(source: Any, target: Any) -> str:
        """Return a stable human-readable graph edge label.

        Args:
            source: Edge source node, formatted with ``str``.
            target: Edge target node, formatted with ``str``.

        Returns:
            ``"source -> target"`` for diagnostics.
        """
        return f"{source} -> {target}"

    @classmethod
    def _cycle_diagnostics(cls, graph: nx.DiGraph) -> tuple[str, str, list[Any]]:
        """Return cycle path, edge list, and node list for a non-DAG graph.

        Args:
            graph: Directed graph expected to contain a cycle.

        Returns:
            Cycle path text, edge-list text, and the cycle nodes in traversal
            order; placeholder text and an empty node list if no cycle remains.
        """
        try:
            cycle_edges = nx.find_cycle(graph)
        except nx.NetworkXNoCycle:
            return "<cycle unavailable>", "<cycle edges unavailable>", []

        normalized_edges = [(edge[0], edge[1]) for edge in cycle_edges]
        cycle_nodes = [normalized_edges[0][0]]
        cycle_nodes.extend(target for _, target in normalized_edges)
        cycle_path = " -> ".join(str(node) for node in cycle_nodes)
        edge_list = ", ".join(
            cls._edge_label(source, target) for source, target in normalized_edges
        )
        return cycle_path, edge_list, cycle_nodes

    @staticmethod
    def _debug_log_offending_nodes(
        graph: nx.DiGraph,
        graph_name: str,
        node_ids: list[Any],
    ) -> None:
        """Log full node payloads for graph diagnostics in debug mode.

        Args:
            graph: Graph holding the node payloads.
            graph_name: Name included in each diagnostic message.
            node_ids: Existing graph-node identifiers to log.

        Returns:
            None. Emits DEBUG records only.
        """
        for node_id in node_ids:
            log.debug(
                "DirectoryStructure - %s offending node %s data: %r",
                graph_name,
                node_id,
                graph.nodes[node_id].get("data"),
            )

    @classmethod
    def _ensure_bidirectional_edges(cls, graph: nx.DiGraph, graph_name: str) -> None:
        """Ensure every edge in a traversal graph has a reverse edge.

        Args:
            graph: Mutable traversal graph to inspect and repair.
            graph_name: Name included in warning messages.

        Returns:
            None. Missing reverse edges are added in place before graphs freeze.
        """
        missing_reverse_edges = [
            (source, target)
            for source, target in list(graph.edges())
            if not graph.has_edge(target, source)
        ]
        if not missing_reverse_edges:
            return

        log.warning(
            "DirectoryStructure - %s has %d edge(s) without a reverse edge.",
            graph_name,
            len(missing_reverse_edges),
        )
        for source, target in missing_reverse_edges:
            log.warning(
                "DirectoryStructure - %s: Missing reverse edge for %s; adding %s.",
                graph_name,
                cls._edge_label(source, target),
                cls._edge_label(target, source),
            )
            cls._debug_log_offending_nodes(graph, graph_name, [source, target])
            graph.add_edge(target, source)

    @classmethod
    def _validate_directed_acyclic_graph(
        cls,
        graph: nx.DiGraph,
        graph_name: str,
        label: str,
    ) -> None:
        """Raise an actionable error if a supposed DAG contains a cycle.

        Args:
            graph: Directed hierarchy graph to validate.
            graph_name: Internal graph name included in diagnostics.
            label: User-facing hierarchy label included in the exception.

        Returns:
            None when acyclic.

        Raises:
            Exception: With cycle path and edge details when ``graph`` is not
                a DAG.
        """
        if nx.algorithms.dag.is_directed_acyclic_graph(graph):
            return

        cycle_path, cycle_edges, cycle_nodes = cls._cycle_diagnostics(graph)
        cls._debug_log_offending_nodes(graph, graph_name, cycle_nodes)
        raise Exception(
            "DirectoryStructure",
            (
                f"{label} is not DAG: {graph_name} violates the directed "
                f"acyclic graph requirement; offending cycle: {cycle_path}; "
                f"cycle edges: {cycle_edges}"
            ),
        )

    @classmethod
    def _validate_directory_dags(
        cls,
        collections_dag: nx.DiGraph,
        services_dag: nx.DiGraph,
        studies_dag: nx.DiGraph,
        *,
        skip_validation: bool,
    ) -> None:
        """Validate Directory hierarchy DAGs unless emergency mode is enabled.

        Args:
            collections_dag: Biobank-to-collection hierarchy graph.
            services_dag: Biobank-to-service hierarchy graph.
            studies_dag: Biobank/collection-to-study relationship DAG.
            skip_validation: Whether to warn and bypass all acyclicity checks.

        Returns:
            None. Validation is deliberately all-or-nothing in emergency mode.
        """
        if skip_validation:
            log.warning(
                "Emergency mode enabled: skipping Directory DAG acyclicity "
                "validation for collection, service, and study graphs. "
                "Proceed at own risk; hierarchy traversal results may be unreliable."
            )
            return

        cls._validate_directed_acyclic_graph(
            collections_dag,
            "directoryCollectionsDAG",
            "Collection DAG",
        )
        cls._validate_directed_acyclic_graph(
            services_dag,
            "directoryServicesDAG",
            "Service DAG",
        )
        cls._validate_directed_acyclic_graph(
            studies_dag,
            "directoryStudiesDAG",
            "Study DAG",
        )

    @staticmethod
    def _load_quality_table(session: Client, table_name: str, schema: str) -> pd.DataFrame:
        """Load an optional quality-info table or return an empty DataFrame when absent.

        Args:
            session: Open client already selected to ``schema``.
            table_name: Optional quality table to retrieve.
            schema: Schema name used only in the absent-table log message.

        Returns:
            Table DataFrame, or a new empty DataFrame when the table is absent.
        """
        try:
            return session.get(table=table_name, as_df=True)
        except NoSuchTableException:
            log.info("Skipping optional quality table %s in schema %s.", table_name, schema)
            return pd.DataFrame()

    @staticmethod
    def _has_complete_cached_snapshot(cache: Cache) -> bool:
        """Return whether the cache contains the minimum full snapshot needed for offline reuse.

        Args:
            cache: Open diskcache containing Directory snapshot entries.

        Returns:
            Whether all core entity keys required for offline construction exist;
            optional quality, service, and study keys are not required.
        """
        required_keys = ("biobanks", "collections", "contacts", "networks", "facts")
        return all(key in cache for key in required_keys)

    @staticmethod
    def _get_cached_dataframe(cache: Cache, key: str) -> pd.DataFrame:
        """Return a cached DataFrame value or an empty DataFrame when the cache key is absent.

        Args:
            cache: Open diskcache to query.
            key: Cache key expected to contain a pandas DataFrame.

        Returns:
            Cached DataFrame itself, or a new empty DataFrame for an absent or
            non-DataFrame entry. The cached value is not copied.
        """
        if key in cache:
            cached_value = cache[key]
            if isinstance(cached_value, pd.DataFrame):
                return cached_value
        return pd.DataFrame()

    @staticmethod
    def _get_missing_optional_quality_cache_keys(cache: Cache) -> list[tuple[str, str]]:
        """Return missing optional quality cache keys and their live table names.

        Args:
            cache: Open diskcache to inspect.

        Returns:
            Cache-key/table-name pairs for absent optional quality tables, in
            the fixed biobank-then-collection order.
        """
        quality_tables = [
            ("quality_info_biobanks", "QualityInfoBiobanks"),
            ("quality_info_collections", "QualityInfoCollections"),
        ]
        return [
            (cache_key, table_name)
            for cache_key, table_name in quality_tables
            if cache_key not in cache
        ]

    def _load_cached_snapshot(self, cache: Cache, schema: str) -> None:
        """Populate Directory tables from an existing cache snapshot without using the live API.

        Args:
            cache: Complete snapshot cache to read; it is not mutated.
            schema: Schema name used for informative log messages.

        Returns:
            None. Loaded entities subsequently share mappings with their graph
            node data; absent optional services or studies become new empty lists.
        """
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
        log.info('   ... retrieving studies')
        self.studies = cache['studies'] if 'studies' in cache else []
        if 'studies' in cache:
            log.info(f'   ... retrieved {len(self.studies)} studies from cache')
        else:
            log.info('   ... cached snapshot has no studies table; using empty list')

    def _refresh_missing_optional_quality_tables(
        self,
        cache: Cache,
        schema: str,
        client_kwargs: dict[str, Any],
        username: Optional[str],
        password: Optional[str],
        token: Optional[str],
    ) -> None:
        """Backfill missing optional quality tables without refetching the full snapshot.

        Args:
            cache: Complete snapshot cache whose absent optional entries may be
                backfilled.
            schema: Schema selected on the short-lived backfill client.
            client_kwargs: Client construction keyword arguments, currently
                carrying a token when configured.
            username: Optional account name paired with ``password``.
            password: Optional account password paired with ``username``.
            token: Token-presence indicator used for the unauthenticated log.

        Returns:
            None. Backfill failure is logged and leaves the usable core snapshot
            intact; it never refetches core tables.
        """
        missing_quality_tables = self._get_missing_optional_quality_cache_keys(cache)
        if not missing_quality_tables:
            return

        log.info(
            "Cached snapshot for schema %s is missing optional quality tables; attempting live backfill.",
            schema,
        )
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
                for cache_key, table_name in missing_quality_tables:
                    quality_df = self._load_quality_table(session, table_name, schema)
                    cache[cache_key] = quality_df
                    if cache_key == "quality_info_biobanks":
                        self.qualBBtable = quality_df
                    elif cache_key == "quality_info_collections":
                        self.qualColltable = quality_df
        except Exception as exc:
            log.warning(
                "Unable to backfill optional quality tables for schema %s; continuing with cached snapshot: %s",
                schema,
                exc,
            )

    def _load_live_snapshot(self, session: Client, cache: Cache, schema: str, debug: bool) -> None:
        """Populate Directory tables from the live API and cache the retrieved snapshot.

        Args:
            session: Open, schema-selected Directory client.
            cache: Cache read for existing entities and written for newly
                retrieved values.
            schema: Schema name passed to optional-quality-table logging.
            debug: Whether to pretty-print live-fetched collections when a
                pretty-printer was supplied at construction.

        Returns:
            None. Existing cached core tables are reused; optional services and
            studies degrade to empty lists if their live reads fail.
        """
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
        log.info('   ... retrieving studies')
        if 'studies' in cache:
            self.studies = cache['studies']
            log.info(f'   ... retrieved {len(self.studies)} studies from cache')
        else:
            try:
                start_time = time.perf_counter()
                self.studies = session.get_graphql("Studies")
                cache['studies'] = self.studies
                end_time = time.perf_counter()
                log.info(f'   ... retrieved {len(self.studies)} studies in ' + "%0.3f" % (end_time-start_time) + 's')
            except Exception as exc:
                log.warning('Unable to retrieve studies: %s', exc)
                self.studies = []

    def prepare_ai_cache_checksum_state(self):
        """Capture pristine entities for AI-cache checksum validation.

        Returns:
            None. On its first call, deep-copies loaded biobanks and collections;
            later calls preserve that original snapshot.
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
        """Return the pristine snapshot entity used for AI-cache checksums.

        Args:
            entity_type: Top-level checksum group, normally ``BIOBANK`` or
                ``COLLECTION``.
            entity_id: Identifier within that group.

        Returns:
            The retained deep-copied entity mapping, or ``None`` if unknown.
            The retained mapping is shared with the checksum state and read-only.
        """
        if not self._ai_checksum_snapshot:
            self.prepare_ai_cache_checksum_state()
        return self._ai_checksum_snapshot.get(entity_type, {}).get(entity_id)

    def setOrphaCodesMapper(self, o):
        """Attach an OrphaCodes mapper implementation.

        Args:
            o: Mapper object or ``None`` to attach without validation.

        Returns:
            None. Replaces the previously configured mapper.
        """
        self.__orphacodesmapper = o

    def issetOrphaCodesMapper(self) -> bool:
        """Return whether an OrphaCodes mapper is configured.

        Returns:
            ``True`` exactly when the stored mapper is not ``None``.
        """
        return self.__orphacodesmapper is not None

    def getOrphaCodesMapper(self):
        """Return the configured OrphaCodes mapper.

        Returns:
            The stored mapper object, including ``None``; it is not copied.
        """
        return self.__orphacodesmapper

    def getSchema(self) -> str:
        """Return the configured Directory schema/staging-area name.

        Returns:
            The schema string passed during construction.
        """
        return self.__package

    def getDirectoryUrl(self) -> str:
        """Return the configured Directory base URL.

        Returns:
            The base URL selected during construction.
        """
        return self.__directoryURL

    @staticmethod
    def _is_explicitly_withdrawn(entity: Optional[dict[str, Any]]) -> bool:
        """Return whether an entity is explicitly marked as withdrawn.

        Args:
            entity: Entity mapping, or ``None`` for no entity.

        Returns:
            ``bool(entity["withdrawn"])`` when present, otherwise ``False``.
        """
        if not entity:
            return False
        return bool(entity.get("withdrawn"))

    def isBiobankWithdrawn(self, biobankID: str) -> bool:
        """Return whether a biobank is explicitly marked as withdrawn.

        Args:
            biobankID: Identifier of a biobank graph node.

        Returns:
            Its own ``withdrawn`` flag only; no scope filtering is applied.
        """
        biobank = self.directoryGraph.nodes[biobankID]['data']
        return self._is_explicitly_withdrawn(biobank)

    def isCollectionWithdrawn(self, collectionID: str) -> bool:
        """Return whether a collection is withdrawn, including inherited state.

        Args:
            collectionID: Identifier of a collection graph node.

        Returns:
            ``True`` for an explicit withdrawal, a withdrawn owner biobank, or
            a withdrawn ancestor collection.
        """
        return self._is_collection_withdrawn(collectionID, [])

    def _is_collection_withdrawn(
        self,
        collectionID: str,
        parent_path: list[str],
    ) -> bool:
        """Return inherited collection withdrawal state without recursing forever.

        Args:
            collectionID: Collection graph-node identifier being evaluated.
            parent_path: Current recursive ancestor path for cycle detection.

        Returns:
            Cached inherited withdrawal state. A detected inheritance cycle logs
            a warning and contributes ``False`` for that cyclic path.
        """
        if collectionID in self._collection_withdrawn_cache:
            return self._collection_withdrawn_cache[collectionID]
        if collectionID in parent_path:
            cycle_path = parent_path[parent_path.index(collectionID):] + [collectionID]
            log.warning(
                "DirectoryStructure - collection withdrawal inheritance cycle "
                "detected while checking %s: %s. Treating cyclic parent "
                "inheritance as not withdrawn for this path.",
                collectionID,
                " -> ".join(cycle_path),
            )
            return False

        collection = self.directoryGraph.nodes[collectionID]['data']
        withdrawn = self._is_explicitly_withdrawn(collection)
        if not withdrawn:
            withdrawn = self.isBiobankWithdrawn(collection['biobank']['id'])
        if not withdrawn and 'parent_collection' in collection:
            withdrawn = self._is_collection_withdrawn(
                collection['parent_collection']['id'],
                parent_path + [collectionID],
            )

        self._collection_withdrawn_cache[collectionID] = withdrawn
        return withdrawn

    def _matches_withdrawn_scope(self, is_withdrawn: bool) -> bool:
        """Return whether an entity matches the configured withdrawn scope.

        Args:
            is_withdrawn: Effective withdrawal state of the candidate entity.

        Returns:
            Whether the state passes ``only_withdrawn_entities`` first, then
            ``include_withdrawn_entities``, otherwise the active-only default.
        """
        if self.only_withdrawn_entities:
            return is_withdrawn
        if self.include_withdrawn_entities:
            return True
        return not is_withdrawn

    def getBiobanks(self):
        """Return loaded biobanks in snapshot order after configured scope filtering.

        Returns:
            A new list containing shared biobank mappings that callers must
            treat as read-only. ``only_withdrawn_entities`` selects withdrawn
            biobanks, ``include_withdrawn_entities`` selects both states, and
            the default selects active biobanks.
        """
        return [
            biobank for biobank in self.biobanks
            if self._matches_withdrawn_scope(self.isBiobankWithdrawn(biobank['id']))
        ]

    @staticmethod
    def _normalize_quality_entity_reference(value: Any) -> str:
        """Return a comparable entity identifier from a quality-table reference cell.

        Args:
            value: Quality-table reference cell, which may be a mapping.

        Returns:
            Its ``id`` when mapped, otherwise its string form; null becomes
            the empty string.
        """
        if isinstance(value, dict):
            value = value.get("id", "")
        return str(value) if value is not None else ""

    @staticmethod
    def _filter_quality_table_by_entity_ids(
        df: pd.DataFrame,
        entity_column: str,
        allowed_ids: set[str],
    ) -> pd.DataFrame:
        """Return only the quality rows whose entity reference matches ``allowed_ids``.

        Args:
            df: Raw quality DataFrame; it is never mutated.
            entity_column: Column containing entity references.
            allowed_ids: Normalized entity IDs permitted in the result.

        Returns:
            A copy of matching rows, or a copy of the input when it is empty or
            lacks ``entity_column``.
        """
        if df.empty or entity_column not in df.columns:
            return df.copy()
        mask = df[entity_column].apply(Directory._normalize_quality_entity_reference).isin(allowed_ids)
        return df.loc[mask].copy()

    @staticmethod
    def _reshape_quality_table(
        df: pd.DataFrame,
        entity_column: str,
        assess_level_column: str,
    ) -> pd.DataFrame:
        """Return one wide quality row per entity from the raw quality rows.

        Args:
            df: Raw quality rows; it is never mutated.
            entity_column: Biobank or collection reference column.
            assess_level_column: Assessment-level value column to pivot.

        Returns:
            New DataFrame with one row per entity and sorted quality-standard
            columns, or only ``entity_column`` when required columns are absent.
        """
        required_columns = {"id", entity_column, "quality_standard", assess_level_column}
        missing_columns = sorted(required_columns.difference(df.columns))
        if df.empty or missing_columns:
            return pd.DataFrame(columns=[entity_column])

        pivoted_df = df.pivot(
            index=["id", entity_column],
            columns="quality_standard",
            values=assess_level_column,
        ).reset_index()
        pivoted_df = pivoted_df.drop(columns="id")
        pivoted_df.columns.name = None
        final_df = pivoted_df.groupby(entity_column, as_index=False).first()
        return final_df[[entity_column] + sorted(col for col in final_df.columns if col != entity_column)]

    @staticmethod
    def _rename_quality_standard_columns(
        df: pd.DataFrame,
        quality_standards_ontology: pd.DataFrame,
    ) -> pd.DataFrame:
        """Rename quality-standard code columns to ontology labels when available.

        Args:
            df: Wide quality DataFrame whose standard-code columns may be renamed.
            quality_standards_ontology: Ontology table with optional ``name`` and
                ``label`` columns.

        Returns:
            A copied DataFrame with available code-to-label column renames; the
            input is unchanged.
        """
        if df.empty:
            return df.copy()
        if quality_standards_ontology.empty or not {"name", "label"}.issubset(quality_standards_ontology.columns):
            return df.copy()
        renamed_df = df.copy()
        mapping = {
            row["name"]: row["label"]
            for _, row in quality_standards_ontology.iterrows()
            if row.get("name") not in (None, "") and row.get("label") not in (None, "")
        }
        return renamed_df.rename(columns=mapping)

    def _resolve_quality_scope(self, scope: str) -> str:
        """Validate and normalize a quality-table scope selector.

        Args:
            scope: One of ``configured``, ``active``, ``withdrawn``, or ``all``.

        Returns:
            The unchanged, validated selector.

        Raises:
            ValueError: If the selector is unsupported.
        """
        allowed_scopes = {"configured", "active", "withdrawn", "all"}
        if scope not in allowed_scopes:
            raise ValueError(
                f"Unsupported quality scope {scope!r}; expected one of {sorted(allowed_scopes)}."
            )
        return scope

    def _get_quality_allowed_entity_ids(self, entity_type: str, scope: str) -> Optional[set[str]]:
        """Return the entity ids visible under a given quality-table scope.

        Args:
            entity_type: ``biobank`` or ``collection`` quality-table kind.
            scope: Validated quality scope selector.

        Returns:
            Matching entity IDs, or ``None`` for ``all``. ``configured`` follows
            this instance's withdrawal options; collection withdrawal inherits
            owner and ancestor withdrawal.
        """
        scope = self._resolve_quality_scope(scope)
        if scope == "all":
            return None

        if entity_type == "biobank":
            entities = self.biobanks
            configured_entities = self.getBiobanks()
            is_withdrawn = self.isBiobankWithdrawn
        elif entity_type == "collection":
            entities = self.collections
            configured_entities = self.getCollections()
            is_withdrawn = self.isCollectionWithdrawn
        else:
            raise ValueError(f"Unsupported quality entity type {entity_type!r}.")

        if scope == "configured":
            return {entity["id"] for entity in configured_entities}

        include_withdrawn = scope == "withdrawn"
        return {entity["id"] for entity in entities if is_withdrawn(entity["id"]) is include_withdrawn}

    def getQualityStandardsOntology(self, purge_cache: bool = False) -> pd.DataFrame:
        """Return the cached QualityStandards ontology table for this Directory target.

        Args:
            purge_cache: Whether to remove the target-specific cached ontology
                table before attempting retrieval.

        Returns:
            Cached or fetched ontology DataFrame; see
            ``get_directory_ontology_table`` for session and failure behavior.
        """
        return get_directory_ontology_table(
            "QualityStandards",
            directory_url=self.__directoryURL,
            purge_cache=purge_cache,
        )

    def getBiobankQualityInfo(self, scope: str = "configured") -> pd.DataFrame:
        """Return biobank quality-info rows filtered by the requested scope.

        Args:
            scope: ``configured`` (default), ``active``, ``withdrawn``, or
                ``all``; configured follows this instance's withdrawal options.

        Returns:
            A new DataFrame copy of raw rows whose normalized biobank reference
            matches the scope. ``all`` still returns a copy.
        """
        allowed_ids = self._get_quality_allowed_entity_ids("biobank", scope)
        raw_df = self.qualBBtable.copy()
        if allowed_ids is None:
            return raw_df
        return self._filter_quality_table_by_entity_ids(raw_df, "biobank", allowed_ids)

    def getCollectionQualityInfo(self, scope: str = "configured") -> pd.DataFrame:
        """Return collection quality-info rows filtered by the requested scope.

        Args:
            scope: ``configured`` (default), ``active``, ``withdrawn``, or
                ``all``; collection scope includes inherited withdrawal state.

        Returns:
            A new DataFrame copy of raw rows whose normalized collection
            reference matches the scope.
        """
        allowed_ids = self._get_quality_allowed_entity_ids("collection", scope)
        raw_df = self.qualColltable.copy()
        if allowed_ids is None:
            return raw_df
        return self._filter_quality_table_by_entity_ids(raw_df, "collection", allowed_ids)

    def getBiobankQualityInfoWide(
        self,
        scope: str = "configured",
        *,
        use_ontology_labels: bool = False,
        purge_ontology_cache: bool = False,
        quality_standards_ontology: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Return one wide quality-information row per biobank.

        Args:
            scope: Quality scope passed to ``getBiobankQualityInfo``.
            use_ontology_labels: Rename quality-standard code columns from the
                supplied or cached ontology table.
            purge_ontology_cache: Purge only when an ontology must be fetched.
            quality_standards_ontology: Optional ontology DataFrame, used
                directly instead of fetching.

        Returns:
            New wide DataFrame with one row per biobank and sorted standard
            columns; duplicate entity/standard rows retain pandas ``first``.
        """
        quality_df = self._reshape_quality_table(
            self.getBiobankQualityInfo(scope=scope),
            "biobank",
            "assess_level_bio",
        )
        if use_ontology_labels:
            if quality_standards_ontology is None:
                quality_standards_ontology = self.getQualityStandardsOntology(
                    purge_cache=purge_ontology_cache
                )
            quality_df = self._rename_quality_standard_columns(
                quality_df,
                quality_standards_ontology,
            )
        return quality_df

    def getCollectionQualityInfoWide(
        self,
        scope: str = "configured",
        *,
        use_ontology_labels: bool = False,
        purge_ontology_cache: bool = False,
        quality_standards_ontology: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Return one wide quality-information row per collection.

        Args:
            scope: Quality scope passed to ``getCollectionQualityInfo``.
            use_ontology_labels: Rename standard-code columns from ontology labels.
            purge_ontology_cache: Purge only when an ontology must be fetched.
            quality_standards_ontology: Optional ontology DataFrame used directly.

        Returns:
            New wide DataFrame with one row per collection and sorted standard
            columns; duplicate entity/standard rows retain pandas ``first``.
        """
        quality_df = self._reshape_quality_table(
            self.getCollectionQualityInfo(scope=scope),
            "collection",
            "assess_level_col",
        )
        if use_ontology_labels:
            if quality_standards_ontology is None:
                quality_standards_ontology = self.getQualityStandardsOntology(
                    purge_cache=purge_ontology_cache
                )
            quality_df = self._rename_quality_standard_columns(
                quality_df,
                quality_standards_ontology,
            )
        return quality_df

    def getQualBB(self):
        """Return the raw cached biobank quality-info table without scope filtering.

        Returns:
            A copy of the unfiltered cached ``QualityInfoBiobanks`` table.
        """
        return self.qualBBtable.copy()

    def getQualColl(self):
        """Return the raw cached collection quality-info table without scope filtering.

        Returns:
            A copy of the unfiltered cached ``QualityInfoCollections`` table.
        """
        return self.qualColltable.copy()

    def _get_loaded_biobank_by_id(self, biobankID: str) -> Optional[dict[str, Any]]:
        """Return a loaded biobank regardless of withdrawn scope, or None when absent.

        Args:
            biobankID: Identifier to resolve from the constructed graph.

        Returns:
            Shared loaded biobank mapping regardless of withdrawal scope, or
            ``None`` when the node is absent or does not look like a biobank.
        """
        if self.directoryGraph.has_node(biobankID):
            biobank = self.directoryGraph.nodes[biobankID].get('data')
            if isinstance(biobank, dict) and ('country' in biobank or 'contact' in biobank):
                return biobank
        return None

    def _get_loaded_collection_by_id(self, collectionID: str) -> Optional[dict[str, Any]]:
        """Return a loaded collection regardless of withdrawn scope, or None when absent.

        Args:
            collectionID: Identifier to resolve from the constructed graph.

        Returns:
            Shared loaded collection mapping regardless of withdrawal scope, or
            ``None`` when the node is absent or has no biobank ownership.
        """
        if self.directoryGraph.has_node(collectionID):
            collection = self.directoryGraph.nodes[collectionID]['data']
            if 'biobank' in collection:
                return collection
        return None

    def _get_visible_collection_by_id(self, collectionID: str) -> Optional[dict[str, Any]]:
        """Return a collection visible under the current withdrawn scope, or None.

        Args:
            collectionID: Identifier to resolve from the loaded snapshot.

        Returns:
            Shared collection mapping if it passes the configured withdrawal
            filter, otherwise ``None``.
        """
        collection = self._get_loaded_collection_by_id(collectionID)
        if collection is None:
            return None
        if not self._matches_withdrawn_scope(self.isCollectionWithdrawn(collectionID)):
            return None
        return collection

    def getBiobankById(self, biobankId: str, raise_on_missing: bool = False) -> Optional[dict[str, Any]]:
        """Return a biobank by id.

        Args:
            biobankId: Identifier to search in snapshot order.
            raise_on_missing: Raise rather than log and return ``None`` for an
                absent or scope-hidden biobank.

        Returns:
            Shared mapping for the first matching biobank that passes the
            configured withdrawal scope, or ``None``. Callers must treat the
            mapping as read-only.

        Raises:
            KeyError: If no visible matching biobank exists and requested.
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

    def getLoadedBiobankById(
        self,
        biobankId: str,
        raise_on_missing: bool = False,
    ) -> Optional[dict[str, Any]]:
        """Return a loaded biobank by id, ignoring the current withdrawn scope.

        Args:
            biobankId: Identifier to resolve without withdrawal filtering.
            raise_on_missing: Raise rather than log and return ``None`` when
                the biobank is not loaded.

        Returns:
            Shared mapping regardless of configured withdrawal scope, or
            ``None``. Callers must treat the mapping as read-only.

        Raises:
            KeyError: If the biobank is not loaded and requested.
        """
        biobank = self._get_loaded_biobank_by_id(biobankId)
        if biobank is not None:
            return biobank
        if raise_on_missing:
            raise KeyError(f"Biobank {biobankId!r} not found in loaded directory snapshot.")
        log.warning("Biobank %r not found in loaded directory snapshot.", biobankId)
        return None

    def getBiobanksCount(self):
        """Return the number of loaded biobanks.

        Returns:
            Count of ``getBiobanks()``, after configured withdrawal filtering.
        """
        return len(self.getBiobanks())

    @staticmethod
    def _extract_country_code(value) -> str:
        """Return a country/staging code from a scalar or EMX-style wrapper.

        Args:
            value: Scalar country value or an EMX wrapper containing ``id``.

        Returns:
            Stripped, upper-case code; null becomes ``""``.
        """
        if isinstance(value, dict):
            value = value.get("id", "")
        return str(value).strip().upper() if value is not None else ""

    def getBiobankNN(self, biobankID: str):
        """Return the node/staging-area code for a biobank id.

        Args:
            biobankID: Identifier of an existing biobank graph node.

        Returns:
            Staging-area prefix encoded in the ID when present, otherwise the
            biobank's normalized reported country. No visibility filtering.
        """
        biobank = self.directoryGraph.nodes[biobankID]['data']
        staging_area = NNContacts.extract_staging_area(biobankID)
        if staging_area:
            return staging_area
        return self._extract_country_code(biobank.get('country'))

    def getBiobankCountry(self, biobankID: str):
        """Return the reported country code for a biobank id.

        Args:
            biobankID: Identifier of an existing biobank graph node.

        Returns:
            Normalized reported country, irrespective of staging area or scope.
        """
        biobank = self.directoryGraph.nodes[biobankID]['data']
        return self._extract_country_code(biobank.get('country'))

    def getCollections(self):
        """Return loaded collections in snapshot order after configured scope filtering.

        Returns:
            New list of shared collection mappings that callers must treat as
            read-only. ``only_withdrawn_entities`` selects effectively withdrawn
            collections, ``include_withdrawn_entities`` selects both states, and
            the default excludes explicit, owner-biobank, and ancestor withdrawals.
        """
        return [
            collection for collection in self.collections
            if self._matches_withdrawn_scope(self.isCollectionWithdrawn(collection['id']))
        ]

    def getLoadedCollections(self) -> list[dict[str, Any]]:
        """Return a shallow list copy of collections without scope filtering.

        Returns:
            New outer list with the original shared collection mappings; callers
            must not mutate those mappings.
        """
        return list(self.collections)

    def getCollectionById(self, collectionId: str, raise_on_missing: bool = False) -> Optional[dict[str, Any]]:
        """Return a collection by id.

        Args:
            collectionId: Identifier to search in snapshot order.
            raise_on_missing: Raise rather than log and return ``None`` for an
                absent or scope-hidden collection.

        Returns:
            Shared mapping for the first matching collection that passes
            effective withdrawal filtering, or ``None``. Callers must treat
            the mapping as read-only.

        Raises:
            KeyError: If no visible matching collection exists and requested.
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

    def getLoadedCollectionById(
        self,
        collectionId: str,
        raise_on_missing: bool = False,
    ) -> Optional[dict[str, Any]]:
        """Return a loaded collection by id, ignoring the current withdrawn scope.

        Args:
            collectionId: Identifier to search without withdrawal filtering.
            raise_on_missing: Raise rather than log and return ``None`` when
                no loaded collection matches.

        Returns:
            Shared collection mapping regardless of configured scope, or
            ``None``. Callers must treat the mapping as read-only.

        Raises:
            KeyError: If the collection is not loaded and requested.
        """
        for collection in self.collections:
            if collection['id'] == collectionId:
                return collection
        if raise_on_missing:
            raise KeyError(f"Collection {collectionId!r} not found in loaded directory snapshot.")
        log.warning("Collection %r not found in loaded directory snapshot.", collectionId)
        return None

    def getCollectionsCount(self):
        """Return the number of loaded collections.

        Returns:
            Count of ``getCollections()``, after effective withdrawal filtering.
        """
        return len(self.getCollections())

    def getCollectionBiobankId(self, collectionID: str):
        """Return the parent biobank id of the given collection id.

        Args:
            collectionID: Identifier of an existing collection graph node.

        Returns:
            Biobank ID in the collection's ownership metadata; no scope check.
        """
        collection = self.directoryGraph.nodes[collectionID]['data']
        return collection['biobank']['id']

    def getParentBiobank(self, collectionID: str, raise_on_missing: bool = False) -> Optional[dict[str, Any]]:
        """Return the visible parent biobank for a collection.

        Args:
            collectionID: Loaded collection identifier whose owner is resolved.
            raise_on_missing: Raise instead of logging and returning ``None``
                for missing or scope-unavailable entities.

        Returns:
            Shared visible parent-biobank mapping. It first validates the child
            and owner against the full loaded snapshot, then applies the current
            scope to both child and parent.

        Raises:
            KeyError: If the collection or parent is unavailable and requested.
            ValueError: If graph data or ownership metadata is malformed.
        """
        if (not self.directoryGraph.has_node(collectionID)
                or not any(item['id'] == collectionID for item in self.collections)):
            if raise_on_missing:
                raise KeyError(f"Collection {collectionID!r} is not present in the loaded directory snapshot.")
            log.warning("Collection %r is not present in the loaded directory snapshot.", collectionID)
            return None
        collection = self.directoryGraph.nodes[collectionID].get("data")
        if not isinstance(collection, dict):
            raise ValueError(f"Collection {collectionID!r} has malformed graph data.")
        owner = collection.get("biobank")
        if not isinstance(owner, dict) or not isinstance(owner.get("id"), str) or not owner["id"].strip():
            raise ValueError(f"Collection {collectionID!r} has malformed biobank ownership metadata.")
        biobank_id = owner["id"]
        loaded_biobank = self._get_loaded_biobank_by_id(biobank_id)
        if loaded_biobank is None:
            reason = "not present in the loaded directory snapshot"
            if raise_on_missing:
                raise KeyError(f"Parent biobank {biobank_id!r} of collection {collectionID!r} is {reason}.")
            log.warning("Parent biobank %r of collection %r is %s.", biobank_id, collectionID, reason)
            return None
        if self._get_visible_collection_by_id(collectionID) is None:
            if raise_on_missing:
                raise KeyError(f"Collection {collectionID!r} is unavailable in the configured scope.")
            log.warning("Collection %r is unavailable in the configured scope.", collectionID)
            return None
        biobank = self.getBiobankById(biobank_id)
        if biobank is not None:
            return biobank
        reason = "unavailable in the configured scope"
        if raise_on_missing:
            raise KeyError(f"Parent biobank {biobank_id!r} of collection {collectionID!r} is {reason}.")
        log.warning("Parent biobank %r of collection %r is %s.", biobank_id, collectionID, reason)
        return None

    @staticmethod
    def _normalize_negotiator_scalar(value: Any) -> str:
        """Return a stripped scalar, treating null-like values as empty.

        Args:
            value: Cell value that may be null-like according to pandas.

        Returns:
            Stripped string, or ``""`` for ``None`` and pandas missing values.
        """
        return "" if value is None or pd.isna(value) else str(value).strip()

    def hasNegotiatorData(self) -> bool:
        """Return whether a Negotiator resource dataset has been loaded.

        Returns:
            Whether a representatives mapping was loaded or explicitly set.
        """
        return getattr(self, "_negotiator_resources", None) is not None

    def setNegotiatorRepresentatives(self, data: dict[str, dict[str, Any]]) -> None:
        """Normalize injected Negotiator resource mappings.

        Args:
            data: Resource-ID mapping with optional source names and an iterable
                ``representatives`` value.

        Returns:
            None. Replaces registrations, normalizes source fields, lower-cases
            emails, and records IDs without a visible parent biobank.
        """
        resources = {}
        for resource_id, row in data.items():
            resource_id = self._normalize_negotiator_scalar(resource_id)
            if not resource_id:
                continue
            emails = frozenset(
                email.strip().lower() for email in row.get("representatives", set())
                if self._normalize_negotiator_scalar(email)
            )
            resources[resource_id] = NegotiatorResource(
                resource_id,
                self._normalize_negotiator_scalar(row.get("network_name")),
                self._normalize_negotiator_scalar(row.get("biobank_name")),
                self._normalize_negotiator_scalar(row.get("resource_name")),
                emails,
            )
        unmatched = tuple(sorted(
            resource_id for resource_id in resources
            if self.getParentBiobank(resource_id) is None
        ))
        self._negotiator_resources = resources
        self._negotiator_unmatched_resource_ids = unmatched

    def _require_negotiator_data(self) -> dict[str, NegotiatorResource]:
        """Return loaded Negotiator data or raise a clear state error.

        Returns:
            The internal resource mapping; callers must not mutate it.

        Raises:
            RuntimeError: If no representatives dataset has been loaded.
        """
        resources = getattr(self, "_negotiator_resources", None)
        if resources is None:
            raise RuntimeError("Negotiator data have not been loaded.")
        return resources

    def getCollectionNegotiatorRepresentatives(self, collection_id: str) -> frozenset[str]:
        """Return direct normalized representatives for a visible collection.

        Args:
            collection_id: Collection whose direct registration is requested.

        Returns:
            Immutable, lower-cased direct emails for a visible collection. Parent
            or biobank-derived advisory assignments are intentionally excluded.
        """
        resources = self._require_negotiator_data()
        if self.getParentBiobank(collection_id) is None:
            return frozenset()
        resource = resources.get(collection_id)
        return resource.representatives if resource else frozenset()

    def getNegotiatorResources(self) -> dict[str, NegotiatorResource]:
        """Return a defensive mapping of normalized resource registrations.

        Returns:
            Shallow copy of the resource-ID mapping; immutable resource values
            are shared.
        """
        return dict(self._require_negotiator_data())

    def getUnmatchedNegotiatorResourceIds(self) -> tuple[str, ...]:
        """Return normalized resource IDs absent from the visible Directory scope.

        Returns:
            Sorted tuple captured when registrations were loaded. It is not
            recomputed after a later scope change.
        """
        self._require_negotiator_data()
        return tuple(getattr(self, "_negotiator_unmatched_resource_ids", ()))

    def loadNegotiatorRepresentatives(self, path: str) -> None:
        """Load and normalize the current Negotiator representatives XLSX.

        Args:
            path: XLSX workbook containing the required representatives columns.

        Returns:
            None. Reads the first worksheet through pandas and replaces the
            current direct-registration state.
        """
        table = pd.read_excel(path)
        self._loadNegotiatorRepresentativesTable(
            table,
            source_name=f"Negotiator representatives workbook {str(path)!r}",
        )

    def loadNegotiatorOrphansReport(self, path: str) -> None:
        """Load direct registrations from an orphan-export workbook.

        Args:
            path: Orphan-export XLSX workbook containing the canonical
                ``negotiator_collection_stats`` worksheet.

        Returns:
            None. Imports only direct registration columns from that worksheet;
            advisory auto-assignment sheets are not read.

        Raises:
            ValueError: If the canonical worksheet is absent.
        """
        with pd.ExcelFile(path) as workbook:
            if NEGOTIATOR_ORPHANS_SHEET not in workbook.sheet_names:
                raise ValueError(
                    f"Negotiator orphan report {str(path)!r} has no "
                    f"{NEGOTIATOR_ORPHANS_SHEET!r} worksheet."
                )
            table = pd.read_excel(workbook, sheet_name=NEGOTIATOR_ORPHANS_SHEET)
        self._loadNegotiatorRepresentativesTable(
            table,
            source_name=(
                f"Negotiator orphan report {str(path)!r} worksheet "
                f"{NEGOTIATOR_ORPHANS_SHEET!r}"
            ),
        )

    def _loadNegotiatorRepresentativesTable(
        self,
        table: pd.DataFrame,
        source_name: str,
    ) -> None:
        """Normalize a validated representative table into Directory state.

        Args:
            table: DataFrame with the required Negotiator source columns.
            source_name: Human-readable source label for validation errors.

        Returns:
            None. Groups repeated resources, combines direct representative
            emails, and delegates final normalization to the setter.

        Raises:
            ValueError: If a required source column is missing.
        """
        missing = [
            column
            for column in NEGOTIATOR_REPRESENTATIVE_COLUMNS
            if column not in table.columns
        ]
        if missing:
            raise ValueError(
                f"{source_name} is missing required columns: " + ", ".join(missing)
            )
        records: dict[str, dict[str, Any]] = {}
        for _, row in table.iterrows():
            resource_id = self._normalize_negotiator_scalar(row["resource_source_id"])
            if not resource_id:
                log.warning("Negotiator row without resource_source_id skipped.")
                continue
            current = records.setdefault(resource_id, {"representatives": set()})
            for field in ("network_name", "biobank_name", "resource_name"):
                value = self._normalize_negotiator_scalar(row[field])
                if value and current.get(field) and current[field] != value:
                    log.warning("Negotiator resource %s has conflicting metadata for %s; retaining first value.", resource_id, field)
                elif value:
                    current[field] = value
            current["representatives"].update(
                email.strip().lower() for email in self._normalize_negotiator_scalar(row["representatives_emails"]).split(";") if email.strip()
            )
        self.setNegotiatorRepresentatives(records)

    def getBiobankNegotiatorCoverage(self, biobank_id: str) -> NegotiatorCoverage:
        """Return actual direct Negotiator coverage for one visible biobank.

        Args:
            biobank_id: Visible biobank identifier to look up in computed coverage.

        Returns:
            Coverage record from ``getNegotiatorCoverage()``.

        Raises:
            KeyError: If the biobank is not visible in the configured scope.
        """
        return self.getNegotiatorCoverage()[biobank_id]

    def getNegotiatorCoverage(self) -> dict[str, NegotiatorCoverage]:
        """Return actual direct representative coverage for visible biobanks.

        Returns:
            New mapping in visible-biobank snapshot order. Coverage counts only
            visible child collections and their direct loaded registrations.
        """
        self._require_negotiator_data()
        result = {}
        for biobank in self.getBiobanks():
            collection_ids = [c["id"] for c in self.getCollections() if c["biobank"]["id"] == biobank["id"]]
            represented = sum(bool(self.getCollectionNegotiatorRepresentatives(cid)) for cid in collection_ids)
            status = "no_collections" if not collection_ids else "fully" if represented == len(collection_ids) else "missing" if represented == 0 else "partially"
            result[biobank["id"]] = NegotiatorCoverage(biobank["id"], len(collection_ids), represented, len(collection_ids) - represented, status)
        return result

    def getCollectionContact(self, collectionID: str):
        """Return primary contact record for a collection id.

        Args:
            collectionID: Existing collection graph-node identifier.

        Returns:
            Shared primary contact mapping referenced by the collection. This
            lookup does not apply withdrawal filtering or a fallback contact.
        """
        collection = self.directoryGraph.nodes[collectionID]['data']
        return self.contactHashmap[collection['contact']['id']]

    def getBiobankContact(self, biobankID: str):
        """Return primary contact record for a biobank id.

        Args:
            biobankID: Existing biobank graph-node identifier.

        Returns:
            Shared primary contact mapping referenced by the biobank, without
            scope filtering or fallback handling.
        """
        biobank = self.directoryGraph.nodes[biobankID]['data']
        return self.contactHashmap[biobank['contact']['id']]

    def isTopLevelCollection(self, collectionID: str):
        """Return True when collection has no parent_collection pointer.

        Args:
            collectionID: Existing collection graph-node identifier.

        Returns:
            Whether the collection has no ``parent_collection`` key; scope is
            not considered.
        """
        collection = self.directoryGraph.nodes[collectionID]['data']
        return not 'parent_collection' in collection

    def isCountableCollection(self, collectionID: str, metric: str):
        """Return whether collection should be counted for a specific metric.

        Args:
            collectionID: Existing collection graph-node identifier.
            metric: ``number_of_donors`` or ``size`` to evaluate.

        Returns:
            Whether the collection has an integer metric and no ancestor with an
            integer value for that same metric. Scope is not considered.

        Raises:
            ValueError: If ``metric`` is unsupported.
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
                parent = self.getLoadedCollectionById(collection['parent_collection']['id'])
                parent_dist = 1
                while parent is not None:
                    if metric in parent and isinstance(parent[metric], int):
                        log.debug(f'Collection {collectionID} is not countable as it has countable parent {parent["id"]} (distance {parent_dist}) for metric {metric}.')
                        return False
                    if 'parent_collection' in parent:
                        parent = self.getLoadedCollectionById(parent['parent_collection']['id'])
                        parent_dist += 1
                    else:
                        if parent_dist > 1:
                            log.debug(f'Detected collection {collectionID} deeper than 1 from {parent["id"]} (distance {parent_dist}) for metric {metric}.')
                        parent = None
                return True
                

    def getCollectionNN(self, collectionID):
        """Return the node/staging-area code for a collection id.

        Args:
            collectionID: Existing collection identifier.

        Returns:
            ID-derived staging area when available, otherwise its owner's node;
            no scope filtering is applied.
        """
        staging_area = NNContacts.extract_staging_area(collectionID)
        if staging_area:
            return staging_area
        return self.getBiobankNN(self.getCollectionBiobankId(collectionID))

    def getCollectionCountry(self, collectionID: str):
        """Return the reported country code for a collection id.

        Args:
            collectionID: Existing collection graph-node identifier.

        Returns:
            Collection country when nonempty, otherwise its owner's normalized
            country; staging area and scope are not considered.
        """
        collection = self.directoryGraph.nodes[collectionID]['data']
        country = self._extract_country_code(collection.get('country'))
        if country:
            return country
        return self.getBiobankCountry(self.getCollectionBiobankId(collectionID))

    # return the whole subgraph including the biobank itself
    def getGraphBiobankCollectionsFromBiobank(self, biobankID: str):
        """Return subgraph containing a biobank and all descendant collections.

        Args:
            biobankID: Existing biobank node in the collection DAG.

        Returns:
            Structurally read-only NetworkX subgraph view of the biobank plus
            all nodes reachable in the DAG's parent-to-child direction. It is
            unfiltered; node and edge attribute mappings remain shared with the
            source graph and can still be mutated.
        """
        return self.directoryCollectionsDAG.subgraph(nx.algorithms.dag.descendants(self.directoryCollectionsDAG, biobankID).union({biobankID}))

    # return the whole subgraph including some collection
    def getGraphBiobankCollectionsFromCollection(self, collectionID: str):
        """Return subgraph containing a collection, its ancestors, and descendants.

        Args:
            collectionID: Existing collection node in the collection DAG.

        Returns:
            Structurally read-only NetworkX subgraph view containing this node,
            all DAG ancestors, and all DAG descendants. It ignores configured
            withdrawal scope; node and edge attribute mappings remain shared
            with the source graph and can still be mutated.
        """
        return self.directoryCollectionsDAG.subgraph(nx.algorithms.dag.ancestors(self.directoryCollectionsDAG, collectionID).union(nx.algorithms.dag.descendants(self.directoryCollectionsDAG, collectionID)).union({collectionID}))

    def getCollectionsDescendants(self, collectionID: str):
        """Return descendant collection ids for a collection id.

        Args:
            collectionID: Existing collection node in the collection DAG.

        Returns:
            Unordered set of all nodes reachable in the parent-to-child direction;
            no scope filtering is applied.
        """
        return nx.algorithms.dag.descendants(self.directoryCollectionsDAG, collectionID)

    def getDirectSubcollections(self, collectionID: str):
        """Return direct child collections of a collection id.

        Args:
            collectionID: Existing collection node whose DAG successors are read.

        Returns:
            New list of shared child collection mappings in DAG successor order,
            filtered by configured effective withdrawal scope. Non-collection
            successors are excluded.
        """
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
        """Return the loaded contact list without withdrawal filtering.

        Returns:
            The internal list itself, in snapshot order; callers must treat both
            the list and its mappings as read-only.
        """
        return self.contacts

    def getContact(self, contactID: str):
        """Return a contact by id.

        Args:
            contactID: Existing contact identifier.

        Returns:
            Shared contact mapping from the ID hashmap; missing IDs raise
            ``KeyError`` and no scope filtering occurs.
        """
        return self.contactHashmap[contactID]

    def getContactNN(self, contactID: str):
        """Return the node/staging-area code for a contact id.

        Args:
            contactID: Existing contact identifier.

        Returns:
            ID-derived staging area when available, otherwise the contact's
            normalized reported country.
        """
        staging_area = NNContacts.extract_staging_area(contactID)
        if staging_area:
            return staging_area
        return self.getContactCountry(contactID)

    def getContactCountry(self, contactID: str):
        """Return the reported country code for a contact id.

        Args:
            contactID: Existing contact identifier.

        Returns:
            Contact's normalized reported country, or ``""`` when unavailable.
        """
        return self._extract_country_code(self.contactHashmap[contactID].get('country'))


    def getNetworks(self):
        """Return the loaded network list without scope filtering.

        Returns:
            The internal snapshot list itself, in source order; mappings are shared.
        """
        return self.networks

    def getFacts(self):
        """Return the loaded collection-fact list without scope filtering.

        Returns:
            The internal snapshot list itself, in source order; fact mappings are shared.
        """
        return self.facts

    def getCollectionFacts(self, collectionID: str):
        """Return facts for a specific collection id.

        Args:
            collectionID: Collection ID used as the fact-map key.

        Returns:
            Shared list of fact mappings in source order, or a new empty list if
            no facts are indexed. No collection scope filtering is applied.
        """
        return self.collectionFactMap.get(collectionID, [])

    def getServices(self):
        """Return services whose owner biobank passes configured withdrawal scope.

        Returns:
            New list of shared service mappings in snapshot order. Services have
            no own withdrawal check; owner-biobank state determines visibility.
        """
        return [
            service for service in self.services
            if self._matches_withdrawn_scope(
                self.isBiobankWithdrawn(service['biobank']['id'])
            )
        ]

    def getServiceById(self, serviceID: str, raise_on_missing: bool = False) -> Optional[dict[str, Any]]:
        """Return a service by id.

        Args:
            serviceID: Identifier to resolve from the loaded service hashmap.
            raise_on_missing: Raise instead of logging and returning ``None``
                when absent or hidden by its owner biobank's scope.

        Returns:
            Shared service mapping when its owner passes configured withdrawal
            scope, otherwise ``None``.

        Raises:
            KeyError: If no visible matching service exists and requested.
        """
        if serviceID in self.serviceHashmap:
            service = self.serviceHashmap[serviceID]
            if self._matches_withdrawn_scope(self.isBiobankWithdrawn(service['biobank']['id'])):
                return service
        if raise_on_missing:
            raise KeyError(f"Service {serviceID!r} not found in loaded directory snapshot.")
        log.warning("Service %r not found in loaded directory snapshot.", serviceID)
        return None

    def getServicesCount(self):
        """Return the number of loaded services.

        Returns:
            Count of visible services from ``getServices()``.
        """
        return len(self.getServices())

    def getBiobankServices(self, biobankID: str):
        """Return services belonging to a biobank id.

        Args:
            biobankID: Existing biobank identifier whose service map is queried.

        Returns:
            Shared list of that owner's services in source order, or a new empty
            list if the biobank is hidden or has no services.
        """
        if not self._matches_withdrawn_scope(self.isBiobankWithdrawn(biobankID)):
            return []
        return self.biobankServiceMap.get(biobankID, [])

    def getServiceBiobankId(self, serviceID: str):
        """Return the parent biobank id of the given service id.

        Args:
            serviceID: Existing service graph-node identifier.

        Returns:
            Owner biobank ID from the service mapping, without scope filtering.
        """
        service = self.directoryServicesGraph.nodes[serviceID]['data']
        return service['biobank']['id']

    def getServiceBiobank(self, serviceID: str) -> Optional[dict[str, Any]]:
        """Return the parent biobank of a service id.

        Args:
            serviceID: Existing service graph-node identifier.

        Returns:
            Shared visible owner-biobank mapping, or ``None`` if its owner is
            hidden by configured withdrawal scope.
        """
        return self.getBiobankById(self.getServiceBiobankId(serviceID))

    def getServiceContact(self, serviceID: str):
        """Return primary contact record for a service id via its parent biobank.

        Args:
            serviceID: Existing service graph-node identifier.

        Returns:
            Shared primary contact of the owner biobank. This direct graph lookup
            does not apply the service's visible-scope check.
        """
        return self.getBiobankContact(self.getServiceBiobankId(serviceID))

    def getServiceNN(self, serviceID: str):
        """Return the node/staging-area code for a service id.

        Args:
            serviceID: Existing service identifier.

        Returns:
            ID-derived staging area when available, otherwise the owner biobank's
            node; no scope filtering is applied.
        """
        staging_area = NNContacts.extract_staging_area(serviceID)
        if staging_area:
            return staging_area
        return self.getBiobankNN(self.getServiceBiobankId(serviceID))

    def getServiceCountry(self, serviceID: str):
        """Return the reported country code for a service id.

        Args:
            serviceID: Existing service identifier.

        Returns:
            Owner biobank's normalized country; no scope filtering is applied.
        """
        return self.getBiobankCountry(self.getServiceBiobankId(serviceID))

    def getGraphBiobankServicesFromBiobank(self, biobankID: str):
        """Return subgraph containing a biobank and its services.

        Args:
            biobankID: Existing biobank node in the service DAG.

        Returns:
            Structurally read-only NetworkX subgraph view of the biobank and
            nodes reachable in the owner-to-service direction. It does not
            apply withdrawal filtering; node and edge attribute mappings remain
            shared with the source graph and can still be mutated.
        """
        return self.directoryServicesDAG.subgraph(
            nx.algorithms.dag.descendants(self.directoryServicesDAG, biobankID).union({biobankID})
        )

    def getStudies(self):
        """Return studies having at least one configured-scope collection membership.

        Returns:
            New list of shared study mappings in snapshot order. Membership comes
            from ``Collections.studies``; a study's own withdrawal state is not read.
        """
        visible_studies = []
        for study in self.studies:
            for collection_id in self.studyCollectionIdMap.get(study['id'], []):
                collection = self._get_visible_collection_by_id(collection_id)
                if collection is not None:
                    visible_studies.append(study)
                    break
        return visible_studies

    def getStudyById(self, studyID: str, raise_on_missing: bool = False) -> Optional[dict[str, Any]]:
        """Return a study by id when it has at least one visible associated collection.

        Args:
            studyID: Identifier to resolve from the loaded study hashmap.
            raise_on_missing: Raise instead of logging and returning ``None`` if
                absent or not connected to a visible collection.

        Returns:
            Shared study mapping only if at least one linked collection passes
            configured effective withdrawal filtering, otherwise ``None``.

        Raises:
            KeyError: If no visible matching study exists and requested.
        """
        if studyID in self.studyHashmap:
            study = self.studyHashmap[studyID]
            if any(
                self._get_visible_collection_by_id(collection_id) is not None
                for collection_id in self.studyCollectionIdMap.get(studyID, [])
            ):
                return study
        if raise_on_missing:
            raise KeyError(f"Study {studyID!r} not found in loaded directory snapshot.")
        log.warning("Study %r not found in loaded directory snapshot.", studyID)
        return None

    def getStudiesCount(self):
        """Return the number of loaded studies.

        Returns:
            Count of studies returned by ``getStudies()``.
        """
        return len(self.getStudies())

    def getCollectionStudies(self, collectionID: str):
        """Return studies associated with a collection id.

        Args:
            collectionID: Collection identifier whose ``studies`` memberships
                are queried.

        Returns:
            New list of shared study mappings in collection-membership order,
            provided the collection and each study are visible; otherwise empty.
        """
        if self._get_visible_collection_by_id(collectionID) is None:
            return []
        visible_studies = []
        for study in self.collectionStudyMap.get(collectionID, []):
            if self.getStudyById(study['id']) is not None:
                visible_studies.append(study)
        return visible_studies

    def getCollectionStudyIds(self, collectionID: str):
        """Return study ids associated with a collection id.

        Args:
            collectionID: Collection identifier passed to ``getCollectionStudies``.

        Returns:
            New list of visible study IDs in the corresponding study order.
        """
        return [study['id'] for study in self.getCollectionStudies(collectionID)]

    def getBiobankStudies(self, biobankID: str):
        """Return studies associated with collections of a biobank id.

        Args:
            biobankID: Biobank identifier whose child-collection memberships are
                queried.

        Returns:
            New list of shared visible study mappings, unique per biobank in the
            first encountered collection-membership order; empty for hidden owner.
        """
        if not self._matches_withdrawn_scope(self.isBiobankWithdrawn(biobankID)):
            return []
        visible_studies = []
        for study in self.biobankStudyMap.get(biobankID, []):
            if self.getStudyById(study['id']) is not None:
                visible_studies.append(study)
        return visible_studies

    def getBiobankStudyIds(self, biobankID: str):
        """Return study ids associated with collections of a biobank id.

        Args:
            biobankID: Biobank identifier passed to ``getBiobankStudies``.

        Returns:
            New list of visible study IDs in the corresponding study order.
        """
        return [study['id'] for study in self.getBiobankStudies(biobankID)]

    def getStudyCollectionIds(self, studyID: str):
        """Return visible collection ids associated with a study id.

        Args:
            studyID: Study identifier which must resolve as visible.

        Returns:
            New list of visible collection IDs in ``Collections.studies``
            discovery order.

        Raises:
            KeyError: If the study is absent or lacks a visible collection.
        """
        self.getStudyById(studyID, raise_on_missing=True)
        collection_ids = []
        for collection_id in self.studyCollectionIdMap.get(studyID, []):
            if self._get_visible_collection_by_id(collection_id) is not None:
                collection_ids.append(collection_id)
        return collection_ids

    def getStudyCollections(self, studyID: str):
        """Return visible collections associated with a study id.

        Args:
            studyID: Visible study identifier passed to ``getStudyCollectionIds``.

        Returns:
            New list of shared visible collection mappings in membership order.
        """
        return [
            self._get_visible_collection_by_id(collection_id)
            for collection_id in self.getStudyCollectionIds(studyID)
        ]

    def getStudyBiobankIds(self, studyID: str):
        """Return visible parent biobank ids associated with a study id.

        Args:
            studyID: Visible study identifier whose collections are traversed.

        Returns:
            New de-duplicated list of owner biobank IDs, ordered by first visible
            collection membership.
        """
        biobank_ids = []
        for collection in self.getStudyCollections(studyID):
            if collection is None:
                continue
            biobank_id = collection['biobank']['id']
            if biobank_id not in biobank_ids:
                biobank_ids.append(biobank_id)
        return biobank_ids

    def getStudyCountries(self, studyID: str):
        """Return sorted visible collection countries associated with a study id.

        Args:
            studyID: Visible study identifier whose collection countries are read.

        Returns:
            Sorted list of unique normalized countries of visible linked
            collections, including ``""`` if a collection has no country.
        """
        return sorted(
            {
                self.getCollectionCountry(collection_id)
                for collection_id in self.getStudyCollectionIds(studyID)
            }
        )

    def getStudyBiobanks(self, studyID: str):
        """Resolve parent biobanks associated with a visible study's collections.

        Args:
            studyID: Visible study identifier whose owners are resolved.

        Returns:
            New list in first-membership order. Each item is the shared owner
            mapping when that biobank passes the configured withdrawal scope, or
            ``None`` when a visible collection's owner is hidden by that scope.
        """
        return [
            self.getBiobankById(biobank_id)
            for biobank_id in self.getStudyBiobankIds(studyID)
        ]

    def getStudyBiobankId(self, studyID: str) -> Optional[str]:
        """Return the single parent biobank id of a visible study's collections.

        Args:
            studyID: Visible study identifier whose unique owner is requested.

        Returns:
            The sole owner ID represented by visible linked collections,
            regardless of whether that biobank itself passes the configured
            scope; otherwise ``None`` for zero or multiple owner IDs.
        """
        biobank_ids = self.getStudyBiobankIds(studyID)
        if len(biobank_ids) == 1:
            return biobank_ids[0]
        return None

    def getStudyContacts(self, studyID: str):
        """Return unique contacts associated with the visible collections of a study.

        Args:
            studyID: Visible study identifier whose collections are traversed.

        Returns:
            New de-duplicated list of shared contacts in collection order: a
            collection primary contact first, otherwise its visible owner contact.
        """
        contacts = []
        seen_contact_ids = set()
        for collection in self.getStudyCollections(studyID):
            if collection is None:
                continue
            contact = None
            if 'contact' in collection and collection['contact'].get('id') in self.contactHashmap:
                contact = self.contactHashmap[collection['contact']['id']]
            elif 'biobank' in collection:
                biobank = self.getBiobankById(collection['biobank']['id'])
                if biobank is not None and 'contact' in biobank:
                    contact = self.contactHashmap.get(biobank['contact']['id'])
            if contact is None or contact['id'] in seen_contact_ids:
                continue
            contacts.append(contact)
            seen_contact_ids.add(contact['id'])
        return contacts

    def getStudyContact(self, studyID: str) -> Optional[dict[str, Any]]:
        """Return the single unique study contact, or None when ambiguous.

        Args:
            studyID: Visible study identifier whose contacts are collected.

        Returns:
            The sole shared contact only when exactly one unique contact is found;
            otherwise ``None``.
        """
        contacts = self.getStudyContacts(studyID)
        if len(contacts) == 1:
            return contacts[0]
        return None

    def getGraphBiobankStudiesFromBiobank(self, biobankID: str):
        """Return subgraph containing a biobank, descendant collections, and linked studies.

        Args:
            biobankID: Existing biobank node in the study DAG.

        Returns:
            Structurally read-only NetworkX subgraph view of the biobank and
            every node reachable in the owner-to-child/study direction. It
            ignores configured withdrawal scope; node and edge attribute
            mappings remain shared with the source graph and can still be mutated.
        """
        return self.directoryStudiesDAG.subgraph(
            nx.algorithms.dag.descendants(self.directoryStudiesDAG, biobankID).union({biobankID})
        )

    def getGraphBiobankStudiesFromStudy(self, studyID: str):
        """Return subgraph containing a study, its associated collections, and ancestor biobanks.

        Args:
            studyID: Existing study node in the study DAG.

        Returns:
            Structurally read-only NetworkX subgraph view of the study and every
            ancestor in the reverse owner/membership direction. It ignores
            configured withdrawal scope; node and edge attribute mappings remain
            shared with the source graph and can still be mutated.
        """
        return self.directoryStudiesDAG.subgraph(
            nx.algorithms.dag.ancestors(self.directoryStudiesDAG, studyID).union({studyID})
        )

    def getNetworkNN(self, networkID: str):
        """Return the node/staging-area code for a network id.

        Args:
            networkID: Existing network graph-node identifier.

        Returns:
            ID-derived staging area when present. Otherwise, a present ``country``
            key is returned after normalization even when empty; only an absent
            country key permits primary-contact fallback, and a network lacking
            both keys falls back to ``"EU"``. No scope filtering is applied.
        """
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
        """Return the reported country code for a network id when present.

        Args:
            networkID: Existing network graph-node identifier.

        Returns:
            A present network ``country`` value normalized even when empty; only
            an absent country key permits primary-contact fallback. Returns
            ``""`` when neither key exists.
        """
        network = self.networkGraph.nodes[networkID]['data']
        if 'country' in network:
            return self._extract_country_code(network['country'])
        if 'contact' in network:
            return self.getContactCountry(network['contact']['id'])
        return ""

    @staticmethod
    def getEntityAttributeId(value: Any):
        """Return the canonical identifier-like value of an entity attribute.

        Args:
            value: Scalar, entity-reference mapping, ``None``, or floating-point
                NaN. Other pandas missing sentinels are treated as ordinary scalars.

        Returns:
            Mapping ``id`` preferentially, then ``name``; original scalar
            otherwise; ``None`` for ``None``, floating-point NaN, or an
            unidentifiable mapping.
        """
        if value is None:
            return None
        if isinstance(value, float) and pd.isna(value):
            return None
        if isinstance(value, dict):
            if value.get('id') not in (None, ''):
                return value['id']
            if value.get('name') not in (None, ''):
                return value['name']
            return None
        return value

    @staticmethod
    def getListOfEntityAttributeIds(entity, key: str):
        """Return normalized identifier-like values from an entity attribute list.

        Args:
            entity: Mapping that may hold scalar or list-valued attributes.
            key: Attribute key to normalize.

        Returns:
            New list preserving source order, with missing/empty normalized
            values removed. A present scalar is treated as one element.
        """
        if key not in entity:
            return []
        values = entity[key]
        if not isinstance(values, list):
            values = [values]
        normalized = []
        for value in values:
            normalized_value = Directory.getEntityAttributeId(value)
            if normalized_value not in (None, ''):
                normalized.append(normalized_value)
        return normalized

    @staticmethod
    def getListOfEntityAttributes(entity, key: str):
        """Return list value of an entity attribute when present, else empty list.

        Args:
            entity: Mapping that may hold a list-valued attribute.
            key: Attribute key to retrieve.

        Returns:
            Shallow new list of the attribute elements, or a new empty list when
            absent. A present non-iterable still follows Python iteration rules.
        """
        return [ element for element in entity[key] ] if key in entity else []
