---
name: event-driven-remediation-demo
description: "Design or review safe, deterministic event-driven remediation automations that invoke the Devin API for conflict resolution, failed CI repair, or release cherry-picking."
---

# Event-Driven Remediation with the Devin API

Use this skill for automations that turn repository events into bounded Devin sessions and verified, updateable outcomes. Treat event payloads, forks, logs, artifacts, and Devin output as untrusted input. **Do not start a session until every preflight item passes; do not publish a success until independent verification passes.**

## Reusable flow

1. Normalize and validate the event into a typed internal request.
2. Authorize the actor, repository, operation, refs, and requested write scope.
3. Resolve the target branch to an immutable SHA and collect evidence from that SHA.
4. Deduplicate atomically, then create a bounded Devin session.
5. Observe terminal state and validate structured output.
6. Independently verify the proposed result in a clean environment.
7. Recheck the target SHA, apply or publish through a controlled writer, and upsert the PR/check/report.

Parameterize the workflow rather than forking it:

| Use case | Deterministic evidence | Independent acceptance |
| --- | --- | --- |
| Conflict resolution | base/head SHAs, merge-base, conflicting paths, reproducible merge command | clean merge/rebase, tests, diff limited to policy |
| Failed CI repair | workflow/job IDs, exact logs and artifacts, failing command, toolchain/lockfiles | rerun the failed command plus required regression tests |
| Release cherry-pick | source commit, release SHA, ordered commit list, policy metadata | clean cherry-pick, provenance preserved, release checks pass |

## Strict design and review checklist

### Event boundary and idempotency

- [ ] Verify webhook signature, timestamp/age, delivery ID, content type, payload size, and expected event/action before parsing fields.
- [ ] Parse with a strict schema; reject missing, unknown-critical, malformed, or ambiguous repository/ref/SHA values.
- [ ] Build a stable idempotency key from provider + repository ID + event/action + delivery or operation ID + immutable input SHA(s).
- [ ] Atomically claim that key in durable storage; duplicates return the existing run/output and never create another session.
- [ ] Define replay retention and distinguish a retry of one run from a genuinely new SHA or operation.

### Immutable inputs and deterministic evidence

- [ ] Pin repository by provider and immutable repository ID (not payload URL alone), target branch by full ref, and target/source inputs by full immutable SHA.
- [ ] Resolve the branch server-side through the trusted provider API; require the event SHA to match the resolved SHA.
- [ ] Collect evidence before invoking Devin from a clean checkout at the pinned SHA using fixed commands, versions, environment, and dependency lockfiles.
- [ ] Store commands, exit codes, relevant stdout/stderr, artifact IDs/checksums, merge-base, and evidence timestamps with size and secret-redaction limits.
- [ ] Give Devin evidence references and bounded excerpts, never credentials or an instruction to discover the failure nondeterministically.

### Bounded Devin sessions

- [ ] Create the session with one explicit objective, pinned inputs, acceptance commands, allowed paths, prohibited actions, and whether writes are permitted.
- [ ] Require a versioned structured-output schema with no free-form success path. At minimum require `schema_version`, `outcome`, `summary`, `changed_paths`, `evidence`, and `verification_commands`; constrain enums, lengths, and additional properties.
- [ ] Set explicit ACU and wall-clock limits, cancellation behavior, and retry count; retries reuse the run identity and remain within an aggregate budget.
- [ ] Attach searchable tags such as workflow version, run ID, idempotency key, repository ID, operation, target SHA, environment, and role.
- [ ] Persist the Devin session ID before waiting; support webhook and polling recovery without creating a replacement session accidentally.
- [ ] Handle every documented terminal state explicitly. Treat timeout, cancellation, API error, unknown state, malformed/missing structured output, and budget exhaustion as non-success.
- [ ] Validate output against the exact schema and cross-check claimed paths, SHAs, commands, and artifacts against observed data.

A useful outcome enum is `proposed`, `no_change`, `blocked`, and `failed`; automation—not Devin—decides whether a proposal is accepted.

### Roles, authorization, and write safety

