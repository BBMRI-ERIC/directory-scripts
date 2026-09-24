"""Test survey so2 directory behavior."""

from argparse import Namespace
import ast
from datetime import datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json

import pytest


def write_descriptive_schema(tmp_path: Path) -> Path:
    """Write the descriptive schema fixture.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        Path to descriptive-schema.json describing the controlled Digital maturity question.
    """
    payload = {
        "schema_version": "1",
        "input": {
            "worksheet": "Survey responses",
            "alias": "SO2_2025",
            "header_row": 4,
        },
        "columns": {
            "respondent_context": ["Name of Institution", "Country"],
            "institution_column": "Name of Institution",
            "country_column": "Country",
            "administrative_exclusions": [],
            "administrative_exclusion_reasons": {},
        },
        "questions": [
            {
                "question_id": "digital_maturity",
                "column": "Digital maturity",
                "question_type": "ordinal",
                "label": "Digital maturity",
                "categories": ["Low", "High"],
            }
        ],
        "output": {"source_row_column": "source_row"},
    }
    path = tmp_path / "descriptive-schema.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def write_descriptive_form_manifest(tmp_path: Path) -> Path:
    """Write runtime JSON form metadata for the controlled question.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        Path to descriptive-form.json containing the mandatory single-choice Digital maturity field.
    """
    path = tmp_path / "descriptive-form.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "generator_version": "1",
        "survey_uid": "",
        "survey_alias": "SO2_2025",
        "source_path": "fixture.eus",
        "archive_sha256": "a" * 64,
        "active_member_sha256": "b" * 64,
        "fields": [{
            "uid": "q1", "title": "Digital maturity", "field_type": "single_choice",
            "mandatory": True, "readonly": False, "hidden": False, "position": 1,
            "choices": [], "shown_when": None, "matrix_rows": [], "matrix_columns": [],
        }],
    }), encoding="utf-8")
    return path


def write_empty_association_registry(tmp_path: Path) -> Path:
    """Write a valid registry for tests that intentionally have no association panels.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        Path to empty-association-registry.json, whose definitions list is intentionally empty.
    """
    path = tmp_path / "empty-association-registry.json"
    path.write_text(json.dumps({"schema_version": "1", "definitions": []}), encoding="utf-8")
    return path



def write_descriptive_workbook(tmp_path: Path) -> Path:
    """Write the descriptive workbook fixture.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        Path to descriptive.xlsx with one Czech institution answering High to Digital maturity.
    """
    path = tmp_path / "descriptive.xlsx"
    workbook = __import__("openpyxl").Workbook()
    sheet = workbook.active
    sheet.title = "Survey responses"
    sheet.append(["Alias", "SO2_2025"])
    sheet.append(["Export Date", datetime(2026, 3, 13, 7, 22, 45)])
    sheet.append([])
    sheet.append(["Name of Institution", "Country", "Digital maturity"])
    sheet.append(["Demo Biobank", "Czech Republic", "High"])
    workbook.save(path)
    return path


def test_describe_has_no_directory_dependency(tmp_path, monkeypatch):
    """Verify describe has no directory dependency.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Verifies describe has no directory dependency.
    """
    module = load_module()
    monkeypatch.setattr(module, "Directory", lambda *args, **kwargs: pytest.fail("Directory must not be used"))
    output_json = tmp_path / "descriptive.json"
    args = module.build_cli().parse_args([
        "describe", "-i", str(write_descriptive_workbook(tmp_path)),
        "--descriptive-schema", str(write_descriptive_schema(tmp_path)),
        "--form-json", str(write_descriptive_form_manifest(tmp_path)),
        "--association-heatmap-registry", str(write_empty_association_registry(tmp_path)),
        "-o", str(output_json),
    ])

    assert module.run_describe(args) == module.EXIT_OK
    assert json.loads(output_json.read_text(encoding="utf-8"))["payload_type"] == "so2_descriptive_statistics"


def test_describe_passes_association_heatmap_registry_provenance_and_excludes_exploratory_pairs(tmp_path, monkeypatch):
    """Describe embeds only default registry definitions unless explicitly opted in.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Describe embeds only default registry definitions unless explicitly opted in.
    """
    module = load_module()
    registry = tmp_path / "association-heatmaps.json"
    registry.write_text("{}", encoding="utf-8")
    output_json = tmp_path / "descriptive.json"
    captured = {}

    class DescriptiveStub:
        """Capture registry provenance and default/exploratory pair selection without rendering a report.
        """
        class InputError(Exception):
            """Stand in for descriptive input-validation failures caught by the CLI.
            """
            pass

        @staticmethod
        def load_descriptive_schema(_path):
            """Load the descriptive schema fixture.

            Args:
                _path: Schema JSON filename ignored by the stub; no file is read.

            Returns:
                The loaded descriptive schema used by the test.
            """
            return {}

        @staticmethod
        def load_association_heatmap_registry(_path):
            """Load the association heatmap registry fixture.

            Args:
                _path: Association-registry JSON filename ignored by the stub; no file is read.

            Returns:
                The loaded association heatmap registry used by the test.
            """
            return ()

        @staticmethod
        def load_form_manifest_structure(_path):
            """Load the form manifest structure fixture.

            Args:
                _path: EUS form-manifest JSON filename ignored by the stub; no file is read.

            Returns:
                The loaded form manifest structure used by the test.
            """
            return {}

        @staticmethod
        def read_descriptive_workbook(_path, _schema):
            """Return the controlled workbook response from the patched reader.

            Args:
                _path: Response XLSX filename ignored because the stub supplies in-memory rows.
                _schema: Descriptive schema deliberately ignored by the patched helper.

            Returns:
                The parsed descriptive workbook fixture value.
            """
            return Namespace(responses=__import__("pandas").DataFrame({
                "Digital maturity": ["High"], "source_row": [5],
            }))

        @staticmethod
        def load_association_heatmap_registry(_path):
            """Load the association heatmap registry fixture.

            Args:
                _path: Association-registry JSON filename ignored by the stub; no file is read.

            Returns:
                The loaded association heatmap registry used by the test.
            """
            return (
                Namespace(mode="default"),
                Namespace(mode="exploratory"),
            )

        @staticmethod
        def validate_descriptive_schema(_schema, _headers):
            """Validate the controlled schema through the patched validator.

            Args:
                _schema: Descriptive schema deliberately ignored by the patched helper.
                _headers: Worksheet headers deliberately ignored by the patched helper.

            Returns:
                One question stub with ID digital_maturity for association-registry validation.
            """
            return (Namespace(question_id="digital_maturity"),)

        @staticmethod
        def validate_association_definitions(definitions, _questions):
            """Validate controlled association definitions through the patched validator.

            Args:
                definitions: Association definitions submitted to the validation bypass.
                _questions: Question definitions deliberately ignored by the validation bypass.

            Returns:
                None. Validate controlled association definitions through the patched validator.
            """
            captured["validated"] = definitions

        @staticmethod
        def build_descriptive_payload(*_args, **kwargs):
            """Build the descriptive payload fixture.

            Args:
                *_args: Workbook/schema positional inputs ignored while capturing association options.
                **kwargs: Association definitions, registry hash, and provenance options observed without computing statistics.

            Returns:
                The constructed descriptive payload fixture.
            """
            captured.update(kwargs)
            return {"payload_type": "so2_descriptive_statistics"}

    monkeypatch.setattr(module, "_load_descriptive_report_module", lambda: DescriptiveStub)
    args = module.build_cli().parse_args([
        "describe", "-i", str(write_descriptive_workbook(tmp_path)),
        "--descriptive-schema", str(write_descriptive_schema(tmp_path)),
        "--form-json", str(write_descriptive_form_manifest(tmp_path)),
        "--association-heatmap-registry", str(registry), "-o", str(output_json),
    ])

    assert args.include_exploratory_association_heatmaps is False
    assert module.run_describe(args) == module.EXIT_OK
    assert [definition.mode for definition in captured["validated"]] == ["default", "exploratory"]
    assert [definition.mode for definition in captured["association_definitions"]] == ["default"]
    assert captured["association_registry_sha256"] == __import__("hashlib").sha256(
        registry.read_bytes()
    ).hexdigest()


def test_unknown_association_heatmap_registry_blocks_all_describe_publication(tmp_path):
    """An unreadable registry fails before JSON, TeX, PDF, or chart publication.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. An unreadable registry fails before JSON, TeX, PDF, or chart publication.
    """
    module = load_module()
    output_json = tmp_path / "payload.json"
    output_tex = tmp_path / "report.tex"
    output_pdf = tmp_path / "report.pdf"
    chart_dir = tmp_path / "charts"
    args = module.build_cli().parse_args([
        "describe", "-i", str(write_descriptive_workbook(tmp_path)),
        "--descriptive-schema", str(write_descriptive_schema(tmp_path)),
        "--form-json", str(write_descriptive_form_manifest(tmp_path)),
        "--association-heatmap-registry", str(tmp_path / "unknown.json"),
        "-o", str(output_json), "--output-tex", str(output_tex),
        "--output-pdf", str(output_pdf), "--output-chart-dir", str(chart_dir),
    ])

    with pytest.raises(module.InputError, match="association registry"):
        module.run_describe(args)

    assert not output_json.exists()
    assert not output_tex.exists()
    assert not output_pdf.exists()
    assert not chart_dir.exists()


def test_describe_refuses_association_registry_as_output(tmp_path):
    """The association registry is an input and must never be overwritten.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. The association registry is an input and must never be overwritten.
    """
    module = load_module()
    registry = write_empty_association_registry(tmp_path)
    args = module.build_cli().parse_args([
        "describe", "-i", str(write_descriptive_workbook(tmp_path)),
        "--descriptive-schema", str(write_descriptive_schema(tmp_path)),
        "--form-json", str(write_descriptive_form_manifest(tmp_path)),
        "--association-heatmap-registry", str(registry),
        "-o", str(registry), "--overwrite",
    ])

    with pytest.raises(module.InputError, match="must not overwrite input"):
        module.run_describe(args)


def test_render_descriptive_cli_accepts_exploratory_association_opt_in(tmp_path):
    """Rerendering can retain exploratory panels already present in a payload.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Rerendering can retain exploratory panels already present in a payload.
    """
    module = load_module()
    args = module.build_cli().parse_args([
        "render-descriptive-report", "-i", str(tmp_path / "payload.json"),
        "--output-tex", str(tmp_path / "report.tex"),
        "--include-exploratory-association-heatmaps",
    ])

    assert args.include_exploratory_association_heatmaps is True


def test_default_registry_schema_mismatch_blocks_describe_publication(tmp_path, monkeypatch):
    """A loaded default registry must not be silently discarded on schema mismatch.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. A loaded default registry must not be silently discarded on schema mismatch.
    """
    module = load_module()
    output_json = tmp_path / "payload.json"

    class DescriptiveStub:
        """Inject an association-registry/schema mismatch before output publication.
        """
        class InputError(Exception):
            """Stand in for descriptive input-validation failures caught by the CLI.
            """
            pass

        @staticmethod
        def load_descriptive_schema(_path):
            """Load the descriptive schema fixture.

            Args:
                _path: Schema JSON filename ignored by the stub; no file is read.

            Returns:
                The loaded descriptive schema used by the test.
            """
            return {"output": {"source_row_column": "source_row"}}

        @staticmethod
        def load_form_manifest_structure(_path):
            """Load the form manifest structure fixture.

            Args:
                _path: EUS form-manifest JSON filename ignored by the stub; no file is read.

            Returns:
                The loaded form manifest structure used by the test.
            """
            return {}

        @staticmethod
        def read_descriptive_workbook(_path, _schema):
            """Return the controlled workbook response from the patched reader.

            Args:
                _path: Response XLSX filename ignored because the stub supplies in-memory rows.
                _schema: Descriptive schema deliberately ignored by the patched helper.

            Returns:
                The parsed descriptive workbook fixture value.
            """
            return Namespace(responses=__import__("pandas").DataFrame({"source_row": [5]}))

        @staticmethod
        def validate_descriptive_schema(_schema, _headers):
            """Validate the controlled schema through the patched validator.

            Args:
                _schema: Descriptive schema deliberately ignored by the patched helper.
                _headers: Worksheet headers deliberately ignored by the patched helper.

            Returns:
                One question stub with ID unrelated, intentionally incompatible with the registry.
            """
            return (Namespace(question_id="unrelated"),)

        @staticmethod
        def validate_association_definitions(_definitions, _questions):
            """Validate controlled association definitions through the patched validator.

            Args:
                _definitions: Association definitions deliberately ignored by the validation bypass.
                _questions: Question definitions deliberately ignored by the validation bypass.

            Returns:
                None. Validate controlled association definitions through the patched validator.
            """
            raise DescriptiveStub.InputError("schema mismatch")

        @staticmethod
        def build_descriptive_payload(_workbook, _schema, _form_structure, **_kwargs):
            """Build the descriptive payload fixture.

            Args:
                _workbook: Workbook deliberately ignored by the patched payload builder.
                _schema: Schema deliberately ignored by the patched payload builder.
                _form_structure: Form structure deliberately ignored by the patched payload builder.
                **_kwargs: Additional keyword arguments accepted to preserve the patched builder signature.

            Returns:
                The constructed descriptive payload fixture.
            """
            return {"payload_type": "so2_descriptive_statistics"}

    monkeypatch.setattr(module, "_load_descriptive_report_module", lambda: DescriptiveStub)
    monkeypatch.setattr(
        module,
        "_load_association_heatmap_registry",
        lambda *_args: ((Namespace(mode="default"),), "a" * 64),
    )
    args = module.build_cli().parse_args([
        "describe", "-i", str(write_descriptive_workbook(tmp_path)),
        "--descriptive-schema", str(write_descriptive_schema(tmp_path)),
        "--form-json", str(write_descriptive_form_manifest(tmp_path)),
        "-o", str(output_json),
    ])

    with pytest.raises(module.InputError, match="schema mismatch"):
        module.run_describe(args)

    assert not output_json.exists()


