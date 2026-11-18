#!/usr/bin/env python3
"""Catalogue validator and README renderer (Python standard library; PyYAML for YAML checks).

Commands:
  render    Regenerate the generated blocks in README.md from data/resources.json.
  check     Validate data, README, file links, anchors, workflows, YAML and the public tree.
            Add --release for evidence-based release blockers.
  links     Verify live catalogue URLs over HTTPS (network). Writes structured evidence.
  history   Report (redacted) whether reachable commits carry non-noreply identities.

Only the hosts in APPROVED_HOSTS are ever contacted.
"""

import argparse
import concurrent.futures
import datetime as dt
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

APPROVED_HOSTS = frozenset({"seeitflow.com"})
APPROVED_EMAILS = frozenset({"hello@seeitflow.com"})
NOREPLY_SUFFIX = "@users.noreply.github.com"
SCHEMA_VERSION = 2
SITE_PAGE_KEYS = ("system_design", "about", "contact")
KINDS = ("foundation", "design", "production")
LEVELS = ("Foundations", "Intermediate", "Advanced distributed systems", "AI systems")
COMMON_FIELDS = {"id", "kind", "group", "title", "url"}
KIND_FIELDS = {
    "foundation": {"description"},
    "production": {"description"},
    "design": {"level", "challenges"},
}
DESCRIPTION_WORDS = (10, 32)
CHALLENGE_COUNT = (2, 4)
COUNT_KEYS = ("design", "foundation", "production", "total")
REQUIRED_COUNT_KEYS = ("design", "total")
MAX_BYTES = 2_000_000
MAX_REDIRECTS = 3
EVIDENCE_MAX_AGE_DAYS = 14
UA = "SeeItFlow-catalogue-validator/2.0 (+https://github.com/seeitflow/system-design)"

ALLOWED_FILES = [
    r"README\.md", r"CONTRIBUTING\.md", r"CODE_OF_CONDUCT\.md", r"MAINTAINERS\.md",
    r"SECURITY\.md", r"LICENSE", r"NOTICE\.md", r"\.gitignore", r"\.markdownlint-cli2\.yaml",
    r"\.github/ISSUE_TEMPLATE/[^/]+\.yml", r"\.github/PULL_REQUEST_TEMPLATE\.md",
    r"\.github/workflows/[^/]+\.yml", r"scripts/validate_catalogue\.py",
    r"tests/test_validate_catalogue\.py", r"data/resources\.json", r"CITATION\.cff",
]
# Patterns are assembled from fragments so this file does not match its own scan.
CREDENTIAL_PATTERNS = {
    "private key block": r"-----BEGIN [A-Z ]*PRIVATE" + r" KEY-----",
    "GitHub token": r"\bgh[pousr]" + r"_[A-Za-z0-9]{30,}\b",
    "AWS access key id": r"\bAK" + r"IA[0-9A-Z]{16}\b",
    "Slack token": r"\bxox[abprs]" + r"-[A-Za-z0-9-]{10,}\b",
    "secret assignment": r"(?i)\b(api[_-]?key|secret|passwd|password|token)\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]",
}
EMAIL_RX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")
RELEASE_MARKERS = (
    "CATALOGUE-PENDING", "LICENSE-PENDING", "SECURITY-CHANNEL-PENDING",
    "OWNER-CONFIRMATION-PENDING", "[INSERT ",
)
CHALLENGE_PATTERNS = (
    "just a moment", "attention required", "enable javascript", "captcha",
    "access denied", "blocked by url filter", "web gateway", "verify you are human",
    "checking your browser",
)
SOFT_404_PATTERNS = ("page not found", "not found", "404", "no longer available", "page unavailable")
STOP_WORDS = frozenset({"system", "design", "the", "and", "for", "with", "how", "what", "from"})


