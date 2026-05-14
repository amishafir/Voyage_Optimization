"""
Matplotlib figure generation for cross-approach comparison.

All figures are saved as PNG files. Uses Agg backend for headless environments.
"""

import logging
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

STYLES = {
    "static_det":  {"color": "#2196F3", "label": "Static LP",       "ls": "-"},
    "dynamic_det": {"color": "#FF9800", "label": "Dynamic DP",      "ls": "--"},
    "dynamic_rh":  {"color": "#4CAF50", "label": "Rolling Horizon", "ls": "-."},
    "lower_bound": {"color": "#8BC34A", "label": "Lower Bound",     "ls": ":"},
    "upper_bound": {"color": "#F44336", "label": "Upper Bound",     "ls": ":"},
}

# Auto-assign colors for sweep variants and other unknown approaches
_AUTO_COLORS = ["#9C27B0", "#00BCD4", "#FF5722", "#795548", "#607D8B",
                "#E91E63", "#009688", "#CDDC39", "#3F51B5", "#FFC107"]


def _style(approach):
    if approach in STYLES:
        return STYLES[approach]
    # Auto-generate a style for unknown approaches (e.g. sweep variants)
    idx = hash(approach) % len(_AUTO_COLORS)
    return {"color": _AUTO_COLORS[idx], "label": approach, "ls": "--"}


def _save(fig, save_dir, name):
    path = os.path.join(save_dir, f"{name}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved figure: %s", path)
    return path


def _segment_boundaries(df):
    """Return cumulative distances where segment changes."""
    boundaries = []
    prev_seg = None
    for _, row in df.iterrows():
        seg = row.get("segment")
        if seg is not None and seg != prev_seg and prev_seg is not None:
            boundaries.append(row["cum_distance_nm"])
        prev_seg = seg
    return boundaries


def plot_speed_profiles(time_series, save_dir):
    """Figure 1: SWS vs cumulative distance, one line per approach.

    Args:
        time_series: dict {approach: DataFrame}
        save_dir: directory to save the figure

    Returns:
        Path to saved PNG.
    """
    fig, ax = plt.subplots(figsize=(12, 5))

    # Draw segment boundaries from first available time series
    first_df = next(iter(time_series.values()))
    for x in _segment_boundaries(first_df):
        ax.axvline(x, color="lightgray", linewidth=0.5, zorder=0)

    for approach in sorted(time_series.keys()):
        df = time_series[approach]
        s = _style(approach)
        ax.plot(
            df["cum_distance_nm"], df["sws_knots"],
            color=s["color"], linestyle=s["ls"], label=s["label"],
            linewidth=1.2, alpha=0.9,
        )

    ax.set_xlabel("Cumulative Distance (nm)")
    ax.set_ylabel("Ship Water Speed (knots)")
    ax.set_title("Speed Profiles by Approach")
    ax.legend()
    ax.grid(True, alpha=0.3)

    return _save(fig, save_dir, "speed_profiles")


def plot_fuel_curves(time_series, save_dir):
    """Figure 2: Cumulative fuel vs cumulative distance, one line per approach.

    Args:
        time_series: dict {approach: DataFrame}
        save_dir: directory to save the figure

    Returns:
        Path to saved PNG.
    """
    fig, ax = plt.subplots(figsize=(12, 5))

    for approach in sorted(time_series.keys()):
        df = time_series[approach]
        s = _style(approach)
        ax.plot(
            df["cum_distance_nm"], df["cum_fuel_mt"],
            color=s["color"], linestyle=s["ls"], label=s["label"],
            linewidth=1.2, alpha=0.9,
        )

    ax.set_xlabel("Cumulative Distance (nm)")
    ax.set_ylabel("Cumulative Fuel (mt)")
    ax.set_title("Fuel Consumption Curves")
    ax.legend()
    ax.grid(True, alpha=0.3)

    return _save(fig, save_dir, "fuel_curves")


