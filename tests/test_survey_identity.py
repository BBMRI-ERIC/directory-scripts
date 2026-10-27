"""Conservative canonical-biobank matching and reviewed-override regression tests."""

import importlib
import json
from types import SimpleNamespace

import pytest

from survey_evidence import SourceRecord


def test_exact_and_ambiguous_identity(tmp_path):
    """Accept unique exact identities but never fuzzy or shared-contact matches.

    Args:
        tmp_path: Isolated directory holding synthetic override configuration.

    Returns:
        None. Strong and ambiguous identity signals have distinct outcomes.
    """
    module = importlib.import_module("survey_identity")
    ids = ["bbmri-eric:ID:AT_A", "bbmri-eric:ID:AT_B"]
    cat = module.IdentityCatalogue({ids[0]: {"id": ids[0], "name": "Alpha", "country": "AT"},
                                    ids[1]: {"id": ids[1], "name": "Beta", "country": "AT"}},
                                   frozenset(ids), {"unique@example.org": {ids[0]},
                                                    "shared@example.org": set(ids)})
    path = tmp_path / "overrides.json"
    path.write_text(json.dumps({"schema_version": "1", "decisions": [], "input_bindings": []}))
    overrides = module.load_match_overrides(path, {})
    for identity, expected in [({"explicit_biobank_id": "AT_A"}, "accepted"),
                               ({"email_addresses": ["unique@example.org"]}, "accepted"),
                               ({"email_addresses": ["unique@example.org"], "institution_name": "Beta"}, "review"),
                               ({"institution_name": "Alpha"}, "accepted"),
                               ({"email_addresses": ["shared@example.org"]}, "review"),
                               ({"institution_name": "Alphaa"}, "review")]:
        record = SourceRecord({"record_id": "RESP-001", "survey": "MuCP", "country": "Austria",
                               "record_type": "submission", "identity": identity})
        assert module.resolve_source_identity(record, cat, overrides).data["status"] == expected


def test_override_is_fingerprint_bound_and_national_summary_excluded(tmp_path):
    """Keep reviewed decisions reusable while rejecting changed identity evidence.

    Args:
        tmp_path: Temporary filesystem holding an explicit synthetic acceptance decision.

    Returns:
        None. A stale mapping cannot override new evidence or broadcast a national summary.
    """
    module = importlib.import_module("survey_identity")
    bid = "bbmri-eric:ID:AT_A"
    record = SourceRecord({"record_id": "RESP-001", "survey": "MuCP", "country": "AT",
                           "identity": {"institution_name": "Unrecognised"}, "record_type": "submission"})
    decision = {"survey": "MuCP", "source_record_id": "RESP-001", "action": "accept",
                "biobank_id": bid, "identity_fingerprint": module.identity_fingerprint(record),
                "reason": "Reviewed source", "reviewer": "tester", "reviewed_on": "2026-10-02"}
    path = tmp_path / "overrides.json"
    path.write_text(json.dumps({"schema_version": "1", "decisions": [decision], "input_bindings": []}))
    cat = module.IdentityCatalogue({bid: {"id": bid, "name": "Alpha", "country": "AT"}}, frozenset({bid}), {})
    overrides = module.load_match_overrides(path, {})
    assert module.resolve_source_identity(record, cat, overrides).data["method"] == "override"
    changed = SourceRecord({**dict(record.data), "identity": {"institution_name": "Changed"}})
    with pytest.raises(ValueError, match="Stale"):
        module.resolve_source_identity(changed, cat, overrides)
    national = SourceRecord({**dict(record.data), "record_id": "RESP-002", "record_type": "country_summary"})
    assert module.resolve_source_identity(national, cat, overrides).data["status"] == "excluded"


def test_scoped_override_never_broadcasts_submission_evidence():
    """Assign only the explicitly reviewed scope while retaining unassigned root diagnostics.

    Returns:
        None. A manual split never copies a national/submission-wide answer to a biobank.
    """
    module = importlib.import_module("survey_identity")
    bid = "bbmri-eric:ID:AT_A"
    record = SourceRecord({"record_id": "RESP-001", "survey": "MuCP", "country": "AT",
                           "record_type": "country_summary", "identity": {"institution_name": "National response"},
                           "scopes": [{"scope_id": "root", "kind": "submission"}, {"scope_id": "nested", "kind": "collection"}],
                           "evidence": [{"scope_id": "root", "question_id": "all"}, {"scope_id": "nested", "question_id": "local"}]})
    decision = {"survey": "MuCP", "source_record_id": "RESP-001", "scope_id": "nested", "action": "accept",
                "biobank_id": bid, "identity_fingerprint": module.identity_fingerprint(record),
                "reason": "Reviewed explicit institution", "reviewer": "tester", "reviewed_on": "2026-10-02"}
    cat = module.IdentityCatalogue({bid: {"id": bid, "country": "AT"}}, frozenset({bid}), {})
    records, resolutions = module.resolve_scoped_sources([record], cat, module.MatchOverrides({("MuCP", "RESP-001", "nested"): decision}, {}))
    selected = [r for r, d in zip(records, resolutions) if d.data["status"] == "accepted"]
    assert len(selected) == 1
    assert [item["question_id"] for item in selected[0].data["evidence"]] == ["local"]
    assert [item["question_id"] for item in records[0].data["evidence"]] == ["all"]
    assert [scope["scope_id"] for scope in records[0].data["scopes"]] == ["root"]
    decision["scope_id"] = "root"
    with pytest.raises(ValueError, match="national|summary|collection",):
        module.resolve_scoped_sources([record], cat, module.MatchOverrides({("MuCP", "RESP-001", "root"): decision}, {}))