# --------------------------------------------------------------------- URLs
def parse_url(value, *, label="url"):
    """Return (normalized_url, error). Strict HTTPS, approved host, no port/credentials/query/fragment."""
    if not isinstance(value, str) or not value.strip():
        return None, f"{label}: must be a non-empty string"
    if re.search(r"[\s\x00-\x1f\x7f\\]", value):
        return None, f"{label}: contains whitespace, control or backslash characters"
    try:
        u = urllib.parse.urlsplit(value)
        port = u.port
    except ValueError:
        return None, f"{label}: malformed URL"
    if u.scheme != "https":
        return None, f"{label}: scheme must be https"
    if u.username is not None or u.password is not None or "@" in u.netloc:
        return None, f"{label}: credentials are not allowed"
    if port is not None:
        return None, f"{label}: explicit ports are not allowed"
    if u.netloc != (u.hostname or "") or u.hostname not in APPROVED_HOSTS:
        return None, f"{label}: host must be one of {sorted(APPROVED_HOSTS)} in lower case"
    if u.query or u.fragment or "?" in value or "#" in value:
        return None, f"{label}: query strings and fragments are not allowed"
    path = u.path or "/"
    if "//" in path or any(seg in (".", "..") for seg in path.split("/")):
        return None, f"{label}: path must be normalized"
    return f"https://{u.hostname}{path}", None


def identity_key(url):
    """Route identity used to detect duplicates (trailing slash and case-insensitive host)."""
    u = urllib.parse.urlsplit(url)
    return (u.hostname or "").lower() + (u.path.rstrip("/") or "/")


# ------------------------------------------------------------- data checks
def _plain_text_error(label, value):
    if not isinstance(value, str) or not value.strip():
        return f"{label}: must be non-empty text"
    if value != value.strip() or re.search(r"[\[\]<>`|\\\n\r\t*]", value):
        return f"{label}: must be single-line plain text without []<>`|*\\ or edge whitespace"
    return None


def _norm(text):
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def validate_data(data):
    """Validate shape and content. Never raises on malformed input."""
    errors = []
    if not isinstance(data, dict):
        return ["data: top level must be an object"]
    if set(data) != {"schema_version", "site", "site_pages", "resources"}:
        errors.append("data: top-level keys must be exactly schema_version, site, site_pages, resources")
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"data: schema_version must be {SCHEMA_VERSION}")
    seen_routes = {}

    def register(label, url):
        norm, err = parse_url(url, label=label)
        if err:
            errors.append(f"data: {err}")
            return
        key = identity_key(norm)
        if key in seen_routes:
            errors.append(f"data: {label} duplicates {seen_routes[key]}")
        seen_routes[key] = label

    register("site", data.get("site"))
    pages = data.get("site_pages")
    if not isinstance(pages, dict) or set(pages) != set(SITE_PAGE_KEYS):
        errors.append(f"data: site_pages must be an object with keys {list(SITE_PAGE_KEYS)}")
    else:
        for name in SITE_PAGE_KEYS:
            register(f"site_pages.{name}", pages[name])
    resources = data.get("resources")
    if not isinstance(resources, list) or not resources:
        errors.append("data: resources must be a non-empty list")
        return errors
    ids, titles = set(), set()
    for i, r in enumerate(resources):
        tag = f"resources[{i}]"
        if not isinstance(r, dict):
            errors.append(f"data: {tag} must be an object")
            continue
        rid = r.get("id")
        tag = f"resources[{i}] ({rid if isinstance(rid, str) else '?'})"
        kind = r.get("kind")
        if kind not in KINDS:
            errors.append(f"data: {tag}: kind must be one of {list(KINDS)}")
            continue
        expected = COMMON_FIELDS | KIND_FIELDS[kind]
        if set(r) != expected:
            errors.append(f"data: {tag}: fields must be exactly {sorted(expected)}")
            continue
        if not isinstance(rid, str) or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", rid):
            errors.append(f"data: {tag}: id must be kebab-case text")
        elif rid in ids:
            errors.append(f"data: {tag}: duplicate id")
        else:
            ids.add(rid)
        register(f"{tag}.url", r["url"])
        for f in ("group", "title"):
            err = _plain_text_error(f"{tag}.{f}", r[f])
            if err:
                errors.append(f"data: {err}")
        if isinstance(r["title"], str):
            n = _norm(r["title"])
            if n in titles:
                errors.append(f"data: {tag}: duplicate title")
            titles.add(n)
        if kind == "design":
            if r["level"] not in LEVELS:
                errors.append(f"data: {tag}.level must be one of {list(LEVELS)}")
            ch = r["challenges"]
            if not isinstance(ch, list) or not CHALLENGE_COUNT[0] <= len(ch) <= CHALLENGE_COUNT[1]:
                errors.append(f"data: {tag}.challenges must be a list of {CHALLENGE_COUNT[0]}-{CHALLENGE_COUNT[1]} items")
            else:
                seen = set()
                for c in ch:
                    err = _plain_text_error(f"{tag}.challenges item", c)
                    if err:
                        errors.append(f"data: {err}")
                    elif "," in c or ";" in c:
                        errors.append(f"data: {tag}.challenges item must not contain commas or semicolons: {c!r}")
                    elif _norm(c) in seen:
                        errors.append(f"data: {tag}.challenges repeats an item")
                    else:
                        seen.add(_norm(c))
        else:
            err = _plain_text_error(f"{tag}.description", r["description"])
            if err:
                errors.append(f"data: {err}")
            else:
                n = len(r["description"].split())
                if not DESCRIPTION_WORDS[0] <= n <= DESCRIPTION_WORDS[1]:
                    errors.append(f"data: {tag}.description has {n} words (expected {DESCRIPTION_WORDS[0]}-{DESCRIPTION_WORDS[1]})")
    return errors