def test_piechart_ratio_parser_accepts_positive_width_to_height_values():
    """The CLI ratio accepts conventional, wide, and tall chart proportions.

    Returns:
        None. The CLI ratio accepts conventional, wide, and tall chart proportions.
    """
    module = load_module()

    assert module._parse_piechart_ratio("4:3") == pytest.approx(4 / 3)
    assert module._parse_piechart_ratio("16:9") == pytest.approx(16 / 9)
    assert module._parse_piechart_ratio("1:2") == pytest.approx(1 / 2)

    for value in ("4", "0:3", "1:0", "wide:tall"):
        with pytest.raises(module.InputError):
            module._parse_piechart_ratio(value)


def test_describe_refuses_to_overwrite_existing_payload(tmp_path):
    """The primary descriptive JSON is a new output, not an overwrite target.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. The primary descriptive JSON is a new output, not an overwrite target.
    """
    module = load_module()
    output_json = tmp_path / "descriptive.json"
    output_json.write_text("keep me", encoding="utf-8")
    args = module.build_cli().parse_args([
        "describe", "-i", str(write_descriptive_workbook(tmp_path)),
        "--descriptive-schema", str(write_descriptive_schema(tmp_path)),
        "--form-json", str(write_descriptive_form_manifest(tmp_path)),
        "-o", str(output_json),
    ])

    with pytest.raises(module.InputError, match="must be a new file"):
        module.run_describe(args)

    assert output_json.read_text(encoding="utf-8") == "keep me"


def test_describe_overwrite_replaces_existing_json(tmp_path):
    """Explicit overwrite permits a deliberate descriptive JSON rerun.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Explicit overwrite permits a deliberate descriptive JSON rerun.
    """
    module = load_module()
    output_json = tmp_path / "descriptive.json"
    output_json.write_text("old payload", encoding="utf-8")
    args = module.build_cli().parse_args([
        "describe", "-i", str(write_descriptive_workbook(tmp_path)),
        "--descriptive-schema", str(write_descriptive_schema(tmp_path)),
        "--form-json", str(write_descriptive_form_manifest(tmp_path)),
        "--association-heatmap-registry", str(write_empty_association_registry(tmp_path)),
        "-o", str(output_json), "--overwrite",
    ])

    assert module.run_describe(args) == module.EXIT_OK
    assert json.loads(output_json.read_text(encoding="utf-8"))["payload_type"] == "so2_descriptive_statistics"


def test_describe_records_report_relative_chart_paths_before_writing_payload(
    tmp_path, monkeypatch,
):
    """Chart filenames added by rendering are persisted in the JSON payload.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Chart filenames added by rendering are persisted in the JSON payload.
    """
    module = load_module()
    output_json = tmp_path / "descriptive.json"
    output_tex = tmp_path / "publication" / "report.tex"
    output_tex.parent.mkdir()
    chart_dir = output_tex.parent / "charts"

    class DescriptiveStub:
        """Capture chart-relative paths and renderer options while replacing TeX/PDF generation with sentinels.
        """
        class InputError(Exception):
            """Stand in for descriptive input-validation failures caught by the CLI.
            """
            pass

        @staticmethod
        def load_descriptive_schema(_path):
            """Load the descriptive schema fixture.

            Args:
                _path: Schema JSON filename ignored by the stub; no file is read.

            Returns:
                The loaded descriptive schema used by the test.
            """
            return {}

        @staticmethod
        def load_association_heatmap_registry(_path):
            """Load the association heatmap registry fixture.

            Args:
                _path: Association-registry JSON filename ignored by the stub; no file is read.

            Returns:
                The loaded association heatmap registry used by the test.
            """
            return ()

        @staticmethod
        def load_form_manifest_structure(_path):
            """Load the form manifest structure fixture.

            Args:
                _path: EUS form-manifest JSON filename ignored by the stub; no file is read.

            Returns:
                The loaded form manifest structure used by the test.
            """
            return object()

        @staticmethod
        def read_descriptive_workbook(_path, _schema):
            """Return the controlled workbook response from the patched reader.

            Args:
                _path: Response XLSX filename ignored because the stub supplies in-memory rows.
                _schema: Descriptive schema deliberately ignored by the patched helper.

            Returns:
                The parsed descriptive workbook fixture value.
            """
            return Namespace(responses=__import__("pandas").DataFrame({"source_row": [5]}))

        @staticmethod
        def validate_descriptive_schema(_schema, _headers):
            """Validate the controlled schema through the patched validator.

            Args:
                _schema: Descriptive schema deliberately ignored by the patched helper.
                _headers: Worksheet headers deliberately ignored by the patched helper.

            Returns:
                Empty tuple: this path tests chart publication rather than question validation.
            """
            return ()

        @staticmethod
        def validate_association_definitions(definitions, _questions):
            """Validate controlled association definitions through the patched validator.

            Args:
                definitions: Association definitions submitted to the validation bypass.
                _questions: Question definitions deliberately ignored by the validation bypass.

            Returns:
                None. Validate controlled association definitions through the patched validator.
            """
            assert definitions == ()

        @staticmethod
        def build_descriptive_payload(_workbook, _schema, _form_structure, **kwargs):
            """Build the descriptive payload fixture.

            Args:
                _workbook: Workbook deliberately ignored by the patched payload builder.
                _schema: Schema deliberately ignored by the patched payload builder.
                _form_structure: Form structure deliberately ignored by the patched payload builder.
                **kwargs: Association definitions, registry hash, and provenance options observed without computing statistics.

            Returns:
                The constructed descriptive payload fixture.
            """
            assert kwargs["association_definitions"] == ()
            assert len(kwargs["association_registry_sha256"]) == 64
            return {
                "payload_type": "so2_descriptive_statistics",
                "payload_version": "1",
                "questions": [{}],
            }

        @staticmethod
        def render_descriptive_tex(
            payload, chart_path, report_path=None, include_contribution_tables=False,
            include_parent_context=False, include_exploratory_association_heatmaps=False,
            max_piechart_ratio=4 / 3,
        ):
            """Render controlled TeX through the patched report renderer.

            Args:
                payload: Descriptive payload forwarded to the patched TeX renderer.
                chart_path: Chart output directory used to derive the report-relative q.pdf link.
                report_path: Final TeX output filename anchoring relative chart paths; asserted against output_tex.
                include_contribution_tables: Contribution-table toggle; asserted false for this CLI invocation.
                include_parent_context: Free-text parent-answer toggle; asserted true for this CLI invocation.
                include_exploratory_association_heatmaps: Exploratory-panel toggle; asserted false for this CLI invocation.
                max_piechart_ratio: Piechart aspect-ratio limit forwarded to the patched TeX renderer.

            Returns:
                A sentinel object standing in for rendered TeX during CLI orchestration.
            """
            assert include_contribution_tables is False
            assert include_parent_context is True
            assert include_exploratory_association_heatmaps is False
            assert max_piechart_ratio == pytest.approx(16 / 9)
            assert Path(report_path) == output_tex
            relative = Path(__import__("os").path.relpath(
                Path(chart_path) / "q.pdf", output_tex.parent
            )).as_posix()
            payload["questions"][0]["chart_paths"] = [relative]
            payload["chart_paths"] = {"q": relative}
            return object()

        @staticmethod
        def render_descriptive_pdf(
            _rendered, tex_path, _pdf_path, _chart_dir, overwrite=False,
            additional_text_outputs=None,
        ):
            """Render controlled PDF output through the patched report renderer.

            Args:
                _rendered: Rendered TeX fixture deliberately ignored by the patched PDF renderer.
                tex_path: Destination where the stub writes sentinel report text instead of compiling TeX.
                _pdf_path: Requested PDF destination, ignored; this double creates no PDF.
                _chart_dir: Chart-directory fixture deliberately ignored by the patched PDF renderer.
                overwrite: Overwrite flag asserted when the patched PDF renderer is invoked.
                additional_text_outputs: Additional staged text outputs passed through the patched PDF renderer.

            Returns:
                None. Render controlled PDF output through the patched report renderer.
            """
            assert overwrite is False
            Path(tex_path).write_text("report", encoding="utf-8")
            for target, text in (additional_text_outputs or {}).items():
                Path(target).write_text(text, encoding="utf-8")

    monkeypatch.setattr(module, "_load_descriptive_report_module", lambda: DescriptiveStub)
    args = module.build_cli().parse_args([
        "describe", "-i", str(write_descriptive_workbook(tmp_path)),
        "--descriptive-schema", str(write_descriptive_schema(tmp_path)),
        "--form-json", str(write_descriptive_form_manifest(tmp_path)),
        "--association-heatmap-registry", str(write_empty_association_registry(tmp_path)),
        "-o", str(output_json),
        "--output-tex", str(output_tex),
        "--output-chart-dir", str(chart_dir),
        "--include-parent-context", "--max-piechart-ratio", "16:9",
    ])

    assert module.run_describe(args) == module.EXIT_OK
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["chart_paths"] == {"q": "charts/q.pdf"}
    assert payload["questions"][0]["chart_paths"] == ["charts/q.pdf"]


def test_describe_wraps_payload_write_failure_as_input_error(tmp_path, monkeypatch):
    """Filesystem errors while writing the requested JSON are actionable.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Filesystem errors while writing the requested JSON are actionable.
    """
    module = load_module()
    output_json = tmp_path / "descriptive.json"
    real_write_text = Path.write_text

    def fail_output(path, *args, **kwargs):
        """Inject the fail output fixture.

        Args:
            path: Path.write_text receiver; writing output_json raises OSError, other paths use the real writer.
            *args: Path.write_text content/options forwarded for non-rejected destinations.
            **kwargs: Path.write_text keyword options forwarded unchanged for non-rejected destinations.

        Returns:
            The original text-write result when output-publication failure injection is inactive.
        """
        if path == output_json:
            raise OSError("simulated JSON write failure")
        return real_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_output)
    args = module.build_cli().parse_args([
        "describe", "-i", str(write_descriptive_workbook(tmp_path)),
        "--descriptive-schema", str(write_descriptive_schema(tmp_path)),
        "--form-json", str(write_descriptive_form_manifest(tmp_path)),
        "--association-heatmap-registry", str(write_empty_association_registry(tmp_path)),
        "-o", str(output_json),
    ])

    with pytest.raises(module.InputError, match="Could not write JSON.*simulated JSON write failure"):
        module.run_describe(args)


def test_render_descriptive_rejects_nonobject_json_root(tmp_path):
    """A JSON array cannot escape as an incidental attribute error.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. A JSON array cannot escape as an incidental attribute error.
    """
    module = load_module()
    input_json = tmp_path / "payload.json"
    input_json.write_text("[]", encoding="utf-8")
    args = Namespace(
        input_json=str(input_json),
        output_tex=str(tmp_path / "out.tex"),
        output_pdf=None,
        output_chart_dir=None,
    )

    with pytest.raises(module.InputError, match="root must be an object"):
        module.run_render_descriptive_report(args)


def test_every_top_level_survey_function_has_a_docstring():
    """Verify every top level survey function has a docstring.

    Returns:
        None. Verifies every top level survey function has a docstring.
    """
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))

    undocumented = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not ast.get_docstring(node)
    ]

    assert undocumented == []


def test_describe_rejects_output_alias_to_source(tmp_path):
    """Verify describe rejects output alias to source.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies describe rejects output alias to source.
    """
    module = load_module()
    source = write_descriptive_workbook(tmp_path)
    args = module.build_cli().parse_args([
        "describe", "-i", str(source),
        "--descriptive-schema", str(write_descriptive_schema(tmp_path)),
        "--form-json", str(write_descriptive_form_manifest(tmp_path)),
        "-o", str(source),
    ])

    with pytest.raises(module.InputError, match="must not overwrite input"):
        module.run_describe(args)


def test_describe_rejects_implicit_tex_path_that_aliases_output_json(tmp_path):
    """A derived TeX target must not replace the descriptive JSON payload.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. A derived TeX target must not replace the descriptive JSON payload.
    """
    module = load_module()
    output_json = tmp_path / "descriptive.tex"
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        module,
        "_load_descriptive_report_module",
        lambda: pytest.fail("output collision must be rejected before loading the renderer"),
    )
    args = module.build_cli().parse_args([
        "describe", "-i", str(write_descriptive_workbook(tmp_path)),
        "--descriptive-schema", str(write_descriptive_schema(tmp_path)),
        "--form-json", str(write_descriptive_form_manifest(tmp_path)),
        "-o", str(output_json),
        "--output-pdf", str(tmp_path / "descriptive.pdf"),
    ])

    try:
        with pytest.raises(module.InputError, match="alias each other"):
            module.run_describe(args)
    finally:
        monkeypatch.undo()

    assert not output_json.exists()


def test_render_descriptive_rejects_legacy_findings_json(tmp_path):
    """Verify render descriptive rejects legacy findings json.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies render descriptive rejects legacy findings json.
    """
    module = load_module()
    input_json = tmp_path / "findings.json"
    input_json.write_text(json.dumps({"summary": {}}), encoding="utf-8")
    args = Namespace(
        input_json=str(input_json),
        output_tex=str(tmp_path / "out.tex"),
        output_pdf=None,
        output_chart_dir=None,
    )

    with pytest.raises(module.InputError, match="descriptive-statistics payload"):
        module.run_render_descriptive_report(args)


def test_render_descriptive_rejects_non_object_json_as_input_error(tmp_path):
    """A syntactically valid but malformed payload has a user-facing failure.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. A syntactically valid but malformed payload has a user-facing failure.
    """
    module = load_module()
    input_json = tmp_path / "payload.json"
    input_json.write_text("[]", encoding="utf-8")
    args = Namespace(
        input_json=str(input_json),
        output_tex=str(tmp_path / "out.tex"),
        output_pdf=None,
        output_chart_dir=None,
    )

    with pytest.raises(module.InputError, match="JSON object"):
        module.run_render_descriptive_report(args)


def test_descriptive_commands_require_new_file_outputs(tmp_path, monkeypatch):
    """Descriptive CLI commands do not silently replace prior report artifacts.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Descriptive CLI commands do not silently replace prior report artifacts.
    """
    module = load_module()
    source = write_descriptive_workbook(tmp_path)
    schema = write_descriptive_schema(tmp_path)
    output_json = tmp_path / "descriptive.json"
    output_json.write_text("existing", encoding="utf-8")
    monkeypatch.setattr(
        module,
        "_load_descriptive_report_module",
        lambda: pytest.fail("existing outputs must be rejected before work starts"),
    )
    describe_args = module.build_cli().parse_args([
        "describe", "-i", str(source), "--descriptive-schema", str(schema),
        "--form-json", str(write_descriptive_form_manifest(tmp_path)),
        "-o", str(output_json),
    ])

    with pytest.raises(module.InputError, match="must be a new file"):
        module.run_describe(describe_args)

    payload_path = tmp_path / "payload.json"
    payload_path.write_text(
        json.dumps({"payload_type": "so2_descriptive_statistics"}),
        encoding="utf-8",
    )
    output_tex = tmp_path / "report.tex"
    output_tex.write_text("existing", encoding="utf-8")
    render_args = Namespace(
        input_json=str(payload_path),
        output_tex=str(output_tex),
        output_pdf=None,
        output_chart_dir=None,
    )

    with pytest.raises(module.InputError, match="must be a new file"):
        module.run_render_descriptive_report(render_args)


