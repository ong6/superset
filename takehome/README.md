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

# GitHub Issue Remediation Pilot

## Executive overview

We built a bounded workflow that turns a GitHub issue into a reviewable,
independently verified pull request without asking maintainers to leave GitHub.
The pilot combines automatic issue triage with explicit human authorization,
Devin-led investigation and implementation, repository-owned CI, and a visible
audit trail.

The outcome is not unrestricted autonomous development. It is a controlled
delegation model: maintainers decide which issues may proceed, the automation
limits what can change, and existing review and branch-protection processes
remain authoritative.

## The client problem

An accepted engineering issue still requires someone to:

1. understand and classify the report;
2. collect missing reproduction and acceptance details;
3. identify the relevant code and checks;
4. implement a focused change;
5. open and explain a pull request; and
6. monitor CI and return the result to the issue.

These handoffs create repeated context gathering and make it difficult to
delegate safely. Maintainers need a way to reduce that work without losing
control over scope, quality, security, or merge decisions.

The repository confirms that Superset has a large, heterogeneous codebase and
CI surface. The size of the time or throughput opportunity has not yet been
measured; establishing that baseline is part of the pilot.

## What we delivered

### Automatic issue triage

New and reopened issues can receive a bounded Devin triage session. The workflow
classifies the request, identifies missing information, and proposes a narrow
remediation contract covering allowed files, an acceptance command, and the CI
check that should prove the result.

### Maintainer-controlled remediation

No repair starts from an ordinary public issue alone. A maintainer with write
access must explicitly authorize it with `/devin fix`, `devin-fix`, or a manual
workflow dispatch. Maintainers can exclude an issue or request a separate retry.

### Bounded implementation

The controller creates one Devin session against an immutable default-branch
revision. It validates the issue contract, restricts changed paths and commands,
sets time and ACU limits, and does not pass GitHub or repository secrets into
the session.

### Independent proof

A run is successful only when the resulting pull request:

- targets the expected repository revision;
- changes only approved paths;
- closes the source issue;
- reports a consistent pull request and file list; and
- passes the named repository CI check.

Devin's own completion message is not treated as proof.

### Observable operation

GitHub labels and comments show triage, active work, verified completion, or the
need for human attention. SQLite records runs and state transitions, while the
report command summarizes elapsed time, ACU use, pull requests, CI, and outcomes.
Duplicate events are claimed and reconciled rather than starting duplicate
sessions.

### Repeatable demonstration

The repository includes a credential-free simulation, automated coverage for
success and guardrail failures, and three deterministic Superset examples:

- report-execution boundary validation;
- generated OpenAPI drift; and
- database migration downgrade ordering.

## How the workflow operates

```text
issue opened or reopened
  -> bounded triage and proposed scope
  -> maintainer authorizes a fix
  -> controller validates and claims the request
  -> bounded Devin session investigates and opens one pull request
  -> controller verifies scope, issue linkage, and repository CI
  -> GitHub records the outcome for the maintainer
```

The implementation is in
[Devin Issue Autopilot](../devin-issue-autopilot/README.md), with GitHub event
wiring in the repository workflow and reusable triage and repair procedures in
the Devin skills.

## Goals

1. **Reduce issue-to-review effort.** Automate repetitive triage, investigation,
   implementation, and status work for suitable issues.
2. **Preserve human ownership.** Keep authorization, review, merge, and policy
   decisions with maintainers.
3. **Make outcomes trustworthy.** Require deterministic acceptance criteria and
   independent repository checks.
4. **Fit the existing workflow.** Use GitHub issues, pull requests, labels,
   comments, and CI rather than introducing a separate interface.
5. **Create an evidence-based expansion path.** Measure value and failure modes
   before increasing scope or permissions.

## Current boundary

The delivered pilot is intentionally limited to one repository and narrowly
scoped issues. It does not merge changes, bypass branch protection, repair every
public issue, or provide a multi-repository control plane.

The current GitHub Actions job and controller form a working reviewer slice.
Production hardening would separate patch generation from publication, verify
changes in a clean sandbox, improve cancellation and recovery, and introduce a
durable queue or service only when scale requires it.

## Recommended pilot

Run the workflow on a small set of maintainer-approved issues and compare it
with the existing process. Capture:

- time from authorization to reviewable pull request;
- maintainer effort before and after automation;
- acceptance and merge rates;
- CI pass rate and policy rejection reasons;
- duplicate, timeout, cancellation, and escalation behavior; and
- ACU usage per accepted outcome.

Agree on target thresholds, stop conditions, and an owner before the pilot.
Expand to more issues or repositories only after the evidence supports it.

## Longer-term direction

The same controlled remediation platform can later support failed-CI repair,
dependency maintenance, migration issues, release work, or other deterministic
engineering tasks. Those are expansion options, not claims about the current
implementation.
