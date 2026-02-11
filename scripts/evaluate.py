#!/usr/bin/env python3
"""Skill Evaluator CLI - L1/L4/L6 평가."""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from models import MetricResult, LayerResult
from discovery import discover_skills, SkillMetadata
from reporter import format_text, format_json, format_markdown, weighted_score


# ──────────────────────────────────────────────
# L1: 구조적 무결성 평가
# ──────────────────────────────────────────────

def check_yaml_validity(skill: SkillMetadata) -> MetricResult:
    """YAML frontmatter 유효성 검사 (30점)."""
    score = 0.0
    details = []

    if skill.name and skill.name != skill.skill_path.name:
        score += 10
        details.append("name 필드 존재")
    elif skill.name:
        score += 5
        details.append("name 필드 존재 (디렉토리명과 동일)")
    else:
        details.append("name 필드 없음")

    if skill.description:
        score += 10
        details.append("description 필드 존재")
    else:
        details.append("description 필드 없음")

    if skill.triggers.keywords:
        score += 10
        details.append(f"트리거 {len(skill.triggers.keywords)}개 추출")
    else:
        details.append("트리거 키워드 없음")

    return MetricResult(
        name="yaml_validity",
        score=score,
        max_score=30.0,
        details="; ".join(details),
        passed=score >= 20,
    )


def check_directory_structure(skill: SkillMetadata) -> MetricResult:
    """디렉토리 구조 검사 (40점)."""
    score = 10.0  # SKILL.md 존재 (여기 왔으면 존재)
    details = ["SKILL.md 존재"]

    if skill.has_scripts_dir:
        score += 15
        details.append(f"scripts/ ({len(skill.script_files)} files)")
    else:
        details.append("scripts/ 없음")

    if skill.has_references_dir:
        score += 10
        details.append(f"references/ ({len(skill.reference_files)} files)")
    else:
        details.append("references/ 없음")

    if skill.has_tests_dir:
        score += 5
        details.append("tests/ 존재")

    if skill.has_design_decision:
        score += 3
        details.append("DESIGN_DECISION.md 존재")

    return MetricResult(
        name="directory_structure",
        score=min(score, 40.0),
        max_score=40.0,
        details="; ".join(details),
        passed=score >= 20,
    )


def check_resource_independence(skill: SkillMetadata) -> MetricResult:
    """리소스 독립성 검사 (30점) - 하드코딩 절대경로 탐지."""
    score = 30.0
    details = []
    violations = []

    scripts_dir = skill.skill_path / "scripts"
    if not scripts_dir.is_dir():
        return MetricResult(
            name="resource_independence",
            score=15.0,
            max_score=30.0,
            details="scripts/ 없어서 부분 점수",
            passed=True,
        )

    hardcoded_pattern = re.compile(r'["\'/](Users|home|mnt)/\w+/')

    for py_file in scripts_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            matches = hardcoded_pattern.findall(content)
            if matches:
                score -= 10
                violations.append(py_file.name)
        except (UnicodeDecodeError, PermissionError):
            pass

    # 상대경로 / SKILLS_ROOT 사용 확인
    uses_relative = False
    for py_file in scripts_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            if "Path(__file__)" in content or "SKILLS_ROOT" in content or "skill_paths" in content:
                uses_relative = True
                break
        except (UnicodeDecodeError, PermissionError):
            pass

    if uses_relative:
        details.append("상대경로/SKILLS_ROOT 사용 확인")
    else:
        score -= 5
        details.append("상대경로/SKILLS_ROOT 사용 미확인")

    if violations:
        details.append(f"하드코딩 경로 발견: {', '.join(violations)}")
    else:
        details.append("하드코딩 절대경로 없음")

    score = max(score, 0.0)
    return MetricResult(
        name="resource_independence",
        score=score,
        max_score=30.0,
        details="; ".join(details),
        passed=score >= 15,
    )


def evaluate_l1(skill: SkillMetadata) -> LayerResult:
    """L1 구조적 무결성 전체 평가."""
    result = LayerResult(layer="L1", skill_name=skill.name)
    result.metrics = [
        check_yaml_validity(skill),
        check_directory_structure(skill),
        check_resource_independence(skill),
    ]
    result.compute_score()
    for m in result.metrics:
        if not m.passed:
            result.recommendations.append(f"{m.name}: {m.details}")
    return result


