# Guide — P3-08 A/B Testing

## Why multi-variant endpoints

A traditional deployment flips 100% of traffic from old model to new model at once.
If the new model is worse, every user is affected before you notice. A multi-variant
endpoint lets you route a small percentage of traffic to the new model first, measure
its performance in production, and only roll it out fully once you have evidence it works.

## How SageMaker routes traffic without TargetVariant

When you send requests with no `TargetVariant` header, SageMaker uses the `InitialVariantWeight`
values to do probabilistic routing. With weights 9 and 1 (sum=10), approximately 90% of
requests go to the current variant and 10% to the challenger. It is not perfectly deterministic
per-request, but over 1000 requests you will see the ratio converge.

## The decision rule: AUC delta threshold

A challenger that is only 0.001 AUC better may be within statistical noise. The 0.01 threshold
is a business decision: is it worth the deployment risk and operational cost for a 0.01 AUC
improvement? In practice this threshold should come from: what AUC delta translates to meaningful
business outcomes (e.g., additional revenue, fewer false positives).

This project's real run is a concrete example of the rule doing its job: the challenger
(deeper trees, lower learning rate, more estimators — `max_depth=7, learning_rate=0.05,
n_estimators=200`) scored val_AUC 0.9294 against the production model's 0.9289, a delta of
only +0.0005. That is comfortably inside the 0.01 threshold, so the rule's output is "keep
current" — more capacity and a slower learning rate did not buy a meaningful improvement on
this dataset. That is itself a useful result: it tells you to look at features or a different
model family next, not just deeper trees.

## CloudWatch per-variant metrics

SageMaker automatically publishes invocation counts broken down by `VariantName` dimension to
CloudWatch. You can also see per-variant `ModelLatency` and `OverheadLatency`. The `evaluate_winner.py`
script reads these to understand actual traffic distribution, but for AUC you need to run inference
on your hold-out set — CloudWatch does not know your model's accuracy.

## The shift_traffic flow

`update_endpoint_weights_and_capacities()` is a live update — no endpoint recreation needed.
The shift takes effect within seconds. This is the correct way to do a gradual rollout:
90/10 → 50/50 → 0/100, pausing to evaluate at each step.

## Verifying the decision rule without AWS

`load_current_model`, `train_challenger`, and `apply_decision_rule` have no AWS dependency at
all — they only need a local MLflow registry and the training data. That means the entire
"is the challenger worth shipping" question can be answered for real with zero AWS account: load
the real production model, train a real challenger with the configured hyperparameters, compute
its real val_AUC, and run it through the actual decision rule. This project did exactly that
against `experiment-tracking/`'s real registry, and the result (keep current, delta +0.0005) is
genuine signal — not a toy number. What stays unverified is purely the AWS plumbing: whether
SageMaker's weighted routing produces a ratio close to 90/10 in practice, and whether CloudWatch's
per-variant metrics line up with what `invoke_traffic.py` observed locally.

## Promoting safely

`promote_winner.py`'s registry-mutating calls (`mlflow.register_model()`,
`set_registered_model_alias()`) were verified against a disposable temp registry, never the
shared one other projects depend on. That is the same discipline you'd want in a real team:
never point a "let me just check this works" script at the production registry. Use a scratch
copy, verify the logic, then run the real script once you trust it.

## Interview framing

"I implement model A/B testing using SageMaker's multi-variant endpoints: start with a 90/10
traffic split, measure the challenger's performance under real traffic, apply a quantitative
AUC improvement threshold to make the promotion decision, and use live traffic shifts to roll
out gradually. No big-bang deployments. I also know that not every challenger should ship —
my own test run found a challenger with deeper trees and more estimators only beat baseline by
0.0005 AUC, well under threshold, so the rule correctly said keep the current model."
