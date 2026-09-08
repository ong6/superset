<!--
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements. See the NOTICE file
distributed with this work for additional information
regarding copyright ownership. The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License. You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied. See the License for the
specific language governing permissions and limitations
under the License.
-->

# GitHub Issue Remediation Automation

## 1. Decision

Build a working **GitHub Issue Remediation Runner** whose first production
surface is a maintainer-authorized GitHub issue:

```text
issue receives `devin:fix`
  -> GitHub Actions validates and claims one remediation generation
  -> the workflow creates one bounded Devin session
  -> Devin investigates, implements, tests, and opens a pull request
  -> a scheduled Actions reconciler tracks the session and pull request
  -> repository CI independently verifies the change
  -> one issue comment and one status label show the lifecycle and outcome
```

This returns the take-home to its original requirement: one successful
**issue-to-remediation** path in the Superset fork. Failed-check repair remains
a valuable later trigger, but it is not the first product.

For the pilot, use GitHub Actions as the event and orchestration surface rather
than deploying a long-running webhook service. Put the orchestration logic in a
small tested Python package that runs in Actions and in Docker locally. Store
the durable user-facing state in GitHub, with the Devin session and pull
request as linked execution records.

The implementation has four workflows:

1. **dispatch** on the `devin:fix` label;
2. **reconcile** on a five-minute schedule and manual dispatch; and
3. **cancel** when the issue closes or authorization is removed; and
4. **report** on a schedule or manual dispatch to aggregate pilot outcomes.

An external controller is the production expansion path when multiple
repositories, lower reconciliation latency, centralized policy, or stronger
analytics justify another service.

## 2. Product boundary

### Pilot input

- one open issue in `ong6/superset`;
- one maintainer-applied `devin:fix` label;
- one issue generation at a time;
- one configured Devin playbook and repository;
- one bounded Devin session; and
- one pull request targeting the configured default branch.

### Pilot output

- one updateable issue status comment;
- one mutually exclusive status label;
- one linked Devin session;
- one remediation pull request;
- normal repository CI as the independent verification oracle; and
- one machine-readable run artifact per dispatcher or reconciler execution.

### Non-goals

- no automatic execution for every newly opened public issue;
- no direct push to the default branch;
- no autonomous merge, approval, or branch-protection bypass;
- no GitHub token, Actions token, or publisher secret passed to Devin;
- no claim of success from Devin's prose or terminal status alone;
- no hidden retry that can create a duplicate session;
- no arbitrary workflow or security-policy edits without explicit review; and
- no requirement to run Superset's product runtime to operate the automation.

## 3. Architecture options

### Option A: one GitHub Actions job calls Devin and stops

```text
issues.labeled -> POST /sessions -> comment session URL -> end
```

This is the smallest working trigger and mirrors the public Devin GitHub
Actions example. It is insufficient as the final design because it cannot
reliably expose long-running status, blocked sessions, timeout, cancellation,
pull-request CI, or restart recovery after the dispatcher exits.

### Option B: Actions dispatcher plus scheduled reconciler

```text
issues.labeled
  -> claim and create session

schedule / workflow_dispatch
  -> poll active sessions and linked PRs
  -> update one status record
  -> terminate stale or cancelled work
```

This is the recommended pilot:

- it is a real event-driven integration rather than a mock webhook;
- it requires no public service, queue, or database;
- it keeps status in the system where maintainers already work;
- it can be replayed locally through the same Python entry points;
- it has a clear failure model and kill switch; and
- it is small enough to implement and demonstrate end to end.

The tradeoff is scheduled reconciliation latency and a GitHub-backed state
store that is appropriate for one repository, not a large fleet.

### Option C: GitHub App webhook plus durable controller

```text
GitHub App webhook
  -> API
  -> database and queue
  -> Devin adapter
  -> verification and publisher workers
```

