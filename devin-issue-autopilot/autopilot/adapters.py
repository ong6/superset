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
from hashlib import sha256
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

from autopilot.models import (
    Issue,
    PullRequest,
    Run,
    SessionCreate,
    SessionSnapshot,
    Settings,
    Target,
    output_schema,
)


class GitHubLabel(BaseModel):
    name: str


class GitHubActor(BaseModel):
    login: str


class GitHubRef(BaseModel):
    sha: str
    ref: str


class GitHubCommit(BaseModel):
    sha: str


class GitHubIssueData(BaseModel):
    number: int
    title: str
    body: str | None = None
    labels: list[GitHubLabel] = Field(default_factory=list)


class GitHubEvent(BaseModel):
    event: str
    created_at: str
    label: GitHubLabel | None = None
    actor: GitHubActor | None = None


class GitHubPullData(BaseModel):
    state: str
    head: GitHubRef
    base: GitHubRef


class GitHubRepoData(BaseModel):
    default_branch: str


class GitHubPermissionData(BaseModel):
    permission: str


class GitHubBranchData(BaseModel):
    commit: GitHubCommit


class GitHubFile(BaseModel):
    filename: str


class GitHubCheck(BaseModel):
    name: str
    status: str
    conclusion: str | None = None


class GitHubChecks(BaseModel):
    check_runs: list[GitHubCheck]


class GitHubStatus(BaseModel):
    context: str
    state: str


class GitHubStatuses(BaseModel):
    statuses: list[GitHubStatus]


class GitHubComment(BaseModel):
    id: int
    body: str = ""


class FakePR(BaseModel):
    head_sha: str
    files: list[str]
    state: str = "open"
    head_ref: str = "devin/issue-1-fixture"
    base_sha: str = "b" * 40
    base_ref: str = "master"
    checks: list[tuple[str, str | None]] = [("completed", "success")]


type FakePRs = Mapping[str, FakePR | dict[str, object]]


class DevinClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.org_id = settings.devin_org_id
        self.repo = settings.github_repo
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
                "title": f"Fix {self.repo}#{issue.number}: {issue.title}",
                "prompt": prompt,
                "repos": [self.repo],
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
            and event.label.name in {"devin-fix", "devin-retry"}
        ]
        if not labels:
            raise ValueError(f"Issue #{number} has no Devin label event")
        label_at = labels[-1].created_at
        actor = labels[-1].actor
        return Issue(
            number=number,
            title=data.title,
            body=data.body or "",
            label_at=label_at,
            label_actor=actor.login if actor is not None else "",
        )

    def list_issues(self) -> list[Issue]:
        response = self.client.get(
            f"/repos/{self.repo}/issues",
            params={"state": "open", "per_page": 100},
        )
        response.raise_for_status()
        issues: list[Issue] = []
        for data in response.json():
            if "pull_request" in data:
                continue
            issue = GitHubIssueData.model_validate(data)
            if not any(label.name in {"devin-fix", "devin-retry"} for label in issue.labels):
                continue
            issues.append(self._issue(issue))
        return issues

    def get_issue(self, number: int) -> Issue:
        response = self.client.get(f"/repos/{self.repo}/issues/{number}")
        response.raise_for_status()
        return self._issue(GitHubIssueData.model_validate(response.json()))

    def target(self) -> Target:
        repository = self.client.get(f"/repos/{self.repo}")
        repository.raise_for_status()
        branch = GitHubRepoData.model_validate(repository.json()).default_branch
        response = self.client.get(f"/repos/{self.repo}/branches/{branch}")
        response.raise_for_status()
        sha = GitHubBranchData.model_validate(response.json()).commit.sha
        return Target(branch=branch, sha=sha)

    def labeler_authorized(self, issue: Issue) -> bool:
        if re.fullmatch(r"[A-Za-z0-9-]+", issue.label_actor) is None:
            return False
        response = self.client.get(
            f"/repos/{self.repo}/collaborators/{issue.label_actor}/permission"
        )
        if response.status_code == 404:
            return False
        response.raise_for_status()
        permission = GitHubPermissionData.model_validate(response.json()).permission
        return permission in {"admin", "maintain", "write"}

    def resolve_pr(self, url: str) -> PullRequest:
        match = re.fullmatch(r"https://github\.com/([^/]+/[^/]+)/pull/(\d+)", url)
        if match is None or match.group(1) != self.repo:
            raise ValueError("PR URL is not for the configured repository")
        response = self.client.get(f"/repos/{self.repo}/pulls/{match.group(2)}")
        response.raise_for_status()
        data = GitHubPullData.model_validate(response.json())
        return PullRequest(
            state=data.state,
            head_sha=data.head.sha,
            head_ref=data.head.ref,
            base_sha=data.base.sha,
            base_ref=data.base.ref,
        )

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
        response = self.client.get(f"/repos/{self.repo}/commits/{sha}/status")
        response.raise_for_status()
        statuses = GitHubStatuses.model_validate(response.json())
        for status in statuses.statuses:
            if status.context.casefold() == name.casefold():
                if status.state == "pending":
                    return "in_progress", None
                return "completed", status.state
        return "queued", None

    def conclude(self, issue: int, key: str, body: str, outcome: str) -> str:
        marker = f"<!-- devin-issue-autopilot:{sha256(key.encode()).hexdigest()[:16]} -->"
        marked_body = f"{marker}\n{body}"
        existing_response = self.client.get(
            f"/repos/{self.repo}/issues/{issue}/comments",
            params={"per_page": 100},
        )
        existing_response.raise_for_status()
        comments = [GitHubComment.model_validate(comment) for comment in existing_response.json()]
        existing = next((comment for comment in comments if marker in comment.body), None)
        if existing is None:
            response = self.client.post(
                f"/repos/{self.repo}/issues/{issue}/comments",
                json={"body": marked_body},
            )
            response.raise_for_status()
            comment_id = str(GitHubComment.model_validate(response.json()).id)
        else:
            response = self.client.patch(
                f"/repos/{self.repo}/issues/comments/{existing.id}",
                json={"body": marked_body},
            )
            response.raise_for_status()
            comment_id = str(existing.id)
        label = "devin-verified" if outcome == "verified" else "devin-needs-human"
        other_label = "devin-needs-human" if label == "devin-verified" else "devin-verified"
        for removable in (other_label, "devin-fix", "devin-retry"):
            removed = self.client.delete(f"/repos/{self.repo}/issues/{issue}/labels/{removable}")
            if removed.status_code != 404:
                removed.raise_for_status()
        labels = self.client.post(
            f"/repos/{self.repo}/issues/{issue}/labels", json={"labels": [label]}
        )
        labels.raise_for_status()
        return comment_id


