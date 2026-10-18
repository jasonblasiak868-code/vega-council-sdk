"""Tests added after the mutation check found fixes no earlier test noticed."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import fixture_council as fx  # noqa: E402
from vega_council import deliberation as D  # noqa: E402


class Sharpened(unittest.TestCase):
    def test_an_answer_backed_by_one_family_out_of_three_is_not_a_winner(self):
        dag, _ = fx.new_dag()

        def only_b(prompt, others, own):
            return [{"stance": "VALIDATE" if t == "answer-b" else "CHALLENGE", "target": l, "note": "n"} for l, t in others.items()]

        def challenger(prompt, others, own):
            return [{"stance": "CHALLENGE", "target": l, "note": "n"} for l in others]
        brains = [D.Brain("a", "f1", lambda p: "answer-a", only_b), D.Brain("b", "f2", lambda p: "answer-b", challenger), D.Brain("c", "f3", lambda p: "answer-c", challenger)]
        out = D.Council(brains, dag).deliberate("q")
        self.assertEqual(out["outcome"], "SPLIT")
        self.assertEqual(out["scores"]["b"]["validate"], 1)

    def test_labels_are_shuffled_by_the_prompt_not_assigned_in_name_order(self):
        seen = {}
        for i in range(25):
            got = {}

            def spy(prompt, others, own, n):
                got[n] = own
                return []
            bs = [D.Brain(n, "f" + n, lambda p, n=n: "answer " + n, lambda p, o, s, n=n: spy(p, o, s, n)) for n in ("alpha", "beta", "gamma")]
            dag, _ = fx.new_dag()
            D.Council(bs, dag).deliberate("prompt number %d" % i)
            seen.setdefault("alpha", set()).add(got["alpha"])
        self.assertGreaterEqual(len(seen["alpha"]), 2)


if __name__ == "__main__":
    unittest.main()
