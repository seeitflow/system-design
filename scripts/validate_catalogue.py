#!/usr/bin/env python3
"""Catalogue validator and README renderer (standard library only).

Commands:
  render   Regenerate the catalogue blocks in README.md from data/resources.json.
  check    Validate data, README, links between files, anchors, workflows and the public tree.
  links    Check live catalogue URLs (network). Only approved hosts are contacted.

`check --release` additionally reports release blockers (pending markers, missing
license, empty catalogue, unverified entries).
"""

import argparse
import concurrent.futures
import ipaddress
import json
import re
import socket
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "resources.json"
README = ROOT / "README.md"

APPROVED_HOSTS = {"seeitflow.com"}
KINDS = ("foundation", "design", "production")
TEXT_FIELD = {"foundation": "description", "production": "description", "design": "challenges"}
ALLOWED_FILES = [
    r"README\.md", r"CONTRIBUTING\.md", r"CODE_OF_CONDUCT\.md", r"MAINTAINERS\.md",
    r"SECURITY\.md", r"LICENSE", r"\.gitignore", r"\.markdownlint-cli2\.yaml",
    r"assets/[^/]+\.(svg|png)", r"\.github/ISSUE_TEMPLATE/[^/]+\.yml",
    r"\.github/PULL_REQUEST_TEMPLATE\.md", r"\.github/workflows/[^/]+\.yml",
    r"scripts/validate_catalogue\.py", r"data/resources\.json", r"CITATION\.cff",
]
SECRET_PATTERNS = {
    "private key block": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "GitHub token": r"\bgh[pousr]_[A-Za-z0-9]{30,}\b",
    "AWS access key id": r"\bAKIA[0-9A-Z]{16}\b",
    "Slack token": r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b",
    "generic secret assignment": r"(?i)\b(api[_-]?key|secret|passwd|password|token)\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]",
    "email address": r"\b[\w.+-]+@[A-Za-z][\w-]*(\.[A-Za-z][\w-]*)+\b",
}
RELEASE_MARKERS = ("CATALOGUE-PENDING", "LICENSE-PENDING", "SECURITY-CHANNEL-PENDING", "[INSERT ")
UA = "SeeItFlow-catalogue-validator/1.0 (+https://github.com/seeitflow/system-design)"


def site_urls(data):
    return [data["site"]] + list(data.get("site_pages", {}).values())


def load_data():
    return json.loads(DATA.read_text(encoding="utf-8"))


def public_files():
    out = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    return sorted(set(out))


# ---------------------------------------------------------------- data checks
def validate_data(data):
    errors = []
    if data.get("schema_version") != 1:
        errors.append("data: schema_version must be 1")
    site = data.get("site", "")
    if urllib.parse.urlparse(site).hostname not in APPROVED_HOSTS:
        errors.append("data: site must be an https URL on an approved host")
    for name, url in data.get("site_pages", {}).items():
        u = urllib.parse.urlparse(url)
        if u.scheme != "https" or u.hostname not in APPROVED_HOSTS or u.query or u.fragment:
            errors.append(f"data: site_pages.{name} must be a clean HTTPS URL on an approved host")
    seen_ids, seen_urls, seen_titles = set(), set(), set()
    for i, r in enumerate(data.get("resources", [])):
        tag = f"data: resources[{i}] ({r.get('id', '?')})"
        kind = r.get("kind")
        if kind not in KINDS:
            errors.append(f"{tag}: kind must be one of {KINDS}")
            continue
        required = {"id", "kind", "group", "title", "url", TEXT_FIELD[kind]}
        if set(r) != required:
            errors.append(f"{tag}: fields must be exactly {sorted(required)}")
            continue
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", r["id"]):
            errors.append(f"{tag}: id must be kebab-case")
        if r["id"] in seen_ids:
            errors.append(f"{tag}: duplicate id")
        seen_ids.add(r["id"])
        u = urllib.parse.urlparse(r["url"])
        if u.scheme != "https" or u.hostname not in APPROVED_HOSTS:
            errors.append(f"{tag}: url must be HTTPS on an approved host")
        if u.query or u.fragment or u.username or u.password:
            errors.append(f"{tag}: url must not contain query, fragment or credentials")
        if r["url"] in seen_urls:
            errors.append(f"{tag}: duplicate url")
        seen_urls.add(r["url"])
        if r["title"].casefold() in seen_titles:
            errors.append(f"{tag}: duplicate title")
        seen_titles.add(r["title"].casefold())
        for f in ("group", "title", TEXT_FIELD[kind]):
            if not isinstance(r[f], str) or not r[f].strip() or re.search(r"[|\n\r]", r[f]):
                errors.append(f"{tag}: {f} must be non-empty single-line text without '|'")
        text = r[TEXT_FIELD[kind]]
        words = len(text.split())
        if kind != "design" and not 8 <= words <= 40:
            errors.append(f"{tag}: description has {words} words (expected roughly 10-30)")
        if kind == "design" and not 2 <= len([c for c in re.split(r",|;", text) if c.strip()]) <= 5:
            errors.append(f"{tag}: challenges should list 2-4 distinct items")
    return errors


