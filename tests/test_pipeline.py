"""Regression tests for the bugs found in the review of v1.

Run:  python -m unittest discover -s tests -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "python"))
sys.path.insert(0, ROOT)
import common  # noqa: E402

PY = sys.executable


def run_script(script, *args, **env):
    e = dict(os.environ)
    e.update(env)
    p = subprocess.run([PY, os.path.join(ROOT, script)] + list(args),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e)
    out = [json.loads(l) for l in p.stdout.decode("utf-8").splitlines() if l.strip()]
    return p.returncode, out, p.stderr.decode("utf-8", "replace")


class TestCommon(unittest.TestCase):
    def test_arabic_presentation_forms_normalised(self):
        self.assertEqual(common.normalize_text(u"ﺍﻟﻣ"), u"الم")

    def test_invisible_chars_removed(self):
        self.assertEqual(common.normalize_text(u"a‏b‪c"), "abc")

    def test_chunking_keeps_all_text_and_splits_on_words(self):
        text = " ".join("word%d" % i for i in range(5000))
        chunks = common.split_chunks(text, 1000)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(" ".join(chunks).split(), text.split())
        self.assertTrue(all(len(c) <= 1000 for c in chunks))

    def test_doc_id_is_short_ascii_even_for_long_arabic_paths(self):
        p = "/data/" + u"تقرير" * 200 + ".pdf"
        self.assertLess(len(common.path_hash(p)), 64)
        rec = common.make_records(p, "x", "pdf_text", "t")[0]
        self.assertTrue(rec["doc_id"].isascii())

    def test_empty_text_gets_warning_not_silent_success(self):
        rec = common.make_records("/x/a.png", "", "image", "tesseract")[0]
        self.assertEqual(rec["warning"], "no_text_extracted")

    def test_no_error_marker_pollutes_content(self):
        rec = common.error_record("/x/a.png", "image", "boom")
        self.assertEqual(rec["content"], "")
        self.assertEqual(rec["error"], "boom")


class TestDocExtractor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_csv_windows1256_arabic_is_decoded(self):          # v1 bug #3
        path = os.path.join(self.tmp, "ar.csv")
        rows = u"الاسم,المدينة\r\nأحمد,الرياض\r\n"
        open(path, "wb").write(rows.encode("cp1256"))
        rc, out, _ = run_script("python/doc_extractor.py", path)
        self.assertEqual(rc, 0)
        self.assertNotIn("error", out[0])
        self.assertIn(u"الرياض", out[0]["content"])

    def test_xlsx_reads_all_sheets(self):
        from openpyxl import Workbook
        path = os.path.join(self.tmp, "w.xlsx")
        wb = Workbook()
        wb.active.append(["alpha"])
        wb.create_sheet("S2").append(["bravo_unique"])
        wb.save(path)
        rc, out, _ = run_script("python/doc_extractor.py", path)
        self.assertIn("bravo_unique", out[0]["content"])

    def test_large_file_is_chunked_not_truncated(self):
        path = os.path.join(self.tmp, "big.csv")
        with open(path, "w") as h:
            for i in range(3000):
                h.write("row%d,some,words,here\n" % i)
        rc, out, _ = run_script("python/doc_extractor.py", path, CHUNK_CHARS="5000")
        self.assertGreater(len(out), 1)
        self.assertEqual(out[0]["chunk_total"], len(out))
        joined = "\n".join(r["content"] for r in out)
        self.assertIn("row2999", joined)
        self.assertFalse(out[0]["truncated"])

    def test_corrupt_file_reports_error_record_exit_zero(self):
        path = os.path.join(self.tmp, "bad.xlsx")
        open(path, "wb").write(b"not a zip")
        rc, out, _ = run_script("python/doc_extractor.py", path)
        self.assertEqual(rc, 0)
        self.assertTrue(out[0]["error"])


class TestDispatcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.inp = os.path.join(self.tmp, "in")
        os.makedirs(os.path.join(self.inp, "sub"))
        self.state = os.path.join(self.tmp, "state.json")

    def dispatch(self, **env):
        e = dict(INPUT_DIR=self.inp, STATE_FILE=self.state, PYTHON_BIN=PY)
        e.update(env)
        return run_script("main_dispatcher.py", **e)

    def test_every_file_yields_a_record_even_if_extractor_crashes(self):   # v1 bug #2
        bad = os.path.join(self.inp, "broken.xlsx")
        open(bad, "wb").write(b"garbage")
        rc, out, _ = self.dispatch()
        self.assertEqual(rc, 0)
        rec = [r for r in out if r["filename"] == "broken.xlsx"]
        self.assertEqual(len(rec), 1)
        self.assertTrue(rec[0]["error"])

    def test_stdout_is_json_only(self):
        open(os.path.join(self.inp, "a.csv"), "w").write("a,b\n1,2\n")
        p = subprocess.run([PY, os.path.join(ROOT, "main_dispatcher.py")], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,
                           env=dict(os.environ, INPUT_DIR=self.inp, STATE_FILE=self.state, PYTHON_BIN=PY))
        for line in p.stdout.decode().splitlines():
            json.loads(line)                        # must not raise

    def test_unchanged_files_are_skipped_on_second_run(self):
        open(os.path.join(self.inp, "sub", "a.csv"), "w").write("a,b\n1,2\n")    # also tests recursion
        _, first, _ = self.dispatch()
        _, second, _ = self.dispatch()
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 0)
        _, third, _ = self.dispatch(REPROCESS="1")
        self.assertEqual(len(third), 1)

    def test_changed_file_is_reprocessed(self):
        path = os.path.join(self.inp, "a.csv")
        open(path, "w").write("a,b\n")
        self.dispatch()
        open(path, "w").write("a,b\n1,2,3,4,5\n")
        os.utime(path, (1, 1))                       # force a different mtime signature
        _, again, _ = self.dispatch()
        self.assertEqual(len(again), 1)

    def test_hanging_extractor_times_out_and_is_reported(self):
        hang = os.path.join(self.tmp, "hang.py")
        open(hang, "w").write("import time; time.sleep(60)\n")
        sys.path.insert(0, ROOT)
        import importlib
        os.environ.update(INPUT_DIR=self.inp, STATE_FILE=self.state, FILE_TIMEOUT="1")
        import main_dispatcher
        importlib.reload(main_dispatcher)
        target = os.path.join(self.inp, "x.csv")
        open(target, "w").write("a\n")
        lines = main_dispatcher.run_extractor(hang, [target])
        rec = json.loads(lines[0])
        self.assertIn("timeout", rec["error"])

    def test_failed_file_retried_only_max_attempts_times(self):
        open(os.path.join(self.inp, "broken.xlsx"), "wb").write(b"garbage")
        counts = [len(self.dispatch(MAX_ATTEMPTS="2")[1]) for _ in range(4)]
        self.assertEqual(counts, [1, 1, 0, 0])

    def test_unsupported_type_is_ignored_quietly(self):
        open(os.path.join(self.inp, "x.bin"), "wb").write(b"1")
        rc, out, err = self.dispatch()
        self.assertEqual(out, [])
        self.assertNotIn("Unsupported file type", err)


if __name__ == "__main__":
    unittest.main()
