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

# PR CI Rescue Product Implementation Design

## 1. Decision

Implement PR CI Rescue as a small standalone Python service under
`takehome/ci_rescue/`, not inside the Superset Flask application.

The service is a modular monolith with:

- one HTTP process that validates and records GitHub events;
- one worker that advances persisted runs through an explicit state machine;
- SQLite and fake adapters for the credential-free demo;
- PostgreSQL and live GitHub/Devin adapters behind the same interfaces; and
- isolated replay and verification sandboxes owned by the controller.

The first implementation pull request should deliver an **offline vertical
slice through read-only diagnosis**. It should prove event validation,
idempotency, immutable correlation, exact pytest-node selection, state
transitions, a bounded fake Devin contract, structured-output validation, and
one updateable fake Check. It should not wait for live credentials or attempt
repair publication.

The next pull request can replace the fake GitHub and Devin adapters with live
read-only integrations. A third pull request can add explicitly authorized
repair, policy validation, clean-room verification, and controlled publishing.

This sequence preserves a useful review boundary:

```text
Milestone 1: deterministic controller
Milestone 2: live diagnosis
Milestone 3: controlled repair
```

## 2. Why this shape

### Keep the automation out of Superset's product runtime

CI Rescue operates on the repository and GitHub control plane. It does not
serve Superset users or depend on Superset's Flask application state.
Embedding it in `superset/` would:

- couple an experimental automation to Superset's release dependencies;
- give the controller access to more application configuration than it needs;
- make local replay depend on starting Superset; and
- obscure which changes belong to the take-home product versus the target
  application.

A standalone package keeps its dependency lock, Docker image, state store, and
security boundary explicit.

### Use a modular monolith before queues and microservices

The important boundaries are logical, not deployment-driven:

```text
event input
  -> domain orchestration
  -> GitHub / Devin / sandbox / persistence ports
```

One deployable service is enough for the pilot. The webhook returns after a
durable insert, and a worker claims the run from the database. HTTP and worker
processes may share one image and codebase. A production queue can replace
database-backed claiming without changing domain behavior.

### Build the deterministic spine before invoking Devin

The controller must be testable without GitHub, a Devin API token, network
access, or a mutable pull request. The fake adapters are therefore product
components, not throwaway mocks: they power fixtures, demos, failure injection,
and contract tests.

## 3. First implementation pull request

### Included

The first implementation pull request accepts one saved normalized
`workflow_run.completed` event representing:

- the configured `ong6/superset` repository;
- the `Python-Unit` workflow;
- one open same-repository pull request;
- one immutable head SHA;
- one failed JUnit test with an exact pytest node; and
- the report-execution equality-boundary regression.

Running the replay command must:

1. validate the fixture with strict typed schemas;
2. calculate delivery and failure keys;
3. atomically create one run;
4. suppress a duplicate replay;
5. ingest the credential-free evidence bundle;
6. select a fixed argv array for the exact pytest node;
7. record a deterministic failing replay result from the fixture adapter;
8. create one fake investigator session;
9. validate the investigator output against the versioned schema;
10. transition the run to `diagnosis_ready`;
11. upsert one fake Check payload; and
12. export the complete run timeline as JSON.

### Acceptance commands

The exact command names can be finalized with the package scaffolding, but the
public interface should be:

```bash
python -m ci_rescue replay \
  --event fixtures/normalized_failed_event.json \
  --database .ci-rescue/demo.db

python -m ci_rescue show-run <run_id> --database .ci-rescue/demo.db

pytest -q takehome/ci_rescue/tests
```

The first command exits successfully only when the fixture reaches
`diagnosis_published`. Replaying the same event prints the existing `run_id`
and creates no additional session or Check.

### Excluded

- no public webhook endpoint exposed to GitHub;
- no live Devin session;
- no GitHub App token;
- no branch write or companion pull request;
- no `/devin fix` command;
- no arbitrary command execution;
- no Docker-in-Docker sandbox; and
- no broad Python-unit log parser.

