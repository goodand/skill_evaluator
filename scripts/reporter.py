"""평가 결과 출력 — Text, JSON, Markdown."""

import json
from datetime import datetime

from models import LayerResult, EcosystemResult
from eval_config import DEFAULT_LAYER_WEIGHTS


def weighted_score(layer_results: dict, layer_weights: dict = None) -> float:
    """가중 평균 점수 계산."""
    weights = layer_weights or DEFAULT_LAYER_WEIGHTS
    missing = sorted(lid for lid in layer_results.keys() if lid not in weights)
    if missing:
        raise ValueError(f"Missing layer weights for: {', '.join(missing)}")
    total_weight = 0.0
    weighted_sum = 0.0
    for lid, lr in layer_results.items():
        w = weights.get(lid, 0)
        weighted_sum += lr.overall_score * w
        total_weight += w
    return weighted_sum / total_weight if total_weight > 0 else 0.0


def _ecosystem_text(eco: EcosystemResult) -> str:
    """에코시스템 결과 텍스트 렌더링."""
    lines = [
        "=" * 60,
        f"Ecosystem Health: {eco.overall_score:.1f}/100",
        "=" * 60, "",
    ]
    for m in eco.metrics:
        status = "PASS" if m.score >= m.max_score * 0.6 else "WARN"
        lines.append(f"  {m.name}: {m.score:.0f}/{m.max_score:.0f} [{status}] - {m.details}")
    if eco.recommendations:
        lines.append("  Recommendations:")
        for r in eco.recommendations:
            lines.append(f"    - {r}")
    lines.append("")
    return "\n".join(lines)


def format_text(results: dict, ecosystem_result=None, layer_weights: dict = None) -> str:
    """Text 출력. results: {skill_name: {layer_id: LayerResult}}"""
    layers_used = sorted({lid for lrs in results.values() for lid in lrs})
    lines = ["=" * 60, f"Skill Evaluator - {', '.join(layers_used)}", "=" * 60, ""]

    for skill_name, layer_results in results.items():
        w_score = weighted_score(layer_results, layer_weights=layer_weights)
        lines.append(f"[{skill_name}] Weighted: {w_score:.1f}/100")

        for lid in layers_used:
            lr = layer_results.get(lid)
            if not lr:
                continue
            lines.append(f"  {lid}: {lr.overall_score:.1f}/100")
            for m in lr.metrics:
                status = "PASS" if m.passed else "FAIL"
                lines.append(f"    {m.name}: {m.score:.0f}/{m.max_score:.0f} [{status}] - {m.details}")

        all_recs = [r for lr in layer_results.values() for r in lr.recommendations]
        if all_recs:
            lines.append("  Recommendations:")
            for r in all_recs:
                lines.append(f"    - {r}")
        lines.append("")

    all_w = [weighted_score(lrs, layer_weights=layer_weights) for lrs in results.values()]
    avg = sum(all_w) / len(all_w) if all_w else 0
    lines.append("-" * 60)
    lines.append(f"Total: {len(results)} skills | Layers: {', '.join(layers_used)} | Weighted Avg: {avg:.1f}/100")
    lines.append("")

    if ecosystem_result:
        lines.append(_ecosystem_text(ecosystem_result))

    return "\n".join(lines)


