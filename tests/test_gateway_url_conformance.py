"""The gateway-URL contract, run against THIS repo's copy of the normaliser.

WHY THIS FILE EXISTS, AND WHY IT IS NOT A CHECKSUM TEST
──────────────────────────────────────────────────────
Fourteen services carry their own copy of the same gateway-URL normaliser. In August 2026 an
adversarial review found the load-bearing check in it — "is this URL pointed at a model vendor"
— was exact set membership against a frozenset of vendor API hostnames. So a vendor's bare
registrable domain, and any subdomain under one of those API hostnames, were both accepted as
gateways by twelve of the fourteen; and the same API hostname written with a trailing dot (the
DNS root, which resolves to the identical addresses) was accepted by ALL fourteen, including the
two implementations that already handled subdomains correctly. One bug, fourteen times, because
copying is how the module travels. Every one of those inputs is spelled out in the vector file
this test loads — deliberately kept there rather than repeated here, so that a repo's own
"no hardcoded vendor host in a .py file" guard has nothing to trip on.

novahub already has the right precedent for a vendored file — tests/test_vendored_design_system_
parity.py pins the sha256 of each canonical CSS file, and every consumer repo pins the SAME hash
against its own copy. That works there because those files are byte-identical by declaration.

It cannot work here. These fourteen copies are not byte-identical and cannot be made so: they
read different env-var tuples (icp and leadfuel-intake also honour LLM_GATEWAY_BASE_URL), raise
different exception hierarchies (some have GatewayMisconfigured, some only GatewayNotConfigured,
NovahPrime's subclasses ReasoningConfigError), expose different entry points (`base_url(env)`,
`gateway_url()`, `AnthropicProvider._resolve_gateway()`), and carry different extra functions
around the shared core. Hashing the code would be a gate nobody could keep green, and a gate
nobody can keep green is a gate that gets deleted.

So the shared artefact is the CONTRACT, not the code. gateway_url_vectors.json is pure data,
identical in all fourteen repos, and hashed here the same way the design-system test hashes CSS.
Each repo writes only the four-line adapter below. Then:

  * the table drifts   -> the sha256 assertion goes red
  * an implementation drifts -> one of its vectors goes red, in ITS repo, naming the URL
  * a repo never vendors it  -> this file is simply absent, which `python
    scripts/gateway_url_conformance_sweep.py` reports as MISSING

HONEST LIMIT: as of 2026-08-22 no repo in the estate runs GitHub Actions — jobs finish in ~1s
with steps=0 because billing has failed since at least 2026-07-24. Nothing here is enforced by
CI today. Until billing is restored this is a thing a human runs, which is what the sweep script
is for. Writing the gate now is still right: the alternative is fourteen copies with no shared
contract at all, and the enforcement arrives the day the runners do.

UPDATING THE TABLE after a deliberate contract change:
  1. Edit novahub/gateway_url_vectors.json (the canonical copy).
  2. Recompute:
       python -c "import hashlib,pathlib; print(hashlib.sha256(
         pathlib.Path('gateway_url_vectors.json').read_bytes()
         .replace(b'\r\n', b'\n')).hexdigest())"
  3. Update VECTORS_SHA256 here AND in every consumer repo's copy of this file, and re-vendor
     the json into each. The list of consumers is in docs/LLM_GATEWAY.md.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

# ── ADAPTER: the only part that differs between repos ────────────────────────────────────────
from novahos import gateway_url as gw


def call(url: str) -> str:
    """Run THIS repo's normaliser on one raw value. Raise if it refuses."""
    return gw.base_url({gw.CANONICAL_URL_ENV: url})


REFUSALS = (gw.GatewayNotConfigured, gw.GatewayMisconfigured)
# ─────────────────────────────────────────────────────────────────────────────────────────────

#: sha256 of gateway_url_vectors.json with CRLF normalised to LF, so a Windows checkout
#: (core.autocrlf=true) and a Linux runner agree. Identical in all fourteen repos.
VECTORS_SHA256 = "1c700faf5ae382eedeed355fbdfaa2719ead00fa22363612a8367f5663ff6dcc"

VECTORS_FILENAME = "gateway_url_vectors.json"


def _find_vectors() -> Path:
    """Walk up from this test until the vectors file appears.

    Deliberately a search rather than a fixed `parents[N]`: the fourteen repos put their tests
    at different depths (`tests/`, `tests/compliance/`, `apps/novahawk/tests/`), and this file
    is meant to be copied between them with only the adapter block changed.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / VECTORS_FILENAME
        if candidate.exists():
            return candidate
    raise AssertionError(
        f"{VECTORS_FILENAME} is not in this repo. It is vendored byte-identical from novahub "
        f"and is the only shared definition of what the gateway-URL check must do."
    )


VECTORS_PATH = _find_vectors()
VECTORS = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))["vectors"]


def test_the_vector_table_is_the_one_every_repo_pinned():
    """A table edited in one repo and not the others is thirteen silent disagreements."""
    actual = hashlib.sha256(
        VECTORS_PATH.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()
    assert actual == VECTORS_SHA256, (
        f"{VECTORS_FILENAME} no longer matches the pinned hash (expected {VECTORS_SHA256}, "
        f"got {actual}). If the change was deliberate, follow 'UPDATING THE TABLE' in this "
        f"file's docstring: the canonical copy is novahub's, and every consumer repo has to "
        f"be re-vendored and re-pinned in the same change."
    )


def test_the_table_is_not_empty_and_covers_both_verdicts():
    """A vendored table that silently became [] would pass every other test in this file."""
    verdicts = {v["verdict"] for v in VECTORS}
    assert len(VECTORS) >= 30, f"only {len(VECTORS)} vectors — the table has been truncated"
    assert verdicts == {"accept", "refuse"}, verdicts


@pytest.mark.parametrize(
    "vector",
    [v for v in VECTORS if v["verdict"] == "refuse"],
    ids=[v["url"] or "<empty>" for v in VECTORS if v["verdict"] == "refuse"],
)
def test_refused(vector):
    """Every one of these must raise. A warning would be a decision to continue."""
    with pytest.raises(REFUSALS):
        call(vector["url"])


@pytest.mark.parametrize(
    "vector",
    [v for v in VECTORS if v["verdict"] == "accept"],
    ids=[v["url"] for v in VECTORS if v["verdict"] == "accept"],
)
def test_accepted(vector):
    """And every one of THESE must pass. Half of this table is the false-positive half: a
    check that refuses `notanthropic.com` is one people route around rather than fix."""
    assert call(vector["url"]) == vector["base_url"], vector["why"]
