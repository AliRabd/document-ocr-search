import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "evaluation"))
import metrics as m


class TestMetrics(unittest.TestCase):
    def test_edit_distance(self):
        self.assertEqual(m.edit_distance("kitten", "sitting"), 3)
        self.assertEqual(m.edit_distance("", "abc"), 3)
        self.assertEqual(m.edit_distance("abc", "abc"), 0)

    def test_cer_wer(self):
        self.assertAlmostEqual(m.cer("invoice", "lnvoice"), 1 / 7.0)
        self.assertAlmostEqual(m.wer("invoice number 12345", "lnvoice nurnber 12345"), 2 / 3.0)
        self.assertEqual(m.cer("", ""), 0.0)
        self.assertEqual(m.cer("", "x"), 1.0)

    def test_arabic_normalisation(self):
        # alef variants, tashkeel and tatweel must not count as errors
        a = u"أحمد المدينة"
        b = u"احمَد المدينـة"
        self.assertEqual(m.ocr_scores(a, b)["cer"], 0.0)

    def test_presentation_forms(self):
        # NFKC maps Arabic presentation forms to base letters
        self.assertEqual(m.normalize(u"ﺍﻟﻣ"), m.normalize(u"الم"))

    def test_bm25_and_search_metrics(self):
        idx = m.BM25({"a": "invoice from acme corp", "b": "contract with beta ltd",
                      "c": "meeting notes"})
        self.assertEqual(idx.search("acme invoice")[0], "a")
        res = [["a", "b"], ["c", "b"], ["x", "y"]]
        exp = [{"a"}, {"b"}, {"z"}]
        s = m.search_metrics(res, exp)
        self.assertAlmostEqual(s["hit@1"], 1 / 3.0)
        self.assertAlmostEqual(s["hit@3"], 2 / 3.0)
        self.assertAlmostEqual(s["mrr"], (1 + 0.5 + 0) / 3.0)

    def test_field_accuracy(self):
        t = [{"file": "1", "total": "10.00"}, {"file": "2", "total": "5.00"}]
        e = [{"file": "1", "total": "10.00"}, {"file": "2", "total": "6.00"}]
        self.assertEqual(m.field_accuracy(t, e, ["total"]), {"total": 0.5})


if __name__ == "__main__":
    unittest.main()
