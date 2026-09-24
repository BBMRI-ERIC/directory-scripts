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
    """Aggregate local validation failures in a Pydantic-compatible error shape.

    Attributes:
        _errors: Original validation-record list retained internally; `errors()`
            returns a shallow copy of this list.
    """

    def __init__(self, errors: list[dict[str, Any]]):
        """Initialize the exception and derive its semicolon-separated message.

        Args:
            errors: Structured records with optional `loc` and `msg` keys. The list
                itself is retained, so callers that own it must not mutate it after
                construction if they require stable exception details.
        """
        self._errors = errors
        message = "; ".join(
            f"{'.'.join(str(part) for part in error.get('loc', ()))}: {error.get('msg', 'invalid value')}"
            if error.get("loc")
            else str(error.get("msg", "invalid value"))
            for error in errors
        )
        super().__init__(message)

    def errors(self) -> list[dict[str, Any]]:
        """Return a shallow copy of the structured validation records.

        Returns:
            New outer list containing the original record mappings; mappings are not
            deep-copied.
        """
        return list(self._errors)


def _make_error(loc: tuple[str | int, ...], msg: str) -> dict[str, Any]:
    """Create one validation record in the compatibility error format.

    Args:
        loc: Field/index path identifying the invalid input location.
        msg: Human-readable validation message.

    Returns:
        New mapping with exactly `loc` and `msg` keys.
    """
    return {"loc": loc, "msg": msg}


def _raise_if_errors(errors: list[dict[str, Any]]) -> None:
    """Raise aggregated validation errors only when the supplied list is nonempty.

    Args:
        errors: Accumulated validation records retained by a raised `ValidationError`.

    Returns:
        None when `errors` is empty.

    Raises:
        ValidationError: If at least one record was accumulated.
    """
    if errors:
        raise ValidationError(errors)


def _non_empty_string(value: Any, *, field_name: str) -> str:
    """Coerce a required field to stripped, nonempty text.

    Args:
        value: Required input value; non-`None` values are stringified then stripped.
        field_name: Field path used in the structured error record.

    Returns:
        Stripped string value.

    Raises:
        ValidationError: If the value is missing or becomes empty after stripping.
    """
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
    """Read one string field, honoring aliases and required/default semantics.

    Args:
        payload: Input mapping read without mutation.
        field_name: Preferred key and error-location name.
        aliases: Fallback keys searched after the preferred key.
        required: Whether a present value must be nonempty and absence raises.
        default: Value returned for an absent/`None` optional field.

    Returns:
        Stripped required value, stringified optional value, or `default`.

    Raises:
        ValidationError: If a required field is absent, null, or blank.
    """
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
    """Read a list field or return a fresh list made from its default.

    Args:
        payload: Input mapping read without mutation.
        field_name: Required list key when present.
        default: Optional fallback sequence copied into a new list for absent/blank
            fields.

    Returns:
        Existing payload list without copying, or a newly allocated fallback list.

    Raises:
        ValidationError: If a present nonblank value is not a list.
    """
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
    """Provide the minimal ``dict()`` compatibility API shared by local models.

    Attributes:
        This compatibility base declares no fields of its own; dataclass
        subclasses define the validated fields serialized by ``dict()``.
    """

    def dict(self) -> dict[str, Any]:
        """Return a shallow mapping of this instance's stored attributes.

        Returns:
            New dictionary copied from `__dict__`; nested mutable values remain shared.
        """
        return dict(self.__dict__)


