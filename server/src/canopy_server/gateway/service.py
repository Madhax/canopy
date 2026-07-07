"""The gateway service: resolve → budget → dispatch → meter → spend.

This is the hot path and one of the two mediation chokepoints. The ordering is load-bearing:
the **budget is checked before the provider is ever called** (invariant 7), the credential is
resolved server-side from the run token and never returned (invariant 10), and every call becomes
a Step + SpendEvent so cost is analyzable, not merely accounted (domain Economics).
"""

from __future__ import annotations

import asyncio
import time

from pydantic import BaseModel

from ..activity import ActivityLog
from ..db import Db, register_schema
from ..deps import now_iso
from ..ids import new_step_id
from ..ledger import BudgetExhausted, BudgetLedger, Meter
from ..profiles import ProfileStore
from ..runtokens import RunTokenStore
from ..secretstore import SecretStore
from .base import CompletionRequest, ModelGateway, StepKind, ToolCall, ValidationResult
from .providers import ProviderError, provider_registry

SCHEMA = """
CREATE TABLE IF NOT EXISTS gateway_step (
    id            TEXT PRIMARY KEY,
    actuation_id  TEXT NOT NULL,
    node_id       TEXT NOT NULL,
    task_id       TEXT,
    provider      TEXT NOT NULL,
    model         TEXT NOT NULL,
    kind          TEXT NOT NULL DEFAULT 'production',
    input_tokens  INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    duration_ms   INTEGER NOT NULL,
    stop_reason   TEXT NOT NULL,
    delta_note    TEXT,
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_step_node ON gateway_step (actuation_id, node_id);
"""
register_schema(SCHEMA)


class GatewayError(Exception):
    status = 500
    code = "GATEWAY_ERROR"

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class GatewayAuthError(GatewayError):
    status = 401
    code = "RUN_TOKEN_INVALID"


class GatewayConfigError(GatewayError):
    def __init__(self, code: str, message: str):
        self.code = code
        self.status = 422
        super().__init__(message)


class GatewayProviderError(GatewayError):
    status = 502
    code = "PROVIDER_ERROR"


class GatewayBudgetExhausted(GatewayError):
    status = 402
    code = "BUDGET_EXHAUSTED"

    def __init__(self, meter_id: str):
        self.meterId = meter_id
        super().__init__(f"budget exhausted for meter {meter_id}")


class MeterView(BaseModel):
    id: str
    allowance: int
    spent: int
    reserved: int
    state: str
    warnThresholdPct: float
    warned: bool

    @classmethod
    def of(cls, m: Meter) -> MeterView:
        return cls(
            id=m.id, allowance=m.allowance, spent=m.spent, reserved=m.reserved, state=m.state,
            warnThresholdPct=m.warnThresholdPct, warned=m.warned,
        )


class GatewayResult(BaseModel):
    text: str
    toolCalls: list[ToolCall]
    inputTokens: int
    outputTokens: int
    stopReason: str
    stepId: str
    provider: str
    model: str
    kind: StepKind
    estCostMicros: int
    priceKnown: bool  # False → the model is missing from the price table; cost shown as 0
    crossedWarn: bool
    meter: MeterView


