"""Test collection factsheet descriptor updater behavior."""

from argparse import Namespace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "collection-factsheet-descriptor-updater.py"


def load_module():
    """Import the fact-sheet descriptor updater without invoking its CLI.

    Returns:
        Newly executed collection-factsheet-descriptor-updater.py module for patching read/write clients.
    """
    spec = spec_from_file_location("collection_factsheet_descriptor_updater", MODULE_PATH)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_update_collection_from_facts_reads_eric_from_configured_target(monkeypatch):
    """Verify update collection from facts reads eric from configured target.

    Args:
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Verifies update collection from facts reads eric from configured target.
    """
    module = load_module()
    directory_calls = []
    session_urls = []

    class DirectoryStub:
        """Record ERIC read options and expose one male-adult plasma fact for a Czech collection.
        """
        def __init__(self, **kwargs):
            """Record Directory connection options for read-versus-write target assertions.

            Args:
                **kwargs: Directory reader options appended to directory_calls for target/authentication assertions.
            """
            directory_calls.append(kwargs)

        def getCollectionById(self, collection_id, raise_on_missing=False):
            """Return synthetic collection record selected by the requested identifier, or `None` when absent.

            Args:
                collection_id: Collection identifier whose fixture record this stub returns or omits.
                raise_on_missing: Whether the fixture lookup should raise instead of returning a missing record.

            Returns:
                The synthetic collection record selected by the requested identifier, or `None` when absent.
            """
            assert collection_id == "bbmri-eric:ID:CZ_demo:collection:col1"
            assert raise_on_missing is True
            return {"id": collection_id}

        def getCollectionFacts(self, collection_id):
            """Return synthetic fact rows associated with the requested collection.

            Args:
                collection_id: Collection identifier whose fixture fact rows this stub returns.

            Returns:
                The synthetic fact rows associated with the requested collection.
            """
            assert collection_id == "bbmri-eric:ID:CZ_demo:collection:col1"
            return [
                {
                    "id": "f1",
                    "sex": "MALE",
                    "age_range": "Adult",
                    "sample_type": "PLASMA",
                    "disease": {"name": "urn:miriam:icd:C18.1"},
                    "number_of_samples": 1,
                    "number_of_donors": 1,
                }
            ]

    class DirectorySessionStub:
        """Verify authenticated BBMRI-CZ reads and reject writes during the dry-run test.
        """
        def __init__(self, url):
            """Record Directory connection options for read-versus-write target assertions.

            Args:
                url: Directory endpoint retained by the session test double.
            """
            session_urls.append(url)

        def __enter__(self):
            """Enter the context-manager test double.

            Returns:
                The context-manager test double entered by the with statement.
            """
            return self

        def __exit__(self, exc_type, exc, tb):
            """Exit the context-manager test double.

            Args:
                exc_type: Exception class accepted by the context-manager exit hook and deliberately not suppressed.
                exc: Exception instance accepted by the context-manager exit hook and deliberately not suppressed.
                tb: Traceback accepted by the context-manager exit hook and deliberately not suppressed.

            Returns:
                False, so exceptions raised inside the with block propagate to the caller.
            """
            return False

        def signin(self, username, password):
            """Record the sign-in call on the Directory-session double.

            Args:
                username: Credential value recorded by the fake sign-in call.
                password: Credential value recorded by the fake sign-in call.

            Returns:
                None. Record the sign-in call on the Directory-session double.
            """
            assert username == "user"
            assert password == "secret"

        def get(self, *, table, schema, as_df):
            """Return DataFrame fixture returned for the requested Directory table.

            Args:
                table: Directory table whose fixture rows the fake session returns.
                schema: Schema argument accepted by the fake session without changing its fixture rows.
                as_df: Flag selecting the DataFrame-shaped fixture result expected by the caller.

            Returns:
                The DataFrame fixture returned for the requested Directory table.
            """
            assert table == "Collections"
            assert schema == "BBMRI-CZ"
            assert as_df is True
            return pd.DataFrame(
                [
                    {
                        "id": "bbmri-eric:ID:CZ_demo:collection:col1",
                        "diagnosis_available": "",
                        "materials": "",
                        "sex": "",
                        "age_low": "",
                        "age_high": "",
                        "age_unit": "",
                        "size": "",
                        "number_of_donors": "",
                    }
                ]
            )

        def save_table(self, **kwargs):
            """Record the table-save call on the Directory-session double.

            Args:
                **kwargs: Proposed table write options (including data and target schema/table); recorded or rejected without remote I/O.

            Returns:
                None. Record the table-save call on the Directory-session double.
            """
            raise AssertionError("dry-run should not save")

    monkeypatch.setattr(module, "Directory", DirectoryStub)
    monkeypatch.setattr(module, "DirectorySession", DirectorySessionStub)

    args = Namespace(
        collection_id="bbmri-eric:ID:CZ_demo:collection:col1",
        schema="BBMRI-CZ",
        verbose=False,
        debug=False,
        dry_run=True,
        force=True,
        quiet=True,
        replace_existing=False,
        directory_target="https://directory.example.org",
        directory_username="user",
        directory_password="secret",
    )

    result = module.update_collection_from_facts(args)

    assert result == module.EXIT_OK
    assert len(directory_calls) == 1
    assert directory_calls[0]["schema"] == "ERIC"
    assert directory_calls[0]["purgeCaches"] == ["directory"]
    assert directory_calls[0]["directory_url"] == "https://directory.example.org"
    assert directory_calls[0]["include_withdrawn_entities"] is True
    assert session_urls == ["https://directory.example.org"]
