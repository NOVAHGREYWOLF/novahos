# Nova/LeadFuel — Ecosystem Production Game Plan (batched)

> The suite of apps **is** the agent fleet the NOVAH documents describe. The
> **foundation is shared** (the `novahos` kernel + the `novahub` hub) — never copied
> into an app. **Echo is one agent** (NOVAH, "the Prime"): the digital twin that talks
> to every other agent over the mesh. It does **not** own the foundation. We build the
> ecosystem to resemble the docs **in batches**, reusing what already exists.
>
> Source of truth for the target architecture: `NovahPrime/ARCHITECTURE_STANDARD.md`
> (Doc 26) + `NovahPrime/APP_MANIFEST.md` (the 54-agent roster). `NovahPrime/` is the
> complete reference implementation we harvest from — not a thing we deploy.

---

## 1. Target state (what the docs describe)

- **One foundation** every app imports: Constitution + WARDEN (deterministic 8-step gate)
  + tiered auth + consent tiers + data classification/inference/lifecycle + MCP boundary
  + agent contract (manifest/registry/onboarding) + 3-tier memory + reasoning seam.
- **NOVA-PRIME orchestration**: agents *propose*, WARDEN *disposes*, the hub records an
  immutable audit trail; 30-day reversibility; agents never direct-execute outward.
- **The apps are the agents.** Each app declares its agent(s) via a manifest and runs on
  the shared foundation. The "one brain" (novahub: knowledge + memory + identity model)
  is the shared substrate they read/write.
- **Echo = NOVAH/the Prime** — the twin agent. It verifies "sounds like me", composes as
  you, and (later) coordinates with other agents on your behalf — all gated by the shared
  WARDEN, all reading/writing the one brain.

## 2. Current state (census + the gap)

**Live apps → NOVAH agents** (deployed Railway services in `LeadfuelBusinessSuites`):

| App | Maps to (NOVAH agents) | State |
|---|---|---|
| **novahub** | NOVA-PRIME (console/orchestrator), HERALD, LIBRARIAN | live; holds the brain (knowledge/memory/model) + identity + billing |
| **echo** | **NOVAH (the Prime twin)**, MIRROR, VOICEWATCH | live; voice+identity capture, compose, verifier, autonomy; on the mesh |
| **novahawk** | SENTINEL, IRIS, HERMES, ORACLE | live; email relationship intelligence |
| **smarticp** | CROESUS, PROSPECT, APOLLO | live; the ICP "profile brain" producer |
| **lucid** | ATHENA, COACH, MENTOR, PATHFINDER, SCHEDULER | live; personal+work coach |
| **novaherald** | COURIER, HERALD, PROSPECT | skeleton; outbound campaigns |
| **novahound/novahcast** | PUBLISHER, WORDSMITH, COURIER | live; LinkedIn auto-post + reply drafts |
| **leadfuel-intake** | RECEPTOR, SCRIBE, APOLLO | live; chat/voice intake → HubSpot |
| **novahos** (kernel) | WARDEN, AEGIS, VAULT (the substrate) | partial foundation |
| **wolfos** | (local NOVA-PRIME prototype) | being wound down |

**Agent gaps (no app yet):** finance — LEDGER/INVOICE/FORECAST (Plaid/Stripe); health —
HYGEIA/VITALS (HealthKit, Tier-1); building — VULCAN/DEPLOYER/CODER/TESTER/PATCHER;
capture — SCREENWATCH; security — CIPHER; content — CHRONICLE; innovation — ANALYST/ADVISOR.

**Foundation gap (the spine):** the production-grade foundation is fully implemented in
`NovahPrime/foundation/` but the *shared* kernel `novahos` has only:
- ✅ `constitution.py`, `consent.py`, `privacy.py` (production)
- 🟡 `warden.py` (risk-scoring only — missing the full 8-step validator pipeline)
- 🟡 `warden_audit.py` (DB-coupled)
- ❌ MISSING from the shared kernel: tiered/3-factor auth, data **lifecycle** + **inference
  compression**, **MCP boundary + credential vault**, **agent base/manifest/registry/
  onboarding**, **3-tier memory**, **reasoning provider**, **NOVA-PRIME orchestration**.

→ Until those move into `novahos`, every app forks the foundation. **This is Batch 1.**

## 3. Guiding principles

1. **Foundation is shared, not forked.** Deterministic primitives + agent contract + memory
   *interfaces* live in `novahos` (pip `novahos @ git+https`). Stateful shared services
   (brain/knowledge/memory store, identity, audit log, NOVA-PRIME runtime) live in `novahub`
   (called over the `X-Service-Token` mesh). **Nothing foundational lives inside Echo or any
   single app.**