# ------------------------------------------------------------------ rendering
def render_block(resources, kind):
    items = [r for r in resources if r["kind"] == kind]
    if not items:
        return ""
    groups = {}
    for r in items:
        groups.setdefault(r["group"], []).append(r)
    parts = []
    for group, rs in groups.items():
        lines = [f"### {group}", ""]
        if kind == "design":
            lines += ["| System design | Core engineering challenges |", "| --- | --- |"]
            lines += [f"| [{r['title']}]({r['url']}) | {r['challenges']} |" for r in rs]
        else:
            lines += [f"- [{r['title']}]({r['url']}) — {r['description']}" for r in rs]
        parts.append("\n".join(lines))
    return "\n\n".join(parts) + "\n"


def render_readme(text, data):
    for kind in KINDS:
        pat = re.compile(
            rf"(<!-- BEGIN GENERATED:{kind} -->\n)(.*?)(<!-- END GENERATED:{kind} -->)", re.S)
        if not pat.search(text):
            raise SystemExit(f"README: missing generated block markers for '{kind}'")
        block = render_block(data["resources"], kind)
        text = pat.sub(lambda m: m.group(1) + (block + "\n" if block else "") + m.group(3), text, 1)
    return text


# ------------------------------------------------------------- markdown checks
def slugify(heading, counts):
    h = re.sub(r"[`*_~]|\[([^\]]*)\]\([^)]*\)", lambda m: m.group(1) or "", heading).strip().lower()
    h = "".join(c for c in h if c in " -_" or unicodedata.category(c)[0] in "LN")
    slug = h.replace(" ", "-")
    n = counts.get(slug, 0)
    counts[slug] = n + 1
    return slug if n == 0 else f"{slug}-{n}"


def strip_code(text):
    return re.sub(r"```.*?```", "", text, flags=re.S)


