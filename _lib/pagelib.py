"""Shared page-building machinery for skills that render a self-contained HTML page from a
shell template (marker slicing, prose sanitizing, small render helpers). No SKILL.md here: this
is a library, not a skill, reached by a per-skill `lib` symlink (see README.md).

Stdlib only, Python 3.10 or newer.
"""

from __future__ import annotations

import html
import re
import sys
from html.parser import HTMLParser

TITLE_START, TITLE_END = "<!-- TITLE:START -->", "<!-- TITLE:END -->"
STYLE_START, STYLE_END = "<!-- STYLE:START -->", "<!-- STYLE:END -->"
BODY_START, BODY_END = "<!-- BODY:START -->", "<!-- BODY:END -->"
SCRIPT_START, SCRIPT_END = "<!-- SCRIPT:START -->", "<!-- SCRIPT:END -->"


def fail(msg: str) -> None:
    print(f"build_tour: {msg}", file=sys.stderr)
    sys.exit(1)


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# ---------------------------------------------------------------- prose sanitizing

PROSE_ALLOWED_TAGS = {"p", "br", "b", "strong", "i", "em", "code", "pre", "a", "ul", "ol", "li", "span"}
PROSE_VOID_TAGS = {"br"}


def _sanitize_href(raw: str) -> str | None:
    """`href` survives only as a hash link, an absolute http(s) URL, or a scheme-less relative
    path; anything else (a `javascript:` URL, entity- or control-char-obscured or not) is
    dropped. Control and whitespace characters are removed first so a scheme cannot hide inside
    a tab or newline the way it can in a browser's own URL parser."""
    cleaned = "".join(ch for ch in raw if ord(ch) > 0x20 and ord(ch) != 0x7F)
    if not cleaned:
        return None
    low = cleaned.lower()
    if cleaned.startswith("#") or low.startswith("http://") or low.startswith("https://"):
        return cleaned
    colon = cleaned.find(":")
    slash = cleaned.find("/")
    if colon == -1 or (slash != -1 and slash < colon):
        return cleaned
    return None


class _ProseSanitizer(HTMLParser):
    """Rebuilds attacker-controlled prose from a small tag allowlist. Disallowed tags are
    dropped but the text inside them survives; text and attribute values are re-escaped on
    output. `convert_charrefs=True` makes the base parser decode entities before we ever see
    them, so an entity-obscured `javascript:` href is caught by `_sanitize_href` like a plain
    one."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag not in PROSE_ALLOWED_TAGS:
            return
        if tag == "a":
            href = None
            for name, value in attrs:
                if name.lower() == "href" and value is not None:
                    href = _sanitize_href(value)
                    break
            self.out.append(f'<a href="{esc(href)}">' if href is not None else "<a>")
        else:
            self.out.append(f"<{tag}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in PROSE_VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in PROSE_ALLOWED_TAGS and tag not in PROSE_VOID_TAGS:
            self.out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.out.append(html.escape(data, quote=False))


def sanitize_prose(value) -> str:
    """Allowlist-sanitize a prose field for direct embedding in the page. Never fails the
    build: malformed or hostile markup is stripped, not rejected."""
    if not isinstance(value, str):
        return ""
    parser = _ProseSanitizer()
    try:
        parser.feed(value)
        parser.close()
    except Exception:
        return esc(value)
    return "".join(parser.out)


# ---------------------------------------------------------------- shell assembly


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


def assemble(shell: str, title: str, body: str) -> tuple[str, str]:
    """Slice the shell's style/script and splice in the title and body. `title` is already
    HTML-escaped; `body` is the rendered page body. Returns (document, fragment): the full
    shell with title/body spliced in, and a standalone fragment of title+style+body+script
    without the document wrappers."""
    style = slice_between(shell, STYLE_START, STYLE_END, "template").strip()
    script = slice_between(shell, SCRIPT_START, SCRIPT_END, "template").strip()

    document = replace_between(shell, TITLE_START, TITLE_END, f"<title>{title}</title>", "template")
    document = replace_between(document, BODY_START, BODY_END, body, "template")
    fragment = "\n".join([f"<title>{title}</title>", style, body, script]) + "\n"
    return document, fragment
