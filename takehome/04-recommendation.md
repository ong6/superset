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

# Recommendation and Next Steps

## Document role

The product decision remains GitHub issue remediation. The working take-home
is the standalone polling controller in
[`devin-issue-autopilot/`](../devin-issue-autopilot/README.md), triggered by
`devin-fix`. This document describes the stronger production-hardening target;
references to Actions, immutable preflight, patch-only Devin access, a clean
verifier, and a controlled writer are not claims about the current slice.

## Selected product: GitHub Issue Remediation Runner

Build a maintainer-authorized GitHub automation that turns one repository issue
into one deterministic reproduction, one bounded Devin patch proposal, one
clean-room verification, one controlled pull request, independently verified
CI, and a visible terminal outcome on the issue.

This is the best first implementation because it matches the original
take-home goal directly:

- the trigger is a real issue in the target repository;
- the authorization is a normal maintainer label;
- Devin performs the repository-scale investigation and proposes the code
  change;
- a controlled writer publishes only after independent verification;
- clean-room acceptance and repository CI provide deterministic proof; and
- status, failure, and success remain visible in GitHub.

The implemented reviewer path is in
[Devin Issue Autopilot](../devin-issue-autopilot/README.md). The complete
hardening plan is in
[GitHub Issue Remediation Automation](09-github-issue-remediation-implementation.md).

## Problem statement

A GitHub issue describes a desired change, but accepted issues still require a
maintainer or contributor to:

1. understand whether the report is correct and sufficiently scoped;
2. locate the relevant code and repository instructions;
3. reproduce the behavior;
4. select a minimal implementation;
5. add or update tests;
6. run repository checks;
7. open a reviewable pull request; and
8. communicate progress or blockers.

Devin is useful because these steps require repository-scale reasoning and tool
use rather than a fixed string-to-command mapping. The surrounding automation
must still own authorization, state, deadlines, publication, and the
independent success claim.

## Product boundary

The first version supports:

- one configured repository;
- one open issue;
- one strict, machine-readable issue contract;
- one `devin-fix` authorization label;
- one active remediation generation;
- one configured Devin playbook;
- one pinned target SHA and clean preflight;
- one bounded, read-only Devin session;
- one clean verifier and controlled writer;
- one linked pull request; and
- one configured set of required GitHub checks.

It does not run on every public issue, write to the default branch, merge,
approve, bypass protection, pass publisher credentials to Devin, or claim
success from session status alone.

## Production-hardening architecture decision

Use **GitHub Actions dispatcher plus scheduled reconciler** for the hardened
pilot.

```text
issues.labeled(`devin-fix`)
  -> validate contract, authorize, pin SHA, and reproduce
  -> claim
  -> create Devin session
  -> publish queued/running state

schedule / workflow_dispatch
  -> poll session
  -> validate structured patch
  -> clean-room policy and acceptance verification
  -> recheck target SHA and publish one PR
  -> read required checks
  -> publish terminal outcome
```

This is stronger than a one-shot workflow because a Devin session outlives the
dispatcher. It is faster to deliver than a custom public webhook controller
because GitHub supplies event delivery, identity, permissions, scheduling,
logs, summaries, artifacts, and the user-facing issue and PR surfaces.

Use a small Python package for orchestration rather than embedding state
decisions in shell and YAML. The same package runs with fake adapters in Docker
for deterministic replay.

## Why the take-home starts with a standalone controller

A GitHub App, database, queue, and workers are the correct production shape
when the system spans many repositories or requires immediate callbacks and
centralized analytics. They are not prerequisites for proving one
issue-to-remediation loop.

The implemented controller uses 30-second issue polling, SQLite state,
bounded Devin sessions, PR path policy, named CI verification, issue comments
and labels, and a durable report. It is intentionally deploy-free and can be
replayed without credentials.

The next hardening step can move orchestration into an Actions dispatcher and
scheduled reconciler with:

- per-issue concurrency;
- durable state in one versioned issue comment;
- API and domain idempotency;
- scheduled restart recovery;
- timeout and cancellation;
- independent PR verification;
- structured artifacts; and
- a production migration threshold.

## Trigger and authorization

Trigger only when a maintainer applies `devin-fix`. Do not automatically send
all newly opened public issues to Devin.

The dispatcher validates:

