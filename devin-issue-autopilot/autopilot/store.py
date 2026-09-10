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

import sqlite3
import time
import uuid
from pathlib import Path

from autopilot.models import Issue, ReportRun, Run


class Store:
    def __init__(self, path: Path | str) -> None:
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
              run_id TEXT PRIMARY KEY, issue INTEGER NOT NULL, key TEXT UNIQUE NOT NULL,
              contract_key TEXT NOT NULL DEFAULT '',
              session_id TEXT, session_url TEXT, state TEXT NOT NULL, pr_url TEXT,
              head_sha TEXT, acus REAL NOT NULL DEFAULT 0,
              acus_reported INTEGER NOT NULL DEFAULT 0,
              nudges INTEGER NOT NULL DEFAULT 0,
              created REAL NOT NULL, updated REAL NOT NULL, issue_title TEXT NOT NULL,
              issue_body TEXT NOT NULL, label_at TEXT NOT NULL, label_actor TEXT NOT NULL DEFAULT '',
              outcome TEXT, ci TEXT,
              comment_id TEXT, structured_output TEXT NOT NULL DEFAULT '',
              verification_started REAL, pr_opened REAL,
              target_branch TEXT, target_sha TEXT,
              summary TEXT NOT NULL DEFAULT '',
              acu_guard_source TEXT NOT NULL DEFAULT '',
              acu_guard_total REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS transitions (
              run_id TEXT NOT NULL, "from" TEXT, "to" TEXT NOT NULL,
              at REAL NOT NULL, note TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS report_runs (
              source_id TEXT PRIMARY KEY, issue INTEGER NOT NULL, issue_url TEXT NOT NULL,
              issue_state TEXT NOT NULL, kind TEXT NOT NULL, source TEXT NOT NULL,
              session_role TEXT NOT NULL, session_url TEXT, state TEXT NOT NULL,
              pr_url TEXT, pr_state TEXT,
              ci TEXT, outcome TEXT NOT NULL, acus REAL NOT NULL DEFAULT 0,
              acus_reported INTEGER NOT NULL DEFAULT 0,
              elapsed INTEGER NOT NULL DEFAULT 0, nudges INTEGER NOT NULL DEFAULT 0,
              time_to_pr INTEGER, needs_human INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(runs)").fetchall()
        }
        for name in (
            "target_branch",
            "target_sha",
            "label_actor",
            "summary",
            "structured_output",
            "acu_guard_source",
            "contract_key",
        ):
            if name not in columns:
                self.connection.execute(
                    f"ALTER TABLE runs ADD COLUMN {name} TEXT NOT NULL DEFAULT ''"
                )
        if "acu_guard_total" not in columns:
            self.connection.execute(
                "ALTER TABLE runs ADD COLUMN acu_guard_total REAL NOT NULL DEFAULT 0"
            )
        self.connection.execute("UPDATE runs SET contract_key = key WHERE contract_key = ''")
        if "acus_reported" not in columns:
            self.connection.execute(
                "ALTER TABLE runs ADD COLUMN acus_reported INTEGER NOT NULL DEFAULT 0"
            )
            self.connection.execute("UPDATE runs SET acus_reported = 1 WHERE acus != 0")
        report_columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(report_runs)").fetchall()
        }
        for name in ("issue_url", "issue_state", "source", "session_role"):
            if name not in report_columns:
                self.connection.execute(
                    f"ALTER TABLE report_runs ADD COLUMN {name} TEXT NOT NULL DEFAULT ''"
                )
        if "acus_reported" not in report_columns:
            self.connection.execute(
                "ALTER TABLE report_runs ADD COLUMN acus_reported INTEGER NOT NULL DEFAULT 0"
            )
        self.connection.commit()

    def claim(self, issue: Issue, now: float | None = None) -> Run:
        at = now or time.time()
        run_id = str(uuid.uuid4())
        inserted = self.connection.execute(
            """
            INSERT OR IGNORE INTO runs
              (run_id, issue, key, contract_key, state, created, updated, issue_title, issue_body,
               label_at, label_actor)
            VALUES (?, ?, ?, ?, 'new', ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                issue.number,
                issue.key,
                issue.contract_key,
                at,
                at,
                issue.title,
                issue.body,
                issue.label_at,
                issue.label_actor,
            ),
        )
        if inserted.rowcount:
            self.connection.execute(
                'INSERT INTO transitions VALUES (?, NULL, "new", ?, "")', (run_id, at)
            )
            self._log_transition(issue.number, run_id, None, "new", 0)
        self.connection.commit()
        row = self.connection.execute("SELECT * FROM runs WHERE key = ?", (issue.key,)).fetchone()
        assert row is not None
        return Run.model_validate(dict(row))

    def for_contract(self, contract_key: str) -> list[Run]:
        rows = self.connection.execute(
            "SELECT * FROM runs WHERE contract_key = ? ORDER BY created DESC",
            (contract_key,),
        ).fetchall()
        return [Run.model_validate(dict(row)) for row in rows]

    def active_for_contract(self, contract_key: str) -> Run | None:
        terminal = (
            "verified",
            "merged",
            "merged_unverified",
            "check_skipped",
            "ci_failed",
            "policy_rejected",
            "no_pr",
            "pr_closed",
            "blocked",
            "no_change",
            "timed_out",
            "stale_sha",
            "devin_error",
            "triaged",
            "triage_failed",
            "needs_human",
        )
        placeholders = ",".join("?" for _ in terminal)
        row = self.connection.execute(
            f"""
            SELECT * FROM runs
            WHERE contract_key = ? AND state NOT IN ({placeholders})
            ORDER BY created DESC
            LIMIT 1
            """,
            (contract_key, *terminal),
        ).fetchone()
        return Run.model_validate(dict(row)) if row is not None else None

    def get(self, run_id: str) -> Run:
        row = self.connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return Run.model_validate(dict(row))

    def begin_start(self, run: Run, now: float | None = None) -> tuple[Run, bool]:
        at = now or time.time()
        updated = self.connection.execute(
            """
            UPDATE runs
            SET state = 'creating', updated = ?
            WHERE run_id = ? AND state = 'new'
            """,
            (at, run.run_id),
        )
        if updated.rowcount:
            self.connection.execute(
                'INSERT INTO transitions VALUES (?, "new", "creating", ?, "")',
                (run.run_id, at),
            )
            self._log_transition(
                run.issue,
                run.run_id,
                "new",
                "creating",
                int(at - run.created),
            )
        self.connection.commit()
        return self.get(run.run_id), bool(updated.rowcount)

    def update(self, run_id: str, **values: object) -> Run:
        if not values:
            return self.get(run_id)
        values["updated"] = values.get("updated", time.time())
        assignments = ", ".join(f"{name} = ?" for name in values)
        self.connection.execute(
            f"UPDATE runs SET {assignments} WHERE run_id = ?",
            (*values.values(), run_id),
        )
        self.connection.commit()
        return self.get(run_id)

    def transition(
        self,
        run: Run,
        state: str,
        note: str = "",
        now: float | None = None,
        **values: object,
    ) -> Run:
        at = now or time.time()
        self.connection.execute(
            "INSERT INTO transitions VALUES (?, ?, ?, ?, ?)",
            (run.run_id, run.state, state, at, note[:500]),
        )
        self._log_transition(
            run.issue,
            run.run_id,
            run.state,
            state,
            int(at - run.created),
        )
        values.update(state=state, updated=at)
        assignments = ", ".join(f"{name} = ?" for name in values)
        self.connection.execute(
            f"UPDATE runs SET {assignments} WHERE run_id = ?",
            (*values.values(), run.run_id),
        )
        self.connection.commit()
        return self.get(run.run_id)

    def live(self) -> list[Run]:
        terminal = (
            "verified",
            "merged",
            "merged_unverified",
            "check_skipped",
            "ci_failed",
            "policy_rejected",
            "no_pr",
            "pr_closed",
            "blocked",
            "no_change",
            "timed_out",
            "stale_sha",
            "devin_error",
            "triaged",
            "triage_failed",
            "needs_human",
        )
        placeholders = ",".join("?" for _ in terminal)
        rows = self.connection.execute(
            f"""
            SELECT * FROM runs
            WHERE state NOT IN ({placeholders}) OR comment_id IS NULL
            """,
            terminal,
        ).fetchall()
        return [Run.model_validate(dict(row)) for row in rows]

    def all(self) -> list[Run]:
        rows = self.connection.execute("SELECT * FROM runs ORDER BY created").fetchall()
        return [Run.model_validate(dict(row)) for row in rows]

    def replace_report_runs(self, runs: list[ReportRun]) -> None:
        """Replace the local report cache with rebuilt rows."""

        self.connection.execute("DELETE FROM report_runs")
        self.connection.executemany(
            """
            INSERT INTO report_runs
              (source_id, issue, issue_url, issue_state, kind, source, session_role,
               session_url, state, pr_url, pr_state, ci, outcome, acus, elapsed,
               acus_reported, nudges, time_to_pr, needs_human)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run.source_id,
                    run.issue,
                    run.issue_url,
                    run.issue_state,
                    run.kind,
                    run.source,
                    run.session_role,
                    run.session_url,
                    run.state,
                    run.pr_url,
                    run.pr_state,
                    run.ci,
                    run.outcome,
                    run.acus or 0,
                    run.elapsed,
                    int(run.acus is not None),
                    run.nudges,
                    run.time_to_pr,
                    int(run.needs_human),
                )
                for run in runs
            ],
        )
        self.connection.commit()

    def cached_report_runs(self) -> list[ReportRun]:
        """Return normalized rows from the local report cache."""

        rows = self.connection.execute(
            "SELECT * FROM report_runs ORDER BY issue, kind, source_id"
        ).fetchall()
        return [
            ReportRun.model_validate(
                {
                    **dict(row),
                    "acus": row["acus"] if row["acus_reported"] else None,
                    "needs_human": bool(row["needs_human"]),
                }
            )
            for row in rows
        ]

    def acus_since(self, timestamp: float) -> float:
        row = self.connection.execute(
            "SELECT COALESCE(SUM(acus), 0) AS total FROM runs WHERE created >= ?",
            (timestamp,),
        ).fetchone()
        return float(row["total"])

    @staticmethod
    def _log_transition(
        issue: int,
        run_id: str,
        source: str | None,
        target: str,
        elapsed: int,
    ) -> None:
        """Emit one grep-friendly transition timeline entry."""

        print(
            "transition "
            f"issue={issue} run_id={run_id} from={source or '-'} "
            f"to={target} elapsed={elapsed}s",
            flush=True,
        )
