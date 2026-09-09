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

# Sequential remediation demo runbook

This runbook demonstrates two **synthetic demo fixtures**, not upstream defect
discoveries:

1. [#42](https://github.com/ong6/superset/issues/42): report reserve equality.
2. [#44](https://github.com/ong6/superset/issues/44): migration downgrade order.

[PR #46](https://github.com/ong6/superset/pull/46) restores the baseline and
adds both exact acceptance commands to `unit-tests (current)`. It is setup
work, not an automated remediation. Run one case at a time and never move
`master` between applying `devin-fix` and the controller's terminal outcome.

## Common commands and invariants

```bash
set -euo pipefail
export REPO=ong6/superset
export REPORT_TEST='tests/unit_tests/utils/test_report_execution.py::test_report_execution_config_rejects_invalid_startup_values[overrides2-must total less]'
export MIGRATION_TEST=tests/unit_tests/migrations/test_add_deleted_at_to_tables.py

git fetch origin master
PINNED_MASTER=$(git rev-parse origin/master)
test "$PINNED_MASTER" = \
  "$(gh api "repos/$REPO/git/ref/heads/master" --jq .object.sha)"
printf 'PINNED_MASTER=%s\n' "$PINNED_MASTER"
```

During an active controller run, use this check before trusting any outcome:

```bash
test "$PINNED_MASTER" = \
  "$(gh api "repos/$REPO/git/ref/heads/master" --jq .object.sha)" ||
  { echo 'STOP: master moved; treat the run as stale'; false; }
```

For each generated remediation PR, independently inspect provenance and CI:

```bash
# Replace ISSUE after the controller posts its lifecycle comment.
gh api "repos/$REPO/issues/$ISSUE/comments" \
  --jq 'map(select(.body | contains("app.devin.ai/sessions/"))) |
        last | {comment: .html_url, body: .body}'

PR_URL=$(gh api "repos/$REPO/issues/$ISSUE/timeline" \
  -H 'Accept: application/vnd.github+json' \
  --jq '[.[] | select(.event == "cross-referenced" and
        .source.issue.pull_request)] | last | .source.issue.html_url')
test -n "$PR_URL"

PR_NUMBER=${PR_URL##*/}
gh api "repos/$REPO/pulls/$PR_NUMBER" \
  --jq '{url: .html_url, state, body, base: .base.sha, head: .head.sha}'
test "$(gh api "repos/$REPO/pulls/$PR_NUMBER" --jq .base.sha)" = \
  "$PINNED_MASTER"
gh api --paginate "repos/$REPO/pulls/$PR_NUMBER/files" --jq '.[].filename'

HEAD_SHA=$(gh api "repos/$REPO/pulls/$PR_NUMBER" --jq .head.sha)
RUN_ID=$(gh run list --workflow superset-python-unittest.yml \
  --commit "$HEAD_SHA" --limit 1 --json databaseId \
  --jq '.[0].databaseId')
gh run watch "$RUN_ID" --exit-status
gh api --paginate "repos/$REPO/commits/$HEAD_SHA/check-runs?per_page=100" \
  -H 'Accept: application/vnd.github+json' \
  --jq '.check_runs[] | select(.name == "unit-tests (current)") |
        {url: .html_url, status, conclusion}'
gh run view "$RUN_ID" --json url,conclusion,headSha
gh run view "$RUN_ID" --json jobs \
  --jq '.jobs[] | select(.name == "unit-tests (current)") |
        {url, conclusion, steps: [.steps[] | {name, conclusion}]}'
gh run view "$RUN_ID" --log | rg -m 2 '1 passed|5 passed'
```

The PR must close the source issue, be based on `PINNED_MASTER`, modify only
the issue's allowed path, pass `unit-tests (current)`, and end with the
controller's `verified` lifecycle outcome. A PR opening is not verification.

## Case 1: #42 report equality

### Synthetic seed PR

Start only after PR #46 is merged and both acceptance commands pass on
`master`.

```bash
git fetch origin master
PINNED_MASTER=$(git rev-parse origin/master)
git switch -c demo/synthetic-report-equality "$PINNED_MASTER"
git apply <<'PATCH'
diff --git a/superset/utils/report_execution.py b/superset/utils/report_execution.py
--- a/superset/utils/report_execution.py
+++ b/superset/utils/report_execution.py
@@ -52,7 +52,7 @@ def validate_report_execution_config(config: Mapping[str, Any]) -> None:
         raise ValueError("Report execution budget must be greater than zero")
     if any(reserve < 0 for reserve in reserves):
         raise ValueError("Report execution phase reserves cannot be negative")
-    if sum(reserves) >= budget:
+    if sum(reserves) > budget:
         raise ValueError(
             "Report execution phase reserves must total less than the execution budget"
         )
PATCH
if pytest -q "$REPORT_TEST"; then
  echo 'STOP: synthetic report fixture did not reproduce the failure'
  exit 1
fi
git add superset/utils/report_execution.py
pre-commit run
git commit -m 'test(demo): inject synthetic report equality fixture'
git push -u origin HEAD
gh pr create --base master \
  --title 'test(demo): inject synthetic report equality fixture' \
  --body 'Synthetic demo fixture for #42. Expected: the explicit report acceptance step is red. This is setup evidence, not an upstream discovery or automated remediation.'
```

Expected seed evidence:

```text
Failed: DID NOT RAISE <class 'ValueError'>
1 failed
unit-tests (current): failure
```

**Maintainer merge gate 1:** inspect the one-line synthetic diff, acknowledge
that its red check is intentional, and merge the seed PR. Do not trigger #42
before this merge.

### Controller remediation

After the seed merge, reproduce and pin the broken `master`, then trigger the
existing controller:

```bash
git fetch origin master
PINNED_MASTER=$(git rev-parse origin/master)
git switch --detach "$PINNED_MASTER"
if pytest -q "$REPORT_TEST"; then
  echo 'STOP: #42 failure is not present on pinned master'
  exit 1
fi
export ISSUE=42
gh issue edit "$ISSUE" --add-label devin-fix
```

Do not merge or push to `master` while this run is active. Use the common
provenance commands above. Expected passing evidence from the generated PR:

```text
Remediation acceptance checks
1 passed
5 passed
unit-tests (current): success
controller outcome: verified
```

**Maintainer merge gate 2:** merge the controller-created remediation PR only
after the pinned base, allowed path, linked issue/session, exact acceptance
step, broad check, and terminal outcome are all verified.

Before case 2, fetch the merged `master` and require both commands to pass:

```bash
git fetch origin master
git switch --detach origin/master
pytest -q "$REPORT_TEST"
pytest -q "$MIGRATION_TEST"
```

## Case 2: #44 migration downgrade

### Synthetic seed PR

```bash
git fetch origin master
PINNED_MASTER=$(git rev-parse origin/master)
git switch -c demo/synthetic-migration-order "$PINNED_MASTER"
git apply <<'PATCH'
diff --git a/superset/migrations/versions/2026-05-08_12-10_3a8e6f2c1b95_add_deleted_at_to_tables.py b/superset/migrations/versions/2026-05-08_12-10_3a8e6f2c1b95_add_deleted_at_to_tables.py
--- a/superset/migrations/versions/2026-05-08_12-10_3a8e6f2c1b95_add_deleted_at_to_tables.py
+++ b/superset/migrations/versions/2026-05-08_12-10_3a8e6f2c1b95_add_deleted_at_to_tables.py
@@ -56,3 +56,3 @@ def downgrade() -> None:
     """Reverse ``upgrade`` by removing the column and index."""
-    drop_index(TABLE_NAME, INDEX_NAME)
     drop_columns(TABLE_NAME, "deleted_at")
+    drop_index(TABLE_NAME, INDEX_NAME)
PATCH
if pytest -q "$MIGRATION_TEST"; then
  echo 'STOP: synthetic migration fixture did not reproduce the failure'
  exit 1
fi
git add superset/migrations/versions/2026-05-08_12-10_3a8e6f2c1b95_add_deleted_at_to_tables.py
pre-commit run
git commit -m 'test(demo): inject synthetic migration order fixture'
git push -u origin HEAD
gh pr create --base master \
  --title 'test(demo): inject synthetic migration order fixture' \
  --body 'Synthetic demo fixture for #44. Expected: the explicit migration acceptance step is red. This is setup evidence, not an upstream discovery or automated remediation.'
```

Expected seed evidence:

```text
sqlite3.OperationalError: no such column: deleted_at
3 failed, 2 passed
unit-tests (current): failure
```

**Maintainer merge gate 3:** inspect and intentionally merge this red seed PR.
Keep `devin-exclude` on #44 until the seed is merged and independently
reproduced.

### Controller remediation

```bash
git fetch origin master
PINNED_MASTER=$(git rev-parse origin/master)
git switch --detach "$PINNED_MASTER"
if pytest -q "$MIGRATION_TEST"; then
  echo 'STOP: #44 failure is not present on pinned master'
  exit 1
fi

export ISSUE=44
gh issue edit "$ISSUE" --remove-label devin-exclude
gh issue edit "$ISSUE" --add-label devin-triage
gh api "repos/$REPO/issues/$ISSUE/comments" \
  --jq 'map({url: .html_url, author: .user.login, body}) | last'
# Wait for the bounded triage brief before authorization.
gh issue edit "$ISSUE" --add-label devin-fix
```

Freeze `master` and use the common provenance commands. Expected passing
evidence is the same explicit `1 passed`, `5 passed`, successful named check,
and terminal `verified` outcome.

**Maintainer merge gate 4:** merge the verified controller-created remediation
PR. This completes the second substantive success.

## Optional smoke case and five-minute Loom

[#43](https://github.com/ong6/superset/issues/43) is optional smoke only:

```bash
pytest -q --doctest-modules superset/result_set.py
```

It is not one of the two successes, and `unit-tests (current)` does not prove
this doctest. Do not trigger it unless its acceptance evidence is deliberately
added and captured.

Suggested Loom evidence, in order:

1. PR #46: green baseline and explicit acceptance step; label it setup work.
2. #42: synthetic seed PR, exact red terminal output, and immutable master SHA.
3. #42 lifecycle comment: issue URL, API-created Devin session URL, generated
   PR URL, Actions URL, exact acceptance output, and `verified`.
4. Clean merged master, then the equivalent #44 seed and lifecycle evidence.
5. Final report from PR #47, distinguishing verified from merged outcomes.

The #42/#44 session, remediation PR, Actions, terminal-comment, and final-report
links do not exist until their live runs complete. Leave placeholders visible
or say “not run yet”; do not substitute historical, simulated, or setup links.

## Smallest next decision

Merge PR #46 after its updated CI remains green. Do not create a seed PR or a
live controller run before that merge.
