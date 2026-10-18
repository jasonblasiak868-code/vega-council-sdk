"""RED TEAM 1 - council and builder: ballot stuffing, self-votes, paid brains, skipped design approval, a builder that marks its own homework."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import fixture_council as fx  # noqa: E402
from vega_council import builder as B  # noqa: E402
from vega_council import deliberation as D  # noqa: E402


def council(brains, **kw):
    dag, t = fx.new_dag()
    return D.Council(brains, dag, **kw), dag, t


class A_Ballot(unittest.TestCase):
    def test_five_copies_of_one_family_are_one_voice(self):
        brains = [fx.brain("w%d" % i, "same", "WIDGET PLAN", "VALIDATE") for i in range(5)] + [fx.brain("x", "other1", "REAL PLAN", "CHALLENGE"), fx.brain("y", "other2", "THIRD PLAN", "CHALLENGE")]
        r, _, _ = council(brains)
        out = r.deliberate("q")
        # the five copies all validate everyone else's answers, but they are ONE family; 'need' is a majority of FAMILIES (3 families -> 2)
        self.assertEqual(out["scores"]["x"]["validate"], 1)
        self.assertNotIn("x", out["winners"])

    def test_a_brain_cannot_vote_for_its_own_answer(self):
        def selfish(prompt, others, own):
            return [{"stance": "VALIDATE", "target": own, "note": "mine is best"}]
        brains = [D.Brain("a", "f1", lambda p: "A", selfish), D.Brain("b", "f2", lambda p: "B", selfish), D.Brain("c", "f3", lambda p: "C", selfish)]
        out = council(brains)[0].deliberate("q")
        self.assertEqual(out["outcome"], "SPLIT")
        self.assertTrue(all(s["validate"] == 0 for s in out["scores"].values()))

    def test_wrong_shaped_reviews_abstain(self):
        bad = [None, "VALIDATE", {"stance": "VALIDATE"}, [None], [{"stance": "LOVE", "target": "A"}], [{"stance": "VALIDATE", "target": "Z"}], [{"stance": "VALIDATE", "target": 1}], 5, [[]]]
        for b in bad:
            brains = [D.Brain("a", "f1", lambda p: "A", lambda p, o, own, v=b: v), D.Brain("b", "f2", lambda p: "B", lambda p, o, own, v=b: v)]
            out = council(brains)[0].deliberate("q")
            self.assertEqual(out["outcome"], "SPLIT", repr(b))

    def test_a_crashing_brain_abstains_and_the_rest_still_decide(self):
        def boom(*a):
            raise RuntimeError("down")
        brains = [D.Brain("a", "f1", boom, boom), fx.brain("b", "f2", "same"), fx.brain("c", "f3", "same2"), fx.brain("d", "f4", "same3")]
        out = council(brains)[0].deliberate("q")
        self.assertEqual(out["answers"], 3)

    def test_empty_and_non_text_answers_do_not_count(self):
        brains = [D.Brain("a", "f1", lambda p: "", lambda p, o, s: []), D.Brain("b", "f2", lambda p: None, lambda p, o, s: []), D.Brain("c", "f3", lambda p: 5, lambda p, o, s: []),
                  fx.brain("d", "f4", "only real answer")]
        self.assertEqual(council(brains)[0].deliberate("q")["outcome"], "INSUFFICIENT")

    def test_labels_hide_authors_from_reviewers(self):
        seen = []

        def spy(prompt, others, own):
            seen.append((own, sorted(others)))
            return []
        brains = [D.Brain(n, "f" + n, lambda p, n=n: "answer " + n, spy) for n in ("alpha", "beta", "gamma")]
        council(brains)[0].deliberate("q")
        for own, others in seen:
            self.assertRegex(own, r"^[A-Z]$")
            self.assertTrue(all(len(o) == 1 for o in others))

    def test_the_label_order_follows_the_prompt_not_the_brain_order(self):
        def labels(brains):
            got = {}

            def spy(prompt, others, own, n):
                got[n] = own
                return []
            bs = [D.Brain(n, "f" + n, lambda p, n=n: "answer " + n, lambda p, o, s, n=n: spy(p, o, s, n)) for n in brains]
            council(bs)[0].deliberate("same prompt")
            return got
        self.assertEqual(labels(["a", "b", "c"]), labels(["c", "b", "a"]))

    def test_paid_brains_need_exactly_true(self):
        for answer in ("yes", 1, [1], None, "True"):
            brains = [fx.brain("a", "f1", "x"), fx.brain("b", "f2", "x"), fx.brain("p", "f3", "x", cost="paid")]
            out = council(brains, paid_ok=lambda b, h, v=answer: v)[0].deliberate("q")
            self.assertEqual(out["skipped"], ["p"], repr(answer))

    def test_a_crashing_commitment_check_means_no(self):
        def boom(b, h):
            raise RuntimeError("x")
        brains = [fx.brain("a", "f1", "x"), fx.brain("b", "f2", "x"), fx.brain("p", "f3", "x", cost="paid")]
        self.assertEqual(council(brains, paid_ok=boom)[0].deliberate("q")["skipped"], ["p"])

    def test_the_paid_brain_runs_when_the_commitment_holds(self):
        brains = [fx.brain("a", "f1", "x"), fx.brain("p", "f3", "x", cost="paid")]
        asked = []
        out = council(brains, paid_ok=lambda b, h: asked.append(b) or True)[0].deliberate("q")
        self.assertEqual((out["skipped"], asked), ([], ["p"]))

    def test_bad_councils_and_prompts(self):
        a = fx.brain("a", "f1", "x")
        dag, _ = fx.new_dag()
        for brains in ([], [a], [a, a], "ab", None, [a, "b"]):
            with self.assertRaises(D.CouncilRefused, msg=repr(brains)):
                D.Council(brains, dag)
        c = D.Council([a, fx.brain("b", "f2", "x")], dag)
        for p in ("", "   ", None, 5):
            with self.assertRaises(D.CouncilRefused):
                c.deliberate(p)
        for kw in (dict(brain_id="", family="f", answer=len, review=len), dict(brain_id="a b", family="f", answer=len, review=len), dict(brain_id="a", family="", answer=len, review=len),
                   dict(brain_id="a", family="f", answer=None, review=len), dict(brain_id="a", family="f", answer=len, review=None), dict(brain_id="a", family="f", answer=len, review=len, cost="gratis")):
            with self.assertRaises(D.CouncilRefused):
                D.Brain(**kw)

    def test_the_chain_holds_hashes_only(self):
        brains = [fx.brain("a", "f1", "TOP SECRET ANSWER"), fx.brain("b", "f2", "TOP SECRET OTHER")]
        r, dag, t = council(brains)
        r.deliberate("TOP SECRET PROMPT")
        self.assertNotIn("TOP SECRET", open(t / "c.jsonl", encoding="utf-8").read())

    def test_enabled_filter_limits_who_is_asked(self):
        asked = []
        brains = [D.Brain(n, "f" + n, lambda p, n=n: asked.append(n) or "x", lambda p, o, s: []) for n in ("a", "b", "c")]
        council(brains)[0].deliberate("q", enabled={"a", "b"})
        self.assertEqual(sorted(asked), ["a", "b"])


class B_Builder(unittest.TestCase):
    def setUp(self):
        self.dag, self.t = fx.new_dag()
        self.b = B.Builder(self.dag)
        self.h = self.b.propose_design({"stack": "x"})

    def ready(self, phases=None):
        self.b.approve(self.h, lambda d: True)
        self.b.plan(phases or [{"id": "p1"}, {"id": "p2", "depends_on": ["p1"]}])
        return self.b

    def chk(self, **over):
        item = {"id": "t1", "expected": True, "coded": True, "required": True, "passed": True}
        item.update(over)
        return [item]

    def test_approval_must_be_exactly_true_and_for_this_design(self):
        for ok in ("yes", 1, None, [1], "True"):
            with self.assertRaises(B.BuilderRefused, msg=repr(ok)):
                self.b.approve(self.h, lambda d, v=ok: v)
        with self.assertRaises(B.BuilderRefused):
            self.b.approve("00" * 32, lambda d: True)

        def boom(d):
            raise RuntimeError("signer down")
        with self.assertRaises(B.BuilderRefused):
            self.b.approve(self.h, boom)
        self.assertFalse(self.b.approved)

    def test_a_changed_design_voids_the_approval(self):
        self.ready()
        self.b.propose_design({"stack": "different"})
        with self.assertRaises(B.BuilderRefused):
            self.b.build("p1", "bb", "fa", lambda p: {"artifact": "x"})

    def test_plans_with_cycles_unknown_deps_or_duplicates_are_refused(self):
        self.b.approve(self.h, lambda d: True)
        for phases in ([{"id": "a", "depends_on": ["b"]}, {"id": "b", "depends_on": ["a"]}], [{"id": "a", "depends_on": ["a"]}], [{"id": "a", "depends_on": ["zzz"]}], [{"id": "a"}, {"id": "a"}],
                       [], None, [{"id": ""}], [{"id": "a b"}], [{"id": "a", "extra": 1}], [{"id": "a", "depends_on": "b"}], ["a"]):
            with self.assertRaises(B.BuilderRefused, msg=repr(phases)):
                self.b.plan(phases)

    def test_dependencies_run_first_and_a_phase_cannot_be_built_twice(self):
        self.ready()
        with self.assertRaises(B.BuilderRefused):
            self.b.build("p2", "bb", "fa", lambda p: {"artifact": "x"})
        self.b.build("p1", "bb", "fa", lambda p: {"artifact": "x"})
        with self.assertRaises(B.BuilderRefused):
            self.b.build("p1", "bb", "fa", lambda p: {"artifact": "x"})

    def test_a_taste_word_in_the_tags_pauses_even_without_a_declared_decision(self):
        self.ready()
        out = self.b.build("p1", "bb", "fa", lambda p: {"artifact": "ui", "tags": ["Dark", "api"]})
        self.assertEqual(out["status"], "DECISION")

    def test_a_phase_cannot_skip_a_pending_decision(self):
        self.ready()
        self.b.build("p1", "bb", "fa", lambda p: {"artifact": "ui", "decisions": [{"key": "theme", "options": ["a", "b"]}]})
        with self.assertRaises(B.BuilderRefused):
            self.b.verify("p1", "checker", "fb", self.chk())
        for ok in ("yes", 1, None):
            with self.assertRaises(B.BuilderRefused):
                self.b.decide("p1", "theme", "a", lambda t, v=ok: v)
        with self.assertRaises(B.BuilderRefused):
            self.b.decide("p1", "nope", "a", lambda t: True)
        with self.assertRaises(B.BuilderRefused):
            self.b.decide("p1", "theme", "  ", lambda t: True)
        self.assertEqual(self.b.status()["phases"]["p1"], "DECISION")

    def test_the_builder_and_family_may_not_verify(self):
        self.ready()
        self.b.build("p1", "bb", "fa", lambda p: {"artifact": "x"})
        for brain, fam in (("bb", "fz"), ("zz", "fa"), ("bb", "fa")):
            with self.assertRaises(B.BuilderRefused):
                self.b.verify("p1", brain, fam, self.chk())

    def test_an_unfinished_or_hollow_checklist_does_not_pass_a_phase(self):
        self.ready()
        self.b.build("p1", "bb", "fa", lambda p: {"artifact": "x"})
        for over in ({"passed": False}, {"coded": False}, {"expected": False}):
            self.assertEqual(self.b.verify("p1", "ck", "fb", self.chk(**over))["state"], "BUILT_REJECTED", repr(over))
            self.b.build("p1", "bb", "fa", lambda p: {"artifact": "x"})
        with self.assertRaises(B.BuilderRefused):
            self.b.verify("p1", "ck", "fb", self.chk(required=False))
        for bad in ([], None, "x", [{"id": "t"}], [{"id": "t", "expected": 1, "coded": True, "required": True, "passed": True}], self.chk() + self.chk()):
            with self.assertRaises(B.BuilderRefused, msg=repr(bad)):
                self.b.verify("p1", "ck", "fb", bad)

    def test_a_crashing_or_malformed_build_is_a_failure_not_a_pass(self):
        self.ready()

        def boom(p):
            raise RuntimeError("x")
        self.assertEqual(self.b.build("p1", "bb", "fa", boom)["status"], "FAILED")
        for out in (None, {}, {"artifact": 5}, {"artifact": "x", "decisions": "d"}, {"artifact": "x", "decisions": [{"key": 1, "options": []}]}, {"artifact": "x", "decisions": [{"key": "k"}]}):
            self.assertEqual(self.b.build("p1", "bb", "fa", lambda p, o=out: o)["status"], "FAILED", repr(out))
        self.assertEqual(self.b.status()["phases"]["p1"], "PLANNED")

    def test_complete_only_when_every_phase_is_done(self):
        self.ready()
        self.assertFalse(self.b.status()["complete"])
        self.b.build("p1", "bb", "fa", lambda p: {"artifact": "x"})
        self.b.verify("p1", "ck", "fb", self.chk())
        self.assertFalse(self.b.status()["complete"])

    def test_the_chain_holds_hashes_not_artifacts(self):
        self.ready()
        self.b.build("p1", "bb", "fa", lambda p: {"artifact": "PROPRIETARY SOURCE CODE"})
        self.assertNotIn("PROPRIETARY", open(self.t / "c.jsonl", encoding="utf-8").read())

    def test_design_must_be_a_real_dict(self):
        for bad in (None, {}, [], "x", 5):
            with self.assertRaises(B.BuilderRefused):
                self.b.propose_design(bad)


if __name__ == "__main__":
    unittest.main()
