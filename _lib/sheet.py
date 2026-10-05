"""Report sheet: schema, required panels per kind, derived facts, and panel HTML.

A sheet is validated JSON in, one glanceable page body out. The builder derives every count,
stamp, and figure from validated rows, so no number on the page is hand-typed by an agent.
Every string field has one class (label, instruction, prose, literal); the voice lint runs on
all but literal. Class names emitted here are the contract with sheet.css and sheet.js.

Stdlib only, Python 3.10 or newer.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import figures
import gitfacts
import pagelib
import svg
import voice

HERE = Path(__file__).resolve().parent

KINDS = ("plan", "execute", "vet", "finish", "research", "grill", "session")
SPANS = (3, 4, 6, 8, 12)
DEFAULT_SPAN = {"asks": 4, "checks": 8, "files": 8, "figure": 12, "decisions": 12, "tasks": 12,
                "findings": 12, "claims": 8, "commands": 4, "matrix": 6, "table": 8}
MIN_SPAN = {"asks": 4, "commands": 4, "matrix": 4, "checks": 6, "files": 6, "claims": 6, "table": 6,
            "findings": 8, "decisions": 8, "tasks": 8, "figure": 8}
ENUMS = {
    "status": ("done", "failed", "blocked", "skipped", "todo"),
    "sev": ("P0", "P1", "P2", "P3"),
    "default": ("fix", "skip"),
    "outcome": ("fixed", "skipped", "rejected", "open"),
    "result": ("verified", "corrected", "unverified"),
    "level": ("low", "med", "high"),
}
# field -> (class, required). Classes: label, instruction, literal, exit (int or null), bool,
# litlist (list of literals), litlist1 (non-empty), enum:<name>.
ROW_FIELDS = {
    "asks": {"ask": ("label", True), "why": ("instruction", False)},
    "checks": {"cmd": ("literal", True), "cwd": ("literal", True), "exit": ("exit", True),
               "result": ("label", False)},
    "decisions": {"id": ("literal", False), "decision": ("label", True), "chosen": ("label", True),
                  "rejected": ("label", False), "why": ("instruction", True), "parent": ("literal", False)},
    "tasks": {"id": ("literal", True), "name": ("label", True), "status": ("enum:status", True),
              "after": ("litlist", False), "commit": ("literal", False), "exit": ("exit", False)},
    "findings": {"id": ("literal", True), "sev": ("enum:sev", True), "claim": ("instruction", True),
                 "where": ("literal", False), "foundBy": ("litlist1", True),
                 "dispute": ("instruction", False), "default": ("enum:default", True),
                 "outcome": ("enum:outcome", False)},
    "claims": {"id": ("literal", True), "claim": ("instruction", True), "source": ("literal", True),
               "result": ("enum:result", True), "note": ("instruction", False)},
    "commands": {"cmd": ("literal", True), "does": ("label", True), "danger": ("bool", False)},
    "matrix": {"id": ("literal", True), "label": ("label", True), "likelihood": ("enum:level", True),
               "impact": ("enum:level", True)},
}
PANEL_KEYS = {
    "figure": {"svg", "mermaid", "caption", "steps"},
    "table": {"columns", "rows"},
    "files": set(),
}
REQUIRED = {
    "plan": [("needs you", "asks"), ("hardening", "table"), ("tasks", "tasks"), ("decisions", "decisions")],
    "execute": [("needs you", "asks"), ("checks", "checks"), ("files", "files"), ("tasks", "tasks"),
                ("review", "findings"), ("decisions", "decisions")],
    "vet": [("needs you", "asks"), ("findings", "findings")],
    "finish": [("needs you", "asks"), ("next move", "commands"), ("checks", "checks"),
               ("diff", "files"), ("review", "findings")],
    "research": [("needs you", "asks"), ("claims", "claims")],
    "grill": [("needs you", "asks"), ("decisions", "decisions"), ("docs changed", "files")],
    "session": [("needs you", "asks")],
}
READY_STAMP = {"plan": "READY", "finish": "READY", "research": "ANSWERED"}
CODE_RE = re.compile(r"`([^`]*)`")
KEY_LANES = (("add", "added, pass, done"), ("del", "removed, fail, blocked"), ("amb", "needs you"),
             ("blu", "changed"), ("gry", "not run, skipped"))


def _label(text: str) -> str:
    return CODE_RE.sub(lambda m: f"<code>{m.group(1)}</code>", pagelib.esc(text))


class _Ctx:
    """Carries the words counter and the first reviewer-order table through one check."""

    def __init__(self) -> None:
        self.words = 0

    def text(self, where: str, value, cls: str, max_sentences: int | None = None) -> str:
        if not isinstance(value, str) or not value.strip():
            pagelib.fail(f"{where}: must be non-empty text")
        voice.check_field(where, value, cls, max_sentences)
        self.words += len(voice.plain(value, cls).split())
        return value


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _check_value(ctx: _Ctx, where: str, name: str, value, cls: str) -> None:
    here = f"{where} {name}"
    if cls in ("label", "instruction"):
        ctx.text(here, value, cls)
    elif cls == "literal":
        if not isinstance(value, str) or not value:
            pagelib.fail(f"{here}: must be a non-empty string")
    elif cls == "exit":
        if value is not None and not _is_int(value):
            pagelib.fail(f"{here}: must be a whole number or null")
    elif cls == "bool":
        if not isinstance(value, bool):
            pagelib.fail(f"{here}: must be true or false")
    elif cls in ("litlist", "litlist1"):
        ok = isinstance(value, list) and all(isinstance(x, str) and x for x in value)
        if not ok or (cls == "litlist1" and not value):
            pagelib.fail(f"{here}: must be a {'non-empty ' if cls == 'litlist1' else ''}list of strings")
    elif cls.startswith("enum:"):
        allowed = ENUMS[cls[5:]]
        if value not in allowed:
            pagelib.fail(f"{here}: must be one of {', '.join(allowed)}")


def _check_row(ctx: _Ctx, where: str, row, fields: dict) -> dict:
    if not isinstance(row, dict):
        pagelib.fail(f"{where}: row must be an object")
    for name in row:
        if name not in fields:
            pagelib.fail(f"{where}: unknown field {name!r}")
    for name, (cls, required) in fields.items():
        if name not in row:
            if required:
                pagelib.fail(f"{where}: missing {name}")
            continue
        _check_value(ctx, where, name, row[name], cls)
    return dict(row)


def _resolve_tree(tree, spec_dir: Path | None) -> tuple[Path, str, str]:
    if not isinstance(tree, dict) or not all(isinstance(tree.get(k), str) and tree[k] for k in ("repo", "base", "head")):
        pagelib.fail("tree: needs repo, base, and head")
    root = Path(tree["repo"])
    if not root.is_absolute():
        root = (spec_dir or Path.cwd()) / root
    if not root.is_dir():
        pagelib.fail(f"tree: repo is not a folder: {root}")
    return root, tree["base"], tree["head"]


def _check_figure(ctx: _Ctx, where: str, p: dict, letter: str) -> dict:
    has_svg, has_mm = "svg" in p, "mermaid" in p
    if has_svg == has_mm:
        pagelib.fail(f"{where}: needs exactly one of svg or mermaid")
    out = {"caption": ctx.text(f"{where} caption", p.get("caption"), "label"), "steps": []}
    steps = p.get("steps")
    if has_mm:
        if steps:
            pagelib.fail(f"{where}: steps need svg")
        if not isinstance(p["mermaid"], str) or not p["mermaid"].strip():
            pagelib.fail(f"{where} mermaid: must be non-empty text")
        out["mermaid"] = p["mermaid"]
        return out
    if not isinstance(p["svg"], str):
        pagelib.fail(f"{where} svg: must be text")
    out["svg"] = svg.validate_figure(p["svg"], where, f"p{letter.lower()}-")
    if steps is not None and not isinstance(steps, list):
        pagelib.fail(f"{where} steps: must be a list")
    for i, st in enumerate(steps or []):
        if not isinstance(st, dict) or set(st) != {"n", "say"}:
            pagelib.fail(f"{where} steps[{i}]: needs n and say")
        if st["n"] != i + 1 or not _is_int(st["n"]):
            pagelib.fail(f"{where} steps[{i}]: steps must number 1..N in order")
        ctx.text(f"{where} steps[{i}] say", st["say"], "instruction")
        out["steps"].append({"n": st["n"], "say": st["say"]})
    used = svg.step_ids(out["svg"])
    for n in sorted(used):
        if n > len(out["steps"]) or n < 1:
            pagelib.fail(f"{where}: data-s {n} has no step")
    for st in out["steps"]:
        if st["n"] not in used:
            pagelib.fail(f"{where}: step {st['n']} is not used by any data-s")
    return out


def _check_table(ctx: _Ctx, where: str, p: dict) -> dict:
    cols, rows = p.get("columns"), p.get("rows")
    if not isinstance(cols, list) or not 1 <= len(cols) <= 5:
        pagelib.fail(f"{where}: columns must be a list of 1 to 5")
    for i, c in enumerate(cols):
        ctx.text(f"{where} columns[{i}]", c, "label")
        if len(voice.plain(c, "label").split()) > 3:
            pagelib.fail(f"{where} columns[{i}]: keep to 3 words")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 8:
        pagelib.fail(f"{where}: rows must be a list of 1 to 8")
    for r, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != len(cols):
            pagelib.fail(f"{where} rows[{r}]: needs {len(cols)} cells")
        for c, cell in enumerate(row):
            ctx.text(f"{where} rows[{r}] c{c}", cell, "label")
    return {"columns": list(cols), "rows": [list(r) for r in rows]}


def _normalize_panel(ctx: _Ctx, p, letter: str, tree) -> dict:
    where = f"panel {letter}"
    if not isinstance(p, dict):
        pagelib.fail(f"{where}: must be an object")
    typ = p.get("type")
    if typ not in DEFAULT_SPAN:
        pagelib.fail(f"{where}: unknown type {typ!r}")
    allowed = {"role", "type", "span"} | PANEL_KEYS.get(typ, {"rows"})
    for k in p:
        if k not in allowed:
            pagelib.fail(f"{where} {typ}: unknown field {k!r}")
    role = ctx.text(f"{where} role", p.get("role"), "label")
    if len(voice.plain(role, "label").split()) > 4:
        pagelib.fail(f"{where} role: keep to 4 words")
    span = p.get("span", DEFAULT_SPAN[typ])
    if span not in SPANS or isinstance(span, bool):
        pagelib.fail(f"{where} span: must be one of {', '.join(map(str, SPANS))}")
    out = {"letter": letter, "role": role, "type": typ, "span": span, "fixed": "span" in p}
    where = f"{where} {typ}"

    if typ == "figure":
        out.update(_check_figure(ctx, where, p, letter))
    elif typ == "table":
        out.update(_check_table(ctx, where, p))
    elif typ == "files":
        if p.get("rows"):
            pagelib.fail(f"{where}: files panel takes no rows; the builder reads them from git")
        if tree is None:
            pagelib.fail(f"{where}: files panel needs tree")
        root, base, head = tree
        out["rows"] = [{"status": r.status, "path": r.path, "added": r.added, "removed": r.removed}
                       for r in gitfacts.diff_rows(root, base, head)]
    else:
        rows = p.get("rows", [])
        if not isinstance(rows, list):
            pagelib.fail(f"{where}: rows must be a list")
        out["rows"] = [_check_row(ctx, f"{where}[{i}]", r, ROW_FIELDS[typ]) for i, r in enumerate(rows)]
        _check_rows_extra(where, typ, out["rows"], tree)
    return out


def _check_rows_extra(where: str, typ: str, rows: list[dict], tree) -> None:
    if typ == "findings":
        for i, r in enumerate(rows):
            if "where" in r:
                if tree is None:
                    pagelib.fail(f"{where}[{i}]: where needs tree")
                r["whereOk"] = gitfacts.line_exists(tree[0], tree[2], r["where"])
    elif typ == "tasks":
        ids = [r["id"] for r in rows]
        if len(set(ids)) != len(ids):
            pagelib.fail(f"{where}: task ids must be unique")
        for i, r in enumerate(rows):
            if "commit" in r:
                if tree is None:
                    pagelib.fail(f"{where}[{i}]: commit needs tree")
                if not gitfacts.commit_exists(tree[0], r["commit"]):
                    pagelib.fail(f"{where}[{i}]: commit {r['commit']} not found in the repo")
        figures.waves(rows)
    elif typ == "decisions":
        if any("parent" in r for r in rows) and any("id" not in r for r in rows):
            pagelib.fail(f"{where}: id is required on every row when any row has a parent")
        figures.decision_tree(rows)
    elif typ == "matrix":
        figures.heat_matrix(rows)


def pack_rows(panels: list[dict]) -> None:
    """Resize spans in place so every 12-column row is full, keeping panel order. A span the agent
    set is fixed; otherwise a panel may shrink to its type minimum or the row's last panel widen."""
    left, row = 12, []
    for p in panels:
        lo = p["span"] if p.get("fixed") else min(p["span"], MIN_SPAN[p["type"]])
        if left == 0:
            left, row = 12, []
        if p["span"] <= left:
            pass
        elif lo <= left:
            p["span"] = left
        else:
            row[-1]["span"] += left
            left, row = 12, []
        left -= p["span"]
        row.append(p)
    if row and left:
        row[-1]["span"] += left


