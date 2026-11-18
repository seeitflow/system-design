"""Offline tests for scripts/validate_catalogue.py. No network access is used."""

import copy
import datetime as dt
import json
import sys
import tempfile
import unittest
import urllib.error
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


def page(url, title="HTTP Fundamentals", h1="HTTP", canonical=True, extra="", body="<p>content</p>"):
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
        self.assertTrue(self.run_tree({"notes/internal.md": "x"}))
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


class ReleaseTests(unittest.TestCase):
    NOW = dt.datetime(2026, 1, 10, tzinfo=dt.timezone.utc)

    def evidence(self, data, **over):
        results = []
        for u in v.all_urls(data):
            results.append({"url": u, "final_url": u, "redirect_chain": [], "result": "VERIFIED", "http_ok": True,
                            "content_verified": True, "canonical_verified": True,
                            "fetched_at": (self.NOW - dt.timedelta(days=1)).isoformat()})
        ev = {"method": "origin-http", "results": results}
        ev.update(over)
        return ev

    def test_good_evidence(self):
        d = good_data()
        self.assertEqual(v.evidence_blockers(d, self.evidence(d), self.NOW), [])

    def test_bad_evidence(self):
        d = good_data()

        def with_change(fn):
            ev = self.evidence(d)
            fn(ev)
            return v.evidence_blockers(d, ev, self.NOW)

        cases = {
            "manual flag": lambda e: e.update(method="manual", results=[]),
            "not a dict": lambda e: e.clear() or e.update(results="x"),
            "missing url": lambda e: e["results"].pop(),
            "extra url": lambda e: e["results"].append({"url": "https://seeitflow.com/extra", "result": "VERIFIED"}),
            "unknown result": lambda e: e["results"][1].update(result="UNKNOWN"),
            "forged flags": lambda e: e["results"][1].update(canonical_verified=False),
            "redirected": lambda e: e["results"][1].update(final_url="https://seeitflow.com/elsewhere"),
            "stale": lambda e: e["results"][1].update(fetched_at=(self.NOW - dt.timedelta(days=30)).isoformat()),
            "future": lambda e: e["results"][1].update(fetched_at=(self.NOW + dt.timedelta(days=3)).isoformat()),
            "no timestamp": lambda e: e["results"][1].pop("fetched_at"),
        }
        for name, fn in cases.items():
            with self.subTest(name):
                self.assertTrue(with_change(fn), name)
        self.assertTrue(v.evidence_blockers(d, [], self.NOW))

    def test_baseline(self):
        d = good_data()
        url = d["resources"][1]["url"]
        self.assertEqual(v.baseline_blockers(d, {"design_urls": [url]}), [])
        self.assertTrue(v.baseline_blockers(d, {"design_urls": [url, "https://seeitflow.com/system-design/x"]}))
        self.assertTrue(v.baseline_blockers(d, {"design_urls": []}))
        self.assertTrue(v.baseline_blockers(d, {}))

    def test_release_markers_and_missing_files(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / "README.md").write_text("<!-- LICENSE-PENDING: x -->\n", encoding="utf-8")
            blockers = v.release_blockers(["README.md"], good_data(), None, None, root, with_history=False)
        text = "\n".join(blockers)
        for needle in ("LICENSE-PENDING", "LICENSE: not tracked", "evidence: file not supplied", "baseline: file not supplied"):
            self.assertIn(needle, text)

    def test_evidence_json_round_trip(self):
        d = good_data()
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / "e.json").write_text("{not json", encoding="utf-8")
            blockers = v.release_blockers([], d, root / "e.json", root / "e.json", root, with_history=False)
        self.assertTrue(any("not valid JSON" in b for b in blockers))
        json.dumps(self.evidence(d))


if __name__ == "__main__":
    unittest.main()
