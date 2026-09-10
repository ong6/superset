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

## Reviewer path, tested on 2026-09-10

This path was run from a fresh checkout of `ong6/superset` `master`
(`0497f871fe`). Required/verified tools: Docker Engine `29.7.2` and Docker
Compose `v5.4.0`. Run from `devin-issue-autopilot/`; wall times vary by machine
and network.

| Step | Command | Expected output excerpt | Wall time |
|---|---|---|---|
| Build | `docker compose build` | `Image devin-issue-autopilot-watch Built` | 15.50s |
| Tests | `make test` | `50 passed in 0.56s` | 1.78s |
| Simulation and report | `make simulate` | `1: verified` … `3: verified`; `# Autopilot report`; `Simulated: 3/3 runs` | 1.14s |

No GitHub or Devin credentials were present for the simulation. `make simulate`
runs in Docker and finishes by rendering the simulated report to the terminal
and `reports/summary.md`. The standalone live `make report` is GitHub-backed
and exits with `GITHUB_TOKEN is required` when run without that credential.

The Compose service is named `watch`; use `make test` verbatim. The stale
command `docker compose run --rm autopilot make test` fails with
`no such service: autopilot` and is not part of the reviewer path.

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
markers to prevent duplicate sessions. Each claimed job restores the controller
SQLite database from an `actions/cache` prefix and saves a new cache entry after
execution, including failure. This is best-effort persistence: concurrent jobs
for different issues can restore the same snapshot and race when their divergent
databases are saved.

## How would an engineering leader know this is working?

The issue labels expose the queue and outcome: `devin-triaging` and
`devin-running` show active work, `devin-candidate` is ready for approval,
`devin-verified` is ready for review, and `devin-needs-human` needs intervention.
The `devin-issue-autopilot-report` artifact shows the three decision totals:
**Fix attempted**, **CI/policy verified**, and **Merged**. See the
[latest successful report-only Actions run](https://github.com/ong6/superset/actions/runs/34448848049).

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

A newly opened issue moves from `devin-triaging` to `devin-candidate` when its
readiness brief succeeds. The detailed demo sequence and evidence gates are in
[`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md).

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
| `python -m autopilot report --devin` | Also reconcile pull requests and internal session diagnostics from tagged Devin v3 sessions when Devin credentials are set |
| `python -m autopilot report --include-raw-usage` | Opt into a raw/unverified usage diagnostics table; default reports omit it |
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
| Daily ACU cap | In both Actions and Compose, queries tagged or controller-titled Devin sessions created in the last 24 hours and refuses a new session at 20 reported ACUs by default. If that API call fails, Actions sums the best-effort restored SQLite cache while Compose sums the SQLite database on its named volume; the lifecycle comment identifies the fallback. |
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
| Restart safety | Both runtimes claim `new → creating` atomically, persist `session_id` before polling, and never blindly recreate it. Compose keeps the database on the `autopilot-data` volume. Actions restores and saves the database with `actions/cache`, so resume state is best-effort and concurrent jobs can race. |
| Idempotent output | Updates one durable lifecycle comment and rejects duplicate terminal request markers |
| Label reconciliation | Removes trigger and conflicting terminal labels before applying the outcome |
| Workflow claim | Serializes by issue and rejects existing triage or remediation claims |

## Observability

`report` rebuilds history from `devin-*` issues, trusted terminal comments
authored by `github-actions[bot]`, and current pull-request state. SQLite is only
a reconstructed cache. `GITHUB_TOKEN` is required; `--devin` optionally adds
tagged-session diagnostics when Devin credentials are also set.

The terminal, `reports/summary.md`, Actions Summary, and
`devin-issue-autopilot-report` artifact contain the same linked run table and
denominated totals. Backlog labels are operational context, not success
evidence. Raw usage is omitted unless `--include-raw-usage` is requested and is
never interpreted as billing or savings.

The `AUTOPILOT_DAILY_ACU_CAP` gate queries organization sessions created in the
last 24 hours, keeps sessions carrying the `autopilot` tag or the controller's
`Fix <repo>#` / `Triage <repo>#` title prefix, and sums reported ACUs. If the
Devin sessions API fails, the gate falls back to local SQLite rows and records
that source in the lifecycle comment. Compose keeps those rows on the
`autopilot-data` volume. Actions restores and saves them through an immutable,
run-specific cache entry under the stable `autopilot-db-<repository>-` prefix;
concurrent jobs can race, so this fallback and restart persistence are
best-effort rather than a shared lock or organization billing limit. Missing
usage is not counted. Each remediation session is still created with a 4-ACU
limit and a 2400-second controller timeout with at most one nudge; triage uses
`AUTOPILOT_TRIAGE_ACU_LIMIT` (default 1), a 600-second timeout, and no nudges.

Logs emit `transition issue=... run_id=... from=... to=... elapsed=...`.
Report-only dispatches and the daily schedule publish Markdown without changing
the repository; artifacts are retained for 30 days.

## Scope

This is a one-repository pilot. It does not merge pull requests, bypass branch
protection, run on excluded issues, provide a shared queue, or verify patches in
a separate clean-room publisher.

Day-to-day status links are in the [fork README](../README.md#devin-workflow-current-issue-status);
the longer maintainer and recording procedure is in
[`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md).
