import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit  # noqa: E402

TODAY = date(2026, 11, 19)


def skill(repo: Path, rel: str, name: str, desc="Do a thing. Use when testing.", extra_fm="", body=""):
    d = repo / rel
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n{extra_fm}---\n\n{body}\n")


@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".claude" / "skills" / "maintenance").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "maintenance" / "upstreams.json").write_text(
        json.dumps({"skills": {}, "removed": {"old-skill": "gone"}}))
    (tmp_path / "meta").mkdir()
    (tmp_path / "meta" / "README.md").write_text("| [`listed`](listed/SKILL.md) | x |\n")
    skill(tmp_path, "meta/listed", "listed")
    return tmp_path


def checks(repo, known=(), name=None):
    found = audit.run(repo, set(known), TODAY)
    return [f for f in found if name is None or f["skill"] == name]


def has(found, check, needle=""):
    return [f for f in found if f["check"] == check and needle in f["detail"]]


def test_clean_skill_has_no_findings(repo):
    assert checks(repo, name="listed") == []


def test_removed_ref(repo):
    skill(repo, "meta/a", "a", body="Run `old-skill` first.\nsee /old-skill and the old-skill skill.")
    found = checks(repo, name="a")
    assert len(has(found, "removed-ref", "old-skill")) == 2  # one per line
    assert not has(found, "unknown-ref")  # removed names are reported once, not again


def test_unknown_ref_patterns_and_exclusions(repo):
    body = ("Use /ghost now.\n`phantom` skill is here.\nthe `spectral-thing` skill.\n"
            "see skills/wraith/ for more\nuse /listed and /etc/hosts and /a.b and /tmp\n"
            "```\n/fenced-ghost\n```\nthe user-invoked skill and /known-host")
    skill(repo, "meta/a", "a", body=body)
    found = has(checks(repo, known={"known-host"}, name="a"), "unknown-ref")
    details = " ".join(f["detail"] for f in found)
    for expect in ("/ghost", "`phantom` skill", "spectral-thing", "skills/wraith/"):
        assert expect in details
    for refused in ("fenced-ghost", "/listed", "/etc", "/tmp", "a.b", "user-invoked", "known-host"):
        assert refused not in details


def test_no_trigger_only_for_model_invoked(repo):
    skill(repo, "meta/a", "a", desc="Does things.")
    skill(repo, "meta/b", "b", desc="Does things.", extra_fm="disable-model-invocation: true\n")
    found = checks(repo)
    assert [f["skill"] for f in has(found, "no-trigger")] == ["a"]


def test_long_description_with_folded_value(repo):
    d = repo / "meta" / "a"
    d.mkdir()
    long = "word " * 220
    (d / "SKILL.md").write_text(f"---\nname: a\ndescription: >\n  Use when x. {long}\n  tail\n---\nbody\n")
    found = has(checks(repo, name="a"), "long-description")
    assert found and found[0]["line"] == 3 and "chars" in found[0]["detail"]
    assert not has(checks(repo, name="a"), "no-trigger")


def test_long_skill(repo):
    skill(repo, "meta/a", "a", body="line\n" * 520)
    assert has(checks(repo, name="a"), "long-skill")


def test_stale_source(repo):
    skill(repo, "meta/a", "a", body="Source fetched 2026-01-02.\nOther fetched 2026-10.\nOld fetched 2025-05")
    found = has(checks(repo, name="a"), "stale-source")
    assert [f["detail"].split()[1] for f in found] == ["2026-01-02", "2025-05"]


def test_model_id(repo):
    skill(repo, "meta/a", "a", body="Use claude-opus-4-5 or gpt-5.1-codex, gemini-3-pro, o3-mini.")
    found = [f["detail"] for f in has(checks(repo, name="a"), "model-id")]
    assert len(found) == 4 and any("claude-opus-4-5" in d for d in found)


def test_host_cli(repo):
    skill(repo, "meta/a", "a", body="Run orca then t3_code, cursor-agent, Hermes.")
    found = has(checks(repo, name="a"), "host-cli")
    assert len(found) == 1 and found[0]["detail"] == "mentions cursor-agent, hermes, orca, t3_code"


