#!/bin/bash
# Launch a paid run fully detached from the SSH channel.
#   run_detached.sh <name> "<command that reads the API key on stdin>"
# The key is staged in a 0600 temp file, piped in, then deleted; it never appears
# in the command line, the log or the repository.
set -e
R=/home/imss/cw/MedRAX_reproduction_20261027
NAME=${1:?name}
CMD=${2:?command}
LOG="$R/logs/$NAME.log"
mkdir -p "$R/logs"
: > "$LOG"
( cat /tmp/.qwen_key | setsid nohup bash -c "$CMD" >> "$LOG" 2>&1 & echo $! > "$R/logs/$NAME.pid" )
sleep 6
rm -f /tmp/.qwen_key
echo "started $NAME pid $(cat "$R/logs/$NAME.pid")"
tail -n 3 "$LOG" || true
