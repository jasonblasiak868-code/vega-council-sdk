"""builder.py - the build pipeline: design first, taste decisions belong to the human, and whoever built a phase never verifies it.

  Builder(dag)
    propose_design(design)         design: a plain dict (options, stack, screens). Returns its hash. Nothing builds until a human approves THAT hash.
    approve(design_hash, human_ok) human_ok(design_hash) must be exactly True (the caller wires it to a human-signed commitment check). The approved design is the contract: a build step
                                   carries the hash it was built under, and a changed design needs a new approval.
    plan(phases)                   phases: [{"id", "depends_on": [ids]}], run in dependency order; unknown ids, duplicates and cycles are refused.
    build(phase_id, brain, fn)     fn(phase_id) -> {"artifact": text, "decisions": [{"key", "options": [...]}]}. If the step hits a TASTE decision (anything it lists under `decisions`, or a
                                   taste word in the artifact's declared tags) the phase PAUSES: status DECISION, nothing is marked built until decide() is called with the human's choice.
    decide(phase_id, key, choice, human_ok)   the human picks; human_ok(phase_id+key+choice hash) must be exactly True.
    verify(phase_id, brain, checklist)        brain must differ from the builder of that phase AND be of a different family. checklist: [{"id", "expected", "coded", "required", "passed"}]:
                                   a required item must be expected (written before the build), coded and passed. Phase DONE only then.
    status()                       per phase state and COMPLETE only when every phase is DONE.
Everything is recorded as hashes and ids on the custody chain."""
import hashlib
import json
import re

from vega_custody.dag.dag import RecordRefused

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}")
TASTE_WORDS = frozenset(["dark", "light", "theme", "playful", "formal", "serif", "sans", "palette", "colour", "color", "tone", "mascot", "logo", "branding", "typography", "layout-style"])
MAX_PHASES = 200


class BuilderRefused(ValueError):
    pass


def _h(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=repr).encode()).hexdigest()