def load_data(path=DATA):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SystemExit(f"cannot read {path}: {e}")


def all_urls(data):
    pages = data["site_pages"]
    return [data["site"]] + [pages[k] for k in SITE_PAGE_KEYS] + [r["url"] for r in data["resources"]]


def check_license(root=ROOT):
    """The repository is public but not open source: LICENSE must be All Rights Reserved."""
    path = root / "LICENSE"
    if not path.is_file():
        return ["license: LICENSE file is missing"]
    text = path.read_text(encoding="utf-8")
    errors = []
    if "all rights reserved" not in text.lower():
        errors.append("license: LICENSE must state All Rights Reserved")
    for term in ("permission is hereby granted", "apache license", "creative commons", "gnu general public", "mit license"):
        if term in text.lower():
            errors.append(f"license: LICENSE must not grant open-source terms ('{term}')")
    return errors


# --------------------------------------------------------------- rendering
def counts(data):
    c = {k: sum(r["kind"] == k for r in data["resources"]) for k in KINDS}
    c["total"] = len(data["resources"])
    return c


def render_block(resources, kind):
    items = [r for r in resources if r["kind"] == kind]
    groups = {}
    for r in items:
        groups.setdefault(r["group"], []).append(r)
    parts = []
    for group, rs in groups.items():
        lines = [f"### {group}", ""]
        if kind == "design":
            lines += ["| System design | Level | Core engineering challenges |", "| --- | --- | --- |"]
            lines += [f"| [{r['title']}]({r['url']}) | {r['level']} | {', '.join(r['challenges'])} |" for r in rs]
        else:
            lines += [f"- [{r['title']}]({r['url']}) — {r['description']}" for r in rs]
        parts.append("\n".join(lines))
    return "\n\n".join(parts) + "\n"


def _single_block(text, begin, end):
    if text.count(begin) != 1 or text.count(end) != 1 or text.index(begin) > text.index(end):
        raise ValueError(f"README must contain exactly one well-ordered {begin.strip()} / {end.strip()} pair")
    return text.index(begin), text.index(end)


def render_readme(text, data):
    for kind in KINDS:
        begin, end = f"<!-- BEGIN GENERATED:{kind} -->\n", f"<!-- END GENERATED:{kind} -->"
        b, e = _single_block(text, begin, end)
        text = text[: b + len(begin)] + render_block(data["resources"], kind) + "\n" + text[e:]
    c = counts(data)
    for key in COUNT_KEYS:
        begin, end = f"<!-- BEGIN GENERATED:count_{key} -->", f"<!-- END GENERATED:count_{key} -->"
        if key not in REQUIRED_COUNT_KEYS and begin not in text and end not in text:
            continue
        b, e = _single_block(text, begin, end)
        text = text[: b + len(begin)] + str(c[key]) + text[e:]
    return text


# --------------------------------------------------------- markdown checks
def slugify(heading, seen):
    h = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    h = re.sub(r"[`*~]", "", h).strip().lower()
    h = "".join(ch for ch in h if ch in " -_" or unicodedata.category(ch)[0] in "LN")
    slug = h.replace(" ", "-")
    n = seen.get(slug, 0)
    seen[slug] = n + 1
    return slug if n == 0 else f"{slug}-{n}"


