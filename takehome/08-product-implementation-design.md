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

# Future Extension: PR CI Rescue Product Implementation Design

## Document role

The selected first implementation is the
[GitHub Issue Remediation Runner](09-github-issue-remediation-implementation.md).
This design is retained as a hardened future adapter for automatic
pull-request CI repair. It preserves the stronger delivery, attempt,
failure-claim, isolated-source, lost-response, and publishing contracts added
after the original CI-rescue review.

## 1. Future CI-rescue decision

Implement PR CI Rescue as a small standalone Python service under
`takehome/ci_rescue/`, not inside the Superset Flask application.

That location is for the take-home pilot. Before live diagnosis is operated as
a production service, the controller should move to a separately owned
repository and deployment boundary so its GitHub App, database, release
cadence, and incident response are not coupled to the repository it repairs.

The service is a modular monolith with:

- one HTTP process that validates and records GitHub events;
- one worker that advances persisted runs through an explicit state machine;
- SQLite and fake adapters for the credential-free demo;
- PostgreSQL and live GitHub/Devin adapters behind the same interfaces; and
- isolated replay and verification sandboxes owned by the controller.

The first CI-extension pull request should deliver an **offline vertical slice
through read-only diagnosis**. It should prove event validation,
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

## 3. First CI-extension pull request

### Included

The first CI-extension pull request accepts one saved normalized
workflow-attempt envelope plus a fixture `Event File` representing:

- the configured `ong6/superset` repository;
- the `Python-Unit` workflow;
- one open same-repository pull request;
- one immutable head SHA;
- one failed JUnit test with an exact pytest node; and
- the report-execution equality-boundary regression.

Running the replay command must:

1. validate the fixture with strict typed schemas;
2. atomically claim the delivery and workflow attempt;
3. ingest the credential-free evidence bundle;
4. derive the versioned failure identity from canonical evidence;
5. atomically create or attach to one canonical rescue run;
6. suppress duplicate delivery and equivalent-failure side effects;
7. select a fixed argv array for the exact pytest node;
8. record a deterministic failing replay result from the fixture adapter;
9. create one fake investigator session;
10. validate the investigator output against the versioned schema;
11. upsert one fake Check payload; and
12. export the workflow-attempt and canonical-run timelines as JSON.

### Acceptance commands

The Milestone 1 public interface is:

```bash
cd takehome/ci_rescue

python -m ci_rescue replay \
  --event fixtures/normalized_workflow_attempt.json \
  --database .ci-rescue/demo.db

python -m ci_rescue show-run <run_id> --database .ci-rescue/demo.db

pytest -q tests
```

The first command exits successfully only when the canonical run reaches
`completed` with terminal reason `diagnosis_only`. Replaying the same delivery
prints the existing `attempt_id` and `run_id` and creates no additional
session or Check. A distinct workflow rerun with the same versioned failure
identity creates a new attempt that attaches to the existing run.

### Excluded

- no public webhook endpoint exposed to GitHub;
- no live Devin session;
- no GitHub App token;
- no branch write or companion pull request;
- no `/devin fix` command;
- no arbitrary command execution;
- no Docker-in-Docker sandbox; and
- no broad Python-unit log parser.

These exclusions make the first CI-extension pull request deterministic and
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
│   ├── normalized_workflow_attempt.json
│   ├── event_file_ready_for_review.json
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
produces a strict intake model, then an eligible-failure model after parsing the
uploaded source event. `delivery_id` is a bounded opaque provider identifier
rather than an assumed UUID. `base_sha` is the exact
provider-resolved `pull_request.base.sha` recorded during acceptance; it is not
the moving base branch head or a merge-base.

