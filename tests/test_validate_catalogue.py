"""Offline tests for scripts/validate_catalogue.py. No network access is used."""

import copy
import datetime as dt
import json
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import validate_catalogue as v  # noqa: E402

SITE = "https://seeitflow.com/"
AT = chr(64)  # keeps e-mail-like fixtures out of the source scan
WORDS = "How a request moves through the system and what each component contributes to it"


def good_data():
    return {
        "schema_version": 2,
        "site": SITE,
        "site_pages": {
            "system_design": "https://seeitflow.com/system-design",
            "about": "https://seeitflow.com/about",
            "contact": "https://seeitflow.com/contact",
        },
        "resources": [
            {"id": "http", "kind": "foundation", "group": "Networking", "title": "HTTP",
             "url": "https://seeitflow.com/networking/http", "description": WORDS},
            {"id": "chat", "kind": "design", "group": "Real time", "title": "Chat System Design",
             "url": "https://seeitflow.com/system-design/foundations/chat/complete-design",
             "level": "Foundations", "challenges": ["message ordering", "offline delivery"]},
            {"id": "slo", "kind": "production", "group": "Operations", "title": "SLOs",
             "url": "https://seeitflow.com/production/slo", "description": WORDS},
        ],
    }


LESSON_BODY = "<main><h2>Overview</h2><p>" + " ".join(
    "requests travel through load balancers and caches before reaching application servers".split() * 9) + "</p></main>"


def page(url, title="HTTP Fundamentals", h1="HTTP", canonical=True, extra="", body=LESSON_BODY):
    link = f'<link rel="canonical" href="{url}">' if canonical is True else (canonical or "")
    return {"status": 200, "content_type": "text/html", "x_robots_tag": None, "truncated": False, "location": None,
            "body": f"<html><head><title>{title}</title>{link}{extra}</head><body><h1>{h1}</h1>{body}</body></html>"}


def resolve_ok(host):
    return None


class UrlTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(v.parse_url("https://seeitflow.com/a/b")[0], "https://seeitflow.com/a/b")

    def test_invalid_variants(self):
        bad = [
            "http://seeitflow.com/a", "https://evil.com/a", "https://seeitflow.com:8443/a",
            f"https://user:pw{AT}seeitflow.com/a", "https://seeitflow.com/a?x=1", "https://seeitflow.com/a#frag",
            "https://SEEITFLOW.com/a", "https://seeitflow.com/a/../b", "https://seeitflow.com//a",
            "https://seeitflow.com/a b", f"https://seeitflow.com\\{AT}evil.com/", "https://seeitflow.com.evil.com/",
            f"https://evil.com{AT}seeitflow.com/", "", None, 5, ["x"], "javascript:alert(1)", "https://seeitflow.com/\x00",
        ]
        for u in bad:
            with self.subTest(u=u):
                self.assertIsNone(v.parse_url(u)[0])
                self.assertTrue(v.parse_url(u)[1])


class SchemaTests(unittest.TestCase):
    def test_good_data_passes(self):
        self.assertEqual(v.validate_data(good_data()), [])

    def test_real_catalogue_passes_and_counts(self):
        data = v.load_data()
        self.assertEqual(v.validate_data(data), [])
        self.assertEqual(v.counts(data), {"foundation": 48, "design": 31, "production": 26, "total": 105})

    def mutate(self, fn):
        d = good_data()
        fn(d)
        return v.validate_data(d)

    def test_malformed_types_never_raise(self):
        for bad in (None, [], "x", 3, {"resources": "x"}, {"schema_version": 2, "site": 1, "site_pages": [], "resources": [None, 1, "x", []]}):
            with self.subTest(bad=bad):
                self.assertTrue(v.validate_data(bad))

    def test_failures(self):
        cases = {
            "duplicate id": lambda d: d["resources"][2].update(id="http"),
            "duplicate url": lambda d: d["resources"][2].update(url=d["resources"][0]["url"]),
            "duplicate url slash": lambda d: d["resources"][2].update(url=d["resources"][0]["url"] + "/"),
            "duplicate title": lambda d: d["resources"][2].update(title="http"),
            "site duplicate": lambda d: d["resources"][0].update(url=SITE),
            "extra field": lambda d: d["resources"][0].update(extra="x"),
            "missing field": lambda d: d["resources"][0].pop("description"),
            "bad kind": lambda d: d["resources"][0].update(kind="other"),
            "bad id": lambda d: d["resources"][0].update(id="Bad_ID"),
            "markdown in title": lambda d: d["resources"][0].update(title="[x](y)"),
            "pipe in group": lambda d: d["resources"][0].update(group="a|b"),
            "short description": lambda d: d["resources"][0].update(description="Too short."),
            "description not text": lambda d: d["resources"][0].update(description=["x"]),
            "bad level": lambda d: d["resources"][1].update(level="Expert"),
            "challenges string": lambda d: d["resources"][1].update(challenges="a, b"),
            "challenge comma": lambda d: d["resources"][1].update(challenges=["a, b", "c"]),
            "challenge repeat": lambda d: d["resources"][1].update(challenges=["same", "Same"]),
            "too few challenges": lambda d: d["resources"][1].update(challenges=["one"]),
            "bad schema version": lambda d: d.update(schema_version=1),
            "extra top key": lambda d: d.update(other=1),
            "other host": lambda d: d["resources"][0].update(url="https://example.com/x"),
        }
        for name, fn in cases.items():
            with self.subTest(name):
                self.assertTrue(self.mutate(fn), name)


class RenderTests(unittest.TestCase):
    def readme(self):
        blocks = "".join(f"<!-- BEGIN GENERATED:{k} -->\nold\n<!-- END GENERATED:{k} -->\n" for k in v.KINDS)
        counts = "".join(f"<!-- BEGIN GENERATED:count_{k} -->0<!-- END GENERATED:count_{k} -->" for k in v.REQUIRED_COUNT_KEYS)
        return counts + "\n" + blocks

    def test_deterministic_and_complete(self):
        data = good_data()
        out = v.render_readme(self.readme(), data)
        self.assertEqual(out, v.render_readme(out, data))
        for r in data["resources"]:
            self.assertEqual(out.count(f"]({r['url']})"), 1)
        self.assertIn("| [Chat System Design](", out)
        self.assertIn("message ordering, offline delivery", out)
        self.assertIn("<!-- BEGIN GENERATED:count_total -->3<!--", out)

    def test_marker_errors(self):
        data = good_data()
        text = self.readme()
        with self.assertRaises(ValueError):
            v.render_readme(text.replace("<!-- END GENERATED:design -->", ""), data)
        with self.assertRaises(ValueError):
            v.render_readme(text + text, data)

    def test_real_readme_in_sync(self):
        data = v.load_data()
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertEqual(readme, v.render_readme(readme, data))
        self.assertEqual(v.check_readme_coverage(readme, data), [])


