#!/usr/bin/env python3
"""Catalogue validator and README renderer (Python standard library; PyYAML for YAML checks).

Commands:
  render    Regenerate the generated blocks in README.md from data/resources.json.
  check     Validate data, README, links, anchors, workflows, YAML, licensing and the public tree.
            Unknown but safe files are warnings. Add --release for strict file-manifest
            enforcement and evidence-based release blockers.
  links     Verify live catalogue URLs over HTTPS (network). Writes structured evidence.
  history   Classify commit identities against a local, private identity policy.

Only the hosts in APPROVED_HOSTS are ever contacted.

Evidence model: `links` output is *consistency-checked* by `check --release`; it is not
cryptographic proof of provenance. Use evidence from a trusted GitHub Actions run
(artifact from the exact commit) and confirm the run on GitHub.
"""

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import http.client
import ipaddress
import json
import os
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

VALIDATOR_VERSION = "3.0.0"
EVIDENCE_SCHEMA = 2
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "resources.json"
README = ROOT / "README.md"

APPROVED_HOSTS = frozenset({"seeitflow.com"})
APPROVED_EMAILS = frozenset({"hello@seeitflow.com"})
APPROVED_CONTACT_LINKS = frozenset({"https://github.com/seeitflow/system-design/security/policy"})
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
DESCRIPTION_WORDS = (10, 34)
CHALLENGE_COUNT = (2, 4)
COUNT_KEYS = ("design", "foundation", "production", "total")
REQUIRED_COUNT_KEYS = ("design", "total")

MAX_BYTES = 2_000_000
MAX_REDIRECTS = 3
REQUEST_TIMEOUT = 15
URL_BUDGET_SECONDS = 90  # per-URL deadline across redirects and retries
EVIDENCE_MAX_AGE_DAYS = 14
UA = "SeeItFlow-catalogue-validator/3.0 (+https://github.com/seeitflow/system-design)"

# Visible-content thresholds. Short legitimate pages pass; shells and stubs do not.
LESSON_MIN_WORDS = 100
GENERAL_MIN_WORDS = 25
SHELL_MAX_WORDS = 9
GENERAL_PAGE_TERMS = {
    "site": ("seeitflow", "see them work"),
    "system_design": ("system design",),
    "about": ("about",),
    "contact": ("contact",),
}

ALLOWED_FILES = [
    r"README\.md", r"CONTRIBUTING\.md", r"CODE_OF_CONDUCT\.md", r"MAINTAINERS\.md",
    r"SECURITY\.md", r"LICENSE", r"\.gitignore", r"\.markdownlint-cli2\.yaml",
    r"\.github/ISSUE_TEMPLATE/[^/]+\.yml", r"\.github/PULL_REQUEST_TEMPLATE\.md", r"\.github/CODEOWNERS",
    r"\.github/workflows/[^/]+\.yml", r"scripts/validate_catalogue\.py",
    r"tests/test_validate_catalogue\.py", r"data/resources\.json",
]
FORBIDDEN_PATHS = [
    (r"(^|/)\.review(/|$)", "internal review material"),
    (r"(^|/)SEEITFLOW_", "private SeeItFlow document or inventory"),
    (r"(^|/)(RESOURCE_INVENTORY|DESIGN_BASELINE|APPROVED_BASELINE|IDENTITY_POLICY)", "private inventory, baseline or policy"),
    (r"(^|/)live-url-evidence[^/]*\.json$", "generated verification evidence"),
    (r"\.(bundle|bak|orig|rej|swp|tmp|log|pyc)$", "backup, temporary or generated file"),
    (r"(^|/)(__pycache__|node_modules)(/|$)", "dependency or cache directory"),
    (r"(^|/)\.(idea|vscode|wibey|copilot|claude|cursor|aider)[^/]*(/|$)", "local editor or AI-tool configuration"),
    (r"(^|/)\.env(\.|$)", "local environment file"),
    (r"(^|/)(mirror|backup)[^/]*\.git(/|$)", "repository backup"),
    (r"(^|/)(prompt|prompts)[^/]*\.txt$", "local working prompt"),
]
REQUIRED_GITIGNORE = (
    ".review/", "SEEITFLOW_*_REQUIREMENTS.md", "SEEITFLOW_*_INVENTORY.json", "SEEITFLOW_*_REVIEW.md",
    "*.bundle", "*.bak", "live-url-evidence*.json", ".idea/", ".env",
)
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
SOFT_404_RX = re.compile(r"page not found|not found|\b404\b|no longer available|page unavailable|does not exist")
LOGIN_RX = re.compile(r"\b(log ?in|sign ?in)\b")
STOP_WORDS = frozenset({"system", "design", "the", "and", "for", "with", "how", "what", "from", "explained"})
ROBOTS_AGENTS = frozenset({"robots", "googlebot", "bingbot"})
THIRD_PARTY_NOTICE_MARKER = "Contributor Covenant"
OPEN_SOURCE_TERMS = ("permission is hereby granted", "apache license", "creative commons",
                     "gnu general public", "mit license", "bsd license", "mozilla public license")


# --------------------------------------------------------------------- URLs
def parse_url(value, *, label="url"):
    """Return (normalized_url, error). Strict HTTPS on an approved host.

    Rejects credentials, ports, query strings, fragments, whitespace and control characters,
    any percent-encoding (encoded traversal, separators, control characters and double
    encoding), non-ASCII text, dot segments, empty segments and trailing host dots.
    """
    if not isinstance(value, str) or not value.strip():
        return None, f"{label}: must be a non-empty string"
    if re.search(r"[\s\x00-\x1f\x7f\\]", value):
        return None, f"{label}: contains whitespace, control or backslash characters"
    if not value.isascii():
        return None, f"{label}: must be ASCII"
    if "%" in value:
        return None, f"{label}: percent-encoding is not allowed (encoded separators, traversal and double encoding)"
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


