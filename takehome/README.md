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

# Devin Event-Driven Automation Take-Home

This directory captures the discovery and design work for an event-driven
automation built around the Devin API and this Superset fork.

## Documents

1. [Goal and success criteria](01-goal.md)
2. [Ranked automation ideas](02-ideas.md)
3. [Superset codebase overview](03-codebase-overview.md)
4. [Architecture map](architecture/README.md)
5. [Recommendation and next steps](04-recommendation.md)

## Recommended direction

Build the **Migration Upgrade Contract Guardian**: a GitHub-event-driven
controller that deterministically rehearses changed Alembic migrations,
starts Devin only for reproduced failures, and tracks the path from detection
to a passing remediation pull request.

The recommendation is intentionally narrow:

- deterministic database commands decide pass or fail;
- Devin investigates and remediates one reproduced invariant violation;
- GitHub issues, checks, pull requests, logs, and metrics make the result
  observable;
- the entire before-and-after loop fits a five-minute demonstration.
