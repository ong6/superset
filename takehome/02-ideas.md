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

# Ranked Automation Ideas

## Evaluation method

Six independent scouting agents evaluated Superset from security governance,
dependency maintenance, CI/test reliability, API contract quality, frontend
quality, and release operations perspectives. A synthesis agent then rescored
the candidates with this weighted rubric:

| Dimension | Weight |
|---|---:|
| Business value | 20% |
| Technical depth | 20% |
| Devin-as-core-primitive fit | 25% |
| Five-minute demo strength | 15% |
| Four-day feasibility | 20% |

Ideas were penalized when they were too broad, depended on nondeterministic
evidence, risked unsafe vulnerability framing, used Devin only as a summarizer,
or lacked a crisp before-and-after demo. Only ideas scoring at least 8.0 were
retained; overlapping ideas were consolidated.

## Recommendation

Build the **Migration Upgrade Contract Guardian** first.

It has the best VP-level story: schema migrations are high-risk, the evidence is
deterministic, the demo can show a clear failure-to-fix loop, and Devin performs
the engineering investigation and remediation after a conventional oracle
reproduces the failure.

The backup option is **Python Pin Drift Autopilot**. It is easier to implement
and operationally useful, but it is less technically deep than migration
rehearsal.

## Top ideas

### 1. Migration Upgrade Contract Guardian — 9.3

**Problem:** Superset's single-head Alembic check is necessary but insufficient:
a migration can have one valid head and still fail downgrade, re-upgrade,
idempotency, or data-preservation expectations on a real database.

**Event trigger:** `pull_request` opened, reopened, or synchronized when
`superset/migrations/versions` or migration-specific tests change; also a
completed migration-head/check workflow failure.

**Workflow:** A path-filtered PR event deduplicates by delivery ID and head SHA,
then runs deterministic preflight for changed migration revisions. Disposable
PostgreSQL and SQLite databases execute graph check, upgrade to the changed
revision, downgrade to parent, re-upgrade, and matching migration tests. A Devin
investigator receives the exact revision, graph, logs, snapshots, and failed
invariant. Only a reproducible failure creates an issue. A remediation session
then receives one revision and one invariant and makes the smallest fix plus a
focused test.

**Observable outputs:** GitHub Check matrix, structured JSON artifact, concise PR
comment with failing revision and command, deduplicated GitHub issue, and linked
remediation PR.

**Leadership metrics:** Migration PRs rehearsed, first-pass rate, failures by
invariant and database, detection latency, median repair time, repeat-failure
rate by release branch, Docker runtime, and migration coverage.

**Demo seed:** Add a fork-only migration with one valid Alembic head and
successful upgrade, but a downgrade that references a nonexistent table or
constraint. Show the existing graph check passing, the round-trip rehearsal
failing, Devin diagnosing and fixing the migration, and the same rehearsal
passing.

**Why Devin:** Deterministic database commands decide pass/fail, while Devin maps
the failure across Alembic code, migration conventions, and tests into a minimal
repair.

### 2. Python Pin Drift Autopilot — 9.3

**Problem:** A PR can update `pyproject.toml` or requirement inputs while leaving
generated requirement pins stale. Superset detects semantic drift, but automated
regeneration is narrowly scoped to upstream Dependabot pip PRs.

**Event trigger:** Failed `Check Python Dependencies` check run, or PR changes to
`pyproject.toml`, `requirements/*.in`, `superset-core/pyproject.toml`, or
`superset-extensions-cli/pyproject.toml`.

**Workflow:** A failed check or dependency-source diff creates one immutable-SHA
Devin session. Devin runs the repository lock-generation command, verifies
`requirements/development` remains a superset of base with matching shared
versions, summarizes material transitive changes, and classifies the result as
clean, stale generated files, ambiguous resolver change, or unsafe/untrusted
write. Trusted branches get a remediation session that regenerates the minimum
required files.

**Observable outputs:** GitHub Check summary with stale file set and pin delta,
structured resolver report, optional issue for ambiguous constraints, and a
remediation PR or commit containing regenerated requirements plus command
transcript.

**Leadership metrics:** Events received and deduplicated, session-start latency,
median detect-to-fix time, first-session remediation rate, stale files per event,
pins changed per event, recurrence rate, estimated manual minutes avoided, ACU,
and Docker runtime.

**Demo seed:** Raise one direct lower bound in `pyproject.toml` but leave
generated requirements stale. Show the dependency check failure, Devin's stale
pin classification, a minimal regenerated-files remediation, and the invariant
passing.

**Why Devin:** The deterministic checker finds drift; Devin closes the loop by
interpreting resolver deltas and preparing a trusted minimal fix.

