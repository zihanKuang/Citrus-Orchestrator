"""In-memory service adjacency from Jaeger. Used only to group multi-alert webhooks.

Not a knowledge graph. No Neo4j. If Jaeger is down the table is empty and
aggregation falls back to listing the alert labels as-is.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Dict, Iterable, List, Set, Tuple

DEFAULT_JAEGER_URL = "http://localhost:16686"
DEFAULT_LOOKBACK_MS = 3_600_000  # 1 hour


def default_jaeger_url() -> str:
    import os

    return os.getenv("JAEGER_URL") or DEFAULT_JAEGER_URL


def fetch_dependencies(
    jaeger_url: str = "",
    *,
    lookback_ms: int = DEFAULT_LOOKBACK_MS,
    timeout: float = 5.0,
) -> List[Dict[str, object]]:
    """GET /api/dependencies. Returns [] on any failure (degrade)."""
    base = (jaeger_url or default_jaeger_url()).rstrip("/")
    end_ts = int(time.time() * 1000)
    url = f"{base}/api/dependencies?endTs={end_ts}&lookback={lookback_ms}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return []

    if isinstance(payload, dict):
        data = payload.get("data") or payload.get("dependencies") or []
    elif isinstance(payload, list):
        data = payload
    else:
        data = []
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def adjacency(dependencies: Iterable[Dict[str, object]]) -> Dict[str, Set[str]]:
    """Undirected neighbor map: parent↔child. Call counts are ignored."""
    graph: Dict[str, Set[str]] = {}
    for row in dependencies:
        parent = str(row.get("parent") or "").strip()
        child = str(row.get("child") or "").strip()
        if not parent or not child or parent == child:
            continue
        graph.setdefault(parent, set()).add(child)
        graph.setdefault(child, set()).add(parent)
    return graph


def related_edges(
    services: Iterable[str],
    graph: Dict[str, Set[str]],
) -> List[Tuple[str, str]]:
    """Edges among the alerted services (and one-hop neighbors that are also alerted)."""
    names = {s for s in services if s}
    edges: List[Tuple[str, str]] = []
    seen: Set[Tuple[str, str]] = set()
    for name in sorted(names):
        for neighbor in sorted(graph.get(name, set())):
            if neighbor not in names:
                continue
            pair = (name, neighbor) if name < neighbor else (neighbor, name)
            if pair in seen:
                continue
            seen.add(pair)
            edges.append(pair)
    return edges


def cluster_services(
    services: Iterable[str],
    graph: Dict[str, Set[str]],
) -> List[List[str]]:
    """Union-find: alerted services that share an edge become one group."""
    names = sorted({s for s in services if s})
    parent = {s: s for s in names}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for a, b in related_edges(names, graph):
        union(a, b)

    groups: Dict[str, List[str]] = {}
    for s in names:
        groups.setdefault(find(s), []).append(s)
    return list(groups.values())


class ServiceGraph:
    """Cached adjacency list. Refresh is best-effort."""

    def __init__(self, jaeger_url: str = "", ttl_s: float = 60.0):
        self.jaeger_url = jaeger_url or default_jaeger_url()
        self.ttl_s = ttl_s
        self._graph: Dict[str, Set[str]] = {}
        self._fetched_at: float = 0.0

    def refresh(self, force: bool = False) -> Dict[str, Set[str]]:
        now = time.time()
        if not force and self._fetched_at > 0 and (now - self._fetched_at) < self.ttl_s:
            return self._graph
        deps = fetch_dependencies(self.jaeger_url)
        self._graph = adjacency(deps)
        self._fetched_at = now
        return self._graph

    def neighbors(self, service: str) -> Set[str]:
        self.refresh()
        return set(self._graph.get(service, set()))

    def edges_among(self, services: Iterable[str]) -> List[Tuple[str, str]]:
        self.refresh()
        return related_edges(services, self._graph)
