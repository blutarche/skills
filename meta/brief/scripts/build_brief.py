#!/usr/bin/env python3
"""Render a brief page from a brief.json spec.

Reads the spec, checks every field against the rules in references/spec.md, and renders the
whole page from the spec's fields plus the shell in templates/brief-shell.html. The sheet (stamp,
panels, figures) comes from _lib/sheet.py; chapters follow it as the full report. The agent never edits
the HTML; a rejected spec is fixed and rebuilt.

Usage:
    build_brief.py --spec brief.json --out brief.html
                   [--fragment brief.fragment.html] [--data-out stats.json]
                   [--template path/to/brief-shell.html] [--no-mmdc]

Exit status 1 with a message naming the defect on any validation failure. A failed build writes
a BUILD FAILED page (the error, never the spec text) to --out and --fragment. Stdlib only,
Python 3.10 or newer.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = SKILL_DIR / "templates" / "brief-shell.html"
LIB_DIR = SKILL_DIR / "lib"
LIB_STYLE, LIB_SCRIPT = "<!-- LIB:STYLE -->", "<!-- LIB:SCRIPT -->"
SHEET_STYLE, SHEET_SCRIPT = "<!-- SHEET:STYLE -->", "<!-- SHEET:SCRIPT -->"

sys.path.insert(0, str(LIB_DIR))
import pagelib  # noqa: E402  (needs sys.path set up above)
import dock  # noqa: E402
import sheet  # noqa: E402
import svg  # noqa: E402
import voice  # noqa: E402

fail = pagelib.fail
esc = pagelib.esc
sanitize_prose = pagelib.sanitize_prose
MAX_CHAPTERS = 12

KINDS = sheet.KINDS
MERMAID_TYPES = {
    "flowchart", "graph", "sequenceDiagram", "stateDiagram", "stateDiagram-v2",
    "classDiagram", "erDiagram", "journey", "gantt", "pie", "quadrantChart",
    "timeline", "mindmap", "sankey-beta", "xychart-beta", "block-beta",
    "gitGraph", "C4Context",
}
KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
CODE_RE = re.compile(r"`([^`]*)`")
PRE_MERMAID = '<pre class="mermaid">{}</pre>'
MERMAID_VERSION = "11.15.0"
_MISSING = object()


def label_html(text: str) -> str:
    return CODE_RE.sub(lambda m: f"<code>{m.group(1)}</code>", esc(text))


# ---------------------------------------------------------------- svg figures


def build_svg_figure(svg_src: str, cid: str, idx: int) -> str:
    return svg.validate_figure(svg_src, f"chapter {cid} visual[{idx}]", f"f{cid}-{idx}-")


# ---------------------------------------------------------------- mermaid


def first_diagram_line(mermaid: str) -> str:
    """The first line a reader's eye lands on: past any leading blank lines, a `---`
    frontmatter block, and a `%%{init...}%%` directive, in either order."""
    lines = mermaid.splitlines()
    i, n = 0, len(lines)
    while True:
        while i < n and not lines[i].strip():
            i += 1
        if i >= n:
            return ""
        line = lines[i].strip()
        if line == "---":
            i += 1
            while i < n and lines[i].strip() != "---":
                i += 1
            if i < n:
                i += 1
            continue
        if line.startswith("%%{"):
            while i < n and "}%%" not in lines[i]:
                i += 1
            if i < n:
                i += 1
            continue
        return line


def mermaid_picture(mmdc: str, source: str, caption: str, tmpdir: Path, key: str, where: str) -> str:
    """Pre-render one diagram with mmdc in the light and dark themes and return a <picture>
    holding both as data URIs. A non-zero mmdc exit fails the build with its stderr."""
    mmd = tmpdir / f"{key}.mmd"
    mmd.write_text(source, encoding="utf-8")
    uris = {}
    for theme in ("default", "dark"):
        out = tmpdir / f"{key}-{theme}.svg"
        proc = subprocess.run(
            [mmdc, "-i", str(mmd), "-o", str(out), "-t", theme, "-b", "transparent", "-q"],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            fail(f"{where}: mmdc rejected the diagram: {proc.stderr.strip()}")
        if not out.is_file():
            fail(f"{where}: mmdc wrote no output")
        uris[theme] = "data:image/svg+xml;base64," + base64.b64encode(out.read_bytes()).decode("ascii")
    return (
        f'<picture><source media="(prefers-color-scheme: dark)" srcset="{uris["dark"]}">'
        f'<img src="{uris["default"]}" alt="{esc(caption)}"></picture>'
    )


def render_mermaid(sheet_html: str, norm: dict, chapters: list, tmpdir: Path, use_mmdc: bool) -> tuple[str, bool]:
    """Replace each mermaid <pre> (sheet figure panels, then chapter figures) with a
    pre-rendered <picture> when mmdc is available. Chapter figures get `_html` set. Returns the
    sheet html and whether any <pre class="mermaid"> is left for the online script."""
    jobs = []  # (source, caption, where, setter)
    for p in norm["panels"]:
        if p["type"] == "figure" and "mermaid" in p:
            jobs.append((p["mermaid"], p["caption"], f"panel {p['letter']} {p['role']}", None))
    for ch in chapters:
        for i, fig in enumerate(ch.get("_figures", [])):
            if fig.get("mermaid"):
                jobs.append((fig["mermaid"], fig["caption"], f"chapter {ch['id']} visual[{i}]", fig))
    if not jobs:
        return sheet_html, False
    mmdc = shutil.which("mmdc") if use_mmdc else None
    if not mmdc:
        print("build_brief: mmdc not found; mermaid figures render only online", file=sys.stderr)
    left = False
    for n, (source, caption, where, fig) in enumerate(jobs):
        pre = PRE_MERMAID.format(esc(source))
        html_out = mermaid_picture(mmdc, source, caption, tmpdir, f"m{n}", where) if mmdc else pre
        if fig is not None:
            fig["_html"] = html_out
        else:
            sheet_html = sheet_html.replace(pre, html_out, 1)
        left = left or not mmdc
    return sheet_html, left


# ---------------------------------------------------------------- validation


def normalize_figures(ch: dict, cid: str) -> list:
    """`visual` is either one figure object or an array of 1 to 4 of them; return it as a
    list either way. Called only once `visual` is known to be truthy."""
    visual = ch["visual"]
    if isinstance(visual, dict):
        return [visual]
    if isinstance(visual, list):
        if not 1 <= len(visual) <= 4:
            fail(f"chapter {cid}: visual must have 1 to 4 figures, has {len(visual)}")
        return visual
    fail(f"chapter {cid}: visual must be a figure object or an array of 1 to 4 figures")


def check_figure(fig, cid: str, idx: int) -> dict:
    """Validate one figure (exactly one of `mermaid`/`svg`, a label `caption`) and return it
    with `_svg` filled in when it is an svg figure, ready for rendering."""
    where = f"chapter {cid} visual[{idx}]"
    if not isinstance(fig, dict):
        fail(f"{where}: figure must be an object")

    has_mermaid = bool(fig.get("mermaid"))
    has_svg = bool(fig.get("svg"))
    if has_mermaid and has_svg:
        fail(f"{where}: has both mermaid and svg; use exactly one")
    if not has_mermaid and not has_svg:
        fail(f"{where}: needs exactly one of mermaid or svg")

    caption = fig.get("caption")
    if not isinstance(caption, str) or not caption.strip():
        fail(f"{where}: caption must be a non-empty string")
    voice.check_field(f"{where} caption", caption, "label")

    if has_mermaid:
        mermaid = fig["mermaid"]
        if not isinstance(mermaid, str):
            fail(f"{where}: mermaid must be a string")
        if not mermaid.strip():
            fail(f"{where}: mermaid must be non-empty")
        line = first_diagram_line(mermaid)
        first_token = line.split()[0] if line else ""
        if first_token not in MERMAID_TYPES:
            fail(
                f"{where}: mermaid diagram must start with one of "
                f"{sorted(MERMAID_TYPES)}; first line is {line!r}"
            )
    else:
        svg_src = fig["svg"]
        if not isinstance(svg_src, str):
            fail(f"{where}: svg must be a string")
        fig["_svg"] = build_svg_figure(svg_src, cid, idx)
    return fig


def check_text(where: str, value, cls: str, max_sentences: int | None = None) -> None:
    if not isinstance(value, str) or not value.strip():
        fail(f"{where}: must be non-empty text")
    voice.check_field(where, value, cls, max_sentences)


def check_chapter(ch, chapter_idx: int, seen_ids: set) -> None:
    if not isinstance(ch, dict):
        fail(f"chapters[{chapter_idx}] must be an object, got {type(ch).__name__}")
    for key in ("id", "title", "prose"):
        if not ch.get(key):
            fail(f"chapter {ch.get('id', '?')} is missing a required field: {key}")
    cid = ch["id"]
    if not isinstance(cid, str) or not KEBAB_RE.match(cid):
        fail(f"chapter id {cid!r} is not kebab-case")
    if cid in seen_ids:
        fail(f"duplicate chapter id: {cid}")
    seen_ids.add(cid)

    check_text(f"chapter {cid} title", ch["title"], "label")
    if not isinstance(ch["prose"], str):
        fail(f"chapter {cid} prose: must be text")
    if "proseWhy" in ch:
        fail(f"chapter {cid}: proseWhy is no longer used; prose has no length cap")
    voice.check_field(f"chapter {cid} prose", ch["prose"], "prose")

    if "visual" in ch:
        ch["_figures"] = [
            check_figure(fig, cid, i) for i, fig in enumerate(normalize_figures(ch, cid))
        ]

    figure_layout = ch.get("figureLayout")
    if figure_layout is not None and figure_layout != "row":
        fail(f"chapter {cid}: figureLayout must be \"row\" or absent, got {figure_layout!r}")

    decisions_val = ch.get("decisions", [])
    if not isinstance(decisions_val, list):
        fail(f"chapter {cid}: decisions must be an array")
    for i, d in enumerate(decisions_val):
        if not isinstance(d, dict):
            fail(f"chapter {cid} decisions[{i}]: must be an object")
        for key in ("decision", "chosen", "rejected", "why"):
            if not d.get(key):
                fail(f"chapter {cid} decisions[{i}]: missing {key}")
        for key in ("decision", "chosen", "rejected"):
            check_text(f"chapter {cid} decisions[{i}] {key}", d[key], "label")
        check_text(f"chapter {cid} decisions[{i}] why", d["why"], "instruction")

    evidence_val = ch.get("evidence", [])
    if not isinstance(evidence_val, list):
        fail(f"chapter {cid}: evidence must be an array")
    for i, e in enumerate(evidence_val):
        if not isinstance(e, dict):
            fail(f"chapter {cid} evidence[{i}]: must be an object")
        if not e.get("cmd"):
            fail(f"chapter {cid} evidence[{i}]: missing cmd")
        if not e.get("cwd"):
            fail(f"chapter {cid} evidence[{i}]: missing cwd")
        exit_val = e.get("exit", _MISSING)
        valid_exit = exit_val is None or (isinstance(exit_val, int) and not isinstance(exit_val, bool))
        if exit_val is _MISSING or not valid_exit:
            fail(f"chapter {cid} evidence[{i}]: exit must be an integer or null")
        if "ok" in e and not isinstance(e["ok"], bool):
            fail(f"chapter {cid} evidence[{i}]: ok must be true or false")
        if "summary" in e:
            check_text(f"chapter {cid} evidence[{i}] summary", e["summary"], "instruction")


def check_spec(spec, spec_dir: Path | None = None) -> dict:
    """Validate the whole spec; return the normalized sheet. Chapters are checked in place."""
    if not isinstance(spec, dict):
        fail("the spec must be a JSON object")
    for key in ("title", "kind", "state", "panels"):
        if not spec.get(key):
            fail(f"spec is missing a required field: {key}")
    if spec["kind"] not in KINDS:
        fail(f"kind {spec['kind']!r} is not one of {sorted(KINDS)}")

    chapters = spec.get("chapters", [])
    if not isinstance(chapters, list):
        fail(f"chapters must be an array of chapter objects, got {type(chapters).__name__}")
    if len(chapters) > MAX_CHAPTERS:
        fail(f"{len(chapters)} chapters; keep between 0 and {MAX_CHAPTERS}")
    seen_ids: set[str] = set()
    for chapter_idx, ch in enumerate(chapters):
        check_chapter(ch, chapter_idx, seen_ids)
    targets = {ch["id"]: (n, ch["title"]) for n, ch in enumerate(chapters, start=1)}
    return sheet.check_sheet(spec, kind=spec["kind"], title=spec["title"], spec_dir=spec_dir, targets=targets)


# ---------------------------------------------------------------- page


def render_evidence_chip(exit_val, ok) -> str:
    if exit_val is None:
        return '<span class="chip exit-none">not run</span>'
    if ok is True:
        return f'<span class="chip exit-ok">{int(exit_val)}</span>'
    if ok is False:
        return f'<span class="chip exit-bad">{int(exit_val)}</span>'
    return f'<span class="chip">{int(exit_val)}</span>'


def render_chapter(idx: int, ch: dict) -> str:
    """One closed card of the full report."""
    cid = ch["id"]
    o = [
        f'<details class="chapter" id="ch-{esc(cid)}" data-chapter="{esc(cid)}">',
        f'<summary class="chead"><span class="num">{idx}</span><h3 class="ttl">{label_html(ch["title"])}</h3>'
        f'<span class="chev" aria-hidden="true">▸</span></summary>',
        '<div class="dbody">',
    ]
    figures = ch.get("_figures", [])
    if figures:
        o.append(f'<div class="figs{" row" if ch.get("figureLayout") == "row" else ""}">')
        for fig in figures:
            if fig.get("mermaid"):
                inner = fig.get("_html") or PRE_MERMAID.format(esc(fig["mermaid"]))
            else:
                inner = f'<div class="fig cfig-svg">{fig["_svg"]}</div>'
            o.append(f'<figure class="cfig">{inner}<figcaption>{label_html(fig["caption"])}</figcaption></figure>')
        o.append("</div>")
    o.append(f'<div class="prose">{sanitize_prose(ch["prose"], pagelib.PROSE_RICH_TAGS)}</div>')

    decisions = ch.get("decisions", [])
    if decisions:
        o.append(
            '<div class="scroll"><table class="decisions"><thead><tr>'
            "<th>Decision</th><th>Chosen</th><th>Rejected</th><th>Why</th>"
            "</tr></thead><tbody>"
        )
        for d in decisions:
            o.append(
                f'<tr><td>{label_html(d["decision"])}</td><td>{label_html(d["chosen"])}</td>'
                f'<td>{label_html(d["rejected"])}</td><td>{label_html(d["why"])}</td></tr>'
            )
        o.append("</tbody></table></div>")

    evidence = ch.get("evidence", [])
    if evidence:
        o.append(
            '<div class="scroll"><table class="evidence"><thead><tr>'
            '<th class="col-cwd">CWD</th><th>Command</th><th class="col-exit">Exit</th>'
            "<th>Summary</th></tr></thead><tbody>"
        )
        for e in evidence:
            chip = render_evidence_chip(e.get("exit"), e.get("ok"))
            o.append(
                f'<tr><td class="col-cwd"><code>{esc(str(e["cwd"]))}</code></td>'
                f'<td><code>{esc(str(e["cmd"]))}</code></td><td class="col-exit">{chip}</td>'
                f'<td>{label_html(str(e.get("summary", "")))}</td></tr>'
            )
        o.append("</tbody></table></div>")

    o.append(
        f'<section class="dnote" data-role="{esc(ch["title"])}">'
        f'<textarea data-note="ch-{esc(cid)}" placeholder="Note on this chapter"></textarea></section>'
    )
    o.append("</div></details>")
    return "\n".join(o)


def page_title(title: str, norm: dict) -> str:
    return " · ".join(p for p in (norm["project"], norm["branch"], title) if p)


def build_body(spec: dict, norm: dict, page_key: str, tmpdir: Path, use_mmdc: bool) -> tuple[str, dict, bool]:
    chapters = spec.get("chapters", [])
    sheet_html, mermaid_left = render_mermaid(sheet.render_sheet(norm), norm, chapters, tmpdir, use_mmdc)
    built = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")

    o = [
        f'<div class="wrap" data-storage-key="brief:{esc(page_key)}" data-doc-title="{esc(spec["title"])}">',
        sheet_html,
    ]
    if chapters:
        o.append('<section class="report" id="report"><div class="rhead"><h2>Full report</h2>'
                 f'{pagelib.at_row(norm["project"], norm["branch"], True)}'
                 '<button type="button" class="btn" data-toggle-all>Open all</button></div>')
        o.extend(
            render_chapter(i, ch) for i, ch in enumerate(chapters, start=1)
        )
        o.append("</section>")
    o.append(dock.render_dock(norm["project"], norm["branch"], bool(chapters)))
    o.append(f'<footer class="pgfoot">Words on sheet: {norm["words"]} · built {esc(built)} from brief.json</footer>')
    o.append("</div>")

    figures = sum(1 for p in norm["panels"] if p["type"] == "figure")
    figures += sum(len(ch.get("_figures", [])) for ch in chapters)
    stats = {
        "kind": norm["kind"],
        "stamp": norm["stamp"],
        "panels": len(norm["panels"]),
        "asks": len(norm["panels"][0]["rows"]),
        "words": norm["words"],
        "figures": figures,
        "chapters": len(chapters),
    }
    return "\n".join(o), stats, mermaid_left


# ---------------------------------------------------------------- assembly


def load_shell(template: Path) -> str:
    if not template.is_file():
        fail(f"template not found: {template}")
    shell = template.read_text(encoding="utf-8")
    for marker in (LIB_STYLE, LIB_SCRIPT, SHEET_STYLE, SHEET_SCRIPT):
        if marker not in shell:
            fail(f"{template}: missing {marker} marker")
    sheet_css, sheet_js = sheet.assets()
    dock_css, dock_js = dock.assets()
    for marker, path, extra in ((LIB_STYLE, LIB_DIR / "page.css", dock_css), (LIB_SCRIPT, LIB_DIR / "notes.js", dock_js)):
        shell = shell.replace(marker, path.read_text(encoding="utf-8").rstrip("\n") + "\n" + extra.rstrip("\n"))
    shell = shell.replace(SHEET_STYLE, sheet_css.rstrip("\n"))
    return shell.replace(SHEET_SCRIPT, sheet_js.rstrip("\n"))


def main() -> None:
    ap = argparse.ArgumentParser(description="Render a brief page from brief.json.")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True, help="full HTML document")
    ap.add_argument("--fragment", default=None, help="same content without the document wrappers")
    ap.add_argument("--data-out", default=None, help="write the derived stats as JSON here")
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    ap.add_argument("--no-mmdc", action="store_true", help="skip mmdc; mermaid renders in the browser")
    args = ap.parse_args()

    shell = load_shell(Path(args.template))
    try:
        try:
            spec_bytes = Path(args.spec).read_bytes()
        except OSError as e:
            fail(f"cannot read the spec {args.spec}: {e}")
        try:
            spec = json.loads(spec_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            fail(f"cannot parse the spec {args.spec}: {e}")

        norm = check_spec(spec, Path(args.spec).resolve().parent)
        page_key = hashlib.sha256(spec_bytes).hexdigest()[:12]
        with tempfile.TemporaryDirectory() as tmp:
            body, stats, mermaid_left = build_body(spec, norm, page_key, Path(tmp), not args.no_mmdc)
        document, fragment = pagelib.assemble(shell, esc(page_title(spec["title"], norm)), body)
    except pagelib.BuildFailed as e:
        document, fragment = pagelib.assemble(shell, "Build failed", sheet.render_failure(e.msg, args.spec))
        Path(args.out).write_text(document, encoding="utf-8")
        if args.fragment:
            Path(args.fragment).write_text(fragment, encoding="utf-8")
        raise

    if mermaid_left:
        mermaid_script = (
            f'<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/{MERMAID_VERSION}/'
            'mermaid.min.js"></script>\n'
            # A diagram inside a closed <details> lays out at zero size, so it renders when the
            # <details> first opens, not on page load.
            "<script>if(window.mermaid){mermaid.initialize({startOnLoad:false, securityLevel: 'strict', theme: "
            'window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "default"});'
            "var mmRun=function(root){var n=[].slice.call(root.querySelectorAll('pre.mermaid:not([data-processed])'))"
            ".filter(function(e){return !e.closest('details:not([open])')});if(n.length)mermaid.run({nodes:n})};"
            "mmRun(document);document.querySelectorAll('details').forEach(function(d){"
            "d.addEventListener('toggle',function(){if(d.open)mmRun(d)})})}</script>"
        )
        document = document.replace("<!-- SCRIPT:END -->", "<!-- SCRIPT:END -->\n" + mermaid_script, 1)

    Path(args.out).write_text(document, encoding="utf-8")
    if args.fragment:
        Path(args.fragment).write_text(fragment, encoding="utf-8")
    if args.data_out:
        Path(args.data_out).write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(
        f"build_brief: ok kind={stats['kind']} stamp={stats['stamp']} panels={stats['panels']} "
        f"asks={stats['asks']} words={stats['words']} chapters={stats['chapters']}"
    )


if __name__ == "__main__":
    main()
