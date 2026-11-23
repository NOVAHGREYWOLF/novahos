# Conductor tick routine (definition only)

One scheduled Routine drives `/tick`. It is **documented, not created**: nobody has called `create_trigger` for it. To enable it, a person
(or a session they direct) creates it with `create_trigger`:

| Field | Value |
| --- | --- |
| name | `Conductor tick` |
| create_new_session_on_fire | `true` (each firing is a fresh, small session; no long-lived conductor context) |
| cron_expression | `CRON_TZ=<user tz> 17 */4 * * *` (every 4 hours, off the hour; hourly is the minimum) |
| initiation | `human_schedule` |
| connectors | `[]` |
| prompt | `Run /tick for the conductor plan in <repo> (branch <branch>) using the conductor skill. One pass, then stop. No polling, no wake-ups, never archive unless the plan sets auto_archive. If the plan is missing or invalid, report that and stop.` |

Why this shape: the tick is idempotent (starts are claimed as `doing` before returning), so a missed or doubled firing is harmless.
Pause with `update_trigger(enabled=false)`. Budget stops (soft/hard) make a tick start nothing, so a runaway plan cannot spend past `project.json` budget.
