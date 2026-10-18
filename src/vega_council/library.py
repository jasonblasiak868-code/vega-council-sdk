"""library.py - the quarantined reference library: the builder can look things up at its fingertips, under the use gate, with every read marked.

The library holds third-party repos (for example a collection of published system prompts and tool definitions of app builders). Their licenses decide what may be done with what is read:
  - find() lists names only (file names and sizes): that is always allowed
  - read() hands back a capped, credential-scrubbed excerpt, but ONLY for a PERSONAL build, and the repo's matrix row must say a personal build is allowed; every read is recorded
    (repo, path hash, byte count, hashes only) and returns a provenance stub naming the library source. Anything derived from it is TAINTED and release_gate() refuses it
  - a PUBLIC build never reads: public work is clean-room (write a specification in your own words; someone who never opened the source writes the code)
  - an unknown repo, an unknown class, or no matrix is treated as NO_LICENSE_FILE (the strict side)
Paths are resolved inside the repo folder after symlinks; a name or path that leaves it is refused. Not legal advice."""
import hashlib
import os
import re

from vega_custody import safepaths as sp
from vega_custody.dag.dag import RecordRefused, contains_credential
from vega_harness import use_gate

READ_CAP = 8000
LIST_CAP = 2000
FILE_CAP = 2 * 1024 * 1024
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


class LibraryRefused(ValueError):
    pass


class ReferenceLibrary:
    def __init__(self, root, dag, matrix=None):
        self.root = os.path.realpath(root)
        if not os.path.isdir(self.root):
            raise LibraryRefused("the library folder does not exist")
        self.dag, self.matrix = dag, matrix

    def _repo_dir(self, repo):
        try:
            name = sp.safe_name(repo)
            return sp.contained(self.root, name)
        except sp.PathRefused as exc:
            raise LibraryRefused(str(exc))

    def find(self, repo, query, limit=50):
        base = self._repo_dir(repo)
        if not os.path.isdir(base):
            raise LibraryRefused("no such repo in the library")
        if not isinstance(query, str) or not query.strip():
            raise LibraryRefused("a query is non-empty text")
        q = query.casefold()
        hits, seen = [], 0
        for dirpath, dirnames, files in os.walk(base):
            dirnames[:] = [d for d in dirnames if d != ".git"]
            for f in files:
                seen += 1
                if seen > 200000:
                    break
                rel = os.path.relpath(os.path.join(dirpath, f), base)
                if q in rel.casefold():
                    try:
                        size = os.path.getsize(os.path.join(dirpath, f))
                    except OSError:
                        continue
                    hits.append({"path": rel.replace("\\", "/"), "bytes": size})
                    if len(hits) >= min(limit, LIST_CAP):
                        return hits
        return hits

    def read(self, repo, relpath, build="personal"):
        gate = use_gate.splice_gate([repo], build, self.matrix) if isinstance(repo, str) else {"allowed": False, "reason": "repo is a name"}
        if build != "personal" or not gate.get("allowed"):
            self._rec("LIB_REFUSED", {"repo": repo if isinstance(repo, str) and re.fullmatch(r"[A-Za-z0-9._ +@-]{1,200}", repo) else "?", "build": str(build)[:16], "reason": gate.get("reason", "build must be personal")[:200]})
            raise LibraryRefused(gate.get("reason") or "only a personal build may read the library")
        base = self._repo_dir(repo)
        if not isinstance(relpath, str) or not relpath or "\x00" in relpath:
            raise LibraryRefused("a path is non-empty text")
        try:
            target = sp.contained(base, *[p for p in re.split(r"[\\/]+", relpath) if p])
        except sp.PathRefused as exc:
            raise LibraryRefused(str(exc))
        if not os.path.isfile(target):
            raise LibraryRefused("not a file in that repo")
        try:
            raw = sp.read_capped(target, FILE_CAP)
        except sp.PathRefused as exc:
            raise LibraryRefused(str(exc))
        text = _CTRL.sub(" ", raw.decode("utf-8", "replace"))
        excerpt = "\n".join("[REDACTED: credential-shaped line]" if contains_credential(l) else l for l in text.split("\n"))[:READ_CAP]
        self._rec("LIB_READ", {"repo": repo, "path_sha256": hashlib.sha256(relpath.encode()).hexdigest(), "bytes": len(raw), "class": use_gate.klass(repo, self.matrix), "tainted": True})
        return {"excerpt": excerpt, "truncated": len(text) > READ_CAP, "tainted": True, "strictest_class": gate["strictest_class"], "condition": gate["condition"],
                "provenance": {"library_sources": [repo], "tainted": True}, "use_card": use_gate.use_card(repo, self.matrix)}

    def _rec(self, kind, payload):
        try:
            self.dag.record(kind, payload)
        except RecordRefused as exc:
            raise LibraryRefused("could not record: %s" % exc)

    @staticmethod
    def release_ok(provenance):
        return use_gate.release_gate(provenance)
