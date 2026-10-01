"""The session-budget kit: context guard maths and the model router."""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

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
    assert guard.decide(99_000, 0, 100_000, 150_000) == (None, 0)
    msg, last = guard.decide(101_000, 0, 100_000, 150_000)
    assert "handoff" in msg and "HARD" not in msg and last == 101_000
    assert guard.decide(105_000, last, 100_000, 150_000) == (None, last)  # inside the re-warn window
    msg, _ = guard.decide(112_000, last, 100_000, 150_000)
    assert msg
    msg, _ = guard.decide(160_000, 0, 100_000, 150_000)
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


def test_guard_defaults_are_the_300k_450k_policy():
    assert (guard.SOFT_DEFAULT, guard.HARD_DEFAULT) == (300_000, 450_000)
    assert guard.decide(299_000, 0, guard.SOFT_DEFAULT, guard.HARD_DEFAULT) == (None, 0)
    msg, _ = guard.decide(301_000, 0, guard.SOFT_DEFAULT, guard.HARD_DEFAULT)
    assert "handoff point 300k" in msg and "HARD" not in msg
    msg, _ = guard.decide(450_000, 0, guard.SOFT_DEFAULT, guard.HARD_DEFAULT)
    assert "HARD CAP" in msg


def test_kit_settings_carry_env_permission_and_both_hooks():
    s = json.loads((ROOT / ".claude" / "settings.json").read_text())
    assert s["env"] == {"SESSION_SOFT_TOKENS": "300000", "SESSION_HARD_TOKENS": "450000"}
    assert s["permissions"]["allow"] == ["mcp__claude-code-remote__send_message"]
    assert set(s["hooks"]) == {"PostToolUse", "UserPromptSubmit"}


merge = _load("scripts/merge_claude_settings.py", "merge_claude_settings").merge


def test_merge_adds_and_never_overwrites():
    src = json.loads((ROOT / ".claude" / "settings.json").read_text())
    own_hook = {"hooks": [{"type": "command", "command": "echo mine"}]}
    dst = {"model": "opus", "env": {"SESSION_SOFT_TOKENS": "1", "FOO": "bar"},
           "permissions": {"allow": ["Bash(ls)"], "deny": ["Bash(rm:*)"]}, "hooks": {"PostToolUse": [own_hook]}}
    out = merge(src, json.loads(json.dumps(dst)))
    assert out["model"] == "opus" and out["permissions"]["deny"] == ["Bash(rm:*)"]
    assert out["permissions"]["allow"] == ["Bash(ls)", "mcp__claude-code-remote__send_message"]
    assert out["env"] == {"SESSION_SOFT_TOKENS": "1", "FOO": "bar", "SESSION_HARD_TOKENS": "450000"}  # theirs wins
    assert out["hooks"]["PostToolUse"][0] == own_hook and len(out["hooks"]["PostToolUse"]) == 2
    assert len(out["hooks"]["UserPromptSubmit"]) == 1
    assert merge(src, json.loads(json.dumps(out))) == out  # idempotent: no duplicate hooks or rules


@pytest.mark.skipif(shutil.which("bash") is None or shutil.which("python3") is None, reason="needs bash and python3")
def test_installer_merges_into_existing_settings_and_skips_bad_json(tmp_path):
    def install(*repos):
        return subprocess.run(["bash", str(ROOT / "scripts" / "install_session_budget.sh"), *map(str, repos)],
                              capture_output=True, text=True)

    fresh, existing, broken = (tmp_path / n for n in ("fresh", "existing", "broken"))
    for r in (fresh, existing, broken):
        (r / ".git").mkdir(parents=True)
    (existing / ".claude").mkdir()
    (existing / ".claude" / "settings.json").write_text(json.dumps({"model": "sonnet", "permissions": {"allow": ["Bash(ls)"]}}))
    (broken / ".claude").mkdir()
    (broken / ".claude" / "settings.json").write_text("{not json")

    r = install(fresh, existing, broken)
    assert r.returncode == 0, r.stderr
    kit = json.loads((ROOT / ".claude" / "settings.json").read_text())
    assert json.loads((fresh / ".claude" / "settings.json").read_text()) == kit
    merged = json.loads((existing / ".claude" / "settings.json").read_text())
    assert merged["model"] == "sonnet" and merged["env"] == kit["env"]
    assert merged["permissions"]["allow"] == ["Bash(ls)", "mcp__claude-code-remote__send_message"]
    assert merged["hooks"] == kit["hooks"]
    assert (existing / ".claude" / "hooks" / "context_guard.py").exists()
    assert (broken / ".claude" / "settings.json").read_text() == "{not json"  # never overwritten
    assert not (broken / ".claude" / "hooks").exists() and "skip" in r.stderr
    before = (existing / ".claude" / "settings.json").read_text()
    assert install(existing).returncode == 0
    assert (existing / ".claude" / "settings.json").read_text() == before  # rerun changes nothing
