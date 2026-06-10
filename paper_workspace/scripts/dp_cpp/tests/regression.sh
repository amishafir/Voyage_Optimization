#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Golden-master regression harness for dp_cpp.
#
# Locks the NON-RH behaviour (actual weather, no rolling horizon) of dp_SR /
# dp_luo so the C++ RH port (RH_PORT_PLAN.md) cannot silently change existing
# results.
#
#   ./regression.sh capture   # run ONCE on pristine C++; writes golden/ — COMMIT IT
#   ./regression.sh verify    # run after each port phase; diffs vs golden/  (exit!=0 on drift)
#
# The per-arc CSV (--csv) is the strong check: every arc's fuel / SWS / SOG /
# heading / six weather fields is hashed, so ANY drift in path, weather lookup,
# or physics is caught — far stronger than checking the fuel total alone.
#
# The RH port keeps new params inert by default (empty time_key,
# override_sample_hour=-1, d_start=0). When inert, emit_from_src / eval_arc run
# the original statements in the original order → bit-identical output → exact
# CSV hash match. That is what this harness enforces.
#
# IMPORTANT: capture MUST run on pristine C++ (before Phase 0) and golden/ must
# never be regenerated after edits — it is the frozen ground truth.
# ---------------------------------------------------------------------------
set -euo pipefail

MODE="${1:-}"
if [[ "$MODE" != "capture" && "$MODE" != "verify" ]]; then
  echo "usage: $0 {capture|verify}" >&2
  exit 2
fi

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DP_CPP=$(cd "$SCRIPT_DIR/.." && pwd)
PIPELINE=$(cd "$DP_CPP/.." && pwd)
BIN="$DP_CPP/build"
ROUTES="$PIPELINE/config/routes"
DATA="$PIPELINE/data"
GOLDEN="$SCRIPT_DIR/golden"
WORK="$SCRIPT_DIR/work"

# Route configs (must match run_chain_sweep.ROUTES).
R1_YAML="$ROUTES/persian_gulf_malacca_paper.yaml"; R1_H5="$DATA/experiment_b_138wp.h5"; R1_ETA=280
R2_YAML="$ROUTES/st_johns_liverpool.yaml";          R2_H5="$DATA/experiment_d_391wp.h5"; R2_ETA=168

# Portable sha256.
if command -v sha256sum >/dev/null 2>&1; then SHA(){ sha256sum "$1" | awk '{print $1}'; }
else SHA(){ shasum -a 256 "$1" | awk '{print $1}'; }; fi

for b in dp_SR dp_luo; do
  [[ -x "$BIN/$b" ]] || {
    echo "missing $BIN/$b — build first:" >&2
    echo "  (cd $DP_CPP && cmake -S . -B build && cmake --build build -j)" >&2
    exit 3
  }
done

mkdir -p "$WORK"
[[ "$MODE" == capture ]] && mkdir -p "$GOLDEN"
FAIL=0

# run_one NAME BIN CSV_OUT <binary args...>
# Binaries write their CSV (sr_dp.csv / luo_dp.csv / baseline.csv) into CWD,
# so we run from WORK and rename to <NAME>.csv.
run_one() {
  local name=$1 bin=$2 csv=$3; shift 3
  local args=("$@")
  ( cd "$WORK" && "$BIN/$bin" "${args[@]}" >"$WORK/$name.stdout" 2>&1 ) || {
    echo "FAIL $name: $bin exited non-zero"; FAIL=1; sed 's/^/    /' "$WORK/$name.stdout" | tail -5; return
  }
  # Stable summary only (fuel + voyage time); drop volatile build/solve timing.
  grep -Ei 'total fuel|voyage time' "$WORK/$name.stdout" > "$WORK/$name.summary" || true

  [[ -f "$WORK/$csv" ]] || { echo "FAIL $name: no $csv produced"; FAIL=1; return; }
  mv "$WORK/$csv" "$WORK/$name.csv"

  if [[ "$MODE" == capture ]]; then
    cp "$WORK/$name.csv" "$GOLDEN/$name.csv"
    cp "$WORK/$name.summary" "$GOLDEN/$name.summary"
    echo "captured $name  sha=$(SHA "$GOLDEN/$name.csv" | cut -c1-12)  [$(tr '\n' ' ' <"$GOLDEN/$name.summary" | sed 's/  */ /g')]"
  else
    local g="$GOLDEN/$name.csv"
    [[ -f "$g" ]] || { echo "FAIL $name: no golden file (run 'capture' on pristine C++ first)"; FAIL=1; return; }
    if [[ "$(SHA "$WORK/$name.csv")" == "$(SHA "$g")" ]]; then
      echo "PASS $name  [$(tr '\n' ' ' <"$WORK/$name.summary" | sed 's/  */ /g')]"
    else
      echo "FAIL $name: CSV differs from golden"
      diff "$g" "$WORK/$name.csv" | head -20 || true
      FAIL=1
    fi
  fi
}

# The matrix = the current setup: actual weather, no RH, default sample_hour.
run_one sr_route1    dp_SR  sr_dp.csv    --yaml "$R1_YAML" --h5 "$R1_H5" --eta "$R1_ETA" --csv
run_one sr_route2    dp_SR  sr_dp.csv    --yaml "$R2_YAML" --h5 "$R2_H5" --eta "$R2_ETA" --csv
run_one luo_route1   dp_luo luo_dp.csv   --yaml "$R1_YAML" --h5 "$R1_H5" --eta "$R1_ETA" --csv
run_one luo_route2   dp_luo luo_dp.csv   --yaml "$R2_YAML" --h5 "$R2_H5" --eta "$R2_ETA" --csv
run_one naive_route1 dp_luo baseline.csv --yaml "$R1_YAML" --h5 "$R1_H5" --eta "$R1_ETA" --baseline --csv
run_one naive_route2 dp_luo baseline.csv --yaml "$R2_YAML" --h5 "$R2_H5" --eta "$R2_ETA" --baseline --csv

echo "------------------------------------------------------------"
if [[ "$MODE" == capture ]]; then
  echo "Golden captured in tests/golden/ — COMMIT IT (frozen reference; do not regenerate after edits)."
elif [[ $FAIL -eq 0 ]]; then
  echo "ALL PASS — non-RH (actual-weather, no-RH) path is byte-identical to golden."
else
  echo "REGRESSION DETECTED — see FAIL lines above."; exit 1
fi
