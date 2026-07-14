# Multi-Stage Dockerfile for MCP Server

# Stage 1: Builder (Build Dependencies)

FROM python:3.12-slim as builder

# Set work directory for build
WORKDIR /build

# Copy only requirements first (Docker layer caching optimization)
# If requirements.txt doesn't change, this layer is cached
COPY requirements.txt .

# Install dependencies to a specific directory (not system-wide)
RUN pip install --no-cache-dir \
    --target=/install \
    -r requirements.txt

# Stage 2: Runtime (Distroless)

FROM gcr.io/distroless/python3-debian12

# Set Python path to include our installed packages
ENV PYTHONPATH=/usr/local/lib/python3.12/site-packages

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local/lib/python3.12/site-packages

# Set working directory for application
WORKDIR /app

# Copy application code
COPY server.py /app/
COPY tools/ /app/tools/

# Distroless images don't have USER command working well, but they run as
# non-root by default (user "nonroot", UID 65532)
# This is automatically secure - no need to add USER directive

# Set entry point
# Note: Distroless uses a specific Python path
# CMD must be in exec form (JSON array) because there's no shell
CMD ["server.py"]