<!-- empty -->
# Demo - report

## Goal

Ship the demo.

## Tasks

0 task(s): todo 0, doing 0, pr 0, review 0, done 0, blocked 0.

No tasks.

## Cost

By task:

No spend.

By model:

No spend.

## Budget

- Total spend: $0.00
- Total context tokens: 0
- Soft budget: 5,000,000 tokens (ok)
- Hard budget: 8,000,000 tokens (ok)
- Status: **within budget**

## Archive candidates

None.

## Decisions

None.

## Lessons

None.

## Open items

None.

<!-- case -->
<!-- all-statuses -->
# Demo - report

## Goal

Ship the demo.

## Tasks

7 task(s): todo 1, doing 1, pr 1, review 1, done 2, blocked 1.

| id | title | status | model | PR |
|---|---|---|---|---|
| a | plan \| schema | done | sonnet | #26 |
| b | report | review | sonnet | #27 |
| c | tick | pr | opus | #28 |
| d | runner | doing | haiku | - |
| e | cloud | blocked | - | - |
| f | board | todo | - | - |
| g | docs | done | sonnet | - |

## Cost

By task:

| task | model | cost | context tokens |
|---|---|---|---|
| a | sonnet | $1.50 | 40,000 |
| b | sonnet | $0.76 | 30,000 |
| c | opus | $3.00 | 20,000 |
| d | haiku | $0.10 | 5,000 |
| e | - | $0.00 | 0 |
| f | - | $0.00 | 0 |
| g | sonnet | $0.20 | 1,000 |

By model:

| model | tasks | cost | context tokens |
|---|---|---|---|
| haiku | 1 | $0.10 | 5,000 |
| opus | 1 | $3.00 | 20,000 |
| sonnet | 3 | $2.46 | 71,000 |
| unassigned | 2 | $0.00 | 0 |

## Budget

- Total spend: $5.55
- Total context tokens: 96,000
- Soft budget: 5,000,000 tokens (ok)
- Hard budget: 8,000,000 tokens (ok)
- Status: **within budget**

## Archive candidates

auto_archive is off: listed only, nothing is archived without a yes.

- a: session s_a

## Decisions

- Use Sonnet for ticks

## Lessons

- Keep steps small

## Open items

- e is blocked: cloud
- Confirm weekly reset

<!-- case -->
<!-- over-soft -->
# Demo - report

## Goal

Ship the demo.

## Tasks

7 task(s): todo 1, doing 1, pr 1, review 1, done 2, blocked 1.

| id | title | status | model | PR |
|---|---|---|---|---|
| a | plan \| schema | done | sonnet | #26 |
| b | report | review | sonnet | #27 |
| c | tick | pr | opus | #28 |
| d | runner | doing | haiku | - |
| e | cloud | blocked | - | - |
| f | board | todo | - | - |
| g | docs | done | sonnet | - |

## Cost

By task:

| task | model | cost | context tokens |
|---|---|---|---|
| a | sonnet | $1.50 | 40,000 |
| b | sonnet | $0.76 | 30,000 |
| c | opus | $3.00 | 20,000 |
| d | haiku | $0.10 | 5,000 |
| e | - | $0.00 | 0 |
| f | - | $0.00 | 0 |
| g | sonnet | $0.20 | 1,000 |

By model:

| model | tasks | cost | context tokens |
|---|---|---|---|
| haiku | 1 | $0.10 | 5,000 |
| opus | 1 | $3.00 | 20,000 |
| sonnet | 3 | $2.46 | 71,000 |
| unassigned | 2 | $0.00 | 0 |

## Budget

- Total spend: $5.55
- Total context tokens: 96,000
- Soft budget: 50,000 tokens (exceeded)
- Hard budget: 8,000,000 tokens (ok)
- Status: **OVER SOFT BUDGET**

## Archive candidates

auto_archive is off: listed only, nothing is archived without a yes.

- a: session s_a

## Decisions

None.

## Lessons

None.

## Open items

- e is blocked: cloud

<!-- case -->
<!-- over-hard -->
# Demo - report

## Goal

Ship the demo.

## Tasks

1 task(s): todo 0, doing 0, pr 0, review 0, done 1, blocked 0.