# ──────────────────────────────────────────────
# L4: 워크플로우 평가
# ──────────────────────────────────────────────

def check_workflow_structure(skill: SkillMetadata) -> MetricResult:
    """워크플로우 구조 감지 (60점)."""
    skill_md = skill.skill_path / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")

    score = 0.0
    details = []

    # Phase/Step/Pipeline 패턴
    phases = re.findall(r'[Pp]hase\s+\d', text)
    steps = re.findall(r'[Ss]tep\s+\d', text)
    has_pipeline = bool(re.search(r'[Pp]ipeline|파이프라인', text))

    workflow_items = set(phases + steps)

    if workflow_items or has_pipeline:
        score += 20
        details.append(f"워크플로우 감지 (Phase:{len(set(phases))}, Step:{len(set(steps))}, Pipeline:{'Y' if has_pipeline else 'N'})")
    else:
        details.append("워크플로우 구조 없음")

    if len(workflow_items) >= 3:
        score += 15
        details.append(f"3+ 단계 ({len(workflow_items)}개)")
    if len(workflow_items) >= 5:
        score += 10
        details.append("5+ 단계")

    # 조건부 실행
    conditional = re.search(r'건너뛰기|skip|optional|선택|조건', text, re.IGNORECASE)
    if conditional:
        score += 15
        details.append("조건부 실행 있음")

    return MetricResult(
        name="workflow_structure",
        score=min(score, 60.0),
        max_score=60.0,
        details="; ".join(details),
        passed=score >= 20,
    )


def check_plan_adherence(skill: SkillMetadata) -> MetricResult:
    """계획 준수 마커 감지 (40점)."""
    skill_md = skill.skill_path / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")

    score = 0.0
    details = []

    # 체크리스트
    checklists = re.findall(r'- \[[ x]\]', text)
    if checklists:
        score += 10
        details.append(f"체크리스트 {len(checklists)}개")

    # 자가 점검 섹션
    if re.search(r'자가\s*점검|self[- ]?check', text, re.IGNORECASE):
        score += 15
        details.append("자가 점검 섹션")

    # 사용 조건 / 비사용 조건
    if re.search(r'[Ww]hen to use|사용\s*조건|언제\s*사용', text):
        score += 5
        details.append("사용 조건 명시")
    if re.search(r"[Dd]on'?t use|비목표|[Nn]on-?[Gg]oal", text):
        score += 5
        details.append("비목표/비사용 명시")

    # 전환 기준
    if re.search(r'전환|transition|다음\s*단계|next\s*phase', text, re.IGNORECASE):
        score += 5
        details.append("단계 전환 기준")

    if not details:
        details.append("계획 준수 마커 없음")

    return MetricResult(
        name="plan_adherence",
        score=min(score, 40.0),
        max_score=40.0,
        details="; ".join(details),
        passed=score >= 10,
    )


def evaluate_l4(skill: SkillMetadata) -> LayerResult:
    """L4 워크플로우 전체 평가."""
    result = LayerResult(layer="L4", skill_name=skill.name)
    result.metrics = [
        check_workflow_structure(skill),
        check_plan_adherence(skill),
    ]
    result.compute_score()
    for m in result.metrics:
        if not m.passed:
            result.recommendations.append(f"{m.name}: {m.details}")
    return result


# ──────────────────────────────────────────────
# L6: 검증 평가
# ──────────────────────────────────────────────

def check_verification_infra(skill: SkillMetadata) -> MetricResult:
    """검증 인프라 (50점)."""
    score = 0.0
    details = []

    if skill.has_tests_dir:
        score += 20
        details.append("tests/ 존재")

    # --verify / --check 플래그 탐지
    scripts_dir = skill.skill_path / "scripts"
    if scripts_dir.is_dir():
        for py_file in scripts_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
                if re.search(r'--verify|--check|--validate', content):
                    score += 15
                    details.append(f"검증 플래그 ({py_file.name})")
                    break
            except (UnicodeDecodeError, PermissionError):
                pass

        # checker/validator 스크립트
        for py_file in scripts_dir.rglob("*.py"):
            if re.search(r'check|valid|verif', py_file.stem, re.IGNORECASE):
                score += 15
                details.append(f"검증 스크립트 ({py_file.name})")
                break

    if not details:
        details.append("검증 인프라 없음")

    return MetricResult(
        name="verification_infra",
        score=min(score, 50.0),
        max_score=50.0,
        details="; ".join(details),
        passed=score >= 15,
    )