These exclusions make the first implementation pull request deterministic and
reviewable while preserving the real interfaces.

## 4. Proposed repository layout

```text
takehome/ci_rescue/
├── README.md
├── pyproject.toml
├── Dockerfile
├── compose.yaml
├── src/ci_rescue/
│   ├── __init__.py
│   ├── app.py
│   ├── cli.py
│   ├── config.py
│   ├── domain/
│   │   ├── models.py
│   │   ├── states.py
│   │   └── transitions.py
│   ├── schemas/
│   │   ├── events.py
│   │   ├── evidence.py
│   │   ├── investigator.py
│   │   └── remediator.py
│   ├── services/
│   │   ├── intake.py
│   │   ├── orchestrator.py
│   │   ├── command_selector.py
│   │   ├── output_validator.py
│   │   └── patch_policy.py
│   ├── ports/
│   │   ├── artifacts.py
│   │   ├── clock.py
│   │   ├── devin.py
│   │   ├── github.py
│   │   ├── sandbox.py
│   │   └── store.py
│   └── adapters/
│       ├── artifacts_filesystem.py
│       ├── devin_fake.py
│       ├── devin_http.py
│       ├── github_fake.py
│       ├── github_http.py
│       ├── sandbox_fixture.py
│       ├── sandbox_container.py
│       ├── sqlite_store.py
│       └── postgres_store.py
├── migrations/
├── fixtures/
│   ├── normalized_failed_event.json
│   ├── evidence_bundle.json
│   ├── investigator_output_change_caused.json
│   ├── malformed_output.json
│   ├── policy_rejected_test_edit.json
│   └── run_timeline_verified.json
└── tests/
    ├── unit/
    ├── contract/
    └── integration/
```

Only files required by the active milestone should be added. For example,
Milestone 1 should define the live port interfaces but implement only SQLite,
filesystem, fixture-sandbox, fake-Devin, and fake-GitHub adapters.

## 5. Dependency boundary

The standalone package should use Python 3.11 or newer and pin its own direct
dependencies. It should not add CI Rescue packages to Superset's runtime
dependencies.

Expected categories are:

| Need | Choice |
|---|---|
| Typed validation | Pydantic v2 |
| HTTP entry point | FastAPI |
| HTTP clients | HTTPX |
| Persistence | SQLAlchemy 2 with Alembic |
| Production server | Uvicorn |
| Metrics | Prometheus client |
| Tests | pytest |

Exact versions must be selected when the package is created, then resolved to
a committed lock file. The implementation must not rely on whichever versions
happen to be installed for Superset.

## 6. Core domain contracts

### Normalized event

Provider payloads must not flow directly into orchestration. The GitHub adapter
produces one strict internal model:

```python
class NormalizedFailedRun(BaseModel):
    schema_version: Literal["ci-rescue-event/v1"]
    provider: Literal["github"]
    repository_id: int
    repository_full_name: str
    installation_id: int
    delivery_id: UUID
    event_name: Literal["workflow_run"]
    event_action: Literal["completed"]
    workflow_run_id: int
    workflow_name: Literal["Python-Unit"]
    workflow_conclusion: Literal["failure", "timed_out"]
    workflow_completed_at: datetime
    pull_request_number: int
    head_sha: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
    base_sha: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
    head_ref: str
    base_ref: str
    is_fork: bool
    sender_login: str
```

Unknown fields should be rejected at every trust boundary. Provider-specific
extra data can be retained as a hashed artifact but cannot silently affect
domain decisions.

### Stable keys

```text
delivery_key =
  github:{repository_id}:{delivery_id}

failure_key =
  github:{repository_id}:pr:{pull_request_number}:sha:{head_sha}:
  job:{job_logical_key}:fp:{failure_fingerprint}
```

Key construction is a pure function with fixed canonicalization rules and
golden tests. The key version should be stored separately so a future
fingerprint algorithm can coexist with earlier runs.