@dataclass
class ToolConnectionSettingsModel(_BaseModel):
    """Validate common Directory connection settings for local CLIs.

    Attributes:
        directory_target: Required Directory endpoint/target string, stripped.
        directory_username: Username required only when no token is supplied.
        directory_password: Password required only when no token is supplied.
        directory_token: Stripped token, or `None`; its presence permits blank
            username and password.
    """

    directory_target: str
    directory_username: str = ""
    directory_password: str = ""
    directory_token: Optional[str] = None

    @classmethod
    def parse_obj(cls, payload: Any) -> "ToolConnectionSettingsModel":
        """Validate and normalize local Directory connection settings.

        Args:
            payload: JSON-like mapping with target and either token or credentials.

        Returns:
            New normalized settings model. With a token, username/password are
            stringified but not required.

        Raises:
            ValidationError: If input is not a mapping or required credentials/target
                are missing or blank.
        """
        if not isinstance(payload, dict):
            raise ValidationError([_make_error((), "input must be a JSON object")])
        errors: list[dict[str, Any]] = []

        def parse_required(name: str) -> str:
            """Parse one required payload field while accumulating validation errors.

            Args:
                name: Payload key and validation-field name.

            Returns:
                Stripped value, or an empty placeholder after recording its error.
            """
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
    """Validate resolved ``directory-tables-modifier.py`` runtime settings.

    Attributes:
        schema_name: Required schema name, accepting legacy input key `schema`.
        table: Required target table name.
        file_format: One of `auto`, `csv`, or `tsv`.
        separator: Optional single-character delimiter, with `\\t`/`tab` normalized
            to a literal tab.
        tsv_quote_char: Required single-character quote marker for TSV parsing.
        tsv_escape_char: Optional single-character TSV escape marker.
    """

    schema_name: str = ""
    table: str = ""
    file_format: str = "auto"
    separator: Optional[str] = None
    tsv_quote_char: str = '"'
    tsv_escape_char: Optional[str] = None

    @classmethod
    def parse_obj(cls, payload: Any) -> "TableModifierSettingsModel":
        """Validate resolved table-modifier connection and delimited-file settings.

        Args:
            payload: JSON-like mapping containing base connection fields and table
                settings, including optional legacy `schema`.

        Returns:
            New model with normalized delimiter aliases and inherited credentials.

        Raises:
            ValidationError: If required fields, connection settings, format, or
                delimiter/quote/escape constraints are invalid.
        """
        if not isinstance(payload, dict):
            raise ValidationError([_make_error((), "input must be a JSON object")])
        base = ToolConnectionSettingsModel.parse_obj(payload)
        errors: list[dict[str, Any]] = []

        def parse_non_empty(field_name: str, aliases: tuple[str, ...] = ()) -> str:
            """Parse a required field, optionally accepting its first present alias.

            Args:
                field_name: Preferred key and error location.
                aliases: Fallback keys searched only when the preferred value is null.

            Returns:
                Stripped value, or an empty placeholder after adding an error.
            """
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
    """Validate resolved ``collection-factsheet-descriptor-updater.py`` settings.

    Attributes:
        schema_name: Required write schema, accepting legacy input key `schema`.
        collection_id: Required Directory collection ID to update.
    """

    schema_name: str = ""
    collection_id: str = ""

    @classmethod
    def parse_obj(cls, payload: Any) -> "FactsheetUpdaterSettingsModel":
        """Validate connection settings plus a fact-sheet update target.

        Args:
            payload: JSON-like mapping with base connection values, schema, and
                collection ID.

        Returns:
            New settings model with normalized inherited connection values.

        Raises:
            ValidationError: If the input, connection settings, schema, or collection
                ID is invalid.
        """
        if not isinstance(payload, dict):
            raise ValidationError([_make_error((), "input must be a JSON object")])
        base = ToolConnectionSettingsModel.parse_obj(payload)
        errors: list[dict[str, Any]] = []

        def parse_non_empty(field_name: str, aliases: tuple[str, ...] = ()) -> str:
            """Parse a required field while collecting its validation failure.

            Args:
                field_name: Preferred payload key and error location.
                aliases: Keys checked when the preferred value is null.

            Returns:
                Stripped value, or an empty placeholder after recording an error.
            """
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
    """Normalized warning-suppression record.

    Attributes:
        check_id: Required nonblank warning or fix check identifier.
        entity_id: Required nonblank affected Directory entity ID.
        entity_type: Optional uppercase entity kind limited to supported warning types.
        suppress_warning: Whether matching warnings are hidden; defaults to true.
        suppress_fix: Whether attached fix proposals are hidden; defaults to true.
        reason: Free-text suppression rationale, preserving whitespace except `None`.
        added_by: Optional stripped actor identifier.
        added_on: Optional date-like `YYYY-MM-DD` text, or empty text.
        expires_on: Optional date-like `YYYY-MM-DD` text, or empty text.
        ticket: Optional stripped tracking reference.
        extras: Unrecognized input keys preserved by reference for round-tripping.
    """

    check_id: str
    entity_id: str
    entity_type: str = ""
    suppress_warning: bool = True
    suppress_fix: bool = True
    reason: str = ""
    added_by: str = ""
    added_on: str = ""
    expires_on: str = ""
    ticket: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse_obj(cls, payload: Any) -> "WarningSuppressionEntryModel":
        """Validate and normalize a canonical warning-suppression entry.

        Args:
            payload: JSON-like mapping; unknown keys are retained as `extras`.

        Returns:
            New normalized suppression model with permissive boolean spellings.

        Raises:
            ValidationError: If required identifiers, entity type, boolean spellings,
                or coarse date format/ranges are invalid.
        """
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

        def parse_optional_bool(field_name: str, default: bool) -> bool:
            """Normalize an optional boolean while appending invalid-value errors.

            Args:
                field_name: Payload key and error location.
                default: Value used for missing and invalid input.

            Returns:
                Native boolean, accepted case-insensitive string spelling, or default.
            """
            value = payload.get(field_name)
            if value is None:
                return default
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"true", "1", "yes", "y", "on"}:
                    return True
                if normalized in {"false", "0", "no", "n", "off"}:
                    return False
            errors.append(_make_error((field_name,), "must be a boolean"))
            return default

        def parse_optional_date(field_name: str) -> str:
            """Normalize an optional coarse ISO date while collecting format errors.

            Args:
                field_name: Payload key and error location.

            Returns:
                Empty text for missing input, otherwise stripped text even when an
                error is recorded; calendar-day validity is not checked.
            """
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
        suppress_warning = parse_optional_bool("suppress_warning", True)
        suppress_fix = parse_optional_bool("suppress_fix", True)
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
                "suppress_warning",
                "suppress_fix",
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
            suppress_warning=suppress_warning,
            suppress_fix=suppress_fix,
            reason=normalized_reason,
            added_by=added_by,
            added_on=added_on,
            expires_on=expires_on,
            ticket=ticket,
            extras=extras,
        )


