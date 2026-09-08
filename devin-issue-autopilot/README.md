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
other than `Python-Unit`. Apply `devin-fix` to start. Repeated polls reuse the
same label-event key; applying `devin-retry` creates a new key.

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
| Allowed paths | Fetches the PR file list and rejects every out-of-policy path |
| One nudge | Sends one bounded message for `waiting_for_user` |
| No secrets | Devin receives `secret_ids: []`; tokens stay in the controller |
| CI verification | Requires an open PR and successful named check on its head SHA |
| Restart safety | Persists `session_id` before polling and never recreates it |
| Idempotent output | Stores the GitHub comment ID and posts once |

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
