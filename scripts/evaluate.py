#!/usr/bin/env python3
"""Skill Evaluator CLI — 6-Layer 평가 오케스트레이터."""

import argparse
import json
import os
import sys
from pathlib import Path

from discovery import discover_skills
from reporter import format_text, format_json, format_markdown, weighted_score
from evaluators import LAYERS, evaluate_ecosystem
from history import (
    save_snapshot, load_history, compute_diff,
    format_diff_text, format_history_text, _build_snapshot,
)


def _load_config(config_path: Path) -> dict:
    """config.json 로드."""
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def main():
    default_config = Path(__file__).parent.parent / "config.json"

    parser = argparse.ArgumentParser(description="Skill Evaluator")
    parser.add_argument(
        "--skills-root", type=Path, default=None,
        help="Root directory containing skills (each with SKILL.md)",
    )
    parser.add_argument(
        "--skill", type=str, default=None,
        help="Evaluate a specific skill by name",
    )
    parser.add_argument(
        "--layer", type=str, default=None,
        help="Comma-separated layers to evaluate (e.g. L1,L4,L6). Default: all",
    )
    parser.add_argument(
        "--format", choices=["text", "json", "markdown"], default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--output", "-o", type=Path, default=None,
        help="Save output to file",
    )
    parser.add_argument(
        "--ci-mode", action="store_true",
        help="Exit with code 1 if any skill below threshold",
    )
    parser.add_argument(
        "--threshold", type=float, default=None,
        help="Minimum passing score (default: from config or 60.0)",
    )
    parser.add_argument(
        "--config", type=Path, default=default_config,
        help="Config file path",
    )
    parser.add_argument(
        "--benchmarks", type=Path, default=None,
        help="Benchmarks directory for L2/L5 dynamic evaluation",
    )
    parser.add_argument(
        "--ecosystem", action="store_true",
        help="Include cross-skill ecosystem analysis",
    )
    parser.add_argument(
        "--save-history", action="store_true",
        help="Save evaluation snapshot to history.jsonl",
    )
    parser.add_argument(
        "--diff", nargs="?", const="latest", default=None,
        help="Compare with baseline (default: latest). Use N for Nth entry",
    )
    parser.add_argument(
        "--show-history", action="store_true",
        help="Show score history summary and exit",
    )
    args = parser.parse_args()

    # Config 로드
    config = _load_config(args.config)

    # --show-history: 이력 출력 후 종료
    if args.show_history:
        history = load_history()
        print(format_history_text(history))
        sys.exit(0)

    # skills-root: CLI > env > config
    env_root = os.environ.get("SKILLS_ROOT", "")
    config_root = config.get("skills_root", "")
    raw = args.skills_root or (Path(env_root) if env_root else None) or (Path(config_root) if config_root else None)
    skills_root = raw
    if not skills_root or not skills_root.is_dir():
        print("Error: --skills-root required (or set in config.json / SKILLS_ROOT env)", file=sys.stderr)
        sys.exit(1)

    threshold = args.threshold or config.get("threshold", 60.0)

    # 레이어 결정
    if args.layer:
        layer_ids = [l.strip().upper() for l in args.layer.split(",")]
        for lid in layer_ids:
            if lid not in LAYERS:
                print(f"Unknown layer: {lid}. Available: {', '.join(LAYERS)}", file=sys.stderr)
                sys.exit(1)
    else:
        layer_ids = list(LAYERS.keys())

    # 스킬 탐지
    skills = discover_skills(skills_root)
    if not skills:
        print(f"No skills found in {skills_root}", file=sys.stderr)
        sys.exit(1)

    if args.skill:
        skills = [s for s in skills if s.name == args.skill]
        if not skills:
            print(f"Skill '{args.skill}' not found", file=sys.stderr)
            sys.exit(1)

    # 벤치마크 경로
    benchmarks_dir = args.benchmarks or Path(__file__).parent.parent / "benchmarks"

    # 평가: {skill_name: {layer_id: LayerResult}}
    results = {}
    for skill in skills:
        results[skill.name] = {}
        for lid in layer_ids:
            results[skill.name][lid] = LAYERS[lid](
                skill,
                all_skills=skills,
                benchmarks_dir=benchmarks_dir,
            )

    # 에코시스템 분석
    ecosystem_result = None
    if args.ecosystem:
        ecosystem_result = evaluate_ecosystem(skills)

    # --diff: 베이스라인과 비교
    if args.diff is not None:
        history = load_history()
        if not history:
            print("No history found. Run with --save-history first.", file=sys.stderr)
            sys.exit(1)
        if args.diff == "latest":
            baseline = history[-1]
        else:
            idx = int(args.diff) - 1
            if idx < 0 or idx >= len(history):
                print(f"Invalid history index: {args.diff} (1-{len(history)})", file=sys.stderr)
                sys.exit(1)
            baseline = history[idx]
        current_snap = _build_snapshot(results, ecosystem_result)
        diff = compute_diff(current_snap, baseline)
        print(format_diff_text(diff))

    # --save-history: 스냅샷 저장
    if args.save_history:
        fp = save_snapshot(results, ecosystem_result)
        print(f"History saved to {fp}", file=sys.stderr)

    # 출력 (diff가 없을 때만 일반 출력)
    if args.diff is None:
        formatters = {"text": format_text, "json": format_json, "markdown": format_markdown}
        output = formatters[args.format](results, ecosystem_result=ecosystem_result)

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
            print(f"Saved to {args.output}")
        else:
            print(output)

    # CI 모드
    if args.ci_mode:
        failed = []
        for skill_name, layer_results in results.items():
            w = weighted_score(layer_results)
            if w < threshold:
                failed.append((skill_name, w))
        if failed:
            print(f"\nCI FAILED: {len(failed)} skill(s) below {threshold}:", file=sys.stderr)
            for name, score in failed:
                print(f"  {name}: {score:.1f}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"\nCI PASSED: All skills above {threshold}", file=sys.stderr)


if __name__ == "__main__":
    main()
