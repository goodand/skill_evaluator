"""reporter.py 단위 테스트 — format_text, format_json, format_markdown, weighted_score."""

import json
import pytest

from models import MetricResult, LayerResult, EcosystemMetric, EcosystemResult
from reporter import format_text, format_json, format_markdown, weighted_score


# ──────────────────────────────────────────────
# 헬퍼: 테스트용 결과 생성
# ──────────────────────────────────────────────

def _make_layer_result(layer="L1", skill_name="test-skill", metrics=None, score=None):
    """단일 LayerResult 생성."""
    lr = LayerResult(layer=layer, skill_name=skill_name)
    lr.metrics = metrics or [
        MetricResult(name="yaml_validity", score=25.0, max_score=30.0, details="ok", passed=True),
        MetricResult(name="directory_structure", score=30.0, max_score=40.0, details="good", passed=True),
        MetricResult(name="resource_independence", score=20.0, max_score=30.0, details="some issues", passed=True),
    ]
    lr.compute_score()
    return lr


def _make_results_single_layer():
    """단일 레이어 results dict: {skill_name: {lid: LayerResult}}."""
    lr = _make_layer_result()
    return {"test-skill": {"L1": lr}}


def _make_results_multi_layer():
    """멀티 레이어 results dict."""
    l1 = _make_layer_result("L1", "alpha")
    l4 = LayerResult(layer="L4", skill_name="alpha")
    l4.metrics = [
        MetricResult(name="workflow_structure", score=40.0, max_score=60.0, details="ok", passed=True),
        MetricResult(name="plan_adherence", score=20.0, max_score=40.0, details="ok", passed=True),
    ]
    l4.compute_score()
    return {"alpha": {"L1": l1, "L4": l4}}


def _make_ecosystem():
    """테스트용 EcosystemResult."""
    eco = EcosystemResult()
    eco.metrics = [
        EcosystemMetric(name="bridge_connectivity", score=25.0, max_score=25.0, details="모든 브릿지 연결 양호"),
        EcosystemMetric(name="cli_consistency", score=15.0, max_score=25.0, details="공유 플래그 없음"),
    ]
    eco.compute_score()
    return eco


# ──────────────────────────────────────────────
# weighted_score
# ──────────────────────────────────────────────

class TestWeightedScore:

    def test_single_layer(self):
        """단일 레이어 가중 점수."""
        lr = _make_layer_result()
        result = weighted_score({"L1": lr})
        # L1 weight = 0.20, score = 75.0
        assert result == 75.0

    def test_multi_layer(self):
        """멀티 레이어 가중 점수."""
        l1 = _make_layer_result("L1")
        l4 = LayerResult(layer="L4", skill_name="test")
        l4.metrics = [
            MetricResult(name="m1", score=50.0, max_score=100.0, details="", passed=True),
        ]
        l4.compute_score()
        result = weighted_score({"L1": l1, "L4": l4})
        # L1: 75.0 * 0.20 = 15.0, L4: 50.0 * 0.15 = 7.5
        # total_weight = 0.35, weighted_sum = 22.5
        # 22.5 / 0.35 = 64.28...
        assert abs(result - 64.3) < 0.1

    def test_empty_layers(self):
        """빈 레이어 dict = 0."""
        assert weighted_score({}) == 0.0

    def test_custom_layer_weights(self):
        """커스텀 가중치 적용."""
        l1 = _make_layer_result("L1")
        l4 = LayerResult(layer="L4", skill_name="test")
        l4.metrics = [MetricResult(name="m1", score=50.0, max_score=100.0, details="", passed=True)]
        l4.compute_score()
        result = weighted_score(
            {"L1": l1, "L4": l4},
            layer_weights={"L1": 0.0, "L4": 1.0},
        )
        assert result == 50.0


# ──────────────────────────────────────────────
# format_text
# ──────────────────────────────────────────────

class TestFormatText:

    def test_contains_skill_name(self):
        results = _make_results_single_layer()
        text = format_text(results)
        assert "test-skill" in text

    def test_contains_header(self):
        results = _make_results_single_layer()
        text = format_text(results)
        assert "Skill Evaluator" in text

    def test_contains_layer_scores(self):
        results = _make_results_single_layer()
        text = format_text(results)
        assert "L1:" in text
        assert "PASS" in text

    def test_contains_weighted_score(self):
        results = _make_results_single_layer()
        text = format_text(results)
        assert "Weighted:" in text

    def test_contains_summary(self):
        results = _make_results_single_layer()
        text = format_text(results)
        assert "Total: 1 skills" in text
        assert "Weighted Avg:" in text

    def test_multi_layer_output(self):
        results = _make_results_multi_layer()
        text = format_text(results)
        assert "L1" in text
        assert "L4" in text
        assert "alpha" in text

    def test_with_ecosystem(self):
        results = _make_results_single_layer()
        eco = _make_ecosystem()
        text = format_text(results, ecosystem_result=eco)
        assert "Ecosystem Health" in text


# ──────────────────────────────────────────────
# format_json
# ──────────────────────────────────────────────

class TestFormatJson:

    def test_valid_json(self):
        results = _make_results_single_layer()
        json_str = format_json(results)
        data = json.loads(json_str)
        assert "skills" in data
        assert "summary" in data

    def test_skill_structure(self):
        results = _make_results_single_layer()
        data = json.loads(format_json(results))
        skill = data["skills"][0]
        assert skill["name"] == "test-skill"
        assert "layers" in skill
        assert "L1" in skill["layers"]
        assert "weighted_score" in skill

    def test_layer_metrics(self):
        results = _make_results_single_layer()
        data = json.loads(format_json(results))
        l1 = data["skills"][0]["layers"]["L1"]
        assert "score" in l1
        assert "metrics" in l1
        assert len(l1["metrics"]) == 3
        assert "recommendations" in l1

    def test_summary(self):
        results = _make_results_single_layer()
        data = json.loads(format_json(results))
        summary = data["summary"]
        assert summary["total_skills"] == 1
        assert "weighted_average" in summary
        assert "min" in summary
        assert "max" in summary

    def test_scores_match(self):
        results = _make_results_single_layer()
        data = json.loads(format_json(results))
        skill = data["skills"][0]
        # (25+30+20) / (30+40+30) * 100 = 75.0
        assert skill["layers"]["L1"]["score"] == 75.0

    def test_with_ecosystem(self):
        results = _make_results_single_layer()
        eco = _make_ecosystem()
        data = json.loads(format_json(results, ecosystem_result=eco))
        assert "ecosystem" in data
        assert "overall_score" in data["ecosystem"]
        assert "metrics" in data["ecosystem"]

    def test_custom_layer_weights_in_summary(self):
        results = _make_results_single_layer()
        data = json.loads(format_json(results, layer_weights={"L1": 1.0}))
        assert data["summary"]["layer_weights"] == {"L1": 1.0}


# ──────────────────────────────────────────────
# format_markdown
# ──────────────────────────────────────────────

class TestFormatMarkdown:

    def test_contains_title(self):
        results = _make_results_single_layer()
        md = format_markdown(results)
        assert "# Skill Evaluation Report" in md

    def test_contains_summary_table(self):
        results = _make_results_single_layer()
        md = format_markdown(results)
        assert "## Summary" in md
        assert "| Skill |" in md
        assert "test-skill" in md

    def test_contains_details(self):
        results = _make_results_single_layer()
        md = format_markdown(results)
        assert "## Details" in md

    def test_with_ecosystem(self):
        results = _make_results_single_layer()
        eco = _make_ecosystem()
        md = format_markdown(results, ecosystem_result=eco)
        assert "## Ecosystem Health" in md