- repository ID and kill switch;
- issue state and type;
- exact label;
- actor permission resolved through the GitHub API;
- strict contract fields, command IDs, allowed paths, and risk tier;
- immutable target SHA and deterministic preflight evidence;
- absence of another active generation; and
- the versioned state record after claiming it.

A trusted issue form may auto-apply the label later. That expansion should
follow measured quality, cost, and failure handling.

## Devin API

Use the current organization-scoped v3 lifecycle consistently:

```text
POST   /v3/organizations/{org_id}/sessions
GET    /v3/organizations/{org_id}/sessions
GET    /v3/organizations/{org_id}/sessions/{devin_id}
DELETE /v3/organizations/{org_id}/sessions/{devin_id}
```

The create request should:

- set a positive `max_acu_limit`;
- select one reviewed `playbook_id`;
- restrict `repos` to `ong6/superset`;
- pass explicit empty secret and knowledge lists by default;
- set `resumable: false`;
- require a versioned, bounded structured-output schema containing outcome,
  summary, unified diff, claimed paths, evidence, and verification commands;
- add repository, issue, generation, workflow, and run-key tags; and
- give the selected Devin identity read-only repository access.

The dispatcher stores the returned session ID and URL immediately. The
reconciler evaluates both `status` and `status_detail`, validates structured
output, and never treats session completion as proof of a correct repair.
`waiting_for_user` and `waiting_for_approval` are unattended
`interaction_required` failures. Because v3 creation has no idempotency field,
an ambiguous create is reconciled by exact unique tags in a bounded recent
session listing; it is never retried blindly.

## State model

```text
requested
  -> validated
  -> authorized
  -> target_pinned
  -> evidence_ready
  -> claimed
  -> creating_session
  -> session_running
  -> proposed
  -> verifying
  -> publishing
  -> pull_request_open
  -> ci_verifying
  -> succeeded
```

Visible nonterminal states:

```text
cancelling
```

Visible terminal outcomes:

```text
succeeded
duplicate
rejected
no_change
blocked
failed
verification_failed
policy_violation
stale
publish_failed
timed_out
cancelled
```

Track the pull request's later business result independently:

```text
no_pull_request
pull_request_open
ci_green
merged
closed_unmerged
```

This separation avoids false statements such as calling an API `finished`
status a verified remediation or calling an unmerged CI-green PR a business
failure.

## Success and failure

Publish `succeeded` only when:

- one terminal session returned valid structured output;
- its patch applied to a clean checkout at the pinned SHA;
- Git-derived paths and file modes passed policy;
- controller-owned acceptance commands passed;
- the target branch still matched the pinned SHA before publication;
- the controlled writer produced one valid linked PR;
- the PR is in the configured repository and targets the configured branch;
- its head SHA is stable;
- the issue link is present;
- policy inspection did not reject the diff; and
- every configured required check passed.

Failures use bounded machine-readable reasons:

- invalid or unauthorized event;
- invalid issue contract or failed reproduction;
- duplicate generation;
- API create rejected or ambiguous;
- API polling exhausted;
- interaction required, suspended, or malformed structured output;
- no proposal, patch application, policy, verification, or stale-SHA failure;
- controlled publication failure;
- invalid PR;
- required check failed or missing;
- timeout;
- user cancellation; or
- unsupported API status.

The status comment should include the next operator action for recoverable
states.

## Idempotency and recovery

Define:

```text
run_key =
  github:{repository_id}:issue:{issue_node_id}:generation:{generation}
```

Use four defenses:

1. an Actions concurrency group per issue;
2. one durable hidden state record in the issue status comment;
3. unique v3 session tags and no blind ambiguous-create retry; and
4. idempotent reconciliation that updates existing labels and comments.

Do not blindly retry an ambiguous session create. Query by unique tags first,
then require an operator decision if the API cannot prove whether creation
succeeded.

Scheduled reconciliation is restart recovery. It resumes from the stored
session ID, Devin state, proposal or published PR, and GitHub checks after any
Actions job exits or fails.

## Security

- Treat issue text, repository content, session output, and PR metadata as
  untrusted.
- Keep `DEVIN_API_TOKEN`, `GITHUB_TOKEN`, and publisher credentials in Actions
  only.
- Give the workflow the minimum GitHub permissions for its current phase.
- Give Devin no organization secrets by default.
- Give Devin read-only repository access and require structured patch output.
- Build prompts from parsed event data; never interpolate issue text into a
  shell script.
