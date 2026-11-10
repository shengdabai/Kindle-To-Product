"""Synthetic, offline regression tests; never open the real book outputs."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def run_script(self, script, *args, **env):
        return subprocess.run(
            [sys.executable, str(ROOT / script), *args],
            env={"PATH": os.defpath, "HOME": str(self.work), **env},
            cwd=self.work, text=True, capture_output=True,
        )

    def write_source(self, body):
        (self.work / 'clean.md').write_text(body, encoding='utf-8')

    def translations(self, numbers):
        folder = self.work / 'chunks-zh'
        folder.mkdir()
        for n in numbers:
            (folder / f'chunk-{n:02d}.md').write_text(
                f'---\nchunk: {n}/{len(numbers)}\n---\n\n正文{n}\n', encoding='utf-8')

    def test_four_way_preserves_body_and_has_no_empty_chunks(self):
        body = 'Introduction\n' + 'first paragraph\n' * 20 + '<!-- page 2 -->\nLast page\n'
        self.write_source('---\ntitle: Test\n---\n' + body)
        result = self.run_script('chunk-md.py', '--work', str(self.work))
        self.assertEqual(result.returncode, 0, result.stderr)
        chunks = sorted((self.work / 'chunks').glob('chunk-*.md'))
        parts = [re.sub(r'^---\n.*?\n---\n\n', '', p.read_text(), flags=re.S) for p in chunks]
        self.assertTrue(all(p.strip() for p in parts))
        self.assertEqual(''.join(parts), body)
        self.assertLessEqual(len(parts), 4)

    def test_four_way_does_not_cut_paragraph_without_pages(self):
        body = 'An unbroken paragraph with many words. ' * 20
        self.write_source(body)
        result = self.run_script('chunk-md.py', '--work', str(self.work))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list((self.work / 'chunks').glob('*.md'))), 1)

    def test_first_page_marker_with_leading_blank_lines_does_not_create_empty_chunk(self):
        self.write_source('\n\n<!-- page 1 -->\n' + 'Long page. ' * 100)
        result = self.run_script('chunk-md.py', '--work', str(self.work))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list((self.work / 'chunks').glob('*.md'))), 1)

    def test_target_rejects_nonpositive_and_invalid_values_before_writing(self):
        self.write_source('sample')
        for target in ('0', '-1', 'invalid'):
            with self.subTest(target=target):
                result = self.run_script('chunk-noid.py', WORK=str(self.work), TARGET=target)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.work / 'chunks').exists())

    def test_word_chunks_preserve_page_blocks(self):
        self.write_source('---\ntitle: Test\n---\n<!-- page 1 -->\nOne two three\n<!-- page 2 -->\nFour five six\n')
        result = self.run_script('chunk-noid.py', WORK=str(self.work), TARGET='8')
        self.assertEqual(result.returncode, 0, result.stderr)
        chunks = sorted((self.work / 'chunks').glob('*.md'))
        self.assertEqual(len(chunks), 2)
        for n, chunk in enumerate(chunks, 1):
            self.assertIn(f'<!-- page {n} -->', chunk.read_text())

    def test_chunkers_reject_stale_chunks_without_overwriting(self):
        self.write_source('Short body\n')
        folder = self.work / 'chunks'
        folder.mkdir()
        stale = folder / 'chunk-99.md'
        stale.write_text('previous result')
        for script in ('chunk-md.py', 'chunk-noid.py'):
            result = self.run_script(script, '--work', str(self.work))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(stale.read_text(), 'previous result')
            self.assertFalse((folder / 'chunk-01.md').exists())

    def test_merge_includes_all_thirteen_chunks(self):
        self.translations(range(1, 14))
        result = self.run_script('merge-zh.py', '--work', str(self.work))
        self.assertEqual(result.returncode, 0, result.stderr)
        output = (self.work / 'clean-zh.md').read_text()
        positions = [output.index(f'正文{i}\n') for i in range(1, 14)]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn('63714', output)

    def test_merge_preserves_repeated_prose(self):
        self.translations(range(1, 5))
        (self.work / 'chunks-zh/chunk-01.md').write_text('Repeat\nRepeat\n\nRepeat\n')
        result = self.run_script('merge-zh.py', '--work', str(self.work))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.work / 'clean-zh.md').read_text().count('Repeat'), 3)

    def test_remerge_preserves_handwritten_metadata_and_refreshes_counts(self):
        self.translations([1])
        metadata = ('title: "手写书名"\nsubtitle: |\n  副标题第一行\n  第二行\n'
                    'author:\n  - "合成作者"\ncustom: {edition: 2}\nlang: zh-Hans\n')
        output = self.work / 'clean-zh.md'
        output.write_text('---\n' + metadata + 'translated_chars: 999\n'
                          'translated_at: old\n---\n\nOld body\n')
        for _ in range(2):
            result = self.run_script('merge-zh.py', '--work', str(self.work))
            self.assertEqual(result.returncode, 0, result.stderr)
            text = output.read_text()
            self.assertIn(metadata, text)
            self.assertNotIn('999', text)
            self.assertNotIn('Old body', text)
            self.assertEqual(text.count('translated_chars:'), 1)
            self.assertEqual(text.count('translated_at:'), 1)

    def test_remerge_rejects_unclosed_metadata_without_overwriting(self):
        self.translations([1])
        output = self.work / 'clean-zh.md'
        previous = '---\ntitle: "Keep this"\nUnclosed metadata\n'
        output.write_text(previous)
        result = self.run_script('merge-zh.py', '--work', str(self.work))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_text(), previous)

    def test_remerge_preserves_quoted_yaml_keys(self):
        self.translations([1])
        output = self.work / 'clean-zh.md'
        metadata = ('"title": "手写标题"\n\'lang\': zh-Hans\n'
                    '"translated_chars": 999\n# Keep editorial note\n')
        output.write_text('---\n' + metadata + '---\nOld text')
        result = self.run_script('merge-zh.py', '--work', str(self.work))
        self.assertEqual(result.returncode, 0, result.stderr)
        text = output.read_text()
        self.assertIn('"title": "手写标题"', text)
        self.assertNotRegex(text, r'(?m)^title:')
        self.assertNotRegex(text, r'(?m)^lang:')
        self.assertNotIn('999', text)
        self.assertIn('# Keep editorial note', text)

    def test_remerge_accepts_empty_yaml_header(self):
        self.translations([1])
        (self.work / 'clean-zh.md').write_text('---\n---\nOld text')
        result = self.run_script('merge-zh.py', '--work', str(self.work))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_merge_sorts_numbers_beyond_99(self):
        self.translations(range(1, 102))
        result = self.run_script('merge-zh.py', '--work', str(self.work))
        self.assertEqual(result.returncode, 0, result.stderr)
        output = (self.work / 'clean-zh.md').read_text()
        self.assertLess(output.index('正文99\n'), output.index('正文100\n'))

    def test_merge_detects_missing_tail_from_comment_header(self):
        self.translations([1])
        (self.work / 'chunks-zh/chunk-01.md').write_text('<!-- chunk 1/2 | words~3 -->\n\nBody\n')
        result = self.run_script('merge-zh.py', '--work', str(self.work))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.work / 'clean-zh.md').exists())

    def test_merge_rejects_duplicate_numeric_names(self):
        self.translations([1])
        (self.work / 'chunks-zh/chunk-1.md').write_text('Duplicate')
        result = self.run_script('merge-zh.py', '--work', str(self.work))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.work / 'clean-zh.md').exists())

    def test_empty_source_does_not_create_chunk_directory(self):
        self.write_source('---\ntitle: Empty\n---\n\n')
        for script in ('chunk-md.py', 'chunk-noid.py'):
            result = self.run_script(script, '--work', str(self.work))
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((self.work / 'chunks').exists())

    def test_merge_gap_preserves_existing_output(self):
        self.translations([1, 3])
        output = self.work / 'clean-zh.md'
        output.write_text('keep previous output')
        result = self.run_script('merge-zh.py', '--work', str(self.work))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_text(), 'keep previous output')

    def test_merge_rejects_huge_sparse_chunk_number_without_range_allocation(self):
        self.translations([1])
        (self.work / 'chunks-zh/chunk-99999999999999999999.md').write_text('Body')
        output = self.work / 'clean-zh.md'
        output.write_text('Previous result')
        result = self.run_script('merge-zh.py', '--work', str(self.work))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('chunk sequence has gaps', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(output.read_text(), 'Previous result')

    def test_merge_detects_missing_final_translation_from_source_chunks(self):
        self.translations(range(1, 5))
        folder = self.work / 'chunks'
        folder.mkdir()
        for n in range(1, 6):
            (folder / f'chunk-{n:02d}.md').write_text('source')
        result = self.run_script('merge-zh.py', '--work', str(self.work))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.work / 'clean-zh.md').exists())

    def test_empty_translation_is_rejected(self):
        self.translations([1])
        (self.work / 'chunks-zh/chunk-01.md').write_text('---\nchunk: 1/1\n---\n\n')
        result = self.run_script('merge-zh.py', '--work', str(self.work))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.work / 'clean-zh.md').exists())

    def test_word_chunk_to_merge_round_trip(self):
        body = ''.join(f'<!-- page {n} -->\nParagraph {n}.\n' for n in range(1, 9))
        self.write_source('---\ntitle: Synthetic\n---\n' + body)
        result = self.run_script('chunk-noid.py', '--work', str(self.work), '--target', '8')
        self.assertEqual(result.returncode, 0, result.stderr)
        target = self.work / 'chunks-zh'
        target.mkdir()
        for source in (self.work / 'chunks').glob('*.md'):
            (target / source.name).write_text(source.read_text())
        result = self.run_script('merge-zh.py', '--work', str(self.work))
        self.assertEqual(result.returncode, 0, result.stderr)
        output = (self.work / 'clean-zh.md').read_text()
        self.assertNotIn('<!-- chunk', output)
        self.assertEqual(re.findall(r'<!-- page \d+ -->', output), re.findall(r'<!-- page \d+ -->', body))
        for n in range(1, 9):
            self.assertEqual(output.count(f'Paragraph {n}.'), 1)


if __name__ == '__main__':
    unittest.main()
