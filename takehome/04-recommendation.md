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

## Recommended build

Build the **Migration Upgrade Contract Guardian**.

This is the strongest take-home direction because it combines:

- a concrete, recurring Superset risk: metadata migrations can block
  deployments;
- a deterministic oracle: graph, upgrade, downgrade, re-upgrade, and focused
  migration tests;
- a clear event-driven loop: GitHub event to check, issue, Devin session,
  remediation pull request, and metrics;
- a safe demo: fork-only seeded migration failure rather than speculative
  production or security claims;
- a strong Devin primitive: Devin diagnoses and repairs one reproduced
  migration contract failure inside explicit guardrails.

## Main idea in depth

### The problem being solved

Superset stores dashboards, charts, datasets, users, roles, saved queries, and
other application state in its metadata database. Alembic migrations evolve
that database as Superset changes.

A migration can look valid in code review and still fail during deployment or
rollback. Examples include:

- the revision points to the correct parent but its `downgrade()` drops the
  wrong table, column, index, or constraint;
- the upgrade succeeds on an empty database but fails against representative
  pre-existing rows;
- a backend-specific operation works on SQLite but not PostgreSQL, or the
  reverse;
- the upgrade mutates data incorrectly even though the schema reaches the
  expected shape;
- the downgrade succeeds, but a subsequent re-upgrade fails because it leaves
  the database in an inconsistent state;
- a focused migration test is missing or does not assert the important data and
  schema invariants.

Superset already checks that its Alembic graph resolves to one head. That
prevents conflicting migration branches, but it does not execute the changed
migration's operational contract. The Guardian adds that missing execution
layer.

### What “migration contract” means

The controller treats each changed migration as a small state machine:

```text
parent revision
  -> apply changed revision
  -> verify post-upgrade invariants
  -> downgrade to parent
  -> verify post-downgrade invariants
  -> apply changed revision again
  -> verify post-re-upgrade invariants
```

The universal contract is intentionally narrow:

1. the repository has exactly one Alembic head;
2. the changed revision can upgrade from its declared parent;
3. its downgrade path executes according to the migration's declared policy;
4. the revision can be applied again after downgrade;
5. its focused tests pass;
6. every failure produces a reproducible command and evidence bundle.

Not every migration can or should restore deleted data. The oracle therefore
does not impose a false global promise of perfect reversibility. A small
per-migration policy describes which schema and data invariants are expected,
whether downgrade is intentionally lossy or a no-op, and which database
backends are relevant. Missing or ambiguous policy is reported for human
decision rather than presented as a vulnerability.

### Deterministic oracle

The oracle is conventional code, not an LLM judgment. It runs in disposable
Docker services and returns a versioned JSON result.

For a migration-related pull request, it:

1. resolves the base SHA, head SHA, changed migration files, revision IDs, and
   declared parent revisions;
2. runs Superset's single-head check;
3. creates a clean metadata database at the parent revision;
4. inserts the fixture data required by the migration's focused test;
5. upgrades to the changed revision;
6. checks the expected schema and data invariants;
7. downgrades to the parent and checks the declared downgrade policy;
8. upgrades to the changed revision again;
9. runs the focused migration tests;
10. stores commands, exit codes, timings, logs, and invariant results.

PostgreSQL is the primary deployment-faithful backend for the demo. SQLite can
be retained as a fast compatibility lane where the migration supports it. The
same oracle is used before and after remediation, so the system cannot declare
success merely because Devin says the issue is fixed.

An illustrative result is:

```json
{
  "repository": "ong6/superset",
  "head_sha": "<immutable SHA>",
  "revision": "<changed revision>",
  "database": "postgresql",
  "failed_invariant": "downgrade_executes",
  "command": "<replayable Docker command>",
  "status": "failed",
  "duration_seconds": 18.4,
  "artifact_path": "runs/<run-id>/oracle.json"
}
```

### Event-driven controller

The external automation repository owns the control plane; Superset remains the
target repository. The controller exposes two equivalent entry points:

- a GitHub `pull_request` webhook for normal operation;
- a local replay command using a saved payload for development and the demo.

It processes only events that change `superset/migrations/versions/`, migration
helpers, or focused migration tests. Each run is keyed by GitHub delivery ID,
repository, pull request number, and head SHA. Repeated deliveries return the
existing run instead of creating duplicate Devin sessions or GitHub issues.

The run state is explicit:

```text
received
  -> ignored | preflight_running
  -> passed | failure_reproduced
  -> investigating
  -> needs_human | remediation_running
  -> verifying
  -> remediated | verification_failed | timed_out | cancelled
```

SQLite persistence is sufficient for the take-home because it makes event,
oracle, session, and output state inspectable without adding infrastructure.
The API and state model can later move to a managed database without changing
the workflow.

### What Devin does

Devin begins only after the deterministic oracle reproduces a failure. This
keeps token usage focused and prevents the automation from becoming a generic
AI reviewer.

The workflow uses two bounded roles:

#### Investigator session

Inputs:

- immutable repository and head SHA;
- changed revision and parent revision;
- failed invariant;
- exact replay command;
- relevant logs and JSON result;
- migration conventions and focused test locations;
- instruction not to modify code.

Expected structured output:

- root-cause explanation tied to files and symbols;
- confidence and evidence;
- smallest proposed repair;
- focused test that would prevent recurrence;
- classification as actionable, expected behavior, insufficient evidence, or
  requires human policy.

#### Remediation session

Inputs:

- the investigator's accepted finding;
- one revision and one failed invariant;
- allowed file paths;
- required verification command;
- branch and pull-request instructions.

Expected output:

- the minimal migration or helper change;
- a focused regression test;
- the commands run and their results;
- a remediation pull request linked to the originating run and issue.

