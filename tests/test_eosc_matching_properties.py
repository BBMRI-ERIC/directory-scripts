"""Property checks for EOSC identity reuse and active inventory refresh."""

from importlib import import_module

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, strategies as st

matcher = import_module("eosc-organisation-matcher")
catalogue = matcher.catalogue
group_biobanks = matcher.group_biobanks
matched_institutions = matcher.matched_institutions
new_registry = matcher.new_registry


@given(st.lists(st.booleans(), min_size=1, max_size=30))
def test_withdrawn_flags_never_leak_ids_or_multiply_institution_counts(flags):
    """Verify withdrawn flags never leak ids or multiply institution counts.

    Args:
        flags: Withdrawal-state sequence supplied to the property-based classification case.

    Returns:
        None. Verifies withdrawn flags never leak ids or multiply institution counts.
    """
    banks = [{"id": f"B{i:03}", "juridical_person": "Research University Alpha",
              "country": "BE", "withdrawn": withdrawn} for i, withdrawn in enumerate(flags)]
    orgs = catalogue([{"organisation_id": "00001", "name": "Research University Alpha",
                       "country": "Belgium", "acronym": "RUA", "membership_type": "Member",
                       "membership_status": "Active"}])
    registry = new_registry({"directory_target": "https://directory.example", "schema": "ERIC"})
    rows, counts = matched_institutions(registry, group_biobanks(banks), orgs)
    expected = [f"B{i:03}" for i, flag in enumerate(flags) if not flag]
    assert [bid for row in rows for bid in row["biobank_ids"]] == expected
    assert counts == {"Member": int(bool(expected)), "Observer": 0}


@given(st.sampled_from(["BE", "Belgium", "België", "Belgique"]),
       st.text(alphabet=" \t\n", min_size=0, max_size=8))
def test_country_and_harmless_whitespace_do_not_change_identity(country, whitespace):
    """Verify country and harmless whitespace do not change identity.

    Args:
        country: Country value varied by the parametrized identity case.
        whitespace: Whitespace variant applied to the identity input.

    Returns:
        None. Verifies country and harmless whitespace do not change identity.
    """
    def identity(name, source_country):
        """Build a normalized identity fixture for matching tests.

        Args:
            name: EOSC institution name whose whitespace/case normalization is tested.
            source_country: Source country included in the normalized identity fixture.

        Returns:
            Identity fingerprint string for a synthetic active Member, after catalogue normalization.
        """
        return catalogue([{"organisation_id": "1", "name": name, "country": source_country,
                            "acronym": "A", "membership_type": "Member", "membership_status": "Active"}])["1"]["identity_fingerprint"]
    assert identity(whitespace + "Institute Alpha" + whitespace, country) == identity("Institute Alpha", "BE")