def test_write_json_translates_output_failure_to_input_error(tmp_path, monkeypatch):
    """Filesystem write errors are reported through the CLI's user-facing error type.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Filesystem write errors are reported through the CLI's user-facing error type.
    """
    module = load_module()

    def fail_write(*_args, **_kwargs):
        """Inject the fail write fixture.

        Args:
            *_args: Ignored writer/renderer positional inputs; this double always raises the injected failure.
            **_kwargs: Additional keyword arguments accepted to preserve the patched helper signature.

        Returns:
            None. Inject the fail write fixture.
        """
        raise OSError("simulated JSON write failure")

    monkeypatch.setattr(Path, "write_text", fail_write)

    with pytest.raises(module.InputError, match="Could not write JSON.*simulated JSON write"):
        module.write_json(tmp_path / "output.json", {"ok": True})


def test_describe_removes_new_json_if_rendering_fails(tmp_path, monkeypatch):
    """A failed multi-output describe operation leaves no payload-only partial result.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. A failed multi-output describe operation leaves no payload-only partial result.
    """
    module = load_module()
    output_json = tmp_path / "descriptive.json"
    args = module.build_cli().parse_args([
        "describe", "-i", str(write_descriptive_workbook(tmp_path)),
        "--descriptive-schema", str(write_descriptive_schema(tmp_path)),
        "--form-json", str(write_descriptive_form_manifest(tmp_path)),
        "--association-heatmap-registry", str(write_empty_association_registry(tmp_path)),
        "-o", str(output_json),
        "--output-tex", str(tmp_path / "descriptive.tex"),
    ])

    def fail_render(*_args, **_kwargs):
        """Inject the fail render fixture.

        Args:
            *_args: Ignored writer/renderer positional inputs; this double always raises the injected failure.
            **_kwargs: Additional keyword arguments accepted to preserve the patched helper signature.

        Returns:
            None. Inject the fail render fixture.
        """
        raise module.InputError("simulated rendering failure")

    monkeypatch.setattr(module, "_render_descriptive_payload", fail_render)

    with pytest.raises(module.InputError, match="simulated rendering failure"):
        module.run_describe(args)

    assert not output_json.exists()


def test_describe_delegates_payload_publication_to_the_render_transaction(tmp_path, monkeypatch):
    """Rendered reports receive JSON as a transaction member rather than a later write.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Rendered reports receive JSON as a transaction member rather than a later write.
    """
    module = load_module()
    output_json = tmp_path / "descriptive.json"
    output_tex = tmp_path / "descriptive.tex"
    args = module.build_cli().parse_args([
        "describe", "-i", str(write_descriptive_workbook(tmp_path)),
        "--descriptive-schema", str(write_descriptive_schema(tmp_path)),
        "--form-json", str(write_descriptive_form_manifest(tmp_path)),
        "--association-heatmap-registry", str(write_empty_association_registry(tmp_path)),
        "-o", str(output_json),
        "--output-tex", str(output_tex),
    ])

    def fake_render(_payload, render_args, _input_paths, additional_json_output):
        """Write a sentinel TeX artifact, then raise a publication InputError.

        Args:
            _payload: Ignored payload placeholder accepted to match the patched renderer signature.
            render_args: Renderer arguments captured by the fake report renderer.
            _input_paths: Ignored input-path placeholder accepted to match the patched renderer signature.
            additional_json_output: Optional JSON target captured by the fake renderer.

        Returns:
            None. Always raises InputError after creating the TeX artifact.
        """
        Path(render_args.output_tex).write_text("rendered", encoding="utf-8")
        assert additional_json_output == output_json
        raise module.InputError("simulated publication failure")

    monkeypatch.setattr(module, "_render_descriptive_payload", fake_render)

    with pytest.raises(module.InputError, match="simulated publication failure"):
        module.run_describe(args)

    assert not output_json.exists()
    assert output_tex.read_text(encoding="utf-8") == "rendered"


def test_public_descriptive_cli_apis_document_contracts():
    """Public descriptive orchestration APIs document inputs, results, and failures.

    Returns:
        None. Public descriptive orchestration APIs document inputs, results, and failures.
    """
    module = load_module()

    for function in (
        module.write_json,
        module.run_describe,
        module.run_render_descriptive_report,
    ):
        docstring = __import__("inspect").getdoc(function) or ""
        assert "Args:" in docstring, function.__name__
        assert "Returns:" in docstring, function.__name__
        assert "Raises:" in docstring, function.__name__


def test_current_commands_keep_existing_parser_contract():
    """Verify current commands keep existing parser contract.

    Returns:
        None. Verifies current commands keep existing parser contract.
    """
    parser = load_module().build_cli()

    assert parser.parse_args(["analyze", "-i", "survey.xlsx", "-o", "findings.json"]).command == "analyze"
    assert parser.parse_args(["render-report", "-i", "findings.json", "--output-pdf", "report.pdf"]).command == "render-report"


MODULE_PATH = Path(__file__).resolve().parents[1] / "survey-so2-directory.py"


def load_module():
    """Import the SO2 CLI without executing an analysis or rendering command.

    Returns:
        Newly executed survey-so2-directory.py module with patchable Directory and renderer dependencies.
    """
    spec = spec_from_file_location("survey_so2_directory", MODULE_PATH)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_mapping(tmp_path: Path) -> Path:
    """Write the mapping fixture.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        Path to mapping.json with Whole Blood mapped to Directory WHOLE_BLOOD material.
    """
    payload = {
        "survey": {
            "file": "survey.xlsx",
            "sheet": "Content",
            "header_row": 4,
        },
        "entity_resolution": [],
        "field_mappings": [],
        "value_maps": {
            "sample_types_to_materials": {
                "Whole Blood": ["WHOLE_BLOOD"],
            }
        },
    }
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def write_objectives_mapping(tmp_path: Path) -> Path:
    """Write the objectives mapping fixture.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        Path to objectives-mapping.json linking sample, promotion, and pathology questions to SO2 objectives.
    """
    payload = {
        "strategic_objectives": {
            "SO2.1": {"title": "Datafication at source", "description": "x"},
            "SO2.4": {"title": "Expand the Federated Platform", "description": "y"},
            "SO2.5": {"title": "On-demand accessible data generation", "description": "z"},
        },
        "question_mappings": [
            {
                "survey_field": "Are you interested in promoting your biobank resources to new partners?",
                "strategic_objectives": ["SO2.4"],
            },
            {
                "survey_field": "Are you interested in promoting your biobank resources to new research or industry partners?",
                "strategic_objectives": ["SO2.4"],
            },
            {
                "survey_field": "Which types of samples do you manage?",
                "strategic_objectives": ["SO2.1"],
            },
            {
                "survey_field": "Sample types",
                "strategic_objectives": ["SO2.1"],
            },
            {
                "survey_field": "Does your biobank provide access to whole-slide image (WSI) histopathology datasets? E.g., disease-focused cohorts with clinical and/or molecular annotations or normal-tissue reference histology across multiple organs from non-diseased donors?",
                "strategic_objectives": ["SO2.5"],
            },
            {
                "survey_field": "You can provide more information about available digital pathology imaging data here (e.g., focus of the collections, more details on modalities):",
                "strategic_objectives": ["SO2.5"],
            },
        ],
    }
    path = tmp_path / "objectives-mapping.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def write_survey(tmp_path: Path) -> Path:
    """Write the survey fixture.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        Path to survey.xlsx with one Directory-resolvable Czech response in the Content sheet at row 5.
    """
    row = {
        "Name": "Test Person",
        "Role": "Manager",
        "E-Mail address": "contact@example.org",
        "Name of Institution": "Demo Biobank",
        "BiobankID in the Directory (if available)": "bbmri-eric:ID:CZ_demo",
        "List of CollectionID in the Directory (if you only represent a part of a biobank; please use ';' as separator in case of more than 1 ID)": "bbmri-eric:ID:CZ_demo:collection:col1",
        "Country": "Czech Republic",
        "Are you interested in promoting your biobank resources to new partners?": "Yes - academic",
        "Which types of samples do you manage?": "Whole Blood",
        "Sample types": "",
        "Does your biobank provide access to whole-slide image (WSI) histopathology datasets? E.g., disease-focused cohorts with clinical and/or molecular annotations or normal-tissue reference histology across multiple organs from non-diseased donors?": "Yes — access to internally generated WSI data collections",
        "You can provide more information about available digital pathology imaging data here (e.g., focus of the collections, more details on modalities):": "",
    }
    path = tmp_path / "survey.xlsx"
    with __import__("pandas").ExcelWriter(path) as writer:
        __import__("pandas").DataFrame([row]).to_excel(writer, sheet_name="Content", index=False, startrow=3)
    return path


def write_survey_row(tmp_path: Path, updates: dict[str, object] | None = None, *, filename: str = "survey.xlsx") -> Path:
    """Write the survey row fixture.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        updates: Cell updates applied to the generated survey-row fixture.
        filename: Output XLSX filename relative to tmp_path, replaced if it already exists.

    Returns:
        Path to the saved Content-sheet XLSX after applying the requested answer-cell overrides.
    """
    row = {
        "Name": "Test Person",
        "Role": "Manager",
        "E-Mail address": "contact@example.org",
        "Name of Institution": "Demo Biobank",
        "BiobankID in the Directory (if available)": "bbmri-eric:ID:CZ_demo",
        "List of CollectionID in the Directory (if you only represent a part of a biobank; please use ';' as separator in case of more than 1 ID)": "bbmri-eric:ID:CZ_demo:collection:col1",
        "Country": "Czech Republic",
        "Are you interested in promoting your biobank resources to new partners?": "",
        "Are you interested in promoting your biobank resources to new research or industry partners?": "",
        "Which types of samples do you manage?": "",
        "Sample types": "",
        "What is the approximate size of your biobank (number of samples aliquots)?": "",
        "Does your biobank provide access to radiology datasets?": "",
        "You can provide more information about available radiology pathology imaging data here (e.g., focus of the collections, more details on modalities):": "",
        "Does your biobank provide access to whole-slide image (WSI) histopathology datasets? E.g., disease-focused cohorts with clinical and/or molecular annotations or normal-tissue reference histology across multiple organs from non-diseased donors?": "",
        "You can provide more information about available digital pathology imaging data here (e.g., focus of the collections, more details on modalities):": "",
        "Does the repository have a direct access to data from any of the following technologies? (Select all that apply)": "",
        "Next-gen sequencing technology/vendor": "",
        "Radiology imaging technology/vendor": "",
        "Pathology imaging technology/vendor": "",
        "Proteomics technology/vendor": "",
        "Metabolomics technology/vendor": "",
        "Technologies": "",
    }
    if updates:
        row.update(updates)
    path = tmp_path / filename
    with __import__("pandas").ExcelWriter(path) as writer:
        __import__("pandas").DataFrame([row]).to_excel(writer, sheet_name="Content", index=False, startrow=3)
    return path


class DirectoryStub:
    """Expose a Czech biobank, one collection, and its contact for survey resolution and fix proposals.
    """
    def __init__(self, *args, **kwargs):
        """Populate the institution, collection, and contact records used by respondent-resolution assertions.

        Args:
            *args: Directory constructor positional arguments, forwarded by subclasses and ignored by the base stub.
            **kwargs: Directory constructor options; only schema is used (default ERIC), and subclasses forward these unchanged.
        """
        self.schema = kwargs.get("schema", "ERIC")
        self._biobank = {
            "id": "bbmri-eric:ID:CZ_demo",
            "name": "Demo Biobank",
            "country": "CZ",
            "contact": {"id": "bbmri-eric:contactID:CZ_demo_1"},
            "collaboration_non_for_profit": False,
            "collaboration_commercial": False,
        }
        self._collection = {
            "id": "bbmri-eric:ID:CZ_demo:collection:col1",
            "biobank": {"id": "bbmri-eric:ID:CZ_demo"},
            "contact": {"id": "bbmri-eric:contactID:CZ_demo_1"},
            "materials": "",
            "data_use": [],
            "type": "",
            "data_categories": "",
            "description": "",
            "imaging_modality": "",
            "image_dataset_type": "",
        }
        self._contact = {
            "id": "bbmri-eric:contactID:CZ_demo_1",
            "email": "contact@example.org",
            "full_name": "Test Person",
        }

    def getSchema(self):
        """Return schema string selected for the fake Directory session.

        Returns:
            The schema string selected for the fake Directory session.
        """
        return self.schema

    def getBiobanks(self):
        """Return synthetic biobank records available to the code under test.

        Returns:
            The synthetic biobank records available to the code under test.
        """
        return [self._biobank]

    def getCollections(self):
        """Return synthetic collection records available to the code under test.

        Returns:
            The synthetic collection records available to the code under test.
        """
        return [self._collection]

    def getBiobankById(self, biobank_id):
        """Return synthetic biobank record selected by the requested identifier, or `None` when absent.

        Args:
            biobank_id: Biobank identifier whose fixture record this stub returns or omits.

        Returns:
            The synthetic biobank record selected by the requested identifier, or `None` when absent.
        """
        return self._biobank if biobank_id == self._biobank["id"] else None

    def getCollectionById(self, collection_id):
        """Return synthetic collection record selected by the requested identifier, or `None` when absent.

        Args:
            collection_id: Collection identifier whose fixture record this stub returns or omits.

        Returns:
            The synthetic collection record selected by the requested identifier, or `None` when absent.
        """
        return self._collection if collection_id == self._collection["id"] else None

    def getContacts(self):
        """Return synthetic contact records available to the code under test.

        Returns:
            The synthetic contact records available to the code under test.
        """
        return [self._contact]

    def getNetworks(self):
        """Return synthetic network records available to the code under test.

        Returns:
            The synthetic network records available to the code under test.
        """
        return []

    def getGraphBiobankCollectionsFromBiobank(self, biobank_id):
        """Return fixture graph relating the requested biobank to its collections.

        Args:
            biobank_id: Biobank identifier used to obtain the fixture collection graph.

        Returns:
            The fixture graph relating the requested biobank to its collections.
        """
        import networkx as nx
        graph = nx.DiGraph()
        graph.add_node(self._biobank["id"])
        graph.add_node(self._collection["id"])
        graph.add_edge(self._biobank["id"], self._collection["id"])
        return graph

    def getContact(self, contact_id):
        """Return synthetic contact record selected by the requested identifier.

        Args:
            contact_id: Contact identifier whose fixture contact record this stub returns.

        Returns:
            The synthetic contact record selected by the requested identifier.
        """
        return self._contact