def strip_code(text):
    return re.sub(r"```.*?```", "", text, flags=re.S)


def check_markdown(files, root=ROOT):
    errors = []
    for f in files:
        if not f.endswith(".md"):
            continue
        text = (root / f).read_text(encoding="utf-8")
        body = strip_code(text)
        seen, slugs, prev, h1 = {}, set(), 0, 0
        for m in re.finditer(r"^(#{1,6}) +(.+?) *#*$", body, re.M):
            level = len(m.group(1))
            h1 += level == 1
            if prev and level > prev + 1:
                errors.append(f"{f}: heading level jumps to H{level} at '{m.group(2)}'")
            prev = level
            slugs.add(slugify(m.group(2), seen))
        if f in ("README.md", "CONTRIBUTING.md", "MAINTAINERS.md", "SECURITY.md") and h1 != 1:
            errors.append(f"{f}: expected exactly one H1, found {h1}")
        for lineno, line in enumerate(text.splitlines(), 1):
            if line != line.rstrip():
                errors.append(f"{f}:{lineno}: trailing whitespace")
        for m in re.finditer(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", body):
            target = m.group(1)
            if target.startswith("mailto:"):
                if target[len("mailto:"):] not in APPROVED_EMAILS:
                    errors.append(f"{f}: mailto link is not an approved public address")
            elif re.match(r"[a-z][a-z0-9+.-]*:", target):
                if not target.startswith("https://"):
                    errors.append(f"{f}: non-HTTPS or unsupported link scheme '{target.split(':')[0]}:'")
            else:
                path, _, frag = target.partition("#")
                if path:
                    if not (root / Path(f).parent / path).exists():
                        errors.append(f"{f}: relative link target missing '{target}'")
                elif frag and frag not in slugs:
                    errors.append(f"{f}: anchor '#{frag}' does not match any heading")
    return errors


def check_site_links(files, data, root=ROOT):
    allowed = {identity_key(u) for u in all_urls(data)}
    errors = []
    for f in files:
        if not f.endswith((".md", ".yml")):
            continue
        text = (root / f).read_text(encoding="utf-8")
        for url in re.findall(r"https?://(?:www\.)?seeitflow\.com[^\s)>\]\"']*", text):
            if identity_key(url) not in allowed:
                errors.append(f"{f}: SeeItFlow URL is not in data/resources.json: {url}")
    return errors


def check_readme_coverage(readme, data):
    return [f"README: {r['url']} must appear exactly once" for r in data["resources"]
            if readme.count(f"]({r['url']})") != 1]


# ------------------------------------------------------- tree and secrets
def public_files(root=ROOT):
    out = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard"], cwd=root, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    return sorted(set(out))


def check_tree(files, root=ROOT):
    """Allow-list, symlink, nested repository, credential and email checks. Findings are redacted."""
    errors = []
    allowed = [re.compile(p) for p in ALLOWED_FILES]
    creds = {k: re.compile(v) for k, v in CREDENTIAL_PATTERNS.items()}
    for f in files:
        p = root / f
        if p.is_symlink():
            errors.append(f"tree: symlink not allowed: {f}")
            continue
        if not any(a.fullmatch(f) for a in allowed):
            errors.append(f"tree: file is not on the public allow-list: {f}")
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"tree: non-text file in public tree: {f}")
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for name, rx in creds.items():
                if rx.search(line):
                    errors.append(f"tree: possible {name} at {f}:{lineno} (value redacted)")
            for m in EMAIL_RX.finditer(line):
                if m.group(0).lower() not in APPROVED_EMAILS:
                    errors.append(f"tree: unapproved email address at {f}:{lineno} (value redacted)")
    for d in root.rglob(".git"):
        rel = d.parent.relative_to(root)
        if str(rel) != "." and not {".review", "node_modules"} & set(rel.parts):
            errors.append(f"tree: nested git repository at {rel}")
    return errors


