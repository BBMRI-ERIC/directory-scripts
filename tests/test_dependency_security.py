"""Guard the certificate-bundle security floor required for HTTPS clients."""

from pathlib import Path

from packaging.requirements import Requirement
import pytest


@pytest.mark.parametrize("version,allowed", [
    ("2025.1.31", False),
    ("2026.7.22", False),
    ("2026.10.18", False),
    ("2026.10.19", True),
    ("2027.1.1", True),
])
def test_certifi_requires_recommended_security_release(version, allowed):
    """Reject affected bundles without preventing future certificate updates.

    Args:
        version: Candidate certifi release tested against runtime requirements.
        allowed: Whether the requirement should permit the candidate release.

    Returns:
        None. Enforces the recommended GHSA-6q48-6c7w-9gw2 floor, not a year-bound pin.
    """
    requirements = [
        Requirement(line)
        for line in (Path(__file__).resolve().parents[1] / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    certifi = [requirement for requirement in requirements if requirement.name.lower() == "certifi"]
    assert len(certifi) == 1
    assert certifi[0].specifier.contains(version) is allowed
