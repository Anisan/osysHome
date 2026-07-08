"""Helpers for synchronizing plugin entity bindings with osysHome objects."""

from __future__ import annotations

from typing import Optional, Tuple

from app.core.lib.object import removeLinkFromObject, setLinkToObject
from app.core.main.ObjectsStorage import objects_storage


def _norm(value: Optional[str]) -> str:
    return str(value or "").strip()


def validate_object_exists(object_name: Optional[str]) -> bool:
    """Return True when object_name refers to a loaded object."""
    name = _norm(object_name)
    if not name:
        return False
    return objects_storage.getObjectByName(name) is not None


def validate_object_property_exists(object_name: Optional[str], property_name: Optional[str]) -> bool:
    """Return True when object.property exists."""
    obj_name = _norm(object_name)
    prop_name = _norm(property_name)
    if not obj_name or not prop_name:
        return False
    obj = objects_storage.getObjectByName(obj_name)
    if obj is None:
        return False
    return prop_name in obj.properties


def sync_property_link(
    plugin_name: str,
    object_name: Optional[str],
    property_name: Optional[str],
    old_object: Optional[str] = None,
    old_property: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Sync Value.linked for property-level plugin bindings.

    Removes the old link when old_object/old_property are provided and changed.
    Adds a new link when object_name and property_name are both non-empty.

    Returns:
        (success, error_message)
    """
    plugin = _norm(plugin_name)
    if not plugin:
        return False, "plugin_name is required"

    new_object = _norm(object_name)
    new_property = _norm(property_name)
    prev_object = _norm(old_object)
    prev_property = _norm(old_property)

    if prev_object and prev_property:
        if prev_object != new_object or prev_property != new_property:
            removeLinkFromObject(prev_object, prev_property, plugin)

    if not new_object and not new_property:
        return True, None

    if new_object and not new_property:
        return False, "linked_property is required when linked_object is set"
    if new_property and not new_object:
        return False, "linked_object is required when linked_property is set"

    if not validate_object_property_exists(new_object, new_property):
        return False, f"Object property not found: {new_object}.{new_property}"

    if not setLinkToObject(new_object, new_property, plugin):
        return False, f"Failed to set link for {new_object}.{new_property}"

    return True, None


def remove_property_link(
    plugin_name: str,
    object_name: Optional[str],
    property_name: Optional[str],
) -> bool:
    """Remove property-level link for a plugin."""
    obj_name = _norm(object_name)
    prop_name = _norm(property_name)
    plugin = _norm(plugin_name)
    if not obj_name or not prop_name or not plugin:
        return True
    return bool(removeLinkFromObject(obj_name, prop_name, plugin))


def sync_object_link(object_name: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate object-level binding (no Value.linked update).

    Returns:
        (success, error_message)
    """
    name = _norm(object_name)
    if not name:
        return True, None
    if not validate_object_exists(name):
        return False, f"Object not found: {name}"
    return True, None
