#!/bin/bash
# Rolling horizon with a 6 h information lag on Routes 3-6, departures every 48 h at 00:00 UTC
# from 2026-10-21 (Tal's first start) while the voyage ends by 2026-11-05 00:00 UTC (last actual
# weather in the snapshot). Run from v2/ on talraviv-pcl: 50 jobs, 10 at a time, niced.
P=${P:-~/collector-venv/bin/python}
D=${D:-~/voyage_collector/data/snapshots/2026-11-05_09Z}
OUT=results/2026-11-05_rolling_lag6h_2day
jobs=()
for spec in "3 118" "4 117" "5 118" "6 67"; do
    set -- $spec
    for day in 21 23 25 27 29 31 02; do
        if [ $day = 02 ]; then start="2026-11-02 00:00"; else start="2026-10-$day 00:00"; fi
        end=$(( $(date -u -d "$start" +%s) + $2 * 3600 ))
        [ $end -le $(date -u -d "2026-11-05 00:00" +%s) ] || continue
        dir=$OUT/start_${start/ /T}; dir=${dir%:00}; mkdir -p "$dir"
        jobs+=("$P -m voyage_v2 $D/route$1_runs.h5 --start '$start' --eta $2 --solve --luo --luo-pricing both --rolling --info-lag 6 > $dir/r$1_full_luo6h.txt 2>&1")
        jobs+=("$P -m voyage_v2 $D/route$1_runs.h5 --start '$start' --eta $2 --luo --epoch 2 --luo-pricing both --rolling --info-lag 6 > $dir/r$1_luo30min.txt 2>&1")
    done
done
echo "${#jobs[@]} jobs"
printf '%s\0' "${jobs[@]}" | xargs -0 -P 10 -I{} nice -n 10 bash -c '{}'
echo done