2. **Apps declare themselves as agents** (manifest + config), then *consume* the kernel.
3. **Echo is one agent.** Strip anything foundation-ish from Echo (e.g. its local `guard.py`)
   and have it import the kernel like everyone else.
4. **Propose → WARDEN → act → audit**, everywhere. No outward action bypasses the gate.
5. **Batches ship value.** Each batch leaves the ecosystem working and more docs-aligned.
   Reuse first (NovahPrime code is production-ready); build only the gaps.

## 4. The batches

Each batch: **Goal · What · Where · Builds on · Outcome.**

### Batch 1 — Consolidate the foundation into the shared kernel (`novahos` v0.x)
- **Goal:** one importable foundation; answer "is the foundation there?" = yes, in one place.
- **What:** harvest from `NovahPrime/foundation/` into `novahos/`: full 8-step **WARDEN** +
  6 validators + pure audit-entry generation; **auth** (tiered/3-factor + cooling); **data**
  (lifecycle + inference compression/validation); **mcp** (boundary + credential vault);
  **agent** (base/manifest/registry/onboarding); **memory** (working/episodic/semantic
  interface); **reasoning** (provider seam). Keep `constitution/consent/privacy` as-is.
  Package: stdlib core, heavy bits behind extras; keep `leadfuel_core` shim.
- **Where:** `novahos` (the kernel). Semantic memory *interface* in novahos; its
  implementation stays in `novahub` brain (pgvector/Voyage).
- **Builds on:** `novahos` already consumed via `novahos @ git+https` by Echo/Lucid/etc.
- **Outcome:** `from novahos import Warden, Agent, AgentRegistry, ...` works; one version,
  every app. This unblocks everything else.

### Batch 2 — Agent contract: every app declares its agents
- **Goal:** the suite becomes a *discoverable* agent fleet on one foundation.
- **What:** add an `APP_MANIFEST` + per-agent `manifest.yaml` + `config/` (consent/auth/
  data/lifecycle YAML) to each live app; register agents in a shared **registry** the hub
  exposes. Start with the most agent-ready: **Echo, Lucid, NovaHawk** (then SmartICP,
  Herald, Hound, Intake).
- **Where:** per-app `agents/` + `config/`; registry endpoint in `novahub`.
- **Builds on:** Batch 1 (agent base/manifest/registry).
- **Outcome:** NOVA-PRIME can discover "who can do what" across real services.

### Batch 3 — NOVA-PRIME orchestration + agent-to-agent mesh
- **Goal:** cross-agent workflows (Planner/Executor/Verifier) across real apps.
- **What:** build the NOVA-PRIME runtime (task → plan → route to agent(s) → WARDEN-gate →
  verify → audit) and a mesh RPC (`invoke_remote(service, agent, action, payload)`). Echo
  (the Prime) plugs in as one agent that can both be called and call others.
- **Where:** orchestration runtime in `novahub` (+ thin `novahos.orchestration` contract).
- **Builds on:** Batches 1–2 + the existing `X-Service-Token` mesh.
- **Outcome:** "draft this and have NovahPrime check it sounds like me, then queue it" spans
  Intake/Hawk/Echo/Herald as gated agent calls.

### Batch 4 — Wire the foundation through every live app
- **Goal:** production-grade governance everywhere.
- **What:** replace per-app stubs (Echo `guard.py`, Lucid `guard.gate`) with the shared
  kernel WARDEN; every outward action gated + written to the immutable audit log; consent
  tiers + data classification + lifecycle enforced; episodic memory on each app.
- **Where:** each app imports `novahos`; audit/log to `novahub`.
- **Builds on:** Batches 1–3.
- **Outcome:** the whole suite is "trustworthy by construction"; compliance-testable.

### Batch 5 — Shared ingestion + the data front door (the "one brain" data path)
- **Goal:** real data flows into the one brain for *all* agents; the twin's voice gets real.
- **What:** move pull/classify/ingest into `novahub` as the shared engine (`ConnectorSync`
  + `/api/connectors/*` + `/api/connectors/{source}/sync`); add **SENT-mail** source backends
  to `novahos.sources` (Outlook Graph SentItems, Gmail `in:sent`); **Echo is the
  "connect your data" UX**; Lucid switches its sync to a mesh call. Reuse the OAuth tokens
  already in `novahub`. (Interim already shipped: Echo `/ingest/sync` pulling sent mail.)
- **Where:** engine in `novahub`; connectors in `novahos.sources`; UX in `echo`.
- **Builds on:** Batches 1–4 (privacy classify + consent gate the ingestion).
- **Outcome:** connect once → the whole fleet reads your data from one brain; NovahPrime
  drafts in your *real* voice.

