"""Shared helpers for the council tests (not a test file)."""
import pathlib
import tempfile

from vega_council.deliberation import Brain
from vega_custody.dag.dag import Dag


def new_dag():
    t = pathlib.Path(tempfile.mkdtemp())
    return Dag([t / "c.jsonl"], [t / "l.jsonl"]), t


def brain(bid, family, answer, stance="VALIDATE", cost="free", note="fine"):
    def review(prompt, others, own):
        return [{"stance": stance, "target": l, "note": note} for l in others]
    return Brain(bid, family, (lambda p, a=answer: a) if isinstance(answer, str) else answer, review, cost)


def matrix(repo="refrepo", klass="STRONG_COPYLEFT", personal="read in quarantine; output is TAINTED"):
    return {repo: {"repo": repo, "license_class": klass, "personal_build": personal, "public_build": "clean-room only", "taint_if_used": True}}
