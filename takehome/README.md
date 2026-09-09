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

# Devin Event-Driven Automation Take-Home

This directory captures the discovery, implemented reviewer slice, and
production-hardening design for an issue-remediation automation built around
the Devin API and this Superset fork.

## Working implementation

The current take-home is the polling controller in
[Devin Issue Autopilot](../devin-issue-autopilot/README.md):

```text
issue opened/reopened unless `devin-exclude`
  -> one bounded Devin API v3 session uses `superset-issue-triage`
  -> controller upserts a classification and proposed contract
  -> maintainer comments `/devin fix` or applies `devin-fix`
  -> controller claims the remediation event in SQLite
  -> one bounded Devin API v3 session uses `superset-issue-fix`
  -> Devin opens one scoped pull request
  -> controller checks issue linkage, PR paths, and the named CI check
  -> controller comments, relabels the issue, and records the report
```

This is the authoritative reviewer path. It is deliberately smaller than the
production-hardening design: GitHub Actions dispatches events, but there is no
external webhook service, queue, controlled publisher, or clean-room patch
sandbox in the implemented slice.

The three issue fixtures are in
[`devin-issue-autopilot/issues/`](../devin-issue-autopilot/issues/), and the
bounded repair procedure is
[`superset-issue-fix`](../.devin/skills/superset-issue-fix/SKILL.md).

## Documents

1. [Product goal and production success criteria](01-goal.md)
2. [Evaluated automation ideas](02-ideas.md)
3. [Superset codebase overview](03-codebase-overview.md)
4. [Architecture map](architecture/README.md)
5. [Production-hardening recommendation](04-recommendation.md)
6. [Prior candidate comparison](05-three-idea-evaluation.md)
7. [Future CI-rescue technical specification](06-failing-check-repair-technical-spec.md)
8. [Future CI-rescue test cases](07-ready-for-review-ci-cases.md)
9. [Future CI-rescue implementation design](08-product-implementation-design.md)
10. [Issue-remediation production design](09-github-issue-remediation-implementation.md)

## Direction

The product direction is **GitHub Issue Remediation**. The working take-home
proves that a maintainer can authorize a narrowly scoped issue and receive one
bounded Devin session, one pull request, independent CI verification, and an
observable outcome.

The design documents describe how to harden that proof:

- move GitHub Actions dispatch into a durable event queue and reconciler;
- pin and reproduce an immutable target before session creation;
- keep repository publishing credentials outside Devin;
- have Devin return a patch rather than publish directly;
- verify in a clean sandbox before a controlled writer opens the PR; and
- add cancellation, richer status, policy versions, and production telemetry.

The earlier failing-check, rebase, release, and migration analyses remain
useful evaluated options and future trigger adapters. They are not the selected
first implementation and should not be read as overriding the issue-to-PR
goal.

## Devin skills

- [FDE customer-value demo](../.devin/skills/fde-customer-value-demo/SKILL.md)
  steers discovery and presentation toward evidenced customer value, adoption,
  and a credible trust path.
- [Event-driven remediation demo](../.devin/skills/event-driven-remediation-demo/SKILL.md)
  supplies the reusable safety, session-management, verification, testing, and
  observability checklist.
- [Superset issue triage](../.devin/skills/superset-issue-triage/SKILL.md)
  classifies incoming issues and proposes a bounded maintainer contract.
- [Superset issue fix](../.devin/skills/superset-issue-fix/SKILL.md) is the
  procedure used by the implemented controller.
