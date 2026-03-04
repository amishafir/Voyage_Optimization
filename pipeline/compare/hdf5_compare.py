"""
Compare two HDF5 voyage weather files (e.g. live-collected vs historical).

Produces a JSON report with:
  - Per-field weather statistics (mean_diff, RMSE, r², max_abs_diff)
  - Per-segment breakdown
  - Optional optimization comparison (LP, DP, RH)
  - Substitutability assessment (VALID / VALID_WITH_CAVEATS / NOT_RECOMMENDED)

Usage:
    cd pipeline
    python3 compare/hdf5_compare.py \
        --original  data/experiment_b_138wp.h5 \
        --historical data/experiment_b_138wp_historical.h5 \
        --config config/experiment_exp_b.yaml \
        [--skip-optimization] [--output results/exp_b/hdf5_comparison.json]
"""

import argparse
import json
import logging
import math
import os
import sys
import time

# Ensure pipeline/ is on sys.path for shared.* imports
_pipeline_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _pipeline_dir not in sys.path:
    sys.path.insert(0, _pipeline_dir)

import numpy as np
import pandas as pd
import yaml

from shared.hdf5_io import read_metadata, read_actual, read_predicted, get_attrs

logger = logging.getLogger(__name__)

# ── Substitutability thresholds ──────────────────────────────────────────────

THRESHOLDS = {
    "wind_speed_10m_kmh":          {"rmse": 5.0,  "unit": "km/h", "rationale": "Half a Beaufort number"},
    "wave_height_m":               {"rmse": 0.3,  "unit": "m",    "rationale": "Within sea-state uncertainty"},
    "ocean_current_velocity_kmh":  {"rmse": 0.5,  "unit": "km/h", "rationale": "< 0.3 kn effect on SOG"},
    "wind_direction_10m_deg":      {"rmse": 30.0, "unit": "deg",  "rationale": "Within one heading sector"},
    "ocean_current_direction_deg": {"rmse": 30.0, "unit": "deg",  "rationale": "Within one heading sector"},
    "optimization_fuel_pct":       {"delta": 2.0, "unit": "%",    "rationale": "Within model uncertainty"},
}

SCALAR_FIELDS = [
    "wind_speed_10m_kmh",
    "beaufort_number",
    "wave_height_m",
    "ocean_current_velocity_kmh",
]

DIRECTION_FIELDS = [
    "wind_direction_10m_deg",
    "ocean_current_direction_deg",
]


# ── Circular angle helpers ───────────────────────────────────────────────────