def read_json(path, label):
    """Read a JSON file; return (value, error) instead of raising."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")), None
    except OSError as e:
        return None, f"{label}: cannot read file ({e.__class__.__name__})"
    except ValueError:
        return None, f"{label}: not valid JSON"


def load_data(path=DATA):
    value, err = read_json(path, "data")
    if err:
        raise SystemExit(err)
    return value


def all_urls(data):
    pages = data["site_pages"]
    return [data["site"]] + [pages[k] for k in SITE_PAGE_KEYS] + [r["url"] for r in data["resources"]]


def catalogue_digest(data):
    """Digest of the catalogue content (key order and whitespace independent)."""
    blob = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def git_head(root=ROOT):
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


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


HEADING_RX = re.compile(r"^(#{1,6}) +(.+?) *#*$", re.M)


def heading_slugs(text):
    seen = {}
    return {slugify(m.group(2), seen) for m in HEADING_RX.finditer(strip_code(text))}


def _inside(root, path):
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def check_markdown(files, root=ROOT):
    errors = []
    cache = {}

    def slugs_of(rel_path):
        if rel_path not in cache:
            p = root / rel_path
            cache[rel_path] = heading_slugs(p.read_text(encoding="utf-8")) if p.suffix == ".md" and p.is_file() else None
        return cache[rel_path]

    for f in files:
        if not f.endswith(".md"):
            continue
        text = (root / f).read_text(encoding="utf-8")
        body = strip_code(text)
        prev, h1 = 0, 0
        for m in HEADING_RX.finditer(body):
            level = len(m.group(1))
            h1 += level == 1
            if prev and level > prev + 1:
                errors.append(f"{f}: heading level jumps to H{level} at '{m.group(2)}'")
            prev = level
        if f in ("README.md", "CONTRIBUTING.md", "MAINTAINERS.md", "SECURITY.md") and h1 != 1:
            errors.append(f"{f}: expected exactly one H1, found {h1}")
        for lineno, line in enumerate(text.splitlines(), 1):
            if line != line.rstrip():
                errors.append(f"{f}:{lineno}: trailing whitespace")
        own = slugs_of(f)
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
                if not path:
                    if frag and own is not None and frag not in own:
                        errors.append(f"{f}: anchor '#{frag}' does not match any heading")
                    continue
                dest = (root / Path(f).parent / path)
                if not _inside(root, dest):
                    errors.append(f"{f}: relative link leaves the repository: '{target}'")
                elif not dest.exists():
                    errors.append(f"{f}: relative link target missing '{target}'")
                elif frag:
                    rel = str(dest.resolve().relative_to(root.resolve()))
                    other = slugs_of(rel)
                    if other is None:
                        errors.append(f"{f}: anchor '#{frag}' used on a non-Markdown target '{path}'")
                    elif frag not in other:
                        errors.append(f"{f}: anchor '#{frag}' does not match any heading in {rel}")
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


def check_tree(files, root=ROOT, strict=False, warnings=None):
    """Forbidden-path, symlink, nested repository, credential and email checks, plus the allow-list.

    Files outside ALLOWED_FILES are reported to `warnings` for maintainer review in standard
    validation and are still scanned like every other file. With strict=True (release
    validation) they are errors, so the final manifest needs explicit approval.

    Operates on tracked and untracked-but-not-ignored files, so a file that is already tracked
    is still caught even if .gitignore later lists it. Findings are redacted.
    """
    errors = []
    allowed = [re.compile(p) for p in ALLOWED_FILES]
    forbidden = [(re.compile(p), why) for p, why in FORBIDDEN_PATHS]
    creds = {k: re.compile(v) for k, v in CREDENTIAL_PATTERNS.items()}
    for f in files:
        p = root / f
        bad = [why for rx, why in forbidden if rx.search(f)]
        if bad:
            errors.append(f"tree: forbidden file in the public tree ({bad[0]}): {f}")
            continue
        if p.is_symlink():
            errors.append(f"tree: symlink not allowed: {f}")
            continue
        if not any(a.fullmatch(f) for a in allowed):
            if strict:
                errors.append(f"tree: file is not on the approved public file manifest: {f}")
            elif warnings is not None:
                warnings.append(f"tree: file is not on the approved public file manifest (review before release): {f}")
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


def check_gitignore(root=ROOT):
    path = root / ".gitignore"
    if not path.is_file():
        return ["gitignore: .gitignore is missing"]
    lines = {ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()}
    return [f"gitignore: missing required pattern '{p}'" for p in REQUIRED_GITIGNORE if p not in lines]


def check_license(root=ROOT):
    """The repository is public but not open source: LICENSE must be All Rights Reserved.

    A narrowly scoped exception exists for a clearly marked third-party notice: a paragraph
    that names the Contributor Covenant may mention its Creative Commons license. The notice
    must be mirrored in CODE_OF_CONDUCT.md with the license link and a statement of changes.
    """
    path = root / "LICENSE"
    if not path.is_file():
        return ["license: LICENSE file is missing"]
    text = path.read_text(encoding="utf-8")
    errors = []
    if "all rights reserved" not in text.lower():
        errors.append("license: LICENSE must state All Rights Reserved")
    paragraphs = re.split(r"\n\s*\n", text)
    scanned = "\n".join(p for p in paragraphs if THIRD_PARTY_NOTICE_MARKER not in p).lower()
    for term in OPEN_SOURCE_TERMS:
        if term in scanned:
            errors.append(f"license: LICENSE must not grant open-source terms ('{term}')")
    coc = root / "CODE_OF_CONDUCT.md"
    if coc.is_file():
        c = coc.read_text(encoding="utf-8")
        if THIRD_PARTY_NOTICE_MARKER in c:
            need = ("creativecommons.org/licenses/by/4.0", "CC BY 4.0", "Changes")
            errors += [f"license: CODE_OF_CONDUCT.md third-party notice lacks '{n}'" for n in need if n not in c]
            if THIRD_PARTY_NOTICE_MARKER not in text:
                errors.append("license: LICENSE must identify the Contributor Covenant carve-out")
    return errors


# ------------------------------------------------------------ YAML checks
def _is_map(x):
    return isinstance(x, dict)


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
        if not _is_map(doc):
            errors.append(f"yaml: {f}: expected a mapping")
        elif f == ".github/ISSUE_TEMPLATE/config.yml":
            errors += check_issue_config(f, doc)
        elif f.startswith(".github/ISSUE_TEMPLATE/"):
            errors += check_issue_form(f, doc)
        elif f.startswith(".github/workflows/"):
            errors += check_workflow(f, doc, raw)
    return errors, "run"


def check_issue_config(f, doc):
    errors = []
    if doc.get("blank_issues_enabled") is not False:
        errors.append(f"yaml: {f}: blank_issues_enabled must be false")
    links = doc.get("contact_links", [])
    if not isinstance(links, list):
        return errors + [f"yaml: {f}: contact_links must be a list"]
    for i, link in enumerate(links):
        if not _is_map(link):
            errors.append(f"yaml: {f}: contact_links[{i}] must be a mapping")
            continue
        for k in ("name", "url", "about"):
            if not isinstance(link.get(k), str) or not link[k].strip():
                errors.append(f"yaml: {f}: contact_links[{i}].{k} must be text")
        url = link.get("url")
        if isinstance(url, str) and url not in APPROVED_CONTACT_LINKS:
            _, err = parse_url(url, label=f"{f} contact_links[{i}].url")
            if err:
                errors.append(f"yaml: {err}")
    return errors


def check_issue_form(f, doc):
    errors = []
    for k in ("name", "description", "body"):
        if k not in doc:
            errors.append(f"yaml: {f}: missing '{k}'")
    body = doc.get("body", [])
    if not isinstance(body, list):
        return errors + [f"yaml: {f}: body must be a list"]
    ids = set()
    for i, item in enumerate(body):
        if not _is_map(item):
            errors.append(f"yaml: {f}: body[{i}] must be a mapping")
            continue
        t = item.get("type")
        if t not in ("markdown", "input", "textarea", "dropdown", "checkboxes"):
            errors.append(f"yaml: {f}: body[{i}] has unknown type {t!r}")
            continue
        attrs = item.get("attributes")
        if not _is_map(attrs):
            errors.append(f"yaml: {f}: body[{i}].attributes must be a mapping")
            attrs = {}
        if t == "markdown":
            continue
        fid = item.get("id")
        if not isinstance(fid, str) or not fid or fid in ids:
            errors.append(f"yaml: {f}: body[{i}] has a missing, non-text or duplicate id")
        else:
            ids.add(fid)
        if not isinstance(attrs.get("label"), str) or not attrs["label"].strip():
            errors.append(f"yaml: {f}: body[{i}] has no label")
        if t == "dropdown" and not (isinstance(attrs.get("options"), list) and attrs["options"]):
            errors.append(f"yaml: {f}: body[{i}] dropdown needs options")
    return errors


def check_workflow(f, doc, raw):
    errors = []
    on = doc.get(True, doc.get("on"))
    if isinstance(on, dict):
        triggers = list(on)
    elif isinstance(on, list):
        triggers = on
    else:
        triggers = [on]
    if "pull_request_target" in triggers:
        errors.append(f"workflow: {f}: pull_request_target is not allowed")
    if doc.get("permissions") != {"contents": "read"}:
        errors.append(f"workflow: {f}: top-level permissions must be exactly contents: read")
    if "concurrency" not in doc:
        errors.append(f"workflow: {f}: concurrency is not set")
    jobs = doc.get("jobs")
    if not _is_map(jobs) or not jobs:
        return errors + [f"workflow: {f}: jobs must be a non-empty mapping"]
    for name, job in jobs.items():
        if not _is_map(job):
            errors.append(f"workflow: {f}: job '{name}' must be a mapping")
            continue
        if not isinstance(job.get("timeout-minutes"), int):
            errors.append(f"workflow: {f}: job '{name}' has no integer timeout-minutes")
        if "permissions" in job and job["permissions"] != {"contents": "read"}:
            errors.append(f"workflow: {f}: job '{name}' requests more than contents: read")
        if not re.fullmatch(r"ubuntu-\d\d\.\d\d", str(job.get("runs-on", ""))):
            errors.append(f"workflow: {f}: job '{name}' must pin a runner image such as ubuntu-24.04")
        steps = job.get("steps", [])
        if not isinstance(steps, list):
            errors.append(f"workflow: {f}: job '{name}' steps must be a list")
            continue
        for i, step in enumerate(steps):
            if not _is_map(step):
                errors.append(f"workflow: {f}: job '{name}' step {i} must be a mapping")
                continue
            uses = step.get("uses")
            if uses is not None and not (isinstance(uses, str) and re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", uses)):
                errors.append(f"workflow: {f}: action is not pinned to a full commit SHA: {uses}")
            run = step.get("run", "")
            if not isinstance(run, str):
                errors.append(f"workflow: {f}: job '{name}' step {i} run must be text")
                continue
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


def public_addresses(host):
    """Resolve `host`; return the list of IPs or raise OSError if any is not globally routable."""
    infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    addrs = []
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise OSError("host resolves to a non-public address")
        addrs.append(str(ip))
    if not addrs:
        raise OSError("host did not resolve")
    return addrs


def host_resolves_publicly(host):
    try:
        public_addresses(host)
    except OSError as e:
        return f"dns/address check failed: {e}"
    return None


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connects to an address validated at connection time, closing the DNS rebinding gap.

    TLS still verifies the certificate against the original host name. Not used when an
    environment proxy is configured: the proxy then performs resolution (see proxy_detected).
    """

    def connect(self):
        ip = public_addresses(self.host)[0]
        sock = socket.create_connection((ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(PinnedHTTPSConnection, req, context=self._context)


def proxy_detected():
    """True when the environment routes HTTPS through a proxy (origin evidence is then not direct)."""
    return bool(urllib.request.getproxies().get("https") or urllib.request.getproxies().get("all"))


def fetch_once(url, timeout=REQUEST_TIMEOUT):
    """One GET without following redirects. Returns a response dict."""
    handlers = [NoRedirect()] if proxy_detected() else [NoRedirect(), PinnedHTTPSHandler()]
    opener = urllib.request.build_opener(*handlers)
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
        "x_robots_tag": headers.get_all("X-Robots-Tag") or [],
        "truncated": len(raw) > MAX_BYTES,
        "body": raw[:MAX_BYTES].decode("utf-8", "replace"),
    }


class PageInfo(HTMLParser):
    """Collects title, first H1, canonical links, robots meta and visible-content statistics."""

    SKIP = frozenset({"script", "style", "noscript", "template", "svg", "head", "nav", "header", "footer", "aside", "form", "button"})

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.h1 = "", ""
        self.canonicals, self.robots = [], []  # robots: list of (agent, content)
        self.words, self.headings, self.paragraphs = 0, 0, 0
        self.has_password_input = False
        self._open = None
        self._done = set()
        self._skip = 0
        self._in_head_title = False

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "title" and "title" not in self._done:
            self._open = "title"
        elif tag == "h1" and "h1" not in self._done:
            self._open = "h1"
        if tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.canonicals.append(a.get("href", ""))
        elif tag == "meta" and a.get("name", "").strip().lower() in ROBOTS_AGENTS:
            self.robots.append((a["name"].strip().lower(), a.get("content", "").lower()))
        elif tag == "input" and a.get("type", "").lower() == "password":
            self.has_password_input = True
        if tag in self.SKIP and tag not in ("head",):
            self._skip += 1
        if self._skip == 0:
            if tag in ("h2", "h3"):
                self.headings += 1
            elif tag in ("p", "li", "pre"):
                self.paragraphs += 1

    def handle_endtag(self, tag):
        if self._open == tag:
            self._done.add(tag)
            self._open = None
        if tag in self.SKIP and tag != "head" and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._open == "title":
            self.title += data
        elif self._open == "h1":
            self.h1 += data
        if self._skip == 0 and self._open != "title":
            self.words += len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'_-]*", data))


def _tokens(text):
    return {t for t in re.findall(r"[a-z0-9]{3,}", text.lower()) if t not in STOP_WORDS}


def _overlap(expected, actual):
    want = _tokens(expected)
    return 1.0 if not want else len(want & _tokens(actual)) / len(want)


def evaluate_robots(meta, headers):
    """Evaluate robots directives for the generic crawler, Googlebot and Bingbot.

    Returns (status, detail): "ok", "noindex" or "ambiguous". This checks page metadata and
    X-Robots-Tag headers only. It says nothing about robots.txt crawl permission or whether
    a search engine has actually indexed the page.
    """
    values = []  # (agent, directives)
    for agent, content in meta or []:
        if agent in ROBOTS_AGENTS:
            values.append((agent, content))
    if isinstance(headers, str):
        headers = [headers]
    for h in headers or []:
        if not isinstance(h, str):
            continue
        m = re.match(r"\s*([a-z0-9-]+)\s*:\s*(.*)$", h.lower())
        if m and not m.group(1).startswith("unavailable_after"):
            agent, content = m.group(1), m.group(2)
            if agent in ROBOTS_AGENTS:
                values.append((agent, content))
        else:
            values.append(("robots", h.lower()))
    deny, allow = False, False
    for _, content in values:
        tokens = {t.strip() for t in re.split(r"[,\s]+", content) if t.strip() and not t.startswith("unavailable_after")}
        if tokens & {"noindex", "none"}:
            deny = True
        if tokens & {"index", "all"}:
            allow = True
    if deny and allow:
        return "ambiguous", "conflicting index and noindex directives"
    if deny:
        return "noindex", "noindex or none directive"
    return "ok", ""


def _expectation(exp):
    if isinstance(exp, dict):
        return exp
    return {"kind": "lesson", "title": exp, "terms": None}


def classify(url, resp, expectation=None):
    """Classify a final (non-redirect) response. Pure function; no network.

    `expectation` is {"kind": "lesson"|"general", "title": str|None, "terms": [str]|None}; a plain
    string is treated as the expected lesson title. Result names beginning with NEEDS- mean the
    check could not decide and a person must look; they are never counted as verified or broken.
    """
    exp = _expectation(expectation)
    general = exp.get("kind") == "general"
    out = {
        "http_status": resp["status"], "content_type": resp.get("content_type"),
        "http_ok": False, "content_verified": False, "canonical_verified": False,
        "robots_ok": None, "title": None, "h1": None, "canonical": None,
        "robots_meta": None, "x_robots_tag": None, "content_words": None, "notes": [],
    }
    xrt = resp.get("x_robots_tag")
    xrt = [xrt] if isinstance(xrt, str) else [x for x in (xrt or []) if isinstance(x, str)]
    out["x_robots_tag"] = xrt
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
               robots_meta=[f"{a}: {c}" for a, c in info.robots] or None, content_words=info.words)
    head = f"{title} {h1}".lower()
    # Challenge phrases are only trusted in the title/H1, or in thin pages, so that lessons which
    # discuss CAPTCHAs, 403 responses or access control are not rejected.
    if any(p in head for p in CHALLENGE_PATTERNS) or (
        info.words < 150 and any(p in resp["body"][:6000].lower() for p in CHALLENGE_PATTERNS)
    ):
        return {**out, "result": "CHALLENGE"}
    if info.has_password_input and (LOGIN_RX.search(head) or info.words < 150):
        return {**out, "result": "LOGIN-PAGE"}
    expected_text = exp.get("title") or " ".join(exp.get("terms") or [])
    if SOFT_404_RX.search(head) and (not expected_text or _overlap(expected_text, head) < 0.5):
        return {**out, "result": "SOFT-404"}
    if info.words <= SHELL_MAX_WORDS:
        return {**out, "result": "EMPTY-SHELL", "notes": ["page has no meaningful visible content"]}
    robots_status, detail = evaluate_robots(info.robots, xrt)
    out["robots_ok"] = robots_status == "ok"
    if robots_status == "noindex":
        return {**out, "result": "NOINDEX", "notes": [detail]}
    if robots_status == "ambiguous":
        out["robots_ok"] = None
        return {**out, "result": "NEEDS-ROBOTS-REVIEW", "notes": [detail]}
    if len(info.canonicals) > 1:
        return {**out, "result": "CANONICAL-MULTIPLE"}
    if not info.canonicals:
        return {**out, "result": "CANONICAL-MISSING"}
    c, err = parse_url(info.canonicals[0], label="canonical")
    if err or c != url:
        return {**out, "result": "CANONICAL-MISMATCH", "notes": [err or "canonical differs from the catalogue URL"]}
    out["canonical_verified"] = True
    if general:
        terms = exp.get("terms") or ()
        if terms and not any(t in head for t in terms):
            return {**out, "result": "WRONG-CONTENT", "notes": ["page title/H1 does not match the expected page identity"]}
        minimum = GENERAL_MIN_WORDS
    else:
        if exp.get("title") and _overlap(exp["title"], head) < 0.5:
            return {**out, "result": "WRONG-CONTENT", "notes": ["page title/H1 share too few terms with the catalogue title"]}
        minimum = LESSON_MIN_WORDS
    if info.words < minimum or (not general and info.headings < 1 and info.paragraphs < 2):
        return {**out, "result": "NEEDS-CONTENT-REVIEW",
                "notes": [f"{info.words} visible words, {info.headings} section headings: below the lesson-content threshold"]}
    out["content_verified"] = True
    return {**out, "result": "VERIFIED"}


