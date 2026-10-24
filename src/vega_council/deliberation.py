"""deliberation.py - the council: equal brains, anonymous cross-review, and an outcome that never hides a dissent.

Round 1  every enabled brain answers the same prompt (no roles, no ranks).
Round 2  each brain sees the OTHER brains' answers under anonymous labels (A, B, C ... shuffled by a seed taken from the prompt) and returns a stance on each: VALIDATE, CHALLENGE or EXTEND, with a note.
Outcome  CONSENSUS (one answer validated by most and challenged by none), CONSENSUS_WITH_DISSENT (validated by most but challenged: the dissent is carried), SPLIT (no answer clears the bar:
         the answers go to a human), INSUFFICIENT (fewer than two answers).
Rules that keep it honest:
  - a brain's stance on its own answer is dropped; a brain cannot vote for itself
  - brains of one FAMILY count as one voice per answer, so running five copies of one model cannot stuff the ballot
  - a brain that crashes or answers in the wrong shape abstains
  - a PAID brain is asked only when paid_ok(brain_id, prompt_sha256) is exactly True (a human-signed commitment check the caller wires in); otherwise it is skipped and the skip is recorded
  - the SDK never opens a network connection: a brain is a function the caller supplies
The record on the chain holds hashes and counts, never the answers."""
import hashlib
import random
import re

from vega_custody.dag.dag import RecordRefused

STANCES = ("VALIDATE", "CHALLENGE", "EXTEND")
COSTS = ("free", "paid")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,63}")
MAX_BRAINS = 32


class CouncilRefused(ValueError):
    pass


def _h(t):
    return hashlib.sha256(t.encode("utf-8", "surrogatepass")).hexdigest()


class Brain:
    def __init__(self, brain_id, family, answer, review, cost="free"):
        for v, w in ((brain_id, "brain_id"), (family, "family")):
            if not isinstance(v, str) or not _ID.fullmatch(v):
                raise CouncilRefused("%s must be a plain id" % w)
        if not callable(answer) or not callable(review) or cost not in COSTS:
            raise CouncilRefused("a brain has answer(prompt) and review(prompt, others, own_label) functions and a cost in %s" % (COSTS,))
        self.id, self.family, self.answer, self.review, self.cost = brain_id, family, answer, review, cost


