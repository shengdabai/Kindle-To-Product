#!/usr/bin/env bash
# ocr-smart: geometry-aware two-column OCR (uses compiled livetext_ocr_smart) -> full.md
set -eo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OCR_BIN="$ROOT/livetext_ocr_smart"
BOOK_NAME="${1:-no-one-did-it}"
case "$BOOK_NAME" in
  ""|.|..|*/*|*$'\n'*|*$'\r'*) echo "ERROR: book name must be one directory name" >&2; exit 1 ;;
esac
LANGS="${2:-en}"
OUTPUT_DIR="$ROOT/output/$BOOK_NAME"
PAGES_DIR="$OUTPUT_DIR/pages"
FULL_MD="$OUTPUT_DIR/full.md"
MANIFEST="$OUTPUT_DIR/manifest.json"

[ -x "$OCR_BIN" ] || { echo "ERROR: $OCR_BIN not built (run: swiftc -O livetext_ocr_smart.swift -o livetext_ocr_smart)" >&2; exit 1; }
[ -d "$PAGES_DIR" ] || { echo "ERROR: pages dir not found: $PAGES_DIR" >&2; exit 1; }

shopt -s nullglob
PAGE_FILES=("$PAGES_DIR"/page_*.png)
PAGE_COUNT=${#PAGE_FILES[@]}
[ "$PAGE_COUNT" -gt 0 ] || { echo "ERROR: no page images found" >&2; exit 1; }
STAGE=$(mktemp -d "$OUTPUT_DIR/.ocr-XXXXXX")
trap 'rm -rf "$STAGE"' EXIT
TEMP_MD="$STAGE/full.md"
for PAGE_FILE in "${PAGE_FILES[@]}"; do
  if [[ ! "${PAGE_FILE##*/}" =~ ^page_[0-9]+\.png$ ]]; then
    echo "ERROR: invalid page filename: $PAGE_FILE" >&2
    exit 1
  fi
done
printf '%s\n' "${PAGE_FILES[@]##*/}" | sort -t_ -k2,2n > "$STAGE/pages.txt"
PAGE_FILES=()
while IFS= read -r PAGE_NAME; do
  PAGE_FILES+=("$PAGES_DIR/$PAGE_NAME")
done < "$STAGE/pages.txt"
BOOK_TITLE=$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1], ensure_ascii=False))' "$BOOK_NAME")
ENGINE=$(python3 -c 'import json,sys; print(json.dumps("macOS Vision (smart two-column layout, " + sys.argv[1] + ")"))' "$LANGS")
echo "OCR (smart 2-col) $PAGE_COUNT images -> $FULL_MD"

cat > "$TEMP_MD" <<EOF
---
title: $BOOK_TITLE
source: Kindle Cloud Reader
extracted_at: $(date -Iseconds)
pages: $PAGE_COUNT
ocr_engine: $ENGINE
---

EOF

START=$(date +%s)
for PAGE_FILE in "${PAGE_FILES[@]}"; do
  PAGE_NUM=$(basename "$PAGE_FILE" .png | sed 's/page_0*//')
  [ -z "$PAGE_NUM" ] && PAGE_NUM=0

  if ! TEXT=$("$OCR_BIN" "$PAGE_FILE" "$LANGS"); then
    echo "ERROR: OCR failed: $PAGE_FILE; previous outputs kept" >&2
    exit 1
  fi
  if [[ ! "$TEXT" =~ [^[:space:]] ]]; then
    echo "ERROR: OCR empty: $PAGE_FILE; previous outputs kept" >&2
    exit 1
  fi

  {
    echo ""
    echo "<!-- page $PAGE_NUM -->"
    printf '%s\n' "$TEXT"
    echo ""
  } >> "$TEMP_MD"

  if [ $((PAGE_NUM % 50)) -eq 0 ]; then
    echo "[$PAGE_NUM/$PAGE_COUNT] done ($(($(date +%s) - START))s)"
  fi
done

WORDS=$(wc -w < "$TEMP_MD" | tr -d ' ')
SIZE=$(du -h "$TEMP_MD" | cut -f1)
python3 - "$BOOK_NAME" "$PAGE_COUNT" "$SIZE" "$WORDS" > "$STAGE/manifest.json" <<'PY'
import datetime, json, sys
book, pages, size, words = sys.argv[1:]
print(json.dumps(dict(book=book, source='Kindle Cloud Reader',
    extracted_at=datetime.datetime.now().isoformat(), pages_captured=int(pages),
    full_md_path='full.md', full_md_size=size, word_count=int(words),
    ocr_engine='macOS Vision smart two-column'), ensure_ascii=False, indent=2))
PY
mv "$TEMP_MD" "$FULL_MD"
mv "$STAGE/manifest.json" "$MANIFEST"

echo ""
echo "OCR complete ($(($(date +%s) - START))s) -> $FULL_MD ($SIZE, $WORDS words)"
