"""Run geocoding orchestration offline while protecting developer artifacts."""

import json
import logging
from pathlib import Path

import pytest

import geocoding


class FakeDirectory:
    """Expose invented biobanks including one explicitly excluded country."""

    def __init__(self, **kwargs):
        """Accept normal Directory construction without performing live access.

        Args:
            **kwargs: Shared Directory CLI configuration, intentionally not connected externally.
        """

    def getBiobanks(self):
        """Provide two in-scope biobanks and one INI-excluded biobank.

        Returns:
            Fresh invented source records, including numeric coordinates and missing columns.
        """
        return [{"id": "bbmri-eric:ID:ZZ_ONE", "name": "First", "country": "ZZ", "longitude": 0, "latitude": 48},
                {"id": "bbmri-eric:ID:ZZ_TWO", "name": "Second", "country": "ZZ", "contact": {"id": "contact"}},
                {"id": "bbmri-eric:ID:YY_SKIP", "name": "Excluded", "country": "YY"}]

    def getContacts(self):
        """Provide organization-only coarse address context for the second biobank.

        Returns:
            Invented contact list with no personal fields or street address.
        """
        return [{"id": "contact", "city": "Example", "country": "ZZ"}]

    def getCollections(self):
        """Avoid collection-derived properties in this small orchestration fixture.

        Returns:
            Empty collection list.
        """
        return []

    def getBiobankNN(self, biobank_id):
        """Return staging grouping for invented fixture IDs.

        Args:
            biobank_id: Canonical ID whose fixture node is requested.

        Returns:
            YY for the excluded fixture, otherwise ZZ.
        """
        return "YY" if "YY_" in biobank_id else "ZZ"


def config_file(tmp_path, overrides="", filters=""):
    """Write a small complete INI for isolated command execution.

    Args:
        tmp_path: Temporary configuration/output directory.
        overrides: Optional legacy coordinate settings used to test migration errors.
        filters: Optional dataset selection conditions.

    Returns:
        Path to the invented INI with YY excluded by node.
    """
    path = tmp_path / "geocoding.config"
    path.write_text("[Biobank config]\nbiobankProperties=biobankID,biobankName,biobankType,biobankSize\n"
        f"[Override biobank position]\n{overrides}\n[Skip biobank]\n[Skip ID]\n"
        "[Skip country]\nbiobanksCountrySkip=YY\n[Filter dataset exact string]\nsearchExactString=No\n"
        f"[Filter dataset]\n{filters}\n")
    return path


@pytest.mark.parametrize("verbosity", [[], ["-v"], ["-d"]])
def test_cli_scope_review_and_summary(tmp_path, monkeypatch, caplog, verbosity):
    """Preserve INI exclusions through output, research selection and statistics.

    Args:
        tmp_path: Isolated input/cache/report directory.
        monkeypatch: Replace Directory and the live geocoder with offline doubles.
        caplog: Captured log records verifying summary visibility.
        verbosity: Default, verbose or debug flags under test.

    Returns:
        None. Outputs contain only selected biobanks and summaries follow verbosity.
    """
    monkeypatch.setattr(geocoding, "Directory", FakeDirectory)
    monkeypatch.setattr(geocoding, "safe_geocode", lambda query: ("not_found", None))
    monkeypatch.setenv("DIRECTORY_CACHE_ROOT", str(tmp_path))
    caplog.set_level(logging.DEBUG)
    prefix, review = tmp_path / "points", tmp_path / "research.md"
    assert geocoding.main([*verbosity, str(config_file(tmp_path)), "-o", str(prefix),
                          "--output-institution-review", str(review)]) == 0
    features = json.loads(prefix.with_suffix(".geojson").read_text())["features"]
    assert [f["properties"]["biobankID"] for f in features] == ["bbmri-eric:ID:ZZ_ONE"]
    assert features[0]["geometry"]["coordinates"] == [0.0, 48.0]
    assert "ZZ_TWO" in review.read_text() and "YY_SKIP" not in review.read_text()
    assert ("Biobanks considered: 2" in caplog.text) == bool(verbosity)


