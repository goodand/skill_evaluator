"""ecosystem.py 단위 테스트 — 크로스 스킬 분석."""

import pytest

from models import EcosystemResult, EcosystemMetric
from helpers import make_skill

from evaluators.ecosystem import (
    check_bridge_connectivity,
    check_cli_consistency,
    check_pipeline_coverage,
    check_trigger_ecosystem_health,
    evaluate_ecosystem,
)


# ──────────────────────────────────────────────
# check_bridge_connectivity
# ──────────────────────────────────────────────

class TestBridgeConnectivity:

    def test_no_bridges(self, tmp_path):
        """브릿지 없으면 만점."""
        s1 = make_skill(tmp_path, name="s1", create_scripts=True)
        s2 = make_skill(tmp_path, name="s2", create_scripts=True)
        result = check_bridge_connectivity([s1, s2])
        assert result.score == 25.0
        assert result.name == "bridge_connectivity"

    def test_single_skill(self, tmp_path):
        """스킬 1개면 연결 체크 불필요."""
        s1 = make_skill(tmp_path, name="s1")
        result = check_bridge_connectivity([s1])
        assert result.score == 25.0


# ──────────────────────────────────────────────
# check_cli_consistency
# ──────────────────────────────────────────────

class TestCliConsistency:

    def test_no_shared_flags(self, tmp_path):
        """공유 플래그 없으면 비교 불가 → 15점."""
        s1 = make_skill(
            tmp_path, name="cli-s1",
            script_contents={"main.py": "parser.add_argument('--input')"},
        )
        s2 = make_skill(
            tmp_path, name="cli-s2",
            script_contents={"main.py": "parser.add_argument('--output')"},
        )
        result = check_cli_consistency([s1, s2])
        assert result.score == 15

    def test_consistent_flags(self, tmp_path):
        """동일한 플래그 사용 시 만점."""
        s1 = make_skill(
            tmp_path, name="con-s1",
            script_contents={"main.py": "parser.add_argument('--format')\nparser.add_argument('--verbose')"},
        )
        s2 = make_skill(
            tmp_path, name="con-s2",
            script_contents={"main.py": "parser.add_argument('--format')\nparser.add_argument('--verbose')"},
        )
        result = check_cli_consistency([s1, s2])
        assert result.score == 25


# ──────────────────────────────────────────────
# check_pipeline_coverage
# ──────────────────────────────────────────────

class TestPipelineCoverage:

    def test_all_isolated(self, tmp_path):
        """모든 스킬 고립 → 0점."""
        s1 = make_skill(tmp_path, name="iso-1")
        s2 = make_skill(tmp_path, name="iso-2")
        result = check_pipeline_coverage([s1, s2])
        assert result.score == 0

    def test_single_skill(self, tmp_path):
        """스킬 1개 고립 → coverage 0."""
        s1 = make_skill(tmp_path, name="solo")
        result = check_pipeline_coverage([s1])
        assert result.score == 0


# ──────────────────────────────────────────────
# check_trigger_ecosystem_health
# ──────────────────────────────────────────────

class TestTriggerEcosystemHealth:

    def test_no_overlap(self, tmp_path):
        """중복 없으면 만점에 가까움."""
        s1 = make_skill(tmp_path, name="eco-1", triggers=["alpha", "beta"])
        s2 = make_skill(tmp_path, name="eco-2", triggers=["gamma", "delta"])
        result = check_trigger_ecosystem_health([s1, s2])
        assert result.score >= 20

    def test_high_overlap(self, tmp_path):
        """높은 중복 시 감점."""
        s1 = make_skill(tmp_path, name="dup-1", triggers=["shared1", "shared2", "unique1"])
        s2 = make_skill(tmp_path, name="dup-2", triggers=["shared1", "shared2", "unique2"])
        result = check_trigger_ecosystem_health([s1, s2])
        assert result.score < 25  # 중복으로 감점

    def test_generic_keywords(self, tmp_path):
        """범용 키워드 많으면 감점."""
        s1 = make_skill(tmp_path, name="gen-1", triggers=["분석", "도와줘", "확인", "help"])
        result = check_trigger_ecosystem_health([s1])
        assert result.score < 25


# ──────────────────────────────────────────────
# evaluate_ecosystem
# ──────────────────────────────────────────────

class TestEvaluateEcosystem:

    def test_returns_ecosystem_result(self, tmp_path):
        s1 = make_skill(tmp_path, name="eco-s1", triggers=["a"], create_scripts=True)
        s2 = make_skill(tmp_path, name="eco-s2", triggers=["b"], create_scripts=True)
        result = evaluate_ecosystem([s1, s2])
        assert isinstance(result, EcosystemResult)
        assert len(result.metrics) == 4
        assert result.overall_score >= 0

    def test_metric_names(self, tmp_path):
        s1 = make_skill(tmp_path, name="eco-n1", triggers=["x"])
        result = evaluate_ecosystem([s1])
        names = [m.name for m in result.metrics]
        assert "bridge_connectivity" in names
        assert "cli_consistency" in names
        assert "pipeline_coverage" in names
        assert "trigger_ecosystem_health" in names
