"""L1: 구조적 무결성 평가."""

import re

from models import MetricResult
from discovery import SkillMetadata
from evaluators.base import run_layer_evaluation, iter_scripts


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
    uses_relative = False

    for py_file, content in iter_scripts(skill, skip_init=False):
        matches = hardcoded_pattern.findall(content)
        if matches:
            score -= 10
            violations.append(py_file.name)
        if "Path(__file__)" in content or "SKILLS_ROOT" in content or "skill_paths" in content:
            uses_relative = True

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


def evaluate(skill: SkillMetadata, **kwargs) -> 'LayerResult':
    """L1 구조적 무결성 전체 평가."""
    return run_layer_evaluation("L1", skill, [
        check_yaml_validity(skill),
        check_directory_structure(skill),
        check_resource_independence(skill),
    ])