### Controller-owned outcomes

Devin outputs classifications and proposals. The controller owns run outcomes:

```python
class TerminalReason(StrEnum):
    DIAGNOSIS_ONLY = "diagnosis_only"
    SUCCEEDED = "succeeded"
    DUPLICATE = "duplicate"
    NOT_ACTIONABLE = "not_actionable"
    VALIDATION_FAILED = "validation_failed"
    AUTHORIZATION_FAILED = "authorization_failed"
    INSUFFICIENT_REPLAY_EVIDENCE = "insufficient_replay_evidence"
    DEVIN_API_FAILED = "devin_api_failed"
    INTERACTION_REQUIRED = "interaction_required"
    TIMED_OUT = "timed_out"
    MALFORMED_OUTPUT = "malformed_output"
    STALE_TARGET = "stale_target"
    POLICY_REJECTED = "policy_rejected"
    VERIFICATION_FAILED = "verification_failed"
    PUBLISH_FAILED = "publish_failed"
    CANCELLED = "cancelled"
```

No adapter may mark a run successful directly.

## 7. Ports and ownership

The domain service depends on typed protocols:

```python
class RunStore(Protocol):
    def claim(self, event: NormalizedFailedRun, keys: RunKeys) -> ClaimResult: ...
    def compare_and_transition(
        self,
        run_id: UUID,
        expected: RunState,
        target: RunState,
        reason: str | None = None,
    ) -> RunRecord: ...


class GitHubGateway(Protocol):
    def resolve_failed_run(self, event: GitHubWorkflowRunEvent) -> ResolvedRun: ...
    def download_evidence(self, run: ResolvedRun) -> EvidenceBundle: ...
    def upsert_check(self, output: CheckOutput) -> CheckReference: ...
    def resolve_head_sha(self, repository_id: int, pull_request: int) -> str: ...
    def resolve_actor_permission(
        self,
        repository_id: int,
        actor_login: str,
    ) -> RepositoryPermission: ...


class DevinGateway(Protocol):
    def create_investigator(self, request: InvestigatorRequest) -> SessionReference: ...
    def create_remediator(self, request: RemediatorRequest) -> SessionReference: ...
    def get_session(self, session_id: str) -> SessionSnapshot: ...
    def terminate_session(self, session_id: str) -> None: ...


class Sandbox(Protocol):
    def replay(self, request: ReplayRequest) -> ReplayResult: ...
    def verify(self, request: VerificationRequest) -> VerificationResult: ...
```

The protocols should be synchronous in the first implementation. HTTP and
subprocess adapters may use internal async clients later, but making the domain
service async before there is concurrent work would complicate fixture tests
without changing behavior.

## 8. Persisted state

### Minimal Milestone 1 tables

Milestone 1 needs five tables:

| Table | Purpose |
|---|---|
| `deliveries` | Unique provider delivery claim and payload hash. |
| `repair_runs` | Current state, immutable inputs, keys, schema and policy versions. |
| `run_transitions` | Append-only state history with monotonic sequence. |
| `devin_sessions` | One persisted session record per run and role. |
| `check_outputs` | Stable fake/live publisher external key and last payload hash. |

Evidence, replay attempts, authorizations, and patches can initially be stored
as typed JSON artifacts referenced from transitions. They should become
dedicated tables when live collection and repair are added.

### Concurrency

SQLite demo mode supports one worker and uses:

- unique indexes on `delivery_key` and `failure_key`;
- `BEGIN IMMEDIATE` for claims; and
- a version column for compare-and-set transitions.

Production PostgreSQL uses the same unique constraints and claims queued work
with `FOR UPDATE SKIP LOCKED`. Both stores must pass the same contract suite.

### State transition API

Every state change is one transaction:

1. load the run by `run_id`;
2. assert current state and version;
3. validate the transition against the transition table;
4. update state and increment version;
5. append exactly one transition record; and
6. commit.

