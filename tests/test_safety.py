"""Offline shell integration tests: every OS/OCR/PDF command is a fixture."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        for name in ('ocr-pages.sh', 'ocr-smart.sh', 'auto-capture.sh', 'build-pdf.sh',
                     'clean-md.sh', 'clean-noid.sh'):
            shutil.copy2(ROOT / name, self.root / name)
        self.env = {'PATH': f'{self.bin}:{os.defpath}', 'HOME': str(self.root),
                    'TRACE': str(self.root / 'trace')}
        (self.bin / 'python3').symlink_to(sys.executable)
        self.book = 'fixture-book'
        self.work = self.root / 'output' / self.book
        self.pages = self.work / 'pages'
        self.pages.mkdir(parents=True)

    def stub(self, name, body):
        path = (self.root if name == 'livetext_ocr_smart' else self.bin) / name
        path.write_text('#!/bin/bash\nset -e\n' + body + '\n')
        path.chmod(0o755)

    def run_script(self, script, *args):
        return subprocess.run(['/bin/bash', str(self.root / script), *args],
                              cwd=self.root, env=self.env, text=True,
                              capture_output=True, timeout=10)

    def fake_ocr(self, body):
        self.stub('swift', body)
        self.stub('livetext_ocr_smart', body)

    def old_outputs(self):
        (self.work / 'full.md').write_text('previous text')
        (self.work / 'manifest.json').write_text('previous manifest')

    def assert_old_outputs(self):
        self.assertEqual((self.work / 'full.md').read_text(), 'previous text')
        self.assertEqual((self.work / 'manifest.json').read_text(), 'previous manifest')
        self.assertEqual(sorted(p.name for p in self.work.iterdir()),
                         ['full.md', 'manifest.json', 'pages'])

    def test_ocr_failure_keeps_previous_outputs(self):
        for script in ('ocr-pages.sh', 'ocr-smart.sh'):
            with self.subTest(script=script):
                self.old_outputs()
                (self.pages / 'page_0001.png').touch()
                (self.pages / 'page_0002.png').touch()
                self.fake_ocr('case "$*" in *page_0002*) exit 9;; esac\necho "Synthetic page"')
                result = self.run_script(script, self.book)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn('page_0002', result.stderr)
                self.assert_old_outputs()

    def test_empty_ocr_keeps_previous_outputs(self):
        for script in ('ocr-pages.sh', 'ocr-smart.sh'):
            with self.subTest(script=script):
                self.old_outputs()
                (self.pages / 'page_0001.png').touch()
                self.fake_ocr('printf "  \\n\\t\\n"')
                result = self.run_script(script, self.book)
                self.assertNotEqual(result.returncode, 0)
                self.assert_old_outputs()

    def test_no_pages_keeps_previous_outputs(self):
        self.old_outputs()
        self.fake_ocr('exit 90')
        for script in ('ocr-pages.sh', 'ocr-smart.sh'):
            result = self.run_script(script, self.book)
            self.assertNotEqual(result.returncode, 0)
            self.assert_old_outputs()

    def test_invalid_page_name_is_rejected_without_running_ocr(self):
        self.old_outputs()
        (self.pages / 'page_bad.png').touch()
        self.fake_ocr('echo called >> "$TRACE"\necho text')
        for script in ('ocr-pages.sh', 'ocr-smart.sh'):
            result = self.run_script(script, self.book)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((self.root / 'trace').exists())
            self.assert_old_outputs()

    def test_book_name_cannot_escape_output_directory(self):
        self.fake_ocr('echo text')
        self.capture_stubs('exit 0')
        for script in ('auto-capture.sh', 'ocr-smart.sh', 'build-pdf.sh'):
            for book in ('../escape', '.', '..', '/tmp/escape', 'book\nname'):
                with self.subTest(script=script, book=book):
                    args = ('2', book, '0') if script == 'auto-capture.sh' else (book,)
                    result = self.run_script(script, *args)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('one directory name', result.stderr)
        # capture_stubs replaces this script to keep capture tests fully offline.
        shutil.copy2(ROOT / 'ocr-pages.sh', self.root / 'ocr-pages.sh')
        result = self.run_script('ocr-pages.sh', '../escape')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('one directory name', result.stderr)

    def test_cleaners_reject_paths_before_reading_or_writing(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'full.md').write_text('Synthetic text')
        (outside / 'clean.md').write_text('Previous result')
        for script in ('clean-md.sh', 'clean-noid.sh'):
            for book in ('../outside', '.', '..', str(outside), 'book\nname', 'book\rname'):
                with self.subTest(script=script, book=book):
                    result = self.run_script(script, book)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('one directory name', result.stderr)
                    self.assertEqual((outside / 'clean.md').read_text(), 'Previous result')

    def test_cleaners_treat_book_names_as_data(self):
        books = ('中文 "quoted" book', 'book\\name',
                 'book"); __import__(\'pathlib\').Path(\'injected\').touch(); #')
        for script in ('clean-md.sh', 'clean-noid.sh'):
            for book in books:
                with self.subTest(script=script, book=book):
                    work = self.root / 'output' / book
                    work.mkdir(exist_ok=True)
                    (work / 'full.md').write_text('<!-- page 2 -->\nSynthetic prose.\n')
                    (self.root / 'injected').unlink(missing_ok=True)
                    result = self.run_script(script, book)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('Synthetic prose.', (work / 'clean.md').read_text())
                    self.assertFalse((self.root / 'injected').exists())

    def test_empty_cleaner_input_preserves_previous_output(self):
        (self.work / 'full.md').write_text('')
        for script in ('clean-md.sh', 'clean-noid.sh'):
            with self.subTest(script=script):
                (self.work / 'clean.md').write_text('Previous result')
                result = self.run_script(script, self.book)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((self.work / 'clean.md').read_text(), 'Previous result')

    def test_successful_ocr_writes_all_pages_and_valid_manifest(self):
        for script in ('ocr-pages.sh', 'ocr-smart.sh'):
            with self.subTest(script=script):
                self.book = 'synthetic "quoted" book'
                self.work = self.root / 'output' / self.book
                self.pages = self.work / 'pages'
                self.pages.mkdir(parents=True, exist_ok=True)
                for n in (1, 2):
                    (self.pages / f'page_{n:04d}.png').touch()
                self.old_outputs()
                self.fake_ocr('echo "-n Synthetic page"')
                result = self.run_script(script, self.book)
                self.assertEqual(result.returncode, 0, result.stderr)
                text = (self.work / 'full.md').read_text()
                self.assertIn('<!-- page 1 -->', text)
                self.assertIn('<!-- page 2 -->', text)
                self.assertEqual(text.count('-n Synthetic page'), 2)
                manifest = json.loads((self.work / 'manifest.json').read_text())
                self.assertEqual(manifest['book'], self.book)
                self.assertEqual(manifest['pages_captured'], 2)

    def test_ocr_sorts_page_numbers_numerically(self):
        for number in (1, 2, 10, 10000):
            (self.pages / f'page_{number}.png').touch()
        self.fake_ocr('echo Synthetic')
        for script in ('ocr-pages.sh', 'ocr-smart.sh'):
            with self.subTest(script=script):
                result = self.run_script(script, self.book)
                self.assertEqual(result.returncode, 0, result.stderr)
                text = (self.work / 'full.md').read_text()
                positions = [text.index(f'<!-- page {n} -->') for n in (1, 2, 10, 10000)]
                self.assertEqual(positions, sorted(positions))

    def capture_stubs(self, osascript):
        self.stub('sleep', 'exit 0')
        self.stub('caffeinate', 'exit 0')
        self.stub('osascript', osascript)
        self.stub('screencapture', 'echo capture >> "$TRACE"\nprintf fixture > "$2"')
        (self.root / 'ocr-pages.sh').write_text('#!/bin/bash\necho OCR >> "$TRACE"\n')
        (self.root / 'ocr-pages.sh').chmod(0o755)

    def test_capture_stops_if_page_turn_fails(self):
        self.capture_stubs('case "$*" in *System*) exit 7;; esac')
        result = self.run_script('auto-capture.sh', '3', self.book, '0')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.root / 'trace').read_text().splitlines(), ['capture'])

    def test_capture_stops_if_activation_fails(self):
        self.capture_stubs('exit 7')
        result = self.run_script('auto-capture.sh', '2', self.book, '0')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'trace').exists())

    def test_capture_success_takes_requested_pages_then_calls_ocr(self):
        self.capture_stubs('exit 0')
        result = self.run_script('auto-capture.sh', '3', self.book, '0')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / 'trace').read_text().splitlines(),
                         ['capture', 'capture', 'capture', 'OCR'])

    def test_capture_without_resume_rejects_existing_pages_before_activation(self):
        self.capture_stubs('echo osascript >> "$TRACE"')
        existing = self.pages / 'page_0001.png'
        existing.write_text('previous capture')
        result = self.run_script('auto-capture.sh', '3', self.book, '0')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--resume', result.stderr)
        self.assertEqual(existing.read_text(), 'previous capture')
        self.assertFalse((self.root / 'trace').exists())
        self.assertEqual(sorted(p.name for p in self.pages.iterdir()), ['page_0001.png'])

    def test_capture_resume_skips_existing_pages_but_still_turns_each_page(self):
        self.capture_stubs('case "$*" in *System*) echo turn >> "$TRACE";; esac')
        for number in (1, 3):
            (self.pages / f'page_{number:04d}.png').write_text(f'previous {number}')
        result = self.run_script('auto-capture.sh', '--resume', '3', self.book, '0')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / 'trace').read_text().splitlines(),
                         ['turn', 'capture', 'turn', 'OCR'])
        for number in (1, 3):
            self.assertEqual((self.pages / f'page_{number:04d}.png').read_text(),
                             f'previous {number}')
            self.assertIn(f'[{number}/3] exists, skip', result.stdout)
        self.assertEqual((self.pages / 'page_0002.png').read_text(), 'fixture')

    def test_capture_resume_all_existing_pages_still_turns_then_calls_ocr(self):
        self.capture_stubs('case "$*" in *System*) echo turn >> "$TRACE";; esac')
        for number in (1, 2):
            (self.pages / f'page_{number:04d}.png').write_text(f'previous {number}')
        result = self.run_script('auto-capture.sh', '--resume', '2', self.book, '0')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / 'trace').read_text().splitlines(), ['turn', 'OCR'])
        for number in (1, 2):
            self.assertEqual((self.pages / f'page_{number:04d}.png').read_text(),
                             f'previous {number}')

    def test_capture_resume_stops_when_turning_past_existing_page_fails(self):
        self.capture_stubs('case "$*" in *System*) exit 7;; esac')
        existing = self.pages / 'page_0001.png'
        existing.write_text('previous capture')
        result = self.run_script('auto-capture.sh', '--resume', '3', self.book, '0')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('page turn failed', result.stderr)
        self.assertEqual(existing.read_text(), 'previous capture')
        self.assertFalse((self.root / 'trace').exists())
        self.assertFalse((self.pages / 'page_0002.png').exists())

    def test_capture_resume_recaptures_empty_page(self):
        self.capture_stubs('case "$*" in *System*) echo turn >> "$TRACE";; esac')
        (self.pages / 'page_0001.png').write_text('')
        result = self.run_script('auto-capture.sh', '--resume', '1', self.book, '0')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / 'trace').read_text().splitlines(), ['capture', 'OCR'])
        self.assertEqual((self.pages / 'page_0001.png').read_text(), 'fixture')

    def test_capture_rejects_misplaced_resume_flag(self):
        self.capture_stubs('exit 0')
        result = self.run_script('auto-capture.sh', '2', '--resume', '0')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--resume', result.stderr)
        self.assertFalse((self.root / 'output' / '--resume').exists())
        self.assertFalse((self.root / 'trace').exists())

    def test_capture_rejects_invalid_counts_delays_and_existing_pages(self):
        self.capture_stubs('exit 0')
        for count, delay in [('0', '0'), ('oops', '0'), ('2', '-1'), ('2', 'oops')]:
            result = self.run_script('auto-capture.sh', count, self.book, delay)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((self.root / 'trace').exists())
        existing = self.pages / 'page_0001.png'
        existing.write_text('previous capture')
        result = self.run_script('auto-capture.sh', '2', self.book, '0')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(existing.read_text(), 'previous capture')
        self.assertFalse((self.root / 'trace').exists())

    def test_pdf_uses_source_metadata_without_fixed_author_or_title(self):
        (self.work / 'clean-zh.md').write_text('---\ntitle: Synthetic\nauthor: Fixture\n---\nText')
        self.stub('pandoc', 'printf "%s\\n" "$@" > "$TRACE"\n'
                  'while [ "$#" -gt 0 ]; do\n'
                  'if [ "$1" = -o ]; then printf fixture > "$2"; break; fi\nshift\ndone')
        result = self.run_script('build-pdf.sh', self.book)
        self.assertEqual(result.returncode, 0, result.stderr)
        args = (self.root / 'trace').read_text()
        self.assertNotIn('--metadata title=', args)
        self.assertNotIn('--metadata author=', args)

    def test_pdf_render_failure_preserves_previous_output(self):
        (self.work / 'clean-zh.md').write_text('Synthetic text')
        previous = self.work / 'clean-zh.pdf'
        previous.write_text('previous fixture PDF')
        self.stub('pandoc', 'while [ "$#" -gt 0 ]; do\n'
                  'if [ "$1" = -o ]; then printf partial > "$2"; exit 8; fi\nshift\ndone')
        result = self.run_script('build-pdf.sh', self.book)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(previous.read_text(), 'previous fixture PDF')


if __name__ == '__main__':
    unittest.main()
