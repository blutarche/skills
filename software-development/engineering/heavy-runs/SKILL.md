---
name: heavy-runs
description: Serialize heavy local runs (full test suites, e2e, docker builds, local model servers) across parallel agents and worktrees with one machine-wide lock, and give each branch its own database on one shared server. Use when several agents or worktrees share a machine and one is about to run a full suite, e2e, an image build, or a model server, or when tests time out or fail only under load.
---

# Heavy Runs

A **heavy run** saturates the machine. Examples: a full test suite, an e2e run, a docker build, a container stack, or traffic to a local model server. When parallel agents each start one, load climbs far past the core count. Tests then fail with health-check timeouts, connect timeouts, out-of-memory kills, and lost containers. None of these is a real bug. Timings taken under that load are worthless. Heavy runs go through one lock, one at a time, on every branch and every project on the machine.

## Steps

1. **Take the lock.** From the project directory, run this skill's `scripts/heavy.sh <command...>`. It waits for the lock, runs the command, and releases the lock on exit.
   - Every agent must use the same path. The default is `/tmp/heavy-run.lock`; set `HEAVY_LOCK` only if every agent uses the same value. Never derive the path from `$TMPDIR`, because sandboxed sessions each get their own.
   - If a sandbox blocks the lock path (the script exits 3), run the heavy command outside the sandbox. Docker and local ports usually need that anyway.
   - Run one suite per acquisition. Prefer a filtered run (one package) to the whole repo when it answers the question, and rerun only the failing package.

2. **Wait visibly.** Run it in the foreground, with a tool timeout longer than the wait plus the run. Send output to a log file, then read the log. Some hosts move a long call to the background at their timeout, and a queued run then dies with no output. If yours does, start the run with the host's background mechanism, poll the log, and never assume the run happened. `heavy.sh --status` names the holder: pid, start time, command, and directory.

3. **Leave others' locks alone.** Never delete a lock you did not take. The script breaks a lock only when it is **stale**. Either the holder's pid answers "No such process", or the lock is older than `HEAVY_MAX_AGE` (default 3 h). "Operation not permitted" from the pid check means the holder is alive in another sandbox. If the wrapper is killed with SIGKILL, its command keeps running and the lock stays held until that command exits. Then the next waiter clears it.

4. **Use your own database.** See [One database per branch](#one-database-per-branch).

5. **Read the result, not the exit code.** A skipped DB test is not a pass. Neither is an auth or connect error in the log, even when the run exits 0. Count the skipped tests in the summary.

6. **Tear down** your stacks and containers when done. Kill child process groups, so that orphan workers do not hold database connections.

## Limits

- Cap parallel workers at a few (2 to 4 on a laptop), not one per task. In one incident, 16 workers on 8 cores drove load to 60–70 and Docker lost its containers twice.
- Run one shared database server and one of each shared service (mail catcher, object store). Never run a stack per branch.
- Send one client at a time to a single local model server. Concurrent traffic made one request take 13 minutes and invalidated every timing from both agents.
- Close idle editor language servers when memory is tight. They starve the container VM.

## One database per branch

- On the one shared server, each branch or worktree gets its own database, created fresh for a test run and dropped afterwards. Name it `<project>_<branch-slug>`, with the slug lowercased and every character outside `a-z0-9_` replaced by `_`. Create and drop it through the project's wrapper, or else the server's own tools (`createdb`, `dropdb`).
- Pass it the way the project's test entrypoint expects (for example `TEST_DATABASE_URL`), and run through that entrypoint. A raw task runner can skip the translation and fall back to the default URL in config. In one incident that default was the developer's own playground database.
- Use the project's DB wrapper if it has one. Never hand-build credentials: a hand-built URL once failed auth while the run still exited 0.
- Against a shared database, run test packages serially (`--concurrency=1` or the runner's equivalent), matching whatever the merge gate uses. Global sweeps and counters race across files. Tests should assert their own rows, not global counts.

## Failures under load

- After an overload, rerun only once the machine has recovered, for example three database connects in a row under 2 s.
- A timing or timeout failure in a package you did not touch, which passes when run alone under the lock, is load noise. Record it in the PR body; do not "fix" it.
- Run one scenario per fresh app instance when scenarios share fixture accounts. A second sign-up of the same test user fails with 409.
