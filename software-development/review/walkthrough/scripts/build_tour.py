#!/usr/bin/env python3
"""Render a walkthrough page from a review-tour.json spec and the real git diff.

Reads the spec, resolves the diff between `base` and `head` (a sha, or the literal
"worktree"), checks every claim the spec makes about the diff, and renders the whole page
from the spec's prose plus the shell in templates/tour-shell.html.

Usage:
    build_tour.py --spec review-tour.json --repo-root . --out tour.html
                  [--fragment tour.fragment.html] [--data-out stats.json]
                  [--template path/to/tour-shell.html]

Exit status 1 with a message naming the defect on any validation failure; no output file is
touched when a build fails. Stdlib only, Python 3.10 or newer.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

WORKTREE = "worktree"
DEFAULT_TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "tour-shell.html"

TITLE_START, TITLE_END = "<!-- TITLE:START -->", "<!-- TITLE:END -->"
STYLE_START, STYLE_END = "<!-- STYLE:START -->", "<!-- STYLE:END -->"
BODY_START, BODY_END = "<!-- BODY:START -->", "<!-- BODY:END -->"
SCRIPT_START, SCRIPT_END = "<!-- SCRIPT:START -->", "<!-- SCRIPT:END -->"

RISK_LABEL = {"attention": "read closely", "medium": "read once", "safe": "skim"}
SIDES = ("new", "old")
STATUS_LABEL = {"A": "added", "M": "modified", "D": "deleted", "R": "renamed", "C": "copied", "T": "type change"}


def fail(msg: str) -> None:
    print(f"build_tour: {msg}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------- git


def git_bytes(root: Path, *args: str) -> bytes:
    out = subprocess.run(["git", *args], cwd=root, capture_output=True)
    if out.returncode != 0:
        fail(f"git {' '.join(args)} failed: {out.stderr.decode('utf-8', 'replace').strip()}")
    return out.stdout


def git(root: Path, *args: str) -> str:
    return git_bytes(root, *args).decode("utf-8", "replace")


def is_binary(blob: bytes) -> bool:
    return b"\0" in blob[:8000]


def lines_of(blob: bytes) -> list[str]:
    return blob.decode("utf-8", "replace").splitlines()


# ---------------------------------------------------------------- diff model


@dataclass
class FileDiff:
    path: str
    status: str  # A M D R C T
    old_path: str | None = None  # base-side path of a rename or copy
    binary: bool = False  # no lines to anchor; the card carries status and counts only
    added: set[int] = field(default_factory=set)  # new-side line numbers
    removed: set[int] = field(default_factory=set)  # old-side line numbers
    # removed text keyed by the new-side line it sits next to: (line, "before"|"after") -> texts
    removed_blocks: dict[tuple[int, str], list[str]] = field(default_factory=dict)
    new_lines: list[str] = field(default_factory=list)
    old_lines: list[str] = field(default_factory=list)


HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def load_changed_files(root: Path, base: str, head: str) -> dict[str, FileDiff]:
    worktree = head == WORKTREE
    rev_args = [base] if worktree else [f"{base}..{head}"]
    files: dict[str, FileDiff] = {}
    # -z keeps paths raw, so a name with a tab, a newline, or non-ASCII survives
    fields = git_bytes(root, "diff", "--name-status", "-z", *rev_args).split(b"\0")
    i = 0
    while i < len(fields) and fields[i]:
        status = fields[i][:1].decode("ascii")
        if status in "RC":
            old_path = fields[i + 1].decode("utf-8", "surrogateescape")
            path = fields[i + 2].decode("utf-8", "surrogateescape")
            i += 3
        else:
            old_path = None
            path = fields[i + 1].decode("utf-8", "surrogateescape")
            i += 2
        files[path] = FileDiff(path=path, status=status, old_path=old_path)

    untracked: list[str] = []
    if worktree:
        for raw in git_bytes(root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0"):
            if raw:
                untracked.append(raw.decode("utf-8", "surrogateescape"))
        for path in untracked:
            files.setdefault(path, FileDiff(path=path, status="A"))

    for fd in files.values():
        base_path = fd.old_path or fd.path
        old_blob = git_bytes(root, "show", f"{base}:{base_path}") if fd.status != "A" else b""
        if fd.status == "D":
            new_blob = b""
        elif worktree:
            disk = root / fd.path
            new_blob = disk.read_bytes() if disk.is_file() else b""
        else:
            new_blob = git_bytes(root, "show", f"{head}:{fd.path}")
        if is_binary(old_blob) or is_binary(new_blob):
            fd.binary = True
            continue
        fd.old_lines = lines_of(old_blob) if fd.status != "A" else []
        fd.new_lines = lines_of(new_blob) if fd.status != "D" else []
        if fd.path in untracked:
            fd.added = set(range(1, len(fd.new_lines) + 1))
            continue
        # both sides of a rename go in the pathspec so git pairs them instead of showing an add
        paths = [base_path, fd.path] if fd.old_path else [fd.path]
        parse_hunks(fd, git(root, "diff", "-U0", "--no-color", *rev_args, "--", *paths))
    return files


def parse_hunks(fd: FileDiff, raw: str) -> None:
    lines = raw.split("\n")
    i = 0
    while i < len(lines):
        m = HUNK_RE.match(lines[i])
        if not m:
            i += 1
            continue
        old_start = int(m.group(1))
        old_count = int(m.group(2)) if m.group(2) is not None else 1
        new_start = int(m.group(3))
        new_count = int(m.group(4)) if m.group(4) is not None else 1
        i += 1
        removed_texts: list[str] = []
        while i < len(lines) and lines[i][:1] in ("-", "+", "\\"):
            if lines[i].startswith("-"):
                removed_texts.append(lines[i][1:])
            i += 1
        fd.removed.update(range(old_start, old_start + old_count))
        fd.added.update(range(new_start, new_start + new_count))
        if removed_texts:
            key = (new_start, "before") if new_count > 0 else (new_start, "after")
            fd.removed_blocks.setdefault(key, []).extend(removed_texts)


def revision_hash(root: Path, base: str) -> str:
    """Identity of the working tree, so a changed tree gets its own reader progress."""
    h = hashlib.sha256()
    h.update(git_bytes(root, "diff", base))
    for raw in git_bytes(root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0"):
        if not raw:
            continue
        h.update(raw)
        disk = root / raw.decode("utf-8", "surrogateescape")
        if disk.is_file():
            h.update(disk.read_bytes())
    return h.hexdigest()[:16]


# ---------------------------------------------------------------- entities

TS_DECL = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:const|let|var|type|interface|enum|class|function\*?)\s+([A-Za-z_$][\w$]*)"
)
TS_METHOD = re.compile(r"^\s{2,}(?:(?:private|public|protected|static|readonly)\s+)*(?:async\s+)?\*?([A-Za-z_$][\w$]*)\s*\(")
TS_TEST = re.compile(r"^\s*(describe|it|test)\(\s*(['\"`])(.+?)\2")
PY_DECL = re.compile(r"^\s*(?:async\s+)?(def|class)\s+([A-Za-z_]\w*)")
GO_DECL = re.compile(r"^\s*(?:func|type)\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)")
RS_DECL = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:fn|struct|enum|trait|mod)\s+([A-Za-z_]\w*)")
SH_DECL = re.compile(r"^\s*(?:function\s+)?([A-Za-z_][\w.-]*)\s*\(\)\s*\{")
MD_HEAD = re.compile(r"^#{1,6}\s+(.+?)\s*$")

TS_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}


def entity_of(suffix: str, text: str) -> str | None:
    if suffix in TS_SUFFIXES:
        m = TS_TEST.match(text)
        if m:
            return f"{m.group(1)}: {m.group(3)}"
        m = TS_DECL.match(text) or TS_METHOD.match(text)
        return m.group(1) if m else None
    if suffix == ".py":
        m = PY_DECL.match(text)
        return f"{m.group(1)} {m.group(2)}" if m else None
    if suffix == ".go":
        m = GO_DECL.match(text)
        return m.group(1) if m else None
    if suffix == ".rs":
        m = RS_DECL.match(text)
        return m.group(1) if m else None
    if suffix in (".sh", ".bash", ".zsh"):
        m = SH_DECL.match(text)
        return m.group(1) if m else None
    if suffix in (".md", ".mdx"):
        m = MD_HEAD.match(text)
        return m.group(1) if m else None
    m = TS_DECL.match(text)
    if m:
        return m.group(1)
    m = PY_DECL.match(text)
    return f"{m.group(1)} {m.group(2)}" if m else None


def derive_entities(fd: FileDiff, only: set[int] | None = None) -> list[str]:
    """Names the added lines introduce, in file order, restricted to `only` when given."""
    out: list[str] = []
    seen: set[str] = set()
    suffix = Path(fd.path).suffix
    for n in sorted(fd.added):
        if only is not None and n not in only:
            continue
        text = fd.new_lines[n - 1] if n - 1 < len(fd.new_lines) else ""
        label = entity_of(suffix, text)
        if label and label not in seen:
            seen.add(label)
            out.append(label)
    return out


# ---------------------------------------------------------------- render helpers


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def blob_url(repo: str, rev: str, path: str, start: int | None = None, end: int | None = None) -> str:
    url = f"https://github.com/{repo}/blob/{rev}/{quote(path, safe='/')}"
    if start is not None:
        url += f"#L{start}" + (f"-L{end}" if end and end != start else "")
    return url


def card_stats(fd: FileDiff) -> str:
    if fd.binary:
        return '<span class="stats"><span class="nohunk">binary</span></span>'
    return f'<span class="stats"><span class="plus">+{len(fd.added)}</span> <span class="minus">-{len(fd.removed)}</span></span>'


def render_range(fd: FileDiff, side: str, start: int, end: int) -> tuple[str, str]:
    """Rendered rows and the plain text of the same range."""
    rows: list[str] = []
    plain: list[str] = []

    def row(kind: str, num: str, text: str) -> None:
        sign = {"add": "+", "del": "-", "ctx": " "}[kind]
        rows.append(
            f'<span class="row {kind}"><span class="ln">{esc(num)}</span>'
            f'<span class="sg">{sign}</span><span class="tx">{esc(text)}</span></span>'
        )
        plain.append(f"{sign} {text}")

    if side == "new":
        for n in range(start, end + 1):
            for t in fd.removed_blocks.get((n, "before"), []):
                row("del", "", t)
            row("add" if n in fd.added else "ctx", str(n), fd.new_lines[n - 1])
            for t in fd.removed_blocks.get((n, "after"), []):
                row("del", "", t)
    else:
        for n in range(start, end + 1):
            row("del" if n in fd.removed else "ctx", str(n), fd.old_lines[n - 1])
    return "".join(rows), "\n".join(plain)


# ---------------------------------------------------------------- validation


def check_spec(spec: dict) -> None:
    for key in ("title", "base", "head", "overview", "chapters"):
        if not spec.get(key):
            fail(f"spec is missing a required field: {key}")
    chapters = spec["chapters"]
    if not isinstance(chapters, list) or not 1 <= len(chapters) <= 10:
        fail(f"{len(chapters)} chapters; keep between 1 and 10")
    seen_ids: set[str] = set()
    for ch in chapters:
        for key in ("id", "title", "risk", "overview"):
            if not ch.get(key):
                fail(f"chapter {ch.get('id', '?')} is missing a required field: {key}")
        if ch["id"] in seen_ids:
            fail(f"duplicate chapter id: {ch['id']}")
        seen_ids.add(ch["id"])
        if ch["risk"] not in RISK_LABEL:
            fail(f"chapter {ch['id']}: unknown risk {ch['risk']!r}; use attention, medium, or safe")
        for f in ch.get("files", []):
            if not f.get("path"):
                fail(f"chapter {ch['id']}: a file entry has no path")
            for h in f.get("hunks", []):
                side = h.get("side", "new")
                if side not in SIDES:
                    fail(f"{f['path']}: unknown side {side!r}; use new or old")
                try:
                    start, end = int(h["start"]), int(h["end"])
                except (KeyError, TypeError, ValueError):
                    fail(f"{f['path']}: a hunk needs integer start and end")
                if start > end:
                    fail(f"{f['path']} {side} {start}-{end}: start is after end")


def check_coverage(spec: dict, files: dict[str, FileDiff]) -> dict[str, list[str]]:
    placed: dict[str, list[str]] = {}
    for ch in spec["chapters"]:
        for f in ch.get("files", []):
            placed.setdefault(f["path"], []).append(ch["id"])
    for f in spec.get("everythingElse", []):
        if f["path"] in placed:
            fail(f"{f['path']} is in everythingElse and in chapter {placed[f['path']][0]}; keep it in one place")
        placed.setdefault(f["path"], []).append("everythingElse")
    missing = sorted(set(files) - set(placed))
    extra = sorted(set(placed) - set(files))
    if missing:
        fail("changed files no chapter claims: " + ", ".join(missing))
    if extra:
        fail("placed files that are not in the diff: " + ", ".join(extra))

    shown: dict[tuple[str, str, int], str] = {}
    for ch in spec["chapters"]:
        for f in ch.get("files", []):
            for h in f.get("hunks", []):
                side = h.get("side", "new")
                for n in range(int(h["start"]), int(h["end"]) + 1):
                    key = (f["path"], side, n)
                    if key in shown:
                        fail(f"{f['path']} {side} line {n} is shown twice: chapters {shown[key]} and {ch['id']}")
                    shown[key] = ch["id"]
    return placed


# ---------------------------------------------------------------- page


def file_card(
    spec: dict,
    files: dict[str, FileDiff],
    ch_id: str,
    ch_title: str,
    f: dict,
    risk: str,
    stats: dict,
    head_label: str,
) -> str:
    repo = spec.get("repo")
    base, head = spec["base"], spec["head"]
    fd = files[f["path"]]
    fid = "f-" + slug(ch_id) + "-" + slug(f["path"])
    hunks = f.get("hunks", [])
    out: list[str] = []
    # a file split across chapters lists only the entities its own hunks introduce
    only = None
    if hunks and sum(1 for c in spec["chapters"] for g in c.get("files", []) if g["path"] == f["path"]) > 1:
        only = {n for h in hunks if h.get("side", "new") == "new" for n in range(int(h["start"]), int(h["end"]) + 1)}
    entities = f.get("entities") or derive_entities(fd, only)

    out.append(f'<div class="file" id="{fid}" data-file="{esc(f["path"])}" data-card="{fid}">')
    out.append('<div class="file-head">')
    out.append(f'<label class="read-box"><input type="checkbox" class="read" data-card="{fid}"> read</label>')
    out.append(f'<span class="status st-{fd.status}" title="{STATUS_LABEL.get(fd.status, fd.status)}">{fd.status}</span>')
    out.append(f'<code class="path">{esc(f["path"])}</code>')
    out.append(card_stats(fd))
    if fd.old_path:
        out.append(f'<span class="nohunk">was {esc(fd.old_path)}</span>')
    if repo:
        if fd.status == "D":
            link = blob_url(repo, base, fd.old_path or fd.path)
            text = f"file at {base[:8]} (deleted)"
        elif head != WORKTREE:
            link = blob_url(repo, head, fd.path)
            text = f"file at {head[:8]}"
        else:
            link = ""
            text = ""
        if link:
            out.append(f'<a class="ext" href="{esc(link)}" target="_blank" rel="noopener">{esc(text)}</a>')
    if not hunks:
        out.append('<span class="nohunk">no hunk shown</span>')
    out.append("</div>")
    if f.get("why"):
        out.append(f'<p class="why">{f["why"]}</p>')
    if entities:
        shown_entities = entities[:12]
        more = len(entities) - len(shown_entities)
        items = "".join(f"<li>{esc(e)}</li>" for e in shown_entities)
        if more > 0:
            items += f'<li class="more">+{more} more</li>'
        out.append(f'<ul class="entities">{items}</ul>')

    if hunks:
        open_attr = "" if risk == "safe" else " open"
        label = f'{len(hunks)} hunk{"s" if len(hunks) != 1 else ""}'
        out.append(f'<details class="hunks"{open_attr}><summary>{label}</summary>')
        for h in hunks:
            side = h.get("side", "new")
            start, end = int(h["start"]), int(h["end"])
            if fd.binary:
                fail(f"{f['path']}: binary file, no hunk can be shown")
            src = fd.new_lines if side == "new" else fd.old_lines
            changed = fd.added if side == "new" else fd.removed
            if start < 1 or end > len(src):
                fail(f"{f['path']} {side} {start}-{end}: outside the file (1-{len(src)})")
            touched = any(n in changed for n in range(start, end + 1))
            if side == "new" and not touched:
                touched = any(
                    (n, pos) in fd.removed_blocks for n in range(start, end + 1) for pos in ("before", "after")
                )
            if not touched:
                fail(f"{f['path']} {side} {start}-{end}: the range holds no changed line")
            stats["hunksShown"] += 1
            rows, plain = render_range(fd, side, start, end)
            where = f"In {repo} at {head_label}" if repo else f"At {head_label}"
            prompt = (
                f"{where}, explain {f['path']}:{start}-{end} ({side} side).\n"
                f"Chapter: {ch_title}.\n\n{plain}"
            )
            out.append(f'<figure class="hunk" id="{fid}-{side}-{start}">')
            caption = [
                f'<span class="loc">{esc(f["path"])}:{start}-{end}{" (old side)" if side == "old" else ""}</span>'
            ]
            if repo:
                if side == "old":
                    link = blob_url(repo, base, fd.old_path or fd.path, start, end)
                elif head != WORKTREE:
                    link = blob_url(repo, head, f["path"], start, end)
                else:
                    link = ""
                if link:
                    caption.append(f'<a class="ext" href="{esc(link)}" target="_blank" rel="noopener">source</a>')
            caption.append(f'<button type="button" class="copy" data-prompt="{esc(prompt)}">Copy as prompt</button>')
            out.append(f"<figcaption>{''.join(caption)}</figcaption>")
            out.append(f'<pre class="code"><code>{rows}</code></pre>')
            if h.get("why"):
                out.append(f'<p class="why">{h["why"]}</p>')
            out.append("</figure>")
        out.append("</details>")
    out.append("</div>")
    return "".join(out)


def build_body(spec: dict, root: Path) -> tuple[str, dict]:
    base, head = spec["base"], spec["head"]
    check_spec(spec)
    git_bytes(root, "rev-parse", "--verify", f"{base}^{{commit}}")
    if head != WORKTREE:
        git_bytes(root, "rev-parse", "--verify", f"{head}^{{commit}}")
    files = load_changed_files(root, base, head)
    placed = check_coverage(spec, files)

    head_label = "working tree" if head == WORKTREE else head[:8]
    storage_id = revision_hash(root, base) if head == WORKTREE else head[:16]
    chapters = spec["chapters"]
    stats = {
        "filesChanged": len(files),
        "filesPlaced": len(placed),
        "everythingElse": len(spec.get("everythingElse", [])),
        "linesAdded": sum(len(fd.added) for fd in files.values()),
        "linesRemoved": sum(len(fd.removed) for fd in files.values()),
        "hunksShown": 0,
        "chapters": len(chapters),
        "attentionChapters": sum(1 for ch in chapters if ch["risk"] == "attention"),
    }

    # chapters render first: the overview strip reports the hunk count this pass derives
    tour: list[str] = []
    for idx, ch in enumerate(chapters, start=1):
        risk = ch["risk"]
        tour.append(
            f'<article class="chapter" id="ch-{esc(ch["id"])}" data-chapter="{esc(ch["id"])}" data-risk="{esc(risk)}">'
        )
        tour.append(
            f'<header class="chapter-head"><span class="num">{idx}</span><div class="chapter-title">'
            f'<h3>{esc(ch["title"])}</h3><div class="chapter-meta">'
            f'<span class="chip risk-{esc(risk)}">{RISK_LABEL[risk]}</span>'
            f'<span class="progress" data-chapter-progress></span></div></div></header>'
        )
        tour.append(f'<div class="overview">{ch["overview"]}</div>')
        for f in ch.get("files", []):
            tour.append(file_card(spec, files, ch["id"], ch["title"], f, risk, stats, head_label))
        tour.append("</article>")

    o: list[str] = []
    o.append(
        f'<div class="wrap" data-storage-key="walkthrough:{esc(storage_id)}" '
        f'data-head-label="{esc(head_label)}" data-doc-title="{esc(spec["title"])}">'
    )

    # ---- header
    built = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    o.append('<header class="top">')
    o.append('<p class="eyebrow">Walkthrough</p>')
    o.append(f"<h1>{esc(spec['title'])}</h1>")
    o.append(
        f'<div class="banner"><b>Revision</b><span>Built against <code>{esc(head_label)}</code> '
        f'from base <code>{esc(base[:8])}</code> on {esc(built)}. Every line number below was checked '
        f"against that diff at build time. Rebuild after the branch moves.</span></div>"
    )
    o.append('<div class="controls">')
    o.append('<span class="prog" data-progress></span>')
    o.append('<button type="button" class="btn primary" data-continue>Continue reading</button>')
    o.append('<button type="button" class="btn" data-changed-only aria-pressed="false">Changed lines only</button>')
    o.append('<button type="button" class="btn" data-reset>Reset progress</button>')
    o.append('<div class="bar"><i data-bar></i></div>')
    o.append("</div></header>")

    # ---- nav
    nav = [("overview", "Overview")]
    if spec.get("focus"):
        nav.append(("focus", "Where to focus"))
    if spec.get("intuition"):
        nav.append(("intuition", "Intuition"))
    if spec.get("background"):
        nav.append(("background", "Background"))
    nav.append(("tour", "Walkthrough"))
    nav.append(("everything-else", "Everything else"))
    if spec.get("verify"):
        nav.append(("verify", "Verify"))
    nav.append(("notes", "Notes"))
    o.append('<nav class="toc" aria-label="Sections">')
    o.extend(f'<a href="#{i}">{esc(t)}</a>' for i, t in nav)
    o.append("</nav>")

    # ---- overview
    o.append('<section id="overview"><h2>Overview</h2>')
    o.append(spec["overview"])
    o.append('<div class="strip">')
    o.append(
        f'<div class="stat"><div class="k">Revision</div><div class="v mono">{esc(head_label)}</div>'
        f'<div class="s">base {esc(base[:8])}</div></div>'
    )
    o.append(
        f'<div class="stat"><div class="k">Files changed</div><div class="v">{stats["filesChanged"]}</div>'
        f'<div class="s">{stats["linesAdded"]} added, {stats["linesRemoved"]} removed</div></div>'
    )
    o.append(
        f'<div class="stat"><div class="k">Chapters</div><div class="v">{stats["chapters"]}</div>'
        f'<div class="s">{stats["attentionChapters"]} to read closely</div></div>'
    )
    o.append(
        f'<div class="stat"><div class="k">Hunks shown</div><div class="v">{stats["hunksShown"]}</div>'
        f'<div class="s">{stats["everythingElse"]} files in everything else</div></div>'
    )
    o.append("</div></section>")

    # ---- focus, intuition, background
    if spec.get("focus"):
        o.append('<section id="focus"><h2>Where to focus</h2>')
        o.append('<p class="lede">Start here if you read nothing else.</p><ol class="focus">')
        o.extend(f"<li>{item}</li>" for item in spec["focus"])
        o.append("</ol></section>")
    if spec.get("intuition"):
        o.append('<section id="intuition"><h2>Intuition</h2>')
        o.append(spec["intuition"])
        o.append("</section>")
    if spec.get("background"):
        o.append('<section id="background"><h2>Background</h2>')
        o.append(spec["background"])
        o.append("</section>")

    # ---- tour
    o.append('<section id="tour"><h2>Walkthrough</h2>')
    o.append(
        '<p class="lede">Chapters are cut by concept in reading order. Each one shows only the hunks its prose '
        "makes a claim about; the other files in it appear as a card with the names they add. Mark a card read to "
        "track where you are.</p>"
    )
    o.extend(tour)
    o.append("</section>")

    # ---- everything else
    ee = spec.get("everythingElse", [])
    o.append('<section id="everything-else"><h2>Everything else</h2>')
    if ee:
        o.append('<p class="lede">Changed files no chapter claims. Listed so the coverage count stays honest.</p>')
        for f in ee:
            fd = files[f["path"]]
            eid = "f-everything-else-" + slug(f["path"])
            o.append(f'<div class="file" id="{eid}" data-file="{esc(f["path"])}" data-card="{eid}"><div class="file-head">')
            o.append(f'<label class="read-box"><input type="checkbox" class="read" data-card="{eid}"> read</label>')
            o.append(f'<span class="status st-{fd.status}">{fd.status}</span><code class="path">{esc(f["path"])}</code>')
            o.append(card_stats(fd))
            o.append("</div>")
            if f.get("why"):
                o.append(f'<p class="why">{f["why"]}</p>')
            entities = derive_entities(fd)
            if entities:
                o.append("<ul class=\"entities\">" + "".join(f"<li>{esc(e)}</li>" for e in entities[:12]) + "</ul>")
            o.append("</div>")
    else:
        o.append('<p class="lede">Empty on purpose: every changed file is claimed by a chapter above.</p>')
    o.append(
        f'<p class="count">{stats["filesPlaced"]} of {stats["filesChanged"]} changed files placed across '
        f'{stats["chapters"]} chapters; {stats["everythingElse"]} here.</p>'
    )
    o.append("</section>")

    # ---- verify
    verify = spec.get("verify") or {}
    if verify:
        o.append('<section id="verify"><h2>Verify</h2>')
        ran = verify.get("ran", [])
        if ran:
            o.append('<p class="lede">Commands that were run against this revision, with their exit codes.</p>')
            o.append('<div class="scroll"><table><thead><tr><th>Command</th><th>Exit</th><th>Result</th><th>Tree</th></tr></thead><tbody>')
            for r in ran:
                code = r.get("exit")
                if code is None:
                    chip = '<span class="chip exit-none">not run</span>'
                else:
                    cls = "exit-ok" if int(code) == 0 else "exit-bad"
                    chip = f'<span class="chip {cls}">{int(code)}</span>'
                o.append(
                    f'<tr><td><code>{esc(str(r.get("cmd", "")))}</code></td><td>{chip}</td>'
                    f'<td>{esc(str(r.get("summary", "")))}</td><td><code>{esc(str(r.get("tree", "")))}</code></td></tr>'
                )
            o.append("</tbody></table></div>")
        manual = verify.get("manual", [])
        if manual:
            o.append("<h3>Check it yourself</h3><ul class=\"plain\">")
            o.extend(f"<li>{item}</li>" for item in manual)
            o.append("</ul>")
        o.append("</section>")

    # ---- notes
    o.append('<section id="notes" class="notes"><h2>Notes</h2>')
    o.append(
        '<p class="lede">Kept in this browser only. "Copy feedback" turns your notes into Markdown you can paste '
        "back into the chat.</p>"
    )
    for ch in chapters:
        o.append('<div class="note">')
        o.append(f'<label for="note-{esc(ch["id"])}">{esc(ch["title"])}</label>')
        o.append(
            f'<textarea id="note-{esc(ch["id"])}" data-note="{esc(ch["id"])}" '
            f'placeholder="What to change, what to explain again, what you approve."></textarea>'
        )
        o.append("</div>")
    o.append('<div class="note global"><label for="note-general">Anything else</label>')
    o.append('<textarea id="note-general" data-note="general" placeholder="Notes that belong to no chapter."></textarea></div>')
    o.append('<p><button type="button" class="btn primary" data-export>Copy feedback</button> ')
    o.append('<span class="count" data-export-status></span></p>')
    o.append("<pre data-export-preview hidden></pre>")
    o.append("</section>")

    o.append(
        f'<footer>Built from review-tour.json against {esc(head_label)} on {esc(built)}. '
        f"Line numbers, counts, and file coverage are derived from git, not typed.</footer>"
    )
    o.append("</div>")

    return "\n".join(o), stats


# ---------------------------------------------------------------- assembly


def slice_between(text: str, start: str, end: str, where: str) -> str:
    a, b = text.find(start), text.find(end)
    if a < 0 or b < a:
        fail(f"{where}: markers {start} / {end} missing or out of order")
    return text[a + len(start) : b]


def replace_between(text: str, start: str, end: str, body: str, where: str) -> str:
    a, b = text.find(start), text.find(end)
    if a < 0 or b < a:
        fail(f"{where}: markers {start} / {end} missing or out of order")
    return text[: a + len(start)] + "\n" + body + "\n" + text[b:]


def main() -> None:
    ap = argparse.ArgumentParser(description="Render a walkthrough page from review-tour.json.")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--out", required=True, help="full HTML document")
    ap.add_argument("--fragment", default=None, help="same content without the document wrappers")
    ap.add_argument("--data-out", default=None, help="write the derived stats as JSON here")
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    args = ap.parse_args()

    root = Path(args.repo_root).resolve()
    try:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        fail(f"cannot read the spec {args.spec}: {e}")
    template = Path(args.template)
    if not template.is_file():
        fail(f"template not found: {template}")
    shell = template.read_text(encoding="utf-8")

    body, stats = build_body(spec, root)
    title = esc(spec["title"])
    style = slice_between(shell, STYLE_START, STYLE_END, str(template)).strip()
    script = slice_between(shell, SCRIPT_START, SCRIPT_END, str(template)).strip()

    document = replace_between(shell, TITLE_START, TITLE_END, f"<title>{title}</title>", str(template))
    document = replace_between(document, BODY_START, BODY_END, body, str(template))
    fragment = "\n".join([f"<title>{title}</title>", style, body, script]) + "\n"

    # everything validated: write the outputs last, so a failed build leaves them untouched
    Path(args.out).write_text(document, encoding="utf-8")
    if args.fragment:
        Path(args.fragment).write_text(fragment, encoding="utf-8")
    if args.data_out:
        Path(args.data_out).write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(
        f"build_tour: ok files={stats['filesChanged']} placed={stats['filesPlaced']} "
        f"else={stats['everythingElse']} hunks={stats['hunksShown']} chapters={stats['chapters']}"
    )


if __name__ == "__main__":
    main()
