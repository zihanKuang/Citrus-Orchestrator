"""
Kubernetes Operations Tools

Wraps kubectl / Kubernetes API for MCP protocol.
Each method corresponds to one MCP tool that AI can invoke.

Deployment Modes:
- Local Development: Uses kubectl with ~/.kube/config
- In-Cluster: Uses Kubernetes Python client with ServiceAccount token
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests


def resolve_namespace(explicit: Optional[str] = None) -> str:
    """Prefer explicit arg, then NAMESPACE / KUBERNETES_NAMESPACE env, else citrus."""
    if explicit:
        return explicit
    return (
        os.getenv("NAMESPACE")
        or os.getenv("KUBERNETES_NAMESPACE")
        or "citrus"
    )


def default_prometheus_url() -> str:
    """
    Local: localhost (expects port-forward).
    In-cluster: kube-prometheus-stack service DNS unless PROMETHEUS_URL is set.
    """
    if os.getenv("PROMETHEUS_URL"):
        return os.getenv("PROMETHEUS_URL")
    if os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"):
        return "http://monitoring-kube-prometheus-prometheus:9090"
    return "http://localhost:9090"


def _parse_event_time(value: Any) -> Optional[datetime]:
    """Parse K8s event timestamp into aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if not text or text == "N/A":
            return None
        # kubectl JSON uses RFC3339; tolerate trailing Z
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