def verify_url(url, expectation=None, fetch=fetch_once, resolve=host_resolves_publicly, sleep=time.sleep,
               clock=time.monotonic):
    """Follow at most MAX_REDIRECTS validated redirects, then classify.

    `fetch`, `resolve`, `sleep` and `clock` are injectable. A per-URL deadline bounds retries.
    """
    start = clock()
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
            if clock() - start > URL_BUDGET_SECONDS:
                record["notes"].append("per-URL time budget exhausted")
                return record
            try:
                resp = fetch(current)
            except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as e:
                record["notes"].append(f"attempt {attempt + 1}: {e.__class__.__name__}")
                resp = None
                sleep(2 ** attempt)
                continue
            if resp["status"] in (429, 500, 502, 503, 504) and attempt < 2:
                sleep(2 ** attempt)
                continue
            break
        if resp is None:
            return record
        if resp["status"] in (301, 302, 303, 307, 308):
            location = resp.get("location")
            if not isinstance(location, str) or not location.strip():
                record["redirect_chain"].append({"from": current, "status": resp["status"], "to": None})
                record.update(result="REDIRECT-REJECTED", notes=record["notes"] + ["redirect without a Location header"])
                return record
            nxt, err = parse_url(urllib.parse.urljoin(current, location), label="redirect target")
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
        verdict = classify(current, resp, expectation)
        notes = record["notes"] + verdict.pop("notes")
        record.update(verdict)
        record["notes"] = notes
        record["final_url"] = current
        if record["redirect_chain"] and record["result"] == "VERIFIED":
            record["result"] = "REDIRECT"
        return record
    record.update(result="REDIRECT-LIMIT")
    return record


