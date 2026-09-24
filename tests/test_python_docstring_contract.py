"""Enforce the repository-wide Google-style Python documentation contract."""

import ast
import json
import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = Path(__file__).with_name("fixtures") / "docstring_contract"
BASELINE_PATH = FIXTURE_DIR / "baseline.json"
CONTRACT_FIXTURE_EXEMPTIONS = frozenset(
    {
        Path("tests/fixtures/docstring_contract/invalid_dataclass.py"),
        Path("tests/fixtures/docstring_contract/invalid_return.py"),
        Path("tests/fixtures/docstring_contract/missing_nested.py"),
    }
)
SECTION_PATTERN = re.compile(
    r"^(Args|Returns|Yields|Attributes|Raises):\s*$", re.MULTILINE
)


def tracked_python_paths(repo_root: Path) -> tuple[Path, ...]:
    """Return tracked Python source paths relative to a repository root.

    Args:
        repo_root: Root directory of the Git repository to inspect.

    Returns:
        Repository-relative, lexicographically sorted paths reported by
        ``git ls-files '*.py'``. Untracked files and ignored artifacts are
        excluded.

    Raises:
        subprocess.CalledProcessError: If Git cannot enumerate tracked files
            for ``repo_root``.
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
        docstring: Cleaned docstring text whose headings start at column zero.

    Returns:
        Mapping from supported heading names to their body text. Duplicate
        headings retain the last body because either occurrence satisfies the
        structural contract.
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
        arguments: Parsed AST argument collection for one function definition.

    Returns:
        Argument names in definition order, excluding ``self`` and ``cls``.
        Variadic arguments retain their ``*`` or ``**`` prefix so their
        documentation entry is unambiguous.
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
        section: Body text extracted from a Google-style ``Args:`` or
            ``Attributes:`` section.

    Returns:
        Mapping from each indented entry name to its complete stripped
        description, including any continuation lines.
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


class _DefinitionVisitor(ast.NodeVisitor):
    """Collect documentation-contract violations while retaining AST nesting."""

    def __init__(self, path: str) -> None:
        """Initialize the visitor for one repository-relative source path.

        Args:
            path: Path prefix included in every deterministic diagnostic.
        """
        self._path = path
        self._names: list[str] = []
        self._violations: list[str] = []

    def collect(self, tree: ast.Module) -> list[str]:
        """Visit a module and return the collected contract diagnostics.

        Args:
            tree: Parsed Python module to validate without importing it.

        Returns:
            Unsorted violation diagnostics accumulated during AST traversal.
        """
        self._require_docstring(tree, "<module>")
        self.visit(tree)
        return self._violations

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Validate one class and recursively inspect its nested definitions.

        Args:
            node: Parsed class definition to validate.

        Returns:
            None. Violations are appended to this visitor's diagnostics.
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
        self._names.append(node.name)
        self.generic_visit(node)
        self._names.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Validate one synchronous function and recursively inspect children.

        Args:
            node: Parsed function or method definition to validate.

        Returns:
            None. Violations are appended to this visitor's diagnostics.
        """
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Validate one asynchronous function and recursively inspect children.

        Args:
            node: Parsed asynchronous function or method definition to validate.

        Returns:
            None. Violations are appended to this visitor's diagnostics.
        """
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Apply function documentation rules and preserve qualified-name scope.

        Args:
            node: Parsed synchronous or asynchronous function definition.

        Returns:
            None. Violations are appended and nested definitions are visited.
        """
        qualified_name = self._qualified_name(node.name)
        sections = self._require_docstring(node, qualified_name)
        required_arguments = _argument_names(node.args)
        if required_arguments:
            documented = _documented_entries(sections.get("Args", ""))
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
        if node.name != "__init__":
            if self._is_generator(node):
                if "Yields" not in sections:
                    self._add(node, qualified_name, "generator requires Yields section")
                elif not sections["Yields"].strip():
                    self._add(node, qualified_name, "Yields section requires description")
            elif self._returns_value(node):
                if "Returns" not in sections:
                    self._add(node, qualified_name, "missing Returns section")
                elif not sections["Returns"].strip():
                    self._add(node, qualified_name, "Returns section requires description")
            elif "Returns" not in sections:
                self._add(node, qualified_name, "missing Returns section")
            else:
                if not sections["Returns"].strip():
                    self._add(node, qualified_name, "Returns section requires description")
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
            node: AST definition whose docstring is required.
            qualified_name: Fully qualified diagnostic name for ``node``.

        Returns:
            Parsed supported sections, or an empty mapping when no docstring is
            present.
        """
        docstring = ast.get_docstring(node, clean=True)
        if docstring is None:
            self._add(node, qualified_name, "missing docstring")
            return {}
        return _sections(docstring)

    def _qualified_name(self, name: str) -> str:
        """Return a dot-qualified definition name under the current scope.

        Args:
            name: Name of the immediate AST definition being visited.

        Returns:
            Dot-separated nesting path ending with ``name``.
        """
        return ".".join((*self._names, name))

    def _add(self, node: ast.AST, qualified_name: str, reason: str) -> None:
        """Append one deterministic violation diagnostic.

        Args:
            node: AST node providing the source line number.
            qualified_name: Dot-qualified definition name in the source file.
            reason: Contract requirement that the definition violates.

        Returns:
            None. The diagnostic is appended to the visitor-owned list.
        """
        self._violations.append(
            f"{self._path}:{getattr(node, 'lineno', 1)}:{qualified_name}:{reason}"
        )

    @staticmethod
    def _is_dataclass(node: ast.ClassDef) -> bool:
        """Return whether a class carries a direct dataclass decorator.

        Args:
            node: Parsed class definition whose decorators are inspected.

        Returns:
            ``True`` when a decorator is named ``dataclass`` directly or via a
            module attribute; otherwise ``False``.
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
            node: Parsed dataclass definition whose annotated assignments are
                inspected.

        Returns:
            Names of annotated instance fields, excluding ``ClassVar`` and
            ``KW_ONLY`` pseudo-fields that do not become dataclass fields.
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
            node: Parsed function definition to inspect for yield expressions.

        Returns:
            ``True`` when the function body contains ``yield`` or ``yield from``
            outside a nested function, class, or lambda; otherwise ``False``.
        """
        return _body_contains(node, (ast.Yield, ast.YieldFrom))

    @staticmethod
    def _returns_value(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Return whether a function returns a non-None value in its own body.

        Args:
            node: Parsed function definition to inspect for return statements.

        Returns:
            ``True`` when a non-None return exists outside a nested definition,
            class, or lambda; otherwise ``False``.
        """
        for child in _body_nodes(node):
            if isinstance(child, ast.Return) and child.value is not None:
                if not (isinstance(child.value, ast.Constant) and child.value.value is None):
                    return True
        return False


