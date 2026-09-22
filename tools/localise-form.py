#!/usr/bin/env python3
"""
Make the intake form's static HTML match the page's own language.

Before: /nl/ and /es/ shipped the form in English and translated it in the
browser on load, so the source, and anything reading it without running JS,
was always English.

After: the markup on /nl/ and /es/ carries the Dutch / Spanish strings, and an
explicit `en` dictionary, built here from the English that was in the markup,
drives the EN toggle. The runtime path becomes symmetrical: every language is
a dictionary lookup, so the DOM snapshot is no longer needed.

Field names, ids, values and anything the n8n webhook reads are untouched:
only text nodes, placeholders and month labels change.

Usage:  python3 tools/localise-form.py [--check]
"""

import argparse
import html
import json
import re
import sys

sys.path.insert(0, "tools")
import formi18n as F

EN_MONTHS = ["January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December"]

# Which dictionary each page's static markup should be written in.
PAGES = {"index.html": None, "nl/index.html": "nl", "es/index.html": "es"}

SNAPSHOT_START = "  // Snapshot of the original English text so we can restore it when switching back to EN.\n"
APPLY_END = "      btnNextLabel.textContent = (step === totalStepsNow()) ? (t['foot.submit'] || 'Submit intake') : (t['foot.continue'] || 'Continue');\n    }\n"

NEW_APPLY = """  function applyFormLang(lang){
    if (!VALID_LANGS.includes(lang)) lang = 'en';
    document.documentElement.setAttribute('data-form-lang', lang);

    const t = FORM_I18N[lang];
    if (t){
      document.querySelectorAll('#intakeModal [data-i18n]').forEach(el => {
        const k = el.getAttribute('data-i18n');
        if (t[k] != null) el.textContent = t[k];
      });
      document.querySelectorAll('#intakeModal [data-i18n-html]').forEach(el => {
        const k = el.getAttribute('data-i18n-html');
        if (t[k] != null) el.innerHTML = t[k];
      });
      // Placeholders
      const ph = t.placeholder || {};
      Object.entries(ph).forEach(([name, value]) => {
        form.querySelectorAll('[name="'+name+'"]').forEach(el => el.setAttribute('placeholder', value));
      });
      // Month options (keep first empty option as the label)
      if (Array.isArray(t.months)){
        form.querySelectorAll('select[name$="_month"]').forEach(sel => {
          const opts = sel.querySelectorAll('option');
          for (let i = 1; i < opts.length && i <= t.months.length; i++){
            opts[i].textContent = t.months[i-1];
          }
        });
      }
      // Footer button label
      btnNextLabel.textContent = (step === totalStepsNow()) ? (t['foot.submit'] || 'Submit intake') : (t['foot.continue'] || 'Continue');
      const backBtn = document.getElementById('btnBack');
      if (backBtn && t['foot.back']) backBtn.textContent = t['foot.back'];
    }
"""


def regions(html):
    """(modal_start, dict_start, valid_langs_start) offsets."""
    a = html.find('id="intakeModal"')
    b = html.find("const FORM_I18N")
    c = html.find("const VALID_LANGS")
    assert a > 0 and a < b < c, "unexpected page structure"
    return a, b, c