This is the strongest production control plane. It provides atomic database
claims, immediate webhook processing, centralized secrets, richer metrics, and
multi-repository policy. It also adds deployment, availability, database,
queue, and webhook-security work before the first issue can be remediated.

### Option D: native Devin automation only

A native automation can reduce custom code, but the take-home needs to
demonstrate explicit API use, event contracts, lifecycle decisions,
independent success criteria, and observable failure handling. It is better
treated as a later simplification if it exposes the required controls.

### Decision matrix

| Criterion | One-shot Action | Actions + reconciler | External controller |
|---|---:|---:|---:|
| Working take-home speed | High | High | Medium |
| Long-running status | Low | High | High |
| Duplicate suppression | Medium | High for one repo | High |
| Cancellation and timeout | Low | High | High |
| Independent PR verification | Medium | High | High |
| Operational overhead | Low | Low | High |
| Multi-repository scale | Low | Medium | High |
| Recommended use | Prototype only | **Pilot** | Production expansion |

## 4. End-to-end lifecycle

### 4.1 Intake and authorization

The dispatcher listens to:

```yaml
on:
  issues:
    types: [labeled]
  workflow_dispatch:
```

It proceeds only when:

- the issue is open;
- the added label is exactly `devin:fix`;
- the repository ID matches configuration;
- the issue is not a pull request;
- no nonterminal remediation generation already owns the issue; and
- the actor has the configured repository permission.

The label is the write-authorization gate. GitHub restricts label mutation to
repository users with suitable permissions, but the controller should still
resolve the actor's effective permission through the GitHub API and record it.

Do not trigger on every `issues.opened` event. Public issue titles and bodies
are untrusted and can be noisy, incomplete, malicious, or too broad. After the
pilot, a trusted issue form or triage rule may apply `devin:fix`
automatically.

### 4.2 Durable claim

Use Actions concurrency to serialize work per issue:

```yaml
concurrency:
  group: devin-issue-${{ github.repository_id }}-${{ github.event.issue.number || inputs.issue_number }}
  cancel-in-progress: false
```

Before calling Devin, the dispatcher creates or updates one bot comment
containing:

- a human-readable status table; and
- a hidden, versioned JSON state record.

Example hidden record:

```html
<!-- devin-issue-remediation
{"schema":"issue-remediation/v1","generation":1,"state":"dispatching",
"run_key":"github:123:issue:I_kwDO...:generation:1","session_id":null}
-->
```

The dispatcher re-reads the comment after writing it. If another nonterminal
generation owns the issue, it records `duplicate` and does not call Devin.

### 4.3 Devin session creation

The recommended pilot uses the documented v1 session API because it exposes
the features needed by an Actions-native coordinator:

- `POST /v1/sessions`;
- documented API idempotency;
- tag-filtered `GET /v1/sessions` recovery;
- `GET /v1/sessions/{session_id}`;
- `DELETE /v1/sessions/{session_id}`;
- playbook, repository, ACU, secret, and tag controls; and
- pull-request metadata on the session.

The GitHub claim remains the source of truth. API idempotency is a second
defense, not a substitute for the claim.

Create request:

```json
{
  "title": "Remediate ong6/superset issue #123",
  "prompt": "<bounded issue-remediation contract>",
  "idempotent": true,
  "max_acu_limit": 4,
  "playbook_id": "<configured issue-remediation playbook>",
  "repos": ["ong6/superset"],
  "secret_ids": [],
  "knowledge_ids": [],
  "tags": [
    "workflow:github-issue-remediation",
    "repo-id:123456",
    "issue:123",
    "generation:1",
    "run-key-hash:abcd1234"
  ],
  "unlisted": true
}
```

Use explicit empty secret and knowledge lists unless a reviewed allowlist is
configured. Devin uses its own repository integration to create a branch and
pull request; the Actions `GITHUB_TOKEN` and `DEVIN_API_KEY` never enter the
session.

Persist the returned session ID and URL in the issue state comment before the
dispatcher exits.

### 4.4 Prompt and playbook contract

