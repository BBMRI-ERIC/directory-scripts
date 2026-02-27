from openpyxl import load_workbook
import pandas as pd
import pytest

from xlsxutils import write_xlsx_tables


def test_write_xlsx_tables_supports_multiple_sheets(tmp_path):
    output_file = tmp_path / "export.xlsx"

    write_xlsx_tables(
        str(output_file),
        [
            (pd.DataFrame([{"id": "bb1"}]), "Biobanks", False),
            (pd.DataFrame([{"id": "col1"}]), "Collections", False),
        ],
    )

    workbook = load_workbook(output_file)
    assert workbook.sheetnames == ["Biobanks", "Collections"]
    assert workbook["Biobanks"]["A2"].value == "bb1"
    assert workbook["Collections"]["A2"].value == "col1"


def test_write_xlsx_tables_rejects_invalid_sheet_specs(tmp_path):
    output_file = tmp_path / "broken.xlsx"

    with pytest.raises(ValueError):
        write_xlsx_tables(str(output_file), [(pd.DataFrame(),)])
