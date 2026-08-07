"""The ``cli-claude`` runtime (cli-runtime.md): wraps one headless Claude Code session per
assignment. The session is the agent's brain and loop; this adapter observes, meters, gates,
and reports.

Per assignment: INTAKE (materialize ``brief/``) → CONFIG (settings.json permissions compiled
from the charter's grants, ``.mcp.json`` with exactly the canopy server, ``CLAUDE.md`` teaching
the assignment protocol) → RUN (``claude -p … --output-format stream-json``) → OBSERVE (events →
settled Step reports; ``init``'s session id → the assignment's resume handle) → GATE (budget
checked as usage accumulates; overshoot kills the process tree at the event boundary — debt
E-D1) → DISCHARGE (the session itself calls MCP ``finish``). Resume after a gate resolution is
``claude --resume <sessionRef>`` — a gated assignment is a suspended conversation.

``CANOPY_CLI_CMD`` overrides the CLI command (a JSON array or a bare name; the fake-CLI shim in
CI points it at a python script). httpx + stdlib only, like the rest of ``canopy_agent``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx

from .runtime import AgentConfig, _log, runtime

MAX_TURNS_DEFAULT = 30

#: F14: how often the observer re-asserts "this session is alive" to the control plane.
HEALTH_HEARTBEAT_SECONDS = 15.0
#: F11: a provider-limit death backs off this long before the next resume attempt —
#: hammering a closed window burns nothing but looks like (and used to be gated as) a stall.
PROVIDER_LIMIT_BACKOFF_SECONDS = 600.0
#: Error text that means "the provider shut the door", not "the session broke".
_PROVIDER_LIMIT_RE = re.compile(r"limit|resets|overloaded|quota|rate.?limit", re.I)

# Grant key -> Claude Code permission entries (cli-runtime.md §2's table, path-concrete in
# target-app.md §5). Generated permissions are defense-in-depth; the MCP server's per-call
# grant checks are the real wall on the subprocess tier.
GRANT_PERMISSIONS: dict[str, list[str]] = {
    "workspace.rw": ["Read", "Edit", "Write", "Glob", "Grep"],
    "repo.read": ["Bash(git log*)", "Bash(git diff*)", "Bash(git show*)", "Bash(git status*)"],
    "code.repo.write": ["Bash(git *)"],
    "test.unit.run": ["Bash(uv run pytest tests/unit*)"],
    "test.run": ["Bash(uv run pytest tests*)"],
    # repo.merge is governed — it travels through MCP as an approval-gated action (E4),
    # never as a session permission.
}
ALWAYS_DENY = ["WebFetch", "WebSearch"]


def _compile_permissions(tool_grants: list[str]) -> tuple[list[str], list[str]]:
    allow: list[str] = ["mcp__canopy"]  # the canopy tool plane is always the agent's surface
    for key in tool_grants:
        allow.extend(GRANT_PERMISSIONS.get(key, []))
    deny = list(ALWAYS_DENY)
    if not any(k in GRANT_PERMISSIONS and GRANT_PERMISSIONS[k] and
               GRANT_PERMISSIONS[k][0].startswith("Bash") for k in tool_grants):
        pass  # no blanket Bash denial needed: unlisted tools are simply not allowed
    return allow, deny


PROTOCOL = """\
## The assignment protocol (Canopy)

You have exactly one assignment; its brief is in `../brief/`. Work only through the `canopy`
MCP tools:

1. Call `get_assignment` first — it carries your brief, contract, budget meter, durable
   memory, and any operator notes (advisory context, not brief changes).
2. Declare a plan with `declare_plan` BEFORE working; keep the cursor honest with
   `update_stage` as you go.
3. Ship results only via `produce_artifact` and end with `finish` citing those refs. The
   deliverable contract is exactly what is accepted — nothing else.
4. If the brief is defective, `open_clarification` — do not guess. If you need a decision
   above your pay grade, `escalate` — asking is cheaper than guessing.
"""

MANAGER_PROTOCOL = """\
### Managers

