# One-Click Full Stack Deployment
# Deploys infrastructure + application in one command
# Usage: .\scripts\deployment\0-deploy-all.ps1

param(
    [string]$Namespace = "citrus"
)

$ErrorActionPreference = "Stop"

Write-Host @"
========================================================
    Citrus-Orchestrator Platform Deployment
    Infrastructure as Code - Full Stack
========================================================
"@ -ForegroundColor Cyan

Write-Host ""
Write-Host "This will deploy:" -ForegroundColor White
Write-Host "  1. Prometheus + Grafana (Monitoring)" -ForegroundColor Gray
Write-Host "  2. Jaeger (Distributed Tracing)" -ForegroundColor Gray
Write-Host "  3. OpenTelemetry Demo (17 microservices)" -ForegroundColor Gray
Write-Host ""

# Confirm
$confirm = Read-Host "Continue? (Y/n)"
if ($confirm -eq "n") {
    Write-Host "Deployment cancelled" -ForegroundColor Yellow
    exit 0
}

Write-Host ""

# Phase 1: Infrastructure
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Phase 1: Infrastructure Layer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
& "$PSScriptRoot\1-deploy-infrastructure.ps1" -Namespace $Namespace

# Phase 2: Application
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Phase 2: Application Layer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
& "$PSScriptRoot\2-deploy-application.ps1" -Namespace $Namespace

# Success
Write-Host ""
Write-Host @"
========================================================
    Deployment Complete!
========================================================
"@ -ForegroundColor Green

Write-Host ""
Write-Host "Quick Access:" -ForegroundColor White
Write-Host ""
Write-Host "  Web Store:" -ForegroundColor Yellow
Write-Host "    kubectl port-forward -n $Namespace svc/otel-demo-frontendproxy 8080:8080" -ForegroundColor Gray
Write-Host "    http://localhost:8080" -ForegroundColor Gray
Write-Host ""
Write-Host "  Grafana:" -ForegroundColor Yellow
Write-Host "    kubectl port-forward -n $Namespace svc/monitoring-grafana 3000:80" -ForegroundColor Gray
Write-Host "    http://localhost:3000 (admin/prom-operator)" -ForegroundColor Gray
Write-Host ""
Write-Host "  Jaeger:" -ForegroundColor Yellow
Write-Host "    kubectl port-forward -n $Namespace svc/jaeger 16686:16686" -ForegroundColor Gray
Write-Host "    http://localhost:16686" -ForegroundColor Gray
Write-Host ""
Write-Host "  Prometheus:" -ForegroundColor Yellow
Write-Host "    kubectl port-forward -n $Namespace svc/monitoring-kube-prometheus-prometheus 9090:9090" -ForegroundColor Gray
Write-Host "    http://localhost:9090" -ForegroundColor Gray
Write-Host ""
Write-Host "Documentation: docs/DEPLOYMENT.md" -ForegroundColor White
