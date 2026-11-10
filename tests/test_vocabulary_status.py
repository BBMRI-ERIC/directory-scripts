"""Exercise dataset/service deprecation checks with synthetic references only."""

from types import SimpleNamespace

from customwarnings import DataCheckEntityType, DataCheckWarningLevel


class VocabularyDirectory:
    """Expose one collection and service with an already loaded reference context."""

    def __init__(self):
        """Initialize repeated deprecated terms and deliberately absent retired terms."""
        self._qc_vocabulary_context = {
            "guidance": None, "diagnostics": [],
            "snapshot": {"ontologies": {
                "DataCategories": [{"name": "IMAGING_DATA", "definition": "Deprecated value, select specific types."}],
                "ServiceTypes": [{"name": "old-service", "definition": "This term is deprecated."}],
            }, "schema_metadata": {"tables": [
                {"name": "Collections", "columns": [{"name": "data_categories", "columnType": "ONTOLOGY_ARRAY", "refSchemaName": "DirectoryOntologies", "refTableName": "DataCategories"}]},
                {"name": "Services", "columns": [{"name": "serviceTypes", "columnType": "REF_ARRAY", "refSchemaName": "DirectoryOntologies", "refTableName": "ServiceTypes"}]},
            ]}},
        }

    def getCollections(self):
        """Supply a repeated deprecated value and a retired value lacking current evidence.

        Returns:
            One collection record; retired values must not become invented errors.
        """
        return [{"id": "collection1", "data_categories": ["IMAGING_DATA", "IMAGING_DATA", "RETIRED"]}]

    def getServices(self):
        """Supply a service referencing a declared deprecated reference term.

        Returns:
            One service record with structured term references.
        """
        return [{"id": "service1", "biobank": {"id": "owner"}, "serviceTypes": [{"name": "old-service"}]}]

    def getCollectionNN(self, collection_id):
        """Route the selected collection through the shared Directory API.

        Args:
            collection_id: Loaded collection whose Node is requested.

        Returns:
            Fixture Node code, independent of identifier spelling.
        """
        return "CZ"

    def getServiceNN(self, service_id):
        """Route the selected service through the shared Directory API.

        Args:
            service_id: Loaded service whose Node is requested.

        Returns:
            Fixture Node code for the owning biobank.
        """
        return "EXT"

    def getServiceBiobankId(self, service_id):
        """Resolve the service's owner without guessing from its identifier.

        Args:
            service_id: Loaded service for which ownership is requested.

        Returns:
            Parent biobank identifier retained outside the service scope.
        """
        return "owner"

    def isBiobankWithdrawn(self, biobank_id):
        """Expose effective owner withdrawal for service warnings.

        Args:
            biobank_id: Owning biobank identifier.

        Returns:
            True to exercise withdrawn service reporting.
        """
        return True

    def isCollectionWithdrawn(self, collection_id):
        """Expose effective collection withdrawal for warning exports.

        Args:
            collection_id: Collection whose effective withdrawal flag is inspected.

        Returns:
            False for the fixture collection.
        """
        return False


def test_declared_deprecation_is_error_without_updates_or_duplicates():
    """Emit one actionable finding per entity/term and never for absent retired terms.

    Returns:
        None.
    """
    from checks.VocabularyStatus import VocabularyStatus
    directory = VocabularyDirectory()
    warnings = VocabularyStatus().check(directory, SimpleNamespace())
    assert len(warnings) == 2
    assert all(w.dataCheckID == "VOC:DeprecatedValue" for w in warnings)
    assert all(w.level == DataCheckWarningLevel.ERROR and not w.fix_proposals for w in warnings)
    assert warnings[0].directoryEntityType == DataCheckEntityType.COLLECTION
    assert warnings[1].directoryEntityType == DataCheckEntityType.SERVICE
    assert warnings[1].directoryEntityWithdrawn is True
    assert warnings[1].NN == "EXT"
    assert "serviceTypes" in warnings[1].message
    assert all("RETIRED" not in w.message for w in warnings)
    assert directory._qc_vocabulary_context["diagnostics"]


def test_unavailable_service_field_skips_only_service_path():
    """Retain dataset checks when the target does not implement Services.serviceTypes.

    Returns:
        None.
    """
    from checks.VocabularyStatus import VocabularyStatus
    directory = VocabularyDirectory()
    directory._qc_vocabulary_context["snapshot"]["schema_metadata"]["tables"].pop()
    warnings = VocabularyStatus().check(directory, None)
    assert len(warnings) == 1
    assert warnings[0].directoryEntityType == DataCheckEntityType.COLLECTION
    assert any("Services.serviceTypes" in text for text in directory._qc_vocabulary_context["diagnostics"])


def test_ambiguous_deprecation_wording_does_not_accuse_records():
    """Keep historical/negated prose out of ERROR classification.

    Returns:
        None.
    """
    from checks.VocabularyStatus import VocabularyStatus
    directory = VocabularyDirectory()
    directory._qc_vocabulary_context["snapshot"]["ontologies"]["DataCategories"][0]["definition"] = "Not deprecated; compatible with older values."
    warnings = VocabularyStatus().check(directory, None)
    assert len(warnings) == 1
    assert warnings[0].directoryEntityType == DataCheckEntityType.SERVICE


def test_immediate_advice_contains_conditional_options_and_questions():
    """Remain actionable when detailed Manual guidance has not yet been published.

    Returns:
        None.
    """
    from checks.VocabularyStatus import VocabularyStatus
    from vocabulary_guidance import load_guidance
    from vocabulary_status import term_fingerprint
    directory = VocabularyDirectory()
    context = directory._qc_vocabulary_context
    rows = context["snapshot"]["ontologies"]["DataCategories"]
    rows.extend({"name": name, "definition": "Specific image category"}
                for name in ("Body image", "Whole slide image", "Photo image"))
    context["guidance"] = load_guidance()
    context["guidance"]["sources"]["datasets-current"]["term_hashes"] = {row["name"]: term_fingerprint(row) for row in rows}
    action = VocabularyStatus().check(directory, None)[0].action
    for name in ("Body image", "Whole slide image", "Photo image"):
        assert name in action
    assert "actually contains" in action
    assert "Which image types are held?" in action
    assert "not yet published" in action
