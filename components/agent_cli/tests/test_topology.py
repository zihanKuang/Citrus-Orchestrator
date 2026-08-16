"""Jaeger adjacency — in-memory only, no Neo4j."""
from agent_cli.topology import adjacency, cluster_services, related_edges


def test_adjacency_is_undirected():
    graph = adjacency([
        {"parent": "frontend", "child": "checkout", "callCount": 9},
        {"parent": "checkout", "child": "payment", "callCount": 3},
    ])
    assert "checkout" in graph["frontend"]
    assert "frontend" in graph["checkout"]
    assert "payment" in graph["checkout"]


def test_self_edges_and_blanks_dropped():
    graph = adjacency([
        {"parent": "frontend", "child": "frontend"},
        {"parent": "", "child": "checkout"},
        {"parent": "frontend", "child": "cart"},
    ])
    assert graph == {"frontend": {"cart"}, "cart": {"frontend"}}


def test_related_edges_only_among_alerted_services():
    graph = adjacency([
        {"parent": "frontend", "child": "checkout"},
        {"parent": "frontend", "child": "cart"},
    ])
    edges = related_edges(["frontend", "checkout"], graph)
    assert edges == [("checkout", "frontend")]


def test_cluster_merges_neighbors_and_keeps_isolates():
    graph = adjacency([
        {"parent": "frontend", "child": "checkout"},
    ])
    groups = cluster_services(["frontend", "checkout", "ads"], graph)
    grouped = {frozenset(g) for g in groups}
    assert frozenset({"frontend", "checkout"}) in grouped
    assert frozenset({"ads"}) in grouped
