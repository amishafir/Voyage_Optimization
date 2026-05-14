"""Agent framework — composable autonomous voyage agents.

An agent is assembled from five components:
    Agent = (Spec, Measurement, Plan, Policy, Environment)

Usage:
    from agent import assemble
    agent = assemble(config, plan="dp", policy="reactive", environment="mid")
    result = agent.execute(...)  # Phase 8.2
"""

from dataclasses import dataclass
from typing import Union

from agent.spec import ShipSpec
from agent.measurement import Measurement
from agent.plans import Plan, NaivePlan, LPPlan, DPPlan
from agent.policies import PassivePolicy, ReactivePolicy, ProactivePolicy
from agent.environments import BasicEnvironment, MidEnvironment, ConnectedEnvironment


PLAN_REGISTRY = {
    "naive": NaivePlan,
    "lp": LPPlan,
    "dp": DPPlan,
}

POLICY_REGISTRY = {
    "passive": PassivePolicy,
    "reactive": ReactivePolicy,
    "proactive": ProactivePolicy,
}

ENVIRONMENT_REGISTRY = {
    "basic": BasicEnvironment,
    "mid": MidEnvironment,
    "connected": ConnectedEnvironment,
}

# Default policy per environment tier
DEFAULT_POLICY = {
    "basic": "passive",
    "mid": "reactive",
    "connected": "proactive",
}


@dataclass
class Agent:
    """Assembled agent — ready to execute a voyage."""

    name: str
    spec: ShipSpec
    measurement: Measurement
    plan: Plan
    policy: Union[PassivePolicy, ReactivePolicy, ProactivePolicy]
    environment: Union[BasicEnvironment, MidEnvironment, ConnectedEnvironment]

    def __repr__(self):
        return f"Agent({self.name}: plan={self.plan.name}, env={type(self.environment).__name__})"


def assemble(
    config: dict,
    plan: str = "dp",
    policy: str = None,
    environment: str = "basic",
    policy_config: dict = None,
    name: str = None,
) -> Agent:
    """Factory: build an agent from config + component names.

    Args:
        config: Full experiment YAML config.
        plan: "naive", "lp", or "dp".
        policy: "passive", "reactive", or "proactive". If None, uses default for environment.
        environment: "basic", "mid", or "connected".
        policy_config: Optional dict of kwargs for the policy constructor.
        name: Agent name for display. Auto-generated if None.

    Returns:
        Assembled Agent ready for execution.
    """
    # Resolve defaults
    if policy is None:
        policy = DEFAULT_POLICY[environment]
    if policy_config is None:
        policy_config = {}
    if name is None:
        env_letter = {"basic": "A", "mid": "B", "connected": "C"}[environment]
        name = f"{plan.upper()}-{env_letter}"

    # Build components
    spec = ShipSpec.from_config(config)
    measurement = Measurement(spec, config)
    plan_obj = PLAN_REGISTRY[plan]()
    policy_obj = POLICY_REGISTRY[policy](**policy_config)
    env_obj = ENVIRONMENT_REGISTRY[environment]()

    return Agent(
        name=name,
        spec=spec,
        measurement=measurement,
        plan=plan_obj,
        policy=policy_obj,
        environment=env_obj,
    )
