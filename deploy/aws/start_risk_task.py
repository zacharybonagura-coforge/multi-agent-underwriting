"""Start the risk agent on Fargate for one case."""

import json
import os

import boto3


def start_risk_task(case: dict) -> str:
    """Start one task. The case is sent as the RISK_CASE environment variable."""
    ecs = boto3.client("ecs", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    response = ecs.run_task(
        cluster=os.environ.get("ECS_CLUSTER", "underwriting"),
        launchType="FARGATE",
        taskDefinition="underwriting-risk-agent",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": [os.environ["ECS_SUBNET"]],
                "securityGroups": [os.environ["ECS_SECURITY_GROUP"]],
                "assignPublicIp": "DISABLED",
            }
        },
        overrides={
            "containerOverrides": [{
                "name": "risk-agent",
                "environment": [{"name": "RISK_CASE", "value": json.dumps(case)}],
            }]
        },
    )
    return response["tasks"][0]["taskArn"]
