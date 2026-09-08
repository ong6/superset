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
  -> GitHub Actions validates the issue contract and pins the target SHA
  -> a clean preflight reproduces the issue before one bounded Devin session
  -> Devin investigates and returns a structured patch proposal
  -> a clean verifier applies the patch and runs controller-owned acceptance
  -> a controlled writer opens one pull request after verification
  -> repository CI independently verifies the published change
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

The implementation has four entry workflows plus one internal reusable
per-issue reconciliation worker:

1. **dispatch** on the `devin:fix` label;
2. **reconcile** on a five-minute schedule and manual dispatch;
3. **cancel** when the issue closes or authorization is removed; and
4. **report** on a schedule or manual dispatch to aggregate pilot outcomes.

The reconcile entry workflow discovers active issue numbers and invokes the
worker once per issue. Dispatch, cancellation, and each worker invocation use
the exact same per-issue concurrency-group format.

An external controller is the production expansion path when multiple
repositories, lower reconciliation latency, centralized policy, or stronger
analytics justify another service.

## 2. Product boundary

### Pilot input

- one open issue in `ong6/superset`;
- one valid `issue-remediation/v1` contract in that issue;
- one maintainer-applied `devin:fix` label;
- one issue generation at a time;
- one configured Devin playbook and repository;
- one immutable target SHA;
- one bounded, read-only Devin session; and
- one pull request targeting the configured default branch.

### Pilot output

- one updateable issue status comment;
- one mutually exclusive status label;
- one linked Devin session;
- one clean-room preflight and verification record;
- one remediation pull request;
- normal repository CI as the independent verification oracle; and
- one machine-readable run artifact per dispatcher or reconciler execution.

### Non-goals

- no automatic execution for every newly opened public issue;
- no direct push to the default branch;
- no autonomous merge, approval, or branch-protection bypass;
- no GitHub token, Actions token, or publisher secret passed to Devin;
- no branch push or pull-request creation by Devin;
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
  -> validate contract, pin SHA, reproduce, claim, and create session

schedule / workflow_dispatch
  -> poll active sessions, verify proposals, publish, and track linked PRs
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
- the issue contains exactly one valid `issue-remediation/v1` contract;
- every command identifier and allowed path is permitted by policy;
- no nonterminal remediation generation already owns the issue; and
- the actor has the configured repository permission.

The label is the write-authorization gate. GitHub restricts label mutation to
repository users with suitable permissions, but the controller should still
resolve the actor's effective permission through the GitHub API and record it.

Do not trigger on every `issues.opened` event. Public issue titles and bodies
are untrusted and can be noisy, incomplete, malicious, or too broad. After the
pilot, a trusted issue form or triage rule may apply `devin:fix`
automatically.

The machine-readable contract is data, not executable text:

```yaml
schema_version: issue-remediation/v1
target_branch: master
problem: Report phase reserves equal to the budget are accepted
expected_behavior: Equality is rejected before report execution starts
reproduction_command_id: report-execution-boundary
acceptance_command_ids:
  - report-execution-config-tests
allowed_paths:
  - superset/utils/report_execution.py
risk: low
patch_mode: propose
```

The issue form places this document under one fixed heading in exactly one
YAML-rendered textarea. Parse only that fenced block with a safe YAML loader
and a strict schema with unknown fields rejected. Resolve command IDs through
a versioned, controller-owned policy file containing argv arrays; never
execute a command or shell fragment supplied by issue text.
Require the configured repository and default target branch in the pilot.
Canonicalize allowed paths and reject traversal, glob expansion, symlinks,
submodules, credentials, executable-bit changes, workflow files, ownership
rules, and security-policy files in the pilot. Bound every string, list,
command count, path count, and total contract size.

