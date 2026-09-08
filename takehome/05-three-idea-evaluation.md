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

# Prior Candidate Comparison: CI, Rebase, and Release Automation

## 1. Document role

This document preserves the evidence-led comparison of three pull-request and
release automations. It does not override the original issue-to-remediation
deliverable. The selected first implementation is the
[GitHub Issue Remediation Runner](09-github-issue-remediation-implementation.md).

Within this three-option comparison, the Failing Check Repair Tool scores
**9.1/10**, ahead of the Rebase Conflict Resolver at **8.8** and the Release
Cherry-Pick Tool at **8.2**. It is therefore the preferred **future automatic
trigger** after the issue-driven session, status, policy, verification, and
observability loop works.

The CI-rescue concept is deliberately narrower than “autofix CI.” Its build
must not repair untrusted forks, infer flakiness from one rerun, execute commands
suggested by logs or a model, let Devin hold GitHub credentials, or call a
repair successful from Devin's report alone. The controller owns event
validation, immutable correlation, commands, authorization, state, and
verification. Devin owns evidence-based diagnosis and the bounded production
code change.

All three should become later workflow adapters on the issue-remediation
event/session/policy/proof platform rather than separate products.

## 2. Evidence snapshot: facts, assumptions, and limits

All public metadata below is a **point-in-time snapshot**, not proof of
causation or measured return on investment. Counts can differ by a few items
within the same date because the public repository changed while the
independent evaluations were performed.

### Observed facts

| Date | Observed evidence | What it supports—and what it does not |
|---|---|---|
| 2026-09-08 | Public GitHub searches returned 429–431 open Superset PRs, approximately 205–206 older than 30 days, and 132–133 older than 90 days. | Superset has a large PR workflow. Age does **not** prove CI caused delay. |
| 2026-09-08 | The public Actions API reported 26,039 historical failed runs across all events and 19,214 from `pull_request` events; recent failures included pre-commit and frontend CI. | Failures recur across the repository. Lifetime totals are not a current failure rate and include expected or quickly fixed runs. |
| 2026-09-08 | 168 of 431 open PRs carried active `requires:rebase`; 129 were at least about 30 days old and 93 at least about 90 days old. | Conflict resolution has unusually broad visible reach. It does not measure conflict-handling minutes or show that target churn caused each conflict. |
| 2026-09-08 | The preceding 30 days contained 753 merged PRs. | The target branch changes substantially. This is context, not causal proof for individual conflicts. |
| 2026-09-08 | Release-label searches returned 348 PRs for `v6.0`, 188 for `v5.0`, and 222 for `v4.1`. | Release candidate sets can be large. Label totals do not reveal conflict rate, release cadence, or manual effort. |
| Repository checkout | Superset defines 52 GitHub workflows and has Python, frontend, integration, E2E, migration, generated-file, and dependency checks (`takehome/03-codebase-overview.md:225-259`). | There is broad, heterogeneous CI and no safe universal replay command. |
| Repository checkout | Python unit CI emits JUnit artifacts, while a separate `workflow_run` reporter writes checks from base-branch context without checking out PR code (`.github/workflows/superset-python-unittest.yml:66-117`; `.github/workflows/superset-python-unittest-report.yml:3-21,34-69`). | There is a concrete event, evidence source, GitHub output surface, and privilege-separation precedent for the future CI trigger. |
| Repository checkout | Frontend CI has eight Jest shards; backend integration has three service environments; E2E captures failure artifacts (`.github/workflows/superset-frontend.yml:76-104`; `.github/workflows/superset-python-integrationtest.yml:41-89,125-177,186-226`; `.github/workflows/superset-e2e.yml:53-309`). | Later adapters require suite-specific evidence and command selection. |
| Repository checkout | A two-hour workflow adds and removes `requires:rebase` (`.github/workflows/label-merge-conflicts.yml:3-20,45-54`). | The rebase idea has an existing signal and UX, although the scheduled detector adds latency. |
| Repository checkout | Release managers use labels and `cherrytree`; conflicts require a manual stop, fix, stage, continue, rerun, and push loop (`RELEASING/README.md:78-84,166-218`). | Backports contain real manual conflict work, but existing tooling already handles clean mechanical picks. |

### Assumptions to validate in a pilot