def test_cli_rejects_bad_inputs_and_output_aliases_before_directory(tmp_path, monkeypatch):
    """Make input errors side-effect free and preserve existing report bytes.

    Args:
        tmp_path: Temporary files including an input/output alias and legacy INI.
        monkeypatch: Fail immediately if Directory construction happens too early.

    Returns:
        None. Bad JSON, aliases and legacy positions fail without loading Directory.
    """
    def forbidden(**kwargs):
        """Reject premature live Directory construction.

        Args:
            **kwargs: Ignored construction configuration proving the call occurred.

        Returns:
            None. The assertion prevents any unapproved live access.

        Raises:
            AssertionError: Always, because these scenarios must fail first.
        """
        raise AssertionError("Directory must not be loaded")

    monkeypatch.setattr(geocoding, "Directory", forbidden)
    cfg = config_file(tmp_path)
    assert geocoding.main([str(cfg), "--manual-overrides", str(tmp_path / "absent.json")]) == 2
    alias = tmp_path / "same.geojson"
    alias.write_text(cfg.read_text())
    assert geocoding.main([str(alias), "-o", str(tmp_path / "same")]) == 2
    before = alias.read_bytes()
    assert before == cfg.read_bytes()
    cfg = config_file(tmp_path, overrides="First=1,2")
    assert geocoding.main([str(cfg)]) == 2


def test_publication_rolls_back_second_replace_failure(tmp_path, monkeypatch):
    """Retain both old products if publication fails after replacing the first.

    Args:
        tmp_path: Existing synthetic output files and their sibling stages.
        monkeypatch: Inject a failure during the second publication replace.

    Returns:
        None. Existing products are restored rather than leaving mixed generations.
    """
    first, second = tmp_path / "first", tmp_path / "second"
    first.write_bytes(b"old first")
    second.write_bytes(b"old second")
    original = geocoding.os.replace
    calls = []

    def replace(source, target):
        """Fail only the second publication replace, permitting subsequent rollback.

        Args:
            source: Temporary stage or backup being promoted.
            target: Report path being replaced.

        Returns:
            None. Performs the real replacement except at the injected failure.

        Raises:
            OSError: On the second operation only.
        """
        calls.append(target)
        if len(calls) == 2:
            raise OSError("injected publication failure")
        original(source, target)

    monkeypatch.setattr(geocoding.os, "replace", replace)
    with pytest.raises(OSError):
        geocoding.publish_outputs({first: b"new first", second: b"new second"})
    assert first.read_bytes() == b"old first" and second.read_bytes() == b"old second"


def test_cli_aliases_and_help():
    """Keep argument aliases hidden while exposing the canonical shared interface.

    Returns:
        None. Legacy spellings parse but canonical options appear in ordered help.
    """
    parser = geocoding.build_cli_parser()
    args = parser.parse_args(["geocoding.config", "--outName", "old", "--print-filtered-df"])
    assert args.output_prefix == "old" and args.print_filtered_dataframe
    help_text = parser.format_help()
    assert "--output-prefix" in help_text and "--outName" not in help_text
    assert help_text.index("--verbose") < help_text.index("--output-prefix")


def test_cli_research_round_trip_and_ini_overrides_scope(tmp_path, monkeypatch, caplog):
    """Ingest research through cold/warm runs without bypassing an INI exclusion.

    Args:
        tmp_path: Isolated catalogue/cache/output directory.
        monkeypatch: Replace Directory and all potential external requests.
        caplog: Captured successful-source summary for each run.

    Returns:
        None. Current files authorize research; omitting them never resurrects the cache.
    """
    from geocoding_utils import make_location_context
    from test_geocoding_locations import catalogue, research_entry
    monkeypatch.setattr(geocoding, "Directory", FakeDirectory)
    monkeypatch.setattr(geocoding, "safe_geocode", lambda query: ("not_found", None))
    monkeypatch.setenv("DIRECTORY_CACHE_ROOT", str(tmp_path))
    caplog.set_level(logging.INFO)
    source = FakeDirectory()
    current = make_location_context(source.getBiobanks()[1], source.getContacts()[0])
    catalogue(tmp_path, [research_entry(current)])
    catalogue(tmp_path, [{"biobank_id": "bbmri-eric:ID:YY_SKIP", "policy": "always",
        "status": "resolved", "longitude": 10, "latitude": 40, "explanation": "Excluded"}], "manual_overrides")
    common = ["-v", str(config_file(tmp_path)), "-o", str(tmp_path / "points"),
              "--manual-overrides", str(tmp_path / "manual_overrides.json")]
    research = ["--institution-resolutions", str(tmp_path / "institution_resolutions.json")]
    for run in range(2):
        assert geocoding.main(common + research) == 0
        assert "AI-assisted institution resolution: 1 biobanks" in caplog.text
        assert len(json.loads((tmp_path / "points.geojson").read_text())["features"]) == 2
        caplog.clear()
    assert geocoding.main(common) == 0
    assert len(json.loads((tmp_path / "points.geojson").read_text())["features"]) == 1


