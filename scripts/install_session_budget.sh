#!/usr/bin/env bash
# Copy the session-budget kit (context guard hook + handoff / route-and-spawn skills) into other repos.
#   scripts/install_session_budget.sh /path/to/repo [/path/to/other ...]
# If the target already has .claude/settings.json, the kit's hooks / permissions.allow / env are MERGED into it
# (scripts/merge_claude_settings.py); nothing else in that file is touched. A target file that is not valid JSON
# is skipped, not overwritten.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
[ $# -ge 1 ] || { echo "usage: $0 <repo> [<repo> ...]" >&2; exit 2; }
for repo in "$@"; do
  [ -d "$repo/.git" ] || { echo "skip $repo: not a git repo" >&2; continue; }
  if ! python3 "$here/scripts/merge_claude_settings.py" "$here/.claude/settings.json" "$repo/.claude/settings.json" >/dev/null; then
    echo "skip $repo: could not merge .claude/settings.json (left untouched); add the hooks by hand" >&2
    continue
  fi
  mkdir -p "$repo/.claude/hooks" "$repo/.claude/skills"
  cp "$here/.claude/hooks/context_guard.py" "$repo/.claude/hooks/"
  cp -R "$here/.claude/skills/handoff" "$here/.claude/skills/route-and-spawn" "$repo/.claude/skills/"
  echo "installed into $repo (review, commit, merge to the default branch)"
done