def check_markdown(files):
    errors = []
    for f in files:
        if not f.endswith(".md"):
            continue
        text = (ROOT / f).read_text(encoding="utf-8")
        body = strip_code(text)
        counts, slugs, prev = {}, set(), 0
        h1 = 0
        for m in re.finditer(r"^(#{1,6}) +(.+?) *#*$", body, re.M):
            level = len(m.group(1))
            h1 += level == 1
            if prev and level > prev + 1:
                errors.append(f"{f}: heading level jumps to H{level} at '{m.group(2)}'")
            prev = level
            slugs.add(slugify(m.group(2), counts))
        if f in ("README.md", "CONTRIBUTING.md", "MAINTAINERS.md", "SECURITY.md") and h1 != 1:
            errors.append(f"{f}: expected exactly one H1, found {h1}")
        for lineno, line in enumerate(text.splitlines(), 1):
            if line != line.rstrip():
                errors.append(f"{f}:{lineno}: trailing whitespace")
        for m in re.finditer(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", body):
            target = m.group(1)
            if re.match(r"[a-z][a-z0-9+.-]*:", target):
                if not target.startswith("https://"):
                    errors.append(f"{f}: non-HTTPS or unsupported link '{target}'")
                continue
            path, _, frag = target.partition("#")
            if path:
                if not (ROOT / Path(f).parent / path).exists():
                    errors.append(f"{f}: relative link target missing '{target}'")
            elif frag and frag not in slugs:
                errors.append(f"{f}: anchor '#{frag}' does not match any heading")
    return errors


def check_seeitflow_links(files, data):
    allowed = {data["site"]} | set(data.get("site_pages", {}).values()) | {r["url"] for r in data["resources"]}
    errors = []
    for f in files:
        if not f.endswith(".md"):
            continue
        for url in re.findall(r"https?://(?:www\.)?seeitflow\.com[^\s)>\]\"']*", (ROOT / f).read_text(encoding="utf-8")):
            if url not in allowed:
                errors.append(f"{f}: SeeItFlow URL not in data/resources.json: {url}")
    return errors


# ------------------------------------------------------------ tree and workflows
def check_tree(files):
    errors = []
    allowed = [re.compile(p) for p in ALLOWED_FILES]
    secrets = {k: re.compile(v) for k, v in SECRET_PATTERNS.items()}
    for f in files:
        p = ROOT / f
        if p.is_symlink():
            errors.append(f"tree: symlink not allowed: {f}")
            continue
        if not any(a.fullmatch(f) for a in allowed):
            errors.append(f"tree: file not on the public allow-list: {f}")
        if not p.is_file() or p.suffix == ".png" or f == "scripts/validate_catalogue.py":
            continue  # the validator itself contains the detection patterns
        for lineno, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for name, rx in secrets.items():
                if rx.search(line):
                    errors.append(f"tree: possible {name} in {f}:{lineno} (value redacted)")
    for d in ROOT.rglob(".git"):
        if d.parent != ROOT and ".review" not in d.parts and "node_modules" not in d.parts:
            errors.append(f"tree: nested git repository at {d.parent.relative_to(ROOT)}")
    return errors


def check_yaml(files):
    try:
        import yaml  # type: ignore
    except ImportError:
        return [], "NOT RUN: PyYAML not installed"
    errors = []
    for f in files:
        if not (f.endswith(".yml") or f.endswith(".yaml")):
            continue
        try:
            doc = yaml.safe_load((ROOT / f).read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            errors.append(f"yaml: {f}: {e}")
            continue
        if f.startswith(".github/ISSUE_TEMPLATE/") and f.endswith("config.yml"):
            if not isinstance(doc, dict):
                errors.append(f"yaml: {f}: expected a mapping")
        elif f.startswith(".github/ISSUE_TEMPLATE/"):
            for k in ("name", "description", "body"):
                if k not in doc:
                    errors.append(f"yaml: {f}: missing '{k}'")
            ids = set()
            for item in doc.get("body", []):
                if item.get("type") not in ("markdown", "input", "textarea", "dropdown", "checkboxes"):
                    errors.append(f"yaml: {f}: unknown body type {item.get('type')}")
                if item.get("type") != "markdown":
                    if not item.get("id") or item["id"] in ids:
                        errors.append(f"yaml: {f}: missing or duplicate field id")
                    ids.add(item.get("id"))
                    if not item.get("attributes", {}).get("label"):
                        errors.append(f"yaml: {f}: field '{item.get('id')}' has no label")
        elif f.startswith(".github/workflows/"):
            errors += check_workflow(f, doc)
    return errors, "run"


def check_workflow(f, doc):
    errors = []
    on = doc.get(True, doc.get("on", {}))
    if "pull_request_target" in (on if isinstance(on, (dict, list)) else [on]):
        errors.append(f"workflow: {f}: pull_request_target is not allowed")
    if doc.get("permissions") != {"contents": "read"}:
        errors.append(f"workflow: {f}: top-level permissions must be exactly contents: read")
    if "concurrency" not in doc:
        errors.append(f"workflow: {f}: concurrency not set")
    for name, job in doc.get("jobs", {}).items():
        if "timeout-minutes" not in job:
            errors.append(f"workflow: {f}: job '{name}' has no timeout-minutes")
        for step in job.get("steps", []):
            uses = step.get("uses")
            if uses and not re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", uses):
                errors.append(f"workflow: {f}: action not pinned to a full commit SHA: {uses}")
    raw = (ROOT / f).read_text(encoding="utf-8")
    if re.search(r"curl[^\n|]*\|\s*(sh|bash)", raw):
        errors.append(f"workflow: {f}: piping curl to a shell is not allowed")
    if "${{" in raw and re.search(r"run:[^\n]*\$\{\{\s*github\.(event|head_ref)", raw):
        errors.append(f"workflow: {f}: untrusted expression interpolated into run")
    return errors


# --------------------------------------------------------------- release gate
def release_blockers(files, data, inventory_path):
    blockers = []
    for f in files:
        if f.endswith(".md"):
            text = (ROOT / f).read_text(encoding="utf-8")
            for marker in RELEASE_MARKERS:
                if marker in text:
                    blockers.append(f"{f}: unresolved marker '{marker.strip()}'")
    if "LICENSE" not in files:
        blockers.append("LICENSE: not present (owner decision required)")
    if not data["resources"]:
        blockers.append("data: catalogue has no entries")
    if not any(r["kind"] == "design" for r in data["resources"]):
        blockers.append("data: no system design entries")
    if not inventory_path or not Path(inventory_path).exists():
        blockers.append("inventory: no verification inventory supplied (--inventory)")
    else:
        inv = {r.get("url"): r for r in json.loads(Path(inventory_path).read_text())["records"]}
        for url in site_urls(data) + [r["url"] for r in data["resources"]]:
            rec = inv.get(url)
            if not rec or rec.get("verification") != "confirmed":
                blockers.append(f"inventory: {url} is not confirmed")
    return blockers


# ------------------------------------------------------------------ live links
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class PageInfo(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title, self.canonical, self.noindex, self.h1 = "", None, False, ""
        self._in = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("title", "h1") and not getattr(self, "_" + tag + "_done", False):
            self._in = tag
        elif tag == "link" and (a.get("rel") or "").lower() == "canonical":
            self.canonical = a.get("href")
        elif tag == "meta" and (a.get("name") or "").lower() == "robots" and "noindex" in (a.get("content") or "").lower():
            self.noindex = True

    def handle_endtag(self, tag):
        if tag == self._in:
            setattr(self, "_" + tag + "_done", True)
            self._in = None

    def handle_data(self, data):
        if self._in == "title":
            self.title += data
        elif self._in == "h1":
            self.h1 += data


def safe_host(url):
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or u.hostname not in APPROVED_HOSTS:
        return "scheme or host not approved"
    try:
        for info in socket.getaddrinfo(u.hostname, 443, proto=socket.IPPROTO_TCP):
            if not ipaddress.ip_address(info[4][0]).is_global:
                return "host resolves to a non-public address"
    except OSError as e:
        return f"dns error: {e}"
    return None


def fetch_once(url, timeout=20):
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, r.headers.get("Location"), r.read(500_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location"), ""


def check_url(url):
    res = {"url": url, "status": None, "final_url": url, "result": "UNKNOWN", "notes": []}
    current = url
    for _hop in range(4):
        problem = safe_host(current)
        if problem:
            res["notes"].append(f"blocked before request: {problem}")
            return res
        status, location, body = None, None, ""
        for attempt in range(3):
            try:
                status, location, body = fetch_once(current)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                res["notes"].append(f"attempt {attempt + 1}: {type(e).__name__}")
                time.sleep(2 ** attempt)
                continue
            if status in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            break
        if status is None:
            return res
        res["status"] = status
        if status in (301, 302, 303, 307, 308) and location:
            current = urllib.parse.urljoin(current, location)
            res["final_url"] = current
            res["notes"].append(f"redirect to {current}")
            continue
        break
    s = res["status"]
    if s == 200:
        info = PageInfo()
        info.feed(body)
        res.update(title=info.title.strip(), h1=info.h1.strip(), canonical=info.canonical)
        soft = re.search(r"not found|404|page unavailable", f"{info.title} {info.h1}", re.I)
        if res["final_url"] != url:
            res["result"] = "REDIRECT"
        elif info.noindex:
            res["result"] = "NOINDEX"
        elif soft:
            res["result"] = "SOFT-404?"
        elif info.canonical and info.canonical.rstrip("/") != url.rstrip("/"):
            res["result"] = "CANONICAL-MISMATCH"
        else:
            res["result"] = "OK"
    elif s in (404, 410):
        res["result"] = "BROKEN"
    elif s is not None and 300 <= s < 400:
        res["result"] = "REDIRECT"
    return res


def run_links(data, json_out):
    urls = site_urls(data) + [r["url"] for r in data["resources"]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(check_url, urls))
    for r in results:
        print(f"{r['result']:20} {r['status']}  {r['url']}  {'; '.join(r['notes'])}")
    if json_out:
        Path(json_out).write_text(json.dumps(results, indent=2))
    return all(r["result"] == "OK" for r in results)


# ------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("command", choices=["render", "check", "links"])
    ap.add_argument("--release", action="store_true", help="also report release blockers")
    ap.add_argument("--inventory", help="local verification inventory (JSON) for --release")
    ap.add_argument("--json", help="write link-check results to this file")
    args = ap.parse_args()

    data = load_data()
    if args.command == "render":
        errs = validate_data(data)
        if errs:
            print("\n".join(errs))
            return 1
        README.write_text(render_readme(README.read_text(encoding="utf-8"), data), encoding="utf-8")
        print("README.md catalogue blocks regenerated")
        return 0
    if args.command == "links":
        return 0 if run_links(data, args.json) else 1

    files = public_files()
    errors = validate_data(data)
    if README.read_text(encoding="utf-8") != render_readme(README.read_text(encoding="utf-8"), data):
        errors.append("README: generated blocks are out of date (run: render)")
    readme = README.read_text(encoding="utf-8")
    for r in data["resources"]:
        if readme.count(f"]({r['url']})") != 1:
            errors.append(f"README: {r['url']} must appear exactly once")
    errors += check_markdown(files)
    errors += check_seeitflow_links(files, data)
    errors += check_tree(files)
    yaml_errors, yaml_state = check_yaml(files)
    errors += yaml_errors
    print(f"public files: {len(files)} | catalogue entries: {len(data['resources'])} | yaml validation: {yaml_state}")
    for e in errors:
        print("ERROR  " + e)
    blockers = release_blockers(files, data, args.inventory) if args.release else []
    for b in blockers:
        print("BLOCKER  " + b)
    if errors:
        return 1
    if blockers:
        print("RESULT: checks passed, NOT READY FOR PUBLICATION")
        return 2
    print("RESULT: checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
