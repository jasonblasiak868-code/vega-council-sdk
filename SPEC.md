# vega-council-sdk — Specification

Spec v1.0 — 2026-10-20 — describes the published reference implementation as tested. Where this document and the source disagree, the source wins.

**Contents:** [Purpose](#1-purpose-and-scope) · [Vocabulary](#2-vocabulary) · [Components](#3-components) · [Guarantees](#4-guarantees-and-non-guarantees) · [Failure modes](#5-failure-modes) · [Interfaces](#6-interfaces-and-diagnostics)

## 1. Purpose and scope

Specified: how several brains deliberate on one prompt, how a design becomes verified work under human control, and how a reference library is read under a licence gate. Out of scope: supplying brains or models, network access, legal advice, and any user interface.

## 2. Vocabulary

| Term | Meaning |
|---|---|
| Brain | A pair of functions, `answer(prompt)` and `review(prompt, others, own_label)`, plus an id, a family and a cost. |
| Family | A label for models that share an origin. One family counts as one voice per answer. |
| Stance | VALIDATE, CHALLENGE or EXTEND, given to another brain's anonymous answer. |
| Outcome | CONSENSUS, CONSENSUS_WITH_DISSENT, CONSENSUS_SEVERAL, SPLIT or INSUFFICIENT. |
| Design hash | SHA-256 of a canonical JSON dump of the design. The thing a human approves. |
| Phase | One unit of a plan with an id and dependencies. States: PLANNED, DECISION, BUILT, BUILT_REJECTED, DONE. |
| Taste decision | A choice reserved for a human: anything a build lists under `decisions`, plus any tag from a fixed taste word list. |
| Tainted | Marks anything derived from a library read. The release gate refuses it. |
| Commitment check | A caller-supplied function that must return exactly `True`. Anything else is a refusal. |

## 3. Components

### 3.1 `deliberation` — the council

**Role.** Run a prompt through equal brains with anonymous cross-review.

**Public interface.** `Brain`, `Council`, `CouncilRefused`, `STANCES`, `COSTS`, `MAX_BRAINS` (32).

**Behavior.**
- A council is 2 to 32 `Brain` objects with unique ids.
- Round 1: every enabled brain answers. A paid brain is asked only if `paid_ok(brain_id, prompt_sha256)` returns exactly `True`; otherwise it is skipped and a `COUNCIL_SKIP` record is written.
- Round 2: each answering brain sees the other answers under labels A, B, C and so on, shuffled by a seed taken from the prompt hash, and returns stances. Stances on its own answer, unknown targets and unknown stance words are dropped.
- Votes count per family. The bar is a majority of families, or one if there is only one family.
- Outcomes: several answers cleared with no challenge give CONSENSUS_SEVERAL; one clean answer gives CONSENSUS; a cleared but challenged answer gives CONSENSUS_WITH_DISSENT with the challenge notes hashed; nothing cleared gives SPLIT; fewer than two answers gives INSUFFICIENT.
- A brain that raises or answers in the wrong shape abstains.

**Invariants.** No self-votes. One voice per family. The chain record holds hashes and counts, never answers. A failed record write raises `CouncilRefused`.

### 3.2 `builder` — design first, human taste, independent verification

**Role.** Move from an approved design to verified phases.

**Public interface.** `Builder` with `propose_design`, `approve`, `plan`, `build`, `decide`, `verify`, `status`; `BuilderRefused`; `TASTE_WORDS`; `MAX_PHASES` (200).

**Behavior.**
- `propose_design` hashes a non-empty dict and clears any earlier approval.
- `approve(design_hash, human_ok)` needs the hash on the table and `human_ok(hash)` exactly `True`.
- `plan` refuses before approval, empty or oversized lists, duplicate ids, self-dependencies, unknown dependencies and cycles. It orders phases by dependency.
- `build` runs only a PLANNED or BUILT_REJECTED phase whose dependencies are DONE and whose design hash still matches. The step function returns `{artifact, decisions, tags}`. Any declared decision or taste tag pauses the phase in DECISION.
- `decide(phase, key, choice, human_ok)` needs `human_ok` over a hash of phase, key and choice to return exactly `True`.
- `verify` needs a BUILT phase, a verifier that differs from the builder in id and in family, and a checklist of items `{id, expected, coded, required, passed}` with exact booleans. At least one item must be required. A required item must be expected, coded and passed, or the phase becomes BUILT_REJECTED.

**Invariants.** A changed design needs a new approval. A phase is DONE only after independent verification. The record holds hashes and ids.

### 3.3 `library` — the quarantined reference library

**Role.** Let a personal build look things up under the licence gate.

**Public interface.** `ReferenceLibrary(root, dag, matrix)` with `find`, `read`, `release_ok`; `LibraryRefused`; caps `READ_CAP` 8000, `LIST_CAP` 2000, `FILE_CAP` 2 MiB.

**Behavior.**
- `find` returns file names and sizes only, skipping `.git`, and is always allowed.
- `read` runs only for `build="personal"` and only when the harness use gate allows the repo. Otherwise it records `LIB_REFUSED` and raises.
- Paths are resolved inside the repo folder after symlinks. Names or paths that leave it are refused.
- The excerpt is control-character stripped, credential-shaped lines are replaced, and the text is capped. The result is marked tainted and carries a provenance stub and a use card.
- `release_ok(provenance)` defers to the harness release gate.

## 4. Guarantees and non-guarantees

| Guarantee | Module | Evidence |
|---|---|---|
| A brain cannot vote for itself | `deliberation` | `tests/redteam_1_council_and_builder.py` |
| Copies of one family cannot stuff the ballot | `deliberation` | `tests/redteam_1_council_and_builder.py` |
| A paid brain is not asked without the commitment check | `deliberation` | `tests/redteam_1_council_and_builder.py` |
| Nothing builds before the exact design hash is approved | `builder` | `tests/test_council.py` |
| The builder cannot verify its own phase | `builder` | `tests/test_sharpened.py` |
| A public build never reads the library | `library` | `tests/redteam_2_library.py` |

| Non-guarantee | Reality |
|---|---|
| Agreement means correct | No. It means the brains agreed. |
| Taste detection is complete | No. It is a fixed word list plus declared decisions. |
| Licence outcomes are legal advice | No. The gate reads a matrix you supply. |

## 5. Failure modes

| Event | What happens |
|---|---|
| Fewer than two brains answer | Outcome INSUFFICIENT, recorded, no winner |
| A brain crashes or answers badly | It abstains |
| Paid brain without a valid commitment | Skipped and recorded |
| Record write refused | The action raises and does not proceed |
| Design changed after planning | `build` refuses until re-approved |
| Verifier is the builder or the same family | `verify` refuses |
| No required checklist item | `verify` refuses |
| Library read in a public build | Refused and recorded |
| Path escapes the repo folder | Refused |

## 6. Interfaces and diagnostics

No console script is published. Diagnostics are `Builder.status()`, the return values of `deliberate`, and the custody chain. Environment variables: none read by this package.
