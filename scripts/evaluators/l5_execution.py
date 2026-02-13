"""L5: 실행 정밀도 평가 (정적 분석)."""

import ast
import json
import re
from pathlib import Path

from models import MetricResult
from discovery import SkillMetadata
from evaluators.base import run_layer_evaluation, iter_scripts, has_scripts_dir


def check_script_count(skill: SkillMetadata) -> MetricResult:
    """스크립트 수 (10점)."""
    n = len(skill.script_files)
    score = min(n * 3, 10) if n > 0 else 0
    return MetricResult(
        name="script_count",
        score=score, max_score=10.0,
        details=f"scripts/ 내 .py 파일 {n}개",
        passed=n > 0,
    )


def check_shebang(skill: SkillMetadata) -> MetricResult:
    """shebang 준수 (10점)."""
    if not has_scripts_dir(skill):
        return MetricResult(
            name="shebang", score=0, max_score=10.0,
            details="scripts/ 없음", passed=False,
        )

    total = 0
    with_shebang = 0
    for _, content in iter_scripts(skill):
        total += 1
        first_line = content.split("\n", 1)[0]
        if first_line.startswith("#!"):
            with_shebang += 1

    if total == 0:
        return MetricResult(
            name="shebang", score=5, max_score=10.0,
            details="실행 가능한 스크립트 없음", passed=True,
        )

    ratio = with_shebang / total
    score = round(ratio * 10)
    return MetricResult(
        name="shebang",
        score=score, max_score=10.0,
        details=f"shebang {with_shebang}/{total} ({ratio:.0%})",
        passed=ratio >= 0.5,
    )


def check_cli_interface(skill: SkillMetadata) -> MetricResult:
    """CLI 인터페이스 — argparse 사용 (10점)."""
    if not has_scripts_dir(skill):
        return MetricResult(
            name="cli_interface", score=0, max_score=10.0,
            details="scripts/ 없음", passed=False,
        )

    has_argparse = False
    has_help = False
    for _, content in iter_scripts(skill):
        if "argparse" in content or "ArgumentParser" in content:
            has_argparse = True
        if "--help" in content or "add_argument" in content:
            has_help = True

    score = 0
    details = []
    if has_argparse:
        score += 7
        details.append("argparse 사용")
    if has_help:
        score += 3
        details.append("인자 정의")

    if not details:
        details.append("CLI 인터페이스 없음")

    return MetricResult(
        name="cli_interface",
        score=score, max_score=10.0,
        details="; ".join(details),
        passed=has_argparse,
    )


def check_docstrings(skill: SkillMetadata) -> MetricResult:
    """모듈 docstring 커버리지 (10점)."""
    if not has_scripts_dir(skill):
        return MetricResult(
            name="docstrings", score=0, max_score=10.0,
            details="scripts/ 없음", passed=False,
        )

    total = 0
    with_doc = 0
    for _, content in iter_scripts(skill):
        total += 1
        c = content.lstrip()
        if c.startswith("#!"):
            c = c.split("\n", 1)[-1].lstrip()
        if c.startswith('"""') or c.startswith("'''"):
            with_doc += 1

    if total == 0:
        return MetricResult(
            name="docstrings", score=5, max_score=10.0,
            details="스크립트 없음", passed=True,
        )

    ratio = with_doc / total
    score = round(ratio * 10)
    return MetricResult(
        name="docstrings",
        score=score, max_score=10.0,
        details=f"docstring {with_doc}/{total} ({ratio:.0%})",
        passed=ratio >= 0.3,
    )


def check_bridge_availability(skill: SkillMetadata) -> MetricResult:
    """브릿지 존재 — 스킬 간 연동 (10점)."""
    has_bridge_script = any("bridge" in f.lower() for f in skill.script_files)
    has_bridge_dir = skill.has_bridges_dir

    if has_bridge_script or has_bridge_dir:
        score = 10
        details = "bridge 존재"
        if has_bridge_dir:
            details += " (bridges/ 디렉토리)"
        if has_bridge_script:
            details += " (scripts/bridge.py)"
    else:
        score = 0
        details = "bridge 없음"

    return MetricResult(
        name="bridge_availability",
        score=score, max_score=10.0,
        details=details,
        passed=True,  # bridge는 선택사항
    )


def check_function_quality(skill: SkillMetadata) -> MetricResult:
    """함수 docstring + 타입 힌트 커버리지 (15점)."""
    if not has_scripts_dir(skill):
        return MetricResult(
            name="function_quality", score=0, max_score=15.0,
            details="scripts/ 없음", passed=False,
        )

    func_pattern = re.compile(r'^(\s*)def\s+(\w+)\s*\(([^)]*)\)(\s*->\s*\S+)?:', re.MULTILINE)
    total_funcs = 0
    with_docstring = 0
    with_typehint = 0

    for _, content in iter_scripts(skill):
        for match in func_pattern.finditer(content):
            total_funcs += 1
            params = match.group(3)
            return_type = match.group(4)
            if return_type or (": " in params and "self" not in params.split(":")[0].split(",")[0]):
                with_typehint += 1

            func_end = match.end()
            remaining = content[func_end:func_end + 200].lstrip()
            if remaining.startswith('"""') or remaining.startswith("'''"):
                with_docstring += 1

    if total_funcs == 0:
        return MetricResult(
            name="function_quality", score=5, max_score=15.0,
            details="함수 없음", passed=True,
        )

    doc_ratio = with_docstring / total_funcs
    hint_ratio = with_typehint / total_funcs

    score = 0.0
    if doc_ratio >= 0.8:
        score += 10
    elif doc_ratio >= 0.5:
        score += 8
    elif doc_ratio >= 0.3:
        score += 5
    else:
        score += 2

    if hint_ratio >= 0.6:
        score += 5
    elif hint_ratio >= 0.3:
        score += 3
    else:
        score += 1

    return MetricResult(
        name="function_quality",
        score=min(score, 15.0), max_score=15.0,
        details=f"함수 {total_funcs}개, docstring {with_docstring} ({doc_ratio:.0%}), 타입힌트 {with_typehint} ({hint_ratio:.0%})",
        passed=doc_ratio >= 0.3,
    )


