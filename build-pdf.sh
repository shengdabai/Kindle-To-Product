#!/usr/bin/env bash
# build-pdf: 中文 markdown → PDF via pandoc + xelatex
# 用 macOS 自带 Songti SC (正文) / Heiti SC (标题/strong) / Menlo (代码)

set -eo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOK_NAME="${1:-half-second}"
case "$BOOK_NAME" in
  ""|.|..|*/*|*$'\n'*|*$'\r'*) echo "ERROR: book name must be one directory name" >&2; exit 1 ;;
esac
SRC="$ROOT/output/$BOOK_NAME/clean-zh.md"
DST="$ROOT/output/$BOOK_NAME/clean-zh.pdf"

if [ ! -f "$SRC" ]; then
  echo "ERROR: source not found: $SRC" >&2
  exit 1
fi

STAGE=$(mktemp -d "$ROOT/output/$BOOK_NAME/.pdf-XXXXXX")
trap 'rm -rf "$STAGE"' EXIT
TEMP_PDF="$STAGE/clean-zh.pdf"
echo "Rendering: $SRC -> $DST"
echo "(this may take 30-60s for ~60k Chinese chars)"
echo ""

pandoc "$SRC" \
  -o "$TEMP_PDF" \
  --pdf-engine=xelatex \
  -V CJKmainfont="Songti SC" \
  -V CJKsansfont="Heiti SC" \
  -V CJKmonofont="Heiti SC" \
  -V mainfont="Songti SC" \
  -V mainfontoptions:"Mapping=tex-text" \
  -V mainfontoptions:"FallbackFont=Arial Unicode MS" \
  -V sansfont="Heiti SC" \
  -V monofont="Menlo" \
  -V geometry:"a4paper,margin=2cm" \
  -V fontsize=11pt \
  -V linestretch=1.5 \
  -V documentclass=article \
  -V colorlinks=true \
  -V linkcolor=NavyBlue \
  -V urlcolor=NavyBlue \
  -V toc-depth=2 \
  --toc \
  --metadata lang=zh-CN \
  --highlight-style=tango \
  2>&1 | tail -10

if [ -s "$TEMP_PDF" ]; then
  mv "$TEMP_PDF" "$DST"
  SIZE=$(du -h "$DST" | cut -f1)
  echo ""
  echo "✅ PDF generated: $DST ($SIZE)"
else
  echo "❌ PDF generation failed" >&2
  exit 1
fi
