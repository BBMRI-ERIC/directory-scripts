import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def pytest_addoption(parser):
    """Register pytest options for optional live Directory integration tests."""
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
    config.addinivalue_line(
        "markers",
        "live_directory: tests that connect to live Directory API data.",
    )


@pytest.fixture(scope="session")
def live_directory_enabled(pytestconfig):
    return pytestconfig.getoption("--live-directory")


@pytest.fixture(scope="session")
def live_directory_schema(pytestconfig):
    return pytestconfig.getoption("--live-directory-schema")


@pytest.fixture(scope="session")
def live_directory_mode(pytestconfig):
    return pytestconfig.getoption("--live-directory-mode")


@pytest.fixture(scope="session")
def live_directory_credentials():
    """Return optional credentials for live Directory tests."""
    username = os.getenv("DIRECTORYUSERNAME")
    password = os.getenv("DIRECTORYPASSWORD")
    if (username and not password) or (password and not username):
        pytest.skip(
            "Set both DIRECTORYUSERNAME and DIRECTORYPASSWORD, or set neither."
        )
    return {"username": username, "password": password}


@pytest.fixture
def isolated_cache_cwd(tmp_path, monkeypatch):
    """Run test in an isolated cwd so cache purges do not affect local working cache."""
    monkeypatch.chdir(tmp_path)
    return tmp_path