| Assumption | Pilot measurement |
|---|---|
| A useful diagnosis saves meaningful contributor or maintainer time. | Sample manual handling time; ask for useful/not-useful feedback; compare event-to-diagnosis and event-to-green against a baseline. |
| A material share of failed checks is reproducible and change-caused. | Eligible failures, adapter coverage, reproduction rate, and validated classification distribution. |
| Maintainers will authorize small evidence-backed repairs. | Repair offers, invocations, acceptance, merge rate, and post-proposal edits. |
| Conflict resolution often costs tens of minutes or more. | Time spent per eligible conflict, candidate acceptance, and human edits; do not infer this from the 168 labels. |
| Release teams support several maintenance lines and backport frequently. | Release cadence, candidates per batch, conflict/dependency rate, and cost per merged backport. |
| A live Devin session and verification fit a five-minute presentation. | Treat this as unproven. Use a warm image and an honestly labeled replay of a completed run as fallback. |

The evidence establishes **prevalence and workflow fit**, not causation. ROI,
classification accuracy, repair quality, semantic preservation, latency, and
cost remain hypotheses until measured.

## 3. Weighted scorecard

Scores are on a 10-point scale. The weights prioritize adoption and real
engineering pain over novelty. Weighted totals are rounded to one decimal.

| Criterion | Weight | Failing Check Repair | Rebase Conflict Resolver | Release Cherry-Pick Tool |
|---|---:|---:|---:|---:|
| Pain frequency and persona reach | 25% | 9.3 | 9.0 | 7.8 |
| Adoption, trust, and workflow fit | 25% | 9.4 | 8.7 | 8.3 |
| Devin is a core reasoning primitive | 20% | 9.2 | 9.4 | 8.8 |
| Deterministic verification and safety | 15% | 9.1 | 8.8 | 9.0 |
| Five-minute demo and implementation feasibility | 15% | 8.3 | 8.0 | 7.0 |
| **Weighted total** | **100%** | **9.1** | **8.8** | **8.2** |
| **Decision within these three** |  | **First future trigger** | Platform extension 2 | Platform extension 3 |

The rebase idea has the strongest single conflict-reasoning task, but its
semantic oracle is necessarily incomplete and safe publishing is socially and
technically harder. The release idea is consequential and safe when
approval-gated, but it is episodic, serves fewer users, and competes with
`cherrytree` on the mechanical path. The selected idea has the best combined
adoption wedge and proof loop.

## 4. Standalone evaluations

### 4.1 Failing Check Repair Tool — 9.1/10

#### Company value and personas

A failed check blocks an existing daily workflow and distributes evidence among
jobs, logs, artifacts, diffs, and repository-specific commands. A useful tool
reduces blind reruns and maintainer back-and-forth while creating normalized CI
failure data. Primary users are contributors, maintainers/reviewers, test and
developer-productivity owners, release managers who consume healthier changes,
and engineering leaders measuring adoption and cost.

The value claim is broad but bounded: the snapshot proves many PRs and a complex
CI surface, not that old PRs are CI-blocked or that every failure is actionable.

#### Event, session, and output design

1. Accept a signed GitHub `workflow_run.completed` failure only when it resolves
   to exactly one open PR and one immutable head SHA. Also accept a signed saved
   payload for deterministic local replay.
2. Verify HMAC, installation and repository allowlists, delivery ID, action,
   conclusion, PR, and SHA. Atomically deduplicate by
   `repo + delivery_id`, then by
   `repo + PR + head_sha + workflow + job + normalized_fingerprint`.
3. Fetch jobs, focused log windows, annotations, JUnit or other artifacts,
   changed paths, and the workflow definition. Treat all PR content, artifacts,
   logs, and repository text as untrusted data.
4. In a secretless, network-restricted sandbox checked out at the exact SHA,
   select an allowlisted repository-native command from deterministic adapters.
   The first adapter supports an exact pytest node. Persist the original CI
   command and the focused command; never execute shell text supplied by a log
   or Devin.
5. Programmatically create one bounded, read-oriented Devin investigation
   session after useful preflight. Persist its returned ID immediately and
   correlate it to repository, PR, SHA, workflow run, failed job, command, and
   controller run. Poll through an API adapter with bounded backoff and a
   controller deadline. Validate a strict structured result. Do not promise
   streaming tokens, a model progress percentage, cancellation, dollar cost,
   or any other API behavior unless the deployed API contract exposes it.
