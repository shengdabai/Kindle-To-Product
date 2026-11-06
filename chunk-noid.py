#!/usr/bin/env python3
"""Split clean.md into word-targeted chunks without cutting page blocks."""
import argparse
import os
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, default=Path(os.environ.get(
        'WORK', Path(__file__).resolve().parent / 'output' / 'no-one-did-it')))
    parser.add_argument('--target', default=os.environ.get('TARGET', '11000'))
    args = parser.parse_args()
    try:
        target = int(args.target)
        if target <= 0:
            raise ValueError
    except ValueError:
        parser.error('target must be a positive integer')
    src = args.work / 'clean.md'
    chunk_dir = args.work / 'chunks'
    text = src.read_text(encoding='utf-8')
    fm = re.match(r'^---\n.*?\n---\n', text, re.DOTALL)
    body = text[fm.end():] if fm else text
    if not body.strip():
        parser.error('clean.md has no body')
    parts = re.split(r'(?m)(^<!-- page \d+ -->)', body)
    blocks = [parts[0]] if parts[0].strip() else []
    blocks.extend(parts[j] + parts[j + 1] for j in range(1, len(parts), 2))
    chunks, current, words = [], '', 0
    for block in blocks:
        count = len(block.split())
        if words > 0 and words + count > target:
            chunks.append(current)
            current, words = block, count
        else:
            current += block
            words += count
    if current.strip():
        chunks.append(current)
    expected = {f'chunk-{i:02d}.md' for i in range(1, len(chunks) + 1)}
    stale = {p.name for p in chunk_dir.glob('chunk-*.md')} - expected
    if stale:
        parser.error('stale chunks exist; use a fresh work directory: ' + ', '.join(sorted(stale)))
    chunk_dir.mkdir(exist_ok=True)
    for i, chunk in enumerate(chunks, 1):
        header = f'<!-- chunk {i}/{len(chunks)} | words~{len(chunk.split())} -->\n\n'
        (chunk_dir / f'chunk-{i:02d}.md').write_text(header + chunk.strip() + '\n', encoding='utf-8')
    print(f'{len(chunks)} chunks (target {target} w/chunk) -> {chunk_dir}')


if __name__ == '__main__':
    main()
