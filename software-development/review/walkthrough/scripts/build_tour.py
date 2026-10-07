#!/usr/bin/env python3
"""Render a walkthrough page from a review-tour.json spec and the real git diff.

Reads the spec, resolves the diff between `base` and `head` (a sha, or the literal
"worktree"), checks every claim the spec makes about the diff, and renders the whole page
from the spec's prose plus the shell in templates/tour-shell.html.

Usage:
    build_tour.py --spec review-tour.json --repo-root . --out tour.html
                  [--fragment tour.fragment.html] [--data-out stats.json]
                  [--template path/to/tour-shell.html] [--seed N]
    build_tour.py --repo-root . --print-worktree-hash <base>

Exit status 1 with a message naming the defect on any validation failure; no output file is
touched when a build fails. Stdlib only, Python 3.10 or newer.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import keyword
import math
import re
import secrets
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree

WORKTREE = "worktree"
SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = SKILL_DIR / "templates" / "tour-shell.html"
LIB_DIR = SKILL_DIR / "lib"
LIB_STYLE, LIB_SCRIPT = "<!-- LIB:STYLE -->", "<!-- LIB:SCRIPT -->"
SHEET_STYLE, SHEET_SCRIPT = "<!-- SHEET:STYLE -->", "<!-- SHEET:SCRIPT -->"

sys.path.insert(0, str(LIB_DIR))
import digest  # noqa: E402  (needs sys.path set up above)
import dock  # noqa: E402
import gitfacts  # noqa: E402
import pagelib  # noqa: E402
import sheet  # noqa: E402
import voice  # noqa: E402

fail = pagelib.fail
esc = pagelib.esc
slug = pagelib.slug
sanitize_prose = pagelib.sanitize_prose

RISK_LABEL = {"attention": "read closely", "medium": "read once", "safe": "skim"}
READ_RISKS = ("attention", "medium")
SIDES = ("new", "old")
STATUS_LABEL = {"A": "added", "M": "modified", "D": "deleted", "R": "renamed", "C": "copied", "T": "type change"}
PR_LENS_SCHEMA = "0.2.0"
PR_LENS_MAX_ASSETS = 256
PR_LENS_MAX_BYTES = 16 * 1024 * 1024
PR_LENS_LENSES = {"architecture", "data-flow"}
PR_LENS_THEMES = {"light", "dark"}


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


@dataclass
class PrLensView:
    lens: str
    view: str | None
    title: str
    width: int
    height: int
    themes: dict[str, str]


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


SKIP_ENTITY_SUFFIXES = {".html", ".htm", ".css", ".json", ".txt"}


def derive_entities(fd: FileDiff, only: set[int] | None = None) -> list[str]:
    """Names the added lines introduce, in file order, restricted to `only` when given."""
    suffix = Path(fd.path).suffix
    if suffix in SKIP_ENTITY_SUFFIXES:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for n in sorted(fd.added):
        if only is not None and n not in only:
            continue
        text = fd.new_lines[n - 1] if n - 1 < len(fd.new_lines) else ""
        label = entity_of(suffix, text)
        if not label or label in seen:
            continue
        if len(label) < 3 or set(label) <= {"$", "_"}:
            continue
        seen.add(label)
        out.append(label)
    # a name list dominated by short names reads as noise, not a summary
    if out and sum(1 for n in out if len(n) < 4) > len(out) / 3:
        return []
    return out


# ---------------------------------------------------------------- render helpers


def blob_url(repo: str, rev: str, path: str, start: int | None = None, end: int | None = None) -> str:
    url = f"https://github.com/{repo}/blob/{rev}/{quote(path, safe='/')}"
    if start is not None:
        url += f"#L{start}" + (f"-L{end}" if end and end != start else "")
    return url


def card_stats(fd: FileDiff) -> str:
    if fd.binary:
        return '<span class="stats"><span class="nohunk">binary</span></span>'
    return f'<span class="stats"><span class="plus">+{len(fd.added)}</span> <span class="minus">-{len(fd.removed)}</span></span>'


# ---------------------------------------------------------------- syntax highlighting

_PY_KW = sorted(set(keyword.kwlist) | {"match", "case", "type", "_"}, key=len, reverse=True)
_PY_PATTERN = re.compile(
    r"(?P<COM>#[^\n]*)"
    r"|(?P<STR>(?:[fFrRbBuU]{1,2})?(?:'''.*?'''|\"\"\".*?\"\"\"|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"))"
    r"|(?P<AT>@[A-Za-z_][\w.]*)"
    r"|(?P<DEFKW>\bdef\b)\s+(?P<DEFNAME>[A-Za-z_]\w*)"
    r"|(?P<CLASSKW>\bclass\b)\s+(?P<CLASSNAME>[A-Za-z_]\w*)"
    r"|(?P<KW>\b(?:" + "|".join(_PY_KW) + r")\b)"
    r"|(?P<NUM>\b\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d+)?[jJ]?\b)"
)
_PY_CLASS = {
    "COM": "cm", "STR": "st", "AT": "at",
    "DEFKW": "kw", "DEFNAME": "fn", "CLASSKW": "kw", "CLASSNAME": "ty",
    "KW": "kw", "NUM": "nu",
}

_JS_KW = sorted(
    [
        "const", "let", "var", "function", "return", "if", "else", "for", "while", "class", "extends",
        "import", "export", "from", "default", "new", "this", "async", "await", "yield", "try", "catch",
        "finally", "throw", "typeof", "instanceof", "of", "in", "null", "undefined", "true", "false",
        "interface", "type", "enum", "implements", "readonly",
    ],
    key=len, reverse=True,
)
_JS_PATTERN = re.compile(
    r"(?P<COM>//[^\n]*|/\*.*?\*/)"
    r"|(?P<STR>`(?:\\.|[^`\\])*`|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\")"
    r"|(?P<KW>\b(?:" + "|".join(_JS_KW) + r")\b)"
    r"|(?P<NUM>\b0[xX][0-9a-fA-F]+\b|\b\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?\b)"
)
_JS_CLASS = {"COM": "cm", "STR": "st", "KW": "kw", "NUM": "nu"}

_GO_KW = sorted(
    [
        "break", "case", "chan", "const", "continue", "default", "defer", "else", "fallthrough", "for",
        "func", "go", "goto", "if", "import", "interface", "map", "package", "range", "return", "select",
        "struct", "switch", "type", "var",
    ],
    key=len, reverse=True,
)
_GO_PATTERN = re.compile(
    r"(?P<COM>//[^\n]*|/\*.*?\*/)"
    r"|(?P<STR>`[^`]*`|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')"
    r"|(?P<KW>\b(?:" + "|".join(_GO_KW) + r")\b)"
    r"|(?P<NUM>\b0[xX][0-9a-fA-F]+\b|\b\d[\d_]*(?:\.\d+)?\b)"
)
_GO_CLASS = {"COM": "cm", "STR": "st", "KW": "kw", "NUM": "nu"}

_RS_KW = sorted(
    [
        "as", "async", "await", "break", "const", "continue", "crate", "dyn", "else", "enum", "extern",
        "false", "fn", "for", "if", "impl", "in", "let", "loop", "match", "mod", "move", "mut", "pub",
        "ref", "return", "self", "Self", "static", "struct", "super", "trait", "true", "type", "unsafe",
        "use", "where", "while",
    ],
    key=len, reverse=True,
)
_RS_PATTERN = re.compile(
    r"(?P<COM>//[^\n]*|/\*.*?\*/)"
    r"|(?P<STR>r?\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])')"
    r"|(?P<KW>\b(?:" + "|".join(_RS_KW) + r")\b)"
    r"|(?P<NUM>\b0[xX][0-9a-fA-F_]+\b|\b\d[\d_]*(?:\.\d+)?\b)"
)
_RS_CLASS = {"COM": "cm", "STR": "st", "KW": "kw", "NUM": "nu"}

_SH_KW = sorted(
    [
        "if", "then", "else", "elif", "fi", "for", "while", "do", "done", "case", "esac", "function",
        "in", "until", "select", "break", "continue", "return", "exit", "local", "export", "readonly",
        "declare",
    ],
    key=len, reverse=True,
)
_SH_PATTERN = re.compile(
    r"(?P<COM>#[^\n]*)"
    r"|(?P<STR>\"(?:\\.|[^\"\\])*\"|'[^']*')"
    r"|(?P<KW>\b(?:" + "|".join(_SH_KW) + r")\b)"
)
_SH_CLASS = {"COM": "cm", "STR": "st", "KW": "kw"}

_JSON_PATTERN = re.compile(
    r"(?P<STR>\"(?:\\.|[^\"\\])*\")"
    r"|(?P<KW>\b(?:true|false|null)\b)"
    r"|(?P<NUM>-?\b\d[\d.]*(?:[eE][+-]?\d+)?\b)"
)
_JSON_CLASS = {"STR": "st", "KW": "kw", "NUM": "nu"}

_CSS_PATTERN = re.compile(
    r"(?P<COM>/\*.*?\*/)"
    r"|(?P<STR>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')"
    r"|(?P<NUM>-?\b\d[\d.]*(?:%|px|em|rem|vh|vw|s|ms)?\b)"
)
_CSS_CLASS = {"COM": "cm", "STR": "st", "NUM": "nu"}

_HTML_PATTERN = re.compile(
    r"(?P<COM><!--.*?-->)"
    r"|(?:</?)(?P<TAGNAME>[A-Za-z][\w:-]*)"
    r"|(?P<STR>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')"
    r"|(?P<AT>[A-Za-z_:][\w:.-]*)(?=\s*=)"
)
_HTML_CLASS = {"COM": "cm", "TAGNAME": "ty", "STR": "st", "AT": "at"}

_MD_PATTERN = re.compile(
    r"(?P<FENCE>^```.*$)"
    r"|(?P<HEAD>^#{1,6}\s.*$)"
    r"|(?P<LINK>\[[^\]]*\]\([^)]*\))"
    r"|(?P<CODE>`[^`]*`)"
)
_MD_CLASS = {"FENCE": "cm", "HEAD": "kw", "LINK": "fn", "CODE": "st"}

_YAML_PATTERN = re.compile(
    r"(?P<COM>#[^\n]*)"
    r"|(?P<STR>\"(?:\\.|[^\"\\])*\"|'(?:[^']|'')*')"
    r"|^\s*(?P<KEY>[\w.-]+)(?=\s*:)"
)
_YAML_CLASS = {"COM": "cm", "STR": "st", "KEY": "at"}

_TOML_PATTERN = re.compile(
    r"(?P<COM>#[^\n]*)"
    r"|(?P<STR>\"\"\".*?\"\"\"|'''.*?'''|\"(?:\\.|[^\"\\])*\"|'[^']*')"
    r"|(?P<HEAD>^\s*\[[^\]]*\]\s*$)"
    r"|^\s*(?P<KEY>[A-Za-z0-9_.-]+)(?=\s*=)"
)
_TOML_CLASS = {"COM": "cm", "STR": "st", "HEAD": "ty", "KEY": "at"}

_SQL_KW = sorted(
    [
        "select", "from", "where", "insert", "into", "values", "update", "set", "delete", "create",
        "table", "alter", "drop", "join", "left", "right", "inner", "outer", "on", "group", "by",
        "order", "having", "limit", "as", "and", "or", "not", "null", "is", "in", "like", "distinct",
        "union", "all", "case", "when", "then", "else", "end", "primary", "key", "foreign",
        "references", "default", "index", "view", "with",
    ],
    key=len, reverse=True,
)
_SQL_PATTERN = re.compile(
    r"(?P<COM>--[^\n]*|/\*.*?\*/)"
    r"|(?P<STR>'(?:[^']|'')*')"
    r"|(?P<KW>\b(?:" + "|".join(_SQL_KW) + r")\b)"
    r"|(?P<NUM>\b\d[\d.]*\b)",
    re.IGNORECASE,
)
_SQL_CLASS = {"COM": "cm", "STR": "st", "KW": "kw", "NUM": "nu"}

_MAKE_KW = sorted(
    ["ifeq", "ifneq", "ifdef", "ifndef", "else", "endif", "include", "export", "override", "define", "endef"],
    key=len, reverse=True,
)
_MAKE_PATTERN = re.compile(
    r"(?P<COM>#[^\n]*)"
    r"|(?P<VAR>\$[({][^)}]*[)}])"
    r"|(?P<TARGET>^[^\s:#][^:#]*)(?=\s*:(?!=))"
    r"|(?P<KW>\b(?:" + "|".join(_MAKE_KW) + r")\b)"
)
_MAKE_CLASS = {"COM": "cm", "VAR": "at", "TARGET": "ty", "KW": "kw"}

_DOCKER_KW = sorted(
    [
        "FROM", "RUN", "CMD", "COPY", "ADD", "ENV", "WORKDIR", "EXPOSE", "VOLUME", "USER", "ENTRYPOINT",
        "ARG", "LABEL", "MAINTAINER", "SHELL", "ONBUILD", "STOPSIGNAL", "HEALTHCHECK",
    ],
    key=len, reverse=True,
)
_DOCKER_PATTERN = re.compile(
    r"(?P<COM>#[^\n]*)"
    r"|(?P<STR>\"(?:\\.|[^\"\\])*\"|'[^']*')"
    r"|(?P<KW>^\s*(?:" + "|".join(_DOCKER_KW) + r")\b)"
)
_DOCKER_CLASS = {"COM": "cm", "STR": "st", "KW": "kw"}

_LANG_SPECS: dict[str, tuple[re.Pattern, dict[str, str]]] = {
    "python": (_PY_PATTERN, _PY_CLASS),
    "js": (_JS_PATTERN, _JS_CLASS),
    "go": (_GO_PATTERN, _GO_CLASS),
    "rust": (_RS_PATTERN, _RS_CLASS),
    "shell": (_SH_PATTERN, _SH_CLASS),
    "json": (_JSON_PATTERN, _JSON_CLASS),
    "css": (_CSS_PATTERN, _CSS_CLASS),
    "html": (_HTML_PATTERN, _HTML_CLASS),
    "markdown": (_MD_PATTERN, _MD_CLASS),
    "yaml": (_YAML_PATTERN, _YAML_CLASS),
    "toml": (_TOML_PATTERN, _TOML_CLASS),
    "sql": (_SQL_PATTERN, _SQL_CLASS),
    "makefile": (_MAKE_PATTERN, _MAKE_CLASS),
    "dockerfile": (_DOCKER_PATTERN, _DOCKER_CLASS),
}

_EXT_LANG = {
    ".py": "python", ".pyi": "python",
    ".js": "js", ".mjs": "js", ".cjs": "js", ".jsx": "js", ".ts": "js", ".tsx": "js",
    ".go": "go",
    ".rs": "rust",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".json": "json",
    ".css": "css",
    ".html": "html", ".htm": "html",
    ".md": "markdown", ".mdx": "markdown",
    ".yml": "yaml", ".yaml": "yaml",
    ".toml": "toml",
    ".sql": "sql",
}
_BASENAME_LANG = {"Makefile": "makefile", "GNUmakefile": "makefile", "makefile": "makefile", "Dockerfile": "dockerfile"}


def detect_lang(path: str, first_line: str) -> str:
    name = Path(path).name
    if name in _BASENAME_LANG:
        return _BASENAME_LANG[name]
    suffix = Path(path).suffix
    if suffix in _EXT_LANG:
        return _EXT_LANG[suffix]
    if not suffix and first_line.startswith("#!") and "sh" in first_line:
        return "shell"
    return "unknown"


def _emit_match(text: str, m: re.Match, class_of: dict[str, str]) -> str:
    """A match may carry several named groups at once (a keyword plus the name after it); render
    each tagged span in position order and the untagged text between them as escaped plain text."""
    spans: list[tuple[int, int, str]] = []
    for name in m.re.groupindex:
        cls = class_of.get(name)
        if not cls:
            continue
        s = m.start(name)
        if s == -1:
            continue
        spans.append((s, m.end(name), cls))
    spans.sort()
    out: list[str] = []
    cur = m.start()
    for s, e, cls in spans:
        if s > cur:
            out.append(esc(text[cur:s]))
        out.append(f'<span class="tk-{cls}">{esc(text[s:e])}</span>')
        cur = e
    if cur < m.end():
        out.append(esc(text[cur:m.end()]))
    return "".join(out)


def highlight(text: str, lang: str) -> str:
    """Line-based, best-effort syntax highlighting. Escaped HTML with `<span class="tk-X">`
    wrappers around recognized tokens; everything else escaped as plain text. Never raises: an
    unrecognized language, or a line a pattern doesn't fully parse, still comes back escaped."""
    spec = _LANG_SPECS.get(lang)
    if spec is None:
        return esc(text)
    pattern, class_of = spec
    out: list[str] = []
    pos = 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            out.append(esc(text[pos : m.start()]))
        out.append(_emit_match(text, m, class_of))
        pos = m.end()
    if pos < len(text):
        out.append(esc(text[pos:]))
    return "".join(out)


