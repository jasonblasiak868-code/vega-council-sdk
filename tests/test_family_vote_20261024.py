"""Regression tests (2026-10-24): a family's vote counted on answers written by its OWN family, so same-family brains could help approve each other's answers (and a council made
of one family could reach 'consensus' by itself). Now only the OTHER families vote on an answer, and the bar is a majority of those other families."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixture_council as fx  # noqa: E402
from vega_council import deliberation as D  # noqa: E402


def backs(*texts, stance="VALIDATE"):
    """A reviewer that takes the given stance on exactly the answers whose text is in `texts`, and says nothing about the rest."""
    def review(prompt, others, own):
        return [{"stance": stance, "target": label, "note": "n"} for label, text in others.items() if text in texts]
    return review


def run(brains):
    dag, _ = fx.new_dag()
    return D.Council(brains, dag).deliberate("q")


class OwnFamilyCannotVote(unittest.TestCase):
    def test_a_sibling_model_cannot_help_approve_its_own_familys_answer(self):
        # three families. 'a2' (same family as a1) and 'b' both back a1's answer. Before: {A, B} = 2 = the bar, so a1 won. Now only B counts, and the bar is 2 of {B, C}.
        out = run([D.Brain("a1", "A", lambda p: "ANS-A1", backs()), D.Brain("a2", "A", lambda p: "ANS-A2", backs("ANS-A1")),
                   D.Brain("b", "B", lambda p: "ANS-B", backs("ANS-A1")), D.Brain("c", "C", lambda p: "ANS-C", backs())])
        self.assertEqual(out["scores"]["a1"]["validate"], 1)
        self.assertNotIn("a1", out["winners"])
        self.assertEqual(out["outcome"], "SPLIT")

    def test_independent_families_still_decide(self):
        out = run([D.Brain("a1", "A", lambda p: "ANS-A1", backs()), D.Brain("a2", "A", lambda p: "ANS-A2", backs("ANS-A1")),
                   D.Brain("b", "B", lambda p: "ANS-B", backs("ANS-A1")), D.Brain("c", "C", lambda p: "ANS-C", backs("ANS-A1"))])
        self.assertEqual(out["scores"]["a1"]["validate"], 2)          # B and C; A's own vote is not counted
        self.assertEqual((out["outcome"], out["winner"]), ("CONSENSUS", "a1"))

    def test_a_council_of_one_family_cannot_reach_consensus_by_itself(self):
        out = run([D.Brain(n, "same", lambda p, n=n: "ANS-" + n, backs("ANS-x", "ANS-y", "ANS-z")) for n in ("x", "y", "z")])
        self.assertEqual((out["outcome"], out["winner"]), ("SPLIT", None))
        self.assertTrue(all(s["validate"] == 0 for s in out["scores"].values()))

    def test_two_families_one_independent_voter_is_enough_for_the_other_familys_answer(self):
        out = run([D.Brain("a1", "A", lambda p: "ANS-A1", backs()), D.Brain("b", "B", lambda p: "ANS-B", backs("ANS-A1"))])
        self.assertEqual((out["outcome"], out["winner"]), ("CONSENSUS", "a1"))


if __name__ == "__main__":
    unittest.main()
