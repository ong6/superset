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

Regenerate the dashboard title OpenAPI description

## Symptom

The dashboard title schema description changed without updating the committed OpenAPI
artifact, so the drift check fails.

## Repro

```bash
SUPERSET__SQLALCHEMY_DATABASE_URI='sqlite:///:memory:' \
  FLASK_APP='superset.app:create_app()' \
  superset update-api-docs
git diff --exit-code -- docs/static/resources/openapi.json
```

## Expected

The generated OpenAPI artifact matches the dashboard schema and the drift check passes.

CI check: `check-openapi-spec-drift`

## Allowed paths

- `superset/dashboards/schemas.py`
- `docs/static/resources/openapi.json`

## Forbidden

- Tests, CI workflows, requirements, and all paths not listed above.
- Reverting the intended schema wording, force-pushing, or merging.

## Acceptance command

```bash
SUPERSET__SQLALCHEMY_DATABASE_URI='sqlite:///:memory:' \
  FLASK_APP='superset.app:create_app()' \
  superset update-api-docs
git diff --exit-code -- docs/static/resources/openapi.json
```
