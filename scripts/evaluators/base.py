"""Evaluator 공통 유틸리티.

모든 Layer evaluator가 재사용하는 패턴:
  - run_layer_evaluation(): check_* 리스트 → LayerResult 생성
  - read_skill_md(): SKILL.md 텍스트 캐싱 읽기
  - read_scripts(): scripts/*.py 콘텐츠 일괄 읽기
"""

import re
from pathlib import Path
from typing import Callable, List, Optional

from models import MetricResult, LayerResult
from discovery import SkillMetadata


def run_layer_evaluation(
    layer_id: str,
    skill: SkillMetadata,
    metrics: List[MetricResult],
) -> LayerResult:
    """공통 Layer 평가 실행 — 점수 계산 + 권장사항 수집."""
    result = LayerResult(layer=layer_id, skill_name=skill.name)
    result.metrics = metrics
    result.compute_score()
    for m in result.metrics:
        if not m.passed:
            result.recommendations.append(f"{m.name}: {m.details}")
    return result


def read_skill_md(skill: SkillMetadata) -> str:
    """SKILL.md 텍스트 반환. 없으면 빈 문자열."""
    skill_md = skill.skill_path / "SKILL.md"
    if not skill_md.exists():
        return ""
    return skill_md.read_text(encoding="utf-8")


def iter_scripts(skill: SkillMetadata, skip_init: bool = True):
    """scripts/*.py 파일을 순회하며 (Path, content) 튜플 yield.

    UnicodeDecodeError, PermissionError는 자동 건너뜀.
    """
    scripts_dir = skill.skill_path / "scripts"
    if not scripts_dir.is_dir():
        return
    for py_file in scripts_dir.rglob("*.py"):
        if skip_init and py_file.name == "__init__.py":
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
            yield py_file, content
        except (UnicodeDecodeError, PermissionError):
            pass


def has_scripts_dir(skill: SkillMetadata) -> bool:
    """scripts/ 디렉토리 존재 여부."""
    return (skill.skill_path / "scripts").is_dir()