6. Require one classification: `change_caused`, `likely_flaky`,
   `infrastructure`, `generated_drift`, or `unresolved`, with cited evidence,
   uncertainty, the controller-selected replay command, allowed paths, and a
   recommendation. One passing rerun never proves a flake.
7. Publish a read-only, updateable GitHub Check first. On a same-repository
   trusted branch, an authenticated maintainer label or `/devin fix` bound to
   the same failure key and SHA may authorize a second bounded remediation
   session. Revalidate head SHA, actor permission, trust, and path policy before
   creation and before any write.
8. Devin returns a minimal patch; it never pushes. The controller applies and
   verifies that patch in a clean sandbox, then a narrowly privileged publisher
   may create a bot commit or companion PR.

Observable output is one GitHub Check plus an immutable machine-readable run
record. The Check shows active/terminal state, pinned SHA, failed job and step,
reproduction result, classification, two or three provenance-linked facts,
analysis and uncertainty, exact replay command, next action, run/session links,
and verification result. A repair artifact includes changed paths, patch hash,
before/after command transcripts, and residual risk.

#### Safety

- Separate the privileged webhook/publisher from secretless code execution.
- Keep Devin credential-free; issue a narrow GitHub token only to the publisher
  after policy and verification pass.
- Keep forks read-only; never run PR code in a privileged base-context job.
- Pin every artifact and session to a SHA; compare the live head again before
  authorization, verification, and write.
- Forbid test, workflow, dependency, security, and out-of-allowlist edits in the
  first repair fixture. Reject skips, deselection, weakened assertions, and a
  changed test collection count.
- Treat Devin output as analysis, not truth. The controller owns schema checks,
  commands, exit codes, artifact hashes, authorization, and success status.
- Bound concurrency, command time, session time, follow-ups, and budget. If an
  API does not expose cost, record `unknown` rather than estimate it.

#### Test strategy

The focused fixture changes `if sum(reserves) >= budget` to `>` in
`superset/utils/report_execution.py:38-58`. The existing equality case in
`tests/unit_tests/utils/test_report_execution.py:182-205` then fails because it
expects `ValueError`. The correct production-only repair restores `>=`.

Required controller tests cover:

- **Happy path:** exact pytest node fails before, the evidence-backed diagnosis
  is published, an authorized minimal repair is independently applied, and the
  same node plus a production invariant probe pass after.
- **Duplicate:** concurrent and replayed equivalent deliveries create one run,
  one investigation, at most one remediation, one Check, and no duplicate write.
- **Stale SHA:** a head change before authorization or write ends
  `stale_target`; the old patch is quarantined and no write occurs.
- **Malformed output:** invalid JSON, an unknown classification, missing evidence
  references, command substitution, or missing patch metadata ends
  `malformed_output` with no remediation or write.
- **Timeout:** replay, investigation, remediation, and verification deadlines
  persist the timed-out stage and partial evidence; polling and follow-up remain
  bounded and restart-safe.
- **Unauthorized write:** an untrusted fork, forged command, or out-of-policy
  path remains read-only and produces an auditable denial without token leakage.
- **Dangerous false green:** deleting or weakening a test, adding skip/xfail,
  changing workflow filters, or avoiding collection is rejected even if a
  command exits zero.
- **Classifier control:** a passing local replay without recurrence evidence is
  `unresolved` or `infrastructure`, not automatically flaky or change-caused.

#### Observability

Persist an append-only transition timeline and expose active versus completed
separately from outcome. States include `received`, `evidence_collecting`,
`replaying`, `investigating`, `diagnosis_published`,
`awaiting_authorization`, `remediation_running`, and `verification_running`;
terminal reasons include rejected, duplicate, diagnosed, repaired, replay or
repair failure, timeout, malformed output, policy violation, stale target, and
cancellation.

Report accepted/deduplicated events, queue depth, reproduction coverage,
classification, diagnosis usefulness, repair offers and invocations, verified
and merged repairs, policy blocks, p50/p95 stage latency, event-to-diagnosis,
event-to-green, sandbox/CI minutes, session count, API-reported consumption when
available, and cost per useful diagnosis and verified rescue. Progress is the
current state, completed evidence items, elapsed time, and deadline—not a model
percentage. Structured logs carry immutable correlation IDs and artifact hashes
and redact tokens and untrusted raw content.

