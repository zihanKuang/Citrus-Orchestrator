# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# PRODUCTION-OPTIMIZED MULTI-STAGE BUILD FOR PYTHON
# Base stage: Minimal Alpine Linux with Python 3.12 (3.14 too bleeding-edge)
FROM alpine:3.19 AS base
RUN apk add --no-cache python3=~3.12 py3-pip

# Stage 1: Builder stage with compilation toolchain
FROM base AS builder

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install build dependencies for compiling Python packages with C extensions
# g++: C++ compiler (needed for grpcio, protobuf)
# python3-dev: Python headers
# linux-headers: Kernel headers for system calls
# musl-dev: C standard library headers for Alpine
RUN apk add --no-cache \\
    g++ \\
    python3-dev \\
    linux-headers \\
    musl-dev

# CACHE OPTIMIZATION: Copy requirements.txt first
# If requirements unchanged, pip install layer is cached
COPY requirements.txt .

# Install to a custom prefix for easy copying to runtime stage
# --prefix isolates packages from system Python
# --no-cache-dir saves ~100MB by not storing pip cache
# --no-warn-script-location suppresses PATH warnings (irrelevant in container)
RUN pip3 install \\
    --prefix=/install \\
    --no-cache-dir \\
    --no-warn-script-location \\
    -r requirements.txt

# Stage 2: Minimal runtime stage
FROM base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# SECURITY: Create non-root user
# -S: system user (no home directory, no login shell)
# -G: assign to group
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Install ONLY runtime libraries (no compilers)
# libstdc++: C++ standard library (required by grpcio at runtime)
RUN apk add --no-cache libstdc++ \\
    && rm -rf /var/cache/apk/*

# Copy installed packages from builder stage
# This includes all dependencies but NOT build tools (~200MB savings)
COPY --from=builder /install/lib/python3.12/site-packages /usr/lib/python3.12/site-packages
COPY --from=builder /install/bin /usr/local/bin

# Copy application code with correct ownership
# --chown prevents permission issues when running as non-root
COPY --chown=appuser:appgroup . .

# SECURITY: Switch to non-root user
# Prevents privilege escalation attacks
USER appuser

# Add health check for Kubernetes readiness/liveness probes
HEALTHCHECK --interval=30s --timeout=3s CMD python3 -c "import socket; s=socket.socket(); s.connect(('localhost',8080)); s.close()" || exit 1

EXPOSE 8080
ENTRYPOINT ["python", "recommendation_server.py"]
