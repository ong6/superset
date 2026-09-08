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

# Technical Specification: Failing Check Repair for Apache Superset

## 1. Executive technical decision

Build **PR CI Rescue** as a narrow, event-driven automation that turns one
failed pull-request check into:

1. validated, deduplicated, immutable work;
2. deterministic failure reproduction outside Devin;
3. a bounded read-only Devin investigation;
4. a visible GitHub Check diagnosis;
5. an explicitly authorized repair for trusted branches only;
6. independent verification before any bot-authored patch is published; and
7. telemetry that records safety, usefulness, latency, throughput, and
   API-reported cost or explicit cost-unknowns.

The first product PR should implement only one Superset path: a trusted
same-repository pull request, one failed Python unit check, one immutable head
SHA, and one exact pytest node. That constraint makes the VP Engineering
review concrete: the system is not an unfalsifiable “AI fixes CI” promise; it
is a control plane with an auditable state machine and deterministic
fail-before/pass-after proof.

## 2. Scope, non-goals, and trust progression

### In scope for the pilot

| Area | Decision |
|---|---|
| Repository | One configured Superset repository and one GitHub App installation. |
| Event | Failed GitHub `workflow_run` from Superset's `Python-Unit` workflow, mapped to one open pull request; check-suite/check-run support can follow later. |
| CI surface | Python unit-test failures with an exact pytest node from logs or JUnit. |
| Branch trust | Same-repository trusted branches only for remediation. Forks are diagnosis-only. |
| Repair size | One minimal production-code patch, policy-checked by changed paths. |
| Verification | Same exact pytest node, unchanged test collection, production invariant probe, and optional focused regression group. |
| Output | One updateable `Python Unit Test Results`-adjacent GitHub Check per failure key, plus optional bot branch or companion repair PR. |
| Observability | Durable run timeline, metrics endpoint/report, logs, traces, alerts, adoption funnel, and cost accounting. |

### Non-goals

- no autonomous merge, approval, or branch-protection bypass;
- no repair of untrusted forks;
- no generic shell-command execution selected by Devin or logs;
- no broad autofix of multiple unrelated failures;
- no claim that a passing rerun proves flakiness;
- no test/workflow/dependency edits in the first repair policy;
- no use of Devin's self-reported tests as the success oracle; and
- no fabricated ACU, cost, ROI, or completion percentage when the API or
  pilot evidence does not expose it.

### Trust progression

| Stage | Capability | Exit gate |
|---|---|---|
| 0. Replay-only | Validate events, reproduce saved failures, emit local reports. | Fixtures cover duplicate, stale, malformed, timeout, unauthorized write, and false-green cases. |
| 1. Diagnosis-only | Publish read-only Checks on real failed PRs. | Maintainers rate at least 80% of sampled diagnoses useful; zero duplicate spam. |
| 2. Human-authorized repair | Accept `/devin fix` or a protected label for trusted same-repo branches. | Every published repair has controller-owned fail-before/pass-after proof and path-policy compliance. |
| 3. Broader CI adapters | Add frontend, pre-commit, generated-file, or migration adapters. | Each adapter has its own deterministic replay command and false-green tests. |
| 4. Platform extensions | Add rebase conflict and release cherry-pick adapters. | The shared policy, proof, and observability gates remain unchanged. |

## 3. End-to-end architecture

```text
GitHub failed check event
  -> FastAPI webhook
  -> EventValidator
  -> PullRequestResolver
  -> IdempotencyStore
  -> EvidenceCollector
  -> ReplaySandbox
  -> DevinSessionBroker(investigator)
  -> StructuredOutputValidator
  -> GitHubCheckPublisher(read-only diagnosis)
  -> AuthorizationGate
  -> DevinSessionBroker(remediator)
  -> PatchPolicyEngine
  -> VerificationSandbox
  -> GitHubPublisher(bot branch / companion PR)
  -> Metrics, logs, traces, dashboard, alerts
```

### Component ownership

| Component | Owns | Must not own |
|---|---|---|
| Webhook/API | HTTP validation, HMAC, timestamp, payload schema, delivery ID. | Repository trust decisions by payload URL alone. |
| Resolver | Repository ID, PR number, head SHA, fork/trust state, workflow/job mapping. | Guessing if the event maps to multiple PRs. |
| Idempotency store | Atomic delivery and failure-key claims. | In-memory duplicate suppression. |
| Evidence collector | Logs, JUnit, annotations, workflow file, changed paths, artifact hashes. | Unbounded log ingestion or secret-bearing raw dumps into Devin. |
| Replay sandbox | Clean checkout, pinned command, resource limits, normalized output. | Commands suggested by model output or untrusted logs. |
| Session broker | Devin API creation, tags, polling, deadlines, structured-output retrieval. | Treating Devin output as authorization or proof. |
| Policy engine | Actor permission, fork policy, allowed paths, stale-SHA checks, write scope. | Letting a session broaden its own permissions. |
| Publisher | One Check per failure key; optional controlled bot branch/PR. | Duplicate comments or direct merges. |
| Verification | Apply patch in fresh checkout, derive diff from Git, rerun exact command. | Trusting self-reported tests. |
| Observability | State, metrics, logs, traces, cost/adoption reporting. | Model-generated progress percentages. |

## 4. Event contract, validation, and immutable correlation

### Accepted event shape