def check_sheet(spec: dict, *, kind: str, title: str, spec_dir: Path | None = None,
                auto_panels: list[dict] | None = None) -> dict:
    """Validate the sheet fields of `spec`, run the voice lint on every label, instruction, and
    prose field, check git facts, and return a normalized sheet. `auto_panels` are builder-made
    panels inserted after panel A. A relative `tree.repo` resolves against `spec_dir`."""
    if kind not in KINDS:
        pagelib.fail(f"kind: {kind!r} is not one of {', '.join(KINDS)}")
    ctx = _Ctx()
    ctx.text("title", title, "label")
    state = ctx.text("state", spec.get("state"), "prose", 2)
    blocked = spec.get("blocked", False)
    if not isinstance(blocked, bool):
        pagelib.fail("blocked: must be true or false")

    facts = spec.get("facts", [])
    if not isinstance(facts, list) or len(facts) > 6:
        pagelib.fail("facts: must be a list of at most 6")
    norm_facts = []
    for i, f in enumerate(facts):
        if not isinstance(f, dict) or set(f) != {"k", "v"}:
            pagelib.fail(f"facts[{i}]: needs k and v")
        ctx.text(f"facts[{i}] k", f["k"], "label")
        if len(f["k"].split()) > 3:
            pagelib.fail(f"facts[{i}] k: keep to 3 words")
        if not isinstance(f["v"], str):
            pagelib.fail(f"facts[{i}] v: must be a string")
        norm_facts.append({"k": f["k"], "v": f["v"]})

    tree = _resolve_tree(spec["tree"], spec_dir) if spec.get("tree") is not None else None

    panels = spec.get("panels")
    if not isinstance(panels, list) or not 1 <= len(panels) <= 8:
        pagelib.fail("panels: must be a list of 1 to 8")
    first = panels[0]
    if not (isinstance(first, dict) and first.get("role") == "needs you" and first.get("type") == "asks"):
        pagelib.fail("panel A must be needs you: asks")
    merged = [panels[0], *(auto_panels or []), *panels[1:]]
    if len(merged) > 8:
        pagelib.fail("panels: at most 8 including builder-made panels")

    normalized = [_normalize_panel(ctx, p, chr(ord("A") + i), tree) for i, p in enumerate(merged)]
    pack_rows(normalized)
    roles = [p["role"] for p in normalized]
    for r in roles:
        if roles.count(r) > 1:
            pagelib.fail(f"panels: duplicate role {r!r}")
    for role, typ in REQUIRED[kind]:
        found = next((p for p in normalized if p["role"] == role), None)
        if found is None:
            pagelib.fail(f"{kind} sheet needs a {role} panel ({typ})")
        if found["type"] != typ:
            pagelib.fail(f"{kind} sheet: panel {found['letter']} {role} must be type {typ}, not {found['type']}")

    asks = normalized[0]["rows"]
    if blocked:
        stamp, tone = "BLOCKED", "bad"
    elif asks:
        stamp, tone = "NEEDS YOU", "amb"
    else:
        stamp, tone = READY_STAMP.get(kind, "DONE"), "ok"
    return {"title": title, "kind": kind, "state": state, "blocked": blocked, "stamp": stamp,
            "stampTone": tone, "facts": norm_facts, "panels": normalized, "words": ctx.words}