class Builder:
    def __init__(self, dag):
        self.dag = dag
        self.design_hash = None
        self.approved = False
        self.phases = {}
        self.order = []

    def _rec(self, kind, payload):
        try:
            self.dag.record(kind, payload)
        except RecordRefused as exc:
            raise BuilderRefused("could not record: %s" % exc)

    def propose_design(self, design):
        if not isinstance(design, dict) or not design:
            raise BuilderRefused("a design is a non-empty dict")
        self.design_hash, self.approved = _h(design), False
        self._rec("BUILD_DESIGN", {"design_sha256": self.design_hash})
        return self.design_hash

    def approve(self, design_hash, human_ok):
        if design_hash != self.design_hash or self.design_hash is None:
            raise BuilderRefused("that is not the design on the table")
        try:
            ok = callable(human_ok) and human_ok(design_hash) is True
        except Exception:
            ok = False
        if not ok:
            raise BuilderRefused("no human approval for this design")
        self.approved = True
        self._rec("BUILD_APPROVED", {"design_sha256": design_hash})

    def plan(self, phases):
        if not self.approved:
            raise BuilderRefused("plan after the design is approved")
        if not isinstance(phases, (list, tuple)) or not phases or len(phases) > MAX_PHASES:
            raise BuilderRefused("phases is a non-empty list")
        seen = {}
        for p in phases:
            if not isinstance(p, dict) or set(p) - {"id", "depends_on"} or not isinstance(p.get("id"), str) or not _ID.fullmatch(p["id"]) or p["id"] in seen:
                raise BuilderRefused("each phase is {id, depends_on} with a new plain id")
            deps = p.get("depends_on", [])
            if not isinstance(deps, (list, tuple)) or any(not isinstance(d, str) for d in deps):
                raise BuilderRefused("depends_on is a list of ids")
            seen[p["id"]] = list(deps)
        for pid, deps in seen.items():
            if pid in deps or any(d not in seen for d in deps):
                raise BuilderRefused("phase %s depends on itself or on an unknown phase" % pid)
        order, state = [], {}

        def visit(n):
            if state.get(n) == 1:
                raise BuilderRefused("the phases contain a cycle")
            if state.get(n) == 2:
                return
            state[n] = 1
            for d in seen[n]:
                visit(d)
            state[n] = 2
            order.append(n)
        for n in seen:
            visit(n)
        self.order = order
        self.phases = {n: {"deps": seen[n], "state": "PLANNED", "builder": None, "family": None, "design_sha256": self.design_hash, "decisions": {}, "pending": []} for n in order}
        self._rec("BUILD_PLAN", {"design_sha256": self.design_hash, "order": order})
        return list(order)

    def build(self, phase_id, brain_id, family, fn):
        ph = self.phases.get(phase_id)
        if ph is None:
            raise BuilderRefused("unknown phase")
        if ph["design_sha256"] != self.design_hash or not self.approved:
            raise BuilderRefused("the design changed since this phase was planned: approve it again")
        if any(self.phases[d]["state"] != "DONE" for d in ph["deps"]):
            raise BuilderRefused("a phase this one depends on is not done")
        if ph["state"] not in ("PLANNED", "BUILT_REJECTED"):
            raise BuilderRefused("phase is %s" % ph["state"])
        for v, w in ((brain_id, "brain_id"), (family, "family")):
            if not isinstance(v, str) or not _ID.fullmatch(v):
                raise BuilderRefused("%s must be a plain id" % w)
        if not callable(fn):
            raise BuilderRefused("fn is a function")
        try:
            out = fn(phase_id)
        except Exception as exc:
            self._rec("BUILD_FAIL", {"phase": phase_id, "brain": brain_id, "error": type(exc).__name__})
            return {"status": "FAILED", "why": type(exc).__name__}
        if not isinstance(out, dict) or not isinstance(out.get("artifact"), str):
            return {"status": "FAILED", "why": "a build returns {artifact: text, decisions: [...]}"}
        decisions = out.get("decisions", [])
        if not isinstance(decisions, (list, tuple)) or any(not isinstance(d, dict) or not isinstance(d.get("key"), str) or not isinstance(d.get("options"), (list, tuple)) for d in decisions):
            return {"status": "FAILED", "why": "decisions is a list of {key, options}"}
        tags = out.get("tags", [])
        taste = [str(t).casefold() for t in tags if isinstance(t, str) and str(t).casefold() in TASTE_WORDS] if isinstance(tags, (list, tuple)) else []
        pending = [d for d in decisions] + [{"key": "taste:%s" % t, "options": []} for t in taste]
        ph.update(builder=brain_id, family=family, artifact_sha256=hashlib.sha256(out["artifact"].encode()).hexdigest())
        if pending:
            ph["state"], ph["pending"] = "DECISION", [d["key"] for d in pending]
            self._rec("BUILD_PAUSED", {"phase": phase_id, "brain": brain_id, "decisions": ph["pending"], "artifact_sha256": ph["artifact_sha256"]})
            return {"status": "DECISION", "decisions": [{"key": d["key"], "options": list(d["options"])} for d in pending]}
        ph["state"] = "BUILT"
        self._rec("BUILD_STEP", {"phase": phase_id, "brain": brain_id, "design_sha256": self.design_hash, "artifact_sha256": ph["artifact_sha256"]})
        return {"status": "BUILT"}

    def decide(self, phase_id, key, choice, human_ok):
        ph = self.phases.get(phase_id)
        if ph is None or ph["state"] != "DECISION" or key not in ph["pending"]:
            raise BuilderRefused("no such pending decision")
        if not isinstance(choice, str) or not choice.strip():
            raise BuilderRefused("a choice is text")
        token = _h({"phase": phase_id, "key": key, "choice": choice})
        try:
            ok = callable(human_ok) and human_ok(token) is True
        except Exception:
            ok = False
        if not ok:
            raise BuilderRefused("the choice was not made by a human")
        ph["decisions"][key] = choice
        ph["pending"].remove(key)
        self._rec("BUILD_DECIDED", {"phase": phase_id, "decision_key": key, "choice_sha256": hashlib.sha256(choice.encode()).hexdigest()})
        if not ph["pending"]:
            ph["state"] = "BUILT"
        return ph["state"]

    def verify(self, phase_id, brain_id, family, checklist):
        ph = self.phases.get(phase_id)
        if ph is None or ph["state"] != "BUILT":
            raise BuilderRefused("only a BUILT phase can be verified")
        if brain_id == ph["builder"] or family == ph["family"]:
            raise BuilderRefused("the builder and the verifier must be different brains of different families")
        if not isinstance(checklist, (list, tuple)) or not checklist:
            raise BuilderRefused("a checklist is a non-empty list")
        bad, ids = [], set()
        for it in checklist:
            if not isinstance(it, dict) or set(it) != {"id", "expected", "coded", "required", "passed"} or not isinstance(it["id"], str) or it["id"] in ids:
                raise BuilderRefused("each checklist item is {id, expected, coded, required, passed} with a new id")
            ids.add(it["id"])
            if any(it[k] is not True and it[k] is not False for k in ("expected", "coded", "required", "passed")):
                raise BuilderRefused("expected, coded, required and passed are exactly true or false")
            if it["required"] and not (it["expected"] and it["coded"] and it["passed"]):
                bad.append(it["id"])
        if not any(it["required"] for it in checklist):
            raise BuilderRefused("a checklist with no required item proves nothing")
        ph["state"] = "DONE" if not bad else "BUILT_REJECTED"
        self._rec("BUILD_VERIFY", {"phase": phase_id, "verifier": brain_id, "state": ph["state"], "failed": sorted(bad)})
        return {"state": ph["state"], "failed": sorted(bad)}

    def status(self):
        states = {n: p["state"] for n, p in self.phases.items()}
        return {"phases": states, "complete": bool(states) and all(s == "DONE" for s in states.values()), "design_sha256": self.design_hash, "approved": self.approved}
