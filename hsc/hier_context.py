"""Upper layers for the sequential KSPDG loop: Opus strategy once, Haiku tactical goals asynchronously.

``HierarchicalContext`` is a ``context_provider`` for ``hsc.kspdg_loop.run``. On the first call it asks the
strategist (Opus) for a mission brief. After that it asks the tactician (Haiku) for a new short-term goal every
``brief.tactical_period_s`` of mission time, on a background thread so the fast layer never waits for it. Each
decision the loop sends Kev the latest brief and goal as ``state.context``. Kev stays the only layer that picks
an action. It is a Choice classifier, so the context shapes its input but is not guaranteed to change its answer.

    python -m hsc.kspdg_loop --env fixture --decider hier --episode      # needs ANTHROPIC_API_KEY and a Kev server

Everything the upper layers did (brief, every goal with its latency and token use, errors) is written next to the
trace as ``<trace>.hier.json``.
"""

from __future__ import annotations

import threading
import time

import numpy as np

from hsc.control.plans import MissionBrief, TacticalGoal
from hsc.control.situation import Situation, situation_from_obs
from hsc.sim.orbits import lvlh_basis

SCENARIO_LABEL = "LBG1_LG7_I2_V1"


class HierarchicalContext:
    def __init__(self, strategist, tactician, prop_capacity: float, episode_timeout_s: float,
                 scenario_label: str = SCENARIO_LABEL):
        self.strategist, self.tactician = strategist, tactician
        self.prop_capacity, self.episode_timeout_s = prop_capacity, episode_timeout_s
        self.scenario_label = scenario_label
        self.brief: MissionBrief | None = None
        self.goal = TacticalGoal()
        self.version = 0
        self.history: list[Situation] = []
        self.next_tactical_t = 0.0
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.log = {"strategy": None, "goals": [], "errors": []}

    # -- called by the loop before every Kev request
    def __call__(self, feat: dict, obs) -> dict:
        s = situation_from_obs(obs, self.prop_capacity, self.episode_timeout_s)
        t = s.t
        if self.brief is None:
            self._plan(s)
        self.history.append(s)
        with self._lock:
            busy = self._thread is not None and self._thread.is_alive()
            if self.tactician is not None and not busy and t >= self.next_tactical_t - 1e-9:
                self.next_tactical_t = t + self.brief.tactical_period_s
                self._thread = threading.Thread(target=self._tactical, args=(list(self.history), self.brief, self.goal, t),
                                                daemon=True)
                self._thread.start()
            goal, version = self.goal, self.version
        wp_cbci = None
        if goal.waypoint_lvlh_m is not None:  # waypoint (Lady LVLH) as an inertial offset from the Bandit, the loop's frame
            basis = lvlh_basis(np.asarray(obs[9:12], dtype=float), np.asarray(obs[12:15], dtype=float))
            wp = basis.T @ np.asarray(goal.waypoint_lvlh_m, dtype=float) + np.asarray(obs[9:12]) - np.asarray(obs[3:6])
            wp_cbci = [round(float(x), 1) for x in wp]
        return {"version": version, "age_s": round(t - goal.issued_at, 1), "frame": "Lady LVLH: x radial out, y along-track, z normal",
                "brief": {"approach": self.brief.approach[:240], "guard_keepout_m": self.brief.guard_keepout_m,
                          "max_closing_speed_mps": self.brief.max_closing_speed_mps},
                "goal": {"mode_hint": goal.mode_hint, "waypoint_lvlh_m": goal.waypoint_lvlh_m,
                         "waypoint_rel_bandit_cbci_m": wp_cbci, "guard_keepout_m": goal.guard_keepout_m,
                         "standoff_m": goal.standoff_m, "max_closing_speed_mps": goal.max_closing_speed_mps,
                         "rationale": goal.rationale[:160]}}

    def _plan(self, s: Situation):
        t0 = time.perf_counter()
        try:
            self.brief, res = self.strategist.plan(s, self.scenario_label)
            self.log["strategy"] = {"brief": self.brief.to_dict(), **_call_meta(res, time.perf_counter() - t0)}
        except Exception as e:  # noqa: BLE001  (keep the run going on the default brief, and say so in the log)
            self.brief = MissionBrief()
            self.log["strategy"] = {"brief": self.brief.to_dict(), "error": repr(e), "used_default_brief": True}
            self.log["errors"].append({"layer": "strategy", "error": repr(e)})
        self.goal = TacticalGoal.from_brief(self.brief)

    def _tactical(self, history, brief, current, t):
        t0 = time.perf_counter()
        try:
            goal, res = self.tactician.update(history, brief, current)
            with self._lock:
                self.goal, self.version = goal, self.version + 1
            self.log["goals"].append({"mission_t": t, "version": self.version, "goal": goal.to_dict(),
                                      **_call_meta(res, time.perf_counter() - t0)})
        except Exception as e:  # noqa: BLE001
            self.log["errors"].append({"layer": "tactical", "mission_t": t, "error": repr(e)})

    def wait(self, timeout: float = 30.0):
        th = self._thread
        if th is not None:
            th.join(timeout)


def _call_meta(res, wall_s: float) -> dict:
    if res is None:
        return {"model": None, "latency_s": round(wall_s, 3)}
    return {"model": res.model, "latency_s": round(res.latency_s, 3), "input_tokens": res.input_tokens,
            "output_tokens": res.output_tokens}
