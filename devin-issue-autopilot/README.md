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

GitHub access uses the workflow's short-lived `GITHUB_TOKEN`. Triage uses the
separate read-only Devin identity, receives no session secrets, requires approval
for actions, and is rejected if it opens a pull request. The workflow serializes
work per issue, updates one durable lifecycle comment, and uses terminal request
markers to prevent duplicate sessions.

## Reviewer walkthrough

Copy a body from [`issues/`](issues/) into a new issue without `devin-exclude`.
Confirm that triage posts a brief, then authorize remediation with `/devin fix`
or `devin-fix`. Follow the session and pull request links in the issue and run
`make report` to inspect the recorded result.

## Live evidence

| Issue | Session | PR | CI result | Outcome |
|---|---|---|---|---|
| [#13](https://github.com/ong6/superset/issues/13) | [4ece9ef5](https://app.devin.ai/sessions/4ece9ef53c7d4d5bbcba6613daa166dd) | [#14](https://github.com/ong6/superset/pull/14) | Passed | Verified |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |

## Controls

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
commands must use an allowed tool without shell operators, and paths and CI
checks must be allowlisted. The default check is `unit-tests (current)`; add
`CI check: <name>` under Expected to select another approved check. An explicit
issue contract takes precedence.

## Commands

| Command | Behavior |
|---|---|
| `python -m autopilot watch` | Discover labeled issues and advance live runs forever |
| `python -m autopilot triage --issue N` | Classify one issue and post a triage brief |
| `python -m autopilot once --issue N` | Run one issue to a terminal outcome |
| `python -m autopilot report` | Rebuild GitHub-backed history, print it, and write `reports/summary.md` |
| `python -m autopilot report --devin` | Also reconcile ACUs and pull requests from tagged Devin v3 sessions when Devin credentials are set |
| `python -m autopilot simulate` | Run credential-free fake fixtures |

From this directory, `make simulate` is the documented credential-free
container check. Reviewers can rebuild the repository's live lifecycle report
with:

```bash
GITHUB_TOKEN="$(gh auth token)" GITHUB_REPO=ong6/superset make report
```

The exact report-only Actions dispatch is:

```bash
gh workflow run devin-issue-autopilot.yml --repo ong6/superset -f mode=report
```

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

## Observability

`report` paginates issues carrying any `devin-*` label, reconstructs terminal
triage and remediation runs from GitHub Actions comments, and reads current pull
request state. `GITHUB_TOKEN` is the only required credential. With `--devin`
and both `DEVIN_API_KEY` and `DEVIN_ORG_ID`, it also reconciles ACUs and pull
requests from tagged v3 sessions. SQLite is a local cache rather than the
historical source of truth.

Each report identifies its generation timestamp, repository, revision, scanned
issue count, and trusted terminal-run count. Only terminal lifecycle tables
authored by `github-actions[bot]` enter effectiveness metrics. Marker-bearing
human or legacy comments are linked separately as unverified exclusions rather
than silently counted as success.

The terminal and `reports/summary.md` contain the same per-run table and
denominated totals. Rows link their issue, session, and pull request; distinguish
triage, remediation, setup/build roles, and simulation; and separate PR-opened,
controller CI/policy-verified (ready for review), merged, and
verified-and-merged outcomes. Every available terminal comment is retained,
including failed attempts. Lifecycle comments updated in place by GitHub can
expose only their latest durable body.

The separate current issue-status/backlog table shows every open Devin-labeled
issue with its label-derived state and next action, including triaging/running,
queued requests, ready for approval/review, missing information, maintainer
attention, and paused work. Those rows are operational context only and
never enter attempt, failure, success-rate, timing, or usage denominators.

Usage figures are omitted from default reports and new lifecycle comments
because a reliable usage source has not been verified. Raw values are retained
internally for diagnostics. To inspect them explicitly, use
`python -m autopilot report --devin --include-raw-usage`; this output is marked
unverified, preserves zero separately from missing values, and must not be used
to claim free work or savings. Existing historical comments are not rewritten.

The runtime still applies its configured per-session limits. The local daily
usage gate depends on available telemetry and a disposable runner cache; it is
not durable organization-wide spend enforcement. These technical controls do
not establish actual usage or cost.

Workflow logs emit `transition issue=... run_id=... from=... to=...
elapsed=...`, so `gh run view --log | grep transition` shows each run's state
timeline. Manual report dispatches and the daily schedule publish the Markdown
on the Actions run's **Summary** page and as the
`devin-issue-autopilot-report` download under **Artifacts** for 30 days, without
changing the repository.

## Scope

This is a one-repository pilot. It does not merge pull requests, bypass branch
protection, run on excluded issues, provide a shared queue, or verify patches in
a separate clean-room publisher.

## Maintainer and demo flow

Use the [repository status links](../README.md#devin-workflow-current-issue-status)
for day-to-day work. New/reopened issues start triage unless excluded. Adding
`devin-triage` requests a fresh brief after clarification. A maintainer authorizes
a repair with `/devin fix` or `devin-fix`; `/devin retry` requests another attempt.
No manual Actions dispatch is needed for those normal events.

Reports refresh after issue processing and daily at 06:17 UTC (14:17 Singapore
time). Manual `mode=report` refresh is optional and read-only. Schedules can be
delayed; always show the generation timestamp. PR merge state is refreshed by
the next report, not continuously.

For the prepared #48/#49 demo issues, keep `devin-exclude` until deliberately
starting. Then remove it and add `devin-triage`, review the issue's brief, and
approve with `/devin fix`. Removing exclusion alone is not a trigger. In the
five-minute recording, show a completed issue/session/PR/check chain rather
than waiting for a full repair. Keep genuine failures and pending work visible.
