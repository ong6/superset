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

# Devin Issue Autopilot moved

The controller, Docker setup, tests and simulation live in
[ong6/devin-issue-autopilot](https://github.com/ong6/devin-issue-autopilot).
Start with that repository's README to run the credential-free Docker simulation.

This Superset fork retains the event workflow, Devin skills, issues, repair PRs,
checks and historical evidence. Its workflow checks out a tested controller
commit from the solution repository; the issue approvals and credentials stay
in this fork.

The original controller remains available in
[the pre-extraction source](https://github.com/ong6/superset/tree/6db1a10b5f149f531961cfba077a09e94b9de999/devin-issue-autopilot).