#### Demo and why Devin

The demo moves one deterministic Python boundary regression from a red check to
an evidence-backed diagnosis and, after explicit authorization, to a verified
green check. Devin is essential because it connects the equality change, test
failure, surrounding validation contract, and minimal production repair. A
static controller can extract a test name and run pytest; without Devin it
cannot generalize that causal reasoning across unfamiliar code and failure
shapes. Devin still cannot authorize or certify its own work.

### 4.2 Rebase Conflict Resolver — 8.8/10

#### Company value and personas

The active `requires:rebase` snapshot—168 of 431 open PRs—provides an unusually
concrete adoption surface. Contributors regain reviewability; maintainers avoid
rebase coaching; CI owners avoid wasteful reruns; release managers can later
reuse the mechanism for backports. The count establishes unresolved breadth,
not manual time or target-churn causation.

#### Event, session, and output design

Consume signed `pull_request` label events, `synchronize` and `reopened`
invalidations, and an authorized `/devin rebase`; support saved-event replay.
Store delivery and resolution keys, original base/head SHAs, latest target SHA,
fork and authorization status, commits, PR diff, conflict index, and protected
oracles. In a no-credential worktree, fetch only pinned objects and reproduce
the conflict by replaying contributor commits in order.

For an actionable conflict, create and persist one bounded Devin session with a
strict output schema and correlation tags. Devin infers both sides' behavior
from commits, tests, review context, and surrounding code; it resolves declared
conflicts and approved adjacent paths and returns a candidate, per-hunk
rationale, source-to-candidate intent map, changed paths, commands, uncertainty,
and residual risk. The controller polls documented session states through an
adapter and validates the output. Optional follow-up is capped at one and used
only when the deployed API contract supports messages.

The primary output is an updateable `Devin Rebase Proof` Check and a read-only
patch or bot-owned candidate branch. It shows old base, original head, target,
and candidate SHAs; conflict files; per-hunk rationale; session link; gate
results; authorization; latency; and API-reported ACUs when available. A proof
bundle includes webhook hash, conflict index, validated output, path/mode
report, `git diff --check`, conflict-marker scan, `git range-diff`, protected
oracle and scoped-test results, and publish lease result.

#### Safety

Devin receives no GitHub credential and untrusted code runs without secrets or
egress. The controller requires target ancestry, unmodified source commits, no
unmerged entries or markers, clean `git diff --check`, allowed paths and modes,
expected authorship mapping, protected tests from a read-only controller-owned
copy, scoped repository checks, and a reviewable range-diff. Range-diff is
review evidence, not a semantic oracle.

Default output is read-only. Forks and unauthorized actors cannot mutate refs.
After explicit authorization, publish to a bot-owned branch or draft companion
PR. Do not force-push a contributor branch in the pilot. Re-read head and target
SHAs immediately before publish; any mismatch invalidates the candidate.
Ambiguous, broad, migration, generated, binary, submodule, rename/delete, or
security-sensitive conflicts route to a human.

#### Test strategy

Use a focused conflict in `scripts/change_detector.py` where the target
preserves the distinction between rate-limited and permission-denied HTTP 403,
while the contributor adds HTTP 408 retry behavior. Controller-owned tests
require both behaviors; either one-sided textual resolution fails.

Exercise happy path, duplicate delivery and equivalent resolution keys, target
advancement before publish, malformed or incomplete Devin JSON, session and
verification timeout, unauthorized fork writes, and the idea-specific dangerous
failure: a marker-free candidate that silently drops either target or
contributor behavior. Verify no duplicate sessions or writes, exact-SHA
staleness handling, bounded polling, and a blocked publish whenever protected
intent tests fail.

#### Observability

Expose fixed stages—conflict reproduced, session running, output validated,
structure passed, intent passed, tests completed, awaiting authorization, and
published—plus entered time, heartbeat, terminal outcome, and reason. Separate
controller operational success from resolution outcome: `needs_human` can be a
safe successful handling, while stale publication or unauthorized mutation is
an operational failure.

Measure events, deduplication, sessions, verified candidates, authorizations,
publishes, mergeability, later merges, p50/p95 stage latency, timeout rate,
sessions and ACUs per outcome when exposed, CI minutes, candidate acceptance,
human edits, one-shot verification, semantic regressions, unauthorized writes,
and repeat use. Never invent model completion percentages or unavailable cost.