The production entry point accepts GitHub `workflow_run.completed` payloads
from `Python-Unit` only when the conclusion is failure-like and the event maps
to exactly one open, non-draft pull request. The uploaded source
`pull_request` event must also show `draft: false`; a draft-originated run never
becomes eligible because the pull request was marked ready before webhook
processing. Later adapters can add `check_suite` or `check_run` inputs after
they pass the same validation and proof gates. Local demos use a saved
normalized event with the same internal fields.

```json
{
  "provider": "github",
  "repository_id": 123456789,
  "repository_full_name": "ong6/superset",
  "installation_id": 11111111,
  "event_name": "workflow_run",
  "event_action": "completed",
  "delivery_id": "2c1d9f90-0000-4000-8000-000000000001",
  "workflow_run_id": 9876543210,
  "workflow_name": "Python-Unit",
  "workflow_conclusion": "failure",
  "pull_request_number": 42,
  "source_pull_request_action": "ready_for_review",
  "source_pull_request_draft": false,
  "live_pull_request_draft": false,
  "head_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "head_ref": "devin/report-budget-regression",
  "base_ref": "master",
  "is_fork": false,
  "sender_login": "maintainer"
}
```

### Validation gates

Reject before any sandbox, Devin, or GitHub publishing side effect when:

- signature, timestamp, content type, payload size, or event/action is invalid;
- repository ID is not allowlisted for the installation;
- conclusion is not actionable;
- the event maps to zero, multiple, closed, or stale PRs;
- the source CI event began while the pull request was a draft;
- the live pull request is a draft when the run is claimed;
- the event head SHA does not match the provider-resolved PR head;
- required workflow/job/artifact fields are absent; or
- the delivery or failure key is already terminal and up to date.

### Idempotency keys

```text
delivery_key = github:{repository_id}:{delivery_id}
failure_key  = github:{repository_id}:pr:{number}:sha:{head_sha}:job:{job_logical_key}:fp:{fingerprint}
```

The delivery key absorbs provider retries. The failure key absorbs equivalent
events, workflow reruns, restarts, and repeated processing. `job_logical_key`
is the stable workflow/job/matrix identity, not the provider's per-run job ID.
A new head SHA creates a new failure key because evidence and repair target
changed.

### Atomic claim pseudocode

```text
BEGIN;
INSERT INTO deliveries(delivery_key, received_at) VALUES (?, ?)
  ON CONFLICT DO NOTHING;

IF delivery existed:
  COMMIT;
  return existing run/check by delivery_key;

INSERT INTO repair_runs(failure_key, state, head_sha, policy_version)
  VALUES (?, 'received', ?, ?)
  ON CONFLICT DO NOTHING
  RETURNING run_id;

IF no run_id returned:
  SELECT run_id, state FROM repair_runs WHERE failure_key = ? FOR UPDATE;
  UPDATE deliveries SET run_id = existing.run_id WHERE delivery_key = ?;
  COMMIT;
  return existing run/check by failure_key;

INSERT INTO run_transitions(run_id, from_state, to_state, reason, occurred_at)
  VALUES (?, NULL, 'received', NULL, ?);
UPDATE deliveries SET run_id = new.run_id WHERE delivery_key = ?;
COMMIT;
```

The next worker moves `received -> validated` with compare-and-set on expected
state and version. Late workers cannot append duplicate transitions or
overwrite a newer terminal state.

## 5. Durable data model

### Core tables

| Table | Purpose | Key fields |
|---|---|---|
| `deliveries` | Provider delivery dedupe and replay audit. | `delivery_key`, `provider`, `event_name`, `received_at`, `payload_hash`, `run_id`. |
| `repair_runs` | One logical CI rescue attempt per failure key. | `run_id`, `failure_key`, `state`, `terminal_reason`, `repository_id`, `pr_number`, `head_sha`, `workflow_run_id`, `job_logical_key`, `fingerprint`, `policy_version`, milestone timestamps, `created_at`, `updated_at`. |
| `run_transitions` | Append-only audit timeline. | `run_id`, `sequence`, `from_state`, `to_state`, `reason`, `actor`, `occurred_at`, `duration_ms`, `metadata_json`. |
| `evidence_artifacts` | Bounded, hashed evidence references. | `artifact_id`, `run_id`, `kind`, `source_url`, `sha256`, `redacted_ref`, `normalized_ref`, `bytes`, `expires_at`. |
| `replay_attempts` | Deterministic command outcomes. | `attempt_id`, `run_id`, `role`, `checkout_sha`, `argv_json`, `exit_code`, `duration_ms`, `stdout_ref`, `stderr_ref`, `collection_hash`. |
| `devin_sessions` | Session correlation and recovery. | `devin_session_id`, `run_id`, `role`, `request_hash`, `status`, `started_at`, `deadline_at`, `completed_at`, `structured_output_ref`, `usage_json`. |
| `authorizations` | Explicit write authorization. | `authorization_id`, `run_id`, `failure_key`, `head_sha`, `actor`, `method`, `scope`, `created_at`, `expires_at`. |
| `patches` | Derived, policy-checked repair artifacts. | `patch_id`, `run_id`, `source_session_id`, `diff_sha256`, `changed_paths_json`, `policy_result`, `bot_branch`, `pr_url`. |
| `check_outputs` | Stable publisher upsert state. | `run_id`, `check_run_id`, `external_key`, `status`, `conclusion`, `last_payload_hash`, `updated_at`. |

