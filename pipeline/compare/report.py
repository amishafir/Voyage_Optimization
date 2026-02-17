"""
Markdown report generation for cross-approach comparison.
"""

import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_report(comparison_df, forecast_errors, figure_paths, results, save_dir):
    """Generate a markdown comparison report.

    Args:
        comparison_df: DataFrame from build_comparison_table()
        forecast_errors: DataFrame from compute_forecast_error() or None
        figure_paths: dict {name: path} for figures
        results: dict {approach: result_dict}
        save_dir: directory to write report.md

    Returns:
        Path to the generated report.md
    """
    sections = []

    # 1. Header
    sections.append(_header_section(results))

    # 2. Comparison table
    sections.append(_comparison_table_section(comparison_df))

    # 3. Key findings
    sections.append(_key_findings_section(comparison_df, results))

    # 4. Theoretical bounds
    sections.append(_bounds_section(results))

    # 5. Forecast error summary
    sections.append(_forecast_error_section(forecast_errors))

    # 6. Decision points / re-planning
    decision_points = None
    if "dynamic_rh" in results:
        decision_points = results["dynamic_rh"].get("decision_points")
    sections.append(_decision_points_section(decision_points))

    # 7. Replan frequency sweep
    sections.append(_replan_sweep_section(results))

    # 8. Figures
    sections.append(_figures_section(figure_paths, save_dir))

    report = "\n\n".join(s for s in sections if s)

    os.makedirs(save_dir, exist_ok=True)
    report_path = os.path.join(save_dir, "report.md")
    with open(report_path, "w") as f:
        f.write(report)
        f.write("\n")

    logger.info("Report written: %s", report_path)
    return report_path


def _header_section(results):
    """Generate header with date, route, ship specs, ETA."""
    lines = ["# Comparison Report"]
    lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # Extract config from any available result
    config_snapshot = None
    for r in results.values():
        config_snapshot = r.get("config_snapshot")
        if config_snapshot:
            break

    if config_snapshot:
        ship = config_snapshot.get("ship", {})
        lines.append("\n## Ship & Route")
        lines.append(f"- Length: {ship.get('length_m', 'N/A')} m")
        lines.append(f"- Beam: {ship.get('beam_m', 'N/A')} m")
        lines.append(f"- Displacement: {ship.get('displacement_tonnes', 'N/A')} tonnes")
        lines.append(f"- Speed range: {ship.get('speed_range_knots', 'N/A')} knots")
        lines.append(f"- ETA constraint: {ship.get('eta_hours', 'N/A')} hours")

    return "\n".join(lines)


def _comparison_table_section(comparison_df):
    """Generate markdown table from comparison DataFrame."""
    if comparison_df.empty:
        return "## Comparison Table\n\nNo results available."

    lines = ["## Comparison Table"]

    col_map = [
        ("approach", "Approach"),
        ("planned_fuel_kg", "Plan Fuel (kg)"),
        ("simulated_fuel_kg", "Sim Fuel (kg)"),
        ("fuel_gap_pct", "Gap (%)"),
        ("planned_time_h", "Plan Time (h)"),
        ("simulated_time_h", "Sim Time (h)"),
        ("arrival_deviation_h", "Arr Dev (h)"),
        ("speed_changes", "Speed Chg"),
        ("co2_kg", "CO2 (kg)"),
        ("computation_time_s", "Comp Time (s)"),
        ("fuel_per_nm", "Fuel/NM"),
        ("avg_sog", "Avg SOG"),
    ]

    # Filter to columns that exist
    cols = [(k, lbl) for k, lbl in col_map if k in comparison_df.columns]
    keys = [k for k, _ in cols]
    headers = [lbl for _, lbl in cols]

    # Header row
    lines.append("")
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")

    # Data rows
    for _, row in comparison_df.iterrows():
        cells = []
        for key in keys:
            val = row[key]
            if val is None or (isinstance(val, float) and val != val):
                cells.append("N/A")
            elif isinstance(val, float):
                cells.append(f"{val:.4f}")
            elif isinstance(val, int):
                cells.append(str(val))
            else:
                cells.append(str(val))
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