def test_no_readme_row_and_prefix_trap(repo):
    skill(repo, "meta/council", "council")
    skill(repo, "meta/research-council", "research-council")
    (repo / "meta" / "README.md").write_text("| [`rc`](research-council/SKILL.md) | x |\n")
    found = has(checks(repo), "no-readme-row")
    assert {f["skill"] for f in found} == {"council", "listed"}


def test_cli_json_and_known_file(repo, tmp_path, capsys):
    skill(repo, "meta/a", "a", body="Use /host-only now.")
    known = tmp_path / "known.txt"
    known.write_text("host-only\n/other\n")
    assert audit.main(["--repo", str(repo), "--known", str(known), "--format", "json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert not [f for f in out if f["check"] == "unknown-ref"]
    assert out and set(out[0]) == {"skill", "file", "line", "check", "severity", "detail"}


def test_trigger_variants(repo):
    for i, w in enumerate(("before", "whenever", "after", "to")):
        skill(repo, f"meta/t{i}", f"t{i}", desc=f"Does things. USE {w} x.")
    assert not has(checks(repo), "no-trigger")


def test_slash_ignores_closing_backtick(repo):
    body = ("see `.env`/secrets and `src`/build here\n"
            "run **`/vet`** or (`/zzz`) or `/accordion`x and /ghost\n")
    skill(repo, "meta/a", "a", body=body)
    details = " ".join(f["detail"] for f in has(checks(repo, name="a"), "unknown-ref"))
    for refused in ("secrets", "build"):
        assert refused not in details
    for expect in ("/vet", "/zzz", "/accordion", "/ghost"):
        assert expect in details


def test_bare_skill_prose_not_flagged(repo):
    skill(repo, "meta/a", "a", body="a fix-it skill and the mobile-native skill.")
    assert not has(checks(repo, name="a"), "unknown-ref")


def test_builtin_host_commands_need_no_known_file(repo):
    skill(repo, "meta/a", "a", body="/sandbox /codex /simplify /security-review /run /plugins")
    details = " ".join(f["detail"] for f in has(checks(repo, name="a"), "unknown-ref"))
    assert "/codex" in details
    for ok in ("sandbox", "simplify", "security-review", "/run", "plugins"):
        assert ok not in details.replace("/codex", "")


def test_severity_and_table_collapses_info(repo, capsys):
    skill(repo, "meta/a", "a", desc="Does things.", body="Run orca now.")
    found = checks(repo, name="a")
    sev = {f["check"]: f["severity"] for f in found}
    assert sev["no-trigger"] == "warn" and sev["host-cli"] == "info" and sev["no-readme-row"] == "info"
    table = audit.render_table(found)
    assert table.index("no-trigger") < table.index("info host-cli")
    assert "info host-cli: 1" in table and "meta/a/SKILL.md:" not in table.split("info host-cli")[1]
    verbose = audit.render_table(found, verbose=True)
    assert "orca" in verbose


def test_no_codex_policy(repo):
    off = "disable-model-invocation: true\n"
    skill(repo, "meta/a", "a", desc="Does things.", extra_fm=off)
    skill(repo, "meta/b", "b", desc="Does things.", extra_fm=off)
    skill(repo, "meta/c", "c", desc="Does things.", extra_fm=off)
    (repo / "meta/b/agents").mkdir()
    (repo / "meta/b/agents/openai.yaml").write_text("policy:\n  allow_implicit_invocation: false\n")
    (repo / "meta/c/agents").mkdir()
    (repo / "meta/c/agents/openai.yaml").write_text("policy:\n  allow_implicit_invocation: true\n")
    found = has(checks(repo), "no-codex-policy")
    assert sorted(f["skill"] for f in found) == ["a", "c"]
    assert found[0]["severity"] == "warn"


def test_trigger_on_user_invoked(repo):
    skill(repo, "meta/a", "a", desc="Does things. Use when asked.", extra_fm="disable-model-invocation: true\n")
    found = has(checks(repo, name="a"), "trigger-on-user-invoked")
    assert len(found) == 1 and found[0]["severity"] == "info"
    assert not has(checks(repo, name="listed"), "trigger-on-user-invoked")


def test_npx_latest(repo):
    skill(repo, "meta/a", "a", body="npx foo@latest run\nnpx -y @scope/bar@latest\nnpx baz@1.2.3")
    found = has(checks(repo, name="a"), "npx-latest")
    assert len(found) == 2 and found[0]["severity"] == "warn"