def plot_fuel_comparison(results, save_dir):
    """Figure 3: Grouped bar chart — planned vs simulated fuel per approach.

    Args:
        results: dict {approach: result_dict}
        save_dir: directory to save the figure

    Returns:
        Path to saved PNG.
    """
    approaches = sorted(results.keys())
    labels = [_style(a)["label"] for a in approaches]
    planned = [results[a]["planned"]["total_fuel_mt"] for a in approaches]
    simulated = [results[a]["simulated"]["total_fuel_mt"] for a in approaches]
    gaps = [results[a]["metrics"]["fuel_gap_percent"] for a in approaches]

    x = np.arange(len(approaches))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    bars1 = ax.bar(x - width / 2, planned, width, label="Planned", color="#64B5F6", edgecolor="white")
    bars2 = ax.bar(x + width / 2, simulated, width, label="Simulated", color="#EF5350", edgecolor="white")

    # Annotate fuel gap above each pair
    for i, gap in enumerate(gaps):
        y_max = max(planned[i], simulated[i])
        ax.annotate(
            f"{gap:+.2f}%",
            xy=(x[i], y_max),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center", fontsize=9,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Total Fuel (mt)")
    ax.set_title("Planned vs Simulated Fuel Consumption")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)

    return _save(fig, save_dir, "fuel_comparison")


def plot_forecast_error(forecast_errors_df, save_dir):
    """Figure 4: RMSE vs lead time for wind speed, wave height, current velocity.

    Args:
        forecast_errors_df: DataFrame with lead_time_h, field, rmse, mae columns.
            None to skip.
        save_dir: directory to save the figure

    Returns:
        Path to saved PNG, or None if skipped.
    """
    if forecast_errors_df is None or forecast_errors_df.empty:
        logger.info("No forecast error data, skipping plot")
        return None

    fields = ["wind_speed_10m_kmh", "wave_height_m", "ocean_current_velocity_kmh"]
    field_labels = {
        "wind_speed_10m_kmh": ("Wind Speed RMSE", "km/h"),
        "wave_height_m": ("Wave Height RMSE", "m"),
        "ocean_current_velocity_kmh": ("Current Velocity RMSE", "km/h"),
    }

    available = [f for f in fields if f in forecast_errors_df["field"].values]
    if not available:
        return None

    fig, axes = plt.subplots(1, len(available), figsize=(5 * len(available), 4), squeeze=False)

    for i, field in enumerate(available):
        ax = axes[0, i]
        subset = forecast_errors_df[forecast_errors_df["field"] == field].sort_values("lead_time_h")
        label, unit = field_labels[field]
        ax.plot(subset["lead_time_h"], subset["rmse"], "o-", markersize=3, linewidth=1.2)
        ax.set_xlabel("Lead Time (h)")
        ax.set_ylabel(f"RMSE ({unit})")
        ax.set_title(label)
        ax.grid(True, alpha=0.3)

    fig.suptitle("Forecast Error vs Lead Time", fontsize=13, y=1.02)
    fig.tight_layout()

    return _save(fig, save_dir, "forecast_error")


def plot_replan_evolution(decision_points, save_dir):
    """Figure 5: Re-planning evolution — DP planned fuel and elapsed fuel vs decision hour.

    Args:
        decision_points: list of dicts from RH result's decision_points field.
            None or empty to skip.
        save_dir: directory to save the figure

    Returns:
        Path to saved PNG, or None if skipped.
    """
    if not decision_points:
        logger.info("No decision points, skipping replan evolution plot")
        return None

    df = pd.DataFrame(decision_points)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

    # Top: DP planned total fuel at each decision point
    ax1.plot(
        df["decision_hour"], df["dp_planned_fuel_mt"],
        "o-", color="#4CAF50", markersize=4, linewidth=1.2,
        label="DP planned total fuel",
    )
    ax1.set_ylabel("DP Planned Fuel (mt)")
    ax1.set_title("Optimizer Estimate Convergence")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Bottom: Elapsed fuel
    ax2.plot(
        df["decision_hour"], df["elapsed_fuel_mt"],
        "s-", color="#FF9800", markersize=4, linewidth=1.2,
        label="Elapsed fuel (actual)",
    )
    ax2.set_xlabel("Decision Hour")
    ax2.set_ylabel("Elapsed Fuel (mt)")
    ax2.set_title("Fuel Consumed at Each Re-plan Point")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()

    return _save(fig, save_dir, "replan_evolution")


