"""
Comparison framework: load result JSONs, compute cross-approach metrics,
and orchestrate figure generation and report writing.
"""

import glob
import json
import logging
import os

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def load_results(output_dir):
    """Load all result_*.json files from output_dir, keyed by approach name.

    Returns:
        dict: {approach_name: result_dict}
    """
    results = {}
    pattern = os.path.join(output_dir, "result_*.json")
    for path in sorted(glob.glob(pattern)):
        try:
            with open(path) as f:
                result = json.load(f)
            approach = result["approach"]
            results[approach] = result
            logger.info("Loaded result: %s", approach)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Skipping unparseable result file %s: %s", path, e)
    return results


def load_time_series(output_dir, approaches):
    """Load timeseries CSVs for the given approaches.

    Returns:
        dict: {approach_name: DataFrame}
    """
    time_series = {}
    for approach in approaches:
        path = os.path.join(output_dir, f"timeseries_{approach}.csv")
        if os.path.isfile(path):
            time_series[approach] = pd.read_csv(path)
            logger.info("Loaded time series: %s (%d rows)", approach, len(time_series[approach]))
        else:
            logger.warning("Time series not found: %s", path)
    return time_series


def build_comparison_table(results):
    """Build a DataFrame with one row per approach and key comparison columns.

    Args:
        results: dict from load_results()

    Returns:
        pd.DataFrame with columns for planned/simulated fuel, time, metrics, etc.
    """
    rows = []
    for approach in sorted(results.keys()):
        r = results[approach]
        planned = r.get("planned", {})
        simulated = r.get("simulated", {})
        metrics = r.get("metrics", {})

        rows.append({
            "approach": approach,
            "planned_fuel_kg": planned.get("total_fuel_kg"),
            "simulated_fuel_kg": simulated.get("total_fuel_kg"),
            "fuel_gap_pct": metrics.get("fuel_gap_percent"),
            "planned_time_h": planned.get("voyage_time_h"),
            "simulated_time_h": simulated.get("voyage_time_h"),
            "arrival_deviation_h": simulated.get("arrival_deviation_h"),
            "speed_changes": simulated.get("speed_changes"),
            "co2_kg": simulated.get("co2_emissions_kg"),
            "computation_time_s": planned.get("computation_time_s"),
            "fuel_per_nm": metrics.get("fuel_per_nm"),
            "avg_sog": metrics.get("avg_sog_knots"),
        })

    return pd.DataFrame(rows)


def compute_forecast_error(hdf5_path):
    """Compute RMSE and MAE of predicted vs actual weather by lead time.

    Joins predicted weather (at sample_hour=0) with actual weather on
    (node_id, forecast_hour) = (node_id, sample_hour), then groups by
    lead_time = forecast_hour - 0 (since sample_hour of prediction is 0).

    Returns:
        pd.DataFrame with columns: lead_time_h, field, rmse, mae
        Returns None if HDF5 is missing or has no predicted data.
    """
    if not os.path.isfile(hdf5_path):
        logger.warning("HDF5 file not found, skipping forecast error: %s", hdf5_path)
        return None

    try:
        from shared.hdf5_io import read_actual, read_predicted
    except ImportError:
        logger.warning("Cannot import hdf5_io, skipping forecast error")
        return None

    actual = read_actual(hdf5_path)
    predicted = read_predicted(hdf5_path)

    if actual.empty or predicted.empty:
        logger.warning("No actual/predicted data in HDF5, skipping forecast error")
        return None

    # Get the set of actual sample hours
    actual_hours = set(actual["sample_hour"].unique())

    # Filter predicted to only forecast_hours that match actual sample hours
    predicted = predicted[predicted["forecast_hour"].isin(actual_hours)]
    if predicted.empty:
        logger.warning("No predicted data overlaps with actual hours")
        return None

    # Compute lead_time = forecast_hour - sample_hour (of prediction)
    predicted = predicted.copy()
    predicted["lead_time_h"] = predicted["forecast_hour"] - predicted["sample_hour"]

    # Fields to compare (skip directions and beaufort for clarity)
    fields = ["wind_speed_10m_kmh", "wave_height_m", "ocean_current_velocity_kmh"]

    rows = []
    for field in fields:
        # Join: for each (node_id, forecast_hour) in predicted,
        # match to actual where actual.sample_hour == predicted.forecast_hour
        merged = predicted.merge(
            actual[["node_id", "sample_hour", field]],
            left_on=["node_id", "forecast_hour"],
            right_on=["node_id", "sample_hour"],
            suffixes=("_pred", "_actual"),
        )

        if merged.empty:
            continue

        # Drop NaN (Port B issue)
        pred_col = f"{field}_pred"
        actual_col = f"{field}_actual"
        merged = merged.dropna(subset=[pred_col, actual_col])

        if merged.empty:
            continue

        # Group by lead_time_h
        for lead_time, group in merged.groupby("lead_time_h"):
            errors = group[pred_col] - group[actual_col]
            rows.append({
                "lead_time_h": int(lead_time),
                "field": field,
                "rmse": float(np.sqrt((errors ** 2).mean())),
                "mae": float(errors.abs().mean()),
                "n_points": len(group),
            })

    if not rows:
        return None

    return pd.DataFrame(rows)


