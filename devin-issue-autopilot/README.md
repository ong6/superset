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