- Apply the patch in a fresh checkout at the pinned SHA, derive changed paths
  from Git, and run only allowlisted argv commands.
- Re-resolve the target SHA immediately before publication.
- Let a controlled writer mint a short-lived GitHub App installation token
  only after verification, then create or update the bot branch and PR.
- Protect the default branch and require review and CI.
- Validate the published PR before monitoring or publishing success.
- Revoke work when the issue closes or authorization is removed.
- Pin third-party Actions by full commit SHA.
- Bound prompt, issue text, retries, ACU, wall clock, and active runs.
- Provide a repository-variable kill switch.

## Observability

The user-facing status is one issue comment plus one status label. The comment
shows:

- current phase and last update;
- session and pull-request links;
- target SHA, evidence hash, patch hash, and policy version;
- preflight and clean-room verification result;
- required-check progress;
- elapsed time;
- terminal outcome and reason; and
- run key and generation.

Each Actions execution also emits:

- a step summary;
- structured redacted logs;
- a versioned `run.json` transition artifact; and
- an explicit success, retryable failure, permanent failure, or no-op exit.

The aggregate pilot report covers:

- authorized issues, sessions, PRs, CI-green PRs, and merges;
- active runs and oldest active age;
- duplicates, blocks, failures, timeouts, and cancellations;
- issue-to-session, issue-to-PR, and issue-to-green latency;
- invalid or CI-failing PRs;
- ACU per session and CI-green PR; and
- missing cost or usage data as an explicit unknown.

Initial safety objectives:

- zero duplicate sessions per run key;
- zero unauthorized default-branch writes;
- zero CI-red or invalid PRs marked successful;
- zero active runs older than twice their deadline; and
- visible issue status within two minutes of authorization.

## Pilot rollout

### Stage 0: local replay

Run saved issue, session, PR, check, duplicate, timeout, and cancellation
fixtures through Docker with fake adapters.

### Stage 1: live dry run

The label creates a status record and validates configuration but does not call
Devin.

### Stage 2: live session, read-only repository access

Devin investigates and returns bounded structured output, but cannot publish a
branch.

### Stage 3: clean verification and controlled publication

The controller verifies the patch, rechecks the target SHA, and lets the
controlled writer open the PR. GitHub CI and human review remain mandatory.

### Stage 4: broader intake

Only after pilot gates pass, add trusted issue forms, more repositories, or
new triggers such as failed CI, rebase conflicts, and release backports.

## Stop conditions

Disable new dispatch immediately when:

- a duplicate session is created for one run key;
- a workflow or session attempts an unauthorized write;
- an invalid or CI-red PR is marked successful;
- secret material appears in logs or artifacts;
- API status changes fail closed repeatedly; or
- the oldest active run exceeds twice its configured deadline.

Existing sessions may be reconciled or cancelled while the dispatch kill switch
is active.

## Demo fixture

Use one honest Superset issue with:

- a reproducible, narrowly scoped defect;
- clear expected behavior;
- a strict contract with controller-owned reproduction and acceptance command
  IDs;
- one focused failing test;
- one low-risk allowed-path set;
- a small production-code repair; and
- normal repository CI coverage.

Demo:

1. apply `devin-fix`;
2. show queued and running status;
3. show exactly one linked session;
4. show the structured patch and clean verifier pass;
5. show the controlled remediation PR;
6. show required CI turn green;
7. show the issue outcome become `succeeded`;
8. replay the label event and show no duplicate; and
9. show one stale, cancelled, or verification-failed fixture with an
   actionable terminal reason.

## Implementation order

1. Build the typed local controller and fixtures.
2. Add dispatch, reconcile, cancel, and report workflows.
3. Configure the Devin API token and organization ID, playbook, read-only
   service identity, publisher identity, labels, command policy, required
   checks, and kill switch.
4. Run dry mode and failure-path tests.
5. Enable one scoped remediation issue.
6. Capture the success and non-success run artifacts.
7. Review pilot outcomes before enabling additional issues or triggers.

## Expansion path

Failed-check repair remains a strong second trigger after the issue loop works.
It can reuse:

- authorization and policy;
- session creation and polling;
- state and failure taxonomy;
- status rendering;
- retry, timeout, cancellation, and kill switch;
- PR validation and independent CI proof; and
- metrics and reporting.

Move the coordinator to an external GitHub App controller when repository count,
event volume, reconciliation latency, central audit retention, or policy
complexity exceed the Actions-native pilot.
