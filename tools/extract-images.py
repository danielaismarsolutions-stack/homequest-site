#!/usr/bin/env python3
"""
Extract base64-embedded images from the HQ Housing homepages into /images/.

Reads each source file line by line and matches only a strict single-token
data-URI pattern, so nothing range-scoped or multi-line ever runs across the
large payloads. Each distinct image is decoded once, written as WebP + AVIF,
and reported with its before/after size.

Encoding rules
  - longest edge capped at MAX_EDGE (1600); every source is already smaller,
    so this is a no-op unless a larger image is added later
  - WebP quality 80; if the result is over MAX_BYTES the encoder steps down
    quality first, then resolution, preferring the largest image that fits
  - AVIF written at AVIF_QUALITY from the same chosen dimensions

Usage:  python3 tools/extract-images.py [--out images] [--dry-run]
"""

import argparse
import base64
import hashlib
import io
import os
import re
import sys

from PIL import Image

DATA_URI = re.compile(r"data:image/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=]+)")
ALT_ATTR = re.compile(r'alt="([^"]*)"')

SOURCES = ["index.html", "nl/index.html", "es/index.html", "HomeQuest.html"]

# Stable kebab-case filename per image, keyed by the alt text in the source.
SLUGS = {
    "Philippe Kamoun, founder of HomeQuest": "philippe-kamoun-founder",
    "Philippe Kamoun, founder of HQ Housing": "philippe-kamoun-founder",
    "Amsterdam canal at sunset": "amsterdam-canal-sunset",
    "Rotterdam Erasmus Bridge at sunset": "rotterdam-erasmus-bridge-sunset",
    "The Hague Binnenhof at night": "the-hague-binnenhof-night",
    "Utrecht canal terraces at dusk": "utrecht-canal-terraces-dusk",
    "Dutch church spire and row houses": "dutch-church-spire-row-houses",
}

MAX_EDGE = 1600
MAX_BYTES = 200 * 1024
WEBP_QUALITIES = [80, 78, 75, 72]
SCALES = [None, 1400, 1200, 1100, 1000, 900, 800]
AVIF_QUALITY = 55


def scaled(im, longest):
    """Return im resized so its longest edge is `longest`, or im if already smaller."""
    if longest is None:
        longest = MAX_EDGE
    w, h = im.size
    if max(w, h) <= longest:
        return im
    if w >= h:
        return im.resize((longest, round(h * longest / w)), Image.LANCZOS)
    return im.resize((round(w * longest / h), longest), Image.LANCZOS)


def encode(im, fmt, quality):
    buf = io.BytesIO()
    kwargs = {"quality": quality}
    if fmt == "WEBP":
        kwargs["method"] = 6
    im.save(buf, fmt, **kwargs)
    return buf.getvalue()


def best_webp(im):
    """Largest/highest-quality WebP that fits MAX_BYTES; falls back to the smallest tried."""
    smallest = None
    for longest in SCALES:
        candidate = scaled(im, longest)
        for q in WEBP_QUALITIES:
            blob = encode(candidate, "WEBP", q)
            if smallest is None or len(blob) < len(smallest[0]):
                smallest = (blob, candidate, q)
            if len(blob) <= MAX_BYTES:
                return blob, candidate, q
    return smallest


def find_images():
    """Yield (slug, alt, raw_bytes, source_file, line_no) for each distinct payload."""
    seen = {}
    for path in SOURCES:
        if not os.path.exists(path):
            print(f"  ! skipping missing source {path}", file=sys.stderr)
            continue
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                m = DATA_URI.search(line)
                if not m:
                    continue
                alt_m = ALT_ATTR.search(line[m.end():])
                alt = alt_m.group(1) if alt_m else ""
                slug = SLUGS.get(alt)
                if slug is None:
                    raise SystemExit(
                        f"{path}:{lineno}: no filename mapped for alt={alt!r}"
                    )
                raw = base64.b64decode(m.group(2))
                digest = hashlib.sha256(raw).hexdigest()
                if slug in seen:
                    if seen[slug] != digest:
                        raise SystemExit(
                            f"{path}:{lineno}: {slug} differs between source files"
                        )
                    continue
                seen[slug] = digest
                yield slug, alt, raw, path, lineno


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="images")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.dry_run:
        os.makedirs(args.out, exist_ok=True)

    total_src = total_webp = total_avif = 0
    print(f"{'file':34s} {'source':>10s} {'dims':>12s} {'webp':>9s} {'avif':>9s}  q")
    for slug, alt, raw, path, lineno in find_images():
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        webp, chosen, q = best_webp(im)
        avif = encode(chosen, "AVIF", AVIF_QUALITY)

        if not args.dry_run:
            with open(os.path.join(args.out, slug + ".webp"), "wb") as fh:
                fh.write(webp)
            with open(os.path.join(args.out, slug + ".avif"), "wb") as fh:
                fh.write(avif)

        total_src += len(raw)
        total_webp += len(webp)
        total_avif += len(avif)
        dims = f"{chosen.size[0]}x{chosen.size[1]}"
        print(
            f"{slug:34s} {len(raw)/1024:9.1f}K {dims:>12s} "
            f"{len(webp)/1024:8.1f}K {len(avif)/1024:8.1f}K  {q}"
        )

    print(
        f"{'TOTAL':34s} {total_src/1024:9.1f}K {'':>12s} "
        f"{total_webp/1024:8.1f}K {total_avif/1024:8.1f}K"
    )


if __name__ == "__main__":
    main()