# ---------------------------------------------------------------- rendering

def _tag(cls: str, text: str) -> str:
    return f'<span class="chip {cls}">{pagelib.esc(text)}</span>'


def _asks(p: dict) -> tuple[str, str]:
    if not p["rows"]:
        return '<p class="empty">✓ Nothing needs you</p>', "0"
    items = []
    for i, r in enumerate(p["rows"], 1):
        why = f'<div class="why">{_label(r["why"])}</div>' if r.get("why") else ""
        items.append(f'<li><span class="n">{i}</span><div><div class="q">{_label(r["ask"])}</div>{why}</div></li>')
    return f'<ol class="asks">{"".join(items)}</ol>', str(len(p["rows"]))


def _checks(p: dict) -> tuple[str, str]:
    rows, out = p["rows"], []
    for r in rows:
        mark, cls = {None: ("○", "nr")}.get(r["exit"], ("✓", "ok") if r["exit"] == 0 else ("✕", "bad"))
        exit_txt = "not run" if r["exit"] is None else f'exit {r["exit"]}'
        res = f'<span class="res">{_label(r["result"])}</span>' if r.get("result") else "<span></span>"
        cwd = f'<code class="cwd">{pagelib.esc(r["cwd"])}</code>' if r["cwd"] != "." else "<span></span>"
        out.append(
            f'<div class="crow {cls}"><span class="ico">{mark}</span>'
            f'<code title="{pagelib.esc(r["cwd"])}">{pagelib.esc(r["cmd"])}</code>{cwd}'
            f'<span class="exit">{exit_txt}</span>{res}</div>')
    ok = sum(1 for r in rows if r["exit"] == 0)
    nr = sum(1 for r in rows if r["exit"] is None)
    sub = f"{ok} pass · {len(rows) - ok - nr} fail · {nr} not run · agent-reported"
    return f'<div class="checks">{"".join(out)}</div>', sub


