"""
Kubernetes Operations Tools

Wraps kubectl operations for MCP protocol.
Each method corresponds to one MCP tool that AI can invoke.

Deployment Modes:
- Local Development: Uses kubectl with ~/.kube/config
- In-Cluster: Uses Kubernetes Python client with ServiceAccount token
"""

import subprocess
import json
import requests
import os
from typing import Dict, Any


class KubernetesTools:
    """Provides Kubernetes cluster inspection capabilities via MCP protocol."""
    
    def __init__(self, namespace: str = "citrus", use_kubectl: bool = None):
        """
        Initialize Kubernetes tools.
        
        Args:
            namespace: Default Kubernetes namespace to query
            use_kubectl: If True, use kubectl CLI. If False, use K8s Python client.
                        If None (default), auto-detect based on environment.
        
        Auto-detection logic:
        - If in Kubernetes cluster: use Python client (checks for SA token)
        - If local development: use kubectl CLI
        """
        self.namespace = namespace
        
        # Auto-detect deployment mode if not specified
        if use_kubectl is None:
            # Check if running inside Kubernetes cluster
            # Kubernetes automatically mounts SA token at this path
            self.use_kubectl = not os.path.exists(
                '/var/run/secrets/kubernetes.io/serviceaccount/token'
            )
        else:
            self.use_kubectl = use_kubectl
        
        # Initialize Kubernetes Python client if in-cluster
        if not self.use_kubectl:
            self._init_k8s_client()
    
    def _init_k8s_client(self):
        """
        Initialize Kubernetes Python client for in-cluster usage.
        
        This method configures the K8s client to use the ServiceAccount token
        that Kubernetes automatically mounts into the Pod at:
        /var/run/secrets/kubernetes.io/serviceaccount/
        
        Security Benefits:
        - Uses ServiceAccount with RBAC restrictions (not admin access)
        - Token auto-rotates (no static credentials)
        - No need to mount sensitive kubeconfig files
        """
        try:
            from kubernetes import client, config
            
            # Load in-cluster configuration
            # This reads:
            # - Token: /var/run/secrets/.../token
            # - CA cert: /var/run/secrets/.../ca.crt
            # - Namespace: /var/run/secrets/.../namespace
            config.load_incluster_config()
            
            # Create API client for core resources (pods, events, etc.)
            self.v1 = client.CoreV1Api()
            
            print(f"[OK] Kubernetes client initialized (in-cluster mode)")
            print(f"    Using ServiceAccount token from /var/run/secrets/...")
            print(f"    Permissions controlled by RBAC")
            
        except Exception as e:
            print(f"[ERROR] Failed to initialize K8s client: {e}")
            print(f"        Falling back to kubectl CLI mode")
            self.use_kubectl = True
    
    def _kubectl(self, *args) -> str:
        """
        Execute kubectl command and return output.
        
        Args:
            *args: kubectl arguments
            
        Returns:
            Command output as string
            
        Raises:
            subprocess.CalledProcessError: If kubectl command fails
        """
        cmd = ['kubectl', '-n', self.namespace] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=True
        )
        return result.stdout.strip() if result.stdout else ""
    
    async def list_pods(self) -> str:
        """
        List all pods in the namespace with phase, readiness, restarts, and key labels.

        Returns:
            Human-readable pod inventory (useful as the first step in incident triage)
        """
        try:
            if self.use_kubectl:
                output = self._kubectl('get', 'pods', '-o', 'json')
                data = json.loads(output)
            else:
                pods = self.v1.list_namespaced_pod(namespace=self.namespace)
                data = {'items': [pod.to_dict() for pod in pods.items]}

            items = data.get('items', [])
            if not items:
                return f"No pods found in namespace '{self.namespace}'"

            lines = [
                f"Pods in namespace '{self.namespace}' ({len(items)} total):",
                "",
            ]
            for pod in items:
                name = pod['metadata']['name']
                phase = pod.get('status', {}).get('phase', 'Unknown')
                labels = pod.get('metadata', {}).get('labels') or {}
                component = (
                    labels.get('app.kubernetes.io/component')
                    or labels.get('app')
                    or labels.get('app.kubernetes.io/name')
                    or 'n/a'
                )
                container_statuses = pod.get('status', {}).get('container_statuses') or []
                restarts = sum(c.get('restart_count', 0) or 0 for c in container_statuses)
                ready = (
                    all(c.get('ready', False) for c in container_statuses)
                    if container_statuses else False
                )
                lines.append(
                    f"- {name} | phase={phase} | ready={ready} | "
                    f"restarts={restarts} | component={component}"
                )

            return "\n".join(lines)

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            return f"Error listing pods: {error_msg}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"

    async def validate_recovery(
        self,
        pod_selector: str,
        min_ready: int = 1,
    ) -> str:
        """
        Validate that pods matching a selector have recovered after disruption.

        Checks phase=Running, all containers Ready, and reports restart counts.
        Does NOT mutate the cluster (read-only closed-loop verification).

        Args:
            pod_selector: Kubernetes label selector
            min_ready: Minimum number of Ready pods required to PASS

        Returns:
            PASS/FAIL report with per-pod details
        """
        try:
            if self.use_kubectl:
                output = self._kubectl('get', 'pods', '-l', pod_selector, '-o', 'json')
                data = json.loads(output)
            else:
                label_dict = dict(
                    item.split('=', 1) for item in pod_selector.split(',') if '=' in item
                )
                label_selector_str = ','.join(f"{k}={v}" for k, v in label_dict.items())
                pods = self.v1.list_namespaced_pod(
                    namespace=self.namespace,
                    label_selector=label_selector_str,
                )
                data = {'items': [pod.to_dict() for pod in pods.items]}

            items = data.get('items', [])
            if not items:
                return (
                    f"FAIL: No pods found matching '{pod_selector}' in "
                    f"namespace '{self.namespace}'. Service may still be down."
                )

            ready_count = 0
            details = []
            for pod in items:
                name = pod['metadata']['name']
                phase = pod.get('status', {}).get('phase', 'Unknown')
                container_statuses = pod.get('status', {}).get('container_statuses') or []
                restarts = sum(c.get('restart_count', 0) or 0 for c in container_statuses)
                is_ready = (
                    phase == 'Running'
                    and bool(container_statuses)
                    and all(c.get('ready', False) for c in container_statuses)
                )
                if is_ready:
                    ready_count += 1

                details.append(
                    f"- {name}: phase={phase}, ready={is_ready}, restarts={restarts}"
                )

            passed = ready_count >= min_ready
            verdict = "PASS" if passed else "FAIL"
            summary = (
                f"{verdict}: {ready_count}/{len(items)} Ready pods "
                f"(required min_ready={min_ready}) for selector '{pod_selector}'"
            )
            note = (
                "\nNote: Elevated restart counts after a chaos kill are expected; "
                "PASS means ReplicaSet self-heal restored Ready capacity."
            )
            return summary + "\n" + "\n".join(details) + note

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            return f"FAIL: Error validating recovery: {error_msg}"
        except Exception as e:
            return f"FAIL: Unexpected error: {str(e)}"

    async def get_pod_logs(self, pod_selector: str, lines: int = 50) -> str:
        """
        Get recent logs from pods matching a label selector.
        
        Args:
            pod_selector: Kubernetes label selector (e.g., "app=frontend")
            lines: Number of recent log lines to retrieve
            
        Returns:
            Log output as string with pod name prefixes
        """
        try:
            # Use kubectl CLI (local development)
            if self.use_kubectl:
                output = self._kubectl(
                    'logs',
                    '-l', pod_selector,
                    '--tail', str(lines),
                    '--prefix'
                )
                
                if not output:
                    return f"No logs found for pods matching '{pod_selector}'"
                
                return output
            
            # Use Kubernetes Python client (in-cluster)
            else:
                # Parse label selector (e.g., "app=frontend" -> {"app": "frontend"})
                label_dict = dict(
                    item.split('=', 1) for item in pod_selector.split(',') if '=' in item
                )
                label_selector_str = ','.join(f"{k}={v}" for k, v in label_dict.items())
                
                # List pods matching selector
                pods = self.v1.list_namespaced_pod(
                    namespace=self.namespace,
                    label_selector=label_selector_str
                )
                
                if not pods.items:
                    return f"No pods found matching '{pod_selector}'"
                
                # Fetch logs from each pod
                log_output = []
                for pod in pods.items:
                    pod_name = pod.metadata.name
                    try:
                        # Read pod logs (tail_lines parameter)
                        logs = self.v1.read_namespaced_pod_log(
                            name=pod_name,
                            namespace=self.namespace,
                            tail_lines=lines
                        )
                        
                        # Format with pod name prefix (like kubectl --prefix)
                        prefixed_logs = '\n'.join(
                            f"[{pod_name}] {line}" for line in logs.split('\n')
                        )
                        log_output.append(prefixed_logs)
                        
                    except Exception as e:
                        log_output.append(f"[{pod_name}] Error: {str(e)}")
                
                return '\n'.join(log_output)
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            return f"Error fetching logs: {error_msg}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
    
    async def get_pod_status(self, pod_selector: str) -> str:
        """
        Get status information for pods matching a label selector.
        
        Args:
            pod_selector: Kubernetes label selector
            
        Returns:
            Human-readable pod status summary
        """
        try:
            # Use kubectl CLI (local development)
            if self.use_kubectl:
                output = self._kubectl('get', 'pods', '-l', pod_selector, '-o', 'json')
                data = json.loads(output)
            
            # Use Kubernetes Python client (in-cluster)
            else:
                label_dict = dict(
                    item.split('=', 1) for item in pod_selector.split(',') if '=' in item
                )
                label_selector_str = ','.join(f"{k}={v}" for k, v in label_dict.items())
                
                pods = self.v1.list_namespaced_pod(
                    namespace=self.namespace,
                    label_selector=label_selector_str
                )
                
                # Convert K8s object to dict-like structure for consistent processing
                data = {'items': [pod.to_dict() for pod in pods.items]}
            
            # Common processing for both modes
            pod_info_list = []
            for pod in data.get('items', []):
                name = pod['metadata']['name']
                phase = pod['status']['phase']
                
                restarts = sum(
                    c['restart_count']
                    for c in pod['status'].get('container_statuses', [])
                )
                
                ready = all(
                    c['ready']
                    for c in pod['status'].get('container_statuses', [])
                )
                
                info = f"Pod: {name}\n"
                info += f"  Status: {phase}\n"
                info += f"  Restarts: {restarts}\n"
                info += f"  Ready: {ready}\n"
                pod_info_list.append(info)
            
            if not pod_info_list:
                return f"No pods found matching '{pod_selector}'"
            
            return "\n".join(pod_info_list)
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            return f"Error fetching pod status: {error_msg}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
    
    async def get_recent_events(self, minutes: int = 10) -> str:
        """
        Get recent Kubernetes events from the namespace.
        
        Args:
            minutes: Time window to look back (for future filtering)
            
        Returns:
            Formatted event list
        """
        try:
            # Use kubectl CLI (local development)
            if self.use_kubectl:
                output = self._kubectl(
                    'get',
                    'events',
                    '--sort-by=.lastTimestamp',
                    '-o', 'custom-columns=TIME:.lastTimestamp,TYPE:.type,REASON:.reason,MESSAGE:.message'
                )
                
                if not output:
                    return "No recent events found"
                
                lines = output.split('\n')[-20:]
                return '\n'.join(lines)
            
            # Use Kubernetes Python client (in-cluster)
            else:
                events = self.v1.list_namespaced_event(
                    namespace=self.namespace
                )
                
                if not events.items:
                    return "No recent events found"
                
                # Sort by timestamp (most recent last)
                sorted_events = sorted(
                    events.items,
                    key=lambda e: e.last_timestamp or e.event_time or '',
                )
                
                # Format output (last 20 events)
                event_lines = ["TIME\tTYPE\tREASON\tMESSAGE"]
                for event in sorted_events[-20:]:
                    time = event.last_timestamp or event.event_time or "N/A"
                    evt_type = event.type or "N/A"
                    reason = event.reason or "N/A"
                    message = event.message or "N/A"
                    
                    event_lines.append(f"{time}\t{evt_type}\t{reason}\t{message}")
                
                return '\n'.join(event_lines)
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            return f"Error fetching events: {error_msg}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
    
    async def query_prometheus(self, promql: str, prometheus_url: str = "http://localhost:9090") -> str:
        """
        Execute a PromQL query against Prometheus.
        
        Args:
            promql: Prometheus Query Language expression
            prometheus_url: Prometheus server URL
            
        Returns:
            Query results formatted as string
        """
        try:
            url = f"{prometheus_url}/api/v1/query"
            params = {'query': promql}
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') != 'success':
                return f"Prometheus query failed: {data.get('error', 'Unknown error')}"
            
            results = data['data']['result']
            
            if not results:
                return f"No data returned for query: {promql}"
            
            output_lines = []
            for result in results:
                metric = result['metric']
                value = result['value'][1]
                
                metric_str = ','.join(f'{k}="{v}"' for k, v in metric.items())
                line = f"Metric: {metric_str}\nValue: {value}\n"
                output_lines.append(line)
            
            return "\n".join(output_lines)
            
        except requests.RequestException as e:
            return f"Prometheus query failed: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