Decompose the brief; one `delegate` per child with a self-contained brief, cited refs, an
explicit deliverable contract, and `dependsOn` for sequencing. Delegations may be staged for
plan review — after your fan-out, call `finish_turn` and end your turn; approval, edits, or
denial arrive when you are resumed. When resumed with completed child work, check
`reports_status`, review each deliverable against its contract, and `accept`/`reject` with a
note (a rejection with an unchanged brief funds rework from the report's own meter). Synthesize
accepted refs into your own deliverable via `finish`. You never do your reports' work — you
have no tools for it.

A report in state `delivering` is NOT still working: it has finished and is blocked waiting on
YOUR review (`reports_status` shows its deliverable under `awaitingYourReview`). Fetch its
artifacts with `fetch_artifact` and `accept`/`reject` immediately — never wait on, poll, or
escalate about a `delivering` report.
"""


def _write_session_config(
    workdir: Path, cfg: AgentConfig, charter: dict, brief: dict | None, memory: list,
) -> None:
    (workdir / ".claude").mkdir(parents=True, exist_ok=True)
    allow, deny = _compile_permissions(charter.get("toolGrants", []))
    (workdir / ".claude" / "settings.json").write_text(json.dumps({
        "permissions": {"allow": allow, "deny": deny},
    }, indent=2), encoding="utf-8")
    (workdir / ".mcp.json").write_text(json.dumps({
        "mcpServers": {
            "canopy": {
                "type": "http",
                "url": f"{cfg.cp_url}/api/dp/mcp",
                "headers": {"Authorization": f"Bearer {cfg.run_token}"},
            }
        }
    }, indent=2), encoding="utf-8")

    parts = [charter.get("instructions", ""), PROTOCOL]
    if charter.get("reportNodeIds"):
        parts.append(MANAGER_PROTOCOL)
        reports = ", ".join(charter["reportNodeIds"])
        parts.append(f"Your direct reports (delegation targets): {reports}")
    if memory:
        lines = ["## Your recent work"]
        for m in memory[-5:]:
            lines.append(f"- [{m.get('outcome', '?')}] {m.get('intentText', '')[:80]} "
                         f"({m.get('costTokens', 0)} tokens)")
        parts.append("\n".join(lines))
    if brief:
        refs = brief.get("artifactRefs") or []
        if refs:
            parts.append("## Granted artifact refs\n" + "\n".join(f"- {r}" for r in refs))
    (workdir / "CLAUDE.md").write_text("\n\n".join(p for p in parts if p), encoding="utf-8")


#: F16 retention: per-assignment stderr rotates at this size, keeping one predecessor.
_STDERR_ROTATE_BYTES = 1024 * 1024


def _rotate_if_large(path: Path, cap: int = _STDERR_ROTATE_BYTES) -> None:
    try:
        if path.is_file() and path.stat().st_size >= cap:
            path.replace(path.with_suffix(path.suffix + ".1"))
    except OSError:
        pass  # rotation is best-effort; appending to an oversized log beats losing it


def _work_root() -> Path:
    """F13: the assignment tree's stable home. The actuator passes an actuation-independent
    path (``data/work/<orgId>/<nodeId>``) so the CLI's per-directory conversation key — and
    with it ``--resume`` — survives deactuate → re-actuate. Absent (tests, older actuators),
    the sandbox cwd keeps the legacy per-actuation shape."""
    raw = os.environ.get("CANOPY_WORK_ROOT")
    return Path(raw) if raw else Path.cwd()


def _transcript_path(workdir: Path, session_id: str) -> Path:
    """Where the CLI writes this session's conversation (F16's pointer): the config dir's
    ``projects/<key>/<sessionId>.jsonl``, where the key is the workdir path with every
    non-alphanumeric character flattened to ``-`` (the CLI's own munge)."""
    raw = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(raw) if raw else Path.home() / ".claude"
    key = re.sub(r"[^A-Za-z0-9]", "-", str(workdir))
    return base / "projects" / key / f"{session_id}.jsonl"


def _archive_transcript(workroot: Path, workdir: Path, session_id: str) -> None:
    """F16: copy the session transcript into the assignment's own home — the org owns the
    complete record of what its agent said and did, not the operator's CLI profile."""
    src = _transcript_path(workdir, session_id)
    try:
        if src.is_file():
            dest = workroot / "transcripts"
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / f"{session_id}.jsonl")
            _log("transcript_archived", session=session_id, path=str(dest))
    except OSError as exc:
        _log("transcript_archive_failed", session=session_id, error=str(exc))


