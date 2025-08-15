FROM public.ecr.aws/lambda/python:3.13

# Work in Lambda task root
COPY src/ ${LAMBDA_TASK_ROOT}/

# Install deps
COPY requirements.txt .
RUN pip install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Copy only the runtime code (keep paths so modules import cleanly)
# This gives you packages "functions" and "analytics" at the task root.
COPY src/functions/ ./functions/
COPY src/analytics/ ./analytics/
COPY src/__init__.py ./

# Default command (Terraform will override per Lambda)
CMD ["functions.client_rearc_lambda.handler"]
