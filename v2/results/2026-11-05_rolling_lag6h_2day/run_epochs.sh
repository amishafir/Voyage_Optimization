#!/bin/bash
# Luo epoch sweep for the convergence chart: same 25 voyages as run.sh, Luo only (both pricings),
# epochs 3, 2, 1.5, 1 and 0.25 h (6 h and 0.5 h are in run.sh's outputs). Run from v2/ on
# talraviv-pcl, 10 jobs at a time, niced. Outputs epochs/start_<date>/r<route>_luo<steps>.txt,
# with <steps> the epoch in 0.25 h steps.
P=${P:-~/collector-venv/bin/python}
D=${D:-~/voyage_collector/data/snapshots/2026-11-05_09Z}
OUT=results/2026-11-05_rolling_lag6h_2day/epochs
jobs=()
for spec in "3 118" "4 117" "5 118" "6 67"; do
    set -- $spec
    for day in 21 23 25 27 29 31 02; do
        if [ $day = 02 ]; then start="2026-11-02 00:00"; else start="2026-10-$day 00:00"; fi
        end=$(( $(date -u -d "$start" +%s) + $2 * 3600 ))
        [ $end -le $(date -u -d "2026-11-05 00:00" +%s) ] || continue
        dir=$OUT/start_${start/ /T}; dir=${dir%:00}; mkdir -p "$dir"
        for e in 12 8 6 4 1; do
            jobs+=("$P -m voyage_v2 $D/route$1_runs.h5 --start '$start' --eta $2 --luo --epoch $e --luo-pricing both --rolling --info-lag 6 > $dir/r$1_luo$e.txt 2>&1")
        done
    done
done
echo "${#jobs[@]} jobs"
printf '%s\0' "${jobs[@]}" | xargs -0 -P 10 -I{} nice -n 10 bash -c '{}'
echo done