```python
ProviderDeliveryId = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
]


class NormalizedWorkflowAttempt(BaseModel):
    schema_version: Literal["ci-rescue-event/v1"]
    provider: Literal["github"]
    repository_id: int
    repository_full_name: str
    installation_id: int
    delivery_id: ProviderDeliveryId
    event_name: Literal["workflow_run"]
    event_action: Literal["completed"]
    workflow_run_id: int
    workflow_name: Literal["Python-Unit"]
    workflow_conclusion: Literal["failure"]
    workflow_completed_at: datetime
    pull_request_number: int
    intake_pull_request_state: Literal["open", "closed"]
    intake_pull_request_draft: bool
    head_sha: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
    base_sha: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
    head_ref: str
    base_ref: str
    is_fork: bool
    workflow_actor_login: str


class NormalizedFailedRun(NormalizedWorkflowAttempt):
    source_event_name: Literal["pull_request"]
    source_pull_request_action: Literal[
        "opened",
        "reopened",
        "ready_for_review",
        "synchronize",
    ]
    source_pull_request_draft: bool
    source_head_sha: Annotated[
        str,
        StringConstraints(pattern=r"^[0-9a-f]{40}$"),
    ]
    live_pull_request_state: Literal["open"]
    live_pull_request_draft: bool
```

Unknown fields should be rejected at every trust boundary. Provider-specific
extra data can be retained as a hashed artifact but cannot silently affect
domain decisions. `workflow_actor_login` is audit metadata only and never
authorizes repair.

Repair authorization has a separate event contract because the authorizing
principal is the issue commenter or label actor, not the actor associated with
the failed workflow:

```python
class RepairAuthorizationRequest(BaseModel):
    schema_version: Literal["ci-rescue-authorization/v1"]
    provider: Literal["github"]
    repository_id: int
    delivery_id: ProviderDeliveryId
    event_name: Literal["issue_comment", "pull_request"]
    event_action: Literal["created", "labeled"]
    run_id: UUID
    pull_request_number: int
    authorized_head_sha: Annotated[
        str,
        StringConstraints(pattern=r"^[0-9a-f]{40}$"),
    ]
    actor_login: str
    method: Literal["fix_comment", "protected_label"]
    requested_at: datetime
```

Cross-field validation permits only
`issue_comment/created/fix_comment` and
`pull_request/labeled/protected_label`.
The controller resolves the authorization event and actor permission through
the provider API, then binds the authorization to the run, failure key, PR,
head SHA, method, scope, and expiry. A head change, draft conversion, closure,
or expiry invalidates it.

### Stable keys

```text
delivery_key =
  github:{repository_id}:{delivery_id}

attempt_key =
  github:{repository_id}:workflow_run:{workflow_run_id}

failure_key =
  github:{repository_id}:pr:{pull_request_number}:sha:{head_sha}:
  job:{job_logical_key}:fp:{failure_fingerprint}
```

The delivery and attempt keys are available at intake. The failure key is not:
`job_logical_key` and `failure_fingerprint` come from normalized evidence.
Claiming therefore has two durable stages:

1. atomically claim `delivery_key` and `attempt_key`, returning the existing
   attempt for a provider retry;
2. collect and normalize evidence without an external side effect;
3. derive the versioned `FailureIdentity`;
4. atomically insert or select the canonical run by `failure_key`; and
5. attach the attempt and delivery to that run before any replay, Devin, or
   publishing side effect.

A reused delivery or attempt key with a different payload hash or immutable
identity is rejected and alerted as a provider-correlation collision.

A concurrent equivalent workflow rerun may perform bounded evidence collection,
but only the canonical run owner advances beyond attachment. Key construction
is a pure function with fixed canonicalization and candidate-ordering rules.
The key and fingerprint versions are stored separately so new algorithms can
coexist with earlier runs.

### Controller-owned lifecycle

Devin outputs classifications and proposals. The controller owns lifecycle,
completion, and duplicate disposition:

