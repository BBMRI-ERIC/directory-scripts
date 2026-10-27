"""Peer-command CLI and unchanged SO2 command parsing regression tests."""

from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path


def test_merge_is_peer_command_with_explicit_sources():
    """Parse the approved merge command without adding a describe mode or flag.

    Returns:
        None. Source, output and withdrawal arguments remain independently addressable.
    """
    spec = spec_from_file_location("so2_merge_cli_test", Path(__file__).parents[1] / "survey-so2-directory.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    parser = module.build_cli()
    args = parser.parse_args(["merge-mucp", "-i", "so2.xlsx", "--descriptive-schema", "schema.json",
                              "--form-json", "form.json", "--mucp-json", "mucp.json", "--mucp-schema", "mucp.schema.json",
                              "-o", "combined.json", "-w", "--output-upset-r-dir", "upsets"])
    assert args.command == "merge-mucp"
    assert args.include_withdrawn is True
    assert args.include_contact_details is False
    assert args.output_upset_r_dir == "upsets"
    assert args.extended_evidence is False
    assert args.include_upset_deviations is False
    assert args.table_biobank_repeated_entries == "empty"
    assert parser.parse_args(["merge-mucp", "-i", "s.xlsx", "--descriptive-schema", "s.json",
        "--form-json", "f.json", "--mucp-json", "m.json", "--mucp-schema", "ms.json",
        "-o", "o.json", "--include-upset-deviations"]).include_upset_deviations is True
    assert parser.parse_args(["merge-mucp", "-i", "s.xlsx", "--descriptive-schema", "s.json",
        "--form-json", "f.json", "--mucp-json", "m.json", "--mucp-schema", "ms.json",
        "-o", "o.json", "--extended-evidence"]).extended_evidence is True
    assert parser.parse_args(["merge-mucp", "-i", "s.xlsx", "--descriptive-schema", "s.json",
        "--form-json", "f.json", "--mucp-json", "m.json", "--mucp-schema", "ms.json",
        "-o", "o.json", "--table-biobank-repeated-entries", "dtto"]).table_biobank_repeated_entries == "dtto"
    describe_options = parser._subparsers._group_actions[0].choices["describe"]._option_string_actions
    assert "--table-biobank-repeated-entries" not in describe_options


def test_zero_overlap_publishes_json_review_and_heatmap_omission(tmp_path):
    """Publish an empty overlap cohort without inventing heatmap response categories.

    Args:
        tmp_path: Isolated directory for synthetic survey inputs and published outputs.

    Returns:
        None. JSON and matching review publish, and TeX explains the omitted panel.
    """
    import json
    from survey_combined import execute_merge
    from test_survey_merge_mucp_integration import fixture_arguments, FakeDirectory

    args = fixture_arguments(tmp_path)
    args.join = "inner"
    source = json.loads(Path(args.mucp_json).read_text())
    selectors = ["B.consent_and_policy.broad_consent", "B.consent_and_policy.share_samples_europe"]
    source["questionnaire"]["checkbox_questions"] = [
        {"id": question_id, "part": "B", "group": "consent_and_policy",
         "key": question_id.rsplit(".", 1)[1], "label": label, "type": "checkbox", "aliases": []}
        for question_id, label in zip(selectors, ("Broad consent", "European sample sharing"))
    ]
    answer = source["responses"][0]["answers"]["B.test.answer"]
    source["responses"][0]["answers"] = {question_id: answer for question_id in selectors}
    Path(args.mucp_json).write_text(json.dumps(source))
    Path(args.visualization_registry).write_text(json.dumps({"schema_version": "1", "heatmaps": [
        {"id": "mucp-consent-sharing", "questions": ["MuCP:" + value for value in selectors], "minimum_n": 5}
    ], "upsets": []}))
    args.output_tex = str(tmp_path / "combined.tex")
    directory = FakeDirectory()
    directory.biobanks = []

    def empty_directory(parsed_args):
        """Return the empty offline Directory catalogue used to establish zero overlap.

        Args:
            parsed_args: Parsed merge options, unused by this synthetic catalogue.

        Returns:
            Directory fixture with no eligible biobanks or collections.
        """
        return directory

    payload = execute_merge(args, empty_directory)
    published = json.loads(Path(args.output_json).read_text())
    assert payload["biobanks"] == published["biobanks"] == []
    assert Path(args.output_match_review).read_text().strip()
    heatmap = published["descriptive_statistics"]["cross_survey"]["heatmaps"][0]
    assert heatmap["pair"]["paired_denominator"] == 0
    assert heatmap["pair"]["observation_ids"] == []
    assert heatmap["pair"]["cells"] == {}
    assert heatmap["definition"]["row_categories"] == []
    assert heatmap["definition"]["column_categories"] == []
    assert heatmap["omission_reason"] == "Insufficient paired biobanks or category variation"
    tex = Path(args.output_tex).read_text()
    assert "Heatmap mucp-consent-sharing omitted:" in tex
    assert heatmap["omission_reason"] in tex
    assert r"\begin{axis}" not in tex
