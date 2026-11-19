#!/usr/bin/env python3
"""Static checks over every SKILL.md in the repo; each finding is a lead, not a verdict.

Usage:
    audit.py [--repo DIR] [--known FILE] [--format json|table] [--today YYYY-MM-DD] [--verbose]

--known is a file of extra host skill names, one per line, that count as real references.
Table output lists warn findings in full and collapses info findings to a count per check
unless --verbose.
Stdlib only, Python 3.10 or newer.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skillmeta  # noqa: E402

TRIGGER_RE = re.compile(r"\buse\s+(when|whenever|before|after|for|on|to)\b", re.I)
NPX_LATEST_RE = re.compile(r"\bnpx\s+(?:-\S+\s+)*[\w@/.-]+@latest\b")
CODEX_OFF_RE = re.compile(r"allow_implicit_invocation:\s*false")
SEVERITY = {"host-cli": "info", "no-readme-row": "info", "trigger-on-user-invoked": "info"}
FETCHED_RE = re.compile(r"\bfetched\s+(\d{4})-(\d{2})(?:-(\d{2}))?\b", re.I)
MODEL_ID_RES = [re.compile(p) for p in (
    r"claude-(?:opus|sonnet|haiku|fable)-\d[-\w.]*", r"\bgpt-\d[\w.-]*", r"\bgemini-\d[\w.-]*",
    r"\bo\d-(?:mini|pro)\b")]
HOST_CLI_RE = re.compile(r"\borca\b|\bt3_\w*|\bcursor-agent\b|\bhermes\b", re.I)
# A backtick counts only when it opens a span, so ".env`/secrets" is not a reference.
SLASH_RE = re.compile(r"(?:^|[\s(*]|(?:^|(?<=[\s(*]))`)/([A-Za-z0-9][A-Za-z0-9._:-]*)(/?)")
BACKTICK_SKILL_RE = re.compile(r"`([a-z0-9][a-z0-9:_-]+)` skill\b")
PATH_SKILL_RE = re.compile(r"\bskills/([a-z0-9][a-z0-9:_-]*)/")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
SYSTEM_PATHS = {"tmp", "etc", "usr", "var", "dev", "bin", "opt", "home", "proc", "null",
                "stdout", "stderr", "stdin", "dev", "sbin", "lib", "mnt", "root", "private"}
HOST_COMMANDS = {"compact", "clear", "config", "mcp", "reload", "model", "help", "goal", "advisor",
                 "init", "review", "resume", "exit", "status", "cost", "login", "logout", "fast",
                 "sandbox", "simplify", "code-review", "security-review", "loop", "schedule", "run",
                 "memory", "permissions", "hooks", "agents", "plugins", "tree", "design", "settings"}


def finding(skill, file, line, check, detail):
    return {"skill": skill, "file": file, "line": line, "check": check,
            "severity": SEVERITY.get(check, "warn"), "detail": detail}


def name_ok(name: str) -> bool:
    return bool(re.match(r"^[a-z0-9][a-z0-9:_-]+$", name))


def in_backticks_span(line: str, pos: int) -> bool:
    return line[:pos].count("`") % 2 == 1


def audit_file(path: Path, repo: Path, names: set[str], known: set[str], removed: set[str],
               today: date) -> list[dict]:
    rel = str(path.relative_to(repo))
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")
    fm, where = skillmeta.parse_frontmatter(text)
    skill = fm.get("name", "").strip() or path.parent.name
    out: list[dict] = []
    add = lambda ln, check, detail: out.append(finding(skill, rel, ln, check, detail))  # noqa: E731

    desc = fm.get("description", "")
    dline = where.get("description", 1)
    user_only = fm.get("disable-model-invocation", "").strip().lower() == "true"
    if not user_only and not TRIGGER_RE.search(desc):
        add(dline, "no-trigger", "description has no 'Use when' / 'Use before' / 'Use for' style trigger")
    if user_only and TRIGGER_RE.search(desc):
        add(dline, "trigger-on-user-invoked", "user-invoked skill has a 'Use when' trigger in its description")
    # Project-local .claude/skills are Claude-only; Codex never sees them.
    if user_only and ".claude" not in path.relative_to(repo).parts:
        policy = path.parent / "agents" / "openai.yaml"
        if not (policy.is_file() and CODEX_OFF_RE.search(policy.read_text(encoding="utf-8", errors="replace"))):
            add(1, "no-codex-policy", "disable-model-invocation without agents/openai.yaml allow_implicit_invocation: false")
    if len(desc) > 1024:
        add(dline, "long-description", f"{len(desc)} chars (limit 1024)")
    body_lines = len(lines) - 1 if lines and lines[-1] == "" else len(lines)
    if body_lines > 500:
        add(1, "long-skill", f"{body_lines} lines (limit 500)")

    ok_names = names | known | removed
    in_fence = False
    for i, line in enumerate(lines, 1):
        fenced = in_fence or bool(FENCE_RE.match(line))
        if FENCE_RE.match(line):
            in_fence = not in_fence

        for r in sorted(removed):
            if re.search(rf"(?<![\w-]){re.escape(r)}(?![\w-])", line):
                add(i, "removed-ref", f"mentions removed skill '{r}'")

        if not fenced:
            for m in SLASH_RE.finditer(line):
                raw = m.group(1)
                name = raw.rstrip(".:")
                if (m.group(2) or "." in name or not name_ok(name) or name in ok_names
                        or name in SYSTEM_PATHS or name in HOST_COMMANDS or name in {"name", "skill"}):
                    continue
                add(i, "unknown-ref", f"/{name} is not a repo, host, or removed skill")
        for m in BACKTICK_SKILL_RE.finditer(line):
            n = m.group(1)
            if n not in ok_names and n not in HOST_COMMANDS and "." not in n:
                add(i, "unknown-ref", f"`{n}` skill is not a repo, host, or removed skill")
        for m in PATH_SKILL_RE.finditer(line):
            n = m.group(1)
            if n not in ok_names:
                add(i, "unknown-ref", f"skills/{n}/ is not a repo, host, or removed skill")

        for m in NPX_LATEST_RE.finditer(line):
            add(i, "npx-latest", f"unpinned '{m.group(0)}'")
        for m in FETCHED_RE.finditer(line):
            try:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3) or 1))
            except ValueError:
                continue
            if (today - d).days > 180:
                add(i, "stale-source", f"fetched {m.group(0).split()[-1]} is {(today - d).days} days old")
        for rx in MODEL_ID_RES:
            for m in rx.finditer(line):
                add(i, "model-id", f"pinned model id '{m.group(0)}'")
        hosts = sorted({m.group(0).lower() for m in HOST_CLI_RE.finditer(line)})
        if hosts:
            add(i, "host-cli", "mentions " + ", ".join(hosts))

    area = rel.split("/")[0]
    readme = repo / area / "README.md"
    if len(rel.split("/")) > 2 and readme.is_file() and not re.search(
            rf"(^|[(/]){re.escape(path.parent.name)}/SKILL\.md", readme.read_text(encoding="utf-8"),
            re.M):
        add(1, "no-readme-row", f"{area}/README.md has no entry for '{path.parent.name}'")
    return out


def load_removed(repo: Path) -> set[str]:
    f = repo / ".claude" / "skills" / "maintenance" / "upstreams.json"
    if not f.is_file():
        return set()
    try:
        return set(json.loads(f.read_text(encoding="utf-8")).get("removed", {}))
    except ValueError:
        return set()


def run(repo: Path, known: set[str], today: date) -> list[dict]:
    names = set(skillmeta.load_repo_skills(repo))
    removed = load_removed(repo)
    results = []
    for f in skillmeta.find_skill_files(repo):
        results += audit_file(f, repo, names, known, removed, today)
    return results


def render_table(findings: list[dict], verbose: bool = False) -> str:
    if not findings:
        return "no findings"
    lines = []
    for level in ("error", "warn", "info"):
        by_check: dict[str, list[dict]] = {}
        for f in findings:
            if f["severity"] == level:
                by_check.setdefault(f["check"], []).append(f)
        for check in sorted(by_check):
            items = by_check[check]
            if level == "info" and not verbose:
                lines.append(f"info {check}: {len(items)} (use --verbose to list)")
                continue
            lines.append(f"{check} ({len(items)})" if level != "info" else f"info {check} ({len(items)})")
            lines += [f"  {f['file']}:{f['line']}  {f['skill']}  {f['detail']}" for f in items]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=str(skillmeta.repo_root()))
    ap.add_argument("--known")
    ap.add_argument("--format", choices=("json", "table"), default="table")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--today", type=date.fromisoformat, default=date.today())
    args = ap.parse_args(argv)
    known = set()
    if args.known:
        known = {ln.strip().lstrip("/") for ln in Path(args.known).read_text().splitlines() if ln.strip()}
    findings = run(Path(args.repo), known, args.today)
    print(json.dumps(findings, indent=2) if args.format == "json" else render_table(findings, args.verbose))
    return 0


if __name__ == "__main__":
    sys.exit(main())
