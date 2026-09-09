<!--
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.
-->

# Live Remediation Record

The integration owner is responsible for the pinned runs. Keep `master` stable
while each controller verification is active; a changed target produces
`stale_sha`. Review and merge are separate maintainer decisions after a
CI/policy-ready-for-review outcome.

## Boundaries

- [#46](https://github.com/ong6/superset/pull/46) restores the testable
  baseline. It is setup evidence, not an API-remediation success.
- [#47](https://github.com/ong6/superset/pull/47) implements the reconstructed
  living-status report. It is product evidence, not a repaired customer issue.
- Issues #42 and #44 are synthetic setup fixtures.
- [#13/#14](https://github.com/ong6/superset/issues/13) is README smoke
  evidence.

## Current real issues

At the **2026-09-09 18:34 UTC** snapshot, both issues were filed with
`devin-exclude`; filing did not trigger a run.

### 1. Issue #48: scheduled-report execution limits

- Issue: [#48](https://github.com/ong6/superset/issues/48)
- Allowed paths: `superset/utils/report_execution.py` and its unit test
- Acceptance:
  `pytest -q tests/unit_tests/utils/test_report_execution.py -k non_finite`
- Named CI: `unit-tests (current)`
- API session, PR, acceptance output, CI result, and controller outcome: pending

### 2. Issue #49: SQL Lab query limits

- Issue: [#49](https://github.com/ong6/superset/issues/49)
- Allowed paths: the two SQL Lab schema modules and their unit test
- Acceptance:
  `pytest -q tests/unit_tests/sqllab/test_schemas.py -k query_limit`
- Named CI: `unit-tests (current)`
- API session, PR, acceptance output, CI result, and controller outcome: pending

## Evidence capture

For each run, preserve the request key and pinned target SHA, Devin API session
URL, generated PR and head SHA, acceptance output, named CI result, terminal
controller comment, current merge state, elapsed time, and raw ACUs when
reported. Keep missing values as `pending` or `unknown`; reported zero usage
does not establish free work.
