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

# Five-minute demo test plan

## Evidence boundary

This demo shows one bounded GitHub issue workflow. A maintainer requests work,
the controller pins the target, creates one Devin API session, accepts one
scoped PR proposal, and independently waits for the named CI check on the PR
head. Controller verification means ready for maintainer review; it does not
mean merged.

Do not use issues #42 or #44 as real repair evidence. Do not quote ACUs as cost,
savings, or proof of free work. Raw usage diagnostics are opt-in and
unverified. Full triage and repair are asynchronous and must not be promised
inside five minutes.

## Evidence URLs

- Issue #48: https://github.com/ong6/superset/issues/48
- Repair session: https://app.devin.ai/sessions/6008929ca38344338baa7d628362d29e
- Repair PR #53: https://github.com/ong6/superset/pull/53
- Repair workflow: https://github.com/ong6/superset/actions/runs/34443782255
- Fresh live candidate #49: https://github.com/ong6/superset/issues/49
- Controller implementation PR #51:
  https://github.com/ong6/superset/pull/51

## Recorded intervention

The #48 readiness brief omitted
`tests/unit_tests/utils/test_report_execution.py` from its displayed allowed
paths even though it requested that test file in the acceptance command. The
original issue body already contained every required contract section and
authorized both the production and test paths, so the controller's supported
issue-body precedence supplied the complete repair contract.

Two `/devin fix` comments exist:

1. Comment `5613964970` was posted immediately before the incomplete-brief
   warning arrived. Workflow `34443715515` was cancelled before bounded
   automation ran; its automation step was skipped, so it created no orphan
   repair API session.
2. Comment `5613973610` was posted after independently confirming the
   issue-body precedence. It produced the single preserved repair session and
   PR #53. No further approval, retry, or repair session was submitted.

## Exact preflight

Run from the repository root with authenticated `gh`, `jq`, and the existing
Python virtual environment.

```bash
set -euo pipefail

BASE=223f3e587356a4f9ae67700110c535c4fc8f3e46
HEAD=7caed0f94e9b59b74c3139493db925c4265e463b
PY="$PWD/venv/bin/python"

gh api repos/ong6/superset/pulls/53 |
  jq -e --arg head "$HEAD" '
    .head.sha == $head and
    (.state == "open" or (.state == "closed" and .merged_at != null))
  ' >/dev/null

gh api repos/ong6/superset/pulls/53/files --paginate --jq '.[].filename' |
  diff -u <(printf '%s\n' \
    superset/utils/report_execution.py \
    tests/unit_tests/utils/test_report_execution.py) -

gh api repos/ong6/superset/issues/49 |
  jq -e '
    .state == "open" and
    .comments == 0 and
    ([.labels[].name] == ["devin-exclude"])
  ' >/dev/null

gh api repos/ong6/superset/issues/48/comments --paginate |
  jq -e '
    any(.[];
      .user.login == "github-actions[bot]" and
      (.body | contains("6008929ca38344338baa7d628362d29e")) and
      (.body | contains("https://github.com/ong6/superset/pull/53")) and
      (.body | contains("master@223f3e587356a4f9ae67700110c535c4fc8f3e46"))
    )
  ' >/dev/null

gh api -X GET "repos/ong6/superset/commits/$HEAD/check-runs" \
  -f per_page=100 |
  jq -e '
    any(.check_runs[];
      .name == "unit-tests (current)" and
      .status == "completed" and
      .conclusion == "success"
    )
  ' >/dev/null
```

The named `unit-tests (current)` check must be successful on `$HEAD` before
describing #48 as controller-verified. If it is pending, say pending. If it
fails, show the failure and stop; do not retry during the demo.

### Full-environment red/green

These commands apply only the PR test diff to the pinned baseline, preserving
the baseline production module, then execute the same test file against the PR
head.