```python
class RunState(StrEnum):
    EVIDENCE_READY = "evidence_ready"
    REPLAYING_FAILURE = "replaying_failure"
    FAILURE_REPRODUCED = "failure_reproduced"
    INVESTIGATION_SESSION_PENDING = "investigation_session_pending"
    INVESTIGATION_SESSION_RUNNING = "investigation_session_running"
    DIAGNOSIS_READY = "diagnosis_ready"
    PUBLISHING_DIAGNOSIS = "publishing_diagnosis"
    DIAGNOSIS_PUBLISHED = "diagnosis_published"
    AWAITING_REPAIR_AUTHORIZATION = "awaiting_repair_authorization"
    REPAIR_AUTHORIZED = "repair_authorized"
    REMEDIATION_SESSION_PENDING = "remediation_session_pending"
    REMEDIATION_SESSION_RUNNING = "remediation_session_running"
    PATCH_PROPOSED = "patch_proposed"
    POLICY_CHECKING = "policy_checking"
    VERIFYING = "verifying"
    PUBLISHING_REPAIR = "publishing_repair"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TerminalReason(StrEnum):
    DIAGNOSIS_ONLY = "diagnosis_only"
    REPAIR_PUBLISHED = "repair_published"
    NOT_ACTIONABLE = "not_actionable"
    VALIDATION_FAILED = "validation_failed"
    AUTHORIZATION_FAILED = "authorization_failed"
    AUTHORIZATION_EXPIRED = "authorization_expired"
    INSUFFICIENT_REPLAY_EVIDENCE = "insufficient_replay_evidence"
    REPLAY_FAILED_INFRA = "replay_failed_infra"
    UNRESOLVED = "unresolved"
    DEVIN_API_FAILED = "devin_api_failed"
    INTERACTION_REQUIRED = "interaction_required"
    TIMED_OUT = "timed_out"
    MALFORMED_OUTPUT = "malformed_output"
    STALE_TARGET = "stale_target"
    POLICY_REJECTED = "policy_rejected"
    VERIFICATION_FAILED = "verification_failed"
    PUBLISH_FAILED = "publish_failed"
    CANCELLED = "cancelled"


class DeliveryDisposition(StrEnum):
    ACCEPTED = "accepted"
    DUPLICATE_DELIVERY = "duplicate_delivery"
    DUPLICATE_ATTEMPT = "duplicate_attempt"
    ATTACHED_TO_EXISTING_FAILURE = "attached_to_existing_failure"
    SUPPRESSED_DRAFT_ORIGIN = "suppressed_draft_origin"
    SUPPRESSED_CURRENT_DRAFT = "suppressed_current_draft"
    STALE_DELIVERY = "stale_delivery"
    REJECTED = "rejected"
```

`terminal_reason` is null until `state` enters `completed`, `failed`, or
`cancelled`. Duplicate deliveries and equivalent workflow attempts do not
transition the canonical run; they record a delivery disposition and point to
the owning attempt/run. No adapter may set a terminal state directly.

## 7. Ports and ownership

The domain service depends on typed protocols:

```python
class RunStore(Protocol):
    def claim_delivery(
        self,
        event: NormalizedWorkflowAttempt,
        delivery_key: str,
        attempt_key: str,
    ) -> DeliveryClaim: ...
    def claim_failure(
        self,
        attempt_id: UUID,
        identity: FailureIdentity,
    ) -> FailureClaim: ...
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
    def reconcile_check(self, intent: EffectIntent) -> CheckReference | None: ...
    def resolve_head_sha(self, repository_id: int, pull_request: int) -> str: ...
    def resolve_actor_permission(
        self,
        repository_id: int,
        actor_login: str,
    ) -> RepositoryPermission: ...


class DevinGateway(Protocol):
    def create_investigator(self, request: InvestigatorRequest) -> SessionReference: ...
    def create_remediator(self, request: RemediatorRequest) -> SessionReference: ...
    def reconcile_session(
        self,
        intent: EffectIntent,
    ) -> SessionReference | None: ...
    def get_session(self, session_id: str) -> SessionSnapshot: ...
    def terminate_session(self, session_id: str) -> None: ...


class Sandbox(Protocol):
    def replay(self, request: ReplayRequest) -> ReplayResult: ...
    def verify(self, request: VerificationRequest) -> VerificationResult: ...
```

