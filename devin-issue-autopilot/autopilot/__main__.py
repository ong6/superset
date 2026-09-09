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
import os
import time
from pathlib import Path

import typer

from autopilot.adapters import DevinClient, FakeDevin, FakeGitHub, GitHubClient
from autopilot.engine import Engine, TERMINAL, write_report
from autopilot.models import Settings
from autopilot.store import Store

app = typer.Typer(no_args_is_help=True)


def real_engine(
    devin_key_env: str = "DEVIN_API_KEY",
    triage_only: bool = False,
) -> Engine:
    settings = Settings.from_env(devin_key_env=devin_key_env)
    devin = DevinClient(settings)
    triage_devin = devin if triage_only else None
    if not triage_only and os.getenv("DEVIN_TRIAGE_API_KEY"):
        triage_settings = Settings.from_env(devin_key_env="DEVIN_TRIAGE_API_KEY")
        triage_devin = DevinClient(triage_settings)
    return Engine(
        settings,
        Store(settings.db_path),
        devin,
        GitHubClient(settings),
        triage_devin=triage_devin,
    )


@app.command()
def watch() -> None:
    engine = real_engine()
    cycle = 0
    try:
        while True:
            engine.watch_once(discover=cycle % 3 == 0)
            cycle += 1
            time.sleep(10)
    except KeyboardInterrupt:
        typer.echo("Stopped.")


@app.command()
def once(
    issue: int = typer.Option(..., "--issue"),
    actor: str | None = typer.Option(None, "--actor"),
    requested_at: str | None = typer.Option(None, "--requested-at"),
    purpose: str = typer.Option("fix", "--purpose"),
) -> None:
    if purpose not in {"fix", "retry"}:
        raise typer.BadParameter("must be fix or retry", param_hint="--purpose")
    engine = real_engine()
    result = engine.run_issue(engine.github.get_issue(issue, actor, requested_at, purpose))
    typer.echo(f"{result.issue}: {result.state}")
    if result.state != "verified":
        raise typer.Exit(1)


@app.command()
def triage(
    issue: int = typer.Option(..., "--issue"),
    actor: str | None = typer.Option(None, "--actor"),
    requested_at: str | None = typer.Option(None, "--requested-at"),
) -> None:
    engine = real_engine("DEVIN_TRIAGE_API_KEY", triage_only=True)
    result = engine.run_triage_issue(engine.github.get_triage_issue(issue, actor, requested_at))
    typer.echo(f"{result.issue}: {result.state}")
    if result.state != "triaged":
        raise typer.Exit(1)


@app.command()
def report() -> None:
    settings = Settings.from_env(fake=True)
    typer.echo(write_report(Store(settings.db_path)))


@app.command()
def simulate() -> None:
    fixture = Path("fixtures/simulation.json")
    github = FakeGitHub.load(fixture)
    data = json.loads(fixture.read_text())
    plans = {int(number): list(plan) for number, plan in data["devin"].items()}
    devin = FakeDevin(plans)
    settings = Settings.from_env(fake=True)
    store = Store(":memory:")
    engine = Engine(settings, store, devin, github)
    failed = False
    for issue_model in github.list_issues():
        run = engine.run_issue(issue_model, sleep=lambda _: None)
        typer.echo(f"{run.issue}: {run.state}")
        failed |= run.state not in TERMINAL or run.state != "verified"
    typer.echo(write_report(store))
    if failed:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