### State machine

```text
received
  -> validated
  -> authorized_read
  -> evidence_collecting
  -> replaying_failure
  -> investigation_session_running
  -> diagnosis_ready
  -> diagnosis_published
  -> awaiting_repair_authorization
       -> diagnosis_only
       -> authorization_expired
       -> repair_authorized
       -> remediation_session_running
       -> patch_proposed
       -> policy_checking
       -> verifying
       -> publishing_repair
       -> succeeded
```

Terminal states:

| State | Meaning |
|---|---|
| `succeeded` | Authorized repair was policy-accepted, verified, and published. |
| `diagnosis_only` | Read-only diagnosis completed and no repair was requested because policy, fork trust, or maintainer choice stopped there. |
| `authorization_expired` | Diagnosis stayed available but the repair authorization window closed. |
| `duplicate` | Existing delivery or failure key owns the work. |
| `not_actionable` | Event is valid but outside scope. |
| `validation_failed` | Event/auth/schema failed. |
| `authorization_failed` | Actor, repo, branch, fork, or scope cannot write. |
| `insufficient_replay_evidence` | No exact deterministic command can be selected. |
| `replay_failed_infra` | Sandbox cannot execute for environment reasons. |
| `unresolved` | Evidence cannot support a confident classification. |
| `devin_api_failed` | Session create/poll/message/terminate failed beyond retry budget. |
| `timed_out` | Wall-clock or ACU budget exhausted. |
| `malformed_output` | Devin output fails schema or cross-check validation. |
| `stale_target` | PR head changed before repair, verification, or publish. |
| `policy_rejected` | Patch violates path, credential, symlink, workflow, or scope rules. |
| `verification_failed` | Clean-room acceptance command or invariant probe failed. |
| `publish_failed` | Check, branch, or companion PR publication failed. |
| `cancelled` | Human or policy kill switch stopped the run. |

Progress is represented by current state plus completed evidence items,
elapsed time, and deadline. The system never reports a model completion
percentage.

## 6. Evidence adapter and clean sandbox

### Evidence bundle

For Python unit failures, collect:

- workflow run, check run, and failed job metadata;
- JUnit XML and GitHub annotations when available;
- bounded log excerpts around the first actionable pytest failure;
- the workflow file at the pinned base context;
- PR diff and changed paths at the immutable head SHA;
- `AGENTS.md`, relevant `.devin/skills`, and nearby tests/source files;
- prior normalized fingerprint occurrences when available; and
- original CI command plus focused replay command.

Normalize timestamps, worker IDs, temp directories, random ports, and absolute
checkout paths before fingerprinting. Keep original artifacts hashed and
referenced, but send only bounded, redacted excerpts to Devin.

### Replay command selection

The controller uses deterministic adapters before invoking Devin:

| Evidence | Replay argv |
|---|---|
| Exact pytest node in JUnit or log | `["pytest", "-q", "<nodeid>"]` |
| Test file plus assertion name | `["pytest", "-q", "<file>::<test>"]` |
| File-level failure only | `["pytest", "-q", "<file>"]`, then mark lower confidence |
| No reliable node/file | terminal `insufficient_replay_evidence` |

The adapter must preserve both the original CI command and focused replay
command. A focused command narrows work; it does not rewrite history about
what CI ran.

The adapter never interpolates a node ID into a shell string. It accepts only
canonical paths under `tests/`, rejects metacharacters, resolves the path inside
the checkout, confirms the target with `pytest --collect-only -q`, and stores
the final command as an argv array.

## 7. Devin API session protocol

### Investigator session

Create exactly one read-only investigator per failure key after evidence is
collected and replayed. The documented API dependency is session creation via
`POST /v1/sessions`, documented status polling, active-session termination via
`DELETE /v1/sessions/{session_id}`, and supported enterprise follow-up
messaging where enabled. The request shape below is the target adapter contract;
implementation must validate optional fields against the active Devin API
before relying on them:

```json
{
  "title": "CI Rescue investigator: ong6/superset#42",
  "prompt": "<bounded prompt with evidence refs and acceptance taxonomy>",
  "idempotent": true,
  "knowledge_ids": ["<repo-skill-or-knowledge-id-if-configured>"],
  "max_acu_limit": 3.0,
  "structured_output_schema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "schema_version": { "type": "string", "const": "ci-rescue-investigator/v1" },
      "classification": {
        "type": "string",
        "enum": ["change_caused", "likely_flaky", "infrastructure", "generated_drift", "unresolved"]
      },
      "summary": { "type": "string", "maxLength": 600 },
      "evidence_refs": { "type": "array", "items": { "type": "string" }, "maxItems": 8 },
      "causal_files": { "type": "array", "items": { "type": "string" }, "maxItems": 8 },
      "repair_recommended": { "type": "boolean" },
      "allowed_paths": { "type": "array", "items": { "type": "string" }, "maxItems": 8 },
      "verification_commands": { "type": "array", "items": { "type": "string" }, "maxItems": 4 },
      "confidence": { "type": "string", "enum": ["low", "medium", "high"] },
      "unknowns": { "type": "array", "items": { "type": "string" }, "maxItems": 8 }
    },
    "required": [
      "schema_version",
      "classification",
      "summary",
      "evidence_refs",
      "causal_files",
      "repair_recommended",
      "allowed_paths",
      "verification_commands",
      "confidence",
      "unknowns"
    ]
  },
  "tags": [
    "ci-rescue",
    "role:investigator",
    "repo:ong6/superset",
    "workflow:python-unit",
    "schema:ci-rescue-investigator-v1"
  ],
  "unlisted": true
}
```

