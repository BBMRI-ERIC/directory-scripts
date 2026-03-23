# vim:ts=4:sw=4:tw=0:sts=4:et

"""Shared helpers for plain XLSX exports."""

import logging as log

import pandas as pd


def write_xlsx_tables(filename: str, sheets) -> None:
    """Write one or more dataframes to an XLSX workbook.

    Args:
        filename: Output workbook path.
        sheets: Iterable of `(dataframe, sheet_name)`,
            `(dataframe, sheet_name, index)`, or
            `(dataframe, sheet_name, index, options)` tuples.
            Supported options currently include
            `hyperlink_columns=[(display_column, url_column), ...]`.

    Raises:
        ValueError: If any sheet specification has an unsupported shape.
    """
    log.info("Writing XLSX export to %s", filename)
    with pd.ExcelWriter(filename, engine="xlsxwriter") as writer:
        for sheet in sheets:
            if len(sheet) == 2:
                dataframe, sheet_name = sheet
                index = True
                options = {}
            elif len(sheet) == 3:
                dataframe, sheet_name, index = sheet
                options = {}
            elif len(sheet) == 4:
                dataframe, sheet_name, index, options = sheet
            else:
                raise ValueError(
                    "Each XLSX sheet specification must contain 2, 3, or 4 values."
                )
            dataframe.to_excel(writer, sheet_name=sheet_name, index=index)
            hyperlink_columns = options.get("hyperlink_columns", [])
            if hyperlink_columns:
                worksheet = writer.sheets[sheet_name]
                hyperlink_format = writer.book.get_default_url_format()
                column_offset = 1 if index else 0
                for display_column, url_column in hyperlink_columns:
                    if display_column not in dataframe.columns or url_column not in dataframe.columns:
                        continue
                    display_column_index = dataframe.columns.get_loc(display_column) + column_offset
                    for row_index, (display_value, url_value) in enumerate(
                        zip(dataframe[display_column], dataframe[url_column]),
                        start=1,
                    ):
                        if pd.isna(display_value) or pd.isna(url_value):
                            continue
                        if str(url_value).strip() == "":
                            continue
                        escaped_url = str(url_value).replace('"', '""')
                        escaped_display_value = str(display_value).replace('"', '""')
                        worksheet.write_formula(
                            row_index,
                            display_column_index,
                            f'=HYPERLINK("{escaped_url}","{escaped_display_value}")',
                            hyperlink_format,
                            str(display_value),
                        )
