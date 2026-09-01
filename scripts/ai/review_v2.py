"""Cross Review Protocol V2: JSON is the review, Markdown is a picture of it.

V1 asked a Markdown parser to tell structure from quoted content while both
used the same twelve labels. Five rounds of hardening produced five bypasses --
the last one defeated by the contract's own text -- because the ambiguity lives
in the format, not the parser: ``ID:`` opening a field and ``ID:`` inside
evidence are the same bytes. V2 deletes the question rather than answering it
again. A review is a JSON document; every value sits in a slot, so evidence may
carry contract labels, whole findings, fences, ``-->``, ``<!--`` or any Unicode
without touching the parse.

Two properties V1 could not express:

* A review is bound to the round and the tree it reviewed. ``run_id`` and
  ``review_tree`` are issued once per round and echoed by both reviewers, so a
  valid artefact from an earlier round cannot be counted, and a tree edited
  mid-round cannot be presented as reviewed.
* State is declared and validated, never inferred from prose. The reviewer
  names its verdict in a field with a closed set of values.

The workspace binding is :mod:`snapshot_v2`, not :func:`workspace_fingerprint`.
The fingerprint reconstructs the tree's identity from what ``git status`` and
``git ls-files --stage`` are willing to say, and any mechanism that makes git
silent about a path -- ``--skip-worktree``, ``--assume-unchanged``, an emptied
gitlink -- removes that path's bytes from the digest while leaving the digest
unmoved. Snapshot V2 stores the bytes instead of describing them, so the round
is bound to ``review_tree``: a git tree object built from the working tree with
every blob rewritten raw. :func:`workspace_fingerprint` is retained because it
is independently useful and heavily tested, but nothing in the round lifecycle
consults it any more.

The Markdown beside each review is rendered from the JSON and read by nobody:
:func:`read_review` never opens it.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4
import json
import os
import subprocess
import sys


if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from snapshot_v2 import (  # noqa: E402
    Snapshot,
    SnapshotError,
    capture,
    release,
    verify,
)


#: Bumped from 2 when the round's binding moved from ``workspace_fingerprint``
#: to Snapshot V2's ``review_tree``. A document naming the old field is not
#: merely missing a value, it was bound by a mechanism now known to be blind,
#: so it must fail loudly rather than validate against the new required slot.
SCHEMA_VERSION = 3

#: Slots of a finding. All required, all non-empty strings, no ordering rules:
#: a JSON object has no line order to get wrong.
FINDING_FIELDS = (
    "id",
    "severity",
    "category",
    "file",
    "lines",
    "claim",
    "evidence",
    "impact",
    "proposed_fix",
    "verification",
    "confidence",
)

ALLOWED_SEVERITIES = frozenset({"CRITICAL", "HIGH", "MEDIUM", "LOW"})

#: Artefacts of this system. They change on every run by construction, so
#: hashing them would make the fingerprint useless as an "unchanged" signal.
FINGERPRINT_EXCLUDED = (".claude/reviews/runtime/", ".codex-tmp/")

#: Stamped into every digest. Changing how the fingerprint is computed must
#: invalidate open rounds loudly rather than let two algorithms compare equal.
FINGERPRINT_VERSION = "fpv3"

#: A repository inside a repository inside a repository is already unusual;
#: beyond this the recursion is refused rather than followed.
MAX_REPO_DEPTH = 8

#: Synthetic status code for the side a rename vacated. Git reports a rename as
#: one entry naming the destination, so without this the source is invisible.
#: Not a code git can emit: the real ones are two characters from its own set.
RENAME_SOURCE = "<-"

#: The checks this platform requires before any verdict may count. Each must
#: appear exactly once and exit 0. The launcher runs them; nobody declares them.
REQUIRED_CHECKS = ("pytest", "ruff", "mypy")

#: Slots of an observed check.
CHECK_FIELDS = ("name", "command", "exit_code", "summary")

# Presupuesto por check. Generoso a proposito: la suite lleva marcador `slow`
# (pyproject.toml) y una corrida completa ronda los 19 min, asi que un limite
# corto convertiria reviews legitimos en fallos. Lo que cierra es el cuelgue
# indefinido, que atasca el protocolo entero (auditoria 2026-09-01, F-09).
CHECK_TIMEOUT_S = 2400          # 40 min

# Presupuesto del reviewer externo. Codex puede tardar, pero no eternamente.
CODEX_TIMEOUT_S = 1800          # 30 min

# Lineas de salida conservadas por check. Con una sola, el artefacto guardaba
# el codigo de salida pero no el motivo del fallo (F-13).
CHECK_SUMMARY_LINES = 20

# Presupuesto de las invocaciones a git. Cortas por naturaleza; si una se
# cuelga es que el repo tiene un lock muerto, y conviene saberlo ya.
GIT_TIMEOUT_S = 120


class Verdict(str, Enum):
    """What a reviewer may declare about its own run."""

    CLEAN = "CLEAN"
    FINDINGS = "FINDINGS"
    BLOCKED = "BLOCKED"


class VerificationStatus(str, Enum):
    """Whether the launcher's own runs of the required checks all succeeded."""

    PASSED = "PASSED"
    FAILED = "FAILED"