def _body_nodes(node: ast.AST) -> tuple[ast.AST, ...]:
    """Return descendants of a definition while excluding nested scopes.

    Args:
        node: Function-like AST node whose executable body is traversed.

    Returns:
        Descendant AST nodes from the definition's own scope, excluding nested
        functions, classes, and lambda expressions.
    """
    nodes: list[ast.AST] = []

    def visit_descendant(current: ast.AST) -> None:
        """Accumulate one descendant unless it creates a nested scope.

        Args:
            current: AST descendant being considered during traversal.

        Returns:
            None. Eligible descendants are appended to ``nodes``.
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
        node: Parsed function definition whose own body is searched.
        expected_types: AST expression node types that satisfy the search.

    Returns:
        ``True`` when an eligible descendant has one of ``expected_types``;
        otherwise ``False``.
    """
    return any(isinstance(child, expected_types) for child in _body_nodes(node))


def collect_contract_violations(source: str, path: str) -> list[str]:
    """Return complete-contract violations for every explicit definition in source.

    Args:
        source: Python source text parsed without importing its module.
        path: Repository-relative source path used in deterministic diagnostics.

    Returns:
        Sorted diagnostics identifying each definition and missing contract item.
    """
    tree = ast.parse(source, filename=path)
    return sorted(_DefinitionVisitor(path).collect(tree))


def repository_contract_paths(repo_root: Path) -> tuple[Path, ...]:
    """Return tracked Python paths included in repository contract validation.

    Args:
        repo_root: Root directory of the Git repository to validate.

    Returns:
        Sorted repository-relative Python paths, excluding only intentionally
        invalid parser fixtures named by ``CONTRACT_FIXTURE_EXEMPTIONS``.
    """
    return tuple(
        path for path in tracked_python_paths(repo_root)
        if path not in CONTRACT_FIXTURE_EXEMPTIONS
    )