def plot_replan_sensitivity(results, save_dir):
    """Figure 6: Simulated fuel vs replan frequency, with reference lines.

    Args:
        results: dict {approach: result_dict} — must contain sweep variants.
        save_dir: directory to save the figure.

    Returns:
        Path to saved PNG, or None if no sweep data.
    """
    # Extract sweep results
    sweep = {}
    for approach, r in results.items():
        if approach.startswith("dynamic_rh_replan_"):
            # Parse frequency from "dynamic_rh_replan_6h"
            suffix = approach.replace("dynamic_rh_replan_", "").rstrip("h")
            try:
                freq = int(suffix)
            except ValueError:
                continue
            sweep[freq] = r["simulated"]["total_fuel_mt"]

    if not sweep:
        logger.info("No replan sweep data, skipping sensitivity plot")
        return None

    freqs = sorted(sweep.keys())
    fuels = [sweep[f] for f in freqs]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(freqs, fuels, "o-", color="#4CAF50", markersize=6, linewidth=1.5,
            label="RH sweep", zorder=5)

    # Reference lines for other approaches
    ref_approaches = [
        ("upper_bound", "#F44336", "Upper Bound"),
        ("lower_bound", "#8BC34A", "Lower Bound"),
        ("static_det", "#2196F3", "Static LP"),
        ("dynamic_det", "#FF9800", "Dynamic DP"),
    ]
    for ref_key, color, label in ref_approaches:
        if ref_key in results:
            fuel = results[ref_key]["simulated"]["total_fuel_mt"]
            ax.axhline(fuel, color=color, linestyle=":", linewidth=1.2, alpha=0.8)
            ax.annotate(f"{label} ({fuel:.1f})",
                        xy=(freqs[-1], fuel),
                        xytext=(5, 0), textcoords="offset points",
                        fontsize=8, color=color, va="center")

    ax.set_xlabel("Replan Frequency (hours)")
    ax.set_ylabel("Simulated Fuel (mt)")
    ax.set_title("Replan Frequency Sensitivity")
    ax.set_xticks(freqs)
    ax.legend()
    ax.grid(True, alpha=0.3)

    return _save(fig, save_dir, "replan_sensitivity")


def plot_horizon_sensitivity(results, save_dir):
    """Figure 7: Simulated fuel vs forecast horizon for DP and RH.

    Args:
        results: dict {approach: result_dict} — must contain horizon sweep variants.
        save_dir: directory to save the figure.

    Returns:
        Path to saved PNG, or None if no horizon sweep data.
    """
    dd_sweep = {}
    rh_sweep = {}
    for approach, r in results.items():
        if approach.startswith("dynamic_det_horizon_"):
            suffix = approach.replace("dynamic_det_horizon_", "").rstrip("h")
            try:
                dd_sweep[int(suffix)] = r["simulated"]["total_fuel_mt"]
            except ValueError:
                continue
        elif approach.startswith("dynamic_rh_horizon_"):
            suffix = approach.replace("dynamic_rh_horizon_", "").rstrip("h")
            try:
                rh_sweep[int(suffix)] = r["simulated"]["total_fuel_mt"]
            except ValueError:
                continue

    if not dd_sweep and not rh_sweep:
        logger.info("No horizon sweep data, skipping plot")
        return None

    fig, ax = plt.subplots(figsize=(8, 5))

    if dd_sweep:
        horizons = sorted(dd_sweep.keys())
        fuels = [dd_sweep[h] for h in horizons]
        days = [h / 24 for h in horizons]
        ax.plot(days, fuels, "s-", color="#FF9800", markersize=6, linewidth=1.5,
                label="Dynamic DP", zorder=5)

    if rh_sweep:
        horizons = sorted(rh_sweep.keys())
        fuels = [rh_sweep[h] for h in horizons]
        days = [h / 24 for h in horizons]
        ax.plot(days, fuels, "o-", color="#4CAF50", markersize=6, linewidth=1.5,
                label="Rolling Horizon", zorder=5)

    # Reference lines
    ref_approaches = [
        ("upper_bound", "#F44336", "Upper Bound"),
        ("lower_bound", "#8BC34A", "Lower Bound"),
        ("static_det", "#2196F3", "Static LP"),
    ]
    for ref_key, color, label in ref_approaches:
        if ref_key in results:
            fuel = results[ref_key]["simulated"]["total_fuel_mt"]
            ax.axhline(fuel, color=color, linestyle=":", linewidth=1.2, alpha=0.8)
            # Place label at rightmost x
            x_max = max(
                max((h / 24 for h in dd_sweep), default=0),
                max((h / 24 for h in rh_sweep), default=0),
            )
            ax.annotate(f"{label} ({fuel:.1f})",
                        xy=(x_max, fuel),
                        xytext=(5, 0), textcoords="offset points",
                        fontsize=8, color=color, va="center")

    ax.set_xlabel("Forecast Horizon (days)")
    ax.set_ylabel("Simulated Fuel (mt)")
    ax.set_title("Forecast Horizon Sensitivity")
    ax.legend()
    ax.grid(True, alpha=0.3)

    return _save(fig, save_dir, "horizon_sensitivity")
