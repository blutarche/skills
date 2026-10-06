"""Builder-drawn sheet figures: task waves, 2-set Venn, severity strip, claim stack, heat
matrix, decision tree. The builder derives each from validated rows, so the agent never draws
them and the numbers cannot drift. Colors come from sheet.css classes, never inline.

Stdlib only, Python 3.10 or newer.
"""

from __future__ import annotations

import pagelib

STATUSES = ("done", "failed", "blocked", "skipped", "todo")
STATUS_WORDS = {"todo": "to do"}
SEVERITIES = ("P0", "P1", "P2", "P3")
LEVELS = ("low", "med", "high")
RESULTS = (("verified", "ok"), ("corrected", "amb"), ("unverified", "gry"))

BOX_W, BOX_H, COL_STEP, ROW_STEP, PAD = 160, 40, 196, 56, 16


def waves(tasks: list[dict]) -> dict[str, int]:
    """Wave number per task id: 0 with no `after`, else 1 + the latest dependency's wave."""
    by_id = {t["id"]: t for t in tasks}
    memo: dict[str, int] = {}
    path: list[str] = []

    def visit(tid: str) -> int:
        if tid in memo:
            return memo[tid]
        if tid in path:
            pagelib.fail(f"tasks: cycle through {tid}")
        path.append(tid)
        wave = 0
        for dep in by_id[tid].get("after") or []:
            if dep not in by_id:
                pagelib.fail(f"tasks: {tid} is after unknown task {dep}")
            wave = max(wave, visit(dep) + 1)
        path.pop()
        memo[tid] = wave
        return wave

    for t in tasks:
        visit(t["id"])
    return memo


def _short(name: str) -> str:
    return name if len(name) <= 20 else name[:20] + "…"


def task_waves_svg(tasks: list[dict]) -> str:
    wave_of = waves(tasks)
    slot: dict[str, tuple[int, int]] = {}
    per_wave: dict[int, int] = {}
    for t in tasks:
        w = wave_of[t["id"]]
        slot[t["id"]] = (PAD + w * COL_STEP, PAD + per_wave.get(w, 0) * ROW_STEP)
        per_wave[w] = per_wave.get(w, 0) + 1

    n_waves = max(wave_of.values()) + 1 if tasks else 0
    width = PAD + max(n_waves - 1, 0) * COL_STEP + BOX_W + PAD
    height = PAD + max(per_wave.values(), default=1) * ROW_STEP - (ROW_STEP - BOX_H) + PAD

    paths, boxes = [], []
    for t in tasks:
        x, y = slot[t["id"]]
        for dep in t.get("after") or []:
            x1, y1 = slot[dep][0] + BOX_W, slot[dep][1] + BOX_H // 2
            x2, y2 = x, y + BOX_H // 2
            mid = (x1 + x2) // 2
            paths.append(
                f'<path class="e-ok" d="M{x1} {y1} C{mid} {y1} {mid} {y2} {x2} {y2}" marker-end="url(#ar)"/>'
            )
        go = data = title = ""
        if t.get("more"):
            go, data = " go", f' data-go="ch-{pagelib.esc(t["more"])}"'
            title = f'<title>Section {t["moreN"]}: {pagelib.esc(t["moreTitle"])}</title>'
        boxes.append(
            f'<g class="task n-{pagelib.esc(t.get("status", "todo"))}{go}"{data}>{title}'
            f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{BOX_H}" rx="4"/>'
            f'<text x="{x + 10}" y="{y + 25}"><tspan class="tid">{pagelib.esc(t["id"])}</tspan> '
            f'{pagelib.esc(_short(t.get("name", "")))}</text></g>'
        )

    counts = [(s, sum(1 for t in tasks if t.get("status", "todo") == s)) for s in STATUSES]
    parts = ", ".join(f"{n} {STATUS_WORDS.get(s, s)}" for s, n in counts if n)
    label = f"{len(tasks)} tasks in {n_waves} waves: {parts}"
    marker = (
        '<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
        'orient="auto"><path d="M0 0 L10 5 L0 10 z"/></marker></defs>'
    )
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{pagelib.esc(label)}">'
        f'{marker}{"".join(paths)}{"".join(boxes)}</svg>'
    )


def venn_counts(rows: list[dict]) -> tuple[list[str], int, int, int]:
    names: list[str] = []
    for r in rows:
        for n in r.get("foundBy") or []:
            if n not in names:
                names.append(n)
    if len(names) != 2:
        return names, 0, 0, 0
    a, b = names
    only_a = only_b = both = 0
    for r in rows:
        found = set(r.get("foundBy") or [])
        if a in found and b in found:
            both += 1
        elif a in found:
            only_a += 1
        elif b in found:
            only_b += 1
    return names, only_a, only_b, both


