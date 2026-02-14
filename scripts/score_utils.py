"""점수 계산/요약 집계 유틸리티."""

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


def summarize_results(results: dict, layer_weights: dict = None) -> dict:
    """평가 결과 요약 집계."""
    weights = layer_weights or DEFAULT_LAYER_WEIGHTS
    all_w = [weighted_score(lrs, layer_weights=weights) for lrs in results.values()]
    error_count = 0
    for layer_results in results.values():
        for lr in layer_results.values():
            if any(m.name == "runtime_error" for m in lr.metrics):
                error_count += 1
    return {
        "total_skills": len(results),
        "weighted_average": round(sum(all_w) / len(all_w), 1) if all_w else 0,
        "min": round(min(all_w), 1) if all_w else 0,
        "max": round(max(all_w), 1) if all_w else 0,
        "layer_weights": weights,
        "error_count": error_count,
    }