```bash
set -euo pipefail

ROOT=$(mktemp -d)
git fetch origin pull/53/head
git worktree add --detach "$ROOT/baseline" "$BASE"
git worktree add --detach "$ROOT/fixed" "$HEAD"
git diff "$BASE..$HEAD" -- tests/unit_tests/utils/test_report_execution.py |
  git -C "$ROOT/baseline" apply

set +e
(cd "$ROOT/baseline" && "$PY" -m pytest -q \
  tests/unit_tests/utils/test_report_execution.py)
RED_EXIT=$?
set -e
test "$RED_EXIT" -eq 1

(cd "$ROOT/fixed" && "$PY" -m pytest -q \
  tests/unit_tests/utils/test_report_execution.py -k non_finite)
(cd "$ROOT/fixed" && "$PY" -m pytest -q \
  tests/unit_tests/utils/test_report_execution.py)

git -C "$ROOT/baseline" restore -- \
  tests/unit_tests/utils/test_report_execution.py
git worktree remove "$ROOT/baseline"
git worktree remove "$ROOT/fixed"
rmdir "$ROOT"
```

Expected evidence:

- baseline with the PR tests: `15 failed, 14 passed`;
- PR head acceptance selector: `15 passed, 14 deselected`;
- PR head full file: `29 passed`;
- independent GitHub `unit-tests (current)`: successful on `$HEAD`.

## Presenter preflight

1. Confirm #49 is open, has only `devin-exclude`, and has no comments.
2. Confirm #48's bot comment links the session, PR #53, and pinned base SHA.
3. Confirm PR #53 still has exactly the two allowed changed paths and the
   expected head SHA.
4. Read PR #53's observed state. Say "open, not merged" only when GitHub says
   `OPEN`; say "merged" only when GitHub says `MERGED`.
5. Confirm the named CI result and controller outcome. Keep the words
   "pending", "verified", and "merged" distinct.
6. Open browser tabs in this order: #49, its Actions workflow, #48, PR #53.
7. Keep the six local slides unchanged and verify both arrow controls once.
8. If GitHub, Actions, or CI is unavailable, skip the live mutation and use
   only the precompleted #48 evidence.

## 60-second live GitHub segment

| Time | Screen | Presenter action and exact claim |
|---:|---|---|
| 0:00-0:10 | Issue #49 | Show it open and excluded. Say: "This is deliberately untouched; the maintainer still controls whether work starts." |
| 0:10-0:25 | Issue #49 | Remove `devin-exclude`, then add `devin-triage` as one deliberate triage request. Do not add a fix label or comment. |
| 0:25-0:40 | Issue/Actions | Show the queued or running acknowledgement. Say only what GitHub displays: "The request is queued" or "Triage is running." |
| 0:40-1:00 | #48 then PR #53 | Switch to the precompleted rehearsal. Show issue-to-session-to-PR provenance, pinned base/head, changed paths, red/green tests, and named CI. Say "verified" only if the controller outcome is terminal verified, and state the merge status exactly as GitHub displays it. |

Do not wait for #49 triage to finish. Do not request or approve a #49 repair
during the recording.

## 4:45 demo spine

| Time | Point |
|---:|---|
| 0:00-0:25 | Slide 1: observed issue intake and maintainer handoffs; avoid unsourced ROI claims. |
| 0:25-0:35 | Slide 2 introduction: bounded authorization and deterministic proof. |
| 0:35-1:35 | Run the 60-second GitHub segment above. |
| 1:35-2:45 | #48 evidence: real defect, API session, scoped PR, full-environment red/green, independent CI. |
| 2:45-3:15 | Why this workflow: least privilege, bounded execution, and maintainer control. |
| 3:15-4:10 | Report: distinguish CI/policy verification, merge state, and verified-and-merged. |
| 4:10-4:45 | Pilot ask: 10 maintainer-approved real issues over 30 days, measured against a manual baseline with explicit stop conditions. |

## Stop conditions

Stop or qualify the claim if any of these are observed:

- PR #53 head or base differs from the pinned SHAs;
- changed paths extend beyond the two issue-authorized files;
- `unit-tests (current)` is not successful on the current PR head;
- the controller outcome is nonterminal or failed;
- #49 was changed before presenter launch;
- report output includes raw ACUs without explicit opt-in;
- GitHub evidence cannot distinguish controller verification from merge state.