class TreeTests(unittest.TestCase):
    def run_tree(self, files):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for name, text in files.items():
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
            return v.check_tree(list(files), root)

    def test_clean(self):
        self.assertEqual(self.run_tree({"README.md": f"Contact hello{AT}seeitflow.com or pkg{AT}0.24.1\n"}), [])

    def test_allowlist(self):
        self.assertTrue(self.run_tree({"SEEITFLOW_X_REVIEW.md": "x"}))

    def test_email_policy_redacted(self):
        errs = self.run_tree({"README.md": f"write to someone{AT}example.org\n"})
        self.assertEqual(len(errs), 1)
        self.assertNotIn("someone", errs[0])

    def test_credentials_redacted(self):
        fake = "gh" + "p_" + "a" * 36
        errs = self.run_tree({"README.md": f"token {fake}\n", "CONTRIBUTING.md": "pass" + "word = 'hunter2hunter2'\n"})
        self.assertEqual(len(errs), 2)
        self.assertTrue(all(fake not in e and "hunter2" not in e for e in errs))

    def test_validator_scans_clean(self):
        self.assertEqual(v.check_tree(["scripts/validate_catalogue.py", "tests/test_validate_catalogue.py"]), [])

    def test_markdown_checks(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / "README.md").write_text(f"# T\n\n[ok](#t) [bad](#nope) [m](mailto:x{AT}y.org) [f](missing.md) [h](http://a.b)\n\n### Skip\n", encoding="utf-8")
            errs = v.check_markdown(["README.md"], root)
        text = "\n".join(errs)
        for needle in ("#nope", "mailto", "missing.md", "non-HTTPS", "heading level"):
            self.assertIn(needle, text)

    def test_site_links(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / "README.md").write_text("[a](https://seeitflow.com/about) [b](https://seeitflow.com/unknown)", encoding="utf-8")
            errs = v.check_site_links(["README.md"], good_data(), root)
        self.assertEqual(len(errs), 1)


class LicenseTests(unittest.TestCase):
    def check(self, text):
        with tempfile.TemporaryDirectory() as d:
            if text is not None:
                (Path(d) / "LICENSE").write_text(text, encoding="utf-8")
            return v.check_license(Path(d))

    def test_all_rights_reserved_passes(self):
        self.assertEqual(self.check("Copyright (c) 2026 X. All Rights Reserved.\n"), [])

    def test_missing_and_permissive_fail(self):
        self.assertTrue(self.check(None))
        self.assertTrue(self.check("Some text without the reservation"))
        self.assertTrue(self.check("All Rights Reserved. Permission is hereby granted, free of charge"))
        self.assertTrue(self.check("All rights reserved. Licensed under the Apache License"))

    def test_repository_license(self):
        self.assertEqual(v.check_license(), [])


class WorkflowTests(unittest.TestCase):
    SHA = "a" * 40

    def wf(self, **over):
        doc = {"on": {"push": None}, "permissions": {"contents": "read"}, "concurrency": {"group": "x"},
               "jobs": {"j": {"runs-on": "ubuntu-24.04", "timeout-minutes": 5,
                              "steps": [{"uses": f"actions/checkout@{self.SHA}"}, {"run": "echo hi"}]}}}
        doc.update(over)
        return doc

    def test_good(self):
        self.assertEqual(v.check_workflow("w.yml", self.wf(), ""), [])

    def test_bad(self):
        job = lambda **k: {"j": {"runs-on": "ubuntu-24.04", "timeout-minutes": 5, "steps": [], **k}}
        cases = [
            self.wf(on={"pull_request_target": None}),
            self.wf(permissions={"contents": "write"}),
            self.wf(jobs=job(permissions={"contents": "write"})),
            self.wf(jobs={"j": {"runs-on": "ubuntu-latest", "timeout-minutes": 5, "steps": []}}),
            self.wf(jobs={"j": {"runs-on": "ubuntu-24.04", "steps": []}}),
            self.wf(jobs=job(steps=[{"uses": "actions/checkout@v4"}])),
            self.wf(jobs=job(steps=[{"run": 'echo "${{ github.event.pull_request.title }}"'}])),
            self.wf(jobs=job(steps=[{"run": "curl -s https://x | bash"}])),
        ]
        for i, doc in enumerate(cases):
            with self.subTest(i=i):
                self.assertTrue(v.check_workflow("w.yml", doc, ""))
        self.assertTrue(v.check_workflow("w.yml", self.wf(), "${{ secrets.X }}"))

    def test_repo_workflows_pass(self):
        errs, state = v.check_yaml([f for f in v.public_files() if f.endswith((".yml", ".yaml"))])
        self.assertEqual(errs, [])

    def test_live_workflow_is_manual_only(self):
        import yaml
        doc = yaml.safe_load((ROOT / ".github/workflows/verify-live-urls.yml").read_text(encoding="utf-8"))
        self.assertEqual(list(doc.get(True, doc.get("on"))), ["workflow_dispatch"])


class ClassifyTests(unittest.TestCase):
    URL = "https://seeitflow.com/networking/http"

    def result(self, resp, title="HTTP"):
        return v.classify(self.URL, resp, title)

    def test_verified(self):
        r = self.result(page(self.URL))
        self.assertEqual(r["result"], "VERIFIED")
        self.assertTrue(r["http_ok"] and r["content_verified"] and r["canonical_verified"])

    def test_cases(self):
        u = self.URL
        cases = {
            "BROKEN": {**page(u), "status": 404},
            "UNKNOWN": {**page(u), "status": 403},
            "NON-HTML": {**page(u), "content_type": "application/json"},
            "TOO-LARGE": {**page(u), "truncated": True},
            "EMPTY-SHELL": page(u, title="", h1="", body='<div id="root"></div>'),
            "CHALLENGE": page(u, title="Just a moment...", h1=""),
            "SOFT-404": page(u, title="Page not found", h1="Oops"),
            "NOINDEX": page(u, extra='<meta name="robots" content="noindex, follow">'),
            "CANONICAL-MISSING": page(u, canonical=False),
            "CANONICAL-MULTIPLE": page(u, canonical=f'<link rel="canonical" href="{u}"><link rel="canonical" href="{u}2">'),
            "CANONICAL-MISMATCH": page(u, canonical='<link rel="canonical" href="https://seeitflow.com/other">'),
            "WRONG-CONTENT": page(u, title="Gardening tips", h1="Tomatoes"),
        }
        for expected, resp in cases.items():
            with self.subTest(expected):
                self.assertEqual(self.result(resp)["result"], expected)

    def test_header_noindex(self):
        r = self.result({**page(self.URL), "x_robots_tag": "noindex"})
        self.assertEqual(r["result"], "NOINDEX")

    def test_403_is_not_proof_of_broken(self):
        r = self.result({**page(self.URL), "status": 403})
        self.assertFalse(r["http_ok"])
        self.assertEqual(r["result"], "UNKNOWN")


