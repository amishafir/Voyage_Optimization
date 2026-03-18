"""Policies — decide when to re-plan during a voyage.

Each policy inspects the voyage state after every leg and returns an Action.
The executor handles the action (re-plan, continue, etc).
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List


class Action(Enum):
    """What the executor should do after a leg."""
    CONTINUE = auto()       # Keep following current plan
    REPLAN = auto()         # Re-plan with stale forecast (Mid environment)
    REPLAN_FRESH = auto()   # Re-plan with fresh forecast (Connected environment)


class FlowType(Enum):
    """Leg execution outcome."""
    FLOW1 = auto()  # Nominal — SWS within [min, max]
    FLOW2 = auto()  # Adverse — required SWS > max, can't keep up
    FLOW3 = auto()  # Favorable — required SWS < min, would overshoot


@dataclass
class VoyageState:
    """Mutable state passed to policy after each leg."""

    leg_idx: int = 0
    cumulative_time_h: float = 0.0
    cumulative_fuel_mt: float = 0.0
    planned_cumulative_time_h: float = 0.0
    delay_h: float = 0.0
    flow_type: FlowType = FlowType.FLOW1
    flow2_streak: int = 0          # consecutive Flow 2 legs
    time_since_replan_h: float = 0.0
    total_legs: int = 0
    replan_count: int = 0
    flow_history: List[FlowType] = field(default_factory=list)


class PassivePolicy:
    """Never re-plan. Follow the original plan regardless of what happens."""

    def on_leg_complete(self, state: VoyageState) -> Action:
        return Action.CONTINUE


class ReactivePolicy:
    """Re-plan when exiting a Flow 2 sequence.

    Only triggers when flow transitions FROM Flow 2 TO Flow 1/3,
    preventing wasteful re-computation during a storm.

    Args:
        trigger: "flow2" — re-plan on Flow 2 exit only.
                 "any_divergence" — re-plan on Flow 2 or Flow 3 exit.
        min_replan_interval_h: Minimum hours between re-plans (prevents thrashing).
    """

    def __init__(self, trigger: str = "flow2", min_replan_interval_h: float = 1.0):
        self.trigger = trigger
        self.min_replan_interval_h = min_replan_interval_h

    def on_leg_complete(self, state: VoyageState) -> Action:
        if state.time_since_replan_h < self.min_replan_interval_h:
            return Action.CONTINUE

        if state.leg_idx >= state.total_legs - 1:
            return Action.CONTINUE  # last leg, nothing to re-plan

        # Check if we just exited a Flow 2 streak
        if self.trigger == "flow2":
            if state.flow_type != FlowType.FLOW2 and state.flow2_streak > 0:
                return Action.REPLAN
        elif self.trigger == "any_divergence":
            if state.flow_type != FlowType.FLOW2 and state.flow2_streak > 0:
                return Action.REPLAN
            if state.flow_type == FlowType.FLOW3:
                return Action.REPLAN

        return Action.CONTINUE


class ProactivePolicy:
    """Re-plan on schedule (every N hours) + reactively on Flow 2.

    Uses REPLAN_FRESH (requests fresh forecast from Connected environment).

    Args:
        interval_h: Hours between scheduled re-plans (default 6, matches NWP cycle).
        also_on_flow2: Also trigger re-plan when exiting Flow 2 sequence.
    """

    def __init__(self, interval_h: float = 6.0, also_on_flow2: bool = True):
        self.interval_h = interval_h
        self.also_on_flow2 = also_on_flow2

    def on_leg_complete(self, state: VoyageState) -> Action:
        if state.leg_idx >= state.total_legs - 1:
            return Action.CONTINUE  # last leg

        # Scheduled re-plan
        if state.time_since_replan_h >= self.interval_h:
            return Action.REPLAN_FRESH

        # Reactive on Flow 2 exit
        if self.also_on_flow2:
            if state.flow_type != FlowType.FLOW2 and state.flow2_streak > 0:
                return Action.REPLAN_FRESH

        return Action.CONTINUE
