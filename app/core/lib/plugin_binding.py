"""Helpers for synchronizing plugin entity bindings with osysHome objects."""

from __future__ import annotations

from typing import Optional, Tuple

from app.core.lib.object import removeLinkFromObject, setLinkToObject
from app.core.main.ObjectsStorage import objects_storage


def _norm(value: Optional[str]) -> str:
    """Normalize optional string (strip; empty if None)."""
    return str(value or "").strip()


def validate_object_exists(object_name: Optional[str]) -> bool:
    """Check that an object name refers to a loadable object.

    Args:
        object_name (str | None): Object name

    Returns:
        bool: True if the object can be loaded
    """
    name = _norm(object_name)
    if not name:
        return False
    return objects_storage.getObjectByName(name) is not None


def validate_object_property_exists(object_name: Optional[str], property_name: Optional[str]) -> bool:
    """Check that ``object.property`` exists on a loadable object.

    Args:
        object_name (str | None): Object name
        property_name (str | None): Property name

    Returns:
        bool: True if the property exists on the object
    """
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
    """Sync ``Value.linked`` for a property-level plugin binding.

    Removes the old link when ``old_object`` / ``old_property`` differ from
    the new target. Adds a new link when both object and property are set.
    Clearing both new names only removes the old link (if any).

    Args:
        plugin_name (str): Plugin / module link name
        object_name (str | None): New linked object
        property_name (str | None): New linked property
        old_object (str | None, optional): Previous linked object
        old_property (str | None, optional): Previous linked property

    Returns:
        tuple[bool, str | None]: ``(success, error_message)``;
            ``error_message`` is None on success
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
    """Remove a property-level plugin link.

    Args:
        plugin_name (str): Plugin / module link name
        object_name (str | None): Object name
        property_name (str | None): Property name

    Returns:
        bool: True if removed or nothing to remove; False on failure
    """
    obj_name = _norm(object_name)
    prop_name = _norm(property_name)
    plugin = _norm(plugin_name)
    if not obj_name or not prop_name or not plugin:
        return True
    return bool(removeLinkFromObject(obj_name, prop_name, plugin))


def sync_object_link(object_name: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validate an object-level binding (no ``Value.linked`` update).

    Args:
        object_name (str | None): Object name (empty clears / no-op)

    Returns:
        tuple[bool, str | None]: ``(success, error_message)``
    """
    name = _norm(object_name)
    if not name:
        return True, None
    if not validate_object_exists(name):
        return False, f"Object not found: {name}"
    return True, None
