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
2. [Ranked automation ideas](02-ideas.md)
3. [Superset codebase overview](03-codebase-overview.md)
4. [Architecture map](architecture/README.md)
5. [Focused comparison of the three candidate automations](05-three-idea-evaluation.md)
6. [Failing Check Repair technical specification](06-failing-check-repair-technical-spec.md)
7. [Ready-for-review CI rescue test cases](07-ready-for-review-ci-cases.md)
8. [PR CI Rescue product implementation design](08-product-implementation-design.md)
9. [Detailed recommendation and implementation design](04-recommendation.md)

## Recommended direction

Build the **PR CI Rescue Autopilot**: a GitHub-event-driven controller that
turns a failed pull-request check into a reproduced failure, a bounded Devin
investigation, and—when authorized—a verified repair.

This direction starts with a workflow engineers already feel:

- Apache Superset has hundreds of open pull requests and a broad CI surface;
- failed tests and checks consume contributor and maintainer attention before
  review can continue;
- Devin works inside the pull request rather than asking engineers to adopt a
  separate product surface;
- deterministic commands verify the diagnosis and repair;
- the pilot can begin read-only, then add opt-in remediation after trust is
  established.

The focused comparison independently evaluates a **Rebase Conflict Resolver**,
**Failing Check Repair Tool**, and **Release Cherry-Pick Tool**. It ranks failed
check repair first, then shows how the other two can reuse the same event,
session, policy, verification, publishing, and observability platform.

The Failing Check Repair technical specification expands that decision into the
controller architecture, Devin API contracts, deterministic report-budget test
case, security gates, observability metrics, pilot scorecard, and follow-up
implementation sequence for a VP Engineering technical review.

The ready-for-review test cases make the product boundary executable: draft CI
never starts Devin, a fresh failed run after `ready_for_review` does, and
duplicate, stale, or re-drafted runs fail closed.

The product implementation design converts that specification into a concrete
standalone package layout, typed ports, persisted state model, API adapter,
patch handoff, fixture suite, and three-pull-request delivery sequence.

## Devin skills

- [FDE customer-value demo](../.devin/skills/fde-customer-value-demo/SKILL.md)
  steers discovery and presentation toward evidenced customer value, adoption,
  and a credible trust path.
- [Event-driven remediation demo](../.devin/skills/event-driven-remediation-demo/SKILL.md)
  supplies the reusable safety, session-management, verification, testing, and
  observability checklist.
