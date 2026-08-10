"""The v1→v2 document migrator, contract-tested against both vector generations.

``testdata/validation-v1/`` holds the frozen v1 golden vectors (kind ``canopy.organization``,
``childOrganizations[].organization``); ``testdata/validation/`` holds the same vectors at v2.
The migrator must map each v1 document exactly onto its v2 twin — that is the "v1 import
accepted indefinitely" promise (design/organizations/07 §2.2), pinned.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from canopy_server.migrate import UnsupportedSchemaVersion, migrate_team
from canopy_server.models import SCHEMA_VERSION, Team

V1_DIR = Path(__file__).resolve().parents[2] / "testdata" / "validation-v1"
V2_DIR = Path(__file__).resolve().parents[2] / "testdata" / "validation"


def _names() -> list[str]:
    return sorted(p.stem for p in V1_DIR.glob("*.json"))


def test_v1_vectors_present():
    assert len(_names()) >= 20


@pytest.mark.parametrize("name", _names())
def test_v1_document_migrates_to_its_v2_twin(name: str):
    v1 = json.loads((V1_DIR / f"{name}.json").read_text(encoding="utf-8"))["document"]
    v2 = json.loads((V2_DIR / f"{name}.json").read_text(encoding="utf-8"))["document"]
    assert migrate_team(v1) == v2


@pytest.mark.parametrize("name", _names())
def test_migrated_v1_parses_as_team(name: str):
    v1 = json.loads((V1_DIR / f"{name}.json").read_text(encoding="utf-8"))["document"]
    team = Team.model_validate(migrate_team(v1))
    assert team.kind == "canopy.team"
    assert team.schemaVersion == SCHEMA_VERSION


def test_migration_is_idempotent():
    v1 = json.loads((V1_DIR / "child-invalid.json").read_text(encoding="utf-8"))["document"]
    once = migrate_team(json.loads(json.dumps(v1)))
    assert migrate_team(json.loads(json.dumps(once))) == once


def test_future_version_is_a_hard_error():
    with pytest.raises(UnsupportedSchemaVersion):
        migrate_team({"kind": "canopy.team", "schemaVersion": SCHEMA_VERSION + 1})
