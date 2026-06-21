# Guide — P3-10 Model Monitoring

## What SageMaker Model Monitor does

Model Monitor captures every request and response to your endpoint (via DataCaptureConfig),
runs a scheduled analysis job that compares the captured input distribution to your training
data baseline, and writes a violation report if any feature distribution has shifted significantly.

The significance test is a non-parametric test (Kolmogorov-Smirnov for numeric features).
The p-value threshold (default 0.05) determines what counts as significant drift.

## What drift detection catches

- **Numeric feature distribution shifts:** If `age` values in production suddenly skew much older
  (e.g., your app went viral with seniors), the KS test will catch this.
- **Missing value rate changes:** If a data pipeline bug starts producing nulls in a field that
  had none during training, Model Monitor flags it.
- **Categorical value frequency shifts:** If `workclass` was 60% Private during training and
  is now 20%, the chi-squared test will flag it.

## What drift detection misses

- **Label drift (concept drift):** The income distribution in the real world may change over time —
  what predicted ">50K" during a boom year may predict "<=50K" during a recession. Model Monitor
  cannot detect this because it only monitors inputs, not outcomes.
- **Subtle multivariate shifts:** A feature may have no marginal distribution change but correlate
  differently with other features. Univariate tests miss this.
- **Silent model degradation without input drift:** If the world changed but your input features
  happen to have the same distribution, no alarm fires. This is why p3-09's live accuracy evaluation
  is necessary alongside Model Monitor.
- **Sampling bias:** If DataCapture records only 10% of traffic, a small drift may not be detected
  until it becomes severe.

## The hourly schedule limitation

Model Monitor runs as a batch job at most once per hour (SageMaker's minimum cron granularity).
For a low-traffic endpoint, there may not be enough captured data in one hour to run a reliable
statistical test. SageMaker will still run the job but may produce inconclusive results.

## Reading violation p-values

A p-value of 0.0008 means: if the production distribution were the same as training, you would
observe this large a difference less than 0.08% of the time. This is strong evidence of drift.
A p-value of 0.04 means only 4% chance — still below 0.05 threshold, but weaker evidence.

## Interview framing

"I set up SageMaker Model Monitor to detect input data drift: enabled data capture at the endpoint,
computed a statistical baseline from training data, and scheduled hourly monitoring. I also know
its limitations — it monitors input distributions, not model accuracy, so it won't catch concept
drift or subtle multivariate shifts. That's why I pair it with the live accuracy evaluation from
the performance report."
