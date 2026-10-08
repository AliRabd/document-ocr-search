#!/usr/bin/env python3
"""Measure SEARCH quality and latency against a real Elasticsearch cluster.

    export ES_USER=elastic ES_PASSWORD='...'            # never put these in Git
    python evaluation/es_search_eval.py --es-url https://ES_HOST:9200 \
        --ca-cert /path/to/http_ca.crt

What it does
  1. extracts every sample file with the real pipeline code,
  2. indexes the chunks into a TEMPORARY index (mapping from elasticsearch/index-template.json),
  3. runs every query in queries.csv (multi_match over content, content.ar, content.en),
     collapsing chunks by filename,
  4. reports hit@1/3/10, MRR, nDCG@10 and query latency (avg / p95 ms),
  5. deletes the temporary index (use --keep to inspect it in Kibana).
Uses only the Python standard library.
"""
import argparse
import base64
import csv
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import metrics as M  # noqa: E402


class ES(object):
    def __init__(self, url, user, password, ca_cert, insecure):
        self.url = url.rstrip("/")
        self.auth = None
        if user:
            self.auth = "Basic " + base64.b64encode(("%s:%s" % (user, password or "")).encode()).decode()
        self.ctx = None
        if self.url.startswith("https"):
            self.ctx = ssl.create_default_context(cafile=ca_cert) if ca_cert else ssl.create_default_context()
            if insecure:
                self.ctx.check_hostname = False
                self.ctx.verify_mode = ssl.CERT_NONE

    def call(self, method, path, body=None, ndjson=False):
        data = None
        headers = {}
        if body is not None:
            data = body.encode("utf-8") if ndjson else json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/x-ndjson" if ndjson else "application/json"
        if self.auth:
            headers["Authorization"] = self.auth
        req = urllib.request.Request(self.url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            raise SystemExit("Elasticsearch %s %s -> HTTP %d: %s" % (
                method, path, exc.code, exc.read().decode("utf-8", "replace")[:300]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--es-url", required=True)
    ap.add_argument("--index", default="ocr_eval_tmp")
    ap.add_argument("--samples", default=os.path.join(HERE, "samples"))
    ap.add_argument("--manifest", default=os.path.join(HERE, "manifest.json"))
    ap.add_argument("--queries", default=os.path.join(HERE, "queries.csv"))
    ap.add_argument("--ca-cert")
    ap.add_argument("--insecure", action="store_true", help="skip TLS verification (testing only)")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--out", default=os.path.join(HERE, "results", "es_search.json"))
    args = ap.parse_args()

    os.environ.setdefault("IMAGE_OCR_ENGINE", "tesseract")
    import main_dispatcher as D

    es = ES(args.es_url, os.environ.get("ES_USER"), os.environ.get("ES_PASSWORD"), args.ca_cert, args.insecure)
    es.call("DELETE", "/%s?ignore_unavailable=true" % args.index)
    tmpl = json.load(open(os.path.join(ROOT, "elasticsearch", "index-template.json")))["template"]
    tmpl["settings"] = {"number_of_shards": 1, "number_of_replicas": 0}
    es.call("PUT", "/" + args.index, tmpl)

    manifest = json.load(open(args.manifest, encoding="utf-8"))
    bulk, n_docs = [], 0
    for name in sorted(manifest):
        path = os.path.join(args.samples, name)
        script = D.classify(path)
        if not script:
            continue
        for line in D.run_extractor(script, [path]):
            rec = json.loads(line)
            bulk.append(json.dumps({"index": {"_index": args.index, "_id": rec["doc_id"]}}))
            bulk.append(json.dumps(rec, ensure_ascii=False))
            n_docs += 1
    res = es.call("POST", "/_bulk?refresh=true", "\n".join(bulk) + "\n", ndjson=True)
    if res.get("errors"):
        raise SystemExit("bulk indexing reported errors: %s" % json.dumps(res)[:400])

    queries = list(csv.DictReader(open(args.queries, encoding="utf-8")))
    ranked, expected, latencies = [], [], []
    for q in queries:
        body = {"size": 10, "_source": ["filename"],
                "query": {"multi_match": {"query": q["query"], "type": "most_fields",
                                          "fields": ["content", "content.ar", "content.en", "filename.text"]}},
                "collapse": {"field": "filename"}}
        t0 = time.time()
        r = es.call("POST", "/%s/_search" % args.index, body)
        latencies.append((time.time() - t0) * 1000.0)
        ranked.append([h["_source"]["filename"] for h in r["hits"]["hits"]])
        expected.append({q["expected_file"]})

    sm = M.search_metrics(ranked, expected)
    lat = sorted(latencies)
    out = {"index": args.index, "chunks_indexed": n_docs, "search": sm,
           "latency_ms": {"avg": sum(lat) / len(lat), "p95": lat[int(0.95 * (len(lat) - 1))]}}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=2)
    print(json.dumps(out, indent=2))
    if not args.keep:
        es.call("DELETE", "/" + args.index)
    return 0


if __name__ == "__main__":
    sys.exit(main())
