#!/usr/bin/env python3
"""
AI-Powered Operations Agent (AIOps) with Google Gemini
=======================================================

This agent automatically analyzes Prometheus alerts and Kubernetes logs,
then generates human-readable incident reports using Google Gemini AI.
Purpose: Intelligent alert triage and root cause analysis
Requires GOOGLE_API_KEY or GEMINI_API_KEY in .env file or environment variable
"""

import os
import json
import argparse
from datetime import datetime
from typing import Dict, List, Optional
import subprocess
import requests
from flask import Flask, request, jsonify
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Look for .env in project root (parent directory of scripts/)
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
    print(f"✅ Loaded .env from {env_path}")
except ImportError:
    print("⚠️  python-dotenv not installed. Run: pip install -r requirements.txt")

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("⚠️  Warning: google-generativeai not installed. Run: pip install -r requirements.txt")


class KubernetesAnalyzer:
    """Analyzes Kubernetes cluster state and logs"""
    
    def __init__(self, namespace: str = "citrus"):
        self.namespace = namespace
    
    def _kubectl(self, *args) -> str:
        """Execute kubectl command"""
        cmd = ['kubectl', '-n', self.namespace] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        return result.stdout.strip()
    
    def get_pod_logs(self, pod_selector: str, lines: int = 50) -> str:
        """Get recent logs from pods matching selector"""
        try:
            output = self._kubectl(
                'logs',
                '-l', pod_selector,
                '--tail', str(lines),
                '--prefix'  # Show pod name prefix
            )
            return output
        except Exception as e:
            return f"Failed to fetch logs: {e}"
    
    def get_pod_status(self, pod_selector: str) -> Dict:
        """Get pod status information"""
        output = self._kubectl(
            'get', 'pods',
            '-l', pod_selector,
            '-o', 'json'
        )
        
        try:
            data = json.loads(output)
            pods = []
            
            for pod in data.get('items', []):
                pod_info = {
                    'name': pod['metadata']['name'],
                    'status': pod['status']['phase'],
                    'restarts': sum(
                        c['restartCount']
                        for c in pod['status'].get('containerStatuses', [])
                    ),
                    'ready': all(
                        c['ready']
                        for c in pod['status'].get('containerStatuses', [])
                    )
                }
                pods.append(pod_info)
            
            return {'pods': pods}
        except Exception as e:
            return {'error': str(e)}
    
    def get_recent_events(self, minutes: int = 10) -> str:
        """Get recent Kubernetes events"""
        output = self._kubectl(
            'get', 'events',
            '--sort-by=.lastTimestamp',
            '-o', 'custom-columns=TIME:.lastTimestamp,TYPE:.type,REASON:.reason,MESSAGE:.message'
        )
        
        lines = output.split('\n')
        return '\n'.join(lines[-20:])  # Last 20 events


