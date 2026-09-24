"""Test data check interrupt behavior."""

from argparse import Namespace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import logging


MODULE_PATH = Path(__file__).resolve().parents[1] / "data-check.py"


def load_module():
    """Import the data-check CLI without invoking its main entry point.

    Returns:
        Newly executed data-check.py module exposing main for interruption injection.
    """
    spec = spec_from_file_location("data_check", MODULE_PATH)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_data_check_main_handles_ctrl_c(monkeypatch, caplog):
    """Verify data check main handles ctrl c.

    Args:
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.
        caplog: Pytest log-capture fixture used to inspect emitted log records.

    Returns:
        None. Verifies data check main handles ctrl c.
    """
    module = load_module()

    class ParserStub:
        """Supply anonymous ERIC CLI defaults for testing clean KeyboardInterrupt handling.
        """
        def parse_args(self):
            """Return preconfigured command-line arguments from the parser double.

            Returns:
                The fixed argparse namespace representing the command-line options for this invocation.
            """
            return Namespace(
                schema="ERIC",
                token=None,
                username=None,
                password=None,
                suppress_validation_warnings=False,
                orphacodesfile=None,
                debug=False,
                nostdout=True,
                outputXLSX=None,
                update_plan=None,
                warning_suppressions="warning-suppressions.json",
                include_withdrawn=False,
                only_withdrawn=False,
            )

    monkeypatch.setattr(module, "parser", ParserStub())
    monkeypatch.setattr(module, "configure_logging", lambda args: None)
    monkeypatch.setattr(
        module,
        "Directory",
        lambda **kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    with caplog.at_level(logging.WARNING):
        result = module.main()

    assert result == module.EXIT_ABORTED
    assert "data-check.py interrupted by Ctrl+C during directory retrieval/check execution." in caplog.text