After validation and authorization, resolve `target_branch` through the GitHub
API and persist its full SHA. A clean checkout at that SHA runs the configured
reproduction command before Devin starts. A missing, passing, or inconclusive
preflight ends as `evidence_failed`; it is not permission to ask Devin to
discover a failure nondeterministically. Re-resolve the target branch after
preflight and before session creation; if it moved, finish `stale_sha` and
require a new generation. Hash canonical JSON containing the repository ID,
target SHA, command-policy version, command ID and argv, verifier image digest,
exit code, and a hash of normalized bounded redacted output. Record wall-clock
duration separately so timing jitter does not change the evidence identity.
Each command policy defines the normalization for timestamps, temporary paths,
durations, and unordered records; unknown nondeterministic output is
`inconclusive`, not silently discarded.

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

Select the record by its fixed marker and configured bot author, then validate
it with a strict schema. Treat every other issue comment as untrusted display
content.

Example hidden record:

```html
<!-- devin-issue-remediation
{"schema":"issue-remediation/v1","generation":1,"state":"creating_session",
"run_key":"github:123:issue:I_kwDO...:generation:1",
"target_sha":"<full-sha>","evidence_hash":"<sha256>","session_id":null}
-->
```

The dispatcher re-reads the comment after writing it. If another nonterminal
generation owns the issue, it records `duplicate` and does not call Devin.

### 4.3 Devin session creation

Use the current organization-scoped v3 session lifecycle:

- `POST /v3/organizations/{org_id}/sessions`;
- `GET /v3/organizations/{org_id}/sessions`;
- `GET /v3/organizations/{org_id}/sessions/{devin_id}`; and
- `DELETE /v3/organizations/{org_id}/sessions/{devin_id}`.

Use `https://api.devin.ai` as the configured base URL,
`Authorization: Bearer ${DEVIN_API_TOKEN}`, and a reviewed
`DEVIN_ORG_ID` repository variable. Log only response status, request ID,
session ID, bounded error category, and timing; never log headers or tokens.

The GitHub claim and serialized per-issue concurrency are the idempotency
boundary. The v3 create request has no idempotency field. Before the call,
persist a `creating` transition and a unique run-key tag. If the response is
ambiguous, list only the recent organization sessions, match the exact unique
tags client-side, and adopt one unambiguous match. If zero or multiple matches
remain, finish `api_create_unknown`; never issue a blind second create.

Create request:

```json
{
  "title": "Remediate ong6/superset issue #123",
  "prompt": "<bounded issue-remediation contract>",
  "max_acu_limit": 4,
  "playbook_id": "<configured issue-remediation playbook>",
  "repos": ["ong6/superset"],
  "secret_ids": [],
  "knowledge_ids": [],
  "resumable": false,
  "structured_output_required": true,
  "structured_output_schema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "schema_version": { "const": "issue-remediation-result/v1" },
      "outcome": {
        "enum": ["proposed", "no_change", "blocked", "failed"]
      },
      "summary": { "type": "string", "maxLength": 1000 },
      "patch": { "type": "string", "maxLength": 40000 },
      "changed_paths": {
        "type": "array",
        "maxItems": 12,
        "items": { "type": "string", "maxLength": 300 }
      },
      "evidence": {
        "type": "array",
        "maxItems": 8,
        "items": { "type": "string", "maxLength": 500 }
      },
      "verification_commands": {
        "type": "array",
        "maxItems": 8,
        "items": { "type": "string", "maxLength": 300 }
      }
    },
    "required": [
      "schema_version",
      "outcome",
      "summary",
      "patch",
      "changed_paths",
      "evidence",
      "verification_commands"
    ]
  },
  "tags": [
    "workflow:github-issue-remediation",
    "repo-id:123456",
    "issue:123",
    "generation:1",
    "run-key-hash:abcd1234"
  ]
}
```

Apply cross-field validation after JSON Schema: `proposed` requires a nonempty
patch, while every other outcome requires an empty patch and empty path list.
Treat `changed_paths` and `verification_commands` as untrusted claims for
display only; Git and the command policy remain authoritative.