def _cli_command() -> list[str]:
    raw = os.environ.get("CANOPY_CLI_CMD", "claude")
    cmd = json.loads(raw) if raw.strip().startswith("[") else [raw]
    # Windows: CreateProcess never applies PATHEXT to a bare name, so an npm shim like
    # claude.cmd is invisible to Popen even though `claude` resolves in every shell.
    # Resolve through PATH here so the probe and the spawn agree on one real path.
    resolved = shutil.which(cmd[0])
    if resolved:
        cmd[0] = resolved
    return cmd


def _kill_tree(proc: subprocess.Popen) -> None:
    """Interrupt the session at the event boundary (cli-runtime.md §6). Windows needs the
    process-group kill (sandbox.md); POSIX gets the group signal."""
    if proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, check=False)
        else:
            import signal

            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except OSError:
        proc.kill()


_READ_ONLY_TOOLS = ("get_assignment", "reports_status", "fetch_artifact")


class _Session:
    """One live headless session and the observer thread consuming its stream."""

    def __init__(self, assignment_id: str):
        self.assignment_id = assignment_id
        self.thread: threading.Thread | None = None
        self.proc: subprocess.Popen | None = None
        self.progress = False  # any non-"none" delta settled by this session

    @property
    def alive(self) -> bool:
        return self.thread is not None and self.thread.is_alive()


_SESSIONS: dict[str, _Session] = {}
_RESUME_BACKOFF: dict[str, dict[str, float]] = {}
#: F13 interim: assignments whose conversation the CLI can no longer find — the next
#: session starts fresh (full brief prompt) instead of retrying a doomed --resume.
_RESUME_FALLBACK: set[str] = set()


