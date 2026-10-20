# vega-council-sdk — Capabilities

The deep capability brief for this kit. Each row says what the capability is, why a policy or prompt-level approach cannot give it, where this code enforces it, which test shows it, and the honest limit.

| Capability | Why a policy or prompt cannot provide it | Enforced in | Test | Honest limit |
|---|---|---|---|---|
| Anonymous cross-review | A prompt cannot stop a model from recognizing its own style, but shuffled labels remove the names | `deliberation.Council.deliberate` | `tests/test_council.py` | Style can still leak through content |
| One voice per family | A rule against stuffing the ballot is only a request unless votes are counted by family | `deliberation.py` | `tests/redteam_1_council_and_builder.py` | Family labels are supplied by the caller |
| Dissent always carried | A summary prompt can drop disagreement; here the outcome type itself records it | `deliberation.py` | `tests/test_council.py` | Dissent is stored as hashes of notes |
| Paid brain gate | Budget rules in a prompt can be ignored; here the call is not made without an exact `True` | `Council._paid` | `tests/redteam_1_council_and_builder.py` | Only as strong as your commitment check |
| Design approval gate | A promise to "ask first" is not a lock; `plan` refuses before approval | `Builder.approve`, `Builder.plan` | `tests/test_council.py` | A careless human approval passes |
| Human taste decisions | A model can claim it asked; the phase pauses and cannot be marked built | `Builder.build`, `Builder.decide` | `tests/redteam_1_council_and_builder.py` | Taste words are a fixed list |
| Independent verification | Self-review is the model grading itself; id and family must differ | `Builder.verify` | `tests/test_sharpened.py`, `tests/mutations.py` | Family labels are caller-supplied |
| Proof written before the build | A required item must be expected, coded and passed | `Builder.verify` | `tests/test_sharpened.py` | The checklist is only as good as its author |
| Quarantined reference library | A licence note in a prompt does not stop a read; the gate does | `library.ReferenceLibrary.read` | `tests/redteam_2_library.py` | Policy, not legal advice |
| Tainted provenance | Without a mark, derived work is indistinguishable; the release gate refuses marked work | `library.release_ok` | `tests/redteam_2_library.py` | Marks follow only what passes through the stub |
| Hash-only audit record | A transcript can leak content; the chain stores hashes and counts | all modules | `tests/test_council.py` | Hashes prove content later, not now |

## Its part in the family loop

Records are written to the custody chain; lessons are distilled from them by the memory layer; the knowledge layer attaches origin and licence to facts; the reasoning layers forecast from that knowledge; this kit sits where several brains are asked and a build is checked, and its outcomes and phase states are what a human reads before deciding again. It does not hold authority. The human does.

See [README.md](README.md), [SPEC.md](SPEC.md) and [ARCHITECTURE.md](ARCHITECTURE.md).
