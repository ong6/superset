<!--
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.
-->

# Devin Issue Autopilot

A small polling controller that turns `devin-fix` issues in `ong6/superset`
into bounded Devin sessions, independently verifies their pull requests, and
records the result on GitHub and in SQLite.

Run every command below from this `devin-issue-autopilot` directory inside a
clone of `ong6/superset`.

## Architecture

```text
GitHub issue + devin-fix
          |
          v
  poller / idempotency ----> SQLite runs + transitions
          |
          v
  pinned default-branch SHA + issue URL
          |
          v
  Devin API v3 session ----> one nudge / ACU + time limits
          |
          v
  PR files + named CI check
          |
          v
 issue comment + labels ----> report table + summary.md
```

## Five-command quickstart

```bash
cp .env.example .env
$EDITOR .env
docker compose up --build
make once ISSUE=123
make report
```

The default Compose service runs `watch`, polling every 30 seconds. Stop it with
Ctrl-C. `once` exits non-zero unless the issue reaches `verified`.

## GitHub Actions

The `Devin issue remediation` workflow runs when an authorized repository
maintainer applies `devin-fix`. It can also be dispatched manually for an issue
that still has `devin-fix`.

Configure the repository under **Settings > Secrets and variables > Actions**:

| Kind | Name | Value |
|---|---|---|
| Secret | `DEVIN_API_KEY` | `cog_...` key for a Devin service user with `UseDevinSessions` |
| Variable | `DEVIN_ORG_ID` | Devin organization ID used by the service user |

GitHub access uses the workflow's short-lived `GITHUB_TOKEN`; no GitHub personal
access token is required. The job grants `issues: write` so the controller can
post its terminal comment and update labels, plus read-only repository, pull
request, check-run access.

The workflow accepts only `admin`, `maintain`, or `write` actors. It serializes
jobs per issue and uses `devin-running` as a visible claim. If a runner is
interrupted before cleanup, leave that label in place until the existing Devin
session has been inspected or cancelled; removing it permits a recovery run.

## Simulation quickstart

No environment variables or credentials are required:

```bash
make simulate
make test
```

Simulation runs the three fixtures through fake Devin and GitHub adapters. Tests
never use the network.

## Reviewer walkthrough

Copy one body from [`issues/`](issues/) into a new `ong6/superset` issue; the
corresponding regressions are intentionally present on `master`. Configure
`.env`, run `docker compose up --build` in one terminal, then apply
`devin-fix`. Follow the session and PR links in the issue outcome, and run
`make report` from another terminal. The
[take-home index](../takehome/README.md) separates this implemented path from
the production-hardening and future CI-rescue designs.

## Issue contract

Issues are Markdown with these sections:

```text
Title
Symptom
Repro (exact command)
Expected
Allowed paths
Forbidden
Acceptance command
```

Add `CI check: <name>` under Expected when verification should wait for a check
other than `Python-Unit`. Checks must be present in
`AUTOPILOT_ALLOWED_CHECKS`. The acceptance section must contain one command
without shell operators and begin with an allowed tool.

Apply `devin-fix` to start. Repeated polls reuse the same label-event key;
applying `devin-retry` creates a new key. The spawned session receives the
canonical GitHub issue URL, the full issue contract as untrusted data, and the
default branch pinned to an immutable SHA.

The controller identifies each issue by its canonical GitHub URL, built from the
configured repository and the issue number:

```python
>>> repository = "ong6/superset"
>>> issue_number = 123
>>> f"https://github.com/{repository}/issues/{issue_number}"
'https://github.com/ong6/superset/issues/123'

```

## Commands

| Command | Behavior |
|---|---|
| `python -m autopilot watch` | Discover labeled issues and advance live runs forever |
| `python -m autopilot once --issue N` | Run one issue to a terminal outcome |
| `python -m autopilot report` | Print the table and write `reports/summary.md` |
| `python -m autopilot simulate` | Run credential-free fake fixtures |

## Guardrails

| Guardrail | Enforcement |
|---|---|
| Daily ACU cap | Refuses new sessions at 20 ACUs by default |
| Wall clock | Deletes a session after 40 minutes, then polls for 2 minutes |
| Label authorization | Requires the actor who applied the trigger label to have write access |
| Contract validation | Rejects oversized issues, unsafe paths or commands, and unapproved checks before session creation |
| Immutable target | Pins the default branch SHA and rejects a PR if the branch or PR base moved |
| Allowed paths | Fetches the PR file list and rejects every out-of-policy path |
| Structured output | Cross-checks the reported PR URL and claimed paths before verification |
| One nudge | Sends one bounded message for `waiting_for_user` |
| No secrets | Devin receives `secret_ids: []`; tokens stay in the controller |
| CI verification | Requires an open PR and successful named check run or commit status on its head SHA |
| Restart safety | Claims `new → creating` atomically, persists `session_id` before polling, and never blindly recreates it |
| Idempotent output | Stores the GitHub comment ID and posts once |
| Label reconciliation | Removes trigger and conflicting terminal labels before applying the outcome |
| Workflow claim | Serializes by issue and rejects an existing `devin-running` label |

## State

`autopilot.db` contains `runs` and append-only `transitions`. The run key is the
issue number plus the timestamp of the latest `devin-fix` or `devin-retry` label
event. Reports include session URL, state, elapsed time, ACUs, PR, CI, outcome,
and nudge count.

## Deliberately not built

| Omission | Reason |
|---|---|
| Webhooks | Thirty-second polling keeps the take-home deploy-free |
| Queue/workers | One process and SQLite are enough for the bounded fork |
| Devin Automations | The exercise demonstrates direct API v3 orchestration |
| Sandboxed verification | Fork CI is the independent acceptance oracle |
| Metrics service | The durable report supplies reviewable operational evidence |