def check_error_handling(skill: SkillMetadata) -> MetricResult:
    """에러 처리 패턴 (30점)."""
    scripts_dir = skill.skill_path / "scripts"
    if not scripts_dir.is_dir():
        return MetricResult(
            name="error_handling", score=0, max_score=30.0,
            details="scripts/ 없음", passed=False,
        )

    score = 0.0
    details = []
    has_try = False
    has_specific = False
    has_exit = False

    for py_file in scripts_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            if "try:" in content:
                has_try = True
            if re.search(r'except\s+\w+', content):
                has_specific = True
            if "sys.exit" in content:
                has_exit = True
        except (UnicodeDecodeError, PermissionError):
            pass

    if has_try:
        score += 10
        details.append("try/except 사용")
    if has_specific:
        score += 10
        details.append("구체적 예외 타입")
    if has_exit:
        score += 10
        details.append("sys.exit 사용")

    if not details:
        details.append("에러 처리 없음")

    return MetricResult(
        name="error_handling",
        score=score,
        max_score=30.0,
        details="; ".join(details),
        passed=score >= 10,
    )


def check_faithfulness(skill: SkillMetadata) -> MetricResult:
    """충실성 마커 (20점)."""
    score = 0.0
    details = []

    # OUTPUT_FORMAT 문서
    for ref in skill.reference_files:
        if re.search(r'output|format|schema', ref, re.IGNORECASE):
            score += 10
            details.append(f"출력 형식 문서 ({ref})")
            break

    # 예시 출력
    for ref in skill.reference_files:
        if re.search(r'example|sample', ref, re.IGNORECASE):
            score += 5
            details.append(f"예시 파일 ({ref})")
            break

    # SKILL.md 내 JSON/출력 예시
    skill_md = skill.skill_path / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    if re.search(r'```json|출력\s*형식|output\s*format', text, re.IGNORECASE):
        score += 5
        details.append("SKILL.md 내 출력 형식 설명")

    if not details:
        details.append("충실성 마커 없음")

    return MetricResult(
        name="faithfulness",
        score=min(score, 20.0),
        max_score=20.0,
        details="; ".join(details),
        passed=score >= 5,
    )


def evaluate_l6(skill: SkillMetadata) -> LayerResult:
    """L6 검증 전체 평가."""
    result = LayerResult(layer="L6", skill_name=skill.name)
    result.metrics = [
        check_verification_infra(skill),
        check_error_handling(skill),
        check_faithfulness(skill),
    ]
    result.compute_score()
    for m in result.metrics:
        if not m.passed:
            result.recommendations.append(f"{m.name}: {m.details}")
    return result


# ──────────────────────────────────────────────
# L2: 활성화 평가 (정적 분석)
# ──────────────────────────────────────────────

# 범용 키워드 — 도메인 특이성 판별용
_GENERIC_KEYWORDS = {
    "분석", "analysis", "도와줘", "help", "확인", "check",
    "보여줘", "알려줘", "실행", "run", "해줘",
}


def check_trigger_count(skill: SkillMetadata) -> MetricResult:
    """트리거 키워드 수 (15점). 8-15개가 최적."""
    n = len(skill.triggers.keywords)
    if n == 0:
        score, details = 0, "트리거 없음"
    elif n <= 2:
        score, details = 5, f"{n}개 (너무 적음)"
    elif n <= 7:
        score, details = 10, f"{n}개"
    elif n <= 15:
        score, details = 15, f"{n}개 (최적 범위)"
    else:
        score, details = 10, f"{n}개 (너무 많음 — 초점 분산 우려)"

    return MetricResult(
        name="trigger_count",
        score=score, max_score=15.0,
        details=f"키워드 {details}; source={skill.triggers.source}",
        passed=n > 0,
    )