class SwissResolutionDirectoryStub:
    """Distinguish Bern human/animal collections and Geneva university/hospital institutions.
    """
    def __init__(self):
        """Populate the institution, collection, and contact records used by respondent-resolution assertions.
        """
        self._biobanks = [
            {"id": "bbmri-eric:ID:CH_UniversityOfBern", "name": "University of Bern", "country": "CH"},
            {"id": "bbmri-eric:ID:CH_Unige", "name": "Université de Genève", "country": "CH"},
            {"id": "bbmri-eric:ID:CH_HopitauxUniversitairesGeneve", "name": "Hôpitaux Universitaires Genève", "country": "CH"},
        ]
        self._collections = [
            {
                "id": "bbmri-eric:ID:CH_UniversityOfBern:collection:CH_VetSuisseBiobankVETGENBERN",
                "biobank": {"id": "bbmri-eric:ID:CH_UniversityOfBern"},
                "name": "VetSuisse Biobank, VET_GEN_BERN",
                "description": "Domestic animal samples.",
                "type": ["NON_HUMAN", "SAMPLE"],
                "materials": ["DNA", "WHOLE_BLOOD"],
                "contact": {"id": "contact-vet"},
            },
            {
                "id": "bbmri-eric:ID:CH_UniversityOfBern:collection:CH_TissueBiobankBern",
                "biobank": {"id": "bbmri-eric:ID:CH_UniversityOfBern"},
                "name": "Tissue Biobank Bern",
                "description": "Human pathology samples from Inselspital.",
                "type": ["DISEASE_SPECIFIC", "HOSPITAL"],
                "materials": ["TISSUE_FROZEN"],
                "contact": {"id": "contact-human"},
            },
            {
                "id": "bbmri-eric:ID:CH_Unige:collection:CH_FABER",
                "biobank": {"id": "bbmri-eric:ID:CH_Unige"},
                "name": "FABER",
                "description": "University of Geneva biomedical cohort.",
                "type": ["SAMPLE"],
                "materials": ["WHOLE_BLOOD"],
                "contact": {"id": "contact-unige"},
            },
            {
                "id": "bbmri-eric:ID:CH_HopitauxUniversitairesGeneve:collection:CH_AneuX",
                "biobank": {"id": "bbmri-eric:ID:CH_HopitauxUniversitairesGeneve"},
                "name": "AneuX",
                "description": "Hospital cohort in Geneva.",
                "type": ["SAMPLE"],
                "materials": ["SERUM"],
                "contact": {"id": "contact-hug"},
            },
        ]

    def getBiobanks(self):
        """Return synthetic biobank records available to the code under test.

        Returns:
            The synthetic biobank records available to the code under test.
        """
        return list(self._biobanks)

    def getCollections(self):
        """Return synthetic collection records available to the code under test.

        Returns:
            The synthetic collection records available to the code under test.
        """
        return list(self._collections)

    def getNetworks(self):
        """Return synthetic network records available to the code under test.

        Returns:
            The synthetic network records available to the code under test.
        """
        return []

    def getGraphBiobankCollectionsFromBiobank(self, biobank_id):
        """Return fixture graph relating the requested biobank to its collections.

        Args:
            biobank_id: Biobank identifier used to obtain the fixture collection graph.

        Returns:
            The fixture graph relating the requested biobank to its collections.
        """
        import networkx as nx

        graph = nx.DiGraph()
        graph.add_node(biobank_id)
        for collection in self._collections:
            if collection["biobank"]["id"] == biobank_id:
                graph.add_node(collection["id"])
                graph.add_edge(biobank_id, collection["id"])
        return graph


def test_survey_so2_analyze_generates_findings_and_proposed_updates(tmp_path, monkeypatch):
    """Verify survey so2 analyze generates findings and proposed updates.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Verifies survey so2 analyze generates findings and proposed updates.
    """
    module = load_module()
    mapping_path = write_mapping(tmp_path)
    objectives_mapping_path = write_objectives_mapping(tmp_path)
    survey_path = write_survey(tmp_path)
    output_json = tmp_path / "report.json"

    monkeypatch.setattr(module, "Directory", DirectoryStub)

    args = Namespace(
        survey_file=str(survey_path),
        mapping_file=str(mapping_path),
        objectives_mapping_file=str(objectives_mapping_path),
        output_json=str(output_json),
        output_tex=None,
        output_pdf=None,
        verbose=False,
        debug=False,
        username=None,
        password=None,
        token=None,
        schema="ERIC",
        directory_target=None,
    )

    result = module.run_analyze(args)

    assert result == module.EXIT_OK
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["summary"]["survey_rows"] == 1
    assert "strategic_objectives" in payload
    proposed = [finding for finding in payload["findings"] if finding.get("proposed_update")]
    assert {finding["mapping_id"] for finding in proposed} == {
        "promotion.partnership_interest",
        "promotion.partnership_interest.duo",
        "sample_types.materials",
        "imaging.wsi_presence",
    }
    duo_finding = next(finding for finding in proposed if finding["mapping_id"] == "promotion.partnership_interest.duo")
    assert duo_finding["proposed_update"]["field"] == "data_use"
    assert duo_finding["proposed_update"]["proposed_value"] == ["DUO:0000018"]
    assert any(finding["strategic_objectives"] for finding in payload["findings"])


def test_survey_so2_analyze_radiology_presence_and_explicit_size_bucket(tmp_path, monkeypatch):
    """Verify survey so2 analyze radiology presence and explicit size bucket.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Verifies survey so2 analyze radiology presence and explicit size bucket.
    """
    module = load_module()
    mapping_path = write_mapping(tmp_path)
    objectives_mapping_path = write_objectives_mapping(tmp_path)
    survey_path = write_survey_row(
        tmp_path,
        {
            "What is the approximate size of your biobank (number of samples aliquots)?": "1000 - 10,000 aliquots",
            "Does your biobank provide access to radiology datasets?": "Yes — access to internally generated radiology data collections (e.g., directly connected to a PACS system)",
        },
        filename="radiology-size.xlsx",
    )
    output_json = tmp_path / "radiology-size-report.json"

    class DirectoryExplicitSizeStub(DirectoryStub):
        """Set the Czech collection size to 1500 for explicit-count comparison.
        """
        def __init__(self, *args, **kwargs):
            """Populate the institution, collection, and contact records used by respondent-resolution assertions.

            Args:
                *args: Directory constructor positional arguments, forwarded by subclasses and ignored by the base stub.
                **kwargs: Directory constructor options; only schema is used (default ERIC), and subclasses forward these unchanged.
            """
            super().__init__(*args, **kwargs)
            self._collection["size"] = 1500

    monkeypatch.setattr(module, "Directory", DirectoryExplicitSizeStub)

    args = Namespace(
        survey_file=str(survey_path),
        mapping_file=str(mapping_path),
        objectives_mapping_file=str(objectives_mapping_path),
        output_json=str(output_json),
        output_tex=None,
        output_pdf=None,
        verbose=False,
        debug=False,
        username=None,
        password=None,
        token=None,
        schema="ERIC",
        directory_target=None,
    )

    result = module.run_analyze(args)

    assert result == module.EXIT_OK
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    size_finding = next(finding for finding in payload["findings"] if finding["mapping_id"] == "biobank_size.samples")
    assert size_finding["status"] == "consistent"
    assert size_finding["directory_value"]["explicit_total"] == 1500
    assert size_finding["directory_value"]["bucket"] == "1000 - 10,000 aliquots"
    radiology_finding = next(finding for finding in payload["findings"] if finding["mapping_id"] == "imaging.radiology_presence")
    assert radiology_finding["status"] == "missing_in_directory"
    assert radiology_finding["proposed_update"]["field"] == "type"
    assert radiology_finding["proposed_update"]["proposed_value"] == ["IMAGE"]




def test_survey_so2_analyze_outputs_technology_upset_artifacts(tmp_path, monkeypatch):
    """Verify survey so2 analyze outputs technology upset artifacts.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Verifies survey so2 analyze outputs technology upset artifacts.
    """
    module = load_module()
    mapping_path = write_mapping(tmp_path)
    objectives_mapping_path = write_objectives_mapping(tmp_path)
    survey_path = write_survey_row(
        tmp_path,
        {
            "Does the repository have a direct access to data from any of the following technologies? (Select all that apply)": (
                "Next-gen sequencing (if yes, specify technology/vendor); "
                "Proteomics (if yes, specify technology/vendor); "
                "Other (please specify):"
            ),
            "Radiology imaging technology/vendor": "Siemens SOMATOM",
            "Technologies": "Mass cytometry",
        },
        filename="technology-upset.xlsx",
    )
    output_json = tmp_path / "technology-upset-report.json"
    upset_prefix = tmp_path / "so2-modalities"

    monkeypatch.setattr(module, "Directory", DirectoryStub)

    args = Namespace(
        survey_file=str(survey_path),
        mapping_file=str(mapping_path),
        objectives_mapping_file=str(objectives_mapping_path),
        output_json=str(output_json),
        output_tex=None,
        output_pdf=None,
        output_tech_upset_prefix=str(upset_prefix),
        verbose=False,
        debug=False,
        username=None,
        password=None,
        token=None,
        schema="ERIC",
        directory_target=None,
    )

    result = module.run_analyze(args)

    assert result == module.EXIT_OK
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    technology_payload = payload["technology_modalities"]
    assert technology_payload["summary"]["modality_counts"]["sequencing"] == 1
    assert technology_payload["summary"]["modality_counts"]["genotyping_panels"] == 0
    assert technology_payload["summary"]["modality_counts"]["radiology"] == 1
    assert technology_payload["summary"]["modality_counts"]["proteomics"] == 1
    assert technology_payload["summary"]["modality_counts"]["other_technology"] == 1
    row = technology_payload["rows"][0]
    assert row["sequencing"] == 1
    assert row["genotyping_panels"] == 0
    assert row["radiology"] == 1
    assert row["proteomics"] == 1
    assert row["other_technology"] == 1
    assert row["metabolomics"] == 0

    csv_path = tmp_path / "so2-modalities-technology-upset.csv"
    r_path = tmp_path / "so2-modalities-technology-upset.R"
    assert csv_path.exists()
    assert r_path.exists()
    df = __import__("pandas").read_csv(csv_path)
    assert {"country", "sequencing", "radiology", "proteomics", "other_technology", "has_any_modality"}.issubset(df.columns)
    assert df.loc[0, "country"] == "CZ"
    assert int(df.loc[0, "sequencing"]) == 1
    assert int(df.loc[0, "radiology"]) == 1
    assert int(df.loc[0, "proteomics"]) == 1
    assert int(df.loc[0, "other_technology"]) == 1
    script_text = r_path.read_text(encoding="utf-8")
    assert "ComplexUpset::upset" in script_text
    assert "Observed Intersection Deviation From Independence" in script_text
    assert "so2-modalities-technology-upset.pdf" in script_text
    assert "so2-modalities-technology-upset-deviation.png" in script_text
    assert "SO2 Survey Respondent-by-Modality Matrix" in script_text
    assert "so2-modalities-technology-matrix.pdf" in script_text
    assert "so2-modalities-technology-matrix.png" in script_text
    assert "tidyr::pivot_longer" in script_text
    assert 'paste0(" (", plot_data$country, ")"' in script_text
    assert 'plot.background = ggplot2::element_rect(fill = "white", colour = NA)' in script_text
    assert 'dplyr::arrange(.data$country, dplyr::desc(.data$modality_count), .data$institution_name, .data$survey_row)' in script_text
    assert 'respondent_label = factor(.data$respondent_label, levels = rev(respondent_levels))' in script_text
    assert "Rows are grouped by country, then sorted by the number of advertised modalities, highest first." in script_text


def test_technology_genotyping_panels_is_split_from_other_positive_detail(tmp_path, monkeypatch):
    """Verify technology genotyping panels is split from other positive detail.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Verifies technology genotyping panels is split from other positive detail.
    """
    module = load_module()
    mapping_path = write_mapping(tmp_path)
    objectives_mapping_path = write_objectives_mapping(tmp_path)
    survey_path = write_survey_row(
        tmp_path,
        {
            "Does the repository have a direct access to data from any of the following technologies? (Select all that apply)": "Other (please specify):",
            "Technologies": "GWAS array",
        },
        filename="technology-genotyping-panels.xlsx",
    )
    output_json = tmp_path / "technology-genotyping-panels-report.json"

    monkeypatch.setattr(module, "Directory", DirectoryStub)

    args = Namespace(
        survey_file=str(survey_path),
        mapping_file=str(mapping_path),
        objectives_mapping_file=str(objectives_mapping_path),
        output_json=str(output_json),
        output_tex=None,
        output_pdf=None,
        output_tech_upset_prefix=None,
        verbose=False,
        debug=False,
        username=None,
        password=None,
        token=None,
        schema="ERIC",
        directory_target=None,
    )

    result = module.run_analyze(args)

    assert result == module.EXIT_OK
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    technology_payload = payload["technology_modalities"]
    assert technology_payload["summary"]["modality_counts"]["genotyping_panels"] == 1
    assert technology_payload["summary"]["field_only_counts"]["genotyping_panels"] == 1
    assert technology_payload["summary"]["modality_counts"]["other_technology"] == 0
    row = technology_payload["rows"][0]
    assert row["genotyping_panels"] == 1
    assert row["genotyping_panels_field_present"] == 1
    assert row["other_technology"] == 0
    assert row["other_technology_field_present"] == 0
    assert row["has_any_modality"] == 1


