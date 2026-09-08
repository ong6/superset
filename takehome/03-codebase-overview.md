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

# Superset Codebase Overview

## Executive summary

Superset is a modular analytics platform with a Python/Flask backend and a
React/TypeScript frontend. Its primary job is to translate authenticated user
intent into governed queries against external analytical databases, then turn
the results into charts, dashboards, exports, alerts, and reports.

The metadata plane and data plane are deliberately separate:

- the **metadata database** stores users, roles, database connections, datasets,
  chart and dashboard definitions, query history, and operational state;
- the **analytical databases** execute the user-facing SQL and remain the
  systems of record for business data.

Optional Redis, Celery, cache backends, and a WebSocket service support
long-running work and realtime updates.

## Repository shape

The checkout contains roughly 10,800 tracked files. The largest areas are the
frontend, documentation, Python backend, and tests.

| Area | Responsibility | Typical change points |
|---|---|---|
| `superset/` | Flask application, APIs, commands, models, query execution | `*/api.py`, `commands/`, `models/`, `db_engine_specs/` |
| `superset-frontend/src/` | Product UI and browser state | `views/`, `features/`, `dashboard/`, `explore/`, `SqlLab/` |
| `superset-frontend/packages/` | Shared UI, chart, query, and extension packages | `superset-ui-core/`, `superset-core/` |
| `superset-core/` | Published Python primitives for backend extensions | `rest_api/`, `tasks/`, `mcp/`, `extensions/` |
| `superset-websocket/` | JWT-authenticated Redis Pub/Sub to browser transport | `src/index.ts`, `src/config.ts` |
| `tests/` | Python unit and integration coverage | `unit_tests/`, `integration_tests/` |
| `docs/` | Administrator, user, and developer documentation | `admin_docs/`, `developer_docs/`, `docs/` |
| `docker/` and compose files | Development and deployment assembly | bootstrap scripts, images, service configuration |
| `helm/` | Kubernetes packaging | charts, templates, values |

Useful scale indicators from this checkout:

- about 2,650 Python files;
- about 4,000 TypeScript and TSX files;
- 77 database engine specification files;
- 385 Alembic migration files;
- 229 backend command modules.

## Runtime topology

```text
Browser
  |
  v
Reverse proxy / load balancer
  |
  +--> Flask application + REST APIs + static asset shell
  |      |            |                 |
  |      |            |                 +--> cache/results backend
  |      |            +--> Redis / message broker
  |      +--> metadata database
  |      +--> analytical databases
  |
  +--> WebSocket service <--> Redis Pub/Sub

Celery worker <--> broker/cache
      |       \
      |        +--> metadata database
      +--> analytical databases

Celery beat --> scheduled tasks --> Celery worker
```

The full development compose stack assembles:

- Nginx;
- PostgreSQL;
- Redis;
- the Superset Flask application;
- the frontend Webpack development server;
- a Node.js WebSocket service;
- a one-shot initialization service;
- a Celery worker;
- Celery beat.

The lightweight local stack used for this discovery runs PostgreSQL, the Flask
application, and the frontend development proxy. It is sufficient for codebase
inspection and the synchronous product path, but it does not exercise
Redis/Celery/WebSocket behavior.

## Backend architecture

### Application initialization

`superset/app.py` creates the Flask application and delegates setup to
`SupersetAppInitializer` in `superset/initialization/__init__.py`.

Initialization wires configuration, feature flags, the metadata database,
Flask-AppBuilder, authentication, security, API blueprints, cache backends,
Celery, middleware, OpenAPI, migrations, event logging, WebSocket cookies, and
extension hooks.

### Request and command layers

A common write path is:

```text
REST route
  -> Marshmallow schema validation
  -> Flask-AppBuilder route authorization
  -> command object
  -> DAO / SQLAlchemy model
  -> metadata database transaction
  -> serialized response
```

The boundaries are intentionally explicit:

- `*/api.py` exposes REST routes and OpenAPI descriptions;
- `*/schemas.py` validates and serializes request and response data;
- `superset/commands/` owns business operations and transaction boundaries;
- `superset/daos/` owns reusable persistence queries;
- `superset/models/` defines metadata entities;
- `superset/security/` and Flask-AppBuilder enforce role and object access.

High-value domains include charts, dashboards, datasets, databases, SQL Lab,
saved queries, alerts and reports, row-level security, tags, themes, and tasks.

### Query execution

Superset has two prominent query paths:

1. **Chart/dashboard data:** the chart data API loads a `QueryContext`, invokes
   `ChartDataCommand`, resolves a datasource and database engine specification,
   executes SQL, applies post-processing, and serializes or caches the result.
2. **SQL Lab:** the SQL Lab API validates the request and database access, then
   runs one or more statements synchronously or through Celery.

`superset/db_engine_specs/` isolates database-specific behavior such as SQL
dialects, limits, error extraction, cancellation, time grains, and metadata
inspection. `superset/connectors/sqla/` represents SQLAlchemy-backed
datasources and translates semantic definitions into queries.

### Persistence

The metadata database owns application state, not analytical facts. Alembic
migrations under `superset/migrations/versions/` evolve this schema. A broken
upgrade or downgrade can block every deployment, making migration rehearsal a
valuable specialized automation after a broader PR/CI workflow earns adoption.