Use explicit empty secret and knowledge lists unless a reviewed allowlist is
configured. The selected Devin service identity and repository integration are
read-only. Devin returns a bounded unified diff in structured output; it does
not push, create a branch, or open a pull request. The Actions
`GITHUB_TOKEN`, publisher token, and `DEVIN_API_TOKEN` never enter the session.

Persist the returned session ID and URL in the issue state comment before the
dispatcher exits.

### 4.4 Prompt and playbook contract

The playbook supplies stable instructions. The per-run prompt supplies facts:

- repository and issue URL;
- issue number, title, and body as quoted untrusted task data;
- run key and generation;
- target branch and pinned full SHA;
- the controller-owned reproduction result and evidence hash;
- controller-resolved command IDs and allowed paths;
- repository instructions to read;
- ACU and wall-clock constraints;
- required outcome: the smallest reviewable unified diff or an explicit
  non-proposal outcome;
- required verification evidence, while making clear that the controller owns
  the acceptance decision; and
- prohibited actions: repository writes, branch or PR creation, secret
  discovery, unrelated refactors, workflow-policy changes, or
  security-control removal.

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

For every issue with an active remediation label, the per-issue worker:

1. reads and validates the hidden state record;
2. fetches the recorded Devin session;
3. maps `status` and `status_detail` into the internal lifecycle;
4. validates the exact structured-output schema;
5. applies a proposed patch in a fresh checkout rooted at the pinned SHA;
6. derives the diff and changed paths from Git and enforces policy;
7. runs controller-owned acceptance commands in an isolated clean-verifier
   container;
8. re-resolves the target branch and fails `stale_sha` if it moved;
9. emits a hash-bound verified-publication artifact;
10. lets the isolated publisher revalidate state, mint a short-lived token,
    and create or update one bot PR;
11. reads required GitHub check results for the pull request;
12. updates the same issue comment and status label;
13. uploads a redacted `run.json` artifact; and
14. terminates work that exceeds the configured deadline.

The reconciler must be idempotent. Reprocessing the same session and PR state
updates the existing comment and labels; it creates no second session,
comment, or pull request.

### 4.6 Verification and publication boundary

The verifier starts from a fresh checkout of the recorded target SHA with
checkout credentials disabled. It writes the bounded patch to a regular file,
runs `git apply --check`, applies it without three-way fallback, and computes
the authoritative diff. It rejects:

- paths outside the canonical issue allowlist;
- symlinks, submodules, path traversal, special files, executable-bit changes,
  binary patches, and an empty or oversized diff;
- credentials, token-like material, workflow definitions, ownership rules,
  repository automation policy, or security-policy files;
- edits to tests or fixtures unless the issue contract explicitly permits
  those paths; and
- any mismatch between the pinned SHA, worktree base, patch hash, and recorded
  state.

Verification runs the issue's controller-owned acceptance command IDs in a
fixed nested container, not directly in the secret-bearing reconciler process.
Run it with network disabled, an isolated PID and user namespace, no host
`/proc` or container-engine socket, only the target worktree and scratch
mounts, no Devin or publisher credential, and bounded CPU, memory, output, and
wall clock. The controller records argv, exit code, duration, bounded redacted
output, environment image digest, and evidence hash. Each command receives an
explicit allowlisted environment rather than inheriting the controller
process, so `DEVIN_API_TOKEN`, `GITHUB_TOKEN`, Actions runtime tokens, and
publisher material are absent. The outer controller, not the sandbox, derives
the authoritative diff and publication record. Devin-suggested commands may
be displayed but are never executed unless they resolve to an already
allowlisted command ID.

Immediately before publication, resolve the target branch again. A mismatch is
terminal `stale_sha`; never silently rebase or apply the patch to a newer base.
Only a verified, nonstale patch enters the writer. The writer mints a
short-lived GitHub App installation token, pushes a deterministic branch such
as `devin/remediate-123-g1-090d330`, and creates or updates the single PR
identified by the run-key marker. It derives the PR head SHA from GitHub after
the push and persists it before monitoring CI.

