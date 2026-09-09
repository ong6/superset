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

# Demo Runbook

Run the issues in this order: **#31, #30, #32**. Finish and merge each PR before
starting the next issue. Verification pins `master`; if `master` moves during a
run, the controller returns `stale_sha`.

## 1. Issue #31: report execution boundary

1. Remove `devin-exclude` from
   [#31](https://github.com/ong6/superset/issues/31).
2. Comment `/devin fix`.
3. Wait for the durable autopilot comment to reach a terminal outcome.
4. Expect `ci_failed` because the #30 migration seed is still live.
5. Read the failure, open the linked PR, and merge it.
6. Confirm the merge is present on `master` before touching #30.

## 2. Issue #30: migration downgrade order

1. Remove `devin-exclude` from
   [#30](https://github.com/ong6/superset/issues/30).
2. Comment `/devin fix`.
3. Wait for the durable autopilot comment to reach a terminal outcome.
4. Read the verification result, open the linked PR, and merge it.
5. Confirm the merge is present on `master` before touching #32.

## 3. Issue #32: dedup doctest

1. Remove `devin-exclude` from
   [#32](https://github.com/ong6/superset/issues/32).
2. Comment `/devin fix`.
3. Wait for the durable autopilot comment to reach a terminal outcome.
4. Read the verification result, open the linked PR, and merge it.