def _observe_stream(
    client: httpx.Client, proc: subprocess.Popen, assignment_id: str, *,
    budget_remaining: int, is_manager: bool, workroot: Path, workdir: Path,
) -> None:
    """Parse stream-json → settled Step reports; kill the tree when spend crosses the budget."""
    session_id: str | None = None
    spent = 0
    last_event = time.monotonic()
    last_health = 0.0
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        etype = event.get("type")

        # F14: any stream event is proof of life — report it (throttled) so the stall sweep
        # keys on real activity instead of inferring life from settled steps.
        now_mono = time.monotonic()
        if now_mono - last_health >= HEALTH_HEARTBEAT_SECONDS:
            last_health = now_mono
            try:
                client.post("/api/dp/assignment/events", json={
                    "assignmentId": assignment_id, "kind": "session-health",
                    "health": "running",
                })
            except httpx.HTTPError:
                pass  # liveness is best-effort; the next event retries

        if etype == "system" and event.get("subtype") == "init":
            session_id = event.get("session_id")
            if session_id:
                client.post("/api/dp/assignment/events", json={
                    "assignmentId": assignment_id, "kind": "session-ref",
                    "sessionRef": session_id,
                    # F16: the org's pointer to the conversation's ground truth.
                    "transcriptPath": str(_transcript_path(workdir, session_id)),
                })
                _log("session_init", assignment=assignment_id, session=session_id)

        elif etype == "assistant":
            msg = event.get("message") or {}
            usage = msg.get("usage") or {}
            in_tok = int(usage.get("input_tokens", 0))
            out_tok = int(usage.get("output_tokens", 0))
            # F1: the context window rides the cache components — dropping them made the
            # ledger blind to ~all input (a whole-corpus read recorded as 65 tokens).
            cache_read = int(usage.get("cache_read_input_tokens", 0))
            cache_creation = int(usage.get("cache_creation_input_tokens", 0))
            content = msg.get("content") or []
            tools = [c.get("name", "") for c in content if c.get("type") == "tool_use"]
            # Read-only status checks are NOT progress: a session that only polls must
            # settle no-delta steps so the engine's stall trigger can see the spin.
            delta = "none"
            if tools and not all(t.endswith(_READ_ONLY_TOOLS) for t in tools):
                delta = "tool-effect"
            if any(t.endswith("produce_artifact") for t in tools):
                delta = "artifact"
            elif any(t.endswith(("delegate", "escalate", "finish_turn")) for t in tools):
                delta = "message"
            if delta != "none":
                sess = _SESSIONS.get(assignment_id)
                if sess is not None:
                    sess.progress = True
            now = time.monotonic()
            client.post("/api/dp/assignment/events", json={
                "assignmentId": assignment_id, "kind": "step",
                "stepKind": "coordination" if is_manager else "production",
                "inputTokens": in_tok, "outputTokens": out_tok,
                "cacheReadTokens": cache_read, "cacheCreationTokens": cache_creation,
                "durationMs": int((now - last_event) * 1000),
                "deltaKind": delta, "deltaRef": tools[0] if tools else None,
                "sessionSpanId": session_id, "settle": True,
                # The session's model prices the settle (F1) — profile.model rides the same
                # env var that sets --model; absent (fake CLI) falls back to the default.
                "model": os.environ.get("CANOPY_CLI_MODEL") or "claude-cli",
            })
            last_event = now
            spent += in_tok + out_tok
            if spent >= budget_remaining:
                # The turn boundary (invariant 7, coarsened per debt E-D1): the settled step
                # above already tripped the engine's hard-stop trigger; stop burning.
                _log("budget_boundary_halt", assignment=assignment_id, spent=spent)
                _kill_tree(proc)
                break

        elif etype == "result":
            err = event.get("result") if event.get("is_error") else None
            _log("session_result", assignment=assignment_id,
                 cost_usd=event.get("total_cost_usd"), turns=event.get("num_turns"),
                 is_error=bool(event.get("is_error")),
                 error=(str(err)[:200] if err is not None else None))
            if event.get("is_error"):
                # F11: surface the cause to the control plane instead of dying silently into
                # a crash-loop the sweep reads as a stall.
                detail = str(err)[:300] if err is not None else "session ended with an error"
                try:
                    client.post("/api/dp/assignment/events", json={
                        "assignmentId": assignment_id, "kind": "session-health",
                        "health": "erroring", "healthDetail": detail,
                    })
                except httpx.HTTPError:
                    pass
                if _PROVIDER_LIMIT_RE.search(detail):
                    # The provider shut the door — retrying before it reopens is pure noise.
                    st = _RESUME_BACKOFF.setdefault(
                        assignment_id, {"count": 0, "until": 0.0}
                    )
                    st["until"] = max(
                        st["until"], time.monotonic() + PROVIDER_LIMIT_BACKOFF_SECONDS
                    )
                    _log("provider_limit_backoff", assignment=assignment_id,
                         seconds=int(PROVIDER_LIMIT_BACKOFF_SECONDS))

    proc.wait()
    if session_id:
        _archive_transcript(workroot, workdir, session_id)
    stderr_tail: list[str] = []
    if proc.returncode:
        try:
            stderr_log = workroot / "session.stderr.log"
            stderr_tail = stderr_log.read_text(encoding="utf-8", errors="replace")\
                .strip().splitlines()[-3:]
        except OSError:
            pass
        # F13 interim: the CLI keys conversations by project directory, so a workdir that
        # moved (re-actuation changes the sandbox path) makes --resume fail forever with
        # "No conversation found". Fall back to a fresh session instead of crash-looping
        # into the stall trigger; the durable work model re-briefs it.
        if any("No conversation found" in line for line in stderr_tail):
            _RESUME_FALLBACK.add(assignment_id)
            _log("resume_conversation_lost", assignment=assignment_id)
    _log("session_exit", assignment=assignment_id, code=proc.returncode,
         stderr_tail=stderr_tail or None)


