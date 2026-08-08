"""RepoManager — the git-mediated executor behind the repo grants (mvp.md §2, envelope §3.4).

The work target lives under platform control at ``data/repos/<orgId>/<name>`` (``main``
protected by convention — nothing in the tool surface can commit to it directly):

- ``ensure_repo``: initialize the org's work target. By default the ``examples/target-app``
  fixture is copied in and ``git init``-ed with one initial commit on ``main`` (the CI spine).
  With a ``source`` (canopy.toml ``[repo] source`` — E8's "point the executor at a local clone
  of the Canopy repo"), the work target is ``git clone``-d from that local repository instead,
  history preserved; the source itself is only ever read.
- ``materialize_worktree`` (the ``code.repo.write`` executor, v1 git-mediated form): a fresh
  worktree on a ``canopy/<assignmentId>`` branch — local worktree + branch, no remotes.
- ``readonly_checkout`` (the ``repo.read`` executor): a detached worktree at a PR's head, for
  QA to run the suite against exactly what was submitted.
- ``assemble_pr``: the PullRequest artifact body ``{branch, baseSha, headSha, diff,
  testOutput}`` from the worktree state at ``finish`` (commits any uncommitted work first —
  the artifact must pin what actually exists).
- ``merge``: the governed-action executor — fast-forward-free merge of an approved branch
  into ``main``; the caller (the engine's gate resolution) verifies the ApprovalGate first
  (consented, then evidenced — invariant 9).

All operations shell out to the ``git`` CLI (present wherever the server runs; CI included)
with explicit ``cwd`` — no libgit dependency.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_FIXTURE = Path(__file__).resolve().parents[3] / "examples" / "target-app"


class RepoError(Exception):
    pass


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
        check=False,
    )
    if r.returncode != 0:
        raise RepoError(f"git {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip()


def _is_url(source) -> bool:
    return isinstance(source, str) and source.startswith(("https://", "http://"))


class RepoManager:
    def __init__(self, repos_root: Path, *, fixture: Path = _FIXTURE,
                 source: Path | None = None, source_resolver=None, auth_resolver=None):
        self.root = repos_root
        self.fixture = fixture
        self.source = source
        # F8 + connectors: org_id -> path | https URL | None. The org's connector instance
        # (builder-connectors.md §4) outranks the F8 binding outranks the boot-time [repo]
        # source; all absent means the fixture.
        self.source_resolver = source_resolver
        # org_id -> token | None, resolved at CALL time inside the control-plane process for
        # URL sources — never stored, never written into the clone's config.
        self.auth_resolver = auth_resolver

    def _source_for(self, org_id: str) -> Path | str | None:
        if self.source_resolver is not None:
            per_org = self.source_resolver(org_id)
            if per_org:
                return per_org if _is_url(per_org) else Path(per_org)
        return self.source

    def _authed_url(self, org_id: str, url: str) -> str:
        token = self.auth_resolver(org_id) if self.auth_resolver is not None else None
        if not token:
            return url
        scheme, _, rest = url.partition("://")
        return f"{scheme}://x-access-token:{token}@{rest}"

    def repo_path(self, org_id: str) -> Path:
        source = self._source_for(org_id)
        if source is None:
            name = "target-app"
        elif _is_url(source):
            name = source.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
        else:
            name = source.name
        return self.root / org_id / name

    def _worktrees_path(self, org_id: str) -> Path:
        return self.root / org_id / "worktrees"

    # ------------------------------------------------------------------ setup
    def ensure_repo(self, org_id: str) -> Path:
        """Initialize the org's work target (idempotent): clone the org's bound source (F8),
        else the global configured source, else copy the fixture in and git-init it."""
        source = self._source_for(org_id)
        repo = self.repo_path(org_id)
        if (repo / ".git").exists():
            return repo
        repo.parent.mkdir(parents=True, exist_ok=True)
        if _is_url(source):
            # Token rides the clone URL only for the duration of the command, then the
            # remote is re-pointed at the tokenless form — nothing secret lands on disk.
            _git(repo.parent, "clone", self._authed_url(org_id, source), str(repo))
            _git(repo, "remote", "set-url", "origin", source)
            try:
                _git(repo, "checkout", "main")
            except RepoError:
                shutil.rmtree(repo, ignore_errors=True)
                raise RepoError(
                    f"repo source {source} has no 'main' branch — the executors "
                    "protect and merge into 'main' (worktrees branch from it)"
                ) from None
        elif source is not None:
            if not (source / ".git").exists():
                raise RepoError(f"repo source is not a git repository: {source}")
            _git(repo.parent, "clone", str(source), str(repo))
            try:
                # DWIM-creates local main from origin/main when the source HEAD is elsewhere.
                _git(repo, "checkout", "main")
            except RepoError:
                # A half-initialized clone must not satisfy the idempotency check next call.
                shutil.rmtree(repo, ignore_errors=True)
                raise RepoError(
                    f"repo source {source} has no 'main' branch — the executors "
                    "protect and merge into 'main' (worktrees branch from it)"
                ) from None
        else:
            shutil.copytree(
                self.fixture, repo,
                ignore=shutil.ignore_patterns(".venv", "__pycache__", ".pytest_cache"),
            )
            _git(repo, "init", "-b", "main")
            _git(repo, "add", "-A")
        _git(repo, "config", "user.email", "canopy@localhost")
        _git(repo, "config", "user.name", "Canopy")
        if source is None:
            _git(repo, "commit", "-m", "target-app: initial fixture state")
        return repo

    # -------------------------------------------------------------- worktrees
    def materialize_worktree(self, org_id: str, assignment_id: str) -> dict:
        """The engineer's intake: a fresh ``canopy/<assignmentId>`` branch in its own worktree.
        Idempotent — re-intake (rework) returns the existing worktree."""
        repo = self.ensure_repo(org_id)
        branch = f"canopy/{assignment_id}"
        path = self._worktrees_path(org_id) / assignment_id
        if path.exists():
            return {"path": str(path), "branch": branch,
                    "baseSha": _git(path, "merge-base", "main", "HEAD")}
        path.parent.mkdir(parents=True, exist_ok=True)
        base_sha = _git(repo, "rev-parse", "main")
        _git(repo, "worktree", "add", "-b", branch, str(path), "main")
        return {"path": str(path), "branch": branch, "baseSha": base_sha}

    def readonly_checkout(self, org_id: str, ref: str, tag: str) -> dict:
        """QA's intake: a detached worktree at the submitted head. Read-only by convention and
        by grant (QA holds no ``code.repo.write``); the fs stays writable on the trusted-local
        tier — the honest wall arrives with the docker provider."""
        repo = self.ensure_repo(org_id)
        sha = _git(repo, "rev-parse", ref)
        path = self._worktrees_path(org_id) / f"ro-{tag}"
        if path.exists():
            _git(path, "checkout", "--detach", sha)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            _git(repo, "worktree", "add", "--detach", str(path), sha)
        return {"path": str(path), "sha": sha}

    # ------------------------------------------------------------ pr assembly
    def assemble_pr(self, org_id: str, assignment_id: str, *, test_output: str = "") -> dict:
        """The PullRequest artifact body from the worktree state at finish. Uncommitted work is
        committed first, so the artifact pins exactly what exists on disk."""
        path = self._worktrees_path(org_id) / assignment_id
        if not path.exists():
            raise RepoError(f"no worktree for assignment {assignment_id}")
        branch = f"canopy/{assignment_id}"
        if _git(path, "status", "--porcelain"):
            _git(path, "add", "-A")
            _git(path, "commit", "-m", f"work for {assignment_id}")
        base_sha = _git(path, "merge-base", "main", "HEAD")
        head_sha = _git(path, "rev-parse", "HEAD")
        diff = _git(path, "diff", f"{base_sha}...HEAD")
        return {"branch": branch, "baseSha": base_sha, "headSha": head_sha, "diff": diff,
                "testOutput": test_output}

    # ------------------------------------------------------------------ push
    def push_branch(self, org_id: str, branch: str) -> dict:
        """Push a canopy/* work branch to the org's remote source (the governed pr-create
        executor's first half — builder-connectors.md §5). Local-path sources are also valid
        push targets (the round-trip the operator does by hand today)."""
        if not branch.startswith("canopy/"):
            raise RepoError(f"refusing to push non-canopy branch {branch!r}")
        source = self._source_for(org_id)
        if source is None:
            raise RepoError("org has no repo source to push to")
        repo = self.ensure_repo(org_id)
        target = self._authed_url(org_id, source) if _is_url(source) else str(source)
        _git(repo, "push", target, f"{branch}:{branch}")
        return {"branch": branch, "headSha": _git(repo, "rev-parse", branch)}

    # ----------------------------------------------------------------- merge
    def merge(self, org_id: str, branch: str) -> dict:
        """The governed merge executor. The CALLER must have verified a resolved ApprovalGate
        for this action — this method only performs it (and refuses garbage branches)."""
        if not branch.startswith("canopy/"):
            raise RepoError(f"refusing to merge non-canopy branch {branch!r}")
        repo = self.ensure_repo(org_id)
        _git(repo, "merge", "--no-ff", branch, "-m", f"merge {branch} (governed)")
        return {"mergedSha": _git(repo, "rev-parse", "main"), "branch": branch}