The playbook supplies stable instructions. The per-run prompt supplies facts:

- repository and issue URL;
- issue number, title, and body as quoted untrusted task data;
- run key and generation;
- configured target branch;
- repository instructions to read;
- ACU and wall-clock constraints;
- required outcome: smallest reviewable change and a pull request;
- required PR text: `Fixes #<issue>`;
- required verification: relevant scoped tests and repository lint/typecheck;
- prohibited actions: direct merge, default-branch push, secret discovery,
  unrelated refactors, workflow-policy changes, or security-control removal.

Devin should investigate uncertainty rather than assume the issue report is
correct. If the issue is not reproducible, unsafe, underspecified, or requires
credentials, it should stop and surface the blocker instead of manufacturing a
patch.

### 4.5 Reconciliation

The reconciler runs from the trusted default branch:

```yaml
on:
  schedule:
    - cron: "*/5 * * * *"
  workflow_dispatch:
```

For every issue with an active remediation label, it:

1. reads and validates the hidden state record;
2. fetches the recorded Devin session;
3. maps the API status into the internal lifecycle;
4. discovers any session-linked pull request;
5. validates repository, base branch, issue link, and head ownership;
6. reads required GitHub check results for the pull request;
7. updates the same issue comment and status label;
8. uploads a redacted `run.json` artifact; and
9. terminates work that exceeds the configured deadline.

The reconciler must be idempotent. Reprocessing the same session and PR state
updates the existing comment and labels; it creates no second session,
comment, or pull request.

### 4.6 Cancellation

Closing the issue, removing `devin:fix`, or applying `devin:cancel` revokes
authorization.

The cancellation workflow:

1. claims the issue concurrency group;
2. reads the recorded session ID;
3. sends `DELETE /v1/sessions/{session_id}` when the session is active;
4. continues bounded reconciliation until terminal or cancellation timeout;
5. records `cancelled` even if the remote termination acknowledgement is
   delayed; and
6. removes active labels without deleting history.

## 5. State and outcome model

Keep four concepts separate:

1. **phase** — where the automation is;
2. **session status** — what the Devin API reports;
3. **terminal outcome** — why automation stopped; and
4. **business result** — what happened to the pull request afterward.

### Phases

```text
requested
  -> claimed
  -> dispatching
  -> session_running
  -> pull_request_open
  -> verifying
  -> succeeded
```

Nonterminal alternatives:

```text
needs_input
cancelling
```

Terminal outcomes:

```text
succeeded
duplicate
rejected
no_change
blocked
failed
verification_failed
timed_out
cancelled
```

Business results, tracked independently:

```text
no_pull_request
pull_request_open
ci_green
merged
closed_unmerged
```

### Session mapping

| API status | Internal behavior |
|---|---|
| `working`, `resumed`, or active request states | Continue bounded reconciliation. |
| `blocked` | Set `needs_input`; expose the blocker and wait until the deadline. |
| `expired` | Finish `timed_out`. |
| `finished` with a valid linked PR | Move to `pull_request_open` or `verifying`. |
| `finished` without a PR | Finish `no_change` only with a validated explicit result; otherwise `failed`. |
| Unknown value | Fail closed as `failed` with reason `unknown_session_status`. |

### Success contract

The automation may publish `succeeded` only when:

1. the recorded session is terminal;
2. it produced exactly one valid pull request in the configured repository;
3. the PR targets the configured base branch;
4. the PR body links the originating issue;
5. the PR remains open at the expected head SHA;
6. all configured required checks have completed successfully; and
7. no policy gate rejected the diff.

Devin's own test report is useful evidence but is not the success oracle.
Repository CI is independent because it executes outside the Devin session.

Merge is not required for automation success because it is a human governance
decision. Merge rate is tracked as an adoption and quality outcome.

### Failure taxonomy