def _circular_abs_diff_deg(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Element-wise absolute angular difference in [0, 180] degrees."""
    diff = np.abs(a - b) % 360
    return np.minimum(diff, 360 - diff)


# ── Weather comparison ───────────────────────────────────────────────────────

def _field_stats(vals_a: np.ndarray, vals_b: np.ndarray, is_direction: bool) -> dict:
    """Compute comparison statistics for a single field."""
    mask = np.isfinite(vals_a) & np.isfinite(vals_b)
    a, b = vals_a[mask], vals_b[mask]
    n = len(a)
    if n == 0:
        return {"n": 0, "mean_diff": None, "rmse": None, "r_squared": None, "max_abs_diff": None}

    if is_direction:
        abs_diff = _circular_abs_diff_deg(a, b)
        mean_diff = float(np.mean(abs_diff))
        rmse = float(np.sqrt(np.mean(abs_diff ** 2)))
        max_abs = float(np.max(abs_diff))
        # r² not meaningful for circular data
        r_sq = None
    else:
        diff = a - b
        abs_diff = np.abs(diff)
        mean_diff = float(np.mean(diff))
        rmse = float(np.sqrt(np.mean(diff ** 2)))
        max_abs = float(np.max(abs_diff))
        if np.std(a) > 0 and np.std(b) > 0:
            r_sq = float(np.corrcoef(a, b)[0, 1] ** 2)
        else:
            r_sq = None

    return {
        "n": int(n),
        "mean_diff": round(mean_diff, 4),
        "rmse": round(rmse, 4),
        "r_squared": round(r_sq, 4) if r_sq is not None else None,
        "max_abs_diff": round(max_abs, 4),
    }


def compare_actual_weather(path_a: str, path_b: str) -> dict:
    """Compare /actual_weather between two HDF5 files.

    Returns dict with 'overall' stats per field and 'per_segment' breakdown.
    """
    meta_a = read_metadata(path_a)
    actual_a = read_actual(path_a)
    actual_b = read_actual(path_b)

    # Align on (node_id, sample_hour)
    merged = actual_a.merge(
        actual_b, on=["node_id", "sample_hour"], suffixes=("_a", "_b"),
    )
    logger.info("Actual weather: %d matched rows (A=%d, B=%d)",
                len(merged), len(actual_a), len(actual_b))

    all_fields = SCALAR_FIELDS + DIRECTION_FIELDS
    overall = {}
    for field in all_fields:
        col_a, col_b = f"{field}_a", f"{field}_b"
        if col_a not in merged.columns:
            continue
        is_dir = field in DIRECTION_FIELDS
        overall[field] = _field_stats(
            merged[col_a].values.astype(float),
            merged[col_b].values.astype(float),
            is_direction=is_dir,
        )

    # Per-segment breakdown
    seg_map = meta_a[["node_id", "segment"]].drop_duplicates()
    merged_seg = merged.merge(seg_map, on="node_id")
    per_segment = {}
    for seg_idx in sorted(merged_seg["segment"].unique()):
        seg_data = merged_seg[merged_seg["segment"] == seg_idx]
        seg_stats = {}
        for field in all_fields:
            col_a, col_b = f"{field}_a", f"{field}_b"
            if col_a not in seg_data.columns:
                continue
            is_dir = field in DIRECTION_FIELDS
            seg_stats[field] = _field_stats(
                seg_data[col_a].values.astype(float),
                seg_data[col_b].values.astype(float),
                is_direction=is_dir,
            )
        per_segment[int(seg_idx)] = seg_stats

    return {
        "matched_rows": len(merged),
        "rows_a": len(actual_a),
        "rows_b": len(actual_b),
        "overall": overall,
        "per_segment": per_segment,
    }


def compare_predicted_weather(path_a: str, path_b: str) -> dict:
    """Compare /predicted_weather between two HDF5 files (overall stats only)."""
    pred_a = read_predicted(path_a)
    pred_b = read_predicted(path_b)

    if len(pred_a) == 0 or len(pred_b) == 0:
        return {"matched_rows": 0, "rows_a": len(pred_a), "rows_b": len(pred_b),
                "overall": {}, "note": "One or both files have no predicted weather"}

    merged = pred_a.merge(
        pred_b, on=["node_id", "forecast_hour", "sample_hour"], suffixes=("_a", "_b"),
    )
    logger.info("Predicted weather: %d matched rows (A=%d, B=%d)",
                len(merged), len(pred_a), len(pred_b))

    all_fields = SCALAR_FIELDS + DIRECTION_FIELDS
    overall = {}
    for field in all_fields:
        col_a, col_b = f"{field}_a", f"{field}_b"
        if col_a not in merged.columns:
            continue
        is_dir = field in DIRECTION_FIELDS
        overall[field] = _field_stats(
            merged[col_a].values.astype(float),
            merged[col_b].values.astype(float),
            is_direction=is_dir,
        )

    return {
        "matched_rows": len(merged),
        "rows_a": len(pred_a),
        "rows_b": len(pred_b),
        "overall": overall,
    }


# ── Optimization comparison ─────────────────────────────────────────────────

def _run_approach(approach: str, hdf5_path: str, config: dict) -> dict:
    """Run a single optimization approach and return result dict."""
    if approach == "static_det":
        from static_det.transform import transform
        from static_det.optimize import optimize
    elif approach == "dynamic_det":
        from dynamic_det.transform import transform
        from dynamic_det.optimize import optimize
    elif approach == "dynamic_rh":
        from dynamic_rh.transform import transform
        from dynamic_rh.optimize import optimize
    else:
        return {"error": f"Unknown approach: {approach}"}

    try:
        t0 = time.time()
        tx = transform(hdf5_path, config)
        opt = optimize(tx, config)
        elapsed = time.time() - t0
        return {
            "fuel_mt": opt.get("planned_fuel_mt"),
            "time_h": opt.get("planned_time_h"),
            "status": opt.get("status"),
            "computation_s": round(elapsed, 3),
        }
    except Exception as e:
        logger.warning("Approach %s failed: %s", approach, e)
        return {"error": str(e)}


def compare_optimization(path_a: str, path_b: str, config: dict) -> dict:
    """Run LP, DP, RH on both files and compare fuel/time."""
    approaches = []
    if config.get("static_det", {}).get("enabled"):
        approaches.append("static_det")
    if config.get("dynamic_det", {}).get("enabled"):
        approaches.append("dynamic_det")
    if config.get("dynamic_rh", {}).get("enabled"):
        approaches.append("dynamic_rh")

    results = {}
    for approach in approaches:
        logger.info("Running %s on original...", approach)
        res_a = _run_approach(approach, path_a, config)
        logger.info("Running %s on historical...", approach)
        res_b = _run_approach(approach, path_b, config)

        fuel_a = res_a.get("fuel_mt")
        fuel_b = res_b.get("fuel_mt")
        if fuel_a and fuel_b and fuel_a > 0:
            fuel_delta_pct = round((fuel_b - fuel_a) / fuel_a * 100, 2)
        else:
            fuel_delta_pct = None

        time_a = res_a.get("time_h")
        time_b = res_b.get("time_h")
        if time_a and time_b:
            time_delta_h = round(time_b - time_a, 2)
        else:
            time_delta_h = None

        results[approach] = {
            "original": res_a,
            "historical": res_b,
            "fuel_delta_pct": fuel_delta_pct,
            "time_delta_h": time_delta_h,
        }

    return results


# ── Substitutability assessment ──────────────────────────────────────────────

def assess_substitutability(weather_stats: dict, opt_results: dict = None) -> dict:
    """Evaluate whether the historical file can substitute for the original.

    Returns:
        verdict: VALID | VALID_WITH_CAVEATS | NOT_RECOMMENDED
        failures: list of threshold violations
        warnings: list of near-threshold items
    """
    failures = []
    warnings = []

    overall = weather_stats.get("overall", {})
    for field, thresh in THRESHOLDS.items():
        if field == "optimization_fuel_pct":
            continue  # handled below
        stats = overall.get(field, {})
        rmse = stats.get("rmse")
        if rmse is None:
            continue
        limit = thresh["rmse"]
        if rmse > limit:
            failures.append({
                "field": field,
                "rmse": rmse,
                "threshold": limit,
                "unit": thresh["unit"],
                "rationale": thresh["rationale"],
            })
        elif rmse > limit * 0.7:
            warnings.append({
                "field": field,
                "rmse": rmse,
                "threshold": limit,
                "unit": thresh["unit"],
                "note": "Approaching threshold (>70%)",
            })

    # Optimization fuel check
    if opt_results:
        fuel_thresh = THRESHOLDS["optimization_fuel_pct"]["delta"]
        for approach, res in opt_results.items():
            delta = res.get("fuel_delta_pct")
            if delta is not None and abs(delta) > fuel_thresh:
                failures.append({
                    "field": f"optimization_fuel_{approach}",
                    "delta_pct": delta,
                    "threshold": fuel_thresh,
                    "unit": "%",
                })
            elif delta is not None and abs(delta) > fuel_thresh * 0.7:
                warnings.append({
                    "field": f"optimization_fuel_{approach}",
                    "delta_pct": delta,
                    "threshold": fuel_thresh,
                    "unit": "%",
                    "note": "Approaching threshold (>70%)",
                })

    if failures:
        verdict = "NOT_RECOMMENDED"
    elif warnings:
        verdict = "VALID_WITH_CAVEATS"
    else:
        verdict = "VALID"

    return {
        "verdict": verdict,
        "failures": failures,
        "warnings": warnings,
    }


# ── Printed summary ─────────────────────────────────────────────────────────

def _print_summary(report: dict):
    """Print a human-readable summary of the comparison."""
    print("\n" + "=" * 70)
    print("HDF5 COMPARISON REPORT")
    print("=" * 70)

    # File info
    meta = report.get("files", {})
    print(f"\nOriginal:   {meta.get('original', '?')}")
    print(f"Historical: {meta.get('historical', '?')}")

    # Actual weather
    aw = report.get("actual_weather", {})
    print(f"\n── Actual Weather ({aw.get('matched_rows', 0)} matched rows) ──")
    overall = aw.get("overall", {})
    print(f"  {'Field':<35} {'RMSE':>8} {'Mean Diff':>10} {'r²':>8} {'Max':>8}")
    print(f"  {'-'*35} {'-'*8} {'-'*10} {'-'*8} {'-'*8}")
    for field in SCALAR_FIELDS + DIRECTION_FIELDS:
        s = overall.get(field, {})
        if not s or s.get("n", 0) == 0:
            continue
        r2_str = f"{s['r_squared']:.4f}" if s.get("r_squared") is not None else "  N/A"
        print(f"  {field:<35} {s['rmse']:8.4f} {s['mean_diff']:10.4f} {r2_str:>8} {s['max_abs_diff']:8.4f}")

    # Predicted weather
    pw = report.get("predicted_weather", {})
    if pw and pw.get("matched_rows", 0) > 0:
        print(f"\n── Predicted Weather ({pw.get('matched_rows', 0)} matched rows) ──")
        p_overall = pw.get("overall", {})
        for field in SCALAR_FIELDS + DIRECTION_FIELDS:
            s = p_overall.get(field, {})
            if not s or s.get("n", 0) == 0:
                continue
            r2_str = f"{s['r_squared']:.4f}" if s.get("r_squared") is not None else "  N/A"
            print(f"  {field:<35} {s['rmse']:8.4f} {s['mean_diff']:10.4f} {r2_str:>8} {s['max_abs_diff']:8.4f}")

    # Optimization
    opt = report.get("optimization", {})
    if opt:
        print("\n── Optimization Comparison ──")
        print(f"  {'Approach':<18} {'Fuel A (mt)':>12} {'Fuel B (mt)':>12} {'Delta %':>10} {'Time Δh':>10}")
        print(f"  {'-'*18} {'-'*12} {'-'*12} {'-'*10} {'-'*10}")
        for approach, res in opt.items():
            fuel_a = res.get("original", {}).get("fuel_mt")
            fuel_b = res.get("historical", {}).get("fuel_mt")
            delta = res.get("fuel_delta_pct")
            time_d = res.get("time_delta_h")
            fa_str = f"{fuel_a:.2f}" if fuel_a else "ERROR"
            fb_str = f"{fuel_b:.2f}" if fuel_b else "ERROR"
            d_str = f"{delta:+.2f}%" if delta is not None else "N/A"
            t_str = f"{time_d:+.2f}" if time_d is not None else "N/A"
            print(f"  {approach:<18} {fa_str:>12} {fb_str:>12} {d_str:>10} {t_str:>10}")

    # Assessment
    assessment = report.get("assessment", {})
    verdict = assessment.get("verdict", "UNKNOWN")
    print(f"\n── Assessment: {verdict} ──")
    for f in assessment.get("failures", []):
        if "rmse" in f:
            print(f"  FAIL: {f['field']} RMSE={f['rmse']:.4f} > {f['threshold']} {f['unit']} ({f['rationale']})")
        else:
            print(f"  FAIL: {f['field']} delta={f['delta_pct']:.2f}% > {f['threshold']}%")
    for w in assessment.get("warnings", []):
        if "rmse" in w:
            print(f"  WARN: {w['field']} RMSE={w['rmse']:.4f} (threshold={w['threshold']} {w['unit']})")
        else:
            print(f"  WARN: {w['field']} delta={w['delta_pct']:.2f}% (threshold={w['threshold']}%)")
    if not assessment.get("failures") and not assessment.get("warnings"):
        print("  All fields within thresholds.")

    print("=" * 70 + "\n")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Compare two HDF5 voyage weather files.")
    parser.add_argument("--original", required=True, help="Path to original (live-collected) HDF5")
    parser.add_argument("--historical", required=True, help="Path to historical (bulk-download) HDF5")
    parser.add_argument("--config", required=True, help="Path to experiment YAML config")
    parser.add_argument("--skip-optimization", action="store_true", help="Skip running optimizers")
    parser.add_argument("--output", default=None, help="Output JSON path (default: results/exp_b/hdf5_comparison.json)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    with open(args.config) as f:
        config = yaml.safe_load(f)

    output_path = args.output or "results/exp_b/hdf5_comparison.json"

    report = {
        "files": {
            "original": args.original,
            "historical": args.historical,
            "config": args.config,
        },
    }

    # 1. Compare actual weather
    logger.info("Comparing actual weather...")
    report["actual_weather"] = compare_actual_weather(args.original, args.historical)

    # 2. Compare predicted weather
    logger.info("Comparing predicted weather...")
    report["predicted_weather"] = compare_predicted_weather(args.original, args.historical)

    # 3. Optimization comparison
    opt_results = None
    if not args.skip_optimization:
        logger.info("Running optimization comparison...")
        opt_results = compare_optimization(args.original, args.historical, config)
        report["optimization"] = opt_results
    else:
        logger.info("Skipping optimization (--skip-optimization)")

    # 4. Assessment
    report["assessment"] = assess_substitutability(
        report["actual_weather"], opt_results
    )

    # 5. Write JSON
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info("Report written to %s", output_path)

    # 6. Print summary
    _print_summary(report)


if __name__ == "__main__":
    main()