def _est_input_tokens(req: CompletionRequest) -> int:
    chars = len(req.system) + sum(len(m.content) for m in req.messages)
    return max(1, chars // 4)


class DefaultModelGateway(ModelGateway):
    def __init__(
        self,
        db: Db,
        profiles: ProfileStore,
        secrets: SecretStore,
        ledger: BudgetLedger,
        runtokens: RunTokenStore,
        activity: ActivityLog,
        *,
        prices: dict,
        concurrency: dict[str, int],
    ):
        self.db = db
        self.profiles = profiles
        self.secrets = secrets
        self.ledger = ledger
        self.runtokens = runtokens
        self.activity = activity
        self.prices = prices
        self._concurrency = concurrency
        self._providers = {k: provider_registry.create(k) for k in provider_registry.keys()}
        self._sems: dict[str, asyncio.Semaphore] = {}

    def _sem(self, provider: str) -> asyncio.Semaphore:
        if provider not in self._sems:
            cap = int(self._concurrency.get(provider, 8))
            self._sems[provider] = asyncio.Semaphore(cap)
        return self._sems[provider]

    def _price(self, provider: str, model: str, in_tok: int, out_tok: int) -> tuple[int, bool]:
        entry = self.prices.get(provider, {}).get(model)
        if not entry:
            return 0, False
        usd = in_tok / 1_000_000 * entry.get("input", 0) + out_tok / 1_000_000 * entry.get(
            "output", 0
        )
        return round(usd * 1_000_000), True

    async def complete(self, run_token, req, *, kind="production", task_id=None) -> GatewayResult:
        rec = self.runtokens.resolve(run_token)
        if rec is None:
            raise GatewayAuthError("unknown or revoked run token")

        binding = self.profiles.get_binding_for_node(rec.orgId, rec.nodeId, rec.orgPath)
        if binding is None:
            raise GatewayConfigError("BINDING_MISSING", f"node {rec.nodeId} has no profile binding")
        profile = self.profiles.get_profile(binding.profileId)
        if profile is None:
            raise GatewayConfigError("PROFILE_DANGLING", "binding points at a missing profile")

        meter_id = task_id and self._meter_for_task(rec.actuationId, rec.nodeId, task_id)
        meter_id = meter_id or rec.defaultMeterId
        if not meter_id:
            raise GatewayConfigError("NO_METER", "no funded meter for this node (invariant 7)")

        cred = self.secrets.reveal(profile.apiKeySecretId) if profile.apiKeySecretId else None

        # The agent's requested output cap is clamped by the profile's — an agent cannot ask for
        # more than its configuration allows. Reserve an upper bound (input estimate + max output)
        # so the pre-dispatch budget check can never be undershot.
        effective_max = min(req.maxOutputTokens or profile.params.maxOutputTokens,
                            profile.params.maxOutputTokens)
        req = req.model_copy(update={"maxOutputTokens": effective_max})
        estimate = _est_input_tokens(req) + effective_max
        try:
            reservation = self.ledger.reserve(meter_id, estimate)
        except BudgetExhausted as exc:
            self.activity.log(
                "system", "budget.hard_stop", org_id=rec.orgId,
                subject_ids=[rec.nodeId, meter_id],
                payload={"actuationId": rec.actuationId, "reason": "reserve"},
            )
            raise GatewayBudgetExhausted(exc.meter_id) from exc

        provider = self._providers[profile.provider]
        started = time.perf_counter()
        try:
            async with self._sem(profile.provider):
                result = await provider.complete(
                    req, cred, model=profile.model, endpoint=profile.endpoint
                )
        except ProviderError as exc:
            self.ledger.release(reservation)
            raise GatewayProviderError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - never leak a reservation on an unexpected error
            self.ledger.release(reservation)
            raise GatewayProviderError(f"unexpected provider failure: {exc}") from exc
        duration_ms = int((time.perf_counter() - started) * 1000)

        est_cost, price_known = self._price(
            profile.provider, profile.model, result.inputTokens, result.outputTokens
        )
        step_id = new_step_id()
        outcome = self.ledger.record(
            meter_id,
            step_id=step_id,
            org_id=rec.orgId,
            node_id=rec.nodeId,
            actuation_id=rec.actuationId,
            provider=profile.provider,
            model=profile.model,
            input_tokens=result.inputTokens,
            output_tokens=result.outputTokens,
            est_cost_micros=est_cost,
            reserved=reservation.amount,
            task_id=task_id,
        )
        self._insert_step(
            step_id, rec.actuationId, rec.nodeId, task_id, profile.provider, profile.model,
            kind, result.inputTokens, result.outputTokens, duration_ms, result.stopReason,
        )
        if outcome.crossedWarn:
            self.activity.log(
                "system", "budget.warn", org_id=rec.orgId, subject_ids=[rec.nodeId, meter_id],
                payload={"spent": outcome.meter.spent, "allowance": outcome.meter.allowance},
            )
        if outcome.exhausted:
            self.activity.log(
                "system", "budget.hard_stop", org_id=rec.orgId,
                subject_ids=[rec.nodeId, meter_id],
                payload={"actuationId": rec.actuationId, "reason": "record"},
            )

        return GatewayResult(
            text=result.text,
            toolCalls=result.toolCalls,
            inputTokens=result.inputTokens,
            outputTokens=result.outputTokens,
            stopReason=result.stopReason,
            stepId=step_id,
            provider=profile.provider,
            model=profile.model,
            kind=kind,
            estCostMicros=est_cost,
            priceKnown=price_known,
            crossedWarn=outcome.crossedWarn,
            meter=MeterView.of(outcome.meter),
        )

    async def validate_profile(self, profile_id: str) -> ValidationResult:
        profile = self.profiles.get_profile(profile_id)
        if profile is None:
            return ValidationResult(ok=False, error="no such profile")
        cred = self.secrets.reveal(profile.apiKeySecretId) if profile.apiKeySecretId else None
        provider = self._providers[profile.provider]
        return await provider.validate(model=profile.model, cred=cred, endpoint=profile.endpoint)

    # -- helpers ------------------------------------------------------------ #
    def _meter_for_task(self, actuation_id: str, node_id: str, task_id: str) -> str | None:
        # A4 opens a fresh meter per delivered task; until then this is unused (A1 uses the
        # node's default meter). Kept so the resolution order is already task-first.
        return None

    def _insert_step(
        self, step_id, actuation_id, node_id, task_id, provider, model, kind, in_tok, out_tok,
        duration_ms, stop_reason,
    ) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO gateway_step (id, actuation_id, node_id, task_id, provider, model, "
                "kind, input_tokens, output_tokens, duration_ms, stop_reason, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (step_id, actuation_id, node_id, task_id, provider, model, kind, in_tok, out_tok,
                 duration_ms, stop_reason, now_iso()),
            )
