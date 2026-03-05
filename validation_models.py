"""Scoped validation helpers for local tool/config/cache payloads.

This module intentionally avoids optional third-party validation runtimes so
that command-line tools keep working in constrained environments (for example
Cygwin). The API keeps compatibility with existing callers:
`Model.parse_obj(...)`, `model.dict()`, and `ValidationError.errors()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


class ValidationError(ValueError):
    """Structured validation error with machine-readable ``errors()`` output."""

    def __init__(self, errors: list[dict[str, Any]]):
        self._errors = errors
        message = "; ".join(
            f"{'.'.join(str(part) for part in error.get('loc', ()))}: {error.get('msg', 'invalid value')}"
            if error.get("loc")
            else str(error.get("msg", "invalid value"))
            for error in errors
        )
        super().__init__(message)

    def errors(self) -> list[dict[str, Any]]:
        return list(self._errors)


def _make_error(loc: tuple[str | int, ...], msg: str) -> dict[str, Any]:
    return {"loc": loc, "msg": msg}


def _raise_if_errors(errors: list[dict[str, Any]]) -> None:
    if errors:
        raise ValidationError(errors)


def _non_empty_string(value: Any, *, field_name: str) -> str:
    if value is None:
        raise ValidationError([_make_error((field_name,), "field is required")])
    text = str(value).strip()
    if not text:
        raise ValidationError([_make_error((field_name,), "field must not be empty")])
    return text


def _get_string(
    payload: dict[str, Any],
    *,
    field_name: str,
    aliases: tuple[str, ...] = (),
    required: bool = True,
    default: Optional[str] = None,
) -> Optional[str]:
    for key in (field_name, *aliases):
        if key in payload:
            value = payload[key]
            if required:
                return _non_empty_string(value, field_name=field_name)
            if value is None:
                return default
            return str(value)
    if required:
        raise ValidationError([_make_error((field_name,), "field is required")])
    return default


def _get_list(
    payload: dict[str, Any],
    *,
    field_name: str,
    default: Optional[list[Any]] = None,
) -> list[Any]:
    if field_name not in payload:
        return [] if default is None else list(default)
    value = payload[field_name]
    if value is None or value == "":
        return [] if default is None else list(default)
    if not isinstance(value, list):
        raise ValidationError([_make_error((field_name,), "must be a list")])
    return value


@dataclass
class _BaseModel:
    """Small base class exposing ``dict()`` for compatibility."""

    def dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class ToolConnectionSettingsModel(_BaseModel):
    """Validate common Directory connection settings for local CLIs."""

    directory_target: str
    directory_username: str = ""
    directory_password: str = ""
    directory_token: Optional[str] = None

    @classmethod
    def parse_obj(cls, payload: Any) -> "ToolConnectionSettingsModel":
        if not isinstance(payload, dict):
            raise ValidationError([_make_error((), "input must be a JSON object")])
        errors: list[dict[str, Any]] = []

        def parse_required(name: str) -> str:
            try:
                return _non_empty_string(payload.get(name), field_name=name)
            except ValidationError as exc:
                errors.extend(exc.errors())
                return ""

        target = parse_required("directory_target")

        token_raw = payload.get("directory_token")
        token = str(token_raw).strip() if token_raw not in (None, "") else None

        if token:
            username = str(payload.get("directory_username") or "")
            password = str(payload.get("directory_password") or "")
        else:
            username = parse_required("directory_username")
            password = parse_required("directory_password")

        _raise_if_errors(errors)
        return cls(
            directory_target=target,
            directory_username=username,
            directory_password=password,
            directory_token=token,
        )


@dataclass
class TableModifierSettingsModel(ToolConnectionSettingsModel):
    """Validate resolved ``directory-tables-modifier.py`` runtime settings."""

    schema_name: str = ""
    table: str = ""
    file_format: str = "auto"
    separator: Optional[str] = None
    tsv_quote_char: str = '"'
    tsv_escape_char: Optional[str] = None

    @classmethod
    def parse_obj(cls, payload: Any) -> "TableModifierSettingsModel":
        if not isinstance(payload, dict):
            raise ValidationError([_make_error((), "input must be a JSON object")])
        base = ToolConnectionSettingsModel.parse_obj(payload)
        errors: list[dict[str, Any]] = []

        def parse_non_empty(field_name: str, aliases: tuple[str, ...] = ()) -> str:
            value = payload.get(field_name)
            if value is None:
                for alias in aliases:
                    if alias in payload:
                        value = payload[alias]
                        break
            try:
                return _non_empty_string(value, field_name=field_name)
            except ValidationError as exc:
                errors.extend(exc.errors())
                return ""

        schema_name = parse_non_empty("schema_name", aliases=("schema",))
        table = parse_non_empty("table")

        file_format = str(payload.get("file_format", "auto"))
        if file_format not in {"auto", "csv", "tsv"}:
            errors.append(_make_error(("file_format",), "must be one of: auto, csv, tsv"))

        separator_raw = payload.get("separator")
        if separator_raw in (None, ""):
            separator = None
        else:
            separator = str(separator_raw)
            if separator == r"\t" or separator.lower() == "tab":
                separator = "\t"
            if len(separator) != 1:
                errors.append(
                    _make_error(
                        ("separator",),
                        "must be a single character (or use \\\\t/tab for tab)",
                    )
                )

        quote_raw = payload.get("tsv_quote_char", '"')
        try:
            quote_char = _non_empty_string(quote_raw, field_name="tsv_quote_char")
            if len(quote_char) != 1:
                errors.append(_make_error(("tsv_quote_char",), "must be a single character"))
        except ValidationError as exc:
            errors.extend(exc.errors())
            quote_char = '"'

        escape_raw = payload.get("tsv_escape_char")
        if escape_raw in (None, ""):
            escape_char = None
        else:
            escape_char = str(escape_raw)
            if len(escape_char) != 1:
                errors.append(_make_error(("tsv_escape_char",), "must be a single character"))

        _raise_if_errors(errors)
        return cls(
            directory_target=base.directory_target,
            directory_username=base.directory_username,
            directory_password=base.directory_password,
            directory_token=base.directory_token,
            schema_name=schema_name,
            table=table,
            file_format=file_format,
            separator=separator,
            tsv_quote_char=quote_char,
            tsv_escape_char=escape_char,
        )


@dataclass
class FactsheetUpdaterSettingsModel(ToolConnectionSettingsModel):
    """Validate resolved ``collection-factsheet-descriptor-updater.py`` settings."""

    schema_name: str = ""
    collection_id: str = ""

    @classmethod
    def parse_obj(cls, payload: Any) -> "FactsheetUpdaterSettingsModel":
        if not isinstance(payload, dict):
            raise ValidationError([_make_error((), "input must be a JSON object")])
        base = ToolConnectionSettingsModel.parse_obj(payload)
        errors: list[dict[str, Any]] = []

        def parse_non_empty(field_name: str, aliases: tuple[str, ...] = ()) -> str:
            value = payload.get(field_name)
            if value is None:
                for alias in aliases:
                    if alias in payload:
                        value = payload[alias]
                        break
            try:
                return _non_empty_string(value, field_name=field_name)
            except ValidationError as exc:
                errors.extend(exc.errors())
                return ""

        schema_name = parse_non_empty("schema_name", aliases=("schema",))
        collection_id = parse_non_empty("collection_id")
        _raise_if_errors(errors)
        return cls(
            directory_target=base.directory_target,
            directory_username=base.directory_username,
            directory_password=base.directory_password,
            directory_token=base.directory_token,
            schema_name=schema_name,
            collection_id=collection_id,
        )


@dataclass
class WarningSuppressionEntryModel(_BaseModel):
    """Normalized warning-suppression record."""

    check_id: str
    entity_id: str
    entity_type: str = ""
    reason: str = ""
    added_by: str = ""
    added_on: str = ""
    expires_on: str = ""
    ticket: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse_obj(cls, payload: Any) -> "WarningSuppressionEntryModel":
        if not isinstance(payload, dict):
            raise ValidationError([_make_error((), "input must be a JSON object")])
        errors: list[dict[str, Any]] = []

        try:
            check_id = _non_empty_string(payload.get("check_id"), field_name="check_id")
        except ValidationError as exc:
            errors.extend(exc.errors())
            check_id = ""
        try:
            entity_id = _non_empty_string(payload.get("entity_id"), field_name="entity_id")
        except ValidationError as exc:
            errors.extend(exc.errors())
            entity_id = ""

        reason = payload.get("reason")
        normalized_reason = "" if reason is None else str(reason)

        entity_type = payload.get("entity_type")
        normalized_entity_type = "" if entity_type is None else str(entity_type).strip().upper()
        if normalized_entity_type and normalized_entity_type not in {"BIOBANK", "COLLECTION", "CONTACT", "NETWORK"}:
            errors.append(
                _make_error(
                    ("entity_type",),
                    "must be one of: BIOBANK, COLLECTION, CONTACT, NETWORK",
                )
            )

        def parse_optional_date(field_name: str) -> str:
            value = payload.get(field_name)
            if value in (None, ""):
                return ""
            text = str(value).strip()
            parts = text.split("-")
            if len(parts) != 3 or not all(part.isdigit() for part in parts):
                errors.append(_make_error((field_name,), "must be in YYYY-MM-DD format"))
                return text
            year, month, day = (int(part) for part in parts)
            if year < 1900 or month < 1 or month > 12 or day < 1 or day > 31:
                errors.append(_make_error((field_name,), "must be in YYYY-MM-DD format"))
            return text

        added_by = "" if payload.get("added_by") is None else str(payload.get("added_by")).strip()
        added_on = parse_optional_date("added_on")
        expires_on = parse_optional_date("expires_on")
        ticket = "" if payload.get("ticket") is None else str(payload.get("ticket")).strip()

        extras = {
            key: value
            for key, value in payload.items()
            if key
            not in {
                "check_id",
                "entity_id",
                "entity_type",
                "reason",
                "added_by",
                "added_on",
                "expires_on",
                "ticket",
            }
        }

        _raise_if_errors(errors)
        return cls(
            check_id=check_id,
            entity_id=entity_id,
            entity_type=normalized_entity_type,
            reason=normalized_reason,
            added_by=added_by,
            added_on=added_on,
            expires_on=expires_on,
            ticket=ticket,
            extras=extras,
        )


@dataclass
class AICheckedEntityModel(_BaseModel):
    """Validated checked-entity checksum record."""

    entity_id: str
    entity_type: str
    entity_checksum: str
    source_checksum: str
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse_obj(cls, payload: Any) -> "AICheckedEntityModel":
        if not isinstance(payload, dict):
            raise ValidationError([_make_error((), "input must be a JSON object")])
        errors: list[dict[str, Any]] = []

        def req(name: str) -> str:
            try:
                return _non_empty_string(payload.get(name), field_name=name)
            except ValidationError as exc:
                errors.extend(exc.errors())
                return ""

        entity_id = req("entity_id")
        entity_type = req("entity_type")
        if entity_type and entity_type not in {"BIOBANK", "COLLECTION"}:
            errors.append(_make_error(("entity_type",), "must be one of: BIOBANK, COLLECTION"))
        entity_checksum = req("entity_checksum")
        source_checksum = req("source_checksum")

        _raise_if_errors(errors)
        extras = {
            key: value
            for key, value in payload.items()
            if key
            not in {"entity_id", "entity_type", "entity_checksum", "source_checksum"}
        }
        return cls(
            entity_id=entity_id,
            entity_type=entity_type,
            entity_checksum=entity_checksum,
            source_checksum=source_checksum,
            extras=extras,
        )

    def dict(self) -> dict[str, Any]:
        out = {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "entity_checksum": self.entity_checksum,
            "source_checksum": self.source_checksum,
        }
        out.update(self.extras)
        return out


@dataclass
class AIFindingModel(_BaseModel):
    """Validated AI-curated finding record."""

    rule: str
    entity_id: str
    entity_type: str
    severity: str
    message: str
    action: str
    fields: list[str] = field(default_factory=list)
    email: str = ""
    nn: str = ""
    withdrawn: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse_obj(cls, payload: Any) -> "AIFindingModel":
        if not isinstance(payload, dict):
            raise ValidationError([_make_error((), "input must be a JSON object")])
        errors: list[dict[str, Any]] = []

        def req(name: str) -> str:
            try:
                return _non_empty_string(payload.get(name), field_name=name)
            except ValidationError as exc:
                errors.extend(exc.errors())
                return ""

        rule = req("rule")
        entity_id = req("entity_id")
        entity_type = req("entity_type")
        if entity_type and entity_type not in {"BIOBANK", "COLLECTION"}:
            errors.append(_make_error(("entity_type",), "must be one of: BIOBANK, COLLECTION"))
        severity = req("severity")
        if severity and severity not in {"ERROR", "WARNING", "INFO"}:
            errors.append(_make_error(("severity",), "must be one of: ERROR, WARNING, INFO"))
        message = req("message")
        action = req("action")

        raw_fields = payload.get("fields", [])
        if raw_fields in (None, ""):
            fields = []
        elif isinstance(raw_fields, list):
            fields = [str(item) for item in raw_fields]
        else:
            fields = []
            errors.append(_make_error(("fields",), "must be a list"))

        _raise_if_errors(errors)
        extras = {
            key: value
            for key, value in payload.items()
            if key
            not in {
                "rule",
                "entity_id",
                "entity_type",
                "severity",
                "message",
                "action",
                "fields",
                "email",
                "nn",
                "withdrawn",
            }
        }
        return cls(
            rule=rule,
            entity_id=entity_id,
            entity_type=entity_type,
            severity=severity,
            message=message,
            action=action,
            fields=fields,
            email="" if payload.get("email") is None else str(payload.get("email")),
            nn="" if payload.get("nn") is None else str(payload.get("nn")),
            withdrawn="" if payload.get("withdrawn") is None else str(payload.get("withdrawn")),
            extras=extras,
        )

    def dict(self) -> dict[str, Any]:
        out = {
            "rule": self.rule,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "severity": self.severity,
            "message": self.message,
            "action": self.action,
            "fields": list(self.fields),
            "email": self.email,
            "nn": self.nn,
            "withdrawn": self.withdrawn,
        }
        out.update(self.extras)
        return out


@dataclass
class AICachePayloadModel(_BaseModel):
    """Validated shareable AI cache file payload."""

    schema_name: Optional[str]
    rule: Optional[str]
    generator: str
    withdrawn_scope: str
    checked_fields: list[str]
    checked_entities: list[AICheckedEntityModel]
    findings: list[AIFindingModel]
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse_obj(cls, payload: Any) -> "AICachePayloadModel":
        if not isinstance(payload, dict):
            raise ValidationError([_make_error((), "input must be a JSON object")])
        errors: list[dict[str, Any]] = []

        schema_name = payload.get("schema_name", payload.get("schema"))
        if schema_name is not None:
            schema_name = str(schema_name)
        rule = payload.get("rule")
        if rule is not None and rule != "":
            rule = str(rule)
        elif rule == "":
            rule = None

        generator = payload.get("generator", "legacy")
        if generator in (None, ""):
            generator = "legacy"
        generator = str(generator)

        withdrawn_scope = str(payload.get("withdrawn_scope", "active-only"))
        if withdrawn_scope not in {"active-only", "include-withdrawn", "only-withdrawn"}:
            errors.append(
                _make_error(
                    ("withdrawn_scope",),
                    "must be one of: active-only, include-withdrawn, only-withdrawn",
                )
            )

        try:
            checked_fields_raw = _get_list(payload, field_name="checked_fields", default=[])
            checked_fields = [str(item) for item in checked_fields_raw]
        except ValidationError as exc:
            errors.extend(exc.errors())
            checked_fields = []

        checked_entities_raw = payload.get("checked_entities", [])
        if checked_entities_raw in (None, ""):
            checked_entities_raw = []
        if not isinstance(checked_entities_raw, list):
            errors.append(_make_error(("checked_entities",), "must be a list"))
            checked_entities_raw = []

        checked_entities: list[AICheckedEntityModel] = []
        for index, record in enumerate(checked_entities_raw):
            try:
                checked_entities.append(AICheckedEntityModel.parse_obj(record))
            except ValidationError as exc:
                for error in exc.errors():
                    loc = ("checked_entities", index, *tuple(error.get("loc", ())))
                    errors.append(_make_error(loc, error.get("msg", "invalid value")))

        if "findings" not in payload:
            errors.append(_make_error(("findings",), "field is required"))
            findings_raw = []
        else:
            findings_raw = payload.get("findings")
        if not isinstance(findings_raw, list):
            errors.append(_make_error(("findings",), "must be a list"))
            findings_raw = []

        findings: list[AIFindingModel] = []
        for index, record in enumerate(findings_raw):
            try:
                findings.append(AIFindingModel.parse_obj(record))
            except ValidationError as exc:
                for error in exc.errors():
                    loc = ("findings", index, *tuple(error.get("loc", ())))
                    errors.append(_make_error(loc, error.get("msg", "invalid value")))

        _raise_if_errors(errors)
        extras = {
            key: value
            for key, value in payload.items()
            if key
            not in {
                "schema_name",
                "schema",
                "rule",
                "generator",
                "withdrawn_scope",
                "checked_fields",
                "checked_entities",
                "findings",
            }
        }
        return cls(
            schema_name=schema_name,
            rule=rule,
            generator=generator,
            withdrawn_scope=withdrawn_scope,
            checked_fields=checked_fields,
            checked_entities=checked_entities,
            findings=findings,
            extras=extras,
        )

    def dict(self) -> dict[str, Any]:
        out = {
            "schema_name": self.schema_name,
            "rule": self.rule,
            "generator": self.generator,
            "withdrawn_scope": self.withdrawn_scope,
            "checked_fields": list(self.checked_fields),
            "checked_entities": [entry.dict() for entry in self.checked_entities],
            "findings": [finding.dict() for finding in self.findings],
        }
        out.update(self.extras)
        return out
