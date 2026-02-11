"""Skill Evaluator 핵심 데이터 모델."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional


@dataclass
class TriggerInfo:
    """SKILL.md에서 추출한 트리거 정보."""
    keywords: List[str]
    source: str  # "yaml_description" | "markdown_section" | "both"


@dataclass
class SkillMetadata:
    """SKILL.md 파싱 + 파일시스템 스캔 결과."""
    name: str
    description: str
    skill_path: Path
    triggers: TriggerInfo
    has_scripts_dir: bool = False
    has_references_dir: bool = False
    has_bridges_dir: bool = False
    has_tests_dir: bool = False
    has_design_decision: bool = False
    script_files: List[str] = field(default_factory=list)
    reference_files: List[str] = field(default_factory=list)
    skill_md_lines: int = 0


@dataclass
class MetricResult:
    """개별 메트릭 측정 결과."""
    name: str
    score: float       # 0.0 - max_score
    max_score: float
    details: str
    passed: bool = True


@dataclass
class LayerResult:
    """단일 Layer 평가 결과."""
    layer: str         # L1, L2, ...
    skill_name: str
    metrics: List[MetricResult] = field(default_factory=list)
    overall_score: float = 0.0
    recommendations: List[str] = field(default_factory=list)

    def compute_score(self):
        """가용 메트릭으로 점수 계산 (0-100)."""
        if not self.metrics:
            self.overall_score = 0.0
            return
        total = sum(m.score for m in self.metrics)
        max_total = sum(m.max_score for m in self.metrics)
        self.overall_score = (total / max_total * 100) if max_total > 0 else 0.0
