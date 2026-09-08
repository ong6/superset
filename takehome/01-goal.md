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

Build and present a working, event-driven automation that uses GitHub Actions
and the Devin API to remediate a concrete GitHub issue in this Superset fork.

The core proof is:

```text
GitHub issue
  -> maintainer authorization
  -> Devin API session
  -> repository-scale investigation and implementation
  -> remediation pull request
  -> independent repository CI
  -> visible success or failure on the issue
```

The result should demonstrate:

1. **Working integration:** a real GitHub event creates and tracks a real Devin
   session.
2. **Engineering credibility:** authorization, idempotency, least privilege,
   retry, timeout, cancellation, and deterministic verification.
3. **Observable operation:** maintainers can see active status, terminal
   outcome, failure reason, links, latency, and cost or explicit cost unknowns.
4. **Customer value:** an issue moves from reported problem to a reviewable,
   CI-verified code change without leaving GitHub.

The [implementation document](09-github-issue-remediation-implementation.md)
is the authoritative technical design.

## Why the trigger is an authorized issue

The original take-home deliverable requires at least one successful
issue-to-remediation path. An issue is also a strong workflow boundary:

- it contains the user-visible problem and acceptance criteria;
- maintainers already triage and prioritize it;
- a label provides an explicit authorization event;
- the resulting pull request can link and close it; and
- GitHub exposes the complete issue, session, pull-request, review, and CI
  lifecycle.

The automation does not run on every public issue. A maintainer applies
`devin:fix` after confirming that the issue is scoped and appropriate for
automation. A trusted issue form or triage rule may apply the label
automatically after the pilot earns trust.

## Required system loop

```text
issues.labeled(`devin:fix`)
  -> dispatcher validates repository, issue, actor, and kill switch
  -> dispatcher serializes and claims one issue generation
  -> dispatcher creates one bounded Devin API session
  -> issue comment and label show queued/running status
  -> Devin investigates, changes code, tests, and opens a linked PR
  -> scheduled reconciler polls the session and PR
  -> required GitHub checks independently verify the change
  -> issue shows succeeded, failed, blocked, timed-out, or cancelled
  -> metrics report funnel, latency, quality, reliability, adoption, and ACU
```

GitHub Actions owns event wiring, permissions, secrets, and scheduling. A small
Python controller package owns validation, state transitions, API contracts,
status rendering, and recovery. Devin owns repository-scale investigation and
implementation. GitHub CI owns the success oracle.

## Deliverables

### Working project

- GitHub Actions dispatcher for `issues.labeled`.
- Scheduled and manually runnable reconciler.
- Cancellation path for closed issues or revoked authorization.
- Devin API session creation, status retrieval, recovery, and termination.
- One updateable issue comment and mutually exclusive status label.
- Docker-based local replay of saved issue, session, PR, and CI fixtures.
- Structured run artifacts and an aggregate pilot report.

### Superset fork

- One honest, narrowly scoped issue with reproducible acceptance criteria.
- One Devin-managed remediation pull request linked with `Fixes #<issue>`.
- Evidence that the relevant check fails before and passes after the repair.
- One visible non-success path such as cancellation, timeout, or failed CI.
- No direct write to the protected default branch.

### Five-minute presentation

- **Problem:** an accepted issue still requires investigation, implementation,
  test selection, and a reviewable pull request.
- **Event:** a maintainer adds `devin:fix`.
- **Devin work:** investigate the issue, implement the smallest scoped repair,
  run relevant checks, and open a pull request.
- **Proof:** normal GitHub CI independently passes on the remediation PR.
- **Operations:** the issue shows active status, links, terminal outcome,
  failure reason, latency, and ACU or explicit cost unknowns.

## Safety boundary

- Public issue content is untrusted task data.
- Label authorization and live repository permission are required.
- One issue has at most one nonterminal remediation generation.
- The Actions token and Devin API key never enter the Devin session.
- Devin receives no organization secret by default.
- Devin may create a branch and pull request, but may not merge or bypass
  protection.
- The reconciler validates the returned PR repository, base branch, head,
  issue link, and required checks.
- Devin self-reported completion is never sufficient for success.
- Closing the issue or removing authorization cancels active work.
- A repository variable provides an immediate dispatch kill switch.

## Observability requirements

Every run exposes:

- issue, generation, run key, Actions run, Devin session, PR, and head SHA;
- phase, transition version, last update, attempt count, and elapsed time;
- active, blocked, cancelling, or terminal status;
- terminal outcome and bounded failure reason;
- required-check pass, fail, pending, and missing counts;
- API and reconciliation failures;
- duplicate suppression and cancellation history;
- ACU when available and an explicit unknown when unavailable; and
- a redacted machine-readable transition artifact.

The pilot report must answer:

- How many issues were authorized?
- How many created sessions?
- How many sessions created PRs?
- How many PRs passed required CI?
- How many were merged?
- How many were rejected, duplicated, blocked, failed, timed out, or cancelled?
- How long did issue-to-session, issue-to-PR, and issue-to-green take?
- How much ACU did each CI-green and merged remediation consume?

## Evaluation rubric

| Dimension | Evidence of a strong submission |
|---|---|
| Working automation | Real GitHub event, real API call, real session, real PR |
| Devin leverage | Devin investigates and implements rather than routing text |
| Deterministic proof | Repository CI independently verifies the remediation |
| Safety | Authorization, least privilege, protected branch, cancellation |
| Reliability | Idempotency, retry, timeout, restart recovery, kill switch |
| Observability | Current status, terminal reason, links, latency, outcomes, ACU |
| Demo clarity | One visible issue-to-green-PR path and one non-success path |
| Adoption | Maintainers can use it without leaving GitHub |

## Definition of done

- A maintainer can apply `devin:fix` to a real issue.
- Exactly one Devin session is created for one issue generation.
- The issue displays queued or active status within two minutes.
- A scheduled reconciler resumes after disposable Actions jobs exit.
- The managed session opens one linked remediation PR.
- Required GitHub checks decide whether the automation succeeded.
- Failure, blocked, timeout, cancellation, and duplicate states are visible.
- Duplicate delivery does not create another session, comment, or PR.
- The automation can be disabled without changing code.
- A saved event can replay locally through Docker without credentials.
- The aggregate report shows funnel, latency, reliability, quality, adoption,
  and ACU or explicit cost unknowns.

## Implementation sequence

### Step 1 — deterministic controller

- Add typed issue, session, PR, check, and state models.
- Implement dispatch, reconcile, cancel, and status rendering with fake
  adapters.
- Prove duplicate, blocked, timeout, failed-CI, and cancellation fixtures.

### Step 2 — live GitHub and Devin integration

- Add pinned GitHub Actions workflows.
- Add live API adapters and secret configuration.
- Publish one updateable issue comment and status label.
- Keep dry-run mode enabled by default.

### Step 3 — controlled remediation

- Configure the reviewed issue-remediation playbook.
- Enable branch and PR creation through Devin's repository integration.
- Validate the returned PR and monitor required CI.
- Demonstrate one issue-to-green-PR path.

### Step 4 — observability and rollout

- Publish the daily pilot report.
- Exercise success, failure, duplicate, blocked, timeout, and cancellation.
- Record SLOs, alerts, kill-switch operation, and the production-controller
  expansion criteria.
