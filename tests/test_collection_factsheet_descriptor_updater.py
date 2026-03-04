from argparse import Namespace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "collection-factsheet-descriptor-updater.py"


def load_module():
    spec = spec_from_file_location("collection_factsheet_descriptor_updater", MODULE_PATH)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_update_collection_from_facts_reads_eric_from_configured_target(monkeypatch):
    module = load_module()
    directory_calls = []
    session_urls = []

    class DirectoryStub:
        def __init__(self, **kwargs):
            directory_calls.append(kwargs)

        def getCollectionById(self, collection_id, raise_on_missing=False):
            assert collection_id == "bbmri-eric:ID:CZ_demo:collection:col1"
            assert raise_on_missing is True
            return {"id": collection_id}

        def getCollectionFacts(self, collection_id):
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
        def __init__(self, url):
            session_urls.append(url)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def signin(self, username, password):
            assert username == "user"
            assert password == "secret"

        def get(self, *, table, schema, as_df):
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
