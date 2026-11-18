# Human-Owned Engineering, AI-Assisted Implementation

## Purpose and precedence

This document defines the collaboration and learning rules for engineering work in Personal AI Workbench. The Project Owner retains authority over scope, architecture, approvals, and acceptance. Coding Agents assist with analysis and implementation within an explicitly authorized task.

The approved Frozen Engineering Scope v1.0 is the boundary for the current engineering cycle. Its canonical scope and exclusions are recorded in [Frozen Engineering Scope v1.0](frozen-engineering-scope-v1.0.md). Any work outside that scope requires explicit Project Owner approval before implementation.

## Human and Coding Agent responsibilities

### Project Owner

- Owns product intent, priorities, scope, architecture decisions, and final acceptance.
- Approves additions or changes to the frozen scope, technology decisions that have not already been approved, and consequential design choices.
- Reviews milestone capability evidence and decides whether the milestone is accepted.
- Explicitly authorizes commits, pushes, releases, or other external publication actions.

### Coding Agent

- Reads `PROJECT_CONTEXT.md`, the applicable governance documents, relevant code, tests, and Git state before work.
- Implements only the authorized task and preserves existing workspace changes.
- May investigate options and make reversible implementation choices within approved decisions; it must label proposals as proposals and must not convert them into architecture decisions.
- Reports evidence, changed files, validation performed, limitations, and unresolved decisions. It does not claim human mastery or Owner acceptance on the Owner's behalf.
- Does not expand scope, add dependencies, or commit/push unless explicitly authorized.

### Architecture and approval authority

Architecture decisions belong to the Project Owner. An Agent may document alternatives, impacts, and a recommendation, but that recommendation is not a decision. When work requires an unresolved decision, the Agent records the blocker and requests the Owner's decision rather than silently choosing a lasting direction. Approval of a task authorizes only the stated task and its necessary implementation details; it does not approve unrelated scope.

## Phase → Milestone → Task

Engineering work is organized as **Phase → Milestone → Task**:

- **Phase** groups related outcomes in the approved engineering scope.
- **Milestone** defines a reviewable capability outcome within a Phase, including completion evidence and the relevant Learning Gate.
- **Task** is a bounded unit of authorized work that contributes to a Milestone.

Tasks inherit their boundaries from the approved Milestone and Frozen Scope. Splitting work into tasks does not authorize additional scope. A change to a Phase or Milestone boundary requires explicit Project Owner approval.

## Knowledge Mastery (L1–L4)

Knowledge Mastery describes the human learner's understanding and ability to work with a subject. It is separate from the L1/L2/L3 Minimum Sufficient Review levels, which describe the depth of code review. The same level labels do not make these systems interchangeable.

| Level | Human capability | Evidence examples |
|---|---|---|
| **L1 — Recognize and explain** | The learner can identify the concept, explain its basic purpose and vocabulary, and distinguish it from closely related concepts. | A clear explanation in their own words; identification of the concept in a concrete example. |
| **L2 — Explain mechanics and trade-offs** | The learner can describe how the concept works, why the design is used, its assumptions, and relevant trade-offs or failure cases. | Walk-through of a flow or design; reasoned comparison of alternatives and limitations. |
| **L3 — Apply independently** | The learner can implement or use the concept, diagnose ordinary failures, and adapt it to a bounded engineering problem without relying on an Agent to make the core decisions. | A working change plus explanation of key choices, debugging steps, and validation. |
| **L4 — Judge and guide** | The learner can make context-sensitive design judgments, evaluate competing approaches, identify systemic risks, and explain or review the approach for others. | Defensible design review, trade-off analysis, or guidance that addresses alternatives and operational consequences. |

Mastery is assessed for the relevant capability and evidence, not inferred from task completion, generated code, or an Agent's assertion. The Project Owner owns the learning assessment; an Agent may help prepare evidence and identify gaps.

## Learning Gate

Each Milestone states the Knowledge Mastery level expected for the capability it introduces or exercises and the evidence by which the human learner can demonstrate it. Before a Milestone is considered complete, the learner reviews the implementation and demonstrates the stated level through explanation, walkthrough, or practical evidence appropriate to the capability.

If the evidence does not meet the stated level, record the gap and the learning action needed. The Project Owner decides whether the Milestone is accepted, needs further learning or implementation, or should be explicitly re-scoped. An Agent must not mark the Learning Gate passed solely because code or tests pass. The expected mastery level must not be raised or lowered silently during implementation.

## Milestone Capability Review

At Milestone completion, review both the delivered capability and the human learning outcome. The review records:

1. The approved outcome and its acceptance evidence.
2. What was implemented and how it behaves, including known limitations.
3. The learner's demonstrated Knowledge Mastery level and supporting evidence.
4. Any remaining gaps, risks, or unresolved decisions.
5. The Project Owner's disposition: accepted, further work required, or scope decision required.

The review is a human-owned acceptance point. Agent analysis can support it but cannot replace the Project Owner's decision.

## Code Review, testing, and commits

Continue to use the existing **L1/L2/L3 Minimum Sufficient Review (CR Policy)** in `PROJECT_CONTEXT.md`: L1 lightweight review, L2 targeted code review, and L3 deep architecture review, selected according to change risk. These are review-depth categories, not Knowledge Mastery levels. A CR level does not establish a learner's mastery, and a Learning Gate does not determine the required code review depth.

Review and validation evidence must be truthful and proportionate to the change. Tests passing do not by themselves prove product acceptance or human mastery. The Project Owner reviews milestone evidence and accepts the result.

Commit and push are separate actions from implementation and review. They require explicit Project Owner authorization unless an existing task explicitly includes them. A completed review is not implied commit approval.

## Scope changes

The Frozen Engineering Scope v1.0 remains fixed for this cycle. An Agent may surface a discovered need and describe its impact, but must not implement it as an assumed extension. The Project Owner must explicitly approve a scope addition before work on that addition begins; the approved change should be reflected in the governing scope record.
