# Application Deployment Script
# Deploys OpenTelemetry Demo to Kubernetes cluster
# Usage: .\scripts\deployment\2-deploy-application.ps1
# Prerequisites: Infrastructure must be deployed first

param(
    [string]$Namespace = "citrus",
    [string]$ReleaseName = "otel-demo",
    [string]$Version = "0.40.9"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Application Layer Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Verify infrastructure
Write-Host "[1/4] Verifying infrastructure layer" -ForegroundColor Yellow
$monitoring = helm list -n $Namespace 2>$null | Select-String "monitoring"
$jaeger = helm list -n $Namespace 2>$null | Select-String "jaeger"

if (-not $monitoring) {
    Write-Host "  ERROR: Monitoring stack not found" -ForegroundColor Red
    Write-Host "  Run 1-deploy-infrastructure.ps1 first" -ForegroundColor Red
    exit 1
}

if (-not $jaeger) {
    Write-Host "  ERROR: Jaeger not found" -ForegroundColor Red
    Write-Host "  Run 1-deploy-infrastructure.ps1 first" -ForegroundColor Red
    exit 1
}

Write-Host "  Infrastructure ready" -ForegroundColor Green
Write-Host ""

# Step 2: Add Helm repository
Write-Host "[2/4] Adding OpenTelemetry Helm repository" -ForegroundColor Yellow
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts 2>&1 | Out-Null
helm repo update | Out-Null
Write-Host "  Repository updated" -ForegroundColor Green
Write-Host ""

# Step 3: Deploy application
Write-Host "[3/4] Deploying OpenTelemetry Demo v$Version" -ForegroundColor Yellow
Write-Host "  (This may take 3-5 minutes...)" -ForegroundColor Gray
Write-Host ""

$appInstalled = helm list -n $Namespace 2>$null | Select-String $ReleaseName
if ($appInstalled) {
    Write-Host "  Application exists, upgrading..." -ForegroundColor Yellow
    helm upgrade $ReleaseName open-telemetry/opentelemetry-demo `
        --version $Version `
        -n $Namespace `
        --values deploy/helm/otel-demo-values.yaml
} else {
    helm install $ReleaseName open-telemetry/opentelemetry-demo `
        --version $Version `
        -n $Namespace `
        --values deploy/helm/otel-demo-values.yaml
}

Write-Host "  Helm release created" -ForegroundColor Green
Write-Host ""

# Step 4: Wait for services
Write-Host "[4/4] Waiting for services to start" -ForegroundColor Yellow
Write-Host "  (Pulling images and starting ~20 services...)" -ForegroundColor Gray

$timeout = 300  # 5 minutes
$elapsed = 0
$interval = 10

while ($elapsed -lt $timeout) {
    $frontend = kubectl get pods -n $Namespace `
        -l app.kubernetes.io/component=frontend `
        -o jsonpath='{.items[0].status.phase}' 2>$null
    
    if ($frontend -eq "Running") {
        Write-Host "  Frontend ready" -ForegroundColor Green
        break
    }
    
    Start-Sleep -Seconds $interval
    $elapsed += $interval
    Write-Host "  Still waiting... ($elapsed/$timeout seconds)" -ForegroundColor Gray
}

Write-Host ""

# Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Application Deployment Complete" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Deployed releases:" -ForegroundColor White
helm list -n $Namespace

Write-Host ""
Write-Host "Access the application:" -ForegroundColor White
Write-Host "  kubectl port-forward -n $Namespace svc/$ReleaseName-frontendproxy 8080:8080" -ForegroundColor Yellow
Write-Host "  Then visit: http://localhost:8080" -ForegroundColor Gray
Write-Host ""
Write-Host "View traces:" -ForegroundColor White
Write-Host "  kubectl port-forward -n $Namespace svc/jaeger 16686:16686" -ForegroundColor Yellow
Write-Host "  Then visit: http://localhost:16686" -ForegroundColor Gray
Write-Host ""
Write-Host "View metrics:" -ForegroundColor White
Write-Host "  kubectl port-forward -n $Namespace svc/monitoring-grafana 3000:80" -ForegroundColor Yellow
Write-Host "  Then visit: http://localhost:3000 (admin/prom-operator)" -ForegroundColor Gray