def test_failed_rollback_retains_recovery_copy(tmp_path, monkeypatch):
    """Do not delete the last original-byte backup when filesystem rollback fails.

    Args:
        tmp_path: Existing output products and temporary recovery-copy directory.
        monkeypatch: Inject publication and subsequent restoration failures.

    Returns:
        None. Recovery bytes survive and the error identifies their retained location.
    """
    first, second = tmp_path / "first", tmp_path / "second"
    first.write_bytes(b"original first")
    second.write_bytes(b"original second")
    original, calls = geocoding.os.replace, []

    def replace(source, target):
        """Fail publication and rollback while permitting the initial replacement.

        Args:
            source: Stage or original-byte backup being promoted.
            target: Existing output path.

        Returns:
            None. Executes only the first real promotion.

        Raises:
            OSError: During second publication and subsequent rollback operations.
        """
        calls.append(target)
        if len(calls) >= 2:
            raise OSError("filesystem unavailable")
        original(source, target)

    monkeypatch.setattr(geocoding.os, "replace", replace)
    with pytest.raises(OSError, match="retained"):
        geocoding.publish_outputs({first: b"new first", second: b"new second"})
    assert any(p.read_bytes() == b"original first" for p in tmp_path.glob(".geocoding-backup-*"))


def test_unavailable_service_preserves_existing_verified_tls_retry_path(monkeypatch):
    """Keep unavailable-service retries from activating the old unreachable TLS bypass.

    Args:
        monkeypatch: Inject unavailable geocoding and suppress real retry sleeps.

    Returns:
        None. Three ordinary retries disable the service without recreating an insecure client.
    """
    class Unavailable:
        """Simulate the installed geopy unavailable-service exception hierarchy."""

        def geocode(self, query):
            """Reject each invented address query as unavailable.

            Args:
                query: Address never sent externally.

            Returns:
                None. The failure prevents a successful location.

            Raises:
                GeocoderUnavailable: Always, matching the installed service-error subtype.
            """
            raise geocoding.geopy.exc.GeocoderUnavailable("offline")

    def forbidden():
        """Detect activation of a previously unreachable replacement-client path.

        Returns:
            None. The assertion signals a TLS-policy regression.

        Raises:
            AssertionError: Always, as an existing client must only be retried here.
        """
        raise AssertionError("Do not replace the client after disabling TLS verification")

    monkeypatch.setattr(geocoding, "geolocator", Unavailable())
    monkeypatch.setattr(geocoding, "geocodingEnabled", True)
    monkeypatch.setattr(geocoding, "geocodingNextRequestMonotonic", 0)
    monkeypatch.setattr(geocoding, "_new_geolocator", forbidden)
    monkeypatch.setattr(geocoding.time, "sleep", lambda seconds: None)
    assert geocoding.safe_geocode("Invented address") == ("disabled", None)


def test_map_launchers_use_renamed_geocoding_cli():
    """Keep shell/R callers aligned with the executable and canonical output flag.

    Returns:
        None. Active launchers reference geocoding.py and the canonical prefix option.
    """
    root = Path(__file__).resolve().parents[1]
    shell = (root / "R-maps/export.sh").read_text()
    renderer = (root / "R-maps/render_pilot_maps.R").read_text()
    assert 'geocoding_script="$repo_root/geocoding.py"' in shell
    assert '"geocoding.py"' in renderer
    assert '"--output-prefix"' in renderer
    assert "geocoding_2022.py" not in shell + renderer