def test_technology_other_checkbox_requires_positive_detail(tmp_path, monkeypatch):
    """Verify technology other checkbox requires positive detail.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Verifies technology other checkbox requires positive detail.
    """
    module = load_module()
    mapping_path = write_mapping(tmp_path)
    objectives_mapping_path = write_objectives_mapping(tmp_path)
    survey_path = write_survey_row(
        tmp_path,
        {
            "Does the repository have a direct access to data from any of the following technologies? (Select all that apply)": "Other (please specify):",
            "Technologies": "The answer is \"No\"",
        },
        filename="technology-other-negative.xlsx",
    )
    output_json = tmp_path / "technology-other-negative-report.json"

    monkeypatch.setattr(module, "Directory", DirectoryStub)

    args = Namespace(
        survey_file=str(survey_path),
        mapping_file=str(mapping_path),
        objectives_mapping_file=str(objectives_mapping_path),
        output_json=str(output_json),
        output_tex=None,
        output_pdf=None,
        output_tech_upset_prefix=None,
        verbose=False,
        debug=False,
        username=None,
        password=None,
        token=None,
        schema="ERIC",
        directory_target=None,
    )

    result = module.run_analyze(args)

    assert result == module.EXIT_OK
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    technology_payload = payload["technology_modalities"]
    assert technology_payload["summary"]["modality_counts"]["other_technology"] == 0
    assert technology_payload["summary"]["field_only_counts"]["other_technology"] == 0
    row = technology_payload["rows"][0]
    assert row["other_technology_selected"] == 1
    assert row["other_technology_detail_present"] == 1
    assert row["other_technology_field_present"] == 0
    assert row["other_technology"] == 0
    assert row["has_any_modality"] == 0


def test_survey_so2_analyze_sample_size_uses_oom_fallback_as_manual_review(tmp_path, monkeypatch):
    """Verify survey so2 analyze sample size uses oom fallback as manual review.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Verifies survey so2 analyze sample size uses oom fallback as manual review.
    """
    module = load_module()
    mapping_path = write_mapping(tmp_path)
    objectives_mapping_path = write_objectives_mapping(tmp_path)
    survey_path = write_survey_row(
        tmp_path,
        {
            "What is the approximate size of your biobank (number of samples aliquots)?": "1000 - 10,000 aliquots",
        },
        filename="size-oom.xlsx",
    )
    output_json = tmp_path / "size-oom-report.json"

    class DirectoryOomSizeStub(DirectoryStub):
        """Set the Czech collection sample order of magnitude to 3 for estimate comparison.
        """
        def __init__(self, *args, **kwargs):
            """Populate the institution, collection, and contact records used by respondent-resolution assertions.

            Args:
                *args: Directory constructor positional arguments, forwarded by subclasses and ignored by the base stub.
                **kwargs: Directory constructor options; only schema is used (default ERIC), and subclasses forward these unchanged.
            """
            super().__init__(*args, **kwargs)
            self._collection["order_of_magnitude"] = 3

    monkeypatch.setattr(module, "Directory", DirectoryOomSizeStub)

    args = Namespace(
        survey_file=str(survey_path),
        mapping_file=str(mapping_path),
        objectives_mapping_file=str(objectives_mapping_path),
        output_json=str(output_json),
        output_tex=None,
        output_pdf=None,
        verbose=False,
        debug=False,
        username=None,
        password=None,
        token=None,
        schema="ERIC",
        directory_target=None,
    )

    result = module.run_analyze(args)

    assert result == module.EXIT_OK
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    size_finding = next(finding for finding in payload["findings"] if finding["mapping_id"] == "biobank_size.samples")
    assert size_finding["status"] == "manual_review"
    assert size_finding["directory_value"]["explicit_total"] is None
    assert size_finding["directory_value"]["estimated_total"] == 1000
    assert size_finding["directory_value"]["bucket"] == "500 - 1000 aliquots"
    assert size_finding["directory_value"]["estimate_used"] is True


def test_survey_so2_export_update_plan_keeps_biobank_and_collection_updates(tmp_path):
    """Verify survey so2 export update plan keeps biobank and collection updates.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies survey so2 export update plan keeps biobank and collection updates.
    """
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "findings": [
            {
                "export_update_plan": True,
                "proposed_update": {
                    "update_id": "survey_so2.biobank.collaboration_non_profit",
                    "module": "SO2",
                    "entity_type": "BIOBANK",
                    "entity_id": "bbmri-eric:ID:CZ_demo",
                    "field": "collaboration_non_for_profit",
                    "mode": "set",
                    "confidence": "uncertain",
                    "current_value_at_export": False,
                    "expected_current_value": False,
                    "proposed_value": True,
                    "human_explanation": "x",
                    "rationale": "r",
                    "term_explanations": [],
                    "source_check_ids": ["SO2:PromotionInterest"],
                    "source_warning_messages": [],
                    "source_warning_actions": [],
                    "replace_required": False,
                    "blocking_reason": "",
                    "exclusive_group": "",
                    "staging_area": "CZ",
                    "update_checksum": "x",
                },
            },
            {
                "export_update_plan": True,
                "proposed_update": {
                    "update_id": "survey_so2.collection.materials_from_sample_types",
                    "module": "SO2",
                    "entity_type": "COLLECTION",
                    "entity_id": "bbmri-eric:ID:CZ_demo:collection:col1",
                    "field": "materials",
                    "mode": "append",
                    "confidence": "uncertain",
                    "current_value_at_export": [],
                    "expected_current_value": [],
                    "proposed_value": ["WHOLE_BLOOD"],
                    "human_explanation": "x",
                    "rationale": "r",
                    "term_explanations": [],
                    "source_check_ids": ["SO2:SampleTypes"],
                    "source_warning_messages": [],
                    "source_warning_actions": [],
                    "replace_required": False,
                    "blocking_reason": "",
                    "exclusive_group": "",
                    "staging_area": "CZ",
                    "update_checksum": "x",
                },
            },
        ],
    }
    input_path = tmp_path / "report.json"
    output_path = tmp_path / "updates.json"
    input_path.write_text(json.dumps(report), encoding="utf-8")

    args = Namespace(input_json=str(input_path), output_json=str(output_path), min_confidence="uncertain")
    result = module.run_export_update_plan(args)

    assert result == module.EXIT_OK
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert {update["entity_type"] for update in payload["updates"]} == {"BIOBANK", "COLLECTION"}


def test_survey_so2_render_report_writes_tex_and_pdf(tmp_path, monkeypatch):
    """Verify survey so2 render report writes tex and pdf.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Verifies survey so2 render report writes tex and pdf.
    """
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 1, "resolved_rows": 1, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "findings": [],
    }
    input_path = tmp_path / "report.json"
    tex_path = tmp_path / "report.tex"
    pdf_path = tmp_path / "report.pdf"
    input_path.write_text(json.dumps(report), encoding="utf-8")

    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/xelatex")

    def fake_run(cmd, cwd, check, stdout, stderr, text):
        """Write report.pdf in the compilation directory and mimic empty process stdout.

        Args:
            cmd: Command vector captured by the patched subprocess runner.
            cwd: Working directory captured by the fake subprocess call.
            check: Subprocess check flag captured by the fake command runner.
            stdout: Subprocess standard-output setting captured by the fake runner.
            stderr: Subprocess standard-error setting captured by the fake runner.
            text: Subprocess text-mode setting captured by the fake runner.

        Returns:
            The successful fake process result consumed by the external renderer wrapper.
        """
        Path(cwd, "report.pdf").write_bytes(b"%PDF-1.4\\n")
        class Result:
            """Mimic a completed TeX process with empty captured stdout.
            """
            stdout = ""
        return Result()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    args = Namespace(input_json=str(input_path), output_tex=str(tex_path), output_pdf=str(pdf_path), verbose=False, debug=False)
    result = module.run_render(args)

    assert result == module.EXIT_OK
    assert tex_path.exists()
    assert pdf_path.exists()


def test_survey_so2_render_tex_escapes_special_characters():
    """Verify survey so2 render tex escapes special characters.

    Returns:
        None. Verifies survey so2 render tex escapes special characters.
    """
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 1, "resolved_rows": 1, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "findings": [
            {
                "status": "missing_in_directory",
                "survey_row": 5,
                "mapping_id": "imaging.wsi_presence",
                "entity_type": "BIOBANK",
                "entity_id": "bbmri-eric:ID:CZ_demo",
                "explanation": "Missing in directory.",
                "why_relevant": "z",
                "relation_type": "derived_presence",
                "reliability": "medium",
                "survey_fields": [],
                "survey_value": "yes",
                "directory_value": "no",
                "proposed_update": None,
            },
            {
                "status": "manual_review",
                "survey_row": 6,
                "mapping_id": "geo.country",
                "entity_type": "BIOBANK",
                "entity_id": "bbmri-eric:ID:NL_LUMC",
                "explanation": "Survey country NL conflicts with biobank name Demo_1 & needs manual review.",
            }
        ],
    }

    tex = module.render_tex(report)

    assert r"BIOBANK \texorpdfstring{\nolinkurl{bbmri-eric:ID:NL_LUMC}}{bbmri-eric:ID:NL_LUMC}" in tex
    assert r"Demo\_\allowbreak{}1 \& needs manual review." in tex
    assert r"NL\\_LUMC" not in tex


def test_survey_so2_render_tex_includes_biobank_grouped_summary():
    """Verify survey so2 render tex includes biobank grouped summary.

    Returns:
        None. Verifies survey so2 render tex includes biobank grouped summary.
    """
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 2, "resolved_rows": 2, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 1},
        "row_resolutions": [
            {
                "survey_row": 6,
                "institution_name": "Demo Biobank",
                "resolution_status": "resolved_by_biobank_id",
                "resolution_reliability": "high",
                "resolution_explanation": "Resolved via biobank ID.",
                "matched_biobank_ids": ["bbmri-eric:ID:CZ_demo"],
                "matched_collection_ids": ["bbmri-eric:ID:CZ_demo:collection:col1"],
                "collection_scope_display": "all collections",
            },
            {
                "survey_row": 7,
                "institution_name": "Demo Biobank follow-up",
                "resolution_status": "resolved_by_biobank_id",
                "resolution_reliability": "high",
                "resolution_explanation": "Resolved via biobank ID.",
                "matched_biobank_ids": ["bbmri-eric:ID:CZ_demo"],
                "matched_collection_ids": ["bbmri-eric:ID:CZ_demo:collection:col2"],
                "collection_scope_display": "All except bbmri-eric:ID:CZ_demo:collection:col1",
            },
        ],
        "findings": [
            {
                "status": "consistent",
                "survey_row": 6,
                "mapping_id": "geo.country",
                "entity_type": "BIOBANK",
                "entity_id": "bbmri-eric:ID:CZ_demo",
                "explanation": "Country matches.",
                "proposed_update": None,
            },
            {
                "status": "inconsistent",
                "survey_row": 7,
                "mapping_id": "sample_types.materials",
                "entity_type": "COLLECTION",
                "entity_id": "bbmri-eric:ID:CZ_demo:collection:col2",
                "explanation": "Materials mismatch.",
                "proposed_update": {"update_id": "x"},
            },
        ],
    }

    tex = module.render_tex(report)

    assert "Biobank-Oriented Summary" in tex
    assert r"\nolinkurl{bbmri-eric:ID:CZ_demo}" in tex
    assert "(2 survey answers)" in tex
    assert "Survey row 6: Demo Biobank" in tex
    assert "Survey row 7: Demo Biobank follow-up" in tex
    assert "Mapped collections: all collections" in tex
    assert r"Mapped collections: All except \texorpdfstring{\nolinkurl{bbmri-eric:ID:CZ_demo:collection:col1}}{bbmri-eric:ID:CZ_demo:collection:col1}" in tex
    assert r"\textcolor{soGreen}{Consistent}" in tex
    assert r"\hyperref[appendix-geo-country]{" in tex
    assert r"\nolinkurl{geo.country}" in tex
    assert r"\textcolor{soRed}{Inconsistent}" in tex
    assert r"\hyperref[appendix-sample-types-materials]{" in tex
    assert r"\nolinkurl{sample_types.materials}" in tex
    assert "[proposed update]" in tex


def test_survey_so2_render_tex_includes_objective_summary():
    """Verify survey so2 render tex includes objective summary.

    Returns:
        None. Verifies survey so2 render tex includes objective summary.
    """
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 1, "resolved_rows": 1, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 1},
        "strategic_objectives": {
            "SO2.4": {"title": "Expand the Federated Platform", "description": "Platform onboarding and discovery."},
        },
        "row_resolutions": [
            {
                "survey_row": 6,
                "institution_name": "Demo Biobank",
                "resolution_status": "resolved_by_biobank_id",
                "resolution_reliability": "high",
                "resolution_explanation": "Resolved via biobank ID.",
                "matched_biobank_ids": ["bbmri-eric:ID:CZ_demo"],
                "matched_collection_ids": [],
            }
        ],
        "findings": [
            {
                "status": "inconsistent",
                "survey_row": 6,
                "mapping_id": "promotion.partnership_interest",
                "entity_type": "BIOBANK",
                "entity_id": "bbmri-eric:ID:CZ_demo",
                "explanation": "Promotion interest differs.",
                "strategic_objectives": ["SO2.4"],
                "proposed_update": {"update_id": "x"},
            }
        ],
    }

    tex = module.render_tex(report)

    assert "Strategic-Objective Summary" in tex
    assert "SO2.4 - Expand the Federated Platform" in tex
    assert "Per biobank" in tex
    assert r"\nolinkurl{bbmri-eric:ID:CZ_demo}" in tex
    assert r"\nolinkurl{promotion.partnership_interest}" in tex


def test_survey_so2_render_tex_keeps_empty_objectives_in_toc():
    """Verify survey so2 render tex keeps empty objectives in toc.

    Returns:
        None. Verifies survey so2 render tex keeps empty objectives in toc.
    """
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 1, "resolved_rows": 1, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "strategic_objectives": {
            "SO2.2": {"title": "Traceability and quality management", "description": "Traceability objective."},
            "SO2.6": {"title": "Capacities to host result data", "description": "Return-data hosting objective."},
        },
        "row_resolutions": [],
        "findings": [],
    }

    tex = module.render_tex(report)

    assert r"\subsection{SO2.2 - Traceability and quality management}" in tex
    assert r"\subsection{SO2.6 - Capacities to host result data}" in tex
    assert "No findings were mapped to this strategic objective in the current report." in tex


