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

# Architecture Map

This directory contains an Archify-generated system overview for Apache
Superset.

## Files

| File | Purpose |
|---|---|
| `superset.architecture.json` | Authored Archify architecture specification. |
| `superset-architecture.visual-check.json` | Automated browser evidence receipt. |
| `superset-architecture.visual-check.html` | Contact sheet for generated evidence screenshots. |
| `superset-architecture.visual-check.*.png` | Light/dark screenshots captured by Archify. |

The generated interactive HTML artifact is a large reproducible bundle. It was
produced during discovery and can be regenerated from the checked-in JSON source
with the `deliver` command below.

## What the diagram shows

The map intentionally stays at the system level. It highlights:

- browser users and the reverse proxy/frontdoor;
- React/TypeScript frontend assets and product routes;
- the Flask/Flask-AppBuilder API and command layer;
- the metadata database boundary;
- external analytical databases;
- cache/results storage;
- Redis-style broker and Pub/Sub behavior;
- Celery workers and Celery beat;
- the optional WebSocket service for realtime task updates;
- representative failure surfaces, including Alembic migration correctness.

Guided views focus the audience on the interactive query path, metadata and
caching, asynchronous execution, and realtime status updates.

The diagram was produced during codebase discovery, before the automation ideas
were re-ranked for engineering-team adoption. Its migration callout should be
read as one technically strong specialized use case. The selected first
automation is the PR CI Rescue Autopilot described in the parent take-home
documents, which operates outside the product runtime and can later route
migration failures into a dedicated rehearsal.

## Generation procedure

The Archify package was checked out separately at `tt-a1i/archify`, and the
`architecture` diagram type was selected after running its guide for this
scenario.

```bash
SUPERSET_REPO=/path/to/superset

node bin/archify.mjs validate architecture \
  "$SUPERSET_REPO/takehome/architecture/superset.architecture.json" \
  --quality showcase --json

node bin/archify.mjs deliver architecture \
  "$SUPERSET_REPO/takehome/architecture/superset.architecture.json" \
  "$SUPERSET_REPO/takehome/architecture/superset-architecture.html" \
  --quality showcase --json

node bin/archify.mjs visual-check \
  "$SUPERSET_REPO/takehome/architecture/superset-architecture.html" \
  --json
```

## Verification

Deterministic validation passed with the showcase profile:

- 9 of 9 layout/render checks passed;
- composition status: `pass`;
- errors: 0;
- warnings: 0.

Automated browser evidence also passed:

- containment passed at 1440×900, 1600×1000, 1920×1080, and 2048×1320;
- readability passed in light and dark captures;
- viewer chrome and generated screenshot capture passed;
- diagnostics: none.

Perceptual review was performed by opening the generated HTML artifact in
Chrome and inspecting the default overview plus the asynchronous-execution
guided view. The diagram was legible, the guided view controls worked, the
primary paths were visible, and the explanatory cards rendered below the
diagram.