The protocols should be synchronous in the first CI-extension slice. HTTP and
subprocess adapters may use internal async clients later, but making the domain
service async before there is concurrent work would complicate fixture tests
without changing behavior.

## 8. Persisted state

### Minimal Milestone 1 tables

Milestone 1 needs seven tables:

| Table | Purpose |
|---|---|
| `deliveries` | Unique provider delivery claim, payload hash, disposition, and attempt link. |
| `workflow_attempts` | One provider workflow execution, immutable identity hash, lifecycle state, terminal disposition, normalized evidence, and optional canonical-run link. |
| `rescue_runs` | One canonical failure identity and hash with current state, immutable inputs, and schema/policy versions. |
| `state_transitions` | Append-only attempt/run history keyed by aggregate kind and ID. |
| `external_effects` | Pre-committed intent, request hash, provider correlation, response state, and reconciliation result. |
| `devin_sessions` | One reconciled session record per run, role, and bounded attempt. |
| `check_outputs` | Stable fake/live publisher external key and last payload hash. |

Evidence, replay attempts, authorizations, and patches can initially be stored
as typed JSON artifacts referenced from transitions. They should become
dedicated tables when live collection and repair are added.

### Concurrency

SQLite demo mode supports one worker and uses:

- unique indexes on `delivery_key`, `attempt_key`, and `failure_key`;
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

External calls use a transactional-intent pattern:

1. persist an `external_effects` row with deterministic correlation and request
   hash;
2. commit the state transition to a `*_pending` or `publishing_*` state;
3. make the remote call;
4. persist the provider ID and response; and
5. reconcile an unknown result before any retry.

This provides at-least-once transport with controller reconciliation; the
design does not claim that a local transaction can make a remote API exactly
once.

## 9. State machine by milestone

### Workflow-attempt lifecycle

Deliveries and workflow executions progress separately from the canonical
failure run:

```text
received
  -> source_event_collecting
  -> eligibility_checking
  -> evidence_collecting
  -> failure_identity_ready
  -> completed
```

`completed` carries a terminal delivery disposition such as `accepted`,
`attached_to_existing_failure`, `suppressed_draft_origin`,
`suppressed_current_draft`, `stale_delivery`, or `rejected`. Attempt lifecycle
state is never used as disposition, and these outcomes never overwrite the
canonical run.

### Canonical run: Milestone 1

```text
evidence_ready
  -> replaying_failure
  -> failure_reproduced
  -> investigation_session_pending
  -> investigation_session_running
  -> diagnosis_ready
  -> publishing_diagnosis
  -> diagnosis_published
  -> completed (diagnosis_only)
```

Other terminal transitions use:

```text
completed: unresolved, not_actionable
failed: validation_failed, authorization_failed,
  insufficient_replay_evidence, replay_failed_infra, devin_api_failed,
  interaction_required, timed_out, malformed_output, publish_failed
cancelled: cancelled
```

### Milestone 3 additions

```text
diagnosis_published
  -> awaiting_repair_authorization
  -> repair_authorized
  -> remediation_session_pending
  -> remediation_session_running
  -> patch_proposed
  -> policy_checking
  -> verifying
  -> publishing_repair
  -> completed (repair_published)
```

Additional terminal transitions are `completed (authorization_expired)`,
`cancelled (stale_target)`, and `failed` with `authorization_failed`,
`policy_rejected`, or `verification_failed`.

Transition definitions should live in one declarative mapping. Tests should
iterate over the mapping and prove that undeclared transitions reject.

## 10. Pipeline behavior

### Intake and eligibility

Eligibility is the conjunction defined by the ready-for-review cases:

Before evaluating it, the uploaded source event must match the claimed
repository, pull request, workflow event type, and workflow head SHA.

```text
eligible =
  workflow conclusion == failure
  and source event == pull_request
  and source pull_request.draft == false
  and live pull request.state == open
  and live pull_request.draft == false
  and source head SHA == live head SHA
```