def expectations(data):
    """URL -> expectation for every page the catalogue links to."""
    exp = {data["site"]: {"kind": "general", "title": None, "terms": list(GENERAL_PAGE_TERMS["site"])}}
    for key in SITE_PAGE_KEYS:
        exp[data["site_pages"][key]] = {"kind": "general", "title": None, "terms": list(GENERAL_PAGE_TERMS[key])}
    for r in data["resources"]:
        exp[r["url"]] = {"kind": "lesson", "title": r["title"], "terms": None}
    return exp


SUMMARY_GROUPS = {
    "verified": ("VERIFIED",),
    "broken": ("BROKEN", "NON-HTML", "TOO-LARGE", "REJECTED"),
    "redirected": ("REDIRECT", "REDIRECT-LOOP", "REDIRECT-LIMIT", "REDIRECT-REJECTED"),
    "uncertain_or_blocked": ("UNKNOWN", "CHALLENGE", "LOGIN-PAGE", "NEEDS-CONTENT-REVIEW", "NEEDS-ROBOTS-REVIEW"),
    "content_mismatch": ("WRONG-CONTENT", "SOFT-404", "EMPTY-SHELL"),
    "canonical_mismatch": ("CANONICAL-MISSING", "CANONICAL-MULTIPLE", "CANONICAL-MISMATCH"),
    "robots_issue": ("NOINDEX", "NEEDS-ROBOTS-REVIEW"),
}