def run_comparison(config, output_dir, hdf5_path):
    """Top-level orchestrator for comparison framework.

    1. Load results and time series
    2. Build comparison table
    3. Compute forecast error (if HDF5 available)
    4. Generate plots
    5. Generate markdown report
    6. Print summary

    Returns:
        Path to the generated report.md
    """
    from compare.plots import (
        plot_fuel_comparison,
        plot_fuel_curves,
        plot_forecast_error,
        plot_horizon_sensitivity,
        plot_replan_evolution,
        plot_replan_sensitivity,
        plot_speed_profiles,
    )
    from compare.report import generate_report

    # 1. Load results
    results = load_results(output_dir)
    if not results:
        logger.error("No result files found in %s", output_dir)
        print("Error: no result_*.json files found in output/")
        return None

    approaches = list(results.keys())
    if len(approaches) == 1:
        logger.warning("Only one approach found (%s), comparison will be limited", approaches[0])

    time_series = load_time_series(output_dir, approaches)

    # 2. Build comparison table
    comparison_df = build_comparison_table(results)

    # 3. Forecast error
    forecast_errors = None
    if hdf5_path and os.path.isfile(hdf5_path):
        forecast_errors = compute_forecast_error(hdf5_path)
    else:
        logger.info("No HDF5 file, skipping forecast error analysis")

    # 4. Generate figures
    comp_dir = os.path.join(output_dir, "comparison")
    fig_dir = os.path.join(comp_dir, "figures")
    os.makedirs(fig_dir, exist_ok=True)

    figure_paths = {}

    if time_series:
        figure_paths["speed_profiles"] = plot_speed_profiles(time_series, fig_dir)
        figure_paths["fuel_curves"] = plot_fuel_curves(time_series, fig_dir)

    if results:
        figure_paths["fuel_comparison"] = plot_fuel_comparison(results, fig_dir)

    if forecast_errors is not None:
        figure_paths["forecast_error"] = plot_forecast_error(forecast_errors, fig_dir)

    # Decision points from RH result
    decision_points = None
    if "dynamic_rh" in results:
        decision_points = results["dynamic_rh"].get("decision_points")
    if decision_points:
        figure_paths["replan_evolution"] = plot_replan_evolution(decision_points, fig_dir)

    # Replan sensitivity plot (if sweep results exist)
    has_sweep = any(a.startswith("dynamic_rh_replan_") for a in results)
    if has_sweep:
        figure_paths["replan_sensitivity"] = plot_replan_sensitivity(results, fig_dir)

    # Horizon sensitivity plot (if horizon sweep results exist)
    has_horizon = any(a.startswith("dynamic_det_horizon_") or a.startswith("dynamic_rh_horizon_")
                      for a in results)
    if has_horizon:
        figure_paths["horizon_sensitivity"] = plot_horizon_sensitivity(results, fig_dir)

    # 5. Generate report
    report_path = generate_report(
        comparison_df, forecast_errors, figure_paths, results, comp_dir
    )

    # 6. Print summary
    print("\n=== Comparison Summary ===\n")
    _print_table(comparison_df)

    return report_path


def _print_table(df):
    """Print a formatted comparison table to console."""
    display_cols = {
        "approach": "Approach",
        "planned_fuel_kg": "Plan Fuel (kg)",
        "simulated_fuel_kg": "Sim Fuel (kg)",
        "fuel_gap_pct": "Gap (%)",
        "simulated_time_h": "Sim Time (h)",
        "arrival_deviation_h": "Arr Dev (h)",
        "fuel_per_nm": "Fuel/NM",
        "avg_sog": "Avg SOG",
    }

    headers = []
    col_keys = []
    for key, label in display_cols.items():
        if key in df.columns:
            headers.append(label)
            col_keys.append(key)

    # Compute column widths
    widths = [len(h) for h in headers]
    str_rows = []
    for _, row in df.iterrows():
        str_row = []
        for i, key in enumerate(col_keys):
            val = row[key]
            if isinstance(val, float):
                s = f"{val:.4f}"
            elif val is None:
                s = "N/A"
            else:
                s = str(val)
            widths[i] = max(widths[i], len(s))
            str_row.append(s)
        str_rows.append(str_row)

    # Print
    header_line = "  ".join(h.rjust(w) for h, w in zip(headers, widths))
    print(header_line)
    print("  ".join("-" * w for w in widths))
    for str_row in str_rows:
        print("  ".join(s.rjust(w) for s, w in zip(str_row, widths)))
    print()