| Reason | Meaning | Retry |
|---|---|---|
| `invalid_event` | Event, label, issue, or repository failed validation. | No |
| `unauthorized_actor` | Actor did not meet the configured permission. | No |
| `duplicate_generation` | Active or completed generation already owns the key. | No |
| `api_create_rejected` | Devin returned a non-retryable create error. | No |
| `api_create_unknown` | Create may have succeeded but response was lost. | Reconcile by tags before any retry |
| `api_poll_exhausted` | Polling failed beyond retry budget. | Operator/manual |
| `session_blocked` | Session requires information or access. | Human decision |
| `session_expired` | API or controller deadline expired. | New generation |
| `session_finished_no_pr` | Session ended without the required artifact. | New generation after review |
| `invalid_pull_request` | PR repo, base, head, or issue link failed policy. | No |
| `required_check_failed` | Independent verification failed. | Continue session only by explicit policy |
| `required_check_missing` | Required CI never appeared before deadline. | Operator/manual |
| `cancelled_by_user` | Authorization was revoked. | New generation |
| `unknown_session_status` | API returned an unsupported value. | No; update adapter |

## 6. Retry, timeout, and restart behavior

### API calls

- Retry `429`, `502`, `503`, and `504` with bounded exponential backoff and
  jitter.
- Honor `Retry-After`.
- Do not retry validation or authorization failures.
- Do not blindly retry a timed-out session-creation request.
- On ambiguous creation, query sessions by the unique tags and update the claim
  before deciding whether a new request is safe.

### Deadlines

Use separate limits:

- dispatcher runtime: 10 minutes;
- session ACU: configured in the create request;
- remediation wall clock: 6 hours for the demo, configurable;
- blocked wait: 2 hours;
- pull-request CI wait: 2 hours after the PR appears; and
- cancellation confirmation: 15 minutes.

### Restart recovery

Actions jobs are disposable. Recovery comes from GitHub and Devin:

- the issue comment stores the run key, generation, session ID, state, and
  transition version;
- labels identify active records;
- tags allow ambiguous-create recovery;
- session details expose terminal status and PR metadata;
- the pull request and checks expose verification; and
- scheduled reconciliation resumes from any persisted phase.

Use compare-and-set semantics on the transition version in the hidden state.
A stale reconciler must not overwrite a newer terminal outcome.

## 7. GitHub status experience

### Control labels

```text
devin:fix
devin:cancel
```

### Mutually exclusive status labels

```text
devin:queued
devin:running
devin:needs-input
devin:pr-open
devin:succeeded
devin:failed
devin:cancelled
```

### One updateable issue comment

Example:

```markdown
## Devin remediation

| Field | Value |
|---|---|
| Status | Verifying pull request |
| Started | 2026-09-08 11:30 UTC |
| Last update | 2026-09-08 11:47 UTC |
| Devin | `<session-url>` |
| Pull request | `<pull-request-url>` |
| Verification | 12 required checks: 10 passed, 2 running |
| Outcome | Pending |
| Run key | `github:...:generation:1` |

The next reconciliation is scheduled within five minutes.
```

Do not create a new comment on each poll. The issue timeline remains readable,
and the edit history preserves an audit trail.

GitHub Check Runs are not the primary issue status surface because they are
commit-scoped and an issue has no immutable head SHA. The remediation pull
request's ordinary Checks tab is the verification surface.

### Actions summaries and artifacts

Every job writes a concise `$GITHUB_STEP_SUMMARY` with:

- repository and issue;
- run key and generation;
- previous and next phase;
- API attempt and latency;
- session and PR links;
- verification counts;
- terminal outcome and reason; and
- next operator action when required.

Upload a redacted `run.json` artifact containing the same structured fields and
transition timestamps. Never upload the Devin API key, Actions token, raw
authorization headers, or unbounded issue/session text.

## 8. Observability

### Correlation fields

Every log, state record, and artifact should carry:

```text
repository_id
issue_node_id
issue_number
generation
run_key_hash
github_delivery_id
github_actions_run_id
devin_session_id
pull_request_number
pull_request_head_sha
phase
transition_version
attempt
duration_ms
terminal_outcome
terminal_reason
```