def summarize(results):
    summary = {"total": len(results)}
    for name, results_in in SUMMARY_GROUPS.items():
        summary[name] = sum(1 for r in results if r.get("result") in results_in)
    return summary


def build_evidence(data, results, source_commit, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    return {
        "evidence_schema": EVIDENCE_SCHEMA,
        "method": "origin-http",
        "validator": "validate_catalogue.py links",
        "validator_version": VALIDATOR_VERSION,
        "generated_at": now.isoformat(),
        "source_commit": source_commit,
        "catalogue_digest": catalogue_digest(data),
        "proxy_detected": proxy_detected(),
        "summary": summarize(results),
        "results": results,
    }


def run_links(data, json_out, workers=3, source_commit=None):
    exp = expectations(data)
    urls = all_urls(data)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(workers, 4))) as ex:
        results = list(ex.map(lambda u: verify_url(u, exp[u]), urls))
    for r in results:
        print(f"{r['result']:22} {r.get('http_status')}  {r['url']}  {'; '.join(r['notes'])}")
    evidence = build_evidence(data, results, source_commit or os.environ.get("GITHUB_SHA") or git_head())
    print("SUMMARY " + json.dumps(evidence["summary"]))
    if json_out:
        Path(json_out).write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return evidence["summary"]["verified"] == evidence["summary"]["total"]


