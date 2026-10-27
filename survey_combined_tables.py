"""Render compact combined-report tables grouped by canonical Directory biobank."""

from collections import defaultdict
from typing import Any, Mapping, Sequence


def render_biobank_table(
    rows: Sequence[Mapping[str, Any]], columns: str, headers: Sequence[str],
    repeated_entries: str = "empty", biobank_column_index: int = 0,
    *, country_headings: bool = False,
) -> str:
    """Render stable per-biobank longtable blocks with fixed continuation context.

    Args:
        rows: Ordered table rows. Each mapping contains canonical ``biobank_id``,
            ``country``, TeX-escaped ``biobank_label`` and TeX-escaped non-bank
            ``cells`` in the order declared by ``headers`` without the bank column.
            ``biobank_sort_label`` optionally supplies the unescaped human name;
            callers using TeX markup must supply it to avoid markup-based sorting.
        columns: Complete longtable column specification, including the bank column.
        headers: TeX-ready column headings in rendered column order.
        repeated_entries: ``empty`` blanks repeated bank cells; ``dtto`` marks them
            with an italic ditto label. The first row in every bank block always names
            the bank.
        biobank_column_index: Zero-based location of the rendered bank column.
        country_headings: Whether to group the logical table under full-width gray country banners.

    Returns:
        TeX ordered by country, bank label and canonical ID. Country tables use
        page marks evaluated by the output routine, not mutable preboxed headers,
        to identify the bank at the end of the preceding page. Other tables use
        independent blocks with fixed literal continuation headers.

    Raises:
        TypeError: If rows or their cell/header collections have invalid types.
        ValueError: If the repeat mode, row shape, identity metadata or column layout
            is inconsistent.
    """
    if repeated_entries not in {"empty", "dtto"}:
        raise ValueError("repeated_entries must be 'empty' or 'dtto'")
    if not isinstance(columns, str) or not columns.strip():
        raise ValueError("columns must be a nonempty TeX column specification")
    if not isinstance(headers, Sequence) or isinstance(headers, (str, bytes)) or not headers:
        raise TypeError("headers must be a nonempty sequence")
    if any(not isinstance(header, str) for header in headers):
        raise TypeError("Every table header must be TeX text")
    if type(biobank_column_index) is not int or not 0 <= biobank_column_index < len(headers):
        raise ValueError("biobank_column_index must identify a declared column")
    import re

    declared_columns = len(re.findall(r"(?:p|m|b)\s*\{[^{}]*\}|[clr]", columns))
    if declared_columns != len(headers):
        raise ValueError("columns must declare at least one column per header")

    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    identities: dict[str, tuple[str, str, str]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise TypeError("Every biobank table row must be a mapping")
        for key in ("biobank_id", "country", "biobank_label", "cells"):
            if key not in row:
                raise ValueError(f"Biobank table row is missing {key}")
        bank_id, country, label = row["biobank_id"], row["country"], row["biobank_label"]
        cells = row["cells"]
        if not all(isinstance(value, str) for value in (bank_id, country, label)) or not bank_id:
            raise ValueError("Biobank table identity, country and label must be text")
        if not isinstance(cells, Sequence) or isinstance(cells, (str, bytes)):
            raise TypeError("Biobank table cells must be a sequence")
        if len(cells) != len(headers) - 1 or any(not isinstance(value, str) for value in cells):
            raise ValueError("Biobank table cells must match the non-biobank columns")
        sort_label = row.get("biobank_sort_label", label)
        if not isinstance(sort_label, str):
            raise ValueError("Biobank sorting name must be plain text")
        identity = (country, label, sort_label)
        if bank_id in identities and identities[bank_id] != identity:
            raise ValueError(f"Biobank table identity metadata conflicts for {bank_id}")
        identities[bank_id] = identity
        grouped[bank_id].append(row)

    def emit_row(row: Mapping[str, Any], first: bool) -> str:
        """Insert a bank cell among caller-escaped non-bank cells.

        Args:
            row: Caller-escaped row assigned to one canonical biobank.
            first: Whether this is the first row in its bank block.

        Returns:
            One TeX longtable data row with the configured repeated-cell value.
        """
        bank_cell = row["biobank_label"] if first else (
            r"\emph{dtto}" if repeated_entries == "dtto" else ""
        )
        cells = list(row["cells"])
        cells.insert(biobank_column_index, bank_cell)
        return " & ".join(cells) + r" \\"

    if country_headings:
        from survey_identity import COUNTRIES
        from so2_descriptive_report import _tex
        country_names = {}
        for name, code in COUNTRIES.items():
            country_names.setdefault(code, name.title())
        ordered = sorted(grouped, key=lambda value: (
            identities[value][0] not in country_names,
            country_names.get(identities[value][0], identities[value][0]).casefold(),
            identities[value][2].casefold(), value))
        # Marks follow shipped rows; ordinary header macros are frozen when
        # longtable builds its head box, before pagination is known.
        block = [r"\begingroup\makeatletter",
                 r"\newmarks\mucpTableMarks",
                 r"\let\mucpOriginalLToutput\LT@output",
                 r"\def\LT@output{\ifnum\outputpenalty>-10000\relax",
                 r"\mucpOriginalLToutput\nointerlineskip",
                 r"\vbox{\let\par\@@par\hsize=\linewidth\raggedright\small\emph{Previous page ended in \botmarks\mucpTableMarks}\par}\nobreak",
                 r"\else\mucpOriginalLToutput\fi}",
                 r"\makeatother",
                 rf"\begin{{longtable}}{{{columns}}}", r"\toprule",
                 " & ".join(headers) + r" \\ \midrule", r"\endfirsthead",
                 r"\toprule", " & ".join(headers) + r" \\ \midrule", r"\endhead",
                 r"\bottomrule", r"\endfoot", r"\bottomrule", r"\endlastfoot"]
        last_country = None
        for bank_id in ordered:
            country = identities[bank_id][0]
            if country != last_country:
                name = country_names.get(country, country or "Country not reported")
                block.extend([r"\rowcolor{gray!15}",
                              rf"\multicolumn{{{len(headers)}}}{{c}}{{\textbf{{{_tex(name)}}}}} \\*"])
                last_country = country
            else:
                block.append(r"\midrule")
            context = _tex(country_names.get(country, country or "Country not reported")) + ": " + identities[bank_id][1]
            for index, row in enumerate(grouped[bank_id]):
                block.extend([rf"\noalign{{\marks\mucpTableMarks{{{context}}}}}", emit_row(row, index == 0)])
        block.extend([r"\end{longtable}", r"\endgroup"])
        return "\n".join(block)

    blocks = []
    for bank_id in sorted(grouped, key=lambda value: (
        identities[value][0].casefold(), identities[value][2].casefold(), value,
    )):
        bank_rows = grouped[bank_id]
        label = bank_rows[0]["biobank_label"]
        block = [rf"\begin{{longtable}}{{{columns}}}"]
        if not blocks:
            block.append(r"\toprule")
            block.extend([" & ".join(headers) + r" \\ \midrule", r"\endfirsthead"])
        else:
            block.append(r"\endfirsthead")
        block.extend([
            r"\toprule",
            rf"\multicolumn{{{len(headers)}}}{{p{{\dimexpr\linewidth-2\tabcolsep\relax}}}}{{\raggedright\emph{{Continued: {label}}}}} \\",
            " & ".join(headers) + r" \\ \midrule",
            r"\endhead",
            r"\bottomrule", r"\endfoot", r"\endlastfoot",
        ])
        block.extend(emit_row(row, index == 0) for index, row in enumerate(bank_rows))
        block.extend([r"\midrule", r"\end{longtable}"])
        blocks.append("\n".join(block))
    return "\n\\vspace{-0.35em}\n".join(blocks)
