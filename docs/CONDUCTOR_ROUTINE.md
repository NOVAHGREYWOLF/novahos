# Conductor routines (live)

Two scheduled Routines run the conductor. Each firing is a fresh, small session (`create_new_session_on_fire`), so there is no long-lived
coordinator context. In the session taxonomy (`CONDUCTOR_DESIGN.md`), a routine-fired session is role `watchdog`.

| Routine | Id | Schedule | Does |
| --- | --- | --- | --- |
| Conductor hourly tick | `trig_015prRzaktsxeYJLiD7x8G9B` | hourly, at minute :36 | Runs `/tick` for the conductor plan: TOOLS CHECK, rate-limit check, pull-first status reads, merged-PR `mark-done`, red-CI report, plan, spawn/reuse, archive by the single gate, ungrouped list. |
| Conductor nightly | `trig_01U9CpzgkUWKbLeymJ46qmuA` | daily, 20:07 PT | TOOLS CHECK, then the close-out: applies the same archive gate (skips already-archived sessions), lists ungrouped sessions, stores the two Briefcase documents, and opens a draft PR with the sanitized public copy. Contract: "Daily report contract" in `CONDUCTOR_DESIGN.md`. |

Paused: the 4-hourly novahos tick `trig_01SXmjamu3JKRDbFyVvvHtGN` (router, 22:17 UTC) is `enabled=false`.

## TOOLS CHECK
Both prompts start with it. The hourly tick needs `mcp__claude-code-remote__*`; the nightly also needs the `novahub_brain` tools
(`store_document`). If they are missing, the session replies `STATUS: NEEDS-NOVAH | routine has no connectors` and stops. It does not improvise.

## Connectors
`create_trigger` has a `connectors` parameter, but it is not available for this organization. A routine created through it stores no
connectors, and its sessions run without `mcp__<server>__*` tools. So the owner adds `Claude_Code_Remote` and `novahub_brain` to
EACH routine in the claude.ai routines UI: connect them at https://claude.ai/customize/connectors, then edit each routine and add them.
Until then every fired session ends at the TOOLS CHECK.

## Verify
- Hourly tick: the first fired session's reply is not "routine has no connectors"; it reports started/reused/status changes.
- Nightly: the first run writes two Briefcase documents, `conductor_report YYYY-MM-DD` and `conductor_report_full YYYY-MM-DD`
  (check with `list_documents(app="conductor", kind="conductor_report")`), and opens the draft PR with `docs/reports/YYYY-MM-DD.md`.

## Notes
The tick is idempotent (starts are claimed as `doing` before returning), so a missed or doubled firing is harmless.
Pause with `update_trigger(enabled=false)`. Budget stops (soft/hard) make a tick start nothing. A tick also starts nothing when its
own `rate_limit_info.status` is not `allowed` or `isUsingOverage` is true.
