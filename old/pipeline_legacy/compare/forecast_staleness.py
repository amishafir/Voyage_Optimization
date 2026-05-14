"""
Forecast staleness analysis: how often do NWP model forecasts actually change?

Investigates whether hourly weather collection provides new information,
given that the underlying NWP models update on different cycles
(verified from Open-Meteo API docs):
    - Wind (GFS/ECMWF IFS/ICON Global): 6h (4x/day at 00/06/12/18z)
    - Waves (ECMWF WAM: 6h, MFWAM: 12h — our route uses MFWAM)
    - Ocean currents (MeteoFrance SMOC): 24h (1x/day)

Three analyses:
    1. Update intervals: run-length of consecutive identical predictions
    2. Gap deltas: |forecast(t+gap) - forecast(t)| for various gap sizes
    3. SOG sensitivity: translate forecast deltas into SOG impact

Produces thesis-ready figures in pipeline/output/comparison/figures/
"""

import logging
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
FIG_DIR = os.path.join(OUTPUT_DIR, "comparison", "figures")

os.makedirs(FIG_DIR, exist_ok=True)

# Weather fields and their display metadata
FIELDS = ["wind_speed_10m_kmh", "wind_direction_10m_deg", "wave_height_m",
           "ocean_current_velocity_kmh", "ocean_current_direction_deg"]

FIELD_LABELS = {
    "wind_speed_10m_kmh":          ("Wind Speed",          "km/h",  "#2196F3"),
    "wind_direction_10m_deg":      ("Wind Direction",      "deg",   "#03A9F4"),
    "wave_height_m":               ("Wave Height",         "m",     "#FF9800"),
    "ocean_current_velocity_kmh":  ("Current Velocity",    "km/h",  "#4CAF50"),
    "ocean_current_direction_deg": ("Current Direction",   "deg",   "#8BC34A"),
}

# Model update cycles (hours) — verified from Open-Meteo API documentation:
#   Wind:     GFS/ECMWF IFS/ICON Global all run 4x/day at 00/06/12/18z → 6h
#   Waves:    ECMWF WAM runs 4x/day (6h), but MFWAM only 2x/day (12h).
#             Our empirical data shows 12h, confirming MFWAM is the source
#             for the Persian Gulf–Indian Ocean route.
#   Currents: MeteoFrance SMOC is computed once daily → 24h
MODEL_CYCLES = {
    "wind_speed_10m_kmh":          6,
    "wind_direction_10m_deg":      6,
    "wave_height_m":               12,
    "ocean_current_velocity_kmh":  24,
    "ocean_current_direction_deg": 24,
}


# =====================================================================
# 1. Update Intervals (run-length analysis)
# =====================================================================

