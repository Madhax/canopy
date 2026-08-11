"""Team revisions — every overwrite is one restore away (revisions.py).

Born from a live incident: an accidental formation stamp autosaved over a real team
within a second. The revision log makes every destructive write (save, restore, delete)
snapshot the version it replaces, so no accident is a loss.
"""

from __future__ import annotations


def _save(client, team, mutate):
    doc = dict(team)
    mutate(doc)
    r = client.put(f"/api/teams/{team['id']}", json=doc)
    assert r.status_code == 200, r.text
    return r.json()["document"]


def test_save_snapshots_the_replaced_version(client, make_org):
    team = make_org(name="Governance")
    v2 = _save(client, team, lambda d: d.update(name="Governance v2"))

    revs = client.get(f"/api/teams/{team['id']}/revisions").json()["revisions"]
    assert len(revs) == 1
    assert revs[0]["reason"] == "save" and revs[0]["name"] == "Governance"

    # A no-op save (content unchanged) records nothing.
    _save(client, v2, lambda d: None)
    revs = client.get(f"/api/teams/{team['id']}/revisions").json()["revisions"]
    assert len(revs) == 1


def test_restore_brings_the_old_version_back_and_is_itself_undoable(client, make_org):
    team = make_org(name="Original")
    _save(client, team, lambda d: d.update(name="Accident"))
    revs = client.get(f"/api/teams/{team['id']}/revisions").json()["revisions"]
    (rev,) = revs

    r = client.post(f"/api/teams/{team['id']}/revisions/{rev['id']}/restore")
    assert r.status_code == 200, r.text
    assert r.json()["document"]["name"] == "Original"
    assert client.get(f"/api/teams/{team['id']}").json()["name"] == "Original"

    # The restore snapshotted the version it replaced — the "accident" is still there.
    revs = client.get(f"/api/teams/{team['id']}/revisions").json()["revisions"]
    reasons = [x["reason"] for x in revs]
    assert reasons[0] == "restore" and revs[0]["name"] == "Accident"


def test_deleted_team_is_recoverable(client, make_org):
    team = make_org(name="Doomed")
    assert client.delete(f"/api/teams/{team['id']}").status_code == 204
    assert client.get(f"/api/teams/{team['id']}").status_code == 404

    revs = client.get(f"/api/teams/{team['id']}/revisions").json()["revisions"]
    assert revs and revs[0]["reason"] == "delete" and revs[0]["name"] == "Doomed"

    r = client.post(f"/api/teams/{team['id']}/revisions/{revs[0]['id']}/restore")
    assert r.status_code == 200
    assert client.get(f"/api/teams/{team['id']}").json()["name"] == "Doomed"


def test_retention_caps_at_twenty(client, make_org):
    team = make_org(name="Busy v0")
    doc = team
    for i in range(1, 25):
        doc = _save(client, doc, lambda d, i=i: d.update(name=f"Busy v{i}"))
    revs = client.get(f"/api/teams/{team['id']}/revisions").json()["revisions"]
    assert len(revs) == 20
    # Newest-first; the oldest snapshots fell off.
    assert revs[0]["name"] == "Busy v23"


def test_unknown_revision_404s(client, make_org):
    team = make_org()
    r = client.post(f"/api/teams/{team['id']}/revisions/rv_missing/restore")
    assert r.status_code == 404