If optional fields such as `idempotent`, `max_acu_limit`, `knowledge_ids`,
usage, or cost are unavailable in the chosen deployment tier, the controller
still enforces its own failure-key idempotency and wall-clock budget, omits the
unsupported field, and records the missing API data as `unknown`.

### Investigator prompt contract

The prompt must state:

- the repository, PR number, immutable head SHA, base SHA, job, and command;
- the exact evidence refs and bounded excerpts;
- allowed classifications and evidence requirements;
- prohibited actions: no edits, no tests beyond the controller command, no
  credential discovery, no shell commands copied from logs;
- output must cite evidence refs, not raw speculation;
- a single green rerun is not enough to call a failure flaky; and
- the controller is the only verifier and authorizer.

### Remediator session

The remediator is created only after:

1. diagnosis is published;
2. the PR is same-repository and trusted;
3. a maintainer authorization is bound to the exact failure key and head SHA;
4. the head SHA is re-resolved and unchanged; and
5. policy has computed a narrow allowed-path set.

The remediator receives only the accepted plan, pinned source files, failing
test context, allowed paths, and prohibited paths. It does not receive a
publisher credential.

```json
{
  "title": "CI Rescue repair: ong6/superset#42",
  "prompt": "<bounded repair prompt>",
  "idempotent": true,
  "max_acu_limit": 4.0,
  "structured_output_schema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "schema_version": { "type": "string", "const": "ci-rescue-remediator/v1" },
      "outcome": { "type": "string", "enum": ["patch_proposed", "no_change", "blocked", "failed"] },
      "summary": { "type": "string", "maxLength": 600 },
      "changed_paths": { "type": "array", "items": { "type": "string" }, "maxItems": 8 },
      "patch_ref": { "type": "string" },
      "verification_commands": { "type": "array", "items": { "type": "string" }, "maxItems": 4 },
      "risk_notes": { "type": "array", "items": { "type": "string" }, "maxItems": 8 }
    },
    "required": [
      "schema_version",
      "outcome",
      "summary",
      "changed_paths",
      "patch_ref",
      "verification_commands",
      "risk_notes"
    ]
  },
  "tags": [
    "ci-rescue",
    "role:remediator",
    "repo:ong6/superset",
    "workflow:python-unit",
    "schema:ci-rescue-remediator-v1"
  ],
  "unlisted": true
}
```

### Session status handling

| Status | Controller behavior |
|---|---|
| `new`, `claimed`, `running`, `resuming` | Continue polling until deadline with bounded backoff and jitter. |
| `suspended` | If a supported follow-up is configured and one has not been used, send one evidence-rich message; otherwise mark non-success and terminate if policy requires. |
| `exit` | Fetch and validate structured output; success is possible only after schema validation and controller cross-checks. |
| `error` | Terminal `devin_api_failed` or role-specific failure. |
| Unknown status | Terminal non-success unless a documented API update explicitly adds handling. |

The session ID is persisted before polling. If the controller crashes after
creation, a sweeper resumes polling the persisted session instead of calling
`POST /v1/sessions` again. On stale SHA, cancellation, or timeout, use
`DELETE /v1/sessions/{session_id}` for active sessions when applicable, and
record whether termination succeeded.

## 8. Authorization, policy, and publishing

### Repair authorization

Accepted authorization methods:

- `/devin fix <run_id>` from a repository maintainer; or
- applying a protected label whose event payload includes the same PR and
  current head SHA.

Authorization expires, is scoped to one failure key, and is invalidated by a
head-SHA change. It never authorizes a fork write, merge, approval, workflow
edit, secret access, or a second unrelated repair.

### Patch policy for the first product slice

Allow only:

```text
superset/utils/report_execution.py
```

Reject:

- tests, GitHub workflows, dependency manifests, generated files, config, or
  security-policy files;
- symlinks, submodules, path traversal, or files outside the checkout root;
- patches that remove the failing assertion path rather than repair
  production behavior;
- patches that alter command selection or verification logic; and
- patches produced against any SHA other than the pinned head.

### GitHub Check output

Use one stable Check per failure key.

```markdown
## CI Rescue diagnosis

State: diagnosis_published
Classification: change_caused
PR: #42
Head SHA: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
Failed job: Python-Unit / unit-tests (matrix python-version=current)
Replay: pytest -q 'tests/unit_tests/utils/test_report_execution.py::test_report_execution_config_rejects_invalid_startup_values[overrides2-must total less]'
Replay result: failed before repair

Evidence:
- JUnit shows equality-boundary config should raise ValueError.
- Replay reproduces the failure at the immutable head SHA.
- The changed comparator allows reserves_total == budget.

Next action:
- Maintainer may authorize `/devin fix <run_id>`.

Uncertainty:
- Only this exact node has been reproduced in the pilot adapter.
```