class FakeDevin:
    def __init__(
        self,
        plans: dict[int, list[SessionSnapshot | dict[str, object]]] | None = None,
        sessions: dict[str, list[SessionSnapshot | dict[str, object]]] | None = None,
    ) -> None:
        self.plans = plans or {}
        self.sessions = sessions or {}
        self.prompts: list[str] = []
        self.create_calls = 0
        self.get_calls = 0
        self.nudge_calls = 0
        self.delete_calls = 0

    def create(self, issue: Issue, run: Run, prompt: str) -> SessionCreate:
        self.create_calls += 1
        self.prompts.append(prompt)
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
    def __init__(
        self,
        issues: list[Issue],
        prs: FakePRs,
        target: Target | None = None,
    ) -> None:
        self.issues = {issue.number: issue for issue in issues}
        self.prs = {url: FakePR.model_validate(pr) for url, pr in prs.items()}
        self.current_target = target or Target(branch="master", sha="b" * 40)
        self.comments: list[dict[str, object]] = []
        self.labeler_is_authorized = True

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

    def target(self) -> Target:
        return self.current_target

    def labeler_authorized(self, issue: Issue) -> bool:
        return self.labeler_is_authorized

    def resolve_pr(self, url: str) -> PullRequest:
        pr = self.prs[url]
        return PullRequest(
            state=pr.state,
            head_sha=pr.head_sha,
            head_ref=pr.head_ref,
            base_sha=pr.base_sha,
            base_ref=pr.base_ref,
        )

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

    def conclude(self, issue: int, key: str, body: str, outcome: str) -> str:
        existing = next((item for item in self.comments if item["key"] == key), None)
        if existing is not None:
            existing.update(body=body, outcome=outcome)
            return str(existing["id"])
        comment_id = str(len(self.comments) + 1)
        self.comments.append(
            {
                "id": comment_id,
                "issue": issue,
                "key": key,
                "body": body,
                "outcome": outcome,
            }
        )
        return comment_id
