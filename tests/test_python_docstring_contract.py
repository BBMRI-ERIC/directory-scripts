"""Check documentation structure and detectable tautologies, not semantic truth.

Reviewers must compare contracts with implementations; lexical checks cannot
prove ownership, side effects, ordering, or the accuracy of domain terminology.
"""

import ast
import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = Path(__file__).with_name("fixtures") / "docstring_contract"
SHARED_HELPER_PATHS = (
    "ai_cache.py",
    "cli_common.py",
    "directory_session_compat.py",
    "directory_stats_utils.py",
    "nncontacts.py",
    "validation_models.py",
    "validation_helpers.py",
    "warning_suppressions.py",
    "warningscontainer.py",
    "customwarnings.py",
    "fix_proposals.py",
    "fact_descriptor_sync.py",
    "fact_sheet_summary.py",
    "fact_sheet_utils.py",
    "xlsxutils.py",
)
WRITE_TOOL_PATHS = (
    "directory-tables-modifier.py",
    "qcheck-updater.py",
    "collection-factsheet-descriptor-updater.py",
    "warning-suppressions-manage.py",
    "importer-ecrin-mdr.py",
    "sync_directory_with_fdp.py",
    "eosc-organisation-matcher.py",
)
QC_HELPER_PATHS = (
    "check_fix_helpers.py",
    "contact_assignment_utils.py",
    "text_consistency.py",
)
ANALYTICS_HELPER_PATHS = (
    "geojsonutils.py",
    "geocoding_2022.py",
    "pddfutils.py",
    "oomutils.py",
    "orphacodes.py",
    "icd10codeshelper.py",
    "k_anonymity.py",
)
SECTION_PATTERN = re.compile(
    r"^(Args|Returns|Yields|Attributes|Raises):\s*$", re.MULTILINE
)
GENERIC_DOCUMENTATION_PATTERN = re.compile(
    r"(?:"
    r"used to configure|"
    r"configured fixture or response value|"
    r"the value produced by|"
    r"test or helper performs setup or assertions without returning a value|"
    r"provide the .+ fixture required by this test|"
    r"the value returned by `[^`]+` for this test case|"
    r"supplied to `[^`]+` for the documented test case|"
    r"passed to `[^`]+` to select its configured response|"
    r"the result returned by `[^`]+` for the controlled inputs|"
    r"return the configured .+ from this test double|"
    r"the configured .+ value held by this test double|"
    r"whether the configured .+ condition is true|"
    r"keyword options accepted when configuring this test helper|"
    r"filesystem location used by this test scenario|"
    r"pytest fixture used to replace dependencies for this scenario|"
    r"test data supplied to exercise the configured scenario|"
    r"expected result against which this scenario is asserted|"
    r"boolean scope control varied by this test scenario"
    r")",
    re.IGNORECASE,
)
# Grammatical and programming scaffolding conveys no domain contract by itself.
# Unlike the historical phrase detector, this is independent of word order and
# quoted identifiers. It is a lint heuristic, not a semantic proof.
DOCUMENTATION_SCAFFOLDING = frozenset("""
a an the of from to in on at for by with and or its this that these those as
is are be being been it their into which whose used use using provided provide
input inputs output outputs argument arguments parameter parameters value values
result results object objects tuple tuples list lists mapping mappings dictionary
dict set sets sequence sequences collection collections field fields attribute
attributes path paths filesystem location locations identifier identifiers name
names function functions method methods helper helpers test tests fixture fixtures
constructed construct assembled assemble emitted emit consumed consume collected
collect returned return read written write produced produce passed pass supplied
supply expected configured controlled requested selected accepted retained given
ordered sorted literal concrete actual data item items called call calls self cls
""".split())


def tracked_python_paths(repo_root: Path) -> tuple[Path, ...]:
    """Return tracked Python source paths relative to a repository root.

    Args:
        repo_root: Repository root whose tracked files are inspected by the contract helper.

    Returns:
        Lexicographically sorted relative Path objects from the Git index;
        untracked Python files are excluded.
    """
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--", "*.py"],
        check=True,
        capture_output=True,
        encoding="utf-8",
        text=True,
    )
    return tuple(sorted(Path(line) for line in completed.stdout.splitlines() if line))


