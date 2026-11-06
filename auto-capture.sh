#!/usr/bin/env bash
# auto-capture: full-auto Kindle Cloud Reader screenshot tool
# No browser hooks. Pure macOS system level (screencapture + AppleScript).
#
# Usage:
#   ./auto-capture.sh [--resume] <pages> [book-name] [delay-seconds]
# Example:
#   ./auto-capture.sh 320 half-second 6

set -eo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RESUME=false
if [ "${1:-}" = "--resume" ]; then
  RESUME=true
  shift
fi

if [ $# -lt 1 ]; then
  echo "Usage: $0 [--resume] <pages> [book-name] [delay-seconds]" >&2
  echo "Example: $0 320 half-second 6" >&2
  exit 1
fi

PAGES="$1"
BOOK_NAME="${2:-half-second}"
case "$BOOK_NAME" in
  ""|.|..|*/*|*$'\n'*|*$'\r'*) echo "ERROR: book name must be one directory name" >&2; exit 1 ;;
  # Catches a misplaced option such as "2 --resume 0"; --resume must come first.
  -*) echo "ERROR: book name must not start with '-' (put --resume before <pages>)" >&2; exit 1 ;;
esac
DELAY="${3:-6}"
if [[ ! "$PAGES" =~ ^[1-9][0-9]*$ || ! "$DELAY" =~ ^[0-9]+$ ]]; then
  echo "ERROR: pages must be positive; delay must be a nonnegative integer" >&2
  exit 1
fi
OUTPUT_DIR="$ROOT/output/$BOOK_NAME"
PAGES_DIR="$OUTPUT_DIR/pages"

mkdir -p "$PAGES_DIR"
shopt -s nullglob
EXISTING=("$PAGES_DIR"/page_*.png)
if [ "${#EXISTING[@]}" -gt 0 ] && [ "$RESUME" = false ]; then
  echo "ERROR: existing captures found; use a new book directory or --resume after positioning the book at page 1" >&2
  exit 1
fi

echo ""
echo "Book: $BOOK_NAME"
echo "Pages: $PAGES"
echo "Output: $OUTPUT_DIR"
echo "Delay: ${DELAY}s per page"
echo "Estimated time: $((PAGES * DELAY / 60)) min"
echo ""
echo "Switch to Chrome NOW. Make sure the book page is on top and full-screen."
if [ "$RESUME" = true ]; then
  echo "Resume: start at page 1 of this capture sequence; existing screenshots will be kept."
fi
echo ""

for i in 5 4 3 2 1; do
  echo "  Starting in $i ..."
  sleep 1
done

echo ""
echo "Capturing..."
echo ""

# Prevent sleep during capture
caffeinate -d -i -s &
CAFFEINATE_PID=$!
trap 'kill "$CAFFEINATE_PID" 2>/dev/null || true' EXIT

# Activate Chrome once
osascript -e 'tell application "Google Chrome" to activate' || {
  echo "ERROR: Chrome activation failed; capture stopped" >&2
  exit 1
}
sleep 1

i=1
while [ "$i" -le "$PAGES" ]; do
  PAGE_FILE=$(printf "%s/page_%04d.png" "$PAGES_DIR" "$i")

  # -s: an interrupted run can leave a 0-byte screenshot; capture that page again.
  if [ "$RESUME" = true ] && [ -s "$PAGE_FILE" ]; then
    echo "[$i/$PAGES] exists, skip"
  else
    screencapture -x "$PAGE_FILE"

    if [ $((i % 10)) -eq 0 ] || [ "$i" -eq 1 ]; then
      SIZE=$(du -h "$PAGE_FILE" | cut -f1)
      echo "[$i/$PAGES] captured ($SIZE)"
    fi
  fi

  if [ "$i" -lt "$PAGES" ]; then
    # ArrowRight key code 124, sent via System Events
    osascript -e 'tell application "System Events" to key code 124' >/dev/null || {
      echo "ERROR: page turn failed; capture stopped before page $((i + 1))" >&2
      exit 1
    }
    sleep "$DELAY"
  fi

  i=$((i + 1))
done

kill $CAFFEINATE_PID 2>/dev/null || true

echo ""
echo "Capture complete: $PAGES pages -> $PAGES_DIR"
echo ""
echo "Starting OCR..."
echo ""

exec "$ROOT/ocr-pages.sh" "$BOOK_NAME"
