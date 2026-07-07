"""Contract fixtures parsed by the pydantic side (risk AR-2).

The same files are parsed by the UI's Zod schemas in
``ui/src/schema/actuation.contract.test.ts``. If a field drifts on one side, one suite fails.
"""

from __future__ import annotations

import json
from pathlib import Path

from canopy_server.gateway.base import CompletionRequest, CompletionResult
from canopy_server.profiles import AgentBinding, AgentProfile
from canopy_server.secretstore import SecretMeta

CONTRACTS = Path(__file__).resolve().parents[2] / "testdata" / "contracts"


def _load(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def test_agent_profile_contract():
    p = AgentProfile.model_validate(_load("agent_profile.json"))
    assert p.provider == "anthropic" and p.params.maxOutputTokens == 8192


def test_agent_binding_contract():
    b = AgentBinding.model_validate(_load("agent_binding.json"))
    assert b.agentNodeId == "a_k7mp2x9q" and b.orgPath == []


def test_secret_meta_contract():
    s = SecretMeta.model_validate(_load("secret_meta.json"))
    assert s.name == "anthropic-key"
    # Metadata only — the shape has no field that could carry a plaintext key.
    assert not hasattr(s, "value") and not hasattr(s, "ciphertext")


def test_completion_request_contract():
    r = CompletionRequest.model_validate(_load("completion_request.json"))
    assert r.messages[0].role == "user" and r.tools[0].name == "write_file"


def test_completion_result_contract():
    r = CompletionResult.model_validate(_load("completion_result.json"))
    assert r.toolCalls[0].name == "produce_artifact" and r.outputTokens == 340
