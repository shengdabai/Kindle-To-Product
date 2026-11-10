#!/usr/bin/env bash
# clean-md: 把 full.md 清理成可用的 clean.md
# - 去除每页 Kindle UI 横幅 / 全屏提示 / 底部 Location 行 / 控件符号
# - 修正常见 OCR 错字 (vears -> years, Cnanter -> Chapter 等)
# - 合并相邻重复行 (相邻整页重复全去掉)
# - 输出: clean.md (markdown 段落保持原样)

set -eo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOK_NAME="${1:-half-second}"
case "$BOOK_NAME" in
  ""|.|..|*/*|*$'\n'*|*$'\r'*) echo "ERROR: book name must be one directory name" >&2; exit 1 ;;
esac
SRC="$ROOT/output/$BOOK_NAME/full.md"
DST="$ROOT/output/$BOOK_NAME/clean.md"

if [ ! -f "$SRC" ]; then
  echo "ERROR: $SRC not found" >&2
  exit 1
fi

echo "Cleaning: $SRC -> $DST"

# 用 Python 做清理 (sed 处理多行模式跨平台麻烦)
python3 - "$SRC" "$DST" <<'PYEOF'
import re, sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
text = src.read_text(encoding="utf-8")
if not text.strip():
    sys.exit("ERROR: full.md is empty; previous clean.md kept")

# 1. 拆 frontmatter
fm_match = re.match(r'^(---\n.*?\n---\n)', text, re.DOTALL)
frontmatter = fm_match.group(1) if fm_match else ""
body = text[len(frontmatter):]

# 2. 行级清理 - 去掉 Kindle UI 噪音
ui_patterns = [
    r'^D Kindle Library\s*$',
    r'^THE HALF SECOND: HOW FIRST REACTIONS GET INSTALLED.*$',
    r'^若要退出全屏模式.*$',
    r'^esC\s*$',
    r'^=Q\s*Aa\s*$',
    r'^』\s*$',
    r'^：\s*$',
    r'^贝\s*$',
    r'^Back to\s*$',
    r'^\s*\d+\s*$',  # 孤立的数字行 (Location 数字单独成行的)
    r'^\d+\s*minute[s]?\s*left.*$',
    r'^Location \d+ of \d+.*$',
    r'^Learning reading speed.*$',
    r'^\d+%\s*$',
    r'^•Chapter\s*\d+:.*\(in TOC repeat\)$',  # 目录里章节占位
]
ui_re = re.compile('|'.join(ui_patterns), re.MULTILINE)

# 3. OCR 错字修正 (高置信度的明显错)
ocr_fixes = [
    (r'\bvears\b', 'years'),
    (r'\bCnanter\b', 'Chapter'),
    (r'\bReneat\b', 'Repeat'),
    (r'\bnast\b', 'past'),
    (r'\bnrotest\b', 'protest'),
    (r'\bkevboard\b', 'keyboard'),
    (r'•Chapter', '• Chapter'),
    (r'•lakeaways', '• Takeaways'),
    (r'lakeaways', 'Takeaways'),
    (r'Iquit', 'I quit'),
]

# 处理每页块
pages = re.split(r'(<!-- page \d+ -->)', body)
cleaned_pages = []
prev_text = ""

for i in range(0, len(pages), 2):
    if i == 0:
        # 前置文本 (frontmatter 之后第一页之前)
        chunk = pages[i]
        marker = ""
    else:
        marker = pages[i-1] if i-1 < len(pages) else ""
        chunk = pages[i] if i < len(pages) else ""

    # 删 UI 行
    lines = chunk.split('\n')
    kept = [ln for ln in lines if not ui_re.match(ln.strip())]
    cleaned = '\n'.join(kept)

    # 修 OCR 错字
    for pat, rep in ocr_fixes:
        cleaned = re.sub(pat, rep, cleaned)

    # 去多余空行 (>2 个空行变成 1 个)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    # 跟上一页内容完全一样的整页跳过 (末尾翻空了重复抓的页)
    stripped = cleaned.strip()
    if stripped and stripped == prev_text:
        continue
    prev_text = stripped

    if marker:
        cleaned_pages.append(marker)
    cleaned_pages.append(cleaned)

result = frontmatter + '\n'.join(cleaned_pages)

# 全局再压一次空行
result = re.sub(r'\n{3,}', '\n\n', result)

dst.write_text(result, encoding="utf-8")
print(f"Done. Source: {len(text)} chars  Clean: {len(result)} chars  ({len(result)*100//len(text)}%)")
PYEOF

SIZE_SRC=$(du -h "$SRC" | cut -f1)
SIZE_DST=$(du -h "$DST" | cut -f1)
WORDS_DST=$(wc -w < "$DST" | tr -d ' ')

echo ""
echo "Original: $SRC ($SIZE_SRC)"
echo "Cleaned:  $DST ($SIZE_DST, $WORDS_DST words)"