### 4.7 Cancellation

Closing the issue, removing `devin:fix`, or applying `devin:cancel` revokes
authorization.

The cancellation workflow:

1. claims the issue concurrency group;
2. reads the recorded session ID;
3. sends
   `DELETE /v3/organizations/{org_id}/sessions/{devin_id}` when the session
   is active;
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
  -> validated
  -> authorized
  -> target_pinned
  -> evidence_ready
  -> claimed
  -> creating_session
  -> session_running
  -> proposed
  -> verifying
  -> publishing
  -> pull_request_open
  -> ci_verifying
  -> succeeded
```

Nonterminal alternatives:

```text
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
policy_violation
stale
publish_failed
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
| `new`, `claimed`, `resuming`, or `running/working` | Continue bounded reconciliation. |
| `running/waiting_for_user` or `running/waiting_for_approval` | Request termination and finish `blocked` with `interaction_required`; unattended automation never responds or approves. |
| `running/finished` | Continue polling for the terminal API status within the deadline. |
| `exit` with valid structured output | Map the declared outcome, then independently verify any proposal. |
| `exit` with missing or malformed structured output | Finish `failed` with `malformed_output`. |
| `suspended` | Map the documented suspension reason to timeout, budget, quota, user cancellation, or API failure; never success. |
| `error` | Finish `failed` and retain the bounded API reason. |
| Unknown value | Fail closed as `failed` with reason `unknown_session_status`. |

### Success contract

The automation may publish `succeeded` only when:

1. the recorded session is terminal;
2. its output passed the exact structured-output schema;
3. the proposed patch applied cleanly to a fresh checkout at the pinned SHA;
4. Git-derived paths and file modes passed the issue and global policy;
5. controller-owned acceptance commands passed outside the Devin session;
6. the target branch still resolved to the pinned SHA before publication;
7. the controlled writer produced exactly one valid pull request;
8. the PR targets the configured base branch and links the issue;
9. the PR remains open at the published head SHA; and
10. all configured required checks completed successfully.

Devin's own test report is useful evidence but is not the success oracle.
Repository CI is independent because it executes outside the Devin session.

Merge is not required for automation success because it is a human governance
decision. Merge rate is tracked as an adoption and quality outcome.

### Failure taxonomy

| Reason | Meaning | Retry |
|---|---|---|
| `invalid_event` | Event, label, issue, or repository failed validation. | No |
| `invalid_issue_contract` | Contract schema, command IDs, paths, or risk tier failed validation. | No |
| `unauthorized_actor` | Actor did not meet the configured permission. | No |
| `evidence_failed` | Clean preflight could not reproduce the issue deterministically. | Human review |
| `duplicate_generation` | Active or completed generation already owns the key. | No |
| `api_create_rejected` | Devin returned a non-retryable create error. | No |
| `api_create_unknown` | Create may have succeeded but recent v3 sessions did not yield exactly one tag match. | Operator/manual |
| `api_poll_exhausted` | Polling failed beyond retry budget. | Operator/manual |
| `interaction_required` | Session requested input or approval. | New generation after review |
| `malformed_output` | Required v3 structured output was missing or invalid. | New generation after review |
| `session_no_proposal` | Session returned `no_change`, `blocked`, or `failed`. | Human decision |
| `patch_apply_failed` | Proposed diff did not apply to the pinned SHA. | New generation |
| `policy_violation` | Git-derived paths, modes, or content exceeded policy. | No |
| `verification_failed` | Clean-room acceptance failed. | New generation after review |
| `stale_sha` | Target branch moved before publication. | New generation |
| `publish_failed` | Controlled branch or PR publication failed. | Bounded retry |
| `invalid_pull_request` | PR repo, base, head, or issue link failed policy. | No |
| `required_check_failed` | Required pull-request CI failed. | Human review or new generation |
| `required_check_missing` | Required CI never appeared before deadline. | Operator/manual |
| `session_timed_out` | Controller wall-clock or session deadline expired. | New generation |
| `budget_exhausted` | ACU or organization quota stopped the session. | Operator/manual |
| `cancelled_by_user` | Authorization was revoked. | New generation |
| `unknown_session_status` | API returned an unsupported value. | No; update adapter |

