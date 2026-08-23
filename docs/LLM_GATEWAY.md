# The one door out — novahos edition

novahos calls a model in exactly one place, `novahos/llm.py`, and after this change every one of
those calls is pinned to novahub's LLM gateway or it does not happen. THE_DOOR.md law 9, in the
one repo where it is easiest to get wrong, because novahos is not a service. It is a library
that other people's processes import.

## Two variables, and what they mean

```bash
LLM_GATEWAY_URL=https://leadfuel.cloud/llm    # origin + mount. NOT /v1/messages.
LLM_GATEWAY_TOKEN=<this service's own gateway token>   # NOT ANTHROPIC_API_KEY.
```

Same two names, same meanings, same resolver as echo and NovahPrime. `novahos/gateway_url.py`
is a vendored copy of novahub's `gateway_url.py` — the executable code is identical, only the
prose differs. Change it in novahub first and copy it down, or the estate grows a second answer
to the question that module exists to have one answer to.

The canonical value is the origin plus the mount, because that is what "base URL" already means
here and in the vendors' own SDKs, and because trimming a known suffix is deterministic while
deciding whether to *append* one requires knowing which client library reads the value. novahos
speaks litellm, which needs the full path, so `novahos/llm.py` calls `gateway_url.messages_url()`
and appends `/v1/messages` explicitly, in code, where it can be grepped. A value pasted in the
old full-path form is trimmed and works.

Hosts that would rather not mutate `os.environ` can call `llm.configure_gateway(url=…, token=…)`.
It runs through the identical validation, so it is a convenience and never a bypass.

## Why this library needed it more than a service does

Grep this repo for `ANTHROPIC_API_KEY`. There is not one occurrence, in any file, and there never
was. That reads like safety and is the opposite of it.

litellm resolves both halves of a call from the ambient process environment, and both chains end
at the vendor. Read in litellm 1.98.0, `main.py:2744` and `:2748`:

```python
api_key  = api_key  or litellm.anthropic_key or litellm.api_key \
                    or os.environ.get("ANTHROPIC_API_KEY")
api_base = api_base or litellm.api_base or get_secret("ANTHROPIC_API_BASE") \
                    or get_secret("ANTHROPIC_BASE_URL") \
                    or "https://api.anthropic.com/v1/messages"
```

So before this change, `reason()` spent whatever key its **host** happened to hold, while naming
that key nowhere in this tree. A service that deletes its own `ANTHROPIC_API_KEY` and then
imports this library has not closed its door — it has moved the door one import deeper, into a
dependency whose diff it does not read and whose environment it does not think of as its own.
A transitive dependency is a door.

The estate-wide scan scored this repo **0 ANTHROPIC_API_KEY files**, and 0 was the most
misleading number in that table: it measured whether the credential was *named* here, when what
mattered was whether it was *used* here.

## Why per-call, and not an env var or the global

All three mechanisms were read in litellm 1.98.0 before choosing. The two rejected options fail
in opposite directions:

| mechanism | position in litellm's chain | failure mode |
|---|---|---|
| `ANTHROPIC_API_BASE` / `ANTHROPIC_BASE_URL` | last, before the hardcoded vendor URL (`main.py:2748`) | a dropped or misspelled variable is **not an error** — it is a silent direct vendor call that succeeds |
| `litellm.api_base` global | **before** the per-call value on the ollama path (`main.py:4225`) | drags a host's deliberately-local model through the gateway and out to a vendor |
| per-call `api_base` | first on the cloud path, ignored on the local one | can fail closed, and cannot reach past this module into a host's other litellm usage |

Only the third can refuse. So `_route()` returns per-call `api_base` + `api_key`, and raises
`GatewayNotConfigured` when either is missing — before a socket is opened.

Self-hosted models (`ollama/`, `ollama_chat/`) are deliberately **not** routed through the
gateway and need no configuration: they run on the host's own box, and pinning them at the
gateway would push text the host chose to keep local out to a vendor. Anything *not* on that
prefix list is treated as cloud, so an unfamiliar prefix fails closed rather than being assumed
safe.

## Where the config is read, and why not `config.py`

`novahos/gateway_url.py` reads `os.environ` at call time, stdlib-only, deliberately not through
`CoreSettings`. Three reasons, all specific to being a library:

1. `settings = CoreSettings()` runs at **import** of `novahos.config`, snapshotting the
   environment whenever the host first touched the kernel. Hosts touch it at wildly different
   instants, and a host that loads its secrets after that first import would snapshot an empty
   gateway URL. Reading at call time deletes the ordering question instead of documenting it.
2. `CoreSettings` sets `env_file=".env"`, so it also reads a dotenv file out of the host's
   working directory — a config source the host did not choose. Tolerable for a model id; not
   for the value that decides whether spend is gated.
3. `CoreSettings` needs pydantic-settings, which lives in the `substrate` **extra**. A guard that
   cannot load in a half-installed environment is a guard that can be missing, and that is
   exactly the environment where you want it loudest.

Model ids stay in `CoreSettings`: those are routing, not credentials, and a wrong one fails
loudly at the gateway.

## A closed door is not a bad answer

Pinning the litellm calls is only half of fail-closed. All four agents that call `llm.reason()`
wrap it in a bare `except Exception`, each for a good reason of its own — a model returning
malformed JSON should not take down a content pipeline. But a refusal is not a model that
answered badly; it is a model that was never asked. Absorbed into those handlers it would
become:

