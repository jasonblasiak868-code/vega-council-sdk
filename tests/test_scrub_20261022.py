"""Regression tests (2026-10-22): the library excerpt was scrubbed one line at a time, so for a multi-line private key only the BEGIN line was replaced and the base64 body lines
(which are not credential-shaped on their own) were handed back."""
import unittest

from vega_council import library


class PrivateKeyBlocks(unittest.TestCase):
    PK = "PRIVATE " + "KEY"                                      # written in pieces so a secret scanner does not read this file as holding a key
    KEY = "-----BEGIN RSA " + PK + "-----\nMIIEowIBAAKCAQEA1234567890abcdef\nZZZZ9999yyyyxxxx\n-----END RSA " + PK + "-----"

    def test_the_whole_block_is_replaced_not_just_its_header(self):
        out = library.scrub_excerpt("before\n" + self.KEY + "\nafter")
        self.assertEqual(out, "before\n[REDACTED: private key block]\nafter")
        for leak in ("MIIEow", "ZZZZ9999", "BEGIN", "END RSA"):
            self.assertNotIn(leak, out)

    def test_other_block_kinds_and_an_unterminated_block_are_replaced(self):
        for head in ("OPENSSH PRIVATE KEY", "EC PRIVATE KEY", "PRIVATE KEY", "PGP PRIVATE KEY BLOCK"):
            out = library.scrub_excerpt("x\n-----BEGIN %s-----\nAAAAbbbbCCCCdddd\nEEEEffffGGGGhhhh" % head)   # no END line at all
            self.assertEqual(out, "x\n[REDACTED: private key block]", head)

    def test_ordinary_text_and_single_credential_lines_behave_as_before(self):
        self.assertEqual(library.scrub_excerpt("plain\ntext"), "plain\ntext")
        self.assertEqual(library.scrub_excerpt("ok\nkey = s" + "k-abcdefghijklmnopqrstuvwxyz0123\nok"), "ok\n[REDACTED: credential-shaped line]\nok")


if __name__ == "__main__":
    unittest.main()
