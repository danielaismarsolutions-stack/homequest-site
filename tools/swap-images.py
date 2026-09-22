#!/usr/bin/env python3
"""
Replace the base64 <img> tags in the homepages with <picture> elements
pointing at /images/.

Each data URI sits alone on its own line inside a single <img> tag, so the
whole operation is line-scoped. The payload is cut out of the line before any
attribute parsing happens, so no regex is ever run over the base64 itself.

Usage:  python3 tools/swap-images.py [--check]
"""

import argparse
import os
import re
import sys

from PIL import Image

DATA_URI = re.compile(r"data:image/(png|jpeg|jpg|webp);base64,[A-Za-z0-9+/=]+")
TARGETS = ["index.html", "nl/index.html", "es/index.html", "HomeQuest.html"]

SLUGS = {
    "Philippe Kamoun, founder of HomeQuest": "philippe-kamoun-founder",
    "Amsterdam canal at sunset": "amsterdam-canal-sunset",
    "Rotterdam Erasmus Bridge at sunset": "rotterdam-erasmus-bridge-sunset",
    "The Hague Binnenhof at night": "the-hague-binnenhof-night",
    "Utrecht canal terraces at dusk": "utrecht-canal-terraces-dusk",
    "Dutch church spire and row houses": "dutch-church-spire-row-houses",
}

# Brand standardisation (site audit item 10) applied to alt text in the same pass.
ALT_REWRITES = {
    "Philippe Kamoun, founder of HomeQuest": "Philippe Kamoun, founder of HQ Housing",
}


def attr(stub, name):
    m = re.search(r'\b' + name + r'="([^"]*)"', stub)
    return m.group(1) if m else None


def dimensions(slug):
    with Image.open(os.path.join("images", slug + ".webp")) as im:
        return im.size


def build(indent, slug, alt, style, loading):
    w, h = dimensions(slug)
    img = [
        f'<img src="/images/{slug}.webp"',
        f'width="{w}"',
        f'height="{h}"',
        f'loading="{loading}"',
        'decoding="async"',
        f'alt="{alt}"',
    ]
    if style:
        img.append(f'style="{style}"')
    return (
        f"{indent}<picture>\n"
        f'{indent}  <source srcset="/images/{slug}.avif" type="image/avif" />\n'
        f"{indent}  {' '.join(img)} />\n"
        f"{indent}</picture>\n"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    for path in TARGETS:
        if not os.path.exists(path):
            print(f"  ! skipping missing {path}", file=sys.stderr)
            continue

        before = os.path.getsize(path)
        out = []
        swapped = 0

        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                m = DATA_URI.search(line)
                if not m:
                    out.append(line)
                    continue

                # Excise the payload before touching the line with any other regex.
                stub = line[: m.start()] + "#" + line[m.end() :]
                if stub.count("<img") != 1:
                    raise SystemExit(f"{path}:{lineno}: expected exactly one <img> on the line")

                alt = attr(stub, "alt")
                slug = SLUGS.get(alt)
                if slug is None:
                    raise SystemExit(f"{path}:{lineno}: no image mapped for alt={alt!r}")

                indent = re.match(r"[ \t]*", stub).group(0)
                out.append(
                    build(
                        indent,
                        slug,
                        ALT_REWRITES.get(alt, alt),
                        attr(stub, "style"),
                        attr(stub, "loading") or "lazy",
                    )
                )
                swapped += 1

        if swapped != 6:
            raise SystemExit(f"{path}: expected 6 images, swapped {swapped}")

        if not args.check:
            with open(path, "w", encoding="utf-8") as fh:
                fh.writelines(out)
            after = os.path.getsize(path)
            print(f"{path:18s} {swapped} images  {before/1024/1024:7.2f} MB -> {after/1024:8.1f} KB")
        else:
            print(f"{path:18s} {swapped} images would be swapped")


if __name__ == "__main__":
    main()
