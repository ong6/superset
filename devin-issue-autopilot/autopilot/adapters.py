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

import json
import re
from collections.abc import Mapping
from pathlib import Path

import httpx
from pydantic import BaseModel

from autopilot.models import (
    Issue,
    PullRequest,
    Run,
    SessionCreate,
    SessionSnapshot,
    Settings,
    output_schema,
)


class GitHubIssueData(BaseModel):
    number: int
    title: str
    body: str | None = None


class GitHubEvent(BaseModel):
    event: str
    created_at: str
    label: dict[str, str] | None = None


class GitHubPullData(BaseModel):
    state: str
    head: dict[str, str]


class GitHubFile(BaseModel):
    filename: str


class GitHubCheck(BaseModel):
    name: str
    status: str
    conclusion: str | None = None


class GitHubChecks(BaseModel):
    check_runs: list[GitHubCheck]


class GitHubComment(BaseModel):
    id: int


class FakePR(BaseModel):
    head_sha: str
    files: list[str]
    state: str = "open"
    checks: list[tuple[str, str | None]] = [("completed", "success")]


type FakePRs = Mapping[str, FakePR | dict[str, object]]


class DevinClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.org_id = settings.devin_org_id
        self.client = httpx.Client(
            base_url="https://api.devin.ai",
            headers={"Authorization": f"Bearer {settings.devin_api_key}"},
            timeout=30,
            transport=transport,
        )

    def create(self, issue: Issue, run: Run, prompt: str) -> SessionCreate:
        response = self.client.post(
            f"/v3/organizations/{self.org_id}/sessions",
            json={
                "title": f"Fix ong6/superset#{issue.number}: {issue.title}",
                "prompt": prompt,
                "repos": ["ong6/superset"],
                "tags": [
                    "autopilot",
                    f"issue:{issue.number}",
                    f"run:{run.run_id}",
                ],
                "max_acu_limit": 4,
                "resumable": False,
                "secret_ids": [],
                "structured_output_required": True,
                "structured_output_schema": output_schema(),
            },
        )
        response.raise_for_status()
        return SessionCreate.model_validate(response.json())

    def get(self, session_id: str) -> SessionSnapshot:
        response = self.client.get(f"/v3/organizations/{self.org_id}/sessions/{session_id}")
        response.raise_for_status()
        return SessionSnapshot.model_validate(response.json())

    def nudge(self, session_id: str) -> None:
        response = self.client.post(
            f"/v3/organizations/{self.org_id}/sessions/{session_id}/messages",
            json={
                "message": (
                    "Proceed with your best judgement within the issue's allowed paths; "
                    "do not ask again."
                )
            },
        )
        response.raise_for_status()

    def delete(self, session_id: str) -> None:
        response = self.client.delete(f"/v3/organizations/{self.org_id}/sessions/{session_id}")
        response.raise_for_status()


class GitHubClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.repo = settings.github_repo
        self.client = httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"Bearer {settings.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
            transport=transport,
        )

    def _issue(self, data: GitHubIssueData) -> Issue:
        number = data.number
        events = self.client.get(
            f"/repos/{self.repo}/issues/{number}/events", params={"per_page": 100}
        )
        events.raise_for_status()
        labels = [
            event
            for event in (GitHubEvent.model_validate(item) for item in events.json())
            if event.event == "labeled"
            and event.label is not None
            and event.label.get("name") in {"devin-fix", "devin-retry"}
        ]
        if not labels:
            raise ValueError(f"Issue #{number} has no Devin label event")
        label_at = labels[-1].created_at
        return Issue(
            number=number,
            title=data.title,
            body=data.body or "",
            label_at=label_at,
        )

    def list_issues(self) -> list[Issue]:
        response = self.client.get(
            f"/repos/{self.repo}/issues",
            params={"state": "open", "labels": "devin-fix", "per_page": 100},
        )
        response.raise_for_status()
        return [
            self._issue(GitHubIssueData.model_validate(data))
            for data in response.json()
            if "pull_request" not in data
        ]

    def get_issue(self, number: int) -> Issue:
        response = self.client.get(f"/repos/{self.repo}/issues/{number}")
        response.raise_for_status()
        return self._issue(GitHubIssueData.model_validate(response.json()))

    def resolve_pr(self, url: str) -> PullRequest:
        match = re.fullmatch(r"https://github\.com/([^/]+/[^/]+)/pull/(\d+)", url)
        if match is None or match.group(1) != self.repo:
            raise ValueError("PR URL is not for the configured repository")
        response = self.client.get(f"/repos/{self.repo}/pulls/{match.group(2)}")
        response.raise_for_status()
        data = GitHubPullData.model_validate(response.json())
        return PullRequest(state=data.state, head_sha=data.head["sha"])

    def pr_files(self, url: str) -> list[str]:
        number = url.rsplit("/", 1)[-1]
        response = self.client.get(
            f"/repos/{self.repo}/pulls/{number}/files", params={"per_page": 100}
        )
        response.raise_for_status()
        return [GitHubFile.model_validate(item).filename for item in response.json()]

    def check(self, sha: str, name: str) -> tuple[str, str | None]:
        response = self.client.get(f"/repos/{self.repo}/commits/{sha}/check-runs")
        response.raise_for_status()
        checks = GitHubChecks.model_validate(response.json())
        for check in checks.check_runs:
            if check.name.casefold() == name.casefold():
                return check.status, check.conclusion
        return "queued", None

    def conclude(self, issue: int, body: str, outcome: str) -> str:
        response = self.client.post(
            f"/repos/{self.repo}/issues/{issue}/comments", json={"body": body}
        )
        response.raise_for_status()
        label = "devin-verified" if outcome == "verified" else "devin-needs-human"
        labels = self.client.post(
            f"/repos/{self.repo}/issues/{issue}/labels", json={"labels": [label]}
        )
        labels.raise_for_status()
        removed = self.client.delete(f"/repos/{self.repo}/issues/{issue}/labels/devin-fix")
        if removed.status_code != 404:
            removed.raise_for_status()
        return str(GitHubComment.model_validate(response.json()).id)


class FakeDevin:
    def __init__(
        self,
        plans: dict[int, list[SessionSnapshot | dict[str, object]]] | None = None,
        sessions: dict[str, list[SessionSnapshot | dict[str, object]]] | None = None,
    ) -> None:
        self.plans = plans or {}
        self.sessions = sessions or {}
        self.create_calls = 0
        self.get_calls = 0
        self.nudge_calls = 0
        self.delete_calls = 0

    def create(self, issue: Issue, run: Run, prompt: str) -> SessionCreate:
        self.create_calls += 1
        session_id = f"devin-fake-{issue.number}-{self.create_calls}"
        self.sessions[session_id] = list(self.plans[issue.number])
        return SessionCreate(
            session_id=session_id,
            url=f"https://app.devin.ai/sessions/{session_id}",
        )

    def get(self, session_id: str) -> SessionSnapshot:
        self.get_calls += 1
        plan = self.sessions[session_id]
        if len(plan) > 1:
            value = plan.pop(0)
        else:
            value = plan[0]
        return SessionSnapshot.model_validate(value)

    def nudge(self, session_id: str) -> None:
        self.nudge_calls += 1

    def delete(self, session_id: str) -> None:
        self.delete_calls += 1


class FakeGitHub:
    def __init__(self, issues: list[Issue], prs: FakePRs) -> None:
        self.issues = {issue.number: issue for issue in issues}
        self.prs = {url: FakePR.model_validate(pr) for url, pr in prs.items()}
        self.comments: list[dict[str, object]] = []

    @classmethod
    def load(cls, path: Path) -> "FakeGitHub":
        data = json.loads(path.read_text())
        issues = [Issue.model_validate(item) for item in data["issues"]]
        prs = {str(url): FakePR.model_validate(pr) for url, pr in data["prs"].items()}
        return cls(issues, prs)

    def list_issues(self) -> list[Issue]:
        return list(self.issues.values())

    def get_issue(self, number: int) -> Issue:
        return self.issues[number]

    def resolve_pr(self, url: str) -> PullRequest:
        pr = self.prs[url]
        return PullRequest(state=pr.state, head_sha=pr.head_sha)

    def pr_files(self, url: str) -> list[str]:
        return self.prs[url].files

    def check(self, sha: str, name: str) -> tuple[str, str | None]:
        pr = next(item for item in self.prs.values() if item.head_sha == sha)
        checks = pr.checks
        if len(checks) > 1:
            check = checks.pop(0)
        else:
            check = checks[0]
        return check

    def conclude(self, issue: int, body: str, outcome: str) -> str:
        comment_id = str(len(self.comments) + 1)
        self.comments.append({"id": comment_id, "issue": issue, "body": body, "outcome": outcome})
        return comment_id
