#!/usr/bin/env python3
"""Merge a complete, contiguous set of translated chunks into clean-zh.md."""
import argparse
import json
import os
import re
from pathlib import Path
from datetime import datetime

def retained_metadata(path: Path) -> str:
    """Keep handwritten YAML verbatim; only regeneration fields are replaced."""
    if not path.exists():
        return ''
    text = path.read_text(encoding='utf-8')
    if not text.startswith('---\n'):
        return ''
    match = re.match(r'^---\n(.*?)^---[ \t]*(?:\n|$)', text, re.DOTALL | re.MULTILINE)
    if not match:
        raise ValueError('existing output has unclosed frontmatter; refusing to overwrite')
    kept = []
    generated = False
    for line in match[1].splitlines(keepends=True):
        if line and not line[0].isspace() and not line.startswith('#'):
            generated = bool(re.match(
                r'''^(?:translated_chars|translated_at|"translated_chars"|"translated_at"|'translated_chars'|'translated_at')\s*:''', line))
        if not generated or line.startswith('#'):
            kept.append(line)
    return ''.join(kept).rstrip('\n') + '\n'

def strip_frontmatter(text: str) -> str:
    """Remove leading YAML frontmatter if present."""
    m = re.match(r'^---\n.*?\n---\n', text, re.DOTALL)
    if m:
        return text[m.end():].lstrip('\n')
    return text

def check_terminology(text: str) -> dict:
    """Quick consistency scan: for key terms, count each variant in the merged text."""
    # Key terms to spot-check (from the iron-law list)
    must_terms = [
        ("半秒", "Half Second 译法"),
        ("频次计数器", "frequency counter 译法"),
        ("第一反应", "first reaction 译法"),
        ("身份脚本", "identity script 译法"),
        ("触发", "trigger 译法"),
        ("意志力", "willpower 译法"),
        ("从不", "never (universal scope)"),
        ("每次都", "always (universal scope)"),
        ("ARISE", "保留缩写"),
        ("「肯定式宣言」", "affirmations 带引号"),
        ("李笑来", "作者名"),
        ("丹尼尔·卡尼曼", "Kahneman 译名"),
    ]
    counts = {}
    for term, note in must_terms:
        counts[f"{term} ({note})"] = text.count(term)
    # Variant-detection: check for inconsistent translations
    variants = {
        "半秒钟 vs 半秒 (期望: 只用'半秒')": text.count("半秒钟"),
        "形成 vs 装上 (install 错译)": text.count("形成"),
        "不会 vs 从不 (never 误译)": text.count("不会"),
    }
    return {"counts": counts, "variants": variants}

def chunk_files(directory: Path) -> list[Path]:
    files = list(directory.glob('chunk-*.md'))
    numbered = {}
    for path in files:
        match = re.fullmatch(r'chunk-(\d+)\.md', path.name)
        if not match or int(match[1]) < 1 or int(match[1]) in numbered:
            raise ValueError(f'invalid or duplicate chunk filename: {path.name}')
        numbered[int(match[1])] = path
    if not numbered:
        raise ValueError(f'no chunks found: {directory}')
    if any(number != expected for expected, number in enumerate(sorted(numbered), 1)):
        raise ValueError(f'chunk sequence has gaps: {directory}')
    return [numbered[n] for n in sorted(numbered)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=Path(os.environ.get(
        'WORK', Path(__file__).resolve().parent / 'output' / 'half-second')))
    args = parser.parse_args()
    root = args.work
    out = root / 'clean-zh.md'
    try:
        metadata = retained_metadata(out)
        paths = chunk_files(root / 'chunks-zh')
        source_dir = root / 'chunks'
        if source_dir.exists():
            sources = chunk_files(source_dir)
            if len(sources) != len(paths):
                raise ValueError(f'translation count {len(paths)} does not match source count {len(sources)}')
        chunks = []
        for number, path in enumerate(paths, 1):
            text = path.read_text(encoding='utf-8')
            # If the translator retained a chunk header, use its total to catch a missing tail.
            header = re.match(r'^---\n.*?\n---\n', text, re.DOTALL)
            chunk_header = re.search(r'(?m)^chunk:\s*(\d+)/(\d+)\s*$', header[0]) if header else None
            comment_header = re.match(r'<!-- chunk (\d+)/(\d+) \|[^\n]*-->\n*', text)
            info = chunk_header or comment_header
            if info and (int(info[1]) != number or int(info[2]) != len(paths)):
                raise ValueError(f'chunk header disagrees with sequence: {path.name}')
            text = strip_frontmatter(text)
            text = re.sub(r'^<!-- chunk \d+/\d+ \|[^\n]*-->\n*', '', text)
            if not text.strip():
                raise ValueError(f'empty translation: {path.name}')
            chunks.append(text)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    # Repetition can be intentional prose; never deduplicate translated lines.
    body = "\n\n".join(chunks)
    body = re.sub(r'\n{3,}', '\n\n', body)
    title = '半秒 (The Half Second)' if root.name == 'half-second' else root.name
    defaults = {'title': title, 'source': 'Kindle Cloud Reader OCR + 中文翻译', 'lang': 'zh-CN'}
    for key, value in defaults.items():
        if not re.search(rf'''(?m)^(?:{key}|"{key}"|'{key}')\s*:''', metadata):
            metadata += f'{key}: {json.dumps(value, ensure_ascii=False)}\n'
    frontmatter = ('---\n' + metadata +
                   f'translated_chars: {len(body)}\n'
                   f'translated_at: {datetime.now().isoformat()}\n'
                   '---\n\n')
    out.write_text(frontmatter + body, encoding='utf-8')
    print(f'merged {len(chunks)} chunks -> {out} ({len(body):,} chars)')
    if root.name == 'half-second':
        check = check_terminology(body)
        print('术语一致性快查（出现次数不代表翻译质量）：')
        for group in check.values():
            for term, count in group.items():
                print(f'  {term}: {count}')
    print(f"page 标记数: {len(re.findall(r'<!-- page [0-9]+ -->', body))}")


if __name__ == '__main__':
    main()