def _sections(docstring: str) -> dict[str, str]:
    """Return Google-style documentation sections from a cleaned docstring.

    Args:
        docstring: Cleaned Google-style docstring split into documentation sections.

    Returns:
        Section names mapped to their raw bodies with trailing whitespace removed;
        repeated headings keep only the last body.
    """
    matches = list(SECTION_PATTERN.finditer(docstring))
    return {
        match.group(1): docstring[match.end(): matches[index + 1].start()
        if index + 1 < len(matches) else len(docstring)].rstrip()
        for index, match in enumerate(matches)
    }


def _argument_names(arguments: ast.arguments) -> tuple[str, ...]:
    """Return documented argument names required by a function definition.

    Args:
        arguments: Parsed function signature used to enumerate documented parameters.

    Returns:
        Parameter names in positional, keyword-only, vararg, then kwarg order;
        variadics retain star prefixes and self/cls are omitted.
    """
    names = [argument.arg for argument in (*arguments.posonlyargs, *arguments.args)]
    names.extend(argument.arg for argument in arguments.kwonlyargs)
    if arguments.vararg is not None:
        names.append("*" + arguments.vararg.arg)
    if arguments.kwarg is not None:
        names.append("**" + arguments.kwarg.arg)
    return tuple(name for name in names if name not in {"self", "cls"})


def _documented_entries(section: str) -> dict[str, str]:
    """Return named entries and descriptions declared in a section.

    Args:
        section: Single Google-style section parsed into named entries.

    Returns:
        Entry names mapped to stripped descriptions including continuation lines;
        optional parenthesized type annotations are omitted from the keys.
    """
    matches = list(
        re.finditer(
            r"^[ \t]+(?P<name>\*{0,2}[A-Za-z_]\w*)"
            r"(?:[ \t]+\([^\n)]*\))?[ \t]*:[ \t]*(?P<description>[^\n]*)$",
            section,
            re.MULTILINE,
        )
    )
    return {
        match.group("name"): section[
            match.start("description"):
            matches[index + 1].start() if index + 1 < len(matches) else len(section)
        ].strip()
        for index, match in enumerate(matches)
    }


def _has_summary_text(docstring: str) -> bool:
    """Return whether a docstring starts with non-section summary prose.

    Args:
        docstring: Cleaned documentation text whose first meaningful line is inspected.

    Returns:
        Whether the text starts with a substantive summary instead of a section heading.
    """
    for line in docstring.splitlines():
        summary = line.strip()
        if summary:
            return not SECTION_PATTERN.fullmatch(summary)
    return False


def _uses_generic_boilerplate(text: str, identifiers: tuple[str, ...] = ()) -> bool:
    """Detect stock phrases or prose containing only identifiers and scaffolding.

    Args:
        text: Summary or section description inspected without executing its source.
        identifiers: Signature or field names whose bare repetition is not a
            description; these are derived from the inspected AST, not a blacklist.

    Returns:
        True for a known stock phrase or nonempty prose with no words beyond
        programming scaffolding after removing quoted identifiers. False does
        not certify semantic accuracy; reviewers must still read the implementation.
    """
    if GENERIC_DOCUMENTATION_PATTERN.search(text):
        return True
    prose = re.sub(r"(`+)([A-Za-z_]\w*(?:\.\w+)*)\1", "", text)
    for identifier in identifiers:
        prose = re.sub(rf"\b{re.escape(identifier.lstrip('*'))}\b", "", prose)
    words = set(re.findall(r"[A-Za-z0-9]+", prose.lower()))
    return bool(text.strip()) and not (words - DOCUMENTATION_SCAFFOLDING)


