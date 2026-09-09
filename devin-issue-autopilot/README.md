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

A small controller that triages new `ong6/superset` issues unless excluded, turns
authorized remediation requests into bounded Devin sessions, independently
verifies their pull requests, and records the result on GitHub and in SQLite.

Run every command below from this `devin-issue-autopilot` directory inside a
clone of `ong6/superset`.

## Architecture

```text
GitHub issue opened/reopened
          |
          v
  devin-exclude? ---- yes ----> stop
          |
          v
  triage session ----> labels + upserted issue brief
          |
          v
maintainer /devin fix or devin-fix
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

The `Devin issue automation` workflow triages opened or reopened issues unless
`devin-exclude` is present. Maintainers can request a fresh brief with
`devin-triage` or manual `triage` dispatch. Remediation starts only when an
authorized repository maintainer applies `devin-fix`/`devin-retry`, comments
`/devin fix` or `/devin retry`, or manually dispatches `remediate`.

Configure the repository under **Settings > Secrets and variables > Actions**:

| Kind | Name | Value |
|---|---|---|
| Secret | `DEVIN_API_KEY` | Writer service key used only for approved remediation |
| Secret | `DEVIN_TRIAGE_API_KEY` | Separate read-only service key used only for triage |
| Variable | `DEVIN_ORG_ID` | Devin organization ID used by the service user |

GitHub access uses the workflow's short-lived `GITHUB_TOKEN`; no GitHub personal
access token is required. The job grants `issues: write` so the controller can
post its terminal comment and update labels, plus read-only repository, pull
request, check-run access.

Remediation accepts only `admin`, `maintain`, or `write` actors. Triage runs for
reporters too, uses only the separate read-only identity, receives no session
secrets, requires approval for actions, and is rejected if it opens a pull
request. The workflow serializes jobs per issue and uses `devin-triaging` or
`devin-running` as visible claims. One durable issue comment is updated from
triage through remediation and verification. Terminal request markers prevent a
rerun of the same GitHub event from creating another session.
If a runner is interrupted before cleanup, leave the claim label in place until
the existing Devin session has been inspected or cancelled; removing it permits
a recovery run.

## Simulation quickstart

No environment variables or credentials are required:

```bash
make simulate
make test
```

Simulation runs the three fixtures through fake Devin and GitHub adapters. Tests
never use the network.

## Reviewer walkthrough

Copy one body from [`issues/`](issues/) into a new `ong6/superset` issue without
`devin-exclude`; the triage workflow should classify it and post a brief. Then
comment `/devin fix` or apply `devin-fix`; the corresponding regressions are
intentionally present on `master`. Configure `.env`, run
`docker compose up --build` in one terminal, follow the session and PR links in
the issue outcome, and run `make report` from another terminal. The
[take-home index](../takehome/README.md) separates this implemented path from
the production-hardening and future CI-rescue designs.

## Labels and issue commands

| Label or command | Behavior |
|---|---|
| `devin-exclude` | Prevents triage and remediation until removed |
| `devin-triage` | Requests a fresh read-only readiness brief |
| `devin-triaging` | Temporary visible claim for an active triage run |
| `devin-triaged` | Triage brief was posted |
| `devin-candidate` | A bounded remediation plan is ready for maintainer approval |
| `devin-triage-bug` / `devin-triage-feature` / `devin-triage-docs` / `devin-triage-question` / `devin-triage-security` / `devin-triage-other` | Devin classification labels |
| `devin-needs-info` | Reporter details are missing |
| `devin-needs-maintainer` | Maintainer decision is required |
| `/devin fix` or `devin-fix` | Authorized maintainer starts bounded remediation |
| `/devin retry` or `devin-retry` | Authorized maintainer starts a new bounded remediation attempt |

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
without shell operators and begin with an allowed tool. When an incoming issue
has no contract, triage proposes narrow allowed paths, an acceptance command,
and a CI check in its brief. A maintainer approves that proposal through a fix
label or command; an explicit issue contract takes precedence.

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
| Idempotent output | Updates one durable lifecycle comment and rejects duplicate terminal request markers |
| Label reconciliation | Removes trigger and conflicting terminal labels before applying the outcome |
| Workflow claim | Serializes by issue and rejects existing triage or remediation claims |

## State

`autopilot.db` contains `runs` and append-only `transitions`. The run key is the
issue number plus the timestamp of the latest triage, label, command, or retry
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
