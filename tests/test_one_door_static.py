"""One door out, checked STATICALLY: no kernel module reaches a vendor but the chokepoint.

Companion to ``test_llm_one_door.py``, and deliberately not a replacement for it. That file
is behavioural — it swaps in a recording litellm and proves the calls novahos.llm actually
makes are pinned at the gateway. It is also the stronger proof, and it is the one to extend
when the question is "what does this call send".

It cannot answer the question THIS file exists for, for two reasons. It only exercises the
functions it calls, so a brand-new module that imports litellm on its own is invisible to it.
And it opens with two ``pytest.importorskip`` lines, so on any install without the substrate
extra — which is most of them, since the stdlib rails are the whole point of the layering —
it skips in full and asserts nothing at all. A guard that is silently skipped looks exactly
like a guard that passed. This file imports nothing but ``ast`` and ``pathlib`` and therefore
runs everywhere, including the foundation-only installs where the other one is absent.

WHY THIS IS AST-BASED AND NOT A GREP. A substring sweep for ``litellm.acompletion`` over
this very repo returns three hits, and one of them is a line of prose inside a docstring.
A checker that counts prose is a checker whose first failure is somebody documenting the
rule — which is how a gate ends up switched off instead of fixed. ``ast`` sees calls and
imports and is structurally blind to comments, docstrings and f-strings, so the rule can be
written down in English anywhere in the tree without tripping it.

WHY IT NEEDS NO EXCLUSION LIST FOR ITSELF. It scans the ``novahos/`` package only. This file
lives in ``tests/``, so it is out of scope by construction rather than by a name that a later
rename would silently drop out of the sweep.

WHAT IT IS GUARDING AGAINST, concretely. ``echo/app/llm.py`` and ``lucid/app/llm.py`` both
open with the line "LLM gateway wrapper over LiteLLM" and both call ``litellm.acompletion``
with no ``api_base`` — they meter the spend accurately and then send the request straight to
the vendor. They are chokepoints for accounting, not for routing, and nothing in either file
says so. The kernel is one careless import away from the same shape, and the same docstring
would still be sitting at the top of the file describing a property it had stopped having.

The baseline is EMPTY: as of this commit ``novahos/llm.py`` is the only module in the kernel
that touches litellm, and nothing touches the Anthropic SDK at all. Nothing needs cleaning up
first, so this is a pure never-regress guard. If a later change has to add a writer, add it
here with a reason — do not widen the pattern.
"""
from __future__ import annotations

import ast
import pathlib

PKG = pathlib.Path(__file__).resolve().parent.parent / "novahos"

#: The one module allowed to reach a vendor SDK. It pins api_base + api_key per call and
#: raises GatewayNotConfigured when either is missing (see novahos/llm.py::_route).
CHOKEPOINT = "llm.py"

_VENDOR_MODULES = {"litellm", "anthropic"}
#: Attribute names that put a request on the wire. ``completion_cost`` is deliberately NOT
#: here: it prices a response that already came back and never opens a connection.
_WIRE_CALLS = {"completion", "acompletion"}
_SDK_CLIENTS = {"Anthropic", "AsyncAnthropic", "Client"}


def _root_name(node: ast.AST) -> str | None:
    """``litellm`` for ``litellm.acompletion``, ``a`` for ``a.b.c()``; None otherwise."""
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _reaches(path: pathlib.Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - not our business here
        return []
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in _VENDOR_MODULES:
                    hits.append(f"L{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in _VENDOR_MODULES:
                hits.append(f"L{node.lineno}: from {node.module} import ...")
        elif isinstance(node, ast.Call):
            fn = node.func
            if not isinstance(fn, ast.Attribute):
                continue
            if fn.attr in _WIRE_CALLS and _root_name(fn) in _VENDOR_MODULES:
                hits.append(f"L{node.lineno}: {_root_name(fn)}.{fn.attr}()")
            elif fn.attr in _SDK_CLIENTS and _root_name(fn) == "anthropic":
                hits.append(f"L{node.lineno}: anthropic.{fn.attr}()")
            elif fn.attr == "create" and isinstance(fn.value, ast.Attribute) \
                    and fn.value.attr == "messages":
                hits.append(f"L{node.lineno}: .messages.create()")
    return hits


def test_only_the_chokepoint_reaches_a_vendor():
    offenders = {
        str(p.relative_to(PKG)): hits
        for p in sorted(PKG.rglob("*.py"))
        if p.name != CHOKEPOINT and (hits := _reaches(p))
    }
    assert not offenders, (
        "These kernel modules reach a vendor SDK directly, bypassing novahos.llm — which is "
        "the only place api_base is pinned at the gateway:\n"
        + "\n".join(f"  novahos/{f}: {', '.join(h)}" for f, h in offenders.items())
        + "\n\nRoute the call through novahos.llm.reason()/classify(), which splat _route()'s "
          "kwargs. Do not add an exemption to make this pass."
    )


def test_the_chokepoint_never_calls_a_vendor_ungated():
    """Every wire call in llm.py carries the gate, so llm.py cannot become echo-shaped.

    Proves the SHAPE, not the contents: a ``**``-splat could in principle hold the wrong
    dict. What it makes impossible is the actual regression seen in the wild — a bare
    ``litellm.acompletion(model=..., messages=...)`` with no api_base at all.
    """
    tree = ast.parse((PKG / CHOKEPOINT).read_text(encoding="utf-8"))
    ungated = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in _WIRE_CALLS or _root_name(node.func) not in _VENDOR_MODULES:
            continue
        # a **splat, or an explicit api_base= — either pins the destination.
        if not any(kw.arg is None or kw.arg == "api_base" for kw in node.keywords):
            ungated.append(f"L{node.lineno}")
    assert not ungated, (
        f"{CHOKEPOINT} calls a vendor with neither a **gate splat nor an explicit api_base "
        f"at {', '.join(ungated)}. Without api_base litellm falls back through env vars to "
        "https://api.anthropic.com — a silent direct vendor call, not an error."
    )
