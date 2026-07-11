from argparse import Namespace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import logging


MODULE_PATH = Path(__file__).resolve().parents[1] / "data-check.py"


def load_module():
    spec = spec_from_file_location("data_check", MODULE_PATH)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_data_check_main_handles_ctrl_c(monkeypatch, caplog):
    module = load_module()

    class ParserStub:
        def parse_args(self):
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
