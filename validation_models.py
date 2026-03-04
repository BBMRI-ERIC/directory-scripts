"""Scoped Pydantic models for local tool/config/cache validation."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, validator


def _non_empty_string(value: Any) -> str:
    if value is None:
        raise ValueError("field is required")
    text = str(value).strip()
    if not text:
        raise ValueError("field must not be empty")
    return text


class ToolConnectionSettingsModel(BaseModel):
    """Validate common Directory connection settings for local CLIs."""

    directory_target: str
    directory_username: str
    directory_password: str

    _validate_directory_target = validator("directory_target", allow_reuse=True)(_non_empty_string)
    _validate_directory_username = validator("directory_username", allow_reuse=True)(_non_empty_string)
    _validate_directory_password = validator("directory_password", allow_reuse=True)(_non_empty_string)


class TableModifierSettingsModel(ToolConnectionSettingsModel):
    """Validate resolved `directory-tables-modifier.py` runtime settings."""

    schema_name: str
    table: str
    file_format: str = "auto"
    tsv_quote_char: str = '"'
    tsv_escape_char: Optional[str] = None

    _validate_schema = validator("schema_name", allow_reuse=True)(_non_empty_string)
    _validate_table = validator("table", allow_reuse=True)(_non_empty_string)

    @validator("file_format", allow_reuse=True)
    def validate_file_format(cls, value: str) -> str:
        if value not in {"auto", "csv", "tsv"}:
            raise ValueError("must be one of: auto, csv, tsv")
        return value

    @validator("tsv_quote_char", allow_reuse=True)
    def validate_tsv_quote_char(cls, value: str) -> str:
        value = _non_empty_string(value)
        if len(value) != 1:
            raise ValueError("must be a single character")
        return value

    @validator("tsv_escape_char", allow_reuse=True)
    def validate_tsv_escape_char(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        value = str(value)
        if len(value) != 1:
            raise ValueError("must be a single character")
        return value

    class Config:
        allow_population_by_field_name = True
        fields = {"schema_name": "schema"}


class FactsheetUpdaterSettingsModel(ToolConnectionSettingsModel):
    """Validate resolved `collection-factsheet-descriptor-updater.py` settings."""

    schema_name: str
    collection_id: str

    _validate_schema = validator("schema_name", allow_reuse=True)(_non_empty_string)
    _validate_collection_id = validator("collection_id", allow_reuse=True)(_non_empty_string)

    class Config:
        allow_population_by_field_name = True
        fields = {"schema_name": "schema"}


class WarningSuppressionEntryModel(BaseModel):
    """Normalized warning-suppression record."""

    check_id: str
    entity_id: str
    reason: str = ""

    _validate_check_id = validator("check_id", allow_reuse=True)(_non_empty_string)
    _validate_entity_id = validator("entity_id", allow_reuse=True)(_non_empty_string)

    @validator("reason", pre=True, always=True, allow_reuse=True)
    def normalize_reason(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value)


class AICheckedEntityModel(BaseModel):
    """Validated checked-entity checksum record."""

    entity_id: str
    entity_type: str
    entity_checksum: str
    source_checksum: str

    class Config:
        extra = "allow"

    _validate_entity_id = validator("entity_id", allow_reuse=True)(_non_empty_string)
    _validate_entity_checksum = validator("entity_checksum", allow_reuse=True)(_non_empty_string)
    _validate_source_checksum = validator("source_checksum", allow_reuse=True)(_non_empty_string)

    @validator("entity_type", allow_reuse=True)
    def validate_entity_type(cls, value: str) -> str:
        value = _non_empty_string(value)
        if value not in {"BIOBANK", "COLLECTION"}:
            raise ValueError("must be one of: BIOBANK, COLLECTION")
        return value


class AIFindingModel(BaseModel):
    """Validated AI-curated finding record."""

    rule: str
    entity_id: str
    entity_type: str
    severity: str
    message: str
    action: str
    fields: list[str] = []
    email: str = ""
    nn: str = ""
    withdrawn: str = ""

    class Config:
        extra = "allow"

    _validate_rule = validator("rule", allow_reuse=True)(_non_empty_string)
    _validate_entity_id = validator("entity_id", allow_reuse=True)(_non_empty_string)
    _validate_message = validator("message", allow_reuse=True)(_non_empty_string)
    _validate_action = validator("action", allow_reuse=True)(_non_empty_string)

    @validator("entity_type", allow_reuse=True)
    def validate_entity_type(cls, value: str) -> str:
        value = _non_empty_string(value)
        if value not in {"BIOBANK", "COLLECTION"}:
            raise ValueError("must be one of: BIOBANK, COLLECTION")
        return value

    @validator("severity", allow_reuse=True)
    def validate_severity(cls, value: str) -> str:
        value = _non_empty_string(value)
        if value not in {"ERROR", "WARNING", "INFO"}:
            raise ValueError("must be one of: ERROR, WARNING, INFO")
        return value

    @validator("fields", pre=True, always=True, allow_reuse=True)
    def validate_fields(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if not isinstance(value, list):
            raise ValueError("must be a list")
        return [str(item) for item in value]


class AICachePayloadModel(BaseModel):
    """Validated shareable AI cache file payload."""

    schema_name: Optional[str] = None
    rule: Optional[str] = None
    generator: str = "legacy"
    withdrawn_scope: str = "active-only"
    checked_fields: list[str] = []
    checked_entities: list[AICheckedEntityModel] = []
    findings: list[AIFindingModel]

    class Config:
        extra = "allow"
        allow_population_by_field_name = True
        fields = {"schema_name": "schema"}

    @validator("generator", pre=True, always=True, allow_reuse=True)
    def normalize_generator(cls, value: Any) -> str:
        if value is None or value == "":
            return "legacy"
        return str(value)

    @validator("withdrawn_scope", allow_reuse=True)
    def validate_withdrawn_scope(cls, value: str) -> str:
        value = _non_empty_string(value)
        if value not in {"active-only", "include-withdrawn", "only-withdrawn"}:
            raise ValueError("must be one of: active-only, include-withdrawn, only-withdrawn")
        return value

    @validator("checked_fields", pre=True, always=True, allow_reuse=True)
    def validate_checked_fields(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if not isinstance(value, list):
            raise ValueError("must be a list")
        return [str(item) for item in value]
