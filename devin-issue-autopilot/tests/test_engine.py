# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from pathlib import Path

from autopilot.adapters import FakeDevin, FakeGitHub
from autopilot.engine import Engine
from autopilot.models import Issue, Settings
from autopilot.store import Store


class Clock:
    def __init__(self) -> None:
        self.value = 1_800_000_000.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def issue(number: int = 1, allowed: str = "superset/example.py") -> Issue:
    return Issue(
        number=number,
        title="Repair fixture",
        body=(
            "## Symptom\nFailure\n\n"
            "## Expected\nCI check: `Python-Unit`\n\n"
            f"## Allowed paths\n- `{allowed}`\n\n"
            "## Acceptance command\npytest -q fixture"
        ),
        label_at="2026-09-08T10:00:00Z",
        labels=["devin-fix"],
    )


def exit_snapshot(url: str) -> dict[str, object]:
    return {
        "status": "exit",
        "acus_consumed": 1.25,
        "pull_requests": [{"pr_url": url}],
        "structured_output": {
            "outcome": "fixed",
            "pr_url": url,
            "branch": "devin/issue-1-fixture",
            "root_cause": "A bounded fixture failure.",
            "acceptance_output": "1 passed",
            "files_changed": ["superset/example.py"],
        },
    }


def setup_engine(
    tmp_path: Path,
    plan: list[dict[str, object]],
    files: list[str] | None = None,
    clock: Clock | None = None,
) -> tuple[Engine, FakeDevin, FakeGitHub, Issue]:
    item = issue()
    url = "https://github.com/ong6/superset/pull/10"
    devin = FakeDevin({item.number: plan})
    github = FakeGitHub(
        [item],
        {
            url: {
                "head_sha": "a" * 40,
                "files": files or ["superset/example.py"],
            }
        },
    )
    settings = Settings("", "", "", db_path=tmp_path / "autopilot.db")
    return (
        Engine(settings, Store(settings.db_path), devin, github, clock or Clock()),
        devin,
        github,
        item,
    )


def test_happy_path_opens_one_session_and_verifies(tmp_path: Path) -> None:
    url = "https://github.com/ong6/superset/pull/10"
    engine, devin, github, item = setup_engine(tmp_path, [exit_snapshot(url)])

    run = engine.run_issue(item, sleep=lambda _: None)

    assert run.state == "verified"
    assert devin.create_calls == 1
    assert devin.get_calls == 1
    assert len(github.comments) == 1


def test_duplicate_label_does_not_create_second_session(tmp_path: Path) -> None:
    url = "https://github.com/ong6/superset/pull/10"
    engine, devin, github, item = setup_engine(tmp_path, [exit_snapshot(url)])

    first = engine.run_issue(item, sleep=lambda _: None)
    second = engine.run_issue(item, sleep=lambda _: None)

    assert first.run_id == second.run_id
    assert devin.create_calls == 1
    assert len(github.comments) == 1


def test_waiting_for_user_is_nudged_once_then_succeeds(tmp_path: Path) -> None:
    url = "https://github.com/ong6/superset/pull/10"
    plan: list[dict[str, object]] = [
        {"status": "running", "status_detail": "waiting_for_user"},
        exit_snapshot(url),
    ]
    engine, devin, _, item = setup_engine(tmp_path, plan)

    run = engine.run_issue(item, sleep=lambda _: None)

    assert run.state == "verified"
    assert run.nudges == 1
    assert devin.nudge_calls == 1
    assert devin.get_calls == 2


def test_timeout_deletes_once_and_finishes(tmp_path: Path) -> None:
    clock = Clock()
    engine, devin, _, item = setup_engine(
        tmp_path,
        [{"status": "running", "status_detail": "working"}],
        clock=clock,
    )
    run = engine.claim(item)
    run = engine.advance(run)
    clock.advance(2401)

    run = engine.advance(run)
    clock.advance(121)
    run = engine.advance(run)

    assert run.state == "timed_out"
    assert devin.create_calls == 1
    assert devin.delete_calls == 1


def test_pr_touching_tests_is_policy_rejected(tmp_path: Path) -> None:
    url = "https://github.com/ong6/superset/pull/10"
    engine, devin, _, item = setup_engine(
        tmp_path, [exit_snapshot(url)], files=["tests/unit_tests/test_escape.py"]
    )

    run = engine.run_issue(item, sleep=lambda _: None)

    assert run.state == "policy_rejected"
    assert devin.create_calls == 1
    assert devin.get_calls == 1


def test_restart_resumes_persisted_session_without_create(tmp_path: Path) -> None:
    clock = Clock()
    url = "https://github.com/ong6/superset/pull/10"
    engine, devin, github, item = setup_engine(tmp_path, [exit_snapshot(url)], clock=clock)
    running = engine.advance(engine.claim(item))
    assert running.session_id is not None

    settings = Settings("", "", "", db_path=tmp_path / "autopilot.db")
    restarted = Engine(settings, Store(settings.db_path), devin, github, clock)
    run = restarted.run_issue(item, sleep=lambda _: None)

    assert run.state == "verified"
    assert devin.create_calls == 1
    assert devin.get_calls == 1
