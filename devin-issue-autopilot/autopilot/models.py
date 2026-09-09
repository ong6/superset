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

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Issue(BaseModel):
    number: int
    title: str
    body: str
    label_at: str
    label_actor: str = ""

    def section(self, name: str) -> str:
        match = re.search(rf"(?ms)^## {re.escape(name)}\s*\n(.*?)(?=^## |\Z)", self.body)
        return match.group(1).strip() if match else ""

    @property
    def allowed_paths(self) -> list[str]:
        return [
            line.removeprefix("-").strip().strip("`")
            for line in self.section("Allowed paths").splitlines()
            if line.strip().startswith("-")
        ]

    @property
    def check_name(self) -> str:
        match = re.search(r"(?im)^CI check:\s*`?([^`\n]+)`?", self.body)
        return match.group(1).strip() if match else "Python-Unit"

    @property
    def acceptance_command(self) -> str:
        value = self.section("Acceptance command")
        match = re.fullmatch(r"```[A-Za-z0-9_-]*\n(?P<command>.*?)\n```", value, re.DOTALL)
        return match.group("command").strip() if match is not None else value

    @property
    def key(self) -> str:
        return f"{self.number}:{self.label_at}"


class StructuredResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["fixed", "no_change", "blocked"]
    pr_url: str = Field(max_length=500)
    branch: str = Field(max_length=300)
    root_cause: str = Field(max_length=400)
    acceptance_output: str = Field(max_length=2000)
    files_changed: list[str] = Field(max_length=20)


class TriageResult(BaseModel):
    """Structured classification and proposed remediation contract."""

    model_config = ConfigDict(extra="forbid")

    outcome: Literal["triaged", "needs_info", "needs_maintainer"]
    category: Literal["bug", "feature", "docs", "question", "security", "other"]
    confidence: Literal["low", "medium", "high"]
    summary: str = Field(max_length=700)
    next_action: str = Field(max_length=400)
    labels: list[str] = Field(max_length=5)
    allowed_paths: list[str] = Field(max_length=20)
    acceptance_command: str = Field(max_length=500)
    ci_check: str = Field(max_length=100)
    missing_information: list[str] = Field(default_factory=list, max_length=10)
    risk_notes: list[str] = Field(default_factory=list, max_length=10)


class SessionCreate(BaseModel):
    session_id: str
    url: str


class SessionPullRequest(BaseModel):
    pr_url: str


class SessionSnapshot(BaseModel):
    status: str
    status_detail: str | None = None
    acus_consumed: float = 0
    pull_requests: list[SessionPullRequest] = Field(default_factory=list)
    structured_output: StructuredResult | TriageResult | None = None


class PullRequest(BaseModel):
    state: str
    body: str
    head_sha: str
    head_ref: str
    base_sha: str
    base_ref: str


class Target(BaseModel):
    branch: str
    sha: str


class Run(BaseModel):
    run_id: str
    issue: int
    key: str
    session_id: str | None = None
    session_url: str | None = None
    state: str
    pr_url: str | None = None
    head_sha: str | None = None
    acus: float = 0
    nudges: int = 0
    created: float
    updated: float
    issue_title: str
    issue_body: str
    label_at: str
    label_actor: str = ""
    outcome: str | None = None
    ci: str | None = None
    comment_id: str | None = None
    structured_output: str = ""
    verification_started: float | None = None
    pr_opened: float | None = None
    target_branch: str | None = None
    target_sha: str | None = None
    summary: str = ""

    @property
    def issue_model(self) -> Issue:
        return Issue(
            number=self.issue,
            title=self.issue_title,
            body=self.issue_body,
            label_at=self.label_at,
            label_actor=self.label_actor,
        )


