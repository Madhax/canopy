"""Event triggers (docs/design/standing-orgs.md): the golden vectors of §8 — fire once per
event, oldest-first capped, cursor frozen on failure, nothing consumed while down, template
rendering, and the route validations. All offline: GitHub is a stub client."""

from __future__ import annotations

from types import SimpleNamespace


class FakeGitHub:
    """Duck-typed stand-in for GitHubClient: canned issues, honoring labels/since minimally."""

    def __init__(self, issues=None, fail=False):
        self.issues = issues or []
        self.fail = fail

    def list_issues(self, token, owner, repo, *, state="open", labels=None, since=None,
                    per_page=50):
        if self.fail:
            from canopy_server.github_client import GitHubError
            raise GitHubError(401, "bad credentials")
        out = [i for i in self.issues if i.get("state", "open") == state]
        if labels:
            out = [i for i in out
                   if set(labels) <= {lbl["name"] for lbl in i.get("labels", [])}]
        if since:
            out = [i for i in out if i.get("updated_at", "") >= since]
        return out

    def get_repo(self, token, owner, repo):
        return {"full_name": f"{owner}/{repo}"}


def _issue(n, title, *, labels=(), created="2026-08-08T00:00:00Z", updated=None):
    return {
        "number": n, "title": title, "state": "open", "body": f"body of #{n}",
        "html_url": f"https://github.com/acme/canopy/issues/{n}",
        "labels": [{"name": lbl} for lbl in labels],
        "user": {"login": "reporter"},
        "created_at": created, "updated_at": updated or created,
    }


class FakeActuator:
    def __init__(self, state="live"):
        self.state = state

    def get_current(self, org_id):
        if self.state is None:
            return None
        return SimpleNamespace(id="act_trigtest", state=self.state)


def _scheduler(client, org, github, *, actuator=None, max_per_pass=3):
    from canopy_server.catalog import get_catalog
    from canopy_server.deps import (
        get_activity,
        get_connector_store,
        get_engine,
        get_secret_store,
        get_work_store,
    )
    from canopy_server.engine.triggers import TriggerScheduler

    return TriggerScheduler(
        get_work_store(), get_engine(), actuator or FakeActuator(),
        get_connector_store(), get_secret_store(), github, get_catalog(),
        activity=get_activity(), max_per_pass=max_per_pass,
    )


def _setup(client, make_org, *, labels=("bug",)):
    org = make_org(seed={"kind": "formation", "formationKey": "product-engineering-pod"})
    oid = org["id"]
    r = client.post(f"/api/organizations/{oid}/connectors", json={
        "packKey": "github", "name": "canopy repo",
        "config": {"owner": "acme", "repo": "canopy"},
        "secrets": {"scm-token": "ghp_test"},
        "enabledGrants": ["connector.github.issues.read"],
    })
    assert r.status_code == 201, r.text
    inst = r.json()
    r = client.post(f"/api/organizations/{oid}/triggers", json={
        "name": "bug intake", "instanceId": inst["id"],
        "intentTemplate": "Fix the bug in {{url}}: {{title}}\n\n{{body}}",
        "config": {"labels": list(labels), "createdAfter": "2026-01-01T00:00:00Z"},
    })
    assert r.status_code == 201, r.text
    return org, inst, r.json()


# ------------------------------------------------------------------ firing
def test_fires_once_per_issue_with_provenance(client, make_org):
    from canopy_server.deps import get_work_store

    org, _inst, trig = _setup(client, make_org)
    gh = FakeGitHub([_issue(1, "crash on save", labels=["bug"]),
                     _issue(2, "not a bug", labels=["question"])])
    sched = _scheduler(client, org, gh)

    fired = sched.run_once()
    assert len(fired) == 1
    intent = fired[0]
    assert intent.triggerId == trig["id"] and intent.externalKey == "issue:1"
    assert "crash on save" in intent.text and "issues/1" in intent.text
    assert intent.createdBy == "trigger"
    # Downstream-indistinguishable: the root assignment routes to the operator.
    a = get_work_store().get_assignment(intent.rootAssignmentId)
    assert a.issuedBy == "operator"

    # Second pass: the ledger holds — nothing re-fires, even with the cursor wiped.
    assert sched.run_once() == []
    get_work_store().mark_trigger_checked(trig["id"], cursor={"since": None})
    assert sched.run_once() == []

    # The intent list carries the ⚡ provenance fields.
    listed = client.get(f"/api/organizations/{org['id']}/intents").json()["intents"]
    assert listed[0]["triggerId"] == trig["id"] and listed[0]["externalKey"] == "issue:1"


