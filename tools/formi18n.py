#!/usr/bin/env python3
"""
Helpers for the intake-form i18n: locate a [data-i18n] element in raw HTML and
read or replace its inner content, without disturbing anything else.

The intake markup is machine-regular, so elements are found by their data-i18n
attribute and matched to their closing tag by counting nested same-name tags.
"""

import html
import re

TAG_OPEN = re.compile(r"<([a-zA-Z][\w-]*)\b")


def element_span(html, attr, key):
    """Return (tag, inner_start, inner_end) for the element carrying attr="key"."""
    marker = f'{attr}="{key}"'
    at = html.find(marker)
    if at < 0:
        return None
    lt = html.rfind("<", 0, at)
    tag = TAG_OPEN.match(html, lt).group(1)
    gt = html.find(">", at)
    if html[gt - 1] == "/":  # self-closing, no inner content
        return None
    inner_start = gt + 1

    depth = 1
    pos = inner_start
    open_re = re.compile(rf"<{tag}\b", re.I)
    close_re = re.compile(rf"</{tag}\s*>", re.I)
    while depth:
        nxt_o = open_re.search(html, pos)
        nxt_c = close_re.search(html, pos)
        if not nxt_c:
            raise ValueError(f"unclosed <{tag}> for {key}")
        if nxt_o and nxt_o.start() < nxt_c.start():
            depth += 1
            pos = nxt_o.end()
        else:
            depth -= 1
            pos = nxt_c.end()
            if not depth:
                return tag, inner_start, nxt_c.start()
    return None


def keys_in(html, attr):
    return re.findall(rf'{attr}="([^"]+)"', html)


def get_inner(html, attr, key):
    span = element_span(html, attr, key)
    return None if span is None else html[span[1] : span[2]]


def set_inner(html, attr, key, value):
    span = element_span(html, attr, key)
    if span is None:
        return html, False
    _, a, b = span
    return html[:a] + value + html[b:], True


def text_of(inner):
    """Plain text of an inner fragment, as textContent would render it."""
    stripped = re.sub(r"<[^>]+>", "", inner)
    return re.sub(r"\s+", " ", html.unescape(stripped)).strip()


def placeholders_in(html):
    """Map input/textarea name -> placeholder, for elements that have both."""
    out = {}
    for m in re.finditer(r"<(?:input|textarea)\b[^>]*>", html):
        tag = m.group(0)
        n = re.search(r'\bname="([^"]+)"', tag)
        p = re.search(r'\bplaceholder="([^"]*)"', tag)
        if n and p:
            out[n.group(1)] = p.group(1)
    return out


def set_placeholder(html, name, value):
    def repl(m):
        tag = m.group(0)
        n = re.search(r'\bname="([^"]+)"', tag)
        if not n or n.group(1) != name or 'placeholder="' not in tag:
            return tag
        return re.sub(r'(\bplaceholder=")[^"]*(")', lambda x: x.group(1) + value + x.group(2), tag)

    return re.sub(r"<(?:input|textarea)\b[^>]*>", repl, html)