def repository_contract_violations(repo_root: Path) -> list[str]:
    """Return sorted documentation violations for tracked production and test code.

    Args:
        repo_root: Root directory of the Git repository to validate.

    Returns:
        Sorted violations from every tracked Python file except the intentionally
        invalid parser-corpus fixtures used to prove this validator's behavior.
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


def _fixture_source(name: str) -> str:
    """Return UTF-8 source text from a named documentation-contract fixture.

    Args:
        name: Filename of a fixture stored under the contract fixture directory.

    Returns:
        Complete fixture source text without importing the fixture module.
    """
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_contract_accepts_complete_class_function_and_dataclass_docs() -> None:
    """Verify complete module, class, function, and dataclass contracts pass.

    Returns:
        None. The test fails when valid fixture source produces a violation.
    """
    assert collect_contract_violations(_fixture_source("valid.py"), "valid.py") == []


def test_contract_reports_nested_function_and_implicit_none_procedure() -> None:
    """Verify nested definitions and implicit procedures remain enforceable.

    Returns:
        None. The test fails when required nested or None diagnostics are absent.
    """
    violations = collect_contract_violations(
        _fixture_source("missing_nested.py"), "nested.py"
    )
    assert any("outer.inner:missing docstring" in item for item in violations)
    assert any("outer:missing Returns section" in item for item in violations)


def test_contract_requires_yields_for_generators_and_attributes_for_dataclasses() -> None:
    """Verify generators and generated dataclass fields use dedicated sections.

    Returns:
        None. The test fails when dedicated Yields or Attributes diagnostics are
        absent.
    """
    generator_violations = collect_contract_violations(
        _fixture_source("invalid_return.py"), "generator.py"
    )
    dataclass_violations = collect_contract_violations(
        _fixture_source("invalid_dataclass.py"), "dataclass.py"
    )
    assert any("sample:generator requires Yields section" in item for item in generator_violations)
    assert any(
        "Record:dataclass requires Attributes section" in item
        for item in dataclass_violations
    )


def test_contract_requires_dataclass_field_and_section_entry_descriptions() -> None:
    """Verify dataclass fields and documentation sections need descriptions.

    Returns:
        None. The test fails when empty Args, Attributes, Returns, or Yields
        descriptions are accepted.
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


def test_contract_reports_qualified_nested_class_names_and_positional_only_args() -> None:
    """Verify nested qualified names and positional-only arguments are enforced.

    Returns:
        None. The test fails when nested class scope is omitted from diagnostics
        or a positional-only argument is not treated as documented input.
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
        tmp_path: Pytest-managed directory initialized as an isolated Git repo.

    Returns:
        None. The test fails when discovery includes an untracked source or
        loses sorted repository-relative paths.
    """
    tracked = tmp_path / "tracked.py"
    untracked = tmp_path / "untracked.py"
    tracked.write_text('"""Tracked module."""\n', encoding="utf-8")
    untracked.write_text('"""Untracked module."""\n', encoding="utf-8")
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "tracked.py"], cwd=tmp_path, check=True)

    assert tracked_python_paths(tmp_path) == (Path("tracked.py"),)


def test_repository_fixture_exemptions_retain_valid_source_coverage() -> None:
    """Verify only intentionally invalid parser fixtures bypass repository scans.

    Returns:
        None. The test fails when a valid fixture is accidentally exempted from
        repository-wide contract validation.
    """
    valid_fixture = Path("tests/fixtures/docstring_contract/valid.py")
    invalid_fixture = Path("tests/fixtures/docstring_contract/invalid_return.py")
    assert valid_fixture not in CONTRACT_FIXTURE_EXEMPTIONS
    assert invalid_fixture in CONTRACT_FIXTURE_EXEMPTIONS
    assert valid_fixture in repository_contract_paths(REPO_ROOT)
    assert invalid_fixture not in repository_contract_paths(REPO_ROOT)


def test_tracked_python_files_have_a_documentation_baseline() -> None:
    """Verify tracked source violations equal the temporary remediation baseline.

    Returns:
        None. The test fails when documentation debt changes unexpectedly before
        the final zero-violation gate replaces this baseline.
    """
    violations = repository_contract_violations(REPO_ROOT)
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    assert violations == baseline
