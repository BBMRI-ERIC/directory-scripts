import logging

from cli_common import (
    add_directory_auth_arguments,
    add_directory_schema_argument,
    add_logging_arguments,
    add_no_stdout_argument,
    add_optional_xlsx_output_argument,
    add_plugin_disable_argument,
    add_purge_cache_arguments,
    add_remote_check_disable_arguments,
    add_xlsx_output_argument,
    build_parser,
    configure_logging,
)


def test_standard_exporter_arguments_support_normalized_and_legacy_aliases():
    parser = build_parser()
    add_logging_arguments(parser)
    add_xlsx_output_argument(parser)
    add_no_stdout_argument(parser)
    add_purge_cache_arguments(parser, ["directory"])

    args = parser.parse_args(
        [
            "--verbose",
            "--output-XLSX",
            "report.xlsx",
            "--output-no-stdout",
            "--purge-cache",
            "directory",
        ]
    )

    assert args.verbose is True
    assert args.outputXLSX == ["report.xlsx"]
    assert args.nostdout is True
    assert args.purgeCaches == ["directory"]


def test_schema_argument_accepts_schema_and_legacy_package_names():
    parser = build_parser()
    add_directory_schema_argument(parser, default="ERIC")

    assert parser.parse_args([]).schema == "ERIC"
    assert parser.parse_args(["--schema", "BBMRI-EU"]).schema == "BBMRI-EU"
    assert parser.parse_args(["--package", "BBMRI-NL"]).schema == "BBMRI-NL"


def test_qc_arguments_can_be_enabled_selectively():
    parser = build_parser()
    add_remote_check_disable_arguments(parser, ["emails", "geocoding"])
    add_plugin_disable_argument(parser, ["PluginA", "PluginB"])
    add_directory_auth_arguments(parser)
    add_optional_xlsx_output_argument(
        parser,
        dest="outputWEXLSX",
        long_option="--warnings-xlsx",
        short_option="-W",
        legacy_long_options=["--output-WE-XLSX"],
        help_text="write warnings/errors to the provided XLSX file",
    )

    args = parser.parse_args(
        [
            "--disable-checks-remote",
            "emails",
            "--disable-plugins",
            "PluginB",
            "-u",
            "alice",
            "-p",
            "secret",
            "--output-WE-XLSX",
            "warnings.xlsx",
        ]
    )

    assert args.disableChecksRemote == ["emails"]
    assert args.disablePlugins == ["PluginB"]
    assert args.username == "alice"
    assert args.password == "secret"
    assert args.outputWEXLSX == ["warnings.xlsx"]


def test_qc_arguments_support_short_option_for_disabling_all_remote_checks():
    parser = build_parser()
    add_remote_check_disable_arguments(parser, ["emails", "geocoding"])

    args = parser.parse_args(["-r"])

    assert args.disableChecksRemote == ["emails", "geocoding"]


def test_configure_logging_sets_debug_level():
    parser = build_parser()
    add_logging_arguments(parser)
    args = parser.parse_args(["--debug"])

    root_logger = logging.getLogger()
    previous_level = root_logger.level
    previous_handlers = list(root_logger.handlers)
    try:
        for handler in previous_handlers:
            root_logger.removeHandler(handler)
        configure_logging(args)
        assert logging.getLogger().level == logging.DEBUG
    finally:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)
        for handler in previous_handlers:
            root_logger.addHandler(handler)
        root_logger.setLevel(previous_level)