def check_trigger_specificity(skill: SkillMetadata) -> MetricResult:
    """트리거 특이성 (15점). 도메인 특화 키워드 비율."""
    keywords = skill.triggers.keywords
    if not keywords:
        return MetricResult(
            name="trigger_specificity", score=0, max_score=15.0,
            details="키워드 없음", passed=False,
        )

    generic = sum(1 for kw in keywords if kw.lower() in _GENERIC_KEYWORDS)
    specific = len(keywords) - generic
    ratio = specific / len(keywords) if keywords else 0

    if ratio >= 0.8:
        score = 15
    elif ratio >= 0.6:
        score = 10
    elif ratio >= 0.4:
        score = 7
    else:
        score = 3

    return MetricResult(
        name="trigger_specificity",
        score=score, max_score=15.0,
        details=f"도메인 특화: {specific}/{len(keywords)} ({ratio:.0%})",
        passed=ratio >= 0.4,
    )


def check_trigger_overlap(skill: SkillMetadata, all_skills: list) -> MetricResult:
    """트리거 중복도 (10점). 다른 스킬과 키워드 겹침."""
    my_kws = set(kw.lower() for kw in skill.triggers.keywords)
    if not my_kws:
        return MetricResult(
            name="trigger_overlap", score=0, max_score=10.0,
            details="키워드 없음", passed=False,
        )

    overlaps = []
    for other in all_skills:
        if other.name == skill.name:
            continue
        other_kws = set(kw.lower() for kw in other.triggers.keywords)
        shared = my_kws & other_kws
        if shared:
            overlaps.append((other.name, shared))

    if not overlaps:
        return MetricResult(
            name="trigger_overlap", score=10, max_score=10.0,
            details="다른 스킬과 중복 없음", passed=True,
        )

    total_shared = set()
    overlap_names = []
    for name, shared in overlaps:
        total_shared |= shared
        overlap_names.append(f"{name}({len(shared)})")

    ratio = len(total_shared) / len(my_kws)
    if ratio <= 0.1:
        score = 8
    elif ratio <= 0.3:
        score = 5
    else:
        score = 2

    return MetricResult(
        name="trigger_overlap",
        score=score, max_score=10.0,
        details=f"중복 {len(total_shared)}개 ({ratio:.0%}): {', '.join(overlap_names)}",
        passed=ratio <= 0.3,
    )


def _load_trigger_benchmarks(skill: SkillMetadata, benchmarks_dir: Path) -> dict:
    """L2 벤치마크 데이터 로드."""
    bench_file = benchmarks_dir / "L2_activation" / "trigger_queries.json"
    if not bench_file.exists():
        return {}
    data = json.loads(bench_file.read_text(encoding="utf-8"))
    return data.get(skill.name, {})


def check_trigger_benchmark(skill: SkillMetadata, benchmarks_dir: Path) -> MetricResult:
    """벤치마크 기반 트리거 인식 테스트 (60점). 벤치마크 없으면 N/A."""
    bench = _load_trigger_benchmarks(skill, benchmarks_dir)
    if not bench:
        return MetricResult(
            name="trigger_benchmark", score=0, max_score=0,
            details="벤치마크 없음 (benchmarks/L2_activation/trigger_queries.json)",
            passed=True,
        )

    keywords = set(kw.lower() for kw in skill.triggers.keywords)
    correct = 0
    total = 0

    # positive: 이 키워드가 매칭되어야 함
    for item in bench.get("positive", []):
        total += 1
        query = item["query"].lower()
        if any(kw in query for kw in keywords):
            correct += 1

    # negative: 이 키워드가 매칭되면 안 됨
    for item in bench.get("negative", []):
        total += 1
        query = item["query"].lower()
        if not any(kw in query for kw in keywords):
            correct += 1

    if total == 0:
        return MetricResult(
            name="trigger_benchmark", score=0, max_score=0,
            details="벤치마크 데이터 비어있음", passed=True,
        )

    ratio = correct / total
    score = round(ratio * 60)
    return MetricResult(
        name="trigger_benchmark",
        score=score, max_score=60.0,
        details=f"정답 {correct}/{total} ({ratio:.0%})",
        passed=ratio >= 0.6,
    )