A draft-originated failure remains `suppressed_draft_origin`; marking the pull
request ready cannot retroactively activate it. `ready_for_review` must cause a
fresh workflow execution whose failure is independently accepted.

The live HTTP route performs only:

1. request-size, content-type, HMAC, event-name, and delivery-ID validation;
2. strict GitHub payload parsing;
3. provider-resolved event-age, repository, workflow, action, and conclusion
   allowlist checks;
4. trusted API resolution of repository ID, pull request, base SHA, head SHA,
   and the intake PR snapshot;
5. atomic delivery and workflow-attempt claim; and
6. a `202 Accepted` response containing `attempt_id`, intake disposition, and
   a nullable canonical `run_id`.

It cannot claim `failure_key` because the evidence-derived fingerprint is not
available yet. It also cannot prove source-event readiness because that value
is inside the uploaded `Event File`, not the `workflow_run` webhook. It does
not download artifacts, start Devin, or wait for replay.

The worker first downloads and safely parses only the accepted workflow run's
`Event File`, then performs a fresh live PR lookup and evaluates the full gate.
Failure records `suppressed_draft_origin`, `suppressed_current_draft`,
`stale_delivery`, or `rejected` on the attempt and stops before JUnit replay,
Devin, Checks, comments, or write-capable credentials. A passing attempt
becomes `NormalizedFailedRun` and may collect the remaining bounded evidence.

Live state and head SHA are re-resolved before canonical failure attachment,
investigator creation, repair authorization, remediator creation,
verification, and publishing. If a pull request becomes draft after
investigation starts, the controller requests bounded cancellation where
supported, may publish an already validated diagnosis, and refuses every
remediation/write transition.

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

Artifact names, archive entries, XML, test names, output, and the uploaded
`Event File` are untrusted. The collector downloads artifacts only from the
accepted workflow-run ID into a fresh quarantine directory and:

- hashes original artifacts;
- caps compressed bytes, entry count, per-entry bytes, total expanded bytes,
  nesting depth, and compression ratio;
- rejects absolute paths, `..`, NULs, duplicate normalized paths, symlinks,
  hard links, devices, and other non-regular entries before extraction;
- extracts through a controller-owned streaming ZIP reader, never an archive
  shell command;
- parses XML with external entities disabled;
- bounds total bytes and test-case count;
- redacts configured secret patterns;
- canonically sorts actionable failures before selecting one;
- records all candidate node IDs; and
- selects one only when the adapter can prove a canonical test path.

After normalization, the worker derives `FailureIdentity`, atomically attaches
the workflow attempt to the canonical run, and stops if another attempt already
owns that failure. Only the canonical run proceeds to replay.

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

Before `POST`, the worker persists a session intent and transitions to
`investigation_session_pending`. On restart, it reads the persisted intent and
session ID and resumes observation. It must never create a replacement session
merely because a poll or create response timed out.

### Diagnosis publication

`CheckOutput` is rendered from controller records, not from model-authored
Markdown. Model strings are length-limited, escaped, and placed only in
designated fields.

The external key is the failure key. The fake publisher writes one JSON file.
The live publisher sets the Check Run `external_id` to a deterministic,
versioned value derived from the failure key and creates or updates that Check
at the pinned head SHA.

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
- `secret_ids: []`.

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

The v3 create contract does not expose a controller-supplied idempotency key.
Every create request therefore includes deterministic tags for controller
version, run ID, role, request hash, repository ID, failure-key hash, head SHA,
and environment. If the `POST` result is unknown, the adapter uses the v3 list
endpoint filtered by tags, creation window, service user, and repository:

- exactly one matching session is adopted and persisted;
- no match permits one bounded retry using the same intent and aggregate
  budget; and
- multiple matches fail closed, request termination of extras where possible,
  and alert on duplicate side effects.

