"""
Kubernetes Operations Tools

Wraps kubectl operations for MCP protocol.
Each method corresponds to one MCP tool that AI can invoke.
"""

import subprocess
import json
import requests
from typing import Dict, Any


class KubernetesTools:
    """Provides Kubernetes cluster inspection capabilities via MCP protocol."""
    
    def __init__(self, namespace: str = "citrus"):
        """
        Initialize Kubernetes tools.
        
        Args:
            namespace: Default Kubernetes namespace to query
        """
        self.namespace = namespace
    
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
            check=True
        )
        return result.stdout.strip()
    
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
            output = self._kubectl(
                'logs',
                '-l', pod_selector,
                '--tail', str(lines),
                '--prefix'
            )
            
            if not output:
                return f"No logs found for pods matching '{pod_selector}'"
            
            return output
            
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
            output = self._kubectl('get', 'pods', '-l', pod_selector, '-o', 'json')
            data = json.loads(output)
            
            pod_info_list = []
            for pod in data.get('items', []):
                name = pod['metadata']['name']
                phase = pod['status']['phase']
                
                restarts = sum(
                    c['restartCount']
                    for c in pod['status'].get('containerStatuses', [])
                )
                
                ready = all(
                    c['ready']
                    for c in pod['status'].get('containerStatuses', [])
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
