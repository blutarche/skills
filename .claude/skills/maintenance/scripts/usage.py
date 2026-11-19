#!/usr/bin/env python3
"""Count skill use on this machine from agent transcripts and state databases.

Reads, when present and always read-only: Claude Code transcripts, Codex rollouts, T3 Code's
state database, and Hermes's state.db. Prints skill names, counts, dates, and source names; never
message text.

Usage:
    usage.py [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--repo DIR] [--home DIR]
             [--archive DIR ...] [--format json|table] [--drawer] [--host NAME]

Stdlib only, Python 3.10 or newer.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import socket
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skillmeta  # noqa: E402

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9:_-]{1,63}$")
PATH_SKILL_RE = re.compile(r"/([a-z0-9][a-z0-9:_-]*)/SKILL\.md")
LEAD_RE = re.compile(r"^[$/]([A-Za-z0-9][A-Za-z0-9:_-]*)(?=\s|$)")
COMMAND_NAME_RE = re.compile(r"<command-name>\s*/?([^<\s]+)\s*</command-name>")
BUILTINS = {
    "compact", "clear", "config", "mcp", "reload", "model", "help", "goal", "advisor", "init",
    "review", "resume", "exit", "status", "cost", "login", "logout", "fast", "tree", "design",
    "settings", "plugins", "agents", "hooks", "memory", "permissions",
}
KINDS = ("model", "user", "read")
CODEX_CALLS = ("function_call", "custom_tool_call", "local_shell_call")
DRAWER_LIMIT = 3000
FOREIGN_TOP = 15


def clean_name(name) -> str | None:
    if not isinstance(name, str):
        return None
    name = name.strip().lstrip("/")
    return name if NAME_RE.match(name) else None


def parse_ts(value) -> datetime | None:
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, timezone.utc)
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, OverflowError, OSError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def lead_name(text) -> str | None:
    """Skill name a user message starts with (`/name` or `$name`), or None."""
    if not isinstance(text, str):
        return None
    m = LEAD_RE.match(text.lstrip())
    return clean_name(m.group(1)) if m else None


def open_ro(path: Path) -> sqlite3.Connection:
    quoted = quote(str(path))
    for mode in ("mode=ro", "immutable=1"):
        try:
            con = sqlite3.connect(f"file:{quoted}?{mode}", uri=True)
            con.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchall()
            return con
        except sqlite3.Error:
            continue
    raise sqlite3.OperationalError(f"cannot open {path} read-only")


class Tally:
    def __init__(self, since: datetime, until: datetime):
        self.since, self.until = since, until
        self.events: dict[tuple, dict] = {}
        self.sources: dict[str, dict] = {}

    def source(self, name: str, present: bool = True) -> dict:
        return self.sources.setdefault(
            name, {"present": present, "files_or_rows": 0, "events": 0, "first": None, "last": None})

    def add(self, skill, kind, ts, source, session):
        if skill is None or ts is None or not (self.since <= ts < self.until):
            return
        st = self.source(source)
        st["events"] += 1
        stamp = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        st["first"] = min(st["first"] or stamp, stamp)
        st["last"] = max(st["last"] or stamp, stamp)
        # T3 drives Claude and Codex, so one use shows up in several sources a few seconds apart.
        ev = self.events.setdefault((skill, kind, int(ts.timestamp()) // 60), {
            "ts": ts, "sources": set(), "sessions": set()})
        ev["sources"].add(source)
        # Each source has its own session ids for the same conversation; keep one per merged event.
        if session and not ev["sessions"]:
            ev["sessions"].add(str(session))


# ---------------------------------------------------------------- claude


def scan_claude(root: Path, source: str, tally: Tally):
    st = tally.source(source, present=root.is_dir())
    if not root.is_dir():
        return
    cutoff = tally.since.timestamp()
    for f in sorted(root.rglob("*.jsonl")):
        try:
            if f.stat().st_mtime < cutoff:
                continue
        except OSError:
            continue
        st["files_or_rows"] += 1
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"Skill"' not in line and "SKILL.md" not in line and "command-name" not in line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(obj, dict):
                    continue
                claude_line(obj, source, tally)


def claude_line(obj: dict, source: str, tally: Tally):
    ts, sid = parse_ts(obj.get("timestamp")), obj.get("sessionId")
    msg = obj.get("message")
    content = msg.get("content") if isinstance(msg, dict) else None
    if obj.get("type") == "assistant" and isinstance(content, list):
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_use":
                continue
            inp = item.get("input") if isinstance(item.get("input"), dict) else {}
            if item.get("name") == "Skill":
                tally.add(clean_name(inp.get("skill")), "model", ts, source, sid)
            elif item.get("name") == "Read":
                fp = inp.get("file_path")
                if isinstance(fp, str) and fp.endswith("/SKILL.md"):
                    tally.add(clean_name(PurePosixPath(fp).parent.name), "read", ts, source, sid)
    elif obj.get("type") == "user":
        texts = [content] if isinstance(content, str) else [
            i.get("text") for i in content or [] if isinstance(i, dict)]
        for text in texts:
            for m in COMMAND_NAME_RE.finditer(text if isinstance(text, str) else ""):
                tally.add(user_name(m.group(1)), "user", ts, source, sid)


def user_name(raw: str) -> str | None:
    name = clean_name(raw)
    return None if name is None or name in BUILTINS else name


# ---------------------------------------------------------------- codex


def scan_codex(root: Path, tally: Tally):
    st = tally.source("codex", present=root.is_dir())
    if not root.is_dir():
        return
    cutoff = tally.since.timestamp()
    for f in sorted(root.rglob("*.jsonl")):
        try:
            if f.stat().st_mtime < cutoff:
                continue
        except OSError:
            continue
        st["files_or_rows"] += 1
        sid = f.stem
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                head = line[:200]
                if '"turn_context"' in head:
                    continue
                is_meta = '"session_meta"' in head
                # session_meta lists every installed skill path; read the id, count nothing.
                if not is_meta and "SKILL.md" not in line and '"user"' not in line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(obj, dict):
                    continue
                payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
                if obj.get("type") == "session_meta":
                    sid = payload.get("id") or sid
                elif obj.get("type") == "response_item":
                    codex_item(payload, parse_ts(obj.get("timestamp")), sid, tally)


def codex_item(payload: dict, ts, sid, tally: Tally):
    ptype = payload.get("type")
    if ptype in CODEX_CALLS:
        blob = json.dumps([payload.get(k) for k in ("arguments", "input", "action")])
        for name in sorted(set(PATH_SKILL_RE.findall(blob.replace("\\/", "/")))):
            tally.add(clean_name(name), "read", ts, "codex", sid)
    elif ptype == "message" and payload.get("role") == "user":
        for item in payload.get("content") or []:
            if isinstance(item, dict) and item.get("type") == "input_text":
                name = lead_name(item.get("text"))
                tally.add(user_name(name) if name else None, "user", ts, "codex", sid)


# ---------------------------------------------------------------- t3


def scan_t3(db: Path, tally: Tally):
    st = tally.source("t3", present=db.is_file())
    if not db.is_file():
        return
    try:
        con = open_ro(db)
    except sqlite3.Error:
        st["present"] = False
        return
    since = tally.since.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        rows = con.execute(
            "SELECT type, payload_json, updated_at, thread_id FROM orchestration_v2_projection_turn_items "
            "WHERE type IN ('dynamic_tool','command_execution') AND updated_at >= ? "
            "AND (payload_json LIKE '%SKILL.md%' OR payload_json LIKE '%\"Skill\"%')", (since,))
        for typ, payload_json, updated, thread in rows:
            st["files_or_rows"] += 1
            try:
                p = json.loads(payload_json)
            except ValueError:
                continue
            ts = parse_ts(p.get("startedAt")) or parse_ts(updated)
            t3_item(typ, p, ts, thread, tally)
    except sqlite3.Error:
        pass
    try:
        rows = con.execute(
            "SELECT created_at, thread_id, json_extract(payload_json, '$.text') "
            "FROM orchestration_v2_projection_messages WHERE role = 'user' AND created_at >= ? "
            "AND (json_extract(payload_json, '$.text') LIKE '/%' "
            "OR json_extract(payload_json, '$.text') LIKE '$%')", (since,))
        for created, thread, text in rows:
            st["files_or_rows"] += 1
            tally.add(user_name(lead_name(text) or ""), "user", parse_ts(created), "t3", thread)
    except sqlite3.Error:
        pass
    con.close()


def t3_item(typ: str, p: dict, ts, thread, tally: Tally):
    inp = p.get("input")
    if typ == "dynamic_tool" and isinstance(inp, dict):
        if p.get("toolName") == "Skill":
            tally.add(clean_name(inp.get("skill")), "model", ts, "t3", thread)
        elif p.get("toolName") == "Read":
            fp = inp.get("file_path")
            if isinstance(fp, str) and fp.endswith("SKILL.md"):
                tally.add(clean_name(PurePosixPath(fp).parent.name), "read", ts, "t3", thread)
    elif typ == "command_execution" and isinstance(inp, str):
        for name in sorted(set(PATH_SKILL_RE.findall(inp))):
            tally.add(clean_name(name), "read", ts, "t3", thread)


# ---------------------------------------------------------------- hermes


def scan_hermes(db: Path, tally: Tally):
    st = tally.source("hermes", present=db.is_file())
    if not db.is_file():
        return
    try:
        con = open_ro(db)
    except sqlite3.Error:
        st["present"] = False
        return
    try:
        rows = con.execute(
            "SELECT session_id, role, content, tool_calls, timestamp FROM messages "
            "WHERE timestamp >= ? AND timestamp < ? AND (tool_calls LIKE '%skill_view%' "
            "OR (role = 'user' AND (content LIKE '/%' OR content LIKE '$%')))",
            (tally.since.timestamp(), tally.until.timestamp()))
        for sid, role, content, tool_calls, stamp in rows:
            st["files_or_rows"] += 1
            ts = parse_ts(stamp)
            if role == "user":
                tally.add(user_name(lead_name(content) or ""), "user", ts, "hermes", sid)
            if tool_calls and "skill_view" in tool_calls:
                hermes_calls(tool_calls, ts, sid, tally)
    except sqlite3.Error:
        pass
    con.close()


def hermes_calls(raw: str, ts, sid, tally: Tally):
    try:
        calls = json.loads(raw)
    except ValueError:
        return
    for call in calls if isinstance(calls, list) else []:
        fn = call.get("function") if isinstance(call, dict) else None
        if not isinstance(fn, dict) or fn.get("name") != "skill_view":
            continue
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except ValueError:
            continue
        name = args.get("name") if isinstance(args, dict) else None
        # Hermes names skills "category/name"; the folder is the last segment.
        tally.add(clean_name(name.rsplit("/", 1)[-1]) if isinstance(name, str) else None,
                  "model", ts, "hermes", sid)


# ---------------------------------------------------------------- report


def normalize_host(raw: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-") or "unknown"


def default_host() -> str:
    if platform.system() == "Darwin":
        try:
            out = subprocess.run(["scutil", "--get", "ComputerName"], capture_output=True,
                                 text=True, timeout=5).stdout.strip()
            if out:
                return normalize_host(out)
        except (OSError, subprocess.SubprocessError):
            pass
    return normalize_host(socket.gethostname())


def collect(args, repo_skills: dict[str, dict]) -> Tally:
    since = datetime.combine(args.since, datetime.min.time(), timezone.utc)
    until = datetime.combine(args.until + timedelta(days=1), datetime.min.time(), timezone.utc)
    tally = Tally(since, until)
    home = Path(args.home).expanduser()
    scan_claude(home / ".claude" / "projects", "claude", tally)
    for arc in args.archive:
        p = Path(arc).expanduser().resolve()
        scan_claude(p, f"archive:{p.parent.name}", tally)
    scan_codex(home / ".codex" / "sessions", tally)
    scan_t3(home / ".t3" / "userdata" / "statev2.sqlite", tally)
    scan_hermes(home / ".hermes" / "state.db", tally)
    drop_unknown_user_events(tally, repo_skills)
    tally.excluded_sessions = drop_audit_sessions(tally)
    return tally


AUDIT_READS = 10


def drop_audit_sessions(tally: Tally) -> int:
    # A session that reads many skill files is reviewing the repo (this skill, a cleanup), not
    # using those skills; counting it would make every skill look used.
    reads: dict[str, set[str]] = {}
    audit = set()
    for (name, kind, _), ev in tally.events.items():
        for sid in ev["sessions"]:
            if kind == "read":
                reads.setdefault(sid, set()).add(name)
            if name == "maintenance":
                audit.add(sid)
    audit |= {sid for sid, names in reads.items() if len(names) >= AUDIT_READS}
    for key in [k for k, ev in tally.events.items() if ev["sessions"] & audit]:
        del tally.events[key]
    return len(audit)


def drop_unknown_user_events(tally: Tally, repo_skills: dict[str, dict]):
    known = set(repo_skills) | {k[0] for k in tally.events if k[1] != "user"}
    for key in [k for k in tally.events if k[1] == "user" and k[0] not in known]:
        del tally.events[key]


def build_report(args, repo_skills: dict[str, dict], tally: Tally) -> dict:
    skills: dict[str, dict] = {}
    for (name, kind, _), ev in tally.events.items():
        s = skills.setdefault(name, {
            "uses": 0, "sessions": set(), "last_used": None, "by_kind": {}, "by_source": {}})
        s["uses"] += 1
        s["sessions"] |= ev["sessions"]
        s["by_kind"][kind] = s["by_kind"].get(kind, 0) + 1
        for src in ev["sources"]:
            s["by_source"][src] = s["by_source"].get(src, 0) + 1
        day = ev["ts"].strftime("%Y-%m-%d")
        s["last_used"] = max(s["last_used"] or day, day)
    out_skills = {}
    for name in sorted(skills):
        s = skills[name]
        out_skills[name] = {
            "uses": s["uses"], "sessions": len(s["sessions"]), "last_used": s["last_used"],
            "by_kind": s["by_kind"], "by_source": s["by_source"],
            "in_repo": name in repo_skills,
            "user_invoked": repo_skills[name]["user_invoked"] if name in repo_skills else None,
        }
    return {
        "host": args.host,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window": {"since": args.since.isoformat(), "until": args.until.isoformat()},
        "sources": tally.sources,
        "excluded_audit_sessions": getattr(tally, "excluded_sessions", 0),
        "skills": out_skills,
        "unused_repo_skills": sorted(n for n in repo_skills if n not in skills),
        "foreign_skills": {n: s["uses"] for n, s in out_skills.items() if not s["in_repo"]},
    }


def by_uses(counts: dict[str, int]) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def render_table(rep: dict) -> str:
    rows = [(n, s) for n, s in rep["skills"].items() if s["in_repo"]]
    rows.sort(key=lambda r: (-r[1]["uses"], r[0]))
    lines = [f"host {rep['host']}  window {rep['window']['since']}..{rep['window']['until']}", "",
             f"{'skill':<34}{'uses':>6}{'sess':>6}  {'last':<11}kinds"]
    for n, s in rows:
        kinds = " ".join(f"{k}={v}" for k, v in sorted(s["by_kind"].items()))
        flag = " (user-invoked)" if s["user_invoked"] else ""
        lines.append(f"{n:<34}{s['uses']:>6}{s['sessions']:>6}  {s['last_used']:<11}{kinds}{flag}")
    lines += ["", f"unused repo skills ({len(rep['unused_repo_skills'])}): "
              + (", ".join(rep["unused_repo_skills"]) or "none")]
    if rep["foreign_skills"]:
        top = by_uses(rep["foreign_skills"])[:FOREIGN_TOP]
        lines.append("foreign (top): " + ", ".join(f"{n}={c}" for n, c in top))
    srcs = []
    for name, st in rep["sources"].items():
        srcs.append(f"{name}: " + (f"{st['events']} events, {st['files_or_rows']} files/rows"
                                   if st["present"] else "absent"))
    lines.append("sources: " + "; ".join(srcs))
    return "\n".join(lines)


def render_drawer(rep: dict, today: date) -> str:
    srcs = [n for n, s in rep["sources"].items() if s["present"] and s["events"]]
    repo_counts = by_uses({n: s["uses"] for n, s in rep["skills"].items() if s["in_repo"]})
    counts = ", ".join(f"{n}={c}" for n, c in repo_counts)
    unused = ", ".join(rep["unused_repo_skills"])
    foreign = [f"{n}={c}" for n, c in by_uses(rep["foreign_skills"])[:FOREIGN_TOP]]
    head = (f"{today.isoformat()} skill-usage {rep['host']} {rep['window']['since']}.."
            f"{rep['window']['until']} — why: counts from {', '.join(srcs) or 'none'}: ")

    def build(n_foreign: int) -> str:
        line = f"{head}{counts}; unused: {unused}"
        if n_foreign:
            line += "; foreign: " + ", ".join(foreign[:n_foreign])
        return line

    n = len(foreign)
    while n and len(build(n)) > DRAWER_LIMIT:
        n -= 1
    line = build(n)
    return line if len(line) <= DRAWER_LIMIT else line[:DRAWER_LIMIT - 1] + "…"


def parse_args(argv=None):
    today = date.today()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--since", type=date.fromisoformat, default=today - timedelta(days=90))
    ap.add_argument("--until", type=date.fromisoformat, default=today)
    ap.add_argument("--repo", default=str(skillmeta.repo_root()))
    ap.add_argument("--home", default="~")
    ap.add_argument("--archive", action="append", default=[])
    ap.add_argument("--format", choices=("json", "table"), default="table")
    ap.add_argument("--drawer", action="store_true")
    ap.add_argument("--host", default=None)
    args = ap.parse_args(argv)
    # Sandboxes fake the machine name, so a drawer keyed on it would split one machine in two.
    if args.drawer and not args.host:
        ap.error("--drawer needs --host: the machine part of your MemPalace identity")
    args.host = normalize_host(args.host) if args.host else default_host()
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    repo_skills = skillmeta.load_repo_skills(Path(args.repo))
    tally = collect(args, repo_skills)
    rep = build_report(args, repo_skills, tally)
    if args.drawer:
        print(render_drawer(rep, date.today()))
    elif args.format == "json":
        print(json.dumps(rep, indent=2))
    else:
        print(render_table(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
