# vim:ts=4:sw=4:tw=0:sts=4:et

"""Shared helpers for plain XLSX exports."""

import logging as log

import pandas as pd


def write_xlsx_tables(filename: str, sheets) -> None:
    """Write one or more dataframes to an XLSX workbook.

    Args:
        filename: Output workbook path.
        sheets: Iterable of `(dataframe, sheet_name)` or
            `(dataframe, sheet_name, index)` tuples.

    Raises:
        ValueError: If any sheet specification has an unsupported shape.
    """
    log.info("Writing XLSX export to %s", filename)
    with pd.ExcelWriter(filename, engine="xlsxwriter") as writer:
        for sheet in sheets:
            if len(sheet) == 2:
                dataframe, sheet_name = sheet
                index = True
            elif len(sheet) == 3:
                dataframe, sheet_name, index = sheet
            else:
                raise ValueError(
                    "Each XLSX sheet specification must contain 2 or 3 values."
                )
            dataframe.to_excel(writer, sheet_name=sheet_name, index=index)
