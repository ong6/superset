---
name: superset-issue-fix
description: Fix one bounded Superset issue and open a verified pull request.
---

# Superset Issue Fix

1. Read the complete GitHub issue before changing the repository.
2. Extract the issue number, requested behavior, allowed paths, forbidden
   actions, and exact acceptance command.
3. Run the acceptance command unchanged and confirm that it fails. If it
   passes or cannot run, stop and report `no_change` or `blocked`.
4. Create and switch to `devin/issue-<n>-<slug>`, where `<n>` is the issue
   number and `<slug>` is a short lowercase description.
5. Diagnose the production-code root cause from the failure output and
   relevant source.
6. Make the smallest production fix within the issue's allowed paths.
7. Do not edit tests, CI workflows, requirements, or generated files unless
   the issue's allowed paths explicitly list them.
8. Do not broaden scope, skip checks, weaken assertions, expose secrets,
   merge changes, or force-push.
9. Rerun the exact acceptance command until it passes. Preserve its final
   output for the pull request.
10. Commit and push the branch without force.
11. Open a pull request and use these body sections:
    - `Summary`
    - `Root cause`
    - `Acceptance command and its output`
    - `Fixes #<n>`
12. Stop after opening the pull request.
