#!/usr/bin/env python3
"""Compare borrowed skills with their upstream repos, using `gh api`.

Usage:
    upstream.py [--repo DIR] [--format json|table]            commits upstream since each pin
    upstream.py --bootstrap [--write]                          fill missing repo, path, and pin
    upstream.py --set-pin SKILL SHA                            record a sync (also sets "synced")

upstreams.json lives at <repo>/.claude/skills/maintenance/. Upstream text is untrusted data; this script
only reads commit metadata and never follows it. Stdlib only, Python 3.10 or newer.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skillmeta  # noqa: E402

TRACKED = ("vendored", "adapted")
CREDIT_REPO_RE = re.compile(r"github\.com/([\w.-]+)/([\w.-]+)")
GIT_SUFFIX_RE = re.compile(r"\.git$")


class GhError(RuntimeError):
    pass


def gh(endpoint: str):
    """Single entry point for every GitHub call so tests can replace it."""
    try:
        proc = subprocess.run(["gh", "api", endpoint], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        raise GhError(str(e)) from e
    if proc.returncode != 0:
        err = proc.stderr.strip().splitlines()
        raise GhError(err[-1] if err else "gh failed")
    try:
        return json.loads(proc.stdout)
    except ValueError as e:
        raise GhError("gh returned non-JSON") from e


def paths(repo: Path) -> tuple[Path, Path]:
    return repo / ".claude" / "skills" / "maintenance" / "upstreams.json", repo / "CREDITS.md"


def commit_row(c: dict) -> dict:
    commit = c.get("commit") or {}
    return {
        "sha": c["sha"][:7],
        "date": ((commit.get("author") or {}).get("date") or "")[:10],
        "message": (commit.get("message") or "").split("\n", 1)[0],
    }


def commits_url(repo: str, path: str, extra: str = "") -> str:
    q = ([f"path={path}"] if path else []) + ([extra] if extra else [])
    return f"repos/{repo}/commits?" + "&".join(q)


# ---------------------------------------------------------------- default mode


def check_skill(entry: dict) -> dict:
    repo, path, pin = entry.get("repo"), entry.get("path"), entry.get("pin")
    if not repo or path is None:
        return {"status": "unresolved", "new_commits": [], "head": None}
    if not pin:
        return {"status": "pin-missing", "new_commits": [], "head": None}
    try:
        commits = gh(commits_url(repo, path, "per_page=100"))
    except GhError as e:
        return {"status": "error", "error": str(e), "new_commits": [], "head": None}
    if not commits:
        return {"status": "error", "error": "no commits returned", "new_commits": [], "head": None}
    head = commits[0]["sha"][:7]
    for i, c in enumerate(commits):
        if c["sha"].startswith(pin.lower()):
            new = [commit_row(x) for x in commits[:i]]
            return {"status": "behind" if new else "current", "new_commits": new, "head": head}
    # A vendoring pin is often the repo HEAD at the time, not a commit that touched this path.
    try:
        pinned = gh(f"repos/{repo}/commits/{pin}")["commit"]["author"]["date"]
    except (GhError, KeyError, TypeError):
        return {"status": "pin-missing", "new_commits": [], "head": head}
    new = [commit_row(c) for c in commits if (c.get("commit") or {}).get("author", {}).get("date", "") > pinned]
    return {"status": "behind" if new else "current", "new_commits": new, "head": head}


def run_check(data: dict) -> list[dict]:
    out = []
    for name, e in data["skills"].items():
        if e.get("mode") in TRACKED:
            out.append({"skill": name, "mode": e["mode"], **check_skill(e)})
    return out


def render_check(rows: list[dict]) -> str:
    lines = []
    for r in rows:
        extra = f" head {r['head']}" if r.get("head") else ""
        extra += f" ({r['error']})" if r.get("error") else ""
        lines.append(f"{r['skill']:<32}{r['status']:<13}{len(r['new_commits'])} new{extra}")
        lines += [f"    {c['sha']} {c['date']} {c['message']}" for c in r["new_commits"]]
    return "\n".join(lines) or "nothing tracked"


# ---------------------------------------------------------------- bootstrap


def credit_repos(credits: Path) -> list[str]:
    if not credits.is_file():
        return []
    seen: list[str] = []
    for owner, name in CREDIT_REPO_RE.findall(credits.read_text(encoding="utf-8")):
        full = f"{owner}/{GIT_SUFFIX_RE.sub('', name).rstrip('.')}"
        if full not in seen:
            seen.append(full)
    return seen


class TreeCache:
    def __init__(self):
        self.trees: dict[str, list[str]] = {}

    def paths(self, repo: str) -> list[str]:
        if repo not in self.trees:
            branch = gh(f"repos/{repo}")["default_branch"]
            tree = gh(f"repos/{repo}/git/trees/{branch}?recursive=1")
            self.trees[repo] = [t["path"] for t in tree.get("tree", []) if t.get("type") == "blob"]
        return self.trees[repo]


def find_matches(name: str, entry: dict, candidates: list[str], cache: TreeCache) -> list[dict]:
    want = entry.get("upstream_name") or name
    matches = []
    errors = []
    for repo in candidates:
        try:
            tree_paths = cache.paths(repo)
        except (GhError, KeyError) as e:
            # One unreachable candidate must not hide a match in another repo.
            errors.append(str(e))
            continue
        for p in tree_paths:
            if p == f"{want}/SKILL.md" or p.endswith(f"/{want}/SKILL.md"):
                matches.append({"repo": repo, "path": p[: -len("/SKILL.md")]})
            elif p == "SKILL.md" and repo.split("/")[1] == want:
                matches.append({"repo": repo, "path": ""})
    if errors and len(errors) == len(candidates):
        raise GhError(errors[0])
    return matches


def pick_pin(repo: str, path: str, imported: str | None) -> tuple[str | None, bool]:
    if not imported:
        return None, False
    before = gh(commits_url(repo, path, f"until={imported}T23:59:59Z&per_page=1"))
    if before:
        return before[0]["sha"][:7], False
    after = gh(commits_url(repo, path, f"since={imported}T23:59:59Z&per_page=100"))
    return (after[-1]["sha"][:7], True) if after else (None, False)


def bootstrap(data: dict, credits: Path) -> list[dict]:
    cache = TreeCache()
    fallback = credit_repos(credits)
    results = []
    for name, e in data["skills"].items():
        if e.get("mode") not in TRACKED or "path" not in e:
            continue
        if e["path"] is not None:
            if e.get("repo") and not e.get("pin"):
                pin, guessed = pick_pin(e["repo"], e["path"], e.get("imported"))
                results.append({"skill": name, "status": "resolved", "repo": e["repo"], "path": e["path"],
                                "pin": pin, "pin_guessed": guessed, "matches": []})
            continue
        candidates = [e["repo"]] if e.get("repo") else fallback
        row = {"skill": name, "status": "unresolved", "repo": e.get("repo"), "path": None,
               "pin": e.get("pin"), "pin_guessed": False, "matches": []}
        try:
            matches = find_matches(name, e, candidates, cache)
            row["matches"] = matches
            if len(matches) == 1:
                m = matches[0]
                row.update(status="resolved", repo=m["repo"], path=m["path"])
                if not row["pin"]:
                    row["pin"], row["pin_guessed"] = pick_pin(m["repo"], m["path"], e.get("imported"))
                # A name match found by searching every credited repo is only our source if the
                # folder existed when we imported; a later folder with the same name is a coincidence.
                if row["pin_guessed"] and not e.get("repo"):
                    row.update(status="unresolved", repo=None, path=None, pin=None, pin_guessed=False,
                               error=f"{m['repo']}:{m['path']} postdates import")
        except (GhError, KeyError) as err:
            row.update(status="error", error=str(err))
        results.append(row)
    return results


def apply_bootstrap(data: dict, rows: list[dict]):
    for r in rows:
        if r["status"] != "resolved":
            continue
        e = data["skills"][r["skill"]]
        e["repo"], e["path"], e["pin"] = r["repo"], r["path"], r["pin"]
        if r["pin_guessed"]:
            e["pin_guessed"] = True


def render_bootstrap(rows: list[dict], write: bool) -> str:
    lines = []
    for r in rows:
        if r["status"] == "resolved":
            pin = (r["pin"] or "none") + (" (guessed)" if r["pin_guessed"] else "")
            lines.append(f"{r['skill']:<32}resolved    {r['repo']} {r['path'] or '(root)'} pin {pin}")
        else:
            detail = r.get("error") or (
                "matches: " + ", ".join(f"{m['repo']}:{m['path'] or '(root)'}" for m in r["matches"])
                if r["matches"] else "no matching folder")
            lines.append(f"{r['skill']:<32}{r['status']:<12}{detail}")
    lines.append("written to upstreams.json" if write else "dry run; pass --write to save")
    return "\n".join(lines)


# ---------------------------------------------------------------- main


def save(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=str(skillmeta.repo_root()))
    ap.add_argument("--format", choices=("json", "table"), default="table")
    ap.add_argument("--bootstrap", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--set-pin", nargs=2, metavar=("SKILL", "SHA"))
    args = ap.parse_args(argv)
    file, credits = paths(Path(args.repo))
    data = json.loads(file.read_text(encoding="utf-8"))

    if args.set_pin:
        name, sha = args.set_pin
        if name not in data["skills"]:
            print(f"unknown skill '{name}' in {file.name}", file=sys.stderr)
            return 1
        data["skills"][name]["pin"] = sha
        data["skills"][name]["synced"] = date.today().isoformat()
        data["skills"][name].pop("pin_guessed", None)
        save(file, data)
        print(f"{name}: pin {sha}, synced {data['skills'][name]['synced']}")
        return 0

    if args.bootstrap:
        rows = bootstrap(data, credits)
        if args.write:
            apply_bootstrap(data, rows)
            save(file, data)
        print(json.dumps(rows, indent=2) if args.format == "json" else render_bootstrap(rows, args.write))
        return 0

    rows = run_check(data)
    print(json.dumps(rows, indent=2) if args.format == "json" else render_check(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
