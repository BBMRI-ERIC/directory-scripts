"""Configure optional live Directory tests and isolate runtime caches."""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def pytest_addoption(parser):
    """Register pytest options for optional live Directory integration tests.

    Args:
        parser: Pytest option parser that receives the repository-specific test flags.

    Returns:
        None. Registers pytest options for optional live Directory integration tests.
    """
    group = parser.getgroup("live-directory")
    group.addoption(
        "--live-directory",
        action="store_true",
        default=False,
        help="Run tests that query live data from the BBMRI Directory API.",
    )
    group.addoption(
        "--live-directory-schema",
        action="store",
        default=os.getenv("DIRECTORY_TEST_SCHEMA", "ERIC"),
        help=(
            "Schema (staging area) used by live Directory tests. "
            "Defaults to env DIRECTORY_TEST_SCHEMA or ERIC."
        ),
    )
    group.addoption(
        "--live-directory-mode",
        action="store",
        choices=("cached", "fresh", "both"),
        default=os.getenv("DIRECTORY_TEST_MODE", "both"),
        help=(
            "Cache behavior for live tests: cached, fresh, or both. "
            "Defaults to env DIRECTORY_TEST_MODE or both."
        ),
    )


def pytest_configure(config):
    """Register the live-Directory marker with Pytest.

    Args:
        config: Pytest configuration object updated by the hook.

    Returns:
        None. Register the live-Directory marker with Pytest.
    """
    config.addinivalue_line(
        "markers",
        "live_directory: tests that connect to live Directory API data.",
    )


@pytest.fixture(scope="session")
def live_directory_enabled(pytestconfig):
    """Read whether live Directory integration tests are enabled.

    Args:
        pytestconfig: Pytest configuration fixture supplying command-line test settings.

    Returns:
        True only when --live-directory was supplied; false by default.
    """
    return pytestconfig.getoption("--live-directory")


@pytest.fixture(scope="session")
def live_directory_schema(pytestconfig):
    """Read the selected schema for live Directory integration tests.

    Args:
        pytestconfig: Pytest configuration fixture supplying command-line test settings.

    Returns:
        Schema name from --live-directory-schema, defaulting to DIRECTORY_TEST_SCHEMA or ERIC.
    """
    return pytestconfig.getoption("--live-directory-schema")


@pytest.fixture(scope="session")
def live_directory_mode(pytestconfig):
    """Read the selected cache mode for live Directory integration tests.

    Args:
        pytestconfig: Pytest configuration fixture supplying command-line test settings.

    Returns:
        One of cached, fresh, or both from --live-directory-mode.
    """
    return pytestconfig.getoption("--live-directory-mode")


@pytest.fixture(scope="session")
def live_directory_credentials():
    """Return optional credentials for live Directory tests.

    Returns:
        Username/password dictionary from Directory environment variables, both None for anonymous tests; a partial pair skips the test.
    """
    username = os.getenv("DIRECTORYUSERNAME")
    password = os.getenv("DIRECTORYPASSWORD")
    if (username and not password) or (password and not username):
        pytest.skip(
            "Set both DIRECTORYUSERNAME and DIRECTORYPASSWORD, or set neither."
        )
    return {"username": username, "password": password}


@pytest.fixture
def isolated_cache_cwd(tmp_path, monkeypatch):
    """Run test in an isolated cwd so cache purges do not affect local working cache.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        The temporary Path now used as cwd; monkeypatch restores the previous cwd after the test.
    """
    monkeypatch.chdir(tmp_path)
    return tmp_path
