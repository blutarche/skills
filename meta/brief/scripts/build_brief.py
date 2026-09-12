#!/usr/bin/env python3
"""Render a brief page from a brief.json spec.

Reads the spec, checks every field against the rules in references/spec.md, and renders the
whole page from the spec's prose plus the shell in templates/brief-shell.html. The agent never
edits the HTML; a rejected spec is fixed and rebuilt.

Usage:
    build_brief.py --spec brief.json --out brief.html
                   [--fragment brief.fragment.html] [--data-out stats.json]
                   [--template path/to/brief-shell.html] [--no-mmdc]

Exit status 1 with a message naming the defect on any validation failure; no output file is
touched when a build fails. Stdlib only, Python 3.10 or newer.
"""

from __future__ import annotations

import argparse
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

sys.path.insert(0, str(LIB_DIR))
import pagelib  # noqa: E402  (needs sys.path set up above)

fail = pagelib.fail
esc = pagelib.esc
sanitize_prose = pagelib.sanitize_prose

KINDS = {"plan", "execution", "investigation", "mixed"}
KIND_LABEL = {
    "plan": "Plan",
    "execution": "Execution result",
    "investigation": "Investigation",
    "mixed": "Mixed",
}
MERMAID_TYPES = {
    "flowchart", "graph", "sequenceDiagram", "stateDiagram", "stateDiagram-v2",
    "classDiagram", "erDiagram", "journey", "gantt", "pie", "quadrantChart",
    "timeline", "mindmap", "sankey-beta", "xychart-beta", "block-beta",
    "gitGraph", "C4Context",
}
KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SENTENCE_RE = re.compile(r"(?<=[.!?])(?:\s+|$)")
_MISSING = object()


# ---------------------------------------------------------------- prose measurement


def plain_text(value: str) -> str:
    """Sanitized text with every surviving tag stripped and entities resolved, for word and
    sentence counting. Never fails: an odd or empty field just counts as empty."""
    sanitized = sanitize_prose(value)
    stripped = re.sub(r"<[^>]+>", " ", sanitized)
    return html.unescape(stripped)


def word_count(text: str) -> int:
    return len(text.split())


def sentences_of(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_RE.split(text.strip()) if s.strip()]


def check_word_cap(where: str, text: str, cap: int) -> None:
    n = word_count(text)
    if n > cap:
        fail(f"{where} is {n} words; keep to {cap}")


def check_sentence_cap(where: str, text: str) -> None:
    for sentence in sentences_of(text):
        n = word_count(sentence)
        if n > 25:
            first_five = " ".join(sentence.split()[:5])
            fail(f"{where}: a sentence is {n} words, over 25: \"{first_five} ...\"")


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


