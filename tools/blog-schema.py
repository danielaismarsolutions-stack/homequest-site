#!/usr/bin/env python3
"""
Add publisher.logo to the BlogPosting / Blog schema and a BreadcrumbList to
every blog index and article.

Breadcrumb labels reuse the words already visible on the page: the "Journal" /
"Blog" back-link in the article eyebrow, and the site's own home label.

Usage:  python3 tools/blog-schema.py
"""

import json
import os
import re
import subprocess

SITE = "https://www.hqhousing.com"
LOGO = {
    "@type": "ImageObject",
    "url": f"{SITE}/icon-512.png",
    "width": 512,
    "height": 512,
}

OLD_PUBLISHER = '"publisher":{"@type":"Organization","name":"HQ Housing","legalName":"Home Quest Housing Solutions S.L."}'
NEW_PUBLISHER = (
    '"publisher":{"@type":"Organization","name":"HQ Housing",'
    '"legalName":"Home Quest Housing Solutions S.L.",'
    '"logo":{"@type":"ImageObject","url":"https://www.hqhousing.com/icon-512.png",'
    '"width":512,"height":512}}'
)

# Home label and blog index URL per language prefix.
LANGS = {
    "": ("Home", f"{SITE}/", f"{SITE}/blog/"),
    "nl/": ("Home", f"{SITE}/nl/", f"{SITE}/nl/blog/"),
    "es/": ("Inicio", f"{SITE}/es/", f"{SITE}/es/blog/"),
}


def lang_prefix(path):
    for p in ("nl/", "es/"):
        if path.startswith(p):
            return p
    return ""


def read(path, n=None):
    with open(path, encoding="utf-8") as fh:
        return fh.read() if n is None else fh.read(n)


def breadcrumb(items):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": name, "item": url}
            for i, (name, url) in enumerate(items, 1)
        ],
    }


def insert_schema(path, txt, obj):
    blob = json.dumps(obj, ensure_ascii=False, indent=2)
    block = f'<script type="application/ld+json">\n{blob}\n</script>\n'
    anchor = '\n<link rel="preconnect" href="https://fonts.googleapis.com" />'
    assert anchor in txt, path
    return txt.replace(anchor, "\n" + block + anchor, 1)


def main():
    files = [
        f
        for f in subprocess.check_output(["git", "ls-files", "-z", "*blog/*.html"])
        .decode()
        .split("\0")
        if f
    ]

    for path in sorted(files):
        txt = read(path)
        prefix = lang_prefix(path)
        home_label, home_url, blog_url = LANGS[prefix]
        changed = []

        if OLD_PUBLISHER in txt:
            txt = txt.replace(OLD_PUBLISHER, NEW_PUBLISHER)
            changed.append("publisher.logo")

        if '"BreadcrumbList"' not in txt:
            is_index = os.path.basename(path) == "index.html"
            # The visible back-link text is the blog's own name on this page.
            m = re.search(r'<a href="index\.html">←\s*([^<]+)</a>', txt)
            blog_label = m.group(1).strip() if m else ("Journal" if prefix != "es/" else "Blog")

            if is_index:
                # The blog index calls itself by its <h1>; fall back to the schema name.
                n = re.search(r'"name":"HQ Housing (\w+)"', txt)
                label = n.group(1) if n else blog_label
                items = [(home_label, home_url), (label, blog_url)]
            else:
                head = re.search(r'"headline":"((?:[^"\\]|\\.)*)"', txt)
                canon = re.search(r'<link rel="canonical" href="([^"]+)"', txt)
                items = [
                    (home_label, home_url),
                    (blog_label, blog_url),
                    (json.loads(f'"{head.group(1)}"'), canon.group(1)),
                ]

            txt = insert_schema(path, txt, breadcrumb(items))
            changed.append(f"BreadcrumbList({len(items)})")

        if changed:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(txt)
            print(f"{path}: {', '.join(changed)}")
        else:
            print(f"{path}: no change")


if __name__ == "__main__":
    main()