def _files(p: dict) -> tuple[str, str]:
    rows = p["rows"]
    if not rows:
        return '<p class="empty">No file changes</p>', "0 files"
    top = max(((r["added"] or 0) + (r["removed"] or 0)) for r in rows) or 1
    out = []
    for r in rows:
        if r["added"] is None:
            bar, nums = '<span class="bin">binary</span>', ""
        else:
            a, d = r["added"] * 100 // top, r["removed"] * 100 // top
            bar = f'<span class="bar"><i class="add" style="width:{a}%"></i><i class="del" style="width:{d}%"></i></span>'
            nums = f'<span class="n add">+{r["added"]}</span><span class="n del">−{r["removed"]}</span>'
        out.append(f'<div class="frow st-{r["status"]}"><span class="st">{r["status"]}</span>'
                   f'<code>{pagelib.esc(r["path"])}</code>{bar}{nums}</div>')
    add = sum(r["added"] or 0 for r in rows)
    dele = sum(r["removed"] or 0 for r in rows)
    return f'<div class="files">{"".join(out)}</div>', f"{len(rows)} files · +{add} −{dele}"


def _figure(p: dict) -> tuple[str, str]:
    cap = f'<figcaption>{_label(p["caption"])}</figcaption>'
    if "mermaid" in p:
        return f'<figure><pre class="mermaid">{pagelib.esc(p["mermaid"])}</pre>{cap}</figure>', ""
    steps = p["steps"]
    attr = f" data-steps='{pagelib.esc(json.dumps([s['say'] for s in steps]))}'" if steps else ""
    stepper = ""
    if steps:
        stepper = (
            '<div class="stepper"><button type="button" data-act="prev">◀</button>'
            '<button type="button" data-act="next">▶</button>'
            '<button type="button" data-act="play">play</button>'
            '<button type="button" data-act="all">show all</button>'
            '<button type="button" data-act="say" aria-pressed="false">narrate</button>'
            '<span class="cap"></span></div>')
    return f'<figure><div class="fig"{attr}>{p["svg"]}</div>{stepper}{cap}</figure>', ""


