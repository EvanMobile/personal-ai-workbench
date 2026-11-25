"""R3.4.2: automated module dependency boundary checks (test-only)."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]

# Current production roots.  M03 is intentionally absent: it is not implemented
# in M1-A, and M02 ``knowledge`` must not be relabeled as M03.
MODULE_ROOTS: dict[str, tuple[str, ...]] = {
    "M01": ("app.api.v1.rag",),
    "M02": (
        "app.modules.knowledge",
        "app.modules.capture",
        "app.modules.dossier",
        "app.modules.page",
        "app.modules.artifact",
    ),
    "M05": ("app.modules.execution",),
    "M06": ("app.modules.evaluation",),
    "M03": (),
}

# Reserved future namespace for M03 RAG & Agent Harness.  No source is scanned
# today; this only makes the future rule explicit and prevents premature
# dependencies from being introduced unnoticed.
M03_FUTURE_ROOTS = (
    "app.modules.rag",
    "app.modules.harness",
    "app.modules.dataset",
)

M03_FUTURE_CONSTRAINTS = {
    "M03_MUST_NOT_IMPORT_M05": "Future M03 must not depend on M05 implementation.",
    "M03_MUST_NOT_IMPORT_M06": "Future M03 must not depend on M06 implementation.",
}

M03_EXEMPT_EXISTING = ()


@dataclass(frozen=True)
class Rule:
    code: str
    source_module: str
    target_module: str
    forbidden_prefixes: tuple[str, ...]
    allowed_prefixes: tuple[str, ...]
    reason: str
    allowed_exact: tuple[str, ...] = ()
    allowed_targets: tuple[str, ...] = ()


RULES: tuple[Rule, ...] = (
    Rule(
        "M01_ROUTER_MUST_NOT_IMPORT_M05_INTERNAL",
        "M01",
        "M05",
        ("app.modules.execution",),
        ("app.modules.execution.errors",),
        "M01 Router must access execution capabilities through M06 Facade.",
        (),
    ),
    Rule(
        "M01_ROUTER_MUST_NOT_IMPORT_M06_INTERNAL",
        "M01",
        "M06",
        ("app.modules.evaluation",),
        (
            "app.modules.evaluation.facades",
            "app.modules.evaluation.read_models",
            "app.modules.evaluation.errors",
        ),
        "M01 Router must not bypass M06 Facade or import M06 handlers/ORM.",
        (),
    ),
    Rule(
        "M01_ROUTER_MUST_NOT_IMPORT_FUTURE_M03",
        "M01",
        "M03",
        M03_FUTURE_ROOTS,
        (),
        "M01 must not pre-depend on the future M03 implementation.",
        (),
    ),
    Rule(
        "M06_MUST_NOT_IMPORT_M05_ORM",
        "M06",
        "M05",
        ("app.modules.execution",),
        (
            "app.modules.execution.service",
            "app.modules.execution.read_models",
            "app.modules.execution.runtime",
            "app.modules.execution.errors",
            "app.modules.execution.results",
        ),
        "M06 may use only M05 public Service/Read Models/Runtime APIs.",
        (),
        (
            "app.modules.execution.worker.JobContext",
        ),
    ),
    Rule(
        "M06_MUST_NOT_IMPORT_M01",
        "M06",
        "M01",
        ("app.api.v1.rag",),
        (),
        "M06 must not reverse-depend on the M01 API layer.",
    ),
    Rule(
        "M06_MUST_NOT_IMPORT_FUTURE_M03_INTERNAL",
        "M06",
        "M03",
        M03_FUTURE_ROOTS,
        (),
        "M06 must use a future M03 public API, not its internal implementation.",
    ),
    Rule(
        "M05_MUST_NOT_IMPORT_M06",
        "M05",
        "M06",
        ("app.modules.evaluation",),
        (),
        "M05 Execution must remain independent of M06 evaluation business logic.",
    ),
    Rule(
        "M05_MUST_NOT_IMPORT_M02",
        "M05",
        "M02",
        (
            "app.modules.knowledge",
            "app.modules.capture",
            "app.modules.dossier",
            "app.modules.page",
            "app.modules.artifact",
        ),
        (),
        "M05 must not depend on Personal Knowledge business modules.",
    ),
    Rule(
        "M05_MUST_NOT_IMPORT_M01",
        "M05",
        "M01",
        ("app.api.v1.rag",),
        (),
        "M05 must not reverse-depend on the M01 API layer.",
    ),
    Rule(
        "M05_MUST_NOT_IMPORT_FUTURE_M03",
        "M05",
        "M03",
        M03_FUTURE_ROOTS,
        (),
        "M05 must remain business-neutral and not pre-depend on M03.",
    ),
    Rule(
        "M02_MUST_NOT_IMPORT_FUTURE_M03_INTERNAL",
        "M02",
        "M03",
        M03_FUTURE_ROOTS,
        (),
        "M02 must use a future M03 public API, not its internal implementation.",
    ),
)


@dataclass(frozen=True)
class ImportRef:
    source_file: str
    source_module: str
    line: int
    target: str
    raw: str
    name: str | None = None


@dataclass(frozen=True)
class Violation:
    code: str
    source_file: str
    line: int
    source_module: str
    target_module: str
    target: str
    reason: str

    def __str__(self) -> str:
        return (
            "MODULE_BOUNDARY_VIOLATION\n\n"
            f"Source:\n{self.source_file}:{self.line}\n\n"
            f"Target:\n{self.target}\n\n"
            f"Rule:\n{self.code}\n\n"
            f"Modules:\n{self.source_module} -> {self.target_module}\n\n"
            f"Reason:\n{self.reason}"
        )


@dataclass(frozen=True)
class ScanResult:
    violations: tuple[Violation, ...]
    edges: frozenset[tuple[str, str]]

    def has_edge(self, source: str, target: str) -> bool:
        return (source, target) in self.edges


def _module_of(target: str) -> str | None:
    for module, roots in MODULE_ROOTS.items():
        if not roots:
            continue
        if any(target == root or target.startswith(root + ".") for root in roots):
            return module
    if any(
        target == root or target.startswith(root + ".")
        for root in M03_FUTURE_ROOTS
    ):
        return "M03"
    return None


def _module_parts(relative_file: Path) -> tuple[str, ...]:
    parts = list(relative_file.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return tuple(parts)


def _resolve_from(level: int, module: str | None, relative_file: Path) -> str:
    if level == 0:
        return module or ""
    package = list(_module_parts(relative_file))
    if relative_file.name != "__init__.py":
        package.pop()
    for _ in range(level - 1):
        if package:
            package.pop()
    if module:
        package.append(module)
    return ".".join(package)


def _imports_for_file(path: Path, relative_file: Path) -> list[ImportRef]:
    source_module_parts = _module_parts(relative_file)
    source_module = _module_of(".".join(source_module_parts))
    if source_module is None:
        return []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    refs: list[ImportRef] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                refs.append(
                    ImportRef(
                        source_file=str(relative_file),
                        source_module=source_module,
                        line=node.lineno,
                        target=alias.name,
                        raw=f"import {alias.name}",
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_from(node.level, node.module, relative_file)
            for alias in node.names:
                if alias.name == "*":
                    refs.append(
                        ImportRef(
                            source_file=str(relative_file),
                            source_module=source_module,
                            line=node.lineno,
                            target=base,
                            raw=f"from {base} import *",
                            name="*",
                        )
                    )
                    continue
                target = f"{base}.{alias.name}" if base else alias.name
                refs.append(
                    ImportRef(
                        source_file=str(relative_file),
                        source_module=source_module,
                        line=node.lineno,
                        target=target,
                        raw=f"from {base} import {alias.name}",
                        name=alias.name,
                    )
                )
    return refs


def _matches(target: str, prefixes: tuple[str, ...]) -> bool:
    return any(target == prefix or target.startswith(prefix + ".") for prefix in prefixes)


def scan(root: Path = API_ROOT) -> ScanResult:
    violations: list[Violation] = []
    edges: set[tuple[str, str]] = set()
    seen: set[tuple[str, str, int, str]] = set()

    for source_name, module_roots in MODULE_ROOTS.items():
        for module_root in module_roots:
            source_root = root / module_root.replace(".", "/")
            if not source_root.exists():
                continue
            for path in sorted(source_root.rglob("*.py")):
                if "__pycache__" in path.parts:
                    continue
                relative_file = path.relative_to(root)
                for ref in _imports_for_file(path, relative_file):
                    target_module = _module_of(ref.target)
                    if target_module is None:
                        continue
                    edges.add((ref.source_module, target_module))
                    for rule in RULES:
                        if (
                            rule.source_module != ref.source_module
                            or rule.target_module != target_module
                        ):
                            continue
                        if not _matches(ref.target, rule.forbidden_prefixes):
                            continue
                        allowed = (
                            ref.name != "*"
                            and (
                                ref.target in rule.allowed_exact
                                or ref.target in rule.allowed_targets
                                or _matches(ref.target, rule.allowed_prefixes)
                            )
                        )
                        if allowed:
                            continue
                        key = (rule.code, ref.source_file, ref.line, ref.target)
                        if key in seen:
                            continue
                        seen.add(key)
                        violations.append(
                            Violation(
                                code=rule.code,
                                source_file=ref.source_file,
                                line=ref.line,
                                source_module=ref.source_module,
                                target_module=target_module,
                                target=ref.target,
                                reason=rule.reason,
                            )
                        )
    return ScanResult(violations=tuple(violations), edges=frozenset(edges))


def find_cycles(edges: frozenset[tuple[str, str]]) -> list[tuple[str, ...]]:
    graph: dict[str, set[str]] = {}
    for source, target in edges:
        if source != target:
            graph.setdefault(source, set()).add(target)
    color: dict[str, int] = {}
    stack: list[str] = []
    cycles: set[tuple[str, ...]] = set()

    def visit(node: str) -> None:
        color[node] = 1
        stack.append(node)
        for next_node in sorted(graph.get(node, ())):
            if color.get(next_node, 0) == 0:
                visit(next_node)
            elif color.get(next_node) == 1:
                index = stack.index(next_node)
                cycle = stack[index:] + [next_node]
                # Normalize rotation for deterministic reporting.
                body = cycle[:-1]
                rotations = [tuple(body[i:] + body[:i]) for i in range(len(body))]
                normalized = min(rotations)
                cycles.add(normalized + (normalized[0],))
        stack.pop()
        color[node] = 2

    for node in sorted(set(graph) | {target for targets in graph.values() for target in targets}):
        if color.get(node, 0) == 0:
            visit(node)
    return sorted(cycles)


def test_current_production_code_has_no_boundary_violations() -> None:
    result = scan()
    assert not result.violations, "\n\n".join(str(v) for v in result.violations)
    assert result.has_edge("M01", "M06")
    assert result.has_edge("M06", "M05")


def test_current_dependency_graph_has_no_cycles() -> None:
    result = scan()
    cycles = find_cycles(result.edges)
    assert cycles == [], f"cycle path(s): {cycles}"


def test_m03_is_not_fabricated_and_future_constraints_are_registered() -> None:
    assert MODULE_ROOTS["M03"] == ()
    assert M03_FUTURE_ROOTS
    assert M03_FUTURE_CONSTRAINTS["M03_MUST_NOT_IMPORT_M05"]
    assert M03_FUTURE_CONSTRAINTS["M03_MUST_NOT_IMPORT_M06"]
    # Do not treat M02 Personal Knowledge as M03.
    assert not any(root.startswith("app.modules.knowledge") for root in M03_FUTURE_ROOTS)


def _write_fixture(root: Path, relative: str, source: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _assert_violation(root: Path, expected_code: str, expected_target: str) -> None:
    result = scan(root)
    matching = [v for v in result.violations if v.code == expected_code]
    assert matching, [str(v) for v in result.violations]
    violation = matching[0]
    assert violation.target == expected_target or violation.target.startswith(
        expected_target + "."
    )
    text = str(violation)
    assert "MODULE_BOUNDARY_VIOLATION" in text
    assert violation.source_file in text
    assert str(violation.line) in text
    assert expected_target in text


def test_negative_m01_imports_m05_orm(tmp_path) -> None:
    _write_fixture(
        tmp_path,
        "app/api/v1/rag/bad.py",
        "from app.modules.execution.models import ExecutionRun\n",
    )
    _assert_violation(
        tmp_path,
        "M01_ROUTER_MUST_NOT_IMPORT_M05_INTERNAL",
        "app.modules.execution.models",
    )


def test_negative_m01_imports_m05_service(tmp_path) -> None:
    _write_fixture(
        tmp_path,
        "app/api/v1/rag/bad.py",
        "from app.modules.execution.service import create_run\n",
    )
    _assert_violation(
        tmp_path,
        "M01_ROUTER_MUST_NOT_IMPORT_M05_INTERNAL",
        "app.modules.execution.service",
    )


def test_negative_m01_imports_m06_handler(tmp_path) -> None:
    _write_fixture(
        tmp_path,
        "app/api/v1/rag/bad.py",
        "from app.modules.evaluation.handlers.dossier_rollup import dossier_rollup\n",
    )
    _assert_violation(
        tmp_path,
        "M01_ROUTER_MUST_NOT_IMPORT_M06_INTERNAL",
        "app.modules.evaluation.handlers.dossier_rollup",
    )


def test_negative_m06_imports_m05_orm(tmp_path) -> None:
    _write_fixture(
        tmp_path,
        "app/modules/evaluation/handlers/bad.py",
        "from app.modules.execution.models import ExecutionJob\n",
    )
    _assert_violation(
        tmp_path,
        "M06_MUST_NOT_IMPORT_M05_ORM",
        "app.modules.execution.models",
    )


def test_negative_m05_imports_m06(tmp_path) -> None:
    _write_fixture(
        tmp_path,
        "app/modules/execution/bad.py",
        "from app.modules.evaluation.facades.dossiers import DossierFacade\n",
    )
    _assert_violation(
        tmp_path,
        "M05_MUST_NOT_IMPORT_M06",
        "app.modules.evaluation.facades.dossiers",
    )


def test_negative_m06_relative_import_of_m05_orm(tmp_path) -> None:
    _write_fixture(
        tmp_path,
        "app/modules/evaluation/handlers/bad.py",
        "from ...execution.models import ExecutionRun\n",
    )
    _assert_violation(
        tmp_path,
        "M06_MUST_NOT_IMPORT_M05_ORM",
        "app.modules.execution.models",
    )


def test_negative_cycle_is_detected(tmp_path) -> None:
    _write_fixture(
        tmp_path,
        "app/api/v1/rag/cycle_a.py",
        "from app.modules.evaluation.facades.cycle_b import cycle_b\n",
    )
    _write_fixture(
        tmp_path,
        "app/modules/evaluation/facades/cycle_b.py",
        "from app.api.v1.rag.cycle_a import cycle_a\n",
    )
    result = scan(tmp_path)
    assert result.has_edge("M01", "M06")
    assert result.has_edge("M06", "M01")
    cycles = find_cycles(result.edges)
    assert cycles
    assert ("M01", "M06", "M01") in cycles


def test_negative_rule_reports_file_line_and_reason(tmp_path) -> None:
    _write_fixture(
        tmp_path,
        "app/modules/execution/bad.py",
        "from app.modules.evaluation.facades.dossiers import DossierFacade\n",
    )
    result = scan(tmp_path)
    violation = next(v for v in result.violations if v.code == "M05_MUST_NOT_IMPORT_M06")
    text = str(violation)
    assert "app/modules/execution/bad.py:1" in text
    assert "app.modules.evaluation.facades.dossiers" in text
    assert "M05 Execution must remain independent" in text


def test_negative_m01_plain_import_of_m05_orm(tmp_path) -> None:
    _write_fixture(
        tmp_path,
        "app/api/v1/rag/bad.py",
        "import app.modules.execution.models\n",
    )
    _assert_violation(
        tmp_path,
        "M01_ROUTER_MUST_NOT_IMPORT_M05_INTERNAL",
        "app.modules.execution.models",
    )


def test_positive_m01_facade_and_m06_public_m05_imports(tmp_path) -> None:
    _write_fixture(
        tmp_path,
        "app/api/v1/rag/good.py",
        "from app.modules.evaluation.facades.dossiers import DossierFacade\n",
    )
    _write_fixture(
        tmp_path,
        "app/modules/evaluation/facades/good.py",
        "from app.modules.execution.service import create_run_with_step_job\n"
        "from app.modules.execution.read_models import RunSummary\n"
        "from app.modules.execution.runtime import read_worker_snapshot\n"
        "from app.modules.execution.worker import JobContext\n",
    )
    result = scan(tmp_path)
    assert not result.violations, "\n\n".join(str(v) for v in result.violations)


def test_negative_m06_imports_m05_repository(tmp_path) -> None:
    _write_fixture(
        tmp_path,
        "app/modules/evaluation/handlers/bad.py",
        "from app.modules.execution.repository import ExecutionRepository\n",
    )
    _assert_violation(
        tmp_path,
        "M06_MUST_NOT_IMPORT_M05_ORM",
        "app.modules.execution.repository",
    )


def test_negative_m06_imports_m05_internal_implementation(tmp_path) -> None:
    _write_fixture(
        tmp_path,
        "app/modules/evaluation/handlers/bad.py",
        "from app.modules.execution.internal import helper\n",
    )
    _assert_violation(
        tmp_path,
        "M06_MUST_NOT_IMPORT_M05_ORM",
        "app.modules.execution.internal",
    )


def test_negative_m06_imports_worker_internal_symbol(tmp_path) -> None:
    _write_fixture(
        tmp_path,
        "app/modules/evaluation/handlers/bad.py",
        "from app.modules.execution.worker import Worker\n",
    )
    _assert_violation(
        tmp_path,
        "M06_MUST_NOT_IMPORT_M05_ORM",
        "app.modules.execution.worker",
    )


def test_wildcard_imports_do_not_escape_boundaries(tmp_path) -> None:
    _write_fixture(
        tmp_path,
        "app/api/v1/rag/bad.py",
        "from app.modules.execution import *\n",
    )
    _assert_violation(
        tmp_path,
        "M01_ROUTER_MUST_NOT_IMPORT_M05_INTERNAL",
        "app.modules.execution",
    )

    _write_fixture(
        tmp_path,
        "app/api/v1/rag/other.py",
        "from app.modules.evaluation import *\n",
    )
    _assert_violation(
        tmp_path,
        "M01_ROUTER_MUST_NOT_IMPORT_M06_INTERNAL",
        "app.modules.evaluation",
    )

    _write_fixture(
        tmp_path,
        "app/modules/evaluation/handlers/wild.py",
        "from app.modules.execution import *\n",
    )
    _assert_violation(
        tmp_path,
        "M06_MUST_NOT_IMPORT_M05_ORM",
        "app.modules.execution",
    )