def evaluate_l2(skill: SkillMetadata, all_skills: list = None, benchmarks_dir: Path = None) -> LayerResult:
    """L2 활성화 전체 평가."""
    result = LayerResult(layer="L2", skill_name=skill.name)
    metrics = [
        check_trigger_count(skill),
        check_trigger_specificity(skill),
        check_trigger_overlap(skill, all_skills or []),
    ]

    # 벤치마크 메트릭 추가 (있을 때만 점수에 반영)
    if benchmarks_dir:
        bench_result = check_trigger_benchmark(skill, benchmarks_dir)
        if bench_result.max_score > 0:
            metrics.append(bench_result)

    result.metrics = metrics
    result.compute_score()
    for m in result.metrics:
        if not m.passed:
            result.recommendations.append(f"{m.name}: {m.details}")
    return result


# ──────────────────────────────────────────────
# L3: 검색 평가 (정적 분석)
# ──────────────────────────────────────────────

def check_reference_count(skill: SkillMetadata) -> MetricResult:
    """참고 문서 수 (20점)."""
    n = len(skill.reference_files)
    if n == 0:
        score = 0
    elif n == 1:
        score = 10
    elif n == 2:
        score = 15
    else:
        score = 20

    return MetricResult(
        name="reference_count",
        score=score, max_score=20.0,
        details=f"references/ 파일 {n}개",
        passed=n > 0,
    )


def check_reference_type_coverage(skill: SkillMetadata) -> MetricResult:
    """참고 문서 타입 커버리지 (20점). API/Examples/Integration/Output 4종."""
    types_found = []
    for ref in skill.reference_files:
        ref_lower = ref.lower()
        if re.search(r'api', ref_lower) and "api" not in types_found:
            types_found.append("api")
        if re.search(r'example|sample', ref_lower) and "example" not in types_found:
            types_found.append("example")
        if re.search(r'integrat|bridge', ref_lower) and "integration" not in types_found:
            types_found.append("integration")
        if re.search(r'output|format|schema', ref_lower) and "output" not in types_found:
            types_found.append("output")
        if re.search(r'test|testing', ref_lower) and "testing" not in types_found:
            types_found.append("testing")

    score = min(len(types_found) * 5, 20)
    return MetricResult(
        name="reference_type_coverage",
        score=score, max_score=20.0,
        details=f"타입 {len(types_found)}종: {', '.join(types_found) if types_found else '없음'}",
        passed=len(types_found) >= 1,
    )


def check_progressive_disclosure(skill: SkillMetadata) -> MetricResult:
    """정보 분산도 (10점). SKILL.md는 간결하고 상세는 references/로."""
    lines = skill.skill_md_lines
    if lines < 200:
        score = 10
        detail = f"{lines}줄 (간결)"
    elif lines < 300:
        score = 8
        detail = f"{lines}줄 (적정)"
    elif lines < 500:
        score = 5
        detail = f"{lines}줄 (다소 길음)"
    else:
        score = 2
        detail = f"{lines}줄 (과다 — references/로 분리 권장)"

    return MetricResult(
        name="progressive_disclosure",
        score=score, max_score=10.0,
        details=detail,
        passed=lines < 500,
    )


def check_reference_freshness(skill: SkillMetadata) -> MetricResult:
    """참조 파일 실존 여부 (20점)."""
    refs_dir = skill.skill_path / "references"
    if not refs_dir.is_dir() or not skill.reference_files:
        return MetricResult(
            name="reference_freshness", score=0, max_score=20.0,
            details="references/ 없음", passed=False,
        )

    existing = sum(1 for f in skill.reference_files if (refs_dir / f).exists())
    total = len(skill.reference_files)
    ratio = existing / total if total > 0 else 0

    if ratio == 1.0:
        score = 20
    elif ratio >= 0.8:
        score = 15
    else:
        score = int(ratio * 20)

    return MetricResult(
        name="reference_freshness",
        score=score, max_score=20.0,
        details=f"실존 {existing}/{total} ({ratio:.0%})",
        passed=ratio >= 0.8,
    )