class VerifyUrlTests(unittest.TestCase):
    URL = "https://seeitflow.com/networking/http"

    def run_verify(self, responses, title="HTTP"):
        calls = []

        def fetch(url):
            calls.append(url)
            r = responses[min(len(calls) - 1, len(responses) - 1)]
            if isinstance(r, Exception):
                raise r
            return r

        return v.verify_url(self.URL, title, fetch=fetch, resolve=resolve_ok, sleep=lambda s: None), calls

    def redirect(self, to, status=301):
        return {"status": status, "location": to, "content_type": "", "x_robots_tag": None, "truncated": False, "body": ""}

    def test_verified_direct(self):
        rec, calls = self.run_verify([page(self.URL)])
        self.assertEqual(rec["result"], "VERIFIED")
        self.assertEqual(rec["method"], "origin-http")
        self.assertEqual(len(calls), 1)

    def test_redirect_recorded_and_not_verified(self):
        target = "https://seeitflow.com/networking/http2"
        rec, _ = self.run_verify([self.redirect(target), page(target)])
        self.assertEqual(rec["result"], "REDIRECT")
        self.assertEqual(rec["final_url"], target)
        self.assertEqual(len(rec["redirect_chain"]), 1)

    def test_redirect_to_other_host_rejected_before_request(self):
        rec, calls = self.run_verify([self.redirect("https://evil.example/x")])
        self.assertEqual(rec["result"], "REDIRECT-REJECTED")
        self.assertEqual(len(calls), 1)

    def test_redirect_to_http_rejected(self):
        rec, _ = self.run_verify([self.redirect("http://seeitflow.com/x")])
        self.assertEqual(rec["result"], "REDIRECT-REJECTED")

    def test_redirect_loop(self):
        rec, _ = self.run_verify([self.redirect(self.URL)])
        self.assertEqual(rec["result"], "REDIRECT-LOOP")

    def test_redirect_limit(self):
        hops = [self.redirect(f"https://seeitflow.com/h{i}") for i in range(10)]
        rec, calls = self.run_verify(hops)
        self.assertEqual(rec["result"], "REDIRECT-LIMIT")
        self.assertEqual(len(calls), v.MAX_REDIRECTS + 1)

    def test_network_failure_is_unknown(self):
        rec, calls = self.run_verify([urllib.error.URLError("down")])
        self.assertEqual(rec["result"], "UNKNOWN")
        self.assertEqual(len(calls), 3)

    def test_transient_status_retries(self):
        rec, calls = self.run_verify([{**page(self.URL), "status": 503}, page(self.URL)])
        self.assertEqual(rec["result"], "VERIFIED")
        self.assertEqual(len(calls), 2)

    def test_invalid_input_never_requested(self):
        called = []
        rec = v.verify_url("http://evil.example/", fetch=lambda u: called.append(u), resolve=resolve_ok)
        self.assertEqual(rec["result"], "REJECTED")
        self.assertEqual(called, [])

    def test_private_address_blocked(self):
        called = []
        rec = v.verify_url(self.URL, fetch=lambda u: called.append(u), resolve=lambda h: "host resolves to a non-public address")
        self.assertEqual(rec["result"], "UNKNOWN")
        self.assertEqual(called, [])

    def test_page_info_ignores_later_titles(self):
        info = v.PageInfo()
        info.feed("<title>A</title><h1>One</h1><svg><title>Icon</title></svg><h1>Two</h1>")
        self.assertEqual((info.title, info.h1), ("A", "One"))


COMMIT = "a" * 40


def baseline_for(data):
    return {"site_urls": [data["site"], *data["site_pages"].values()],
            "resources": [{"url": r["url"], "kind": r["kind"]} for r in data["resources"]]}


def evidence_for(data, now, **changes):
    """Evidence shaped like `links` output for a fully verified catalogue."""
    results = []
    for url, exp in v.expectations(data).items():
        name = exp["title"] or exp["terms"][0]
        results.append({
            "url": url, "final_url": url, "redirect_chain": [], "result": "VERIFIED", "method": "origin-http",
            "http_status": 200, "http_ok": True, "content_verified": True, "canonical_verified": True,
            "robots_ok": True, "robots_meta": None, "x_robots_tag": [], "canonical": url, "title": name,
            "h1": name, "content_words": 300, "fetched_at": (now - dt.timedelta(days=1)).isoformat(),
        })
    with mock.patch.object(v, "proxy_detected", return_value=False):
        ev = v.build_evidence(data, results, COMMIT, now - dt.timedelta(days=1))
    ev.update(changes)
    return ev