## 6. Retry, timeout, and restart behavior

### API calls

- Retry `429`, `502`, `503`, and `504` with bounded exponential backoff and
  jitter.
- Honor `Retry-After`.
- Do not retry validation or authorization failures.
- Do not blindly retry a timed-out session-creation request.
- On ambiguous creation, scan a bounded recent page of v3 organization
  sessions for the exact unique tags. Adopt exactly one match; otherwise stop.

### Deadlines

Use separate limits:

- dispatcher runtime: 10 minutes;
- session ACU: configured in the create request;
- remediation wall clock: 6 hours for the demo, configurable;
- pull-request CI wait: 2 hours after the PR appears; and
- cancellation confirmation: 15 minutes.

### Restart recovery

Actions jobs are disposable. Recovery comes from GitHub and Devin:

- the issue comment stores the run key, generation, session ID, state, and
  transition version, pinned SHA, evidence hash, and patch hash;
- labels identify active records;
- tags allow bounded ambiguous-create recovery;
- session details expose status, status detail, ACU, and structured output;
- clean-room artifacts expose policy and acceptance results;
- the pull request and checks expose publication and CI verification; and
- scheduled reconciliation resumes from any persisted phase.

All issue-state writers use the same per-issue Actions concurrency group.
Within that serialized boundary, re-read the bot-authored comment and compare
its transition version immediately before every write. A stale reconciler must
not overwrite a newer terminal outcome. This is a pilot serialization
mechanism, not a substitute for the transactional database used by the
production controller.

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
devin:verifying
devin:publishing
devin:pr-open
devin:ci-verifying
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
| Target | `master@<full-sha>` |
| Preflight | Reproduced; evidence `<sha256>` |
| Clean verification | Passed; patch `<sha256>` |
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
transition timestamps. Never upload the Devin API token, Actions token, raw
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
target_branch
target_sha
evidence_hash
patch_hash
policy_version
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
  "to": "ci_verifying",
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
| `issue_remediation_clean_verifications_total` | counter | `repo`, `result` |
| `issue_remediation_ci_verifications_total` | counter | `repo`, `result` |
| `issue_remediation_merges_total` | counter | `repo`, `result` |
| `issue_remediation_cancellations_total` | counter | `repo`, `stage` |

Do not use issue number, branch, SHA, session ID, user, title, or error text as
metric labels.

### Dashboards

The pilot report should answer:

1. **Funnel:** authorized issues -> sessions -> PRs -> CI-green PRs -> merges.
2. **Status:** active count by phase and age of the oldest active generation.
3. **Quality:** no-proposal finishes, verification failures, invalid PRs, and
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

- `DEVIN_API_TOKEN`;
- Actions `GITHUB_TOKEN`;
- short-lived publisher credentials;
- repository write permissions;
- configured playbook and repository allowlists; and
- status publication.

### Required controls

- Pin third-party Actions by full commit SHA.
- Use least-privilege workflow permissions.
- Keep `DEVIN_API_TOKEN` only in the Actions environment.
- Pass `secret_ids: []` to Devin by default.
- Use a dedicated Devin service identity with read-only repository access.
- Use `structured_output_required: true`, validate the exact JSON Schema, and
  bound the inline unified diff.
- Build the prompt from parsed event JSON and validated contract fields; never
  interpolate issue text into a shell script or heredoc.
- Protect the default branch and require CI and human review.
- Apply the proposal in a fresh checkout rooted at the pinned SHA and derive
  changed paths and modes from Git.
