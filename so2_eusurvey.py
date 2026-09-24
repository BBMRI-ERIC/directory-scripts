"""Decode an EUSurvey active form into a reviewable JSON form manifest.

Only the explicit ``export-eus-form-json`` maintenance path uses this module's
Java-serialization decoder. Report generation reads the generated JSON manifest
and never needs to decode the EUSurvey archive again.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import importlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping
import zipfile


MANIFEST_SCHEMA_VERSION = 1
MANIFEST_GENERATOR_VERSION = "1"
_MAX_ARCHIVE_MEMBERS = 32
_MAX_ACTIVE_MEMBER_BYTES = 16 * 1024 * 1024


class FormInputError(ValueError):
    """Raised when EUSurvey form provenance or a JSON manifest is invalid."""


@dataclass(frozen=True)
class RoutingAtom:
    """One parent-choice condition that can make a field visible.

    Attributes:
        parent_uid: UID of the parent field whose answer is evaluated.
        choice_uid: UID of the parent choice that satisfies this condition.
    """

    parent_uid: str
    choice_uid: str


@dataclass(frozen=True)
class RoutingExpression:
    """Structured AND/OR conditions controlling a field's visibility.

    Attributes:
        operator: ``all`` or ``any`` relation applied to the routing atoms.
        atoms: Immutable parent-choice conditions evaluated by the relation.
    """

    operator: Literal["all", "any"]
    atoms: tuple[RoutingAtom, ...]


@dataclass(frozen=True)
class FormChoice:
    """A selectable EUSurvey value or a matrix axis label.

    Attributes:
        uid: EUSurvey identifier for the choice or matrix-axis value.
        label: Reader-facing text retained from the source form.
        position: Source ordering position used for deterministic rendering.
    """

    uid: str
    label: str
    position: int


@dataclass(frozen=True)
class FormField:
    """Normalized EUSurvey field metadata required for response validation.

    Attributes:
        uid: Stable EUSurvey field identifier.
        title: Visible field wording retained from the active form.
        field_type: Supported scalar, choice, or matrix response type.
        mandatory: Whether EUSurvey requires a response when the field is shown.
        readonly: Whether the field is displayed but cannot accept an answer.
        hidden: Whether the field is not displayed to respondents.
        position: Source order used to preserve the form's question sequence.
        choices: Selectable values for ordinary structured questions.
        shown_when: Optional normalized conditional-visibility expression.
        matrix_rows: Matrix row definitions for matrix questions.
        matrix_columns: Matrix column definitions for matrix questions.
    """

    uid: str
    title: str
    field_type: Literal["free_text", "single_choice", "multi_choice", "matrix"]
    mandatory: bool
    readonly: bool
    hidden: bool
    position: int
    choices: tuple[FormChoice, ...]
    shown_when: RoutingExpression | None
    matrix_rows: tuple[FormChoice, ...] = ()
    matrix_columns: tuple[FormChoice, ...] = ()


@dataclass(frozen=True)
class FormDefinition:
    """Immutable form model with source hashes retained as provenance.

    Attributes:
        survey_uid: Stable EUSurvey survey identifier from the archive.
        survey_alias: Human-readable survey alias from the active member.
        source_path: EUS archive or manifest source path used to build the model.
        archive_sha256: SHA-256 checksum of the complete EUS archive.
        active_member_sha256: SHA-256 checksum of the decoded active form member.
        fields_by_uid: Immutable lookup of normalized fields keyed by EUS UID.
    """

    survey_uid: str
    survey_alias: str
    source_path: str
    archive_sha256: str
    active_member_sha256: str
    fields_by_uid: Mapping[str, FormField]


def _class_name(value: Any) -> str:
    """Return a Java or fixture class name for ``value``.

    Args:
        value: A Java serialization object or a test fixture mapping.

    Returns:
        The terminal class name, or an empty string when it is unavailable.
    """
    if isinstance(value, Mapping):
        return str(value.get("class", ""))
    descriptor = getattr(value, "classdesc", None)
    return str(getattr(descriptor, "name", "")).rsplit(".", 1)[-1]


def _value(value: Any, name: str, default: Any = None) -> Any:
    """Read named EUS data from a fixture mapping or Java object.

    Args:
        value: Source fixture mapping or Java object.
        name: Exact EUS field name.
        default: Value returned when the field is absent.

    Returns:
        The EUS field value or ``default``.
    """
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _as_sequence(value: Any) -> tuple[Any, ...]:
    """Convert EUS Java collection-like values to a deterministic tuple.

    Args:
        value: A collection, scalar, or ``None`` from the decoded graph.

    Returns:
        A tuple retaining EUS ordering where available.
    """
    if value is None:
        return ()
    if isinstance(value, Mapping):
        return tuple(value.values())
    if isinstance(value, (str, bytes)):
        return ()
    try:
        return tuple(value)
    except TypeError:
        return ()


def _decode_active_member(data: bytes) -> Any:
    """Decode serialized EUS data without importing Java application classes.

    Args:
        data: The serialized bytes of the archive's active survey member.

    Returns:
        The data graph returned by ``javaobj.v2``.

    Raises:
        FormInputError: If the optional pure-Python decoder is unavailable or
            cannot deserialize the supplied data.
    """
    try:
        decoder = importlib.import_module("javaobj.v2")
    except ModuleNotFoundError as exc:
        raise FormInputError("EUS manifest generation requires javaobj-py3") from exc
    try:
        return decoder.loads(data)
    except Exception as exc:  # javaobj exposes several decoder-specific errors
        raise FormInputError(f"could not decode survey-active.eus: {exc}") from exc


def _choice(value: Any) -> FormChoice:
    """Normalize one EUS possible answer or matrix text element.

    Args:
        value: EUS child element representing a label/value.

    Returns:
        A normalized choice record.

    Raises:
        FormInputError: If a stable UID or label is missing.
    """
    uid = str(_value(value, "uid", ""))
    label = str(_value(value, "title", ""))
    if not uid or not label:
        raise FormInputError("form choice is missing uid or title")
    return FormChoice(uid=uid, label=label, position=int(_value(value, "position", 0)))


def _matrix_axes(value: Any) -> tuple[tuple[FormChoice, ...], tuple[FormChoice, ...]]:
    """Extract labeled matrix rows and columns from an EUS matrix.

    Args:
        value: Decoded EUS matrix instance.

    Returns:
        Ordered row and column label tuples. Empty tuples are valid for forms
        whose matrix labels are not represented as standalone text elements.
    """
    cells = _as_sequence(_value(value, "childElements"))
    # EUSurvey serializes current matrices as one flat row-major list. Older
    # exports can retain nested rows, so normalize both representations.
    flattened = tuple(
        item
        for cell in cells
        for item in (_as_sequence(cell) or (cell,))
    )
    labels = tuple(
        _choice(cell) for cell in flattened
        if _class_name(cell) == "Text" and _value(cell, "uid")
    )
    rows = int(_value(value, "rows", 0))
    columns = int(_value(value, "columns", 0))
    if not labels or rows <= 1 or columns <= 1:
        return (), ()
    # The first cell is an empty corner, then column labels, then row labels.
    # ``rows``/``columns`` include the header row/column in EUSurvey.
    column_count = columns - 1
    row_count = rows - 1
    if len(labels) < column_count + row_count:
        raise FormInputError("matrix child labels do not match declared dimensions")
    return labels[column_count:column_count + row_count], labels[:column_count]


def _field(value: Any) -> FormField | None:
    """Convert a supported EUS question object to normalized metadata.

    Args:
        value: A decoded item from ``Survey.elements``.

    Returns:
        A normalized field, or ``None`` for non-question layout elements.

    Raises:
        FormInputError: If a question type or mandatory identity is unsupported.
    """
    kind = _class_name(value)
    types: dict[str, Literal["free_text", "single_choice", "multi_choice", "matrix"]] = {
        "FreeTextQuestion": "free_text",
        "SingleChoiceQuestion": "single_choice",
        "MultipleChoiceQuestion": "multi_choice",
        "Matrix": "matrix",
    }
    if kind in {"Text", "Section", "EmptyElement"}:
        return None
    if kind not in types:
        raise FormInputError(f"unsupported EUSurvey element class: {kind or type(value).__name__}")
    uid = str(_value(value, "uid", ""))
    title = str(_value(value, "title", ""))
    if not uid or not title:
        raise FormInputError(f"{kind} is missing uid or title")
    choices = tuple(_choice(item) for item in _as_sequence(_value(value, "possibleAnswers")))
    rows, columns = _matrix_axes(value) if kind == "Matrix" else ((), ())
    return FormField(
        uid=uid,
        title=title,
        field_type=types[kind],
        mandatory=not bool(_value(value, "optional", True)),
        readonly=bool(_value(value, "readonly", False)),
        hidden=bool(_value(value, "hidden", False)),
        position=int(_value(value, "position", 0)),
        choices=choices,
        shown_when=None,
        matrix_rows=rows,
        matrix_columns=columns,
    )


def load_active_form(path: str | Path) -> FormDefinition:
    """Decode the active EUSurvey form from a bounded archive.

    Args:
        path: Path to an EUSurvey ``.eus`` ZIP archive.

    Returns:
        Immutable normalized form metadata with EUS provenance hashes.

    Raises:
        FormInputError: If the archive is malformed, unsafe, has no unique
            active member, or contains unsupported form structures.
    """
    source = Path(path)
    try:
        archive_bytes = source.read_bytes()
        with zipfile.ZipFile(source) as archive:
            members = archive.infolist()
            active = [item for item in members if item.filename == "survey-active.eus"]
            if len(members) > _MAX_ARCHIVE_MEMBERS or len(active) != 1:
                raise FormInputError("archive must contain exactly one survey-active.eus member")
            member = active[0]
            if member.file_size > _MAX_ACTIVE_MEMBER_BYTES:
                raise FormInputError("survey-active.eus exceeds the size limit")
            active_bytes = archive.read(member)
    except FormInputError:
        raise
    except (OSError, zipfile.BadZipFile) as exc:
        raise FormInputError(f"could not read EUS archive {source}: {exc}") from exc
    root = _decode_active_member(active_bytes)
    elements = _as_sequence(_value(root, "elements"))
    fields: dict[str, FormField] = {}
    dependencies: dict[str, list[RoutingAtom]] = {}
    parent_logic: dict[str, str] = {}
    for element in elements:
        field = _field(element)
        if field is None:
            continue
        if field.uid in fields:
            raise FormInputError(f"duplicate form field uid: {field.uid}")
        fields[field.uid] = field
        parent_logic[field.uid] = "all" if bool(_value(element, "useAndLogic", False)) else "any"
        for choice in _as_sequence(_value(element, "possibleAnswers")):
            atom = RoutingAtom(parent_uid=field.uid, choice_uid=str(_value(choice, "uid", "")))
            dependency_items = _as_sequence(_value(choice, "dependentElements"))
            if not dependency_items and _value(choice, "dependentElements") is not None:
                dependency_items = (_value(choice, "dependentElements"),)
            for dependency in dependency_items:
                for child in _as_sequence(_value(dependency, "dependentElements")):
                    child_uid = str(_value(child, "uid", ""))
                    if not child_uid:
                        raise FormInputError("dependency target is missing a uid")
                    dependencies.setdefault(child_uid, []).append(atom)
    for child_uid, atoms in dependencies.items():
        if child_uid not in fields:
            raise FormInputError(f"dependency target is not a form question: {child_uid}")
        operators = {parent_logic[atom.parent_uid] for atom in atoms}
        if len(operators) != 1:
            raise FormInputError("dependency target mixes incompatible AND/OR parents")
        fields[child_uid] = replace(
            fields[child_uid], shown_when=RoutingExpression(
                operator=operators.pop(), atoms=tuple(atoms),
            )
        )
    if not fields:
        raise FormInputError("survey-active.eus contains no supported questions")
    return FormDefinition(
        survey_uid=str(_value(root, "uid", "")),
        survey_alias=str(_value(root, "shortname", _value(root, "alias", ""))),
        source_path=str(source),
        archive_sha256=sha256(archive_bytes).hexdigest(),
        active_member_sha256=sha256(active_bytes).hexdigest(),
        fields_by_uid=MappingProxyType(dict(sorted(fields.items()))),
    )


def _field_to_json(field: FormField) -> dict[str, Any]:
    """Serialize one immutable field to JSON-safe stable primitives.

    Args:
        field: Normalized form field.

    Returns:
        A JSON-compatible field mapping.
    """
    result = asdict(field)
    if field.shown_when is not None:
        result["shown_when"] = asdict(field.shown_when)
    return result


def write_form_manifest(form: FormDefinition, output: str | Path) -> None:
    """Write a canonical JSON manifest for normal report execution.

    Args:
        form: Form metadata decoded from the active EUS archive.
        output: Destination JSON path, which is overwritten atomically by the
            caller's staging/publishing workflow.

    Returns:
        ``None`` after a UTF-8, deterministic manifest is written.
    """
    payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generator_version": MANIFEST_GENERATOR_VERSION,
        "survey_uid": form.survey_uid,
        "survey_alias": form.survey_alias,
        "source_path": form.source_path,
        "archive_sha256": form.archive_sha256,
        "active_member_sha256": form.active_member_sha256,
        "fields": [_field_to_json(field) for _, field in sorted(form.fields_by_uid.items())],
    }
    Path(output).write_text(json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _choices(values: list[Mapping[str, Any]]) -> tuple[FormChoice, ...]:
    """Deserialize JSON choice metadata.

    Args:
        values: JSON list containing choice mappings.

    Returns:
        Immutable ordered choice metadata.
    """
    return tuple(FormChoice(uid=str(value["uid"]), label=str(value["label"]), position=int(value["position"])) for value in values)


def load_form_manifest(path: str | Path) -> FormDefinition:
    """Load and validate a generated JSON form manifest without Java decoding.

    Args:
        path: Path to a canonical JSON form manifest.

    Returns:
        Immutable normalized form metadata for report/runtime validation.

    Raises:
        FormInputError: If JSON is invalid, schema-incompatible, or violates
            UID/choice/routing invariants.
    """
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FormInputError(f"could not read form manifest {source}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise FormInputError("form manifest root must be a JSON object")
    if payload.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise FormInputError(f"unsupported manifest schema_version: {payload.get('schema_version')!r}")
    required = ("survey_alias", "archive_sha256", "active_member_sha256", "fields")
    if any(not payload.get(key) for key in required):
        raise FormInputError("form manifest is missing required provenance or field data")
    if "survey_uid" not in payload:
        raise FormInputError("form manifest is missing survey_uid")
    fields: dict[str, FormField] = {}
    try:
        for raw in payload["fields"]:
            routing = raw.get("shown_when")
            shown_when = None if routing is None else RoutingExpression(
                operator=routing["operator"],
                atoms=tuple(RoutingAtom(**atom) for atom in routing["atoms"]),
            )
            field = FormField(
                uid=str(raw["uid"]), title=str(raw["title"]), field_type=raw["field_type"],
                mandatory=bool(raw["mandatory"]), readonly=bool(raw["readonly"]), hidden=bool(raw["hidden"]),
                position=int(raw["position"]), choices=_choices(raw.get("choices", [])),
                shown_when=shown_when, matrix_rows=_choices(raw.get("matrix_rows", [])),
                matrix_columns=_choices(raw.get("matrix_columns", [])),
            )
            if field.uid in fields:
                raise FormInputError(f"duplicate form field uid: {field.uid}")
            if field.field_type not in {"free_text", "single_choice", "multi_choice", "matrix"}:
                raise FormInputError(f"unsupported form field type: {field.field_type}")
            fields[field.uid] = field
    except (KeyError, TypeError, ValueError) as exc:
        raise FormInputError(f"invalid form manifest field: {exc}") from exc
    for field in fields.values():
        if field.shown_when is not None:
            if field.shown_when.operator not in {"all", "any"}:
                raise FormInputError("invalid routing operator")
            for atom in field.shown_when.atoms:
                parent = fields.get(atom.parent_uid)
                if parent is None or atom.choice_uid not in {choice.uid for choice in parent.choices}:
                    raise FormInputError("routing reference does not resolve to a parent choice")
    return FormDefinition(
        survey_uid=str(payload["survey_uid"]), survey_alias=str(payload["survey_alias"]),
        source_path=str(payload.get("source_path", "")), archive_sha256=str(payload["archive_sha256"]),
        active_member_sha256=str(payload["active_member_sha256"]),
        fields_by_uid=MappingProxyType(dict(sorted(fields.items()))),
    )
