#!/usr/bin/env python3
"""
Resolve every internal href/src/srcset target against the filesystem, the way
Vercel serves this site (directory -> index.html, plus the rewrites in
vercel.json). Exits non-zero if anything does not resolve.

Usage:  python3 tools/check-links.py
"""

import json
import os
import re
import subprocess
import sys
from urllib.parse import urlsplit

# Endpoints injected by the platform at runtime; nothing on disk to check.
RUNTIME_PREFIXES = ("/_vercel/",)


def rewrites():
    cfg = json.load(open("vercel.json"))
    return {r["source"]: r["destination"].lstrip("/") for r in cfg.get("rewrites", [])}


def targets(html):
    """Yield each internal URL, splitting only real srcset attributes on commas."""
    for m in re.finditer(r'\b(href|src)="([^"]+)"', html):
        yield m.group(2)
    for m in re.finditer(r'\bsrcset="([^"]+)"', html):
        for part in m.group(1).split(","):
            candidate = part.strip().split(" ")[0]
            if candidate:
                yield candidate


def resolve(url, src, rw):
    u = urlsplit(url)
    if u.scheme or u.netloc or url.startswith(("mailto:", "tel:", "#", "data:")):
        return None
    path = u.path
    if not path or path.startswith(RUNTIME_PREFIXES):
        return None
    if path in rw:
        return rw[path]
    if path.startswith("/"):
        cand = path.lstrip("/")
    else:
        cand = os.path.normpath(os.path.join(os.path.dirname(src), path))
    if cand in ("", ".") or cand.endswith("/") or not os.path.splitext(cand)[1]:
        cand = os.path.join(cand, "index.html")
    return cand


def main():
    rw = rewrites()
    files = [
        f
        for f in subprocess.check_output(["git", "ls-files", "-z", "*.html"]).decode().split("\0")
        if f and not f.startswith("project/") and f != "HomeQuest.html"
    ]

    checked, broken = 0, []
    for path in sorted(files):
        html = open(path, encoding="utf-8").read()
        for url in targets(html):
            t = resolve(url, path, rw)
            if t is None:
                continue
            checked += 1
            if not os.path.exists(t):
                broken.append((path, url, t))

    print(f"{checked} internal targets resolved, {len(broken)} broken")
    for f, u, t in broken:
        print(f"  {f}: {u}  ->  {t}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
