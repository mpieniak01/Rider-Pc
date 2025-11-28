#!/usr/bin/env python3
from pathlib import Path
import re
import json

ROOT = Path('web')
CSS_FILES = sorted((ROOT / 'assets').glob('*.css')) + sorted((ROOT / 'assets' / 'pages').glob('*.css'))
HTML_FILES = sorted(ROOT.glob('*.html'))

CLASS_RE = re.compile(r'class="([^"]+)"')
ID_RE = re.compile(r'id="([^"]+)"')
SELECTOR_CLASS_RE = re.compile(r'\.[A-Za-z0-9_-]+')
SELECTOR_ID_RE = re.compile(r'#[A-Za-z0-9_-]+')

used_classes = set()
used_ids = set()
for html in HTML_FILES:
    text = html.read_text(encoding='utf-8', errors='ignore')
    for cls in CLASS_RE.findall(text):
        for part in re.split(r'\s+', cls.strip()):
            if part:
                used_classes.add(part)
    for _id in ID_RE.findall(text):
        if _id:
            used_ids.add(_id)

summary = []
for css in CSS_FILES:
    text = css.read_text(encoding='utf-8', errors='ignore')
    selectors = set(SELECTOR_CLASS_RE.findall(text) + SELECTOR_ID_RE.findall(text))
    class_hits = 0
    class_total = 0
    id_hits = 0
    id_total = 0
    for token in selectors:
        if token.startswith('.'):
            class_total += 1
            if token[1:] in used_classes:
                class_hits += 1
        elif token.startswith('#'):
            id_total += 1
            if token[1:] in used_ids:
                id_hits += 1
    summary.append(
        {
            'stylesheet': str(css.relative_to(ROOT)),
            'class_selectors': class_total,
            'class_matched': class_hits,
            'id_selectors': id_total,
            'id_matched': id_hits,
        }
    )

Path('logs').mkdir(exist_ok=True)
out = Path('logs/css_static_usage.json')
out.write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
