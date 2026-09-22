#!/usr/bin/env python3
"""
Parse every application/ld+json block on every page and report its type.
Exits non-zero if any block fails to parse.

Usage:  python3 tools/check-jsonld.py [--verbose]
"""

import json
import subprocess
import sys
from html.parser import HTMLParser


class LdCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.blocks = []
        self.grab = False

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type") == "application/ld+json":
            self.grab = True
            self.blocks.append("")

    def handle_endtag(self, tag):
        if tag == "script":
            self.grab = False

    def handle_data(self, data):
        if self.grab:
            self.blocks[-1] += data


def describe(obj):
    t = obj.get("@type", "?")
    if t == "BreadcrumbList":
        crumbs = " > ".join(i["name"] for i in obj.get("itemListElement", []))
        return f"BreadcrumbList[{crumbs}]"
    if t == "FAQPage":
        return f"FAQPage[{len(obj.get('mainEntity', []))} Q&A]"
    return str(t)


def main():
    verbose = "--verbose" in sys.argv
    files = [
        f
        for f in subprocess.check_output(["git", "ls-files", "-z", "*.html"]).decode().split("\0")
        if f and not f.startswith("project/")
    ]

    total = failures = 0
    for path in sorted(files):
        c = LdCollector()
        c.feed(open(path, encoding="utf-8").read())
        if not c.blocks:
            continue
        kinds = []
        for i, raw in enumerate(c.blocks, 1):
            total += 1
            try:
                kinds.append(describe(json.loads(raw)))
            except json.JSONDecodeError as e:
                failures += 1
                kinds.append(f"INVALID(block {i}: {e})")
        line = f"{path}: {', '.join(kinds)}"
        if verbose or "INVALID" in line:
            print(line)

    print(f"\n{total} JSON-LD blocks parsed, {failures} invalid")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