@dataclass(frozen=True)
class Settings:
    devin_api_key: str
    devin_org_id: str
    github_token: str
    github_repo: str = "ong6/superset"
    db_path: Path = Path("autopilot.db")
    daily_acu_cap: float = 20
    triage_acu_limit: int = 1
    allowed_checks: tuple[str, ...] = ("Python-Unit", "Check OpenAPI spec drift")
    triage_labels: tuple[str, ...] = (
        "devin-triage-bug",
        "devin-triage-feature",
        "devin-triage-docs",
        "devin-triage-question",
        "devin-triage-security",
        "devin-triage-other",
        "devin-needs-info",
        "devin-needs-maintainer",
        "devin-triaged",
    )

    def __post_init__(self) -> None:
        if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.github_repo) is None:
            raise ValueError("GITHUB_REPO must be an owner/repository name")
        if not self.allowed_checks:
            raise ValueError("At least one allowed CI check is required")
        if self.triage_acu_limit <= 0:
            raise ValueError("Triage ACU limit must be positive")
        required_triage_labels = {
            "devin-triage-bug",
            "devin-triage-feature",
            "devin-triage-docs",
            "devin-triage-question",
            "devin-triage-security",
            "devin-triage-other",
            "devin-needs-info",
            "devin-needs-maintainer",
            "devin-triaged",
        }
        if not required_triage_labels.issubset(self.triage_labels):
            raise ValueError("AUTOPILOT_TRIAGE_LABELS must include every managed triage label")

    @classmethod
    def from_env(
        cls,
        fake: bool = False,
        devin_key_env: str = "DEVIN_API_KEY",
    ) -> "Settings":
        required = (devin_key_env, "DEVIN_ORG_ID", "GITHUB_TOKEN")
        missing = [name for name in required if not os.getenv(name)]
        if missing and not fake:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        return cls(
            devin_api_key=os.getenv(devin_key_env, ""),
            devin_org_id=os.getenv("DEVIN_ORG_ID", ""),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            github_repo=os.getenv("GITHUB_REPO", "ong6/superset"),
            db_path=Path(os.getenv("AUTOPILOT_DB", "autopilot.db")),
            daily_acu_cap=float(os.getenv("AUTOPILOT_DAILY_ACU_CAP", "20")),
            triage_acu_limit=int(os.getenv("AUTOPILOT_TRIAGE_ACU_LIMIT", "1")),
            allowed_checks=tuple(
                check.strip()
                for check in os.getenv(
                    "AUTOPILOT_ALLOWED_CHECKS",
                    "Python-Unit,Check OpenAPI spec drift",
                ).split(",")
                if check.strip()
            ),
            triage_labels=tuple(
                label.strip()
                for label in os.getenv(
                    "AUTOPILOT_TRIAGE_LABELS",
                    (
                        "devin-triage-bug,devin-triage-feature,devin-triage-docs,"
                        "devin-triage-question,devin-triage-security,devin-triage-other,"
                        "devin-needs-info,devin-needs-maintainer,devin-triaged"
                    ),
                ).split(",")
                if label.strip()
            ),
        )


def output_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "outcome": {"type": "string", "enum": ["fixed", "no_change", "blocked"]},
            "pr_url": {"type": "string", "maxLength": 500},
            "branch": {"type": "string", "maxLength": 300},
            "root_cause": {"type": "string", "maxLength": 400},
            "acceptance_output": {"type": "string", "maxLength": 2000},
            "files_changed": {
                "type": "array",
                "maxItems": 20,
                "items": {"type": "string", "maxLength": 500},
            },
        },
        "required": [
            "outcome",
            "pr_url",
            "branch",
            "root_cause",
            "acceptance_output",
            "files_changed",
        ],
    }


def triage_output_schema() -> dict[str, object]:
    """Return the strict Devin triage output schema."""

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "outcome": {
                "type": "string",
                "enum": ["triaged", "needs_info", "needs_maintainer"],
            },
            "category": {
                "type": "string",
                "enum": ["bug", "feature", "docs", "question", "security", "other"],
            },
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "summary": {"type": "string", "maxLength": 700},
            "next_action": {"type": "string", "maxLength": 400},
            "labels": {
                "type": "array",
                "maxItems": 5,
                "items": {"type": "string", "maxLength": 80},
            },
            "allowed_paths": {
                "type": "array",
                "maxItems": 20,
                "items": {"type": "string", "maxLength": 300},
            },
            "acceptance_command": {"type": "string", "maxLength": 500},
            "ci_check": {"type": "string", "maxLength": 100},
            "missing_information": {
                "type": "array",
                "maxItems": 10,
                "items": {"type": "string", "maxLength": 300},
            },
            "risk_notes": {
                "type": "array",
                "maxItems": 10,
                "items": {"type": "string", "maxLength": 300},
            },
        },
        "required": [
            "outcome",
            "category",
            "confidence",
            "summary",
            "next_action",
            "labels",
            "allowed_paths",
            "acceptance_command",
            "ci_check",
            "missing_information",
            "risk_notes",
        ],
    }
