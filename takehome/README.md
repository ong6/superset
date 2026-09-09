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

# GitHub Issue Remediation Pilot

## WHAT

**167 open issues.** Apache Superset also received 70 issues in the last 30
days, or **16.3 issues per week**, and its 10 open issues carrying the `#bug`
label have a **2.6-day median age**.

These figures are a GitHub API snapshot taken on **2026-09-09 UTC**. The weekly
rate is `70 / 30 * 7`; pull requests are excluded from the bug-age calculation.

```bash
gh api 'search/issues?q=repo%3Aapache%2Fsuperset+is%3Aissue+is%3Aopen&per_page=1'
gh api 'search/issues?q=repo%3Aapache%2Fsuperset+is%3Aissue+created%3A2026-08-10T13%3A31%3A00Z..2026-09-09T13%3A31%3A00Z&per_page=1'
gh api --paginate --slurp \
  'repos/apache/superset/issues?state=open&labels=%23bug&per_page=100' |
  jq --arg asof '2026-09-09T13:31:00Z' \
  '[add[] | select(has("pull_request") | not) |
    (($asof | fromdateiso8601) - (.created_at | fromdateiso8601)) / 86400] |
   sort | if length % 2 == 1 then .[length / 2 | floor]
   else (.[length / 2 - 1] + .[length / 2]) / 2 end'
```

An accepted issue still costs a maintainer six handoffs before a reviewable PR:
classify the report, close information gaps, define acceptance, find the code,
implement and explain the change, then monitor CI and report the outcome.

The pilot moves those handoffs through one bounded path inside GitHub.
Maintainers authorize work with `/devin fix`, review the resulting PR, and keep
the merge decision. Labels, one durable issue comment, the PR, repository CI,
and a SQLite run record make each decision inspectable.

## HOW

```text
issue opened or reopened
  -> bounded triage and proposed scope
  -> maintainer authorizes a fix
  -> controller validates and claims the request
  -> bounded Devin session investigates and opens one pull request
  -> controller verifies scope, issue linkage, and repository CI
  -> GitHub records the outcome for the maintainer
```

### Three architectural decisions

1. **Claim once before paying for work.** The workflow
   [serializes each issue](https://github.com/ong6/superset/blob/1657bbc21e3f9b4a3abf6aefb504b9f2d70549be/.github/workflows/devin-issue-autopilot.yml#L41-L43),
   derives an idempotency key from the issue, purpose, and request time, checks
   the terminal marker, and acquires a claim label before session creation.
   Duplicate deliveries return without starting a second paid session
   ([code](https://github.com/ong6/superset/blob/1657bbc21e3f9b4a3abf6aefb504b9f2d70549be/.github/workflows/devin-issue-autopilot.yml#L248-L284)).
2. **Treat Devin output as a proposal.** Devin must return structured output.
   The controller resolves the PR itself, checks the closing reference, verifies
   the pinned base SHA and allowed paths, and reads the named CI result from the
   PR head SHA
   ([code](https://github.com/ong6/superset/blob/1657bbc21e3f9b4a3abf6aefb504b9f2d70549be/devin-issue-autopilot/autopilot/engine.py#L261-L360)).
3. **Bound the recovery loop.** Remediation sessions have a
   [4-ACU cap](https://github.com/ong6/superset/blob/1657bbc21e3f9b4a3abf6aefb504b9f2d70549be/devin-issue-autopilot/autopilot/adapters.py#L159-L176);
   the controller sends
   [one nudge and cancels after 40 minutes](https://github.com/ong6/superset/blob/1657bbc21e3f9b4a3abf6aefb504b9f2d70549be/devin-issue-autopilot/autopilot/engine.py#L241-L250).

The controller details live in
[Devin Issue Autopilot](../devin-issue-autopilot/README.md). The checked-in
[system](architecture/issue-autopilot.architecture.json),
[workflow](architecture/issue-autopilot.workflow.json), and
[lifecycle](architecture/issue-autopilot.lifecycle.json) diagrams show the same
boundaries.

### Live evidence

| Issue | Session | PR | CI | Outcome | ACUs | Elapsed |
|---|---|---|---|---|---:|---:|
| [#13](https://github.com/ong6/superset/issues/13) | [4ece9ef5](https://app.devin.ai/sessions/4ece9ef53c7d4d5bbcba6613daa166dd) | [#14](https://github.com/ong6/superset/pull/14) | Passed | Verified | 0.00 | 553s |
| [#31](https://github.com/ong6/superset/issues/31) |  |  |  |  |  |  |
| [#30](https://github.com/ong6/superset/issues/30) |  |  |  |  |  |  |
| [#32](https://github.com/ong6/superset/issues/32) |  |  |  |  |  |  |

## WHY

A script can route labels and run known commands. Triage has to read an
ambiguous report and write a remediation contract: allowed production paths,
one acceptance command, and the CI check that will decide the outcome.

The adversarial examples show the boundary. [#34](https://github.com/ong6/superset/issues/34)
was refused when triage could not produce a complete contract.
[#35](https://github.com/ong6/superset/issues/35) asked for the missing
dashboard, environment, expected behavior, reproduction, and evidence.
[#36](https://github.com/ong6/superset/issues/36) was refused because its
proposed CI check was outside policy.

[#30](https://github.com/ong6/superset/issues/30) also requires repository
semantics. On SQLite, dropping `deleted_at` first makes the batch migration
re-create an index against a missing column. The safe repair drops the index
before the column. A search-and-replace rule cannot choose that order safely
from the symptom alone.

[#31](https://github.com/ong6/superset/issues/31) and
[#32](https://github.com/ong6/superset/issues/32) are small fixes chosen for
determinism: one equality boundary and one doctest continuation error. That is
the right demo surface for a bounded pilot because the acceptance commands are
fast, the allowed paths are narrow, and controller failures remain easy for a
maintainer to inspect.

## WHEN

### Pilot plan

Run the workflow on a small set of maintainer-approved issues in one repository.
Name an owner, record the existing process first, set target thresholds and stop
conditions, and keep authorization, review, and merge with maintainers.

Measure:

- authorization-to-reviewable-PR time;
- maintainer effort before and after automation;
- acceptance and merge rates;
- CI pass rate and policy rejection reasons;
- duplicate, timeout, cancellation, stale-SHA, and escalation behavior; and
- ACUs per accepted outcome.

Expand the issue cohort or repository count after the measured results meet the
agreed gates for quality, cost, security, and maintainer acceptance.

### Deliberately left out

| Pilot boundary | Customer engagement delivery |
|---|---|
| GitHub Actions starts the controller | Use Devin Automations as the event trigger |
| One repository policy | Define security profiles for each repository |
| One daily controller cap | Set per-team ACU caps and escalation owners |
| SQLite generates the report | Feed the report from the Devin metrics API |
| Verification reads GitHub evidence | Run acceptance in a sandboxed verifier |
| Direct processing | Add a queue only when measured volume requires it |
