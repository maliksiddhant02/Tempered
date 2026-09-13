---
name: hackathon-idea-evaluator
description: Rigorously scores and evaluates hackathon ideas across 6 dimensions (Novelty, Feasibility, Scalability, Impact, Demo-ability, Domain Fit) with anti-inflation rules. This skill should be used when comparing multiple hackathon ideas, validating a chosen approach, or stress-testing a pitch before submission.
metadata:
  mcpmarket-version: 1.0.0
---
# Hackathon Idea Evaluator

Score hackathon ideas honestly across 6 dimensions with built-in anti-inflation rules to prevent overconfident scoring.

**Core principle:** Honest evaluation saves you from building the wrong idea. Inflated scores lose hackathons.

## When to Use This Skill

- When comparing multiple hackathon ideas and need to pick one
- When validating whether your chosen approach is strong enough
- When stress-testing your pitch before judges
- When a teammate proposes an idea and you need objective assessment
- Before committing your hackathon's limited hours to building

## Scoring Rubric

Score each dimension 1-10:

| Dimension | 1-3 (Weak) | 4-6 (Average) | 7-10 (Strong) |
|-----------|-----------|----------------|----------------|
| **Novelty** | Clone of existing solution | Incremental improvement | Genuinely new approach + tech |
| **Feasibility** | Can't build in time | Possible with compromises | Clearly achievable MVP |
| **Scalability** | Works for demo only | Works for thousands | Architecture handles millions |
| **Impact** | Nice-to-have | Solves real problem | Transforms lives/industry |
| **Demo-ability** | Hard to show live | Requires explanation | WOW factor in 3 minutes |
| **Domain Fit** | Tangential to domain | Related to domain | Core domain problem |

**Target: >= 48/60 on corrected (honest) scoring.**

## Anti-Inflation Rules

These rules prevent the most common scoring biases:

### Rule 1: Novelty — Score the TECH, Not the Metaphor
- If the underlying algorithm/technology exists elsewhere (e.g., geo-clustering, matching engines, recommendation systems), **novelty caps at 7** regardless of how clever the framing is
- "Tinder for trucks" uses matching engines that Uber already has → Novelty <= 7
- "Package social network" uses geo-clustering that DHL already does → Novelty <= 7
- Only score 8+ if both the FRAMING and the core TECHNOLOGY are genuinely new

### Rule 2: Feasibility — Penalize Data & Hardware Gaps
- If the idea needs real historical data you don't have → **deduct 2 points**
- If the idea needs hardware you can't demo → **deduct 2 points**
- If the idea needs API integrations that don't exist or are paid → **deduct 1 point**
- A working demo with synthetic data scores lower than a working demo with real data

### Rule 3: Impact — Model Adoption Barriers
- Will the target user actually CHANGE their behavior to use this?
- Are there cultural barriers? (e.g., Indians prefer doorstep delivery over lockers)
- Is there a chicken-and-egg problem? (two-sided marketplaces)
- Does the business model close at small volumes?
- Impact = technical potential x adoption probability

### Rule 4: Demo-ability — Mock != Real
- Judges can distinguish mock data from real data → **deduct 1 point** for mock-dependent demos
- Static dashboards score lower than interactive demos
- If the core value prop can't be shown LIVE, it's a pitch, not a hackathon entry

## Instructions

When a user asks to evaluate a hackathon idea:

1. **Understand the idea fully** — Ask clarifying questions if needed
2. **Score each dimension** — Apply anti-inflation rules honestly
3. **Provide justification** — Every score needs evidence

Output format:
```markdown
## [Idea Name] — Evaluation

| Dimension | Score | Justification |
|-----------|-------|---------------|
| Novelty | X/10 | [Evidence-based reasoning] |
| Feasibility | X/10 | [Time, data, hardware assessment] |
| Scalability | X/10 | [Architecture analysis] |
| Impact | X/10 | [Market size x adoption probability] |
| Demo-ability | X/10 | [What can be shown live vs slides] |
| Domain Fit | X/10 | [How core is this to the domain?] |
| **TOTAL** | **XX/60** | |

### Verdict
[Build / Pivot / Abandon] — [One sentence reason]

### Biggest Risk
[The single dimension that could kill this idea]

### How to Improve Score
[Specific actions to gain +3-5 points]
```

4. **Compare ideas** — If evaluating multiple, rank with justification:

```markdown
| Rank | Idea | Score | Strength | Weakness |
|------|------|-------|----------|----------|
| 1 | [Name] | XX/60 | [Best dimension] | [Worst dimension] |
```

## Combination Strategy

When two ideas score 45-50 individually, check if combining them creates a 55+ idea:

- Do they address complementary weaknesses?
- Do they share infrastructure (same backend, same data)?
- Can you demo both in 3 minutes (1.5 min each)?
- Does the combination tell a stronger story than either alone?

**Example:** AddressIQ (address scoring, 53/60) + PackBuddy (package clustering, 49/60) = SmartRoute (~56/60) — verified addresses feed the clustering engine, creating something neither achieves alone.

## Red Flags — Abandon the Idea

- Total score < 40/60 after honest evaluation
- Feasibility < 5 (you literally can't build it)
- Demo-ability < 5 (you can't show it working)
- Novelty < 4 (judges have seen this exact thing)
- Impact < 5 AND Novelty < 5 (neither innovative nor impactful)

## Remember

- Honest evaluation now saves wasted hackathon hours
- The idea that SCORES lower but can be DEMO'D better often wins
- Combine two 48-scoring ideas into one 55+ idea
- Judges remember the WOW moment, not the slide deck
- Test your pitch on a non-technical friend — if they don't get it in 30 seconds, simplify
