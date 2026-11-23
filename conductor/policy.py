"""Session-size policy defaults: the single source of truth for the conductor kit.

Owner decision 2026-10-01: weekly usage is low, so sessions are bigger so work gets finished.
Override per project in .conductor/project.json: `budget {soft, hard}` (project total) and
`per_session {soft, hard, reuse_below}`. Missing keys fall back to these values.

Not importable from .claude/hooks/context_guard.py (the hook is copied into other repos), which keeps its own
copy of SESSION_SOFT/HARD and reads SESSION_SOFT_TOKENS / SESSION_HARD_TOKENS; a test keeps the two equal.
"""
SESSION_SOFT = 300_000        # "finish the step, hand off"
SESSION_HARD = 450_000        # "stop now"
REUSE_BELOW = 200_000         # reuse an idle session for new work only below this
NO_WAKE_ABOVE = 300_000       # never wake an idle session above this
HAIKU_MAX = 150_000           # Haiku tasks stay under this (its window is 200k)
PROJECT_SOFT = 5_000_000      # sum of context tokens across all tasks
PROJECT_HARD = 8_000_000
COORDINATOR_HANDOFF = 200_000  # coordinator / tick runner self-check