After the bounded retry, zero remaining matches fail closed. This lost-response
path is covered by contract fixtures. A poll timeout never causes another
create request.

The HTTP adapter should be covered by recorded request/response fixtures, not
tests against the live API. A startup compatibility probe may validate that
configured fields remain accepted before live processing is enabled.

## 12. Read-only Devin environment

Prompt instructions and Devin service-user roles are not repository permission
boundaries. The standard Devin GitHub integration requires repository write
capabilities, so the pilot must not give investigator sessions direct access to
the target `ong6/superset` integration.

The default live investigator source is an ephemeral mirror or source snapshot
created at the pinned SHA. The target repository is not installed for that
identity. The mirror has no upstream credentials or branch protection role,
contains no secrets, and is deleted or rebuilt after its retention window.
Writes inside that isolated mirror are harmless and are never accepted as a
patch or publication.

Live sessions run under a dedicated Devin service identity that has:

- access only to the isolated source mirror/snapshot;
- no pull-request, Checks, Actions, administration, or workflow write access;
- no controller GitHub App private key;
- no publisher installation token;
- no unrelated organization secrets; and
- only the knowledge IDs selected for CI Rescue.

The controller mints separate short-lived GitHub App installation tokens
narrowed to each operation. They are never sent to Devin or mounted in replay
sandboxes. Direct target-repository
access is permitted only if a deployment-time permission probe proves the
effective integration is read-only for contents, Checks, pull requests,
Actions, workflows, and administration. Otherwise startup fails closed.

The remediator uses the same isolated source boundary and returns only a
bounded inline patch. It never pushes from the Devin environment.

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
container. A digest-pinned image and dependency layer are built from the
trusted default branch or a controller-approved lock digest, not from
pull-request-controlled install scripts. Network is disabled before the PR
checkout is exposed to any build backend, import, test collection, or hook.
If the PR package itself must be installed, that step runs after network
disablement in the disposable sandbox.

If offline installation cannot satisfy an adapter, a separate uncredentialed
builder may use only allowlisted package sources, execute with no internal
network access, and export a hashed dependency artifact. The replay sandbox
accepts only that artifact and remains offline; the builder never receives
controller, repository, or cloud credentials.

The container has:

- no network or access to cloud metadata/internal service ranges;
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
controller installation. Enabling comment authorization also adds `Issues:
read`. The controller resolves the authorizing actor's effective permission
with the repository collaborator-permission endpoint, whose current GitHub App
contract requires repository `Metadata: read`; webhook `author_association`,
the workflow actor, labels, and comment text are evidence, not authorization.
The deployment probe verifies the provider's advertised accepted permissions
and fails closed rather than requesting broader organization access by
default.

The App registration may hold the union above, but each installation token is
downscoped: intake and eligibility receive read permissions only; diagnosis
publishing receives `Checks: write` only after eligibility; and repair
publishing receives content/PR write only after authorization and the final
live-state/SHA check.

The controller writes only to a configured `devin/ci-rescue/<run_id>`
bot-branch namespace and never merges.

The Check publisher persists an intent before creation and stores the provider
Check Run ID after success. On an unknown create result, it lists Checks for
the pinned SHA and adopts the unique matching `external_id`; it never searches
by display name or posts a new comment. Zero matches allow one bounded retry;
after that, zero or multiple matches fail closed and alert.

Repair publishing uses the deterministic
`devin/ci-rescue/<run_id>` branch as its correlation key. Before creating a
companion pull request, the publisher reconciles an existing PR by exact head
branch, base branch, repository, and run marker. It never creates a second PR
because a response was lost; unresolved zero or multiple matches after the
bounded retry fail closed.

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
DEVIN_SERVICE_USER_ID=service-user-...
DEVIN_SOURCE_REPOSITORY=<isolated-owner>/<ephemeral-mirror>
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

