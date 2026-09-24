"""Synthetic tests for the bounded EOSC membership XLSX adapter."""

from __future__ import annotations

from importlib import import_module
import hashlib
import logging
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

xlsx_adapter = import_module("eosc-organisation-matcher")
CONTRIBUTOR_TAG = xlsx_adapter.CONTRIBUTOR_TAG
read_membership = xlsx_adapter.read_membership
write_matches_xlsx = xlsx_adapter.write_matches_xlsx


def _make_source(path: Path, *, source_name: str = "Membership") -> Path:
    """Write a membership workbook with a preamble, two institutions, and an unrelated sheet.

    Args:
        path: Destination XLSX filename, overwritten if present; its parent must exist.
        source_name: Displayed membership-source name written into the workbook fixture.

    Returns:
        The destination Path after saving the workbook, for passing to read_membership.
    """
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = source_name
    sheet.append(["Preamble", None, None, None, None, None, None, None])
    sheet.append(
        [
            " Organisation - ID ",
            "Organisation - Name",
            "Organisation - Acronym",
            "Organisation - Country",
            "Membership Type",
            "Membership Status",
            "Node Coordinator",
            "Node Contributor",
        ]
    )
    sheet.append(["0012", "Leading = Literal", "L12", "Belgium", "Member", "Active", None, None])
    sheet.append([13, "Second", "S", "Czechia", "Observer", "Active", "Coordinator", "occupied"])
    workbook.create_sheet("Other")
    workbook.save(path)
    return path


