"""Bedrock adapter for the risk agent. Credentials come from the ECS task role."""

import json
import os

import boto3
from botocore.config import Config
from botocore.exceptions import ConnectTimeoutError, ReadTimeoutError

from model.base import Generation, ModelTimeoutError


class BedrockAdapter:
    """Call Amazon Nova through Bedrock InvokeModel."""

    provider = "bedrock"

    def __init__(self, model_id: str | None = None, region: str | None = None) -> None:
        self.model_id = model_id or os.environ.get("BEDROCK_MODEL_ID", "us.amazon.nova-micro-v1:0")
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=region or os.environ.get("AWS_REGION", "us-east-1"),
            config=Config(connect_timeout=10, read_timeout=120, retries={"max_attempts": 1}),
        )

    def generate(self, prompt: str) -> Generation:
        """Send one prompt and return the model text plus token counts."""
        body = {
            "schemaVersion": "messages-v1",
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": 512, "temperature": 0},
        }
        try:
            response = self._client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
        except (ConnectTimeoutError, ReadTimeoutError) as exc:
            raise ModelTimeoutError(str(exc)) from exc
        payload = json.loads(response["body"].read())
        text = payload["output"]["message"]["content"][0]["text"].strip()
        usage = payload.get("usage", {})
        return Generation(
            text=text,
            input_tokens=int(usage.get("inputTokens", 0)),
            output_tokens=int(usage.get("outputTokens", 0)),
        )
