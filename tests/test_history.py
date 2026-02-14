"""history.py 단위 테스트 — 스냅샷 저장/로드/비교."""

import json
import pytest
from pathlib import Path

from models import MetricResult, LayerResult
from history import (
    _build_snapshot,
    save_snapshot,
    load_history,
    get_latest,
    compute_diff,
    format_diff_text,
    format_history_text,
)


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────

def _make_results():
    """테스트용 results dict: {skill_name: {lid: LayerResult}}."""
    lr = LayerResult(layer="L1", skill_name="alpha")
    lr.metrics = [
        MetricResult(name="m1", score=20.0, max_score=30.0, details="ok", passed=True),
        MetricResult(name="m2", score=30.0, max_score=40.0, details="ok", passed=True),
    ]
    lr.compute_score()
    return {"alpha": {"L1": lr}}


# ──────────────────────────────────────────────
# _build_snapshot
# ──────────────────────────────────────────────

class TestBuildSnapshot:

    def test_basic_snapshot(self):
        results = _make_results()
        snap = _build_snapshot(results)
        assert "timestamp" in snap
        assert "evaluator_version" in snap
        assert len(snap["evaluator_version"]) == 12
        assert "skills" in snap
        assert "summary" in snap
        assert "alpha" in snap["skills"]

    def test_skill_details(self):
        results = _make_results()
        snap = _build_snapshot(results)
        skill = snap["skills"]["alpha"]
        assert "weighted" in skill
        assert "layers" in skill
        assert "L1" in skill["layers"]

    def test_summary(self):
        results = _make_results()
        snap = _build_snapshot(results)
        summary = snap["summary"]
        assert "weighted_average" in summary
        assert "skill_count" in summary
        assert summary["skill_count"] == 1

    def test_with_ecosystem(self):
        from models import EcosystemResult, EcosystemMetric
        results = _make_results()
        eco = EcosystemResult()
        eco.metrics = [
            EcosystemMetric(name="m1", score=20.0, max_score=25.0, details="ok"),
        ]
        eco.compute_score()
        snap = _build_snapshot(results, eco)
        assert "ecosystem" in snap
        assert "overall_score" in snap["ecosystem"]


# ──────────────────────────────────────────────
# save_snapshot / load_history
# ──────────────────────────────────────────────

class TestSaveAndLoad:

    def test_save_creates_file(self, tmp_path):
        filepath = tmp_path / "history.jsonl"
        results = _make_results()
        returned = save_snapshot(results, filepath=filepath)
        assert returned == filepath
        assert filepath.exists()

    def test_load_after_save(self, tmp_path):
        filepath = tmp_path / "history.jsonl"
        results = _make_results()
        save_snapshot(results, filepath=filepath)
        history = load_history(filepath)
        assert len(history) == 1
        assert "skills" in history[0]

    def test_multiple_saves_append(self, tmp_path):
        filepath = tmp_path / "history.jsonl"
        results = _make_results()
        save_snapshot(results, filepath=filepath)
        save_snapshot(results, filepath=filepath)
        history = load_history(filepath)
        assert len(history) == 2

    def test_load_nonexistent(self, tmp_path):
        filepath = tmp_path / "nonexistent.jsonl"
        history = load_history(filepath)
        assert history == []


# ──────────────────────────────────────────────
# get_latest
# ──────────────────────────────────────────────

class TestGetLatest:

    def test_no_history(self, tmp_path):
        filepath = tmp_path / "empty.jsonl"
        assert get_latest(filepath) is None

    def test_with_history(self, tmp_path):
        filepath = tmp_path / "history.jsonl"
        results = _make_results()
        save_snapshot(results, filepath=filepath)
        save_snapshot(results, filepath=filepath)
        latest = get_latest(filepath)
        assert latest is not None
        assert "timestamp" in latest


# ──────────────────────────────────────────────
# compute_diff
# ──────────────────────────────────────────────

