"""평가 실행 오케스트레이터."""

import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from config_loader import load_eval_config
from discovery import discover_skills
from evaluators import LAYERS, evaluate_ecosystem
from history import (
    build_snapshot,
    compute_diff,
    format_diff_text,
    format_history_text,
    load_history,
    save_snapshot,
)
from models import LayerResult, MetricResult
from reporter import format_json, format_markdown, format_text
from score_utils import weighted_score


class LayerEvaluationError(Exception):
    """레이어 평가 실패를 상위 흐름으로 전달."""

    def __init__(self, skill_name: str, layer_id: str, original: Exception):
        self.skill_name = skill_name
        self.layer_id = layer_id
        self.original = original
        super().__init__(f"skill={skill_name} layer={layer_id} error={type(original).__name__}: {original}")


def _error_layer_result(layer_id: str, skill_name: str, exc: Exception) -> LayerResult:
    """레이어 평가 실패를 LayerResult 형태로 캡슐화."""
    detail = f"{type(exc).__name__}: {exc}"
    lr = LayerResult(layer=layer_id, skill_name=skill_name)
    lr.metrics = [
        MetricResult(
            name="runtime_error",
            score=0.0,
            max_score=1.0,
            details=detail,
            passed=False,
        )
    ]
    lr.compute_score()
    lr.recommendations.append(f"runtime_error: {detail}")
    return lr


def _evaluate_one_skill(task):
    """단일 스킬의 모든 레이어를 평가."""
    skill, layer_ids, all_skills, benchmarks_dir, fail_fast = task
    layer_results = {}
    for lid in layer_ids:
        try:
            layer_results[lid] = LAYERS[lid](
                skill,
                all_skills=all_skills,
                benchmarks_dir=benchmarks_dir,
            )
        except Exception as exc:  # noqa: BLE001
            if fail_fast:
                raise LayerEvaluationError(skill.name, lid, exc) from exc
            print(
                f"[WARN] layer evaluation failed: skill={skill.name} layer={lid} error={type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            layer_results[lid] = _error_layer_result(lid, skill.name, exc)
    return skill.name, layer_results


def _collect_results_sequential(skills, layer_ids, all_skills, benchmarks_dir, fail_fast):
    """순차 실행으로 결과 수집."""
    results = {}
    for skill in skills:
        name, layer_results = _evaluate_one_skill((skill, layer_ids, all_skills, benchmarks_dir, fail_fast))
        results[name] = layer_results
    return results


def _collect_results_parallel(tasks, workers):
    """병렬 실행으로 결과 수집."""
    results = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for name, layer_results in ex.map(_evaluate_one_skill, tasks):
            results[name] = layer_results
    return results


def run(args) -> int:
    """CLI args를 받아 평가를 실행하고 종료 코드를 반환."""
    config = load_eval_config(args.config)

    if args.show_history:
        history = load_history()
        print(format_history_text(history))
        return 0

    env_root = os.environ.get("SKILLS_ROOT", "")
    config_root = config.skills_root
    raw = args.skills_root or (Path(env_root) if env_root else None) or (Path(config_root) if config_root else None)
    skills_root = raw
    if not skills_root or not skills_root.is_dir():
        print("Error: --skills-root required (or set in config.json / SKILLS_ROOT env)", file=sys.stderr)
        return 1

    threshold = args.threshold or config.threshold

    if args.layer:
        layer_ids = [l.strip().upper() for l in args.layer.split(",")]
        for lid in layer_ids:
            if lid not in LAYERS:
                print(f"Unknown layer: {lid}. Available: {', '.join(LAYERS)}", file=sys.stderr)
                return 1
    else:
        layer_ids = list(LAYERS.keys())
    missing_weights = sorted(lid for lid in layer_ids if lid not in config.layer_weights)
    if missing_weights:
        print(f"[ERROR] Missing layer weights for selected layers: {', '.join(missing_weights)}", file=sys.stderr)
        return 1
    if args.workers < 1:
        print("--workers must be >= 1", file=sys.stderr)
        return 1

    skills = discover_skills(skills_root)
    if not skills:
        print(f"No skills found in {skills_root}", file=sys.stderr)
        return 1

    if args.skill:
        skills = [s for s in skills if s.name == args.skill]
        if not skills:
            print(f"Skill '{args.skill}' not found", file=sys.stderr)
            return 1

    benchmarks_dir = args.benchmarks or Path(__file__).parent.parent / "benchmarks"
    fail_fast = args.fail_fast

    try:
        if args.workers == 1 or len(skills) <= 1:
            results = _collect_results_sequential(
                skills, layer_ids, skills, benchmarks_dir, fail_fast
            )
        else:
            tasks = [(skill, layer_ids, skills, benchmarks_dir, fail_fast) for skill in skills]
            try:
                results = _collect_results_parallel(tasks, args.workers)
            except (PermissionError, OSError):
                # 일부 샌드박스/환경에서 프로세스 풀이 제한될 수 있으므로 순차 실행으로 복구.
                results = _collect_results_sequential(
                    skills, layer_ids, skills, benchmarks_dir, fail_fast
                )
    except LayerEvaluationError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    ecosystem_result = evaluate_ecosystem(skills) if args.ecosystem else None

    if args.diff is not None:
        history = load_history()
        if not history:
            print("No history found. Run with --save-history first.", file=sys.stderr)
            return 1
        if args.diff == "latest":
            baseline = history[-1]
        else:
            idx = int(args.diff) - 1
            if idx < 0 or idx >= len(history):
                print(f"Invalid history index: {args.diff} (1-{len(history)})", file=sys.stderr)
                return 1
            baseline = history[idx]
        current_snap = build_snapshot(
            results,
            ecosystem_result,
            layer_weights=config.layer_weights,
        )
        diff = compute_diff(current_snap, baseline)
        print(format_diff_text(diff))

    if args.save_history:
        fp = save_snapshot(
            results,
            ecosystem_result,
            layer_weights=config.layer_weights,
        )
        print(f"History saved to {fp}", file=sys.stderr)

    if args.diff is None:
        formatters = {"text": format_text, "json": format_json, "markdown": format_markdown}
        output = formatters[args.format](
            results,
            ecosystem_result=ecosystem_result,
            layer_weights=config.layer_weights,
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
            print(f"Saved to {args.output}")
        else:
            print(output)

    if args.ci_mode:
        failed = []
        for skill_name, layer_results in results.items():
            w = weighted_score(layer_results, layer_weights=config.layer_weights)
            if w < threshold:
                failed.append((skill_name, w))
        if failed:
            print(f"\nCI FAILED: {len(failed)} skill(s) below {threshold}:", file=sys.stderr)
            for name, score in failed:
                print(f"  {name}: {score:.1f}", file=sys.stderr)
            return 1
        print(f"\nCI PASSED: All skills above {threshold}", file=sys.stderr)

    return 0
