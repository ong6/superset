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

# Title

Fix report execution reserve equality validation

## Symptom

Superset accepts a report execution budget whose phase reserves consume the entire
budget, leaving no time for report work.

## Repro

```bash
pytest -q 'tests/unit_tests/utils/test_report_execution.py::test_report_execution_config_rejects_invalid_startup_values[overrides2-must total less]'
```

## Expected

The equality boundary is rejected and the `Python-Unit` check passes.

CI check: `Python-Unit`

## Allowed paths

- `superset/utils/report_execution.py`

## Forbidden

- Tests, CI workflows, requirements, generated files, and all paths not listed above.
- Skipping checks, weakening assertions, force-pushing, or merging.

## Acceptance command

```bash
pytest -q 'tests/unit_tests/utils/test_report_execution.py::test_report_execution_config_rejects_invalid_startup_values[overrides2-must total less]'
```