After repair verification, update the same Check with patch hash, bot branch or
companion PR URL, verification command, elapsed times, session IDs, sandbox
minutes, and API-reported ACU/cost or `unknown`.

## 9. Independent verification and false-green prevention

Verification happens in a fresh checkout rooted at the pinned head SHA. The
controller applies the proposed patch, derives changed paths from Git, checks
policy, and runs commands it selected before Devin was invoked.

Required verification for PR #1's documentation/demo proof uses the existing
executable equality-boundary node. The product PR may switch this to the named
test in Section 10 after it is added:

```bash
pytest -q 'tests/unit_tests/utils/test_report_execution.py::test_report_execution_config_rejects_invalid_startup_values[overrides2-must total less]'
```

Additional guards:

```bash
pytest --collect-only -q tests/unit_tests/utils/test_report_execution.py
python - <<'PY'
from superset.utils.report_execution import validate_report_execution_config

config = {
    "ALERT_REPORTS_WORKING_TIME_OUT_KILL": True,
    "ALERT_REPORTS_EXECUTION_BUDGET_SECONDS": 210,
    "ALERT_REPORTS_EXECUTION_CAPTURE_RESERVE_SECONDS": 60,
    "ALERT_REPORTS_EXECUTION_DELIVERY_RESERVE_SECONDS": 120,
    "ALERT_REPORTS_EXECUTION_CLEANUP_RESERVE_SECONDS": 30,
    "ALERT_REPORTS_EXECUTION_HARD_TIMEOUT_GRACE_SECONDS": 30,
    "ALERT_REPORTS_WORKING_SOFT_TIME_OUT_LAG": 1,
    "ALERT_REPORTS_WORKING_TIME_OUT_LAG": 10,
}

try:
    validate_report_execution_config(config)
except ValueError as ex:
    assert "must total less" in str(ex)
else:
    raise AssertionError("equal reserves must be rejected")
PY
```

The `--collect-only` hash prevents false greens caused by deleting or renaming
the test. The invariant probe prevents false greens caused by weakening the
assertion while keeping the test name. The policy engine prevents false greens
from test-only edits in the first slice.

## 10. Deterministic test case design for the next product PR

PR #1 remains documentation-only. The product PR should add the explicit unit
test below and keep the existing parameterized invalid-config coverage intact
or remove only the equivalent anonymous equality case if maintainers prefer
one source of coverage.

```python
def test_report_execution_config_rejects_reserves_equal_to_budget() -> None:
    with pytest.raises(ValueError, match="must total less"):
        validate_report_execution_config(
            _report_config(
                ALERT_REPORTS_EXECUTION_BUDGET_SECONDS=210,
                ALERT_REPORTS_EXECUTION_CAPTURE_RESERVE_SECONDS=60,
                ALERT_REPORTS_EXECUTION_DELIVERY_RESERVE_SECONDS=120,
                ALERT_REPORTS_EXECUTION_CLEANUP_RESERVE_SECONDS=30,
            )
        )
```

### Seeded regression for the demo

The demo seed is a local or separate-branch mutation, not a change in this
documentation PR:

```diff
-    if sum(reserves) >= budget:
+    if sum(reserves) > budget:
         raise ValueError(
             "Report execution phase reserves must total less than the execution budget"
         )
```

Expected sequence:

```bash
# 1. Prove baseline is green with the executable node in PR #1.
pytest -q 'tests/unit_tests/utils/test_report_execution.py::test_report_execution_config_rejects_invalid_startup_values[overrides2-must total less]'

# 2. Seed the regression locally.
python - <<'PY'
from pathlib import Path

path = Path("superset/utils/report_execution.py")
text = path.read_text()
old = "    if sum(reserves) >= budget:\\n"
new = "    if sum(reserves) > budget:\\n"
if old not in text:
    raise SystemExit("expected comparator not found")
path.write_text(text.replace(old, new, 1))
PY

# 3. Prove the exact node fails.
pytest -q 'tests/unit_tests/utils/test_report_execution.py::test_report_execution_config_rejects_invalid_startup_values[overrides2-must total less]'

# 4. Restore without destructive Git commands.
python - <<'PY'
from pathlib import Path

path = Path("superset/utils/report_execution.py")
text = path.read_text()
old = "    if sum(reserves) > budget:\\n"
new = "    if sum(reserves) >= budget:\\n"
if old not in text:
    raise SystemExit("seeded comparator not found")
path.write_text(text.replace(old, new, 1))
PY

# 5. Prove repair is green.
pytest -q 'tests/unit_tests/utils/test_report_execution.py::test_report_execution_config_rejects_invalid_startup_values[overrides2-must total less]'
```

### Fixture records to implement

The next PR should include replayable, credential-free JSON fixtures:

| Fixture | Contents |
|---|---|
| `normalized_failed_event.json` | Repository ID, delivery ID, workflow run, PR, immutable SHA, job, conclusion, same-repo trust, artifact IDs. |
| `evidence_bundle.json` | Redacted log/JUnit refs, artifact SHA-256 hashes, exact pytest node, changed paths, fingerprint. |
| `investigator_output_change_caused.json` | Valid structured output linking `>` to the equality-boundary invariant. |
| `run_timeline_verified.json` | Full state transitions, session IDs, authorization, patch hash, verification result, timings, duplicate handling, and metrics. |
| `malformed_output.json` | Invalid or unsupported output used to prove fail-closed behavior. |
| `policy_rejected_test_edit.json` | Patch metadata showing a test edit that would make pytest green but must be rejected. |