#### Demo and why Devin

Show a red `requires:rebase` PR, replay the event, reproduce the pinned conflict,
show Devin's two-sided intent map, run protected tests, authorize a bot branch,
and demonstrate duplicate suppression plus rejection of a one-sided candidate.
Devin is core because Git can identify conflicts but cannot infer how old and
new behavior should compose. The limitation is explicit: graph checks and tests
prove selected contracts, not all human intent.

### 4.3 Release Cherry-Pick Tool — 8.2/10

#### Company value and personas

An approval-gated backport planner can reduce wrong-branch, omitted-commit,
conflict, and partial-batch risk for release managers, maintainers, subsystem
owners, QA, and incident responders. Its work is consequential but episodic and
its direct persona set is narrower. Existing `cherrytree` already provides
candidate discovery and mechanical application, so Devin's incremental value
must be semantic applicability, dependency reasoning, conflict resolution, and
test selection—not running `git cherry-pick`.

#### Event, session, and output design

Accept signed release-label add/remove events and merged/closed events that
change eligibility, with dispatch or saved-event reconciliation. Validate the
installation, repository, exact label-to-target mapping, merged source SHA, and
target. Deduplicate transport by delivery key and immutable work by a plan key
containing target ref/base SHA and the sorted candidate PR/source-SHA set.

The controller computes patch IDs, finds already-applied changes, derives known
dependencies, and dry-runs the ordered picks in a disposable worktree. Clean
mechanical batches need no Devin session. A conflict, dependency ambiguity, or
semantic-applicability question creates one bounded session with pinned source
and target SHAs, PR intent, diffs and conflict hunks, maintenance-branch code,
allowed paths and commands, and a strict schema. Devin returns candidate order,
dependency concerns, per-PR applicability, a conflict patch, tests and rationale,
uncertainty, and `ready_for_approval` or `human_required`.

Publish a read-only plan first. An authenticated release manager approves the
exact plan ID. Revalidate permission, labels, candidate SHAs, and target SHA,
recreate the result from the manifest, independently test it, push only to a
lease-protected bot branch, and open a companion PR against the maintenance
branch. Never push the maintenance branch directly.

Outputs are an updateable GitHub Check, versioned `backport-plan.json`, linked
validated session analysis, bot-owned companion PR after approval, transition
timeline, and audit/metrics record. The manifest records target and source SHAs,
patch IDs, order, touched and conflict paths, approval, verification commands
and results, and correlation IDs.

#### Safety

Treat labels as candidate signals, not authorization. Keep Devin credential-free
and enforce allowlisted paths and commands independently. Recheck target SHA,
label state, and approver permission immediately before write; use a bot branch
and lease semantics. Reject missing prerequisites, duplicate patch IDs,
unexpected paths, test weakening, malformed output, and unverifiable results.
Normal maintenance-branch CI and human review remain mandatory because a clean
pick can still be semantically wrong.

#### Test strategy

Seed a maintenance branch where a helper was renamed but retains branch-specific
behavior. One source PR applies cleanly and a second implementation-plus-test PR
conflicts at that helper. The happy path produces an immutable manifest, one
Devin conflict session, approval, a bot PR, and green focused/affected tests.

Also test duplicate deliveries and equivalent plan keys, target changes before
push, malformed output and out-of-allowlist files, session/verification timeout,
unauthorized approval, label or permission revocation, already-applied and
partial batches, and the dangerous case where PR B applies textually but depends
on an unlabelled PR A. A clean cherry-pick with a missing behavioral dependency
must end `human_required` or `verification_failed`, never success.

#### Observability

Expose candidate collection, dry-run, session, approval, application,
verification, PR-open, and terminal stages. Show candidates total,
preflighted, clean, conflicted, already applied, and blocked. Measure plans,
candidates, conflicts, deterministic versus Devin-assisted batches, successful
and merged backport PRs, human intervention, p50/p95 automation and approval
latency separately, CI minutes, sessions and API-reported consumption, cost per
resolved conflict/merged backport, approval and repeat-use rates, edits after
Devin, false-ready rate, cancellations, and direct-target writes (target zero).
Estimated release-manager time saved must remain labeled as an assumption.

#### Demo and why Devin

