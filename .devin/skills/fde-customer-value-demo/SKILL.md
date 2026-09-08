---
name: fde-customer-value-demo
description: "Builds evidence-led customer value demos and adoption plans as a technically credible Cognition forward-deployed engineer."
---

# Customer Value Demo Checklist

Use this checklist to find, prove, and expand a Devin workflow inside a target company.

## 1. Start from observed pain

- Identify the workflow as engineers perform it, in their existing system of work: repositories, tickets, CI, review, chat, and operational tools.
- Name each affected persona and the step where they wait, repeat work, context-switch, make errors, or assume risk.
- Separate **observed**, **customer-reported**, **inferred**, and **unknown** claims; cite the available source for each.
- Quantify only with evidence:
  - **Frequency:** how often the event occurs.
  - **Reach:** how many people, teams, repositories, or services encounter it.
  - **Time/risk:** cycle time, toil, incidents, defects, or exposure.
  - **Adoption friction:** permissions, integrations, policy, behavior change, and ownership.
- Ask for missing baselines or propose how to measure them. Never manufacture numbers, workflows, or customer intent.

## 2. Rank opportunities

Score candidate workflows consistently and show the evidence or uncertainty behind every score:

- **Customer value:** meaningful time, quality, reliability, or risk improvement.
- **Workflow fit:** lands where engineers already work with minimal disruption.
- **Trust path:** can begin safely and gain permissions through demonstrated control.
- **Devin leverage:** benefits from autonomous investigation, implementation, and tool use rather than a generic assistant.
- **Deterministic proof:** has repeatable inputs, checks, and acceptance criteria.
- **Demo clarity:** can be understood quickly without hidden setup or hand-waving.

Prefer a narrow, frequent, measurable workflow over a broad showcase. State tradeoffs and disqualify ideas whose proof or trust path is weak.

## 3. Design for trust and adoption

- Meet engineers in their current intake, code, review, CI, and communication paths; avoid requiring a parallel workflow without strong evidence.
- Start read-only: inspect, reproduce, classify, summarize, or recommend before changing customer systems.
- Earn write access in explicit stages: sandbox change, draft or branch, human-approved merge, then tightly scoped automation.
- Use least privilege, bounded scope, approval points, visible diffs, deterministic checks, auditability, and rollback.
- Expose assumptions, confidence, unresolved questions, failed attempts, and cases requiring a human. Do not hide uncertainty.

## 4. Build the demo spine

Present one crisp, end-to-end story:

1. **Problem:** observed pain, persona, baseline, and why it matters.
2. **Event:** the real trigger in the customer's workflow.
3. **Devin reasoning:** evidence gathered, tools used, decisions made, and uncertainty surfaced.
4. **Output:** the artifact delivered in the system where the engineer already works.
5. **Proof:** reproducible tests, checks, comparison, or acceptance criteria.
6. **Business result:** the measured or explicitly hypothesized effect on time, quality, risk, or throughput.

Keep the reasoning technically inspectable and the proof deterministic. Label projected results as hypotheses until a pilot measures them.

## 5. Propose the pilot and expansion path

- Define the pilot cohort, repositories or services, workflow boundary, owner, duration, and baseline collection method.
- Set gates before broader access: security and compliance approval, output quality, deterministic check pass rate, human acceptance, failure handling, and measurable customer value.
- Include stop conditions and a rollback path; review false positives, misses, escalations, and adoption friction.
- Expand only after gates pass: more users, adjacent repositories, broader workflow stages, or graduated permissions.
- Tie each expansion step to new evidence and a named owner rather than assuming adoption.

## Final quality check

- The story starts with customer evidence and affected personas, not Devin capabilities.
- Every number and claim is sourced, qualified, or marked unknown.
- The chosen workflow wins on value, fit, trust, leverage, proof, and clarity.
- The demo shows an inspectable artifact and repeatable proof in the customer's system of work.
- The pilot has measurable gates, safe permissions, stop conditions, and an evidence-based expansion path.
- Remove generic AI claims, vanity session counts, speculative ROI, and sales language unsupported by evidence.