def _key_findings_section(comparison_df, results):
    """Generate pairwise delta analysis."""
    lines = ["## Key Findings"]

    approaches = set(comparison_df["approach"].values) if not comparison_df.empty else set()

    # Value of dynamic weather: static vs dynamic_det
    if "static_det" in approaches and "dynamic_det" in approaches:
        static_row = comparison_df[comparison_df["approach"] == "static_det"].iloc[0]
        dyn_row = comparison_df[comparison_df["approach"] == "dynamic_det"].iloc[0]

        static_fuel = static_row["simulated_fuel_kg"]
        dyn_fuel = dyn_row["simulated_fuel_kg"]
        if static_fuel and static_fuel > 0:
            delta_pct = (dyn_fuel - static_fuel) / static_fuel * 100
            lines.append(f"\n**Value of dynamic weather**: Dynamic DP simulated fuel is "
                         f"{delta_pct:+.2f}% vs Static LP ({dyn_fuel:.2f} vs {static_fuel:.2f} kg)")

        # Gap comparison
        static_gap = static_row["fuel_gap_pct"]
        dyn_gap = dyn_row["fuel_gap_pct"]
        if static_gap is not None and dyn_gap is not None:
            lines.append(f"- Static LP plan-vs-sim gap: {static_gap:+.2f}%")
            lines.append(f"- Dynamic DP plan-vs-sim gap: {dyn_gap:+.2f}%")

    # Value of re-planning: dynamic_det vs dynamic_rh
    if "dynamic_det" in approaches and "dynamic_rh" in approaches:
        dyn_row = comparison_df[comparison_df["approach"] == "dynamic_det"].iloc[0]
        rh_row = comparison_df[comparison_df["approach"] == "dynamic_rh"].iloc[0]

        dyn_gap = dyn_row["fuel_gap_pct"]
        rh_gap = rh_row["fuel_gap_pct"]
        if dyn_gap is not None and rh_gap is not None:
            lines.append(f"\n**Value of re-planning**: Rolling Horizon gap is {rh_gap:+.2f}% "
                         f"vs Dynamic DP gap of {dyn_gap:+.2f}%")
            lines.append(f"- RH achieves a tighter plan-to-simulation match "
                         f"({'yes' if abs(rh_gap) < abs(dyn_gap) else 'no'})")

    if len(lines) == 1:
        lines.append("\nInsufficient data for pairwise comparison (need at least 2 approaches).")

    return "\n".join(lines)


def _forecast_error_section(forecast_errors):
    """Generate forecast error summary at key lead times."""
    lines = ["## Forecast Error Summary"]

    if forecast_errors is None or forecast_errors.empty:
        lines.append("\nForecast error analysis: N/A (no HDF5 data or no overlapping hours)")
        return "\n".join(lines)

    fields = forecast_errors["field"].unique()
    lead_times = sorted(forecast_errors["lead_time_h"].unique())

    # Show RMSE at a few key lead times
    key_leads = [lt for lt in [0, 6, 12, 24, 48] if lt in lead_times]
    if not key_leads:
        key_leads = lead_times[:5]

    lines.append("")
    header = "| Field | " + " | ".join(f"LT={lt}h" for lt in key_leads) + " |"
    sep = "| --- | " + " | ".join("---" for _ in key_leads) + " |"
    lines.append(header)
    lines.append(sep)

    field_labels = {
        "wind_speed_10m_kmh": "Wind Speed (km/h)",
        "wave_height_m": "Wave Height (m)",
        "ocean_current_velocity_kmh": "Current Vel (km/h)",
    }

    for field in fields:
        label = field_labels.get(field, field)
        cells = []
        for lt in key_leads:
            row = forecast_errors[
                (forecast_errors["field"] == field) & (forecast_errors["lead_time_h"] == lt)
            ]
            if row.empty:
                cells.append("N/A")
            else:
                cells.append(f"{row.iloc[0]['rmse']:.4f}")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    return "\n".join(lines)


def _decision_points_section(decision_points):
    """Generate summary of RH re-planning behavior."""
    lines = ["## Decision Points (Rolling Horizon)"]

    if not decision_points:
        lines.append("\nNo rolling horizon decision points available.")
        return "\n".join(lines)

    n = len(decision_points)
    first = decision_points[0]
    last = decision_points[-1]

    lines.append(f"\n- Total re-plan events: {n}")
    lines.append(f"- First decision: hour {first['decision_hour']}, "
                 f"DP planned fuel = {first['dp_planned_fuel_kg']:.2f} kg")
    lines.append(f"- Last decision: hour {last['decision_hour']}, "
                 f"DP planned fuel = {last['dp_planned_fuel_kg']:.2f} kg")

    # Show how the estimate converged
    initial_est = first["dp_planned_fuel_kg"]
    final_elapsed = last["elapsed_fuel_kg"]
    lines.append(f"- Initial total estimate: {initial_est:.2f} kg")
    lines.append(f"- Final elapsed fuel: {final_elapsed:.2f} kg")

    # All statuses
    statuses = set(dp["dp_status"] for dp in decision_points)
    lines.append(f"- Solver statuses: {', '.join(sorted(statuses))}")

    return "\n".join(lines)