### 3. Principal-Aware Authorization Regression Reproducer — 9.1

**Problem:** Superset authorization spans principals, capabilities, resources,
DAO filters, embedded/guest behavior, and Admin exceptions. Static checks can
flag intentional designs while missing real object-scope regressions.

**Event trigger:** PRs touching security manager, embedded or guest access,
dashboard/chart/dataset APIs, DAO filters, filters, or related tests.

**Workflow:** Security-sensitive PR events enter deterministic path/diff triage.
Devin receives policy excerpts, changed symbols, and known
principal/capability rows, then returns a candidate matrix: principal,
role/capability, resource, action, expected allow/deny, and reproduction command.
Only plausible rows start a Docker reproducer. Remediation starts only when an
unauthorized operation succeeds reproducibly; undisclosed vulnerabilities stay
private.

**Observable outputs:** Neutral GitHub Check/comment with role-resource-action
matrix, command, redacted evidence, disposition, and session links; private
advisory/private-fork issue for verified undisclosed vulnerabilities; public
issue only for a disclosed demo fixture or test gap; focused regression-test PR.

**Leadership metrics:** Candidate/reproduced/rejected counts, false-positive
rate, principal × capability × resource coverage, webhook-to-triage latency,
webhook-to-proof latency, fix latency, remediation acceptance, ACU, and retries.

**Demo seed:** Use a disclosed historical embedded guest-token boundary fix as a
safe fixture by reverting the guest-only deny that prevents an embedded guest
token from reaching a draft non-embedded dashboard outside its issued scope.

**Why Devin:** Devin's value is mapping a diff to the correct principal,
resource, and capability rule; runtime tests remain the oracle.

### 4. Semantic OpenAPI Breaking-Change Sentinel — 9.1

**Problem:** Superset's OpenAPI drift workflow proves the committed
`openapi.json` was regenerated; it does not prove the regenerated spec is
backward compatible for clients.

**Event trigger:** PRs touching API, schema, OpenAPI artifact/test files, or
contract-sensitive dependencies; failed OpenAPI drift checks enter diagnosis.

**Workflow:** A PR event regenerates normalized base/head specs and runs
deterministic semantic rules: removed operations, newly required parameters,
narrowed enum/type, incompatible response schema changes, unresolved component
references, and description/order-only suppression. Devin receives rule-coded
deltas and waiver policy, confirms impact and intent, deduplicates prior
findings, and launches compatibility remediation only for confirmed breaks or
explicit labels.

**Observable outputs:** Required GitHub Check with rule IDs and affected
operations, JSON/Markdown contract report, deduplicated issue per confirmed
break, expiring waiver record, and focused compatibility PR.

**Leadership metrics:** Breaking changes prevented, operations impacted,
additive-to-breaking ratio, false-positive/waiver rate, session success rate,
detection latency, median verified-remediation time, and recurring rule
offenders.

**Demo seed:** Remove or narrow a pinned field/reference from
`DashboardRestApi.get_list`, regenerate `openapi.json`, and show ordinary drift
passing while semantic compatibility fails.

**Why Devin:** Rules detect the delta; Devin explains client impact, distinguishes
additive changes from breaks, manages waiver context, and drafts a compatibility
fix.

### 5. Retry-Hidden E2E Flake Ledger — 9.0

**Problem:** Cypress and Playwright retries can make a workflow green after an
earlier failed attempt. A green workflow can hide first-pass instability, retry
cost, and recurring flakes.

**Event trigger:** Completion of Cypress or Playwright workflows, including
successful conclusions; optional immediate event when retry configuration
changes.

**Workflow:** The controller parses Cypress attempt lines and Playwright JSON
into normalized spec/test fingerprints. It updates a durable ledger and starts
Devin only when attempts exceed a threshold or recur. Devin receives the exact
fingerprint, artifacts, route/spec, and prior occurrences, then reproduces one
bounded spec. A repair session starts only when instability is reproduced.

**Observable outputs:** GitHub Check summary on otherwise-green commits, durable
fingerprint ledger, deduplicated flake issue with attempt history and artifact
links, and focused stabilization/migration PR with before/after repeated-run
evidence.

**Leadership metrics:** First-pass pass rate, hidden-green count, retry minutes,
top recurring specs, p50/p95 attempts-to-pass, flake budget by suite,
stabilized/migrated tests per month, and ACU per confirmed fingerprint.

**Demo seed:** Add machine-readable attempt summary output to
`scripts/cypress_run.py` and replay a spec that succeeds after an outer retry.

