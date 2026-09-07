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

## Four-day path

| Day | Target |
|---|---|
| 1 | Controller, replay CLI, event model, idempotency, path filters, GitHub/Devin adapters, check stubs |
| 2 | Migration oracle for graph, upgrade, downgrade, re-upgrade, focused tests, logs, and JSON results |
| 3 | Devin investigator/remediation sessions, seeded failing migration, issue deduplication |
| 4 | GitHub outputs, metrics endpoint, before/after demo, README, runbook, and Loom script |

## Loom structure

| Segment | Time | Content |
|---|---:|---|
| What | 45s | Migration failures are deployment-blocking toil; single-head checks miss round-trip contract failures. |
| How | 2m | Show event replay, deterministic failure, Devin investigator, remediation session, PR/check/issue outputs. |
| Why Devin | 1m | Devin performs repository-scale diagnosis and minimal repair after deterministic evidence, not generic summarization. |
| When next | 45s | Add more migration invariants, branch/release coverage, policy waivers, and portfolio metrics. |
| Close | 30s | Show metrics: rehearsed PRs, failures fixed, latency, success rate, and cost. |

## Implementation order after this discovery PR

1. Create the public automation repository.
2. Add the replayable Docker controller skeleton.
3. Implement the migration rehearsal oracle.
4. Seed the first fork issue and failing migration branch.
5. Integrate Devin API session management.
6. Add GitHub output adapters and metrics.
7. Run the end-to-end before/after demo.
8. Record the Loom and submit the repository links.