class Council:
    def __init__(self, brains, dag, paid_ok=None):
        if not isinstance(brains, (list, tuple)) or not 2 <= len(brains) <= MAX_BRAINS or any(not isinstance(b, Brain) for b in brains):
            raise CouncilRefused("a council is 2..%d Brain objects" % MAX_BRAINS)
        if len({b.id for b in brains}) != len(brains):
            raise CouncilRefused("two brains share an id")
        self.brains, self.dag, self.paid_ok = list(brains), dag, paid_ok

    def _rec(self, kind, payload):
        try:
            self.dag.record(kind, payload)
        except RecordRefused as exc:
            raise CouncilRefused("could not record: %s" % exc)

    def _paid(self, brain, ph):
        try:
            return callable(self.paid_ok) and self.paid_ok(brain.id, ph) is True
        except Exception:
            return False

    def deliberate(self, prompt, enabled=None):
        if not isinstance(prompt, str) or not prompt.strip():
            raise CouncilRefused("a prompt is non-empty text")
        ph = _h(prompt)
        pool = [b for b in self.brains if enabled is None or b.id in enabled]
        skipped = []
        round1 = {}
        for b in pool:
            if b.cost == "paid" and not self._paid(b, ph):
                skipped.append(b.id)
                self._rec("COUNCIL_SKIP", {"brain": b.id, "prompt_sha256": ph, "reason": "paid_without_commitment"})
                continue
            try:
                a = b.answer(prompt)
            except Exception:
                continue
            if isinstance(a, str) and a.strip():
                round1[b.id] = a
        if len(round1) < 2:
            self._rec("COUNCIL_RESULT", {"prompt_sha256": ph, "outcome": "INSUFFICIENT", "answered": len(round1)})
            return {"outcome": "INSUFFICIENT", "answers": len(round1), "skipped": skipped, "winner": None, "dissent": []}
        ids = sorted(round1)
        order = ids[:]
        random.Random(int(ph[:16], 16)).shuffle(order)
        label_of = {bid: chr(65 + i) for i, bid in enumerate(order)}
        by_label = {label_of[bid]: round1[bid] for bid in ids}
        votes = {l: {"VALIDATE": set(), "CHALLENGE": set(), "EXTEND": set()} for l in by_label}
        notes = {l: [] for l in by_label}
        fam = {b.id: b.family for b in pool}
        author_of = {l: bid for bid, l in label_of.items()}          # label -> the brain that wrote it (kept private; only the family is used)
        for b in pool:
            if b.id not in round1:
                continue
            own = label_of[b.id]
            others = {l: t for l, t in by_label.items() if l != own}
            try:
                env = b.review(prompt, dict(others), own)
            except Exception:
                continue
            if not isinstance(env, (list, tuple)):
                continue
            for s in env:
                if not isinstance(s, dict) or s.get("stance") not in STANCES or s.get("target") not in by_label or s.get("target") == own:
                    continue
                if fam[b.id] == fam[author_of[s["target"]]]:
                    continue                                       # a family's vote on its OWN family's answer does not count: same-family brains are biased toward each other
                votes[s["target"]][s["stance"]].add(fam[b.id])
                if s["stance"] == "CHALLENGE" and isinstance(s.get("note"), str):
                    notes[s["target"]].append(_h(s["note"]))
        families = {fam[bid] for bid in round1}
        need = {}                                                  # per answer: a majority of the OTHER families (the author's own family cannot vote on it)
        for l in by_label:
            others_n = len(families - {fam[author_of[l]]})
            need[l] = others_n // 2 + 1 if others_n else None      # nobody independent left to vote: this answer can never clear the bar
        scored = {l: (len(v["VALIDATE"]), len(v["CHALLENGE"])) for l, v in votes.items()}
        clear = [l for l, (v, c) in scored.items() if need[l] is not None and v >= need[l]]
        clean = [l for l in clear if scored[l][1] == 0]
        dirty = [l for l in clear if scored[l][1] > 0]
        winner, winners, dissent, outcome = None, [], [], "SPLIT"
        if len(clean) >= 2:                                        # several answers each cleared the bar and nobody challenged any: no single winner is invented
            outcome, winners = "CONSENSUS_SEVERAL", clean
            dissent = [n for l in dirty for n in notes[l]]
        elif len(clean) == 1:
            winner = clean[0]
            winners = [winner]
            outcome = "CONSENSUS" if not dirty else "CONSENSUS_WITH_DISSENT"
            dissent = [n for l in dirty for n in notes[l]]
        elif len(dirty) == 1:
            winner = dirty[0]
            winners = [winner]
            outcome, dissent = "CONSENSUS_WITH_DISSENT", notes[winner]
        rev = {v: k for k, v in label_of.items()}
        self._rec("COUNCIL_RESULT", {"prompt_sha256": ph, "outcome": outcome, "answered": len(round1), "families": len(families), "need_by_brain": {rev[l]: n for l, n in need.items()}, "winner_brain": rev[winner] if winner else None,
                                     "answer_sha256": {rev[l]: _h(t) for l, t in by_label.items()}, "validate": {rev[l]: s[0] for l, s in scored.items()}, "challenge": {rev[l]: s[1] for l, s in scored.items()},
                                     "dissent_sha256": dissent})
        return {"outcome": outcome, "winner": rev[winner] if winner else None, "winner_text": by_label[winner] if winner else None, "winners": sorted(rev[l] for l in winners),
                "answers": len(round1), "skipped": skipped, "dissent": dissent,
                "scores": {rev[l]: {"validate": s[0], "challenge": s[1]} for l, s in scored.items()}}