class KubernetesTools:
    """Provides Kubernetes cluster inspection capabilities via MCP protocol."""

    def __init__(self, namespace: str = None, use_kubectl: bool = None):
        """
        Args:
            namespace: Target namespace. If None, resolve from env.
            use_kubectl: True=kubectl CLI, False=K8s Python client,
                         None=auto-detect (SA token => in-cluster).
        """
        self.namespace = resolve_namespace(namespace)
        self.prometheus_url = default_prometheus_url()

        if use_kubectl is None:
            self.use_kubectl = not os.path.exists(
                "/var/run/secrets/kubernetes.io/serviceaccount/token"
            )
        else:
            self.use_kubectl = use_kubectl

        if not self.use_kubectl:
            self._init_k8s_client()

    def _init_k8s_client(self):
        """Initialize Kubernetes Python client for in-cluster usage."""
        try:
            from kubernetes import client, config

            config.load_incluster_config()
            self.v1 = client.CoreV1Api()
            print("[OK] Kubernetes client initialized (in-cluster mode)")
            print(f"    Namespace: {self.namespace}")
            print(f"    Prometheus: {self.prometheus_url}")
        except Exception as e:
            print(f"[ERROR] Failed to initialize K8s client: {e}")
            print("        Falling back to kubectl CLI mode")
            self.use_kubectl = True

    def _kubectl(self, *args) -> str:
        cmd = ["kubectl", "-n", self.namespace] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        return result.stdout.strip() if result.stdout else ""

    def _parse_label_selector(self, pod_selector: str) -> str:
        label_dict = dict(
            item.split("=", 1) for item in pod_selector.split(",") if "=" in item
        )
        return ",".join(f"{k}={v}" for k, v in label_dict.items())

    async def list_pods(self) -> str:
        """List all pods in the namespace with phase, readiness, restarts, labels."""
        try:
            if self.use_kubectl:
                output = self._kubectl("get", "pods", "-o", "json")
                data = json.loads(output)
            else:
                pods = self.v1.list_namespaced_pod(namespace=self.namespace)
                data = {"items": [pod.to_dict() for pod in pods.items]}

            items = data.get("items", [])
            if not items:
                return f"No pods found in namespace '{self.namespace}'"

            lines = [
                f"Pods in namespace '{self.namespace}' ({len(items)} total):",
                "",
            ]
            for pod in items:
                name = pod["metadata"]["name"]
                phase = pod.get("status", {}).get("phase", "Unknown")
                labels = pod.get("metadata", {}).get("labels") or {}
                component = (
                    labels.get("app.kubernetes.io/component")
                    or labels.get("app")
                    or labels.get("app.kubernetes.io/name")
                    or "n/a"
                )
                container_statuses = pod.get("status", {}).get("container_statuses") or []
                restarts = sum(c.get("restart_count", 0) or 0 for c in container_statuses)
                ready = (
                    all(c.get("ready", False) for c in container_statuses)
                    if container_statuses
                    else False
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
        """Read-only closed-loop check: matching pods Running + Ready."""
        try:
            if self.use_kubectl:
                output = self._kubectl("get", "pods", "-l", pod_selector, "-o", "json")
                data = json.loads(output)
            else:
                label_selector_str = self._parse_label_selector(pod_selector)
                pods = self.v1.list_namespaced_pod(
                    namespace=self.namespace,
                    label_selector=label_selector_str,
                )
                data = {"items": [pod.to_dict() for pod in pods.items]}

            items = data.get("items", [])
            if not items:
                return (
                    f"FAIL: No pods found matching '{pod_selector}' in "
                    f"namespace '{self.namespace}'. Service may still be down."
                )

            ready_count = 0
            details = []
            for pod in items:
                name = pod["metadata"]["name"]
                phase = pod.get("status", {}).get("phase", "Unknown")
                container_statuses = pod.get("status", {}).get("container_statuses") or []
                restarts = sum(c.get("restart_count", 0) or 0 for c in container_statuses)
                is_ready = (
                    phase == "Running"
                    and bool(container_statuses)
                    and all(c.get("ready", False) for c in container_statuses)
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
        """Get recent logs from pods matching a label selector."""
        try:
            if self.use_kubectl:
                output = self._kubectl(
                    "logs",
                    "-l",
                    pod_selector,
                    "--tail",
                    str(lines),
                    "--prefix",
                )
                if not output:
                    return f"No logs found for pods matching '{pod_selector}'"
                return output

            label_selector_str = self._parse_label_selector(pod_selector)
            pods = self.v1.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=label_selector_str,
            )

            if not pods.items:
                return f"No pods found matching '{pod_selector}'"

            log_output = []
            for pod in pods.items:
                pod_name = pod.metadata.name
                try:
                    logs = self.v1.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=self.namespace,
                        tail_lines=lines,
                    )
                    prefixed_logs = "\n".join(
                        f"[{pod_name}] {line}" for line in logs.split("\n")
                    )
                    log_output.append(prefixed_logs)
                except Exception as e:
                    log_output.append(f"[{pod_name}] Error: {str(e)}")

            return "\n".join(log_output)

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            return f"Error fetching logs: {error_msg}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"

    async def get_pod_status(self, pod_selector: str) -> str:
        """Get status for pods matching a label selector."""
        try:
            if self.use_kubectl:
                output = self._kubectl("get", "pods", "-l", pod_selector, "-o", "json")
                data = json.loads(output)
            else:
                label_selector_str = self._parse_label_selector(pod_selector)
                pods = self.v1.list_namespaced_pod(
                    namespace=self.namespace,
                    label_selector=label_selector_str,
                )
                data = {"items": [pod.to_dict() for pod in pods.items]}

            pod_info_list = []
            for pod in data.get("items", []):
                name = pod["metadata"]["name"]
                phase = pod["status"]["phase"]
                statuses = pod["status"].get("container_statuses") or []
                restarts = sum(c.get("restart_count", 0) or 0 for c in statuses)
                ready = all(c.get("ready", False) for c in statuses) if statuses else False

                info = (
                    f"Pod: {name}\n"
                    f"  Status: {phase}\n"
                    f"  Restarts: {restarts}\n"
                    f"  Ready: {ready}\n"
                )
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
        Get Kubernetes events from the namespace within the last `minutes`.
        """
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(1, minutes))
            rows: List[tuple] = []

            if self.use_kubectl:
                output = self._kubectl("get", "events", "-o", "json")
                data = json.loads(output) if output else {"items": []}
                for event in data.get("items", []):
                    ts = (
                        _parse_event_time(event.get("lastTimestamp"))
                        or _parse_event_time(event.get("eventTime"))
                        or _parse_event_time(
                            (event.get("metadata") or {}).get("creationTimestamp")
                        )
                    )
                    if ts is None or ts < cutoff:
                        continue
                    rows.append(
                        (
                            ts,
                            event.get("type") or "N/A",
                            event.get("reason") or "N/A",
                            event.get("message") or "N/A",
                        )
                    )
            else:
                events = self.v1.list_namespaced_event(namespace=self.namespace)
                for event in events.items:
                    ts = (
                        _parse_event_time(event.last_timestamp)
                        or _parse_event_time(event.event_time)
                        or _parse_event_time(
                            event.metadata.creation_timestamp
                            if event.metadata
                            else None
                        )
                    )
                    if ts is None or ts < cutoff:
                        continue
                    rows.append(
                        (
                            ts,
                            event.type or "N/A",
                            event.reason or "N/A",
                            event.message or "N/A",
                        )
                    )

            if not rows:
                return (
                    f"No events in namespace '{self.namespace}' "
                    f"within the last {minutes} minute(s)"
                )

            rows.sort(key=lambda r: r[0])
            # Cap output to keep context small; newest last
            rows = rows[-40:]
            lines = [f"Events in last {minutes}m (namespace={self.namespace}):", "TIME\tTYPE\tREASON\tMESSAGE"]
            for ts, evt_type, reason, message in rows:
                lines.append(f"{ts.isoformat()}\t{evt_type}\t{reason}\t{message}")
            return "\n".join(lines)

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            return f"Error fetching events: {error_msg}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"

    async def query_prometheus(
        self,
        promql: str,
        prometheus_url: str = None,
    ) -> str:
        """Execute a PromQL query against Prometheus."""
        url_base = prometheus_url or self.prometheus_url
        try:
            url = f"{url_base.rstrip('/')}/api/v1/query"
            response = requests.get(url, params={"query": promql}, timeout=10)
            response.raise_for_status()

            data = response.json()
            if data.get("status") != "success":
                return f"Prometheus query failed: {data.get('error', 'Unknown error')}"

            results = data["data"]["result"]
            if not results:
                return f"No data returned for query: {promql}"

            output_lines = []
            for result in results:
                metric = result["metric"]
                value = result["value"][1]
                metric_str = ",".join(f'{k}="{v}"' for k, v in metric.items())
                output_lines.append(f"Metric: {metric_str}\nValue: {value}\n")

            return "\n".join(output_lines)

        except requests.RequestException as e:
            return (
                f"Prometheus query failed (url={url_base}): {str(e)}. "
                "Local tip: kubectl port-forward -n citrus "
                "svc/monitoring-kube-prometheus-prometheus 9090:9090"
            )
        except Exception as e:
            return f"Unexpected error: {str(e)}"
