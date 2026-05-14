"""
Thesis analysis scripts for:
  4. Forecast error vs lead time curve (+ inter-forecast spread proxy)
  6. SWS violation magnitude distribution

Produces thesis-ready figures in pipeline/output/comparison/figures/thesis_*.png
"""

import json
import logging
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
FIG_DIR = os.path.join(OUTPUT_DIR, "comparison", "figures")
HDF5_PATH = os.path.join(BASE_DIR, "data", "voyage_weather.h5")

os.makedirs(FIG_DIR, exist_ok=True)

# ── Style constants ──────────────────────────────────────────────────
APPROACH_STYLE = {
    "static_det":  {"color": "#2196F3", "label": "Static LP",       "marker": "s"},
    "dynamic_det": {"color": "#FF9800", "label": "Dynamic DP",      "marker": "^"},
    "dynamic_rh":  {"color": "#4CAF50", "label": "Rolling Horizon", "marker": "o"},
}


# =====================================================================
# TASK 4: Forecast Error vs Lead Time
# =====================================================================

def analysis_forecast_error(hdf5_path=None, output_suffix=""):
    """Compute and plot forecast error vs lead time.

    Part A: RMSE against actual weather (ground truth).
        With 12 samples: limited to 0-11h.
        With 144 samples: full 0-143h curve (the key missing thesis figure).
    Part B: Inter-forecast spread as proxy for uncertainty.

    Args:
        hdf5_path: Path to HDF5 file. Defaults to voyage_weather.h5.
        output_suffix: Suffix for output filenames (e.g. "_full" for exp_b data).

    Returns dict with DataFrames and figure paths.
    """
    sys.path.insert(0, BASE_DIR)
    from shared.hdf5_io import read_actual, read_predicted

    if hdf5_path is None:
        hdf5_path = HDF5_PATH

    actual = read_actual(hdf5_path)
    predicted = read_predicted(hdf5_path)

    fields = ["wind_speed_10m_kmh", "wave_height_m", "ocean_current_velocity_kmh"]
    field_labels = {
        "wind_speed_10m_kmh":          ("Wind Speed",       "km/h"),
        "wave_height_m":               ("Wave Height",      "m"),
        "ocean_current_velocity_kmh":  ("Current Velocity", "km/h"),
    }

    # ── Part A: RMSE vs actual (ground truth) ─────────────────────────
    actual_hours = set(actual["sample_hour"].unique())
    pred_filtered = predicted[predicted["forecast_hour"].isin(actual_hours)].copy()
    pred_filtered["lead_time_h"] = pred_filtered["forecast_hour"] - pred_filtered["sample_hour"]

    # Only positive lead times (forecasting INTO the future)
    pred_filtered = pred_filtered[pred_filtered["lead_time_h"] >= 0]

    rmse_rows = []
    for field in fields:
        merged = pred_filtered.merge(
            actual[["node_id", "sample_hour", field]],
            left_on=["node_id", "forecast_hour"],
            right_on=["node_id", "sample_hour"],
            suffixes=("_pred", "_actual"),
        )
        merged = merged.dropna(subset=[f"{field}_pred", f"{field}_actual"])

        for lead_time, group in merged.groupby("lead_time_h"):
            errors = group[f"{field}_pred"] - group[f"{field}_actual"]
            rmse_rows.append({
                "lead_time_h": int(lead_time),
                "field": field,
                "rmse": float(np.sqrt((errors ** 2).mean())),
                "mae": float(errors.abs().mean()),
                "bias": float(errors.mean()),
                "n_points": len(group),
            })

    rmse_df = pd.DataFrame(rmse_rows)

    # ── Part B: Inter-forecast spread (proxy for long-range error) ────
    # For each (node_id, forecast_hour), compute std of predictions across
    # different sample_hours. This shows how much forecasts "jitter" — a
    # proxy for forecast uncertainty even without ground truth.
    spread_rows = []
    for field in fields:
        for fh in sorted(predicted["forecast_hour"].unique()):
            if fh < 0:
                continue
            subset = predicted[predicted["forecast_hour"] == fh]
            if len(subset["sample_hour"].unique()) < 2:
                continue
            # Per-node std, then average across nodes
            node_stds = subset.dropna(subset=[field]).groupby("node_id")[field].std()
            if node_stds.empty:
                continue
            # lead_time = forecast_hour - mean(sample_hour) as representative
            mean_sample = subset["sample_hour"].mean()
            spread_rows.append({
                "forecast_hour": int(fh),
                "mean_lead_time_h": float(fh - mean_sample),
                "field": field,
                "mean_spread_std": float(node_stds.mean()),
                "n_nodes": len(node_stds),
                "n_samples": len(subset["sample_hour"].unique()),
            })

    spread_df = pd.DataFrame(spread_rows)

    # ── Combined Figure ───────────────────────────────────────────────
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))

    for i, field in enumerate(fields):
        label, unit = field_labels[field]

        # Top row: RMSE against actual (ground truth)
        ax = axes[0, i]
        subset = rmse_df[rmse_df["field"] == field].sort_values("lead_time_h")
        if not subset.empty:
            ax.plot(subset["lead_time_h"], subset["rmse"], "o-",
                    color="#2196F3", markersize=5, linewidth=1.5, label="RMSE")
            ax.plot(subset["lead_time_h"], subset["mae"], "s--",
                    color="#FF9800", markersize=4, linewidth=1.2, alpha=0.7, label="MAE")
            ax.fill_between(subset["lead_time_h"],
                            subset["bias"] - subset["rmse"],
                            subset["bias"] + subset["rmse"],
                            alpha=0.1, color="#2196F3")

        ax.set_title(f"{label} — Verified Error", fontsize=11, fontweight="bold")
        ax.set_xlabel("Lead Time (h)")
        ax.set_ylabel(f"Error ({unit})")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        if not subset.empty:
            ax.set_xlim(-0.5, subset["lead_time_h"].max() + 0.5)
        else:
            ax.set_xlim(-0.5, 11.5)

        # Bottom row: Inter-forecast spread (proxy)
        ax2 = axes[1, i]
        sub_spread = spread_df[spread_df["field"] == field].sort_values("mean_lead_time_h")
        if not sub_spread.empty:
            ax2.plot(sub_spread["mean_lead_time_h"], sub_spread["mean_spread_std"],
                     ".-", color="#9C27B0", markersize=2, linewidth=1.0)
            # Overlay the RMSE points for comparison in the overlap region
            if not subset.empty:
                ax2.plot(subset["lead_time_h"], subset["rmse"], "o",
                         color="#2196F3", markersize=5, alpha=0.6, label="RMSE (verified)")
                ax2.legend(fontsize=8)

        ax2.set_title(f"{label} — Forecast Spread (proxy)", fontsize=11, fontweight="bold")
        ax2.set_xlabel("Lead Time (h)")
        ax2.set_ylabel(f"Std across forecasts ({unit})")
        ax2.grid(True, alpha=0.3)

        # Mark the forecast horizons used in the thesis
        for horizon in [72, 120, 168]:
            if not sub_spread.empty and sub_spread["mean_lead_time_h"].max() >= horizon * 0.5:
                ax2.axvline(horizon, color="red", linestyle=":", alpha=0.3, linewidth=0.8)
                ax2.text(horizon, ax2.get_ylim()[1] * 0.95, f"{horizon}h",
                         fontsize=7, color="red", ha="center", va="top")

    max_lt = int(rmse_df["lead_time_h"].max()) if not rmse_df.empty else 0
    title_range = f"0-{max_lt}h" if max_lt > 11 else "0-11h"
    fig.suptitle(f"Forecast Error Analysis ({title_range}): Verified RMSE (top) and Forecast Spread Proxy (bottom)",
                 fontsize=13, fontweight="bold", y=1.01)
    fig.tight_layout()
    path_combined = os.path.join(FIG_DIR, f"thesis_forecast_error{output_suffix}.png")
    fig.savefig(path_combined, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path_combined}")

    # ── Print summary ─────────────────────────────────────────────────
    max_lt = int(rmse_df["lead_time_h"].max()) if not rmse_df.empty else 11
    print(f"\n=== Forecast Error vs Lead Time (Ground Truth, 0-{max_lt}h) ===\n")

    # Adaptive lead-time sampling for display
    if max_lt > 20:
        display_lts = [0, 6, 12, 24, 48, 72, 96, 120, 143]
    else:
        display_lts = None  # show all

    for field in fields:
        label, unit = field_labels[field]
        subset = rmse_df[rmse_df["field"] == field].sort_values("lead_time_h")
        if subset.empty:
            continue
        print(f"  {label} ({unit}):")
        if display_lts is not None:
            for target_lt in display_lts:
                close = subset.iloc[(subset["lead_time_h"] - target_lt).abs().argsort()[:1]]
                if not close.empty:
                    row = close.iloc[0]
                    print(f"    LT={int(row['lead_time_h']):3d}h: RMSE={row['rmse']:.3f}, "
                          f"MAE={row['mae']:.3f}, bias={row['bias']:+.3f} (n={int(row['n_points'])})")
        else:
            for _, row in subset.iterrows():
                print(f"    LT={int(row['lead_time_h']):3d}h: RMSE={row['rmse']:.3f}, "
                      f"MAE={row['mae']:.3f}, bias={row['bias']:+.3f} (n={int(row['n_points'])})")
        print()

    print("=== Forecast Spread at Key Horizons ===\n")
    for field in fields:
        label, unit = field_labels[field]
        sub = spread_df[spread_df["field"] == field]
        if sub.empty:
            continue
        print(f"  {label} ({unit}):")
        for target_lt in [0, 6, 12, 24, 48, 72, 120, 143]:
            close = sub.iloc[(sub["mean_lead_time_h"] - target_lt).abs().argsort()[:1]]
            if not close.empty:
                row = close.iloc[0]
                print(f"    ~{target_lt:3d}h lead: spread_std={row['mean_spread_std']:.3f} "
                      f"(actual LT={row['mean_lead_time_h']:.0f}h, {int(row['n_samples'])} forecasts)")
        print()

    # Save data as CSV for downstream analysis
    if output_suffix:
        rmse_csv = os.path.join(FIG_DIR, f"forecast_error_rmse{output_suffix}.csv")
        rmse_df.to_csv(rmse_csv, index=False)
        spread_csv = os.path.join(FIG_DIR, f"forecast_spread{output_suffix}.csv")
        spread_df.to_csv(spread_csv, index=False)
        print(f"Saved: {rmse_csv}")
        print(f"Saved: {spread_csv}")

    return {
        "rmse_df": rmse_df,
        "spread_df": spread_df,
        "figure": path_combined,
    }


