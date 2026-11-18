# Contributing

Thank you for helping keep this catalogue accurate and useful. By participating you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Scope

This repository is a curated directory that links to lessons and case studies on [SeeItFlow](https://seeitflow.com/). It does not host full lessons, case studies, diagrams or interview answers, and pull requests that add them will be closed.

Welcome contributions:

- Reports of broken, redirected or wrongly targeted links.
- Technical corrections to catalogue descriptions.
- Suggestions for additional resources that are relevant to system design and independently useful.
- Fixes to typos, formatting and accessibility of the Markdown files.

Not accepted: advertising, affiliate or tracking links, reciprocal-link requests, copied text, and bulk or automated submissions.

A catalogue change is not automatically a website content change. Website corrections may be triaged here but are handled separately.

## Report an issue

Use the [issue templates](https://github.com/seeitflow/system-design/issues/new/choose): broken link, technical correction or resource suggestion. Do not include personal or sensitive information. Report leaked credentials or malicious links privately as described in [SECURITY.md](SECURITY.md).

## Propose a resource or change

1. Open the resource and confirm that it works, is publicly accessible, and uses its canonical HTTPS URL without tracking parameters.
2. Write the description in your own words, in one specific sentence, describing what a learner will understand. Do not copy text from the destination.
3. Disclose any relationship with the resource's author or publisher.
4. Edit `data/resources.json`, the single source of truth for catalogue entries, then regenerate the README sections (see below). Do not edit the generated blocks in `README.md` by hand.
5. Run the local checks and open a pull request using the template.

Entries are accepted when they are relevant, accurate, non-duplicative, publicly available and verified. Maintainers may decline a suggestion without detailed explanation.

## Local checks

Python 3.9 or later is required for the validator, which uses only the standard library.

```bash
python3 scripts/validate_catalogue.py render    # regenerate README catalogue sections
python3 scripts/validate_catalogue.py check     # data, README, links to files, anchors, public tree
python3 scripts/validate_catalogue.py links     # live check of catalogue URLs (network required)
npx --yes markdownlint-cli2@0.24.1 "**/*.md"    # Markdown lint
```

Pull requests run `check` and the Markdown lint automatically. The live `links` check is run by maintainers, because a temporary network failure should not block a contribution.

## Data format

Each object in `data/resources.json` has `id`, `kind` (`foundation`, `design` or `production`), `group`, `title`, `url` and a text field: `description` for `foundation` and `production` entries, `challenges` for `design` entries. A design appears in exactly one group. URLs must be unique, HTTPS and on an approved host.
