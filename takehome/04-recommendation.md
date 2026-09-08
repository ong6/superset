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

# Recommendation and Next Steps

## Selected build: PR CI Rescue Autopilot

Build a GitHub-event-driven controller that turns a failed pull-request check
into a reproduced failure, a bounded Devin investigation, and—only when
authorized—a verified repair.

The automation should first answer:

> What failed, does it reproduce at this exact SHA, is the pull request the
> cause, and what is the smallest safe next action?

That is a better adoption wedge than an LLM reviewer on every pull request or a
specialized migration-only guard:

- engineers already wait on failed checks;
- the automation appears inside GitHub rather than a new dashboard;
- read-only diagnosis creates value before write access is granted;
- the same repository command can verify both the problem and the repair;
- successful use has measurable outcomes: accepted diagnoses, invoked repairs,
  and shorter time-to-green.

## Problem statement

Superset's CI surface is intentionally broad. Pull requests can run Python unit
and integration suites, frontend tests and lint, pre-commit, E2E, dependency
checks, API drift checks, and database-specific jobs.

When one fails, the relevant context is distributed:

- the workflow and failed job;
- annotations, logs, screenshots, videos, or JUnit artifacts;
- the pull-request diff and changed paths;
- repository instructions and suite-specific replay commands;
- prior failures of the same test or fingerprint;
- whether the head branch is trusted and writable.

A contributor often sees a red check before they have a useful diagnosis.
Blind reruns may hide a flake, and generic log summaries do not tell an engineer
whether or how to change code.

## Product boundary

The first version handles one failed check on one open pull request at one
immutable head SHA.

It does not:

- review every line of every pull request;
- rerun every failed workflow automatically;
- claim a flake from one failed attempt;
- edit an untrusted fork;
- modify multiple unrelated subsystems;
- merge, close, or approve pull requests;
- treat Devin's explanation as the success oracle.

## Architecture

```text
GitHub workflow_run/check event
  -> event validator and PR resolver
  -> idempotency and fingerprint store
  -> log/artifact and changed-path collector
  -> deterministic focused replay
  -> investigator Devin session
  -> structured classification and PR diagnosis
  -> policy gate: read-only / authorized repair
  -> remediation Devin session
  -> repeat the same focused replay
  -> GitHub output and adoption metrics
```

The controller owns facts, state, policy, and verification. Devin owns
repository-scale diagnosis and bounded code changes.

## Trigger and correlation

The production trigger is a completed failed `workflow_run` or check event. A
saved event payload provides a deterministic local demo path.

For every accepted event, resolve and persist:

- repository and installation;
- delivery ID and workflow run ID;
- pull-request number;
- immutable head SHA;
- workflow, job, and failed step;
- actor, author association, and fork status;
- changed paths;
- artifact URLs and retention status;
- failure fingerprint;
- selected replay command and timeout.

If the run does not map to one open pull request and one head SHA, finish with
`not_actionable` instead of guessing.

## Idempotency

Duplicate webhook delivery must not create duplicate comments, Devin sessions,
or repairs.

Use two keys:

```text
delivery_key = repository + delivery_id
failure_key  = repository + pr + head_sha + workflow + job + fingerprint
```

The delivery key absorbs GitHub retries. The failure key absorbs equivalent
events and repeated controller processing. A new head SHA creates a new
evaluation because the evidence and repair target changed.

## Evidence collection

Before starting Devin, the controller should gather the smallest useful
evidence bundle:

1. failed job and step metadata;
2. focused log excerpts around the first actionable error;
3. test reports and available screenshots or traces;
4. pull-request diff and changed paths;
5. workflow definition and repository instructions;
6. prior occurrences of the same normalized fingerprint;
7. a candidate replay command.

Normalize unstable values such as timestamps, worker IDs, temporary paths, and
random ports before fingerprinting. Preserve the original artifact alongside
the normalized fingerprint.

## Selecting the replay command

The controller should use deterministic mappings before asking Devin:

| Failure evidence | First replay target |
|---|---|
| Python test node ID | Exact `pytest` node |
| Jest test file or test name | Exact test file and name filter |
| Pre-commit hook | Named hook against changed files |
| Playwright test | Exact spec and project where available |
| Dependency or generated-file check | Repository-provided checker |
| No reliable target | Mark `insufficient_replay_evidence` |

Changed paths and the workflow definition can narrow the environment, but they
must not silently replace the command CI actually ran. Persist both the CI
command and the focused replay command.

The replay result is evidence, not an absolute classifier:

