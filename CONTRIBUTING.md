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

There are two separate lanes.

### Lane 1: first-party catalogue entries

The catalogue lists SeeItFlow lessons only, and the validator accepts only `seeitflow.com` URLs. To change or add an entry:

1. Open the lesson and confirm that it works, is publicly accessible, and uses its canonical HTTPS URL without tracking parameters.
2. Write the description in your own words, in one specific sentence, describing what a learner will understand. Do not copy text from the destination.
3. Disclose any relationship with the resource's author or publisher.
4. Edit `data/resources.json`, the single source of truth for catalogue entries, then run `render`. Do not edit the generated blocks in `README.md` by hand.
5. Run the local checks and open a pull request using the template.

### Lane 2: external references

Useful resources published elsewhere are welcome as suggestions through the [resource suggestion form](https://github.com/seeitflow/system-design/issues/new/choose). They are considered separately by the maintainers for a possible future editorial section. A suggestion is never added to the catalogue automatically, and pull requests that add external URLs to `data/resources.json` or extend the validator's approved hosts will be closed.

Entries are accepted when they are relevant, accurate, non-duplicative, publicly available and verified. Maintainers may decline a suggestion without detailed explanation.

## Local checks

Python 3.9 or later is required for the validator, which otherwise uses only the standard library. The YAML check needs PyYAML (`pip install PyYAML==6.0.2`). Markdown linting needs Node.js.

```bash
python3 scripts/validate_catalogue.py render    # regenerate README catalogue sections
python3 scripts/validate_catalogue.py check     # data, README generation, links, anchors, YAML, public tree
python3 -m unittest discover -s tests           # validator tests (no network needed)
npx --yes markdownlint-cli2@0.24.1 "**/*.md"    # Markdown lint
```

Pull requests run these checks automatically. Live URL verification is a separate, manually triggered workflow (`Verify live URLs`) run by maintainers, because a temporary network failure should not block a contribution. Contributors may also run `python3 scripts/validate_catalogue.py links` locally. It contacts only `seeitflow.com`.

## Data format

`data/resources.json` has `schema_version`, `site`, `site_pages` and `resources`. Each resource has `id` (kebab-case), `kind` (`foundation`, `design` or `production`), `group`, `title` and `url`, plus:

- `description` for `foundation` and `production` entries: one plain-text sentence of 10 to 32 words.
- `level` and `challenges` for `design` entries: the level SeeItFlow publishes for the design, and a list of 2 to 4 short engineering challenges without commas.

Text must not contain Markdown or HTML characters. IDs, titles and URLs must be unique. URLs must be HTTPS, on an approved host, with no port, credentials, query string or fragment.

## Licensing of contributions

<!-- LICENSE-PENDING: the repository license and the contribution terms are an owner decision -->
The repository license has not been announced yet. Please wait for it before contributing substantial changes.

## Website feedback

Feedback about the SeeItFlow website or its lessons is welcome on the [SeeItFlow contact page](https://seeitflow.com/contact). Issues here cover the catalogue only.