# ---------------------------------------------------------------- render helpers (continued)


def render_range(fd: FileDiff, side: str, start: int, end: int) -> tuple[str, str]:
    """Rendered rows and the plain text of the same range."""
    rows: list[str] = []
    plain: list[str] = []
    src = fd.new_lines if side == "new" else fd.old_lines
    lang = detect_lang(fd.path, src[0] if src else "")

    def row(kind: str, num: str, text: str) -> None:
        sign = {"add": "+", "del": "-", "ctx": " "}[kind]
        rows.append(
            f'<span class="row {kind}"><span class="ln">{esc(num)}</span>'
            f'<span class="sg">{sign}</span><span class="tx">{highlight(text, lang)}</span></span>'
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


# ---------------------------------------------------------------- PR Lens


def json_no_duplicates(text: str, label: str, numbers_as_float: bool = False) -> dict:
    def object_pairs(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError(f"duplicate key {key!r}")
            out[key] = value
        return out

    try:
        number_options = {"parse_int": float, "parse_float": float} if numbers_as_float else {}
        value = json.loads(text, object_pairs_hook=object_pairs, **number_options)
    except (json.JSONDecodeError, ValueError) as e:
        fail(f"cannot read {label}: {e}")
    if not isinstance(value, dict):
        fail(f"{label} must contain a JSON object")
    return value


def canonical_json(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            fail("PR Lens graph contains a non-finite number")
        if value == 0:
            return "0"
        raw = repr(value).lower()
        magnitude = abs(value)
        if 1e-6 <= magnitude < 1e21:
            fixed = format(Decimal(raw), "f")
            return fixed.rstrip("0").rstrip(".") if "." in fixed else fixed
        mantissa, exponent = raw.split("e")
        mantissa = mantissa.rstrip("0").rstrip(".")
        power = int(exponent)
        return f"{mantissa}e{'+' if power >= 0 else ''}{power}"
    if isinstance(value, list):
        return "[" + ",".join(canonical_json(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            f"{canonical_json(key)}:{canonical_json(value[key])}" for key in sorted(value)
        ) + "}"
    fail(f"PR Lens graph contains unsupported JSON value {type(value).__name__}")


def local_path(base: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        fail(f"{label} must be a non-empty relative path")
    if "\\" in value or "://" in value or value.startswith(("/", "~")):
        fail(f"{label} must be a POSIX relative path")
    parts = Path(value).parts
    if any(part in ("", ".", "..") for part in parts):
        fail(f"{label} must not contain . or .. segments")
    try:
        resolved = (base / value).resolve(strict=True)
        resolved.relative_to(base.resolve())
    except (OSError, ValueError):
        fail(f"{label} escapes its containing directory or does not exist: {value}")
    return resolved


def validate_svg(raw: bytes, label: str) -> None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        fail(f"unsafe SVG {label}: not UTF-8")
    lowered = text.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        fail(f"unsafe SVG {label}: DTDs and entities are not allowed")
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as e:
        fail(f"unsafe SVG {label}: malformed XML: {e}")

    def local(name: str) -> str:
        return name.rsplit("}", 1)[-1].lower()

    if local(root.tag) != "svg":
        fail(f"unsafe SVG {label}: root element is not svg")
    blocked = {"script", "style", "foreignobject", "iframe", "object", "embed", "image", "audio", "video", "link"}
    for element in root.iter():
        if local(element.tag) in blocked:
            fail(f"unsafe SVG {label}: <{local(element.tag)}> is not allowed")
        for name, value in element.attrib.items():
            attr = local(name)
            candidate = value.strip().lower()
            if attr.startswith("on"):
                fail(f"unsafe SVG {label}: event attributes are not allowed")
            if attr in {"href", "src"} and not candidate.startswith("#"):
                fail(f"unsafe SVG {label}: external references are not allowed")
            if attr == "style" and any(
                token in candidate for token in ("javascript:", "https:", "http:", "data:", "@import")
            ):
                fail(f"unsafe SVG {label}: external or executable content is not allowed")
            for match in re.finditer(r"url\(([^)]*)\)", candidate):
                target = match.group(1).strip(" \t\r\n\"'")
                if not target.startswith("#"):
                    fail(f"unsafe SVG {label}: external url() references are not allowed")


def flatten_graph_views(views: object, lenses: set[str]) -> list[tuple[str, str | None, str]]:
    if not isinstance(views, list):
        fail("PR Lens graph views must be an array")
    out: list[tuple[str, str | None, str]] = []

    def visit(items: list) -> None:
        for view in items:
            if not isinstance(view, dict):
                fail("PR Lens graph view must be an object")
            lens, view_id, title = view.get("lens"), view.get("id"), view.get("title")
            if lens not in lenses or not isinstance(view_id, str) or not isinstance(title, str):
                fail("PR Lens graph view needs a declared lens, id, and title")
            out.append((lens, view_id, title))
            children = view.get("children", [])
            if not isinstance(children, list):
                fail(f"PR Lens graph view {view_id}: children must be an array")
            visit(children)

    visit(views)
    return out


def load_pr_lens(spec: dict, spec_dir: Path, root: Path) -> list[PrLensView]:
    config = spec.get("prLens")
    if not isinstance(config, dict):
        fail("spec is missing required prLens graph and manifest paths")
    graph_path = local_path(spec_dir, config.get("graph"), "prLens.graph")
    manifest_path = local_path(spec_dir, config.get("manifest"), "prLens.manifest")
    graph = json_no_duplicates(
        graph_path.read_text(encoding="utf-8"), "PR Lens graph", numbers_as_float=True
    )
    manifest = json_no_duplicates(manifest_path.read_text(encoding="utf-8"), "PR Lens manifest")

    if graph.get("schemaVersion") != PR_LENS_SCHEMA or graph.get("kind") != "graph":
        fail(f"PR Lens graph must be a {PR_LENS_SCHEMA} graph document")
    if manifest.get("schemaVersion") != PR_LENS_SCHEMA or manifest.get("kind") != "render-manifest":
        fail(f"PR Lens manifest must be a {PR_LENS_SCHEMA} render-manifest")
    lenses_raw = graph.get("lenses")
    if not isinstance(lenses_raw, list) or not lenses_raw or any(lens not in PR_LENS_LENSES for lens in lenses_raw):
        fail("PR Lens graph lenses must contain architecture or data-flow")
    lenses = set(lenses_raw)

    provenance = graph.get("provenance")
    if not isinstance(provenance, dict):
        fail("PR Lens graph is missing provenance")
    base_sha = (provenance.get("base") or {}).get("sha") if isinstance(provenance.get("base"), dict) else None
    head_sha = (provenance.get("head") or {}).get("sha") if isinstance(provenance.get("head"), dict) else None
    expected_head = git(root, "rev-parse", "HEAD").strip() if spec["head"] == WORKTREE else spec["head"]
    if base_sha != spec["base"] or head_sha != expected_head:
        fail("PR Lens graph provenance does not match the walkthrough revision")
    manifest_graph = manifest.get("graph")
    if not isinstance(manifest_graph, dict) or manifest_graph.get("headSha") != head_sha:
        fail("PR Lens manifest headSha does not match its graph")
    graph_hash = manifest_graph.get("contentHash")
    if not isinstance(graph_hash, str) or not re.fullmatch(r"[0-9a-f]{16,64}", graph_hash):
        fail("PR Lens manifest graph contentHash is invalid")
    actual_graph_hash = hashlib.sha256(canonical_json(graph).encode("utf-8")).hexdigest()
    if not actual_graph_hash.startswith(graph_hash):
        fail("PR Lens manifest graph contentHash does not match drawn.graph.json")
    if spec["head"] == WORKTREE:
        recorded = config.get("worktreeHash")
        if recorded != revision_hash(root, spec["base"]):
            fail("prLens.worktreeHash does not match the current working tree")

    graph_views = graph.get("views", [])
    if graph_views:
        expected = flatten_graph_views(graph_views, lenses)
    else:
        flows = graph.get("flows", [])
        expected = [
            (lens, None, f'{graph.get("title", "PR Lens")} - {lens}')
            for lens in lenses_raw
            if lens != "data-flow" or flows
        ]
    expected_keys = [(lens, view) for lens, view, _ in expected]
    if len(expected_keys) != len(set(expected_keys)):
        fail("PR Lens graph contains duplicate logical views")

    assets = manifest.get("assets")
    if not isinstance(assets, list) or not 1 <= len(assets) <= PR_LENS_MAX_ASSETS:
        fail(f"PR Lens manifest assets must contain 1 to {PR_LENS_MAX_ASSETS} entries")
    by_key: dict[tuple[str, str | None], dict[str, tuple[dict, str]]] = {}
    ids: set[str] = set()
    paths: set[str] = set()
    total = 0
    for index, asset in enumerate(assets):
        if not isinstance(asset, dict):
            fail(f"PR Lens asset {index} must be an object")
        asset_id, lens, theme = asset.get("id"), asset.get("lens"), asset.get("theme")
        view, path = asset.get("view"), asset.get("path")
        if not isinstance(asset_id, str) or asset_id in ids:
            fail(f"PR Lens asset {index} has a missing or duplicate id")
        ids.add(asset_id)
        if lens not in PR_LENS_LENSES or theme not in PR_LENS_THEMES:
            fail(f"PR Lens asset {asset_id} has an invalid lens or theme")
        if view is not None and not isinstance(view, str):
            fail(f"PR Lens asset {asset_id} has an invalid view")
        if asset.get("mediaType") != "image/svg+xml":
            fail(f"PR Lens asset {asset_id} is not image/svg+xml")
        if not isinstance(path, str) or path in paths:
            fail(f"PR Lens asset {asset_id} has a missing or duplicate path")
        paths.add(path)
        svg_path = local_path(manifest_path.parent, path, f"PR Lens asset {asset_id} path")
        raw = svg_path.read_bytes()
        total += len(raw)
        if total > PR_LENS_MAX_BYTES:
            fail(f"PR Lens assets exceed {PR_LENS_MAX_BYTES} bytes")
        if asset.get("bytes") != len(raw):
            fail(f"PR Lens asset {asset_id} byte count does not match its file")
        digest = asset.get("contentHash")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{16,64}", digest):
            fail(f"PR Lens asset {asset_id} has an invalid contentHash")
        if not hashlib.sha256(raw).hexdigest().startswith(digest):
            fail(f"PR Lens asset {asset_id} contentHash does not match its file")
        width, height = asset.get("width"), asset.get("height")
        if not isinstance(width, int) or width < 1 or not isinstance(height, int) or height < 1:
            fail(f"PR Lens asset {asset_id} needs positive width and height")
        validate_svg(raw, asset_id)
        key = (lens, view)
        if theme in by_key.setdefault(key, {}):
            fail(f"PR Lens manifest duplicates {lens}/{view or 'root'} theme {theme}")
        encoded = base64.b64encode(raw).decode("ascii")
        by_key[key][theme] = (asset, encoded)

    if set(by_key) != set(expected_keys):
        missing = set(expected_keys) - set(by_key)
        extra = set(by_key) - set(expected_keys)
        fail(f"PR Lens manifest views do not match its graph: missing={sorted(map(str, missing))} extra={sorted(map(str, extra))}")
    theme_sets = {frozenset(themes) for themes in (group.keys() for group in by_key.values())}
    if len(theme_sets) != 1:
        fail("PR Lens manifest uses inconsistent theme sets across views")

    result: list[PrLensView] = []
    for lens, view, title in expected:
        themed = by_key[(lens, view)]
        first = themed.get("light") or themed.get("dark")
        assert first is not None
        result.append(
            PrLensView(
                lens=lens,
                view=view,
                title=title,
                width=first[0]["width"],
                height=first[0]["height"],
                themes={theme: encoded for theme, (_, encoded) in themed.items()},
            )
        )
    return result


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
    digest.check_groups(spec, seen_ids)

    verify = spec.get("verify") or {}
    for i, r in enumerate(verify.get("ran", [])):
        if not r.get("cwd"):
            fail(f"verify.ran[{i}]: missing required field cwd")
        if "ok" in r and not isinstance(r["ok"], bool):
            fail(f"verify.ran[{i}]: ok must be true or false")


def check_coverage(spec: dict, files: dict[str, FileDiff]) -> tuple[dict[str, list[str]], int, int, int]:
    placed: dict[str, list[str]] = {}
    for ch in spec["chapters"]:
        for f in ch.get("files", []):
            placed.setdefault(f["path"], []).append(ch["id"])
    for f in spec.get("everythingElse", []):
        if f["path"] in placed:
            fail(f"{f['path']} is in everythingElse and in chapter {placed[f['path']][0]}; keep it in one place")
        placed.setdefault(f["path"], []).append("everythingElse")
    # a changed file with no place fails in digest.classify, which also knows groups and derived files
    extra = sorted(set(placed) - set(files))
    if extra:
        fail("placed files that are not in the diff: " + ", ".join(extra))
    ee = spec.get("everythingElse", [])
    cap = min(20, max(3, len(files) // 10))
    if len(ee) > cap:
        fail(
            f"everythingElse holds {len(ee)} files; the limit for this diff is {cap}. "
            "Declare groups or chapters for the rest"
        )

    shown: dict[tuple[str, str, int], str] = {}
    shown_changed: set[tuple[str, str, int]] = set()
    shown_per_file: dict[str, int] = {}
    opened: set[str] = set()
    for ch in spec["chapters"]:
        for f in ch.get("files", []):
            if f.get("hunks"):
                opened.add(f["path"])
            fd = files[f["path"]]
            for h in f.get("hunks", []):
                side = h.get("side", "new")
                changed = fd.added if side == "new" else fd.removed
                for n in range(int(h["start"]), int(h["end"]) + 1):
                    key = (f["path"], side, n)
                    if key in shown:
                        fail(f"{f['path']} {side} line {n} is shown twice: chapters {shown[key]} and {ch['id']}")
                    shown[key] = ch["id"]
                    if n in changed:
                        shown_changed.add(key)
                        shown_per_file[f["path"]] = shown_per_file.get(f["path"], 0) + 1

    # a file the tour opens (at least one hunk) but doesn't fully cover reads differently from
    # one that never gets a hunk at all: the reader has already seen some of the first kind
    unshown_in_opened = 0
    unshown_in_unopened = 0
    for path, fd in files.items():
        missing = len(fd.added) + len(fd.removed) - shown_per_file.get(path, 0)
        if missing <= 0:
            continue
        if path in opened:
            unshown_in_opened += missing
        else:
            unshown_in_unopened += missing
    return placed, len(shown_changed), unshown_in_opened, unshown_in_unopened


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
        new_lines_shown = {
            n for h in hunks if h.get("side", "new") == "new" for n in range(int(h["start"]), int(h["end"]) + 1)
        }
        # old-side-only hunks introduce no new line: fall back to every name the file adds
        only = new_lines_shown or None
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
        out.append(f'<p class="why">{sanitize_prose(f["why"])}</p>')
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
            if any(n not in changed for n in range(start, end + 1)):
                stats["hasContextRow"] = True
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
                out.append(f'<p class="why">{sanitize_prose(h["why"])}</p>')
            out.append("</figure>")
        out.append("</details>")
    out.append("</div>")
    return "".join(out)


def render_pr_lens_view(view: PrLensView, index: int) -> str:
    fallback = view.themes.get("light") or view.themes["dark"]
    sources: list[str] = []
    if "dark" in view.themes:
        sources.append(
            '<source media="(prefers-color-scheme: dark)" '
            f'srcset="data:image/svg+xml;base64,{view.themes["dark"]}">'
        )
    if "light" in view.themes:
        sources.append(
            '<source media="(prefers-color-scheme: light)" '
            f'srcset="data:image/svg+xml;base64,{view.themes["light"]}">'
        )
    return (
        f'<figure class="pr-lens-view" id="pr-lens-view-{index}">'
        f'<figcaption><span class="chip pr-lens-kind">{esc(view.lens)}</span><h3>{esc(view.title)}</h3></figcaption>'
        f'<picture>{"".join(sources)}'
        f'<img src="data:image/svg+xml;base64,{fallback}" width="{view.width}" height="{view.height}" '
        f'alt="{esc(view.title)}" loading="lazy" decoding="async"></picture></figure>'
    )


# Runs after the tour's dock wiring and before sheet.js. The dock sends the tour's feedback text;
# this adds the sheet answers, notes, and fix/skip choices to it.
SHEET_GLUE = """
  var tourFeedback = feedbackMarkdown;
  feedbackMarkdown = function () {
    var md = tourFeedback(), extra = [];
    $$(".sheet textarea[data-note]").forEach(function (ta) {
      var text = ta.value.trim();
      if (!text) return;
      var sec = ta.closest("section");
      extra.push("### Panel " + ta.getAttribute("data-note") + ": " + (sec ? sec.getAttribute("data-role") : ""), "", text, "");
    });
    var togs = $$(".sheet .tog");
    if (togs.length) {
      var fix = [], skip = [];
      togs.forEach(function (t) {
        var p = $('[aria-pressed="true"]', t);
        (p && p.getAttribute("data-v") === "fix" ? fix : skip).push(t.getAttribute("data-id"));
      });
      extra.push("Fix: " + (fix.join(", ") || "none"), "Skip: " + (skip.join(", ") || "none"), "");
    }
    if (typeof sheetAnswers === "function" && $$(".asks > li[data-ask]").length) md = sheetAnswers().text + "\\n\\n" + md;
    if (!extra.length) return md;
    return md.replace("(no notes written)\\n\\n", "") + "\\n\\n## Report sheet\\n\\n" + extra.join("\\n");
  };
"""


def result_label(summary: object) -> str | None:
    """A short check result for the sheet, or None when the summary would fail the voice lint."""
    if not isinstance(summary, str) or "<" in summary:
        return None
    first = re.split(r"(?<=[.!?])\s", summary.strip(), maxsplit=1)[0].rstrip(".")
    if not first or len(first.split()) > 12 or voice.issues(first, "label"):
        return None
    return first


def reading_order(chapters: list[dict]) -> list[dict]:
    """Read-tier chapters, then skim chapters, each in spec order. Chapter numbers follow it."""
    return [ch for ch in chapters if ch["risk"] in READ_RISKS] + [ch for ch in chapters if ch["risk"] not in READ_RISKS]


def build_sheet(spec: dict, root: Path, files: dict[str, FileDiff]) -> str:
    """Validate the optional `sheet` block and render it. The builder owns the checks and files
    panels, so the agent supplying either one is an error."""
    block = spec["sheet"]
    if not isinstance(block, dict):
        fail("sheet: must be an object")
    for key in ("title", "kind", "tree"):
        if key in block:
            fail(f"sheet: {key} comes from the tour; remove it")
    for p in block.get("panels") or []:
        if isinstance(p, dict) and p.get("type") in ("checks", "files"):
            fail("sheet: walkthrough builds checks and files itself; remove the " + str(p.get("role")) + " panel")
    rows = []
    for r in (spec.get("verify") or {}).get("ran", []):
        row = {"cmd": str(r.get("cmd", "")), "cwd": str(r["cwd"]),
               "exit": None if r.get("exit") is None else int(r["exit"])}
        label = result_label(r.get("summary"))
        if label:
            row["result"] = label
        rows.append(row)
    auto = [{"role": "checks", "type": "checks", "rows": rows}, {"role": "files", "type": "files"}]
    tree = {"repo": str(root), "base": spec["base"], "head": spec["head"]}
    targets = {ch["id"]: (n, ch["title"]) for n, ch in enumerate(reading_order(spec["chapters"]), start=1)}
    norm = sheet.check_sheet(block | {"tree": tree}, kind="execute", title=spec["title"], auto_panels=auto,
                             targets=targets)
    return sheet.render_sheet(norm)


def project_branch(root: Path) -> tuple[str, str | None]:
    """The main repo folder name and the checked-out branch, both from git."""
    return gitfacts.project_name(root) or root.name, gitfacts.branch_name(root)


def build_body(spec: dict, root: Path, pr_lens_views: list[PrLensView], seed: int) -> tuple[str, dict]:
    base, head = spec["base"], spec["head"]
    check_spec(spec)
    git_bytes(root, "rev-parse", "--verify", f"{base}^{{commit}}")
    if head != WORKTREE:
        git_bytes(root, "rev-parse", "--verify", f"{head}^{{commit}}")
    files = load_changed_files(root, base, head)
    dg = digest.classify(spec, files, root, base, head, seed)
    placed, lines_shown, unshown_opened, unshown_unopened = check_coverage(spec, files)

    head_label = "working tree" if head == WORKTREE else head[:8]
    storage_id = revision_hash(root, base) if head == WORKTREE else head[:16]
    chapters = spec["chapters"]
    lines_added = sum(len(fd.added) for fd in files.values())
    lines_removed = sum(len(fd.removed) for fd in files.values())
    lines_changed = lines_added + lines_removed
    coverage_percent = round(100 * lines_shown / lines_changed) if lines_changed else 100
    stats = {
        "filesChanged": len(files),
        "filesPlaced": len(placed),
        "everythingElse": len(spec.get("everythingElse", [])),
        "linesAdded": lines_added,
        "linesRemoved": lines_removed,
        "linesShown": lines_shown,
        "linesChanged": lines_changed,
        "coveragePercent": coverage_percent,
        "linesUnshownInOpenedFiles": unshown_opened,
        "linesUnshownInUnopenedFiles": unshown_unopened,
        "hunksShown": 0,
        "chapters": len(chapters),
        "attentionChapters": sum(1 for ch in chapters if ch["risk"] == "attention"),
        "prLensViews": len(pr_lens_views),
        "hasContextRow": False,
        "flagged": len(dg.flags),
        "digest": {
            "seed": dg.seed,
            "counts": dg.counts,
            "lines": dg.lines,
            "tiers": dict(sorted(dg.tiers.items())),
            "groups": [
                {"id": g.id, "kind": g.kind, "tier": g.tier, "files": g.files, "samples": [asdict(s) for s in g.samples]}
                for g in dg.groups
            ],
            "flags": [{"path": f.path, "group": f.group, "reason": f.reason} for f in dg.flags],
        },
    }

    # chapters render first: the overview strip reports the hunk count this pass derives
    tour: list[str] = []
    for idx, ch in enumerate(reading_order(chapters), start=1):
        risk = ch["risk"]
        tour.append(
            f'<details class="chapter" id="ch-{esc(ch["id"])}" data-chapter="{esc(ch["id"])}" data-risk="{esc(risk)}">'
            f'<summary class="chead"><span class="num">{idx}</span>'
            f'<span class="chip risk-{esc(risk)}">{RISK_LABEL[risk]}</span>'
            f'<h3 class="ttl">{esc(ch["title"])}</h3>'
            f'<span class="meta" data-chapter-progress></span>'
            f'<span class="chev" aria-hidden="true">▸</span></summary><div class="dbody">'
        )
        tour.append(f'<div class="overview">{sanitize_prose(ch["overview"])}</div>')
        for f in ch.get("files", []):
            tour.append(file_card(spec, files, ch["id"], ch["title"], f, risk, stats, head_label))
        tour.append("</div></details>")

    o: list[str] = []
    o.append(
        f'<div class="wrap" data-storage-key="walkthrough:{esc(storage_id)}" '
        f'data-head-label="{esc(head_label)}" data-doc-title="{esc(spec["title"])}">'
    )
    has_sheet = "sheet" in spec
    if has_sheet:
        o.append(build_sheet(spec, root, files))

    # ---- header
    built = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    project, branch = project_branch(root)
    o.append('<header class="top">')
    o.append(pagelib.at_row(project, branch, has_sheet))
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
    # no unchanged row exists to hide, so the toggle would do nothing
    hidden_attr = "" if stats["hasContextRow"] else " hidden"
    o.append(
        f'<button type="button" class="btn" data-changed-only aria-pressed="false"{hidden_attr}>'
        "Changed lines only</button>"
    )
    o.append('<button type="button" class="btn" data-reset>Reset progress</button>')
    o.append('<div class="bar"><i data-bar></i></div>')
    o.append("</div></header>")

    # ---- overview
    o.append('<section id="overview"><h2>Overview</h2>')
    o.append(sanitize_prose(spec["overview"]))
    if not has_sheet:
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
        coverage_line = (
            f'lines shown {stats["linesShown"]} / changed {stats["linesChanged"]} ({stats["coveragePercent"]}%)'
        )
        o.append(
            f'<div class="stat"><div class="k">Coverage</div><div class="v">{stats["coveragePercent"]}%</div>'
            f'<div class="s">{coverage_line}</div></div>'
        )
        o.append("</div>")
    if stats["coveragePercent"] < 30:
        o.append(
            f'<p class="lede">This tour shows {stats["coveragePercent"]}% of changed lines: '
            f'{stats["linesUnshownInOpenedFiles"]} lines not shown sit in files that are opened above, '
            f'{stats["linesUnshownInUnopenedFiles"]} in files listed by name only.</p>'
        )
    o.append("</section>")

    # ---- architecture and data flow
    o.append('<section id="pr-lens"><h2>Architecture and data flow</h2>')
    o.append(
        f'<p class="lede">PR Lens rendered {len(pr_lens_views)} view'
        f'{"s" if len(pr_lens_views) != 1 else ""} for this revision. Every view is embedded in this page.</p>'
    )
    o.append('<div class="pr-lens-views">')
    o.extend(render_pr_lens_view(view, index) for index, view in enumerate(pr_lens_views, start=1))
    o.append("</div></section>")

    # ---- focus, intuition, background
    if spec.get("focus"):
        o.append('<section id="focus"><h2>Where to focus</h2>')
        o.append('<p class="lede">Start here if you read nothing else.</p><ol class="focus">')
        # one grid cell per item: a bare text node after <b> would land in the number column
        o.extend(f"<li><span>{sanitize_prose(item)}</span></li>" for item in spec["focus"])
        o.append("</ol></section>")
    if spec.get("intuition"):
        o.append('<section id="intuition"><h2>Intuition</h2>')
        o.append(sanitize_prose(spec["intuition"]))
        o.append("</section>")
    if spec.get("background"):
        o.append('<section id="background"><h2>Background</h2>')
        o.append(sanitize_prose(spec["background"]))
        o.append("</section>")

    # ---- tour
    o.append(
        '<section id="tour"><div class="rhead"><h2>Walkthrough</h2>'
        f'{pagelib.at_row(project, branch, True)}'
        '<button type="button" class="btn" data-toggle-all>Open all</button></div>'
    )
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
                o.append(f'<p class="why">{sanitize_prose(f["why"])}</p>')
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
            o.append(
                '<div class="scroll"><table><thead><tr><th class="col-cwd">CWD</th><th>Command</th>'
                '<th class="col-exit">Exit</th><th>Result</th><th class="col-tree">Tree</th></tr></thead><tbody>'
            )
            for r in ran:
                code = r.get("exit")
                ok = r.get("ok")
                if code is None:
                    chip = '<span class="chip exit-none">not run</span>'
                elif ok is True:
                    chip = f'<span class="chip exit-ok">{int(code)}</span>'
                elif ok is False:
                    chip = f'<span class="chip exit-bad">{int(code)}</span>'
                else:
                    chip = f'<span class="chip">{int(code)}</span>'
                o.append(
                    f'<tr><td class="col-cwd"><code>{esc(str(r.get("cwd", "")))}</code></td>'
                    f'<td class="col-command"><code>{esc(str(r.get("cmd", "")))}</code></td><td class="col-exit">{chip}</td>'
                    f'<td>{sanitize_prose(str(r.get("summary", "")))}</td>'
                    f'<td class="col-tree"><code>{esc(str(r.get("tree", "")))}</code></td></tr>'
                )
            o.append("</tbody></table></div>")
        manual = verify.get("manual", [])
        if manual:
            o.append("<h3>Check it yourself</h3><ul class=\"plain\">")
            o.extend(f"<li>{sanitize_prose(item)}</li>" for item in manual)
            o.append("</ul>")
        o.append("</section>")

    # ---- notes
    o.append('<section id="notes" class="notes"><h2>Notes</h2>')
    o.append(
        '<p class="lede">Kept in this browser only. Press Send feedback at the bottom right to copy your notes '
        "as Markdown, then paste them back into the chat.</p>"
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
    o.append("</section>")
    o.append(dock.render_dock(project, branch, has_sheet))

    o.append(
        f'<footer>Built from review-tour.json against {esc(head_label)} on {esc(built)}. '
        f"Line numbers, counts, and file coverage are derived from git, not typed.</footer>"
    )
    o.append("</div>")

    return "\n".join(o), stats


# ---------------------------------------------------------------- assembly


def splice_sheet_assets(shell: str, template: Path, with_sheet: bool) -> str:
    """Fill the sheet markers. Without a sheet each marker line is removed, so the page is
    byte for byte what it was before sheets existed."""
    if SHEET_STYLE not in shell or SHEET_SCRIPT not in shell:
        fail(f"{template}: missing {SHEET_STYLE} or {SHEET_SCRIPT} marker")
    if not with_sheet:
        return shell.replace(SHEET_STYLE + "\n", "").replace(SHEET_SCRIPT + "\n", "")
    css, js = sheet.assets()
    shell = shell.replace(SHEET_STYLE, css.rstrip("\n"))
    return shell.replace(SHEET_SCRIPT, SHEET_GLUE.strip("\n") + "\n\n" + js.rstrip("\n"))


def main() -> None:
    ap = argparse.ArgumentParser(description="Render a walkthrough page from review-tour.json.")
    ap.add_argument("--spec")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--out", help="full HTML document")
    ap.add_argument("--fragment", default=None, help="same content without the document wrappers")
    ap.add_argument("--data-out", default=None, help="write the derived stats as JSON here")
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    ap.add_argument("--seed", type=int, default=None, help="seed for the spot-check samples (default: random)")
    ap.add_argument("--print-worktree-hash", metavar="BASE", help="print the tracked and untracked tree fingerprint")
    args = ap.parse_args()

    root = Path(args.repo_root).resolve()
    if args.print_worktree_hash:
        print(revision_hash(root, args.print_worktree_hash))
        return
    if not args.spec or not args.out:
        ap.error("--spec and --out are required unless --print-worktree-hash is used")
    spec_path = Path(args.spec).resolve()
    try:
        spec_text = spec_path.read_text(encoding="utf-8")
    except OSError as e:
        fail(f"cannot read the spec {args.spec}: {e}")
    spec = json_no_duplicates(spec_text, f"spec {args.spec}")
    template = Path(args.template)
    if not template.is_file():
        fail(f"template not found: {template}")
    shell = template.read_text(encoding="utf-8")
    if LIB_STYLE not in shell or LIB_SCRIPT not in shell:
        fail(f"{template}: missing {LIB_STYLE} or {LIB_SCRIPT} marker")
    # rstrip: the marker carries no trailing newline of its own, and the lib files each end
    # with one, so keeping it would insert a blank line the original template never had
    dock_css, dock_js = dock.assets()
    for marker, names, extra in (
        (LIB_STYLE, ("page.css", "report.css"), dock_css),
        (LIB_SCRIPT, ("notes.js", "report.js"), dock_js),
    ):
        parts = [(LIB_DIR / name).read_text(encoding="utf-8").rstrip("\n") for name in names]
        shell = shell.replace(marker, "\n".join(parts) + "\n" + extra.rstrip("\n"))

    has_sheet = isinstance(spec, dict) and "sheet" in spec
    seed = args.seed if args.seed is not None else secrets.randbits(32)
    try:
        page_shell = splice_sheet_assets(shell, template, has_sheet)
        pr_lens_views = load_pr_lens(spec, spec_path.parent, root)
        body, stats = build_body(spec, root, pr_lens_views, seed)
        title = esc(" · ".join(p for p in (*project_branch(root), spec["title"]) if p))
        document, fragment = pagelib.assemble(page_shell, title, body)
    except pagelib.BuildFailed as e:
        # Only a sheet build gets a failure page: a sheet-less build keeps its old output untouched.
        if has_sheet:
            failed = splice_sheet_assets(shell, template, True)
            document, fragment = pagelib.assemble(failed, "Build failed", sheet.render_failure(e.msg, args.spec))
            Path(args.out).write_text(document, encoding="utf-8")
            if args.fragment:
                Path(args.fragment).write_text(fragment, encoding="utf-8")
        raise

    # everything validated: write the outputs last, so a failed build leaves them untouched
    Path(args.out).write_text(document, encoding="utf-8")
    if args.fragment:
        Path(args.fragment).write_text(fragment, encoding="utf-8")
    if args.data_out:
        Path(args.data_out).write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    flags = stats["digest"]["flags"]
    if flags:
        listed = ", ".join(f"{f['path']} ({f['group']})" for f in flags)
        print(
            f"build_tour: warning: {len(flags)} file{'s' if len(flags) != 1 else ''} broke a rule: {listed}",
            file=sys.stderr,
        )
    counts = stats["digest"]["counts"]
    print(
        f"build_tour: ok files={stats['filesChanged']} placed={stats['filesPlaced']} "
        f"else={stats['everythingElse']} hunks={stats['hunksShown']} chapters={stats['chapters']} "
        f"pr-lens={stats['prLensViews']} "
        f"lines shown {stats['linesShown']} / changed {stats['linesChanged']} ({stats['coveragePercent']}%) "
        "tiers " + " ".join(f"{t}={counts[t]}" for t in digest.TIERS)
    )


if __name__ == "__main__":
    main()
