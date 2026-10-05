"""SVG allowlist for agent-drawn figures. Fails, never strips: a rejected drawing is the agent's to fix.

Stdlib only, Python 3.10 or newer.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pagelib

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
XML_NS = "http://www.w3.org/XML/1998/namespace"
SVG_MAX_BYTES = 64 * 1024
URL_REF_RE = re.compile(r"url\(([^)]*)\)", re.IGNORECASE)
DTD_RE = re.compile(r"<!DOCTYPE|<!ENTITY", re.IGNORECASE)

# Everything not named here is refused: SMIL animation (`set`, `animate`, ...), `feImage`,
# `image`, `foreignObject`, `iframe`, `a`, `script`, `style`, and any HTML tag.
SVG_ALLOWED_TAGS = {
    "svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
    "text", "tspan", "textPath", "defs", "clipPath", "mask", "pattern",
    "linearGradient", "radialGradient", "stop", "marker", "symbol", "use",
    "title", "desc", "filter",
    "feGaussianBlur", "feOffset", "feBlend", "feColorMatrix", "feComposite",
    "feFlood", "feMerge", "feMergeNode", "feMorphology", "feTile", "feTurbulence",
    "feDropShadow", "feComponentTransfer", "feFuncR", "feFuncG", "feFuncB", "feFuncA",
}

# Attributes allowed on any allowed element. `href`/`xlink:href` are handled separately
# below since they are only safe on a handful of reference-only elements.
SVG_ALLOWED_ATTRS = {
    "id", "class", "transform", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry",
    "width", "height", "d", "points", "dx", "dy", "rotate", "textLength", "lengthAdjust",
    "fill", "fill-opacity", "fill-rule", "stroke", "stroke-width", "stroke-opacity",
    "stroke-linecap", "stroke-linejoin", "stroke-dasharray", "stroke-dashoffset",
    "stroke-miterlimit", "opacity", "font-family", "font-size", "font-weight", "font-style",
    "text-anchor", "dominant-baseline", "letter-spacing", "text-decoration", "viewBox",
    "preserveAspectRatio", "role", "aria-label", "aria-hidden", "aria-labelledby",
    "clip-path", "mask", "marker-start", "marker-mid", "marker-end", "filter",
    "gradientUnits", "gradientTransform", "spreadMethod", "offset", "stop-color", "stop-opacity",
    "patternUnits", "patternContentUnits", "patternTransform", "clipPathUnits", "maskUnits",
    "maskContentUnits", "markerWidth", "markerHeight", "markerUnits", "refX", "refY", "orient",
    "in", "in2", "result", "stdDeviation", "mode", "type", "values", "operator",
    "k1", "k2", "k3", "k4", "flood-color", "flood-opacity", "radius",
    "baseFrequency", "numOctaves", "seed", "tableValues", "slope", "intercept",
    "amplitude", "exponent", "xml:space", "lang", "xmlns", "data-s",
}

# `href`/`xlink:href` are only meaningful, and only safe, as a local (`#id`) reference on
# these elements; anywhere else it is refused outright.
SVG_HREF_ALLOWED_TAGS = {"use", "textPath", "pattern", "linearGradient", "radialGradient"}

SCHEME_RE = re.compile(r"javascript:|data:")


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[1] if tag.startswith("{") else tag


def _attr_local_name(key: str) -> str:
    """Local attribute name for allowlist comparison. `href` and `xlink:href` collapse to
    the same `href` (both are the same reference in practice); `xml:space` keeps its
    prefix, since that is how it appears in `SVG_ALLOWED_ATTRS`; any other namespaced
    attribute drops its namespace URI."""
    if not key.startswith("{"):
        return key
    ns, local = key[1:].split("}", 1)
    if ns == XLINK_NS:
        return local
    if ns == XML_NS:
        return f"xml:{local}"
    return local


def _strip_namespaces(elem: ET.Element) -> None:
    """Drop every namespace prefix from a tag and its attributes, recursively (using the
    same collapsing rules as `_attr_local_name`), so the re-serialized tree can never grow
    an `ns0:`-style prefix regardless of how the input declared its namespaces."""
    elem.tag = _local_name(elem.tag)
    if elem.attrib:
        elem.attrib = {_attr_local_name(k): v for k, v in elem.attrib.items()}
    for child in elem:
        _strip_namespaces(child)


def _check_svg_value(value: str, where: str, el_tag: str, key: str) -> None:
    """Refuse a `javascript:`/`data:` scheme (case-insensitive, whitespace stripped first
    so `java\\tscript:` can't sneak past a naive substring check) and any `url(...)` that
    isn't a local `#` reference, wherever they appear."""
    collapsed = re.sub(r"\s+", "", value).lower()
    if SCHEME_RE.search(collapsed):
        pagelib.fail(f"{where}: <{el_tag}> {key} contains a disallowed scheme: {value!r}")
    for m in URL_REF_RE.finditer(collapsed):
        ref = m.group(1).strip("'\"")
        if not ref.startswith("#"):
            pagelib.fail(f"{where}: <{el_tag}> {key} has an external url() reference: {value!r}")


def _scope_figure_ids(root: ET.Element, prefix: str) -> None:
    """Prefix every `id` in the figure with `prefix` and rewrite every reference to it
    (`url(#id)`, `href="#id"`, `aria-labelledby`), so two figures that both happen to
    define `id="ar"` (a common marker/gradient name) never collide once both land on the
    same page. Call after `_strip_namespaces`, so attribute names are already plain."""
    id_map = {el.get("id"): f"{prefix}{el.get('id')}" for el in root.iter() if el.get("id")}
    if not id_map:
        return
    for el in root.iter():
        if el.get("id") in id_map:
            el.set("id", id_map[el.get("id")])
        href = el.get("href")
        if href and href.startswith("#") and href[1:] in id_map:
            el.set("href", "#" + id_map[href[1:]])
        labelledby = el.get("aria-labelledby")
        if labelledby:
            el.set(
                "aria-labelledby",
                " ".join(id_map.get(tok, tok) for tok in labelledby.split()),
            )
        for key, value in list(el.attrib.items()):
            if "url(" not in value.lower():
                continue

            def _rewrite(m: re.Match) -> str:
                ref = m.group(1).strip().strip("'\"")
                if ref.startswith("#") and ref[1:] in id_map:
                    return f"url(#{id_map[ref[1:]]})"
                return m.group(0)

            el.set(key, URL_REF_RE.sub(_rewrite, value))


def validate_figure(svg_src: str, where: str, id_prefix: str) -> str:
    """Validate an untrusted `svg` figure and return the safe, normalized markup to embed.
    Fails (naming the chapter and figure index) rather than stripping: a rejected drawing is
    the agent's to fix, never silently altered."""
    if len(svg_src.encode("utf-8")) > SVG_MAX_BYTES:
        pagelib.fail(f"{where}: svg is over {SVG_MAX_BYTES // 1024} KB; simplify the drawing")
    if DTD_RE.search(svg_src):
        pagelib.fail(f"{where}: svg must not declare a DTD or entities")
    try:
        root = ET.fromstring(svg_src)
    except ET.ParseError as e:
        pagelib.fail(f"{where}: svg does not parse: {e}")

    tag = _local_name(root.tag)
    ns = root.tag.split("}", 1)[0][1:] if root.tag.startswith("{") else None
    if tag != "svg" or (ns is not None and ns != SVG_NS):
        pagelib.fail(f"{where}: svg root must be an <svg> element")
    if not root.get("viewBox"):
        pagelib.fail(f"{where}: svg must carry a viewBox attribute")

    for el in root.iter():
        el_tag = _local_name(el.tag)
        if el_tag not in SVG_ALLOWED_TAGS:
            pagelib.fail(f"{where}: svg contains a disallowed <{el_tag}> element")
        for key, value in el.attrib.items():
            local_key = _attr_local_name(key)
            if local_key == "href":
                if el_tag not in SVG_HREF_ALLOWED_TAGS:
                    pagelib.fail(f"{where}: <{el_tag}> may not carry href")
                if not value.startswith("#"):
                    pagelib.fail(f"{where}: <{el_tag}> href must be a local reference (#...): {value!r}")
                continue
            if local_key not in SVG_ALLOWED_ATTRS:
                pagelib.fail(f"{where}: <{el_tag}> has a disallowed attribute {local_key!r}")
            _check_svg_value(value, where, el_tag, local_key)
            if local_key == "data-s" and not re.fullmatch(r"\d+( \d+)*", value):
                pagelib.fail(f"{where}: data-s must be space-separated step numbers: {value!r}")

    _strip_namespaces(root)
    root.attrib.pop("width", None)
    root.attrib.pop("height", None)
    _scope_figure_ids(root, id_prefix)
    root.attrib = {"xmlns": SVG_NS, **root.attrib}

    serialized = ET.tostring(root, encoding="unicode")
    if len(serialized.encode("utf-8")) > SVG_MAX_BYTES:
        pagelib.fail(f"{where}: svg is over {SVG_MAX_BYTES // 1024} KB; simplify the drawing")
    return serialized


def step_ids(svg_src: str) -> set[int]:
    """Every step number named by a data-s attribute. Call after validate_figure."""
    root = ET.fromstring(svg_src)
    found: set[int] = set()
    for el in root.iter():
        for tok in (el.get("data-s") or "").split():
            found.add(int(tok))
    return found
