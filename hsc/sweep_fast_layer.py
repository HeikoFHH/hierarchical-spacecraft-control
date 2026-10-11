"""Sweep the rule baseline's throttle and burn duration on the lbg1_lite fixture (no model, no key).

    python -m hsc.sweep_fast_layer --scenarios i2:lg0,i2:lg1,i2:lg7 --out results/fast_layer_sweep

The fast layer has to be able to reach the Lady before it is worth asking whether upper layers help. Reports the
closest Lady and Guard approaches, outcome and fuel per (scenario, throttle, duration).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import tempfile

from hsc import kspdg_loop as K


def run_one(scenario: str, magnitude: float, duration: float, decider: str = "rule") -> dict:
    cfg = K.LoopConfig(decider=decider, thrust_magnitude=magnitude, burn_duration_s=duration,
                       fixture_scenario=scenario, kev_base_url="http://127.0.0.1:9")
    with tempfile.TemporaryDirectory() as d:
        out = K.run(K.make_env("fixture", cfg), cfg, None, env_kind="fixture", trace_path=pathlib.Path(d) / "t.jsonl")
    info = out.get("info", {})
    return {"scenario": scenario, "throttle": magnitude, "duration_s": duration, "steps": out["steps"],
            "outcome": out["terminal_reason"], "closest_lady_m": round(info.get("closest_lady_bandit_approach", float("nan")), 1),
            "closest_guard_m": round(info.get("closest_bandit_guard_approach", float("nan")), 1),
            "fuel_kg": round(info.get("bandit_fuel_usage", float("nan")), 1),
            "score": round(info.get("weighted_score", float("nan")))}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenarios", default="i2:lg0,i2:lg1,i2:lg7")
    ap.add_argument("--throttles", default="0.2,0.5,1.0")
    ap.add_argument("--durations", default="0.25,0.5,1.0")
    ap.add_argument("--out", default="results/fast_layer_sweep")
    args = ap.parse_args(argv)
    rows = [run_one(sc, m, d) for sc in args.scenarios.split(",") for m in map(float, args.throttles.split(","))
            for d in map(float, args.durations.split(","))]
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(rows, indent=1))
    cols = list(rows[0])
    md = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + \
         ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
    out.with_suffix(".md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
