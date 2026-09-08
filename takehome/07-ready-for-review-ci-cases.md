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

# Future CI-Rescue Extension: Ready-for-Review Test Cases

## Document role

These cases remain the required safety boundary when failed pull-request CI is
added as an automatic trigger. They do not define the selected first
implementation. The current
[`devin-issue-autopilot`](../devin-issue-autopilot/README.md) slice starts only
after a maintainer applies `devin-fix` to an open issue; the stronger
[issue-remediation design](09-github-issue-remediation-implementation.md)
defines the future platform boundary.

## Product invariant

The controller may observe and record CI while a pull request is a draft, but
it must not create a Devin session until the pull request is open, out of
draft, and still points at the failed run's immutable head SHA.

Superset already includes `ready_for_review` in the pull-request triggers for
Python unit tests, Python dependency checks, OpenAPI drift, migration conflict
checks, and E2E. A draft failure therefore remains permanently ineligible.
Moving the pull request to ready for review starts fresh CI; only a failure
from that review-ready execution can start Devin.

The gate uses both the uploaded source `pull_request` event and a live provider
lookup:

```text
eligible =
  workflow conclusion == failure
  and source event == pull_request
  and source pull_request.draft == false
  and live pull request.state == open
  and live pull_request.draft == false
  and source head SHA == live head SHA
```

The first `Python-Unit` adapter can read the source state from its uploaded
`Event File` artifact. Any later workflow adapter must capture equivalent
source-event metadata; a live lookup alone cannot prove that CI started after
the PR left draft.

The source-event check closes a race where draft CI finishes, the pull request
is marked ready, and the old `workflow_run` webhook is processed afterward.
The live-state check closes the opposite race where an eligible run finishes
but the author converts the pull request back to draft before processing.

No sandbox, Devin API call, PR comment, Check, or write-capable token is
created before this gate passes. Suppressed events may produce an internal
run record and metric.

## Lifecycle acceptance matrix

Every case asserts the count of Devin session-creation calls, not just the
visible GitHub output.

| ID | Event sequence | Expected controller behavior | Devin sessions |
|---|---|---|---:|
| R1 | Open a draft PR with a deterministic regression; CI fails. | Record `suppressed_draft_origin`; publish nothing. | 0 |
| R2 | After R1, mark the same PR ready for review; the fresh `ready_for_review` CI run fails at the same SHA. | Ignore the old draft run, accept the fresh run, and publish one investigation Check. | 1 investigator |
| R3 | Open a non-draft PR; its first CI run fails. | Accept the failed run immediately after preflight. | 1 investigator |
| R4 | Open or mark a PR ready; CI passes. | Record no actionable failure and publish nothing. | 0 |
| R5 | CI fails while ready, but the PR becomes draft before the worker claims the run. | Record `suppressed_current_draft`; do not start work. | 0 |
| R6 | GitHub retries the delivery and the controller receives concurrent copies of one eligible failure. | Atomically claim one failure key and upsert one Check. | 1 investigator |
| R7 | CI fails for SHA A, then the author pushes SHA B before processing. | Record SHA A as `stale_target`; wait for CI on SHA B. If SHA B fails while ready, create one new run. | 0 for A; 1 for B |
| R8 | The PR becomes draft after an investigator started while it was eligible. | Cancel bounded work where supported, suppress follow-up/remediation, and publish no repair. | At most 1 investigator; 0 remediators |
| R9 | A closed PR is reopened as non-draft and fresh CI fails. | Accept only the fresh failure mapped to the reopened head SHA. | 1 investigator |
| R10 | A ready-for-review fork PR fails. | Permit a credential-free, read-only investigation; never create a writer or expose repository secrets. | 1 investigator; 0 remediators |

For R2, the important assertion is that the draft-originated run never becomes
eligible retroactively. The session must correlate to the fresh workflow run
created by `ready_for_review`.

## Recommended demo choreography

Use one seeded regression to demonstrate the product boundary and repair loop:

1. Open the seeded PR as a draft and let CI fail.
2. Show the internal suppressed run and zero Devin API calls.
3. Mark the PR ready for review.
4. Let the fresh review-ready CI run fail and show exactly one investigator.
5. Authorize the bounded repair and show the same focused command turn green.
6. Replay the webhook and show no duplicate session, Check, or patch.

This proves the adoption behavior before showing broader failure coverage:
Devin waits until the author explicitly signals that the change is ready for
review.

## Showcase PR fixtures

### S1. Change-caused Python boundary regression

This is the primary five-minute fixture because it is fast, deterministic, and
has an unambiguous production-only repair.

Seed:

```diff
-    if sum(reserves) >= budget:
+    if sum(reserves) > budget:
```

Expected failed command:

```bash
pytest -q 'tests/unit_tests/utils/test_report_execution.py::test_report_execution_config_rejects_invalid_startup_values[overrides2-must total less]'
```

Expected classification is `change_caused`. The accepted repair restores
`>=`; test edits, skips, or workflow changes are rejected.

### S2. Stale OpenAPI generated artifact

Change `dashboard_title_description` in `superset/dashboards/schemas.py` but
intentionally omit the generated
`docs/static/resources/openapi.json` update.

Expected failing check is `Check OpenAPI spec drift`. The evidence includes the
repository-provided regeneration command:

```bash
SUPERSET__SQLALCHEMY_DATABASE_URI='sqlite:///:memory:' \
  FLASK_APP='superset.app:create_app()' \
  superset update-api-docs
git diff --exit-code -- docs/static/resources/openapi.json
```

Expected classification is `generated_drift`. The repair retains the
intentional schema change and updates only its generated artifact.

### S3. Broken migration downgrade order

In
`2026-05-08_12-10_3a8e6f2c1b95_add_deleted_at_to_tables.py`, seed a downgrade
that drops `deleted_at` before dropping `ix_tables_deleted_at`.

Expected failing command:

```bash
pytest -q tests/unit_tests/migrations/test_add_deleted_at_to_tables.py
```

Expected classification is `change_caused`. The repair restores the safe
index-then-column downgrade order, and the upgrade/downgrade/idempotency tests
provide independent acceptance.

### S4. Python dependency pin drift

As a slower generated-drift variant, tighten the `apispec` bound in
`requirements/base.in` from `<6.7.0` to `<6.6.1` without regenerating pinned
requirements.

Expected failing check is `Check python dependencies`. Verification uses:

```bash
./scripts/uv-pip-compile.sh
git diff --exit-code -- \
  requirements/base.txt \
  requirements/development.txt \
  requirements/translations.txt
```

Expected classification is `generated_drift`. This fixture is better for an
extended demo because dependency resolution is slower and depends on package
index availability.

## Controller-only safety fixtures

Some important classifications should use saved events, logs, and artifacts
rather than deliberately harmful live PRs:

| Fixture | Evidence | Expected result |
|---|---|---|
| Passing retry after an initial failure | Same SHA and fingerprint fails, then passes once. | `unresolved` unless recurrence evidence supports `likely_flaky`; no repair. |
| Runner or service outage | Log shows network, quota, runner, or service failure without a code-linked assertion. | `infrastructure`; recommend rerun; no remediator. |
| Malformed Devin output | Invalid schema, unknown outcome, or false changed-path claim. | `malformed_output`; fail closed. |
| Verification rejects a false green | Proposed patch weakens or removes a test. | `policy_rejected` or `verification_failed`; no publish. |

These cases demonstrate that the product does not equate every red check with a
code change and does not trust Devin's self-reported success.