# ------------------------------------------------------------ YAML checks
def check_yaml(files, root=ROOT):
    try:
        import yaml  # type: ignore
    except ImportError:
        return ["yaml: PyYAML is required (pip install PyYAML==6.0.2); use --skip-yaml only for local development"], "missing"
    errors = []
    for f in files:
        if not f.endswith((".yml", ".yaml")):
            continue
        raw = (root / f).read_text(encoding="utf-8")
        try:
            doc = yaml.safe_load(raw)
        except yaml.YAMLError as e:
            errors.append(f"yaml: {f}: {e.__class__.__name__}: invalid YAML")
            continue
        if not isinstance(doc, dict):
            errors.append(f"yaml: {f}: expected a mapping")
        elif f == ".github/ISSUE_TEMPLATE/config.yml":
            for link in doc.get("contact_links") or []:
                _, err = parse_url(link.get("url"), label=f"{f} contact link")
                if err:
                    errors.append(f"yaml: {err}")
        elif f.startswith(".github/ISSUE_TEMPLATE/"):
            errors += check_issue_form(f, doc)
        elif f.startswith(".github/workflows/"):
            errors += check_workflow(f, doc, raw)
    return errors, "run"


def check_issue_form(f, doc):
    errors = []
    for k in ("name", "description", "body"):
        if k not in doc:
            errors.append(f"yaml: {f}: missing '{k}'")
    ids = set()
    for item in doc.get("body") or []:
        t = item.get("type")
        if t not in ("markdown", "input", "textarea", "dropdown", "checkboxes"):
            errors.append(f"yaml: {f}: unknown body type {t}")
        if t != "markdown":
            if not item.get("id") or item["id"] in ids:
                errors.append(f"yaml: {f}: missing or duplicate field id")
            ids.add(item.get("id"))
            if not (item.get("attributes") or {}).get("label"):
                errors.append(f"yaml: {f}: field '{item.get('id')}' has no label")
    return errors


def check_workflow(f, doc, raw):
    errors = []
    on = doc.get(True, doc.get("on"))
    triggers = list(on) if isinstance(on, (dict, list)) else [on]
    if "pull_request_target" in triggers:
        errors.append(f"workflow: {f}: pull_request_target is not allowed")
    if doc.get("permissions") != {"contents": "read"}:
        errors.append(f"workflow: {f}: top-level permissions must be exactly contents: read")
    if "concurrency" not in doc:
        errors.append(f"workflow: {f}: concurrency is not set")
    for name, job in (doc.get("jobs") or {}).items():
        if "timeout-minutes" not in job:
            errors.append(f"workflow: {f}: job '{name}' has no timeout-minutes")
        if "permissions" in job and job["permissions"] != {"contents": "read"}:
            errors.append(f"workflow: {f}: job '{name}' requests more than contents: read")
        if not re.fullmatch(r"ubuntu-\d\d\.\d\d", str(job.get("runs-on", ""))):
            errors.append(f"workflow: {f}: job '{name}' must pin a runner image such as ubuntu-24.04")
        for step in job.get("steps") or []:
            uses = step.get("uses")
            if uses and not re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", uses):
                errors.append(f"workflow: {f}: action is not pinned to a full commit SHA: {uses}")
            run = step.get("run", "")
            if re.search(r"\$\{\{\s*(github\.(event|head_ref)|inputs|env)", run):
                errors.append(f"workflow: {f}: untrusted expression interpolated into a run step")
            if re.search(r"curl[^\n|]*\|\s*(sh|bash)", run):
                errors.append(f"workflow: {f}: piping curl to a shell is not allowed")
    if "secrets." in raw:
        errors.append(f"workflow: {f}: workflows must not use secrets")
    return errors


# ----------------------------------------------------------- live fetching
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def host_resolves_publicly(host):
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError as e:
        return f"dns error: {e.__class__.__name__}"
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            return "host resolves to a non-public address"
    return None


