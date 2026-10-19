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
    tasks = response.get("tasks") or []
    if not tasks:
        raise RuntimeError(f"ECS did not start a task: {response.get('failures')}")
    task_arn = tasks[0].get("taskArn")
    if task_arn is None:
        raise RuntimeError("ECS task is missing a task ARN")
    return task_arn