The publisher writes only after its preceding state transaction commits.
Publisher retries use the stored external key and payload hash.

## 9. State machine by milestone

### Milestone 1

```text
received
  -> validated
  -> authorized_read
  -> evidence_ready
  -> replaying_failure
  -> failure_reproduced
  -> investigation_session_running
  -> diagnosis_ready
  -> diagnosis_published
  -> diagnosis_only
```

Failure exits:

```text
validation_failed
authorization_failed
duplicate
insufficient_replay_evidence
replay_failed_infra
devin_api_failed
interaction_required
timed_out
malformed_output
publish_failed
cancelled
```

### Milestone 3 additions

```text
diagnosis_published
  -> awaiting_repair_authorization
  -> repair_authorized
  -> remediation_session_running
  -> patch_proposed
  -> policy_checking
  -> verifying
  -> publishing_repair
  -> succeeded
```

Additional exits are `authorization_failed`, `authorization_expired`,
`stale_target`, `policy_rejected`, and `verification_failed`.

Transition definitions should live in one declarative mapping. Tests should
iterate over the mapping and prove that undeclared transitions reject.

## 10. Pipeline behavior

### Intake

The live HTTP route performs only:

1. request-size, content-type, HMAC, event-name, and delivery-ID validation;
2. strict GitHub payload parsing;
3. provider-resolved event-age, repository, workflow, action, and conclusion
   allowlist checks;
4. trusted API resolution of repository ID, pull request, and head SHA;
5. atomic delivery/failure claim; and
6. a `202 Accepted` response containing the existing or new `run_id`.

It does not download artifacts, start Devin, or wait for replay.

GitHub does not provide a signed webhook timestamp header. Replay resistance
therefore comes from the HMAC-validated payload, delivery-key claim, payload
hash, and a freshness check against the workflow completion time resolved from
the GitHub API. If an ingress adds a signed receipt timestamp, that may be an
additional gate but must not be assumed by the provider adapter.

The fixture CLI enters after signature validation but passes through the same
normalized-event schema and claim service.

### Evidence

For the first live adapter, the source of truth is the artifacts already
published by Superset's `Python-Unit` workflow:

- `junit-results-current`;
- `Event File`; and
- workflow/job metadata from the GitHub API.

The existing `Python Unit Test Results` workflow demonstrates the safe
base-branch pattern: consume artifacts from `workflow_run` without checking out
untrusted pull-request code in a privileged job.

The collector:

- hashes original artifacts;
- parses XML with external entities disabled;
- bounds total bytes and test-case count;
- redacts configured secret patterns;
- extracts the first actionable failure;
- records all candidate node IDs; and
- selects one only when the adapter can prove a canonical test path.

### Command selection

The first adapter accepts only a pytest node whose file:

- is under `tests/unit_tests/`;
- ends in `.py`;
- contains no NUL, newline, path traversal, glob, or shell metacharacter;
- resolves inside the checkout; and
- is confirmed by `pytest --collect-only -q`.

Execution is always an argv array:

```python
("pytest", "-q", node_id)
```

Neither logs nor Devin may supply a shell string.

### Investigation

The orchestrator creates a session only after a failing replay result is
persisted. The prompt includes immutable IDs, bounded evidence excerpts,
allowed classifications, and evidence references. It explicitly forbids
editing or publishing.

On restart, the worker reads the persisted session ID and resumes observation.
It must never create a replacement session merely because a poll timed out.

### Diagnosis publication

`CheckOutput` is rendered from controller records, not from model-authored
Markdown. Model strings are length-limited, escaped, and placed only in
designated fields.

The external key is the failure key. The fake publisher writes one JSON file;
the live publisher creates or updates one Check Run at the pinned head SHA.

## 11. Devin API adapter

The implementation should use one API version consistently. The preferred live
adapter is the organization-scoped v3 API because its documented session
response includes:

- `status` values `new`, `claimed`, `running`, `exit`, `error`, `suspended`,
  and `resuming`;