class ReviewState(str, Enum):
    """What the pipeline concludes. Only two of these are a review."""

    FINDINGS = "FINDINGS"
    CLEAN = "CLEAN"

    BLOCKED = "BLOCKED"
    MISSING = "MISSING"
    EMPTY = "EMPTY"
    NOT_EXECUTED = "NOT_EXECUTED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    RUN_MISMATCH = "RUN_MISMATCH"
    WORKSPACE_CHANGED = "WORKSPACE_CHANGED"


#: Only these may participate in consensus.
COUNTS_AS_REVIEW = frozenset({ReviewState.FINDINGS, ReviewState.CLEAN})


class FingerprintError(RuntimeError):
    """The workspace fingerprint could not be computed."""


@dataclass(frozen=True)
class Outcome:
    reviewer: str
    state: ReviewState
    detail: str = ""
    findings: tuple[dict[str, str], ...] = ()
    document: dict[str, Any] = field(default_factory=dict)

    @property
    def counts(self) -> bool:
        return self.state in COUNTS_AS_REVIEW

    @property
    def is_clean(self) -> bool:
        return self.state is ReviewState.CLEAN

    def summary(self) -> str:
        detail = f" -- {self.detail}" if self.detail else ""

        if self.state is ReviewState.FINDINGS:
            return f"{self.state.value} ({len(self.findings)}){detail}"

        return f"{self.state.value}{detail}"