**Why Devin:** Deterministic parsing exposes hidden signal; Devin reproduces the
specific flaky path and proposes a focused wait/race fix or Cypress-to-Playwright
migration.

### 6. Semantic Accessibility Regression Responder — 9.0

**Problem:** Icon-only controls and visually labeled inputs can lack accessible
names or programmatic label associations even while JSX lint passes and visual
behavior looks correct.

**Event trigger:** PRs changing React/UI components or tests; manual seed event
for the Dataset List flow.

**Workflow:** A deterministic preflight on React/UI diffs selects candidates such
as icon-only actions, unbound labels, or new `getByTestId`-only test patterns.
Devin receives the component, existing tests, and expected role/name semantics,
then runs focused React Testing Library queries without modifying the target
branch. Only a reproduced semantic failure creates an issue. Remediation makes
the minimal `aria-label` or label-association fix and focused test update.

**Observable outputs:** GitHub Check summary, confirmed issue with role/name
query and expected accessible name, focused reproduction command, and linked
remediation PR with passing test evidence.

**Leadership metrics:** Confirmation rate, false-positive rate, semantic-rule
counts, median event-to-confirmation, median event-to-PR, remediation pass/merge
rate, accessible-query coverage trend, and ACU per confirmed issue.

**Demo seed:** Use Dataset List gaps such as an icon-only import action lacking
accessible text or a search input lacking explicit label association.

**Why Devin:** Devin converts syntactic candidates into user-semantic evidence
and minimal fixes while role/name queries remain deterministic.

### 7. Coordinated npm Compatibility Canary — 9.0

**Problem:** Superset's frontend has many direct/dev dependencies, overrides,
multiple npm roots, and compatibility-sensitive families. A dependency PR can
have a valid lockfile but still break build/runtime compatibility across roots.

**Event trigger:** PRs for allowlisted npm dependency updates; check failures
from npm dependency tree, frontend typecheck/test/build, websocket, or embedded
SDK checks.

**Workflow:** An allowlisted npm dependency PR creates one diagnostic Devin
session per affected npm root. Sessions run the smallest relevant install,
dependency-tree, typecheck, test, or build command. A coordinator aggregates
structured findings and starts exactly one resolver session only when diagnostics
agree on a bounded compatibility change.

**Observable outputs:** GitHub Check matrix by package root and command,
evidence-rich blocked-upgrade issue, and one resolver-owned remediation PR
changing dependency, lockfile, adapter, config, and focused tests as needed.

**Leadership metrics:** Dependency PR pass rate, compatibility failures by
package family/root, parallel session duration, ACU use, median
classification/fix time, ignored-upgrade backlog age, first-fix success, and
repeat-revert count.

**Demo seed:** Upgrade `simple-zstd` from 1.4.2 to 2.1.0 and reproduce the known
synchronous-to-asynchronous API incompatibility before deciding to re-pin or add
a bounded adapter.

**Why Devin:** Devin coordinates cross-root diagnostics and chooses a
compatibility strategy; deterministic builds and tests decide pass/fail.

## Rejected or merged concepts

- **Async task and realtime principal-isolation gate:** important but too broad
  for the first four-day build because it requires full Compose,
  Redis/WebSocket/task identity matrices, and careful vulnerability handling.
- **Direct-dependency provenance and remediation broker:** valuable, but the
  vulnerability/SCA framing risks premature claims; Python Pin Drift has cleaner
  deterministic signals.
- **Dependency Policy Drift Sentinel:** mostly static inventory, with Devin
  acting too much like a summarizer.
- **Failed-check fingerprint router and repair coordinator:** useful but generic
  compared with migration rehearsal or retry-hidden flake accounting.
- **Quarantine exit manager:** probabilistic repeated-run proof and stale
  maintainer intent weaken the demo.
- **Alembic Graph and Docker Rehearsal Gate:** merged into Migration Upgrade
  Contract Guardian.
- **REST Schema and Documentation Consistency Auditor:** merged conceptually into
  the OpenAPI breaking-change sentinel.
- **Bounded TypeScript and deprecated-pattern debt queue:** actionable, but more
  like backlog generation than an evidence-driven repair loop.
- **Bundle regression investigator:** promising later extension, but less
  deterministic for a four-day take-home.
- **Release Candidate Readiness Gate / Feature-Flag Lifecycle Governor:** broad
  governance checks with weaker five-minute proof.
- **Generic LLM reviewer:** rejected because it lacks a deterministic oracle and
  has high false-positive risk.
- **Public security issue filing from static patterns:** rejected because Superset
  findings require runtime proof and private handling for undisclosed issues.
