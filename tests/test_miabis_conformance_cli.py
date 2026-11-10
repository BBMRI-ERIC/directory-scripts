"""Check the metadata-only CLI boundary and safe report publication."""

import importlib.util
from pathlib import Path


def load_cli():
    """Import the metadata-only command without running argument parsing.

    Returns:
        Module object exposing the CLI parser and callable main entry point.
    """
    path = Path(__file__).resolve().parents[1] / "directory-miabis-conformance.py"
    spec = importlib.util.spec_from_file_location("conformance_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_existing_report_is_protected_before_any_remote_read(tmp_path, monkeypatch):
    """A default invocation must not overwrite a user's existing audit report.

    Args:
        tmp_path: Isolated output directory with a sentinel report.
        monkeypatch: Pytest manager installing a forbidden network boundary.

    Returns:
        None.
    """
    module = load_cli()
    path = tmp_path / "report.json"
    path.write_text("sentinel", encoding="utf-8")

    def forbidden(**kwargs):
        """Fail if output preflight reaches metadata retrieval.

        Args:
            **kwargs: Metadata arguments, deliberately not used by this sentinel.

        Returns:
            None; always raises for an unexpected read.
        """
        raise AssertionError("remote read before overwrite protection")

    monkeypatch.setattr(module, "get_directory_metadata_snapshot", forbidden)
    assert module.main(["--output-json", str(path)]) == 2
    assert path.read_text() == "sentinel"


def test_offline_failure_is_clear_and_does_not_create_reports(tmp_path):
    """Missing offline sources must not publish an apparently successful audit.

    Args:
        tmp_path: Empty source cache and report destination directory.

    Returns:
        None.
    """
    module = load_cli()
    path = tmp_path / "report.json"
    assert module.main(["--offline", "--cache-dir", str(tmp_path / "cache"),
                        "--output-json", str(path)]) == 2
    assert not path.exists()


def test_publication_failure_restores_previous_outputs(tmp_path, monkeypatch):
    """Rollback a failed multi-report replacement without damaging old reports.

    Args:
        tmp_path: Temporary destinations holding previous report contents.
        monkeypatch: Pytest manager injecting one replacement failure.

    Returns:
        None.
    """
    import pytest
    module = load_cli()
    first, second = tmp_path / "one.json", tmp_path / "two.md"
    first.write_text("old-one")
    second.write_text("old-two")
    original = module.os.replace

    def fail_second(source, destination):
        """Simulate a failure during the second final publication.

        Args:
            source: Prepared temporary report path.
            destination: Requested final report destination.

        Returns:
            Result of replacing the first destination; second raises OSError.
        """
        if Path(destination) == second:
            raise OSError("simulated replacement failure")
        return original(source, destination)

    monkeypatch.setattr(module.os, "replace", fail_second)
    with pytest.raises(OSError):
        module.publish_reports({first: "new-one", second: "new-two"})
    assert first.read_text() == "old-one"
    assert second.read_text() == "old-two"
