#!/usr/bin/env python3
"""Skill Evaluator CLI — 6-Layer 평가 오케스트레이터."""

import argparse
import sys
from pathlib import Path

from orchestrator import run

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
    parser.add_argument(
        "--workers", type=int, default=1,
        help="Number of parallel workers for per-skill evaluation (default: 1)",
    )
    parser.add_argument(
        "--fail-fast", action="store_true",
        help="Abort immediately if any layer evaluation raises runtime exception",
    )
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
