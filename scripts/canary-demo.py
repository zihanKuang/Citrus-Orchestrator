#!/usr/bin/env python3
"""
MLOps Canary Deployment - Demo Version
Simplified version for demonstration purposes
"""

import requests
import subprocess
import time

class PrometheusClient:
    def __init__(self, url="http://localhost:9090"):
        self.url = url
    
    def query(self, promql):
        try:
            resp = requests.get(f"{self.url}/api/v1/query", params={'query': promql}, timeout=10)
            data = resp.json()
            if data['status'] == 'success' and data['data']['result']:
                return float(data['data']['result'][0]['value'][1])
            return 0.0
        except:
            return 0.0

def get_metrics(service, prom):
    """Query Prometheus for service metrics"""
    
    # Error rate
    error_query = f'''
        sum(rate(http_requests_total{{job="{service}",status=~"5.."}}[5m]))
        /
        sum(rate(http_requests_total{{job="{service}"}}[5m]))
        * 100
    '''
    error_rate = prom.query(error_query)
    
    # P99 latency
    latency_query = f'''
        histogram_quantile(0.99,
            sum(rate(http_request_duration_seconds_bucket{{job="{service}"}}[5m])) by (le)
        ) * 1000
    '''
    latency = prom.query(latency_query)
    
    return error_rate, latency

def main():
    print("\n" + "="*60)
    print("[DEMO] MLOps Canary Deployment - Decision Logic Demo")
    print("="*60 + "\n")
    
    prom = PrometheusClient("http://localhost:9090")
    
    # Test Prometheus connection
    print("[TEST] Testing Prometheus connection...")
    try:
        resp = requests.get("http://localhost:9090/api/v1/status/config", timeout=5)
        if resp.status_code == 200:
            print("[OK] Prometheus connected\n")
        else:
            print("[ERROR] Prometheus not accessible")
            return
    except:
        print("[ERROR] Cannot connect to Prometheus")
        return
    
    # Simulate baseline metrics
    print("[SIMULATE] Baseline Version (v1.0)")
    print("   Error Rate: 0.10%")
    print("   P99 Latency: 150ms")
    
    # Simulate canary metrics - SUCCESS scenario
    print("\n[SIMULATE] Canary Version (v2.0) - Success Scenario")
    print("   Error Rate: 0.08%")
    print("   P99 Latency: 135ms")
    
    baseline_errors = 0.10
    canary_errors = 0.08
    baseline_latency = 150
    canary_latency = 135
    
    error_ratio = canary_errors / baseline_errors
    latency_ratio = canary_latency / baseline_latency
    
    print("\n[DECISION] Performance Ratios:")
    print(f"   Error ratio: {error_ratio:.2f}x (threshold: 1.2x)")
    print(f"   Latency ratio: {latency_ratio:.2f}x (threshold: 1.5x)")
    
    if error_ratio > 1.2:
        print("\n[ROLLBACK] DECISION: ROLLBACK (error rate too high)")
    elif latency_ratio > 1.5:
        print("\n[ROLLBACK] DECISION: ROLLBACK (latency too high)")
    else:
        print("\n[PROCEED] DECISION: PROCEED (canary performing well)")
        print("\n[ROLLOUT] Gradual rollout: 20% -> 50% -> 75% -> 100%")
        print("[COMPLETE] New version deployed successfully!")
    
    # Try to query real metrics
    print("\n" + "="*60)
    print("[REAL] Querying Real Prometheus Metrics")
    print("="*60 + "\n")
    
    service = "recommendationservice"
    error_rate, latency = get_metrics(service, prom)
    
    print(f"[METRICS] {service}:")
    print(f"   Current Error Rate: {error_rate:.4f}%")
    print(f"   Current P99 Latency: {latency:.2f}ms")
    
    if error_rate == 0.0 and latency == 0.0:
        print("\n[INFO] No metrics found (service might not be exporting metrics)")
        print("[INFO] This is normal if ServiceMonitor is not configured")
    
    print("\n" + "="*60)
    print("[COMPLETE] Demo completed successfully!")
    print("="*60)
    
    # Generate report
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "service": service,
        "baseline": {
            "error_rate": f"{baseline_errors}%",
            "p99_latency": f"{baseline_latency}ms"
        },
        "canary": {
            "error_rate": f"{canary_errors}%",
            "p99_latency": f"{canary_latency}ms"
        },
        "decision": {
            "error_ratio": f"{error_ratio:.2f}x",
            "latency_ratio": f"{latency_ratio:.2f}x",
            "result": "PROCEED"
        }
    }
    
    import json
    with open("CANARY_DEPLOYMENT_REPORT.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n[REPORT] Report saved to: CANARY_DEPLOYMENT_REPORT.json")

if __name__ == "__main__":
    main()
