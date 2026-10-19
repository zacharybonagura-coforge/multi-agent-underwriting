# 1. IAM Role

The trusted entity I select is Elastic Container Service, use case Elastic Container Service Task. I would then add permissions for one Bedrock call: `bedrock:InvokeModel` and `bedrock:GetInferenceProfile`, limited to Amazon Nova Micro (`us.amazon.nova-micro-v1:0`). I would not attach a managed policy.

For the role name, it would be `underwriting-risk-agent-task`. For the description, it would be "Task role for the underwriting risk agent. Allows that ECS task to invoke Amazon Nova Micro and to read that inference profile."

For trusted entities, the principal is `ecs-tasks.amazonaws.com`, and the action is `sts:AssumeRole`. A condition limits assumption to ECS in this account: `aws:SourceAccount` equals the account ID, and `aws:SourceArn` matches `arn:aws:ecs:REGION:ACCOUNT_ID:*`. A user, an EC2 instance, or a Lambda function cannot assume this role.

For permissions, one inline policy with three statements:

- \texttt{bedrock:InvokeModel} on \texttt{arn:aws:bedrock:REGION:ACCOUNT\_ID:inference-profile/us.amazon.nova-micro-v1:0}. \texttt{BedrockAdapter.generate} calls \texttt{InvokeModel} with model id \texttt{us.amazon.nova-micro-v1:0}. That id is an inference profile, so IAM checks this profile ARN. Without this statement the score call is denied before Nova Micro runs. The resource is this one profile, so the role cannot invoke any other model.
- \texttt{bedrock:InvokeModel} on the Nova Micro foundation model in \texttt{us-east-1}, \texttt{us-east-2}, and \texttt{us-west-2}, only when \texttt{bedrock:InferenceProfileArn} is that same profile. The US profile does not host the model. It forwards the request to the foundation model in one of those three regions, and IAM requires \texttt{InvokeModel} on that destination as well as on the profile. The condition allows those foundation models only when the call came through this profile. A direct call to \texttt{amazon.nova-micro-v1:0}, skipping the profile, does not match the condition and is denied.
- \texttt{bedrock:GetInferenceProfile} on that same profile. Bedrock reads the profile to learn which foundation model and which regions it routes to. That read is a separate action from \texttt{InvokeModel}. Without it, a call that names the profile can still fail. The resource is the one profile the container uses, so the role cannot read every profile in the account.

ECR pull and CloudWatch logs stay on the ECS execution role from Week 3. They are not on this role. The risk agent also gets no S3 access and no access to the applicant store.

For tags, `Agent` = `risk` and `Component` = `underwriting`. Tags only label the role. They do not grant access.

Then create role.

I ensure it has the correct scoped policy attached by opening the role after creation. The Trust relationships tab shows only `ecs-tasks.amazonaws.com` with the account condition. The Permissions tab shows only that inline policy, with those three statements, and no `AmazonBedrockFullAccess`, `AdministratorAccess`, or other managed policy.

## 2. Deploy the container

The image runs only the risk agent. `risk_agent` is unchanged. `deploy/aws/bedrock_adapter.py` implements the same `generate` call the agent already uses, and it calls `bedrock:InvokeModel` on `us.amazon.nova-micro-v1:0`. There are no AWS keys in the image. On Fargate, boto3 uses the task role from step 1. With no arguments it scores `ada-lovelace-auto`: good credit, one prior claim, product auto. The golden tier for that case is `medium`. A JSON file argument, or a `RISK_CASE` environment variable, scores a different case with the same image.

`deploy/aws/Dockerfile` starts from `python:3.12-slim` and installs `pydantic` and `boto3`. It copies only the risk path: `risk.py`, `model_io.py`, `model/base.py`, `prompts/repository.py`, `risk.v1.md`, and `observability.py`, plus the Bedrock adapter and `risk_main.py`. Intake, enrichment, recommendation, Ollama, and the store stay out of the image. The container runs `python /app/risk_main.py bedrock`. The same `main` takes an Ollama adapter when you pass `ollama` instead.

