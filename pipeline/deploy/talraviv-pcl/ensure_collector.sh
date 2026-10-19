#!/bin/bash
# Run by cron every 10 minutes (collector.crontab): start the collector for the volatile
# routes (Routes 3-6, "--route volatile") in tmux session collector_volatile if it is not
# running, e.g. after a reboot or a crash. The collector resumes from the /runs table of its
# archives.
#
# The pipeline copy is the directory two levels up from this script (e.g. ~/voyage_collector),
# and Python is the account's virtual environment ~/collector-venv (override with
# COLLECTOR_PYTHON).
#
# To stop the collector on purpose, first create the file STOP in the pipeline directory
# (touch ~/voyage_collector/STOP), then stop it (Ctrl+C in the tmux session). Delete STOP to
# let this script start it again.

DIR=$(cd "$(dirname "$0")/../.." && pwd)
PY=${COLLECTOR_PYTHON:-$HOME/collector-venv/bin/python}
ROUTES=volatile
SESSION=collector_volatile
export LANG=C.UTF-8
cd "$DIR" || exit 1
[ -e STOP ] && exit 0
mkdir -p data

# Anchored pattern: matches the collector process only, not this script or the cron shell
# whose command lines merely mention it.
/usr/bin/pgrep -u "$(id -u)" -f "^$PY run_all.py --route $ROUTES\$" >/dev/null && exit 0

/usr/bin/tmux kill-session -t "$SESSION" 2>/dev/null
/usr/bin/tmux new-session -d -s "$SESSION" "$PY run_all.py --route $ROUTES"
echo "$(date -u '+%Y-%m-%d %H:%M:%SZ') collector was not running; started it" >> data/watchdog.log
