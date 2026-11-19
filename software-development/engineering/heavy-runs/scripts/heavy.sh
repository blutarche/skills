#!/bin/sh
# Usage: heavy.sh <command> [args...]    run the command under the machine-wide lock
#        heavy.sh --status               print the holder; exit 0 free, 1 held
#
# Every agent on the machine must use the same lock path, so the default is a
# fixed absolute path, not one under $TMPDIR (sandboxed sessions get their own).
#   HEAVY_LOCK     lock directory          (default /tmp/heavy-run.lock)
#   HEAVY_POLL     seconds between tries   (default 20)
#   HEAVY_MAX_AGE  seconds after which a held lock is stale even if its pid
#                  still answers, since pids get reused (default 10800)
# Exit: the command's status; 2 usage; 3 lock path not writable.

set -u
LOCK=${HEAVY_LOCK:-/tmp/heavy-run.lock}
POLL=${HEAVY_POLL:-20}
MAX_AGE=${HEAVY_MAX_AGE:-10800}

now() { awk 'BEGIN { srand(); print srand() }'; }
field() { sed -n "s/^$1=//p" "$2/owner" 2>/dev/null; }

# "Operation not permitted" means the process exists but belongs to another
# sandbox or user: alive. Only "No such process" (or any other error) is dead.
alive() {
  err=$(kill -0 "$1" 2>&1) && return 0
  case $err in *ermitted*) return 0 ;; esac
  return 1
}

if [ "${1:-}" = "--status" ]; then
  if [ -d "$LOCK" ]; then
    echo "held: $LOCK"
    cat "$LOCK/owner" 2>/dev/null || echo "(no owner file)"
    exit 1
  fi
  echo "free: $LOCK"
  exit 0
fi
[ $# -gt 0 ] || { echo "usage: heavy.sh <command> [args...] | --status" >&2; exit 2; }

# Stale: neither the wrapper nor its command is alive, or the lock is older
# than MAX_AGE. A lock with no owner file (taken by hand with mkdir) is aged
# from when this waiter first saw it.
ownerless_since=
stale() {
  pid=$(field pid "$LOCK")
  child=$(field child "$LOCK")
  started=$(field started "$LOCK")
  if [ -z "$pid" ]; then
    [ -n "$ownerless_since" ] || ownerless_since=$(now)
    [ $(( $(now) - ownerless_since )) -ge "$MAX_AGE" ]
    return
  fi
  ownerless_since=
  if alive "$pid" || { [ -n "$child" ] && alive "$child"; }; then
    [ -n "$started" ] && [ $(( $(now) - started )) -ge "$MAX_AGE" ]
    return
  fi
  return 0
}

# Rename first so two waiters cannot both break the same lock; if the holder
# changed between the check and the rename, put the fresh lock back.
break_lock() {
  judged=$(field pid "$LOCK")
  mv "$LOCK" "$LOCK.stale.$$" 2>/dev/null || return 0
  if [ "$(field pid "$LOCK.stale.$$")" != "$judged" ]; then
    mv "$LOCK.stale.$$" "$LOCK" 2>/dev/null || {
      echo "heavy: raced while breaking a stale lock; left it at $LOCK.stale.$$" >&2
    }
    return 0
  fi
  echo "heavy: broke stale lock ($(cat "$LOCK.stale.$$/owner" 2>/dev/null | tr '\n' ' '))" >&2
  rm -rf "$LOCK.stale.$$"
}

waited=0
until mkdir "$LOCK" 2>/dev/null; do
  if [ ! -d "$LOCK" ]; then
    echo "heavy: cannot create $LOCK (missing parent or no write access; a sandbox may block it)" >&2
    exit 3
  fi
  if stale; then
    break_lock
    continue
  fi
  [ $((waited % 300)) -lt "$POLL" ] &&
    echo "heavy: waiting ${waited}s for $(field cmd "$LOCK") (pid $(field pid "$LOCK"))" >&2
  sleep "$POLL"
  waited=$((waited + POLL))
done

# Only now is the lock ours, so only now may the exit trap remove it.
release() {
  [ "$(field pid "$LOCK")" = "$$" ] && rm -rf "$LOCK"
}
trap release EXIT

# The command runs in the background so a signal to this wrapper reaches it
# now, not after it finishes; a background child ignores terminal SIGINT, so
# every signal is forwarded as TERM. fd 3 hands it the caller's stdin.
child=
stop() {
  if [ -n "$child" ]; then
    kill -s TERM "$child" 2>/dev/null
    wait "$child"
  fi
  exit "$1"
}
trap 'stop 129' HUP
trap 'stop 130' INT
trap 'stop 143' TERM

{
  echo "pid=$$"
  echo "started=$(now)"
  echo "cwd=$(pwd)"
  echo "cmd=$*"
} > "$LOCK/owner"

[ "$waited" -gt 0 ] && echo "heavy: got the lock after ${waited}s" >&2
exec 3<&0
"$@" 0<&3 3<&- &
child=$!
echo "child=$child" >> "$LOCK/owner"
wait "$child"
