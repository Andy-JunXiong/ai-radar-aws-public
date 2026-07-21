from __future__ import annotations

import hashlib
from typing import Any


SCHEMA_VERSION = 1
RELATIONSHIP_SCOPE = "reflection_explicit_links"
EDGE_TYPE_RELATED_REFLECTION = "related_reflection"
EDGE_PROVENANCE = "frontmatter.related"
EVIDENCE_ROLE = "cognitive_context_not_evidence"


def build_reflection_relationship_index(reflections: list[Any]) -> dict[str, Any]:
    nodes = [_reflection_node(item) for item in reflections]
    known_ids = {node["id"] for node in nodes}
    edges: list[dict[str, Any]] = []

    for item in reflections:
        source_id = _field(item, "id")
        if not source_id:
            continue
        for target_id in _string_list(_field(item, "related")):
            edges.append(_relationship_edge(source_id=source_id, target_id=target_id, known_ids=known_ids))

    return {
        "schema_version": SCHEMA_VERSION,
        "scope": RELATIONSHIP_SCOPE,
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "unresolved_edge_count": sum(1 for edge in edges if not edge["target_exists"]),
        },
    }


def get_reflection_relationships(index: dict[str, Any], reflection_id: str) -> dict[str, Any]:
    target = str(reflection_id or "").strip()
    nodes = index.get("nodes") if isinstance(index, dict) else []
    edges = index.get("edges") if isinstance(index, dict) else []
    node = next((item for item in nodes if isinstance(item, dict) and item.get("id") == target), None)
    outbound = [
        edge
        for edge in edges
        if isinstance(edge, dict) and edge.get("source_id") == target
    ]
    inbound = [
        edge
        for edge in edges
        if isinstance(edge, dict) and edge.get("target_id") == target
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": RELATIONSHIP_SCOPE,
        "reflection_id": target,
        "node": node,
        "outbound_edges": outbound,
        "inbound_edges": inbound,
        "summary": {
            "outbound_count": len(outbound),
            "inbound_count": len(inbound),
            "unresolved_outbound_count": sum(1 for edge in outbound if not edge.get("target_exists")),
        },
    }


def _relationship_edge(*, source_id: str, target_id: str, known_ids: set[str]) -> dict[str, Any]:
    return {
        "id": _edge_id(source_id, target_id),
        "source_id": source_id,
        "target_id": target_id,
        "type": EDGE_TYPE_RELATED_REFLECTION,
        "layer": "reflection",
        "target_exists": target_id in known_ids,
        "metadata": {
            "provenance": EDGE_PROVENANCE,
            "semantic_role": "explicit_cognitive_context_link",
            "evidence_role": EVIDENCE_ROLE,
            "auto_extracted": False,
        },
    }


def _reflection_node(item: Any) -> dict[str, Any]:
    return {
        "id": _field(item, "id"),
        "layer": "reflection",
        "title": _field(item, "title"),
        "tags": _string_list(_field(item, "tags")),
        "source": _source_value(_field(item, "source")),
        "immutable_source": True,
    }


def _edge_id(source_id: str, target_id: str) -> str:
    seed = f"{EDGE_TYPE_RELATED_REFLECTION}:{source_id}:{target_id}"
    return f"ref_edge_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def _field(item: Any, field_name: str) -> Any:
    if isinstance(item, dict):
        return item.get(field_name)
    return getattr(item, field_name, None)


def _source_value(value: Any) -> str:
    source = getattr(value, "value", value)
    return str(source or "").strip()


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        values = value
    else:
        values = [value]

    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        result.append(text)
        seen.add(text)
    return result