- a repeatable failure supports investigation;
- a passing replay may indicate a flake, environment difference, or incomplete
  reproduction;
- an unavailable environment is an explicit terminal outcome, not permission
  to speculate.

## Failure classification

The investigator returns exactly one primary classification:

| Classification | Required evidence | Default next action |
|---|---|---|
| `change_caused` | Failure reproduces and connects to changed behavior | Offer bounded repair |
| `likely_flaky` | Same fingerprint has inconsistent outcomes or repeated prior evidence | Record recurrence; investigate stabilization |
| `infrastructure` | Evidence points to runner, network, service, quota, or artifact failure | Recommend rerun; no code repair |
| `generated_drift` | Repository checker proves stale generated output | Offer mechanical repair |
| `unresolved` | Evidence is contradictory or insufficient | Request human decision |

A single green rerun is not enough to label a test flaky. The result should
state what was observed and which evidence is still missing.

## Investigator Devin session

Create one investigator session per failure key.

### Inputs

- repository and immutable SHA;
- pull-request diff and changed paths;
- failed workflow/job/step;
- focused logs and artifacts;
- original and replay commands with outcomes;
- prior fingerprint occurrences;
- repository instructions;
- allowed read scope and deadline.

### Responsibilities

1. reproduce or explain why reproduction is incomplete;
2. identify the first causal failure rather than downstream noise;
3. connect the failure to the diff and surrounding code;
4. classify it using the allowed taxonomy;
5. propose the smallest safe next action;
6. name the exact verification command;
7. identify uncertainty without inventing evidence.

### Structured output

```json
{
  "classification": "change_caused",
  "summary": "Changed validation rejects an existing empty-value case.",
  "evidence": [
    "Focused test fails at the pull-request head SHA",
    "The failure begins in a changed validation branch"
  ],
  "replay_command": "pytest tests/unit_tests/example_test.py::test_empty_value",
  "repair_recommended": true,
  "allowed_paths": [
    "superset/example.py",
    "tests/unit_tests/example_test.py"
  ],
  "confidence": "high",
  "unknowns": []
}
```

Reject malformed output and expose the validation failure. Do not infer
authorization from `repair_recommended`.

## Pull-request diagnosis

The first useful product output is read-only. Publish one updateable GitHub
Check or compact comment containing:

- failed workflow and job;
- classification;
- whether focused replay failed, passed, or was unavailable;
- two or three evidence bullets;
- exact replay command;
- recommended next action;
- linked controller run and Devin session;
- explicit uncertainty;
- repair authorization instructions when eligible.

Update the same artifact for the same failure key rather than creating a stream
of bot comments.

## Repair authorization

Use a gradual trust model:

1. **Untrusted fork:** read-only diagnosis. Never expose privileged secrets or
   write to the contributor's branch.
2. **Trusted branch without opt-in:** diagnosis plus an offered `/devin fix`
   command or label.
3. **Trusted branch with opt-in:** bounded remediation session.
4. **Allowlisted repeatable failure class:** optional automatic remediation
   only after pilot metrics justify it.

The demo should use a trusted fork branch and explicit authorization so the
permission transition is visible.

## Remediation Devin session

The remediation session receives the validated investigation, not the entire
unfiltered workflow log.

Its contract is:

- start from the exact investigated SHA;
- edit only the approved path set;
- preserve the pull request's intent;
- make the smallest repair;
- do not weaken, delete, skip, or broadly relax tests;
- do not add retries as a substitute for a root-cause fix;
- run the focused replay command;
- run the affected suite when feasible;
- return changed files, commands, results, residual risk, and a concise commit
  message.

The controller independently reruns the focused command. Devin cannot mark its
own change successful.

If verification fails, the system may send one evidence-rich follow-up to the
same session. Further attempts require a new decision rather than an unbounded
repair loop.

## State machine

```text
received
  -> rejected
  -> deduplicated
  -> evidence_collecting
  -> not_actionable
  -> replaying
  -> replay_failed
  -> replay_passed
  -> investigating
  -> diagnosis_published
  -> awaiting_authorization
  -> remediation_running
  -> verification_running
  -> repaired
  -> repair_failed
  -> timed_out
  -> malformed_output
  -> cancelled
```

Each transition records a timestamp, correlation IDs, evidence references,
duration, and reason. Terminal states must remain queryable after the process
restarts.

## Failure handling