def evaluate_l3(skill: SkillMetadata) -> LayerResult:
    """L3 검색 전체 평가."""
    result = LayerResult(layer="L3", skill_name=skill.name)
    result.metrics = [
        check_reference_count(skill),
        check_reference_type_coverage(skill),
        check_progressive_disclosure(skill),
        check_reference_freshness(skill),
    ]
    result.compute_score()
    for m in result.metrics:
        if not m.passed:
            result.recommendations.append(f"{m.name}: {m.details}")
    return result


# ──────────────────────────────────────────────
# L5: 실행 평가 (정적 분석)
# ──────────────────────────────────────────────

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
    scripts_dir = skill.skill_path / "scripts"
    if not scripts_dir.is_dir():
        return MetricResult(
            name="shebang", score=0, max_score=10.0,
            details="scripts/ 없음", passed=False,
        )

    total = 0
    with_shebang = 0
    for py_file in scripts_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        total += 1
        try:
            first_line = py_file.read_text(encoding="utf-8").split("\n", 1)[0]
            if first_line.startswith("#!"):
                with_shebang += 1
        except (UnicodeDecodeError, PermissionError):
            pass

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
    scripts_dir = skill.skill_path / "scripts"
    if not scripts_dir.is_dir():
        return MetricResult(
            name="cli_interface", score=0, max_score=10.0,
            details="scripts/ 없음", passed=False,
        )

    has_argparse = False
    has_help = False
    for py_file in scripts_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            if "argparse" in content or "ArgumentParser" in content:
                has_argparse = True
            if "--help" in content or "add_argument" in content:
                has_help = True
        except (UnicodeDecodeError, PermissionError):
            pass

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
    scripts_dir = skill.skill_path / "scripts"
    if not scripts_dir.is_dir():
        return MetricResult(
            name="docstrings", score=0, max_score=10.0,
            details="scripts/ 없음", passed=False,
        )

    total = 0
    with_doc = 0
    for py_file in scripts_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        total += 1
        try:
            content = py_file.read_text(encoding="utf-8").lstrip()
            # shebang 건너뛰기
            if content.startswith("#!"):
                content = content.split("\n", 1)[-1].lstrip()
            if content.startswith('"""') or content.startswith("'''"):
                with_doc += 1
        except (UnicodeDecodeError, PermissionError):
            pass

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

    # required_patterns: 스크립트에 반드시 있어야 할 패턴
    for item in bench.get("required_patterns", []):
        total += 1
        target_file = scripts_dir / item["file"]
        if target_file.exists():
            content = target_file.read_text(encoding="utf-8")
            if re.search(item["pattern"], content):
                correct += 1

    # forbidden_patterns: 스크립트에 있으면 안 되는 패턴
    for item in bench.get("forbidden_patterns", []):
        total += 1
        target_file = scripts_dir / item["file"]
        if target_file.exists():
            content = target_file.read_text(encoding="utf-8")
            if not re.search(item["pattern"], content):
                correct += 1
        else:
            correct += 1  # 파일 없으면 위반 아님

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


def evaluate_l5(skill: SkillMetadata, benchmarks_dir: Path = None) -> LayerResult:
    """L5 실행 전체 평가."""
    result = LayerResult(layer="L5", skill_name=skill.name)
    metrics = [
        check_script_count(skill),
        check_shebang(skill),
        check_cli_interface(skill),
        check_docstrings(skill),
        check_bridge_availability(skill),
    ]

    # 벤치마크 메트릭 추가 (있을 때만 점수에 반영)
    if benchmarks_dir:
        bench_result = check_script_benchmark(skill, benchmarks_dir)
        if bench_result.max_score > 0:
            metrics.append(bench_result)

    result.metrics = metrics
    result.compute_score()
    for m in result.metrics:
        if not m.passed:
            result.recommendations.append(f"{m.name}: {m.details}")
    return result


# ──────────────────────────────────────────────
# Layer 레지스트리
# ──────────────────────────────────────────────

