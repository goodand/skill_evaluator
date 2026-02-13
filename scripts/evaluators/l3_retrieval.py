"""L3: 검색 품질 평가 (정적 분석)."""

import json
import re

from models import MetricResult
from discovery import SkillMetadata
from evaluators.base import run_layer_evaluation


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


def check_reference_content_validity(skill: SkillMetadata) -> MetricResult:
    """참조 파일 내용 품질 검증 (10점)."""
    refs_dir = skill.skill_path / "references"
    if not refs_dir.is_dir() or not skill.reference_files:
        return MetricResult(
            name="reference_content_validity", score=0, max_score=10.0,
            details="references/ 없음", passed=False,
        )

    score = 0.0
    details = []
    json_score = 0
    md_score = 0
    nonempty_score = 0

    for fname in skill.reference_files:
        fpath = refs_dir / fname
        if not fpath.exists():
            continue

        try:
            content = fpath.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue

        if len(content.strip()) > 0:
            nonempty_score += 1

        if fname.endswith(".json"):
            try:
                json.loads(content)
                json_score += 3
            except (json.JSONDecodeError, ValueError):
                details.append(f"{fname}: invalid JSON")

        if fname.endswith(".md"):
            lines = content.split("\n")
            has_heading = any(l.startswith("#") for l in lines)
            if len(lines) >= 10 and has_heading:
                md_score += 2
            elif len(lines) >= 5:
                md_score += 1

    json_score = min(json_score, 6)
    md_score = min(md_score, 6)
    nonempty_score = min(nonempty_score, 4)
    score = min(json_score + md_score + nonempty_score, 10)

    details.insert(0, f"json:{json_score} md:{md_score} nonempty:{nonempty_score}")

    return MetricResult(
        name="reference_content_validity",
        score=score, max_score=10.0,
        details="; ".join(details),
        passed=score >= 4,
    )


def evaluate(skill: SkillMetadata, **kwargs) -> 'LayerResult':
    """L3 검색 전체 평가."""
    return run_layer_evaluation("L3", skill, [
        check_reference_count(skill),
        check_reference_type_coverage(skill),
        check_progressive_disclosure(skill),
        check_reference_freshness(skill),
        check_reference_content_validity(skill),
    ])
