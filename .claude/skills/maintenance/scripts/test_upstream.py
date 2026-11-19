import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import upstream  # noqa: E402


def commit(sha, date="2026-10-05", msg="change\n\nbody"):
    return {"sha": sha, "commit": {"message": msg, "author": {"date": f"{date}T10:00:00Z"}}}


def make_repo(tmp_path, skills, credits=""):
    d = tmp_path / ".claude" / "skills" / "maintenance"
    d.mkdir(parents=True)
    (d / "upstreams.json").write_text(json.dumps({"skills": skills, "removed": {}}))
    (tmp_path / "CREDITS.md").write_text(credits)
    return tmp_path


def fake_gh(routes):
    calls = []

    def gh(endpoint):
        calls.append(endpoint)
        for prefix, value in sorted(routes.items(), key=lambda kv: -len(kv[0])):
            if endpoint.startswith(prefix):
                if isinstance(value, Exception):
                    raise value
                return value
        raise upstream.GhError(f"no route {endpoint}")

    gh.calls = calls
    return gh


ENTRY = {"mode": "vendored", "repo": "o/r", "path": "skills/a", "pin": "abc1234", "imported": "2026-10-01"}


def test_current_behind_and_pin_prefix(monkeypatch):
    commits = [commit("f" * 40), commit("e" * 40, msg="second"), commit("abc1234" + "0" * 33)]
    monkeypatch.setattr(upstream, "gh", fake_gh({"repos/o/r/commits?path=skills/a": commits}))
    behind = upstream.check_skill(ENTRY)
    assert behind["status"] == "behind" and behind["head"] == "fffffff"
    assert [c["sha"] for c in behind["new_commits"]] == ["fffffff", "eeeeeee"]
    assert behind["new_commits"][0] == {"sha": "fffffff", "date": "2026-10-05", "message": "change"}
    assert upstream.check_skill({**ENTRY, "pin": "fffff"})["status"] == "current"
    assert upstream.check_skill({**ENTRY, "pin": "0000000"})["status"] == "pin-missing"


def test_unresolved_pin_missing_and_error(monkeypatch):
    monkeypatch.setattr(upstream, "gh", fake_gh({"repos/": upstream.GhError("boom")}))
    assert upstream.check_skill({**ENTRY, "path": None})["status"] == "unresolved"
    assert upstream.check_skill({**ENTRY, "pin": None})["status"] == "pin-missing"
    r = upstream.check_skill(ENTRY)
    assert r["status"] == "error" and r["error"] == "boom"


def test_run_check_skips_original(monkeypatch):
    monkeypatch.setattr(upstream, "gh", fake_gh({"repos/o/r/commits": [commit("abc1234" + "0" * 33)]}))
    rows = upstream.run_check({"skills": {"a": ENTRY, "b": {"mode": "original"}}})
    assert [(r["skill"], r["status"]) for r in rows] == [("a", "current")]


def tree(*paths):
    return {"tree": [{"path": p, "type": "blob"} for p in paths]}


def bootstrap_routes(extra=None):
    routes = {
        "repos/o/one": {"default_branch": "main"},
        "repos/o/one/git/trees/main": tree("skills/zed/SKILL.md", "README.md"),
        "repos/o/two": {"default_branch": "dev"},
        "repos/o/two/git/trees/dev": tree("a/zed/SKILL.md", "b/zed/SKILL.md", "solo/SKILL.md"),
        "repos/o/solo": {"default_branch": "main"},
        "repos/o/solo/git/trees/main": tree("SKILL.md"),
    }
    routes.update(extra or {})
    return routes


def entry(**kw):
    return {"mode": "adapted", "repo": None, "path": None, "pin": None, "imported": "2026-10-01", **kw}


def test_bootstrap_single_match_with_pin_before_import(tmp_path, monkeypatch):
    repo = make_repo(tmp_path, {"zed": entry(repo="o/one")})
    g = fake_gh(bootstrap_routes({"repos/o/one/commits?path=skills/zed&until=2026-10-01T23:59:59Z&per_page=1":
                                  [commit("1234567" + "0" * 33)]}))
    monkeypatch.setattr(upstream, "gh", g)
    rows = upstream.bootstrap(json.loads((repo / ".claude/skills/maintenance/upstreams.json").read_text()),
                              repo / "CREDITS.md")
    assert rows[0]["status"] == "resolved" and rows[0]["path"] == "skills/zed"
    assert rows[0]["pin"] == "1234567" and rows[0]["pin_guessed"] is False


def test_bootstrap_guesses_pin_after_import(tmp_path, monkeypatch):
    routes = bootstrap_routes({
        "repos/o/one/commits?path=skills/zed&until": [],
        "repos/o/one/commits?path=skills/zed&since": [commit("b" * 40), commit("a" * 40)],
    })
    monkeypatch.setattr(upstream, "gh", fake_gh(routes))
    rows = upstream.bootstrap({"skills": {"zed": entry(repo="o/one")}}, tmp_path / "none.md")
    assert rows[0]["pin"] == "aaaaaaa" and rows[0]["pin_guessed"] is True


