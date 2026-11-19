#!/bin/sh
# Usage: migcheck.sh <base-ref> <tip-ref> [migrations-dir]
#
# Lists migrations that a single-version migrator would skip or reject once
# <tip> merges into <base>:
#   LOW  new on tip, numbered at or below base's highest in the same directory
#        (silently skipped on any database already migrated past it)
#   DUP  two different migrations share one number after the merge
# Then prints the next free number per directory.
#
# A migration is a file whose name starts with digits and "_". Without
# [migrations-dir], only *.sql files anywhere in the tree are considered.
# Exit: 0 clean, 1 offenders found, 2 usage error, bad ref, or no migrations
# found on either side (wrong directory or wrong repo).

set -u

[ $# -ge 2 ] && [ $# -le 3 ] || {
  echo "usage: migcheck.sh <base-ref> <tip-ref> [migrations-dir]" >&2
  exit 2
}
base=$1 tip=$2 dir=${3:-}

for ref in "$base" "$tip"; do
  git rev-parse --verify --quiet "$ref^{commit}" >/dev/null || {
    echo "migcheck: not a commit: $ref" >&2
    exit 2
  }
done

list() {
  if [ -n "$dir" ]; then
    git ls-tree -r --name-only "$1" -- "$dir"
  else
    git ls-tree -r --name-only "$1" | grep '\.sql$'
  fi
}

{
  list "$base" | sed 's/^/B /'
  list "$tip" | sed 's/^/T /'
} | awk '
  {
    side = $1
    path = substr($0, 3)
    n = split(path, parts, "/")
    file = parts[n]
    d = (n > 1) ? substr(path, 1, length(path) - length(file) - 1) : "."
    if (!match(file, /^[0-9]+_/)) next
    found++
    ver = substr(file, 1, RLENGTH - 1)
    num = ver + 0                      # awk reads "0042" as 42, never octal
    name = substr(file, RLENGTH + 1)
    # 0042_x.up.sql and 0042_x.down.sql are one migration; 0042_x.ce.up.sql is another
    if (!sub(/\.(up|down)\.[^.]*$/, "", name)) sub(/\.[^.]*$/, "", name)
    id = d SUBSEP num SUBSEP name
    if (!(d in width) || length(ver) > width[d]) width[d] = length(ver)
    if (side == "B") {
      inB[id] = 1
      if (!(d in maxB) || num > maxB[d]) maxB[d] = num
    } else {
      inT[id] = 1
    }
    if (!(id in seen)) {
      seen[id] = 1
      key = d SUBSEP num
      count[key]++
      names[key] = names[key] " " ver "_" name
      if (!(d in maxAll) || num > maxAll[d]) maxAll[d] = num
      dirs[d] = 1
    }
    label[id] = ver "_" name
  }
  END {
    if (!found) {
      print "migcheck: no migrations found; check the directory and run it inside the project repo" | "cat 1>&2"
      exit 2
    }
    bad = 0
    for (id in inT) {
      if (id in inB) continue
      split(id, f, SUBSEP)
      if ((f[1] in maxB) && f[2] + 0 <= maxB[f[1]]) {
        printf "LOW  %s/%s  (base is already at %d)\n", f[1], label[id], maxB[f[1]]
        bad = 1
      }
    }
    for (key in count) {
      if (count[key] < 2) continue
      split(key, f, SUBSEP)
      printf "DUP  %s: %s\n", f[1], substr(names[key], 2)
      bad = 1
    }
    for (d in dirs)
      printf "next free in %s: %0" width[d] "d\n", d, maxAll[d] + 1
    exit bad
  }
'
