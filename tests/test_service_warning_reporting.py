"""Keep service findings first-class and prevent accidental write support."""

from openpyxl import load_workbook
from pathlib import Path
import runpy

from customwarnings import DataCheckEntityType, DataCheckWarning, DataCheckWarningLevel
from validation_models import WarningSuppressionEntryModel
from warningscontainer import WarningsContainer


def test_service_warning_is_routed_printed_and_exported(tmp_path, capsys):
    """Expose service identity and Boolean withdrawal without version repetition.

    Args:
        tmp_path: Temporary destination for the isolated QC workbook.
        capsys: Pytest capture of human-readable warning output.

    Returns:
        None.
    """
    container = WarningsContainer()
    warning = DataCheckWarning("VOC:DeprecatedValue", "", "EXT", DataCheckWarningLevel.ERROR,
                               "service1", DataCheckEntityType.SERVICE, True,
                               "serviceTypes contains an explicitly deprecated term")
    container.newWarning(warning)
    container.dumpWarnings()
    assert "Service service1 VOC:DeprecatedValue/ERROR" in capsys.readouterr().out
    path = tmp_path / "qc.xlsx"
    container.dumpWarningsXLSX([str(path)], {}, {}, True)
    workbook = load_workbook(path)
    assert workbook["EXT"]["B2"].value == "Service"
    assert workbook["EXT"]["C2"].value is True
    assert workbook["ALL"]["D2"].value == "VOC:DeprecatedValue"
    workbook.close()


def test_service_suppression_is_valid_and_hides_warning():
    """Accept SERVICE in suppression metadata without promoting it to write support.

    Returns:
        None.
    """
    entry = WarningSuppressionEntryModel.parse_obj({
        "check_id": "VOC:DeprecatedValue", "entity_id": "service1", "entity_type": "SERVICE"
    })
    assert entry.entity_type == "SERVICE"
    container = WarningsContainer({entry.check_id: {entry.entity_id: "reviewed"}})
    container.newWarning(DataCheckWarning(entry.check_id, "", "CZ", DataCheckWarningLevel.ERROR,
                                         entry.entity_id, DataCheckEntityType.SERVICE, False, "deprecated"))
    assert container.getWarnings() == []


def test_service_fix_proposals_remain_unsupported():
    """Reject SERVICE in write-plan validation, independent of warning support.

    Returns:
        None.
    """
    module = runpy.run_path(str(Path(__file__).resolve().parents[1] / "qcheck-updater.py"))
    assert "SERVICE" not in module["SUPPORTED_ENTITY_TYPES"]
