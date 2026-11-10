#!/usr/bin/env bash
# clean-noid: clean full.md -> clean.md for "No One Did It"
#  - drop front desktop/terminal mis-capture pages (Ghostty/VMark/capture log)
#  - strip Kindle UI noise: banner(split), Location line, top-toolbar icons, bookmark W
#  - keep in-text * (section breaks / copyright star)
#  - dedupe adjacent identical pages (trailing back-cover repeats)
set -eo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOK_NAME="${1:-no-one-did-it}"
case "$BOOK_NAME" in
  ""|.|..|*/*|*$'\n'*|*$'\r'*) echo "ERROR: book name must be one directory name" >&2; exit 1 ;;
esac
export SRC="$ROOT/output/$BOOK_NAME/full.md"
export DST="$ROOT/output/$BOOK_NAME/clean.md"

[ -f "$SRC" ] || { echo "ERROR: $SRC not found" >&2; exit 1; }
echo "Cleaning: $SRC -> $DST"

python3 <<'PYEOF'
import os, re, sys
from pathlib import Path

src = Path(os.environ['SRC']); dst = Path(os.environ['DST'])
text = src.read_text(encoding="utf-8")
if not text.strip():
    sys.exit("ERROR: full.md is empty; previous clean.md kept")

fm = re.match(r'^(---\n.*?\n---\n)', text, re.DOTALL)
frontmatter = fm.group(1) if fm else ""
body = text[len(frontmatter):]

# line-level UI noise (matched against stripped line, whole-line)
ui_patterns = [
    r'^[•1]?\s*Kindle Library\s*$',
    r'^NO ONE DID IT:\s*RESPONSIBILITY LAUNDERING.*$',     # banner full / left half
    r'^,?\s*FROM THE SCAPEGOAT TO THE ALGORITHM\s*$',      # banner right half
    r'^Learning reading speed.*$',
    r'^Location\s+\d[\d,]*\s+of\s+7654.*$',
    r'^Location\s+\d[\d,]*\s*$',
    r'^(of\s+)?7654\s*[•·]?\s*\d+\s*%?\s*$',
    r'^\d{1,3}\s*%\s*$',
    # Kindle top-toolbar icons (OCR variants)
    r'^[=E][:：]?\s*Q?\s*(Aa\w*)?\s*K?\s*$',   # =: / E: / =: Q / =: Q Aa / = Q Aa K
    r'^Q\s*Aa\w*\s*K?\s*$',          # Q Aa / Q Aar / Q Aa K
    r'^Aa\s*K?\s*$',                 # Aa / Aa K
    r'^Q\s*$',                       # lone Q (toolbar search)
    r'^W\s*$',                       # bookmark flag icon -> W
    r'^\*\s*K\s*$',                  # *K
    r'^K\s*$',                       # lone K
    r'^[:：]\s*$',
    r'^[<>‹›❮❯•=]\s*$',
]
ui_re = re.compile('|'.join(ui_patterns))

# front mis-capture page markers: drop a page if it contains >=2 of these
NOISE = ['Ghostty', 'VMark', 'Last login', 'Capturing', 'auto-capture', 'ttys',
         'captured (', 'Switch', 'Starting in', 'Estimated time', 'Delay:',
         'Book: no-one', 'Pages: 580', 'Gumroad', '20°C', 'File Edit Block',
         'subagent', 'kindle-to-product']

ocr_fixes = [(r'\bEcole\b', 'École')]

pages = re.split(r'(<!-- page \d+ -->)', body)
out, prev = [], ""

for i in range(0, len(pages), 2):
    if i == 0:
        chunk, marker, pnum = pages[i], "", None
    else:
        marker = pages[i-1] if i-1 < len(pages) else ""
        chunk  = pages[i]   if i   < len(pages) else ""
        m = re.search(r'page (\d+)', marker)
        pnum = int(m.group(1)) if m else None

    if pnum == 1:                                  # desktop mis-capture
        continue
    if sum(1 for n in NOISE if n in chunk) >= 2:   # terminal/editor mis-capture page
        continue

    lines = chunk.split('\n')
    kept = [ln for ln in lines if not ui_re.match(ln.strip())]
    cleaned = '\n'.join(kept)
    for pat, rep in ocr_fixes:
        cleaned = re.sub(pat, rep, cleaned)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    stripped = cleaned.strip()
    if stripped and stripped == prev:              # dedupe adjacent identical (back-cover repeats)
        continue
    prev = stripped

    if marker:
        out.append(marker)
    out.append(cleaned)

result = frontmatter + '\n'.join(out)
result = re.sub(r'\n{3,}', '\n\n', result)
dst.write_text(result, encoding="utf-8")
print(f"Done. full: {len(text):,} chars  clean: {len(result):,} chars")
print(f"words: {len(result.split()):,}   pages kept: {result.count('<!-- page')}")
PYEOF

echo "Cleaned: $DST ($(du -h "$DST" | cut -f1))"