def test_ini_or_filters_and_explicit_name_id_exclusions(tmp_path):
    """Preserve existing OR filters and independent name/ID exclusion rules.

    Args:
        tmp_path: Isolated INI directory for combinations of selection/exclusion settings.

    Returns:
        None. Selection retains OR semantics, then applies all exclusions.
    """
    path = config_file(tmp_path, filters="name=First\ncountry=ZZ")
    config = geocoding.read_config(path)
    assert len(geocoding.select_biobanks(FakeDirectory(), config, False)) == 2
    config["Skip biobank"]["biobanksNameSkip"] = "Second"
    config["Skip ID"]["biobanksIDSkip"] = "bbmri-eric:ID:ZZ_ONE"
    assert geocoding.select_biobanks(FakeDirectory(), config, False) == []


def test_cleanup_failure_does_not_mask_retained_backup_diagnostic(tmp_path, monkeypatch):
    """Keep recovery locations visible even if abandoned-stage cleanup also fails.

    Args:
        tmp_path: Existing synthetic products and recovery files.
        monkeypatch: Inject publication, restoration and cleanup failures independently.

    Returns:
        None. The primary exception identifies retained original bytes, not just a stage filename.
    """
    first, second = tmp_path / "first", tmp_path / "second"
    first.write_bytes(b"original first")
    second.write_bytes(b"original second")
    replace_original, unlink_original, calls = geocoding.os.replace, Path.unlink, []

    def replace(source, target):
        """Fail promotion/restoration after the first successful publication.

        Args:
            source: Stage or backup being promoted.
            target: Final product path.

        Returns:
            None. Only the first replacement is performed.

        Raises:
            OSError: On publication/rollback after the first operation.
        """
        calls.append(target)
        if len(calls) > 1:
            raise OSError("publication or restoration failed")
        replace_original(source, target)

    def unlink(path, missing_ok=False):
        """Fail only stage cleanup without deleting recovery copies.

        Args:
            path: Temporary file being cleaned up.
            missing_ok: Standard pathlib missing-file cleanup behavior.

        Returns:
            None. Non-stage files use their real cleanup implementation.

        Raises:
            OSError: For any abandoned stage filename.
        """
        if path.name.startswith(".geocoding-stage-"):
            raise OSError("stage cleanup failed")
        unlink_original(path, missing_ok=missing_ok)

    monkeypatch.setattr(geocoding.os, "replace", replace)
    monkeypatch.setattr(Path, "unlink", unlink)
    with pytest.raises(OSError, match="original bytes retained at"):
        geocoding.publish_outputs({first: b"new", second: b"new"})
    assert any(p.read_bytes() == b"original first" for p in tmp_path.glob(".geocoding-backup-*"))


def test_path_aliases_include_symlinks_hardlinks_and_output_pairs(tmp_path, monkeypatch):
    """Reject all supported filesystem aliases, not just identical path spelling.

    Args:
        tmp_path: Temporary filesystem supporting local symbolic and hard links.
        monkeypatch: Simulate same-inode detection when Android Python lacks hardlink creation.

    Returns:
        None. Every input/output and output/output alias fails before writes.
    """
    source = tmp_path / "input.json"
    source.write_text("source bytes")
    symlink, hardlink = tmp_path / "symlink", tmp_path / "hardlink"
    symlink.symlink_to(source)
    if hasattr(geocoding.os, "link"):
        geocoding.os.link(source, hardlink)
    else:
        hardlink.write_text("synthetic same-inode alias")
        original_samefile = geocoding.os.path.samefile

        def samefile(first, second):
            """Model one hardlink identity while preserving real symlink behavior.

            Args:
                first: Output candidate whose identity is checked.
                second: Input or prior output against which it is compared.

            Returns:
                True for the synthetic hardlink pair or real filesystem aliases.
            """
            return {Path(first), Path(second)} == {source, hardlink} or original_samefile(first, second)

        monkeypatch.setattr(geocoding.os.path, "samefile", samefile)
    for output in (symlink, hardlink):
        with pytest.raises(ValueError, match="aliases"):
            geocoding.validate_targets([source], [output])
    with pytest.raises(ValueError, match="aliases"):
        geocoding.validate_targets([], [symlink, source])
