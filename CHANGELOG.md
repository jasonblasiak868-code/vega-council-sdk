# Changelog

## 2026-10-20: fixes found by a source read

These were found by reading the source against its own documentation after release, not by the earlier test and review passes. Each fix has a regression test in
`tests/test_findings_20261020.py` that failed before the fix, and each fix was checked by undoing it and confirming a test fails. Behaviour that changed is listed under "Changed".

### Fixed
- **The builder changed its state before recording it.** A failed chain write could leave a design approved, a phase built, a decision taken or a phase marked DONE with no record. Each step now records first and changes state after.
- **Designs were hashed with `default=repr`**, so a design holding an object hashed differently on every run (the repr holds a memory address). A design is now hashed as plain data and an object inside it is refused.
- The builder's operations now run one at a time.
- The reference library's docstring promised that a personal read needs the matrix row to allow it; the gate (in `vega-harness-sdk`) never looked at the row. A row whose `personal_build` says no now blocks the read and the refusal is recorded.