def test_survey_so2_render_tex_uses_appendix_and_detailed_inconsistent_values():
    """Verify survey so2 render tex uses appendix and detailed inconsistent values.

    Returns:
        None. Verifies survey so2 render tex uses appendix and detailed inconsistent values.
    """
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 2, "resolved_rows": 2, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "strategic_objectives": {},
        "row_resolutions": [
            {
                "survey_row": 6,
                "institution_name": "Demo Biobank",
                "resolution_status": "resolved_by_biobank_id",
                "resolution_reliability": "high",
                "resolution_explanation": "Resolved via biobank ID.",
                "matched_biobank_ids": ["bbmri-eric:ID:CZ_demo"],
                "matched_collection_ids": [],
            },
            {
                "survey_row": 7,
                "institution_name": "Demo Biobank",
                "resolution_status": "resolved_by_biobank_id",
                "resolution_reliability": "high",
                "resolution_explanation": "Resolved via biobank ID.",
                "matched_biobank_ids": ["bbmri-eric:ID:CZ_demo"],
                "matched_collection_ids": [],
            },
        ],
        "findings": [
            {
                "status": "consistent",
                "survey_row": 6,
                "mapping_id": "geo.country",
                "entity_type": "BIOBANK",
                "entity_id": "bbmri-eric:ID:CZ_demo",
                "explanation": "Country matches.",
                "why_relevant": "Country validates the mapping.",
                "relation_type": "exact_field",
                "reliability": "high",
                "survey_fields": ["Country"],
                "strategic_objectives": [],
                "survey_value": "CZ",
                "directory_value": "CZ",
                "proposed_update": None,
            },
            {
                "status": "inconsistent",
                "survey_row": 7,
                "mapping_id": "sample_types.materials",
                "entity_type": "COLLECTION",
                "entity_id": "bbmri-eric:ID:CZ_demo:collection:col1",
                "explanation": "Materials differ.",
                "why_relevant": "Sample types should align with materials.",
                "relation_type": "controlled_vocabulary_mapping",
                "reliability": "medium",
                "survey_fields": ["Which types of samples do you manage?"],
                "strategic_objectives": ["SO2.1"],
                "survey_value": {"expected_materials": ["WHOLE_BLOOD"]},
                "directory_value": {"observed_materials": []},
                "proposed_update": None,
            },
        ],
    }

    tex = module.render_tex(report)

    assert r"\section{Finding-Type Reference}" in tex
    assert tex.count(r"geo.country\label{appendix-geo-country}") == 1
    assert tex.count(r"sample\_\allowbreak{}types.materials\label{appendix-sample-types-materials}") == 1
    assert r"\hyperref[appendix-geo-country]{" in tex
    assert r"\nolinkurl{geo.country}" in tex
    assert r"\hyperref[appendix-sample-types-materials]{" in tex
    assert r"\nolinkurl{sample_types.materials}" in tex
    assert "Consistent." in tex
    assert r"Missing in Directory=WHOLE\_\allowbreak{}BLOOD; Extra in Directory=<empty>." in tex


def test_survey_so2_render_tex_breaks_entity_identifiers():
    """Verify survey so2 render tex breaks entity identifiers.

    Returns:
        None. Verifies survey so2 render tex breaks entity identifiers.
    """
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 1, "resolved_rows": 1, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "row_resolutions": [],
        "findings": [
            {
                "status": "inconsistent",
                "survey_row": 6,
                "mapping_id": "geo.country",
                "entity_type": "COLLECTION",
                "entity_id": "bbmri-eric:ID:NL_LUMC:collection:CRC.Cohort-1",
                "explanation": "Country differs.",
                "why_relevant": "x",
                "relation_type": "exact_field",
                "reliability": "high",
                "survey_fields": ["Country"],
                "strategic_objectives": [],
                "survey_value": "NL",
                "directory_value": "DE",
                "proposed_update": None,
            }
        ],
    }

    tex = module.render_tex(report)

    assert r"COLLECTION \texorpdfstring{\nolinkurl{bbmri-eric:ID:NL_LUMC:collection:CRC.Cohort-1}}{bbmri-eric:ID:NL_LUMC:collection:CRC.Cohort-1}" in tex


def test_escape_latex_breakable_entity_hyphenates_camel_case_segments():
    """Verify escape latex breakable entity hyphenates camel case segments.

    Returns:
        None. Verifies escape latex breakable entity hyphenates camel case segments.
    """
    module = load_module()

    rendered = module.escape_latex_breakable_entity("bbmri-eric:ID:CH_FondazioneEpatocentroTicino")

    assert r"\nolinkurl{bbmri-eric:ID:CH_Fondazione-Epatocentro-Ticino}" in rendered


def test_survey_so2_render_tex_uses_status_colors():
    """Verify survey so2 render tex uses status colors.

    Returns:
        None. Verifies survey so2 render tex uses status colors.
    """
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 1, "resolved_rows": 1, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "row_resolutions": [],
        "findings": [
            {
                "status": "inconsistent",
                "survey_row": 6,
                "mapping_id": "geo.country",
                "entity_type": "BIOBANK",
                "entity_id": "bbmri-eric:ID:CZ_demo",
                "explanation": "Country differs.",
                "why_relevant": "x",
                "relation_type": "exact_field",
                "reliability": "high",
                "survey_fields": ["Country"],
                "strategic_objectives": [],
                "survey_value": "CZ",
                "directory_value": "DE",
                "proposed_update": None,
            }
        ],
    }

    tex = module.render_tex(report)

    assert r"\usepackage[table]{xcolor}" in tex
    assert r"\definecolor{soRed}{HTML}{9E2A2B}" in tex
    assert r"\textcolor{soRed}{Inconsistent}" in tex


def test_survey_so2_render_tex_includes_toc_and_clearpage_after_title():
    """Verify survey so2 render tex includes toc and clearpage after title.

    Returns:
        None. Verifies survey so2 render tex includes toc and clearpage after title.
    """
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 0, "resolved_rows": 0, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "row_resolutions": [],
        "findings": [],
    }

    tex = module.render_tex(report)

    assert r"\maketitle" in tex
    assert r"\tableofcontents" in tex
    assert r"\clearpage" in tex
    assert tex.index(r"\maketitle") < tex.index(r"\tableofcontents") < tex.index(r"\clearpage") < tex.index(r"\section{Summary}")


def test_resolve_row_normalizes_collection_scope_and_avoids_geneva_bern_mixup():
    """Verify resolve row normalizes collection scope and avoids geneva bern mixup.

    Returns:
        None. Verifies resolve row normalizes collection scope and avoids geneva bern mixup.
    """
    module = load_module()
    directory = SwissResolutionDirectoryStub()
    biobank_index = {biobank["id"]: biobank for biobank in directory.getBiobanks()}
    collection_index = {collection["id"]: collection for collection in directory.getCollections()}
    network_index = {}
    contacts_by_email = {}
    biobank_ids_by_contact, collection_ids_by_contact = module.build_contact_usage_indexes(biobank_index, collection_index)
    biobanks_by_normalized_name = {}
    biobanks_by_alias = {}
    biobanks_by_signature = {}
    for biobank in directory.getBiobanks():
        biobanks_by_normalized_name.setdefault(module.normalize_text(biobank.get("name")), []).append(biobank)
        for alias in module.institution_aliases(biobank.get("name")).union(module.biobank_id_aliases(biobank.get("id"))):
            biobanks_by_alias.setdefault(alias, []).append(biobank)
        biobanks_by_signature.setdefault(module.normalized_institution_signature(biobank.get("name")), []).append(biobank)
    collection_contact_domain_counts = {
        "unige.ch": {"bbmri-eric:ID:CH_Unige": 1, "bbmri-eric:ID:CH_HopitauxUniversitairesGeneve": 1},
        "unibe.ch": {"bbmri-eric:ID:CH_UniversityOfBern": 2},
    }

    veterinary_row = {
        "Name of Institution": "Insitute of Genetics, Vetsuisse Faculty, University of Bern",
        "BiobankID in the Directory (if available)": "bbmri-eric:ID:CH_UniversityOfBern",
        "List of CollectionID in the Directory (if you only represent a part of a biobank; please use ';' as separator in case of more than 1 ID)": "CH_UniversityOfBern:collection:CH_VetSuisseBiobankVETGENBERN",
        "Country": "Switzerland",
        "E-Mail address": "michaela.droegemueller@unibe.ch",
        "Research field": "genetic traits and diseases in animals",
        "What field of research does your biobank or biomolecular resource support? (Select all that apply)": "Other (please specify):",
    }
    veterinary_resolution = module.resolve_row(
        __import__("pandas").Series(veterinary_row),
        17,
        directory,
        biobank_index,
        collection_index,
        network_index,
        contacts_by_email,
        biobank_ids_by_contact,
        collection_ids_by_contact,
        biobanks_by_normalized_name,
        biobanks_by_alias,
        biobanks_by_signature,
        collection_contact_domain_counts,
    )
    assert veterinary_resolution["matched_biobank_ids"] == ["bbmri-eric:ID:CH_UniversityOfBern"]
    assert veterinary_resolution["matched_collection_ids"] == [
        "bbmri-eric:ID:CH_UniversityOfBern:collection:CH_VetSuisseBiobankVETGENBERN"
    ]

    geneva_row = {
        "Name of Institution": "University of Geneva",
        "BiobankID in the Directory (if available)": "",
        "List of CollectionID in the Directory (if you only represent a part of a biobank; please use ';' as separator in case of more than 1 ID)": "",
        "Country": "Switzerland",
        "E-Mail address": "valerie.dutoit@unige.ch",
    }
    geneva_resolution = module.resolve_row(
        __import__("pandas").Series(geneva_row),
        57,
        directory,
        biobank_index,
        collection_index,
        network_index,
        contacts_by_email,
        biobank_ids_by_contact,
        collection_ids_by_contact,
        biobanks_by_normalized_name,
        biobanks_by_alias,
        biobanks_by_signature,
        collection_contact_domain_counts,
    )
    assert "bbmri-eric:ID:CH_UniversityOfBern" not in geneva_resolution["matched_biobank_ids"]


def test_normalize_biobank_id_accepts_bare_directory_id():
    """Verify normalize biobank id accepts bare directory id.

    Returns:
        None. Verifies normalize biobank id accepts bare directory id.
    """
    module = load_module()

    assert module.normalize_biobank_id("NL_AUMCBB") == "bbmri-eric:ID:NL_AUMCBB"
    assert module.normalize_biobank_id("bbmri-eric:ID:NL_AUMCBB") == "bbmri-eric:ID:NL_AUMCBB"


def test_resolve_row_matches_bare_biobank_id_and_falls_back_from_invalid_explicit_id():
    """Verify resolve row matches bare biobank id and falls back from invalid explicit id.

    Returns:
        None. Verifies resolve row matches bare biobank id and falls back from invalid explicit id.
    """
    module = load_module()
    directory = DirectoryStub()
    biobank_index = {biobank["id"]: biobank for biobank in directory.getBiobanks()}
    collection_index = {collection["id"]: collection for collection in directory.getCollections()}
    network_index = {}
    contacts_by_email = {directory.getContacts()[0]["email"]: directory.getContacts()}
    biobank_ids_by_contact, collection_ids_by_contact = module.build_contact_usage_indexes(biobank_index, collection_index)
    biobanks_by_normalized_name = {}
    biobanks_by_alias = {}
    biobanks_by_signature = {}
    for biobank in directory.getBiobanks():
        biobanks_by_normalized_name.setdefault(module.normalize_text(biobank.get("name")), []).append(biobank)
        for alias in module.institution_aliases(biobank.get("name")).union(module.biobank_id_aliases(biobank.get("id"))):
            biobanks_by_alias.setdefault(alias, []).append(biobank)
        biobanks_by_signature.setdefault(module.normalized_institution_signature(biobank.get("name")), []).append(biobank)

    row = {
        "Name of Institution": "Demo Biobank",
        "BiobankID in the Directory (if available)": "CZ_demo",
        "List of CollectionID in the Directory (if you only represent a part of a biobank; please use ';' as separator in case of more than 1 ID)": "",
        "Country": "Czech Republic",
        "E-Mail address": "contact@example.org",
    }
    resolved = module.resolve_row(
        __import__("pandas").Series(row),
        0,
        directory,
        biobank_index,
        collection_index,
        network_index,
        contacts_by_email,
        biobank_ids_by_contact,
        collection_ids_by_contact,
        biobanks_by_normalized_name,
        biobanks_by_alias,
        biobanks_by_signature,
        {},
    )
    assert resolved["resolution_status"] == "resolved_by_biobank_id"
    assert resolved["matched_biobank_ids"] == ["bbmri-eric:ID:CZ_demo"]

    row["BiobankID in the Directory (if available)"] = "CZ_missing"
    resolved = module.resolve_row(
        __import__("pandas").Series(row),
        0,
        directory,
        biobank_index,
        collection_index,
        network_index,
        contacts_by_email,
        biobank_ids_by_contact,
        collection_ids_by_contact,
        biobanks_by_normalized_name,
        biobanks_by_alias,
        biobanks_by_signature,
        {},
    )
    assert resolved["resolution_status"] == "resolved_by_contact_email"
    assert resolved["matched_biobank_ids"] == ["bbmri-eric:ID:CZ_demo"]
    assert "Survey biobank ID CZ_missing does not exist in schema ERIC." in resolved["resolution_explanation"]


def test_alias_and_acronym_matching_supports_chuv_and_small_typos():
    """Verify alias and acronym matching supports chuv and small typos.

    Returns:
        None. Verifies alias and acronym matching supports chuv and small typos.
    """
    module = load_module()

    assert module.normalize_text(float("nan")) == ""
    assert module.normalize_text("Hôpitaux Universitaires Genève") == "hopitaux university geneve"

    aliases = module.institution_aliases("Centre Hospitalier Universitaire Vaudois")
    assert "chuv" in aliases

    biobank = {
        "id": "bbmri-eric:ID:CH_CHUV",
        "name": "Centre Hospitalier Universitaire Vaudois",
        "country": "CH",
    }
    biobanks_by_alias = {}
    for alias in module.institution_aliases(biobank["name"]).union(module.biobank_id_aliases(biobank["id"])):
        biobanks_by_alias.setdefault(alias, []).append(biobank)

    alias_candidates = module.match_biobank_alias_candidates({"chuv"}, biobanks_by_alias, country="CH")
    assert [candidate["id"] for candidate in alias_candidates] == ["bbmri-eric:ID:CH_CHUV"]

    score = max(
        __import__("difflib").SequenceMatcher(None, survey_key, candidate_key).ratio()
        for survey_key in module.institution_aliases("Leids Universtair Medical Center")
        for candidate_key in module.institution_aliases("Leiden University Medical Center Biobank")
    )
    assert score >= 0.82