def venn_svg(rows: list[dict]) -> str | None:
    names, only_a, only_b, both = venn_counts(rows)
    if len(names) != 2:
        return None
    a, b = (pagelib.esc(n) for n in names)
    label = f"{a} found {only_a + both}, {b} found {only_b + both}, both found {both}"
    return (
        f'<svg viewBox="0 0 240 140" role="img" aria-label="{label}">'
        '<circle class="rv-a" cx="90" cy="60" r="55"/><circle class="rv-b" cx="150" cy="60" r="55"/>'
        f'<text class="big" x="62" y="68" text-anchor="middle">{only_a}</text>'
        f'<text class="big" x="120" y="68" text-anchor="middle">{both}</text>'
        f'<text class="big" x="178" y="68" text-anchor="middle">{only_b}</text>'
        f'<text x="80" y="132" text-anchor="middle">{a}</text>'
        f'<text x="160" y="132" text-anchor="middle">{b}</text></svg>'
    )


def severity_strip(rows: list[dict]) -> str:
    spans = []
    for p in SEVERITIES:
        n = sum(1 for r in rows if r.get("sev") == p)
        if n:
            spans.append(f'<span class="sev-{p.lower()}" style="flex:{n}">{p} {n}</span>')
    return f'<div class="sev-strip">{"".join(spans)}</div>'


def decision_tree(rows: list[dict]) -> str:
    ids = {r.get("id") for r in rows}
    kids: dict[str | None, list[dict]] = {}
    for r in rows:
        parent = r.get("parent")
        if parent is not None and parent not in ids:
            pagelib.fail(f"decisions: {r.get('id')} has unknown parent {parent}")
        kids.setdefault(parent, []).append(r)

    shown = 0

    def node(r: dict) -> str:
        nonlocal shown
        shown += 1
        out = f'<li><b>{pagelib.esc(r.get("decision", ""))}</b>'
        if r.get("chosen"):
            out += f' <span class="ok">✓ {pagelib.esc(r["chosen"])}</span>'
        if r.get("rejected"):
            out += f' <span class="bad">✕ <s>{pagelib.esc(r["rejected"])}</s></span>'
        children = kids.get(r.get("id"), []) if r.get("id") is not None else []
        if children:
            out += "<ul>" + "".join(node(c) for c in children) + "</ul>"
        return out + "</li>"

    body = "".join(node(r) for r in kids.get(None, []))
    if shown != len(rows):
        pagelib.fail("decisions: parent links form a cycle")
    return f'<ul class="tree">{body}</ul>'


def heat_matrix(rows: list[dict]) -> str:
    cells: dict[tuple[str, str], list[str]] = {}
    for r in rows:
        lk, im = r.get("likelihood"), r.get("impact")
        if lk not in LEVELS or im not in LEVELS:
            pagelib.fail(f"matrix: {r.get('id')} needs likelihood and impact of low, med or high")
        cells.setdefault((lk, im), []).append(pagelib.esc(r["id"]))
    out = []
    for lk in reversed(LEVELS):
        for im in LEVELS:
            score = LEVELS.index(lk) + LEVELS.index(im)
            out.append(
                f'<div class="h{score}" data-cell="{lk}-{im}">{" ".join(cells.get((lk, im), []))}</div>'
            )
    rows_ax = "".join(f'<span class="ax-y">{w}</span>' for w in reversed(LEVELS))
    cols_ax = "".join(f'<span class="ax-x">{w}</span>' for w in LEVELS)
    return (
        '<div class="heatbox"><span class="ax-cap-y">likelihood</span>'
        f'<div class="ax-rows">{rows_ax}</div><div class="heat">{"".join(out)}</div>'
        f'<span></span><span></span><div class="ax-cols">{cols_ax}</div>'
        f'<span></span><span></span><span class="ax-cap-x">impact</span></div>')


def claim_stack(rows: list[dict]) -> str:
    bars, words = [], []
    for res, cls in RESULTS:
        n = sum(1 for r in rows if r.get("result") == res)
        if n:
            bars.append(f'<span class="{cls}" style="flex:{n}" title="{res} {n}">{res} {n}</span>')
            words.append(f"{n} {res}")
    label = " · ".join(words)
    return f'<div class="claim-stack" aria-label="{pagelib.esc(label)}">{"".join(bars)}<span class="lbl">{pagelib.esc(label)}</span></div>'