def _cyclomatic_complexity(node: ast.AST) -> int:
    """단일 함수/메서드의 cyclomatic complexity 계산."""
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            # and/or 연산자 수 (values가 2개면 연산자 1개)
            complexity += len(child.values) - 1
        elif isinstance(child, ast.Assert):
            complexity += 1
        elif isinstance(child, ast.IfExp):
            complexity += 1
    return complexity


def check_code_complexity(skill: SkillMetadata) -> MetricResult:
    """코드 복잡도 — AST 기반 cyclomatic complexity (15점).

    함수별 CC를 측정하고 평균 CC로 점수를 산출합니다.
    낮은 CC = 읽기 쉬운 코드 = 높은 점수.
    """
    if not has_scripts_dir(skill):
        return MetricResult(
            name="code_complexity", score=0, max_score=15.0,
            details="scripts/ 없음", passed=False,
        )

    func_complexities = []

    for py_file, content in iter_scripts(skill, skip_init=True):
        try:
            tree = ast.parse(content, filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cc = _cyclomatic_complexity(node)
                func_complexities.append((node.name, cc))

    if not func_complexities:
        return MetricResult(
            name="code_complexity", score=5, max_score=15.0,
            details="분석 가능한 함수 없음", passed=True,
        )

    avg_cc = sum(cc for _, cc in func_complexities) / len(func_complexities)
    max_cc = max(cc for _, cc in func_complexities)
    max_func = next(name for name, cc in func_complexities if cc == max_cc)

    if avg_cc <= 5:
        score = 15
    elif avg_cc <= 10:
        score = 10
    elif avg_cc <= 15:
        score = 5
    else:
        score = 2

    return MetricResult(
        name="code_complexity",
        score=score, max_score=15.0,
        details=f"함수 {len(func_complexities)}개, 평균 CC={avg_cc:.1f}, 최대 CC={max_cc} ({max_func})",
        passed=avg_cc <= 10,
    )


def _load_script_benchmarks(skill: SkillMetadata, benchmarks_dir: Path) -> dict:
    """L5 벤치마크 데이터 로드."""
    bench_file = benchmarks_dir / "L5_execution" / "script_tests.json"
    if not bench_file.exists():
        return {}
    data = json.loads(bench_file.read_text(encoding="utf-8"))
    return data.get(skill.name, {})


def check_script_benchmark(skill: SkillMetadata, benchmarks_dir: Path) -> MetricResult:
    """벤치마크 기반 스크립트 품질 테스트 (50점). 벤치마크 없으면 N/A."""
    bench = _load_script_benchmarks(skill, benchmarks_dir)
    if not bench:
        return MetricResult(
            name="script_benchmark", score=0, max_score=0,
            details="벤치마크 없음 (benchmarks/L5_execution/script_tests.json)",
            passed=True,
        )

    scripts_dir = skill.skill_path / "scripts"
    if not scripts_dir.is_dir():
        return MetricResult(
            name="script_benchmark", score=0, max_score=50.0,
            details="scripts/ 없음", passed=False,
        )

    correct = 0
    total = 0

    for item in bench.get("required_patterns", []):
        total += 1
        target_file = scripts_dir / item["file"]
        if target_file.exists():
            content = target_file.read_text(encoding="utf-8")
            if re.search(item["pattern"], content):
                correct += 1

    for item in bench.get("forbidden_patterns", []):
        total += 1
        target_file = scripts_dir / item["file"]
        if target_file.exists():
            content = target_file.read_text(encoding="utf-8")
            if not re.search(item["pattern"], content):
                correct += 1
        else:
            correct += 1

    if total == 0:
        return MetricResult(
            name="script_benchmark", score=0, max_score=0,
            details="벤치마크 데이터 비어있음", passed=True,
        )

    ratio = correct / total
    score = round(ratio * 50)
    return MetricResult(
        name="script_benchmark",
        score=score, max_score=50.0,
        details=f"정답 {correct}/{total} ({ratio:.0%})",
        passed=ratio >= 0.6,
    )


def evaluate(skill: SkillMetadata, benchmarks_dir: Path = None, **kwargs) -> 'LayerResult':
    """L5 실행 전체 평가."""
    metrics = [
        check_script_count(skill),
        check_shebang(skill),
        check_cli_interface(skill),
        check_docstrings(skill),
        check_bridge_availability(skill),
        check_function_quality(skill),
        check_code_complexity(skill),
    ]

    if benchmarks_dir:
        bench_result = check_script_benchmark(skill, benchmarks_dir)
        if bench_result.max_score > 0:
            metrics.append(bench_result)

    return run_layer_evaluation("L5", skill, metrics)