# --- workspace fingerprint ---------------------------------------------------


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run git, converting every failure mode into FingerprintError.

    ``surrogateescape`` rather than ``replace``: git emits path bytes verbatim
    under ``-z``, and two different undecodable names must not collapse onto the
    same replacement character. Spawn failures are wrapped here because they do
    not produce a return code at all -- an over-long argv raised a raw
    ``OSError`` straight through the digest before (ADJ-V2-05).
    """
    try:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="surrogateescape",
            check=False,
            timeout=GIT_TIMEOUT_S,
        )
    # `TimeoutExpired` es `SubprocessError`, asi que un git colgado por un
    # `.git/*.lock` muerto se convierte en FingerprintError como cualquier otro
    # fallo, en vez de bloquear la ronda (F-09).
    except (OSError, subprocess.SubprocessError) as exc:
        raise FingerprintError(
            f"could not run 'git {' '.join(args)}' in {root}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def _git(root: Path, *args: str) -> str:
    result = _run_git(root, *args)

    if result.returncode != 0:
        raise FingerprintError(
            f"git {' '.join(args)} failed ({result.returncode}) in {root}: "
            f"{result.stderr.strip() or '[no stderr]'}"
        )

    return result.stdout


def is_excluded(path: str, exclusions: tuple[str, ...] = FINGERPRINT_EXCLUDED) -> bool:
    return any(path.startswith(prefix) for prefix in exclusions)


def changed_entries(
    root: Path, exclusions: tuple[str, ...] = FINGERPRINT_EXCLUDED
) -> list[tuple[str, str, str]]:
    """Every path git reports as changed, paired with its two-letter code.

    ``--untracked-files=all`` lists new files individually rather than naming
    their directory -- except at a repository boundary, where git cannot look
    inside and emits a single ``?? dir/`` entry. That collapse is why the code
    is returned alongside the path: the caller has to recurse there, and it also
    has to tell a deletion (legitimately absent) from a read failure (not).

    Ignored files never appear. This system's own artefacts are dropped
    explicitly so that editing .gitignore cannot smuggle them back in.
    """
    tokens = _git(
        root, "status", "--porcelain=v1", "-z", "--untracked-files=all"
    ).split("\0")

    entries: list[tuple[str, str, str]] = []
    position = 0

    while position < len(tokens):
        entry = tokens[position]
        position += 1

        if len(entry) < 4:
            continue

        code, path = entry[:2], entry[3:]
        source = ""

        if code[0] in ("R", "C"):
            # A rename or copy entry is followed by its source path.
            source = tokens[position] if position < len(tokens) else ""
            position += 1

        if not is_excluded(path, exclusions):
            entries.append((code, path, source))

        if code[0] == "R" and source and not is_excluded(source, exclusions):
            # The vacated side of a rename is its own event. Dropping it made
            # two different renames onto one destination collide (CLA-V3-01),
            # and -- when the destination was excluded -- made a tracked file
            # leave the reviewable tree with no trace at all (ADJ-V3-A). An
            # exclusion may hide our own artefacts; it may not erase the
            # departure of a path that was under review.
            entries.append((RENAME_SOURCE, source, path))

    return sorted(set(entries), key=lambda item: (item[1], item[0], item[2]))


def changed_paths(root: Path) -> list[str]:
    """The paths of :func:`changed_entries`, for callers that need only those."""
    return [path for _, path, _ in changed_entries(root)]


def index_digests(root: Path) -> dict[str, str]:
    """Stage, mode and object id of every entry in the index.

    No pathspec: the whole index comes back in one call, so argv does not grow
    with the number of changed paths. Passing them explicitly used to raise a
    raw ``OSError`` past 503 paths (ADJ-V2-05).

    The mode is part of the value because a staged ``100644 -> 100755`` or
    ``-> 120000`` flip keeps the same blob id, and dropping the mode made that
    change invisible (CLA-V2-03). Conflicted paths carry stages 1..3, all of
    which are recorded and sorted.
    """
    staged: dict[str, list[str]] = {}

    for entry in _git(root, "ls-files", "--stage", "-z").split("\0"):
        if not entry:
            continue

        meta, separator, path = entry.partition("\t")

        if not separator:
            continue

        fields = meta.split()

        if len(fields) >= 3:
            mode, oid, stage = fields[0], fields[1], fields[2]
            staged.setdefault(path, []).append(f"{stage}:{mode}:{oid}")

    return {path: "|".join(sorted(stages)) for path, stages in staged.items()}


def _record(path: str, index_part: str, worktree_part: str) -> str:
    """One length-prefixed record, so no path can forge a field boundary."""
    return f"{len(path)}:{path}\0{index_part}\0{worktree_part}\0"


def _is_repository(path: Path) -> bool:
    """True only when `path` is itself a repository root.

    ``rev-parse`` walks upwards, so any directory inside a repository answers
    yes to "are you in a repository". The question that matters here is whether
    this directory is a *boundary*, so its own toplevel must be itself.
    """
    result = _run_git(path, "rev-parse", "--show-toplevel")

    if result.returncode != 0:
        return False

    return os.path.realpath(result.stdout.strip()) == os.path.realpath(path)


def _head_of(root: Path) -> str:
    """HEAD, or a sentinel for a repository with no commits yet."""
    result = _run_git(root, "rev-parse", "--verify", "--quiet", "HEAD")

    return result.stdout.strip() if result.returncode == 0 else "unborn"


def _is_gitlink(index_entry: str) -> bool:
    """True when any stage of this index entry is a gitlink.

    Parsed rather than substring-matched: ``":160000:"`` also appears inside an
    object id often enough to matter, and a conflicted path can mix modes.
    """
    for stage in index_entry.split("|"):
        fields = stage.split(":")

        if len(fields) == 3 and fields[1] == "160000":
            return True

    return False


def _worktree_component(
    root: Path,
    code: str,
    path: str,
    index_entry: str,
    visited: set[str],
    depth: int,
    counterpart: str = "",
) -> str:
    """What the working tree holds at `path`, resolved by kind.

    Nothing here may hash to a constant unless the path genuinely holds nothing.
    The original code caught ``OSError`` from reading a directory and recorded
    ``"absent"``, which let a nested repository hide arbitrary content behind a
    fixed value (CLA-V2-02).
    """
    target = root / path

    if code == RENAME_SOURCE:
        # This path was vacated by a rename. Naming the destination keeps two
        # different renames apart even when both destinations are excluded.
        return "renamed-to:" + counterpart

    if _is_gitlink(index_entry):
        # A gitlink. The recorded commit is already in the index component; the
        # rest binds the submodule's actual local state. Every distinguishable
        # shape gets its own value -- returning a constant for "not a live
        # submodule" made a replacement file of any content hash alike, and
        # made replacement indistinguishable from removal (CLA-V3-02).
        if target.is_symlink():
            return "gitlink:symlink:" + sha256(
                os.readlink(target).encode("utf-8", "surrogateescape")
            ).hexdigest()

        if target.is_file():
            try:
                return "gitlink:file:" + sha256(target.read_bytes()).hexdigest()
            except OSError as exc:
                raise FingerprintError(
                    f"could not read {path!r} in {root}, which replaced a "
                    f"submodule: {type(exc).__name__}: {exc}"
                ) from exc

        if target.is_dir():
            if _is_repository(target):
                return "gitlink:repo:" + _repo_digest(target, (), visited, depth + 1)

            if not any(target.iterdir()):
                return "gitlink:empty-dir"

            raise FingerprintError(
                f"{path!r} holds a gitlink but is a non-empty directory that is "
                f"not a repository in {root}; refusing to represent it"
            )

        return "gitlink:absent"

    if path.endswith("/"):
        # git refused to look inside: a nested repository or an inner worktree.
        if not target.is_dir():
            raise FingerprintError(
                f"{path!r} is reported as a directory entry but is not a "
                f"directory on disk in {root}"
            )

        if not _is_repository(target):
            raise FingerprintError(
                f"git collapsed {path!r} into a single entry but it is not a "
                f"repository; this fingerprint cannot represent its contents"
            )

        return "tree:" + _repo_digest(target, (), visited, depth + 1)

    if target.is_symlink():
        return "symlink:" + sha256(
            os.readlink(target).encode("utf-8", "surrogateescape")
        ).hexdigest()

    if target.is_dir():
        if _is_repository(target):
            return "tree:" + _repo_digest(target, (), visited, depth + 1)

        raise FingerprintError(
            f"{path!r} is a directory that git listed as a single entry in "
            f"{root}; refusing to represent it as a constant"
        )

    try:
        return "file:" + sha256(target.read_bytes()).hexdigest()
    except FileNotFoundError:
        if "D" in code:
            return "absent"

        raise FingerprintError(
            f"{path!r} is missing in {root} but git reports it as {code!r}, "
            f"not a deletion"
        ) from None
    except OSError as exc:
        raise FingerprintError(
            f"could not read {path!r} in {root}: {type(exc).__name__}: {exc}"
        ) from exc


def _repo_digest(
    root: Path, exclusions: tuple[str, ...], visited: set[str], depth: int
) -> str:
    """A deterministic digest of one repository's reviewable state.

    The same primitives at every level -- HEAD, porcelain status, the staged
    index -- so a nested repository, an inner worktree and a submodule are all
    described the way the outer repository is, and each respects its own ignore
    rules because its own git reports it.
    """
    if depth > MAX_REPO_DEPTH:
        raise FingerprintError(
            f"repository nesting deeper than {MAX_REPO_DEPTH} at {root}"
        )

    key = os.path.realpath(root)

    if key in visited:
        # A worktree can point back at a tree already described. Recording the
        # identity keeps the digest finite and deterministic.
        return "visited:" + sha256(key.encode("utf-8", "surrogateescape")).hexdigest()

    visited.add(key)

    entries = changed_entries(root, exclusions)
    staged = index_digests(root)
    records = [
        _record(
            f"{code}\0{path}",
            "index=" + staged.get(path, "none"),
            "worktree="
            + _worktree_component(
                root, code, path, staged.get(path, ""), visited, depth, counterpart
            ),
        )
        for code, path, counterpart in entries
    ]

    payload = f"{FINGERPRINT_VERSION}\0head={_head_of(root)}\0" + "".join(
        sorted(records)
    )

    return sha256(payload.encode("utf-8", "surrogateescape")).hexdigest()


def workspace_fingerprint(root: Path) -> str:
    """A deterministic digest of the change under review.

    Four layers, because a reviewer sees all four. HEAD pins the base. The index
    pins what is staged, with stage, mode and object id -- ``git diff`` is the
    working tree *against the index*, so the diff a reviewer reads moves when
    the index moves. The working tree pins the bytes on disk. Nested
    repositories, inner worktrees and submodules are described recursively by
    the same three, so none of them can hide behind an opaque entry.

    Content and git metadata only: no timestamps, no inode data.
    """
    return _repo_digest(root, FINGERPRINT_EXCLUDED, set(), 0)


# --- the run manifest --------------------------------------------------------


@dataclass(frozen=True)
class Run:
    run_id: str
    snapshot: Snapshot
    started_utc: str

    @property
    def review_tree(self) -> str:
        """The value both reviewers echo: this round's operative tree identity."""
        return self.snapshot.review_tree

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "snapshot": self.snapshot.as_dict(),
            "started_utc": self.started_utc,
        }


