"""models.py 단위 테스트."""

import pytest
from pathlib import Path

from models import MetricResult, LayerResult, SkillMetadata, TriggerInfo


# ──────────────────────────────────────────────
# MetricResult
# ──────────────────────────────────────────────

class TestMetricResult:
    """MetricResult 데이터 클래스 생성 및 기본값 테스트."""

    def test_create_basic(self):
        m = MetricResult(name="test_metric", score=8.0, max_score=10.0, details="ok")
        assert m.name == "test_metric"
        assert m.score == 8.0
        assert m.max_score == 10.0
        assert m.details == "ok"
        assert m.passed is True  # default

    def test_create_with_passed_false(self):
        m = MetricResult(
            name="failing", score=2.0, max_score=10.0,
            details="below threshold", passed=False,
        )
        assert m.passed is False

    def test_zero_score(self):
        m = MetricResult(name="zero", score=0.0, max_score=10.0, details="nothing")
        assert m.score == 0.0

    def test_full_score(self):
        m = MetricResult(name="full", score=30.0, max_score=30.0, details="perfect")
        assert m.score == m.max_score


# ──────────────────────────────────────────────
# LayerResult
# ──────────────────────────────────────────────

class TestLayerResult:
    """LayerResult.compute_score() 동작 검증."""

    def test_compute_score_empty_metrics(self):
        """메트릭이 없으면 0점."""
        lr = LayerResult(layer="L1", skill_name="test")
        lr.compute_score()
        assert lr.overall_score == 0.0

    def test_compute_score_single_perfect(self):
        """메트릭 1개, 만점이면 100."""
        lr = LayerResult(layer="L1", skill_name="test")
        lr.metrics = [MetricResult(name="m1", score=10.0, max_score=10.0, details="ok")]
        lr.compute_score()
        assert lr.overall_score == 100.0

    def test_compute_score_single_half(self):
        """메트릭 1개, 절반이면 50."""
        lr = LayerResult(layer="L1", skill_name="test")
        lr.metrics = [MetricResult(name="m1", score=5.0, max_score=10.0, details="half")]
        lr.compute_score()
        assert lr.overall_score == 50.0

    def test_compute_score_multiple_metrics(self):
        """다수 메트릭의 가중 평균 계산."""
        lr = LayerResult(layer="L1", skill_name="test")
        lr.metrics = [
            MetricResult(name="yaml", score=20.0, max_score=30.0, details=""),
            MetricResult(name="dir", score=30.0, max_score=40.0, details=""),
            MetricResult(name="res", score=25.0, max_score=30.0, details=""),
        ]
        lr.compute_score()
        # (20+30+25) / (30+40+30) * 100 = 75/100 * 100 = 75.0
        assert lr.overall_score == 75.0

    def test_compute_score_all_zero(self):
        """모든 메트릭 0점이면 0."""
        lr = LayerResult(layer="L1", skill_name="test")
        lr.metrics = [
            MetricResult(name="m1", score=0.0, max_score=30.0, details=""),
            MetricResult(name="m2", score=0.0, max_score=40.0, details=""),
        ]
        lr.compute_score()
        assert lr.overall_score == 0.0

    def test_compute_score_max_score_zero(self):
        """max_score 합이 0이면 0 (0으로 나누기 방지)."""
        lr = LayerResult(layer="L1", skill_name="test")
        lr.metrics = [MetricResult(name="m1", score=0.0, max_score=0.0, details="")]
        lr.compute_score()
        assert lr.overall_score == 0.0

    def test_default_fields(self):
        """기본 필드값 확인."""
        lr = LayerResult(layer="L1", skill_name="test")
        assert lr.metrics == []
        assert lr.overall_score == 0.0
        assert lr.recommendations == []

    def test_recommendations_list(self):
        """recommendations 필드가 독립 인스턴스인지 확인."""
        lr1 = LayerResult(layer="L1", skill_name="a")
        lr2 = LayerResult(layer="L1", skill_name="b")
        lr1.recommendations.append("fix X")
        assert lr2.recommendations == []


# ──────────────────────────────────────────────
# SkillMetadata
# ──────────────────────────────────────────────

class TestSkillMetadata:
    """SkillMetadata 데이터 클래스 생성 테스트."""

    def test_create_minimal(self):
        trigger = TriggerInfo(keywords=["test"], source="yaml_description")
        meta = SkillMetadata(
            name="my-skill",
            description="A test skill",
            skill_path=Path("/tmp/my-skill"),
            triggers=trigger,
        )
        assert meta.name == "my-skill"
        assert meta.description == "A test skill"
        assert meta.triggers.keywords == ["test"]
        assert meta.triggers.source == "yaml_description"
        assert meta.has_scripts_dir is False
        assert meta.has_references_dir is False
        assert meta.has_bridges_dir is False
        assert meta.has_tests_dir is False
        assert meta.has_design_decision is False
        assert meta.script_files == []
        assert meta.reference_files == []
        assert meta.skill_md_lines == 0

    def test_create_full(self):
        trigger = TriggerInfo(keywords=["debug", "troubleshoot"], source="both")
        meta = SkillMetadata(
            name="full-skill",
            description="Full featured",
            skill_path=Path("/tmp/full-skill"),
            triggers=trigger,
            has_scripts_dir=True,
            has_references_dir=True,
            has_bridges_dir=True,
            has_tests_dir=True,
            has_design_decision=True,
            script_files=["main.py", "utils.py"],
            reference_files=["guide.md"],
            skill_md_lines=150,
        )
        assert meta.has_scripts_dir is True
        assert meta.has_bridges_dir is True
        assert meta.has_tests_dir is True
        assert meta.has_design_decision is True
        assert len(meta.script_files) == 2
        assert len(meta.reference_files) == 1
        assert meta.skill_md_lines == 150

    def test_trigger_info_creation(self):
        t = TriggerInfo(keywords=["a", "b", "c"], source="markdown_section")
        assert len(t.keywords) == 3
        assert t.source == "markdown_section"

    def test_default_list_fields_independent(self):
        """기본 list 필드가 인스턴스 간 공유되지 않는지 확인."""
        trigger = TriggerInfo(keywords=[], source="yaml_description")
        m1 = SkillMetadata(
            name="s1", description="", skill_path=Path("/tmp/s1"), triggers=trigger,
        )
        m2 = SkillMetadata(
            name="s2", description="", skill_path=Path("/tmp/s2"), triggers=trigger,
        )
        m1.script_files.append("added.py")
        assert "added.py" not in m2.script_files