def fetch_once(url, timeout=20):
    """One GET without following redirects. Returns a response dict."""
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})
    try:
        r = opener.open(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        r = e
    with r:
        raw = r.read(MAX_BYTES + 1)
        headers = r.headers
        status = getattr(r, "status", None) or r.code
    return {
        "status": status,
        "location": headers.get("Location"),
        "content_type": (headers.get("Content-Type") or "").split(";")[0].strip().lower(),
        "x_robots_tag": headers.get("X-Robots-Tag"),
        "truncated": len(raw) > MAX_BYTES,
        "body": raw[:MAX_BYTES].decode("utf-8", "replace"),
    }


class PageInfo(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.h1 = "", ""
        self.canonicals, self.robots = [], []
        self._open = None
        self._done = set()

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag in ("title", "h1") and tag not in self._done:
            self._open = tag
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.canonicals.append(a.get("href", ""))
        elif tag == "meta" and a.get("name", "").lower() in ("robots", "googlebot"):
            self.robots.append(a.get("content", "").lower())

    def handle_endtag(self, tag):
        if self._open == tag:
            self._done.add(tag)
            self._open = None

    def handle_data(self, data):
        if self._open == "title":
            self.title += data
        elif self._open == "h1":
            self.h1 += data


def _tokens(text):
    return {t for t in re.findall(r"[a-z0-9]{3,}", text.lower()) if t not in STOP_WORDS}


def classify(url, resp, expected_title=None):
    """Classify a final (non-redirect) response. Pure function; no network."""
    out = {
        "http_status": resp["status"], "content_type": resp.get("content_type"),
        "http_ok": False, "content_verified": False, "canonical_verified": False,
        "robots_ok": None, "title": None, "h1": None, "canonical": None,
        "robots_meta": None, "x_robots_tag": resp.get("x_robots_tag"), "notes": [],
    }
    s = resp["status"]
    if s in (404, 410):
        return {**out, "result": "BROKEN"}
    if s in (403, 408, 429) or s >= 500:
        return {**out, "result": "UNKNOWN", "notes": [f"HTTP {s}; not treated as proof the page is broken"]}
    if s != 200:
        return {**out, "result": "BROKEN", "notes": [f"unexpected HTTP {s}"]}
    out["http_ok"] = True
    if resp.get("truncated"):
        return {**out, "result": "TOO-LARGE"}
    if resp.get("content_type") not in ("text/html", "application/xhtml+xml"):
        return {**out, "result": "NON-HTML"}
    info = PageInfo()
    info.feed(resp["body"])
    info.close()
    title, h1 = " ".join(info.title.split()), " ".join(info.h1.split())
    out.update(title=title, h1=h1, canonical=info.canonicals[0] if info.canonicals else None,
               robots_meta=info.robots or None)
    haystack = f"{title} {h1} {resp['body'][:4000]}".lower()
    if any(p in haystack for p in CHALLENGE_PATTERNS):
        return {**out, "result": "CHALLENGE"}
    if not title and not h1:
        return {**out, "result": "EMPTY-SHELL"}
    if re.search("|".join(SOFT_404_PATTERNS), f"{title} {h1}".lower()):
        return {**out, "result": "SOFT-404"}
    robots_values = [v for v in (info.robots + [resp.get("x_robots_tag") or ""]) if v]
    out["robots_ok"] = not any("noindex" in v for v in robots_values)
    if not out["robots_ok"]:
        return {**out, "result": "NOINDEX"}
    if len(info.canonicals) > 1:
        return {**out, "result": "CANONICAL-MULTIPLE"}
    if not info.canonicals:
        return {**out, "result": "CANONICAL-MISSING"}
    c, err = parse_url(info.canonicals[0], label="canonical")
    if err or c != url:
        return {**out, "result": "CANONICAL-MISMATCH", "notes": [err or "canonical differs from the catalogue URL"]}
    out["canonical_verified"] = True
    if expected_title:
        want = _tokens(expected_title)
        have = _tokens(f"{title} {h1}")
        if want and len(want & have) / len(want) < 0.5:
            return {**out, "result": "WRONG-CONTENT", "notes": ["page title/H1 share too few terms with the catalogue title"]}
    out["content_verified"] = True
    return {**out, "result": "VERIFIED"}


def verify_url(url, expected_title=None, fetch=fetch_once, resolve=host_resolves_publicly, sleep=time.sleep):
    """Follow at most MAX_REDIRECTS validated redirects, then classify. `fetch`/`resolve` are injectable."""
    record = {"url": url, "final_url": url, "redirect_chain": [],
              "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "method": "origin-http", "result": "UNKNOWN", "notes": []}
    norm, err = parse_url(url)
    if err:
        record.update(result="REJECTED", notes=[err])
        return record
    current, seen = norm, {norm}
    for _ in range(MAX_REDIRECTS + 1):
        problem = resolve(urllib.parse.urlsplit(current).hostname)
        if problem:
            record["notes"].append(f"not requested: {problem}")
            return record
        resp = None
        for attempt in range(3):
            try:
                resp = fetch(current)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                record["notes"].append(f"attempt {attempt + 1}: {e.__class__.__name__}")
                sleep(2 ** attempt)
                continue
            if resp["status"] in (429, 500, 502, 503, 504) and attempt < 2:
                sleep(2 ** attempt)
                continue
            break
        if resp is None:
            return record
        if resp["status"] in (301, 302, 303, 307, 308):
            nxt, err = parse_url(urllib.parse.urljoin(current, resp.get("location") or ""), label="redirect target")
            record["redirect_chain"].append({"from": current, "status": resp["status"], "to": nxt})
            if err:
                record.update(result="REDIRECT-REJECTED", notes=record["notes"] + [err])
                return record
            if nxt in seen:
                record.update(result="REDIRECT-LOOP", final_url=nxt)
                return record
            seen.add(nxt)
            current = nxt
            record["final_url"] = nxt
            continue
        verdict = classify(current, resp, expected_title)
        notes = record["notes"] + verdict.pop("notes")
        record.update(verdict)
        record["notes"] = notes
        record["final_url"] = current
        if record["redirect_chain"] and record["result"] == "VERIFIED":
            record["result"] = "REDIRECT"
        return record
    record.update(result="REDIRECT-LIMIT")
    return record


def run_links(data, json_out, workers=3):
    pairs = [(data["site"], None)] + [(data["site_pages"][k], None) for k in SITE_PAGE_KEYS]
    pairs += [(r["url"], r["title"]) for r in data["resources"]]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(workers, 4))) as ex:
        results = list(ex.map(lambda p: verify_url(*p), pairs))
    for r in results:
        print(f"{r['result']:20} {r.get('http_status')}  {r['url']}  {'; '.join(r['notes'])}")
    if json_out:
        evidence = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "method": "origin-http",
                    "validator": "validate_catalogue.py links", "results": results}
        Path(json_out).write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return all(r["result"] == "VERIFIED" for r in results)


