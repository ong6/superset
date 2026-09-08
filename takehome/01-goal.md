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

# Goal and Success Criteria

## Objective

Build and present a Dockerized, event-driven engineering automation that uses
the Devin API to remove a recurring blocker from the Superset pull-request
workflow.

The core take-home question is not only whether Devin can perform an impressive
task. It is whether an engineering team would choose to keep the automation
enabled after the demo.

The selected automation should therefore:

1. start from a problem engineers already encounter frequently;
2. appear in GitHub, where contributors and maintainers already work;
3. produce useful read-only output before it receives write permission;
4. use deterministic commands to establish failure and success;
5. make the smallest reviewable change when remediation is authorized;
6. measure whether engineers accept and reuse its output.

## Repository evidence

A 2026-09-08 GitHub API snapshot of `apache/superset` found:

- 429 open pull requests;
- 206 open pull requests older than 30 days;
- 133 open pull requests older than 90 days;
- a median open-pull-request age of 27 days;
- 52 workflow definitions in `.github/workflows/`;
- recent failed workflow runs across Python unit and integration tests,
  frontend tests and lint, E2E, pre-commit, and Presto/Hive.

The repository also has explicit reports of recurring CI instability, including
[a recent flaky Jest failure](https://github.com/apache/superset/issues/43656)
and the long-running
[Presto/Hive flake ledger](https://github.com/apache/superset/issues/17750).

These signals do not prove that every old pull request is blocked by CI. They do
show that pull-request throughput and failed-check diagnosis are broad,
visible, recurring engineering workflows. That makes them stronger adoption
targets than a narrow subsystem-specific guard.

## Required system loop

```text
failed review-ready pull-request workflow event
  -> controller validates and deduplicates delivery
  -> controller rejects draft-origin, currently-draft, and stale-SHA runs
  -> controller resolves pull request, immutable SHA, failed job, and artifacts
  -> deterministic preflight selects and reruns the smallest relevant command
  -> controller creates an investigator Devin session
  -> Devin classifies and explains the reproduced failure
  -> read-only diagnosis appears on the pull request
  -> authorized remediation Devin session makes a bounded repair
  -> the same command verifies the repair
  -> metrics report time-to-diagnosis, time-to-green, acceptance, and cost
```

Devin must perform meaningful engineering work. It should not merely summarize
raw CI output. The controller supplies the failed job, changed files, test
artifacts, immutable SHA, and replay command. Devin connects that evidence to
the repository, distinguishes change-caused failures from flakes or
infrastructure failures, and proposes or implements the smallest safe repair.

## Adoption hypothesis

The pilot should earn trust in stages:

| Stage | Automation behavior | Trust signal |
|---|---|---|
| Observe | Classify failed checks without writing code | Diagnoses are accurate and replayable |
| Assist | Post a concise root cause and exact rerun command | Engineers act on the output |
| Repair | Fix only after a label, command, or trusted-branch policy allows it | Proposed changes are accepted |
| Expand | Handle repeated failure classes automatically | Teams keep the automation enabled |

## Deliverables

### Working project

- Public automation repository with a Docker-based local workflow.
- `workflow_run`/check webhook or replayable failed-run entry point.
- Devin API session creation, polling, follow-up, and terminal-state handling.
- Structured logs and lightweight metrics.
- Runbook for local simulation without GitHub webhook infrastructure.
- At least one successful failed-check-to-green path in this Superset fork.

### Superset fork

- One seeded pull request with a realistic failing unit test or lint check.
- A structured diagnosis tied to the failed job, test, and changed files.
- An authorized repair created by the automation or its managed Devin session.
- Evidence that the same scoped command fails before and passes after.

### Five-minute presentation

- **What:** too many pull requests lose time waiting for failed-check diagnosis.
- **How:** failed event, evidence extraction, scoped replay, Devin diagnosis,
  opt-in repair, and deterministic verification.
- **Why Devin:** it reasons across the diff, logs, tests, and code rather than
  only routing a known error string.
- **Why adoption:** it meets engineers in GitHub, begins read-only, and proves
  value before requesting broader permissions.

## Evaluation rubric

| Dimension | Evidence of a strong submission |
|---|---|
| Adoption likelihood | Fits an existing workflow, earns trust gradually, and requires little behavior change |
| Problem selection | Frequent, visible, expensive, and supported by repository evidence |
| Devin leverage | Devin owns investigation and remediation, not just prose |
| Technical design | Idempotency, retries, timeouts, scoped access, state model |
| Safety | Deterministic gate, bounded prompts, no speculative findings |
| Observability | Diagnosis accuracy, latency, acceptance, time-to-green, cost |
| Demo quality | Crisp red-check-to-green-check story with visible proof |

## Definition of done

- One event can be replayed locally and through the configured integration.
- Duplicate deliveries do not start duplicate sessions.
- Every Devin session is correlated to repository, pull request, head SHA,
  workflow run, failed job, and rerun command.
- Failure, timeout, cancellation, and malformed-output states are visible.
- A failed check produces a useful diagnosis even when remediation is disabled.
- A trusted or explicitly authorized remediation passes the same scoped command
  that reproduced the failure.
- Untrusted fork pull requests remain read-only unless a maintainer explicitly
  authorizes a safe companion workflow.
- The metrics view answers:
  - How many failed runs were triaged?
  - How many failures were reproduced?
  - How many were change-caused, flaky, infrastructure-related, or unresolved?
  - How often did engineers accept or invoke the suggested action?
  - How long did diagnosis and remediation take?
  - What did each successful rescue cost?

## Fast implementation sequence

This is a compact four-step build sequence, not a four-day estimate. The
intentionally narrow failure fixture, scoped replay command, and opt-in write
path make it suitable for rapid implementation and demonstration.

### Step 1 — define the failure contract

- Add one fork-local pull request with a realistic failing unit test or lint
  check.
- Normalize a saved failed workflow payload, job log, and test artifact.
- Emit a structured result containing the pull request, SHA, workflow, job,
  fingerprint, replay command, duration, and outcome.

### Step 2 — build the event controller

- Add the Dockerized webhook/replay entry point and SQLite run state.
- Resolve the pull request and deduplicate by workflow run, job, and head SHA.
- Use changed paths and job metadata to select the smallest relevant repository
  command.
- Start Devin only after collecting actionable evidence.

### Step 3 — manage investigation and remediation

- Create bounded investigator and opt-in remediation session contracts.
- Poll sessions, validate structured output, and expose terminal states.
- Post a concise diagnosis and replay command to the pull request.
- Require a trusted branch, label, or maintainer command before writing code.
- Re-run the same scoped command against the proposed change.

### Step 4 — prove and present the loop

- Exercise success, failure, duplicate-event, malformed-output, and timeout
  paths.
- Publish triage volume, reproduction rate, classification, acceptance,
  time-to-green, and cost metrics.
- Finalize the README, runbook, architecture, and five-minute demo.
