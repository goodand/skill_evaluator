"""Ecosystem: 크로스 스킬 분석."""

import re
from typing import List

from models import EcosystemMetric, EcosystemResult
from discovery import SkillMetadata
from evaluators.l2_activation import GENERIC_KEYWORDS


def check_bridge_connectivity(skills: List[SkillMetadata]) -> EcosystemMetric:
    """브릿지 연결 양방향 검증 (25점)."""
    score = 25.0
    details = []
    affected = []

    skill_names = {s.skill_path.name for s in skills}

    for skill in skills:
        bridge_files = []
        bridges_dir = skill.skill_path / "bridges"
        scripts_dir = skill.skill_path / "scripts"

        if bridges_dir.is_dir():
            bridge_files.extend(bridges_dir.rglob("*.py"))
            bridge_files.extend(bridges_dir.rglob("*.md"))
        if scripts_dir.is_dir():
            for f in scripts_dir.glob("bridge*.py"):
                bridge_files.append(f)

        for bf in bridge_files:
            try:
                content = bf.read_text(encoding="utf-8").lower()
            except (UnicodeDecodeError, PermissionError):
                continue
            for other_name in skill_names:
                if other_name == skill.skill_path.name:
                    continue
                if other_name.lower() in content:
                    other_skill = next((s for s in skills if s.skill_path.name == other_name), None)
                    if other_skill and skill.skill_path.name not in [t for t in other_skill.pipeline_targets]:
                        score -= 3
                        affected.append(f"{skill.name}→{other_name}")

    score = max(score, 0)
    if affected:
        details.append(f"단방향 연결 {len(affected)}건: {', '.join(affected[:5])}")
    else:
        details.append("모든 브릿지 연결 양호")

    return EcosystemMetric(
        name="bridge_connectivity", score=score, max_score=25.0,
        details="; ".join(details), affected_skills=affected,
    )


def check_cli_consistency(skills: List[SkillMetadata]) -> EcosystemMetric:
    """CLI 플래그 네이밍 일관성 (25점)."""
    flag_usage = {}

    for skill in skills:
        scripts_dir = skill.skill_path / "scripts"
        if not scripts_dir.is_dir():
            continue
        for py_file in scripts_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
            flags = re.findall(r"add_argument\(\s*['\"](-{1,2}[\w-]+)['\"]", content)
            for f in flags:
                flag_usage.setdefault(f, set()).add(skill.name)

    shared_flags = {f: s for f, s in flag_usage.items() if len(s) >= 2}
    if not shared_flags:
        return EcosystemMetric(
            name="cli_consistency", score=15, max_score=25.0,
            details="공유 플래그 없음 (비교 불가)", affected_skills=[],
        )

    inconsistencies = []
    all_flags = set(flag_usage.keys())
    pairs = [("--format", "-f"), ("--verbose", "-v"), ("--output", "-o")]
    for long_f, short_f in pairs:
        if long_f in all_flags and short_f in all_flags:
            long_skills = flag_usage[long_f]
            short_skills = flag_usage[short_f]
            if long_skills != short_skills:
                inconsistencies.append(f"{long_f}/{short_f}")

    score = 25 - len(inconsistencies) * 5
    score = max(score, 0)

    details = []
    details.append(f"공유 플래그 {len(shared_flags)}개")
    if inconsistencies:
        details.append(f"불일치: {', '.join(inconsistencies)}")
    else:
        details.append("네이밍 일관")

    return EcosystemMetric(
        name="cli_consistency", score=score, max_score=25.0,
        details="; ".join(details), affected_skills=inconsistencies,
    )


def check_pipeline_coverage(skills: List[SkillMetadata]) -> EcosystemMetric:
    """파이프라인 커버리지 — 고립 스킬 탐지 (25점)."""
    connected = set()
    for skill in skills:
        if skill.pipeline_targets:
            connected.add(skill.name)
            for target in skill.pipeline_targets:
                target_skill = next((s for s in skills if s.skill_path.name == target), None)
                if target_skill:
                    connected.add(target_skill.name)

    total = len(skills)
    isolated = [s.name for s in skills if s.name not in connected]
    coverage = len(connected) / total if total > 0 else 0

    score = round(coverage * 25)
    details = [f"연결 {len(connected)}/{total} ({coverage:.0%})"]
    if isolated:
        details.append(f"고립: {', '.join(isolated)}")

    return EcosystemMetric(
        name="pipeline_coverage", score=score, max_score=25.0,
        details="; ".join(details), affected_skills=isolated,
    )


def check_trigger_ecosystem_health(skills: List[SkillMetadata]) -> EcosystemMetric:
    """에코시스템 트리거 건강도 (25점)."""
    all_keywords = {}
    generic_count = 0
    total_count = 0

    for skill in skills:
        for kw in skill.triggers.keywords:
            kw_lower = kw.lower()
            all_keywords.setdefault(kw_lower, []).append(skill.name)
            total_count += 1
            if kw_lower in GENERIC_KEYWORDS:
                generic_count += 1

    overlapping = {k: v for k, v in all_keywords.items() if len(v) >= 2}
    overlap_ratio = len(overlapping) / len(all_keywords) if all_keywords else 0
    generic_ratio = generic_count / total_count if total_count > 0 else 0

    score = 25.0
    details = []

    if overlap_ratio > 0.2:
        score -= 10
        details.append(f"중복 키워드 {len(overlapping)}개 ({overlap_ratio:.0%})")
    elif overlap_ratio > 0.1:
        score -= 5
        details.append(f"중복 키워드 {len(overlapping)}개 ({overlap_ratio:.0%})")
    else:
        details.append(f"중복 키워드 적음 ({overlap_ratio:.0%})")

    if generic_ratio > 0.3:
        score -= 5
        details.append(f"범용 키워드 높음 ({generic_ratio:.0%})")
    else:
        details.append(f"범용 키워드 적정 ({generic_ratio:.0%})")

    score = max(score, 0)

    return EcosystemMetric(
        name="trigger_ecosystem_health", score=score, max_score=25.0,
        details="; ".join(details),
        affected_skills=[k for k in list(overlapping.keys())[:5]],
    )


def evaluate_ecosystem(skills: List[SkillMetadata]) -> EcosystemResult:
    """에코시스템 전체 평가."""
    result = EcosystemResult()
    result.metrics = [
        check_bridge_connectivity(skills),
        check_cli_consistency(skills),
        check_pipeline_coverage(skills),
        check_trigger_ecosystem_health(skills),
    ]
    result.compute_score()
    for m in result.metrics:
        if m.score < m.max_score * 0.6:
            result.recommendations.append(f"{m.name}: {m.details}")
    return result