Replay one label event for a two-PR batch, show the pinned manifest and dry-run,
show Devin preserve branch-specific behavior while resolving the renamed-helper
conflict, obtain release-manager approval, open the bot PR, verify the focused
test, and replay the event to show deduplication. Devin is core only in the hard
middle—semantic applicability, dependencies, divergent-branch conflict, and
test selection. Calling Devin for clean picks would add cost without unique
value.

## 5. Historical mapping to the take-home requirements

The mapping below explains why CI rescue remains credible as an expansion. The
current take-home maps the same requirements to a maintainer-authorized issue,
one Devin session, a linked PR, and independent required checks.

### Part 2 — Build an Event-Driven Automation

| Requirement | Selected implementation mapping |
|---|---|
| Be triggered by an event | Production accepts a completed failed GitHub workflow/check event resolving to one open PR and immutable SHA. A normalized saved payload provides deterministic local replay. |
| Programmatically initiate Devin sessions | After deterministic evidence collection, the controller calls `POST /v1/sessions` with a bounded prompt, structured-output schema, tags, selected knowledge, and an ACU limit. Publisher credentials remain in the controller. It persists the returned session ID before waiting. |
| Programmatically manage Devin sessions | An API adapter polls documented states with bounded backoff and deadlines, validates structured output, permits at most one supported evidence-rich follow-up, and terminates or records explicit timeout, cancellation, malformed-output, and API-error outcomes. |
| Produce observable technical output | The first output is an updateable GitHub Check with the pinned SHA, failed job, replay result, classification, evidence, exact command, uncertainty, session link, and next action. Authorized repair produces a patch or companion PR plus controller-owned verification evidence. |
| Remediate the seeded issue | The report-execution equality fixture supplies one realistic failing pytest node, an evidence-backed diagnosis, a production-only repair, and the same command failing before and passing after. |
| Remain safe and reviewable | Forks are read-only; authorization is bound to the same failure key and SHA; Devin holds no publisher credential; test and workflow edits are forbidden in the pilot; the controller independently verifies before publishing. |
| Run locally and repeatably | A Docker-based controller, durable SQLite run store, saved event/log/artifact fixtures, and secretless replay sandbox make the full loop reproducible without depending on a live webhook during every demo. |

### Part 3 — Incorporate Observability

| Requirement | Selected implementation mapping |
|---|---|
| Status of active and completed tasks | The run record exposes fixed active stages from `received` through replay, investigation, authorization, remediation, and verification, plus explicit terminal outcomes and timestamps. |
| Success and failure signals | Success requires controller-owned fail-before/pass-after evidence. Rejection, duplicate, unresolved diagnosis, replay failure, timeout, cancellation, malformed output, policy violation, stale SHA, verification failure, and publish failure remain distinct terminal reasons. |
| Throughput tracking | Counters cover received, accepted, deduplicated, reproduced, diagnosed, repair-offered, repair-invoked, verified, merged, blocked, unresolved, and failed runs. |
| Progress tracking | Progress is the current state, completed evidence items, elapsed time, and deadline. The system never invents a model completion percentage. |
| Latency and efficiency | Histograms report queue, evidence, session, verification, publishing, event-to-diagnosis, and event-to-green latency, with authorization wait separated. |
| Cost and resource use | Every run records session count, API-reported ACUs or cost when available, sandbox/CI minutes, and cost per useful diagnosis or verified rescue; unavailable values remain `unknown`. |
| Adoption and effectiveness | Maintainer usefulness feedback, repair invitations and invocations, acceptance, merge rate, repeat users, human rewrites, false positives, disablement, and false-green rate determine whether the company should keep the automation enabled. |

### Working-project deliverables