def _decisions(p: dict) -> tuple[str, str]:
    rows = []
    for r in p["rows"]:
        rej = f'<td class="bad">✕ <s>{_label(r["rejected"])}</s></td>' if r.get("rejected") else "<td></td>"
        rows.append(f'<tr><td>{_label(r["decision"])}</td><td class="ok">✓ {_label(r["chosen"])}</td>'
                    f'{rej}<td class="why">{_label(r["why"])}</td></tr>')
    tree = figures.decision_tree(p["rows"]) if any("parent" in r for r in p["rows"]) else ""
    table = f'<table class="dict"><tbody>{"".join(rows)}</tbody></table>'
    return tree + table, str(len(p["rows"]))


def _tasks(p: dict) -> tuple[str, str]:
    rows = p["rows"]
    out = []
    for r in rows:
        commit = f'<code>{pagelib.esc(r["commit"][:8])}</code>' if r.get("commit") else ""
        out.append(f'<div class="trow n-{r["status"]}"><code>{pagelib.esc(r["id"])}</code>'
                   f'<span class="tname">{_label(r["name"])}</span>'
                   f'{_tag("st-" + r["status"], figures.STATUS_WORDS.get(r["status"], r["status"]))}{commit}</div>')
    done = sum(1 for r in rows if r["status"] == "done")
    body = f'<div class="fig">{figures.task_waves_svg(rows)}</div><div class="tasks">{"".join(out)}</div>'
    return body, f"{done} of {len(rows)} done"


