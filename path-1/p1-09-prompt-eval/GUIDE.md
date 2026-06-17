# Build guide: Prompt Evaluation Framework

## What you're building and why it matters

"This prompt feels better" is not engineering. Prompt evaluation is. Real teams
maintain test suites for their prompts for the same reason they maintain test suites
for their code: to detect regressions before deployment. When you change a system
prompt and 20% of your test cases fail, you catch it before your users do.
LLM-as-judge scoring — using one LLM to evaluate another's output — is the current
best practice for open-ended evaluation. It is not perfect (the judge has biases)
but it is far better than manual review at scale.

## The decision that matters in this build

**One LLM call per dimension vs one call for all dimensions.** You could ask the judge
to score all dimensions in one call (cheaper, fewer calls) or one dimension at a time
(more accurate, more expensive). Use one call per dimension. When you bundle dimensions,
the judge anchors on the first score and adjusts the others relatively — a well-known
bias. Separate calls give independent scores.

## What will break

**The judge is not objective.** LLM judges have a length bias (longer answers score higher)
and a self-preference bias (Claude judges favour Claude responses). Mitigate by making
the scoring rubric very explicit in the judge prompt. "Score 3 means acceptable, not good"
prevents the judge from giving 4s to everything out of politeness.

**Exit code 1 requires explicit `sys.exit(1)`**, not just a non-zero return from a function.
Test this explicitly — it is the whole point of the CI integration.

## How to talk about this in an interview

"I built a prompt evaluation framework where each test case is scored on independent
dimensions by an LLM judge. The key engineering decision was one judge call per
dimension to prevent anchor bias. I can drop this in a GitHub Action — exit code 1
on any failure means the PR is blocked if prompt quality degrades."
