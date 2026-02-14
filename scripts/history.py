"""Score History — 스냅샷 저장/로드/비교."""

import json
import hashlib
from datetime import datetime
from pathlib import Path

from reporter import weighted_score


DEFAULT_HISTORY_PATH = Path(__file__).parent.parent / "reports" / "history.jsonl"
_PROJECT_ROOT = Path(__file__).parent.parent
_EVALUATOR_CODE_ROOT = _PROJECT_ROOT / "scripts"


def _compute_evaluator_version() -> str:
    """Evaluator 코드 스냅샷 버전(sha256 앞 12자리)을 계산."""
    hasher = hashlib.sha256()
    for fp in sorted(_EVALUATOR_CODE_ROOT.rglob("*.py")):
        if "__pycache__" in fp.parts:
            continue
        rel = fp.relative_to(_PROJECT_ROOT).as_posix()
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(fp.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()[:12]


def build_snapshot(
    results: dict,
    ecosystem_result=None,
    evaluator_version: str = None,
    layer_weights: dict = None,
) -> dict:
    """현재 결과를 스냅샷 dict로 변환."""
    if evaluator_version is None:
        evaluator_version = _compute_evaluator_version()
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "evaluator_version": evaluator_version,
        "skills": {},
        "summary": {},
    }
    all_w = []
    for skill_name, layer_results in results.items():
        w = weighted_score(layer_results, layer_weights=layer_weights)
        all_w.append(w)
        snapshot["skills"][skill_name] = {
            "weighted": round(w, 1),
            "layers": {lid: round(lr.overall_score, 1) for lid, lr in layer_results.items()},
        }
    snapshot["summary"] = {
        "weighted_average": round(sum(all_w) / len(all_w), 1) if all_w else 0,
        "skill_count": len(results),
    }
    if ecosystem_result:
        snapshot["ecosystem"] = {"overall_score": round(ecosystem_result.overall_score, 1)}
    return snapshot


def save_snapshot(results: dict, ecosystem_result=None, filepath: Path = None, layer_weights: dict = None):
    """스냅샷을 history.jsonl에 append."""
    if filepath is None:
        filepath = DEFAULT_HISTORY_PATH
    filepath.parent.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot(results, ecosystem_result, layer_weights=layer_weights)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
    return filepath


def load_history(filepath: Path = None) -> list:
    """history.jsonl에서 모든 스냅샷 로드."""
    if filepath is None:
        filepath = DEFAULT_HISTORY_PATH
    if not filepath.exists():
        return []
    snapshots = []
    for line in filepath.read_text(encoding="utf-8").strip().split("\n"):
        if line.strip():
            snapshots.append(json.loads(line))
    return snapshots


def get_latest(filepath: Path = None):
    """최신 스냅샷 반환. 없으면 None."""
    history = load_history(filepath)
    return history[-1] if history else None


def compute_diff(current: dict, baseline: dict) -> dict:
    """두 스냅샷 비교."""
    diff = {
        "summary": {},
        "skills": {},
        "improved": [],
        "regressed": [],
        "new_skills": [],
        "removed_skills": [],
        "evaluator_version": {
            "before": baseline.get("evaluator_version"),
            "after": current.get("evaluator_version"),
            "changed": baseline.get("evaluator_version") != current.get("evaluator_version"),
        },
    }

    for key in ["weighted_average", "skill_count"]:
        before = baseline.get("summary", {}).get(key, 0)
        after = current.get("summary", {}).get(key, 0)
        diff["summary"][key] = {"before": before, "after": after, "delta": round(after - before, 1)}

    curr_skills = current.get("skills", {})
    base_skills = baseline.get("skills", {})

    all_names = set(list(curr_skills.keys()) + list(base_skills.keys()))
    for name in sorted(all_names):
        if name in curr_skills and name not in base_skills:
            diff["new_skills"].append(name)
            continue
        if name not in curr_skills and name in base_skills:
            diff["removed_skills"].append(name)
            continue

        curr_w = curr_skills[name]["weighted"]
        base_w = base_skills[name]["weighted"]
        delta = round(curr_w - base_w, 1)

        skill_diff = {"weighted": {"before": base_w, "after": curr_w, "delta": delta}, "layers": {}}

        curr_layers = curr_skills[name].get("layers", {})
        base_layers = base_skills[name].get("layers", {})
        for lid in set(list(curr_layers.keys()) + list(base_layers.keys())):
            b = base_layers.get(lid, 0)
            a = curr_layers.get(lid, 0)
            skill_diff["layers"][lid] = {"before": b, "after": a, "delta": round(a - b, 1)}

        diff["skills"][name] = skill_diff
        if delta > 0:
            diff["improved"].append(name)
        elif delta < 0:
            diff["regressed"].append(name)

    return diff


def format_diff_text(diff: dict) -> str:
    """diff 결과 텍스트 출력."""
    lines = ["=" * 60, "Score Diff Report", "=" * 60, ""]

    s = diff["summary"]
    avg = s.get("weighted_average", {})
    d = avg.get("delta", 0)
    arrow = "+" if d > 0 else ""
    lines.append(f"Weighted Avg: {avg.get('before', 0):.1f} → {avg.get('after', 0):.1f} ({arrow}{d:.1f})")
    ev = diff.get("evaluator_version", {})
    if ev.get("changed"):
        lines.append(
            f"Evaluator Version: {ev.get('before', 'unknown')} → {ev.get('after', 'unknown')}"
        )
    lines.append("")

    for name, sd in diff["skills"].items():
        w = sd["weighted"]
        d = w["delta"]
        arrow = "+" if d > 0 else ""
        marker = " ↑" if d > 0 else (" ↓" if d < 0 else "")
        lines.append(f"  {name}: {w['before']:.1f} → {w['after']:.1f} ({arrow}{d:.1f}){marker}")

    if diff["new_skills"]:
        lines.append(f"\n  New: {', '.join(diff['new_skills'])}")
    if diff["removed_skills"]:
        lines.append(f"\n  Removed: {', '.join(diff['removed_skills'])}")

    lines.append("")
    lines.append(f"Improved: {len(diff['improved'])} | Regressed: {len(diff['regressed'])}")
    lines.append("")
    return "\n".join(lines)


def format_history_text(history: list) -> str:
    """이력 요약 텍스트."""
    if not history:
        return "No history entries found."
    lines = [
        f"Score History ({len(history)} entries)",
        "=" * 50,
        f"{'Date':<20} {'Skills':>6} {'Weighted Avg':>13} {'Delta':>7} {'EvalVer':>8}",
        "-" * 50,
    ]
    prev_avg = None
    for snap in history:
        ts = snap.get("timestamp", "")[:16].replace("T", " ")
        s = snap.get("summary", {})
        avg = s.get("weighted_average", 0)
        count = s.get("skill_count", 0)
        if prev_avg is not None:
            d = avg - prev_avg
            delta_str = f"{'+' if d > 0 else ''}{d:.1f}"
        else:
            delta_str = "--"
        ev = snap.get("evaluator_version", "n/a")
        lines.append(f"{ts:<20} {count:>6} {avg:>13.1f} {delta_str:>7} {ev[:8]:>8}")
        prev_avg = avg
    lines.append("=" * 50)
    if len(history) >= 2:
        total_d = history[-1]["summary"]["weighted_average"] - history[0]["summary"]["weighted_average"]
        lines.append(f"Trend: {'+' if total_d > 0 else ''}{total_d:.1f} over {len(history)} evaluations")
    lines.append("")
    return "\n".join(lines)
