"""L6: 검증 커버리지 평가."""

import re

from models import MetricResult
from discovery import SkillMetadata
from evaluators.base import run_layer_evaluation, iter_scripts, read_skill_md


def check_verification_infra(skill: SkillMetadata) -> MetricResult:
    """검증 인프라 (50점)."""
    score = 0.0
    details = []

    if skill.has_tests_dir:
        score += 20
        details.append("tests/ 존재")

    scripts_dir = skill.skill_path / "scripts"
    if scripts_dir.is_dir():
        for py_file, content in iter_scripts(skill, skip_init=False):
            if re.search(r'--verify|--check|--validate', content):
                score += 15
                details.append(f"검증 플래그 ({py_file.name})")
                break

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
    if not (skill.skill_path / "scripts").is_dir():
        return MetricResult(
            name="error_handling", score=0, max_score=30.0,
            details="scripts/ 없음", passed=False,
        )

    score = 0.0
    details = []
    has_try = False
    has_specific = False
    has_exit = False

    for _, content in iter_scripts(skill, skip_init=False):
        if "try:" in content:
            has_try = True
        if re.search(r'except\s+\w+', content):
            has_specific = True
        if "sys.exit" in content:
            has_exit = True

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

    for ref in skill.reference_files:
        if re.search(r'output|format|schema', ref, re.IGNORECASE):
            score += 10
            details.append(f"출력 형식 문서 ({ref})")
            break

    for ref in skill.reference_files:
        if re.search(r'example|sample', ref, re.IGNORECASE):
            score += 5
            details.append(f"예시 파일 ({ref})")
            break

    text = read_skill_md(skill)
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


def evaluate(skill: SkillMetadata, **kwargs) -> 'LayerResult':
    """L6 검증 전체 평가."""
    return run_layer_evaluation("L6", skill, [
        check_verification_infra(skill),
        check_error_handling(skill),
        check_faithfulness(skill),
    ])
