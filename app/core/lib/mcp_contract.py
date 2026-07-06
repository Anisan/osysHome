"""Shared helpers for plugin MCP contract (descriptors, revision, validation)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def revision_from_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    text = str(value).strip()
    return text or None


def revision_from_dict(data: dict, keys: Optional[List[str]] = None) -> str:
    if keys:
        payload = {key: data.get(key) for key in keys}
    else:
        payload = dict(data)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def build_plugin_mcp_descriptors(plugin_name: str, capabilities: dict) -> Tuple[list, list, list]:
    """Build declarative MCP surface from mcp_capabilities()."""
    caps = capabilities or {}
    collections = [item for item in (caps.get("collections") or []) if isinstance(item, dict)]
    operations = [str(item).strip() for item in (caps.get("operations") or []) if str(item).strip()]
    operation_schemas = caps.get("operation_schemas") or {}

    tools: List[dict] = [
        {
            "id": "surface",
            "plugin": plugin_name,
            "kind": "plugin_surface",
            "entities": bool(caps.get("entities")),
            "config_schema": bool(caps.get("config_schema")),
        }
    ]
    for collection in collections:
        collection_id = str(collection.get("id") or "").strip()
        if not collection_id:
            continue
        tools.append(
            {
                "id": f"collection:{collection_id}",
                "plugin": plugin_name,
                "kind": "entity_collection",
                "collection": collection_id,
                "title": collection.get("title") or collection_id,
                "writable": bool(collection.get("writable", True)),
                "has_code": bool(collection.get("has_code")),
                "binding_mode": str(collection.get("binding_mode") or "none"),
            }
        )
    for operation in operations:
        tools.append(
            {
                "id": f"operation:{operation}",
                "plugin": plugin_name,
                "kind": "plugin_operation",
                "operation": operation,
                "schema": operation_schemas.get(operation),
            }
        )

    resources: List[dict] = [
        {"uri": f"osys://plugin/{plugin_name}", "kind": "capabilities", "plugin": plugin_name},
        {"uri": f"osys://plugin/{plugin_name}/config", "kind": "config_schema", "plugin": plugin_name},
    ]
    for collection in collections:
        collection_id = str(collection.get("id") or "").strip()
        if not collection_id:
            continue
        resources.append(
            {
                "uri": f"osys://plugin/{plugin_name}/schema/{collection_id}",
                "kind": "entity_schema",
                "plugin": plugin_name,
                "collection": collection_id,
            }
        )

    prompts: List[dict] = []
    if any(str(item.get("binding_mode") or "") == "property" for item in collections):
        prompts.append(
            {
                "name": f"osys_{plugin_name.lower()}_binding",
                "plugin": plugin_name,
                "description": f"Guided property binding workflow for {plugin_name}",
            }
        )
    if collections:
        prompts.append(
            {
                "name": f"osys_{plugin_name.lower()}_entity_authoring",
                "plugin": plugin_name,
                "description": f"Author {plugin_name} entities by collection schema",
            }
        )

    return tools, resources, prompts


def _type_matches(value: Any, expected: Any) -> bool:
    if expected is None:
        return True
    if isinstance(expected, list):
        if value is None and "null" in expected:
            return True
        options = [item for item in expected if item != "null"]
        return any(_type_matches(value, item) for item in options)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    return True


def validate_entity_payload(payload: dict, schema: dict) -> dict:
    """Lightweight JSON Schema validation for MCP entity payloads."""
    errors: List[dict] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": [{"field": "_", "message": "payload must be an object"}]}
    if not isinstance(schema, dict):
        return {"ok": True, "errors": []}

    properties = schema.get("properties") or {}
    for field in schema.get("required") or []:
        if field not in payload or payload.get(field) in (None, ""):
            errors.append({"field": field, "message": "required"})

    for field, spec in properties.items():
        if field not in payload:
            continue
        value = payload[field]
        if value is None:
            continue
        if not isinstance(spec, dict):
            continue
        expected_type = spec.get("type")
        if expected_type and not _type_matches(value, expected_type):
            errors.append({"field": field, "message": f"expected type {expected_type}"})
        enum_values = spec.get("enum")
        if enum_values and value not in enum_values:
            errors.append({"field": field, "message": f"expected one of {enum_values}"})

    return {"ok": len(errors) == 0, "errors": errors}


def validate_plugin_mcp_capabilities(capabilities: dict) -> dict:
    """Validate plugin MCP capabilities contract."""
    errors: List[str] = []
    if not isinstance(capabilities, dict):
        return {"ok": False, "errors": ["capabilities must be an object"]}

    collections = capabilities.get("collections")
    operations = capabilities.get("operations")
    if capabilities.get("entities") and not collections:
        errors.append("entities=true requires non-empty collections")
    if collections is not None and not isinstance(collections, list):
        errors.append("collections must be an array")
    if operations is not None and not isinstance(operations, list):
        errors.append("operations must be an array")

    collection_ids = set()
    if isinstance(collections, list):
        for idx, collection in enumerate(collections):
            if not isinstance(collection, dict):
                errors.append(f"collections[{idx}] must be an object")
                continue
            collection_id = str(collection.get("id") or "").strip()
            if not collection_id:
                errors.append(f"collections[{idx}].id is required")
                continue
            if collection_id in collection_ids:
                errors.append(f"duplicate collection id: {collection_id}")
            collection_ids.add(collection_id)
            binding_mode = str(collection.get("binding_mode") or "none")
            if binding_mode not in {"none", "property", "object"}:
                errors.append(f"collections[{idx}].binding_mode invalid: {binding_mode}")

    return {"ok": len(errors) == 0, "errors": errors}