def compute_update_intervals(hdf5_path):
    """For each weather field, measure consecutive sample hours where the
    predicted value for a fixed (node, forecast_hour) doesn't change.

    Reports mean/median/mode update interval per field.

    Returns:
        DataFrame with columns: field, mean_interval, median_interval,
        mode_interval, total_runs, pct_unchanged_hourly.
    """
    sys.path.insert(0, BASE_DIR)
    from shared.hdf5_io import read_predicted

    predicted = read_predicted(hdf5_path)
    if predicted.empty:
        print("  No predicted weather data found.")
        return pd.DataFrame()

    sample_hours = sorted(predicted["sample_hour"].unique())
    forecast_hours = sorted(predicted["forecast_hour"].unique())
    node_ids = sorted(predicted["node_id"].unique())

    print(f"  Data: {len(node_ids)} nodes, {len(sample_hours)} sample hours, "
          f"{len(forecast_hours)} forecast hours")

    # Vectorized approach: sort, diff, then run-length encode using cumsum trick
    predicted = predicted.sort_values(["node_id", "forecast_hour", "sample_hour"]).reset_index(drop=True)

    # Pre-compute group ID for each row (unique per node_id + forecast_hour)
    group_id = predicted.groupby(["node_id", "forecast_hour"]).ngroup()

    rows = []
    for field in FIELDS:
        # Diff within each group
        vals = predicted[field].values
        diffs = pd.Series(vals).groupby(group_id).diff()

        # Identify group starts (where diff is NaN due to being first in group)
        is_group_start = diffs.isna() & predicted[field].notna() | (group_id != group_id.shift(1))

        # Non-start pairs
        pair_mask = ~is_group_start
        pair_diffs = diffs[pair_mask]
        total_pairs = len(pair_diffs)
        if total_pairs == 0:
            continue

        # Unchanged: diff==0 (within tolerance) or both NaN
        unchanged_mask = pair_diffs.abs() < 1e-6
        both_nan_mask = pair_diffs.isna()
        unchanged_pairs = int((unchanged_mask | both_nan_mask).sum())

        # Run-length encoding via cumsum:
        # A new run starts at: group boundaries OR value changes
        is_change = (~unchanged_mask & ~both_nan_mask)
        # Also mark group starts as new runs
        new_run = is_group_start.copy()
        new_run.loc[is_change[is_change].index] = True
        run_id = new_run.cumsum()

        # Count elements per run
        run_counts = run_id.value_counts().values

        if len(run_counts) > 0:
            arr = run_counts
            vals_unique, counts = np.unique(arr, return_counts=True)
            mode_val = int(vals_unique[np.argmax(counts)])

            pct_unchanged = unchanged_pairs / total_pairs * 100 if total_pairs > 0 else 0

            rows.append({
                "field": field,
                "mean_interval": round(float(arr.mean()), 2),
                "median_interval": round(float(np.median(arr)), 2),
                "mode_interval": mode_val,
                "max_interval": int(arr.max()),
                "total_runs": len(run_counts),
                "pct_unchanged_hourly": round(pct_unchanged, 1),
                "expected_cycle_h": MODEL_CYCLES[field],
            })

    return pd.DataFrame(rows)


# =====================================================================
# 2. Gap Deltas
# =====================================================================

def compute_gap_deltas(hdf5_path, gaps=None):
    """For each field and gap size, compute |forecast(t+gap) - forecast(t)|
    for the same (node, forecast_hour).

    Shows diminishing returns: big jumps at 6h for wind, 12h for waves,
    flat for currents.

    Args:
        gaps: List of gap sizes in hours. Default: [1, 2, 3, 6, 12, 24].

    Returns:
        DataFrame with columns: field, gap_hours, mean_abs_delta,
        median_abs_delta, pct_nonzero.
    """
    if gaps is None:
        gaps = [1, 2, 3, 6, 12, 24]

    sys.path.insert(0, BASE_DIR)
    from shared.hdf5_io import read_predicted

    predicted = read_predicted(hdf5_path)
    if predicted.empty:
        print("  No predicted weather data found.")
        return pd.DataFrame()

    rows = []
    for field in FIELDS:
        for gap in gaps:
            # Self-join: match rows with same (node_id, forecast_hour) but sample_hour differs by gap
            left = predicted[["node_id", "forecast_hour", "sample_hour", field]].copy()
            right = left.copy()
            right["sample_hour"] = right["sample_hour"] - gap
            right = right.rename(columns={field: f"{field}_future"})

            merged = left.merge(
                right,
                on=["node_id", "forecast_hour", "sample_hour"],
                how="inner",
            )
            merged = merged.dropna(subset=[field, f"{field}_future"])

            if merged.empty:
                continue

            deltas = (merged[f"{field}_future"] - merged[field]).abs()
            nonzero = (deltas > 1e-6).sum()

            rows.append({
                "field": field,
                "gap_hours": gap,
                "mean_abs_delta": round(float(deltas.mean()), 6),
                "median_abs_delta": round(float(deltas.median()), 6),
                "std_abs_delta": round(float(deltas.std()), 6),
                "pct_nonzero": round(float(nonzero / len(deltas) * 100), 1),
                "n_pairs": len(deltas),
            })

    return pd.DataFrame(rows)


