"""평가 실행 오케스트레이터."""

import os
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

from discovery import discover_skills
from eval_config import load_eval_config
from evaluators import LAYERS, evaluate_ecosystem
from history import (
    _build_snapshot,
    compute_diff,
    format_diff_text,
    format_history_text,
    load_history,
    save_snapshot,
)
from reporter import format_json, format_markdown, format_text, weighted_score


def _evaluate_one_skill(task):
    """단일 스킬의 모든 레이어를 평가."""
    skill, layer_ids, all_skills, benchmarks_dir = task
    layer_results = {}
    for lid in layer_ids:
        layer_results[lid] = LAYERS[lid](
            skill,
            all_skills=all_skills,
            benchmarks_dir=benchmarks_dir,
        )
    return skill.name, layer_results


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

    results = {}
    if args.workers == 1 or len(skills) <= 1:
        for skill in skills:
            name, layer_results = _evaluate_one_skill((skill, layer_ids, skills, benchmarks_dir))
            results[name] = layer_results
    else:
        tasks = [(skill, layer_ids, skills, benchmarks_dir) for skill in skills]
        try:
            with ProcessPoolExecutor(max_workers=args.workers) as ex:
                for name, layer_results in ex.map(_evaluate_one_skill, tasks):
                    results[name] = layer_results
        except (PermissionError, OSError):
            # 일부 샌드박스 환경에서 프로세스 풀 생성이 제한될 수 있음.
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                for name, layer_results in ex.map(_evaluate_one_skill, tasks):
                    results[name] = layer_results

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
        current_snap = _build_snapshot(
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
