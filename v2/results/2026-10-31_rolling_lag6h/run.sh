#!/bin/bash
# Rolling horizon with a 6 h information lag on Routes 3-6, both starts; run from v2/ on tsl2.
P=/opt/miniconda3/envs/voyage/bin/python
D=~/voyage_data/snapshot_2026-10-31_15Z
OUT=results/2026-10-31_rolling_lag6h
for start in "2026-10-21 00:00" "2026-10-26 12:00"; do
    dir=$OUT/start_${start/ /T}; dir=${dir%:00}; mkdir -p "$dir"
    for spec in "3 118" "4 117" "5 118" "6 67"; do
        set -- $spec
        $P -m voyage_v2 $D/route$1_runs.h5 --start "$start" --eta $2 --solve --luo --luo-pricing both --rolling --info-lag 6 > $dir/r$1_full_luo6h.txt 2>&1 &
        $P -m voyage_v2 $D/route$1_runs.h5 --start "$start" --eta $2 --luo --epoch 2 --luo-pricing both --rolling --info-lag 6 > $dir/r$1_luo30min.txt 2>&1 &
    done
done
wait