# ------------------------------------------------------------ release gate
def evidence_blockers(data, evidence, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if not isinstance(evidence, dict) or evidence.get("method") != "origin-http" or not isinstance(evidence.get("results"), list):
        return ["evidence: not an origin-http evidence file produced by the links command"]
    blockers, by_url = [], {}
    for r in evidence["results"]:
        if isinstance(r, dict) and isinstance(r.get("url"), str):
            by_url[r["url"]] = r
    expected = set(all_urls(data))
    for u in sorted(expected - set(by_url)):
        blockers.append(f"evidence: no result for {u}")
    for u in sorted(set(by_url) - expected):
        blockers.append(f"evidence: result for URL not in the catalogue: {u}")
    for u in sorted(expected & set(by_url)):
        r = by_url[u]
        if r.get("result") != "VERIFIED" or not (r.get("http_ok") and r.get("content_verified") and r.get("canonical_verified")):
            blockers.append(f"evidence: {u} is {r.get('result')}")
            continue
        if r.get("final_url") != u or r.get("redirect_chain"):
            blockers.append(f"evidence: {u} redirected")
        try:
            age = now - dt.datetime.fromisoformat(r["fetched_at"])
            if age > dt.timedelta(days=EVIDENCE_MAX_AGE_DAYS) or age < -dt.timedelta(minutes=5):
                blockers.append(f"evidence: {u} is stale or dated in the future")
        except (KeyError, ValueError, TypeError):
            blockers.append(f"evidence: {u} has no valid fetched_at")
    return blockers


def baseline_blockers(data, baseline):
    """Every design URL in the owner's baseline must be listed, and none unknown."""
    if not isinstance(baseline, dict) or not isinstance(baseline.get("design_urls"), list):
        return ["baseline: expected an object with a design_urls list"]
    have = {r["url"] for r in data["resources"] if r["kind"] == "design"}
    want = set(baseline["design_urls"])
    return [f"baseline: design missing from catalogue: {u}" for u in sorted(want - have)] + [
        f"baseline: catalogue design not in baseline: {u}" for u in sorted(have - want)]


def history_findings(root=ROOT):
    """Redacted report: commit hashes and counts only, never identity values."""
    try:
        out = subprocess.run(["git", "log", "--all", "--format=%h|%ae|%ce"], cwd=root,
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return ["history: git history could not be read"]
    bad = [h for h, a, c in (line.split("|") for line in out.splitlines() if line.count("|") == 2)
           if not (a.lower().endswith(NOREPLY_SUFFIX) and c.lower().endswith(NOREPLY_SUFFIX))]
    if not bad:
        return []
    return [f"history: {len(bad)} reachable commit(s) have a non-noreply author or committer identity "
            f"(e.g. {', '.join(bad[:3])}); identity values withheld"]


def release_blockers(files, data, evidence_path, baseline_path, root=ROOT, with_history=True):
    blockers = []
    for f in files:
        if f.endswith((".md", ".yml")):
            text = (root / f).read_text(encoding="utf-8")
            for marker in RELEASE_MARKERS:
                if marker in text:
                    blockers.append(f"{f}: unresolved marker '{marker.strip()}'")
    if "LICENSE" not in files:
        blockers.append("LICENSE: not tracked or present")
    for label, path, fn in (("evidence", evidence_path, lambda d: evidence_blockers(data, d)),
                            ("baseline", baseline_path, lambda d: baseline_blockers(data, d))):
        if not path or not Path(path).exists():
            blockers.append(f"{label}: file not supplied (--{label})")
            continue
        try:
            blockers += fn(json.loads(Path(path).read_text(encoding="utf-8")))
        except ValueError:
            blockers.append(f"{label}: not valid JSON")
    if with_history:
        blockers += history_findings(root)
    return blockers


# -------------------------------------------------------------------- main
def run_check(args):
    data = load_data(args.data)
    errors = validate_data(data)
    if errors:
        print("\n".join("ERROR  " + e for e in errors))
        return 1
    readme = README.read_text(encoding="utf-8")
    try:
        if readme != render_readme(readme, data):
            errors.append("README: generated blocks are out of date (run: render)")
    except ValueError as e:
        errors.append(f"README: {e}")
    errors += check_readme_coverage(readme, data)
    files = public_files()
    errors += check_markdown(files) + check_site_links(files, data) + check_tree(files) + check_license()
    if args.skip_yaml:
        yaml_state = "skipped"
    else:
        yaml_errors, yaml_state = check_yaml(files)
        errors += yaml_errors
    c = counts(data)
    print(f"public files: {len(files)} | entries: {c['total']} ({c['design']} designs, {c['foundation']} foundations, "
          f"{c['production']} architecture/production) | yaml: {yaml_state}")
    for e in errors:
        print("ERROR  " + e)
    blockers = release_blockers(files, data, args.evidence, args.baseline) if args.release else []
    for b in blockers:
        print("BLOCKER  " + b)
    if args.release:
        print("MANUAL GATES (not verifiable by this script): owner editorial review, GitHub rendering, "
              "GitHub Actions run, repository settings, private vulnerability reporting enablement")
    if errors:
        return 1
    if blockers:
        print("RESULT: checks passed, NOT READY FOR PUBLICATION")
        return 2
    print("RESULT: checks passed")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["render", "check", "links", "history"])
    ap.add_argument("--data", default=str(DATA), help="catalogue JSON (default: data/resources.json)")
    ap.add_argument("--release", action="store_true", help="check: also report release blockers")
    ap.add_argument("--evidence", help="check --release: evidence JSON written by the links command")
    ap.add_argument("--baseline", help="check --release: JSON {\"design_urls\": [...]} from the owner's product inventory")
    ap.add_argument("--json", help="links: write structured evidence to this file")
    ap.add_argument("--workers", type=int, default=3, help="links: concurrent requests (1-4)")
    ap.add_argument("--skip-yaml", action="store_true", help="check: skip YAML validation (local development only)")
    args = ap.parse_args(argv)

    if args.command == "history":
        findings = history_findings()
        print("\n".join(findings) if findings else "history: all reachable commits use noreply identities")
        return 1 if findings else 0
    data = load_data(args.data)
    if args.command in ("render", "links"):
        errors = validate_data(data)
        if errors:
            print("\n".join("ERROR  " + e for e in errors))
            return 1
    if args.command == "render":
        README.write_text(render_readme(README.read_text(encoding="utf-8"), data), encoding="utf-8")
        print("README.md generated blocks refreshed")
        return 0
    if args.command == "links":
        return 0 if run_links(data, args.json, args.workers) else 1
    return run_check(args)


if __name__ == "__main__":
    sys.exit(main())
