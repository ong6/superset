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

# Evaluated Automation Ideas

## Re-evaluation principle

The take-home originally required one successful issue-to-remediation path.
Later analysis drifted toward using a failed pull-request check as the primary
trigger. That is a strong extension, but it does not match the first
implementation goal as directly as a GitHub issue.

The authoritative product question is:

> Can a maintainer authorize one real issue and receive a reviewable,
> independently verified remediation pull request with observable status and
> failure handling?

The selected build is therefore the **GitHub Issue Remediation Runner**.
Earlier failed-check, rebase, release, flaky-test, and migration ideas remain
valuable future triggers for the same session, policy, verification, and
observability platform.

## Revised evaluation method

| Dimension | Weight |
|---|---:|
| Engineer pain frequency and reach | 25% |
| Adoption, trust, and workflow fit | 25% |
| Devin-as-core-primitive fit | 20% |
| Deterministic verification and safety | 15% |
| Five-minute demo and implementation feasibility | 15% |

Ideas lose points when they require a new dashboard engineers must remember to
visit, produce generic summaries, need broad write access on day one, or address
only a small fraction of pull requests.

## Current decision

| Candidate | Role | Decision |
|---|---|---|
| GitHub Issue Remediation Runner | Original issue-to-PR goal | **Build first** |
| Failing Check Repair Tool | Automatic CI-triggered remediation | Add after the issue loop works |
| Rebase Conflict Resolver | Pull-request maintenance | Platform extension |
| Release Cherry-Pick Tool | Release maintenance | Platform extension |
| Migration Upgrade Contract Guardian | Specialized deterministic guard | Domain adapter |

This is a sequence decision rather than a claim that issue remediation is
always more frequent than failed CI. It wins the first build because it best
matches the stated deliverable, has the shortest path to a real integration,
keeps authorization explicit, and uses ordinary pull-request CI as the
independent oracle.

## Recommendation

Build the **GitHub Issue Remediation Runner** with:

- `issues.labeled` and `devin:fix` as the first authorization event;
- a GitHub Actions dispatcher that validates, claims, and creates one Devin
  session;
- a scheduled reconciler that tracks session, PR, and CI state;
- one updateable issue comment and mutually exclusive status label;
- cancellation when the issue closes or authorization is removed;
- repository CI as the success oracle; and
- a tested Docker-replayable Python controller package.

The [detailed recommendation](04-recommendation.md) defines the selected
product boundary and rollout. The
[implementation design](09-github-issue-remediation-implementation.md) defines
the exact architecture, API lifecycle, workflows, idempotency, security,
status, failure taxonomy, observability, and tests.

## Prior discovery inventory

The earlier inventory below is retained as evidence for future trigger
selection. Its original scores compare opportunity size and demo quality; they
do not override the issue-to-remediation implementation decision.

### 1. PR CI Rescue Autopilot — 9.6

**Problem:** A failed check stops review, but the useful evidence is fragmented
across workflow jobs, logs, artifacts, changed files, and repository-specific
commands. Contributors rerun jobs or wait for maintainers because they do not
know whether the failure is caused by their change, a flake, infrastructure, or
stale generated output.

**Event trigger:** Completed failed `workflow_run` or check suite associated
with an open, non-draft pull request at the same immutable head SHA. The source
CI event must also show that the run began after the pull request was ready for
review. A maintainer label or `/devin fix` command can authorize remediation
after diagnosis.

**Workflow:** Resolve the immutable head SHA and failed job, download logs and
test artifacts, fingerprint the failure, and use workflow metadata plus changed
paths to select the smallest replay command. Devin receives the diff, focused
logs, related tests, repository instructions, and replay result. It classifies
the failure as change-caused, flaky, infrastructure, generated-artifact drift,
or unresolved. The controller posts a concise read-only diagnosis. For trusted
branches or explicit maintainer authorization, a second session makes the
smallest fix and reruns the same command.

**Observable outputs:** Pull-request check or comment with classification,
evidence, exact rerun command, and recommended next action; linked Devin
session; optional repair commit or companion pull request; structured run
record.

**Adoption metrics:** Failed PRs triaged, reproduction rate, diagnosis
acceptance, `/devin fix` invocations, time-to-diagnosis, time-to-green,
first-repair success, repair merge rate, maintainer interventions, and cost per
rescued pull request.

**Demo seed:** Open a trusted fork pull request whose changed production code
breaks one focused Python or frontend unit test. Replay the failed event, show
Devin reproduce and explain the failure, authorize the repair, and show the
same scoped test turn green.

**Why Devin:** A static router can extract a failed test name. Devin connects
the failure to the PR diff and surrounding code, chooses a minimal repair,
implements it, and handles unfamiliar failure shapes without a hand-written
rule per test suite.

### 2. Flaky Test Triage and Stabilization — 9.1

**Problem:** Reruns can turn red workflows green while preserving no durable
answer about which tests are unstable, how often they fail, or why. Superset
has both recent and historical reports of flaky frontend, E2E, and
database-specific CI.

**Event trigger:** Failed and retried workflow completions, including successful
reruns of the same SHA.

