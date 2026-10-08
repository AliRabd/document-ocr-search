"""Pure-Python evaluation metrics (no third-party dependencies).

OCR quality   : CER, WER (Levenshtein), character accuracy
Field quality : exact-match accuracy per field
Search quality: hit@k, precision@k, MRR, nDCG@k   (+ a small BM25 engine so the
                search metrics can be computed without Elasticsearch)
"""
import math
import re
import unicodedata
from collections import Counter, defaultdict

# ---------------------------------------------------------------- normalising
_ARABIC_DIACRITICS = re.compile("[ً-ٰٟۖ-ۭـ]")


def normalize(text, arabic=True, lowercase=False):
    """Make two texts comparable: NFKC, no invisible chars, single spaces.

    arabic=True also folds alef/yaa/taa-marbuta variants and removes tashkeel
    and tatweel, so harmless spelling variants are not counted as OCR errors.
    """
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub("[​-‏‪-‮⁦-⁩﻿]", "", text)
    if arabic:
        text = _ARABIC_DIACRITICS.sub("", text)
        text = re.sub("[آأإٱ]", "ا", text)   # alef forms
        text = text.replace("ى", "ي")                       # alef maqsura -> yaa
        text = text.replace("ة", "ه")                       # taa marbuta -> haa
    if lowercase:
        text = text.lower()
    return re.sub(r"\s+", " ", text).strip()


# ----------------------------------------------------------------- edit dist.
def edit_distance(ref, hyp):
    """Levenshtein distance between two sequences (strings or lists)."""
    if ref == hyp:
        return 0
    if not ref:
        return len(hyp)
    if not hyp:
        return len(ref)
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1]


def cer(reference, hypothesis):
    """Character Error Rate = edits / len(reference). Can exceed 1.0."""
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return edit_distance(reference, hypothesis) / float(len(reference))


def wer(reference, hypothesis):
    """Word Error Rate = word edits / number of reference words."""
    ref, hyp = reference.split(), hypothesis.split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return edit_distance(ref, hyp) / float(len(ref))


def ocr_scores(truth, ocr, arabic=True, lowercase=False):
    t = normalize(truth, arabic, lowercase)
    o = normalize(ocr, arabic, lowercase)
    c, w = cer(t, o), wer(t, o)
    return {"cer": c, "wer": w, "char_accuracy": max(0.0, 1.0 - c),
            "ref_chars": len(t), "ref_words": len(t.split())}


# --------------------------------------------------------------- field-level
def field_accuracy(truth_rows, extracted_rows, fields):
    """Exact-match accuracy per field. Rows are dicts keyed by 'file'."""
    got = {r["file"]: r for r in extracted_rows}
    out = {}
    for f in fields:
        ok = n = 0
        for row in truth_rows:
            n += 1
            e = got.get(row["file"], {})
            ok += normalize(str(row.get(f, "")), False, True) == \
                normalize(str(e.get(f, "")), False, True)
        out[f] = ok / n if n else 0.0
    return out


# ----------------------------------------------------------------- BM25 index
_TOKEN = re.compile(r"\w+", re.UNICODE)


def tokenize(text):
    return _TOKEN.findall(normalize(text, True, True))


class BM25(object):
    """Tiny BM25 index. One entry per document id; used for offline search eval."""

    def __init__(self, docs, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.tf, self.len, self.df = {}, {}, Counter()
        for doc_id, text in docs.items():
            counts = Counter(tokenize(text))
            self.tf[doc_id] = counts
            self.len[doc_id] = sum(counts.values())
            for term in counts:
                self.df[term] += 1
        self.n = len(self.tf)
        self.avg = (sum(self.len.values()) / float(self.n)) if self.n else 0.0

    def search(self, query, size=10):
        scores = defaultdict(float)
        for term in set(tokenize(query)):
            df = self.df.get(term, 0)
            if not df:
                continue
            idf = math.log(1 + (self.n - df + 0.5) / (df + 0.5))
            for doc_id, counts in self.tf.items():
                f = counts.get(term, 0)
                if f:
                    denom = f + self.k1 * (1 - self.b + self.b * self.len[doc_id] / (self.avg or 1))
                    scores[doc_id] += idf * f * (self.k1 + 1) / denom
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return [d for d, _ in ranked[:size]]


# ------------------------------------------------------------ search metrics
def search_metrics(results, expected, ks=(1, 3, 10)):
    """results: list of ranked doc-id lists; expected: list of sets of relevant ids."""
    n = len(results)
    out = {"queries": n}
    if not n:
        return out
    for k in ks:
        out["hit@%d" % k] = sum(1 for r, e in zip(results, expected) if set(r[:k]) & e) / float(n)
    out["precision@3"] = sum(len(set(r[:3]) & e) / 3.0 for r, e in zip(results, expected)) / n
    rr = []
    for r, e in zip(results, expected):
        rank = next((i for i, d in enumerate(r, 1) if d in e), None)
        rr.append(1.0 / rank if rank else 0.0)
    out["mrr"] = sum(rr) / n
    ndcg = []
    for r, e in zip(results, expected):
        dcg = sum(1.0 / math.log2(i + 1) for i, d in enumerate(r[:10], 1) if d in e)
        ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(e), 10) + 1))
        ndcg.append(dcg / ideal if ideal else 0.0)
    out["ndcg@10"] = sum(ndcg) / n
    return out
