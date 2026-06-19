#!/usr/bin/env python3
"""CDK app entrypoint for P3-03 Feature Engineering infrastructure."""

import aws_cdk as cdk

from feature_engineering_stack import FeatureEngineeringStack

app = cdk.App()
FeatureEngineeringStack(app, "FeatureEngineeringStack")

app.synth()
