"""EvalConfig 로더 (IO 전담)."""

import json
from pathlib import Path

from eval_config import EvalConfig, DEFAULT_LAYER_WEIGHTS


def _validate_layer_weights(weights: dict):
    """layer_weights 유효성 검증."""
    unknown = sorted(k for k in weights.keys() if k not in DEFAULT_LAYER_WEIGHTS)
    if unknown:
        raise ValueError(f"Unknown layer weight keys: {', '.join(unknown)}")
    for lid, v in weights.items():
        if not isinstance(v, (int, float)):
            raise ValueError(f"Layer weight for {lid} must be numeric")
        if v < 0:
            raise ValueError(f"Layer weight for {lid} must be non-negative")


def load_eval_config(config_path: Path) -> EvalConfig:
    """config.json을 로드해 EvalConfig를 반환."""
    if not config_path.exists():
        return EvalConfig()

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    raw_weights = raw.get("layer_weights", {})
    _validate_layer_weights(raw_weights)
    merged_weights = dict(DEFAULT_LAYER_WEIGHTS)
    merged_weights.update(raw_weights)

    return EvalConfig(
        skills_root=raw.get("skills_root", ""),
        threshold=raw.get("threshold", 60.0),
        layer_weights=merged_weights,
    )