| Required build/deliverable | Future CI-adapter mapping |
|---|---|
| Docker-based local workflow and replayable event | A containerized controller accepts a normalized, signed saved `workflow_run.completed` payload and uses a secretless sandbox for the exact pytest replay. |
| Configured GitHub entry point | Production accepts a failed workflow/check event resolving to one open PR and immutable SHA; ambiguous events end `not_actionable`. |
| Session creation, polling, follow-up, and terminal handling | An API adapter creates the investigator and authorized remediation sessions, persists IDs before polling, bounds retries/deadlines, validates structured output, allows at most one supported follow-up, and stores explicit terminal reasons. |
| Structured logs and lightweight metrics | The durable run record, append-only transitions, correlation fields, counters, histograms, and pilot dashboard are defined in Section 4.1. |
| Successful Superset failed-check-to-green path | The report-execution equality fixture supplies one realistic failing unit node, an evidence-backed diagnosis, a production-only repair, and the same command failing before and passing after. |
| Useful output before write permission | The updateable diagnosis Check is always published before repair authorization; diagnosis-only is a valid terminal product. |
| Duplicate suppression | Delivery and failure keys ensure retries or equivalent work return the existing run and create no duplicate session, Check, or write. |
| Complete immutable correlation | Every session/run links repository, PR, head SHA, workflow run, failed job, fingerprint, replay command, delivery/failure keys, and artifacts. |
| Visible failure, timeout, cancellation, and malformed output | Fixed terminal enums and timestamps remain queryable in the Check/run record and survive restarts. |
| Trusted/explicitly authorized remediation | Repair requires same-repository trust plus authenticated maintainer authorization bound to the same key and SHA; policy and SHA are rechecked before write. |
| Untrusted forks remain read-only | Forks receive diagnosis only; no write token enters evidence collection, replay, or Devin sessions. |
| Deterministic safety gate and minimal change | The controller chooses the command, forbids test/workflow edits in the pilot, verifies collection and the production invariant, reruns the exact node, and publishes only the allowed minimal patch. |
| Metrics answer the definition of done | Report triage volume, reproduction rate, all five classifications, action acceptance/invocation, diagnosis/remediation latency, and API/sandbox cost per successful rescue. |
| Five-minute presentation covers what/how/why/adoption | Section 8 shows the pain, event/evidence/session/repair loop, why Devin is necessary, and the success gates for keeping it enabled. |

## 6. Recommended future CI-trigger scope

### Pilot scope

Build only the following vertical slice:

- one repository and one open PR;
- one failed Python unit-test job at one immutable head SHA;
- signed webhook validation plus a saved-event local replay;
- SQLite or equivalent durable run/transition storage;
- one exact-pytest-node evidence adapter;
- one bounded investigator session with strict structured output;
- one updateable read-only GitHub Check;
- explicit same-repository maintainer authorization;
- one bounded remediation session restricted to
  `superset/utils/report_execution.py`;
- controller-owned patch inspection, collection check, invariant probe, and the
  same exact pytest command;
- a narrow bot commit or companion PR, never merge or approval;
- structured logs and a minimal metrics endpoint/report.

Defer frontend, E2E, integration services, generated files, flaky-test
stabilization, arbitrary shell selection, fork writes, broad path edits,
multiple simultaneous failures, autonomous merging, and generic CI autofix.

### Why this wins

This slice demonstrates the FDE job end to end: discover customer-specific
friction, use repository evidence without overstating it, fit an existing
workflow, define a narrow trust boundary, integrate Devin programmatically,
make its reasoning indispensable, and prove the result independently. The
report-budget fixture is understandable in seconds, actually requires causal
reasoning, executes quickly, prevents the easy “edit the test” shortcut, and
produces visible red-to-green evidence. The GitHub Check provides value before
permissions expand, while acceptance, latency, and cost determine whether the
customer should keep the automation enabled.

## 7. These ideas as extensions of the selected platform

The issue-remediation build should establish reusable primitives rather than an
issue-specific monolith:

| Shared platform primitive | CI repair adapter | Rebase extension | Backport extension |
|---|---|---|---|
| Signed event normalization | Failed workflow/check | Conflict label/comment | Release label/merge event |
| Immutable work key | PR/head/job/fingerprint | PR/original head/target | Target/base/candidate manifest |
| Evidence sandbox | Logs, artifacts, exact test | Commit replay, conflict index | Patch IDs, dry-run, dependencies |
| Session broker | Diagnose, then repair | Two-sided intent resolution | Applicability/dependency/conflict resolution |
| Policy engine | Trusted repair paths | Read-only candidate; bot branch | Release-manager approval; bot branch |
| Proof runner | Before/after exact command | Graph/path/oracle/range-diff gates | Manifest reconstruction and maintenance tests |
| GitHub publisher | Diagnosis Check and optional repair | Rebase Proof and candidate PR | Plan Check and backport PR |
| Run store/telemetry | Failure classifications | Resolution outcomes | Plan/candidate outcomes |

