#!/usr/bin/env bash
# ocr-pages: macOS Live Text OCR on captured PNGs -> Markdown
# Handles English + Simplified Chinese mixed.

set -eo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SWIFT_OCR="$ROOT/livetext_ocr.swift"

BOOK_NAME="${1:-half-second}"
case "$BOOK_NAME" in
  ""|.|..|*/*|*$'\n'*|*$'\r'*) echo "ERROR: book name must be one directory name" >&2; exit 1 ;;
esac
OUTPUT_DIR="$ROOT/output/$BOOK_NAME"
PAGES_DIR="$OUTPUT_DIR/pages"
FULL_MD="$OUTPUT_DIR/full.md"
MANIFEST="$OUTPUT_DIR/manifest.json"

if [ ! -d "$PAGES_DIR" ]; then
  echo "ERROR: pages dir not found: $PAGES_DIR" >&2
  exit 1
fi

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
echo "OCR processing $PAGE_COUNT images -> $FULL_MD"
echo ""

cat > "$TEMP_MD" <<EOF
---
title: $BOOK_TITLE
source: Kindle Cloud Reader
extracted_at: $(date -Iseconds)
pages: $PAGE_COUNT
ocr_engine: macOS Live Text (zh-Hans,en)
---

EOF

START=$(date +%s)
for PAGE_FILE in "${PAGE_FILES[@]}"; do
  PAGE_NUM=$(basename "$PAGE_FILE" .png | sed 's/page_0*//')
  [ -z "$PAGE_NUM" ] && PAGE_NUM=0

  if ! TEXT=$(swift "$SWIFT_OCR" "$PAGE_FILE" "zh-Hans,en"); then
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

  if [ $((PAGE_NUM % 20)) -eq 0 ]; then
    ELAPSED=$(($(date +%s) - START))
    echo "[$PAGE_NUM/$PAGE_COUNT] done (${ELAPSED}s)"
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
    ocr_engine='macOS Live Text'), ensure_ascii=False, indent=2))
PY
mv "$TEMP_MD" "$FULL_MD"
mv "$STAGE/manifest.json" "$MANIFEST"

TOTAL=$(($(date +%s) - START))
echo ""
echo "OCR complete (${TOTAL}s)"
echo "Output: $FULL_MD ($SIZE, $WORDS words)"
echo "Manifest: $MANIFEST"
echo ""
echo "Optional: ingest to gbrain"
echo "  gbrain put --source kindle-$BOOK_NAME --tag book $FULL_MD"
