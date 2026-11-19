import json
import os
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import usage  # noqa: E402

T0 = "2026-10-10T12:00:10Z"
T0_NEAR = "2026-10-10T12:00:40Z"  # same minute as T0


def write_skill(repo: Path, name: str, extra: str = ""):
    d = repo / "software" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Use when testing.\n{extra}---\n\nbody\n")


def jl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def claude_rows():
    def tool(name, inp, ts=T0):
        return {"type": "assistant", "timestamp": ts, "sessionId": "s1",
                "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]}}

    def user(text, ts=T0):
        return {"type": "user", "timestamp": ts, "sessionId": "s1", "message": {"content": text}}

    return [
        tool("Skill", {"skill": "/council"}),
        tool("Read", {"file_path": "/x/skills/foo/SKILL.md"}, "2026-10-11T08:00:00Z"),
        tool("Skill", {"skill": "codex:rescue"}),
        user("<command-name>/foo</command-name>", "2026-10-12T08:00:00Z"),
        user("<command-name>/tmp/some/path</command-name>"),
        user("<command-name>/compact</command-name>"),
        user([{"type": "text", "text": "<command-name>/nothing-known</command-name>"}]),
        tool("Skill", {"skill": "council"}, "2026-08-01T00:00:00Z"),  # outside window
    ]


@pytest.fixture
def world(tmp_path):
    repo = tmp_path / "repo"
    for n in ("foo", "bar", "council", "idle"):
        write_skill(repo, n, "disable-model-invocation: true\n" if n == "bar" else "")
    home = tmp_path / "home"
    jl(home / ".claude" / "projects" / "p" / "s1.jsonl", claude_rows())
    jl(home / ".claude" / "projects" / "p" / "subagents" / "a.jsonl", [
        {"type": "assistant", "timestamp": "2026-10-13T00:00:00Z", "sessionId": "s9",
         "message": {"content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "foo"}}]}}])
    jl(home / ".codex" / "sessions" / "2026" / "r.jsonl", [
        {"timestamp": T0, "type": "session_meta", "payload": {
            "id": "cx1", "instructions": "skills: /h/.codex/skills/bar/SKILL.md /h/.codex/skills/foo/SKILL.md"}},
        {"timestamp": T0, "type": "turn_context", "payload": {"x": "/h/skills/bar/SKILL.md"}},
        {"timestamp": "2026-10-14T01:00:00Z", "type": "response_item", "payload": {
            "type": "function_call", "arguments": json.dumps({"cmd": "cat /h/.codex/skills/diag-x/SKILL.md"})}},
        {"timestamp": "2026-10-14T02:00:00Z", "type": "response_item", "payload": {
            "type": "message", "role": "user", "content": [{"type": "input_text", "text": "  $foo please"}]}},
        {"timestamp": "2026-10-14T03:00:00Z", "type": "response_item", "payload": {
            "type": "message", "role": "user", "content": [{"type": "input_text", "text": "/etc/hosts look"}]}},
    ])
    t3 = home / ".t3" / "userdata" / "statev2.sqlite"
    t3.parent.mkdir(parents=True)
    con = sqlite3.connect(t3)
    con.execute("CREATE TABLE orchestration_v2_projection_turn_items (payload_json TEXT, type TEXT, updated_at TEXT, thread_id TEXT)")
    con.execute("CREATE TABLE orchestration_v2_projection_messages (role TEXT, created_at TEXT, payload_json TEXT, thread_id TEXT)")
    skill_call = {"toolName": "Skill", "input": {"skill": "council"}, "startedAt": T0_NEAR}
    cmd = {"input": "cat /h/skills/idle/SKILL.md", "startedAt": "2026-10-15T00:00:00.000Z"}
    con.execute("INSERT INTO orchestration_v2_projection_turn_items VALUES (?,?,?,?)",
                (json.dumps(skill_call), "dynamic_tool", "2026-10-10T12:01:00Z", "th1"))
    con.execute("INSERT INTO orchestration_v2_projection_turn_items VALUES (?,?,?,?)",
                (json.dumps(cmd), "command_execution", "2026-10-15T00:00:05Z", "th2"))
    con.execute("INSERT INTO orchestration_v2_projection_messages VALUES (?,?,?,?)",
                ("user", "2026-10-16T00:00:00Z", json.dumps({"text": "/foo now"}), "th3"))
    con.commit()
    con.close()
    hermes = home / ".hermes" / "state.db"
    hermes.parent.mkdir(parents=True)
    con = sqlite3.connect(hermes)
    con.execute("CREATE TABLE messages (session_id TEXT, role TEXT, content TEXT, tool_calls TEXT, timestamp REAL)")
    calls = [{"function": {"name": "skill_view", "arguments": json.dumps({"name": "cat/foo"})}}]
    con.execute("INSERT INTO messages VALUES (?,?,?,?,?)", ("h1", "assistant", None, json.dumps(calls), 1792152000.0))
    con.commit()
    con.close()
    return {"repo": repo, "home": home, "tmp": tmp_path}


def run(world, *extra, fmt="json"):
    argv = ["--repo", str(world["repo"]), "--home", str(world["home"]), "--since", "2026-10-01",
            "--until", "2026-10-31", "--host", "Test Box", "--format", fmt, *extra]
    return usage.parse_args(argv)


def report(world, *extra):
    args = run(world, *extra)
    repo_skills = usage.skillmeta.load_repo_skills(Path(args.repo))
    return usage.build_report(args, repo_skills, usage.collect(args, repo_skills))


def test_session_meta_and_turn_context_not_counted(world):
    rep = report(world)
    assert "bar" not in rep["skills"]
    assert "bar" in rep["unused_repo_skills"]
    assert rep["skills"]["foo"]["by_source"].get("codex") == 1  # only the $foo user message


def test_dedupe_across_t3_and_claude(world):
    c = report(world)["skills"]["council"]
    assert c["uses"] == 1 and c["by_kind"] == {"model": 1}
    assert set(c["by_source"]) == {"claude", "t3"}
    assert c["sessions"] == 1  # one conversation seen by two sources counts once


def test_user_path_and_unknown_not_counted(world):
    skills = report(world)["skills"]
    for bad in ("tmp", "tmp/some/path", "etc", "compact", "nothing-known"):
        assert bad not in skills
    assert skills["foo"]["by_kind"]["user"] == 3  # claude, codex, t3


def test_read_and_foreign_and_hermes(world):
    rep = report(world)
    assert rep["skills"]["idle"]["by_kind"] == {"read": 1}
    assert rep["foreign_skills"] == {"codex:rescue": 1, "diag-x": 1}
    assert rep["skills"]["foo"]["by_source"]["hermes"] == 1
    assert rep["unused_repo_skills"] == ["bar"]
    assert rep["skills"]["foo"]["user_invoked"] is False
    assert rep["skills"]["codex:rescue"]["user_invoked"] is None


def test_window_excludes_old_events(world):
    assert report(world)["skills"]["council"]["last_used"] == "2026-10-10"


def test_missing_sources_marked_absent(world):
    rep = report(world, "--archive", str(world["tmp"] / "nope" / "claude-projects"))
    assert rep["sources"]["archive:nope"]["present"] is False


def test_archive_source_name(world):
    arc = world["tmp"] / "incoming" / "cleverse-mbp" / "claude-projects"
    jl(arc / "p" / "x.jsonl", [
        {"type": "assistant", "timestamp": "2026-10-20T00:00:00Z", "sessionId": "z",
         "message": {"content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "idle"}}]}}])
    rep = report(world, "--archive", str(arc))
    assert rep["skills"]["idle"]["by_source"]["archive:cleverse-mbp"] == 1
    assert rep["sources"]["archive:cleverse-mbp"]["events"] == 1


def test_read_only_open(world):
    t3 = world["home"] / ".t3" / "userdata" / "statev2.sqlite"
    hermes = world["home"] / ".hermes" / "state.db"
    before = [os.stat(p).st_mtime_ns for p in (t3, hermes)]
    report(world)
    assert [os.stat(p).st_mtime_ns for p in (t3, hermes)] == before
    with pytest.raises(sqlite3.OperationalError):
        usage.open_ro(t3).execute("CREATE TABLE nope (a)")


def test_drawer_format(world):
    args = run(world, "--drawer")
    repo_skills = usage.skillmeta.load_repo_skills(Path(args.repo))
    rep = usage.build_report(args, repo_skills, usage.collect(args, repo_skills))
    line = usage.render_drawer(rep, date(2026, 11, 1))
    assert "\n" not in line and len(line) <= 3000
    assert re.match(r"^2026-11-01 skill-usage test-box 2026-10-01\.\.2026-10-31 — why: counts from "
                    r"claude, codex, t3, hermes: foo=\d+, council=1, idle=1; unused: bar; foreign: ", line)
    assert "codex:rescue=1" in line


def test_drawer_truncates_foreign_first(world):
    rep = report(world)
    rep["foreign_skills"] = {f"foreign-{i:03d}": 1 for i in range(15)}
    rep["unused_repo_skills"] = [f"unused-{i:03d}" for i in range(220)]
    line = usage.render_drawer(rep, date(2026, 11, 1))
    assert len(line) <= 3000 and "unused-219" in line and "foreign-014" not in line


def test_table_output(world, capsys):
    usage.main(["--repo", str(world["repo"]), "--home", str(world["home"]), "--since", "2026-10-01",
                "--until", "2026-10-31", "--host", "x"])
    out = capsys.readouterr().out
    assert "unused repo skills (1): bar" in out and "sources:" in out and "foo" in out


def test_drawer_requires_host(world):
    argv = ["--repo", str(world["repo"]), "--home", str(world["home"]), "--drawer"]
    with pytest.raises(SystemExit):
        usage.parse_args(argv)


def test_audit_sessions_are_dropped():
    tally = usage.Tally(datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 11, 1, tzinfo=timezone.utc))
    t0 = datetime(2026, 10, 5, tzinfo=timezone.utc)
    for i in range(usage.AUDIT_READS):
        tally.add(f"skill-{i}", "read", t0 + timedelta(minutes=i), "claude", "audit-session")
    tally.add("git-commit", "model", t0, "claude", "real-session")
    tally.add("council", "model", t0, "claude", "run-session")
    tally.add("maintenance", "read", t0 + timedelta(minutes=1), "claude", "run-session")
    assert usage.drop_audit_sessions(tally) == 2
    assert {k[0] for k in tally.events} == {"git-commit"}
