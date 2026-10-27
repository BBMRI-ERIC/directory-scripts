"""Failure-path tests for transactional publication of combined reports."""

import importlib
import json
from pathlib import Path

import pytest


combined = importlib.import_module("survey_combined_report")


def test_concurrent_new_target_is_not_overwritten_without_permission(tmp_path, monkeypatch):
    """Recheck default new-file protection after staging before final promotion.

    Args:
        tmp_path: Isolated directory for a target created during simulated preparation.
        monkeypatch: Fixture injecting a competing writer after sibling-stage creation.

    Returns:
        None. The competing file survives and the prepared output is not published.
    """
    target = tmp_path / "report.json"
    original = combined.descriptive._stage_publication_file

    def competing_write(path, **kwargs):
        """Create a competing output after the implementation's first preflight.

        Args:
            path: Requested final target whose sibling stage is being prepared.
            **kwargs: Original text/source arguments forwarded unchanged to stage creation.

        Returns:
            Prepared sibling-stage path, leaving the new final target in place.
        """
        stage = original(path, **kwargs)
        target.write_text("concurrent user output")
        return stage

    monkeypatch.setattr(combined.descriptive, "_stage_publication_file", competing_write)
    with pytest.raises(ValueError, match="exist"):
        combined.publish_combined_outputs({"biobanks": []}, None, {"output_json": target}, {}, (), False)
    assert target.read_text() == "concurrent user output"


def test_json_only_publication_obeys_no_overwrite_and_preserves_existing_bytes(tmp_path):
    """JSON-only publication refuses replacement unless overwrite is explicit.

    Args:
        tmp_path: Isolated output directory managed by pytest.

    Returns:
        None. A refused publication leaves existing bytes unchanged.
    """
    target = tmp_path / "report.json"
    target.write_bytes(b"existing")
    payload = {"biobanks": [], "descriptive_statistics": {}}

    with pytest.raises(Exception):
        combined.publish_combined_outputs(
            payload, None, {"output_json": target}, {}, (), False,
        )

    assert target.read_bytes() == b"existing"


def test_json_only_publication_writes_canonical_payload(tmp_path):
    """A JSON-only request stages and publishes serialized combined evidence.

    Args:
        tmp_path: Isolated output directory managed by pytest.

    Returns:
        None. The target contains the full payload after successful publication.
    """
    target = tmp_path / "report.json"
    payload = {"biobanks": [], "descriptive_statistics": {}}

    combined.publish_combined_outputs(
        payload, None, {"output_json": target}, {}, (), False,
    )

    assert json.loads(target.read_text(encoding="utf-8")) == payload


def test_absent_none_targets_are_ignored_for_json_only_publication(tmp_path):
    """CLI-style target mappings may contain None for unrequested artifact paths.

    Args:
        tmp_path: Isolated output directory managed by pytest.

    Returns:
        None. Only the requested JSON target is published.
    """
    target = tmp_path / "report.json"
    payload = {"biobanks": [], "descriptive_statistics": {}}

    combined.publish_combined_outputs(
        payload, None,
        {"output_json": target, "output_tex": None, "output_pdf": None,
         "output_chart_dir": None, "output_biobank_pdf_dir": None,
         "output_match_review": None, "output_upset_r_dir": None,
         "upset_bundle_stage": None}, {}, (), False,
    )

    assert target.is_file()


def test_empty_cohort_publishes_requested_empty_dossier_directory(tmp_path):
    """An empty cohort still publishes the requested per-biobank output directory.

    Args:
        tmp_path: Isolated output directory managed by pytest.

    Returns:
        None. An empty directory is promoted without requiring a dossier document.
    """
    target = tmp_path / "dossiers"

    combined.publish_combined_outputs(
        {"biobanks": [], "descriptive_statistics": {}}, None,
        {"output_json": tmp_path / "report.json", "output_biobank_pdf_dir": target},
        {}, (), False,
    )

    assert target.is_dir()
    assert list(target.iterdir()) == []