class ReleaseTests(unittest.TestCase):
    NOW = dt.datetime.now(dt.timezone.utc)

    def blockers(self, mutate=None, **kw):
        d = good_data()
        ev = evidence_for(d, self.NOW)
        if mutate:
            mutate(ev)
        return v.evidence_blockers(d, ev, kw.get("commit", COMMIT), self.NOW)

    def test_good_evidence(self):
        self.assertEqual(self.blockers(), [])

    def test_record_level_failures(self):
        cases = {
            "duplicate": lambda e: e["results"].append(dict(e["results"][1])),
            "missing": lambda e: e["results"].pop(),
            "extra": lambda e: e["results"].append({"url": "https://seeitflow.com/extra", "result": "VERIFIED"}),
            "malformed record": lambda e: e["results"].append("x"),
            "status 204": lambda e: e["results"][3].update(http_status=204),
            "status flag": lambda e: e["results"][3].update(http_ok=False),
            "result": lambda e: e["results"][3].update(result="UNKNOWN"),
            "canonical flag": lambda e: e["results"][3].update(canonical_verified=False),
            "content flag": lambda e: e["results"][3].update(content_verified=False),
            "robots flag missing": lambda e: e["results"][3].pop("robots_ok"),
            "robots flag forged": lambda e: e["results"][3].update(robots_meta=["robots: noindex"]),
            "robots header forged": lambda e: e["results"][3].update(x_robots_tag=["none"]),
            "canonical forged": lambda e: e["results"][3].update(canonical="https://seeitflow.com/other"),
            "title forged": lambda e: e["results"][3].update(title="Gardening", h1="Tomatoes"),
            "thin content forged": lambda e: e["results"][3].update(content_words=12),
            "words missing": lambda e: e["results"][3].pop("content_words"),
            "redirect": lambda e: e["results"][3].update(final_url="https://seeitflow.com/elsewhere"),
            "redirect chain": lambda e: e["results"][3].update(redirect_chain=[{"from": "a", "to": "b"}]),
            "stale record": lambda e: e["results"][3].update(fetched_at=(self.NOW - dt.timedelta(days=30)).isoformat()),
            "future record": lambda e: e["results"][3].update(fetched_at=(self.NOW + dt.timedelta(days=3)).isoformat()),
            "naive timestamp": lambda e: e["results"][3].update(fetched_at="2026-01-01T00:00:00"),
            "no timestamp": lambda e: e["results"][3].pop("fetched_at"),
            "method": lambda e: e["results"][3].update(method="manual"),
        }
        for name, fn in cases.items():
            with self.subTest(name):
                self.assertTrue(self.blockers(fn), name)

    def test_envelope_failures(self):
        cases = {
            "method": lambda e: e.update(method="manual"),
            "schema": lambda e: e.update(evidence_schema=1),
            "validator version": lambda e: e.update(validator_version="0.0.1"),
            "wrong digest": lambda e: e.update(catalogue_digest="sha256:" + "0" * 64),
            "missing digest": lambda e: e.pop("catalogue_digest"),
            "missing commit": lambda e: e.pop("source_commit"),
            "malformed commit": lambda e: e.update(source_commit="abc"),
            "other commit": lambda e: e.update(source_commit="b" * 40),
            "proxy": lambda e: e.update(proxy_detected=True),
            "proxy unknown": lambda e: e.pop("proxy_detected"),
            "stale generated": lambda e: e.update(generated_at=(self.NOW - dt.timedelta(days=40)).isoformat()),
            "bad generated": lambda e: e.update(generated_at="yesterday"),
            "results type": lambda e: e.update(results="x"),
            "summary mismatch": lambda e: e["summary"].update(total=1),
        }
        for name, fn in cases.items():
            with self.subTest(name):
                self.assertTrue(self.blockers(fn), name)
        self.assertTrue(v.evidence_blockers(good_data(), [], COMMIT, self.NOW))
        self.assertTrue(v.evidence_blockers(good_data(), None, COMMIT, self.NOW))

    def test_digest_detects_catalogue_change(self):
        d = good_data()
        ev = evidence_for(d, self.NOW)
        d["resources"][0]["description"] = d["resources"][0]["description"] + " extra"
        self.assertTrue(any("catalogue_digest" in b for b in v.evidence_blockers(d, ev, COMMIT, self.NOW)))

    def test_digest_is_order_independent(self):
        d = good_data()
        self.assertEqual(v.catalogue_digest(d), v.catalogue_digest(json.loads(json.dumps(d, sort_keys=True))))

    def test_baseline_complete(self):
        d = good_data()
        self.assertEqual(v.baseline_blockers(d, baseline_for(d)), [])

    def test_baseline_failures(self):
        d = good_data()

        def check(fn):
            b = baseline_for(d)
            fn(b)
            return v.baseline_blockers(d, b)

        cases = {
            "removed approved foundation": lambda b: b["resources"].append({"url": "https://seeitflow.com/x", "kind": "foundation"}),
            "unapproved addition": lambda b: b["resources"].pop(0),
            "kind change": lambda b: b["resources"][1].update(kind="production"),
            "duplicate": lambda b: b["resources"].append(dict(b["resources"][0])),
            "missing site page": lambda b: b["site_urls"].pop(),
            "extra site page": lambda b: b["site_urls"].append("https://seeitflow.com/pricing"),
            "malformed resource": lambda b: b["resources"].append("x"),
            "bad kind": lambda b: b["resources"].append({"url": "https://seeitflow.com/y", "kind": "other"}),
        }
        for name, fn in cases.items():
            with self.subTest(name):
                self.assertTrue(check(fn), name)
        for bad in (None, [], {}, {"site_urls": "x", "resources": []}):
            self.assertTrue(v.baseline_blockers(d, bad))

    def test_real_baseline_covers_all_categories(self):
        data = v.load_data()
        b = baseline_for(data)
        kinds = {k: sum(r["kind"] == k for r in b["resources"]) for k in v.KINDS}
        self.assertEqual(kinds, {"foundation": 48, "design": 31, "production": 26})
        self.assertEqual(len(b["site_urls"]), 4)
        self.assertEqual(len(v.all_urls(data)), 109)

    def test_release_markers_and_missing_files(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / "README.md").write_text("<!-- LICENSE-PENDING: x -->\n", encoding="utf-8")
            blockers = v.release_blockers(["README.md"], good_data(), None, None, root, with_history=False)
        text = "\n".join(blockers)
        for needle in ("LICENSE-PENDING", "LICENSE: not tracked", "evidence: file not supplied", "baseline: file not supplied"):
            self.assertIn(needle, text)

    def test_malformed_files_give_errors(self):
        d = good_data()
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / "e.json").write_text("{not json", encoding="utf-8")
            (root / "b.json").write_text("[1, 2]", encoding="utf-8")
            blockers = v.release_blockers([], d, root / "e.json", root / "b.json", root, with_history=False)
        self.assertTrue(any("not valid JSON" in b for b in blockers))
        self.assertTrue(any("expected an object" in b for b in blockers))