def _materialize_brief(client: httpx.Client, workroot: Path, brief: dict | None) -> None:
    brief_dir = workroot / "brief"
    brief_dir.mkdir(parents=True, exist_ok=True)
    if not brief:
        return
    (brief_dir / "BRIEF.md").write_text(brief.get("text", ""), encoding="utf-8")
    for ref in brief.get("artifactRefs") or []:
        try:
            r = client.get("/api/dp/artifacts", params={"ref": ref})
            if r.status_code != 200:
                _log("brief_ref_fetch_failed", ref=ref, status=r.status_code)
                continue
            body = r.json()
            name = (body.get("meta") or {}).get("name", "artifact")
            content = body.get("contentBase64")
            if content:
                import base64

                (brief_dir / f"{name}.bin").write_bytes(base64.b64decode(content))
        except httpx.HTTPError as exc:
            _log("brief_ref_fetch_error", ref=ref, error=str(exc))


def _start_session(
    client: httpx.Client, cfg: AgentConfig, charter: dict, cur: dict, *, resume: bool,
) -> None:
    a = cur["assignment"]
    aid = a["id"]
    workroot = _work_root() / "assignments" / aid
    workdir = workroot / "work"
    workdir.mkdir(parents=True, exist_ok=True)
    (workroot / "out").mkdir(parents=True, exist_ok=True)
    _materialize_brief(client, workroot, cur.get("brief"))
    _write_session_config(workdir, cfg, charter, cur.get("brief"), cur.get("memory") or [])

    meter = cur.get("meter") or {}
    remaining = max(0, int(meter.get("allowance", 0)) - int(meter.get("spent", 0)))
    if remaining <= 0 and meter:
        _log("session_not_started_exhausted", assignment=aid)
        return

    brief_text = (cur.get("brief") or {}).get("text", "")
    if resume and a.get("sessionRef"):
        prompt = ("You have been resumed. Call the canopy `get_assignment` tool to see the "
                  "current state (resolutions, notes, deliveries), then continue the protocol. "
                  "Do not end your turn without advancing the assignment: if your deliverable "
                  "artifacts are already produced, call `finish` citing their refs; if you are "
                  "a manager with a report in state `delivering`, review and accept/reject it "
                  "now; if you are genuinely blocked, escalate or open a clarification instead "
                  "of ending your turn idle.")
        extra = ["--resume", a["sessionRef"]]
    else:
        prompt = (f"Begin your assignment. Brief:\n\n{brief_text}\n\n"
                  "Follow the assignment protocol in CLAUDE.md.")
        extra = []

    max_turns = int(os.environ.get("CANOPY_MAX_TURNS", str(MAX_TURNS_DEFAULT)))
    # The prompt goes over STDIN, never argv: on Windows the npm shim (claude.cmd) runs
    # through cmd.exe, which treats embedded newlines as command separators — a multi-line
    # brief silently strips every flag after it (the session answers in plain text and the
    # observer sees zero events). Stdin also sidesteps the 32K command-line ceiling.
    cmd = _cli_command() + [
        "-p", "--output-format", "stream-json", "--verbose",
        "--max-turns", str(max_turns), "--permission-mode", "default",
        "--mcp-config", ".mcp.json", "--strict-mcp-config", *extra,
    ]
    # The profile's model is the session's model (cli-runtime.md §2: profile.model → --model);
    # without it the CLI silently runs on the operator's personal default.
    model = os.environ.get("CANOPY_CLI_MODEL")
    if model:
        cmd += ["--model", model]
    # CLI stderr goes to a per-assignment file, not DEVNULL: when a session dies at
    # startup (auth, bad flag), this file is the only place the reason lands.
    stderr_path = workroot / "session.stderr.log"
    _rotate_if_large(stderr_path)
    popen_kw: dict = {
        "cwd": str(workdir), "stdin": subprocess.PIPE, "stdout": subprocess.PIPE,
        "stderr": open(stderr_path, "ab"),  # noqa: SIM115 - fd is inherited by the child
        "text": True, "encoding": "utf-8",
    }
    if sys.platform == "win32":
        popen_kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kw["start_new_session"] = True
    try:
        proc = subprocess.Popen(cmd, **popen_kw)  # noqa: S603 - compiled command, no shell
    except OSError as exc:
        _log("session_spawn_failed", assignment=aid, error=str(exc))
        return

    def _feed_stdin(p: subprocess.Popen, text: str) -> None:
        # Own thread: a brief larger than the pipe buffer would otherwise block the tick
        # until the CLI drains it. Closing stdin ends the CLI's 3s stdin wait immediately.
        try:
            assert p.stdin is not None
            p.stdin.write(text)
            p.stdin.close()
        except OSError:
            pass

    threading.Thread(target=_feed_stdin, args=(proc, prompt), daemon=True).start()

    session = _Session(aid)
    session.proc = proc
    is_manager = bool(charter.get("reportNodeIds"))
    session.thread = threading.Thread(
        target=_observe_stream, args=(client, proc, aid),
        kwargs={"budget_remaining": remaining or 10**9, "is_manager": is_manager,
                "workroot": workroot, "workdir": workdir},
        daemon=True,
    )
    session.thread.start()
    _SESSIONS[aid] = session
    _log("session_started", assignment=aid, resume=resume, cmd=cmd[0])