def test_directory_promotion_failure_restores_old_directory_and_json(tmp_path, monkeypatch):
    """A chart-directory rename failure restores both earlier files and old directory.

    Args:
        tmp_path: Isolated output directory managed by pytest.
        monkeypatch: Pytest fixture injecting one chart-stage promotion failure.

    Returns:
        None. Existing JSON and directory contents remain byte-identical.
    """
    report_module = importlib.import_module("so2_descriptive_report")
    json_target = tmp_path / "report.json"
    chart_target = tmp_path / "charts"
    json_target.write_bytes(b"old-json")
    chart_target.mkdir()
    (chart_target / "old.pdf").write_bytes(b"old-chart")
    rendered = report_module.RenderedDescriptiveReport("\\begin{document}x\\end{document}", {}, {}, {})
    real_replace = combined.os.replace
    fail_once = {"enabled": True}

    def fail_chart_stage(source, destination):
        """Inject failure only when the prepared chart directory is promoted.

        Args:
            source: Prepared publication stage path.
            destination: Final public output path.

        Returns:
            Delegated rename result except for one injected promotion failure.
        """
        if (fail_once["enabled"] and Path(destination) == chart_target
                and Path(source).name.startswith(".combined-charts-")):
            fail_once["enabled"] = False
            raise OSError("injected directory rename failure")
        return real_replace(source, destination)

    monkeypatch.setattr(combined.os, "replace", fail_chart_stage)
    with pytest.raises(Exception, match="injected directory rename failure"):
        combined.publish_combined_outputs(
            {"biobanks": [], "descriptive_statistics": {}}, rendered,
            {"output_json": json_target, "output_chart_dir": chart_target}, {}, (), True,
        )

    assert json_target.read_bytes() == b"old-json"
    assert sorted(path.name for path in chart_target.iterdir()) == ["old.pdf"]
    assert (chart_target / "old.pdf").read_bytes() == b"old-chart"


def test_prepared_upset_bundle_is_copied_without_execution(tmp_path):
    """The publisher copies a controller-prepared R bundle as a directory artifact.

    Args:
        tmp_path: Isolated output and bundle-stage directory managed by pytest.

    Returns:
        None. Bundle files publish unchanged and no R execution is required.
    """
    source = tmp_path / "prepared"
    source.mkdir()
    (source / "render.R").write_text("print('prebuilt')", encoding="utf-8")
    destination = tmp_path / "published"
    combined.publish_combined_outputs(
        {"biobanks": [], "descriptive_statistics": {}}, None,
        {"output_json": tmp_path / "report.json", "output_upset_r_dir": destination,
         "upset_bundle_stage": source}, {}, (), False,
    )

    assert (destination / "render.R").read_text(encoding="utf-8") == "print('prebuilt')"


def test_final_rename_failure_restores_all_preexisting_file_bytes(tmp_path, monkeypatch):
    """A later file promotion failure rolls earlier overwritten files back.

    Args:
        tmp_path: Isolated output directory managed by pytest.
        monkeypatch: Pytest fixture intercepting exactly one final stage promotion.

    Returns:
        None. Both old files remain byte-identical after the interrupted transaction.
    """
    json_target = tmp_path / "report.json"
    review_target = tmp_path / "review.md"
    json_target.write_bytes(b"old-json")
    review_target.write_bytes(b"old-review")
    real_replace = combined.os.replace
    fail_once = {"enabled": True}

    def fail_review_stage(source, destination):
        """Fail promotion of the prepared review packet once, then delegate.

        Args:
            source: Source path supplied to os.replace.
            destination: Destination path supplied to os.replace.

        Returns:
            The delegated os.replace result unless the injected failure triggers.
        """
        if (fail_once["enabled"] and Path(destination) == review_target
                and ".so2-stage-" in Path(source).name):
            fail_once["enabled"] = False
            raise OSError("injected final rename failure")
        return real_replace(source, destination)

    monkeypatch.setattr(combined.os, "replace", fail_review_stage)
    with pytest.raises(Exception, match="injected final rename failure"):
        combined.publish_combined_outputs(
            {"biobanks": [], "descriptive_statistics": {}}, None,
            {"output_json": json_target, "output_match_review": review_target}, {}, (), True,
        )

    assert json_target.read_bytes() == b"old-json"
    assert review_target.read_bytes() == b"old-review"


def test_preparation_failure_publishes_no_requested_outputs(tmp_path, monkeypatch):
    """A dossier compilation failure occurs before any target is promoted.

    Args:
        tmp_path: Isolated output directory managed by pytest.
        monkeypatch: Pytest fixture replacing compilation with a deterministic failure.

    Returns:
        None. No JSON or dossier directory survives failed artifact preparation.
    """
    def fail_compile(tex, label, passes=2):
        """Raise at dossier compilation to prove publication has not begun.

        Args:
            tex: Standalone source supplied for compilation.
            label: Temporary document label.
            passes: Requested compiler pass count.

        Returns:
            None. This function always raises the injected failure instead of returning.
        """
        raise RuntimeError("injected dossier preparation failure")

    monkeypatch.setattr(combined, "_compile_document", fail_compile)
    json_target = tmp_path / "report.json"
    dossier_dir = tmp_path / "dossiers"
    with pytest.raises(Exception, match="injected dossier preparation failure"):
        combined.publish_combined_outputs(
            {"biobanks": [], "descriptive_statistics": {}}, None,
            {"output_json": json_target, "output_biobank_pdf_dir": dossier_dir},
            {"institute-1234567890.tex": "\\begin{document}x\\end{document}"}, (), False,
        )

    assert not json_target.exists()
    assert not dossier_dir.exists()