def format_json(results: dict, ecosystem_result=None, layer_weights: dict = None) -> str:
    """JSON 출력."""
    weights = layer_weights or DEFAULT_LAYER_WEIGHTS
    output = {"timestamp": datetime.now().isoformat(), "skills": [], "summary": {}}

    for skill_name, layer_results in results.items():
        skill_data = {"name": skill_name, "layers": {}}
        for lid, lr in layer_results.items():
            skill_data["layers"][lid] = {
                "score": round(lr.overall_score, 1),
                "metrics": [
                    {"name": m.name, "score": m.score, "max_score": m.max_score,
                     "passed": m.passed, "details": m.details}
                    for m in lr.metrics
                ],
                "recommendations": lr.recommendations,
            }
        skill_data["weighted_score"] = round(weighted_score(layer_results, layer_weights=weights), 1)
        output["skills"].append(skill_data)

    all_w = [weighted_score(lrs, layer_weights=weights) for lrs in results.values()]
    output["summary"] = {
        "total_skills": len(results),
        "weighted_average": round(sum(all_w) / len(all_w), 1) if all_w else 0,
        "min": round(min(all_w), 1) if all_w else 0,
        "max": round(max(all_w), 1) if all_w else 0,
        "layer_weights": weights,
    }

    if ecosystem_result:
        output["ecosystem"] = {
            "overall_score": round(ecosystem_result.overall_score, 1),
            "metrics": [
                {"name": m.name, "score": m.score, "max_score": m.max_score,
                 "details": m.details, "affected_skills": m.affected_skills}
                for m in ecosystem_result.metrics
            ],
            "recommendations": ecosystem_result.recommendations,
        }

    return json.dumps(output, ensure_ascii=False, indent=2)


def format_markdown(results: dict, ecosystem_result=None, layer_weights: dict = None) -> str:
    """Markdown 리포트."""
    weights = layer_weights or DEFAULT_LAYER_WEIGHTS
    layers_used = sorted({lid for lrs in results.values() for lid in lrs})
    lines = [
        f"# Skill Evaluation Report",
        f"",
        f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> Layers: {', '.join(layers_used)}",
        f"> Weights: {', '.join(f'{k}={v:.0%}' for k, v in weights.items() if k in layers_used)}",
        f"",
    ]

    # 요약 테이블
    lines.append("## Summary")
    lines.append("")
    header = "| Skill | " + " | ".join(layers_used) + " | **Weighted** |"
    sep = "|-------|" + "|".join(["-----:" for _ in layers_used]) + "|----------:|"
    lines.append(header)
    lines.append(sep)

    for skill_name, layer_results in results.items():
        w = weighted_score(layer_results, layer_weights=weights)
        cells = [f"{layer_results[lid].overall_score:.0f}" if lid in layer_results else "-" for lid in layers_used]
        lines.append(f"| {skill_name} | " + " | ".join(cells) + f" | **{w:.1f}** |")

    all_w = [weighted_score(lrs, layer_weights=weights) for lrs in results.values()]
    avg = sum(all_w) / len(all_w) if all_w else 0
    lines.append(f"| **Average** | " + " | ".join(["" for _ in layers_used]) + f" | **{avg:.1f}** |")
    lines.append("")

    # 스킬별 상세
    lines.append("## Details")
    lines.append("")
    for skill_name, layer_results in results.items():
        w = weighted_score(layer_results, layer_weights=weights)
        lines.append(f"### {skill_name} ({w:.1f})")
        lines.append("")
        for lid in layers_used:
            lr = layer_results.get(lid)
            if not lr:
                continue
            lines.append(f"**{lid}**: {lr.overall_score:.1f}/100")
            lines.append("")
            for m in lr.metrics:
                icon = "+" if m.passed else "-"
                lines.append(f"  - [{icon}] `{m.name}`: {m.score:.0f}/{m.max_score:.0f} — {m.details}")
            lines.append("")

        all_recs = [r for lr in layer_results.values() for r in lr.recommendations]
        if all_recs:
            lines.append("**Recommendations:**")
            for r in all_recs:
                lines.append(f"- {r}")
            lines.append("")

    # 에코시스템
    if ecosystem_result:
        lines.append("## Ecosystem Health")
        lines.append("")
        lines.append(f"**Overall: {ecosystem_result.overall_score:.1f}/100**")
        lines.append("")
        lines.append("| Metric | Score | Details |")
        lines.append("|--------|------:|---------|")
        for m in ecosystem_result.metrics:
            lines.append(f"| {m.name} | {m.score:.0f}/{m.max_score:.0f} | {m.details} |")
        lines.append("")
        if ecosystem_result.recommendations:
            lines.append("**Ecosystem Recommendations:**")
            for r in ecosystem_result.recommendations:
                lines.append(f"- {r}")
            lines.append("")

    return "\n".join(lines)