def read_dict(html, lang):
    """Pull one language object out of the FORM_I18N literal as JSON."""
    b, c = html.find("const FORM_I18N"), html.find("const VALID_LANGS")
    src = html[b:c]
    start = src.find(f"\n    {lang}: {{")
    assert start > 0, f"no {lang} dictionary"
    depth, i = 0, src.find("{", start)
    body_start = i
    while True:
        ch = src[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if not depth:
                break
        elif ch in "'\"":
            i = skip_string(src, i)
        i += 1
    return src[body_start : i + 1]


def skip_string(src, i):
    quote, i = src[i], i + 1
    while src[i] != quote:
        if src[i] == "\\":
            i += 1
        i += 1
    return i


def js_object_to_py(body):
    """Evaluate a literal-only JS object by translating it to JSON."""
    out, i, n = [], 0, len(body)
    while i < n:
        ch = body[i]
        if ch == "/" and body[i : i + 2] == "//":
            i = body.find("\n", i)
            if i < 0:
                break
            continue
        if ch in "'\"":
            j = skip_string(body, i)
            raw = body[i : j + 1]
            inner = raw[1:-1].replace("\\'", "'").replace('\\"', '\\"')
            out.append(json.dumps(inner.encode().decode("unicode_escape") if "\\u" in inner else inner))
            i = j + 1
            continue
        if ch.isalpha() or ch == "_":
            m = re.match(r"[A-Za-z_][\w]*", body[i:])
            word = m.group(0)
            after = body[i + len(word):].lstrip()
            if after.startswith(":"):
                out.append(json.dumps(word))
                i += len(word)
                continue
        out.append(ch)
        i += 1
    text = "".join(out)
    text = re.sub(r",(\s*[}\]])", r"\1", text)  # trailing commas
    return json.loads(text)


def build_en(html):
    """The English strings currently in this page's markup."""
    a, b, _ = regions(html)
    modal = html[a:b]
    d = {}
    for key in dict.fromkeys(F.keys_in(modal, "data-i18n")):
        inner = F.get_inner(modal, "data-i18n", key)
        if inner is not None:
            d[key] = F.text_of(inner)
    for key in dict.fromkeys(F.keys_in(modal, "data-i18n-html")):
        inner = F.get_inner(modal, "data-i18n-html", key)
        if inner is not None:
            d[key] = re.sub(r"\s+", " ", inner).strip()
    d["foot.continue"] = "Continue"
    d["foot.submit"] = "Submit intake"
    d["months"] = EN_MONTHS
    d["placeholder"] = F.placeholders_in(modal)
    return d


def render_dict(lang, d):
    lines = [f"    {lang}: {{"]
    for k, v in d.items():
        if k in ("months", "placeholder"):
            continue
        lines.append(f"      {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)},")
    lines.append(f"      'months': {json.dumps(d['months'], ensure_ascii=False)},".replace('"', "'"))
    lines.append("      'placeholder': {")
    items = list(d["placeholder"].items())
    for i, (name, value) in enumerate(items):
        comma = "" if i == len(items) - 1 else ","
        lines.append(f"        {name}: {json.dumps(value, ensure_ascii=False)}{comma}")
    lines.append("      }")
    lines.append("    },")
    return "\n".join(lines) + "\n"


def localise(html, target):
    """Write the target language's strings into the static markup."""
    a, b, _ = regions(html)
    modal, rest = html[a:b], html[b:]
    t = js_object_to_py(read_dict(html, target))

    changed = 0
    for attr in ("data-i18n", "data-i18n-html"):
        for key in dict.fromkeys(F.keys_in(modal, attr)):
            if key not in t:
                continue
            # data-i18n is assigned via textContent at runtime, so its
            # dictionary value is plain text and must be escaped for markup.
            value = t[key] if attr == "data-i18n-html" else html.escape(t[key], quote=False)
            modal, ok = F.set_inner(modal, attr, key, value)
            changed += ok
    for name, value in (t.get("placeholder") or {}).items():
        modal = F.set_placeholder(modal, name, value)
    # Month <option> labels, keeping the first (the "Month" placeholder option).
    for m in re.finditer(r'<select\b[^>]*name="[^"]*_month"[^>]*>.*?</select>', modal, re.S):
        block = m.group(0)
        opts = re.findall(r"<option\b[^>]*>.*?</option>", block, re.S)
        new_block = block
        for i, opt in enumerate(opts[1:13]):
            new_opt = re.sub(r">([^<]*)</option>", f">{t['months'][i]}</option>", opt)
            new_block = new_block.replace(opt, new_opt, 1)
        modal = modal.replace(block, new_block, 1)

    return html[:a] + modal + rest, changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    for path, target in PAGES.items():
        html = open(path, encoding="utf-8").read()
        if "\n    en: {" in html:
            print(f"{path}: already localised, skipping")
            continue

        en = build_en(html)
        if target:
            html, changed = localise(html, target)
        else:
            changed = 0

        # Insert the en dictionary at the head of FORM_I18N.
        anchor = "  const FORM_I18N = {\n"
        assert html.count(anchor) == 1, path
        html = html.replace(anchor, anchor + render_dict("en", en))

        # Replace the DOM-snapshot restore path with a dictionary lookup.
        s = html.find(SNAPSHOT_START)
        e = html.find(APPLY_END)
        assert s > 0 and e > s, (path, "apply block not found")
        html = html[:s] + NEW_APPLY + html[e + len(APPLY_END):]

        if not args.check:
            open(path, "w", encoding="utf-8").write(html)
        print(f"{path}: en dictionary added ({len(en)-2} strings, "
              f"{len(en['placeholder'])} placeholders), {changed} elements localised"
              f"{' [check only]' if args.check else ''}")


if __name__ == "__main__":
    main()