### Transition record

```json
{
  "schema": "issue-remediation-transition/v1",
  "at": "2026-09-08T11:47:00Z",
  "from": "pull_request_open",
  "to": "verifying",
  "reason": "required_checks_started",
  "actor": "reconciler",
  "github_actions_run_id": 123456789,
  "attempt": 1
}
```

Bound raw issue, session, and CI text before logging it. Record references and
hashes for larger evidence.

### Metrics

The pilot exporter can derive metrics from issue state comments, labels,
Actions runs, Devin sessions, pull requests, and checks:

| Metric | Type | Bounded labels |
|---|---|---|
| `issue_remediation_requests_total` | counter | `repo`, `result` |
| `issue_remediation_active` | gauge | `repo`, `phase` |
| `issue_remediation_completed_total` | counter | `repo`, `outcome`, `reason` |
| `issue_remediation_stage_duration_seconds` | histogram | `repo`, `stage`, `outcome` |
| `issue_remediation_end_to_end_seconds` | histogram | `repo`, `outcome` |
| `issue_remediation_duplicate_suppressed_total` | counter | `repo`, `key_type` |
| `issue_remediation_devin_sessions_total` | counter | `repo`, `outcome` |
| `issue_remediation_devin_acu_total` | counter | `repo`, `outcome` |
| `issue_remediation_cost_unknown_total` | counter | `repo`, `reason` |
| `issue_remediation_pull_requests_total` | counter | `repo`, `result` |
| `issue_remediation_ci_verifications_total` | counter | `repo`, `result` |
| `issue_remediation_merges_total` | counter | `repo`, `result` |
| `issue_remediation_cancellations_total` | counter | `repo`, `stage` |

Do not use issue number, branch, SHA, session ID, user, title, or error text as
metric labels.

### Dashboards

The pilot report should answer:

1. **Funnel:** authorized issues -> sessions -> PRs -> CI-green PRs -> merges.
2. **Status:** active count by phase and age of the oldest active generation.
3. **Quality:** no-PR finishes, verification failures, invalid PRs, and
   closed-unmerged PRs.
4. **Reliability:** API errors, ambiguous creates, duplicates, timeouts,
   cancellations, and stuck runs.
5. **Economics:** ACU per session, ACU per CI-green PR, and explicit unknown
   cost data.
6. **Adoption:** maintainer authorization rate, repeat use, merge rate, and
   median issue-to-PR and issue-to-green time.

For the Actions-native pilot, publish a daily workflow summary and retained
JSON/CSV artifact. The production controller can export the same schema to
Prometheus, OpenTelemetry, and a warehouse without changing domain semantics.

### Alerts and SLOs

| Objective | Initial target | Alert |
|---|---:|---|
| Label to visible queued status | p95 under 2 minutes | Three consecutive breaches |
| Label to session link | p95 under 5 minutes | Sustained breach |
| Reconciliation freshness | p95 under 10 minutes | Active state older than 15 minutes without update |
| Duplicate sessions | Zero per run key | Any occurrence |
| Unauthorized default-branch write | Zero | Any occurrence; disable dispatch |
| False success | Zero | CI-red or invalid PR marked succeeded |
| Stuck active generation | Zero older than 2x deadline | Any occurrence |
| API unknown-status rate | Zero | Any occurrence |

### Alerts without external infrastructure

The pilot can create or update one repository operations issue when:

- an active generation is stale;
- ambiguous session creation cannot be reconciled;
- a session status is unsupported;
- a supposedly successful PR becomes CI-red;
- duplicate sessions share one run key; or
- the dispatch kill switch is enabled.

The operations issue is separate from the user-facing remediation status and
is deduplicated by alert type.

## 9. Security and policy

### Trust boundaries

Treat these as untrusted:

- issue title, body, comments, and attachments;
- repository content;
- Devin output;
- branch names and PR descriptions; and
- CI logs and artifacts.