class _DefinitionVisitor(ast.NodeVisitor):
    """Collect documentation-contract violations while retaining AST nesting.
    """

    def __init__(self, path: str) -> None:
        """Initialize the visitor for one repository-relative source path.

        Args:
            path: Repository-relative source filename prefixed to every diagnostic;
                this visitor does not open the file.
        """
        self._path = path
        self._names: list[str] = []
        self._violations: list[str] = []

    def collect(self, tree: ast.Module) -> list[str]:
        """Visit a module and return the collected contract diagnostics.

        Args:
            tree: Parsed module tree traversed by the documentation-contract visitor.

        Returns:
            Accumulated path:line:qualified-name:reason diagnostics in traversal
            order. The returned list is the visitor's mutable internal list.
        """
        self._require_docstring(tree, "<module>")
        self.visit(tree)
        return self._violations

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Validate one class and recursively inspect its nested definitions.

        Args:
            node: AST node inspected by the documentation-contract visitor.

        Returns:
            None. Validate one class and recursively inspect its nested definitions.
        """
        qualified_name = self._qualified_name(node.name)
        sections = self._require_docstring(node, qualified_name)
        if self._is_dataclass(node):
            documented = _documented_entries(sections.get("Attributes", ""))
            if "Attributes" not in sections:
                self._add(node, qualified_name, "dataclass requires Attributes section")
            for field_name in self._dataclass_field_names(node):
                if field_name not in documented:
                    self._add(
                        node,
                        qualified_name,
                        f"missing Attributes entry {field_name}",
                    )
                elif not documented[field_name]:
                    self._add(
                        node,
                        qualified_name,
                        f"Attributes entry {field_name} requires description",
                    )
                elif _uses_generic_boilerplate(documented[field_name], (node.name, field_name)):
                    self._add(
                        node,
                        qualified_name,
                        f"Attributes entry {field_name} uses generic boilerplate",
                    )
        self._names.append(node.name)
        self.generic_visit(node)
        self._names.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Validate one synchronous function and recursively inspect children.

        Args:
            node: AST node inspected by the documentation-contract visitor.

        Returns:
            None. Validate one synchronous function and recursively inspect children.
        """
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Validate one asynchronous function and recursively inspect children.

        Args:
            node: AST node inspected by the documentation-contract visitor.

        Returns:
            None. Validate one asynchronous function and recursively inspect children.
        """
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Apply function documentation rules and preserve qualified-name scope.

        Args:
            node: AST node inspected by the documentation-contract visitor.

        Returns:
            None. Apply function documentation rules and preserve qualified-name scope.
        """
        qualified_name = self._qualified_name(node.name)
        sections = self._require_docstring(node, qualified_name)
        required_arguments = _argument_names(node.args)
        if required_arguments:
            documented = _documented_entries(sections.get("Args", ""))
            # Older repository contracts spell variadics without their stars.
            # Preserve that valid spelling without changing existing SO2 tests.
            for argument in required_arguments:
                if argument.startswith("*") and argument not in documented:
                    bare_name = argument.lstrip("*")
                    if bare_name in documented:
                        documented[argument] = documented[bare_name]
            if "Args" not in sections:
                self._add(node, qualified_name, "missing Args section")
            for argument in required_arguments:
                if argument not in documented:
                    self._add(node, qualified_name, f"missing Args entry {argument}")
                elif not documented[argument]:
                    self._add(
                        node,
                        qualified_name,
                        f"Args entry {argument} requires description",
                    )
                elif _uses_generic_boilerplate(documented[argument], (node.name, argument)):
                    self._add(
                        node,
                        qualified_name,
                        f"Args entry {argument} uses generic boilerplate",
                    )
        if node.name != "__init__":
            if self._is_generator(node):
                if "Yields" not in sections:
                    self._add(node, qualified_name, "generator requires Yields section")
                elif not sections["Yields"].strip():
                    self._add(node, qualified_name, "Yields section requires description")
                elif _uses_generic_boilerplate(sections["Yields"], (node.name,)):
                    self._add(node, qualified_name, "Yields section uses generic boilerplate")
            elif self._returns_value(node):
                if "Returns" not in sections:
                    self._add(node, qualified_name, "missing Returns section")
                elif not sections["Returns"].strip():
                    self._add(node, qualified_name, "Returns section requires description")
                elif _uses_generic_boilerplate(sections["Returns"], (node.name,)):
                    self._add(node, qualified_name, "Returns section uses generic boilerplate")
            elif "Returns" not in sections:
                self._add(node, qualified_name, "missing Returns section")
            else:
                if not sections["Returns"].strip():
                    self._add(node, qualified_name, "Returns section requires description")
                elif _uses_generic_boilerplate(sections["Returns"], (node.name,)):
                    self._add(node, qualified_name, "Returns section uses generic boilerplate")
                if not re.search(r"\bNone\b", sections["Returns"]):
                    self._add(node, qualified_name, "Returns section must state None")
        self._names.append(node.name)
        self.generic_visit(node)
        self._names.pop()

    def _require_docstring(
        self, node: ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        qualified_name: str,
    ) -> dict[str, str]:
        """Return parsed sections and record a missing-docstring violation.

        Args:
            node: AST node inspected by the documentation-contract visitor.
            qualified_name: Qualified definition name included in a contract diagnostic.

        Returns:
            Google-style section bodies keyed by heading, or an empty mapping
            if documentation is absent. Violations are also appended to the visitor.
        """
        docstring = ast.get_docstring(node, clean=True)
        if docstring is None:
            self._add(node, qualified_name, "missing docstring")
            return {}
        if not _has_summary_text(docstring):
            self._add(node, qualified_name, "docstring requires summary text")
        if _uses_generic_boilerplate(docstring):
            self._add(node, qualified_name, "docstring uses generic boilerplate")
        return _sections(docstring)

    def _qualified_name(self, name: str) -> str:
        """Return a dot-qualified definition name under the current scope.

        Args:
            name: Definition name appended to the current AST traversal scope.

        Returns:
            The dot-qualified name assembled from the active AST scope and definition name.
        """
        return ".".join((*self._names, name))

    def _add(self, node: ast.AST, qualified_name: str, reason: str) -> None:
        """Append one deterministic violation diagnostic.

        Args:
            node: AST node inspected by the documentation-contract visitor.
            qualified_name: Qualified definition name included in a contract diagnostic.
            reason: Specific contract failure reason appended to a diagnostic.

        Returns:
            None. Append one deterministic violation diagnostic.
        """
        self._violations.append(
            f"{self._path}:{getattr(node, 'lineno', 1)}:{qualified_name}:{reason}"
        )

    @staticmethod
    def _is_dataclass(node: ast.ClassDef) -> bool:
        """Return whether a class carries a direct dataclass decorator.

        Args:
            node: AST node inspected by the documentation-contract visitor.

        Returns:
            True for a decorator named dataclass, including qualified names and
            decorator calls; aliases under other names are not resolved.
        """
        for decorator in node.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            if isinstance(target, ast.Name) and target.id == "dataclass":
                return True
            if isinstance(target, ast.Attribute) and target.attr == "dataclass":
                return True
        return False

    @staticmethod
    def _dataclass_field_names(node: ast.ClassDef) -> tuple[str, ...]:
        """Return concrete generated dataclass field names in source order.

        Args:
            node: AST node inspected by the documentation-contract visitor.

        Returns:
            Annotated simple-name fields in source order, excluding ClassVar
            and KW_ONLY declarations. Inherited fields are not inspected.
        """
        fields: list[str] = []
        for statement in node.body:
            if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                continue
            annotation = statement.annotation
            if isinstance(annotation, ast.Subscript):
                annotation = annotation.value
            annotation_name = (
                annotation.id
                if isinstance(annotation, ast.Name)
                else annotation.attr if isinstance(annotation, ast.Attribute) else None
            )
            if annotation_name not in {"ClassVar", "KW_ONLY"}:
                fields.append(statement.target.id)
        return tuple(fields)

    @staticmethod
    def _is_generator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Return whether a function yields outside nested definitions.

        Args:
            node: AST node inspected by the documentation-contract visitor.

        Returns:
            Whether the function body contains a yield node outside nested definitions.
        """
        return _body_contains(node, (ast.Yield, ast.YieldFrom))

    @staticmethod
    def _returns_value(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Return whether a function returns a non-None value in its own body.

        Args:
            node: AST node inspected by the documentation-contract visitor.

        Returns:
            True if a return expression other than literal None occurs outside
            nested scopes, even if that expression could evaluate to None at runtime.
        """
        for child in _body_nodes(node):
            if isinstance(child, ast.Return) and child.value is not None:
                if not (isinstance(child.value, ast.Constant) and child.value.value is None):
                    return True
        return False