### Batch 6 — Close the agent gaps the docs require
- **Goal:** materially complete the 54-agent model.
- **What:** stand up the missing domains as apps/modules on the foundation: **finance**
  (LEDGER/INVOICE/FORECAST via Plaid/Stripe), **health** (HYGEIA/VITALS via HealthKit,
  Tier-1 local), **building** (VULCAN/DEPLOYER + CODER/TESTER/PATCHER), **capture**
  (SCREENWATCH), **security** (CIPHER), **content** (CHRONICLE), **innovation**
  (ANALYST/ADVISOR). Prioritize by business value.
- **Where:** new services or modules in existing apps; all consume `novahos` + the brain.
- **Builds on:** Batches 1–5.
- **Outcome:** the ecosystem looks like the blueprint.

### Batch 7 — Compliance + production hardening
- **Goal:** production-ready, compliant, observable.
- **What:** `ARCHITECTURE_STANDARD.md §9` compliance checklist as automated tests across
  apps; audit-trail immutability; MCP boundary live tests (Tier-1 never to cloud);
  **rotate the leaked `LEADFUEL_SERVICE_TOKEN`** (outstanding) + set suite-wide; billing/
  entitlements review; logging/metrics/uptime; per-app GitHub auto-deploy + healthchecks.
- **Where:** every app + CI.
- **Builds on:** all prior.
- **Outcome:** launchable.

## 5. Echo's place (so it stays "just one agent")

- Echo **imports** `novahos` for WARDEN/Constitution/consent/memory (Batch 1/4) — it deletes
  its local `guard.py` foundation stub.
- Echo declares itself as the **NOVAH** agent via a manifest (Batch 2).
- Echo registers in the fleet and can call / be called by other agents through NOVA-PRIME
  (Batch 3).
- Echo owns only twin-specific compute (voice/identity/compose/verify) + the "connect your
  data" UX (Batch 5). Everything else is shared.

## 6. Start here (Batch 1, concrete)

1. In `novahos/`, create `warden/` (core+validators+audit+types), `auth/`, `data/`
   (lifecycle+inference), `mcp/` (boundary+vault), `agent/` (base+manifest+registry+
   onboarding), `memory/` (working+episodic+semantic-iface), `reasoning/` — harvested from
   `NovahPrime/foundation/` and adapted to the kernel's config seam (env + optional YAML).
2. Update `novahos/__init__.py` to export the canonical API; keep `leadfuel_core` shim.
3. Version + tag; apps already pull `novahos @ git+https://github.com/NOVAHGREYWOLF/novahos.git@main`.
4. Prove it against **one** app (Echo): swap `guard.py` → `novahos` WARDEN; run a gated
   `/compose`; confirm an audit entry. That validates the kernel end-to-end.

> Cadence: one batch at a time, each verified live, checkpoint with the founder between
> batches. Reuse NovahPrime's production code; build only the gaps.

---

## Progress log

### Batch 1 — foundation consolidation (IN PROGRESS, via PR workflow)
`novahos` is being consolidated through PRs (not direct-to-main). Current `origin/main`:
- ✅ merged **#1** — `sources/` inbound layer + CROESUS finance agent + capability manifest (v0.4.0)
- ✅ merged **#2** — hash-chained `AuditTrail` (Phase 1 — fold NovahPrime foundation into the kernel)
- 🔵 branch **`warden-runtime-gate`** — the deeper WARDEN runtime gate (per `WARDEN_RECONCILIATION.md`), not yet merged
- 🔵 branch **`batch1a-memory-data`** — shared `novahos.memory` (working/episodic/semantic) + `novahos.data`
  (lifecycle/inference), additive + verified (existing `warden/privacy/consent` API intact). Awaiting merge.
- ⬜ **still missing on the kernel:** `novahos.auth` (3-factor/tiered), `novahos.agent` (base/manifest/
  registry/onboarding), `novahos.reasoning` (provider seam).

**⏸ PAUSED (founder, 2026-06-16):** reconcile `novahos` before more foundation porting — don't build on a
divergent tree.

### Roadmap / hygiene (do LATER, only when safe)
- **Reconcile the local `novahos` working tree to `origin`.** The local checkout has untracked copies of
  files already committed on origin (`warden_runtime/`, `sources/`, `audit_trail.py`, `docs/`, tests).
  Clean it (`fetch` → confirm everything is committed/pushed → `reset --hard origin/main` + remove stale
  untracked) **only once we're certain no uncommitted WIP would be lost.** Until then, treat `origin/main`
  as the source of truth and work via branches/PRs, not the local tree.
- Then resume Batch 1: merge `warden-runtime-gate` + `batch1a-memory-data`; port the remaining gaps
  (`auth`, `agent`, `reasoning`) as PR branches; then Batch 1d (prove the kernel against Echo).