def _bounds_section(results):
    """Generate theoretical bounds analysis."""
    lines = ["## Theoretical Bounds"]

    has_lower = "lower_bound" in results
    has_upper = "upper_bound" in results

    if not has_lower and not has_upper:
        lines.append("\nNo bounds data available (run `sensitivity` first).")
        return "\n".join(lines)

    if has_lower:
        lb_fuel = results["lower_bound"]["simulated"]["total_fuel_kg"]
        lines.append(f"\n- **Lower bound** (perfect information): {lb_fuel:.2f} kg")
    if has_upper:
        ub_fuel = results["upper_bound"]["simulated"]["total_fuel_kg"]
        lines.append(f"- **Upper bound** (constant speed, no optimization): {ub_fuel:.2f} kg")

    if has_lower and has_upper:
        span = ub_fuel - lb_fuel
        lines.append(f"- **Optimization span**: {span:.2f} kg ({span / ub_fuel * 100:.1f}% of upper bound)")

        # Show where each core approach falls
        lines.append("")
        core_approaches = ["static_det", "dynamic_det", "dynamic_rh"]
        core_labels = {"static_det": "Static LP", "dynamic_det": "Dynamic DP",
                       "dynamic_rh": "Rolling Horizon"}
        for approach in core_approaches:
            if approach not in results:
                continue
            fuel = results[approach]["simulated"]["total_fuel_kg"]
            if span > 0:
                position = (fuel - lb_fuel) / span * 100
                captured = 100 - position
                lines.append(f"- **{core_labels[approach]}**: {fuel:.2f} kg "
                             f"({captured:.1f}% of optimization potential captured)")

    return "\n".join(lines)


def _replan_sweep_section(results):
    """Generate replan frequency sensitivity summary."""
    lines = ["## Replan Frequency Sensitivity"]

    sweep = {}
    for approach, r in results.items():
        if approach.startswith("dynamic_rh_replan_"):
            suffix = approach.replace("dynamic_rh_replan_", "").rstrip("h")
            try:
                freq = int(suffix)
            except ValueError:
                continue
            sweep[freq] = r["simulated"]["total_fuel_kg"]

    if not sweep:
        lines.append("\nNo replan sweep data available (run `sensitivity` first).")
        return "\n".join(lines)

    freqs = sorted(sweep.keys())
    lines.append("")
    lines.append("| Replan Freq (h) | Sim Fuel (kg) |")
    lines.append("| --- | --- |")
    for freq in freqs:
        lines.append(f"| {freq} | {sweep[freq]:.2f} |")

    # Diminishing returns analysis
    if len(freqs) >= 2:
        best_fuel = sweep[freqs[0]]
        worst_fuel = sweep[freqs[-1]]
        delta = worst_fuel - best_fuel
        lines.append(f"\n- Range: {delta:.2f} kg between {freqs[0]}h and {freqs[-1]}h replan")
        if worst_fuel > 0:
            lines.append(f"- Relative impact: {delta / worst_fuel * 100:.2f}%")
        lines.append("- More frequent replanning uses fresher forecasts, reducing fuel; "
                      "diminishing returns beyond a certain point.")

    return "\n".join(lines)


def _figures_section(figure_paths, save_dir):
    """Generate markdown image references."""
    if not figure_paths:
        return "## Figures\n\nNo figures generated."

    lines = ["## Figures"]

    captions = {
        "speed_profiles": "Speed profiles (SWS) across the voyage for each approach",
        "fuel_curves": "Cumulative fuel consumption along the route",
        "fuel_comparison": "Planned vs simulated total fuel by approach",
        "forecast_error": "Forecast error (RMSE) as a function of lead time",
        "replan_evolution": "Rolling Horizon re-planning: optimizer convergence over time",
        "replan_sensitivity": "Fuel consumption vs replan frequency with theoretical bounds",
    }

    for name in ["speed_profiles", "fuel_curves", "fuel_comparison",
                  "forecast_error", "replan_evolution", "replan_sensitivity"]:
        if name not in figure_paths or figure_paths[name] is None:
            continue
        # Use relative path from report location
        rel = os.path.relpath(figure_paths[name], save_dir)
        caption = captions.get(name, name)
        lines.append(f"\n### {caption}")
        lines.append(f"![{caption}]({rel})")

    return "\n".join(lines)