def start_run(runtime: Path, root: Path) -> Run:
    """Phase 0: mint the identity every artefact of this round must carry.

    The snapshot is taken before any reviewer is dispatched, and published as
    ``refs/cross-review/<run_id>``, so the exact tree the reviewers read stays
    reachable and diffable for as long as the round is open.
    """
    run_id = str(uuid4())
    run = Run(
        run_id=run_id,
        snapshot=capture(root, run_id),
        started_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    manifest = runtime / "run.json"

    try:
        runtime.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(run.as_dict(), indent=2) + "\n", encoding="utf-8"
        )
    except OSError as exc:
        # Both writes land or neither does. capture() publishes the ref before
        # the manifest naming it exists, so a failed manifest write stranded
        # that ref: --reset cannot drop what no manifest names, and every retry
        # added another (CLA-V7-01b). Both rollbacks are best effort and
        # neither may replace the cause the caller needs to see.
        with suppress(SnapshotError, OSError):
            release(root, run_id)

        with suppress(OSError):
            manifest.unlink(missing_ok=True)

        raise SnapshotError(
            f"could not write the run manifest for {run_id}: {exc}"
        ) from exc

    return run


def end_run(runtime: Path, root: Path) -> None:
    """Drop the round's ref. Idempotent, and silent when no round is open."""
    run = load_run(runtime)

    if run is not None:
        release(root, run.run_id)


def load_run(runtime: Path) -> Run | None:
    path = runtime / "run.json"

    if not path.exists():
        return None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    if not isinstance(raw, dict):
        return None

    snapshot = raw.get("snapshot")

    if not isinstance(snapshot, dict):
        # A manifest from before the Snapshot V2 binding, or one hand-edited to
        # drop it. Either way it names a round whose tree identity cannot be
        # checked, and an uncheckable round is not one we agree to run.
        return None

    try:
        return Run(
            str(raw["run_id"]),
            Snapshot(
                str(snapshot["base_commit"]),
                str(snapshot["staged_tree"]),
                str(snapshot["review_tree"]),
                str(snapshot["review_commit"]),
            ),
            str(raw.get("started_utc", "")),
        )
    except KeyError:
        return None