## 11. Observability design

### Structured logs

Every log line includes:

| Field | Example |
|---|---|
| `service` | `ci-rescue-controller` |
| `env` | `pilot` |
| `run_id` | `run_01J...` |
| `failure_key` | `github:123:pr:42:sha:aaa:job:987:fp:bbb` |
| `delivery_key` | `github:123:2c1d...` |
| `repository_id` | `123456789` |
| `pr_number` | `42` |
| `head_sha` | full SHA |
| `state` | `replaying_failure` |
| `transition_sequence` | `7` |
| `policy_version` | `ci-rescue-policy/v1` |
| `session_role` | `investigator` or `remediator` |
| `devin_session_id` | `devin-...` when present |
| `attempt` | integer |
| `duration_ms` | integer |
| `terminal_reason` | enum or null |

Do not log raw payloads, secrets, tokens, unbounded logs, or full model output.
Store large artifacts separately with hashes and redacted references.

### Trace spans

```text
webhook.receive
event.validate
github.resolve_pr
idempotency.claim
evidence.collect
sandbox.checkout
sandbox.replay_failure
devin.create_session
devin.poll_session
output.validate
github.check_upsert
authorization.wait
policy.evaluate_patch
sandbox.verify_repair
github.publish_repair
```

Trace attributes use stable IDs and enum labels, not raw test names when doing
so would create unbounded cardinality. High-cardinality values remain logs or
links.

### Metrics

| Metric | Type | Labels | Purpose |
|---|---|---|---|
| `ci_rescue_events_received_total` | counter | `repo`, `event`, `action` | Arrival rate. |
| `ci_rescue_runs_started_total` | counter | `repo`, `adapter` | Accepted workload. |
| `ci_rescue_runs_completed_total` | counter | `repo`, `adapter`, `terminal_reason` | Success/failure taxonomy. |
| `ci_rescue_active_runs` | gauge | `repo`, `state` | Active task status. |
| `ci_rescue_queue_depth` | gauge | `repo`, `queue` | Backlog and saturation. |
| `ci_rescue_stage_duration_seconds` | histogram | `repo`, `adapter`, `stage` | Stage latency. |
| `ci_rescue_end_to_end_seconds` | histogram | `repo`, `adapter`, `terminal_reason` | User-visible latency. |
| `ci_rescue_duplicate_suppressed_total` | counter | `repo`, `key_type` | Idempotency effectiveness. |
| `ci_rescue_stale_target_total` | counter | `repo`, `stage` | Branch churn impact. |
| `ci_rescue_devin_sessions_total` | counter | `repo`, `role`, `outcome` | Session lifecycle. |
| `ci_rescue_devin_acu_total` | counter | `repo`, `role`, `outcome` | API-reported ACU when available. |
| `ci_rescue_devin_cost_usd_total` | counter | `repo`, `role`, `outcome` | API-reported cost when available. |
| `ci_rescue_cost_unknown_total` | counter | `repo`, `role`, `reason` | Missing cost/usage visibility. |
| `ci_rescue_sandbox_minutes_total` | counter | `repo`, `adapter`, `stage` | Local/CI compute cost. |
| `ci_rescue_replay_reproduced_total` | counter | `repo`, `adapter`, `result` | Evidence quality. |
| `ci_rescue_diagnoses_total` | counter | `repo`, `classification`, `confidence` | Failure mix. |
| `ci_rescue_repair_offers_total` | counter | `repo`, `classification` | Eligible repairs. |
| `ci_rescue_repair_authorizations_total` | counter | `repo`, `method`, `result` | Human trust/adoption. |
| `ci_rescue_repairs_verified_total` | counter | `repo`, `result` | Verified red-to-green outcomes. |
| `ci_rescue_policy_rejections_total` | counter | `repo`, `reason` | Safety controls. |
| `ci_rescue_usefulness_feedback_total` | counter | `repo`, `rating` | Maintainer value signal. |
| `ci_rescue_false_green_total` | counter | `repo`, `detector` | Critical safety SLI; target zero. |

Bounded labels are required. Do not label metrics by PR number, SHA, session
ID, raw test node, branch, user, or error message. The `repo` label is a
configured low-cardinality slug or repository ID, not an arbitrary full name
from the webhook payload.

### Dashboards

For VP Engineering:

1. **Adoption funnel:** received events → accepted runs → reproduced failures
   → diagnoses → repair offers → authorizations → verified repairs → merged
   repairs.
2. **Quality and safety:** false greens, verification failures, policy
   rejections, malformed outputs, stale targets, duplicate suppression.
3. **Throughput:** active and completed tasks by state, queue depth, oldest
   nonterminal run, p50/p95 event-to-diagnosis and event-to-green.
4. **Economics:** sessions per verified repair, ACU/cost when available,
   sandbox/CI minutes, cost per useful diagnosis, cost per verified rescue.
5. **Failure mix:** change-caused, likely flaky, infrastructure,
   generated-drift, unresolved, and evidence-gap rates.

For operators:

- stuck nonterminal runs;
- session API failures;
- Check publication failures;
- backlog saturation;
- duplicate write attempts;
- artifact download failures;
- redaction failures; and
- kill-switch state.

