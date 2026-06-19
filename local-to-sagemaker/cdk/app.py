#!/usr/bin/env python3
"""CDK app entrypoint for P3-01 Local to SageMaker infrastructure."""

import aws_cdk as cdk

from local_to_sagemaker_stack import LocalToSagemakerStack

app = cdk.App()
LocalToSagemakerStack(app, "LocalToSagemakerStack")

app.synth()