Separating investigation from remediation makes the audit trail clear and lets
the controller stop for human review when the expected migration behavior is
ambiguous. A later production version could combine the roles for low-risk,
high-confidence failures.

### Observable outputs

Every stage is visible without opening Devin:

- a GitHub Check shows ignored, running, failed, remediating, or passed state;
- a concise pull-request comment links the failing revision, invariant,
  replay command, run, and artifacts;
- one deduplicated issue records the reproduced failure and investigation;
- a remediation pull request contains the focused fix and test;
- a metrics endpoint and run page show throughput, latency, outcomes, and cost.

This answers the engineering-leader question at three levels:

| Question | Evidence |
|---|---|
| Is the automation operating? | Event count, deduplication count, active runs, terminal states |
| Is it improving delivery? | First-pass rate, confirmed failures, remediation success, median repair time |
| Is Devin worth the cost? | Sessions per fix, cost per successful remediation, manual time avoided |

### Demo seed and expected story

The fork-local seed is deliberately safe and obvious:

1. add a migration whose `upgrade()` creates or changes a database object;
2. keep a valid parent revision so the existing single-head check passes;
3. make `downgrade()` reference a nonexistent table or constraint;
4. open a pull request that triggers the controller.

The audience sees:

```text
single-head check passes
  -> round-trip oracle fails during downgrade
  -> investigator Devin explains the incorrect object reference
  -> remediation Devin fixes it and adds a focused test
  -> remediation pull request runs the identical oracle
  -> check turns green and metrics record one successful repair
```

The seed demonstrates a realistic deployment safeguard without claiming an
undisclosed Superset defect. It also creates a crisp before-and-after narrative
that fits the presentation.

### Why Devin is the core primitive

A script can execute Alembic and identify the failing command. It cannot
reliably understand why the migration failed, inspect surrounding conventions,
compare related migrations and tests, choose the smallest safe repair, implement
it, and prepare a reviewable pull request.

Devin performs that repository-scale engineering work. The controller supplies
deterministic facts, scope, and permissions; Devin supplies investigation and
code changes; the oracle independently decides whether those changes worked.
That division of responsibility is the central pitch:

> deterministic systems establish truth, while Devin turns verified failures
> into reviewed engineering outcomes.

## Demo narrative

1. A pull request changes an Alembic migration in the Superset fork.
2. The automation deduplicates the event and runs the migration rehearsal.
3. The existing single-head graph check passes, but the round-trip rehearsal
   fails during downgrade.
4. The controller starts an investigator Devin session with the failed revision,
   invariant, command, and logs.
5. Devin returns a structured finding and the controller creates or updates a
   deduplicated GitHub issue.
6. A remediation Devin session fixes the migration and adds or updates the
   focused regression test.
7. The same rehearsal passes, and the metrics page shows detection latency,
   repair latency, session outcome, and cost.

## Minimum implementation scope

### Automation repository

- Dockerfile and Compose file.
- FastAPI or similar webhook/replay controller.
- Local replay command for development and demo.
- SQLite persistence for events, runs, sessions, issues, and metrics.
- GitHub event validation adapter and mockable local adapter.
- Devin API client for session creation, polling, follow-up, and terminal-state
  handling.
- Structured prompts and JSON-schema validation for investigator and remediation
  sessions.
- GitHub Check/comment/issue/PR output adapter.
- Metrics endpoint and run summary.

### Superset fork artifacts

- One seeded migration issue in the fork.
- One failing migration PR or branch that demonstrates the oracle.
- One remediation PR created by the automation path or its managed Devin
  session.
- Evidence that the exact same command fails before and passes after.

## Guardrails

- Start Devin only after a deterministic failure is reproduced.
- Scope each Devin session to one repository, event, SHA, revision, invariant,
  and command.
- Deduplicate by GitHub delivery ID, repository, pull request number, and head
  SHA.
- Treat malformed Devin output, timeout, cancellation, and failed remediation as
  visible terminal states.
- Avoid broad code review, speculative risk language, or public vulnerability
  claims.
- Never auto-write to untrusted fork code with privileged credentials.

## Fast implementation sequence

This is a focused four-step implementation, not a four-day schedule.

| Step | Target |
|---|---|
| 1 | Seed one migration contract failure and implement the graph/upgrade/downgrade/re-upgrade oracle |
| 2 | Add the Dockerized replay/webhook controller, persistence, filters, and event/SHA deduplication |
| 3 | Integrate bounded Devin investigator/remediation sessions and GitHub issue/check/PR outputs |
| 4 | Re-run the oracle, expose metrics, document the workflow, and record the five-minute demo |

## Loom structure

| Segment | Time | Content |
|---|---:|---|
| What | 45s | Migration failures are deployment-blocking toil; single-head checks miss round-trip contract failures. |
| How | 2m | Show event replay, deterministic failure, Devin investigator, remediation session, PR/check/issue outputs. |
| Why Devin | 1m | Devin performs repository-scale diagnosis and minimal repair after deterministic evidence, not generic summarization. |
| When next | 45s | Add more migration invariants, branch/release coverage, policy waivers, and portfolio metrics. |
| Close | 30s | Show metrics: rehearsed PRs, failures fixed, latency, success rate, and cost. |

## Implementation order after this discovery PR

1. **Prove the contract:** create the public automation repository, seed the
   fork-local migration failure, and make the deterministic rehearsal fail.
2. **Connect the event:** add the Docker controller, replay/webhook entry point,
   persistence, path filters, and idempotency.
3. **Let Devin close the loop:** integrate investigator/remediation sessions
   with GitHub issue, check, and pull-request outputs.
4. **Demonstrate the result:** make the same rehearsal pass, expose metrics,
   finalize the runbook, record the Loom, and submit the repository links.
