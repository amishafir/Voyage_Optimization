"""Ship specification — pure data container, no logic."""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ShipSpec:
    """Immutable ship engineering parameters."""

    length_m: float
    beam_m: float
    draft_m: float
    displacement_tonnes: float
    block_coefficient: float
    rated_power_kw: float
    speed_range: Tuple[float, float]  # (min_sws, max_sws) in knots
    eta_hours: float
    eta_penalty_mt_per_hour: float = None  # None = hard ETA, finite = soft ETA

    @classmethod
    def from_config(cls, config: dict) -> "ShipSpec":
        """Build from experiment YAML config['ship']."""
        ship = config["ship"]
        sr = ship["speed_range_knots"]
        return cls(
            length_m=ship["length_m"],
            beam_m=ship["beam_m"],
            draft_m=ship["draft_m"],
            displacement_tonnes=ship["displacement_tonnes"],
            block_coefficient=ship["block_coefficient"],
            rated_power_kw=ship["rated_power_kw"],
            speed_range=(sr[0], sr[1]),
            eta_hours=ship["eta_hours"],
            eta_penalty_mt_per_hour=ship.get("eta_penalty_mt_per_hour"),
        )

    @property
    def min_sws(self) -> float:
        return self.speed_range[0]

    @property
    def max_sws(self) -> float:
        return self.speed_range[1]
