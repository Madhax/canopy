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


class RepoManager:
    def __init__(self, repos_root: Path, *, fixture: Path = _FIXTURE,
                 source: Path | None = None):
        self.root = repos_root
        self.fixture = fixture
        self.source = source
        self.repo_name = source.name if source is not None else "target-app"

    def repo_path(self, org_id: str) -> Path:
        return self.root / org_id / self.repo_name

    def _worktrees_path(self, org_id: str) -> Path:
        return self.root / org_id / "worktrees"

    # ------------------------------------------------------------------ setup
    def ensure_repo(self, org_id: str) -> Path:
        """Initialize the org's work target (idempotent): clone the configured source repo,
        or copy the fixture in and git-init it."""
        repo = self.repo_path(org_id)
        if (repo / ".git").exists():
            return repo
        repo.parent.mkdir(parents=True, exist_ok=True)
        if self.source is not None:
            if not (self.source / ".git").exists():
                raise RepoError(f"[repo] source is not a git repository: {self.source}")
            _git(repo.parent, "clone", str(self.source), str(repo))
            try:
                # DWIM-creates local main from origin/main when the source HEAD is elsewhere.
                _git(repo, "checkout", "main")
            except RepoError:
                # A half-initialized clone must not satisfy the idempotency check next call.
                shutil.rmtree(repo, ignore_errors=True)
                raise RepoError(
                    f"[repo] source {self.source} has no 'main' branch — the executors "
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
        if self.source is None:
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

    # ----------------------------------------------------------------- merge
    def merge(self, org_id: str, branch: str) -> dict:
        """The governed merge executor. The CALLER must have verified a resolved ApprovalGate
        for this action — this method only performs it (and refuses garbage branches)."""
        if not branch.startswith("canopy/"):
            raise RepoError(f"refusing to merge non-canopy branch {branch!r}")
        repo = self.ensure_repo(org_id)
        _git(repo, "merge", "--no-ff", branch, "-m", f"merge {branch} (governed)")
        return {"mergedSha": _git(repo, "rev-parse", "main"), "branch": branch}