def _findings(p: dict) -> tuple[str, str]:
    rows = p["rows"]
    names = figures.venn_counts(rows)[0]
    out = []
    for r in rows:
        chips = "".join(
            f'<span class="chip rv-{"ab"[names.index(n)] if names.index(n) < 2 else "n"}">{pagelib.esc(n)}</span>'
            for n in r["foundBy"])
        where = ""
        if r.get("where"):
            where = f'<code class="where">{pagelib.esc(r["where"])}</code>'
            if not r["whereOk"]:
                where += '<span class="chip agent">agent-reported</span>'
        dispute = f'<div class="dispute">{_label(r["dispute"])}</div>' if r.get("dispute") else ""
        if r.get("outcome"):
            tail = f'<span class="chip out-{r["outcome"]}">{r["outcome"]}</span>'
        else:
            d = r["default"]
            tail = (f'<span class="tog" data-id="{pagelib.esc(r["id"])}" data-default="{d}">'
                    f'<button type="button" class="fix" data-v="fix" aria-pressed="{str(d == "fix").lower()}">fix</button>'
                    f'<button type="button" class="skp" data-v="skip" aria-pressed="{str(d == "skip").lower()}">skip</button></span>')
        out.append(
            f'<div class="finding sev-{r["sev"].lower()}" data-id="{pagelib.esc(r["id"])}">'
            f'<code class="fid">{pagelib.esc(r["id"])}</code>{_tag("sev-" + r["sev"].lower(), r["sev"])}'
            f'<div class="fmain"><div class="claim">{_label(r["claim"])}</div>{where}{chips}{dispute}</div>{tail}</div>')
    venn = figures.venn_svg(rows)
    board = f'<div class="findings">{"".join(out)}</div>'
    side = f'<div class="fside"><div class="venn">{venn}</div></div>' if venn else ""
    wrap = f'<div class="fwrap{" has-venn" if venn else ""}">{side}{board}</div>'
    return figures.severity_strip(rows) + wrap, str(len(rows))


def _claims(p: dict) -> tuple[str, str]:
    out = []
    for r in p["rows"]:
        cls = {"verified": "ok", "corrected": "amb", "unverified": "gry"}[r["result"]]
        note = f'<div class="note-line">{_label(r["note"])}</div>' if r.get("note") else ""
        out.append(f'<div class="crow2"><code>{pagelib.esc(r["id"])}</code>'
                   f'<div class="cl">{_label(r["claim"])}{note}</div>'
                   f'<code class="src">{pagelib.esc(r["source"])}</code>{_tag("c-" + cls, r["result"])}</div>')
    return figures.claim_stack(p["rows"]) + f'<div class="claims">{"".join(out)}</div>', str(len(p["rows"]))


