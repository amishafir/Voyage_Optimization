#!/usr/bin/env python3
"""Tests for the 3-agent cycle executor.

Tests weather assembly, cycle re-plan timing, and end-to-end execution.

Usage:
    cd pipeline
    python3 -m pytest tests/test_3agent.py -v
"""

import os
import sys
import math

pipeline_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if pipeline_dir not in sys.path:
    sys.path.insert(0, pipeline_dir)

import pytest
import yaml

# ---------------------------------------------------------------------------
# Config and paths
# ---------------------------------------------------------------------------

ROUTE_D_HDF5 = os.path.join(pipeline_dir, "data", "experiment_d_391wp.h5")
ROUTE_D_CONFIG = os.path.join(pipeline_dir, "config", "experiment_3agent_d.yaml")

HAS_DATA = os.path.exists(ROUTE_D_HDF5)
skip_no_data = pytest.mark.skipif(not HAS_DATA, reason="Route D HDF5 not available locally")


def load_config():
    with open(ROUTE_D_CONFIG) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Unit tests: weather assembler
# ---------------------------------------------------------------------------

class TestWeatherAssembler:

    def test_assemble_naive_returns_none(self):
        from agent.weather_assembler import assemble_naive
        grid, max_fh = assemble_naive()
        assert grid is None
        assert max_fh == 0

    def test_assemble_deterministic_constant_weather(self):
        """Deterministic grid should have same weather at every forecast hour."""
        from agent.weather_assembler import assemble_deterministic

        fake_actual = {
            0: {
                1: {"wind_speed_10m_kmh": 20.0, "wind_direction_10m_deg": 90.0,
                    "beaufort_number": 5, "wave_height_m": 2.0,
                    "ocean_current_velocity_kmh": 3.0, "ocean_current_direction_deg": 180.0},
                2: {"wind_speed_10m_kmh": 15.0, "wind_direction_10m_deg": 45.0,
                    "beaufort_number": 4, "wave_height_m": 1.5,
                    "ocean_current_velocity_kmh": 2.0, "ocean_current_direction_deg": 90.0},
            }
        }
        grid, max_fh = assemble_deterministic(
            actual_weather=fake_actual,
            sample_hour=0,
            node_ids=[1, 2],
            max_forecast_hour_needed=24.0,
        )

        assert max_fh == 24
        assert 1 in grid
        assert 2 in grid
        # All forecast hours should have same weather for node 1
        wx_0 = grid[1][0]
        wx_12 = grid[1][12]
        wx_24 = grid[1][24]
        assert wx_0["wind_speed_10m_kmh"] == wx_12["wind_speed_10m_kmh"] == wx_24["wind_speed_10m_kmh"] == 20.0
        # Node 2 should have different weather than node 1
        assert grid[2][0]["wind_speed_10m_kmh"] == 15.0

    def test_assemble_stochastic_injects_actuals(self):
        """Stochastic should inject actuals for near-term, keep forecast for far."""
        from agent.weather_assembler import assemble_stochastic

        fake_actual = {
            6: {
                1: {"wind_speed_10m_kmh": 25.0, "wind_direction_10m_deg": 90.0,
                    "beaufort_number": 6, "wave_height_m": 3.0,
                    "ocean_current_velocity_kmh": 4.0, "ocean_current_direction_deg": 180.0},
            }
        }
        fake_predicted = {
            6: {
                1: {
                    6: {"wind_speed_10m_kmh": 20.0, "wind_direction_10m_deg": 90.0,
                        "beaufort_number": 5, "wave_height_m": 2.0,
                        "ocean_current_velocity_kmh": 3.0, "ocean_current_direction_deg": 180.0},
                    12: {"wind_speed_10m_kmh": 18.0, "wind_direction_10m_deg": 90.0,
                         "beaufort_number": 4, "wave_height_m": 1.8,
                         "ocean_current_velocity_kmh": 2.5, "ocean_current_direction_deg": 180.0},
                    18: {"wind_speed_10m_kmh": 22.0, "wind_direction_10m_deg": 90.0,
                         "beaufort_number": 5, "wave_height_m": 2.5,
                         "ocean_current_velocity_kmh": 3.5, "ocean_current_direction_deg": 180.0},
                },
            }
        }

        grid, max_fh = assemble_stochastic(
            actual_weather=fake_actual,
            predicted_grids=fake_predicted,
            max_forecast_hours={6: 18},
            sample_hour=6,
            node_ids=[1],
            elapsed_time=6.0,
            replan_freq=6,
        )

        # Near-term (fh=6..11): should be actual (25.0 km/h wind)
        assert grid[1][6]["wind_speed_10m_kmh"] == 25.0
        # Far-term (fh=18): should be forecast (22.0 km/h wind)
        assert grid[1][18]["wind_speed_10m_kmh"] == 22.0