### Alerts and SLOs

| Objective | Initial target | Alert |
|---|---:|---|
| Valid webhook to diagnosis Check | p95 under 15 minutes, excluding human wait | p95 breach for 3 consecutive windows. |
| Duplicate side effects | 0 duplicate sessions/checks/branches per failure key | Any duplicate write. |
| Unauthorized or stale writes | 0 | Any occurrence. |
| False-green published repair | 0 | Any occurrence; pause write expansion. |
| Stuck active run | 0 older than 2x deadline | Any stuck run. |
| Malformed Devin output | under 5% in pilot | 2x baseline or sustained breach. |
| Verification success for authorized repairs | customer-agreed pilot threshold | Sustained drop below threshold. |

### Analytics queries

Useful pilot questions:

```sql
-- Active tasks by state.
SELECT state, count(*) FROM repair_runs
WHERE terminal_reason IS NULL
GROUP BY state;

-- Completed outcomes for the last seven days.
SELECT terminal_reason, count(*) FROM repair_runs
WHERE updated_at >= now() - interval '7 days'
GROUP BY terminal_reason
ORDER BY count(*) DESC;

-- Event-to-diagnosis and event-to-green latency.
SELECT
  percentile_cont(0.5) WITHIN GROUP (ORDER BY diagnosis_ms) AS p50_diagnosis_ms,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY diagnosis_ms) AS p95_diagnosis_ms,
  percentile_cont(0.5) WITHIN GROUP (ORDER BY verified_ms) AS p50_verified_ms,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY verified_ms) AS p95_verified_ms
FROM run_latency_summary
WHERE created_at >= now() - interval '7 days';

-- Adoption funnel.
SELECT
  count(*) FILTER (WHERE diagnosis_published_at IS NOT NULL) AS diagnoses,
  count(*) FILTER (WHERE repair_offered_at IS NOT NULL) AS repair_offers,
  count(*) FILTER (WHERE repair_authorized_at IS NOT NULL) AS authorizations,
  count(*) FILTER (WHERE terminal_reason = 'succeeded') AS verified_repairs
FROM repair_runs
WHERE created_at >= now() - interval '30 days';
```

## 12. Security and reliability design

### Threat model

| Threat | Control |
|---|---|
| Forged webhook | HMAC signature, timestamp window, delivery ID, installation allowlist. |
| Replay attack | Delivery key and payload hash retention. |
| Payload repository spoofing | Resolve repository and PR via trusted provider API by immutable IDs. |
| Prompt injection through logs or code | Treat logs/artifacts/code as quoted evidence; prompts forbid following embedded instructions. |
| Secret exfiltration from fork | Forks are read-only; no publisher token in sandbox or Devin. |
| Model chooses unsafe command | Controller owns command mapping; model commands are advisory only. |
| Test-weakening false green | Path policy forbids test edits in pilot; collect-only and invariant probe detect weakening. |
| Symlink/submodule/path traversal | Canonical path normalization and Git-derived changed paths. |
| Stale branch write | Re-resolve head SHA before remediation, verification, and publish. |
| Duplicate bot spam | Stable Check upsert and unique failure key. |
| Cost runaway | Wall-clock deadlines, ACU limits when available, retry caps, queue limits. |
| Late worker overwrite | Compare-and-set transitions and monotonic publisher updates. |
| Artifact retention loss | Store hashes and bounded redacted copies needed for audit. |

### GitHub App permissions

Start with:

- `contents: read`;
- `pull_requests: read`;
- `checks: write`;
- `actions: read`;
- `metadata: read`.

Add for authorized repair only:

- `contents: write` to a bot branch namespace; and
- `pull_requests: write` if opening a companion repair PR.

Do not request `workflows: write`, `administration`, `secrets`, direct merge,
or broad organization privileges for the pilot.

## 13. Test matrix for the product PR

| Layer | Test | Expected result |
|---|---|---|
| Unit | Signature, timestamp, content type, payload schema. | Invalid inputs reject before side effects. |
| Unit | Delivery and failure-key construction. | Stable keys; SHA changes create new failure key. |
| Unit | Source-event and live-state review-ready gate. | Draft-origin or currently-draft runs make zero Devin API calls. |
| Unit | Pytest node extraction from JUnit/log. | Exact command selected or evidence gap terminal. |
| Unit | Structured-output schema validation. | Unknown enum, missing evidence, extra fields, or path mismatch fail closed. |
| Unit | Path policy canonicalization. | Test/workflow/symlink/submodule/traversal edits rejected. |
| Contract | Fake Devin API create/poll/status/output. | Correct request body, tags, budget, polling, terminal mapping. |
| Contract | GitHub Check upsert. | Same failure key updates one Check. |
| Integration | Saved failed-event happy path. | One investigator session, one diagnosis Check, no repair before authorization. |
| Integration | Draft failure followed by `ready_for_review`. | Draft run stays suppressed; one fresh failed run creates one investigator. |
| Integration | Eligible failure re-drafted before claim. | `suppressed_current_draft`, no session or GitHub output. |
| Integration | Authorized same-repo repair. | One remediator session, policy pass, exact node red-to-green, bot output. |
| Integration | Duplicate concurrent deliveries. | One run, one session per role, one Check. |
| Integration | Controller restart after session creation. | Resume persisted session, no second POST. |
| Failure injection | Devin timeout/API error/suspended without follow-up. | Terminal non-success with Check update. |
| Failure injection | Malformed Devin output. | `malformed_output`, no authorization progression. |
| Failure injection | Head SHA changes before publish. | `stale_target`, no write. |
| Security | Fork PR requests repair. | Diagnosis-only; no write token exposed. |
| Security | Patch edits only the test. | `policy_rejected`, no verification/publish. |
| Observability | Every fixture emits metrics/logs/transitions. | Active/completed status, taxonomy, latency, and cost fields queryable. |