def check_mermaid_with_mmdc(spec: dict, tmpdir: Path) -> None:
    mmdc_path = shutil.which("mmdc")
    if not mmdc_path:
        print("build_brief: mmdc not found, mermaid syntax unchecked", file=sys.stderr)
        return
    for ch in spec["chapters"]:
        visual = ch.get("visual")
        if not visual:
            continue
        mmd_path = tmpdir / f"{ch['id']}.mmd"
        svg_path = tmpdir / f"{ch['id']}.svg"
        mmd_path.write_text(visual["mermaid"], encoding="utf-8")
        proc = subprocess.run(
            [mmdc_path, "-i", str(mmd_path), "-o", str(svg_path), "-q"],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            fail(f"chapter {ch['id']}: mmdc rejected the diagram: {proc.stderr.strip()}")


# ---------------------------------------------------------------- validation


def check_spec(spec: dict) -> None:
    for key in ("title", "kind", "state", "chapters"):
        if not spec.get(key):
            fail(f"spec is missing a required field: {key}")
    if spec["kind"] not in KINDS:
        fail(f"kind {spec['kind']!r} is not one of {sorted(KINDS)}")

    chapters = spec["chapters"]
    if not isinstance(chapters, list) or not 1 <= len(chapters) <= 8:
        fail(f"{len(chapters)} chapters; keep between 1 and 8")

    seen_ids: set[str] = set()
    for ch in chapters:
        for key in ("id", "title", "prose"):
            if not ch.get(key):
                fail(f"chapter {ch.get('id', '?')} is missing a required field: {key}")
        cid = ch["id"]
        if not KEBAB_RE.match(cid):
            fail(f"chapter id {cid!r} is not kebab-case")
        if cid in seen_ids:
            fail(f"duplicate chapter id: {cid}")
        seen_ids.add(cid)

        has_visual = bool(ch.get("visual"))
        has_no_visual = bool(ch.get("noVisual"))
        if has_visual and has_no_visual:
            fail(f"chapter {cid}: has both visual and noVisual; use exactly one")
        if not has_visual and not has_no_visual:
            fail(f"chapter {cid}: needs exactly one of visual or noVisual")
        if has_no_visual and not isinstance(ch["noVisual"], str):
            fail(f"chapter {cid}: noVisual must be a non-empty string")
        if has_visual:
            visual = ch["visual"]
            mermaid = visual.get("mermaid") if isinstance(visual, dict) else None
            if not mermaid or not mermaid.strip():
                fail(f"chapter {cid}: visual.mermaid must be non-empty")
            line = first_diagram_line(mermaid)
            first_token = line.split()[0] if line else ""
            if first_token not in MERMAID_TYPES:
                fail(
                    f"chapter {cid}: mermaid diagram must start with one of "
                    f"{sorted(MERMAID_TYPES)}; first line is {line!r}"
                )

        check_word_cap(f"chapter {cid} prose", plain_text(ch["prose"]), 120)
        check_sentence_cap(f"chapter {cid} prose", plain_text(ch["prose"]))

        for i, d in enumerate(ch.get("decisions", [])):
            for key in ("decision", "chosen", "rejected", "why"):
                if not d.get(key):
                    fail(f"chapter {cid} decisions[{i}]: missing {key}")

        for i, e in enumerate(ch.get("evidence", [])):
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

    if spec.get("context"):
        check_word_cap("context", plain_text(spec["context"]), 120)
        check_sentence_cap("context", plain_text(spec["context"]))
    check_word_cap("state", plain_text(spec["state"]), 60)
    check_sentence_cap("state", plain_text(spec["state"]))

    for i, item in enumerate(spec.get("open", [])):
        if not isinstance(item, str):
            fail(f"open[{i}]: must be a string")


# ---------------------------------------------------------------- page


def render_evidence_chip(exit_val, ok) -> str:
    if exit_val is None:
        return '<span class="chip exit-none">not run</span>'
    if ok is True:
        return f'<span class="chip exit-ok">{int(exit_val)}</span>'
    if ok is False:
        return f'<span class="chip exit-bad">{int(exit_val)}</span>'
    return f'<span class="chip">{int(exit_val)}</span>'


def build_body(spec: dict, page_key: str) -> tuple[str, dict]:
    chapters = spec["chapters"]
    context = spec.get("context")
    state = spec["state"]
    open_items = spec.get("open", [])

    visuals = sum(1 for ch in chapters if ch.get("visual"))
    no_visuals = sum(1 for ch in chapters if ch.get("noVisual"))
    decisions_count = sum(len(ch.get("decisions", [])) for ch in chapters)
    evidence_all = [e for ch in chapters for e in ch.get("evidence", [])]
    evidence_ran = sum(1 for e in evidence_all if e.get("exit") is not None)
    evidence_not_run = len(evidence_all) - evidence_ran

    words = word_count(plain_text(context)) if context else 0
    words += word_count(plain_text(state))
    for ch in chapters:
        words += word_count(plain_text(ch["prose"]))

    stats = {
        "chapters": len(chapters),
        "visuals": visuals,
        "noVisuals": no_visuals,
        "decisions": decisions_count,
        "evidenceRan": evidence_ran,
        "evidenceNotRun": evidence_not_run,
        "evidenceTotal": len(evidence_all),
        "words": words,
    }

    built = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    kind_label = KIND_LABEL.get(spec["kind"], spec["kind"])

    o: list[str] = []
    o.append(
        f'<div class="wrap" data-storage-key="brief:{esc(page_key)}" '
        f'data-doc-title="{esc(spec["title"])}">'
    )

    o.append('<header class="top">')
    o.append('<p class="eyebrow">Brief</p>')
    o.append(f'<h1>{esc(spec["title"])}</h1>')
    o.append(
        f'<div class="banner"><b>{esc(kind_label)}</b><span>Built on {esc(built)}. Rendered '
        "from brief.json; the agent never edits this page directly.</span></div>"
    )
    o.append("</header>")

    o.append('<div class="strip">')
    o.append(f'<div class="stat"><div class="k">Chapters</div><div class="v">{stats["chapters"]}</div></div>')
    o.append(
        f'<div class="stat"><div class="k">Visuals</div><div class="v">{stats["visuals"]}</div>'
        f'<div class="s">{stats["noVisuals"]} reasoned skip</div></div>'
    )
    o.append(f'<div class="stat"><div class="k">Decisions</div><div class="v">{stats["decisions"]}</div></div>')
    o.append(
        f'<div class="stat"><div class="k">Evidence</div><div class="v">{stats["evidenceRan"]}/{stats["evidenceTotal"]}</div>'
        f'<div class="s">{stats["evidenceNotRun"]} not run</div></div>'
    )
    o.append(f'<div class="stat"><div class="k">Words</div><div class="v">{stats["words"]}</div></div>')
    o.append("</div>")

    if context:
        o.append('<section id="context"><h2>Context</h2>')
        o.append(sanitize_prose(context))
        o.append("</section>")

    o.append('<section id="state" class="state-box"><h2>State</h2>')
    o.append(sanitize_prose(state))
    o.append("</section>")

    o.append('<section id="chapters">')
    for idx, ch in enumerate(chapters, start=1):
        cid = ch["id"]
        o.append(f'<article class="chapter" id="ch-{esc(cid)}" data-chapter="{esc(cid)}">')
        o.append(
            f'<header class="chapter-head"><span class="num">{idx}</span><h3>{esc(ch["title"])}</h3></header>'
        )
        visual = ch.get("visual")
        if visual:
            o.append('<figure class="visual">')
            o.append(f'<pre class="mermaid">{esc(visual["mermaid"])}</pre>')
            if visual.get("caption"):
                o.append(f'<figcaption>{sanitize_prose(visual["caption"])}</figcaption>')
            o.append("</figure>")
        o.append(f'<div class="prose">{sanitize_prose(ch["prose"])}</div>')

        decisions = ch.get("decisions", [])
        if decisions:
            o.append(
                '<div class="scroll"><table class="decisions"><thead><tr>'
                "<th>Decision</th><th>Chosen</th><th>Rejected</th><th>Why</th>"
                "</tr></thead><tbody>"
            )
            for d in decisions:
                o.append(
                    f'<tr><td>{esc(d["decision"])}</td><td>{esc(d["chosen"])}</td>'
                    f'<td>{esc(d["rejected"])}</td><td>{sanitize_prose(d["why"])}</td></tr>'
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
                    f'<td>{sanitize_prose(str(e.get("summary", "")))}</td></tr>'
                )
            o.append("</tbody></table></div>")

        o.append("</article>")
    o.append("</section>")

    if open_items:
        o.append('<section id="open"><h2>Open</h2><ul class="plain">')
        o.extend(f"<li>{sanitize_prose(item)}</li>" for item in open_items)
        o.append("</ul></section>")

    o.append('<section id="notes" class="notes"><h2>Notes</h2>')
    o.append(
        '<p class="lede">Kept in this browser only. "Copy feedback" turns your notes into '
        "Markdown you can paste back into the chat.</p>"
    )
    for ch in chapters:
        o.append('<div class="note">')
        o.append(f'<label for="note-{esc(ch["id"])}">{esc(ch["title"])}</label>')
        o.append(
            f'<textarea id="note-{esc(ch["id"])}" data-note="{esc(ch["id"])}" '
            'placeholder="What to change, what to check, what you approve."></textarea>'
        )
        o.append("</div>")
    o.append('<p><button type="button" class="btn primary" data-export>Copy feedback</button> ')
    o.append('<span class="count" data-export-status></span></p>')
    o.append("<pre data-export-preview hidden></pre>")
    o.append("</section>")

    o.append(f"<footer>Built from brief.json on {esc(built)}.</footer>")
    o.append("</div>")

    return "\n".join(o), stats


# ---------------------------------------------------------------- assembly

MERMAID_VERSION = "11.4.1"


def main() -> None:
    ap = argparse.ArgumentParser(description="Render a brief page from brief.json.")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True, help="full HTML document")
    ap.add_argument("--fragment", default=None, help="same content without the document wrappers")
    ap.add_argument("--data-out", default=None, help="write the derived stats as JSON here")
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    ap.add_argument("--no-mmdc", action="store_true", help="skip the mmdc mermaid syntax check")
    args = ap.parse_args()

    try:
        spec_bytes = Path(args.spec).read_bytes()
    except OSError as e:
        fail(f"cannot read the spec {args.spec}: {e}")
    try:
        spec = json.loads(spec_bytes.decode("utf-8"))
    except json.JSONDecodeError as e:
        fail(f"cannot parse the spec {args.spec}: {e}")

    template = Path(args.template)
    if not template.is_file():
        fail(f"template not found: {template}")
    shell = template.read_text(encoding="utf-8")
    if LIB_STYLE not in shell or LIB_SCRIPT not in shell:
        fail(f"{template}: missing {LIB_STYLE} or {LIB_SCRIPT} marker")
    shell = shell.replace(LIB_STYLE, (LIB_DIR / "page.css").read_text(encoding="utf-8").rstrip("\n"))
    shell = shell.replace(LIB_SCRIPT, (LIB_DIR / "notes.js").read_text(encoding="utf-8").rstrip("\n"))

    check_spec(spec)
    if not args.no_mmdc:
        with tempfile.TemporaryDirectory() as tmp:
            check_mermaid_with_mmdc(spec, Path(tmp))

    page_key = hashlib.sha256(spec_bytes).hexdigest()[:12]
    body, stats = build_body(spec, page_key)
    title = esc(spec["title"])
    document, fragment = pagelib.assemble(shell, title, body)

    mermaid_script = (
        f'<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/{MERMAID_VERSION}/'
        'mermaid.min.js"></script>\n'
        "<script>mermaid.initialize({startOnLoad:true, theme: "
        'window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "default"});</script>'
    )
    document = document.replace(
        "<!-- SCRIPT:END -->", "<!-- SCRIPT:END -->\n" + mermaid_script, 1
    )

    # everything validated: write the outputs last, so a failed build leaves them untouched
    Path(args.out).write_text(document, encoding="utf-8")
    if args.fragment:
        Path(args.fragment).write_text(fragment, encoding="utf-8")
    if args.data_out:
        Path(args.data_out).write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(
        f"build_brief: ok chapters={stats['chapters']} visuals={stats['visuals']} "
        f"noVisuals={stats['noVisuals']} decisions={stats['decisions']} "
        f"evidence={stats['evidenceRan']}/{stats['evidenceTotal']} words={stats['words']}"
    )


if __name__ == "__main__":
    main()