# =====================================================================
# TASK 6: SWS Violation Magnitude Distribution
# =====================================================================

def analysis_sws_violations():
    """Analyze SWS violation magnitudes across approaches.

    Loads time-series CSVs for the 3 main approaches, computes
    required_sws - engine_limit for each violation, and produces
    distribution histograms + summary statistics.

    Returns dict with DataFrames and figure paths.
    """
    approaches = ["static_det", "dynamic_det", "dynamic_rh"]
    min_speed = 11.0
    max_speed = 13.0

    all_data = {}
    for approach in approaches:
        path = os.path.join(OUTPUT_DIR, f"timeseries_{approach}.csv")
        if os.path.isfile(path):
            all_data[approach] = pd.read_csv(path)

    if not all_data:
        print("No timeseries files found!")
        return None

    # ── Compute violation magnitudes ──────────────────────────────────
    violation_records = []
    for approach, df in all_data.items():
        df = df.copy()
        # planned_sws_knots = required SWS (before clamping)
        # actual_sws_knots = clamped SWS
        df["sws_excess"] = df["planned_sws_knots"] - max_speed  # positive = overspeed
        df["sws_deficit"] = min_speed - df["planned_sws_knots"]  # positive = underspeed
        df["is_overspeed"] = df["planned_sws_knots"] > max_speed + 0.01
        df["is_underspeed"] = df["planned_sws_knots"] < min_speed - 0.01
        df["is_violation"] = df["is_overspeed"] | df["is_underspeed"]
        df["violation_magnitude"] = np.where(
            df["is_overspeed"], df["sws_excess"],
            np.where(df["is_underspeed"], df["sws_deficit"], 0.0)
        )
        df["approach"] = approach
        all_data[approach] = df
        violation_records.append(df)

    combined = pd.concat(violation_records, ignore_index=True)

    # ── Figure 1: Histogram of required SWS by approach ───────────────
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)

    for i, approach in enumerate(approaches):
        ax = axes[i]
        df = all_data[approach]
        style = APPROACH_STYLE[approach]

        required_sws = df["planned_sws_knots"]
        n_total = len(df)
        n_violations = df["is_violation"].sum()
        n_over = df["is_overspeed"].sum()
        n_under = df["is_underspeed"].sum()

        # Histogram of all required SWS values
        bins = np.linspace(
            min(10.0, required_sws.min() - 0.1),
            max(15.0, required_sws.max() + 0.1),
            60
        )
        ax.hist(required_sws, bins=bins, color=style["color"], alpha=0.7,
                edgecolor="white", linewidth=0.5)

        # Mark engine limits
        ax.axvline(min_speed, color="red", linestyle="--", linewidth=1.5, label=f"Min ({min_speed} kn)")
        ax.axvline(max_speed, color="red", linestyle="--", linewidth=1.5, label=f"Max ({max_speed} kn)")

        # Shade violation zones
        ax.axvspan(bins[0], min_speed, alpha=0.08, color="red")
        ax.axvspan(max_speed, bins[-1], alpha=0.08, color="red")

        ax.set_title(f"{style['label']}\n{n_violations}/{n_total} violations "
                     f"({n_over} over, {n_under} under)", fontsize=10, fontweight="bold")
        ax.set_xlabel("Required SWS (knots)")
        if i == 0:
            ax.set_ylabel("Number of legs")
        ax.legend(fontsize=7, loc="upper right")
        ax.grid(True, alpha=0.2, axis="y")

    fig.suptitle("Required SWS Distribution — Engine Limit Violations",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    path1 = os.path.join(FIG_DIR, "thesis_sws_distribution.png")
    fig.savefig(path1, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path1}")

    # ── Figure 2: Violation magnitude CDF + geography ─────────────────
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Left: CDF of violation magnitudes
    for approach in approaches:
        df = all_data[approach]
        violations = df[df["is_violation"]]
        if violations.empty:
            continue
        style = APPROACH_STYLE[approach]
        magnitudes = violations["violation_magnitude"].sort_values()
        cdf = np.arange(1, len(magnitudes) + 1) / len(magnitudes)
        ax1.plot(magnitudes, cdf, style["marker"] + "-",
                 color=style["color"], markersize=3, linewidth=1.2,
                 label=f"{style['label']} (n={len(magnitudes)})")

    ax1.set_xlabel("Violation Magnitude (knots beyond limit)")
    ax1.set_ylabel("Cumulative Fraction")
    ax1.set_title("SWS Violation Severity (CDF)", fontsize=11, fontweight="bold")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.axvline(0.5, color="gray", linestyle=":", alpha=0.5)
    ax1.text(0.52, 0.5, "0.5 kn", fontsize=8, color="gray", transform=ax1.get_xaxis_transform())
    ax1.axvline(1.0, color="gray", linestyle=":", alpha=0.5)
    ax1.text(1.02, 0.5, "1.0 kn", fontsize=8, color="gray", transform=ax1.get_xaxis_transform())

    # Right: Violations along the route (by cumulative distance)
    for approach in approaches:
        df = all_data[approach]
        violations = df[df["is_violation"]]
        if violations.empty:
            continue
        style = APPROACH_STYLE[approach]
        colors = np.where(violations["is_overspeed"], "red", "blue")
        ax2.scatter(violations["cum_distance_nm"], violations["violation_magnitude"],
                    c=style["color"], marker=style["marker"], s=20, alpha=0.6,
                    label=style["label"])

    ax2.set_xlabel("Cumulative Distance (nm)")
    ax2.set_ylabel("Violation Magnitude (knots)")
    ax2.set_title("Violation Location Along Route", fontsize=11, fontweight="bold")
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)

    fig.suptitle("SWS Violation Analysis — Magnitude and Geography",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    path2 = os.path.join(FIG_DIR, "thesis_sws_violations.png")
    fig.savefig(path2, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path2}")

    # ── Figure 3: Per-segment violation rates ─────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))

    bar_width = 0.25
    segments = sorted(combined["segment"].unique())
    x = np.arange(len(segments))

    for j, approach in enumerate(approaches):
        df = all_data[approach]
        style = APPROACH_STYLE[approach]
        rates = []
        for seg in segments:
            seg_df = df[df["segment"] == seg]
            if len(seg_df) == 0:
                rates.append(0)
            else:
                rates.append(seg_df["is_violation"].sum() / len(seg_df) * 100)
        ax.bar(x + j * bar_width, rates, bar_width,
               color=style["color"], alpha=0.8, label=style["label"])

    ax.set_xticks(x + bar_width)
    ax.set_xticklabels([f"Seg {s}" for s in segments], fontsize=8)
    ax.set_xlabel("Segment")
    ax.set_ylabel("Violation Rate (%)")
    ax.set_title("SWS Violation Rate by Segment", fontsize=11, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3, axis="y")

    fig.tight_layout()
    path3 = os.path.join(FIG_DIR, "thesis_sws_by_segment.png")
    fig.savefig(path3, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path3}")

    # ── Print summary statistics ──────────────────────────────────────
    print("\n=== SWS Violation Summary ===\n")
    for approach in approaches:
        df = all_data[approach]
        style = APPROACH_STYLE[approach]
        v = df[df["is_violation"]]
        over = df[df["is_overspeed"]]
        under = df[df["is_underspeed"]]

        print(f"  {style['label']}:")
        print(f"    Total legs: {len(df)}")
        print(f"    Violations: {len(v)} ({len(v)/len(df)*100:.1f}%)")
        print(f"      Overspeed (>13 kn): {len(over)}")
        print(f"      Underspeed (<11 kn): {len(under)}")
        if not v.empty:
            mag = v["violation_magnitude"]
            print(f"    Magnitude: mean={mag.mean():.3f}, median={mag.median():.3f}, "
                  f"max={mag.max():.3f} kn")
            print(f"    Required SWS range: {df['planned_sws_knots'].min():.2f} – "
                  f"{df['planned_sws_knots'].max():.2f} kn")
            # Fraction that are "soft" (<0.5 kn) vs "hard" (>0.5 kn)
            soft = (mag < 0.5).sum()
            hard = (mag >= 0.5).sum()
            very_hard = (mag >= 1.0).sum()
            print(f"    Soft (<0.5 kn): {soft} ({soft/len(v)*100:.0f}%)")
            print(f"    Hard (>=0.5 kn): {hard} ({hard/len(v)*100:.0f}%)")
            print(f"    Very hard (>=1.0 kn): {very_hard} ({very_hard/len(v)*100:.0f}%)")
        else:
            print(f"    No violations!")

        # Weather at violation sites
        if not v.empty:
            print(f"    Weather at violations: BN={v['beaufort'].mean():.1f}, "
                  f"wave={v['wave_height_m'].mean():.2f}m")
        print()

    return {
        "all_data": all_data,
        "combined": combined,
        "figures": [path1, path2, path3],
    }


# =====================================================================
# Main
# =====================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Thesis analysis: forecast error + SWS violations")
    parser.add_argument("--hdf5", type=str, default=None,
                        help="Path to HDF5 file (default: voyage_weather.h5)")
    parser.add_argument("--suffix", type=str, default="",
                        help="Output filename suffix (e.g. '_full' for exp_b)")
    parser.add_argument("--task", type=str, choices=["all", "forecast_error", "sws_violations"],
                        default="all", help="Which analysis to run")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    print("=" * 70)
    print("THESIS ANALYSIS — Experiments 4.4 and 4.6")
    print("=" * 70)

    result_4 = None
    result_6 = None

    if args.task in ("all", "forecast_error"):
        print("\n\n>>> TASK 4: Forecast Error vs Lead Time\n")
        result_4 = analysis_forecast_error(hdf5_path=args.hdf5, output_suffix=args.suffix)

    if args.task in ("all", "sws_violations"):
        print("\n\n>>> TASK 6: SWS Violation Magnitude Distribution\n")
        result_6 = analysis_sws_violations()

    print("\n" + "=" * 70)
    print("DONE. Figures saved to:")
    if result_4:
        print(f"  {result_4['figure']}")
    if result_6:
        for p in result_6["figures"]:
            print(f"  {p}")
    print("=" * 70)