def _body_nodes(node: ast.AST) -> tuple[ast.AST, ...]:
    """Return descendants of a definition while excluding nested scopes.

    Args:
        node: AST definition or syntax node inspected by the traversal helper.

    Returns:
        Descendants in depth-first AST order, omitting nested function, class,
        and lambda nodes and their subtrees; the root itself is excluded.
    """
    nodes: list[ast.AST] = []

    def visit_descendant(current: ast.AST) -> None:
        """Accumulate one descendant unless it creates a nested scope.

        Args:
            current: Current descendant visited while collecting nodes outside nested scopes.

        Returns:
            None. Accumulate one descendant unless it creates a nested scope.
        """
        if current is not node and isinstance(
            current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            return
        nodes.append(current)
        for child in ast.iter_child_nodes(current):
            visit_descendant(child)

    for child in ast.iter_child_nodes(node):
        visit_descendant(child)
    return tuple(nodes)


def _body_contains(
    node: ast.FunctionDef | ast.AsyncFunctionDef, expected_types: tuple[type[ast.AST], ...]
) -> bool:
    """Return whether a function body contains an AST node of expected types.

    Args:
        node: AST definition or syntax node inspected by the traversal helper.
        expected_types: AST node classes to search for, such as Yield and YieldFrom.

    Returns:
        Whether any traversed AST node matches the requested node types.
    """
    return any(isinstance(child, expected_types) for child in _body_nodes(node))


def collect_contract_violations(source: str, path: str) -> list[str]:
    """Return complete-contract violations for every explicit definition in source.

    Args:
        source: Complete Python source text parsed without importing or executing it.
        path: Diagnostic filename passed to the parser; no filesystem access occurs.

    Returns:
        The deterministically sorted contract-diagnostic sequence.
    """
    tree = ast.parse(source, filename=path)
    return sorted(_DefinitionVisitor(path).collect(tree))


def repository_contract_paths(repo_root: Path) -> tuple[Path, ...]:
    """Return every tracked Python path included in contract validation.

    Args:
        repo_root: Repository root whose tracked files are inspected by the contract helper.

    Returns:
        The sorted tracked Python paths selected for repository-wide validation.
    """
    return tracked_python_paths(repo_root)


def repository_contract_violations(repo_root: Path) -> list[str]:
    """Return sorted documentation violations for tracked production and test code.

    Args:
        repo_root: Repository root whose tracked files are inspected by the contract helper.

    Returns:
        The deterministically sorted contract-diagnostic sequence.
    """
    violations: list[str] = []
    for relative_path in repository_contract_paths(repo_root):
        violations.extend(
            collect_contract_violations(
                (repo_root / relative_path).read_text(encoding="utf-8"),
                relative_path.as_posix(),
            )
        )
    return sorted(violations)


def violations_for_path(path: Path) -> list[str]:
    """Return contract diagnostics for one tracked Python file.

    Args:
        path: Absolute Python source path inside REPO_ROOT, read as UTF-8;
            paths outside the repository raise ValueError.

    Returns:
        The diagnostics produced for the requested source text.
    """
    try:
        relative_path = path.relative_to(REPO_ROOT)
    except ValueError as error:
        raise ValueError(f"Path is outside repository root: {path}") from error
    return collect_contract_violations(
        path.read_text(encoding="utf-8"), relative_path.as_posix()
    )


def _fixture_source(name: str) -> str:
    """Return UTF-8 source text from a named documentation-contract fixture.

    Args:
        name: Filename under tests/fixtures/docstring_contract, including its suffix.

    Returns:
        The UTF-8 source text loaded from the named documentation-contract fixture.
    """
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_contract_accepts_complete_class_function_and_dataclass_docs() -> None:
    """Verify complete module, class, function, and dataclass contracts pass.

    Returns:
        None. Verifies complete module, class, function, and dataclass contracts pass.
    """
    assert collect_contract_violations(_fixture_source("valid.py"), "valid.py") == []


def test_contract_reports_nested_function_and_implicit_none_procedure() -> None:
    """Verify nested definitions and implicit procedures remain enforceable.

    Returns:
        None. Verifies nested definitions and implicit procedures remain enforceable.
    """
    violations = collect_contract_violations(
        _fixture_source("missing_nested.txt"), "nested.py"
    )
    assert any("outer.inner:missing docstring" in item for item in violations)
    assert any("outer:missing Returns section" in item for item in violations)


def test_contract_requires_yields_for_generators_and_attributes_for_dataclasses() -> None:
    """Verify generators and generated dataclass fields use dedicated sections.

    Returns:
        None. Verifies generators and generated dataclass fields use dedicated sections.
    """
    generator_violations = collect_contract_violations(
        _fixture_source("invalid_return.txt"), "generator.py"
    )
    dataclass_violations = collect_contract_violations(
        _fixture_source("invalid_dataclass.txt"), "dataclass.py"
    )
    assert any("sample:generator requires Yields section" in item for item in generator_violations)
    assert any(
        "Record:dataclass requires Attributes section" in item
        for item in dataclass_violations
    )


def test_contract_requires_dataclass_field_and_section_entry_descriptions() -> None:
    """Verify dataclass fields and documentation sections need descriptions.

    Returns:
        None. Verifies dataclass fields and documentation sections need descriptions.
    """
    source = '''"""Provide incomplete section descriptions."""

from dataclasses import dataclass
from typing import ClassVar


@dataclass
class Record:
    """Represent a record with incomplete field documentation.

    Attributes:
        name:
        code: Stable record code.
    """

    name: str
    code: str
    category: ClassVar[str] = "shared"


def value(argument: str) -> str:
    """Return an argument with incomplete documentation.

    Args:
        argument:

    Returns:
    """
    return argument


def values():
    """Yield one value with incomplete documentation.

    Yields:
    """
    yield "value"
'''
    violations = collect_contract_violations(source, "descriptions.py")
    assert any("Record:Attributes entry name requires description" in item for item in violations)
    assert not any("Record:missing Attributes entry category" in item for item in violations)
    assert any("value:Args entry argument requires description" in item for item in violations)
    assert any("value:Returns section requires description" in item for item in violations)
    assert any("values:Yields section requires description" in item for item in violations)


def test_contract_rejects_empty_summaries_and_generic_section_boilerplate() -> None:
    """Verify structural documentation cannot replace implementation-specific semantics.

    Returns:
        None. The assertions only inspect documentation-contract diagnostics.
    """
    source = '''""""""


class EmptySummary:
    """"""


def no_summary(argument: str) -> str:
    """Args:
        argument: Concrete argument description.

    Returns:
        The supplied argument.
    """
    return argument


def sample(argument: str, location: str) -> str:
    """Return a value.

    Args:
        argument: Value used to configure the sample scenario.
        location: Filesystem location used by this test scenario.

    Returns:
        Configured fixture or response value consumed by the enclosing test scenario.
    """
    return argument + location
'''
    violations = collect_contract_violations(source, "generic.py")
    assert any("<module>:docstring requires summary text" in item for item in violations)
    assert any("EmptySummary:docstring requires summary text" in item for item in violations)
    assert any("no_summary:docstring requires summary text" in item for item in violations)
    assert any("sample:Args entry argument uses generic boilerplate" in item for item in violations)
    assert any("sample:Args entry location uses generic boilerplate" in item for item in violations)
    assert any("sample:Returns section uses generic boilerplate" in item for item in violations)


def test_contract_rejects_generated_lookup_and_return_templates() -> None:
    """Verify generated lookup and return templates cannot satisfy the contract.

    Returns:
        None. The assertions require diagnostics for both rejected template families.
    """
    source = '''"""Provide source containing generated documentation templates."""


def lookup(entity_id: str) -> str:
    """Return the configured lookup value from this test double.

    Args:
        entity_id: Identifier passed to `lookup` to select its configured response.

    Returns:
        The result returned by `lookup` for the controlled inputs.
    """
    return entity_id
'''
    violations = collect_contract_violations(source, "generated.py")
    assert any("lookup:docstring uses generic boilerplate" in item for item in violations)
    assert any("lookup:Args entry entity_id uses generic boilerplate" in item for item in violations)
    assert any("lookup:Returns section uses generic boilerplate" in item for item in violations)


def test_contract_rejects_identifier_only_descriptions_without_phrase_blacklist() -> None:
    """Reject renamed and reordered scaffolding even when no banned phrase matches.

    Returns:
        None. Both argument and return descriptions must add meaning beyond identifiers.
    """
    for name in ("lookup", "fetch_organisations", "unseen_operation"):
        source = f'''"""Exercise meaningless documentation with varying identifiers."""

def {name}(location):
    """Load institutional membership data.

    Args:
        location: For `{name}`, the input filesystem path.

    Returns:
        From `{name}`, the constructed ordered tuple of values.
    """
    return (location,)
'''
        assert not GENERIC_DOCUMENTATION_PATTERN.search(source)
        violations = collect_contract_violations(source, "renamed.py")
        assert any("Args entry location uses generic boilerplate" in item for item in violations)
        assert any("Returns section uses generic boilerplate" in item for item in violations)


def test_contract_accepts_concrete_path_tuple_and_variadic_semantics() -> None:
    """Accept domain contracts and both conventional spellings of variadic names.

    Returns:
        None. Specific contents, ordering, and variadic roles must pass without exemptions.
    """
    for prefix in ("", "*"):
        source = f'''"""Parse institutional membership data."""

def load(location, *columns):
    """Select institution names from a membership workbook.

    Args:
        location: Existing membership XLSX file opened read-only.
        {prefix}columns: Candidate institution-name headers, in preference order.

    Returns:
        Tuple of institution names sorted alphabetically, retaining duplicates.
    """
    return (location, columns)
'''
        assert collect_contract_violations(source, "specific.py") == []


def test_contract_rejects_bare_signature_repetition_for_arbitrary_names() -> None:
    """Derive tautology detection from signatures, not known identifier spellings.

    Returns:
        None. Unquoted names alone must fail for arguments, returns, and dataclass fields.
    """
    for name in ("zebra_namespace", "institution_membership", "otherwise_unknown"):
        source = f'''"""Inspect signature-derived tautologies."""
from dataclasses import dataclass

@dataclass
class Record:
    """Represent institutional membership.

    Attributes:
        {name}: {name}.
    """
    {name}: str

def lookup_{name}({name}):
    """Resolve institution membership.

    Args:
        {name}: {name}.

    Returns:
        lookup_{name}.
    """
    return {name}
'''
        violations = collect_contract_violations(source, "signature.py")
        assert any(f"Args entry {name} uses generic boilerplate" in item for item in violations)
        assert any("Returns section uses generic boilerplate" in item for item in violations)
        assert any(f"Attributes entry {name} uses generic boilerplate" in item for item in violations)


def test_contract_reports_qualified_nested_class_names_and_positional_only_args() -> None:
    """Verify nested qualified names and positional-only arguments are enforced.

    Returns:
        None. Verifies nested qualified names and positional-only arguments are enforced.
    """
    source = '''"""Provide nested definitions for qualified-name tests."""


class Container:
    """Contain nested documented and undocumented helpers."""

    def outer(self, positional, /, ordinary):
        """Call an undocumented nested helper.

        Args:
            ordinary: Ordinary input value.

        Returns:
            None. This procedure only invokes the nested helper.
        """
        def inner() -> None:
            pass

        inner()
        del positional, ordinary
'''
    violations = collect_contract_violations(source, "qualified.py")
    assert any(
        "Container.outer.inner:missing docstring" in item for item in violations
    )
    assert any(
        "Container.outer:missing Args entry positional" in item for item in violations
    )


def test_tracked_python_paths_are_git_indexed_and_sorted(tmp_path: Path) -> None:
    """Verify discovery reads only indexed Python paths in a temporary repository.

    Args:
        tmp_path: Pytest-managed temporary filesystem directory for this test case.

    Returns:
        None. Verifies discovery reads only indexed Python paths in a temporary repository.
    """
    tracked = tmp_path / "tracked.py"
    untracked = tmp_path / "untracked.py"
    tracked.write_text('"""Tracked module."""\n', encoding="utf-8")
    untracked.write_text('"""Untracked module."""\n', encoding="utf-8")
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "tracked.py"], cwd=tmp_path, check=True)

    assert tracked_python_paths(tmp_path) == (Path("tracked.py"),)


