FROM python:3.12-slim

WORKDIR /app

COPY deploy/aws/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src/agents/risk.py /app/src/agents/risk.py
COPY src/agents/model_io.py /app/src/agents/model_io.py
COPY src/model/base.py /app/src/model/base.py
COPY src/model/bedrock.py /app/src/model/bedrock.py
COPY src/prompts/repository.py /app/src/prompts/repository.py
COPY src/prompts/risk.v1.md /app/src/prompts/risk.v1.md
COPY src/observability.py /app/src/observability.py
COPY deploy/aws/risk_main.py /app/risk_main.py

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV BEDROCK_MODEL_ID=us.amazon.nova-micro-v1:0

CMD ["python", "/app/risk_main.py", "bedrock"]