The R1-R10 matrix in
`takehome/07-ready-for-review-ci-cases.md` is normative and must be implemented
as executable fixtures. R1 and R5 use distinct suppression dispositions; R2
requires a fresh post-`ready_for_review` workflow run; R6 proves concurrent
dedupe; R7 proves SHA scoping; R8 prevents repair after re-drafting; R9 accepts
only fresh CI after reopening; and R10 permits credential-free diagnosis but
never a writer.

| Fixture | Assertion |
|---|---|
| Happy path | One run, one investigator, one Check, complete timeline. |
| Duplicate sequential replay | Existing run returned; no new side effect. |
| Duplicate concurrent replay | Unique constraints permit one owner. |
| Equivalent workflow reruns | Two attempts attach to one failure run and create one investigator. |
| Invalid repository or workflow | Rejected before evidence or session calls. |
| Read authorization denied | Rejected before evidence or session calls. |
| Stale SHA | Provider-resolved SHA mismatch terminates before session creation. |
| Missing pytest node | `insufficient_replay_evidence`. |
| Malicious artifact archive | Traversal, symlink, duplicate path, or expansion limit rejects before extraction. |
| Replay infrastructure failure | No investigator session. |
| Malformed investigator output | `malformed_output`; no diagnosis success. |
| Investigator timeout | Session termination attempted and terminal state persisted. |
| Devin create response lost | Matching tagged session is adopted; no second session is created. |
| Devin reconciliation ambiguous | Multiple matching sessions fail closed and alert. |
| Check create response lost | Matching `external_id` is adopted; no second Check is created. |
| Restart after session creation | Existing session is polled; no second create call. |
| Authorization actor mismatch | Workflow actor cannot authorize a repair requested by another actor. |
| Test-only repair patch | `policy_rejected`. |
| Verification false green | Deleted/renamed test or failed invariant rejects. |
| Untrusted fork authorization | Diagnosis remains; no remediator or writer call. |
| PR create response lost | Existing exact head/base repair PR is adopted. |

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
- fake and HTTP Devin lost-response reconciliation;
- fake and HTTP Check `external_id` reconciliation;
- fake and HTTP repair-PR reconciliation; and
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
- duplicate concurrent deliveries and equivalent workflow reruns create one
  logical run;
- invalid inputs create no session or publisher call; and
- the timeline reaches `completed (diagnosis_only)` through one Check upsert.

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
- duplicate or lost-response paths create no duplicate session or Check.

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
| Production ownership was implicit. | Pilot code stays here; live production operation moves to a separately owned repository and deployment boundary. |
| First CI-extension scope was too broad. | Offline diagnosis vertical slice, then live diagnosis, then repair. |
| Failure identity was claimed before evidence existed. | Claim delivery/attempt at intake; claim the canonical failure only after deterministic evidence normalization. |
| Draft-at-source state was unavailable during webhook intake. | Claim the attempt first, parse the quarantined `Event File`, refresh live PR state, then evaluate R1-R10 eligibility. |
| `patch_ref` ownership was unspecified. | Bounded inline unified diff, persisted by the controller. |
| API versions and status vocabularies were mixed. | Organization-scoped v3 adapter with one normalized status mapper. |
| Remote success with a lost response could duplicate side effects. | Persist effect intent, use deterministic provider correlation, and reconcile before retrying. |
| Devin write isolation relied on prompts. | Target repository is excluded; sessions receive an isolated mirror/snapshot and no publisher credentials. |
| Workflow and authorization actors were conflated. | Repair has a separately claimed event and live repository-permission lookup. |
| Archive and dependency execution limits were implicit. | Streamed quarantine parsing, bounded expansion, offline replay, and uncredentialed dependency materialization are explicit contracts. |
| SQLite concurrency behavior was implicit. | Single demo worker, unique keys, immediate transactions, versioned transitions. |
| Webhook work could exceed request lifetime. | Intake persists and returns `202`; worker advances the run. |
| Live services were required too early. | Fake adapters and saved fixtures are first-class and credential-free. |

These decisions make the next pull request small enough to review while keeping
the architecture on the path to the full pilot.
