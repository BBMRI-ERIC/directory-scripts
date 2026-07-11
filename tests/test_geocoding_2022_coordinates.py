from ast import FunctionDef, Import, Module, alias, fix_missing_locations, parse
from pathlib import Path

import pytest


GEOCODING_PATH = Path("geocoding_2022.py")


def _load_parse_decimal_coordinates():
    source = GEOCODING_PATH.read_text(encoding="utf-8")
    tree = parse(source, filename=str(GEOCODING_PATH))
    wanted = {"_parse_decimal_coordinate_component", "parse_decimal_coordinates"}
    selected = [
        node
        for node in tree.body
        if isinstance(node, FunctionDef) and node.name in wanted
    ]
    module = Module(
        body=[Import(names=[alias(name="re", asname=None)])] + selected,
        type_ignores=[],
    )
    namespace = {}
    exec(compile(fix_missing_locations(module), str(GEOCODING_PATH), "exec"), namespace)
    return namespace["parse_decimal_coordinates"]


def test_parse_decimal_coordinates_combines_both_out_of_range_errors():
    parse_decimal_coordinates = _load_parse_decimal_coordinates()

    with pytest.raises(ValueError, match="longitude out of range: '-2985980'; latitude out of range: '43297691'"):
        parse_decimal_coordinates("-2985980", "43297691")


def test_parse_decimal_coordinates_combines_parse_and_range_errors():
    parse_decimal_coordinates = _load_parse_decimal_coordinates()

    with pytest.raises(ValueError, match="longitude parse error: .*; latitude out of range: '37929341'"):
        parse_decimal_coordinates("1.432.101", "37929341")