def test_repository_contract_paths_exempt_no_tracked_python_file() -> None:
    """Verify parser fixtures use non-Python files instead of exemptions.

    Returns:
        None. Verifies parser fixtures use non-Python files instead of exemptions.
    """
    assert repository_contract_paths(REPO_ROOT) == tracked_python_paths(REPO_ROOT)


def test_directory_contract_has_no_violations() -> None:
    """Verify the shared Directory API meets the strict documentation contract.

    Returns:
        None. Verifies the shared Directory API meets the strict documentation contract.
    """
    assert violations_for_path(REPO_ROOT / "directory.py") == []


def test_shared_helpers_have_no_contract_violations() -> None:
    """Verify all Task 2 shared helpers meet the strict documentation contract.

    Returns:
        None. Verifies all Task 2 shared helpers meet the strict documentation contract.
    """
    paths = [REPO_ROOT / name for name in SHARED_HELPER_PATHS]
    assert {path.name: violations_for_path(path) for path in paths} == {
        path.name: [] for path in paths
    }


def test_write_capable_tools_have_no_contract_violations() -> None:
    """Verify Task 3 maintenance CLIs have complete explicit contracts.

    Returns:
        None. Verifies Task 3 maintenance CLIs have complete explicit contracts.
    """
    paths = [REPO_ROOT / name for name in WRITE_TOOL_PATHS]
    assert {path.name: violations_for_path(path) for path in paths} == {
        path.name: [] for path in paths
    }