def test_bootstrap_multi_match_unresolved(tmp_path, monkeypatch):
    monkeypatch.setattr(upstream, "gh", fake_gh(bootstrap_routes()))
    rows = upstream.bootstrap({"skills": {"zed": entry(repo="o/two")}}, tmp_path / "none.md")
    assert rows[0]["status"] == "unresolved"
    assert {m["path"] for m in rows[0]["matches"]} == {"a/zed", "b/zed"}


def test_bootstrap_zero_match_and_credits_candidates(tmp_path, monkeypatch):
    credits = tmp_path / "CREDITS.md"
    credits.write_text("[x](https://github.com/o/one) and [y](https://github.com/o/two/tree/main/p)")
    assert upstream.credit_repos(credits) == ["o/one", "o/two"]
    monkeypatch.setattr(upstream, "gh", fake_gh(bootstrap_routes()))
    rows = upstream.bootstrap({"skills": {"nothing": entry()}}, credits)
    assert rows[0]["status"] == "unresolved" and rows[0]["matches"] == []


def test_bootstrap_root_skill_and_upstream_name(tmp_path, monkeypatch):
    routes = bootstrap_routes({"repos/o/solo/commits?until": [commit("c" * 40)],
                               "repos/o/one/commits?path=skills/zed": [commit("d" * 40)]})
    monkeypatch.setattr(upstream, "gh", fake_gh(routes))
    data = {"skills": {"solo": entry(repo="o/solo"), "renamed": entry(repo="o/one", upstream_name="zed")}}
    rows = {r["skill"]: r for r in upstream.bootstrap(data, tmp_path / "none.md")}
    assert rows["solo"]["status"] == "resolved" and rows["solo"]["path"] == ""
    assert rows["renamed"]["path"] == "skills/zed"


def test_bootstrap_all_candidates_failing_is_error(tmp_path, monkeypatch):
    monkeypatch.setattr(upstream, "gh", fake_gh({"repos/": upstream.GhError("tls")}))
    rows = upstream.bootstrap({"skills": {"zed": entry(repo="o/one")}}, tmp_path / "none.md")
    assert rows[0]["status"] == "error"


def test_bootstrap_write_only_with_flag(tmp_path, monkeypatch, capsys):
    repo = make_repo(tmp_path, {"zed": entry(repo="o/one")})
    file = repo / ".claude/skills/maintenance/upstreams.json"
    before = file.read_text()
    routes = bootstrap_routes({"repos/o/one/commits?path=skills/zed&until": [commit("1234567" + "0" * 33)]})
    monkeypatch.setattr(upstream, "gh", fake_gh(routes))
    upstream.main(["--repo", str(repo), "--bootstrap"])
    assert file.read_text() == before and "dry run" in capsys.readouterr().out
    upstream.main(["--repo", str(repo), "--bootstrap", "--write"])
    saved = json.loads(file.read_text())["skills"]["zed"]
    assert (saved["repo"], saved["path"], saved["pin"]) == ("o/one", "skills/zed", "1234567")


def test_set_pin(tmp_path, capsys):
    repo = make_repo(tmp_path, {"a": dict(ENTRY)})
    assert upstream.main(["--repo", str(repo), "--set-pin", "a", "deadbee"]) == 0
    saved = json.loads((repo / ".claude/skills/maintenance/upstreams.json").read_text())["skills"]["a"]
    assert saved["pin"] == "deadbee" and saved["synced"]
    assert upstream.main(["--repo", str(repo), "--set-pin", "missing", "deadbee"]) == 1


def test_bootstrap_rejects_fallback_match_that_postdates_import(tmp_path, monkeypatch):
    routes = bootstrap_routes({
        "repos/o/one/commits?path=skills/zed&until": [],
        "repos/o/one/commits?path=skills/zed&since": [commit("a" * 40)],
    })
    monkeypatch.setattr(upstream, "gh", fake_gh(routes))
    credits = tmp_path / "CREDITS.md"
    credits.write_text("- [o/one](https://github.com/o/one)\n")
    rows = upstream.bootstrap({"skills": {"zed": entry(repo=None)}}, credits)
    assert rows[0]["status"] == "unresolved" and rows[0]["pin"] is None


def test_pin_off_path_compares_by_date(monkeypatch):
    commits = [commit("c" * 40, "2026-10-09"), commit("b" * 40, "2026-09-01")]
    routes = {"repos/o/r/commits?path=skills/x&per_page=100": commits,
              "repos/o/r/commits/d16ebe6": commit("d16ebe6" + "0" * 33, "2026-10-01")}
    monkeypatch.setattr(upstream, "gh", fake_gh(routes))
    r = upstream.check_skill({"repo": "o/r", "path": "skills/x", "pin": "d16ebe6"})
    assert r["status"] == "behind" and [c["sha"] for c in r["new_commits"]] == ["ccccccc"]