class AIOpsAgent:
    """
    Operations assistant that analyzes alerts and provides
    actionable insights using Google Gemini AI.
    """
    
    def __init__(self, namespace: str = "citrus"):
        self.k8s = KubernetesAnalyzer(namespace)
        self.model = None
        
        # Initialize Google Gemini if API key is available
        if GENAI_AVAILABLE:
            # Support both GOOGLE_API_KEY and GEMINI_API_KEY (for compatibility)
            api_key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
            if api_key:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('gemini-pro')
                print("✅ Google Gemini AI initialized")
            else:
                print("⚠️  GOOGLE_API_KEY or GEMINI_API_KEY not set, using rule-based analysis")
    
    def analyze_alert(self, alert_data: Dict) -> Dict:
        """
        Analyze Prometheus alert and generate intelligent response
        
        Args:
            alert_data: Prometheus Alertmanager webhook payload
            
        Returns:
            Dict with analysis results and recommendations
        """
        # Extract alert information
        alerts = alert_data.get('alerts', [])
        if not alerts:
            return {'error': 'No alerts in payload'}
        
        alert = alerts[0]  # Process first alert
        alert_name = alert.get('labels', {}).get('alertname', 'Unknown')
        service = alert.get('labels', {}).get('job', 'Unknown')
        severity = alert.get('labels', {}).get('severity', 'warning')
        
        print(f"\n{'='*60}")
        print(f"🚨 Alert Received: {alert_name}")
        print(f"   Service: {service}")
        print(f"   Severity: {severity}")
        print(f"{'='*60}\n")
        
        # Gather context
        context = self._gather_context(service)
        
        # Generate AI-powered analysis (fallback to rules if unavailable)
        if self.model:
            analysis = self._ai_analyze(alert, context)
        else:
            analysis = self._fallback_analyze(alert, context)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'alert': alert_name,
            'service': service,
            'severity': severity,
            'analysis': analysis,
            'context': context
        }
    
    def _gather_context(self, service: str) -> Dict:
        """Gather operational context about the affected service"""
        print("📊 Gathering context...")
        
        # Get pod status
        pod_status = self.k8s.get_pod_status(f'app={service}')
        
        # Get recent logs  
        logs = self.k8s.get_pod_logs(f'app={service}', lines=30)
        
        # Get recent events
        events = self.k8s.get_recent_events()
        
        context = {
            'pod_status': pod_status,
            'recent_logs': logs[-2000:],  # Limit to 2000 chars
            'recent_events': events
        }
        
        print("✅ Context gathered\n")
        return context
    
    def _ai_analyze(self, alert: Dict, context: Dict) -> str:
        """Use Google Gemini to analyze alert and context"""
        print("🤖 Consulting Google Gemini AI for analysis...")
        
        prompt = self._build_analysis_prompt(alert, context)
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"⚠️  AI analysis failed: {e}")
            print("   Falling back to rule-based analysis\n")
            return self._fallback_analyze(alert, context)
    
    def _build_analysis_prompt(self, alert: Dict, context: Dict) -> str:
        """Build comprehensive prompt for AI analysis"""
        alert_name = alert.get('labels', {}).get('alertname', 'Unknown')
        service = alert.get('labels', {}).get('job', 'Unknown')
        severity = alert.get('labels', {}).get('severity', 'warning')
        description = alert.get('annotations', {}).get('description', '')
        
        prompt = f"""
You are an expert Site Reliability Engineer analyzing a production incident.

**ALERT DETAILS:**
- Alert: {alert_name}
- Service: {service}
- Severity: {severity}
- Description: {description}

**KUBERNETES CONTEXT:**
Pod Status:
{json.dumps(context.get('pod_status', {}), indent=2)}

Recent Logs:
{context.get('recent_logs', 'No logs available')[:1000]}

Recent Events:
{context.get('recent_events', 'No events')}

**YOUR TASK:**
Provide a concise incident analysis in the following format:

**Root Cause**: [One sentence explaining what's wrong]

**Impact**: [How this affects users]

**Immediate Action**:
```bash
[kubectl commands to mitigate the issue]
```

**Prevention**: [Long-term fix to prevent recurrence]

Be specific and actionable. Focus on Kubernetes-specific solutions.
"""
        return prompt
    
    def _fallback_analyze(self, alert: Dict, context: Dict) -> str:
        """Rule-based analysis when AI is unavailable"""
        alert_name = alert.get('labels', {}).get('alertname', '')
        service = alert.get('labels', {}).get('job', 'unknown')
        
        # Simple pattern matching
        if 'high' in alert_name.lower() and 'latency' in alert_name.lower():
            return f"""
**Root Cause**: {service} is responding slowly (P99 latency exceeded threshold).

**Impact**: Users experiencing slow page loads and timeouts.

**Immediate Action**:
```bash
# Check pod CPU/memory
kubectl top pods -n citrus -l app={service}

# Scale up if needed
kubectl scale deployment/{service} --replicas=3 -n citrus
```

**Prevention**: Implement autoscaling based on latency metrics.
"""
        
        elif 'error' in alert_name.lower() or '5xx' in alert_name.lower():
            return f"""
**Root Cause**: {service} is returning HTTP 5xx errors (server errors).

**Impact**: Users seeing error pages or failed requests.

**Immediate Action**:
```bash
# Check logs for stack traces
kubectl logs -n citrus -l app={service} --tail=100 | grep -i error

# Restart pods if needed
kubectl rollout restart deployment/{service} -n citrus
```

**Prevention**: Add retry logic and circuit breakers. Review error handling code.
"""
        
        else:
            return f"""
**Alert**: {alert_name}
**Service**: {service}

Check logs and pod status for more details:
```bash
kubectl get pods -n citrus -l app={service}
kubectl logs -n citrus -l app={service} --tail=50
```
"""


# Flask webhook server for receiving Prometheus alerts
app = Flask(__name__)
agent = None


@app.route('/webhook', methods=['POST'])
def alertmanager_webhook():
    """Receive alert from Prometheus Alertmanager"""
    alert_data = request.json
    
    # Analyze alert
    result = agent.analyze_alert(alert_data)
    
    # Print to console (in production, send to Slack/PagerDuty)
    print("\n" + "="*60)
    print("📝 INCIDENT REPORT")
    print("="*60)
    print(result['analysis'])
    print("="*60 + "\n")
    
    return jsonify(result), 200


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    ai_enabled = agent is not None and agent.model is not None
    return jsonify({'status': 'healthy', 'ai_enabled': ai_enabled}), 200


def main():
    parser = argparse.ArgumentParser(
        description="AI-Powered Operations Agent for Kubernetes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start webhook server (for Prometheus Alertmanager)
  $env:GEMINI_API_KEY="your-api-key-here"  # Windows PowerShell
  python aiops-agent.py --mode server --port 5000

  # Analyze single alert from JSON file
  python aiops-agent.py --mode analyze --alert-file alert.json

Configure Alertmanager to send webhooks:
  receivers:
    - name: 'aiops-agent'
      webhook_configs:
        - url: 'http://localhost:5000/webhook'
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['server', 'analyze'],
        default='server',
        help='Run mode: webhook server or single analysis'
    )
    parser.add_argument('--port', type=int, default=5000, help='Webhook server port')
    parser.add_argument('--alert-file', help='Path to alert JSON file (for analyze mode)')
    parser.add_argument('--namespace', default='citrus', help='Kubernetes namespace')
    
    args = parser.parse_args()
    
    # Initialize agent
    global agent
    agent = AIOpsAgent(namespace=args.namespace)
    
    if args.mode == 'server':
        print(f"\n🚀 AIOps Agent listening on port {args.port}")
        print(f"Webhook URL: http://localhost:{args.port}/webhook\n")
        app.run(host='0.0.0.0', port=args.port, debug=False)
    
    elif args.mode == 'analyze':
        if not args.alert_file:
            print("Error: --alert-file required in analyze mode")
            return
        
        with open(args.alert_file) as f:
            alert_data = json.load(f)
        
        result = agent.analyze_alert(alert_data)
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