LAYERS = {
    "L1": evaluate_l1,
    "L2": evaluate_l2,
    "L3": evaluate_l3,
    "L4": evaluate_l4,
    "L5": evaluate_l5,
    "L6": evaluate_l6,
}


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def _load_config(config_path: Path) -> dict:
    """config.json 로드. 없으면 빈 dict."""
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def main():
    default_config = Path(__file__).parent.parent / "config.json"

    parser = argparse.ArgumentParser(description="Skill Evaluator")
    parser.add_argument(
        "--skills-root", type=Path, default=None,
        help="Root directory containing skills (each with SKILL.md)",
    )
    parser.add_argument(
        "--skill", type=str, default=None,
        help="Evaluate a specific skill by name",
    )
    parser.add_argument(
        "--layer", type=str, default=None,
        help="Comma-separated layers to evaluate (e.g. L1,L4,L6). Default: all",
    )
    parser.add_argument(
        "--format", choices=["text", "json", "markdown"], default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--output", "-o", type=Path, default=None,
        help="Save output to file",
    )
    parser.add_argument(
        "--ci-mode", action="store_true",
        help="Exit with code 1 if any skill below threshold",
    )
    parser.add_argument(
        "--threshold", type=float, default=None,
        help="Minimum passing score (default: from config or 60.0)",
    )
    parser.add_argument(
        "--config", type=Path, default=default_config,
        help="Config file path",
    )
    parser.add_argument(
        "--benchmarks", type=Path, default=None,
        help="Benchmarks directory for L2/L5 dynamic evaluation",
    )
    args = parser.parse_args()

    # Config 로드
    config = _load_config(args.config)

    # skills-root: CLI > env > config
    env_root = os.environ.get("SKILLS_ROOT", "")
    config_root = config.get("skills_root", "")
    raw = args.skills_root or (Path(env_root) if env_root else None) or (Path(config_root) if config_root else None)
    skills_root = raw
    if not skills_root or not skills_root.is_dir():
        print("Error: --skills-root required (or set in config.json / SKILLS_ROOT env)", file=sys.stderr)
        sys.exit(1)

    threshold = args.threshold or config.get("threshold", 60.0)

    # 레이어 결정
    if args.layer:
        layer_ids = [l.strip().upper() for l in args.layer.split(",")]
        for lid in layer_ids:
            if lid not in LAYERS:
                print(f"Unknown layer: {lid}. Available: {', '.join(LAYERS)}", file=sys.stderr)
                sys.exit(1)
    else:
        layer_ids = list(LAYERS.keys())

    # 스킬 탐지
    skills = discover_skills(skills_root)
    if not skills:
        print(f"No skills found in {skills_root}", file=sys.stderr)
        sys.exit(1)

    if args.skill:
        skills = [s for s in skills if s.name == args.skill]
        if not skills:
            print(f"Skill '{args.skill}' not found", file=sys.stderr)
            sys.exit(1)

    # 벤치마크 경로
    benchmarks_dir = args.benchmarks or Path(__file__).parent.parent / "benchmarks"

    # 평가: {skill_name: {layer_id: LayerResult}}
    results = {}
    for skill in skills:
        results[skill.name] = {}
        for lid in layer_ids:
            if lid == "L2":
                results[skill.name][lid] = LAYERS[lid](skill, all_skills=skills, benchmarks_dir=benchmarks_dir)
            elif lid == "L5":
                results[skill.name][lid] = LAYERS[lid](skill, benchmarks_dir=benchmarks_dir)
            else:
                results[skill.name][lid] = LAYERS[lid](skill)

    # 출력
    formatters = {"text": format_text, "json": format_json, "markdown": format_markdown}
    output = formatters[args.format](results)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(f"Saved to {args.output}")
    else:
        print(output)

    # CI 모드
    if args.ci_mode:
        failed = []
        for skill_name, layer_results in results.items():
            w = weighted_score(layer_results)
            if w < threshold:
                failed.append((skill_name, w))
        if failed:
            print(f"\nCI FAILED: {len(failed)} skill(s) below {threshold}:", file=sys.stderr)
            for name, score in failed:
                print(f"  {name}: {score:.1f}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"\nCI PASSED: All skills above {threshold}", file=sys.stderr)


if __name__ == "__main__":
    main()