- Run only policy-owned argv commands outside the Devin session and inside a
  networkless sandbox that cannot inspect the reconciler process or its
  credentials.
- Re-resolve the target branch before publication and fail `stale_sha` when it
  moved.
- Mint a short-lived GitHub App installation token only after verification.
  The controlled writer uses it to push a deterministic bot branch and open or
  update one PR; the token is never exposed to Devin.
- Validate the published PR repository, base, head, issue reference, and
  stable run-key marker.
- Re-resolve issue and PR state before every write.
- Reject workflow, branch-protection, ownership, and security-policy changes
  unless the issue and maintainer authorization explicitly allow them.
- Add a repository variable kill switch such as
  `DEVIN_ISSUE_REMEDIATION_ENABLED=false`.
- Bound issue text, prompt size, log size, retries, ACU, wall clock, and active
  generations.

The pilot may use a fine-grained bot PAT if creating a GitHub App is outside
the take-home setup budget, but the token must be restricted to this fork and
only `Contents: write` plus `Pull requests: write`. A short-lived installation
token is the production default. The workflow's ordinary `GITHUB_TOKEN`
remains read-mostly because GitHub suppresses most workflow runs caused by
that token; using the dedicated publisher identity ensures normal PR CI can
start.

## 10. Implementation layout

```text
.github/workflows/
├── devin-issue-dispatch.yml
├── devin-issue-reconcile.yml
├── devin-issue-reconcile-one.yml
├── devin-issue-cancel.yml
└── devin-issue-report.yml

.github/ISSUE_TEMPLATE/
└── devin-remediation.yml

takehome/issue_remediation/
├── README.md
├── pyproject.toml
├── Dockerfile
├── src/issue_remediation/
│   ├── cli.py
│   ├── config.py
│   ├── models.py
│   ├── state.py
│   ├── contract.py
│   ├── command_policy.py
│   ├── evidence.py
│   ├── github.py
│   ├── devin.py
│   ├── dispatch.py
│   ├── reconcile.py
│   ├── verify.py
│   ├── publish.py
│   ├── cancel.py
│   └── report.py
├── fixtures/
│   ├── issue_labeled.json
│   ├── issue_contract_valid.yml
│   ├── issue_contract_invalid.yml
│   ├── reproduction_failed.json
│   ├── session_working.json
│   ├── session_waiting_for_user.json
│   ├── session_waiting_for_approval.json
│   ├── session_exit_proposed.json
│   ├── session_exit_malformed.json
│   ├── patch_disallowed_path.diff
│   ├── target_stale.json
│   ├── required_checks_green.json
│   └── required_checks_failed.json
└── tests/
    ├── test_dispatch.py
    ├── test_contract.py
    ├── test_evidence.py
    ├── test_idempotency.py
    ├── test_reconcile.py
    ├── test_verify.py
    ├── test_publish.py
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
        with:
          persist-credentials: false
      - uses: actions/setup-python@<full-commit-sha>
        with:
          python-version: "3.12"
      - run: pip install ./takehome/issue_remediation
      - run: >-
          python -m issue_remediation dispatch
          --event "$GITHUB_EVENT_PATH"
          --issue-number "$ISSUE_NUMBER"
        env:
          DEVIN_API_TOKEN: ${{ secrets.DEVIN_API_TOKEN }}
          DEVIN_ORG_ID: ${{ vars.DEVIN_ORG_ID }}
          GITHUB_TOKEN: ${{ github.token }}
          ISSUE_NUMBER: ${{ github.event.issue.number || inputs.issue_number }}
```

