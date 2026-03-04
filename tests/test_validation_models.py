from validation_models import (
    FactsheetUpdaterSettingsModel,
    TableModifierSettingsModel,
    ValidationError,
)


def test_table_modifier_settings_model_requires_single_character_tsv_quote():
    try:
        TableModifierSettingsModel.parse_obj(
            {
                "schema": "BBMRI-CZ",
                "table": "CollectionFacts",
                "directory_target": "https://directory.example.org",
                "directory_username": "user",
                "directory_password": "secret",
                "file_format": "tsv",
                "tsv_quote_char": "''",
            }
        )
    except ValidationError as exc:
        assert "single character" in str(exc)
    else:
        raise AssertionError("Expected ValidationError for invalid tsv_quote_char")


def test_factsheet_updater_settings_model_requires_credentials():
    try:
        FactsheetUpdaterSettingsModel.parse_obj(
            {
                "schema": "BBMRI-EU",
                "collection_id": "bbmri-eric:ID:EU_BBMRI-ERIC:collection:MICAN",
                "directory_target": "",
                "directory_username": "user",
                "directory_password": "",
            }
        )
    except ValidationError as exc:
        assert "field must not be empty" in str(exc)
    else:
        raise AssertionError("Expected ValidationError for empty connection settings")
