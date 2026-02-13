"""L4: 워크플로우 충실도 평가."""

import re

from models import MetricResult
from discovery import SkillMetadata
from evaluators.base import run_layer_evaluation, read_skill_md


def check_workflow_structure(skill: SkillMetadata) -> MetricResult:
    """워크플로우 구조 감지 (60점)."""
    text = read_skill_md(skill)

    score = 0.0
    details = []

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

    # ASCII 파이프라인 다이어그램
    if re.search(r'──►|──>|───▶|→.*→', text):
        score += 10
        details.append("파이프라인 다이어그램")

    # mermaid 블록
    if '```mermaid' in text:
        score += 5
        details.append("Mermaid 다이어그램")

    # 테이블 기반 라우팅
    if re.search(r'\|.*커맨드.*\||\|.*[Cc]ommand.*\||\|.*모드.*\|', text):
        score += 5
        details.append("테이블 라우팅")

    return MetricResult(
        name="workflow_structure",
        score=min(score, 60.0),
        max_score=60.0,
        details="; ".join(details),
        passed=score >= 20,
    )


def check_plan_adherence(skill: SkillMetadata) -> MetricResult:
    """계획 준수 마커 감지 (40점)."""
    text = read_skill_md(skill)

    score = 0.0
    details = []

    checklists = re.findall(r'- \[[ x]\]', text)
    if checklists:
        score += 8
        details.append(f"체크리스트 {len(checklists)}개")

    if re.search(r'자가\s*점검|self[- ]?check', text, re.IGNORECASE):
        score += 10
        details.append("자가 점검 섹션")

    if skill.has_when_to_use:
        score += 5
        details.append("When to Use 섹션")
    if skill.has_dont_use:
        score += 5
        details.append("Don't Use 섹션")

    if re.search(r'전환|transition|다음\s*단계|next\s*phase', text, re.IGNORECASE):
        score += 3
        details.append("단계 전환 기준")

    if skill.has_quick_start:
        score += 3
        details.append("Quick Start 섹션")

    if skill.has_llm_judgment_guide:
        score += 4
        details.append("LLM 판단 가이드")

    if skill.has_prerequisites:
        score += 2
        details.append("Prerequisites 섹션")

    if not details:
        details.append("계획 준수 마커 없음")

    return MetricResult(
        name="plan_adherence",
        score=min(score, 40.0),
        max_score=40.0,
        details="; ".join(details),
        passed=score >= 10,
    )


def evaluate(skill: SkillMetadata, **kwargs) -> 'LayerResult':
    """L4 워크플로우 전체 평가."""
    return run_layer_evaluation("L4", skill, [
        check_workflow_structure(skill),
        check_plan_adherence(skill),
    ])