### Asynchronous work

`superset/tasks/celery_app.py` is the worker entry point. Celery tasks cover
asynchronous SQL, alerts and reports, thumbnails, exports, cache warming,
retention, and the global task framework. Redis is commonly used as broker,
results backend, cache, and realtime Pub/Sub transport.

Celery beat schedules recurring work. Workers update the metadata store and may
query analytical databases, write cached artifacts, or publish status events.

## Frontend architecture

`superset-frontend/src/views/index.tsx` initializes the React root and loads
`views/App.tsx`. The app shell initializes shared setup and plugins, reads
server-provided bootstrap data, creates the router, and supplies root context,
Redux state, theme, menu, notifications, extensions, and optional chat UI.

The principal product surfaces are:

- `dashboard/` — dashboard rendering, filters, layout, and interactions;
- `explore/` — chart construction and query controls;
- `SqlLab/` — SQL editor, query execution, results, and history;
- `features/` and `pages/` — resource administration and routed screens;
- `components/` — shared application components;
- `@superset-ui/core` — chart/query utilities, API client, types, and UI
  abstractions;
- `@apache-superset/core` — newer extension-oriented frontend APIs.

The frontend consumes Flask REST APIs through shared client utilities. Server
bootstrap data supplies the authenticated user, feature flags, menu, locale,
branding, and configuration needed before route rendering.

## Realtime and extension surfaces

The optional WebSocket service subscribes to one Redis Pub/Sub channel and
routes typed envelopes to JWT-bound browser sockets. Principal and tab routing
keys keep targeted task updates separated while allowing authenticated global
broadcasts.

Superset also exposes extension surfaces:

- frontend module-federation contributions;
- backend REST APIs and storage;
- task and MCP decorators in `apache-superset-core`;
- chart plugins and shared packages;
- configurable Flask blueprints, security manager, caches, and engine specs.

## Security boundaries

Flask-AppBuilder provides authentication and route-level authorization.
Object-level checks protect data-bearing resources such as dashboards, charts,
datasets, databases, and query contexts. Row-level security can further
constrain generated SQL.

The repository security model treats operators and administrators as trusted
for their documented capabilities. Automated findings must identify the
assumed principal and the violated role/capability rule; pattern matches alone
are not sufficient.

## Development and verification

Primary toolchains:

- Python 3.11+ with pytest, mypy, ruff, pylint, and Alembic;
- Node 24.16.0 with npm, Jest, React Testing Library, ESLint, and oxfmt;
- Docker Compose for the integrated development topology;
- Playwright for new end-to-end coverage;
- pre-commit as the shared quality entry point.

For this checkout:

- Python 3.12.13 is available in `venv`;
- Node 24.16.0 and npm 11.13.0 are installed;
- the pre-commit Git hook is installed;
- the lightweight Docker stack serves the application through the frontend
  development proxy and reports a healthy backend container.

## GitHub issue, pull-request, and CI surface

The repository contains 52 workflow definitions. They cover pull-request
metadata, pre-commit, Python unit and integration tests, frontend tests and
lint, Playwright and Cypress E2E, dependency consistency, OpenAPI drift,
migration-head conflicts, and result-reporting workflows.

The repository exposes the inputs an issue-remediation controller needs:

- issue events, labels, comments, and actor identity;
- pull-request events and immutable head SHAs;
- changed-file filters and `scripts/change_detector.py`;
- job logs, annotations, and uploaded test artifacts;
- pull-request checks and comments;
- repository-provided focused commands for Python, frontend, pre-commit,
  Playwright, dependency, and generated-file checks.

This breadth is the verification opportunity and design constraint. Devin
selects checks from repository context, while the controller requires the
configured GitHub checks to pass before declaring an issue remediated.

## Where an automation should integrate

The take-home controller should remain outside the Superset product runtime.
It lives in this fork under
[`devin-issue-autopilot/`](../devin-issue-autopilot/README.md) and interacts
through the GitHub API, the Devin API, Docker, and repository checks. This
keeps the proof reusable without adding take-home-specific behavior to the
Flask or React applications.

The implemented slice polls for `devin-fix`, lets the bounded Devin session
open the remediation PR, then independently checks changed paths and the
issue-selected CI check. The stronger production boundary is:

For the hardened GitHub Issue Remediation Runner:

- trigger when a maintainer applies `devin-fix` to an open issue;
- validate a strict issue contract, resolve a full target SHA, and reproduce
  the issue through a controller-owned command policy;
- serialize and deduplicate one active remediation generation per issue;
- create one bounded, read-only Devin API session with a reviewed playbook;
- let Devin investigate and return a bounded structured patch;
- derive the actual diff, enforce path and file-mode policy, verify it in a
  clean checkout, recheck the target SHA, and publish through a controlled
  writer;
- keep Actions and publisher credentials outside the Devin session;
- reconcile the session, pull request, and CI on a schedule;
- publish one updateable issue comment and status label;
- cancel when the issue closes or authorization is removed;
- require configured GitHub checks to pass before success; and
- report funnel, latency, reliability, quality, adoption, and ACU or explicit
  cost unknowns.

The architecture map in `takehome/architecture/` remains a system-level view of
Superset. Its migration callout and the repository's broad CI surface represent
future issue types and trigger adapters; they are not the selected first event.
