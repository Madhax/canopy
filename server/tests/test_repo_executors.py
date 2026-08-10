"""E4 — the repo executors: worktree materialization, read-only checkout, PR assembly, and the
governed merge with its attestation (mvp.md E4, testing.md §4 E4 rows).

Adversarial cases per doctrine: QA cannot take a rw worktree, the merge refuses without a
resolved ApprovalGate (there is no other path to it), and denial is a prohibition.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _node(team: dict, role_key: str) -> dict:
    return next(a for a in team["agents"] if a["role"]["key"] == role_key)


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------ RepoManager (unit)
def test_repo_manager_lifecycle(tmp_path):
    from canopy_server.repos import RepoError, RepoManager

    mgr = RepoManager(tmp_path / "repos")
    repo = mgr.ensure_repo("org1")
    assert (repo / ".git").exists() and (repo / "app" / "main.py").exists()
    assert mgr.ensure_repo("org1") == repo  # idempotent

    wt = mgr.materialize_worktree("org1", "as_1")
    assert wt["branch"] == "canopy/as_1"
    path = Path(wt["path"])
    assert (path / "app" / "main.py").exists()
    assert mgr.materialize_worktree("org1", "as_1")["branch"] == wt["branch"]  # idempotent

    # Work happens in the worktree; the PR pins exactly what exists on disk.
    (path / "app" / "export.py").write_text("CSV = 'soon'\n", encoding="utf-8")
    pr = mgr.assemble_pr("org1", "as_1", test_output="9 passed")
    assert pr["branch"] == "canopy/as_1" and pr["baseSha"] != pr["headSha"]
    assert "app/export.py" in pr["diff"] and pr["testOutput"] == "9 passed"

    ro = mgr.readonly_checkout("org1", pr["headSha"], tag="qa_1")
    assert (Path(ro["path"]) / "app" / "export.py").exists()
    assert ro["sha"] == pr["headSha"]

    merged = mgr.merge("org1", "canopy/as_1")
    assert merged["mergedSha"]
    assert (repo / "app" / "export.py").exists()  # main advanced under governance

    with pytest.raises(RepoError, match="non-canopy"):
        mgr.merge("org1", "main")
    with pytest.raises(RepoError, match="no worktree"):
        mgr.assemble_pr("org1", "as_missing")


def test_repo_manager_clones_a_configured_source(tmp_path):
    """E8: with ``[repo] source`` set, the work target is a clone of a real local repository —
    history preserved, source never written — and the whole executor lifecycle runs on it."""
    from canopy_server.repos import RepoManager, _git

    source = tmp_path / "canopy-work"
    source.mkdir()
    _git(source, "init", "-b", "main")
    _git(source, "config", "user.email", "op@localhost")
    _git(source, "config", "user.name", "Operator")
    (source / "README.md").write_text("# Canopy\n", encoding="utf-8")
    (source / "docs").mkdir()
    (source / "docs" / "quickstart.md").write_text("# Quickstart\n", encoding="utf-8")
    _git(source, "add", "-A")
    _git(source, "commit", "-m", "canopy: initial")
    (source / "docs" / "quickstart.md").write_text("# Quickstart\n\nrun it\n", encoding="utf-8")
    _git(source, "add", "-A")
    _git(source, "commit", "-m", "docs: expand quickstart")

    mgr = RepoManager(tmp_path / "repos", source=source)
    repo = mgr.ensure_repo("org1")
    assert repo.name == "canopy-work"  # named after the source, not target-app
    assert _git(repo, "log", "--format=%s").splitlines() == [
        "docs: expand quickstart", "canopy: initial",
    ]  # a clone with history, not a snapshot
    assert mgr.ensure_repo("org1") == repo  # idempotent

    wt = mgr.materialize_worktree("org1", "as_docs")
    assert wt["branch"] == "canopy/as_docs"
    Path(wt["path"], "docs", "readiness.md").write_text("# Readiness\n", encoding="utf-8")
    pr = mgr.assemble_pr("org1", "as_docs")
    assert "docs/readiness.md" in pr["diff"]
    mgr.merge("org1", "canopy/as_docs")
    assert (repo / "docs" / "readiness.md").exists()  # merged under governance
    # The source repository is only ever read — nothing wrote back to it.
    assert not (source / "docs" / "readiness.md").exists()
    assert _git(source, "log", "--format=%s").splitlines()[0] == "docs: expand quickstart"


def test_repo_source_guards(tmp_path):
    from canopy_server.repos import RepoError, RepoManager, _git

    not_a_repo = tmp_path / "plain-dir"
    not_a_repo.mkdir()
    with pytest.raises(RepoError, match="not a git repository"):
        RepoManager(tmp_path / "r1", source=not_a_repo).ensure_repo("org1")

    trunk = tmp_path / "trunk-repo"
    trunk.mkdir()
    _git(trunk, "init", "-b", "trunk")
    _git(trunk, "config", "user.email", "op@localhost")
    _git(trunk, "config", "user.name", "Operator")
    (trunk / "a.txt").write_text("a\n", encoding="utf-8")
    _git(trunk, "add", "-A")
    _git(trunk, "commit", "-m", "init")
    with pytest.raises(RepoError, match="no 'main' branch"):
        RepoManager(tmp_path / "r2", source=trunk).ensure_repo("org1")


# --------------------------------------------------------------- dp surface + grants
@pytest.fixture()
def pod(client, make_org, mint_session):
    from canopy_server.deps import get_engine
    from test_cli_runtime import _seed_charter

    team = make_org(seed={"kind": "formation", "formationKey": "product-engineering-pod"})
    lead, be, qa = (_node(team, k) for k in
                    ("engineering-lead", "backend-engineer", "qa-engineer"))
    s_lead = mint_session(team["id"], node_id=lead["id"])
    s_be = mint_session(team["id"], node_id=be["id"], actuation_id=s_lead["actuationId"])
    s_qa = mint_session(team["id"], node_id=qa["id"], actuation_id=s_lead["actuationId"])
    for node in (lead, be, qa):
        _seed_charter(team, s_lead["actuationId"], node["id"])
    eng = get_engine()
    root = eng.submit_intent(team["id"], s_lead["actuationId"],
                             "Add CSV export; all tests must pass",
                             target_node=lead["id"]).assignment
    eng.mark_intake_complete(root.id)
    eng.declare_plan(root.id, [{"title": "decompose"}])
    be_a = eng.delegate(root.id, be["id"], "implement CSV", contract_type="PullRequest")
    qa_a = eng.delegate(root.id, qa["id"], "verify", contract_type="TestReport",
                        depends_on=[{"assignmentId": be_a.id}])
    gate = eng.finish_turn(root.id)
    eng.resolve_gate(gate.id, action="approve")
    return {"team": team, "engine": eng, "root": root, "be_a": be_a, "qa_a": qa_a,
            "s_lead": s_lead, "s_be": s_be, "s_qa": s_qa}


def test_engineer_worktree_pr_and_qa_checkout_flow(client, pod):
    from canopy_server.deps import get_engine

    eng = pod["engine"]
    be_a = pod["be_a"]
    eng.mark_intake_complete(be_a.id)
    eng.declare_plan(be_a.id, [{"title": "implement"}])

    # Engineer takes the rw worktree (code.repo.write) and does the work.
    wt = client.post("/api/dp/repo/checkout", headers=_h(pod["s_be"]["token"]),
                     json={"assignmentId": be_a.id}).json()
    assert wt["branch"] == f"canopy/{be_a.id}"
    Path(wt["path"], "app", "export.py").write_text("CSV = 'v1'\n", encoding="utf-8")

    pr_resp = client.post("/api/dp/repo/pr", headers=_h(pod["s_be"]["token"]),
                          json={"assignmentId": be_a.id, "testOutput": "unit: 9 passed"})
    assert pr_resp.status_code == 200, pr_resp.text
    ref, pr = pr_resp.json()["ref"], pr_resp.json()["pr"]
    assert "app/export.py" in pr["diff"]

    # finish citing the PR ref resolves QA's verify dependency (E2) with the ref granted.
    eng.finish(be_a.id, artifact_refs=[ref], summary="PR v1")
    qa_a = eng.store.get_assignment(pod["qa_a"].id)
    assert qa_a.state == "briefed"
    eng.mark_intake_complete(qa_a.id)

    # QA fetches the PR artifact (brief-granted), then checks out the submitted head ro.
    got = client.get(f"/api/dp/artifacts?ref={ref}", headers=_h(pod["s_qa"]["token"]))
    assert got.status_code == 200
    ro = client.post("/api/dp/repo/checkout", headers=_h(pod["s_qa"]["token"]),
                     json={"assignmentId": qa_a.id, "ref": pr["headSha"]}).json()
    assert Path(ro["path"], "app", "export.py").exists()
    assert ro["sha"] == pr["headSha"]

    # Adversarial: QA has no code.repo.write — a rw worktree is refused AND audited.
    steal = client.post("/api/dp/repo/checkout", headers=_h(pod["s_qa"]["token"]),
                        json={"assignmentId": qa_a.id})
    assert steal.status_code == 403
    assert steal.json()["error"]["code"] == "GRANT_DENIED"
    events = get_engine().store.list_tool_events(pod["s_qa"]["actuationId"],
                                                 pod["s_qa"]["nodeId"])
    assert events[-1]["outcome"] == "denied" and events[-1]["tool"] == "repo_checkout"


def test_governed_merge_needs_the_gate(client, pod):
    """The merge executor is reachable ONLY through a resolved ApprovalGate; approval runs it
    and the attestation links the gate; denial is a prohibition."""
    from canopy_server.deps import get_repos

    eng = pod["engine"]
    be_a, root = pod["be_a"], pod["root"]
    eng.mark_intake_complete(be_a.id)
    eng.declare_plan(be_a.id, [{"title": "implement"}])
    wt = client.post("/api/dp/repo/checkout", headers=_h(pod["s_be"]["token"]),
                     json={"assignmentId": be_a.id}).json()
    Path(wt["path"], "app", "export.py").write_text("CSV = 'v1'\n", encoding="utf-8")
    pr = client.post("/api/dp/repo/pr", headers=_h(pod["s_be"]["token"]),
                     json={"assignmentId": be_a.id}).json()["pr"]

    # The engineer cannot even ask for a merge (no repo.merge grant).
    r = client.post("/api/dp/repo/merge-request", headers=_h(pod["s_be"]["token"]),
                    json={"assignmentId": be_a.id, "branch": pr["branch"]})
    assert r.status_code == 403 and r.json()["error"]["code"] == "GRANT_DENIED"

    # The lead requests it — a governed action: gate opens, nothing merges yet.
    r = client.post("/api/dp/repo/merge-request", headers=_h(pod["s_lead"]["token"]),
                    json={"assignmentId": root.id, "branch": pr["branch"]})
    assert r.status_code == 200, r.text
    gate = r.json()
    assert gate["kind"] == "approval" and gate["payload"]["governedAction"] == "repo-merge"
    repo = get_repos().repo_path(pod["team"]["id"])
    assert not (repo / "app" / "export.py").exists()  # main untouched pre-approval

    # Operator approves: the executor merges and the attestation links the gate.
    rr = client.post(f"/api/gates/{gate['id']}/resolve", json={"action": "approve"})
    assert rr.status_code == 200, rr.text
    resolution = rr.json()["resolution"]
    assert resolution["executed"] == "repo-merge"
    assert resolution["attestation"]["gateId"] == gate["id"]
    assert resolution["result"]["mergedSha"]
    assert (repo / "app" / "export.py").exists()  # consented, then done
    # The lead is STILL gated — on its await gate (children outstanding), not the resolved
    # approval gate: resolving one gate never tramples another's suspension.
    assert eng.store.get_assignment(root.id).state == "gated"
    awaits = [g for g in eng.store.list_gates(assignment_id=root.id, state="open")
              if g.payload.get("await")]
    assert len(awaits) == 1


def test_governed_merge_denial_is_a_prohibition(client, pod):
    from canopy_server.deps import get_repos

    eng, root = pod["engine"], pod["root"]
    be_a = pod["be_a"]
    eng.mark_intake_complete(be_a.id)
    eng.declare_plan(be_a.id, [{"title": "implement"}])
    wt = client.post("/api/dp/repo/checkout", headers=_h(pod["s_be"]["token"]),
                     json={"assignmentId": be_a.id}).json()
    Path(wt["path"], "app", "export.py").write_text("CSV = 'v1'\n", encoding="utf-8")
    pr = client.post("/api/dp/repo/pr", headers=_h(pod["s_be"]["token"]),
                     json={"assignmentId": be_a.id}).json()["pr"]

    gate = client.post("/api/dp/repo/merge-request", headers=_h(pod["s_lead"]["token"]),
                       json={"assignmentId": root.id, "branch": pr["branch"]}).json()
    rr = client.post(f"/api/gates/{gate['id']}/resolve",
                     json={"action": "deny", "note": "not until QA is green"})
    assert rr.status_code == 200
    repo = get_repos().repo_path(pod["team"]["id"])
    assert not (repo / "app" / "export.py").exists()  # nothing merged
    g = eng.store.get_gate(gate["id"])
    assert g.state == "resolved" and g.resolution["action"] == "deny"  # a prohibition


def test_mcp_repo_tools_are_grant_filtered(client, pod):
    def tools_for(session):
        r = client.post("/api/dp/mcp", headers=_h(session["token"]),
                        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        return {t["name"] for t in r.json()["result"]["tools"]}

    be_tools = tools_for(pod["s_be"])
    qa_tools = tools_for(pod["s_qa"])
    lead_tools = tools_for(pod["s_lead"])
    assert {"repo_checkout", "repo_pr"} <= be_tools and "repo_merge_request" not in be_tools
    assert "repo_checkout" in qa_tools and "repo_pr" not in qa_tools  # ro only
    assert "repo_merge_request" in lead_tools and "repo_pr" not in lead_tools

    # Server-side re-check: QA calling repo_pr is denied and audited.
    from canopy_server.deps import get_work_store

    r = client.post("/api/dp/mcp", headers=_h(pod["s_qa"]["token"]),
                    json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                          "params": {"name": "repo_pr", "arguments": {}}})
    assert "error" in r.json()
    events = get_work_store().list_tool_events(pod["s_qa"]["actuationId"],
                                               pod["s_qa"]["nodeId"])
    assert events[-1]["tool"] == "repo_pr" and events[-1]["outcome"] == "denied"


def test_docs_pod_writer_writes_editor_reviews(client, make_org, mint_session):
    """E8 — the docs re-role. The tier-1 ``docs.repo.write`` grant opens the same rw
    worktree/PR path the engineer uses; the editor (read-only, the verify edge) can check
    out the submitted head but is refused a rw worktree; MCP filters match."""
    from canopy_server.deps import get_engine
    from test_cli_runtime import _seed_charter

    team = make_org(seed={"kind": "formation", "formationKey": "docs-pod"})
    lead, writer, editor = (_node(team, k) for k in
                            ("engineering-lead", "tech-writer", "editor"))
    s_lead = mint_session(team["id"], node_id=lead["id"])
    s_w = mint_session(team["id"], node_id=writer["id"], actuation_id=s_lead["actuationId"])
    s_e = mint_session(team["id"], node_id=editor["id"], actuation_id=s_lead["actuationId"])
    for node in (lead, writer, editor):
        _seed_charter(team, s_lead["actuationId"], node["id"])
    eng = get_engine()
    root = eng.submit_intent(team["id"], s_lead["actuationId"],
                             "Document the readiness codes",
                             target_node=lead["id"]).assignment
    eng.mark_intake_complete(root.id)
    eng.declare_plan(root.id, [{"title": "decompose"}])
    w_a = eng.delegate(root.id, writer["id"], "write the doc page",
                       contract_type="PullRequest")
    e_a = eng.delegate(root.id, editor["id"], "review the doc page",
                       contract_type="EditedDraft",
                       depends_on=[{"assignmentId": w_a.id}])
    gate = eng.finish_turn(root.id)
    eng.resolve_gate(gate.id, action="approve")

    eng.mark_intake_complete(w_a.id)
    eng.declare_plan(w_a.id, [{"title": "write"}])
    wt = client.post("/api/dp/repo/checkout", headers=_h(s_w["token"]),
                     json={"assignmentId": w_a.id})
    assert wt.status_code == 200, wt.text
    assert wt.json()["branch"] == f"canopy/{w_a.id}"
    Path(wt.json()["path"], "docs-page.md").write_text("# Readiness codes\n", encoding="utf-8")
    pr_resp = client.post("/api/dp/repo/pr", headers=_h(s_w["token"]),
                          json={"assignmentId": w_a.id})
    assert pr_resp.status_code == 200, pr_resp.text
    ref, pr = pr_resp.json()["ref"], pr_resp.json()["pr"]
    assert "docs-page.md" in pr["diff"]

    eng.finish(w_a.id, artifact_refs=[ref], summary="doc PR v1")
    e_a = eng.store.get_assignment(e_a.id)
    assert e_a.state == "briefed"  # the verify edge unlocked at submission
    eng.mark_intake_complete(e_a.id)

    # The editor reviews read-only: ro checkout allowed, rw worktree refused + audited.
    ro = client.post("/api/dp/repo/checkout", headers=_h(s_e["token"]),
                     json={"assignmentId": e_a.id, "ref": pr["headSha"]})
    assert ro.status_code == 200 and Path(ro.json()["path"], "docs-page.md").exists()
    steal = client.post("/api/dp/repo/checkout", headers=_h(s_e["token"]),
                        json={"assignmentId": e_a.id})
    assert steal.status_code == 403
    assert steal.json()["error"]["code"] == "GRANT_DENIED"

    def tools_for(session):
        r = client.post("/api/dp/mcp", headers=_h(session["token"]),
                        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        return {t["name"] for t in r.json()["result"]["tools"]}

    assert {"repo_checkout", "repo_pr"} <= tools_for(s_w)
    assert "repo_merge_request" not in tools_for(s_w)
    editor_tools = tools_for(s_e)
    assert "repo_checkout" in editor_tools and "repo_pr" not in editor_tools
    assert "repo_merge_request" in tools_for(s_lead)


def test_pr_artifact_content_round_trips(client, pod):
    """The stored PullRequest artifact is the §8 shape, fetchable by its producer."""
    eng = pod["engine"]
    be_a = pod["be_a"]
    eng.mark_intake_complete(be_a.id)
    eng.declare_plan(be_a.id, [{"title": "implement"}])
    wt = client.post("/api/dp/repo/checkout", headers=_h(pod["s_be"]["token"]),
                     json={"assignmentId": be_a.id}).json()
    Path(wt["path"], "app", "export.py").write_text("CSV = 'v1'\n", encoding="utf-8")
    resp = client.post("/api/dp/repo/pr", headers=_h(pod["s_be"]["token"]),
                       json={"assignmentId": be_a.id, "testOutput": "unit: 9 passed"}).json()

    import base64

    got = client.get(f"/api/dp/artifacts?ref={resp['ref']}",
                     headers=_h(pod["s_be"]["token"])).json()
    body = json.loads(base64.b64decode(got["contentBase64"]))
    assert set(body) == {"branch", "baseSha", "headSha", "diff", "testOutput"}
    assert got["meta"]["type"] == "PullRequest"


# ------------------------------------------------------------- F8: per-team repo source
def test_per_team_repo_source_binds_without_restart(client, make_org, tmp_path):
    """F8: an team bound to its own source repo clones THAT repo as its work target — set at
    runtime through the operator API, no boot config involved; an unbound team keeps the
    fixture fallback unchanged."""
    import subprocess

    from canopy_server.deps import get_repos

    def git(cwd, *args):
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)

    src = tmp_path / "proj"
    src.mkdir()
    (src / "README.md").write_text("the real project\n", encoding="utf-8")
    git(src, "init", "-b", "main")
    git(src, "config", "user.email", "t@t")
    git(src, "config", "user.name", "t")
    git(src, "add", "-A")
    git(src, "commit", "-m", "init")

    bound = make_org(seed={"kind": "root", "roleKey": "engineering-lead"}, name="Bound")
    plain = make_org(seed={"kind": "root", "roleKey": "engineering-lead"}, name="Plain")

    # Bind through the operator API; a non-repo path fails loud at bind time.
    bad = client.put(f"/api/teams/{bound['id']}/repo-source",
                     json={"source": str(tmp_path / "nope")})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "BAD_REPO_SOURCE"
    r = client.put(f"/api/teams/{bound['id']}/repo-source",
                   json={"source": str(src)})
    assert r.status_code == 200 and r.json()["source"] == str(src)
    assert client.get(f"/api/teams/{bound['id']}/repo-source").json()["source"] == str(src)

    repos = get_repos()
    bound_repo = repos.ensure_repo(bound["id"])
    assert bound_repo.name == "proj" and (bound_repo / "README.md").is_file()
    plain_repo = repos.ensure_repo(plain["id"])
    assert plain_repo.name == "target-app"  # fixture fallback untouched

    # Clearing the binding restores the fallback for FUTURE materialization.
    r = client.put(f"/api/teams/{bound['id']}/repo-source", json={"source": None})
    assert r.status_code == 200 and r.json()["source"] is None
    assert client.get(f"/api/teams/{bound['id']}/repo-source").json()["source"] is None
