# WARDEN reconciliation — one gate, shared primitives (Phase 1 design)

**Goal:** fold NovahPrime's deeper WARDEN into `novahos` as a *single* enforcement family —
**without breaking the live apps** that already call `novahos.warden`. This is the first real
step of the NovahOS consolidation (kernel-first, additive).

## The two implementations today

| | `novahos.warden` (production-wired) | `NovahPrime foundation/warden` (deeper) |
|---|---|---|
| Shape | Functional, stateless, ~200 LOC | Class `Warden`, provider-injected (DI) |
| Surfaces | **SIMPLE** `evaluate(Action)->Decision` + **NUMERIC** `score_action`/`decide` (0–100 risk) | One `evaluate(ActionRequest)->WardenDecision` |
| Checks | auth → privacy → consent → resource (simple); risk parts (numeric) | 6 validators in fixed order: constitutional · consent_tier · auth_state · resource_limits · cross_agent_conflict · privacy_tier_transition |
| Audit | optional (`novahos.warden_audit` substrate) | **mandatory**, hash-chained `AuditTrail`, every decision |
| Extras | content validators (`validators.py`: publish caps, DM window) | agent **suspension**, **cross-agent conflict** registry, **required_auth_tier** escalation, resource `commit` on approve |
| Execution model | stateless API calls (Flask handlers, Lucid `guard.gate`) | long-running multi-agent **runtime** (many agents, shared state) |
| Used by | NovaHub, the suite, Lucid (live) | NovahPrime only (standalone) |

## Key finding — they're complementary, not conflicting
- **Verdict spaces already match:** both emit `APPROVE / ESCALATE / BLOCK` (NovahPrime `Decision` enum ≡ novahos simple verdicts). No vocabulary translation needed.
- They gate **different execution models**: `novahos.warden` gates *one API action* statelessly (fast, per-request); NovahPrime's gates *agent actions in a runtime* (stateful, conflict-aware, mandatory audit).
- `novahos.warden` already proves the "one module, multiple surfaces over shared primitives" pattern (it carries SIMPLE + NUMERIC together). We add a **third surface**: the rich runtime gate.

## The reconciliation — one WARDEN family, three surfaces, shared primitives
Shared deterministic primitives stay canonical in `novahos` (they're production-wired):
`novahos.constitution` (ranked principles), `novahos.consent` (tiers), `novahos.privacy` (tiers),
`novahos.validators` (hard guardrails). **Everything builds on these — no parallel copies.**

1. **Keep SIMPLE + NUMERIC verbatim.** `evaluate(Action)`, `score_action`, `decide`, the verdict
   constants, and `verdict_to_gate`/`gate_to_verdict` are unchanged. → live apps + Lucid `guard.gate`
   keep working untouched. (Back-compat is the hard requirement.)
2. **Port NovahPrime's runtime gate as the third surface** — the class `Warden` + its 6 validators +
   `AuditTrail` + `types` — into `novahos` (proposed: `novahos/warden_runtime.py` or
   `novahos/runtime/gate.py`). Rewire it to consume the **novahos** primitives:
   - its `ConstitutionalValidator` → reads `novahos.constitution`
   - its `ConsentTierValidator` → reads `novahos.consent`
   - its `PrivacyTierTransitionValidator` → reads `novahos.privacy`
   - keep its genuinely-new machinery as-is: `auth_state`, `resource_limits`, `cross_agent_conflict`,
     agent suspension, `required_auth_tier`, hash-chained audit.
3. **Make audit consistent.** The runtime gate's mandatory hash-chained `AuditTrail` becomes the
   canonical audit; `novahos.warden_audit` (substrate) is its persistence adapter. The SIMPLE API's
   optional audit dict stays (cheap path for stateless calls).
4. **DI bridge.** NovahPrime injects providers (consent/auth/privacy/…); `novahos` exposes module
   functions. Provide thin **adapter providers** in novahos that wrap the module functions, so the
   ported `Warden` class is constructed with novahos-backed providers by default.

## Additively port the rest of NovahPrime's foundation (separate, later P1 slices)
Not part of the WARDEN merge, but the same "port onto novahos, extras-gated" pattern:
`foundation/auth` (3-factor + continuous) → `novahos.auth`; `foundation/data`
(classification/inference/lifecycle) → enrich `novahos.privacy` + new `novahos.data`;
`foundation/memory` (episodic/semantic/working) → `novahos.memory`; `foundation/agent`
(base/manifest/onboarding/registry) + `app/workflows` + `app/runtime/scheduler` → `novahos.runtime`.
Each is **new modules** (additive) gated behind extras — `import novahos` stays light.

## Safety / back-compat checklist
- `novahos.warden.evaluate` / `score_action` / `decide` signatures + return types **unchanged**.
- No new hard dependency at `import novahos` (runtime gate lives in an extras-gated submodule).
- The 5 live apps + Lucid `guard.gate` import-and-run unchanged (verify in CI).
- Exactly **one** set of primitives (constitution/consent/privacy) — NovahPrime's parallel copies are
  deleted in favor of novahos's after the validators are rewired.

## Tests
- Keep all current `novahos/tests` green (SIMPLE + NUMERIC + sources).
- Port `NovahPrime/tests/compliance/test_warden.py` (+ related foundation tests) under `novahos/tests`,
  retargeted to the merged module. Target: the 8-step order, suspension, audit-chain integrity,
  required-auth escalation, and "most-severe-wins" all pass against the novahos-backed gate.

## Verdict
Low-risk merge: the APIs don't collide (different surfaces, aligned verdicts), back-compat is
preserved by keeping the existing functions untouched, and NovahPrime's depth is added as a new
runtime surface over the existing primitives. This is the blueprint for Phase 1 once
[novahos#1](https://github.com/NOVAHGREYWOLF/novahos/pull/1) merges.
