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

This directory captures the discovery and design work for an event-driven
automation built around the Devin API and this Superset fork.

## Documents

1. [Goal and success criteria](01-goal.md)
2. [Evaluated automation ideas](02-ideas.md)
3. [Superset codebase overview](03-codebase-overview.md)
4. [Architecture map](architecture/README.md)
5. [Recommendation and next steps](04-recommendation.md)
6. [Prior candidate comparison](05-three-idea-evaluation.md)
7. [Future CI-rescue technical specification](06-failing-check-repair-technical-spec.md)
8. [Future CI-rescue test cases](07-ready-for-review-ci-cases.md)
9. [Future CI-rescue implementation design](08-product-implementation-design.md)
10. [GitHub issue remediation implementation](09-github-issue-remediation-implementation.md)

## Recommended direction

Build the **GitHub Issue Remediation Runner**: a maintainer-authorized GitHub
Action that turns a repository issue into one bounded Devin session, one
reviewable pull request, independently verified CI, and one observable status
record on the issue.

This is the authoritative take-home direction:

- a maintainer applies `devin:fix` to an open issue;
- a dispatcher workflow validates and claims one remediation generation;
- the workflow creates a bounded Devin API session;
- Devin investigates, implements, tests, and opens a pull request;
- a scheduled reconciler publishes queued, active, blocked, failed, cancelled,
  timed-out, or successful status; and
- the repository's normal pull-request CI, not Devin's self-report, decides
  whether the remediation succeeded.

The pilot uses GitHub Actions for dispatch, reconciliation, cancellation, and
reporting. This produces a working integration without first deploying a
public webhook service, queue, or database. A small tested Python package owns
the state machine and API contracts and can replay the same events in Docker.

The
[implementation document](09-github-issue-remediation-implementation.md)
contains the architecture comparison, API contract, workflow skeletons,
idempotency strategy, security boundaries, state and failure model,
observability design, test plan, and production expansion criteria.

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
