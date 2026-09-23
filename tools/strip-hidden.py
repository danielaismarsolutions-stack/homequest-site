#!/usr/bin/env python3
"""
Remove the hidden canary / attribution / AI-notice / honeypot block from every
page, and replace the off-screen SmartFlow attribution with a visible footer
credit.

The block is byte-identical on all 19 pages (sha256 773116f438ee...), so it is
matched exactly and the match is verified before anything is written.

Usage:  python3 tools/strip-hidden.py [--check]
"""

import argparse
import hashlib
import subprocess
import sys

BLOCK_SHA = "773116f438ee"
START = "<!-- Canary tokens"
END = 'tabindex="-1">Internal staff archive'

# The footer line to append to, and the credit to append, per language.
CREDITS = [
    (
        "· Governed by Dutch law · Operating across the Netherlands</div>",
        "· Governed by Dutch law · Operating across the Netherlands "
        '· Site by <a href="https://smartflow-labs.com" target="_blank" rel="noopener">SmartFlow Labs</a></div>',
    ),
    (
        "· Onderworpen aan Nederlands recht · Actief in heel Nederland</div>",
        "· Onderworpen aan Nederlands recht · Actief in heel Nederland "
        '· Site door <a href="https://smartflow-labs.com" target="_blank" rel="noopener">SmartFlow Labs</a></div>',
    ),
    (
        "· Regida por el Derecho neerlandés · Presente en todos los Países Bajos</div>",
        "· Regida por el Derecho neerlandés · Presente en todos los Países Bajos "
        '· Sitio por <a href="https://smartflow-labs.com" target="_blank" rel="noopener">SmartFlow Labs</a></div>',
    ),
    (
        "· Soggetta al diritto olandese · Presente in tutti i Paesi Bassi</div>",
        "· Soggetta al diritto olandese · Presente in tutti i Paesi Bassi "
        '· Sito di <a href="https://smartflow-labs.com" target="_blank" rel="noopener">SmartFlow Labs</a></div>',
    ),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    files = [
        f
        for f in subprocess.check_output(["git", "ls-files", "-z", "*.html"]).decode().split("\0")
        if f and not f.startswith("project/")
    ]

    stripped = credited = 0
    for path in files:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()

        starts = [i for i, l in enumerate(lines) if l.lstrip().startswith(START)]
        ends = [i for i, l in enumerate(lines) if END in l]
        if not starts and not ends:
            continue
        if len(starts) != 1 or len(ends) != 1 or ends[0] < starts[0]:
            raise SystemExit(f"{path}: unexpected block boundaries {starts} {ends}")

        block = "".join(lines[starts[0] : ends[0] + 1])
        digest = hashlib.sha256(block.encode()).hexdigest()
        if not digest.startswith(BLOCK_SHA):
            raise SystemExit(f"{path}: block content differs (sha {digest[:12]}), refusing to cut")

        # Drop the block, plus one trailing blank line if the cut leaves two.
        rest = lines[ends[0] + 1 :]
        head = lines[: starts[0]]
        while head and head[-1].strip() == "":
            head.pop()
        out = head + ["\n"] + rest

        # Swap the off-screen attribution for a visible one.
        hits = 0
        for i, line in enumerate(out):
            for old, new in CREDITS:
                if old in line:
                    out[i] = line.replace(old, new)
                    hits += 1
        # HomeQuest.html is a stale duplicate: excluded from the deploy and
        # redirected to /, so it carries an older footer and needs no credit.
        expected = 0 if path == "HomeQuest.html" else 1
        if hits != expected:
            raise SystemExit(f"{path}: expected {expected} footer credit line(s), found {hits}")

        stripped += 1
        credited += hits
        if not args.check:
            with open(path, "w", encoding="utf-8") as fh:
                fh.writelines(out)
        print(f"  {path}: cut lines {starts[0]+1}-{ends[0]+1}, credit added")

    verb = "would strip" if args.check else "stripped"
    print(f"\n{verb} {stripped} blocks, {credited} footer credits")


if __name__ == "__main__":
    main()
