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

import base64
import binascii
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import TypeAlias

import httpx
from pydantic import BaseModel, ConfigDict, Field

from autopilot.models import (
    Issue,
    PullRequest,
    ReportComment,
    ReportIssue,
    ReportPullRequest,
    ReportSession,
    ReportSessionsPage,
    Run,
    SessionCreate,
    SessionSnapshot,
    Settings,
    Target,
    output_schema,
    triage_output_schema,
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
    html_url: str = ""
    state: str = "open"
    body: str | None = None
    created_at: str = ""
    updated_at: str = ""
    user: GitHubActor | None = None
    labels: list[GitHubLabel] = Field(default_factory=list)


class GitHubEvent(BaseModel):
    event: str
    created_at: str
    label: GitHubLabel | None = None
    actor: GitHubActor | None = None


class GitHubPullData(BaseModel):
    state: str
    body: str | None = None
    head: GitHubRef
    base: GitHubRef


class GitHubPullStateData(BaseModel):
    """GitHub response fields needed for report PR state."""

    state: str
    created_at: str
    merged_at: str | None = None


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
    user: GitHubActor | None = None


class TriageContract(BaseModel):
    """Validated contract recovered from a trusted triage comment."""

    model_config = ConfigDict(extra="forbid")

    allowed_paths: list[str] = Field(max_length=20)
    acceptance_command: str = Field(max_length=500)
    ci_check: str = Field(max_length=100)


class FakePR(BaseModel):
    head_sha: str
    files: list[str]
    state: str = "open"
    body: str = ""
    head_ref: str = "devin/issue-1-fixture"
    base_sha: str = "b" * 40
    base_ref: str = "master"
    checks: list[tuple[str, str | None]] = [("completed", "success")]


FakePRs: TypeAlias = Mapping[str, FakePR | dict[str, object]]


class DevinClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.org_id = settings.devin_org_id
        self.repo = settings.github_repo
        self.triage_acu_limit = settings.triage_acu_limit
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
                    "role:remediation",
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

    def create_triage(self, issue: Issue, run: Run, prompt: str) -> SessionCreate:
        """Create a bounded, approval-gated triage session."""

        response = self.client.post(
            f"/v3/organizations/{self.org_id}/sessions",
            json={
                "title": f"Triage {self.repo}#{issue.number}: {issue.title}",
                "prompt": prompt,
                "repos": [self.repo],
                "tags": [
                    "autopilot",
                    "triage",
                    "role:triage",
                    f"issue:{issue.number}",
                    f"run:{run.run_id}",
                ],
                "max_acu_limit": self.triage_acu_limit,
                "bypass_approval": False,
                "resumable": False,
                "secret_ids": [],
                "structured_output_required": True,
                "structured_output_schema": triage_output_schema(),
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

    def list_report_sessions(self) -> list[ReportSession]:
        """List autopilot sessions for optional report reconciliation."""

        sessions: list[ReportSession] = []
        after: str | None = None
        while True:
            params: dict[str, str | int | list[str]] = {
                "first": 200,
                "tags": ["autopilot"],
                "repo_names": [self.repo],
            }
            if after is not None:
                params["after"] = after
            response = self.client.get(
                f"/v3/organizations/{self.org_id}/sessions",
                params=params,
            )
            response.raise_for_status()
            page = ReportSessionsPage.model_validate(response.json())
            sessions.extend(page.items)
            if not page.has_next_page or page.end_cursor is None:
                return sessions
            after = page.end_cursor


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

    def _issue(
        self,
        data: GitHubIssueData,
        request_actor: str | None = None,
        requested_at: str | None = None,
        purpose: str = "fix",
    ) -> Issue:
        number = data.number
        body = data.body or ""
        if purpose != "triage":
            body = self._with_triage_contract(number, data.title, body)
        if request_actor is not None and requested_at is not None:
            return Issue(
                number=number,
                title=data.title,
                body=body,
                label_at=f"{purpose}:{requested_at}",
                label_actor=request_actor,
            )
        events = self.client.get(
            f"/repos/{self.repo}/issues/{number}/events", params={"per_page": 100}
        )
        events.raise_for_status()
        active_labels = {label.name for label in data.labels}
        labels = [
            event
            for event in (GitHubEvent.model_validate(item) for item in events.json())
            if event.event == "labeled"
            and event.label is not None
            and event.label.name in {"devin-fix", "devin-retry"}
            and event.label.name in active_labels
        ]
        if not labels:
            raise ValueError(f"Issue #{number} has no Devin label event")
        label_at = labels[-1].created_at
        actor = labels[-1].actor
        return Issue(
            number=number,
            title=data.title,
            body=body,
            label_at=label_at,
            label_actor=actor.login if actor is not None else "",
        )

    def _with_triage_contract(self, number: int, title: str, body: str) -> str:
        required_sections = ("Symptom", "Expected", "Allowed paths", "Acceptance command")
        if all(
            re.search(rf"(?m)^## {re.escape(section)}\s*$", body) for section in required_sections
        ):
            return body
        comments = self._comments(number)
        contract: TriageContract | None = None
        for comment in reversed(comments):
            if comment.user is None or comment.user.login != "github-actions[bot]":
                continue
            match = re.search(r"<!-- devin-triage-contract:([A-Za-z0-9_-]+) -->", comment.body)
            if match is None:
                continue
            try:
                payload = base64.urlsafe_b64decode(match.group(1) + "===")
                contract = TriageContract.model_validate_json(payload)
            except (binascii.Error, ValueError):
                continue
            break
        if contract is None:
            return body
        additions: list[str] = []
        if re.search(r"(?m)^## Symptom\s*$", body) is None:
            additions.append(f"## Symptom\n{body.strip() or title}")
        if re.search(r"(?m)^## Expected\s*$", body) is None:
            additions.append(
                "## Expected\nImplement the behavior described by the issue.\n\n"
                f"CI check: `{contract.ci_check}`"
            )
        if re.search(r"(?m)^## Allowed paths\s*$", body) is None:
            paths = "\n".join(f"- `{path}`" for path in contract.allowed_paths)
            additions.append(f"## Allowed paths\n{paths}")
        if re.search(r"(?m)^## Acceptance command\s*$", body) is None:
            additions.append(f"## Acceptance command\n{contract.acceptance_command}")
        return f"{body.rstrip()}\n\n" + "\n\n".join(additions)

    def _comments(self, number: int) -> list[GitHubComment]:
        comments: list[GitHubComment] = []
        page = 1
        while True:
            response = self.client.get(
                f"/repos/{self.repo}/issues/{number}/comments",
                params={"per_page": 100, "page": page},
            )
            response.raise_for_status()
            batch = [GitHubComment.model_validate(item) for item in response.json()]
            comments.extend(batch)
            if len(batch) < 100:
                return comments
            page += 1

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

    def report_issues(self) -> list[ReportIssue]:
        """List labeled issues and comments used to rebuild reports."""

        issues: list[ReportIssue] = []
        page = 1
        while True:
            response = self.client.get(
                f"/repos/{self.repo}/issues",
                params={"state": "all", "per_page": 100, "page": page},
            )
            response.raise_for_status()
            batch = response.json()
            for item in batch:
                if "pull_request" in item:
                    continue
                data = GitHubIssueData.model_validate(item)
                labels = [label.name for label in data.labels]
                if not any(label.startswith("devin-") for label in labels):
                    continue
                comments = [
                    ReportComment(
                        author=comment.user.login if comment.user is not None else "",
                        body=comment.body,
                    )
                    for comment in self._comments(data.number)
                ]
                issues.append(
                    ReportIssue(
                        number=data.number,
                        url=data.html_url,
                        state=data.state,
                        labels=labels,
                        comments=comments,
                    )
                )
            if len(batch) < 100:
                return issues
            page += 1

    def get_issue(
        self,
        number: int,
        request_actor: str | None = None,
        requested_at: str | None = None,
        purpose: str = "fix",
    ) -> Issue:
        response = self.client.get(f"/repos/{self.repo}/issues/{number}")
        response.raise_for_status()
        return self._issue(
            GitHubIssueData.model_validate(response.json()),
            request_actor,
            requested_at,
            purpose,
        )

    def get_triage_issue(
        self,
        number: int,
        request_actor: str | None = None,
        requested_at: str | None = None,
    ) -> Issue:
        """Load an issue with a stable triage request identity."""

        response = self.client.get(f"/repos/{self.repo}/issues/{number}")
        response.raise_for_status()
        data = GitHubIssueData.model_validate(response.json())
        actor = request_actor or (data.user.login if data.user is not None else "")
        at = requested_at or data.created_at or data.updated_at
        if not at:
            raise ValueError("issue has no timestamp for triage")
        return self._issue(data, actor, at, "triage")

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
            body=data.body or "",
            head_sha=data.head.sha,
            head_ref=data.head.ref,
            base_sha=data.base.sha,
            base_ref=data.base.ref,
        )

    def report_pr(self, url: str) -> ReportPullRequest:
        """Read the current state and creation time for a repository PR."""

        match = re.fullmatch(r"https://github\.com/([^/]+/[^/]+)/pull/(\d+)", url)
        if match is None or match.group(1) != self.repo:
            raise ValueError("PR URL is not for the configured repository")
        response = self.client.get(f"/repos/{self.repo}/pulls/{match.group(2)}")
        response.raise_for_status()
        data = GitHubPullStateData.model_validate(response.json())
        return ReportPullRequest(
            state="merged" if data.merged_at is not None else data.state,
            created_at=data.created_at,
        )

    def pr_files(self, url: str) -> list[str]:
        number = url.rsplit("/", 1)[-1]
        files: list[str] = []
        for page in range(1, 31):
            response = self.client.get(
                f"/repos/{self.repo}/pulls/{number}/files",
                params={"per_page": 100, "page": page},
            )
            response.raise_for_status()
            batch = [GitHubFile.model_validate(item).filename for item in response.json()]
            files.extend(batch)
            if len(batch) < 100:
                break
        return files

    def check(self, sha: str, name: str) -> tuple[str, str | None]:
        response = self.client.get(
            f"/repos/{self.repo}/commits/{sha}/check-runs",
            params={"per_page": 100},
        )
        response.raise_for_status()
        checks = GitHubChecks.model_validate(response.json())
        for check in checks.check_runs:
            if check.name.casefold() == name.casefold():
                return check.status, check.conclusion
        response = self.client.get(
            f"/repos/{self.repo}/commits/{sha}/status",
            params={"per_page": 100},
        )
        response.raise_for_status()
        statuses = GitHubStatuses.model_validate(response.json())
        for status in statuses.statuses:
            if status.context.casefold() == name.casefold():
                if status.state == "pending":
                    return "in_progress", None
                return "completed", status.state
        return "queued", None

    @staticmethod
    def _request_marker(key: str) -> str:
        digest = sha256(key.encode()).hexdigest()[:16]
        prefix = "devin-triage-request" if ":triage:" in key else "devin-issue-autopilot"
        return f"<!-- {prefix}:{digest} -->"

    def _upsert_comment(
        self,
        issue: int,
        key: str,
        body: str,
        preserve_contract: bool = True,
        include_request_marker: bool = True,
    ) -> str:
        marker = f"<!-- devin-issue-autopilot:{issue} -->"
        comments = self._comments(issue)
        existing = next(
            (
                comment
                for comment in comments
                if comment.user is not None
                and comment.user.login == "github-actions[bot]"
                and (
                    marker in comment.body
                    or re.search(
                        r"<!-- devin-issue-triage:[0-9a-f]{16} -->",
                        comment.body,
                    )
                    is not None
                )
            ),
            None,
        )
        if existing is None:
            request_marker = self._request_marker(key)
            existing = next(
                (
                    comment
                    for comment in comments
                    if comment.user is not None
                    and comment.user.login == "github-actions[bot]"
                    and request_marker in comment.body
                ),
                None,
            )
        previous_body = existing.body if existing is not None else ""
        request_pattern = r"<!-- (?:devin-triage-request|devin-issue-autopilot):[0-9a-f]{16} -->"
        request_markers = re.findall(request_pattern, previous_body) + re.findall(
            request_pattern, body
        )
        if include_request_marker:
            request_markers.append(self._request_marker(key))
        request_markers = list(dict.fromkeys(request_markers))[-500:]
        contract_pattern = r"<!-- devin-triage-contract:[A-Za-z0-9_-]+ -->"
        contract_match = re.search(contract_pattern, body)
        if contract_match is None and preserve_contract:
            contract_match = re.search(contract_pattern, previous_body)
        clean_body = re.sub(
            rf"(?:{re.escape(marker)}|{request_pattern}|{contract_pattern})\n?",
            "",
            body,
        ).strip()
        metadata = [marker, *request_markers]
        if contract_match is not None:
            metadata.append(contract_match.group(0))
        marked_body = "\n".join([*metadata, clean_body])
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
        return comment_id

    def progress(self, issue: int, key: str, body: str) -> str:
        """Create or update the issue's durable automation comment."""

        return self._upsert_comment(
            issue,
            key,
            body,
            include_request_marker=False,
        )

    def conclude(self, issue: int, key: str, body: str, outcome: str) -> str:
        comment_id = self._upsert_comment(issue, key, body)
        label = "devin-verified" if outcome == "verified" else "devin-needs-human"
        other_label = "devin-needs-human" if label == "devin-verified" else "devin-verified"
        for removable in (other_label, "devin-fix", "devin-retry", "devin-candidate"):
            removed = self.client.delete(f"/repos/{self.repo}/issues/{issue}/labels/{removable}")
            if removed.status_code != 404:
                removed.raise_for_status()
        labels = self.client.post(
            f"/repos/{self.repo}/issues/{issue}/labels", json={"labels": [label]}
        )
        labels.raise_for_status()
        return comment_id

    def conclude_triage(self, issue: int, key: str, body: str, labels: list[str]) -> str:
        """Upsert the issue's triage brief and reconcile triage labels."""

        comment_id = self._upsert_comment(issue, key, body, preserve_contract=False)
        for removable in (
            "devin-triage-bug",
            "devin-triage-feature",
            "devin-triage-docs",
            "devin-triage-question",
            "devin-triage-security",
            "devin-triage-other",
            "devin-needs-info",
            "devin-needs-maintainer",
            "devin-candidate",
            "devin-triage",
            "devin-verified",
            "devin-needs-human",
        ):
            removed = self.client.delete(f"/repos/{self.repo}/issues/{issue}/labels/{removable}")
            if removed.status_code != 404:
                removed.raise_for_status()
        response = self.client.post(
            f"/repos/{self.repo}/issues/{issue}/labels", json={"labels": labels}
        )
        response.raise_for_status()
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

    def create_triage(self, issue: Issue, run: Run, prompt: str) -> SessionCreate:
        return self.create(issue, run, prompt)

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
        self.report_fixture: list[ReportIssue] | None = None
        self.report_prs: dict[str, ReportPullRequest] = {}

    @classmethod
    def load(cls, path: Path) -> "FakeGitHub":
        data = json.loads(path.read_text())
        issues = [Issue.model_validate(item) for item in data["issues"]]
        prs = {str(url): FakePR.model_validate(pr) for url, pr in data["prs"].items()}
        return cls(issues, prs)

    @classmethod
    def load_report(cls, path: Path) -> "FakeGitHub":
        """Load report issues and PR metadata from a fixture."""

        data = json.loads(path.read_text())
        github = cls([], {})
        github.report_fixture = [ReportIssue.model_validate(issue) for issue in data["issues"]]
        github.report_prs = {
            str(url): ReportPullRequest.model_validate(pr) for url, pr in data["prs"].items()
        }
        return github

    def list_issues(self) -> list[Issue]:
        return list(self.issues.values())

    def report_issues(self) -> list[ReportIssue]:
        """Return report issues from fixtures or recorded fake comments."""

        if self.report_fixture is not None:
            return self.report_fixture
        comments_by_issue: dict[int, list[ReportComment]] = {}
        for comment in self.comments:
            issue_number = int(str(comment["issue"]))
            comments_by_issue.setdefault(issue_number, []).append(
                ReportComment(
                    author="github-actions[bot]",
                    body=str(comment["body"]),
                )
            )
        return [
            ReportIssue(
                number=issue_number,
                url=f"https://github.com/ong6/superset/issues/{issue_number}",
                state="open",
                labels=[],
                comments=comments_by_issue.get(issue_number, []),
            )
            for issue_number in self.issues
        ]

    def get_issue(
        self,
        number: int,
        request_actor: str | None = None,
        requested_at: str | None = None,
        purpose: str = "fix",
    ) -> Issue:
        issue = self.issues[number]
        if request_actor is None or requested_at is None:
            return issue
        return issue.model_copy(
            update={
                "label_at": f"{purpose}:{requested_at}",
                "label_actor": request_actor,
            }
        )

    def get_triage_issue(
        self,
        number: int,
        request_actor: str | None = None,
        requested_at: str | None = None,
    ) -> Issue:
        issue = self.issues[number]
        if request_actor is None or requested_at is None:
            return issue
        return issue.model_copy(
            update={
                "label_at": f"triage:{requested_at}",
                "label_actor": request_actor,
            }
        )

    def target(self) -> Target:
        return self.current_target

    def labeler_authorized(self, issue: Issue) -> bool:
        return self.labeler_is_authorized

    def resolve_pr(self, url: str) -> PullRequest:
        pr = self.prs[url]
        return PullRequest(
            state=pr.state,
            body=pr.body,
            head_sha=pr.head_sha,
            head_ref=pr.head_ref,
            base_sha=pr.base_sha,
            base_ref=pr.base_ref,
        )

    def report_pr(self, url: str) -> ReportPullRequest:
        """Return fixture-backed PR metadata."""

        if url in self.report_prs:
            return self.report_prs[url]
        return ReportPullRequest(
            state=self.prs[url].state,
            created_at=datetime.now(UTC).isoformat(),
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
        existing = next((item for item in self.comments if item["issue"] == issue), None)
        if existing is not None:
            existing.update(key=key, body=body, outcome=outcome)
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

    def progress(self, issue: int, key: str, body: str) -> str:
        existing = next((item for item in self.comments if item["issue"] == issue), None)
        if existing is not None:
            existing.update(key=key, body=body, outcome="pending")
            return str(existing["id"])
        comment_id = str(len(self.comments) + 1)
        self.comments.append(
            {
                "id": comment_id,
                "issue": issue,
                "key": key,
                "body": body,
                "outcome": "pending",
            }
        )
        return comment_id

    def conclude_triage(self, issue: int, key: str, body: str, labels: list[str]) -> str:
        existing = next(
            (item for item in self.comments if item["issue"] == issue),
            None,
        )
        if existing is not None:
            existing.update(key=key, body=body, outcome="triaged", labels=labels)
            return str(existing["id"])
        comment_id = str(len(self.comments) + 1)
        self.comments.append(
            {
                "id": comment_id,
                "issue": issue,
                "key": key,
                "body": body,
                "outcome": "triaged",
                "labels": labels,
            }
        )
        return comment_id