# =====================================================================
# 3. SOG Sensitivity
# =====================================================================

def compute_sog_sensitivity(hdf5_path, config):
    """Translate forecast deltas into SOG impact.

    For a representative set of (node, forecast_hour) pairs, perturb
    each weather field by its typical hourly delta and measure the
    resulting SOG change.

    Args:
        config: Experiment config dict (for ship parameters).

    Returns:
        DataFrame with columns: field, gap_hours, mean_sog_delta_knots,
        max_sog_delta_knots.
    """
    sys.path.insert(0, BASE_DIR)
    from shared.hdf5_io import read_predicted
    from shared.physics import calculate_speed_over_ground, load_ship_parameters

    predicted = read_predicted(hdf5_path)
    if predicted.empty:
        print("  No predicted weather data found.")
        return pd.DataFrame()

    ship_params = load_ship_parameters(config)

    # Use baseline weather from sample_hour=0 for a representative subset of nodes
    baseline = predicted[predicted["sample_hour"] == 0].copy()
    # Sample up to 200 rows for speed
    if len(baseline) > 200:
        baseline = baseline.sample(200, random_state=42)

    def _sog_from_row(row):
        """Compute SOG from a predicted weather row."""
        wind_dir_rad = math.radians(row.get("wind_direction_10m_deg", 0.0))
        beaufort = int(row.get("beaufort_number", 3))
        wave_height = row.get("wave_height_m", 1.0)
        current_knots = row.get("ocean_current_velocity_kmh", 0.0) / 1.852
        current_dir_rad = math.radians(row.get("ocean_current_direction_deg", 0.0))
        return calculate_speed_over_ground(
            ship_speed=12.0,  # mid-range SWS
            ocean_current=current_knots,
            current_direction=current_dir_rad,
            ship_heading=0.0,
            wind_direction=wind_dir_rad,
            beaufort_scale=beaufort,
            wave_height=wave_height,
            ship_parameters=ship_params,
        )

    # First compute gap_deltas to get typical perturbation sizes
    gap_deltas = compute_gap_deltas(hdf5_path, gaps=[1, 3, 6, 12, 24])

    perturb_fields = {
        "wind_speed_10m_kmh": "wind_speed_10m_kmh",
        "wave_height_m": "wave_height_m",
        "ocean_current_velocity_kmh": "ocean_current_velocity_kmh",
    }

    rows = []
    for field in perturb_fields:
        field_deltas = gap_deltas[gap_deltas["field"] == field]
        if field_deltas.empty:
            continue

        for _, delta_row in field_deltas.iterrows():
            gap = delta_row["gap_hours"]
            perturbation = delta_row["mean_abs_delta"]

            sog_changes = []
            for _, wx_row in baseline.iterrows():
                base_sog = _sog_from_row(wx_row)

                # Perturb the field
                perturbed = wx_row.copy()
                perturbed[field] = wx_row[field] + perturbation
                # Recalculate beaufort if wind speed changed
                if field == "wind_speed_10m_kmh":
                    from shared.beaufort import wind_speed_to_beaufort
                    perturbed["beaufort_number"] = wind_speed_to_beaufort(
                        perturbed["wind_speed_10m_kmh"]
                    )
                perturbed_sog = _sog_from_row(perturbed)
                sog_changes.append(abs(perturbed_sog - base_sog))

            arr = np.array(sog_changes)
            rows.append({
                "field": field,
                "gap_hours": int(gap),
                "perturbation_size": round(perturbation, 4),
                "mean_sog_delta_knots": round(float(arr.mean()), 6),
                "max_sog_delta_knots": round(float(arr.max()), 6),
                "pct_above_01kn": round(float((arr > 0.1).sum() / len(arr) * 100), 1),
            })

    return pd.DataFrame(rows)