def _commands(p: dict) -> tuple[str, str]:
    out = [f'<div class="cmd{" danger" if r.get("danger") else ""}"><code>{pagelib.esc(r["cmd"])}</code>'
           f'<span>{_label(r["does"])}</span></div>' for r in p["rows"]]
    return f'<div class="cmds">{"".join(out)}</div>', str(len(p["rows"]))


def _matrix(p: dict) -> tuple[str, str]:
    legend = "".join(f'<div><code>{pagelib.esc(r["id"])}</code> {_label(r["label"])}</div>' for r in p["rows"])
    return figures.heat_matrix(p["rows"]) + f'<div class="legend">{legend}</div>', str(len(p["rows"]))


def _table(p: dict) -> tuple[str, str]:
    head = "".join(f"<th>{_label(c)}</th>" for c in p["columns"])
    body = "".join("<tr>" + "".join(f"<td>{_label(c)}</td>" for c in row) + "</tr>" for row in p["rows"])
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>", str(len(p["rows"]))


RENDER = {"asks": _asks, "checks": _checks, "files": _files, "figure": _figure, "decisions": _decisions,
          "tasks": _tasks, "findings": _findings, "claims": _claims, "commands": _commands,
          "matrix": _matrix, "table": _table}


def _render_panel(p: dict) -> str:
    body, sub = RENDER[p["type"]](p)
    letter = p["letter"]
    cls = f'panel c{p["span"]} p-{p["type"]}'
    if p["type"] == "asks":
        cls += " needs" + (" has" if p["rows"] else "")
    sub_html = f'<span class="sub">{pagelib.esc(sub)}</span>' if sub else ""
    return (
        f'<section class="{cls}" data-letter="{letter}" data-role="{pagelib.esc(p["role"])}">'
        f'<h2><span class="ltr">{letter}</span>{_label(p["role"])}{sub_html}'
        f'<button type="button" class="note-btn" data-for="{letter}">note</button></h2>'
        f'<div class="pbody">{body}</div>'
        f'<textarea class="note" data-note="{letter}" hidden placeholder="Note on panel {letter}"></textarea>'
        f'</section>')


def render_sheet(sheet: dict) -> str:
    """Band, panel grid, and the title block with the color key."""
    tone = sheet["stampTone"]
    facts = "".join(f'<div><span class="kk">{_label(f["k"])}</span><span class="v">{pagelib.esc(f["v"])}</span></div>'
                    for f in sheet["facts"])
    key = "".join(f'<span><i class="sw sw-{c}"></i>{pagelib.esc(t)}</span>' for c, t in KEY_LANES)
    return (
        f'<div class="sheet" data-kind="{sheet["kind"]}">'
        f'<header class="band tone-{tone}"><div class="who"><div class="eyebrow">/{sheet["kind"]}</div>'
        f'<h1>{_label(sheet["title"])}</h1><p class="state">{pagelib.sanitize_prose(sheet["state"])}</p></div>'
        f'<div class="stamp {tone}">{sheet["stamp"]}</div></header>'
        f'<div class="grid">{"".join(_render_panel(p) for p in sheet["panels"])}</div>'
        f'<footer class="tb">{facts}<div class="key">{key}</div></footer></div>')


def render_failure(msg: str, spec_path: str) -> str:
    """Body of the BUILD FAILED page: the message and the spec path, no panels."""
    return (
        '<div class="sheet" data-kind="failed"><header class="band tone-bad"><div class="who">'
        '<div class="eyebrow">build</div><h1>BUILD FAILED</h1>'
        '<p class="state">Fix the spec and build again. The first error is below.</p></div>'
        '<div class="stamp bad">BUILD FAILED</div></header>'
        f'<div class="failbody"><pre>{pagelib.esc(msg)}</pre>'
        f'<p>Spec: <code>{pagelib.esc(spec_path)}</code></p></div></div>')


def assets() -> tuple[str, str]:
    return (HERE / "sheet.css").read_text(encoding="utf-8"), (HERE / "sheet.js").read_text(encoding="utf-8")
