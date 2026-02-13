"""L2: 활성화 신뢰성 평가 (정적 분석)."""

import json
import re
from pathlib import Path

from models import MetricResult
from discovery import SkillMetadata
from evaluators.base import run_layer_evaluation


# 범용 키워드 — 도메인 특이성 판별용
GENERIC_KEYWORDS = {
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

    generic = sum(1 for kw in keywords if kw.lower() in GENERIC_KEYWORDS)
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

    for item in bench.get("positive", []):
        total += 1
        query = item["query"].lower()
        if any(kw in query for kw in keywords):
            correct += 1

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


def evaluate(skill: SkillMetadata, all_skills: list = None, benchmarks_dir: Path = None, **kwargs) -> 'LayerResult':
    """L2 활성화 전체 평가."""
    metrics = [
        check_trigger_count(skill),
        check_trigger_specificity(skill),
        check_trigger_overlap(skill, all_skills or []),
    ]

    if benchmarks_dir:
        bench_result = check_trigger_benchmark(skill, benchmarks_dir)
        if bench_result.max_score > 0:
            metrics.append(bench_result)

    return run_layer_evaluation("L2", skill, metrics)
