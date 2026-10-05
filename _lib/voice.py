"""STE-80 lint: about 80% of ASD-STE100 Simplified Technical English, checked at build time.

Word lists live in voice-words.json so they grow without code changes. Rules a regex cannot
check live in voice.md. Code spans (`x` or <code>x</code>) are never checked.

Stdlib only, Python 3.10 or newer.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pagelib

HERE = Path(__file__).resolve().parent
WORDS = json.loads((HERE / "voice-words.json").read_text(encoding="utf-8"))
CAPS = {"label": (12, 1), "instruction": (20, 2), "prose": (25, None)}
SENTENCE_RE = re.compile(r"(?<=[.!?])(?:\s+|$)")
CODE_TICK_RE = re.compile(r"`[^`]*`")
CODE_TAG_RE = re.compile(r"<code>.*?</code>|<pre>.*?</pre>", re.IGNORECASE | re.DOTALL)


def _pattern(entry: str) -> re.Pattern:
    if " " in entry or "-" in entry:
        return re.compile(r"\b" + re.escape(entry) + r"\b", re.IGNORECASE)
    return re.compile(r"\b" + re.escape(entry) + r"\w*", re.IGNORECASE)


REPLACE = [(_pattern(k), v) for k, v in WORDS["replace"].items()]
BAN = [_pattern(w) for w in WORDS["ban"]]


def plain(text: str, cls: str) -> str:
    """Visible text with code spans removed. Prose is sanitized HTML; others are plain."""
    if cls == "prose":
        text = pagelib.sanitize_prose(text)
        text = CODE_TAG_RE.sub(" ", text)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
    return CODE_TICK_RE.sub(" ", text)


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_RE.split(text.strip()) if s.strip()]


def issues(text: str, cls: str, max_sentences: int | None = None) -> list[str]:
    """Every rule the text breaks, as short fix hints. Empty list means clean."""
    if cls == "literal":
        return []
    body = plain(text, cls)
    out: list[str] = []
    for pat, fix in REPLACE:
        for m in pat.finditer(body):
            out.append(f'"{m.group(0)}" → "{fix}"')
    for pat in BAN:
        for m in pat.finditer(body):
            out.append(f'"{m.group(0)}" is banned')
    if "—" in body:
        out.append("em dash; split the sentence")
    cap, default_max = CAPS[cls]
    limit = max_sentences if max_sentences is not None else default_max
    sents = sentences(body)
    if limit is not None and len(sents) > limit:
        out.append(f"{len(sents)} sentences; keep to {limit}")
    if cls == "label":
        n = len(body.split())
        if n > cap:
            out.append(f"{n} words; keep to {cap}")
    else:
        for s in sents:
            n = len(s.split())
            if n > cap:
                first_five = " ".join(s.split()[:5])
                out.append(f'a sentence is {n} words, over {cap}: "{first_five} ..."')
    return out


def check_field(where: str, text: str, cls: str, max_sentences: int | None = None) -> None:
    """Fail the build on the first broken rule, naming the field and the fix."""
    found = issues(text, cls, max_sentences)
    if found:
        pagelib.fail(f"{where}: {found[0]}")