### Reconciler entry

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
  discover:
    permissions:
      contents: read
      issues: read
      pull-requests: read
    runs-on: ubuntu-latest
    outputs:
      issue_numbers: ${{ steps.discover.outputs.issue_numbers }}
    steps:
      - uses: actions/checkout@<full-commit-sha>
        with:
          persist-credentials: false
      - uses: actions/setup-python@<full-commit-sha>
        with:
          python-version: "3.12"
      - run: pip install ./takehome/issue_remediation
      - id: discover
        run: >-
          python -m issue_remediation discover
          --github-output "$GITHUB_OUTPUT"
        env:
          GITHUB_TOKEN: ${{ github.token }}

  reconcile:
    needs: discover
    strategy:
      max-parallel: 4
      matrix:
        issue_number: ${{ fromJSON(needs.discover.outputs.issue_numbers) }}
    uses: ./.github/workflows/devin-issue-reconcile-one.yml
    with:
      issue_number: ${{ matrix.issue_number }}
    secrets: inherit
```

### Reusable per-issue worker

```yaml
name: Devin issue remediation reconcile one

on:
  workflow_call:
    inputs:
      issue_number:
        required: true
        type: number

permissions:
  actions: read
  checks: read
  contents: read
  issues: write
  pull-requests: read

concurrency:
  group: devin-issue-${{ github.repository_id }}-${{ inputs.issue_number }}
  cancel-in-progress: false

jobs:
  reconcile:
    runs-on: ubuntu-latest
    outputs:
      publish: ${{ steps.reconcile.outputs.publish }}
      verified_artifact: ${{ steps.reconcile.outputs.verified_artifact }}
    steps:
      - uses: actions/checkout@<full-commit-sha>
        with:
          persist-credentials: false
      - uses: actions/setup-python@<full-commit-sha>
        with:
          python-version: "3.12"
      - run: pip install ./takehome/issue_remediation
      - id: reconcile
        run: >-
          python -m issue_remediation reconcile
          --issue-number "$ISSUE_NUMBER"
          --github-output "$GITHUB_OUTPUT"
        env:
          DEVIN_API_TOKEN: ${{ secrets.DEVIN_API_TOKEN }}
          DEVIN_ORG_ID: ${{ vars.DEVIN_ORG_ID }}
          GITHUB_TOKEN: ${{ github.token }}
          ISSUE_NUMBER: ${{ inputs.issue_number }}
      - if: steps.reconcile.outputs.publish == 'true'
        uses: actions/upload-artifact@<full-commit-sha>
        with:
          name: ${{ steps.reconcile.outputs.verified_artifact }}
          path: ${{ runner.temp }}/verified-publication
          if-no-files-found: error
          retention-days: 1

  publish:
    needs: reconcile
    if: needs.reconcile.outputs.publish == 'true'
    runs-on: ubuntu-latest
    environment: devin-remediation-publisher
    steps:
      - uses: actions/checkout@<full-commit-sha>
        with:
          persist-credentials: false
      - uses: actions/setup-python@<full-commit-sha>
        with:
          python-version: "3.12"
      - uses: actions/download-artifact@<full-commit-sha>
        with:
          name: ${{ needs.reconcile.outputs.verified_artifact }}
          path: ${{ runner.temp }}/verified-publication
      - run: pip install ./takehome/issue_remediation
      - run: >-
          python -m issue_remediation publish
          --verified-record "$RUNNER_TEMP/verified-publication/run.json"
          --issue-number "$ISSUE_NUMBER"
        env:
          PUBLISHER_APP_ID: ${{ vars.PUBLISHER_APP_ID }}
          PUBLISHER_PRIVATE_KEY: ${{ secrets.PUBLISHER_PRIVATE_KEY }}
          GITHUB_TOKEN: ${{ github.token }}
          ISSUE_NUMBER: ${{ inputs.issue_number }}