def test_failed_readable_publication_restores_all_previous_targets(tmp_path, monkeypatch):
    """A quantity-chart compilation failure leaves every prior target untouched.

    Args:
        tmp_path: Isolated targets containing previous published bytes.
        monkeypatch: Replaces chart compilation with a deterministic failure.

    Returns:
        None. Existing JSON, TeX and chart-directory bytes survive preparation.
    """
    from so2_descriptive_report import RenderedDescriptiveReport

    targets = {"output_json": tmp_path / "combined.json", "output_tex": tmp_path / "combined.tex",
               "output_chart_dir": tmp_path / "charts"}
    targets["output_json"].write_bytes(b"previous-json")
    targets["output_tex"].write_bytes(b"previous-tex")
    targets["output_chart_dir"].mkdir()
    (targets["output_chart_dir"] / "old.pdf").write_bytes(b"previous-chart")

    def fail_chart(tex, label, passes=2):
        """Fail before promotion of a newly generated quantity chart.

        Args:
            tex: Source TeX prepared for chart compilation.
            label: Chart key whose compilation was requested.
            passes: Requested compiler pass count.

        Returns:
            None. Raises the synthetic failure instead of returning a PDF.
        """
        raise RuntimeError("quantity chart compilation failed")

    monkeypatch.setattr(combined, "_compile_document", fail_chart)
    rendered = RenderedDescriptiveReport("readable TeX", {"quantity": "PGF"},
                                         {"quantity": "document"}, {})
    with pytest.raises(combined.CombinedPublicationError, match="quantity chart compilation failed"):
        combined.publish_combined_outputs({"biobanks": [], "descriptive_statistics": {}},
                                          rendered, targets, {}, (), True)
    assert targets["output_json"].read_bytes() == b"previous-json"
    assert targets["output_tex"].read_bytes() == b"previous-tex"
    assert (targets["output_chart_dir"] / "old.pdf").read_bytes() == b"previous-chart"
    assert list(targets["output_chart_dir"].iterdir()) == [targets["output_chart_dir"] / "old.pdf"]


def test_second_compiler_pass_preserves_previous_report_and_cleans_stages(tmp_path, monkeypatch):
    """A failed reference-resolution pass never publishes a partial report.

    Args:
        tmp_path: Isolated directory containing previous JSON, TeX and PDF files.
        monkeypatch: Injects a successful first compiler pass and failed second pass.

    Returns:
        None. Every previous artifact survives and temporary stages are removed.
    """
    from so2_descriptive_report import RenderedDescriptiveReport

    targets = {key: tmp_path / filename for key, filename in (
        ("output_json", "report.json"), ("output_tex", "report.tex"),
        ("output_pdf", "report.pdf"))}
    originals = {key: f"previous-{key}".encode() for key in targets}
    for key, target in targets.items():
        target.write_bytes(originals[key])
    calls = []

    def compiler_pass(source, directory, passes=1):
        """Produce one provisional PDF before failing reference resolution.

        Args:
            source: Temporary TeX source whose PDF is being compiled.
            directory: Temporary compilation directory owned by the publisher.
            passes: Number of compiler passes requested for this invocation.

        Returns:
            Provisional PDF path on the first invocation; later calls raise.
        """
        calls.append(directory)
        if len(calls) == 2:
            raise RuntimeError("second compiler pass failed")
        pdf = source.with_suffix(".pdf")
        pdf.write_bytes(b"partial-pdf")
        return pdf

    monkeypatch.setattr(combined.descriptive, "_run_xelatex", compiler_pass)
    rendered = RenderedDescriptiveReport("self-contained report", {}, {}, {})
    with pytest.raises(combined.CombinedPublicationError, match="second compiler pass failed"):
        combined.publish_combined_outputs(
            {"biobanks": [], "descriptive_statistics": {}}, rendered,
            targets, {}, (), True,
        )
    assert len(calls) == 2
    assert all(target.read_bytes() == originals[key] for key, target in targets.items())
    assert all(not directory.exists() for directory in calls)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["report.json", "report.pdf", "report.tex"]