def test_resolve_row_matches_chuv_alias_even_with_invalid_explicit_biobank_id():
    """Verify resolve row matches chuv alias even with invalid explicit biobank id.

    Returns:
        None. Verifies resolve row matches chuv alias even with invalid explicit biobank id.
    """
    module = load_module()

    class ChuvDirectoryStub:
        """Expose CHUV under its full French name for acronym/typo respondent matching.
        """
        def getSchema(self):
            """Return schema string selected for the fake Directory session.

            Returns:
                The schema string selected for the fake Directory session.
            """
            return "ERIC"

        def getBiobanks(self):
            """Return synthetic biobank records available to the code under test.

            Returns:
                The synthetic biobank records available to the code under test.
            """
            return [
                {
                    "id": "bbmri-eric:ID:CH_CHUV",
                    "name": "Centre Hospitalier Universitaire Vaudois",
                    "country": "CH",
                }
            ]

        def getCollections(self):
            """Return synthetic collection records available to the code under test.

            Returns:
                The synthetic collection records available to the code under test.
            """
            return [
                {
                    "id": "bbmri-eric:ID:CH_CHUV:collection:demo",
                    "biobank": {"id": "bbmri-eric:ID:CH_CHUV"},
                    "name": "Demo collection",
                    "description": "",
                    "type": ["SAMPLE"],
                    "materials": ["SERUM"],
                }
            ]

        def getGraphBiobankCollectionsFromBiobank(self, biobank_id):
            """Return fixture graph relating the requested biobank to its collections.

            Args:
                biobank_id: Biobank identifier used to obtain the fixture collection graph.

            Returns:
                The fixture graph relating the requested biobank to its collections.
            """
            import networkx as nx

            graph = nx.DiGraph()
            graph.add_node(biobank_id)
            graph.add_node("bbmri-eric:ID:CH_CHUV:collection:demo")
            graph.add_edge(biobank_id, "bbmri-eric:ID:CH_CHUV:collection:demo")
            return graph

    directory = ChuvDirectoryStub()
    biobank_index = {biobank["id"]: biobank for biobank in directory.getBiobanks()}
    collection_index = {collection["id"]: collection for collection in directory.getCollections()}
    network_index = {}
    contacts_by_email = {}
    biobank_ids_by_contact, collection_ids_by_contact = module.build_contact_usage_indexes(biobank_index, collection_index)
    biobanks_by_normalized_name = {}
    biobanks_by_alias = {}
    biobanks_by_signature = {}
    for biobank in directory.getBiobanks():
        biobanks_by_normalized_name.setdefault(module.normalize_text(biobank.get("name")), []).append(biobank)
        for alias in module.institution_aliases(biobank.get("name")).union(module.biobank_id_aliases(biobank.get("id"))):
            biobanks_by_alias.setdefault(alias, []).append(biobank)
        biobanks_by_signature.setdefault(module.normalized_institution_signature(biobank.get("name")), []).append(biobank)

    row = {
        "Name of Institution": "CHUV",
        "BiobankID in the Directory (if available)": "BB_038",
        "Country": "Switzerland",
        "E-Mail address": "nathalie.vionnet@chuv.ch",
    }
    resolved = module.resolve_row(
        __import__("pandas").Series(row),
        25,
        directory,
        biobank_index,
        collection_index,
        network_index,
        contacts_by_email,
        biobank_ids_by_contact,
        collection_ids_by_contact,
        biobanks_by_normalized_name,
        biobanks_by_alias,
        biobanks_by_signature,
        {},
    )
    assert resolved["resolution_status"] == "resolved_by_institution_name_certain"
    assert resolved["matched_biobank_ids"] == ["bbmri-eric:ID:CH_CHUV"]
    assert "Resolved by institution alias/acronym match" in resolved["resolution_explanation"]


def test_resolve_row_uses_exact_contact_email_before_name_matching():
    """Verify resolve row uses exact contact email before name matching.

    Returns:
        None. Verifies resolve row uses exact contact email before name matching.
    """
    module = load_module()

    class ContactDirectoryStub(DirectoryStub):
        """Change the official biobank name and owner email to isolate contact-based resolution.
        """
        def __init__(self, *args, **kwargs):
            """Populate the institution, collection, and contact records used by respondent-resolution assertions.

            Args:
                *args: Directory constructor positional arguments, forwarded by subclasses and ignored by the base stub.
                **kwargs: Directory constructor options; only schema is used (default ERIC), and subclasses forward these unchanged.
            """
            super().__init__(*args, **kwargs)
            self._biobank["name"] = "Different Official Name"
            self._contact["email"] = "owner@example.org"

    directory = ContactDirectoryStub()
    biobank_index = {biobank["id"]: biobank for biobank in directory.getBiobanks()}
    collection_index = {collection["id"]: collection for collection in directory.getCollections()}
    contact_index = {contact["id"]: contact for contact in directory.getContacts()}
    network_index = {}
    contacts_by_email = {"owner@example.org": directory.getContacts()}
    biobank_ids_by_contact, collection_ids_by_contact = module.build_contact_usage_indexes(biobank_index, collection_index)
    biobanks_by_normalized_name = {}
    biobanks_by_alias = {}
    biobanks_by_signature = {}
    for biobank in directory.getBiobanks():
        biobanks_by_normalized_name.setdefault(module.normalize_text(biobank.get("name")), []).append(biobank)
        for alias in module.institution_aliases(biobank.get("name")).union(module.biobank_id_aliases(biobank.get("id"))):
            biobanks_by_alias.setdefault(alias, []).append(biobank)
        biobanks_by_signature.setdefault(module.normalized_institution_signature(biobank.get("name")), []).append(biobank)
    row = {
        "Name of Institution": "Completely Different Survey Name",
        "BiobankID in the Directory (if available)": "",
        "Country": "Czech Republic",
        "E-Mail address": "owner@example.org",
    }
    resolved = module.resolve_row(
        __import__("pandas").Series(row),
        0,
        directory,
        biobank_index,
        collection_index,
        network_index,
        contacts_by_email,
        biobank_ids_by_contact,
        collection_ids_by_contact,
        biobanks_by_normalized_name,
        biobanks_by_alias,
        biobanks_by_signature,
        {},
    )
    assert resolved["resolution_status"] == "resolved_by_contact_email"
    assert resolved["matched_biobank_ids"] == ["bbmri-eric:ID:CZ_demo"]
    assert resolved["matched_contact_ids"] == ["bbmri-eric:contactID:CZ_demo_1"]


def test_resolve_row_marks_dangling_contact_biobank_references_for_manual_review():
    """Verify resolve row marks dangling contact biobank references for manual review.

    Returns:
        None. Verifies resolve row marks dangling contact biobank references for manual review.
    """
    module = load_module()

    class DanglingContactDirectoryStub:
        """Expose a Spanish contact referencing a biobank absent from the loaded snapshot.
        """
        def getSchema(self):
            """Return schema string selected for the fake Directory session.

            Returns:
                The schema string selected for the fake Directory session.
            """
            return "ERIC"

        def getBiobanks(self):
            """Return synthetic biobank records available to the code under test.

            Returns:
                The synthetic biobank records available to the code under test.
            """
            return []

        def getCollections(self):
            """Return synthetic collection records available to the code under test.

            Returns:
                The synthetic collection records available to the code under test.
            """
            return []

        def getContacts(self):
            """Return synthetic contact records available to the code under test.

            Returns:
                The synthetic contact records available to the code under test.
            """
            return [
                {
                    "id": "bbmri-eric:contactID:ES_demo",
                    "email": "demo@example.org",
                    "biobanks": [{"id": "bbmri-eric:ID:ES_MISSING"}],
                }
            ]

        def getNetworks(self):
            """Return synthetic network records available to the code under test.

            Returns:
                The synthetic network records available to the code under test.
            """
            return []

    directory = DanglingContactDirectoryStub()
    biobank_index = {}
    collection_index = {}
    contact_index = {contact["id"]: contact for contact in directory.getContacts()}
    network_index = {}
    contacts_by_email = {"demo@example.org": directory.getContacts()}
    biobanks_by_normalized_name = {}
    biobanks_by_alias = {}
    biobanks_by_signature = {}
    resolved = module.resolve_row(
        __import__("pandas").Series(
            {
                "Name of Institution": "Demo",
                "BiobankID in the Directory (if available)": "",
                "Country": "Spain",
                "E-Mail address": "demo@example.org",
            }
        ),
        0,
        directory,
        biobank_index,
        collection_index,
        network_index,
        contacts_by_email,
        {},
        {},
        biobanks_by_normalized_name,
        biobanks_by_alias,
        biobanks_by_signature,
        {},
    )
    assert resolved["resolution_status"] == "manual_review"
    assert "bbmri-eric:ID:ES_MISSING" in resolved["resolution_explanation"]
    assert resolved["matched_contact_ids"] == ["bbmri-eric:contactID:ES_demo"]


def test_resolve_row_supports_explicit_network_id():
    """Verify resolve row supports explicit network id.

    Returns:
        None. Verifies resolve row supports explicit network id.
    """
    module = load_module()
    directory = DirectoryStub()
    biobank_index = {biobank["id"]: biobank for biobank in directory.getBiobanks()}
    collection_index = {collection["id"]: collection for collection in directory.getCollections()}
    contact_index = {contact["id"]: contact for contact in directory.getContacts()}
    network_index = {"bbmri-eric:networkID:DE_DKTK": {"id": "bbmri-eric:networkID:DE_DKTK", "name": "DKTK"}}
    contacts_by_email = {directory.getContacts()[0]["email"]: directory.getContacts()}
    biobank_ids_by_contact, collection_ids_by_contact = module.build_contact_usage_indexes(biobank_index, collection_index)
    biobanks_by_normalized_name = {}
    biobanks_by_alias = {}
    biobanks_by_signature = {}
    for biobank in directory.getBiobanks():
        biobanks_by_normalized_name.setdefault(module.normalize_text(biobank.get("name")), []).append(biobank)
        for alias in module.institution_aliases(biobank.get("name")).union(module.biobank_id_aliases(biobank.get("id"))):
            biobanks_by_alias.setdefault(alias, []).append(biobank)
        biobanks_by_signature.setdefault(module.normalized_institution_signature(biobank.get("name")), []).append(biobank)
    resolved = module.resolve_row(
        __import__("pandas").Series(
            {
                "Name of Institution": "German Cancer Consortium",
                "BiobankID in the Directory (if available)": "bbmri-eric:networkID:DE_DKTK",
                "Country": "Germany",
                "E-Mail address": "",
            }
        ),
        0,
        directory,
        biobank_index,
        collection_index,
        network_index,
        contacts_by_email,
        biobank_ids_by_contact,
        collection_ids_by_contact,
        biobanks_by_normalized_name,
        biobanks_by_alias,
        biobanks_by_signature,
        {},
    )
    assert resolved["resolution_status"] == "resolved_by_network_id"
    assert resolved["matched_network_ids"] == ["bbmri-eric:networkID:DE_DKTK"]


def test_survey_so2_render_tex_adds_directory_fields_missing_country_prefix_and_breakable_emails():
    """Verify survey so2 render tex adds directory fields missing country prefix and breakable emails.

    Returns:
        None. Verifies survey so2 render tex adds directory fields missing country prefix and breakable emails.
    """
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 2, "resolved_rows": 1, "missing_rows": 1, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "row_resolutions": [
            {
                "survey_row": 6,
                "institution_name": "Demo Biobank",
                "resolution_status": "resolved_by_biobank_id",
                "resolution_reliability": "high",
                "resolution_explanation": "Resolved via biobank ID bbmri-eric:ID:CZ_demo:collection:col1.",
                "matched_biobank_ids": ["bbmri-eric:ID:CZ_demo"],
                "matched_collection_ids": ["bbmri-eric:ID:CZ_demo:collection:col1"],
            }
        ],
        "findings": [
            {
                "status": "missing_from_directory",
                "survey_row": 7,
                "mapping_id": "row_resolution",
                "entity_type": "BIOBANK",
                "entity_id": "NL_AUMCBB",
                "explanation": "No exact-ID or institution-name-based match was found in the Directory.",
                "why_relevant": "Mapping must be resolved first.",
                "relation_type": "entity_resolution",
                "reliability": "low",
                "survey_fields": ["Country", "E-Mail address"],
                "survey_value": {"country": "NL", "institution_name": "AUMC", "email": "contact.person@example.org"},
                "directory_value": {"matched_biobank_ids": []},
                "proposed_update": None,
            },
            {
                "status": "missing_in_directory",
                "survey_row": 6,
                "mapping_id": "imaging.wsi_presence",
                "entity_type": "BIOBANK",
                "entity_id": "bbmri-eric:ID:CZ_demo",
                "explanation": "Survey-reported WSI availability is not reflected by generic imaging metadata or text.",
                "why_relevant": "Imaging comparison.",
                "relation_type": "derived_presence",
                "reliability": "medium",
                "survey_fields": ["Radiology / WSI"],
                "survey_value": {"answer": "Yes"},
                "directory_value": {"has_image_support": False, "has_wsi_hint": False},
                "proposed_update": None,
            },
            {
                "status": "manual_review",
                "survey_row": 6,
                "mapping_id": "contact.email",
                "entity_type": "CONTACT",
                "entity_id": "bbmri-eric:contactID:CZ_demo_1",
                "explanation": "Respondent email differs from Directory contact email.",
                "why_relevant": "Contact comparison.",
                "relation_type": "exact_field",
                "reliability": "high",
                "survey_fields": ["E-Mail address"],
                "survey_value": "contact.person@example.org",
                "directory_value": "data.owner@example.org",
                "proposed_update": None,
            },
            {
                "status": "inconsistent",
                "survey_row": 6,
                "mapping_id": "sample_types.materials",
                "entity_type": "COLLECTION",
                "entity_id": "bbmri-eric:ID:CZ_demo:collection:col1",
                "explanation": "Inconsistent material types between survey and Directory collection.",
                "why_relevant": "Material comparison.",
                "relation_type": "controlled_vocabulary_mapping",
                "reliability": "medium",
                "survey_fields": ["Which types of samples do you manage?"],
                "survey_value": {"expected_materials": ["DNA", "SERUM"]},
                "directory_value": {"observed_materials": ["DNA", "SALIVA"]},
                "proposed_update": None,
            },
        ],
    }

    tex = module.render_tex(report)

    assert r"\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}" in tex
    assert r"\begin{longtable}{L{1.5cm}L{3.2cm}L{3.2cm}L{6.5cm}}" in tex
    assert r"(NL) BIOBANK \texorpdfstring{\nolinkurl{NL_AUMCBB}}{NL_AUMCBB}" in tex
    assert r"\nolinkurl{contact.person@example.org}" in tex
    assert r"Missing in Directory=SERUM; Extra in Directory=SALIVA." in tex
    assert "These findings are linked to a concrete Directory entity" in tex
    assert "These findings have a plausible survey-to-Directory relation" in tex
    assert "These findings cover survey respondents or identifiers that could not be mapped confidently" in tex
    assert "These findings indicate a concrete mismatch between the survey answer and the mapped Directory metadata" in tex
    assert r"\subsection{\textcolor{soRed}{Survey Data Missing from the Directory}}" in tex
    assert r"\subsection{\textcolor{soOrange}{Data Requiring Manual Review}}" in tex
    assert r"\subsection{\textcolor{soOrange}{Entities Not Mapped to the Directory}}" in tex
    assert r"\textbf{Directory field(s):} COLLECTION.materials\\" in tex
    assert r"\textbf{Comparison method:} Map structured survey sample-type answers" in tex


