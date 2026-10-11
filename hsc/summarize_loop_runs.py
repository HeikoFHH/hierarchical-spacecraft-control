"""Summarise loop traces grouped by arm folder: ``python -m hsc.summarize_loop_runs results/session_v3``.

Each subfolder (rule, opus, haiku, both) holds ``*.jsonl`` traces; ``*.hier.json`` next to a trace adds the upper
layers' call counts, latencies and errors.
"""

from __future__ import annotations

import json
import pathlib
import sys


def summarize(root: str) -> str:
    rows = ["| arm | run | outcome | steps | closest Lady m | closest Guard m | fuel kg | Opus calls | Haiku goals | layer errors |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for arm_dir in sorted(p for p in pathlib.Path(root).iterdir() if p.is_dir()):
        for tr in sorted(arm_dir.glob("*.jsonl")):
            end = json.loads(tr.read_text().splitlines()[-1])
            info = end.get("info", {})
            hier = tr.with_suffix(".hier.json")
            h = json.loads(hier.read_text()) if hier.exists() else None
            opus = "-" if h is None else ("1" if (h["strategy"] and "error" not in h["strategy"]
                                                   and h["strategy"].get("model")) else "0")
            rows.append(f"| {arm_dir.name} | {tr.stem[-6:]} | {end['terminal_reason']} | {end['steps']} | "
                        f"{info.get('closest_lady_bandit_approach', float('nan')):.1f} | "
                        f"{info.get('closest_bandit_guard_approach', float('nan')):.1f} | "
                        f"{info.get('bandit_fuel_usage', float('nan')):.1f} | {opus} | "
                        f"{'-' if h is None else len(h['goals'])} | {'-' if h is None else len(h['errors'])} |")
    return "\n".join(rows)


if __name__ == "__main__":
    print(summarize(sys.argv[1]))
