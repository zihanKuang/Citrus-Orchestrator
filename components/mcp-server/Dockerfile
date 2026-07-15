# =============================================================================
# Dockerfile for MCP Server
# =============================================================================
# Single-stage build using python:3.12-slim
# - Ensures all C extensions and dependencies are correctly installed
# - Smaller than full Python (179 MB vs 1 GB)
# - Compatible with packages requiring compilation (pydantic-core, etc.)
# =============================================================================

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
# Installing directly in the final image ensures all shared libraries are available
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server.py /app/
COPY tools/ /app/tools/

# Run as non-root user for security
USER 65532:65532

# Set Python to unbuffered mode for better logging
ENV PYTHONUNBUFFERED=1

# Entry point
CMD ["python3", "/app/server.py"]

# =============================================================================
# Build & Deploy
# =============================================================================
# Build:
#   docker build -t mcp-server:v1 .
#
# Size: ~180 MB (vs 1 GB for full Python image)
#
# Trade-offs:
# - Larger than distroless (~180 MB vs ~80 MB)
# - Has shell (less secure, but easier to debug)
# - Compatible with all Python packages including C extensions
# =============================================================================
