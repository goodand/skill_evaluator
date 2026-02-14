"""평가 설정 로더 및 기본값."""

import json
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_LAYER_WEIGHTS = {
    "L1": 0.20,
    "L2": 0.15,
    "L3": 0.15,
    "L4": 0.15,
    "L5": 0.25,
    "L6": 0.10,
}


@dataclass
class EvalConfig:
    """평가 실행에 필요한 설정."""

    skills_root: str = ""
    threshold: float = 60.0
    layer_weights: dict = field(default_factory=lambda: dict(DEFAULT_LAYER_WEIGHTS))


def load_eval_config(config_path: Path) -> EvalConfig:
    """config.json을 로드해 EvalConfig를 반환."""
    if not config_path.exists():
        return EvalConfig()

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    merged_weights = dict(DEFAULT_LAYER_WEIGHTS)
    merged_weights.update(raw.get("layer_weights", {}))

    return EvalConfig(
        skills_root=raw.get("skills_root", ""),
        threshold=raw.get("threshold", 60.0),
        layer_weights=merged_weights,
    )