**Extension 1: rebase conflicts.** Add conflict-event normalization, Git object
replay, two-sided intent schemas, protected behavior oracles, and bot candidate
branches. Reuse the same session broker, immutable state, authorization,
publisher, and metrics.

**Extension 2: release backports.** Add release-label mapping, candidate
manifests, patch-ID/dependency preflight, and release-manager approval. Route
clean batches deterministically and invoke the same reasoning service only for
semantic ambiguity. The rebase resolver's conflict proof becomes the core of
backport conflict handling.

This sequence turns three ideas into one **Engineering Change Rescue Platform**:
failed checks prove the event-to-reasoning-to-verification loop, rebases add
multi-version intent preservation, and backports add batch planning and release
policy.

## 8. Future CI-extension presentation and pilot gates

### Presentation sequence

| Time | Show | Point proved |
|---:|---|---|
| 0:00–0:35 | A trusted Superset PR with the report-budget equality regression and one red Python check. | The problem is real, bounded, and already in the engineer's GitHub workflow. |
| 0:35–1:05 | Replay the signed failed-run payload; show HMAC result, immutable SHA, delivery/failure keys, and duplicate suppression. | Event-driven, secure, idempotent control plane. |
| 1:05–1:45 | Show extracted JUnit/job evidence and the exact pytest node failing in the secretless sandbox. | Observed facts and deterministic reproduction precede model analysis. |
| 1:45–2:35 | Open the programmatically created investigator session and validated JSON linking `>` to the violated equality invariant; show the read-only Check. | Devin performs causal repository reasoning, while output remains reviewable and useful without write access. |
| 2:35–3:00 | Issue authenticated `/devin fix`; show trust, path, and unchanged-SHA checks. | Permission is explicit, narrow, and revocable. |
| 3:00–4:05 | Show the remediation patch restoring `>=`; controller rejects test changes, applies the patch cleanly, verifies unchanged collection and invariant probe, then reruns the same pytest node green. | Smallest reviewable change; Devin is not its own oracle. |
| 4:05–4:35 | Show the updated Check/run timeline, patch hash, session IDs, per-stage timings, sandbox minutes, and API-reported consumption or `unknown`. | Active/completed state, evidence, latency, and cost are visible. |
| 4:35–5:00 | Replay the duplicate, then show pre-recorded stale-SHA and test-weakening denials; close with pilot gates and platform extensions. | The memorable moment is not only a green test—it is a dangerous false green failing closed. |

Use a warm container and cached dependencies. If a live external session or CI
exceeds the slot, switch to an **explicitly labeled completed-run replay** with
stored API responses and artifacts; never present recorded output as live.

### Pilot success gates

Proceed from diagnosis-only to authorized repair only when all of these hold for
a representative sample:

1. **Safety:** zero privileged writes to untrusted forks; zero unauthorized,
   stale-SHA, out-of-policy, or direct-target writes; every attempted write has
   a complete immutable audit record.
2. **Truth:** every claimed repair has controller-owned fail-before and
   pass-after evidence for the same command at the same target SHA, unchanged
   test collection, and a passing independent invariant probe.
3. **Idempotency and reliability:** duplicate events create no duplicate
   sessions, Checks, commits, or cost; restart, malformed-output, timeout,
   cancellation, and stale-target tests all fail closed and remain queryable.
4. **Usefulness:** at least **80%** of a reviewed diagnosis sample is rated useful
   by maintainers; classification uncertainty and unresolved cases are visible,
   not forced into a confident answer.
5. **Adoption:** maintainers invoke offered repairs, accept the proposed action,
   and merge a meaningful share without broad manual rewrites; repeat use is
   measured separately from one-time demo use.
6. **Quality:** no observed false-green caused by test weakening and no observed
   semantic regression attributable to an accepted pilot repair. Any such event
   pauses write expansion for review.
7. **Performance:** p50 and p95 event-to-diagnosis and event-to-verified-repair
   are visible and acceptable to pilot users; human authorization wait is
   reported separately.
8. **Economics:** session count, API-reported ACUs/cost when available, and
   sandbox/CI minutes are visible for every outcome; cost per useful diagnosis
   and verified rescue meets a customer-agreed budget. Unknown API cost remains
   `unknown`, never fabricated.

If the gates fail, retain the read-only diagnosis product or stop the pilot;
do not compensate by weakening authorization or verification.
