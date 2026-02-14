"""EvalConfig 로더 (IO 전담)."""

import json
from pathlib import Path

from eval_config import EvalConfig, DEFAULT_LAYER_WEIGHTS


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

