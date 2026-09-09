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

This controller supports the
[GitHub Issue Remediation Pilot](../takehome/README.md). It triages new issues,
starts repairs only after maintainer authorization, verifies the resulting pull
request against repository policy and CI, and records the outcome in GitHub and
SQLite.

Run the commands from this directory.

## Quickstart

```bash
cp .env.example .env
$EDITOR .env
docker compose up --build
make once ISSUE=123
make report
```

The Compose service polls every 30 seconds. `once` exits non-zero unless the
issue reaches `verified`.

For a credential-free local check:

```bash
make simulate
make test
```

## Workflow

```text
new or reopened issue
  -> triage unless `devin-exclude`
  -> maintainer authorizes with `/devin fix` or `devin-fix`
  -> controller validates, claims, and pins the request
  -> one bounded Devin session opens one scoped pull request
  -> controller verifies approved paths, issue linkage, and named CI
  -> labels, comments, and the local report record the outcome
```

## GitHub Actions

The `Devin issue automation` workflow handles opened, reopened, labeled, comment,
and manual-dispatch events. Remediation requires a repository actor with
`admin`, `maintain`, or `write` permission.

Configure the repository under **Settings > Secrets and variables > Actions**:

| Kind | Name | Value |
|---|---|---|
| Secret | `DEVIN_API_KEY` | `cog_...` key for a Devin service user with `UseDevinSessions` |
| Variable | `DEVIN_ORG_ID` | Devin organization ID used by the service user |

GitHub access uses the workflow's short-lived `GITHUB_TOKEN`. The workflow
serializes work per issue, uses visible claim labels, and writes terminal request
markers to prevent duplicate sessions.

## Reviewer walkthrough

Copy a body from [`issues/`](issues/) into a new issue without `devin-exclude`.
Confirm that triage posts a brief, then authorize remediation with `/devin fix`
or `devin-fix`. Follow the session and pull request links in the issue and run
`make report` to inspect the recorded result.

## Controls

| Label or command | Behavior |
|---|---|
| `devin-exclude` | Prevents triage and remediation until removed |
| `devin-triaging` | Temporary visible claim for an active triage run |
| `devin-triaged` | Triage brief was posted |
| `devin-triage-bug` / `devin-triage-feature` / `devin-triage-docs` / `devin-triage-question` / `devin-triage-security` / `devin-triage-other` | Devin classification labels |
| `devin-needs-info` | Reporter details are missing |
| `devin-needs-maintainer` | Maintainer decision is required |
| `/devin fix` or `devin-fix` | Authorized maintainer starts bounded remediation |
| `/devin retry` or `devin-retry` | Authorized maintainer starts a new bounded remediation attempt |

## Issue contract

An explicit issue contract uses these Markdown sections:

```text
Title
Symptom
Repro (exact command)
Expected
Allowed paths
Forbidden
Acceptance command
```

Triage can propose a contract when the issue does not provide one. Acceptance
commands must use an allowed tool without shell operators, paths and CI checks
must be allowlisted, and an explicit issue contract takes precedence.

## Commands

| Command | Behavior |
|---|---|
| `python -m autopilot watch` | Discover labeled issues and advance live runs forever |
| `python -m autopilot triage --issue N` | Classify one issue and post a triage brief |
| `python -m autopilot once --issue N` | Run one issue to a terminal outcome |
| `python -m autopilot report` | Print the table and write `reports/summary.md` |
| `python -m autopilot simulate` | Run credential-free fake fixtures |

## Guardrails

| Guardrail | Enforcement |
|---|---|
| Daily ACU cap | Refuses new sessions at 20 ACUs by default |
| Triage budget | Triage sessions are limited to 1 ACU and 10 minutes |
| Wall clock | Deletes a session after 40 minutes, then polls for 2 minutes |
| Label authorization | Requires the actor who applied the trigger label to have write access |
| Contract validation | Rejects oversized issues, unsafe paths or commands, and unapproved checks before session creation |
| Immutable target | Pins the default branch SHA and rejects a PR if the branch or PR base moved |
| Allowed paths | Fetches the PR file list and rejects every out-of-policy path |
| Structured output | Cross-checks the reported PR URL and claimed paths before verification |
| One nudge | Sends one bounded message for `waiting_for_user` |
| No secrets | Devin receives `secret_ids: []`; tokens stay in the controller |
| CI verification | Requires an open PR and successful named check run or commit status on its head SHA |
| Issue linkage | Requires the pull request body to close the source issue |
| Restart safety | Claims `new → creating` atomically, persists `session_id` before polling, and never blindly recreates it |
| Idempotent output | Upserts one triage brief and rejects duplicate terminal request markers |
| Label reconciliation | Removes trigger and conflicting terminal labels before applying the outcome |
| Workflow claim | Serializes by issue and rejects existing triage or remediation claims |

The local database stores runs and append-only transitions. Reports include the
session, state, elapsed time, ACU use, pull request, CI result, outcome, and
nudge count.

## Scope

This is a one-repository pilot. It does not merge pull requests, bypass branch
protection, run on excluded issues, provide a shared queue, or verify patches in
a separate clean-room publisher.
