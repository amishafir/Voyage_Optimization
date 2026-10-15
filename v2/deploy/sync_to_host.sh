#!/usr/bin/env bash
# Copy v2 to a lab machine and give it the route archives, so solves run there.
#
#   v2/deploy/sync_to_host.sh shlomo1            # code + latest archives from edison
#   v2/deploy/sync_to_host.sh shlomo1 --code     # code only
#
# On HOST the layout mirrors the repository, under ~/Ami/voyage:
#   v2/               the program (its C++ core is compiled there on first use)
#   pipeline/shared/  needed by the tests (reference physics, archive writer)
#   data/             route1_runs.h5, route2_runs.h5, copied from edison's live collector
# Run there, e.g.:
#   ssh HOST 'cd ~/Ami/voyage/v2 && python3 -m voyage_v2 ../data/route1_runs.h5 --start "2026-10-14 13:20" --eta 280 --solve --luo'
#
# Hosts are SSH aliases (~/.ssh/config). The archives are relayed through this machine,
# since the lab machines need not hold keys for each other.
set -euo pipefail

HOST=${1:?usage: $0 HOST [--code]}
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
DEST="Ami/voyage"
SSH=(ssh -o BatchMode=yes)
RSYNC=(rsync -a --delete -e "ssh -o BatchMode=yes" --exclude build --exclude __pycache__)

"${SSH[@]}" "$HOST" "mkdir -p $DEST/pipeline $DEST/data"
"${RSYNC[@]}" "$REPO/v2" "$HOST:$DEST/"
"${RSYNC[@]}" "$REPO/pipeline/shared" "$HOST:$DEST/pipeline/"
echo "code synced to $HOST:~/$DEST"

if [[ "${2:-}" != "--code" ]]; then
    TMP=$(mktemp -d)
    trap 'rm -rf "$TMP"' EXIT
    rsync -a -e "ssh -o BatchMode=yes" "edison:Ami/pipeline_v2/data/route1_runs.h5" \
        "edison:Ami/pipeline_v2/data/route2_runs.h5" "$TMP/"
    rsync -a -e "ssh -o BatchMode=yes" "$TMP/route1_runs.h5" "$TMP/route2_runs.h5" "$HOST:$DEST/data/"
    echo "archives from edison copied to $HOST:~/$DEST/data"
fi
