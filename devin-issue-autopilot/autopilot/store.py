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

from autopilot.models import Issue, Run


class Store:
    def __init__(self, path: Path | str) -> None:
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
              run_id TEXT PRIMARY KEY, issue INTEGER NOT NULL, key TEXT UNIQUE NOT NULL,
              session_id TEXT, session_url TEXT, state TEXT NOT NULL, pr_url TEXT,
              head_sha TEXT, acus REAL NOT NULL DEFAULT 0, nudges INTEGER NOT NULL DEFAULT 0,
              created REAL NOT NULL, updated REAL NOT NULL, issue_title TEXT NOT NULL,
              issue_body TEXT NOT NULL, label_at TEXT NOT NULL, label_actor TEXT NOT NULL DEFAULT '',
              outcome TEXT, ci TEXT,
              comment_id TEXT, verification_started REAL, pr_opened REAL,
              target_branch TEXT, target_sha TEXT
            );
            CREATE TABLE IF NOT EXISTS transitions (
              run_id TEXT NOT NULL, "from" TEXT, "to" TEXT NOT NULL,
              at REAL NOT NULL, note TEXT NOT NULL DEFAULT ''
            );
            """
        )
        columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(runs)").fetchall()
        }
        for name in ("target_branch", "target_sha", "label_actor"):
            if name not in columns:
                self.connection.execute(
                    f"ALTER TABLE runs ADD COLUMN {name} TEXT NOT NULL DEFAULT ''"
                )
        self.connection.commit()

    def claim(self, issue: Issue, now: float | None = None) -> Run:
        at = now or time.time()
        run_id = str(uuid.uuid4())
        inserted = self.connection.execute(
            """
            INSERT OR IGNORE INTO runs
              (run_id, issue, key, state, created, updated, issue_title, issue_body,
               label_at, label_actor)
            VALUES (?, ?, ?, 'new', ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                issue.number,
                issue.key,
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
        self.connection.commit()
        row = self.connection.execute("SELECT * FROM runs WHERE key = ?", (issue.key,)).fetchone()
        assert row is not None
        return Run.model_validate(dict(row))

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
            "ci_failed",
            "policy_rejected",
            "no_pr",
            "blocked",
            "no_change",
            "timed_out",
            "stale_sha",
            "devin_error",
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

    def acus_since(self, timestamp: float) -> float:
        row = self.connection.execute(
            "SELECT COALESCE(SUM(acus), 0) AS total FROM runs WHERE created >= ?",
            (timestamp,),
        ).fetchone()
        return float(row["total"])