- [ ] Use a read-only **investigator** session to diagnose and propose a patch when uncertainty or risk is high; give a separate **writer** only the accepted plan and minimum write capability.
- [ ] Never let an investigator's narrative authorize a writer. The orchestrator validates the structured handoff and policy gates independently.
- [ ] Gate by installation/tenant, actor permission, repository allowlist, event/action, operation, target branch, environment, and policy approval before session creation and again before writing.
- [ ] Enforce canonical normalized allowed paths on the produced diff; reject traversal, symlink escapes, submodules, generated secrets, workflow/policy changes, and any path outside the operation-specific allowlist.
- [ ] Re-resolve the target branch immediately before write/publish. If it differs from the pinned SHA, cancel as `stale_sha`; never silently rebase Devin's result onto new code.
- [ ] Treat fork-originated code and metadata as untrusted. Do not expose secrets or write tokens to untrusted forks; use read-only analysis or require an authorized maintainer to copy/approve the change in a trusted context.
- [ ] Use short-lived, least-privilege credentials in the orchestrator-controlled writer; Devin must not push, merge, approve, or broaden its own permissions.

### Independent verification and outputs

- [ ] Materialize the proposed patch in a fresh isolated checkout rooted at the pinned SHA; derive changed paths and diff from Git rather than Devin's report.
- [ ] Run deterministic acceptance commands outside the Devin session, with pinned tools, network policy, resource limits, and captured logs/checksums.
- [ ] Verify repository/ref/SHA ancestry, clean application, allowed paths, test results, and operation-specific invariants; fail closed on missing evidence.
- [ ] Do not treat Devin's self-reported tests, success, changed paths, or terminal state as proof.
- [ ] Upsert one durable PR/check/report using the idempotency key or stable external ID. Update status, links, evidence, and rerun attempts instead of posting duplicates.
- [ ] Make output monotonic and concurrency-safe: pending → terminal, with compare-and-set/versioning so late workers cannot overwrite newer results.
- [ ] Include pinned SHAs, verification results, run/session IDs, and a concise failure reason; redact secrets and bound untrusted text.

### State machine, observability, and objectives

- [ ] Persist explicit transitions such as `received → validated → authorized → evidence_ready → session_running → proposed → verifying → publishing → succeeded`, with terminal exits for duplicate, rejected, stale, timed_out, cancelled, failed, and verification_failed.
- [ ] Record transition time, attempt, correlation IDs, input/output schema versions, policy version, pinned SHA, session ID, budget consumed, and sanitized reason; make transitions idempotent and auditable.
- [ ] Use a stable failure taxonomy: validation, duplicate, authorization, stale SHA, evidence, Devin API, timeout/budget, malformed output, policy/path violation, verification, publish, and internal.
- [ ] Measure arrival/accepted/completed throughput; queue, evidence, session, verification, publish, and end-to-end latency; acceptance rate; verified-success rate; duplicate suppression; stale/cancel rates; failures by taxonomy; ACU and monetary cost per accepted result.
- [ ] Alert on stuck nonterminal states, terminal-state mismatches, rising malformed output or verification failures, budget overruns, backlog age, and duplicate writes.

### Required fixtures

- [ ] **Happy path:** authorized pinned event produces one session, passes independent verification, and upserts one success output.
- [ ] **Duplicate:** concurrent and replayed deliveries produce no extra session or output.
- [ ] **Malformed output:** invalid JSON/schema, unknown fields/outcome, or false path claims fail closed.
- [ ] **Timeout:** wall-clock/ACU exhaustion cancels work, records a terminal failure, and updates the existing output.
- [ ] **Stale SHA:** branch movement before start and before publish prevents or cancels writing.
- [ ] **Unauthorized writes:** disallowed paths, symlink escapes, permission escalation, and fork-originated secret access are rejected.
- [ ] **Verification failure:** Devin reports success but clean-room acceptance fails; no write/merge occurs and evidence is published as failure.

For each fixture, assert state transitions, API call count, idempotency behavior, tags, redaction, terminal output, metrics, and that no unauthorized side effect occurred.