# ------------------------------------------------------------ release gate
def _parse_time(value):
    try:
        t = dt.datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else None


def evidence_blockers(data, evidence, source_commit=None, now=None):
    """Consistency-check evidence against the current catalogue and revision.

    This catches stale, partial, mismatched or internally inconsistent evidence. It cannot prove
    who generated the file; use an artifact from a trusted GitHub Actions run on the exact commit.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    if not isinstance(evidence, dict):
        return ["evidence: must be a JSON object produced by the links command"]
    blockers = []
    if evidence.get("method") != "origin-http":
        blockers.append("evidence: method must be origin-http")
    if evidence.get("evidence_schema") != EVIDENCE_SCHEMA:
        blockers.append(f"evidence: evidence_schema must be {EVIDENCE_SCHEMA}")
    if evidence.get("validator_version") != VALIDATOR_VERSION:
        blockers.append(f"evidence: validator_version must be {VALIDATOR_VERSION}")
    if evidence.get("catalogue_digest") != catalogue_digest(data):
        blockers.append("evidence: catalogue_digest does not match the current catalogue")
    commit = source_commit or git_head()
    if not isinstance(evidence.get("source_commit"), str) or not re.fullmatch(r"[0-9a-f]{40}", evidence["source_commit"]):
        blockers.append("evidence: source_commit is missing or malformed")
    elif commit and evidence["source_commit"] != commit:
        blockers.append("evidence: source_commit does not match the revision being released")
    if evidence.get("proxy_detected") is not False:
        blockers.append("evidence: generated through a proxy or without proxy information; not direct origin evidence")
    generated = _parse_time(evidence.get("generated_at"))
    if generated is None:
        blockers.append("evidence: generated_at is missing or invalid")
    elif generated > now + dt.timedelta(minutes=5) or now - generated > dt.timedelta(days=EVIDENCE_MAX_AGE_DAYS):
        blockers.append("evidence: generated_at is stale or in the future")
    results = evidence.get("results")
    if not isinstance(results, list):
        return blockers + ["evidence: results must be a list"]
    exp = expectations(data)
    by_url, seen = {}, set()
    for i, r in enumerate(results):
        if not isinstance(r, dict) or not isinstance(r.get("url"), str):
            blockers.append(f"evidence: results[{i}] is malformed")
            continue
        if r["url"] in seen:
            blockers.append(f"evidence: duplicate record for {r['url']}")
        seen.add(r["url"])
        by_url[r["url"]] = r
    expected = set(all_urls(data))
    blockers += [f"evidence: no record for {u}" for u in sorted(expected - set(by_url))]
    blockers += [f"evidence: record for a URL that is not in the catalogue: {u}" for u in sorted(set(by_url) - expected)]
    for u in sorted(expected & set(by_url)):
        blockers += _record_blockers(u, by_url[u], exp[u], now)
    summary = evidence.get("summary")
    if isinstance(summary, dict) and summary.get("total") != len(results):
        blockers.append("evidence: summary does not match the number of records")
    return blockers


def _record_blockers(url, r, exp, now):
    """Re-derive every pass condition from raw fields instead of trusting the success flags."""
    def bad(why):
        return [f"evidence: {url}: {why}"]

    if r.get("method", "origin-http") != "origin-http":
        return bad("method is not origin-http")
    if r.get("result") != "VERIFIED":
        return bad(f"result is {r.get('result')!r}")
    if r.get("http_status") != 200 or r.get("http_ok") is not True:
        return bad("HTTP status is not 200")
    if r.get("canonical_verified") is not True or r.get("content_verified") is not True or r.get("robots_ok") is not True:
        return bad("canonical, content or robots verification flag is not true")
    if r.get("final_url") != url or r.get("redirect_chain") not in ([], None):
        return bad("unexpected redirect")
    t = _parse_time(r.get("fetched_at"))
    if t is None:
        return bad("fetched_at is missing or invalid")
    if t > now + dt.timedelta(minutes=5) or now - t > dt.timedelta(days=EVIDENCE_MAX_AGE_DAYS):
        return bad("fetched_at is stale or in the future")
    canonical, err = parse_url(r.get("canonical"), label="canonical")
    if err or canonical != url:
        return bad("recorded canonical does not equal the URL")
    meta = r.get("robots_meta") or []
    if not isinstance(meta, list) or not all(isinstance(m, str) for m in meta):
        return bad("robots_meta is malformed")
    pairs = [tuple(m.split(":", 1)) if ":" in m else ("robots", m) for m in meta]
    status, _ = evaluate_robots([(a.strip(), c.strip()) for a, c in pairs], r.get("x_robots_tag") or [])
    if status != "ok":
        return bad("recorded robots directives are not indexable")
    title, h1 = r.get("title"), r.get("h1")
    if not isinstance(title, str) or not isinstance(h1, str) or not (title.strip() or h1.strip()):
        return bad("title and H1 are missing")
    head = f"{title} {h1}".lower()
    words = r.get("content_words")
    if not isinstance(words, int) or isinstance(words, bool):
        return bad("content_words is missing")
    if exp["kind"] == "general":
        if not any(t in head for t in exp["terms"]) or words < GENERAL_MIN_WORDS:
            return bad("page identity or content size does not meet the expectation")
    elif _overlap(exp["title"], head) < 0.5 or words < LESSON_MIN_WORDS:
        return bad("page identity or content size does not meet the expectation")
    return []


def baseline_blockers(data, baseline):
    """Compare the catalogue with the independently approved baseline (not derived from the catalogue).

    The baseline is {"site_urls": [4 urls], "resources": [{"url": ..., "kind": ...}, ...]}. A deliberate
    catalogue change therefore requires an explicit baseline update.
    """
    if not isinstance(baseline, dict) or not isinstance(baseline.get("site_urls"), list) \
            or not isinstance(baseline.get("resources"), list):
        return ["baseline: expected an object with site_urls and resources lists"]
    blockers = []
    approved = {}
    for i, item in enumerate(baseline["resources"]):
        if not (isinstance(item, dict) and isinstance(item.get("url"), str) and item.get("kind") in KINDS):
            blockers.append(f"baseline: resources[{i}] is malformed")
            continue
        if item["url"] in approved:
            blockers.append(f"baseline: duplicate approved URL {item['url']}")
        approved[item["url"]] = item["kind"]
    current = {r["url"]: r["kind"] for r in data["resources"]}
    blockers += [f"baseline: approved resource missing from the catalogue: {u}" for u in sorted(set(approved) - set(current))]
    blockers += [f"baseline: catalogue resource not in the approved baseline: {u}" for u in sorted(set(current) - set(approved))]
    blockers += [f"baseline: kind changed for {u}" for u in sorted(set(approved) & set(current)) if approved[u] != current[u]]
    site_now = {data["site"], *(data["site_pages"][k] for k in SITE_PAGE_KEYS)}
    site_ok = {u for u in baseline["site_urls"] if isinstance(u, str)}
    if len(site_ok) != len(baseline["site_urls"]):
        blockers.append("baseline: site_urls must be unique text values")
    blockers += [f"baseline: approved website page missing: {u}" for u in sorted(site_ok - site_now)]
    blockers += [f"baseline: website page not in the approved baseline: {u}" for u in sorted(site_now - site_ok)]
    return blockers


# ------------------------------------------------------------ git identity
def classify_identities(entries, policy):
    """Classify commit identities against a private policy.

    entries: list of (short_hash, author_email, committer_email, historical) tuples.
    policy:  {"approved_emails": [...], "prohibited_emails": [...], "prohibited_domains": [...]}.
    Returns (findings, counts). Findings never include an email address.
    """
    approved = {e.lower() for e in policy.get("approved_emails", [])}
    prohibited_emails = {e.lower() for e in policy.get("prohibited_emails", [])}
    prohibited_domains = tuple("@" + d.lower().lstrip("@") for d in policy.get("prohibited_domains", []))
    tally = {"approved": 0, "community": 0, "prohibited": 0, "review": 0}
    findings = []
    for h, author, committer, historical in entries:
        kinds = set()
        for email in (author, committer):
            e = (email or "").lower()
            if e in prohibited_emails or (prohibited_domains and e.endswith(prohibited_domains)):
                kinds.add("prohibited")
            elif e in approved:
                kinds.add("approved")
            elif e.endswith("@users.noreply.github.com") and not historical:
                kinds.add("community")
            else:
                kinds.add("review")
        worst = next(k for k in ("prohibited", "review", "community", "approved") if k in kinds)
        tally[worst] += 1
        if worst == "prohibited":
            findings.append(f"history: commit {h} carries a prohibited identity (value withheld)")
        elif worst == "review":
            findings.append(f"history: commit {h} carries an unexpected identity requiring manual review (value withheld)")
    return findings, tally


def load_identity_policy(path):
    value, err = read_json(path, "identity policy")
    if err:
        return None, err
    if not isinstance(value, dict) or not all(
        isinstance(value.get(k, []), list) and all(isinstance(x, str) for x in value.get(k, []))
        for k in ("approved_emails", "prohibited_emails", "prohibited_domains")
    ) or not value.get("approved_emails"):
        return None, "identity policy: expected lists approved_emails (non-empty), prohibited_emails, prohibited_domains"
    if value.get("baseline_commit") is not None and not isinstance(value["baseline_commit"], str):
        return None, "identity policy: baseline_commit must be text"
    return value, None


def history_findings(root=ROOT, policy_path=None):
    """Redacted identity review of every reachable commit. Prints hashes and counts, never identities."""
    if not policy_path:
        return ["history: no identity policy supplied (--identity-policy), so absence of prohibited identities is not verified"], None
    policy, err = load_identity_policy(policy_path)
    if err:
        return [f"history: {err}"], None
    try:
        out = subprocess.run(["git", "log", "--all", "--format=%h|%ae|%ce"], cwd=root,
                             capture_output=True, text=True, check=True).stdout
        historical = set()
        if policy.get("baseline_commit"):
            historical = set(subprocess.run(["git", "rev-list", "--abbrev-commit", policy["baseline_commit"]], cwd=root,
                                            capture_output=True, text=True, check=True).stdout.split())
    except (OSError, subprocess.CalledProcessError):
        return ["history: git history could not be read"], None
    entries = [(h, a, c, h in historical) for h, a, c in
               (line.split("|") for line in out.splitlines() if line.count("|") == 2)]
    return classify_identities(entries, policy)


def release_blockers(files, data, evidence_path, baseline_path, root=ROOT, identity_policy=None,
                     with_history=True, source_commit=None):
    blockers = []
    for f in files:
        if f.endswith((".md", ".yml")):
            text = (root / f).read_text(encoding="utf-8")
            for marker in RELEASE_MARKERS:
                if marker in text:
                    blockers.append(f"{f}: unresolved marker '{marker.strip()}'")
    if "LICENSE" not in files:
        blockers.append("LICENSE: not tracked or present")
    for label, path, fn in (("evidence", evidence_path, lambda d: evidence_blockers(data, d, source_commit)),
                            ("baseline", baseline_path, lambda d: baseline_blockers(data, d))):
        if not path or not Path(path).exists():
            blockers.append(f"{label}: file not supplied (--{label})")
            continue
        value, err = read_json(path, label)
        blockers += [err] if err else fn(value)
    if with_history:
        findings, _ = history_findings(root, identity_policy)
        blockers += findings
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
    warnings = []
    errors += check_markdown(files) + check_site_links(files, data)
    errors += check_tree(files, strict=args.release, warnings=warnings)
    errors += check_license() + check_gitignore()
    if args.skip_yaml:
        yaml_state = "skipped"
    else:
        yaml_errors, yaml_state = check_yaml(files)
        errors += yaml_errors
    c = counts(data)
    print(f"public files: {len(files)} | entries: {c['total']} ({c['design']} designs, {c['foundation']} foundations, "
          f"{c['production']} architecture/production) | yaml: {yaml_state} | catalogue {catalogue_digest(data)[:19]}")
    for w in warnings:
        print("WARNING  " + w)
    for e in errors:
        print("ERROR  " + e)
    blockers = (release_blockers(files, data, args.evidence, args.baseline, identity_policy=args.identity_policy)
                if args.release else [])
    for b in blockers:
        print("BLOCKER  " + b)
    if args.release:
        print("MANUAL GATES (not verifiable by this script): owner editorial review, GitHub rendering, "
              "GitHub Actions run, repository settings, private vulnerability reporting enablement, "
              "GitHub-side retention of pre-rewrite commit objects")
    if errors:
        return 1
    note = f" ({len(warnings)} file(s) need maintainer review)" if warnings else ""
    if blockers:
        print("RESULT: checks passed, NOT READY FOR PUBLICATION")
        return 2
    print("RESULT: checks passed" + note)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["render", "check", "links", "history"])
    ap.add_argument("--data", default=str(DATA), help="catalogue JSON (default: data/resources.json)")
    ap.add_argument("--release", action="store_true", help="check: also report release blockers")
    ap.add_argument("--evidence", help="check --release: evidence JSON written by the links command")
    ap.add_argument("--baseline", help="check --release: approved baseline JSON (kept outside the public repository)")
    ap.add_argument("--identity-policy", help="check --release / history: private identity policy JSON (kept outside the public repository)")
    ap.add_argument("--json", help="links: write structured evidence to this file")
    ap.add_argument("--workers", type=int, default=3, help="links: concurrent requests (1-4)")
    ap.add_argument("--skip-yaml", action="store_true", help="check: skip YAML validation (local development only)")
    args = ap.parse_args(argv)

    if args.command == "history":
        findings, tally = history_findings(ROOT, args.identity_policy)
        if tally:
            print("history: " + json.dumps(tally))
        print("\n".join(findings) if findings else "history: no prohibited or unexpected identities found")
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
