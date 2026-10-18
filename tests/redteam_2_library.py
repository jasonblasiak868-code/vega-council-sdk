"""RED TEAM 2 - the quarantined reference library: path tricks, licence gates, public builds, scrubbing, tainted output."""
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import fixture_council as fx  # noqa: E402
from vega_council import library as L  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.dag, self.t = fx.new_dag()
        self.root = self.t / "lib"
        (self.root / "refrepo" / "Tool").mkdir(parents=True)
        (self.root / "refrepo" / "Tool" / "prompt.txt").write_text("builder prompt text\nline two\n", encoding="utf-8")
        (self.root / "secretrepo").mkdir()
        (self.root / "secretrepo" / "x.txt").write_text("other repo", encoding="utf-8")
        (self.t / "outside.txt").write_text("outside the library", encoding="utf-8")
        self.lib = L.ReferenceLibrary(str(self.root), self.dag, fx.matrix())

    def kinds(self):
        return [e["kind"] for e in self.dag.content.entries()]


class A_Paths(Base):
    def test_traversal_and_absolute_paths_are_refused(self):
        for rel in ("..\\..\\outside.txt", "../../outside.txt", "Tool/../../../outside.txt", str(self.t / "outside.txt"), "C:\\Windows\\win.ini", "\\\\server\\share\\f", "..\\secretrepo\\x.txt", "", "\x00", "Tool\\..\\..\\secretrepo\\x.txt"):
            with self.assertRaises(L.LibraryRefused, msg=repr(rel)):
                self.lib.read("refrepo", rel)

    def test_repo_names_must_be_one_plain_component(self):
        for repo in ("..", "../secretrepo", "refrepo/..", "refrepo\\..\\secretrepo", "", "nul", "refrepo.", "a/b", None, 5):
            with self.assertRaises((L.LibraryRefused, Exception), msg=repr(repo)):
                self.lib.read(repo, "Tool/prompt.txt")

    def test_a_junction_out_of_the_repo_is_refused(self):
        link = self.root / "refrepo" / "escape"
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(self.t)], capture_output=True)
        if r.returncode != 0:
            self.skipTest("could not create a junction")
        with self.assertRaises(L.LibraryRefused):
            self.lib.read("refrepo", "escape/outside.txt")

    def test_directories_and_missing_files_are_not_files(self):
        for rel in ("Tool", "nothere.txt", "Tool/missing.txt"):
            with self.assertRaises(L.LibraryRefused):
                self.lib.read("refrepo", rel)

    def test_a_huge_file_is_refused_not_loaded(self):
        with open(self.root / "refrepo" / "big.bin", "wb") as fh:
            fh.truncate(L.FILE_CAP + 1)
        with self.assertRaises(L.LibraryRefused):
            self.lib.read("refrepo", "big.bin")

    def test_find_stays_inside_the_repo_and_lists_names_only(self):
        hits = self.lib.find("refrepo", "prompt")
        self.assertEqual([h["path"] for h in hits], ["Tool/prompt.txt"])
        self.assertEqual(set(hits[0]), {"path", "bytes"})
        self.assertEqual(self.lib.find("refrepo", "zzz-no-match"), [])
        with self.assertRaises(L.LibraryRefused):
            self.lib.find("nosuchrepo", "x")
        for q in ("", "  ", None):
            with self.assertRaises(L.LibraryRefused):
                self.lib.find("refrepo", q)


class B_Gates(Base):
    def test_public_builds_never_read_and_the_refusal_is_recorded(self):
        for build in ("public", "PUBLIC", "release", "", None, "personal ", "Personal"):
            with self.assertRaises(L.LibraryRefused, msg=repr(build)):
                self.lib.read("refrepo", "Tool/prompt.txt", build=build)
        self.assertIn("LIB_REFUSED", self.kinds())
        self.assertNotIn("LIB_READ", self.kinds())

    def test_an_unknown_repo_or_no_matrix_is_treated_as_no_licence(self):
        lib = L.ReferenceLibrary(str(self.root), self.dag, {})
        r = lib.read("refrepo", "Tool/prompt.txt")
        self.assertEqual(r["strictest_class"], "NO_LICENSE_FILE")
        self.assertTrue(r["tainted"])

    def test_the_matrix_class_is_reported_and_unknown_classes_fall_to_the_strict_side(self):
        lib = L.ReferenceLibrary(str(self.root), self.dag, fx.matrix(klass="MADE_UP"))
        self.assertEqual(lib.read("refrepo", "Tool/prompt.txt")["strictest_class"], "NO_LICENSE_FILE")

    def test_every_read_is_tainted_and_cannot_be_released(self):
        r = self.lib.read("refrepo", "Tool/prompt.txt")
        self.assertTrue(r["tainted"])
        self.assertFalse(self.lib.release_ok(r["provenance"])["released"])
        self.assertFalse(self.lib.release_ok({"library_sources": [], "tainted": True, "clean_room_attestation": "yes"})["released"])
        self.assertFalse(self.lib.release_ok({"tainted": False, "clean_room_attestation": "yes"})["released"])                 # an absent list is not an empty list
        self.assertFalse(self.lib.release_ok({"library_sources": [], "clean_room_attestation": True})["released"])             # a bare True is not an attestation
        self.assertTrue(self.lib.release_ok({"library_sources": [], "tainted": False, "clean_room_attestation": "written from a spec by someone who never opened the source"})["released"])

    def test_reads_are_recorded_with_hashes_only(self):
        self.lib.read("refrepo", "Tool/prompt.txt")
        raw = open(self.t / "c.jsonl", encoding="utf-8").read()
        self.assertIn("LIB_READ", raw)
        self.assertNotIn("builder prompt text", raw)
        self.assertNotIn("Tool/prompt.txt", raw)


class C_Scrubbing(Base):
    def test_credential_lines_and_control_characters_are_removed_from_the_excerpt(self):
        body = "fine line\napi_key = " + "Zx9" * 10 + "\nghp_" + "a" * 36 + "\nok\x1b]52;c;ZXZpbA==\x07 end\n"
        (self.root / "refrepo" / "Tool" / "leak.txt").write_text(body, encoding="utf-8")
        ex = self.lib.read("refrepo", "Tool/leak.txt")["excerpt"]
        self.assertNotIn("Zx9Zx9", ex)
        self.assertNotIn("ghp_", ex)
        self.assertNotIn("\x1b", ex)
        self.assertIn("fine line", ex)

    def test_long_files_are_cut_and_flagged(self):
        (self.root / "refrepo" / "Tool" / "long.txt").write_text("word " * 10000, encoding="utf-8")
        r = self.lib.read("refrepo", "Tool/long.txt")
        self.assertEqual(len(r["excerpt"]), L.READ_CAP)
        self.assertTrue(r["truncated"])

    def test_binary_junk_does_not_crash_or_leak_nul_bytes(self):
        (self.root / "refrepo" / "Tool" / "bin.dat").write_bytes(b"\x00\xff\xfe binary \x00 data")
        r = self.lib.read("refrepo", "Tool/bin.dat")
        self.assertNotIn("\x00", r["excerpt"])

    def test_a_missing_library_folder_is_refused(self):
        with self.assertRaises(L.LibraryRefused):
            L.ReferenceLibrary(str(self.t / "nope"), self.dag)


if __name__ == "__main__":
    unittest.main()