| Failure | Behavior |
|---|---|
| Duplicate delivery | Return the existing run |
| Missing or expired artifact | Continue with logs; mark evidence gap |
| No associated pull request | Finish `not_actionable` |
| Head SHA changed during work | Cancel repair and start a new evaluation |
| Replay timeout | Publish timeout and exact attempted command |
| Devin timeout or cancellation | Publish terminal state; preserve evidence |
| Malformed Devin output | Reject it; do not open a repair |
| GitHub rate limit | Retry with bounded backoff and persisted state |
| Verification failure | Keep diagnosis, mark repair failed, do not claim success |

## Demo fixture

Use a small, realistic unit-test regression rather than an artificial syntax
error.

Example:

1. a trusted fork pull request changes a validation helper;
2. one existing edge case fails in a focused Python or frontend unit test;
3. the saved failed workflow event is replayed;
4. the controller extracts the test and reproduces it;
5. Devin connects the changed branch to the failing assertion;
6. the pull request receives a read-only diagnosis;
7. a maintainer authorizes `/devin fix`;
8. Devin makes a minimal implementation repair;
9. the controller runs the exact test and shows it turn green.

Also replay:

- the same event twice to prove deduplication;
- a simulated infrastructure log to prove no code session is started;
- malformed session output to prove validation;
- a fork event to prove the read-only policy.

## Metrics

### Adoption

- pull requests receiving a diagnosis;
- diagnosis reactions or maintainer acceptance;
- `/devin fix` invitations and invocations;
- repeat users and repositories;
- suggested repairs accepted or merged;
- automation disable, dismissal, and false-positive rates.

### Engineering outcomes

- median time from failed check to diagnosis;
- median time from failed check to green;
- reproduction rate;
- first-session repair success;
- reruns avoided;
- maintainer interventions;
- flaky fingerprint recurrence;
- unresolved rate.

### Efficiency

- Devin sessions per successful rescue;
- wall-clock and active session duration;
- ACU or cost per triage and repair;
- CI minutes consumed by replay;
- estimated manual minutes avoided.

Success is not the number of Devin sessions created. A strong pilot creates
fewer, better-scoped sessions and shows that engineers act on their output.

## Pilot gates

Before enabling broader repair:

- at least 80% of sampled diagnoses are judged useful by maintainers;
- no privileged write is performed on untrusted forks;
- every repair has independent replay evidence;
- duplicate events create no duplicate sessions or comments;
- false `change_caused` classifications stay below an agreed threshold;
- cost and latency are visible per run;
- maintainers can disable the automation or cancel a run immediately.

These are proposed pilot thresholds, not claims about existing performance.

## Implementation sequence

This is a compact four-step sequence, not a four-day estimate.

### Step 1 — evidence and replay

- Define the normalized event, run, fingerprint, and classification schemas.
- Add one saved failed-run fixture and one realistic failing pull request.
- Implement PR/SHA resolution, log parsing, and focused replay.

### Step 2 — investigation and read-only output

- Add persistent idempotency and state transitions.
- Create and poll the bounded investigator session.
- Validate structured output and update one GitHub Check or comment.

### Step 3 — opt-in repair

- Enforce fork, branch, path, and command policies.
- Add label or `/devin fix` authorization.
- Create the remediation session and independently verify its change.

### Step 4 — reliability and measurement

- Exercise duplicate, timeout, malformed-output, stale-SHA, infrastructure, and
  untrusted-fork paths.
- Publish adoption, engineering-outcome, latency, and cost metrics.
- Finalize the Docker workflow, runbook, architecture, and presentation.

## Five-minute presentation

1. **Problem:** many pull requests and broad CI create repeated failed-check
   diagnosis work.
2. **Adoption thesis:** meet engineers in GitHub and begin read-only.
3. **Live loop:** replay a failed run, reproduce it, and publish a diagnosis.
4. **Controlled autonomy:** authorize a bounded repair and show the same test
   turn green.
5. **Trust evidence:** deduplication, fork restrictions, terminal states, and
   independent verification.
6. **Business result:** shorter time-to-green, fewer blind reruns, accepted
   repairs, and measurable cost.

## Expansion path

After the general failed-check loop earns trust, add specialized handlers:

1. flaky-test recurrence and stabilization;
2. stale pull-request action queues;
3. dependency pin regeneration;
4. migration upgrade/downgrade rehearsal;
5. OpenAPI and generated-artifact drift;
6. accessibility or performance regression response.

These extensions reuse the same event correlation, session lifecycle,
authorization, GitHub output, idempotency, and metrics platform. The first
automation therefore proves an adoption surface and creates infrastructure for
the narrower high-value ideas rather than discarding them.