## 14. Deployment, operations, and rollback

### Deployment topology

```text
GitHub App
  -> HTTPS ingress
  -> FastAPI controller
  -> Postgres or SQLite-for-demo run store
  -> worker queue
  -> sandbox runner pool
  -> Devin API adapter
  -> GitHub publisher adapter
  -> metrics endpoint + logs + traces
```

For the take-home demo, Docker Compose can run FastAPI, a worker, SQLite, and
a local sandbox with saved event fixtures. Production should use a durable
database, isolated sandbox workers, secret manager, and standard telemetry
backend.

### Operational controls

- global kill switch for remediation while leaving diagnosis enabled;
- per-repository and per-workflow allowlists;
- max active runs and per-PR concurrency;
- per-run wall-clock and ACU budgets;
- artifact retention and redaction policy;
- replay CLI for saved events;
- admin command to cancel a run by failure key;
- idempotent publisher repair for interrupted Check updates; and
- run export for VP and security review.

### Rollback

If safety or quality gates fail:

1. disable repair authorization;
2. continue diagnosis-only if useful and safe;
3. cancel active remediation sessions;
4. preserve run records and artifacts for audit;
5. remove bot branch permissions if required; and
6. publish a pilot incident note with failure taxonomy and corrective action.

## 15. Implementation sequence

| Milestone | Deliverable | Exit gate |
|---|---|---|
| M1. Docs and spec | This design, skills, test-case plan, and observability plan. | PR #1 remains documentation-only. |
| M2. Controller skeleton | FastAPI webhook, schema validation, run store, transitions, saved-event replay. | Invalid/duplicate/stale fixtures pass. |
| M3. Evidence and replay | Python unit adapter, sandbox checkout, exact pytest replay, artifact hashing. | Seeded `>=` to `>` regression reproduces. |
| M4. Devin investigator | Create/poll/validate read-only session, publish diagnosis Check. | Malformed/timeout/API fixtures fail closed. |
| M5. Authorization and remediator | Scoped maintainer authorization, trusted-branch repair session. | Fork/stale/unauthorized cases blocked. |
| M6. Verification and publish | Patch policy, fresh checkout verification, bot branch/PR output. | Exact node fails before and passes after; test-edit false green rejected. |
| M7. Observability and pilot | Metrics, dashboard, alerts, cost/adoption report. | VP scorecard answers safety, usefulness, latency, throughput, and economics. |

## 16. VP Engineering review questions

| Question | Answer |
|---|---|
| Why not just rerun CI? | Reruns do not classify causality, connect logs to the PR diff, or propose a minimal repair. This system reproduces first, then uses Devin only for the ambiguous reasoning step. |
| Why use Devin instead of deterministic scripts? | Deterministic code handles event validation, replay, policy, and verification. Devin is used where repository reasoning is required: identifying the causal change and producing a small code patch. |
| What prevents unsafe AI writes? | Read-only diagnosis comes first; repair requires maintainer authorization, same-repo trust, stale-SHA recheck, path policy, no publisher credential in Devin, and clean-room verification. |
| How do we know it worked? | A repair is successful only if the controller observes the exact command fail before and pass after at the same target, with unchanged collection and invariant checks. |
| What is the blast radius? | One repo, one adapter, one trusted PR SHA, one allowed production file in the first demo. Forks are diagnosis-only. |
| What does success look like for the company? | More useful diagnoses, faster event-to-diagnosis, accepted repairs, verified red-to-green outcomes, reduced duplicate toil, and acceptable cost per useful result. ROI remains a pilot measurement, not a pre-demo claim. |
| What would make us stop? | Any unauthorized write, stale write, duplicate bot branch, false green, hidden cost overrun, or maintainer rejection of diagnosis quality pauses write expansion. |
| How does this become a platform? | The same event validation, idempotency, session broker, policy engine, proof runner, publisher, and telemetry can support rebase conflict resolution and release cherry-pick planning after CI Rescue earns trust. |

## 17. Pilot scorecard

| Dimension | Gate |
|---|---|
| Safety | Zero unauthorized, stale, fork, or out-of-policy writes. |
| Truth | 100% of successful repairs have fail-before/pass-after proof owned by the controller. |
| Reliability | Duplicate, timeout, malformed, stale, cancellation, and restart tests are queryable and fail closed. |
| Usefulness | At least 80% of reviewed diagnoses rated useful before repair expansion. |
| Adoption | Maintainers invoke offered repairs and merge a meaningful share without broad rewrites. |
| Latency | p50/p95 diagnosis and verified-repair times meet pilot expectations with human wait separated. |
| Economics | ACU/cost when available, unknown-cost count, sandbox minutes, and cost per useful result are visible. |
| Extensibility | New adapters reuse shared primitives rather than bypassing safety or observability gates. |