- `status_detail`;
- validated `structured_output`; and
- `acus_consumed`.

Session creation uses:

```text
POST /v3/organizations/{org_id}/sessions
```

with:

- `structured_output_required: true`;
- a self-contained JSON Schema Draft 7 document;
- integer `max_acu_limit`;
- exact tags, knowledge IDs, and repository selection;
- `resumable: false` for disposable investigator/remediator sessions; and
- no session secrets.

Session observation uses:

```text
GET /v3/organizations/{org_id}/sessions/{session_id}
```

and active termination uses:

```text
DELETE /v3/organizations/{org_id}/sessions/{session_id}
```

Session IDs are opaque strings. The adapter must not require the documented
`devin-` prefix because a valid create response may return another accepted
wire representation.

The adapter normalizes both `status` and `status_detail`:

| Wire state | Domain behavior |
|---|---|
| `new`, `claimed`, `resuming` | Continue until the controller deadline. |
| `running` with `working` or no detail | Continue until the controller deadline. |
| `running` with `waiting_for_user` or `waiting_for_approval` | Request termination and fail as `interaction_required`; unattended automation never answers or approves. |
| `running` with `finished` | Poll for a short bounded grace period for `exit`; otherwise request termination and fail closed. |
| `exit` with structured output | Validate schema and cross-check evidence. |
| `exit` without structured output | `malformed_output`. |
| `error` | `devin_api_failed`. |
| `suspended` | Terminal non-success unless one configured follow-up is explicitly supported. |
| Unknown status or detail | Fail closed as `devin_api_failed`. |

A successful `DELETE` is only a termination acknowledgement. The controller
continues bounded polling until a terminal state is observed and records a
termination failure if the session remains active at the deadline.

The controller's unique failure key remains the source of idempotency even
when the API offers its own idempotency behavior.

The HTTP adapter should be covered by recorded request/response fixtures, not
tests against the live API. A startup compatibility probe may validate that
configured fields remain accepted before live processing is enabled.

## 12. Read-only Devin environment

Prompt instructions are not a permission boundary. Live sessions must run
under a dedicated Devin service identity and repository integration that has:

- read-only repository contents;
- no pull-request, Checks, Actions, administration, or workflow write access;
- no controller GitHub App private key;
- no publisher installation token;
- no unrelated organization secrets; and
- only the knowledge IDs selected for CI Rescue.

The controller owns a separate short-lived GitHub App installation token. It
is never sent to Devin or mounted in replay sandboxes.

If the deployment cannot prove the Devin environment is read-only, live
investigation may continue only against a source snapshot or mirror that has no
write credentials. Remediation remains disabled.

## 13. Repair patch handoff

The original specification named a `patch_ref` but did not define who creates
or can read it. The pilot should use an inline, bounded unified diff in
structured output:

```json
{
  "schema_version": "ci-rescue-remediator/v1",
  "outcome": "patch_proposed",
  "base_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "summary": "Restore rejection when reserves equal the budget.",
  "changed_paths": ["superset/utils/report_execution.py"],
  "patch_unified_diff": "diff --git ...",
  "patch_sha256": "<sha256>",
  "verification_commands": [
    "pytest -q tests/unit_tests/utils/test_report_execution.py::..."
  ],
  "risk_notes": []
}
```

For the first repair adapter:

- the patch is limited to 32 KiB UTF-8;
- exactly one regular production file may change;
- binary diffs, renames, mode changes, submodules, and symlinks reject;
- `base_sha` must equal the authorized head SHA;
- controller-derived changed paths must equal the claimed paths;
- controller-derived SHA-256 must equal `patch_sha256`; and
- verification commands from Devin are advisory only.

The controller writes the patch to its artifact store, applies it with
`git apply --check` in a fresh pinned checkout, derives the diff from Git, and
then runs policy and verification.

A cross-field validator requires a non-empty patch and its hash only for
`patch_proposed`; `no_change`, `blocked`, and `failed` must carry an empty patch
and cannot enter policy or verification.