class UrlEncodingTests(unittest.TestCase):
    def test_encoded_forms_rejected(self):
        bad = ["https://seeitflow.com/a/%2e%2e/b", "https://seeitflow.com/a%2fb", "https://seeitflow.com/a%5cb",
               "https://seeitflow.com/a%00b", "https://seeitflow.com/a%0d%0a", "https://seeitflow.com/%252e%252e/x",
               "https://seeitflow.com/caf\u00e9", "https://seeitflow.com./a", "https://seeitflow.com/a%3Fb"]
        for u in bad:
            with self.subTest(u=u):
                self.assertIsNone(v.parse_url(u)[0])

    def test_validate_data_rejects_encoded_url(self):
        d = good_data()
        d["resources"][0]["url"] = "https://seeitflow.com/a%2fb"
        self.assertTrue(v.validate_data(d))

    def test_malformed_redirect_locations(self):
        for location in (None, "", "   ", "//evil.example/x", "https://seeitflow.com/a%2f..%2fb", "javascript:alert(1)"):
            with self.subTest(location=location):
                resp = {"status": 302, "location": location, "content_type": "", "x_robots_tag": [], "truncated": False, "body": ""}
                rec = v.verify_url("https://seeitflow.com/a", None, fetch=lambda u: resp, resolve=resolve_ok)
                self.assertEqual(rec["result"], "REDIRECT-REJECTED")

    def test_public_addresses(self):
        with mock.patch.object(v.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]):
            self.assertEqual(v.public_addresses("seeitflow.com"), ["93.184.216.34"])
        for ip in ("127.0.0.1", "10.0.0.8", "169.254.169.254", "::1"):
            with mock.patch.object(v.socket, "getaddrinfo", return_value=[(2, 1, 6, "", (ip, 443))]):
                with self.assertRaises(OSError):
                    v.public_addresses("seeitflow.com")

    def test_deadline_stops_retries(self):
        ticks = iter([0, 0, 1000, 1000, 1000])
        rec = v.verify_url("https://seeitflow.com/a", None, fetch=lambda u: {"status": 503}, resolve=resolve_ok,
                           sleep=lambda s: None, clock=lambda: next(ticks))
        self.assertEqual(rec["result"], "UNKNOWN")
        self.assertTrue(any("budget" in n for n in rec["notes"]))


class ContentVerificationTests(unittest.TestCase):
    URL = "https://seeitflow.com/networking/http"

    def classify(self, resp, exp="HTTP"):
        return v.classify(self.URL, resp, exp)["result"]

    def test_title_and_canonical_only_is_empty_shell(self):
        self.assertEqual(self.classify(page(self.URL, body="")), "EMPTY-SHELL")
        self.assertEqual(self.classify(page(self.URL, body='<div id="root"></div><script>app()</script>')), "EMPTY-SHELL")

    def test_navigation_only_page_is_not_content(self):
        body = "<nav>" + "<a>Link</a> " * 200 + "</nav><footer>" + "word " * 200 + "</footer>"
        self.assertEqual(self.classify(page(self.URL, body=body)), "EMPTY-SHELL")

    def test_thin_page_needs_review_not_verified_or_broken(self):
        body = "<main><h2>Intro</h2><p>" + "short lesson text " * 10 + "</p></main>"
        self.assertEqual(self.classify(page(self.URL, body=body)), "NEEDS-CONTENT-REVIEW")

    def test_short_legitimate_lesson_passes(self):
        body = "<article><h2>Summary</h2><p>" + "idempotent requests can be retried safely " * 20 + "</p></article>"
        self.assertEqual(self.classify(page(self.URL, body=body)), "VERIFIED")

    def test_wall_of_text_without_structure_needs_review(self):
        body = "<div>" + "unstructured text block " * 60 + "</div>"
        self.assertEqual(self.classify(page(self.URL, body=body)), "NEEDS-CONTENT-REVIEW")

    def test_educational_content_about_errors_is_not_rejected(self):
        body = ("<main><h2>Status codes</h2><p>A 404 page not found response, a 403 access denied response and a CAPTCHA "
                "challenge page are different failure modes. Retries, the CAP theorem and just a moment pages are "
                "discussed here. " + "Clients retry with backoff and jitter. " * 25 + "</p></main>")
        self.assertEqual(self.classify(page(self.URL, title="HTTP Status Codes and Failure Modes", h1="HTTP", body=body)), "VERIFIED")

    def test_soft_404_needs_unrelated_page(self):
        self.assertEqual(self.classify(page(self.URL, title="Page not found", h1="Oops")), "SOFT-404")

    def test_challenge_in_title_and_thin_body(self):
        self.assertEqual(self.classify(page(self.URL, title="Attention Required! | Cloudflare", h1="")), "CHALLENGE")
        self.assertEqual(self.classify(page(self.URL, body="<p>Please enable JavaScript to continue</p>")), "CHALLENGE")

    def test_login_page(self):
        body = '<h2>Account</h2><form><input type="password" name="p"></form><p>' + "welcome back " * 5 + "</p>"
        self.assertEqual(self.classify(page(self.URL, title="Sign in", h1="Sign in", body=body)), "LOGIN-PAGE")

    def test_generic_landing_page_for_unrelated_route(self):
        self.assertEqual(self.classify(page(self.URL, title="SeeItFlow: learn how systems work", h1="Welcome")), "WRONG-CONTENT")

    def test_general_page_identities(self):
        cases = {
            "https://seeitflow.com/about": ("About SeeItFlow", "About", "about"),
            "https://seeitflow.com/contact": ("Contact", "Contact us", "contact"),
            "https://seeitflow.com/system-design": ("System Design Learning Path", "System design", "system_design"),
            "https://seeitflow.com/": ("SeeItFlow | Visual system design", "See them work", "site"),
        }
        for url, (title, h1, key) in cases.items():
            exp = {"kind": "general", "title": None, "terms": list(v.GENERAL_PAGE_TERMS[key])}
            body = "<main><p>" + "learn about this page here " * 8 + "</p></main>"
            with self.subTest(url=url):
                self.assertEqual(v.classify(url, page(url, title, h1, body=body), exp)["result"], "VERIFIED")
                wrong = page(url, "Pricing", "Plans", body=body)
                self.assertEqual(v.classify(url, wrong, exp)["result"], "WRONG-CONTENT")

    def test_general_pages_have_expectations_for_all_four(self):
        exp = v.expectations(good_data())
        general = [e for e in exp.values() if e["kind"] == "general"]
        self.assertEqual(len(general), 4)
        self.assertTrue(all(e["terms"] for e in general))


