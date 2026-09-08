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
        return self.section("Acceptance command")

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
    structured_output: StructuredResult | None = None


class PullRequest(BaseModel):
    state: str
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
    verification_started: float | None = None
    pr_opened: float | None = None
    target_branch: str | None = None
    target_sha: str | None = None

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
    allowed_checks: tuple[str, ...] = ("Python-Unit", "Check OpenAPI spec drift")

    def __post_init__(self) -> None:
        if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.github_repo) is None:
            raise ValueError("GITHUB_REPO must be an owner/repository name")
        if not self.allowed_checks:
            raise ValueError("At least one allowed CI check is required")

    @classmethod
    def from_env(cls, fake: bool = False) -> "Settings":
        required = ("DEVIN_API_KEY", "DEVIN_ORG_ID", "GITHUB_TOKEN")
        missing = [name for name in required if not os.getenv(name)]
        if missing and not fake:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        return cls(
            devin_api_key=os.getenv("DEVIN_API_KEY", ""),
            devin_org_id=os.getenv("DEVIN_ORG_ID", ""),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            github_repo=os.getenv("GITHUB_REPO", "ong6/superset"),
            db_path=Path(os.getenv("AUTOPILOT_DB", "autopilot.db")),
            daily_acu_cap=float(os.getenv("AUTOPILOT_DAILY_ACU_CAP", "20")),
            allowed_checks=tuple(
                check.strip()
                for check in os.getenv(
                    "AUTOPILOT_ALLOWED_CHECKS",
                    "Python-Unit,Check OpenAPI spec drift",
                ).split(",")
                if check.strip()
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
