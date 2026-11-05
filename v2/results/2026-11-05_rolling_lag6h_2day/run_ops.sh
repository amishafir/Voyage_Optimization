#!/bin/bash
# Computation counts (count_ops.py) for the same 25 voyages, one process per voyage covering the
# full graph and Luo at all epochs and both pricings. Run from v2/ on talraviv-pcl, 10 at a time.
P=${P:-~/collector-venv/bin/python}
D=${D:-~/voyage_collector/data/snapshots/2026-11-05_09Z}
OUT=results/2026-11-05_rolling_lag6h_2day/ops
mkdir -p $OUT
jobs=()
for spec in "3 118" "4 117" "5 118" "6 67"; do
    set -- $spec
    for day in 21 23 25 27 29 31 02; do
        if [ $day = 02 ]; then start="2026-11-02 00:00"; else start="2026-10-$day 00:00"; fi
        end=$(( $(date -u -d "$start" +%s) + $2 * 3600 ))
        [ $end -le $(date -u -d "2026-11-05 00:00" +%s) ] || continue
        tag=${start/ /T}; tag=${tag%:00}
        jobs+=("$P results/2026-11-05_rolling_lag6h_2day/count_ops.py $D/route$1_runs.h5 '$start' $2 $OUT/r$1_$tag.csv > $OUT/r$1_$tag.log 2>&1")
    done
done
echo "${#jobs[@]} jobs"
printf '%s\0' "${jobs[@]}" | xargs -0 -P 10 -I{} nice -n 10 bash -c '{}'
echo done
