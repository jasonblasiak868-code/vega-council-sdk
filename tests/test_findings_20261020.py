"""Regression tests (2026-10-20): the builder changed its state (design approved, phase built, verified DONE, decision taken) BEFORE recording the change, so a failed chain write left
the state changed with no record, and hashed designs with default=repr, so a design holding an object hashed differently on every run."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixture_council as fx  # noqa: E402
from vega_council import builder as B  # noqa: E402
from vega_custody.dag.dag import RecordRefused  # noqa: E402

YES = lambda h: True


class FailingDag:
    def __init__(self, real, ok_writes):
        self.real, self.left = real, ok_writes

    def record(self, kind, payload, parents=None):
        if self.left <= 0:
            raise RecordRefused("disk full")
        self.left -= 1
        return self.real.record(kind, payload, parents)


def builder(ok_writes):
    dag, _ = fx.new_dag()
    return B.Builder(FailingDag(dag, ok_writes))


def approved(ok_writes):
    b = builder(ok_writes)
    h = b.propose_design({"stack": "x"})
    b.approve(h, YES)
    return b, h


class RecordThenChange(unittest.TestCase):
    def test_a_design_that_cannot_be_recorded_is_not_on_the_table(self):
        b = builder(0)
        with self.assertRaises(B.BuilderRefused):
            b.propose_design({"stack": "x"})
        self.assertIsNone(b.design_hash)

    def test_an_approval_that_cannot_be_recorded_does_not_approve(self):
        b = builder(1)
        h = b.propose_design({"stack": "x"})
        with self.assertRaises(B.BuilderRefused):
            b.approve(h, YES)
        self.assertFalse(b.approved)

    def test_a_plan_that_cannot_be_recorded_plans_nothing(self):
        b, _ = approved(2)
        with self.assertRaises(B.BuilderRefused):
            b.plan([{"id": "p1"}])
        self.assertEqual((b.phases, b.order), ({}, []))

    def test_a_build_that_cannot_be_recorded_is_not_built(self):
        b, _ = approved(3)
        b.plan([{"id": "p1"}])
        b.dag.left = 0
        with self.assertRaises(B.BuilderRefused):
            b.build("p1", "brain-a", "fam-a", lambda pid: {"artifact": "code"})
        self.assertEqual(b.phases["p1"]["state"], "PLANNED")

    def test_a_decision_that_cannot_be_recorded_is_not_taken(self):
        b, _ = approved(3)
        b.plan([{"id": "p1"}])
        b.dag.left = 1
        out = b.build("p1", "brain-a", "fam-a", lambda pid: {"artifact": "code", "decisions": [{"key": "theme", "options": ["dark", "light"]}]})
        self.assertEqual(out["status"], "DECISION")
        b.dag.left = 0
        with self.assertRaises(B.BuilderRefused):
            b.decide("p1", "theme", "dark", YES)
        self.assertEqual((b.phases["p1"]["state"], b.phases["p1"]["pending"], b.phases["p1"]["decisions"]), ("DECISION", ["theme"], {}))

    def test_a_verification_that_cannot_be_recorded_does_not_finish_the_phase(self):
        b, _ = approved(3)
        b.plan([{"id": "p1"}])
        b.dag.left = 1
        b.build("p1", "brain-a", "fam-a", lambda pid: {"artifact": "code"})
        b.dag.left = 0
        with self.assertRaises(B.BuilderRefused):
            b.verify("p1", "brain-b", "fam-b", [{"id": "c1", "expected": True, "coded": True, "required": True, "passed": True}])
        self.assertEqual(b.phases["p1"]["state"], "BUILT")
        self.assertFalse(b.status()["complete"])


class DesignsAreHashedAsPlainData(unittest.TestCase):
    def test_a_design_holding_an_object_is_refused_not_hashed_by_its_address(self):
        dag, _ = fx.new_dag()
        b = B.Builder(dag)
        with self.assertRaises(B.BuilderRefused):
            b.propose_design({"stack": object()})

    def test_the_same_plain_design_always_has_the_same_hash(self):
        dag, _ = fx.new_dag()
        d = {"stack": "x", "screens": ["a", "b"]}
        self.assertEqual(B.Builder(dag).propose_design(d), B.Builder(dag).propose_design(dict(reversed(list(d.items())))))


class LibraryHonoursAMatrixNo(unittest.TestCase):
    """A matrix row whose personal_build says no forbids reading that repo, as the library's own docstring promises."""

    def setUp(self):
        import pathlib
        self.dag, self.t = fx.new_dag()
        self.root = self.t / "lib"
        (self.root / "refrepo").mkdir(parents=True)
        (self.root / "refrepo" / "p.txt").write_text("some text", encoding="utf-8")

    def test_a_row_that_forbids_a_personal_build_blocks_the_read_and_records_the_refusal(self):
        from vega_council import library as L
        m = fx.matrix(personal="no")
        lib = L.ReferenceLibrary(str(self.root), self.dag, m)
        with self.assertRaises(L.LibraryRefused) as cm:
            lib.read("refrepo", "p.txt")
        self.assertIn("forbids", str(cm.exception))
        self.assertIn("LIB_REFUSED", [e["kind"] for e in self.dag.content.entries()])

    def test_a_row_that_allows_quarantine_reading_still_reads(self):
        from vega_council import library as L
        lib = L.ReferenceLibrary(str(self.root), self.dag, fx.matrix())
        self.assertTrue(lib.read("refrepo", "p.txt")["tainted"])


if __name__ == "__main__":
    unittest.main()
