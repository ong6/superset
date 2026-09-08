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

Restore safe downgrade ordering for tables deleted_at

## Symptom

The tables soft-delete migration removes `deleted_at` before its index during downgrade,
which fails on databases that require the index to be removed first.

## Repro

```bash
pytest -q tests/unit_tests/migrations/test_add_deleted_at_to_tables.py
```

## Expected

Downgrade removes the index before the column and the `Python-Unit` check passes.

CI check: `Python-Unit`

## Allowed paths

- `superset/migrations/versions/2026-05-08_12-10_3a8e6f2c1b95_add_deleted_at_to_tables.py`

## Forbidden

- Tests, CI workflows, requirements, generated files, and all paths not listed above.
- Skipping migration checks, force-pushing, or merging.

## Acceptance command

```bash
pytest -q tests/unit_tests/migrations/test_add_deleted_at_to_tables.py
```
