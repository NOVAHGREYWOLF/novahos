"""The session-budget kit: context guard maths and the model router."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


guard = _load(".claude/hooks/context_guard.py", "context_guard")
router = _load(".claude/skills/route-and-spawn/route.py", "route")


def _line(kind: str, side: bool, **usage) -> str:
    return json.dumps({"type": kind, "isSidechain": side, "message": {"usage": usage}})


def test_context_is_last_main_thread_assistant_turn(tmp_path):
    t = tmp_path / "s.jsonl"
    t.write_text("\n".join([
        _line("assistant", False, input_tokens=2, cache_read_input_tokens=50_000, cache_creation_input_tokens=10_000),
        _line("assistant", True, input_tokens=1, cache_read_input_tokens=999_999),  # subagent: ignored
        _line("user", False),
    ]))
    assert guard.context_tokens(str(t)) == 60_002


def test_unknown_when_no_usage_or_missing_file(tmp_path):
    assert guard.context_tokens(str(tmp_path / "nope.jsonl")) is None
    t = tmp_path / "e.jsonl"
    t.write_text("not json\n")
    assert guard.context_tokens(str(t)) is None


def test_decide_thresholds_and_throttle():
    assert guard.decide(299_000, 0, 300_000, 450_000) == (None, 0)
    msg, last = guard.decide(301_000, 0, 300_000, 450_000)
    assert "handoff" in msg and "HARD" not in msg and last == 301_000
    assert guard.decide(305_000, last, 300_000, 450_000) == (None, last)  # inside the re-warn window
    msg, _ = guard.decide(312_000, last, 300_000, 450_000)
    assert msg
    msg, _ = guard.decide(460_000, 0, 300_000, 450_000)
    assert "HARD CAP" in msg


def test_router_rules():
    r = router.route
    assert r({"title": "x", "envelope": "critical"})["model"] == "opus"
    assert r({"title": "x", "effort": "high"})["model"] == "opus"
    assert r({"title": "Fix auth bug"})["model"] == "opus"
    assert r({"title": "Display-text sweep in signal", "effort": "small", "envelope": "free"})["model"] == "haiku"
    assert r({"title": "Display-text sweep", "effort": "medium"})["model"] == "sonnet"  # not small
    assert r({"title": "Security docs sweep", "effort": "small"})["model"] == "opus"   # risk beats cheap
    assert r({"title": "Wire the thing", "effort": "medium", "envelope": "production"})["model"] == "sonnet"
    assert r({"title": "x", "effort": "high", "model_pin": "sonnet"})["model"] == "sonnet"
    assert r({})["model"] == "sonnet"


def test_hook_defaults_match_policy_module():
    import sys
    sys.path.insert(0, str(ROOT))
    from conductor import policy
    assert (guard.SOFT_DEFAULT, guard.HARD_DEFAULT) == (policy.SESSION_SOFT, policy.SESSION_HARD)