| id | title | status | model | PR |
|---|---|---|---|---|
| x | big | done | opus | - |

## Cost

By task:

| task | model | cost | context tokens |
|---|---|---|---|
| x | opus | $12.00 | 9,000,000 |

By model:

| model | tasks | cost | context tokens |
|---|---|---|---|
| opus | 1 | $12.00 | 9,000,000 |

## Budget

- Total spend: $12.00
- Total context tokens: 9,000,000
- Soft budget: 5,000,000 tokens (exceeded)
- Hard budget: 8,000,000 tokens (exceeded)
- Status: **OVER HARD BUDGET**

## Archive candidates

auto_archive is off: listed only, nothing is archived without a yes.

- x: session s_x

## Decisions

None.

## Lessons

None.

## Open items

None.

<!-- case -->
<!-- auto-archive-on -->
# Demo - report

## Goal

Ship the demo.

## Tasks

7 task(s): todo 1, doing 1, pr 1, review 1, done 2, blocked 1.

| id | title | status | model | PR |
|---|---|---|---|---|
| a | plan \| schema | done | sonnet | #26 |
| b | report | review | sonnet | #27 |
| c | tick | pr | opus | #28 |
| d | runner | doing | haiku | - |
| e | cloud | blocked | - | - |
| f | board | todo | - | - |
| g | docs | done | sonnet | - |

## Cost

By task:

| task | model | cost | context tokens |
|---|---|---|---|
| a | sonnet | $1.50 | 40,000 |
| b | sonnet | $0.76 | 30,000 |
| c | opus | $3.00 | 20,000 |
| d | haiku | $0.10 | 5,000 |
| e | - | $0.00 | 0 |
| f | - | $0.00 | 0 |
| g | sonnet | $0.20 | 1,000 |

By model:

| model | tasks | cost | context tokens |
|---|---|---|---|
| haiku | 1 | $0.10 | 5,000 |
| opus | 1 | $3.00 | 20,000 |
| sonnet | 3 | $2.46 | 71,000 |
| unassigned | 2 | $0.00 | 0 |

## Budget

- Total spend: $5.55
- Total context tokens: 96,000
- Soft budget: 5,000,000 tokens (ok)
- Hard budget: 8,000,000 tokens (ok)
- Status: **within budget**

## Archive candidates

auto_archive is on: these sessions are eligible for archiving.

- a: session s_a

## Decisions

None.

## Lessons

None.

## Open items

- e is blocked: cloud

<!-- case -->
<!-- auto-archive-off -->
# Demo - report

## Goal

Ship the demo.

## Tasks

7 task(s): todo 1, doing 1, pr 1, review 1, done 2, blocked 1.

| id | title | status | model | PR |
|---|---|---|---|---|
| a | plan \| schema | done | sonnet | #26 |
| b | report | review | sonnet | #27 |
| c | tick | pr | opus | #28 |
| d | runner | doing | haiku | - |
| e | cloud | blocked | - | - |
| f | board | todo | - | - |
| g | docs | done | sonnet | - |

## Cost

By task:

| task | model | cost | context tokens |
|---|---|---|---|
| a | sonnet | $1.50 | 40,000 |
| b | sonnet | $0.76 | 30,000 |
| c | opus | $3.00 | 20,000 |
| d | haiku | $0.10 | 5,000 |
| e | - | $0.00 | 0 |
| f | - | $0.00 | 0 |
| g | sonnet | $0.20 | 1,000 |

By model:

| model | tasks | cost | context tokens |
|---|---|---|---|
| haiku | 1 | $0.10 | 5,000 |
| opus | 1 | $3.00 | 20,000 |
| sonnet | 3 | $2.46 | 71,000 |
| unassigned | 2 | $0.00 | 0 |

## Budget

- Total spend: $5.55
- Total context tokens: 96,000
- Soft budget: 5,000,000 tokens (ok)
- Hard budget: 8,000,000 tokens (ok)
- Status: **within budget**

## Archive candidates

auto_archive is off: listed only, nothing is archived without a yes.

- a: session s_a

## Decisions

None.

## Lessons

None.

## Open items

- e is blocked: cloud