class TestComputeDiff:

    def test_same_snapshot(self):
        results = _make_results()
        baseline = _build_snapshot(results, evaluator_version="v-old")
        current = _build_snapshot(results, evaluator_version="v-old")
        diff = compute_diff(current, baseline)
        assert diff["summary"]["weighted_average"]["delta"] == 0
        assert diff["evaluator_version"]["changed"] is False
        assert diff["improved"] == []
        assert diff["regressed"] == []

    def test_improved(self):
        results = _make_results()
        baseline = _build_snapshot(results)

        # 점수 올린 버전
        lr2 = LayerResult(layer="L1", skill_name="alpha")
        lr2.metrics = [
            MetricResult(name="m1", score=30.0, max_score=30.0, details="ok", passed=True),
            MetricResult(name="m2", score=40.0, max_score=40.0, details="ok", passed=True),
        ]
        lr2.compute_score()
        current = _build_snapshot({"alpha": {"L1": lr2}})

        diff = compute_diff(current, baseline)
        assert diff["summary"]["weighted_average"]["delta"] > 0
        assert "alpha" in diff["improved"]

    def test_new_skill(self):
        results = _make_results()
        baseline = _build_snapshot(results)

        # 새 스킬 추가
        lr2 = LayerResult(layer="L1", skill_name="beta")
        lr2.metrics = [
            MetricResult(name="m1", score=10.0, max_score=10.0, details="ok", passed=True),
        ]
        lr2.compute_score()
        current_results = dict(_make_results())
        current_results["beta"] = {"L1": lr2}
        current = _build_snapshot(current_results)

        diff = compute_diff(current, baseline)
        assert "beta" in diff["new_skills"]

    def test_removed_skill(self):
        results = _make_results()
        baseline = _build_snapshot(results)
        current = _build_snapshot({})

        diff = compute_diff(current, baseline)
        assert "alpha" in diff["removed_skills"]

    def test_evaluator_version_changed(self):
        results = _make_results()
        baseline = _build_snapshot(results, evaluator_version="abc123")
        current = _build_snapshot(results, evaluator_version="def456")
        diff = compute_diff(current, baseline)
        assert diff["evaluator_version"]["changed"] is True
        assert diff["evaluator_version"]["before"] == "abc123"
        assert diff["evaluator_version"]["after"] == "def456"


# ──────────────────────────────────────────────
# format_diff_text
# ──────────────────────────────────────────────

class TestFormatDiffText:

    def test_basic_output(self):
        results = _make_results()
        snap = _build_snapshot(results)
        diff = compute_diff(snap, snap)
        text = format_diff_text(diff)
        assert "Score Diff Report" in text
        assert "Weighted Avg" in text

    def test_improved_marker(self):
        results = _make_results()
        baseline = _build_snapshot(results)

        lr2 = LayerResult(layer="L1", skill_name="alpha")
        lr2.metrics = [
            MetricResult(name="m1", score=30.0, max_score=30.0, details="ok", passed=True),
            MetricResult(name="m2", score=40.0, max_score=40.0, details="ok", passed=True),
        ]
        lr2.compute_score()
        current = _build_snapshot({"alpha": {"L1": lr2}})

        diff = compute_diff(current, baseline)
        text = format_diff_text(diff)
        assert "Improved: 1" in text

    def test_evaluator_version_line_when_changed(self):
        results = _make_results()
        baseline = _build_snapshot(results, evaluator_version="abc123")
        current = _build_snapshot(results, evaluator_version="def456")
        diff = compute_diff(current, baseline)
        text = format_diff_text(diff)
        assert "Evaluator Version:" in text


# ──────────────────────────────────────────────
# format_history_text
# ──────────────────────────────────────────────

class TestFormatHistoryText:

    def test_empty_history(self):
        text = format_history_text([])
        assert "No history" in text

    def test_with_entries(self, tmp_path):
        filepath = tmp_path / "history.jsonl"
        results = _make_results()
        save_snapshot(results, filepath=filepath)
        save_snapshot(results, filepath=filepath)
        history = load_history(filepath)
        text = format_history_text(history)
        assert "Score History" in text
        assert "2 entries" in text
        assert "EvalVer" in text

    def test_trend(self, tmp_path):
        filepath = tmp_path / "history.jsonl"
        results = _make_results()
        save_snapshot(results, filepath=filepath)
        save_snapshot(results, filepath=filepath)
        history = load_history(filepath)
        text = format_history_text(history)
        assert "Trend:" in text