def test_qc_plugins_and_check_helpers_have_no_contract_violations() -> None:
    """Verify Task 4 quality-check code has complete explicit contracts.

    Returns:
        None. Verifies Task 4 quality-check code has complete explicit contracts.
    """
    paths = sorted((REPO_ROOT / "checks").glob("*.py"))
    paths.extend(REPO_ROOT / name for name in QC_HELPER_PATHS)
    assert {path.relative_to(REPO_ROOT).as_posix(): violations_for_path(path)
            for path in paths} == {
        path.relative_to(REPO_ROOT).as_posix(): [] for path in paths
    }


def test_all_tracked_production_python_files_have_complete_contracts() -> None:
    """Verify every tracked non-test Python definition has a full contract.

    Returns:
        None. Verifies every tracked non-test Python definition has a full contract.
    """
    paths = tuple(
        path for path in repository_contract_paths(REPO_ROOT)
        if not path.parts[0] == "tests"
    )
    violations: list[str] = []
    for path in paths:
        violations.extend(
            collect_contract_violations(
                (REPO_ROOT / path).read_text(encoding="utf-8"), path.as_posix()
            )
        )
    assert sorted(violations) == []


def test_exporters_and_map_helpers_have_no_contract_violations() -> None:
    """Verify Task 5 exporters and transformations meet the documentation contract.

    Returns:
        None. Verifies Task 5 exporters and transformations meet the documentation contract.
    """
    paths = sorted(REPO_ROOT.glob("exporter-*.py"))
    paths.extend(sorted((REPO_ROOT / "R-maps").glob("*.py")))
    paths.extend(REPO_ROOT / name for name in ANALYTICS_HELPER_PATHS)
    assert {path.relative_to(REPO_ROOT).as_posix(): violations_for_path(path)
            for path in paths} == {
        path.relative_to(REPO_ROOT).as_posix(): [] for path in paths
    }


def test_every_tracked_python_definition_has_a_complete_contract() -> None:
    """Verify every tracked Python definition meets the complete contract.

    Returns:
        None. Verifies every tracked Python definition meets the complete contract.
    """
    assert repository_contract_violations(REPO_ROOT) == []