def test_findings_by_status_orders_missing_in_directory_manual_review_and_missing_from_directory():
    """Verify findings by status orders missing in directory manual review and missing from directory.

    Returns:
        None. Verifies findings by status orders missing in directory manual review and missing from directory.
    """
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 2, "resolved_rows": 0, "missing_rows": 1, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "row_resolutions": [],
        "findings": [
            {
                "status": "missing_from_directory",
                "survey_row": 7,
                "mapping_id": "row_resolution",
                "entity_type": "BIOBANK",
                "entity_id": "NL_AUMCBB",
                "explanation": "Missing.",
                "why_relevant": "x",
                "relation_type": "entity_resolution",
                "reliability": "low",
                "survey_fields": [],
                "survey_value": {"country": "NL"},
                "directory_value": {"matched_biobank_ids": []},
                "proposed_update": None,
            },
            {
                "status": "missing_in_directory",
                "survey_row": 5,
                "mapping_id": "imaging.wsi_presence",
                "entity_type": "BIOBANK",
                "entity_id": "bbmri-eric:ID:CZ_demo",
                "explanation": "Missing in directory.",
                "why_relevant": "z",
                "relation_type": "derived_presence",
                "reliability": "medium",
                "survey_fields": [],
                "survey_value": "yes",
                "directory_value": "no",
                "proposed_update": None,
            },
            {
                "status": "manual_review",
                "survey_row": 6,
                "mapping_id": "contact.email",
                "entity_type": "CONTACT",
                "entity_id": "bbmri-eric:contactID:CZ_demo_1",
                "explanation": "Manual review.",
                "why_relevant": "y",
                "relation_type": "exact_field",
                "reliability": "high",
                "survey_fields": [],
                "survey_value": "a",
                "directory_value": "b",
                "proposed_update": None,
            },
        ],
    }
    tex = module.render_tex(report)
    assert tex.index(r"\subsection{\textcolor{soRed}{Survey Data Missing from the Directory}}") < tex.index(
        r"\subsection{\textcolor{soOrange}{Data Requiring Manual Review}}"
    )
    assert tex.index(r"\subsection{\textcolor{soOrange}{Data Requiring Manual Review}}") < tex.index(
        r"\subsection{\textcolor{soOrange}{Entities Not Mapped to the Directory}}"
    )


def test_findings_by_status_adds_intro_for_ambiguous_section():
    """Verify findings by status adds intro for ambiguous section.

    Returns:
        None. Verifies findings by status adds intro for ambiguous section.
    """
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 1, "resolved_rows": 0, "missing_rows": 0, "ambiguous_rows": 1, "proposed_update_findings": 0},
        "row_resolutions": [],
        "findings": [
            {
                "status": "ambiguous",
                "survey_row": 1,
                "mapping_id": "row_resolution",
                "entity_type": "BIOBANK",
                "entity_id": "Demo",
                "explanation": "Ambiguous.",
                "why_relevant": "x",
                "relation_type": "entity_resolution",
                "reliability": "low",
                "survey_fields": [],
                "survey_value": {"institution_name": "Demo"},
                "directory_value": {"matched_biobank_ids": ["A", "B"]},
                "proposed_update": None,
            },
        ],
    }
    tex = module.render_tex(report)
    assert "These findings indicate that the available survey and Directory evidence supports more than one plausible interpretation or mapping." in tex


def test_findings_by_status_keeps_stable_sections_when_one_status_has_no_findings():
    """Verify findings by status keeps stable sections when one status has no findings.

    Returns:
        None. Verifies findings by status keeps stable sections when one status has no findings.
    """
    module = load_module()
    report = {
        "report_metadata": {"generated_at": "2026-03-13T00:00:00+00:00"},
        "summary": {"survey_rows": 2, "resolved_rows": 0, "missing_rows": 1, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "row_resolutions": [],
        "findings": [
            {
                "status": "manual_review",
                "survey_row": 6,
                "mapping_id": "contact.email",
                "entity_type": "CONTACT",
                "entity_id": "bbmri-eric:contactID:CZ_demo_1",
                "explanation": "Manual review.",
                "why_relevant": "y",
                "relation_type": "exact_field",
                "reliability": "high",
                "survey_fields": [],
                "survey_value": "a",
                "directory_value": "b",
                "proposed_update": None,
            },
            {
                "status": "missing_from_directory",
                "survey_row": 7,
                "mapping_id": "row_resolution",
                "entity_type": "BIOBANK",
                "entity_id": "NL_AUMCBB",
                "explanation": "Missing.",
                "why_relevant": "x",
                "relation_type": "entity_resolution",
                "reliability": "low",
                "survey_fields": [],
                "survey_value": {"country": "NL"},
                "directory_value": {"matched_biobank_ids": []},
                "proposed_update": None,
            },
        ],
    }
    tex = module.render_tex(report)
    assert r"\subsection{\textcolor{soRed}{Survey Data Missing from the Directory}}" in tex
    assert "No findings with this status in the current report." in tex
    assert tex.index(r"\subsection{\textcolor{soRed}{Survey Data Missing from the Directory}}") < tex.index(
        r"\subsection{\textcolor{soOrange}{Data Requiring Manual Review}}"
    )


def test_summarize_collection_scope_uses_all_collections_and_all_except():
    """Verify summarize collection scope uses all collections and all except.

    Returns:
        None. Verifies summarize collection scope uses all collections and all except.
    """
    module = load_module()

    assert module.summarize_collection_scope(["c1", "c2"], ["c1", "c2"]) == "all collections"
    assert module.summarize_collection_scope(["c1", "c3"], ["c1", "c2", "c3"]) == "c1, c3"
    assert module.summarize_collection_scope(["c1", "c3", "c4", "c5"], ["c1", "c2", "c3", "c4", "c5", "c6"]) == "All except c2, c6"
    assert module.summarize_collection_scope(["c1"], ["c1", "c2", "c3", "c4", "c5", "c6"]) == "c1"



def test_survey_so2_render_tex_includes_so21_technology_matrix():
    """Verify survey so2 render tex includes so21 technology matrix.

    Returns:
        None. Verifies survey so2 render tex includes so21 technology matrix.
    """
    module = load_module()
    technology_rows = [
        {
            "survey_row": 7,
            "institution_name": "Gamma Biobank",
            "matched_biobank_ids": "bbmri-eric:ID:CZ_gamma",
            "matched_collection_ids": "",
            "resolution_status": "resolved_by_biobank_id",
            "sequencing": 1,
            "genotyping_panels": 0,
            "radiology": 1,
            "pathology": 1,
            "proteomics": 0,
            "metabolomics": 0,
            "other_technology": 0,
            "has_any_modality": 1,
        },
        {
            "survey_row": 8,
            "institution_name": "Alpha Biobank",
            "matched_biobank_ids": "bbmri-eric:ID:CZ_alpha",
            "matched_collection_ids": "",
            "resolution_status": "resolved_by_biobank_id",
            "sequencing": 1,
            "genotyping_panels": 0,
            "radiology": 0,
            "pathology": 0,
            "proteomics": 0,
            "metabolomics": 0,
            "other_technology": 0,
            "has_any_modality": 1,
        },
    ]
    report = {
        "report_metadata": {"generated_at": "2026-03-19T00:00:00+00:00"},
        "summary": {"survey_rows": 2, "resolved_rows": 2, "missing_rows": 0, "ambiguous_rows": 0, "proposed_update_findings": 0},
        "findings": [],
        "row_resolutions": [],
        "strategic_objectives": {"SO2.1": {"title": "Datafication at source", "description": "x"}},
        "technology_modalities": module.build_technology_modalities_payload(technology_rows),
    }
    tex = module.render_tex(report)
    assert "Technology Modality Matrix" in tex
    assert "Gamma Biobank" in tex
    assert "Alpha Biobank" in tex
    assert tex.index("Gamma Biobank") < tex.index("Alpha Biobank")
    assert "NGS & G/P & Rad & Path & Prot & Met & Other & N" in tex


def test_technology_modalities_combine_question_sources_and_render_inconsistencies(tmp_path):
    """Verify technology modalities combine question sources and render inconsistencies.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies technology modalities combine question sources and render inconsistencies.
    """
    module = load_module()
    survey_row = __import__("pandas").Series(
        {
            "Name of Institution": "Demo Biobank",
            "Does the repository have a direct access to data from any of the following technologies? (Select all that apply)": "I don’t know",
            "Does your biobank provide access to radiology datasets?": "Yes — access to internally generated radiology data collections (e.g., directly connected to a PACS system)",
            "Does your biobank provide access to whole-slide image (WSI) histopathology datasets? E.g., disease-focused cohorts with clinical and/or molecular annotations or normal-tissue reference histology across multiple organs from non-diseased donors?": "Yes — access to internally generated WSI data collections",
        }
    )
    row_resolution = {
        "survey_row": 1,
        "resolution_status": "missing_from_directory",
        "matched_biobank_ids": [],
        "matched_collection_ids": [],
    }
    technology_row = module.build_technology_modality_row(survey_row, row_resolution)
    payload = module.build_technology_modalities_payload([technology_row])

    assert technology_row["radiology"] == 1
    assert technology_row["pathology"] == 1
    assert technology_row["radiology_field_present"] == 0
    assert technology_row["pathology_field_present"] == 0
    assert technology_row["radiology_question_present"] == 1
    assert technology_row["pathology_question_present"] == 1
    assert technology_row["radiology_inconsistent"] == 1
    assert technology_row["pathology_inconsistent"] == 1
    assert payload["summary"]["modality_counts"]["radiology"] == 1
    assert payload["summary"]["modality_counts"]["pathology"] == 1
    assert payload["summary"]["field_only_counts"]["radiology"] == 0
    assert payload["summary"]["field_only_counts"]["pathology"] == 0
    assert payload["summary"]["question_yes_counts"]["radiology"] == 1
    assert payload["summary"]["question_yes_counts"]["pathology"] == 1
    assert payload["summary"]["inconsistency_counts"]["radiology"] == 1
    assert payload["summary"]["inconsistency_counts"]["pathology"] == 1

    report = {
        "report_metadata": {"generated_at": "2026-03-18T00:00:00+00:00"},
        "summary": {
            "survey_rows": 1,
            "resolved_rows": 0,
            "missing_rows": 1,
            "ambiguous_rows": 0,
            "proposed_update_findings": 0,
        },
        "findings": [],
        "row_resolutions": [row_resolution],
        "strategic_objectives": {},
        "technology_modalities": payload,
    }
    tex = module.render_tex(report)
    assert "Technology Modalities" in tex
    assert "Field/question mismatches: Radiology=1, Pathology/WSI=1" in tex
    assert "Technology Source Inconsistencies" in tex

def test_survey_so2_render_report_can_write_only_technology_upset_artifacts(tmp_path):
    """Verify survey so2 render report can write only technology upset artifacts.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies survey so2 render report can write only technology upset artifacts.
    """
    module = load_module()
    survey_row = __import__("pandas").Series(
        {
            "Name of Institution": "Demo Biobank",
            "Does the repository have a direct access to data from any of the following technologies? (Select all that apply)": "Next-gen sequencing (if yes, specify technology/vendor)",
            "Next-gen sequencing technology/vendor": "Illumina",
        }
    )
    row_resolution = {
        "survey_row": 1,
        "resolution_status": "resolved_by_biobank_id",
        "matched_biobank_ids": ["bbmri-eric:ID:CZ_demo"],
        "matched_collection_ids": ["bbmri-eric:ID:CZ_demo:collection:col1"],
    }
    technology_rows = [module.build_technology_modality_row(survey_row, row_resolution)]
    report = {
        "report_metadata": {"generated_at": "2026-03-18T00:00:00+00:00"},
        "summary": {},
        "findings": [],
        "row_resolutions": [],
        "strategic_objectives": {},
        "technology_modalities": module.build_technology_modalities_payload(technology_rows),
    }
    input_json = tmp_path / "report.json"
    input_json.write_text(json.dumps(report), encoding="utf-8")
    upset_prefix = tmp_path / "render-only"

    args = Namespace(
        input_json=str(input_json),
        output_tex=None,
        output_pdf=None,
        output_tech_upset_prefix=str(upset_prefix),
        verbose=False,
        debug=False,
    )

    result = module.run_render(args)

    assert result == module.EXIT_OK
    assert (tmp_path / "render-only-technology-upset.csv").exists()
    assert (tmp_path / "render-only-technology-upset.R").exists()