def snapshot_state(root: Path, run: Run | None) -> tuple[bool, str]:
    """Is the tree on disk still the tree this round froze?

    Wraps :func:`snapshot_v2.verify` so that a repository which cannot be read
    at all blocks the round rather than raising through the gate.
    """
    if run is None:
        return False, "no run manifest: this round was never started"

    try:
        return verify(root, run.snapshot)
    except (SnapshotError, OSError) as exc:
        # OSError is defence in depth, not redundancy: snapshot_v2 promises to
        # raise SnapshotError, and CLA-V6-02 was that promise being broken on a
        # newly reachable path. The gate must fail closed whichever escapes.
        return False, f"cannot verify the snapshot: {exc}"


# --- schema validation -------------------------------------------------------


def _string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_finding(raw: Any, position: int) -> str:
    if not isinstance(raw, dict):
        return f"finding {position} is {type(raw).__name__}, expected an object"

    missing = [name for name in FINDING_FIELDS if name not in raw]

    if missing:
        return f"finding {position} is missing: {', '.join(missing)}"

    extra = [name for name in raw if name not in FINDING_FIELDS]

    if extra:
        return f"finding {position} has unknown field(s): {', '.join(sorted(extra))}"

    empty = [name for name in FINDING_FIELDS if not _string(raw[name])]

    if empty:
        return f"finding {position} has empty or non-string: {', '.join(empty)}"

    if raw["severity"] not in ALLOWED_SEVERITIES:
        return (
            f"finding {position} has severity {raw['severity']!r}; allowed: "
            f"{', '.join(sorted(ALLOWED_SEVERITIES))}"
        )

    return ""


def validate_document(raw: Any, reviewer: str, *, stamped: bool = True) -> str:
    """Check a review against the schema. Returns "" when valid.

    ``stamped`` distinguishes the two shapes. What the reviewer emits carries no
    verification block worth trusting, so only its optional ``notes`` is looked
    at; what the launcher stores must carry the observed checks.
    """
    if not isinstance(raw, dict):
        return f"review is {type(raw).__name__}, expected a JSON object"

    if raw.get("schema_version") != SCHEMA_VERSION:
        return (
            f"schema_version is {raw.get('schema_version')!r}, "
            f"expected {SCHEMA_VERSION}"
        )

    for name in ("run_id", "reviewer", "review_tree"):
        if not _string(raw.get(name)):
            return f"{name!r} must be a non-empty string"

    if stamped:
        error = validate_verification(raw.get("verification"))

        if error:
            return error
    elif "verification" in raw and not isinstance(raw["verification"], (dict, str)):
        return "'verification' must be an object or a string"

    if str(raw["reviewer"]).upper() != reviewer.upper():
        return f"review is attributed to {raw['reviewer']!r}, expected {reviewer!r}"

    result = raw.get("result")

    if not isinstance(result, dict):
        return "'result' must be an object"

    try:
        verdict = Verdict(result.get("verdict"))
    except ValueError:
        return (
            f"result.verdict is {result.get('verdict')!r}; allowed: "
            f"{', '.join(v.value for v in Verdict)}"
        )

    findings = result.get("findings")

    if not isinstance(findings, list):
        return "'result.findings' must be a list"

    for position, finding in enumerate(findings):
        error = validate_finding(finding, position)

        if error:
            return error

    if verdict is Verdict.FINDINGS and not findings:
        return "verdict FINDINGS requires at least one finding"

    if verdict is not Verdict.FINDINGS and findings:
        return f"verdict {verdict.value} requires an empty findings list"

    return ""


def check_commands(interpreter: str) -> tuple[tuple[str, list[str]], ...]:
    """The required checks, as argv the launcher runs itself."""
    return (
        ("pytest", [interpreter, "-m", "pytest", "-q"]),
        ("ruff", [interpreter, "-m", "ruff", "check", "src", "scripts", "tests"]),
        ("mypy", [interpreter, "-m", "mypy", "src"]),
    )