class RobotsTests(unittest.TestCase):
    URL = "https://seeitflow.com/networking/http"

    def result(self, extra="", header=None):
        resp = {**page(self.URL, extra=extra), "x_robots_tag": header}
        return v.classify(self.URL, resp, "HTTP")["result"]

    def test_directives(self):
        cases = [
            ('<meta name="robots" content="noindex">', None, "NOINDEX"),
            ('<meta name="robots" content="none">', None, "NOINDEX"),
            ('<meta name="googlebot" content="noindex">', None, "NOINDEX"),
            ('<meta name="robots" content="NoIndex, Follow">', None, "NOINDEX"),
            ('<meta name="robots" content="nofollow">', None, "VERIFIED"),
            ('<meta name="robots" content="index, follow">', None, "VERIFIED"),
            ('<meta name="otherbot" content="noindex">', None, "VERIFIED"),
            ("", ["nofollow"], "VERIFIED"),
            ("", ["noindex"], "NOINDEX"),
            ("", "none", "NOINDEX"),
            ("", ["googlebot: noindex"], "NOINDEX"),
            ("", ["otherbot: noindex"], "VERIFIED"),
            ("", ["index", "noindex"], "NEEDS-ROBOTS-REVIEW"),
            ("", ["all", "none"], "NEEDS-ROBOTS-REVIEW"),
            ("", ["nofollow", "unavailable_after: 25 Jun 2030 15:00:00 PST"], "VERIFIED"),
            ('<meta name="robots" content="index">', ["noindex"], "NEEDS-ROBOTS-REVIEW"),
        ]
        for meta, header, expected in cases:
            with self.subTest(meta=meta, header=header):
                self.assertEqual(self.result(meta, header), expected)

    def test_multiple_headers_any_noindex_blocks(self):
        self.assertEqual(self.result("", ["nofollow", "noindex"]), "NOINDEX")

    def test_robots_ok_flag_reflects_status(self):
        r = v.classify(self.URL, {**page(self.URL), "x_robots_tag": ["nofollow"]}, "HTTP")
        self.assertIs(r["robots_ok"], True)
        r = v.classify(self.URL, {**page(self.URL), "x_robots_tag": ["index", "noindex"]}, "HTTP")
        self.assertIsNot(r["robots_ok"], True)


class MarkdownAnchorTests(unittest.TestCase):
    def check(self, files):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for name, text in files.items():
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
            return v.check_markdown(list(files), root)

    def test_cross_file_anchors(self):
        files = {"README.md": "# T\n\n[ok](OTHER.md#real-heading) [bad](OTHER.md#nope) [nofile](MISSING.md#x)\n",
                 "OTHER.md": "# Other\n\n## Real heading\n"}
        text = "\n".join(self.check(files))
        self.assertIn("'#nope' does not match any heading in OTHER.md", text)
        self.assertIn("MISSING.md", text)
        self.assertNotIn("real-heading", text)

    def test_duplicate_heading_slug_suffix(self):
        files = {"README.md": "# T\n\n[b](OTHER.md#same-1)\n", "OTHER.md": "# O\n\n## Same\n\n## Same\n"}
        self.assertEqual(self.check(files), [])

    def test_relative_link_cannot_leave_repository(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t)
            (base / "outside.md").write_text("# Outside\n", encoding="utf-8")
            root = base / "repo"
            root.mkdir()
            (root / "README.md").write_text("# T\n\n[x](../outside.md)\n", encoding="utf-8")
            errors = v.check_markdown(["README.md"], root)
        self.assertTrue(any("leaves the repository" in e for e in errors))

    def test_anchor_on_non_markdown_target(self):
        files = {"README.md": "# T\n\n[x](data.json#a)\n", "data.json": "{}"}
        self.assertTrue(any("non-Markdown" in e for e in self.check(files)))

    def test_real_repository_links(self):
        self.assertEqual(v.check_markdown(v.public_files()), [])


