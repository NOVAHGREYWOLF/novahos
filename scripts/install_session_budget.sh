#!/usr/bin/env bash
# Copy the session-budget kit (context guard hook + handoff / route-and-spawn skills) into other repos.
#   scripts/install_session_budget.sh /path/to/repo [/path/to/other ...]
# Merges nothing: refuses if the target already has .claude/settings.json (add the hooks by hand).
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
[ $# -ge 1 ] || { echo "usage: $0 <repo> [<repo> ...]" >&2; exit 2; }
for repo in "$@"; do
  [ -d "$repo/.git" ] || { echo "skip $repo: not a git repo" >&2; continue; }
  if [ -e "$repo/.claude/settings.json" ]; then
    echo "skip $repo: .claude/settings.json exists; add the two hooks from $here/.claude/settings.json by hand" >&2
    continue
  fi
  mkdir -p "$repo/.claude/hooks" "$repo/.claude/skills"
  cp "$here/.claude/hooks/context_guard.py" "$repo/.claude/hooks/"
  cp "$here/.claude/settings.json" "$repo/.claude/settings.json"
  cp -R "$here/.claude/skills/handoff" "$here/.claude/skills/route-and-spawn" "$repo/.claude/skills/"
  echo "installed into $repo (review, commit, merge to the default branch)"
done
