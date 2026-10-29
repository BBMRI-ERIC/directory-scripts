"""Test combined coordinate diagnostics without importing executable-side I/O."""

import pytest


from geocoding_utils import parse_decimal_coordinates


def test_parse_decimal_coordinates_combines_both_out_of_range_errors():
    """Verify parse decimal coordinates combines both out of range errors.

    Returns:
        None. Verifies parse decimal coordinates combines both out of range errors.
    """
    with pytest.raises(ValueError, match="longitude out of range: '-2985980'; latitude out of range: '43297691'"):
        parse_decimal_coordinates("-2985980", "43297691")


def test_parse_decimal_coordinates_combines_parse_and_range_errors():
    """Verify parse decimal coordinates combines parse and range errors.

    Returns:
        None. Verifies parse decimal coordinates combines parse and range errors.
    """
    with pytest.raises(ValueError, match="longitude parse error: .*; latitude out of range: '37929341'"):
        parse_decimal_coordinates("1.432.101", "37929341")