def test_scope_quantity_indexes_follow_owned_evidence_and_keep_unknown_diagnostics():
    """Separate source-scope quantity indexes instead of copying them to every projection.

    Returns:
        None. Root/collection quantities remain owned; unlocatable entries stay
        diagnostic-only and the original immutable index is unchanged.
    """
    import survey_identity as module
    bid = "bbmri-eric:ID:AT_A"
    entries = [{"field":"B.count", "value":value, "unit":"donors", "raw_token":str(value),
                "evidence":[{"source_id":"S1","locator":locator}]}
               for value,locator in ((900,"root-count"),(100,"child-count"),(250,"unassigned"))]
    record = SourceRecord({"record_id":"R1", "survey":"MuCP", "country":"AT", "record_type":"submission",
        "identity":{}, "scopes":[{"scope_id":"root","kind":"submission"},{"scope_id":"child","kind":"collection"}],
        "evidence":[{"scope_id":scope,"question_id":"B.count","source_refs":[{"source_id":"S1","locator":locator}]}
                    for scope,locator in (("root","root-count"),("child","child-count"))],
        "metadata":{"quantity_index":entries}})
    decision = {"survey":"MuCP","source_record_id":"R1","scope_id":"child","action":"accept","biobank_id":bid,
                "identity_fingerprint":module.identity_fingerprint(record),"reason":"Invented split","reviewer":"test","reviewed_on":"2026-10-13"}
    catalogue = module.IdentityCatalogue({bid:{"id":bid,"country":"AT"}},frozenset({bid}),{})
    records,_ = module.resolve_scoped_sources([record],catalogue,module.MatchOverrides({("MuCP","R1","child"):decision},{}))
    assert [item["value"] for item in records[0].data["metadata"]["quantity_index"]]==[900]
    assert [item["value"] for item in records[1].data["metadata"]["quantity_index"]]==[100]
    assert [item["value"] for item in records[0].data["metadata"]["unassigned_quantity_index"]]==[250]
    assert [item["value"] for item in record.data["metadata"]["quantity_index"]]==[900,100,250]


def test_quantity_index_can_use_owned_collection_count_references():
    """Collection count metadata supplies ownership even without a separate text answer.

    Returns:
        None. Exact references from the original owned count retain its index entry.
    """
    from copy import deepcopy
    from survey_identity import _project_quantity_index
    ref = {"source_id":"S1","locator":"collection-count"}
    entry = {"value":100,"field":"B.count","evidence":[ref]}
    original = {"scopes":[{"scope_id":"child","metadata":{"count":{"evidence":[ref]}}}],
                "evidence":[],"metadata":{"quantity_index":[entry]}}
    projected = deepcopy(original)
    _project_quantity_index(projected,original,True)
    assert projected["metadata"]["quantity_index"]==[entry]


def test_catalogue_keeps_withdrawn_collection_contact_ownership():
    """Excluded ownership must not manufacture a unique email match in active scope.

    Returns:
        None. Ownership uses loaded parent IDs and remains ambiguous across both biobanks.
    """
    from survey_identity import build_identity_catalogue, resolve_source_identity, MatchOverrides
    ids = ["bbmri-eric:ID:AT_A", "bbmri-eric:ID:AT_B"]
    biobanks = [{"id": bid, "country": "AT"} for bid in ids]
    collections = [{"id": "c1", "contact": {"id": "p1"}}, {"id": "c2", "contact": {"id": "p1"}}]

    def loaded_collections():
        """Provide both active and withdrawn synthetic child entities.

        Returns:
            Both collections, irrespective of the configured reporting scope.
        """
        return collections

    def visible_biobanks():
        """Select only the first synthetic biobank for the report.

        Returns:
            A one-item list excluding the second owner from output, not matching evidence.
        """
        return biobanks[:1]

    def parent_id(cid):
        """Resolve actual child ownership without applying withdrawal scope.

        Args:
            cid: Synthetic collection ID whose explicit parent is requested.

        Returns:
            The corresponding loaded canonical biobank ID.
        """
        return dict(zip(["c1", "c2"], ids))[cid]

    directory = SimpleNamespace(biobanks=biobanks, contacts=[{"id": "p1", "email": "shared@example.invalid"}],
                                getLoadedCollections=loaded_collections, getBiobanks=visible_biobanks,
                                getCollectionBiobankId=parent_id)
    catalogue = build_identity_catalogue(directory)
    source = SourceRecord({"record_id": "R", "survey": "MuCP", "country": "AT", "record_type": "submission",
                           "identity": {"email_addresses": ["shared@example.invalid"]}})
    assert resolve_source_identity(source, catalogue, MatchOverrides({}, ())).data["status"] == "review"


def test_country_summary_cannot_be_accepted_by_root_override():
    """Require reviewed scope assignment instead of assigning an entire national summary.

    Returns:
        None. Broad country evidence cannot be made biobank-wide by a root mapping.
    """
    from survey_identity import identity_fingerprint, resolve_source_identity, MatchOverrides, IdentityCatalogue
    record = SourceRecord({"survey": "MuCP", "record_id": "national", "record_type": "country_summary"})
    bid = "bbmri-eric:ID:AT_TEST"
    override = {"identity_fingerprint": identity_fingerprint(record), "action": "accept", "biobank_id": bid, "reason": "Review"}
    with pytest.raises(ValueError, match="scope"):
        resolve_source_identity(record, IdentityCatalogue({bid: {}}, frozenset({bid}), {}),
                                MatchOverrides({("MuCP", "national", ""): override}, ()))
