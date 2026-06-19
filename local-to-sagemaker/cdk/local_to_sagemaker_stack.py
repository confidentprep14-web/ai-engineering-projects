"""CDK stack provisioning the S3 bucket and SageMaker execution role for
P3-01 Local to SageMaker.

Deliberately does NOT use the AmazonSageMakerFullAccess managed policy.
Instead it grants an inline least-privilege policy:
  - s3:GetObject / s3:PutObject / s3:ListBucket scoped to this stack's bucket only
  - logs:CreateLogGroup / CreateLogStream / PutLogEvents scoped to the
    SageMaker training job log group prefix
  - sagemaker:CreateTrainingJob / DescribeTrainingJob / StopTrainingJob with
    resource "*" — these SageMaker actions do not support resource-level
    restriction in IAM, so "*" is correct here, not a shortcut.
"""

from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from constructs import Construct


class LocalToSagemakerStack(Stack):
    """Provisions the S3 bucket + IAM role needed to run P3-01 on SageMaker."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket = s3.Bucket(
            self,
            "TrainingBucket",
            versioned=True,
            removal_policy=RemovalPolicy.RETAIN,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        sagemaker_role = iam.Role(
            self,
            "SagemakerExecutionRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            description="Least-privilege execution role for P3-01 SageMaker training jobs",
        )

        sagemaker_role.add_to_policy(
            iam.PolicyStatement(
                sid="S3DataAccess",
                effect=iam.Effect.ALLOW,
                actions=["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
                resources=[bucket.bucket_arn, f"{bucket.bucket_arn}/*"],
            )
        )

        sagemaker_role.add_to_policy(
            iam.PolicyStatement(
                sid="CloudWatchLogsAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/sagemaker/TrainingJobs*",
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/sagemaker/TrainingJobs*:log-stream:*",
                ],
            )
        )

        # SageMaker training-job actions do not support resource-level
        # permissions in IAM (https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonsagemaker.html) —
        # resource "*" is the documented, correct scope for these actions,
        # not a placeholder for "figure this out later".
        sagemaker_role.add_to_policy(
            iam.PolicyStatement(
                sid="SagemakerTrainingJobAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "sagemaker:CreateTrainingJob",
                    "sagemaker:DescribeTrainingJob",
                    "sagemaker:StopTrainingJob",
                ],
                resources=["*"],
            )
        )

        CfnOutput(
            self,
            "BucketName",
            value=bucket.bucket_name,
            description="S3 bucket for training data and model artifacts — copy into .env as S3_BUCKET",
        )

        CfnOutput(
            self,
            "SagemakerRoleArn",
            value=sagemaker_role.role_arn,
            description="IAM role ARN SageMaker assumes during training — copy into .env as SAGEMAKER_ROLE_ARN",
        )