```

The implementation must replace placeholders with reviewed immutable Action
commit SHAs. The publish job validates the artifact hash, current issue state,
authorization label, target SHA, and transition version before minting the
installation token. It never applies or executes the proposed patch; it runs
only the reviewed publisher code from the trusted default branch. The
reconcile command must launch acceptance commands in the isolated verifier
sandbox described above; scrubbing child-process environment variables without
process and network isolation is insufficient.

## 12. Deterministic test plan

### Contract tests

- strict parsing of issue contract, event, v3 session, PR, and check responses;
- unknown contract fields, shell-valued command fields, unknown command IDs,
  and noncanonical paths reject before any Devin API call;
- unsupported status fails closed;
- `waiting_for_user` and `waiting_for_approval` terminate as
  `interaction_required`;
- malformed or missing structured output fails closed;
- redaction removes credentials and bounds untrusted text;
- status comment round-trips the hidden schema;
- API errors map to the documented failure taxonomy.

### State-machine tests

- one label delivery creates one claim and one session;
- concurrent duplicate events create one session;
- clean preflight and evidence hashing precede session creation;
- an active issue cannot start a second generation;
- a terminal issue can start generation two only after explicit reauthorization;
- suspended, interaction-required, no-proposal, cancelled, and unknown statuses
  remain non-success;
- stale reconcilers cannot overwrite newer transition versions.

### GitHub policy tests

- closed issues and pull-request-shaped issue events reject;
- unauthorized actors reject;
- invalid repository or base branch rejects;
- target movement before session creation or publication rejects as
  `stale_sha`;
- disallowed paths, symlink escapes, submodules, credentials, workflow files,
  and false changed-path claims reject;
- Devin-reported success with a failing clean-room command becomes
  `verification_failed` and creates no branch;
- a PR without the issue link rejects;
- failed or missing required checks cannot become success;
- closing the issue or removing authorization cancels active work.

### End-to-end fixture

Create one honest, narrowly scoped Superset issue with:

- a reproducible boundary defect;
- the exact expected behavior;
- a focused failing-test command ID and acceptance command ID;
- an implementation scope small enough for one PR; and
- no security-sensitive or production-only data.

The showcase succeeds only when:

1. a maintainer applies `devin:fix`;
2. the issue immediately shows queued/running status;
3. exactly one Devin session appears;
4. Devin returns one structured patch without repository writes;
5. the clean verifier applies the patch and the scoped acceptance command
   passes;
6. the controlled writer opens one linked remediation PR;
7. the PR's required CI passes;
8. the issue status becomes `succeeded`;
9. replaying the event creates no duplicate;
10. cancellation and stale-SHA fixtures visibly terminate non-successfully;
    and
11. the run artifact exposes the complete transition history, hashes, ACU,
    and policy version.

## 13. Delivery sequence

### Pull request 1: deterministic local controller

- package, Dockerfile, strict models, state machine, fake adapters, fixtures,
  status renderer, and tests;
- local `dispatch`, `reconcile`, `cancel`, and `show-run` commands; and
- no live credentials.

### Pull request 2: live dispatch and status

- pinned dispatcher and reconciler workflows;
- GitHub and Devin API adapters;
- clean checkout, patch-policy, verification, and controlled-writer adapters;
- issue labels and one updateable comment;
- duplicate, retry, timeout, and cancellation handling; and
- dry-run mode enabled by default.

### Pull request 3: controlled remediation proof

- reviewed playbook and read-only Devin repository integration;
- short-lived controlled publisher identity;
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
- A strict issue contract and clean preflight pass before session creation.
- The issue always exposes queued, active, blocked, succeeded, failed,
  cancelled, or timed-out status.
- Devin returns validated structured output and never receives publisher
  credentials.
- A clean verifier derives the diff, enforces policy, and runs acceptance
  before a controlled writer creates the linked PR.
- Success requires clean-room verification and repository CI, not Devin
  self-report.
- Cancellation revokes authorization and requests session termination.
- Restart recovery resumes from GitHub and Devin state.
- A local Docker run replays the dispatcher and reconciler fixtures.
- The observability report shows funnel, latency, outcomes, duplicates,
  timeouts, cancellations, merge results, and ACU or explicit cost unknowns.
- The five-minute demo shows one issue-to-green-PR path and one non-success
  path without hidden manual state repair.