def test_burst_drains_capped_oldest_first(client, make_org):
    org, _inst, _trig = _setup(client, make_org)
    gh = FakeGitHub([_issue(n, f"bug {n}", labels=["bug"],
                            created=f"2026-08-0{n}T00:00:00Z") for n in range(1, 6)])
    sched = _scheduler(client, org, gh, max_per_pass=2)

    first = sched.run_once()
    assert [i.externalKey for i in first] == ["issue:1", "issue:2"]  # oldest first, capped
    second = sched.run_once()
    assert [i.externalKey for i in second] == ["issue:3", "issue:4"]
    assert [i.externalKey for i in sched.run_once()] == ["issue:5"]
    assert sched.run_once() == []  # drained


def test_failure_freezes_cursor_and_dedupes_the_warning(client, make_org):
    from canopy_server.deps import get_work_store

    org, _inst, trig = _setup(client, make_org)
    ok = FakeGitHub([_issue(1, "first", labels=["bug"])])
    sched = _scheduler(client, org, ok)
    sched.run_once()
    cursor_before = get_work_store().get_trigger(trig["id"]).cursor

    bad = _scheduler(client, org, FakeGitHub(fail=True))
    bad.run_once()
    t = get_work_store().get_trigger(trig["id"])
    assert t.lastError and "bad credentials" in t.lastError
    assert t.cursor == cursor_before  # frozen on failure
    bad.run_once()  # the warning dedupes per failure streak
    notes = client.get(f"/api/organizations/{org['id']}/notifications").json()["notifications"]
    assert sum(1 for n in notes if n["kind"] == "trigger-error") == 1

    # Recovery: a new matching issue fires; the error clears.
    ok2 = FakeGitHub([_issue(1, "first", labels=["bug"]),
                      _issue(2, "second", labels=["bug"],
                             created="2026-08-08T01:00:00Z")])
    fired = _scheduler(client, org, ok2).run_once()
    assert [i.externalKey for i in fired] == ["issue:2"]
    assert get_work_store().get_trigger(trig["id"]).lastError is None


def test_nothing_consumed_while_not_actuated(client, make_org):
    """Events are durable — unlike cadence occurrences, a down org drops nothing."""
    org, _inst, _trig = _setup(client, make_org)
    gh = FakeGitHub([_issue(1, "while down", labels=["bug"])])
    down = _scheduler(client, org, gh, actuator=FakeActuator(state=None))
    assert down.run_once() == []
    stopped = _scheduler(client, org, gh, actuator=FakeActuator(state="stopped"))
    assert stopped.run_once() == []
    up = _scheduler(client, org, gh)
    assert [i.externalKey for i in up.run_once()] == ["issue:1"]


def test_check_now_and_dry_run(client, make_org, monkeypatch):
    org, _inst, trig = _setup(client, make_org)
    gh = FakeGitHub([_issue(7, "dry me", labels=["bug"])])
    sched = _scheduler(client, org, gh)
    import canopy_server.deps as deps
    monkeypatch.setattr(deps, "get_trigger_scheduler", lambda: sched)

    oid = org["id"]
    dry = client.post(f"/api/organizations/{oid}/triggers/{trig['id']}/dry-run").json()
    assert [c["key"] for c in dry["candidates"]] == ["issue:7"]
    assert "dry me" in dry["renderedFirst"]
    # Dry run fired nothing.
    assert client.get(f"/api/organizations/{oid}/intents").json()["intents"] == []

    res = client.post(f"/api/organizations/{oid}/triggers/{trig['id']}/check").json()
    assert res["candidates"] == 1 and len(res["fired"]) == 1


# ------------------------------------------------------------------ validation
def test_trigger_route_validations(client, make_org):
    org = make_org()
    oid = org["id"]
    # An instance WITHOUT issues.read enabled is not a valid source.
    r = client.post(f"/api/organizations/{oid}/connectors", json={
        "packKey": "github", "name": "no-issues",
        "config": {"owner": "a", "repo": "b"},
        "enabledGrants": ["connector.github.repo.read"],
    })
    inst = r.json()
    body = {"name": "t", "instanceId": inst["id"], "intentTemplate": "x {{title}}"}
    r = client.post(f"/api/organizations/{oid}/triggers", json=body)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "BAD_TRIGGER_SOURCE"

    client.put(f"/api/organizations/{oid}/connectors/{inst['id']}", json={
        "enabledGrants": ["connector.github.repo.read", "connector.github.issues.read"],
    })
    assert client.post(f"/api/organizations/{oid}/triggers", json=body).status_code == 201

    # Unknown placeholder and unknown kind fail loud.
    r = client.post(f"/api/organizations/{oid}/triggers",
                    json={**body, "intentTemplate": "x {{issueTitle}}"})
    assert r.json()["error"]["code"] == "BAD_TEMPLATE"
    r = client.post(f"/api/organizations/{oid}/triggers", json={**body, "kind": "rss"})
    assert r.json()["error"]["code"] == "BAD_TRIGGER"

    # Delete removes the source; its intents (none here) would stay.
    trig = client.get(f"/api/organizations/{oid}/triggers").json()["triggers"][0]
    assert client.delete(
        f"/api/organizations/{oid}/triggers/{trig['id']}"
    ).status_code == 204
