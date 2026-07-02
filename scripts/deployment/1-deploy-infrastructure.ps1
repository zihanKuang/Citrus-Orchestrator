# Infrastructure Deployment Script
# Deploys Prometheus + Grafana + Jaeger to Kubernetes cluster
# Usage: .\scripts\deployment\1-deploy-infrastructure.ps1

param(
    [string]$Namespace = "citrus",
    [switch]$SkipNamespace
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Infrastructure Layer Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Create namespace
if (-not $SkipNamespace) {
    Write-Host "[1/5] Creating namespace: $Namespace" -ForegroundColor Yellow
    kubectl create namespace $Namespace --dry-run=client -o yaml | kubectl apply -f -
    Write-Host "  Namespace ready" -ForegroundColor Green
    Write-Host ""
}

# Step 2: Add Helm repositories
Write-Host "[2/5] Adding Helm repositories" -ForegroundColor Yellow
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>&1 | Out-Null
helm repo add jaegertracing https://jaegertracing.github.io/helm-charts 2>&1 | Out-Null
helm repo update | Out-Null
Write-Host "  Helm repositories updated" -ForegroundColor Green
Write-Host ""

# Step 3: Deploy Prometheus + Grafana
Write-Host "[3/5] Deploying Prometheus + Grafana" -ForegroundColor Yellow
Write-Host "  (This may take 1-2 minutes...)" -ForegroundColor Gray

$monitoringInstalled = helm list -n $Namespace 2>$null | Select-String "monitoring"
if ($monitoringInstalled) {
    Write-Host "  Monitoring stack exists, upgrading..." -ForegroundColor Yellow
    helm upgrade monitoring prometheus-community/kube-prometheus-stack `
        -n $Namespace `
        --values deploy/helm/monitoring-stack-values.yaml `
        --wait --timeout 5m
} else {
    helm install monitoring prometheus-community/kube-prometheus-stack `
        -n $Namespace `
        --values deploy/helm/monitoring-stack-values.yaml `
        --wait --timeout 5m
}

Write-Host "  Monitoring stack deployed" -ForegroundColor Green
Write-Host ""

# Step 4: Wait for Prometheus
Write-Host "[4/5] Waiting for Prometheus to be ready" -ForegroundColor Yellow
kubectl wait --for=condition=ready pod `
    -l app.kubernetes.io/name=prometheus `
    -n $Namespace --timeout=120s 2>$null | Out-Null
Write-Host "  Prometheus ready" -ForegroundColor Green
Write-Host ""

# Step 5: Deploy Jaeger
Write-Host "[5/5] Deploying Jaeger" -ForegroundColor Yellow

$jaegerInstalled = helm list -n $Namespace 2>$null | Select-String "jaeger"
if ($jaegerInstalled) {
    Write-Host "  Jaeger exists, upgrading..." -ForegroundColor Yellow
    helm upgrade jaeger jaegertracing/jaeger `
        -n $Namespace `
        --values deploy/helm/jaeger-values.yaml `
        --wait --timeout 3m
} else {
    helm install jaeger jaegertracing/jaeger `
        -n $Namespace `
        --values deploy/helm/jaeger-values.yaml `
        --wait --timeout 3m
}

Write-Host "  Jaeger deployed" -ForegroundColor Green
Write-Host ""

# Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Infrastructure Deployment Complete" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Deployed releases:" -ForegroundColor White
helm list -n $Namespace

Write-Host ""
Write-Host "Access services:" -ForegroundColor White
Write-Host "  Prometheus: kubectl port-forward -n $Namespace svc/monitoring-kube-prometheus-prometheus 9090:9090" -ForegroundColor Gray
Write-Host "  Grafana:    kubectl port-forward -n $Namespace svc/monitoring-grafana 3000:80" -ForegroundColor Gray
Write-Host "  Jaeger:     kubectl port-forward -n $Namespace svc/jaeger 16686:16686" -ForegroundColor Gray
Write-Host ""
Write-Host "Next: Run .\scripts\deployment\2-deploy-application.ps1" -ForegroundColor Yellow