This design lets Devin propose a change without receiving publisher
credentials or needing access to controller storage. A later version can use a
signed artifact upload only if the storage and expiry contract is independently
specified and tested.

## 14. Sandbox design

### Fixture sandbox

Milestone 1 uses a deterministic adapter whose replay result is loaded from
`evidence_bundle.json`. It records the same fields as the live sandbox:

- checkout SHA;
- argv;
- exit code;
- stdout/stderr artifact references;
- duration;
- collection hash; and
- environment version.

### Container sandbox

The live adapter creates a fresh checkout at the pinned SHA and runs inside a
container with:

- network disabled after repository and dependency materialization;
- read-only dependency caches;
- a writable checkout and bounded artifact directory;
- non-root user;
- CPU, memory, process, file-size, and wall-clock limits;
- no Docker socket;
- no host Git credentials; and
- a fixed environment image digest.

Failure replay and repair verification use separate fresh checkouts. The
verification checkout starts at the same authorized SHA and receives only the
controller-validated patch.

## 15. GitHub adapter

The live GitHub App subscribes initially to:

- `workflow_run`;
- `issue_comment` only when repair authorization is implemented; and
- installation/repository lifecycle events needed to disable stale
  configuration.

Minimum diagnosis permissions:

```text
Actions: read
Checks: write
Contents: read
Metadata: read
Pull requests: read
```

Repair publishing adds `Contents: write` and `Pull requests: write` only to the
controller installation. Repair authorization also requires `Issues: read` for
the `issue_comment` event. The controller resolves the actor's effective
repository permission through the trusted provider API using `Metadata: read`;
webhook `author_association` is evidence, not authorization.

The controller writes only to a configured `devin/ci-rescue/<run_id>`
bot-branch namespace and never merges.

The Check publisher stores the provider Check Run ID. Retries update that ID;
they do not search by display name or post a new comment.

## 16. Configuration and secrets

Configuration is strict and split by capability:

```text
CI_RESCUE_MODE=fixture|diagnosis|repair
CI_RESCUE_DATABASE_URL=...
CI_RESCUE_ARTIFACT_ROOT=...
CI_RESCUE_REPOSITORY_ID=...
CI_RESCUE_REPOSITORY_FULL_NAME=ong6/superset
CI_RESCUE_WORKFLOW_NAME=Python-Unit
CI_RESCUE_POLICY_VERSION=ci-rescue-policy/v1
CI_RESCUE_ENVIRONMENT_IMAGE=<image>@sha256:<digest>
DEVIN_API_BASE_URL=https://api.devin.ai
DEVIN_ORG_ID=org-...
DEVIN_INVESTIGATOR_MAX_ACU=3
DEVIN_REMEDIATOR_MAX_ACU=4
```

Secret values are supplied through the deployment secret manager:

```text
GITHUB_APP_PRIVATE_KEY
GITHUB_WEBHOOK_SECRET
DEVIN_API_TOKEN
```

Startup fails when the selected mode lacks required configuration. Fixture
mode requires no secrets and must reject live network adapters.

## 17. Fixture and test plan

### Required fixture cases

| Fixture | Assertion |
|---|---|
| Happy path | One run, one investigator, one Check, complete timeline. |
| Duplicate sequential replay | Existing run returned; no new side effect. |
| Duplicate concurrent replay | Unique constraints permit one owner. |
| Invalid repository or workflow | Rejected before evidence or session calls. |
| Read authorization denied | Rejected before evidence or session calls. |
| Stale SHA | Provider-resolved SHA mismatch terminates before session creation. |
| Missing pytest node | `insufficient_replay_evidence`. |
| Replay infrastructure failure | No investigator session. |
| Malformed investigator output | `malformed_output`; no diagnosis success. |
| Investigator timeout | Session termination attempted and terminal state persisted. |
| Publisher retry | Existing external Check key is updated, not duplicated. |
| Restart after session creation | Existing session is polled; no second create call. |
| Test-only repair patch | `policy_rejected`. |
| Verification false green | Deleted/renamed test or failed invariant rejects. |
| Untrusted fork authorization | Diagnosis remains; no remediator or writer call. |

