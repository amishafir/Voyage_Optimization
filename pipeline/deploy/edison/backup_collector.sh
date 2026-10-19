#!/bin/bash
# Run by cron daily at 04:30 UTC (collector.crontab), a quiet time between
# fetches: copy the collector's archives and logs to the lab NAS (/tsl-disk).
# Keeps one copy refreshed daily (latest/) and a dated copy every Sunday
# (weekly/YYYY-MM-DD/); weekly copies older than WEEKLY_KEEP are deleted after a
# successful backup. rsync replaces each file only once its copy is complete,
# so an interrupted backup never damages the previous one.

SRC=/home/user/Ami/pipeline_v2/data/
DST=/tsl-disk/ami/voyage_weather_collector_backup
LOG=/home/user/Ami/pipeline_v2/data/backup.log
WEEKLY_KEEP="3 months"   # GNU date: weekly copies dated before this long ago are deleted
stamp() { date -u '+%Y-%m-%d %H:%M:%SZ'; }

# Delete the weekly copies (weekly/YYYY-MM-DD, nothing else) dated before the cutoff.
prune_weekly() {
    local cutoff d name
    cutoff=$(date -u -d "$WEEKLY_KEEP ago" +%Y-%m-%d) || return 1
    for d in "$DST"/weekly/*; do
        name=$(basename "$d")
        [ -d "$d" ] && [[ "$name" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || continue
        if [[ "$name" < "$cutoff" ]]; then
            if timeout 600 rm -rf -- "$d"; then
                echo "$(stamp) removed weekly copy $name (before $cutoff)" >> "$LOG"
            else
                echo "$(stamp) could not remove weekly copy $name" >> "$LOG"
            fi
        fi
    done
}

exec 9>/tmp/backup_collector.lock
flock -n 9 || exit 0    # the previous backup is still running

# /tsl-disk is an NFS mount; time-limit everything that touches it.
if ! timeout 60 mountpoint -q /tsl-disk; then
    echo "$(stamp) /tsl-disk is not mounted; no backup" >> "$LOG"; exit 1
fi
if ! timeout 60 mkdir -p "$DST/latest" "$DST/weekly"; then
    echo "$(stamp) cannot create $DST; no backup" >> "$LOG"; exit 1
fi
if timeout 3600 rsync -rt --exclude backup.log "$SRC" "$DST/latest/"; then
    if [ "$(date -u +%u)" = 7 ]; then
        timeout 3600 cp -r --preserve=timestamps "$DST/latest" "$DST/weekly/$(date -u +%Y-%m-%d)"
    fi
    prune_weekly
    echo "$(stamp) backup OK: $(du -sh "$DST/latest" | cut -f1) in $DST/latest" >> "$LOG"
else
    echo "$(stamp) backup FAILED (rsync exit $?)" >> "$LOG"; exit 1
fi
