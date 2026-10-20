# vega-council-sdk — Architecture

**Contents:** [Layer map](#where-it-sits) · [Components](#components) · [Deliberation workflow and its stops](#deliberation-workflow-and-where-it-fails-closed) · [Build workflow and its stops](#build-workflow-and-where-it-fails-closed) · [Library workflow](#library-workflow-and-where-it-fails-closed) · [Custom constraints](#custom-constraints)

## Where it sits

```mermaid
flowchart TB
    U[15 assemble: umbrella] --> C[14 deliberate: council - THIS REPO]
    C --> H[6 conduct: harness - use gate]
    C --> K[0 record: custody - chain and safe paths]
    H --> K
```

```
 15 assemble   vega-umbrella-sdk
>>> 14 deliberate vega-council-sdk   <-- THIS REPO
  6 conduct    vega-harness-sdk      (dependency)
  0 record     vega-custody-sdk      (dependency)
```

## Components

| Module | Concern | Uses |
|---|---|---|
| `deliberation` | Equal brains, anonymous review, dissent carried | custody `Dag.record` |
| `builder` | Approved design, human taste, independent verification | custody `Dag.record` |
| `library` | Gated reference reads, tainted provenance | custody `safepaths`, `Dag`, harness `use_gate` |

## Deliberation workflow and where it fails closed

```mermaid
flowchart TD
    S[deliberate prompt] --> V{prompt non-empty text}
    V -->|no| X1[CouncilRefused]
    V -->|yes| E[for each enabled brain]
    E --> P{paid brain}
    P -->|yes| PC{paid_ok returns exactly True}
    PC -->|no| SK[skip and record COUNCIL_SKIP]
    PC -->|yes| AN[ask the brain]
    P -->|no| AN
    AN --> OK{non-empty text answer}
    OK -->|crash or bad shape| AB[brain abstains]
    OK -->|yes| R1[round 1 answer kept]
    R1 --> CNT{two or more answers}
    CNT -->|no| IN[INSUFFICIENT recorded]
    CNT -->|yes| RV[anonymous review, drop self and unknown targets]
    RV --> TL[count one voice per family]
    TL --> OUT[outcome and dissent recorded as hashes]
    OUT --> W{record write accepted}
    W -->|no| X2[CouncilRefused]
```

| Stop point | Mechanism | Where |
|---|---|---|
| Bad prompt | raise | `Council.deliberate` |
| Paid brain without commitment | deny by default, skip, record | `Council._paid` |
| Bad brain output | abstain | `Council.deliberate` |
| Too few answers | INSUFFICIENT, no winner invented | `Council.deliberate` |
| Record refused | raise | `Council._rec` |

## Build workflow and where it fails closed

```mermaid
flowchart TD
    D[propose_design] --> A{human_ok returns exactly True for the hash}
    A -->|no| X1[BuilderRefused]
    A -->|yes| PL[plan: refuse cycles, duplicates, unknown ids]
    PL --> B{design hash unchanged and dependencies DONE}
    B -->|no| X2[BuilderRefused]
    B -->|yes| RUN[run step function]
    RUN --> F{returned the right shape}
    F -->|no| FAIL[status FAILED, recorded]
    F -->|yes| T{decisions or taste tags}
    T -->|yes| DEC[phase DECISION, build paused]
    DEC --> HD{human_ok over phase key choice}
    HD -->|no| X3[BuilderRefused]
    HD -->|yes| BU[BUILT]
    T -->|no| BU
    BU --> VF{verifier differs in id and family}
    VF -->|no| X4[BuilderRefused]
    VF -->|yes| CK{every required item expected, coded and passed}
    CK -->|no| RJ[BUILT_REJECTED]
    CK -->|yes| DONE[DONE]
```

| Stop point | Mechanism | Where |
|---|---|---|
| No human approval | raise | `Builder.approve` |
| Design changed | raise on build | `Builder.build` |
| Taste decision | pause until a human decides | `Builder.build`, `Builder.decide` |
| Self-verification | raise | `Builder.verify` |
| Required item fails | BUILT_REJECTED | `Builder.verify` |

## Library workflow and where it fails closed

```mermaid
flowchart TD
    R[read repo path build] --> G{build is personal and use gate allows}
    G -->|no| RF[record LIB_REFUSED and raise]
    G -->|yes| P{path stays inside the repo after symlinks}
    P -->|no| X[LibraryRefused]
    P -->|yes| RD[capped read, strip controls, redact credential lines]
    RD --> T[record LIB_READ, return tainted excerpt with provenance]
    T --> REL[release_ok refuses anything derived]
```

## Custom constraints

Extension points in the published code: the brain functions, `paid_ok`, `human_ok`, the checklist contents and the licence matrix passed to `ReferenceLibrary`. User-defined constraints may be STRICTER than the legal minimum for the applicable jurisdiction, never looser. Jurisdictional legal minimums are defined by the jurisdiction registry (vega-jurisdiction-sdk); a custom constraint that would drop below a registered minimum is rejected at the gate.
