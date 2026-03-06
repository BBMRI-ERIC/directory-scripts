from validation_models import (
    FactsheetUpdaterSettingsModel,
    TableModifierSettingsModel,
    ToolConnectionSettingsModel,
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


def test_table_modifier_settings_model_accepts_semicolon_separator():
    settings = TableModifierSettingsModel.parse_obj(
        {
            "schema": "BBMRI-CZ",
            "table": "CollectionFacts",
            "directory_target": "https://directory.example.org",
            "directory_username": "user",
            "directory_password": "secret",
            "file_format": "csv",
            "separator": ";",
        }
    )
    assert settings.separator == ";"


def test_table_modifier_settings_model_rejects_invalid_separator():
    try:
        TableModifierSettingsModel.parse_obj(
            {
                "schema": "BBMRI-CZ",
                "table": "CollectionFacts",
                "directory_target": "https://directory.example.org",
                "directory_username": "user",
                "directory_password": "secret",
                "file_format": "csv",
                "separator": ";;",
            }
        )
    except ValidationError as exc:
        assert "single character" in str(exc)
    else:
        raise AssertionError("Expected ValidationError for invalid separator")


def test_table_modifier_settings_model_accepts_tab_separator_alias():
    settings = TableModifierSettingsModel.parse_obj(
        {
            "schema": "BBMRI-CZ",
            "table": "CollectionFacts",
            "directory_target": "https://directory.example.org",
            "directory_username": "user",
            "directory_password": "secret",
            "file_format": "tsv",
            "separator": r"\t",
        }
    )
    assert settings.separator == "\t"


def test_connection_settings_accepts_token_without_credentials():
    settings = ToolConnectionSettingsModel.parse_obj(
        {
            "directory_target": "https://directory.example.org",
            "directory_token": "my-secret-token",
        }
    )
    assert settings.directory_token == "my-secret-token"
    assert settings.directory_username == ""
    assert settings.directory_password == ""


def test_connection_settings_rejects_missing_credentials_and_token():
    try:
        ToolConnectionSettingsModel.parse_obj(
            {
                "directory_target": "https://directory.example.org",
            }
        )
    except ValidationError as exc:
        assert "directory_username" in str(exc)
    else:
        raise AssertionError("Expected ValidationError when neither token nor credentials provided")


def test_table_modifier_passes_token_through():
    settings = TableModifierSettingsModel.parse_obj(
        {
            "schema": "BBMRI-CZ",
            "table": "CollectionFacts",
            "directory_target": "https://directory.example.org",
            "directory_token": "tok-123",
        }
    )
    assert settings.directory_token == "tok-123"


def test_factsheet_updater_passes_token_through():
    settings = FactsheetUpdaterSettingsModel.parse_obj(
        {
            "schema": "BBMRI-EU",
            "collection_id": "bbmri-eric:ID:EU_BBMRI-ERIC:collection:MICAN",
            "directory_target": "https://directory.example.org",
            "directory_token": "tok-456",
        }
    )
    assert settings.directory_token == "tok-456"
