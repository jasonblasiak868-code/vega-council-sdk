# vega-council-sdk

![vega-council-sdk](assets/tile.svg)

Council and builder: anonymous equal-brains deliberation, design-first building with human taste decisions and independent verification, and a use-gated reference library.

> **Licensing.** Source-available, not open source. Free for personal use; free for registered small businesses (under US$1M revenue and valuation); everyone else needs a commercial license (see LICENSE; for a commercial license write to jasonblasiak.ai.mail@gmail.com). Patent pending. Draft licence text, not yet reviewed by an attorney.

Package: `vega_council` (src layout). Depends on: vega-custody-sdk, vega-harness-sdk.

## Modules

| Module | What it does |
|---|---|
| `deliberation` | Anonymous cross-review, families count once, no self-votes, paid brains only with a verified commitment, dissent carried, no invented winner. |
| `builder` | Design approved by a human before planning; taste decisions pause the build; builder and verifier differ; required proof items must be expected, coded and passed. |
| `library` | Quarantined reference library: names are always listable; reads are personal-build only, scrubbed, recorded and TAINTED; public builds never read. |

## What it does NOT do (read this)

- Consensus among brains is not truth.
- The library gate reads licence classes from the matrix; it is not legal advice, and an unlisted repo is treated as having no licence.

## Status

See STATUS.md. Tests: 54 tests in 4 files, all passing.  See SECURITY.md for the threat model.

## Run the tests

Put `src` of this repo and of the repos it depends on on PYTHONPATH, then run each file in `tests/`.
