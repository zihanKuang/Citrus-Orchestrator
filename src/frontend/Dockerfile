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

# OPTIMIZED MULTI-STAGE BUILD
# Stage 1: Build stage with full toolchain
# Uses official Go Alpine image for minimal size while maintaining build tools
FROM --platform=$BUILDPLATFORM golang:1.25.6-alpine@sha256:98e6cffc31ccc44c7c15d83df1d69891efee8115a5bb7ede2bf30a38af3e3c92 AS builder
ARG TARGETOS
ARG TARGETARCH
WORKDIR /src

# Install build dependencies (ca-certificates for HTTPS, tzdata for timezone support)
RUN apk add --no-cache ca-certificates tzdata

# CACHE OPTIMIZATION: Copy dependency files first
# Docker layer caching: if go.mod/go.sum unchanged, this layer is reused
# Prevents re-downloading dependencies on every code change
COPY go.mod go.sum ./
RUN go mod download && go mod verify

# Copy source code after dependencies (changes more frequently)
COPY . .

# Compile with optimizations:
# -ldflags="-s -w" removes debug info and symbol table (reduces binary size 20-30%)
# CGO_ENABLED=0 produces static binary (no libc dependency)
ARG SKAFFOLD_GO_GCFLAGS
RUN GOOS=${TARGETOS} GOARCH=${TARGETARCH} CGO_ENABLED=0 go build \\
    -ldflags="-s -w" \\
    -gcflags="${SKAFFOLD_GO_GCFLAGS}" \\
    -o /go/bin/frontend .

# Stage 2: Runtime stage (minimal distroless image)
# Distroless contains ONLY runtime dependencies, no shell or package manager
# Reduces attack surface and image size (final image ~20MB vs 300MB+ with full Alpine)
FROM gcr.io/distroless/static-debian12:nonroot
WORKDIR /app

# Copy compiled binary and runtime assets from builder stage
COPY --from=builder /go/bin/frontend /app/server
COPY --from=builder /src/templates /app/templates
COPY --from=builder /src/static /app/static
# Copy CA certificates for HTTPS calls to backend services
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

# SECURITY: Run as non-root user (UID 65532 is 'nonroot' in distroless)
# Prevents container breakout exploits that require root privileges
USER nonroot:nonroot

# Definition of this variable is used by 'skaffold debug' to identify a golang binary.
# Default behavior - a failure prints a stack trace for the current goroutine.
ENV GOTRACEBACK=single

EXPOSE 8080
ENTRYPOINT ["/app/server"]
