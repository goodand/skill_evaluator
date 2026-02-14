"""orchestrator.py 단위 테스트."""

import json
from argparse import Namespace

import orchestrator
from models import LayerResult, MetricResult


def _make_args(tmp_path, config_path, fail_fast=False):
    return Namespace(
        skills_root=tmp_path,
        skill=None,
        layer="L1",
        format="json",
        output=None,
        ci_mode=False,
        threshold=None,
        config=config_path,
        benchmarks=None,
        ecosystem=False,
        save_history=False,
        diff=None,
        show_history=False,
        workers=1,
        fail_fast=fail_fast,
    )


def _make_skill_dir(root, name):
    d = root / name
    d.mkdir()
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test\n---\n",
        encoding="utf-8",
    )


def _ok_layer_result(skill_name):
    lr = LayerResult(layer="L1", skill_name=skill_name)
    lr.metrics = [
        MetricResult(name="m", score=1.0, max_score=1.0, details="ok", passed=True),
    ]
    lr.compute_score()
    return lr


def test_run_continues_when_single_layer_raises(tmp_path, monkeypatch, capsys):
    _make_skill_dir(tmp_path, "good-skill")
    _make_skill_dir(tmp_path, "bad-skill")

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"layer_weights": {"L1": 1.0}}),
        encoding="utf-8",
    )

    def fake_l1(skill, **kwargs):
        if skill.name == "bad-skill":
            raise RuntimeError("boom")
        return _ok_layer_result(skill.name)

    monkeypatch.setattr(orchestrator, "LAYERS", {"L1": fake_l1})
    args = _make_args(tmp_path, config_path)

    rc = orchestrator.run(args)
    assert rc == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    by_name = {s["name"]: s for s in data["skills"]}

    assert "good-skill" in by_name
    assert "bad-skill" in by_name
    assert by_name["good-skill"]["layers"]["L1"]["score"] == 100.0
    assert by_name["bad-skill"]["layers"]["L1"]["score"] == 0.0
    metric = by_name["bad-skill"]["layers"]["L1"]["metrics"][0]
    assert metric["name"] == "runtime_error"
    assert metric["passed"] is False
    err = captured.err
    assert "[WARN]" in err
    assert "bad-skill" in err
    assert "L1" in err


def test_run_fail_fast_aborts_on_layer_error(tmp_path, monkeypatch, capsys):
    _make_skill_dir(tmp_path, "good-skill")
    _make_skill_dir(tmp_path, "bad-skill")

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"layer_weights": {"L1": 1.0}}),
        encoding="utf-8",
    )

    def fake_l1(skill, **kwargs):
        if skill.name == "bad-skill":
            raise RuntimeError("boom")
        return _ok_layer_result(skill.name)

    monkeypatch.setattr(orchestrator, "LAYERS", {"L1": fake_l1})
    args = _make_args(tmp_path, config_path, fail_fast=True)

    rc = orchestrator.run(args)
    assert rc == 1
    captured = capsys.readouterr()
    assert "[ERROR]" in captured.err
    assert "bad-skill" in captured.err
    assert "L1" in captured.err


def test_run_fails_when_layer_weights_missing_for_selected_layers(tmp_path, monkeypatch, capsys):
    _make_skill_dir(tmp_path, "only-skill")

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"layer_weights": {"L1": 1.0}}),
        encoding="utf-8",
    )

    # 레이어 레지스트리에 비표준 L7이 있으면 config 기본 가중치에 없으므로 즉시 실패해야 함.
    monkeypatch.setattr(orchestrator, "LAYERS", {"L1": lambda *a, **k: _ok_layer_result("only-skill"), "L7": lambda *a, **k: _ok_layer_result("only-skill")})
    args = _make_args(tmp_path, config_path)
    args.layer = None

    rc = orchestrator.run(args)
    assert rc == 1
    captured = capsys.readouterr()
    assert "[ERROR]" in captured.err
    assert "Missing layer weights" in captured.err
    assert "L7" in captured.err