**Workflow:** Normalize JUnit, Jest, Playwright, Cypress, and job-log evidence
into stable test fingerprints. A ledger records first-pass and rerun outcomes.
Devin starts only after a fingerprint repeats or passes on rerun, then examines
the test, product code, timing, artifacts, and prior occurrences. A repair
session runs repeated focused verification before proposing stabilization.

**Observable outputs:** First-pass reliability check, flake ledger, deduplicated
issue, reproduction command, and focused stabilization pull request.

**Adoption metrics:** First-pass pass rate, hidden-green count, retry minutes,
repeat fingerprints, confirmed flakes, stabilization merge rate, and avoided
reruns.

**Demo seed:** Seed a focused test with a deterministic race switch so its first
attempt fails and its retry passes. Show the automation preserve the hidden
failure, reproduce the race, and remove it.

**Why Devin:** Parsing detects recurrence; Devin reasons about async behavior,
fixtures, state leakage, and waits to create a real fix rather than adding
another retry.

### 3. PR Backlog Shepherd — 8.8

**Problem:** A queue of hundreds of open pull requests makes it difficult to see
which changes are one action away from review, which are blocked by conflicts
or CI, and which need a product decision.

**Event trigger:** Scheduled backlog sweep plus pull-request, review, and check
events.

**Workflow:** Deterministic rules collect age, last activity, review state,
mergeability, failed checks, requested changes, and author association. Devin
reads only the highest-value blocked candidates and proposes one concrete next
action: fix CI, rebase, answer a review question, request a decision, or leave
untouched. It never closes pull requests automatically.

**Observable outputs:** Maintainer queue grouped by next action, opt-in pull
request comment, and linked rescue sessions for selected candidates.

**Adoption metrics:** Queue age, blocked-to-ready conversions, maintainer actions
accepted, reopened conversations, time waiting for next action, and stale PRs
resolved.

**Demo seed:** Replay a small fixture set containing a failed-check PR, a
conflicted PR, and a PR awaiting a maintainer decision. Show that the queue
assigns different, evidence-backed next actions.

**Why Devin:** Rules can sort by age; Devin can understand review threads,
diffs, and repository context well enough to recommend the next engineering
action.

**Why not first:** The business value is high, but the outcome is less
deterministic and maintainers may distrust automated backlog judgments before
seeing Devin succeed on narrower failed-check rescues.

### 4. Python Pin Drift Autopilot — 8.6

**Problem:** Dependency-source changes can leave generated requirement pins
stale, blocking a pull request with a mechanical but repository-specific repair.

**Event trigger:** Failed `Check Python Dependencies` run or changes to Python
dependency inputs.

**Workflow:** Reproduce the repository dependency check. Devin interprets the
resolver delta, regenerates only required files on an authorized branch, and
reports material transitive changes. The original checker verifies the result.

**Observable outputs:** Stale-file set, pin delta, resolver transcript, and
optional repair.

**Adoption metrics:** Dependency PRs rescued, first-fix success, resolver
ambiguities, time-to-green, and recurrence.

**Demo seed:** Change a direct dependency bound without regenerating its pins.

**Why Devin:** The checker finds drift; Devin interprets and safely resolves the
result.

**Why not first:** It is highly automatable but reaches a much smaller share of
the engineering team and pull-request queue.

### 5. Migration Upgrade Contract Guardian — 8.1

**Problem:** A valid Alembic graph does not prove that a changed migration can
upgrade, downgrade according to policy, and re-upgrade against a representative
database.

**Event trigger:** Migration-related pull-request changes or failed migration
checks.

**Workflow:** Run a disposable database rehearsal and start Devin only for a
reproduced invariant violation. Devin diagnoses and repairs the bounded
migration failure; the same rehearsal verifies the fix.

**Observable outputs:** Migration check matrix, replay artifact, investigation,
and focused repair.

**Adoption metrics:** Migration PRs rehearsed, contract failures found, repair
time, and deployment incidents avoided.

**Demo seed:** Add a migration with a valid head and broken downgrade object
reference.

**Why Devin:** Devin maps the database failure across migrations, helpers, and
tests into a minimal repair.

**Why demoted:** The design remains technically strong and deterministic, but
it helps only engineers changing migrations. It demonstrates capability better
than organization-wide adoption.

## Ideas retained for later expansion

- **Semantic OpenAPI breaking-change sentinel:** strong contract protection,
  but limited to API/schema changes.
- **Coordinated npm compatibility canary:** useful for dependency upgrades, but
  expensive and narrower than general failed-check rescue.
- **Semantic accessibility regression responder:** valuable and user-centered,
  but not the repository's most visible delivery bottleneck.
- **Principal-aware authorization reproducer:** technically deep but requires
  stricter private handling and is a poor first trust-building automation.

## Ideas rejected

- **Generic LLM review on every pull request:** noisy, difficult to verify, and
  likely to reduce trust.
- **Automatic stale-PR closing:** optimizes queue size rather than engineering
  outcomes and can alienate contributors.
- **Automatic rerun of every failed job:** hides flakes and spends CI without
  producing understanding.
- **Static dashboard of CI failures:** useful reporting, but Devin is not a core
  primitive and engineers must visit another surface.
- **Public security issue filing from patterns:** conflicts with Superset's
  evidence and private-disclosure requirements.