### Side-effect assertions

Every fixture should assert:

- exact state-transition sequence;
- adapter call count and order;
- persisted schema and policy versions;
- session tags and budget;
- redaction of untrusted text;
- stable output hashes;
- emitted metric increments; and
- absence of unauthorized calls.

### Contract suites

Each port has one reusable contract suite. Fake and live adapters must satisfy
the same observable behavior. Examples:

- SQLite and PostgreSQL claim semantics;
- fake and HTTP Devin status normalization;
- fake and HTTP Check upsert semantics; and
- fixture and container replay-result fields.

## 18. Pull-request sequence

### Milestone 1 — deterministic controller

Deliver:

- standalone package and lock file;
- normalized schemas and state machine;
- SQLite store;
- fixture artifact store;
- fake GitHub, Devin, and sandbox adapters;
- replay/show-run CLI;
- happy, duplicate, malformed, timeout, stale, and restart fixtures; and
- JSON run export.

Exit gate:

- all fixture tests pass without network or credentials;
- duplicate concurrent replay creates one logical run;
- invalid inputs create no session or publisher call; and
- the timeline reaches `diagnosis_only` through one Check upsert.

### Milestone 2 — live read-only diagnosis

Deliver:

- FastAPI webhook;
- GitHub signature and provider-resolution adapter;
- JUnit artifact collector;
- container replay sandbox;
- v3 Devin investigator adapter;
- live Check publisher; and
- diagnosis-only deployment configuration.

Exit gate:

- a trusted test pull request produces one real diagnosis Check;
- a fork receives no privileged checkout or write capability;
- restart and timeout tests remain green; and
- duplicate webhook deliveries create no duplicate session or Check.

### Milestone 3 — controlled repair

Deliver:

- `/devin fix <run_id>` authorization;
- actor-permission and expiry checks;
- v3 remediator adapter with bounded inline patch;
- path and patch policy;
- fresh-checkout verification;
- bot branch and companion pull-request publisher; and
- repair kill switch.

Exit gate:

- the equality-boundary node fails before and passes after;
- collection hash and invariant probe remain valid;
- test-only, stale, fork, oversized, and out-of-path patches reject; and
- Devin never receives publisher credentials.

## 19. Five-minute implementation demo

```text
1. Replay the saved failed workflow event.
2. Show the exact immutable inputs and failing pytest argv.
3. Show one persisted investigator request and validated diagnosis.
4. Replay the same event and show the same run ID with no extra calls.
5. Inject malformed output and show the fail-closed terminal state.
6. In the live phase, open the single GitHub Check.
7. Authorize repair and show the controller-owned fail-before/pass-after proof.
```

The demo should foreground state, evidence, and policy decisions rather than a
chat transcript.

## 20. Resolved design gaps

| Gap in the technical specification | Implementation decision |
|---|---|
| Product code location was unspecified. | Standalone `takehome/ci_rescue` package. |
| First implementation scope was too broad. | Offline diagnosis vertical slice, then live diagnosis, then repair. |
| `patch_ref` ownership was unspecified. | Bounded inline unified diff, persisted by the controller. |
| API versions and status vocabularies were mixed. | Organization-scoped v3 adapter with one normalized status mapper. |
| Devin write isolation relied on prompts. | Dedicated read-only Devin identity/integration; separate controller writer token. |
| SQLite concurrency behavior was implicit. | Single demo worker, unique keys, immediate transactions, versioned transitions. |
| Webhook work could exceed request lifetime. | Intake persists and returns `202`; worker advances the run. |
| Live services were required too early. | Fake adapters and saved fixtures are first-class and credential-free. |

These decisions make the next pull request small enough to review while keeping
the architecture on the path to the full pilot.