def run_checks(root: Path, interpreter: str) -> list[dict[str, Any]]:
    """Run the required checks and record what happened.

    This is the whole of requirement 6. V1 asked the reviewer to describe its
    verification and then tried to tell an honest description from a fabricated
    one by reading the prose -- which is undecidable, and produced ADJ-01. Here
    the launcher runs the commands, so ``exit_code`` is observed rather than
    claimed. A reviewer cannot promote a failed run by writing JSON, because
    what it writes in this block is discarded.
    """
    observed: list[dict[str, Any]] = []

    for name, argv in check_commands(interpreter):
        try:
            result = subprocess.run(
                argv,
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=CHECK_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            # Un check colgado no puede dejar la ronda abierta para siempre:
            # `check_reviews_v2.py --start` se niega a abrir una nueva mientras
            # no pueda cerrar la anterior, asi que el protocolo entero queda
            # atascado hasta intervencion manual (auditoria 2026-09-01, F-09).
            # Un timeout se registra como exit != 0, que es lo correcto: un
            # check que no termina NO es un check que pasa.
            observed.append({
                "name": name,
                "command": " ".join(argv),
                "exit_code": 124,          # convencion de `timeout(1)`
                "summary": f"[TIMEOUT tras {CHECK_TIMEOUT_S}s: el check no termino]",
            })
            continue
        # stderr se CONCATENA en vez de descartarse: `result.stdout or
        # result.stderr` perdia stderr siempre que hubiera algo en stdout, y
        # pytest escribe el fallo en stdout mientras que un crash del
        # interprete va a stderr. Se conservan las ultimas lineas, no una:
        # con una sola, el artefacto guardaba el codigo de salida pero no el
        # motivo, y habia que re-ejecutar para saber que se rompio (F-13).
        chunks = [c.strip() for c in (result.stdout, result.stderr) if c and c.strip()]
        output = "\n".join(chunks).splitlines()
        tail = [ln.strip() for ln in output[-CHECK_SUMMARY_LINES:]]

        observed.append(
            {
                "name": name,
                "command": " ".join(argv),
                "exit_code": result.returncode,
                "summary": "\n".join(tail) if tail else "[no output]",
            }
        )

    return observed


def validate_verification(raw: Any) -> str:
    """Check the stamped verification block. Returns "" when valid."""
    if not isinstance(raw, dict):
        return "'verification' must be an object"

    try:
        VerificationStatus(raw.get("status"))
    except ValueError:
        return (
            f"verification.status is {raw.get('status')!r}; allowed: "
            f"{', '.join(s.value for s in VerificationStatus)}"
        )

    checks = raw.get("checks")

    if not isinstance(checks, list) or not checks:
        return "'verification.checks' must be a non-empty list"

    for position, check in enumerate(checks):
        if not isinstance(check, dict):
            return f"check {position} is not an object"

        missing = [name for name in CHECK_FIELDS if name not in check]

        if missing:
            return f"check {position} is missing: {', '.join(missing)}"

        if not _string(check["name"]) or not _string(check["command"]):
            return f"check {position} has an empty name or command"

        if not isinstance(check["exit_code"], int) or isinstance(
            check["exit_code"], bool
        ):
            return f"check {position} has a non-integer exit_code"

        if not isinstance(check["summary"], str):
            return f"check {position} has a non-string summary"

    if "notes" in raw and not isinstance(raw["notes"], str):
        return "'verification.notes' must be a string when present"

    return ""


def required_checks_failure(verification: dict[str, Any]) -> str:
    """Why the required checks do not back a counting verdict. "" when they do."""
    checks = verification.get("checks", [])
    seen: dict[str, list[dict[str, Any]]] = {}

    for check in checks:
        seen.setdefault(str(check["name"]), []).append(check)

    for name in REQUIRED_CHECKS:
        found = seen.get(name, [])

        if not found:
            return f"required check {name!r} is missing"

        if len(found) > 1:
            return f"required check {name!r} appears {len(found)} times, expected once"

        if found[0]["exit_code"] != 0:
            return (
                f"required check {name!r} exited {found[0]['exit_code']}: "
                f"{found[0]['summary']}"
            )

    if VerificationStatus(verification["status"]) is not VerificationStatus.PASSED:
        return f"verification.status is {verification['status']}"

    return ""


def stamp_verification(
    checks: list[dict[str, Any]], notes: str
) -> dict[str, Any]:
    """Build the canonical verification block from observed results.

    ``notes`` is carried through verbatim and never read again: it is the one
    place the reviewer may say something in prose, and nothing depends on it.
    """
    passed = not required_checks_failure(
        {"status": VerificationStatus.PASSED.value, "checks": checks}
    )

    return {
        "status": (
            VerificationStatus.PASSED if passed else VerificationStatus.FAILED
        ).value,
        "checks": checks,
        "notes": notes,
    }


def derive_state(document: dict[str, Any], run: Run | None) -> tuple[ReviewState, str]:
    """Classify a validated document against the round it claims to belong to."""
    launcher = document.get("launcher")

    if not isinstance(launcher, dict):
        return ReviewState.NOT_EXECUTED, "no launcher attestation"

    if not launcher.get("launched") or launcher.get("exit_code") != 0:
        return ReviewState.EXECUTION_FAILED, str(
            launcher.get("failure") or f"exit_code={launcher.get('exit_code')!r}"
        )

    if run is not None:
        if document["run_id"] != run.run_id:
            return ReviewState.RUN_MISMATCH, (
                f"review belongs to run {document['run_id']}, "
                f"this round is {run.run_id}"
            )

        if document["review_tree"] != run.review_tree:
            return ReviewState.WORKSPACE_CHANGED, (
                "review carries a different review_tree than the round: "
                f"{document['review_tree']} != {run.review_tree}"
            )

    verdict = Verdict(document["result"]["verdict"])
    verification = document.get("verification")

    if not isinstance(verification, dict):
        return ReviewState.VERIFICATION_FAILED, "no stamped verification block"

    if verdict is Verdict.BLOCKED:
        return ReviewState.BLOCKED, str(verification.get("notes", ""))

    # No verdict counts unless the launcher's own runs of the required checks
    # all succeeded. Nothing here reads prose: `notes` is not consulted.
    failure = required_checks_failure(verification)

    if failure:
        return ReviewState.VERIFICATION_FAILED, failure

    if verdict is Verdict.CLEAN:
        return ReviewState.CLEAN, _checks_line(verification)

    return ReviewState.FINDINGS, ""


def _checks_line(verification: dict[str, Any]) -> str:
    return "; ".join(
        f"{check['name']} -> {check['summary']}"
        for check in verification.get("checks", [])
        if check["name"] in REQUIRED_CHECKS
    )


# --- storage -----------------------------------------------------------------


def review_path(runtime: Path, reviewer: str) -> Path:
    return runtime / f"{reviewer.lower()}.json"


def write_review(
    runtime: Path,
    reviewer: str,
    body: str,
    *,
    launched: bool,
    exit_code: int | None,
    command: str,
    duration_s: float,
    run: Run | None,
    checks: list[dict[str, Any]] | None = None,
    failure: str = "",
) -> Outcome:
    """Validate a reviewer's JSON, stamp what the launcher saw, and persist it.

    Only this function writes the ``launcher`` and ``verification`` blocks, so a
    document without them is by construction a review nobody ran. ``checks`` are
    the launcher's own observations; whatever the reviewer put in
    ``verification`` is discarded apart from its ``notes``.
    """
    launcher: dict[str, Any] = {
        "launched": launched,
        "exit_code": exit_code,
        "command": command,
        "duration_s": round(duration_s, 3),
        "recorded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    if failure:
        launcher["failure"] = failure

    document: dict[str, Any]
    state: ReviewState
    detail: str

    observed = list(checks or [])

    if not launched or exit_code != 0:
        document = _shell_document(reviewer, run, launcher, observed)
        state = ReviewState.EXECUTION_FAILED
        detail = failure or f"exit_code={exit_code!r}"
    else:
        parsed, error = parse_json(body)

        if not error:
            error = validate_document(parsed, reviewer, stamped=False)

        if error:
            document = _shell_document(reviewer, run, launcher, observed, raw=body)
            state, detail = ReviewState.SCHEMA_INVALID, error
        else:
            document = dict(parsed)
            document["launcher"] = launcher
            # The reviewer's own verification block is replaced, not merged:
            # only the launcher may say what ran. Its notes survive verbatim.
            document["verification"] = stamp_verification(
                observed, reviewer_notes(parsed.get("verification"))
            )
            state, detail = derive_state(document, run)

    document.setdefault("launcher", launcher)

    findings = tuple(
        document.get("result", {}).get("findings", [])
        if state is ReviewState.FINDINGS
        else ()
    )

    runtime.mkdir(parents=True, exist_ok=True)
    review_path(runtime, reviewer).write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    outcome = Outcome(reviewer.upper(), state, detail, findings, document)

    (runtime / f"{reviewer.lower()}.md").write_text(
        render_markdown(outcome), encoding="utf-8"
    )

    return outcome


def reviewer_notes(raw: Any) -> str:
    """The reviewer's optional prose. Carried, never interpreted."""
    if isinstance(raw, dict):
        return str(raw.get("notes", ""))

    return raw if isinstance(raw, str) else ""


def _shell_document(
    reviewer: str,
    run: Run | None,
    launcher: dict[str, Any],
    checks: list[dict[str, Any]],
    raw: str = "",
) -> dict[str, Any]:
    """A record for a run that produced no valid document."""
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run.run_id if run else "",
        "reviewer": reviewer.upper(),
        "review_tree": run.review_tree if run else "",
        "launcher": launcher,
        "result": {"verdict": Verdict.BLOCKED.value, "findings": []},
        "verification": {
            "status": VerificationStatus.FAILED.value,
            "checks": checks,
            "notes": "",
        },
        "raw_output": raw,
    }


def parse_json(text: str) -> tuple[dict[str, Any], str]:
    """Read the JSON document out of a reviewer's stdout.

    Reviewers wrap output in fences or trail a sentence after it. Recovering the
    object is a transport concern, not the semantic guessing V1 did: whatever is
    recovered must still satisfy the schema.
    """
    stripped = text.strip()

    if not stripped:
        return {}, "review body is empty"

    candidates = [stripped]

    if stripped.startswith("```"):
        inner = stripped.split("\n", 1)[-1]
        candidates.append(inner.rsplit("```", 1)[0])

    opened, closed = stripped.find("{"), stripped.rfind("}")

    if 0 <= opened < closed:
        candidates.append(stripped[opened : closed + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, dict):
            return parsed, ""

    return {}, "output is not a JSON object"


def read_review(runtime: Path, reviewer: str, run: Run | None) -> Outcome:
    """Classify a stored review. Reads the JSON only; the Markdown is a view."""
    name = reviewer.upper()
    path = review_path(runtime, reviewer)

    if not path.exists():
        return Outcome(name, ReviewState.MISSING, f"no file at {path}")

    text = path.read_text(encoding="utf-8", errors="replace")

    if not text.strip():
        return Outcome(name, ReviewState.EMPTY, f"{path} is empty")

    document, error = parse_json(text)

    if error:
        return Outcome(name, ReviewState.SCHEMA_INVALID, error)

    if "launcher" not in document:
        return Outcome(
            name,
            ReviewState.NOT_EXECUTED,
            "no launcher attestation: this file was not produced by a review run",
        )

    error = validate_document(document, name)
    launcher = document.get("launcher")

    # `launcher` is present but need not be an object: the key was checked
    # above, the type never was, so a document carrying `"launcher": "yes"`
    # plus any schema error used to raise AttributeError straight through the
    # gate instead of returning a state (CLA-V5-04). A non-object attestation
    # is no attestation, and derive_state below says so.
    if error and isinstance(launcher, dict) and launcher.get("exit_code") == 0:
        return Outcome(name, ReviewState.SCHEMA_INVALID, error, (), document)

    state, detail = derive_state(document, run)
    findings = tuple(
        document.get("result", {}).get("findings", [])
        if state is ReviewState.FINDINGS
        else ()
    )

    return Outcome(name, state, detail, findings, document)


# --- consensus ---------------------------------------------------------------


def consensus_available(
    outcomes: list[Outcome],
    run: Run | None,
    tree_ok: bool,
    tree_detail: str = "",
) -> tuple[bool, str]:
    """Both reviewers ran, on the same round, against the tree still on disk.

    ``tree_ok`` is the Snapshot V2 verdict produced by :func:`snapshot_state`.
    It is passed in rather than recomputed here so that no caller can quietly
    substitute a weaker notion of "unchanged" than the one the round was bound
    with -- which is exactly how the fingerprint era went wrong.
    """
    if run is None:
        return False, "no run manifest: this round was never started"

    absent = [o for o in outcomes if not o.counts]

    if absent:
        names = ", ".join(f"{o.reviewer} ({o.state.value})" for o in absent)

        return False, f"these reviewers did not produce a review: {names}"

    if len(outcomes) < 2:
        return False, "consensus needs two reviewers"

    ids = {str(o.document.get("run_id", "")) for o in outcomes}

    if ids != {run.run_id}:
        return False, f"reviews disagree on run_id: {sorted(ids)}"

    trees = {str(o.document.get("review_tree", "")) for o in outcomes}

    if trees != {run.review_tree}:
        return False, f"reviews disagree on the review_tree: {sorted(trees)}"

    if not tree_ok:
        return False, (
            "the working tree changed after the round started; the reviews "
            f"describe a state that no longer exists ({tree_detail})"
        )

    return True, ""


# --- human view --------------------------------------------------------------


def render_markdown(outcome: Outcome) -> str:
    """Render a review for a human. Nothing reads this back."""
    document = outcome.document
    launcher = document.get("launcher", {})
    verification = document.get("verification")

    if not isinstance(verification, dict):
        verification = {}

    lines = [
        f"# {outcome.reviewer} review -- {outcome.state.value}",
        "",
        "> Rendered from the JSON review. Editing this file changes nothing:",
        "> the JSON beside it is the review.",
        "",
        f"- run_id: `{document.get('run_id', '')}`",
        f"- review_tree: `{document.get('review_tree', '')}` (Snapshot V2)",
        f"- launched: `{launcher.get('launched')}`"
        f" exit_code: `{launcher.get('exit_code')}`"
        f" duration_s: `{launcher.get('duration_s')}`",
        f"- recorded_utc: `{launcher.get('recorded_utc', '')}`",
        "",
        "## Verification",
        "",
        f"status: `{verification.get('status', '')}` "
        "(observed by the launcher, not declared by the reviewer)",
        "",
    ]

    for check in verification.get("checks", []):
        lines.append(
            f"- `{check.get('name')}` exit `{check.get('exit_code')}` -- "
            f"`{check.get('command')}` -- {check.get('summary')}"
        )

    lines += [
        "",
        "### Reviewer notes (informational only)",
        "",
        str(verification.get("notes", "")) or "_none_",
        "",
        f"## Findings ({len(outcome.findings)})",
        "",
    ]

    for finding in outcome.findings:
        lines.append(f"### {finding['id']} -- {finding['severity']}")
        lines.append("")

        for name in FINDING_FIELDS:
            if name in ("id", "severity"):
                continue

            lines.append(f"**{name}**:")
            lines.append("")
            lines.append(str(finding[name]))
            lines.append("")

    if not outcome.findings:
        lines.append("_none_")
        lines.append("")

    return "\n".join(lines)
