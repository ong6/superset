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
the Devin API as its execution primitive to detect, investigate, and remediate
a concrete problem in this Superset fork.

The result should demonstrate two things at once:

1. **Engineering credibility:** deterministic evidence, bounded permissions,
   idempotent event handling, failure recovery, and reproducible remediation.
2. **Executive value:** less engineering toil, faster recovery, measurable
   throughput, and a clear path from pilot to production.

## Required system loop

```text
GitHub event
  -> controller validates and deduplicates delivery
  -> deterministic preflight reproduces a failure
  -> controller creates an investigator Devin session
  -> structured result updates a check or issue
  -> controller creates a bounded remediation Devin session
  -> remediation pull request runs the same deterministic oracle
  -> metrics report outcome, duration, and cost
```

Devin must perform meaningful engineering work. It should not merely summarize
the output of a conventional script. The surrounding system should provide
facts, constraints, tools, and success criteria; Devin should reason across
the repository, make the smallest safe change, and return observable artifacts.

## Deliverables

### Working project

- Public automation repository with a Docker-based local workflow.
- Webhook or replayable event entry point.
- Devin API session creation, polling, follow-up, and terminal-state handling.
- Structured logs and lightweight metrics.
- Runbook for local simulation without GitHub webhook infrastructure.
- At least one successful issue-to-remediation path in this Superset fork.

### Superset fork

- Honest, scoped issues describing reproducible problems or seeded test cases.
- Pull requests created by the automation or its managed Devin sessions.
- Evidence that the same deterministic check fails before and passes after.

### Five-minute presentation

- **What:** the engineering workflow problem and its business cost.
- **How:** event, controller, Devin sessions, deterministic oracle, and outputs.
- **Why Devin:** repository-scale reasoning and autonomous remediation within
  explicit guardrails.
- **When next:** production hardening, broader triggers, governance, and
  portfolio-level analytics.

## Evaluation rubric

| Dimension | Evidence of a strong submission |
|---|---|
| Problem selection | Specific, recurring, expensive, and reproducible |
| Devin leverage | Devin owns investigation and remediation, not just prose |
| Technical design | Idempotency, retries, timeouts, scoped access, state model |
| Safety | Deterministic gate, bounded prompts, no speculative findings |
| Observability | Status, latency, success rate, throughput, cost, artifacts |
| Demo quality | Crisp event-to-PR story with visible before/after proof |
| Business case | Clear time saved, risk reduced, and adoption path |

## Definition of done

- One event can be replayed locally and through the configured integration.
- Duplicate deliveries do not start duplicate sessions.
- Every Devin session is correlated to repository, event, commit SHA, and issue.
- Failure, timeout, cancellation, and malformed-output states are visible.
- A reproduced issue creates a useful GitHub artifact.
- A remediation pull request passes the same check that detected the issue.
- The metrics view answers:
  - How many events were received?
  - How many became actionable tasks?
  - How many sessions succeeded or failed?
  - How long did detection and remediation take?
  - How many issues were fixed?
  - What did each successful remediation cost?

## Fast implementation sequence

This is a compact four-step build sequence, not a four-day estimate. The
intentionally narrow migration fixture, deterministic oracle, and replayable
event path make it suitable for rapid implementation and demonstration.

### Step 1 — define the failure contract

- Add one fork-local migration issue and seeded failing revision.
- Implement the graph, upgrade, downgrade, and re-upgrade rehearsal.
- Emit a structured result containing the revision, invariant, command, logs,
  duration, and outcome.

### Step 2 — build the event controller

- Add the Dockerized webhook/replay entry point and SQLite run state.
- Filter migration-related pull requests and deduplicate by delivery ID and
  head SHA.
- Run the deterministic oracle and start Devin only for a reproduced failure.

### Step 3 — manage investigation and remediation

- Create bounded investigator and remediation session contracts.
- Poll sessions, validate structured output, and expose terminal states.
- Create or update the GitHub issue, remediation pull request, and check.
- Re-run the same oracle against the proposed change.

### Step 4 — prove and present the loop

- Exercise success, failure, duplicate-event, malformed-output, and timeout
  paths.
- Publish status, latency, throughput, success-rate, and cost metrics.
- Finalize the README, runbook, architecture, and five-minute demo.
