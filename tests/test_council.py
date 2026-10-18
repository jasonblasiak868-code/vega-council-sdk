"""Functional tests for the council SDK."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import fixture_council as fx  # noqa: E402
from vega_council import builder as B  # noqa: E402
from vega_council import deliberation as D  # noqa: E402
from vega_council import library as L  # noqa: E402


class Deliberation(unittest.TestCase):
    def test_everyone_validates_gives_consensus(self):
        dag, _ = fx.new_dag()
        c = D.Council([fx.brain("a", "f1", "use plan one"), fx.brain("b", "f2", "use plan one"), fx.brain("c", "f3", "use plan one")], dag)
        r = c.deliberate("which plan?")
        self.assertEqual(r["outcome"], "CONSENSUS_SEVERAL")                 # three answers, all validated by the others: no single winner is invented
        self.assertEqual(r["winners"], ["a", "b", "c"])

    def test_a_challenge_is_carried_as_dissent(self):
        dag, _ = fx.new_dag()

        def review_b(prompt, others, own):
            return [{"stance": "CHALLENGE" if t == "answer-a" else "VALIDATE", "target": l, "note": "I disagree with a"} for l, t in others.items()]
        brains = [fx.brain("a", "f1", "answer-a"), D.Brain("b", "f2", lambda p: "answer-b", review_b), fx.brain("c", "f3", "answer-c"), fx.brain("d", "f4", "answer-d"), fx.brain("e", "f5", "answer-e")]
        r = D.Council(brains, dag).deliberate("q")
        self.assertIn(r["outcome"], ("CONSENSUS_SEVERAL", "CONSENSUS_WITH_DISSENT"))
        self.assertEqual(len(r["dissent"]), 1)
        self.assertEqual(r["scores"]["a"]["challenge"], 1)

    def test_nobody_validated_is_a_split(self):
        dag, _ = fx.new_dag()
        c = D.Council([fx.brain("a", "f1", "one", "CHALLENGE"), fx.brain("b", "f2", "two", "CHALLENGE"), fx.brain("c", "f3", "three", "CHALLENGE")], dag)
        self.assertEqual(c.deliberate("q")["outcome"], "SPLIT")

    def test_paid_brains_are_skipped_without_a_commitment(self):
        dag, _ = fx.new_dag()
        c = D.Council([fx.brain("a", "f1", "x"), fx.brain("b", "f2", "x"), fx.brain("p", "f3", "x", cost="paid")], dag)
        r = c.deliberate("q")
        self.assertEqual(r["skipped"], ["p"])

    def test_the_record_holds_hashes_not_answers(self):
        dag, t = fx.new_dag()
        D.Council([fx.brain("a", "f1", "SECRET ANSWER ONE"), fx.brain("b", "f2", "SECRET ANSWER TWO")], dag).deliberate("SECRET PROMPT")
        with open(t / "c.jsonl", encoding="utf-8") as fh:
            raw = fh.read()
        self.assertNotIn("SECRET", raw)


class Builder(unittest.TestCase):
    def ready(self):
        dag, t = fx.new_dag()
        b = B.Builder(dag)
        h = b.propose_design({"stack": "x", "screens": 3})
        b.approve(h, lambda d: True)
        b.plan([{"id": "p1"}, {"id": "p2", "depends_on": ["p1"]}])
        return b

    def test_happy_path(self):
        b = self.ready()
        self.assertEqual(b.build("p1", "builder1", "fa", lambda p: {"artifact": "code"})["status"], "BUILT")
        chk = [{"id": "t1", "expected": True, "coded": True, "required": True, "passed": True}]
        self.assertEqual(b.verify("p1", "checker", "fb", chk)["state"], "DONE")
        b.build("p2", "builder1", "fa", lambda p: {"artifact": "code2"})
        b.verify("p2", "checker", "fb", chk)
        self.assertTrue(b.status()["complete"])

    def test_nothing_plans_before_approval(self):
        dag, _ = fx.new_dag()
        b = B.Builder(dag)
        b.propose_design({"x": 1})
        with self.assertRaises(B.BuilderRefused):
            b.plan([{"id": "p1"}])

    def test_a_taste_decision_pauses_until_a_human_picks(self):
        b = self.ready()
        out = b.build("p1", "builder1", "fa", lambda p: {"artifact": "ui", "decisions": [{"key": "theme", "options": ["dark", "light"]}]})
        self.assertEqual(out["status"], "DECISION")
        with self.assertRaises(B.BuilderRefused):
            b.build("p2", "builder1", "fa", lambda p: {"artifact": "x"})
        b.decide("p1", "theme", "light", lambda t: True)
        self.assertEqual(b.status()["phases"]["p1"], "BUILT")

    def test_builder_never_verifies_their_own_phase(self):
        b = self.ready()
        b.build("p1", "builder1", "fa", lambda p: {"artifact": "code"})
        chk = [{"id": "t1", "expected": True, "coded": True, "required": True, "passed": True}]
        with self.assertRaises(B.BuilderRefused):
            b.verify("p1", "builder1", "fz", chk)
        with self.assertRaises(B.BuilderRefused):
            b.verify("p1", "other", "fa", chk)


class Library(unittest.TestCase):
    def setUp(self):
        self.dag, self.t = fx.new_dag()
        self.root = self.t / "lib"
        (self.root / "refrepo" / "Tool").mkdir(parents=True)
        (self.root / "refrepo" / "Tool" / "prompt.txt").write_text("You are an app builder.\nuse tools.\napi_key = " + "Zx9" * 10 + "\n")
        self.lib = L.ReferenceLibrary(str(self.root), self.dag, fx.matrix())

    def test_find_lists_names_only(self):
        self.assertEqual(self.lib.find("refrepo", "prompt")[0]["path"], "Tool/prompt.txt")

    def test_personal_read_is_marked_scrubbed_and_recorded(self):
        r = self.lib.read("refrepo", "Tool/prompt.txt")
        self.assertTrue(r["tainted"])
        self.assertIn("app builder", r["excerpt"])
        self.assertNotIn("Zx9Zx9", r["excerpt"])
        self.assertEqual(r["provenance"]["library_sources"], ["refrepo"])
        self.assertFalse(self.lib.release_ok(r["provenance"])["released"])

    def test_public_builds_never_read(self):
        with self.assertRaises(L.LibraryRefused):
            self.lib.read("refrepo", "Tool/prompt.txt", build="public")


if __name__ == "__main__":
    unittest.main()