| agent | what the refusal would have looked like |
|---|---|
| WORDSMITH | a transcript-stub "draft" — and novahound publishes whatever `compose()` returns |
| CURATOR | `{"index": 0, "reason": "default"}`, indistinguishable from a real ranking |
| ORACLE | `[]`, indistinguishable from a quiet week with nothing to suggest |
| CROESUS | `{}`, which lucid's Steward renders as a generic-but-real financial reading, shown to a person, with nothing behind it |

So `GatewayNotConfigured` and `GatewayMisconfigured` now pass through all four handlers.
Everything else is still caught — the existing fail-soft behaviour is deliberate and is not what
this change is for. `tests/test_agents_fail_closed.py` asserts both halves for each agent, so a
future edit cannot satisfy it by making the handler catch nothing at all.

## Who this affects, and when

novahos is pinned by SHA in eight repos and by branch in one. **Nothing changes for any of them
until its pin is bumped** — with one exception, listed first because it is the one that breaks
the assumption:

| repo | pin | reaches `novahos.llm`? |
|---|---|---|
| **wolfos** | `@main` — **picks this up on its next build, no bump needed** | no — imports `sources`, `warden`, `sources.discovery` only |
| echo | `@8200322` | no — imports `warden_runtime`, `agent`, `data.inference` |
| icp | `@8200322` | no — imports `warden_runtime`, `agent`, `audit_trail` |
| lucid | `@8200322` | **yes** — `novahos.agents.resolve("croesus","assess")` |
| novaherald | `@8200322` | no — imports `warden_runtime`, `agent`, `audit_trail` |
| novahound | `@8200322` (`novahos[agents]`) | **yes** — `novahos.agents.apollo` + `novahos.llm` |
| novahawk | `@8200322` | no — imports `agent`, `warden` |
| novahub | `@d8de124` | no — imports `warden_runtime`, `mcp`, `audit_trail` |
| odyssey | `@724d486` | no — imports `audit_trail`, `mcp`, `agent` |

wolfos is safe at `@main` only because it never reaches this module. That was checked, not
assumed — but it is one import away from not being true, which is the argument for closing this
in the library rather than in each host.

**A pin bump is not a one-line change.** `8200322` and `d8de124` are **not on `main`** — both
live on the unmerged `mesh/per-spoke-auth` branch, which also carries the per-spoke service-token
work those hosts depend on and an older `llm.py` that predates kernel metering entirely. Bumping
those seven pins to a `main` SHA would silently drop the mesh auth work. Reconciling that branch
with `main` is prerequisite work for the bumps, and is out of scope here.

## Order of operations

A host that bumps its pin before its gateway variables are set will raise on every model call.
That is the design, not a defect — but the order matters:

1. Merge novahub #456. **The gateway route does not exist yet**: `/llm/v1/messages` answers
   404 today while `/healthz` answers 200 (verified).
2. Deploy novahub.
3. Mint a gateway token per service and set `LLM_GATEWAY_URL` + `LLM_GATEWAY_TOKEN`.
4. Merge the service PRs.
5. Delete `ANTHROPIC_API_KEY` per service — the load-bearing step. With no credential present, a
   future mistake fails loudly instead of quietly working.
6. Reconcile `mesh/per-spoke-auth` with `main`, then bump the pins, starting with the two hosts
   that actually reach this module (novahound, lucid).

While a host still holds a vendor key, `novahos.llm` logs one warning per process saying so. It
cannot delete the key and must not refuse because of it — every host legitimately still holds one
until its own migration lands — but silence there would be its own small lie, because any *other*
litellm or SDK call in that process which does not pin `api_base` still reaches the vendor with
it.

## Known consequence: a double count, stated rather than fixed

novahub's gateway writes each call to the `llm_usage` meter **and** to the suite-shared
`ai_usage` ledger. `novahos.llm._emit_shared()` writes to `ai_usage` too. Once the gateway is
deployed and a host bumps its pin, one kernel call can produce two `ai_usage` rows.

Nothing double-counts yet, because the gateway is not deployed and every consumer that reaches
this module is pinned to an older SHA. It is stated here rather than fixed here because egress
and accounting are two changes, and an accounting bug introduced alongside an egress change is
invisible until a bill arrives. Whoever bumps the first pin owns closing it.

Do not close it by making the kernel stop writing. A silent meter is the defect the metering work
already fixed once; trading a double-count for darkness is not an improvement.

## This is a public repo

novahos is one of two public repos in the estate, so everything added here was checked against
that:

- **Secrets:** none. Test fixtures use `https://gateway.example/llm` and obviously-fake tokens.
  The `sk-ant-` string in the tests is a prefix literal for the vendor-key check, not a key.
- **Hostnames:** `leadfuel.cloud` appears in prose in `gateway_url.py`, matching the canonical
  copy. That is not a new disclosure — it is already the committed default at
  `novahos/sources/_identity.py:18` in this same public repo.
- **Vendor hostnames:** `_VENDOR_HOSTS` lists public API endpoints. A guard has to name what it
  guards against.
- **Internal paths:** other repos' file names (`compose.py`, `app/experts/steward.py`) appear in
  comments explaining who calls what. This matches the disclosure level already committed here —
  `ECOSYSTEM_GAME_PLAN.md` names Echo's `guard.py`, Lucid's `guard.gate` and its `/compose`
  endpoint, and `llm.py`'s pre-existing docstring already said `compose.py`.
- **What is deliberately absent:** no token values, no `.env` file, no gateway token format
  beyond the fact that it is not a vendor key, and no non-public hostname.