Treat these as privileged:

- `DEVIN_API_KEY`;
- Actions `GITHUB_TOKEN`;
- repository write permissions;
- configured playbook and repository allowlists; and
- status publication.

### Required controls

- Pin third-party Actions by full commit SHA.
- Use least-privilege workflow permissions.
- Keep `DEVIN_API_KEY` only in the Actions environment.
- Pass `secret_ids: []` to Devin by default.
- Use a dedicated Devin service identity and minimally scoped repository
  integration.
- Protect the default branch and require CI and human review.
- Validate the returned PR repository, base, head, and issue reference.
- Re-resolve issue and PR state before every write.
- Reject workflow, branch-protection, ownership, and security-policy changes
  unless the issue and maintainer authorization explicitly allow them.
- Add a repository variable kill switch such as
  `DEVIN_ISSUE_REMEDIATION_ENABLED=false`.
- Bound issue text, prompt size, log size, retries, ACU, wall clock, and active
  generations.

## 10. Implementation layout

```text
.github/workflows/
├── devin-issue-dispatch.yml
├── devin-issue-reconcile.yml
├── devin-issue-cancel.yml
└── devin-issue-report.yml

takehome/issue_remediation/
├── README.md
├── pyproject.toml
├── Dockerfile
├── src/issue_remediation/
│   ├── cli.py
│   ├── config.py
│   ├── models.py
│   ├── state.py
│   ├── github.py
│   ├── devin.py
│   ├── dispatch.py
│   ├── reconcile.py
│   ├── cancel.py
│   └── report.py
├── fixtures/
│   ├── issue_labeled.json
│   ├── session_working.json
│   ├── session_blocked.json
│   ├── session_finished_with_pr.json
│   ├── required_checks_green.json
│   └── required_checks_failed.json
└── tests/
    ├── test_dispatch.py
    ├── test_idempotency.py
    ├── test_reconcile.py
    ├── test_cancellation.py
    └── test_status_rendering.py
```

The Python package owns decisions and API contracts. Workflow YAML owns only
event wiring, permissions, secrets, concurrency, and invocation.

## 11. Workflow skeletons

### Dispatcher

```yaml
name: Devin issue remediation dispatch

on:
  issues:
    types: [labeled]
  workflow_dispatch:
    inputs:
      issue_number:
        description: Issue number to dispatch
        required: true
        type: number

permissions:
  contents: read
  issues: write
  pull-requests: read

concurrency:
  group: devin-issue-${{ github.repository_id }}-${{ github.event.issue.number || inputs.issue_number }}
  cancel-in-progress: false

jobs:
  dispatch:
    if: >-
      github.event_name == 'workflow_dispatch' ||
      github.event.label.name == 'devin:fix'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<full-commit-sha>
      - uses: actions/setup-python@<full-commit-sha>
        with:
          python-version: "3.12"
      - run: pip install ./takehome/issue_remediation
      - run: >-
          python -m issue_remediation dispatch
          --event "$GITHUB_EVENT_PATH"
          --issue-number "$ISSUE_NUMBER"
        env:
          DEVIN_API_KEY: ${{ secrets.DEVIN_API_KEY }}
          GITHUB_TOKEN: ${{ github.token }}
          ISSUE_NUMBER: ${{ github.event.issue.number || inputs.issue_number }}
```

### Reconciler

```yaml
name: Devin issue remediation reconcile

on:
  schedule:
    - cron: "*/5 * * * *"
  workflow_dispatch:

permissions:
  actions: read
  checks: read
  contents: read
  issues: write
  pull-requests: read

jobs:
  reconcile:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<full-commit-sha>
      - uses: actions/setup-python@<full-commit-sha>
        with:
          python-version: "3.12"
      - run: pip install ./takehome/issue_remediation
      - run: python -m issue_remediation reconcile --all-active
        env:
          DEVIN_API_KEY: ${{ secrets.DEVIN_API_KEY }}
          GITHUB_TOKEN: ${{ github.token }}
```

