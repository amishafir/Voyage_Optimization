#!/bin/bash
# Run by cron every 10 minutes (collector.crontab): start the weather collector
# in tmux session collector_v2 if it is not running, e.g. after a reboot or a
# crash. The collector resumes from the /runs table of its archives.
#
# To stop the collector on purpose, first create the file STOP in the pipeline
# directory (touch ~/Ami/pipeline_v2/STOP), then stop it (Ctrl+C in the tmux
# session). Delete STOP to let this script start it again.

DIR=/home/user/Ami/pipeline_v2
export LANG=C.UTF-8
cd "$DIR" || exit 1
[ -e STOP ] && exit 0

# Anchored pattern: matches the collector process only, not this script or
# the cron shell whose command lines merely mention it.
/usr/bin/pgrep -f '^python3 run_all.py --route all' >/dev/null && exit 0

/usr/bin/tmux kill-session -t collector_v2 2>/dev/null
/usr/bin/tmux new-session -d -s collector_v2 'python3 run_all.py --route all'
echo "$(date -u '+%Y-%m-%d %H:%M:%SZ') collector was not running; started it" >> data/watchdog.log
