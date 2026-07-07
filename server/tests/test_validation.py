"""The authoritative validator must reproduce every golden vector exactly.

Vectors live in ``testdata/validation/*.json`` and are shared with the TypeScript validator
(docs/org-chart-editor.md §5.4). Both sides normalize issues the same way and must agree.
"""

import json
from pathlib import Path

import pytest

from canopy_server.catalog import get_catalog
from canopy_server.models import Organization
from canopy_server.validation import validate_organization
from canopy_server.validation.codes import ACTUATION_CODES, CODE_MESSAGES

VECTOR_DIR = Path(__file__).resolve().parents[2] / "testdata" / "validation"


def normalize_issue(issue: dict) -> dict:
    out = {"severity": issue["severity"], "code": issue["code"]}
    if issue.get("agentIds"):
        out["agentIds"] = sorted(issue["agentIds"])
    if issue.get("dependencyIds"):
        out["dependencyIds"] = sorted(issue["dependencyIds"])
    if issue.get("orgPath"):
        out["orgPath"] = issue["orgPath"]
    return out


def sort_key(issue: dict) -> str:
    return f"{issue['code']}|" + json.dumps(issue, sort_keys=True)


def load_vectors() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(VECTOR_DIR.glob("*.json"))]


VECTORS = load_vectors()


def test_vectors_present():
    assert VECTORS, "no golden vectors found in testdata/validation"


@pytest.mark.parametrize("vector", VECTORS, ids=[v["name"] for v in VECTORS])
def test_validator_matches_vector(vector):
    catalog = get_catalog()
    org = Organization.model_validate(vector["document"])
    issues = validate_organization(org, vector["mode"], catalog)
    actual = sorted((normalize_issue(i.to_dict()) for i in issues), key=sort_key)
    expected = sorted((normalize_issue(i) for i in vector["expectedIssues"]), key=sort_key)
    assert actual == expected, f"{vector['name']}: validator output diverged from vector"


def test_every_rule_code_has_a_vector():
    seen = {ni["code"] for v in VECTORS for ni in v["expectedIssues"]}
    # Actuation-readiness codes are checked at actuate time, not against a document.
    missing = set(CODE_MESSAGES) - seen - ACTUATION_CODES
    assert not missing, f"rule codes with no vector coverage: {sorted(missing)}"