def _set_formula_caches(path: Path, values: dict[str, tuple[str, str]]) -> None:
    """Inject cached formula values into a synthetic XLSX fixture.

    Args:
        path: Existing XLSX archive replaced in place after patching sheet1.xml cache values.
        values: Cell-coordinate-to-(cached text, XLSX type code) mapping; only existing cells are patched.

    Returns:
        None. Inject cached formula values into a synthetic XLSX fixture.
    """
    worksheet_path = "xl/worksheets/sheet1.xml"
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    ET.register_namespace("", namespace)
    with zipfile.ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    root = ET.fromstring(entries[worksheet_path])
    for cell in root.iter(f"{{{namespace}}}c"):
        reference = cell.attrib.get("r")
        if reference not in values:
            continue
        cached_value, cell_type = values[reference]
        value_element = cell.find(f"{{{namespace}}}v")
        if value_element is None:
            value_element = ET.SubElement(cell, f"{{{namespace}}}v")
        value_element.text = cached_value
        cell.set("t", cell_type)
    entries[worksheet_path] = ET.tostring(
        root, encoding="utf-8", xml_declaration=True
    )
    replacement = path.with_name(path.stem + ".cached.xlsx")
    with zipfile.ZipFile(replacement, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    replacement.replace(path)


def test_read_membership_preserves_text_ids_and_selects_sheet(tmp_path):
    """Verify read membership preserves text ids and selects sheet.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies read membership preserves text ids and selects sheet.
    """
    source = _make_source(tmp_path / "membership.xlsx")

    result = read_membership(source, sheet_index=1)

    assert result["sheet_name"] == "Membership"
    assert result["header_row"] == 2
    assert result["organisations"] == [
        {
            "organisation_id": "0012",
            "name": "Leading = Literal",
            "acronym": "L12",
            "country": "Belgium",
            "membership_type": "Member",
            "membership_status": "Active",
            "source_row": 3,
        },
        {
            "organisation_id": "13",
            "name": "Second",
            "acronym": "S",
            "country": "Czechia",
            "membership_type": "Observer",
            "membership_status": "Active",
            "source_row": 4,
        },
    ]
    assert result["rows"][0][0] == "Preamble"
    assert result["rows"][2][0] == "0012"
    assert result["contributor_columns"] == [8]
    assert len(result["workbook_sha256"]) == 64
    assert Path(result["source_path"]).resolve() == source.resolve()


def test_sheet_selection_is_mutually_exclusive_and_one_based(tmp_path):
    """Verify sheet selection is mutually exclusive and one based.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies sheet selection is mutually exclusive and one based.
    """
    source = _make_source(tmp_path / "membership.xlsx")

    with pytest.raises(ValueError, match="mutually exclusive"):
        read_membership(source, sheet="Membership", sheet_index=1)
    with pytest.raises(ValueError, match="positive one-based"):
        read_membership(source, sheet_index=0)
    with pytest.raises(ValueError, match="outside"):
        read_membership(source, sheet_index=3)
    with pytest.raises(ValueError, match="not found"):
        read_membership(source, sheet="missing")


def test_read_membership_skips_external_and_blank_ids_but_keeps_rows(tmp_path):
    """Verify read membership skips external and blank ids but keeps rows.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies read membership skips external and blank ids but keeps rows.
    """
    source = _make_source(tmp_path / "membership.xlsx")
    workbook = load_workbook(source)
    sheet = workbook["Membership"]
    sheet.append(["external", "External", None, "Belgium", None, None, None, "node"])
    sheet.append([" ", "A note on a non-membership row", None, None, None, None, None, "node"])
    workbook.save(source)

    result = read_membership(source)

    assert len(result["organisations"]) == 2
    assert len(result["rows"]) == 6
    assert result["rows"][5][1] == "A note on a non-membership row"


def test_read_membership_rejects_missing_required_values_and_duplicate_ids(tmp_path):
    """Verify read membership rejects missing required values and duplicate ids.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies read membership rejects missing required values and duplicate ids.
    """
    source = _make_source(tmp_path / "membership.xlsx")
    workbook = load_workbook(source)
    sheet = workbook["Membership"]
    sheet["E3"] = None
    workbook.save(source)
    with pytest.raises(ValueError, match="membership_type"):
        read_membership(source)

    source = _make_source(tmp_path / "duplicate.xlsx")
    workbook = load_workbook(source)
    workbook["Membership"]["A4"] = "0012"
    workbook.save(source)
    with pytest.raises(ValueError, match="Ambiguous duplicate"):
        read_membership(source)


def test_blank_country_is_unknown_and_missing_record_fields_still_fail(tmp_path, caplog):
    """Verify blank country is unknown and missing record fields still fail.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        caplog: Pytest log-capture fixture used to inspect emitted log records.

    Returns:
        None. Verifies blank country is unknown and missing record fields still fail.
    """
    source = _make_source(tmp_path / "missing-country.xlsx")
    workbook = load_workbook(source)
    workbook["Membership"]["D3"] = "  "
    workbook.save(source)

    with caplog.at_level(logging.WARNING):
        result = read_membership(source)
    assert result["organisations"][0]["country"] == ""
    assert "D3" in caplog.text
    assert "unknown country" in caplog.text

    for cell, field in (("B3", "name"), ("E3", "membership_type"), ("F3", "membership_status")):
        source = _make_source(tmp_path / f"missing-{field}.xlsx")
        workbook = load_workbook(source)
        workbook["Membership"][cell] = None
        workbook.save(source)
        with pytest.raises(ValueError, match=field):
            read_membership(source)

    source = _make_source(tmp_path / "missing-id-with-data.xlsx")
    workbook = load_workbook(source)
    workbook["Membership"]["A3"] = " "
    workbook["Membership"]["B3"] = "Retained note"
    workbook.save(source)
    result = read_membership(source)
    assert result["rows"][2][1] == "Retained note"
    assert len(result["organisations"]) == 1


def test_formula_identity_fails_and_formula_contributor_warns(tmp_path, caplog):
    """Verify formula identity fails and formula contributor warns.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        caplog: Pytest log-capture fixture used to inspect emitted log records.

    Returns:
        None. Verifies formula identity fails and formula contributor warns.
    """
    source = _make_source(tmp_path / "formula.xlsx")
    workbook = load_workbook(source)
    sheet = workbook["Membership"]
    sheet["B3"] = "=CONCAT(\"Leading\",\" identity\")"
    sheet["H4"] = "=1+1"
    workbook.save(source)

    with pytest.raises(ValueError, match="Missing cached required identity"):
        read_membership(source)

    source = _make_source(tmp_path / "formula-contributor.xlsx")
    workbook = load_workbook(source)
    workbook["Membership"]["H4"] = "=1+1"
    workbook.save(source)
    with caplog.at_level(logging.WARNING):
        result = read_membership(source)
    assert [4, 8] in result["formula_cells"]
    assert "formula cell" in caplog.text


def test_cached_formula_identity_values_are_read_and_formula_slots_remain_occupied(
    tmp_path, caplog
):
    """Verify cached formula identity values are read and formula slots remain occupied.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        caplog: Pytest log-capture fixture used to inspect emitted log records.

    Returns:
        None. Verifies cached formula identity values are read and formula slots remain occupied.
    """
    source = _make_source(tmp_path / "cached-formula.xlsx")
    workbook = load_workbook(source)
    sheet = workbook["Membership"]
    sheet["A3"] = "=1+11"
    sheet["B3"] = '="Cached Name"'
    sheet["D3"] = '="Belgium"'
    sheet["E3"] = '="Member"'
    sheet["F3"] = '="Active"'
    sheet["H3"] = '="Existing formula contributor"'
    workbook.save(source)
    _set_formula_caches(
        source,
        {
            "A3": ("0012", "str"),
            "B3": ("Cached Name", "str"),
            "D3": ("Belgium", "str"),
            "E3": ("Member", "str"),
            "F3": ("Active", "str"),
            "H3": ("Existing formula contributor", "str"),
        },
    )

    with caplog.at_level(logging.WARNING):
        result = read_membership(source)
    assert result["organisations"][0]["organisation_id"] == "0012"
    assert result["organisations"][0]["name"] == "Cached Name"
    assert result["organisations"][0]["country"] == "Belgium"
    assert result["organisations"][0]["membership_type"] == "Member"
    assert result["organisations"][0]["membership_status"] == "Active"
    assert [3, 1] in result["formula_cells"]
    assert [3, 2] in result["formula_cells"]
    assert "formula cell" in caplog.text

    output = tmp_path / "cached-output.xlsx"
    write_matches_xlsx(
        result,
        [
            {
                "organisation_id": "0012",
                "eosc_name": "EOSC One",
                "directory_juridical_person": "Directory One",
                "biobank_ids": [],
            }
        ],
        output,
    )
    written = load_workbook(output, data_only=False)["Membership"]
    assert written["A3"].value == "0012"
    assert written["B3"].value == "Cached Name"
    assert written["H3"].value == "Existing formula contributor"
    assert written["I3"].value == CONTRIBUTOR_TAG


def test_cached_excel_error_identity_does_not_enter_matchable_data(tmp_path):
    """Verify cached excel error identity does not enter matchable data.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies cached excel error identity does not enter matchable data.
    """
    source = _make_source(tmp_path / "cached-error.xlsx")
    workbook = load_workbook(source)
    workbook["Membership"]["A3"] = "=1+11"
    workbook.save(source)
    _set_formula_caches(source, {"A3": ("#REF!", "e")})

    with pytest.raises(ValueError, match="Excel error identity"):
        read_membership(source)


def test_writer_appends_one_shared_contributor_column_and_preserves_source(tmp_path):
    """Verify writer appends one shared contributor column and preserves source.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies writer appends one shared contributor column and preserves source.
    """
    source = _make_source(tmp_path / "membership.xlsx")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    parsed = read_membership(source)
    output = tmp_path / "output.xlsx"

    write_matches_xlsx(
        parsed,
        [
            {
                "organisation_id": "0012",
                "eosc_name": "EOSC One",
                "directory_juridical_person": "Directory One",
                "biobank_ids": ["bb1", "bb2"],
            }
        ],
        output,
    )

    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    workbook = load_workbook(output, data_only=False)
    assert workbook.sheetnames == ["Matched institutions", "Membership"]
    assert [cell.value for cell in workbook["Matched institutions"][1]] == [
        "Organisation ID",
        "EOSC-A Name",
        "BBMRI-ERIC Name",
        "List of biobankIDs",
    ]
    assert [cell.value for cell in workbook["Matched institutions"][2]] == [
        "0012",
        "EOSC One",
        "Directory One",
        "bb1,bb2",
    ]
    source_sheet = workbook["Membership"]
    assert source_sheet.max_column == 8
    assert source_sheet["H3"].value == CONTRIBUTOR_TAG
    assert source_sheet["H4"].value == "occupied"
    assert source_sheet["A3"].value == "0012"
    assert source_sheet["B3"].value == "Leading = Literal"


def test_writer_reuses_exact_tag_and_appends_after_notes_without_overwriting(tmp_path):
    """Verify writer reuses exact tag and appends after notes without overwriting.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies writer reuses exact tag and appends after notes without overwriting.
    """
    source = _make_source(tmp_path / "membership.xlsx")
    workbook = load_workbook(source)
    sheet = workbook["Membership"]
    sheet.insert_cols(8, 1)
    sheet["H2"] = "Node Contributor"
    sheet["H3"] = CONTRIBUTOR_TAG
    sheet["H4"] = "full"
    sheet["I2"] = "Notes"
    sheet["I3"] = "keep this note"
    workbook.save(source)
    parsed = read_membership(source)
    output = tmp_path / "output.xlsx"

    write_matches_xlsx(
        parsed,
        [
            {
                "organisation_id": "0012",
                "eosc_name": "EOSC One",
                "directory_juridical_person": "Directory One",
                "biobank_ids": [],
            },
            {
                "organisation_id": "13",
                "eosc_name": "EOSC Two",
                "directory_juridical_person": "Directory Two",
                "biobank_ids": [],
            },
        ],
        output,
    )

    result = load_workbook(output, data_only=False)["Membership"]
    assert result.max_column == 10
    assert result["H3"].value == CONTRIBUTOR_TAG
    assert result["I3"].value == "keep this note"
    assert result["J2"].value == "Node Contributor"
    assert result["J4"].value == CONTRIBUTOR_TAG


def test_writer_treats_formula_slots_as_occupied_and_warns(tmp_path, caplog):
    """Verify writer treats formula slots as occupied and warns.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        caplog: Pytest log-capture fixture used to inspect emitted log records.

    Returns:
        None. Verifies writer treats formula slots as occupied and warns.
    """
    source = _make_source(tmp_path / "membership.xlsx")
    workbook = load_workbook(source)
    workbook["Membership"]["H3"] = "=1+1"
    workbook.save(source)
    parsed = read_membership(source)
    output = tmp_path / "output.xlsx"

    with caplog.at_level(logging.WARNING):
        write_matches_xlsx(
            parsed,
            [
                {
                    "organisation_id": "0012",
                    "eosc_name": "EOSC One",
                    "directory_juridical_person": "Directory One",
                    "biobank_ids": [],
                }
            ],
            output,
        )

    result = load_workbook(output, data_only=False)["Membership"]
    assert result.max_column == 9
    assert result["H3"].value is None
    assert result["I3"].value == CONTRIBUTOR_TAG
    assert "Formula cells" in caplog.text


def test_writer_rejects_existing_or_source_alias_and_empty_matches_are_valid(tmp_path):
    """Verify writer rejects existing or source alias and empty matches are valid.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies writer rejects existing or source alias and empty matches are valid.
    """
    source = _make_source(tmp_path / "membership.xlsx")
    parsed = read_membership(source)
    with pytest.raises(ValueError, match="alias"):
        write_matches_xlsx(parsed, [], source)
    existing = tmp_path / "existing.xlsx"
    existing.write_bytes(b"not an xlsx")
    with pytest.raises(FileExistsError):
        write_matches_xlsx(parsed, [], existing)
    dangling = tmp_path / "dangling.xlsx"
    try:
        dangling.symlink_to(tmp_path / "missing-target.xlsx")
    except OSError:
        pytest.skip("symlinks are unavailable in this environment")
    with pytest.raises(FileExistsError, match="symlink"):
        write_matches_xlsx(parsed, [], dangling)

    output = tmp_path / "empty.xlsx"
    write_matches_xlsx(parsed, [], output)
    workbook = load_workbook(output)
    assert workbook.sheetnames == ["Matched institutions", "Membership"]
    assert workbook["Matched institutions"].max_row == 1
    assert workbook["Membership"].max_column == 8


def test_writer_renames_conflicting_source_sheet_and_rejects_missing_match_keys(tmp_path):
    """Verify writer renames conflicting source sheet and rejects missing match keys.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies writer renames conflicting source sheet and rejects missing match keys.
    """
    source = _make_source(tmp_path / "membership.xlsx", source_name="Matched institutions")
    parsed = read_membership(source)
    with pytest.raises(ValueError, match="missing required key"):
        write_matches_xlsx(parsed, [{"organisation_id": "0012"}], tmp_path / "bad.xlsx")

    output = tmp_path / "output.xlsx"
    write_matches_xlsx(parsed, [], output)
    assert load_workbook(output).sheetnames == ["Matched institutions", "Source"]


def test_writer_keeps_literal_equals_strings_and_reopens_atomically(tmp_path):
    """Verify writer keeps literal equals strings and reopens atomically.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies writer keeps literal equals strings and reopens atomically.
    """
    source = _make_source(tmp_path / "membership.xlsx")
    parsed = read_membership(source)
    output = tmp_path / "output.xlsx"
    write_matches_xlsx(
        parsed,
        [
            {
                "organisation_id": "0012",
                "eosc_name": "=not a formula",
                "directory_juridical_person": "Directory",
                "biobank_ids": "bb1",
            }
        ],
        output,
    )
    workbook = load_workbook(output, data_only=False)
    cell = workbook["Matched institutions"]["B2"]
    assert cell.value == "=not a formula"
    assert cell.data_type == "s"
    assert not list(tmp_path.glob(".*.tmp.xlsx"))


def test_writer_validates_semantically_blank_country_roundtrip(tmp_path):
    """Verify writer validates semantically blank country roundtrip.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies writer validates semantically blank country roundtrip.
    """
    source = _make_source(tmp_path / "blank-country.xlsx")
    workbook = load_workbook(source)
    workbook["Membership"]["D3"] = ""
    workbook.save(source)
    parsed = read_membership(source)

    output = tmp_path / "blank-country-output.xlsx"
    write_matches_xlsx(parsed, [], output)
    assert load_workbook(output, data_only=False)["Membership"]["D3"].value is None


def test_publication_fails_without_atomic_no_overwrite_primitive(tmp_path, monkeypatch):
    """Verify publication fails without atomic no overwrite primitive.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.
        monkeypatch: Pytest monkeypatch fixture; temporary dependency and environment overrides are undone after the test.

    Returns:
        None. Verifies publication fails without atomic no overwrite primitive.
    """
    temporary = tmp_path / "temporary.xlsx"
    destination = tmp_path / "destination.xlsx"
    temporary.write_bytes(b"validated")
    monkeypatch.delattr(xlsx_adapter.os, "link", raising=False)

    class NoRenameAt2:
        """Provide no rename at2 used to isolate the tested behavior.
        """
        pass

    monkeypatch.setattr(
        xlsx_adapter.ctypes, "CDLL", lambda *args, **kwargs: NoRenameAt2()
    )
    with pytest.raises(OSError, match="without a supported"):
        xlsx_adapter._publish_without_overwrite(temporary, destination)
    assert temporary.exists()
    assert not destination.exists()


def test_read_membership_property_for_text_ids_if_hypothesis_is_available(tmp_path):
    """Verify read membership property for text ids if hypothesis is available.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies read membership property for text ids if hypothesis is available.
    """
    hypothesis = pytest.importorskip("hypothesis")
    from hypothesis import given, strategies as st

    @given(st.from_regex(r"[0-9]{1,8}", fullmatch=True))
    def check(identifier):
        """Record the identifier inspected by the formula-cache helper.

        Args:
            identifier: Membership identifier checked by the formula-cache helper.

        Returns:
            None. Record the identifier inspected by the formula-cache helper.
        """
        source = tmp_path / f"{identifier}.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Membership"
        sheet.append(
            ["Organisation ID", "Name", "Country", "Type", "Status", "Node Contributor"]
        )
        sheet.append([identifier, "Name", "Belgium", "Member", "Active", None])
        workbook.save(source)
        assert read_membership(source)["organisations"][0]["organisation_id"] == identifier

    check()


def test_writer_reuses_equivalent_contributor_spelling(tmp_path):
    """Verify writer reuses equivalent contributor spelling.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies writer reuses equivalent contributor spelling.
    """
    source = _make_source(tmp_path / "equivalent.xlsx")
    book = load_workbook(source)
    book["Membership"]["H3"] = " eosc   node bbmri-eric "
    book.save(source)
    parsed = read_membership(source)
    destination = tmp_path / "equivalent-output.xlsx"
    write_matches_xlsx(parsed, [{"organisation_id": "0012", "eosc_name": "Institution",
                               "directory_juridical_person": "Institution", "biobank_ids": ["B1"]}],
                       destination)
    output = load_workbook(destination)
    assert output["Membership"].max_column == 8
    assert output["Membership"]["H3"].value == " eosc   node bbmri-eric "
    output.close()
