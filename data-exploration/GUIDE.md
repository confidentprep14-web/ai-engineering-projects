# Guide — Data Exploration

## Why EDA before modeling

Skipping EDA is the fastest way to build a model that silently fails. The UCI Adult dataset
has `?` in three columns — if you read those as strings, your encoder will create a `?` category
that poisons predictions. The missing fraction matters: if 30% of `occupation` is missing,
median imputation is a different choice than if 1% is missing.

## What to look for in the output

**Class balance:** UCI Adult is roughly 76%/24% (<=50K / >50K). You need to decide whether to
use `class_weight='balanced'` in your model or upsample the minority class. Neither is always right.

**Correlation:** `education-num` and `fnlwgt` — check if they are highly correlated. If so,
dropping one may simplify the model without hurting accuracy.

**Missing values:** In UCI Adult, `workclass`, `occupation`, and `native-country` have `?` replaced
with NaN. These are the columns that will need imputation in p3-03.

## How to read the correlation table

Pearson correlation measures linear dependence. A value of +1 means perfect positive correlation,
-1 perfect negative. Values above |0.7| between features are worth investigating — one may be
derivable from the other (redundancy).

## The imputation decision

The report flags columns above the threshold. For `native-country` (which is 98% United States),
missing values likely represent the same group. For `occupation`, missing is likely not at random
(unemployed people may not report occupation). These decisions belong in your feature engineering
spec, not in train.py.

## Interview framing

"Before any feature engineering or training, I run a systematic EDA that quantifies class imbalance,
flags columns with high missing rates, and checks for correlated features — so every preprocessing
decision has a documented reason rather than being arbitrary."
