"""평가 설정 데이터 모델 및 기본값."""

from dataclasses import dataclass, field


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
