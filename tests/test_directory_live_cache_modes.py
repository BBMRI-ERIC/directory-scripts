"""Test directory live cache modes behavior."""

import pytest

from directory import Directory


pytestmark = pytest.mark.live_directory


def _maybe_skip_live_tests(live_directory_enabled):
    """Skip the integration test when live access is disabled.

    Args:
        live_directory_enabled: Boolean fixture that gates live Directory integration tests.

    Returns:
        None. Skip the integration test when live access is disabled.
    """
    if not live_directory_enabled:
        pytest.skip("Live Directory tests are disabled. Re-run with --live-directory.")


def _build_live_directory(schema, purge_caches, credentials):
    """Load a real Directory snapshot with optional authentication and cache purge.

    Args:
        schema: Real Directory schema/staging area to load, such as ERIC.
        purge_caches: Whether the live-directory helper purges caches before loading.
        credentials: Optional credentials forwarded to the live Directory constructor.

    Returns:
        Initialized Directory using cached or live data; construction may perform
        network requests and write caches in the current working directory.
    """
    kwargs = {"schema": schema, "purgeCaches": purge_caches}
    if credentials["username"] and credentials["password"]:
        kwargs["username"] = credentials["username"]
        kwargs["password"] = credentials["password"]
    return Directory(**kwargs)


def test_live_directory_fresh_mode_loads_data(
    live_directory_enabled,
    live_directory_mode,
    live_directory_schema,
    live_directory_credentials,
    isolated_cache_cwd,
):
    """Verify live directory fresh mode loads data.

    Args:
        live_directory_enabled: Boolean fixture that gates live Directory integration tests.
        live_directory_mode: Configured cache mode for the live Directory integration test.
        live_directory_schema: Directory schema selected for the live integration test.
        live_directory_credentials: Credential mapping passed to the live Directory constructor.
        isolated_cache_cwd: Temporary working-directory fixture that isolates cache artifacts.

    Returns:
        None. Verifies live directory fresh mode loads data.
    """
    _maybe_skip_live_tests(live_directory_enabled)
    if live_directory_mode not in {"fresh", "both"}:
        pytest.skip("fresh mode disabled by --live-directory-mode")

    directory = _build_live_directory(
        schema=live_directory_schema,
        purge_caches=["directory"],
        credentials=live_directory_credentials,
    )

    assert directory.getBiobanksCount() > 0
    assert directory.getCollectionsCount() > 0
    assert len(directory.getContacts()) > 0
    assert len(directory.getNetworks()) > 0


def test_live_directory_cached_mode_uses_cached_snapshot(
    live_directory_enabled,
    live_directory_mode,
    live_directory_schema,
    live_directory_credentials,
    isolated_cache_cwd,
):
    """Verify live directory cached mode uses cached snapshot.

    Args:
        live_directory_enabled: Boolean fixture that gates live Directory integration tests.
        live_directory_mode: Configured cache mode for the live Directory integration test.
        live_directory_schema: Directory schema selected for the live integration test.
        live_directory_credentials: Credential mapping passed to the live Directory constructor.
        isolated_cache_cwd: Temporary working-directory fixture that isolates cache artifacts.

    Returns:
        None. Verifies live directory cached mode uses cached snapshot.
    """
    _maybe_skip_live_tests(live_directory_enabled)
    if live_directory_mode not in {"cached", "both"}:
        pytest.skip("cached mode disabled by --live-directory-mode")

    fresh_directory = _build_live_directory(
        schema=live_directory_schema,
        purge_caches=["directory"],
        credentials=live_directory_credentials,
    )
    cached_directory = _build_live_directory(
        schema=live_directory_schema,
        purge_caches=[],
        credentials=live_directory_credentials,
    )

    # Counts should match because second run reads the snapshot cached by first run.
    assert cached_directory.getBiobanksCount() == fresh_directory.getBiobanksCount()
    assert (
        cached_directory.getCollectionsCount() == fresh_directory.getCollectionsCount()
    )
    assert len(cached_directory.getContacts()) == len(fresh_directory.getContacts())
    assert len(cached_directory.getNetworks()) == len(fresh_directory.getNetworks())