def probe_cli() -> bool:
    """Actuation-readiness probe: is the CLI on PATH and answering ``--version``?"""
    cmd = _cli_command()
    exe = cmd[0]
    if shutil.which(exe) is None and not Path(exe).exists():
        return False
    try:
        r = subprocess.run([*cmd, "--version"], capture_output=True, timeout=15, check=False)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


_CHARTERS: dict[str, dict] = {}


@runtime("cli-claude")
def cli_tick(client: httpx.Client, cfg: AgentConfig) -> str:
    """One adapter tick: keep the session aligned with the assignment's engine state."""
    charter = _CHARTERS.get(cfg.node_id)
    if charter is None:
        r = client.get("/api/dp/charter")
        if r.status_code != 200:
            return "idle"
        charter = r.json()
        _CHARTERS[cfg.node_id] = charter

    try:
        r = client.get("/api/dp/assignment/current")
    except httpx.HTTPError as exc:
        _log("work_poll_error", error=str(exc))
        return "idle"
    if r.status_code != 200 or r.json() is None:
        return "idle"
    cur = r.json()
    a = cur["assignment"]
    aid, state = a["id"], a["state"]

    session = _SESSIONS.get(aid)
    if session and session.alive:
        if state in ("gated", "paused"):
            # The engine suspended the assignment (X1 halt flag, hard-stop) — interrupt at
            # the boundary; the session id survives for resume.
            _kill_tree(session.proc)  # type: ignore[arg-type]
            return "engaged"
        return "engaged"  # session is driving; nothing for the adapter to do

    if state in ("briefed", "intake"):
        _materialize_brief(client, _work_root() / "assignments" / aid, cur.get("brief"))
        client.post("/api/dp/assignment/events",
                    json={"assignmentId": aid, "kind": "intake-complete"})
        return "engaged"
    if state in ("planning", "executing"):
        resuming = bool(a.get("sessionRef")) and state == "executing"
        if resuming and aid in _RESUME_FALLBACK:
            # F13 interim: the conversation is gone — start over from the brief.
            _RESUME_FALLBACK.discard(aid)
            resuming = False
            _log("resume_fallback_fresh", assignment=aid)
        if resuming:
            # A resume that follows a no-progress session backs off exponentially:
            # without this, a session that keeps ending with only status polls gets
            # re-dispatched every tick at full session price.
            st = _RESUME_BACKOFF.setdefault(aid, {"count": 0, "until": 0.0})
            prev = _SESSIONS.get(aid)
            if prev is not None and prev.progress:
                st["count"], st["until"] = 0, 0.0
            elif prev is not None:
                if time.monotonic() < st["until"]:
                    return "engaged"
                st["count"] += 1
                st["until"] = time.monotonic() + min(10.0 * (2 ** st["count"]), 300.0)
                if st["count"] >= 2:
                    _log("resume_backoff", assignment=aid, count=st["count"])
        _start_session(client, cfg, charter, cur, resume=resuming)
        return "engaged"
    return "idle"  # delivering / gated / terminal: awaiting review or resolution
