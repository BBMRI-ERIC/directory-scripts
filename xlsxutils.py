# vim:ts=4:sw=4:tw=0:sts=4:et

"""Shared helpers for plain XLSX exports."""

import logging as log

import pandas as pd


EXCEL_MAX_CELL_CHARS = 32767
EXCEL_TRUNCATION_MARKER = "... [truncated to fit Excel cell limit]"
MAX_TRUNCATION_DETAILS = 50


def _excel_cell_text(value):
    """Return the text Excel will effectively receive for long object values."""
    if isinstance(value, str):
        return value
    if pd.api.types.is_scalar(value):
        return None
    return str(value)


def _truncate_excel_cell_value(value):
    """Return a value safe for writing to one Excel cell."""
    cell_text = _excel_cell_text(value)
    if cell_text is None:
        return value
    if len(cell_text) <= EXCEL_MAX_CELL_CHARS:
        return value
    return (
        cell_text[: EXCEL_MAX_CELL_CHARS - len(EXCEL_TRUNCATION_MARKER)]
        + EXCEL_TRUNCATION_MARKER
    )


def _format_entity_fragment(entity_id) -> str:
    """Return an optional log fragment identifying the affected entity."""
    if entity_id in (None, ""):
        return ""
    return f", entity_id={entity_id}"


def _truncate_long_text_cells(dataframe: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    """Truncate cells that exceed Excel's hard text-size limit."""
    if dataframe.empty:
        return dataframe

    truncated_details = []
    truncated_counts = {}
    output = dataframe.copy()
    for column_name in output.columns:
        long_value_mask = output[column_name].map(
            lambda value: (
                (cell_text := _excel_cell_text(value)) is not None
                and len(cell_text) > EXCEL_MAX_CELL_CHARS
            )
        )
        if not long_value_mask.any():
            continue
        truncated_counts[column_name] = int(long_value_mask.sum())
        for row_index, value in output.loc[long_value_mask, column_name].items():
            cell_text = _excel_cell_text(value)
            truncated_value = _truncate_excel_cell_value(value)
            entity_id = None
            if "id" in output.columns:
                entity_id = output.at[row_index, "id"]
            truncated_details.append(
                {
                    "row_index": row_index,
                    "entity_id": entity_id,
                    "column": column_name,
                    "original_length": len(cell_text),
                    "original_value": cell_text,
                    "truncated_value": truncated_value,
                }
            )
        output.loc[long_value_mask, column_name] = output.loc[
            long_value_mask, column_name
        ].map(_truncate_excel_cell_value)

    if truncated_counts:
        details = ", ".join(
            f"{column_name}={count}" for column_name, count in truncated_counts.items()
        )
        log.warning(
            "Truncated XLSX cells exceeding Excel's %d-character limit on sheet %s: %s",
            EXCEL_MAX_CELL_CHARS,
            sheet_name,
            details,
        )
        for detail in truncated_details[:MAX_TRUNCATION_DETAILS]:
            log.info(
                "Truncated XLSX cell detail: sheet=%s, row_index=%s%s, column=%s, "
                "original_length=%d, written_length=%d",
                sheet_name,
                detail["row_index"],
                _format_entity_fragment(detail["entity_id"]),
                detail["column"],
                detail["original_length"],
                EXCEL_MAX_CELL_CHARS,
            )
        for detail in truncated_details:
            log.debug(
                "Truncated XLSX cell exact value: sheet=%s, row_index=%s%s, "
                "column=%s, original_value=%r, truncated_value=%r",
                sheet_name,
                detail["row_index"],
                _format_entity_fragment(detail["entity_id"]),
                detail["column"],
                detail["original_value"],
                detail["truncated_value"],
            )
        if len(truncated_details) > MAX_TRUNCATION_DETAILS:
            log.info(
                "Truncated XLSX cell detail list for sheet %s omitted %d additional cells.",
                sheet_name,
                len(truncated_details) - MAX_TRUNCATION_DETAILS,
            )
    return output


def write_xlsx_tables(filename: str, sheets) -> None:
    """Write one or more dataframes to an XLSX workbook.

    Args:
        filename: Output workbook path.
        sheets: Iterable of `(dataframe, sheet_name)`,
            `(dataframe, sheet_name, index)`, or
            `(dataframe, sheet_name, index, options)` tuples.
            Supported options currently include
            `hyperlink_columns=[(display_column, url_column), ...]` and
            `hide_columns=[column_name, ...]`.
            Cell values exceeding Excel's 32,767-character text limit are
            truncated in the workbook output only.

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
            excel_dataframe = _truncate_long_text_cells(dataframe, sheet_name)
            excel_dataframe.to_excel(writer, sheet_name=sheet_name, index=index)
            hyperlink_columns = options.get("hyperlink_columns", [])
            if hyperlink_columns:
                worksheet = writer.sheets[sheet_name]
                hyperlink_format = writer.book.get_default_url_format()
                column_offset = 1 if index else 0
                for display_column, url_column in hyperlink_columns:
                    if (
                        display_column not in excel_dataframe.columns
                        or url_column not in excel_dataframe.columns
                    ):
                        continue
                    display_column_index = (
                        excel_dataframe.columns.get_loc(display_column) + column_offset
                    )
                    for row_index, (display_value, url_value) in enumerate(
                        zip(
                            excel_dataframe[display_column],
                            excel_dataframe[url_column],
                        ),
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
            hidden_columns = options.get("hide_columns", [])
            if hidden_columns:
                worksheet = writer.sheets[sheet_name]
                column_offset = 1 if index else 0
                for column_name in hidden_columns:
                    if column_name not in excel_dataframe.columns:
                        continue
                    column_index = (
                        excel_dataframe.columns.get_loc(column_name) + column_offset
                    )
                    worksheet.set_column(
                        column_index, column_index, None, None, {"hidden": True}
                    )