The implementation must replace placeholders with reviewed immutable Action
commit SHAs.

## 12. Deterministic test plan

### Contract tests

- strict parsing of issue, session, PR, and check responses;
- unsupported status fails closed;
- redaction removes credentials and bounds untrusted text;
- status comment round-trips the hidden schema;
- API errors map to the documented failure taxonomy.

### State-machine tests

- one label delivery creates one claim and one session;
- concurrent duplicate events create one session;
- an active issue cannot start a second generation;
- a terminal issue can start generation two only after explicit reauthorization;
- blocked, expired, finished-without-PR, cancelled, and unknown statuses remain
  non-success;
- stale reconcilers cannot overwrite newer transition versions.

### GitHub policy tests

- closed issues and pull-request-shaped issue events reject;
- unauthorized actors reject;
- invalid repository or base branch rejects;
- a PR without the issue link rejects;
- failed or missing required checks cannot become success;
- closing the issue or removing authorization cancels active work.

### End-to-end fixture

Create one honest, narrowly scoped Superset issue with:

- a reproducible boundary defect;
- the exact expected behavior;
- a focused failing test command;
- an implementation scope small enough for one PR; and
- no security-sensitive or production-only data.

The showcase succeeds only when:

1. a maintainer applies `devin:fix`;
2. the issue immediately shows queued/running status;
3. exactly one Devin session appears;
4. Devin opens a linked remediation PR;
5. the PR's scoped test and required CI pass;
6. the issue status becomes `succeeded`;
7. replaying the event creates no duplicate;
8. a cancellation fixture visibly terminates non-successfully; and
9. the run artifact exposes the complete transition history.

## 13. Delivery sequence

### Pull request 1: deterministic local controller

- package, Dockerfile, strict models, state machine, fake adapters, fixtures,
  status renderer, and tests;
- local `dispatch`, `reconcile`, `cancel`, and `show-run` commands; and
- no live credentials.

### Pull request 2: live dispatch and status

- pinned dispatcher and reconciler workflows;
- GitHub and Devin API adapters;
- issue labels and one updateable comment;
- duplicate, retry, timeout, and cancellation handling; and
- dry-run mode enabled by default.

### Pull request 3: controlled remediation proof

- reviewed playbook;
- write-enabled Devin repository integration limited to branch and PR creation;
- seeded issue;
- required-check policy;
- daily observability report; and
- recorded success, failure, duplicate, timeout, and cancellation runs.

## 14. Production expansion

Move to the external controller when any of these become true:

- more than a small allowlist of repositories;
- reconciliation must be faster than the Actions schedule;
- active run volume makes issue scanning inefficient;
- centralized audit retention exceeds GitHub artifact retention;
- multiple policy versions or customer-specific controls are required;
- webhook-to-session atomicity needs a database transaction; or
- Prometheus/OpenTelemetry and cost allocation become mandatory.

The production service should preserve the same run key, state machine, failure
taxonomy, status renderer, Devin tags, and success contract. GitHub Actions can
remain the visible manual trigger and emergency fallback.

## 15. Definition of done

- A real GitHub issue can trigger the automation through `devin:fix`.
- The workflow uses the Devin API rather than a manually started session.
- Duplicate event delivery creates one session.
- The issue always exposes queued, active, blocked, succeeded, failed,
  cancelled, or timed-out status.
- A linked PR is created by the managed session.
- Success requires repository CI, not Devin self-report.
- Cancellation revokes authorization and requests session termination.
- Restart recovery resumes from GitHub and Devin state.
- A local Docker run replays the dispatcher and reconciler fixtures.
- The observability report shows funnel, latency, outcomes, duplicates,
  timeouts, cancellations, merge results, and ACU or explicit cost unknowns.
- The five-minute demo shows one issue-to-green-PR path and one non-success
  path without hidden manual state repair.