# ---------------------------------------------------------------------------
# Integration tests: cycle executor (require HDF5 data)
# ---------------------------------------------------------------------------

class TestCycleExecutor:

    @skip_no_data
    def test_naive_completes(self):
        """Naive agent should complete the voyage."""
        from agent.cycle_executor import execute_cycle_voyage
        config = load_config()
        result = execute_cycle_voyage("naive", ROUTE_D_HDF5, config)
        assert result["status"] == "Completed"
        assert result["total_fuel_mt"] > 0
        assert result["total_time_h"] > 0

    @skip_no_data
    def test_deterministic_completes(self):
        """Deterministic agent should complete the voyage."""
        from agent.cycle_executor import execute_cycle_voyage
        config = load_config()
        result = execute_cycle_voyage("deterministic", ROUTE_D_HDF5, config)
        assert result["status"] == "Completed"
        assert result["total_fuel_mt"] > 0

    @skip_no_data
    def test_stochastic_completes(self):
        """Stochastic agent should complete the voyage."""
        from agent.cycle_executor import execute_cycle_voyage
        config = load_config()
        result = execute_cycle_voyage("stochastic", ROUTE_D_HDF5, config)
        assert result["status"] == "Completed"
        assert result["total_fuel_mt"] > 0

    @skip_no_data
    def test_replan_at_nwp_boundaries(self):
        """Re-plan log should show NWP-aligned hours (0, 6, 12, ...)."""
        from agent.cycle_executor import execute_cycle_voyage
        config = load_config()
        result = execute_cycle_voyage("naive", ROUTE_D_HDF5, config)

        nwp_hours = [entry["nwp_hour"] for entry in result["replan_log"]]
        for h in nwp_hours:
            assert h % 6 == 0, f"Re-plan at non-NWP hour: {h}"

    @skip_no_data
    def test_no_mid_cycle_replans(self):
        """All re-plans should be in the replan_log (no hidden reactive replans)."""
        from agent.cycle_executor import execute_cycle_voyage
        config = load_config()
        result = execute_cycle_voyage("deterministic", ROUTE_D_HDF5, config)

        # Number of re-plans should match the number of NWP cycles
        expected_cycles = len(range(0, config["ship"]["eta_hours"] + 6, 6))
        # Should be close but may be fewer if voyage ends mid-cycle
        assert result["replan_count"] <= expected_cycles
        assert result["replan_count"] == len(result["replan_log"])

    @skip_no_data
    def test_all_legs_executed(self):
        """Time series should cover all legs."""
        from agent.cycle_executor import execute_cycle_voyage
        from shared.hdf5_io import read_metadata
        config = load_config()
        result = execute_cycle_voyage("naive", ROUTE_D_HDF5, config)

        metadata = read_metadata(ROUTE_D_HDF5)
        expected_legs = len(metadata) - 1
        assert len(result["time_series"]) == expected_legs

    @skip_no_data
    def test_fuel_in_reasonable_range(self):
        """Fuel should be in a reasonable range for Route D."""
        from agent.cycle_executor import execute_cycle_voyage
        config = load_config()
        result = execute_cycle_voyage("deterministic", ROUTE_D_HDF5, config)

        # Route D reference: 214-218 mt for various agents
        fuel = result["total_fuel_mt"]
        assert 150 < fuel < 300, f"Fuel {fuel:.2f} mt outside reasonable range"


# ---------------------------------------------------------------------------
# Runner test
# ---------------------------------------------------------------------------

class TestRunner:

    @skip_no_data
    def test_run_3agent(self):
        """Runner should produce results for all 3 agents."""
        from agent.new_runner import run_3agent
        config = load_config()
        results = run_3agent(config, ROUTE_D_HDF5)

        assert len(results) == 3
        agents = {r["agent"] for r in results}
        assert agents == {"Naive", "Deterministic", "Stochastic"}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Run without pytest
    import unittest

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for test_class in [TestWeatherAssembler, TestCycleExecutor, TestRunner]:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