@dataclass
class AICheckedEntityModel(_BaseModel):
    """Validated checked-entity checksum record.

    Attributes:
        entity_id: Required nonblank Directory entity identifier.
        entity_type: Required `BIOBANK` or `COLLECTION` family.
        entity_checksum: Required nonblank digest of the full checked entity.
        source_checksum: Required nonblank digest of the rule's source fields.
        extras: Unrecognized input keys preserved by reference for round-tripping.
    """

    entity_id: str
    entity_type: str
    entity_checksum: str
    source_checksum: str
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def parse_obj(cls, payload: Any) -> "AICheckedEntityModel":
        """Validate one AI-cache checksum record and preserve unknown fields.

        Args:
            payload: JSON-like mapping containing identifiers and both checksums.

        Returns:
            New normalized record with unrecognized keys placed in `extras`.

        Raises:
            ValidationError: If the input is not a mapping, required strings are
                absent/blank, or the entity type is unsupported.
        """
        if not isinstance(payload, dict):
            raise ValidationError([_make_error((), "input must be a JSON object")])
        errors: list[dict[str, Any]] = []

        def req(name: str) -> str:
            """Parse one required string and aggregate a validation error if needed.

            Args:
                name: Payload key and validation-field name.

            Returns:
                Stripped required value, or empty placeholder after recording failure.
            """
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
        """Serialize this checksum record and merge preserved unknown fields.

        Returns:
            New mapping with canonical fields followed by `extras`; colliding extras
            intentionally override canonical keys because of the merge order.
        """
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
    """Validated AI-curated finding record.

    Attributes:
        rule: Required nonblank AI rule identifier.
        entity_id: Required nonblank affected Directory entity ID.
        entity_type: Required `BIOBANK` or `COLLECTION` family.
        severity: Required `ERROR`, `WARNING`, or `INFO` severity string.
        message: Required nonblank finding explanation.
        action: Required nonblank proposed action text.
        fields: Stringified source field identifiers; empty/null input becomes empty.
        email: Optional value stringified without stripping; null becomes empty.
        nn: Optional node/staging value stringified without stripping; null becomes empty.
        withdrawn: Optional withdrawal value stringified without stripping; null becomes
            empty.
        extras: Unrecognized input keys preserved by reference for round-tripping.
    """

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
        """Validate and normalize one AI-curated finding mapping.

        Args:
            payload: JSON-like finding mapping. Unknown keys are retained as extras.

        Returns:
            New normalized finding model.

        Raises:
            ValidationError: If required values, entity type, severity, or optional
                fields-list type are invalid.
        """
        if not isinstance(payload, dict):
            raise ValidationError([_make_error((), "input must be a JSON object")])
        errors: list[dict[str, Any]] = []

        def req(name: str) -> str:
            """Parse a required finding field while collecting any failure.

            Args:
                name: Payload key and validation-field name.

            Returns:
                Stripped required value, or empty placeholder after recording failure.
            """
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
        """Serialize the finding with copied field names and preserved extras.

        Returns:
            New mapping; `fields` is copied, while unknown `extras` are merged last.
        """
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
    """Validated shareable AI cache file payload.

    Attributes:
        schema_name: Optional cache schema text, accepting legacy input key `schema`.
        rule: Optional rule text; an empty input rule becomes `None`.
        generator: Generator marker string, defaulting to `legacy` when blank/missing.
        withdrawn_scope: Scope limited to the three supported cache scope labels.
        checked_fields: Stringified checked-source field names.
        checked_entities: Validated checksum records for the reviewed entity scope.
        findings: Validated AI-curated findings; the payload must explicitly include it.
        extras: Unrecognized input keys preserved by reference for round-tripping.
    """

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
        """Validate a complete shareable AI-cache JSON payload.

        Args:
            payload: JSON-like cache object with optional metadata and required
                `findings`; legacy `schema` is accepted.

        Returns:
            New normalized payload model with nested records validated and unknown
            top-level fields retained as extras.

        Raises:
            ValidationError: If the object shape, scope, nested lists, or nested
                records fail validation. Nested locations are prefixed with indexes.
        """
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
        """Serialize the payload with newly allocated nested output lists.

        Returns:
            New mapping containing canonical metadata, serialized nested models, and
            preserved extras merged last.
        """
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