class MalformedStructureTests(unittest.TestCase):
    def test_issue_form_shapes(self):
        base = {"name": "n", "description": "d"}
        cases = [
            {**base, "body": "text"},
            {**base, "body": ["x"]},
            {**base, "body": [{"type": "input", "id": "a", "attributes": "oops"}]},
            {**base, "body": [{"type": "input", "id": ["a"], "attributes": {"label": "L"}}]},
            {**base, "body": [{"type": "input", "id": "a", "attributes": {"label": ""}}]},
            {**base, "body": [{"type": "dropdown", "id": "a", "attributes": {"label": "L", "options": []}}]},
            {**base, "body": [{"type": "weird"}]},
            {"name": "n"},
        ]
        for doc in cases:
            with self.subTest(doc=doc):
                self.assertTrue(v.check_issue_form("f.yml", doc))
        self.assertEqual(v.check_issue_form("f.yml", {**base, "body": [{"type": "input", "id": "a", "attributes": {"label": "L"}}]}), [])

    def test_issue_config_shapes(self):
        self.assertTrue(v.check_issue_config("c.yml", {"blank_issues_enabled": True}))
        self.assertTrue(v.check_issue_config("c.yml", {"blank_issues_enabled": False, "contact_links": "x"}))
        self.assertTrue(v.check_issue_config("c.yml", {"blank_issues_enabled": False, "contact_links": ["x"]}))
        link = {"name": "n", "about": "a", "url": "https://evil.example/x"}
        self.assertTrue(v.check_issue_config("c.yml", {"blank_issues_enabled": False, "contact_links": [link]}))
        link["url"] = "https://github.com/seeitflow/system-design/security/policy"
        self.assertEqual(v.check_issue_config("c.yml", {"blank_issues_enabled": False, "contact_links": [link]}), [])

    def test_workflow_shapes(self):
        base = {"on": "push", "permissions": {"contents": "read"}, "concurrency": {"group": "g"}}
        cases = [
            {**base, "jobs": []},
            {**base, "jobs": {"j": "text"}},
            {**base, "jobs": {"j": {"runs-on": "ubuntu-24.04", "timeout-minutes": "ten", "steps": []}}},
            {**base, "jobs": {"j": {"runs-on": "ubuntu-24.04", "timeout-minutes": 5, "steps": "x"}}},
            {**base, "jobs": {"j": {"runs-on": "ubuntu-24.04", "timeout-minutes": 5, "steps": ["x"]}}},
            {**base, "jobs": {"j": {"runs-on": "ubuntu-24.04", "timeout-minutes": 5, "steps": [{"run": ["echo"]}]}}},
            {**base, "jobs": {"j": {"runs-on": "ubuntu-24.04", "timeout-minutes": 5, "steps": [{"uses": 5}]}}},
        ]
        for doc in cases:
            with self.subTest(doc=doc):
                self.assertTrue(v.check_workflow("w.yml", doc, ""))

    def test_malformed_yaml_text(self):
        import yaml  # noqa: F401
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / ".github/ISSUE_TEMPLATE").mkdir(parents=True)
            (root / ".github/workflows").mkdir(parents=True)
            files = {".github/ISSUE_TEMPLATE/a.yml": "name: [unclosed", ".github/workflows/b.yml": "- just\n- a list\n"}
            for name, text in files.items():
                (root / name).write_text(text, encoding="utf-8")
            errors, _ = v.check_yaml(list(files), root)
        self.assertEqual(len(errors), 2)

    def test_malformed_catalogue_file(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / "d.json"
            path.write_text("[1,", encoding="utf-8")
            with self.assertRaises(SystemExit):
                v.load_data(path)


class IdentityTests(unittest.TestCase):
    POLICY = {"approved_emails": ["owner" + AT + "users.noreply.github.com"],
              "prohibited_emails": [], "prohibited_domains": ["corp.example"]}
    OWNER = "owner" + AT + "users.noreply.github.com"

    def classify(self, entries):
        return v.classify_identities(entries, self.POLICY)

    def test_approved_only(self):
        findings, tally = self.classify([("a1", self.OWNER, self.OWNER, True)])
        self.assertEqual((findings, tally["approved"]), ([], 1))

    def test_prohibited_domain_flagged_and_redacted(self):
        bad = "person" + AT + "corp.example"
        findings, tally = self.classify([("a1", bad, self.OWNER, True)])
        self.assertEqual(tally["prohibited"], 1)
        self.assertTrue(all(bad not in f and "corp.example" not in f for f in findings))

    def test_arbitrary_noreply_is_not_proof_for_historical_commits(self):
        other = "1+other" + AT + "users.noreply.github.com"
        findings, tally = self.classify([("a1", other, other, True)])
        self.assertEqual(tally["review"], 1)
        self.assertTrue(findings)

    def test_community_noreply_allowed_after_baseline(self):
        other = "1+other" + AT + "users.noreply.github.com"
        findings, tally = self.classify([("a1", other, other, False)])
        self.assertEqual((findings, tally["community"]), ([], 1))

    def test_unexpected_non_noreply_needs_review_even_after_baseline(self):
        findings, tally = self.classify([("a1", "x" + AT + "example.org", self.OWNER, False)])
        self.assertEqual(tally["review"], 1)

    def test_prohibited_wins_over_approved(self):
        findings, tally = self.classify([("a1", self.OWNER, "p" + AT + "CORP.example", False)])
        self.assertEqual(tally["prohibited"], 1)

    def test_policy_loading(self):
        with tempfile.TemporaryDirectory() as t:
            good = Path(t) / "p.json"
            good.write_text(json.dumps(self.POLICY), encoding="utf-8")
            self.assertIsNone(v.load_identity_policy(good)[1])
            for text in ("{", "[]", json.dumps({"approved_emails": []}), json.dumps({"approved_emails": "x"}),
                         json.dumps({**self.POLICY, "prohibited_domains": [1]})):
                bad = Path(t) / "b.json"
                bad.write_text(text, encoding="utf-8")
                self.assertIsNotNone(v.load_identity_policy(bad)[1], text)
            self.assertIsNotNone(v.load_identity_policy(Path(t) / "missing.json")[1])

    def test_missing_policy_is_a_blocker_not_a_pass(self):
        findings, _ = v.history_findings(ROOT, None)
        self.assertTrue(findings)

    def test_history_with_temp_repository(self):
        import subprocess
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            env = {"GIT_AUTHOR_NAME": "n", "GIT_AUTHOR_EMAIL": "p" + AT + "corp.example", "GIT_COMMITTER_NAME": "n",
                   "GIT_COMMITTER_EMAIL": self.OWNER, "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"}
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / "f").write_text("x", encoding="utf-8")
            subprocess.run(["git", "add", "f"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "m"], cwd=root, check=True, env=env)
            policy = root / "policy.json"
            policy.write_text(json.dumps(self.POLICY), encoding="utf-8")
            findings, tally = v.history_findings(root, policy)
        self.assertEqual(tally["prohibited"], 1)
        self.assertTrue(all("corp.example" not in f for f in findings))