From the repo root, with `ACCOUNT_ID` and `REGION` replaced:

```bash
aws ecr create-repository --repository-name underwriting-risk-agent --region REGION

aws ecr get-login-password --region REGION \
  | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com

docker build -f deploy/aws/Dockerfile -t underwriting-risk-agent .

docker tag underwriting-risk-agent:latest \
  ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/underwriting-risk-agent:latest

docker push ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/underwriting-risk-agent:latest
```

The task definition is `deploy/aws/task-definition.json`. `executionRoleArn` is the Week 3 ECS execution role, which pulls from ECR and writes CloudWatch logs. `taskRoleArn` is `underwriting-risk-agent-task`. I would create the log group, register the task definition, and run it on Fargate:

```bash
aws logs create-log-group --log-group-name /ecs/underwriting-risk-agent --region REGION

aws ecs register-task-definition \
  --cli-input-json file://deploy/aws/task-definition.json \
  --region REGION

aws ecs run-task \
  --cluster underwriting \
  --launch-type FARGATE \
  --task-definition underwriting-risk-agent \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxxxxx],securityGroups=[sg-xxxxxxxx],assignPublicIp=DISABLED}" \
  --region REGION
```

I would confirm the task stopped with exit code 0, then read the log stream. A correct result is JSON with `risk_score` from 0 to 100, `risk_factors` drawn from the case, and `tier` set by the agent from that score. For this input the expected tier is `medium`.

## 3. Networking

The risk task is not a service. Nothing on the internet connects to it. It starts, calls Bedrock, writes a log line, and exits. I place it in a private subnet and set `assignPublicIp` to `DISABLED`. The task has no public address.

The subnet is a private subnet in the lab VPC, for example `underwriting-private-a`. Its route table has the local VPC route only. It has no route to an internet gateway and no NAT gateway. A task in that subnet cannot be reached from the internet, and it cannot open its own connection to the public internet.

The task still has to reach four AWS APIs. I add VPC endpoints in that same private subnet so those calls stay on the AWS network:

| Endpoint | Why the task needs it |
|---|---|
| `com.amazonaws.REGION.ecr.api` | The Fargate agent asks ECR for the image manifest. |
| `com.amazonaws.REGION.ecr.dkr` | The Fargate agent downloads the image layers' instructions. |
| `com.amazonaws.REGION.s3` (gateway) | ECR stores the image layers in S3. |
| `com.amazonaws.REGION.logs` | The container writes the score to CloudWatch Logs. |
| `com.amazonaws.REGION.bedrock-runtime` | `risk_main.py` calls `InvokeModel` on Nova Micro. |

Private DNS is enabled on the interface endpoints, so the normal AWS hostnames resolve to those endpoints. The S3 endpoint is a gateway endpoint on the private route table.

Security group `underwriting-risk-task` is attached to the task.

- Inbound: no rules. Nothing is allowed to open a connection to the task.
- Outbound: TCP 443 to security group `underwriting-vpc-endpoints`. That covers ECR, CloudWatch Logs, and Bedrock.
- Outbound: TCP 443 to the S3 prefix list for this region. The gateway endpoint has no security group, so this rule is what allows the image-layer download.

Security group `underwriting-vpc-endpoints` is attached to the interface endpoints.

- Inbound: TCP 443 from `underwriting-risk-task` only.
- Outbound: none required for these calls. The endpoints receive the task's requests and answer them.

`start_risk_task` sets `assignPublicIp` to `DISABLED` on every run, so the task never receives a public address. The subnet id and the security group id come from `ECS_SUBNET` and `ECS_SECURITY_GROUP`. Those are set to the private subnet and to `underwriting-risk-task` before the call. The endpoints are how that private task reaches ECR, S3, CloudWatch Logs, and Bedrock.
