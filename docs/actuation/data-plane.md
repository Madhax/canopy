# Data Plane — A2A Communication, Mediated Routing, and the Distribution Bus

## 1. Protocol choice: A2A, mediated

Agents speak **A2A (Agent2Agent) v1.0** — Agent Cards for identity/capability discovery, stateful Tasks with a defined lifecycle (`working / input-required / completed / failed / canceled / rejected`), Messages with typed Parts, Artifacts as task outputs, JSON-RPC-over-HTTP binding (the v1 transport; gRPC is a later option), via the official Python SDK (`a2a-sdk`). Each Canopy agent runs an A2A **server**; managers act as A2A **clients** toward their reports and vice-versa for escalation-shaped replies.

Two facts drive the architecture:

1. **A2A is point-to-point.** The protocol has no built-in work distribution, queueing, fan-out, or load balancing — a client sends a task to one agent. So distribution is *our* layer: the **Message Router + Bus** below. A2A remains the *envelope* (task semantics, artifacts, lifecycle); the bus is the *delivery substrate*. This is exactly the "each report subscribes to its manager" pub/sub seam — modeled so the v1 local implementation and a future managed pub/sub are the same abstraction.
2. **The domain forbids unmediated channels** (invariant 3: communication follows the chart; the platform mediates everything). Therefore agents never dial each other's endpoints. Every A2A message is POSTed to the control plane's router, which validates the channel against the chart and forwards. Agents don't even know peer addresses — only node ids.

```
manager runtime                    CONTROL PLANE                          report runtime
──────────────                     ─────────────                          ──────────────
a2a task (JSON-RPC)  ──────▶  Router: authenticate sender,
  to node a_qa01               check channel (manager↔report?),
                               log envelope, enqueue          ──────▶  Bus queue: agent.a_qa01.inbox
                                                                            │ (delivery worker)
                                                              ──────▶  forward to report's local
                                                                        A2A server (127.0.0.1:port)
              ◀──────  task status / artifacts flow back the same mediated path
```

## 2. Channel model

Derived from the actuated chart, held in `router.channels`:

- `manager↔report` — always, both directions (delegation down, delivery/escalation up).
- `operator↔any` — the operator (UI/API) may address any node; intents enter here, targeting the root by default.
- `team broadcast` — a manager may send one message to all its reports (fan-out done by the router, N queue entries — the first place the bus visibly beats point-to-point).
- Everything else is **rejected** (`403 CHANNEL_FORBIDDEN` with the domain's own explanation: route via the common manager). Sibling data flows through artifact refs delivered by the manager, not peer messages. Brokered channels and cross-team grants are phase-3 features and get channel rows when they arrive — the enforcement point already exists.

Nested orgs: the child org's root has a channel to its mount agent (it "looks like any other report"); no channel crosses into a child org's internals (sub-org opacity, enforced here too).

## 3. The Bus abstraction (the scalability seam)

```python
class Bus(ABC):
    async def publish(self, topic: str, envelope: Envelope) -> str: ...        # returns message id
    async def poll(self, topic: str, consumer: str, max_n: int, ttl: s) -> list[Delivery]: ...
    async def ack(self, delivery_id: str) -> None: ...                         # at-least-once + ack
    async def nack(self, delivery_id: str, requeue: bool) -> None: ...
```

Topics in v1: one durable inbox per agent (`act.<actuationId>.agent.<nodeId>.inbox`). Semantics: **at-least-once, per-topic FIFO**, visibility timeout on poll, dead-letter after N nacks (dead-letters surface as activity events → operator).

**v1 implementation — `SqliteBus`:** a `router.queues` table (`topic, seq, envelope, state, locked_until, attempts`) with `SELECT ... WHERE state='ready' ORDER BY seq LIMIT n` under a transaction. Delivery workers inside the control-plane process poll ready messages and forward to the target agent's A2A server; an agent marked `engaged` or `paused` in the directory simply isn't delivered to until it heartbeats `idle` — queueing gives us the domain's "one executing assignment at a time; a growing queue is a visible bottleneck" for free (queue depth per node is surfaced on the live chart).

**Future implementations** (same ABC; see `roadmap.md`): Redis Streams, NATS JetStream (self-hosted scale-out), GCP Pub/Sub or SQS (managed), at which point delivery workers move out-of-process and agents on other hosts receive via A2A push notifications (the protocol's webhook mechanism) instead of local forwards.

Why not "reports literally subscribe to a manager topic"? Because Canopy delegation is *addressed*, not anonymous work-stealing — a manager assigns *this* task to *this* report (single-assignee, domain rule). Per-report inboxes preserve that. The pattern you described is still reachable for pooled roles later: a `team.<managerId>.pool` topic with competing consumers is one more topic shape on the same Bus, listed in the roadmap as **work pools**.

## 4. Envelope and task mapping

The router carries opaque-ish envelopes: `{ id, actuationId, fromNodeId, toNodeId, kind: "a2a", a2aPayload, taskRef?, ts }`. Domain mapping (phase-2 subset):

| Domain concept | A2A realization |
|---|---|
| Intent (operator → root) | new A2A task; `message.metadata.canopy = { kind: "intent", intentId }` |
| Delegation (manager → report) | new A2A task on the report; metadata `{ kind: "delegation", parentTaskId, briefArtifactRefs[] }` |
| Deliverable (report → manager) | task completion; A2A artifact parts carry `org://` refs (never inline blobs > 64KB) |
| Status nudge / re-brief | `message/send` on the existing task |
| Rejection of defective brief | task `rejected` state + reason message (ClarificationGate proper is phase 3) |
| Escalation-shaped question | `input-required` on the child task, question in the status message; manager answers with `message/send` (EscalationGate proper is phase 3) |

Task ids are minted by the receiving agent per A2A; the router records the mapping `(a2aTaskId ↔ canopy taskRef ↔ parent taskRef)` so the control plane can render the intent's task tree and attribute spend without parsing agent conversations.

## 5. Scalability posture

v1 is one host, dozens of agents — SQLite FIFO + local HTTP is comfortably sufficient. The scaling story is: (1) bus backend swap (managed pub/sub) removes the delivery bottleneck; (2) sandbox provider swap distributes agents across hosts/containers; (3) router extraction makes mediation horizontally scalable (stateless workers over the shared bus); (4) work pools add competing-consumer distribution where roles are fungible. Nothing in the agent runtime changes across any of these — that is the test the design must keep passing.