class ManifestAndLicenseTests(unittest.TestCase):
    def tree(self, files):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for name, text in files.items():
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
            return v.check_tree(list(files), root)

    def test_forbidden_files_have_specific_errors(self):
        names = [".review/REPORT.md", "SEEITFLOW_X_REVIEW.md", "RESOURCE_INVENTORY.json", "live-url-evidence.json",
                 "backup/all.bundle", "notes.bak", "scripts/__pycache__/x.pyc", ".idea/workspace.xml", ".wibey/x.md",
                 ".copilot/a.md", ".claude/s.json", ".env", ".env.local", "prompt.txt", "IDENTITY_POLICY.json",
                 "APPROVED_BASELINE.json", "node_modules/x/index.js", "app.log"]
        for n in names:
            with self.subTest(n=n):
                errors = self.tree({n: "x"})
                self.assertTrue(any("forbidden" in e for e in errors), errors)

    def test_tracked_but_ignored_file_is_still_detected(self):
        import subprocess
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".gitignore").write_text(".review/\n", encoding="utf-8")
            (root / ".review").mkdir()
            (root / ".review/r.md").write_text("internal", encoding="utf-8")
            subprocess.run(["git", "add", "-f", ".review/r.md", ".gitignore"], cwd=root, check=True)
            files = v.public_files(root)
            self.assertIn(".review/r.md", files)
            self.assertTrue(any("forbidden" in e for e in v.check_tree(files, root)))

    def test_allowed_manifest(self):
        for n in ("README.md", "LICENSE", "scripts/validate_catalogue.py", ".github/workflows/validate.yml"):
            self.assertEqual(self.tree({n: "text"}), [], n)
        self.assertEqual(self.tree({"docs/extra.md": "x"}), [])

    def test_real_public_tree_matches_manifest(self):
        files = v.public_files()
        self.assertEqual(v.check_tree(files), [])
        self.assertIn("LICENSE", files)
        self.assertFalse([f for f in files if f.startswith(".review") or f.startswith("SEEITFLOW_")])

    def test_gitignore_requirements(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            self.assertTrue(v.check_gitignore(root))
            (root / ".gitignore").write_text("\n".join(v.REQUIRED_GITIGNORE), encoding="utf-8")
            self.assertEqual(v.check_gitignore(root), [])
            (root / ".gitignore").write_text(".review/\n", encoding="utf-8")
            self.assertTrue(v.check_gitignore(root))

    def lic(self, license_text, coc=None):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / "LICENSE").write_text(license_text, encoding="utf-8")
            if coc is not None:
                (root / "CODE_OF_CONDUCT.md").write_text(coc, encoding="utf-8")
            return v.check_license(root)

    THIRD_PARTY = ("Contributor Covenant 2.1 is licensed under Creative Commons Attribution 4.0 (CC BY 4.0) and "
                   "stays under that license.")
    COC = ("Adapted from the Contributor Covenant. Licensed under CC BY 4.0: https://creativecommons.org/licenses/by/4.0/\n\n"
           "Changes: contact added.\n")

    def test_third_party_exception_is_narrow(self):
        base = "Copyright (c) 2026 X. All Rights Reserved."
        self.assertEqual(self.lic(base + "\n\n" + self.THIRD_PARTY, self.COC), [])
        self.assertTrue(self.lic(base + "\n\nThis is licensed under the Creative Commons Attribution license."))
        self.assertTrue(self.lic(base + "\n\n" + self.THIRD_PARTY + "\n\nPermission is hereby granted, free of charge."))
        self.assertTrue(self.lic(base + "\n\nNothing else.", self.COC))

    def test_coc_attribution_requirements(self):
        base = "Copyright (c) 2026 X. All Rights Reserved.\n\n" + self.THIRD_PARTY
        self.assertTrue(self.lic(base, "Adapted from the Contributor Covenant.\n"))
        self.assertTrue(self.lic(base, "Contributor Covenant. CC BY 4.0 https://creativecommons.org/licenses/by/4.0/\n"))

    def test_repository_license_and_attribution(self):
        self.assertEqual(v.check_license(), [])
        coc = (ROOT / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
        self.assertIn("CC BY 4.0", coc)
        self.assertIn("All Rights Reserved", (ROOT / "LICENSE").read_text(encoding="utf-8"))


class UnknownFileTests(unittest.TestCase):
    def tree(self, files, strict=False):
        warnings = []
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for name, text in files.items():
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
            errors = v.check_tree(list(files), root, strict=strict, warnings=warnings)
        return errors, warnings

    def test_new_legitimate_files_pass_standard_validation(self):
        files = {"docs/guide.md": "# Guide\n", "tests/test_other.py": "import unittest\n", "test.txt": ""}
        errors, warnings = self.tree(files)
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 3)
        self.assertTrue(all("manifest" in w for w in warnings))

    def test_unknown_harmless_file_warns_without_failing(self):
        errors, warnings = self.tree({"test.txt": "hello\n"})
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn("test.txt", warnings[0])

    def test_approved_files_produce_no_warning(self):
        self.assertEqual(self.tree({"README.md": "x"}), ([], []))

    def test_strict_mode_rejects_unapproved_files(self):
        errors, warnings = self.tree({"test.txt": "hello\n", "docs/guide.md": "# G\n"}, strict=True)
        self.assertEqual(len(errors), 2)
        self.assertEqual(warnings, [])

    def test_prohibited_files_fail_in_both_modes(self):
        for strict in (False, True):
            for name in (".review/r.md", "SEEITFLOW_X_REVIEW.md", "x.bundle", "RESOURCE_INVENTORY.json", ".env"):
                errors, _ = self.tree({name: "x"}, strict=strict)
                self.assertTrue(any("forbidden" in e for e in errors), (name, strict))

    def test_secrets_and_emails_in_unknown_files_are_detected(self):
        fake = "gh" + "p_" + "b" * 36
        errors, warnings = self.tree({"notes/new.txt": f"token {fake}\nmail someone{AT}example.org\n"})
        self.assertEqual(len(errors), 2)
        self.assertTrue(all(fake not in e and "someone" not in e for e in errors))
        self.assertEqual(len(warnings), 1)

    def test_binary_unknown_file_still_fails(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / "img.bin").write_bytes(b"\xff\xfe\x00\x80")
            self.assertTrue(v.check_tree(["img.bin"], root, warnings=[]))

    def test_warnings_default_is_safe(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "x.txt").write_text("x", encoding="utf-8")
            self.assertEqual(v.check_tree(["x.txt"], Path(t)), [])

    def run_cli(self, *args):
        import subprocess
        return subprocess.run([sys.executable, str(ROOT / "scripts/validate_catalogue.py"), "check", *args],
                              capture_output=True, text=True, cwd=ROOT)

    def test_cli_modes_with_an_unknown_tracked_file(self):
        extra = ROOT / "zz_unknown_probe.txt"
        extra.write_text("harmless\n", encoding="utf-8")
        try:
            standard = self.run_cli()
            strict = self.run_cli("--release")
        finally:
            extra.unlink()
        self.assertEqual(standard.returncode, 0, standard.stdout)
        self.assertIn("WARNING  tree:", standard.stdout)
        self.assertIn("zz_unknown_probe.txt", standard.stdout)
        self.assertIn("maintainer review", standard.stdout)
        self.assertEqual(strict.returncode, 1, strict.stdout)
        self.assertIn("ERROR  tree: file is not on the approved public file manifest", strict.stdout)


class ConsistencyTests(unittest.TestCase):
    def test_contribution_terms_are_referenced_everywhere(self):
        for name in (".github/PULL_REQUEST_TEMPLATE.md", ".github/ISSUE_TEMPLATE/resource-suggestion.yml",
                     ".github/ISSUE_TEMPLATE/broken-link.yml", ".github/ISSUE_TEMPLATE/technical-correction.yml", "README.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("ontribution terms", text, name)

    def test_confidential_reporting_is_consistent(self):
        for name in ("SECURITY.md", "CODE_OF_CONDUCT.md", "CONTRIBUTING.md"):
            self.assertIn("hello" + AT + "seeitflow.com", (ROOT / name).read_text(encoding="utf-8"), name)
        sec = (ROOT / "SECURITY.md").read_text(encoding="utf-8").lower()
        self.assertNotIn("response within", sec)
        self.assertNotIn("is enabled", sec)

    def test_live_workflow_covers_manual_trigger_and_budget(self):
        text = (ROOT / ".github/workflows/verify-live-urls.yml").read_text(encoding="utf-8")
        import yaml
        doc = yaml.safe_load(text)
        timeout = doc["jobs"]["verify"]["timeout-minutes"]
        worst_per_url = v.URL_BUDGET_SECONDS + v.REQUEST_TIMEOUT
        data = v.load_data()
        rounds = -(-len(v.all_urls(data)) // 3)
        self.assertGreaterEqual(timeout * 60, rounds * worst_per_url)
        self.assertIn("--workers 3", text)


if __name__ == "__main__":
    unittest.main()
