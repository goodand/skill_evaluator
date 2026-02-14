"""eval_config.py 단위 테스트."""

import json

from config_loader import load_eval_config
from eval_config import DEFAULT_LAYER_WEIGHTS, EvalConfig


class TestLoadEvalConfig:

    def test_missing_file_returns_defaults(self, tmp_path):
        cfg = load_eval_config(tmp_path / "missing.json")
        assert isinstance(cfg, EvalConfig)
        assert cfg.skills_root == ""
        assert cfg.threshold == 60.0
        assert cfg.layer_weights == DEFAULT_LAYER_WEIGHTS

    def test_merges_custom_layer_weights(self, tmp_path):
        fp = tmp_path / "config.json"
        fp.write_text(
            json.dumps(
                {
                    "skills_root": "/tmp/skills",
                    "threshold": 70.0,
                    "layer_weights": {"L1": 0.5, "L6": 0.0},
                }
            ),
            encoding="utf-8",
        )
        cfg = load_eval_config(fp)
        assert cfg.skills_root == "/tmp/skills"
        assert cfg.threshold == 70.0
        assert cfg.layer_weights["L1"] == 0.5
        assert cfg.layer_weights["L6"] == 0.0
        # unspecified keys keep defaults
        assert cfg.layer_weights["L5"] == DEFAULT_LAYER_WEIGHTS["L5"]

    def test_invalid_unknown_layer_weight_key_raises(self, tmp_path):
        fp = tmp_path / "config.json"
        fp.write_text(
            json.dumps({"layer_weights": {"L7": 0.1}}),
            encoding="utf-8",
        )
        try:
            load_eval_config(fp)
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "Unknown layer weight keys" in str(e)

    def test_invalid_negative_weight_raises(self, tmp_path):
        fp = tmp_path / "config.json"
        fp.write_text(
            json.dumps({"layer_weights": {"L1": -0.1}}),
            encoding="utf-8",
        )
        try:
            load_eval_config(fp)
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "must be non-negative" in str(e)
