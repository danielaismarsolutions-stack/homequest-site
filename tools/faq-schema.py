#!/usr/bin/env python3
"""
Build FAQPage JSON-LD from the FAQ that is already visible on a page.

Questions and answers are read out of the rendered <details>/<summary> markup
with html.parser, so the schema can only ever contain text a visitor can see.
Nothing is authored here.

Usage:  python3 tools/faq-schema.py --list <file>       # show what was found
        python3 tools/faq-schema.py --emit <file>       # print the JSON-LD
        python3 tools/faq-schema.py --insert <file>...  # write it into the page
"""

import argparse
import json
import re
import sys
from html.parser import HTMLParser

VOID = {"br", "img", "input", "hr", "meta", "link", "source", "path", "svg"}


class FaqReader(HTMLParser):
    """Collect (question, answer) pairs from <details> elements."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self.depth = 0          # nesting depth inside the current <details>
        self.mode = None        # None | 'summary' | 'body'
        self.buf = []
        self.q = None
        self.skip = 0           # inside <svg>, which carries no readable text

    def handle_starttag(self, tag, attrs):
        if tag == "svg":
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "details":
            self.depth = 1
            self.q = None
            return
        if not self.depth:
            return
        if tag == "summary":
            self.mode, self.buf = "summary", []
        elif self.q is not None and self.mode is None:
            # first element after the summary is the answer body
            self.mode, self.buf = "body", []
        elif tag == "br" and self.mode:
            self.buf.append("\n")

    def handle_endtag(self, tag):
        if tag == "svg":
            self.skip = max(0, self.skip - 1)
            return
        if self.skip or not self.depth:
            return
        if tag == "summary" and self.mode == "summary":
            self.q = self.flush()
            self.mode = None
        elif tag == "details":
            if self.mode == "body":
                answer = self.flush()
                if self.q and answer:
                    self.items.append((self.q, answer))
            self.depth = 0
            self.mode = None
            self.q = None

    def handle_data(self, data):
        if self.mode and not self.skip:
            self.buf.append(data)

    def flush(self):
        text = "".join(self.buf)
        # <br><br> in the source is a paragraph break in the rendered answer.
        text = re.sub(r"[ \t]*\n[ \t]*\n[ \t]*", "\u0000", text)
        text = re.sub(r"\s+", " ", text)
        return text.replace("\u0000", " ").strip()


def read_faq(path):
    p = FaqReader()
    p.feed(open(path, encoding="utf-8").read())
    return p.items


def schema(path, items, url, lang):
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "inLanguage": lang,
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in items
        ],
    }


def page_meta(path):
    txt = open(path, encoding="utf-8").read(8000)
    lang = re.search(r'<html lang="([^"]+)"', txt)
    canon = re.search(r'<link rel="canonical" href="([^"]+)"', txt)
    return (lang.group(1) if lang else "en"), (canon.group(1) if canon else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--insert", action="store_true")
    ap.add_argument("files", nargs="+")
    args = ap.parse_args()

    for path in args.files:
        items = read_faq(path)
        lang, url = page_meta(path)

        if args.list:
            print(f"\n=== {path}  ({len(items)} Q&A, lang={lang})")
            for i, (q, a) in enumerate(items, 1):
                print(f"  {i}. Q: {q}")
                print(f"     A: {a[:150]}{'...' if len(a) > 150 else ''}")
            continue

        if not items:
            print(f"{path}: no FAQ found, skipping", file=sys.stderr)
            continue

        blob = json.dumps(schema(path, items, url, lang), ensure_ascii=False, indent=2)
        block = f'<script type="application/ld+json">\n{blob}\n</script>\n'

        if args.emit:
            print(f"--- {path}\n{block}")
            continue

        txt = open(path, encoding="utf-8").read()
        if '"FAQPage"' in txt:
            print(f"{path}: already has FAQPage, skipping")
            continue
        anchor = "\n<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\" />"
        if anchor in txt:
            txt = txt.replace(anchor, "\n" + block + anchor, 1)
        else:
            anchor = "</head>"
            txt = txt.replace(anchor, block + anchor, 1)
        open(path, "w", encoding="utf-8").write(txt)
        print(f"{path}: FAQPage added ({len(items)} Q&A)")


if __name__ == "__main__":
    main()