# =====================================================================
# Figure generation
# =====================================================================

def generate_figures(intervals_df, deltas_df, sog_df, output_suffix=""):
    """Generate a 2-panel thesis figure.

    Panel 1 (left): Update intervals per field (bar chart with model cycle overlay)
    Panel 2 (right): |delta| vs gap size (line plot per field)

    Returns:
        Path to saved figure.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

    # ── Panel 1: Update intervals ────────────────────────────────────
    if not intervals_df.empty:
        fields_plot = intervals_df["field"].tolist()
        labels = [FIELD_LABELS[f][0] for f in fields_plot]
        medians = intervals_df["median_interval"].values
        means = intervals_df["mean_interval"].values
        expected = intervals_df["expected_cycle_h"].values

        x = np.arange(len(fields_plot))
        width = 0.3

        bars1 = ax1.bar(x - width / 2, medians, width, label="Median run length",
                        color="#2196F3", alpha=0.8)
        bars2 = ax1.bar(x + width / 2, means, width, label="Mean run length",
                        color="#FF9800", alpha=0.8)

        # Overlay expected model cycle
        ax1.scatter(x, expected, marker="D", color="red", s=80, zorder=5,
                    label="Expected NWP cycle")

        ax1.set_xticks(x)
        ax1.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
        ax1.set_ylabel("Hours")
        ax1.set_title("Forecast Update Intervals\n(consecutive unchanged predictions)",
                       fontsize=11, fontweight="bold")
        ax1.legend(fontsize=8)
        ax1.grid(True, alpha=0.3, axis="y")

        # Annotate % unchanged
        for i, row in intervals_df.iterrows():
            ax1.text(i, max(row["median_interval"], row["mean_interval"]) + 0.3,
                     f"{row['pct_unchanged_hourly']:.0f}%\nunchanged",
                     ha="center", va="bottom", fontsize=7, color="gray")

    # ── Panel 2: |delta| vs gap size ─────────────────────────────────
    if not deltas_df.empty:
        # Normalize deltas to percentage of field mean for comparability
        magnitude_fields = ["wind_speed_10m_kmh", "wave_height_m", "ocean_current_velocity_kmh"]
        for field in magnitude_fields:
            sub = deltas_df[deltas_df["field"] == field].sort_values("gap_hours")
            if sub.empty:
                continue
            label, unit, color = FIELD_LABELS[field]
            ax2.plot(sub["gap_hours"], sub["mean_abs_delta"],
                     "o-", color=color, markersize=6, linewidth=1.5,
                     label=f"{label} ({unit})")

            # Mark the expected model cycle
            cycle = MODEL_CYCLES[field]
            cycle_row = sub[sub["gap_hours"] == cycle]
            if not cycle_row.empty:
                ax2.axvline(cycle, color=color, linestyle=":", alpha=0.4, linewidth=0.8)

        ax2.set_xlabel("Gap Size (hours)")
        ax2.set_ylabel("Mean |delta| (original units)")
        ax2.set_title("Forecast Change vs Collection Gap\n(diminishing returns above model cycle)",
                       fontsize=11, fontweight="bold")
        ax2.legend(fontsize=8)
        ax2.grid(True, alpha=0.3)
        ax2.set_xticks([1, 2, 3, 6, 12, 24])

    fig.suptitle("Forecast Staleness Analysis — Is Hourly Collection Valuable?",
                 fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout()
    path = os.path.join(FIG_DIR, f"thesis_forecast_staleness{output_suffix}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {path}")

    # ── SOG sensitivity figure (if available) ────────────────────────
    sog_path = None
    if sog_df is not None and not sog_df.empty:
        fig2, ax = plt.subplots(figsize=(8, 5))
        for field in sog_df["field"].unique():
            sub = sog_df[sog_df["field"] == field].sort_values("gap_hours")
            label, unit, color = FIELD_LABELS[field]
            ax.plot(sub["gap_hours"], sub["mean_sog_delta_knots"],
                    "o-", color=color, markersize=6, linewidth=1.5,
                    label=f"{label}")

        ax.axhline(0.1, color="red", linestyle="--", alpha=0.5, linewidth=1,
                   label="0.1 kn threshold")
        ax.set_xlabel("Gap Size (hours)")
        ax.set_ylabel("Mean SOG Impact (knots)")
        ax.set_title("SOG Sensitivity to Forecast Staleness\n(weather deltas translated to speed impact)",
                     fontsize=11, fontweight="bold")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.set_xticks([1, 3, 6, 12, 24])

        fig2.tight_layout()
        sog_path = os.path.join(FIG_DIR, f"thesis_sog_sensitivity{output_suffix}.png")
        fig2.savefig(sog_path, dpi=150, bbox_inches="tight")
        plt.close(fig2)
        print(f"Saved: {sog_path}")

    return path, sog_path


# =====================================================================
# Print summaries
# =====================================================================

def print_summary(intervals_df, deltas_df, sog_df):
    """Print thesis-ready summary tables to stdout."""

    print("\n" + "=" * 70)
    print("FORECAST STALENESS ANALYSIS")
    print("=" * 70)

    # 1. Update intervals
    print("\n--- 1. Update Intervals (run-length of unchanged predictions) ---\n")
    if not intervals_df.empty:
        print(f"  {'Field':<30} {'Median':>7} {'Mean':>7} {'Mode':>6} "
              f"{'Max':>5} {'%Unchanged':>11} {'NWP Cycle':>10}")
        print("  " + "-" * 78)
        for _, row in intervals_df.iterrows():
            label = FIELD_LABELS[row["field"]][0]
            print(f"  {label:<30} {row['median_interval']:>7.1f} {row['mean_interval']:>7.1f} "
                  f"{row['mode_interval']:>6d} {row['max_interval']:>5d} "
                  f"{row['pct_unchanged_hourly']:>10.1f}% {row['expected_cycle_h']:>9d}h")
    else:
        print("  No data.")

    # 2. Gap deltas
    print("\n--- 2. Forecast Deltas by Gap Size ---\n")
    if not deltas_df.empty:
        magnitude_fields = ["wind_speed_10m_kmh", "wave_height_m", "ocean_current_velocity_kmh"]
        for field in magnitude_fields:
            label, unit, _ = FIELD_LABELS[field]
            sub = deltas_df[deltas_df["field"] == field].sort_values("gap_hours")
            if sub.empty:
                continue
            print(f"  {label} ({unit}):")
            print(f"    {'Gap':>5}  {'Mean |d|':>10}  {'Median |d|':>11}  {'% nonzero':>10}")
            print("    " + "-" * 40)
            for _, row in sub.iterrows():
                print(f"    {row['gap_hours']:>4}h  {row['mean_abs_delta']:>10.4f}  "
                      f"{row['median_abs_delta']:>11.4f}  {row['pct_nonzero']:>9.1f}%")
            print()

    # 3. SOG sensitivity
    print("--- 3. SOG Sensitivity ---\n")
    if sog_df is not None and not sog_df.empty:
        print(f"  {'Field':<25} {'Gap':>5} {'Perturb':>9} {'Mean SOG d':>11} "
              f"{'Max SOG d':>10} {'>0.1kn':>7}")
        print("  " + "-" * 70)
        for _, row in sog_df.iterrows():
            label = FIELD_LABELS[row["field"]][0]
            print(f"  {label:<25} {row['gap_hours']:>4}h {row['perturbation_size']:>9.4f} "
                  f"{row['mean_sog_delta_knots']:>11.6f} {row['max_sog_delta_knots']:>10.6f} "
                  f"{row['pct_above_01kn']:>6.1f}%")
    else:
        print("  No data (requires config for ship parameters).")

    # Thesis conclusion
    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    if not intervals_df.empty:
        wind_row = intervals_df[intervals_df["field"] == "wind_speed_10m_kmh"]
        wave_row = intervals_df[intervals_df["field"] == "wave_height_m"]
        curr_row = intervals_df[intervals_df["field"] == "ocean_current_velocity_kmh"]

        wind_pct = wind_row["pct_unchanged_hourly"].values[0] if not wind_row.empty else 0
        wave_pct = wave_row["pct_unchanged_hourly"].values[0] if not wave_row.empty else 0
        curr_pct = curr_row["pct_unchanged_hourly"].values[0] if not curr_row.empty else 0

        print(f"  Hourly collection redundancy:")
        print(f"    Wind:     {wind_pct:.0f}% of consecutive hours are identical (NWP cycle: 6h)")
        print(f"    Waves:    {wave_pct:.0f}% of consecutive hours are identical (NWP cycle: 12h)")
        print(f"    Currents: {curr_pct:.0f}% of consecutive hours are identical (NWP cycle: 24h)")
        print()
        print("  Recommendation: 6-hourly collection aligns with the fastest model")
        print("  update cycle (GFS wind). Hourly collection wastes ~80%+ of API calls")
        print("  on identical data. Replan frequency should match collection frequency.")
    print("=" * 70)


# =====================================================================
# Main
# =====================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Forecast staleness analysis")
    parser.add_argument("--hdf5", type=str, default=None,
                        help="Path to HDF5 file (default: experiment_b_138wp.h5)")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to experiment YAML (for SOG sensitivity)")
    parser.add_argument("--suffix", type=str, default="",
                        help="Output filename suffix")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    # Defaults
    if args.hdf5 is None:
        args.hdf5 = os.path.join(BASE_DIR, "data", "experiment_b_138wp.h5")
    if args.config is None:
        args.config = os.path.join(BASE_DIR, "config", "experiment_exp_b.yaml")

    print("=" * 70)
    print("FORECAST STALENESS ANALYSIS")
    print(f"  HDF5: {args.hdf5}")
    print("=" * 70)

    # 1. Update intervals
    print("\n[1/3] Computing update intervals...")
    intervals_df = compute_update_intervals(args.hdf5)

    # 2. Gap deltas
    print("\n[2/3] Computing gap deltas...")
    deltas_df = compute_gap_deltas(args.hdf5)

    # 3. SOG sensitivity (requires config)
    sog_df = None
    if os.path.isfile(args.config):
        import yaml
        print("\n[3/3] Computing SOG sensitivity...")
        with open(args.config) as f:
            config = yaml.safe_load(f)
        sog_df = compute_sog_sensitivity(args.hdf5, config)
    else:
        print("\n[3/3] Skipping SOG sensitivity (no config file)")

    # Print summaries
    print_summary(intervals_df, deltas_df, sog_df)

    # Save CSVs
    if not intervals_df.empty:
        csv_path = os.path.join(FIG_DIR, f"staleness_intervals{args.suffix}.csv")
        intervals_df.to_csv(csv_path, index=False)
        print(f"Saved: {csv_path}")
    if not deltas_df.empty:
        csv_path = os.path.join(FIG_DIR, f"staleness_deltas{args.suffix}.csv")
        deltas_df.to_csv(csv_path, index=False)
        print(f"Saved: {csv_path}")
    if sog_df is not None and not sog_df.empty:
        csv_path = os.path.join(FIG_DIR, f"staleness_sog_sensitivity{args.suffix}.csv")
        sog_df.to_csv(csv_path, index=False)
        print(f"Saved: {csv_path}")

    # Generate figures
    print("\nGenerating figures...")
    generate_figures(intervals_df, deltas_df, sog_df, output_suffix=args.suffix)

    print("\nDone.")
