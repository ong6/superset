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

The FDE proposal turns suitable issues into useful engineering capacity through
one bounded path inside GitHub. Maintainers authorize work, receive a scoped PR
with deterministic evidence, and keep review and merge authority.

The reviewed implementation in [#51](https://github.com/ong6/superset/pull/51)
adds a living status report. It reconstructs available terminal controller
comments from GitHub, reads the current PR state, and optionally reconciles
tagged Devin sessions
([code](https://github.com/ong6/superset/blob/3a46b45ef7ed88233ec8a8ba05fa4fbb10b45e13/devin-issue-autopilot/autopilot/engine.py#L969-L1048)).
It reports CI/policy-ready-for-review, merged, and verified-and-merged as
separate measures
([code](https://github.com/ong6/superset/blob/3a46b45ef7ed88233ec8a8ba05fa4fbb10b45e13/devin-issue-autopilot/autopilot/engine.py#L1377-L1456)).

## HOW

```text
reproduced issue
  -> readiness brief proposes paths, acceptance command, and CI check
  -> maintainer authorizes a fix
  -> controller validates, claims, and pins the request
  -> Devin API creates one bounded session
  -> session investigates and opens one scoped pull request
  -> controller verifies the PR head, policy, linkage, and named CI
  -> GitHub records "Ready for review"
  -> living report tracks later merge status separately
```

### Three architectural decisions

1. **Claim once before paying for work.** The workflow
   [serializes each issue](https://github.com/ong6/superset/blob/3a46b45ef7ed88233ec8a8ba05fa4fbb10b45e13/.github/workflows/devin-issue-autopilot.yml#L44-L46),
   derives an idempotency key from the issue, purpose, and request time, checks
   the terminal marker, and acquires a claim label before session creation.
   Duplicate deliveries return without starting a second paid session
   ([code](https://github.com/ong6/superset/blob/3a46b45ef7ed88233ec8a8ba05fa4fbb10b45e13/.github/workflows/devin-issue-autopilot.yml#L256-L292)).
2. **Treat Devin output as a proposal.** Devin must return structured output.
   The controller resolves the PR, checks the closing reference, pinned base
   SHA, allowed paths, and named CI result on the PR head SHA. Passing those
   checks means ready for maintainer review; it does not mean merged
   ([code](https://github.com/ong6/superset/blob/3a46b45ef7ed88233ec8a8ba05fa4fbb10b45e13/devin-issue-autopilot/autopilot/engine.py#L349-L390)).
3. **Bound the recovery loop.** Remediation sessions have a
   [4-ACU API limit](https://github.com/ong6/superset/blob/3a46b45ef7ed88233ec8a8ba05fa4fbb10b45e13/devin-issue-autopilot/autopilot/adapters.py#L176-L193);
   the controller sends
   [one nudge and cancels after 40 minutes](https://github.com/ong6/superset/blob/3a46b45ef7ed88233ec8a8ba05fa4fbb10b45e13/devin-issue-autopilot/autopilot/engine.py#L254-L280).

The report rebuilds a runner-local SQLite cache from GitHub evidence
([code](https://github.com/ong6/superset/blob/3a46b45ef7ed88233ec8a8ba05fa4fbb10b45e13/devin-issue-autopilot/autopilot/store.py#L227-L280)).
The cache is disposable, and the configured daily gate is not durable
organization-wide spend enforcement. Default customer-facing reports omit raw
usage
([code](https://github.com/ong6/superset/blob/223f3e587356a4f9ae67700110c535c4fc8f3e46/devin-issue-autopilot/autopilot/engine.py#L1380-L1471)).

### Live evidence

Evidence snapshot: **2026-09-10 06:17 UTC**.

| Issue | Role | API session | PR | Acceptance / CI | Controller | Merge | Elapsed |
|---|---|---|---|---|---|---|---:|
| [#13](https://github.com/ong6/superset/issues/13) | README smoke | [session](https://app.devin.ai/sessions/4ece9ef53c7d4d5bbcba6613daa166dd) | [#14](https://github.com/ong6/superset/pull/14) | Doctest and CI passed | Ready for review (`verified`) | Merged | 553s |
| [#48](https://github.com/ong6/superset/issues/48) | Real report limits defect | [session](https://app.devin.ai/sessions/6008929ca38344338baa7d628362d29e) | [#53](https://github.com/ong6/superset/pull/53) | Full-environment regression: baseline 15 failed/14 passed; head 29 passed | Waiting for `unit-tests (current)` | Open | Pending |
| [#49](https://github.com/ong6/superset/issues/49) | Fresh live candidate | Not started | None | Preserved open with `devin-exclude` | Not started | None | N/A |

[#13/#14](https://github.com/ong6/superset/issues/13) proves the API-to-PR
wiring with a README doctest. It is smoke evidence, not substantive Superset
repair capacity. Issue #48 provides a real generated repair and local red/green
evidence, but remains unverified until the named CI check and controller finish.
Issue #49 remains excluded and untouched for the presenter-initiated live
request.

## WHY

A script can route labels and run known commands. The engineering work is
turning observed behavior into a safe remediation contract, tracing the cause,
making the smallest change, and explaining uncertainty.

The adversarial examples show the boundary. [#34](https://github.com/ong6/superset/issues/34)
was refused when triage could not produce a complete contract.
[#35](https://github.com/ong6/superset/issues/35) asked for the missing
dashboard, environment, expected behavior, reproduction, and evidence.
[#36](https://github.com/ong6/superset/issues/36) was refused because its
proposed CI check was outside policy.

The two real pilot issues require repository semantics. [#48](https://github.com/ong6/superset/issues/48)
connects non-finite configuration values to later Celery timeout construction
and reserve arithmetic. [#49](https://github.com/ong6/superset/issues/49)
traces negative and fractional `queryLimit` values through two schemas, a
maximum-limit sentinel, and raw request reuse.

Both have narrow paths and deterministic acceptance commands. That makes them a
credible bounded pilot: the defects are real, the proof is fast, and every
controller rejection remains inspectable. Their business impact is stated in
the issues; saved maintainer time remains a hypothesis until the pilot measures
it.

## WHEN

### Pilot ask

Authorize **10 maintainer-approved real issues over 30 days** in this repository.
The Superset maintainer owns issue selection, review, and merge; the FDE owns
workflow operation, evidence quality, and weekly failure review. Record a
comparable manual baseline before counting capacity gains.

Measure:

- authorization-to-reviewable-PR time;
- maintainer minutes spent per issue;
- CI/policy-ready-for-review, merged, and verified-and-merged rates;
- acceptance failures and policy rejection reasons;
- duplicate, timeout, cancellation, stale-SHA, and escalation behavior.

Pause on any unauthorized path, duplicate paid session, secret exposure, or two
consecutive unusable PRs. Expand only after the cohort meets customer-agreed
quality, capacity, bounded-execution, and security gates. Reduced maintainer
effort and higher useful throughput are value hypotheses until those
measurements exist.

After the pilot, native Devin Automations can be an optional event trigger.
Further customer delivery can add repository security profiles, team-specific
execution caps and escalation owners, sandboxed verification, and a queue only
when measured volume requires it.
